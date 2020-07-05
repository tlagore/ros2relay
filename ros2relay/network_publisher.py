import rclpy
from rclpy.node import Node

from contextlib import contextmanager
from functools import partial, total_ordering
from importlib import import_module
import queue
import socket
from typing import Any
import threading
import traceback
import time

from ros2relay.message_socket.message_socket import MessageSocket, SocketMessage, MessageType
from ros2relay.metrics.metrics import MessageMetricsHandler

# class obtained from combination of https://stackoverflow.com/a/16782490/4089216 and https://stackoverflow.com/a/16782391/4089216
class TimeoutLock(object):
    def __init__(self):
        self._lock = threading.Lock()

    @contextmanager
    def acquire_timeout(self, timeout):
        result = self._lock.acquire(timeout=timeout)
        yield result
        if result:
            self._lock.release()

# class obtained from https://stackoverflow.com/a/54028394/4089216
@total_ordering
class PrioritizedItem:
    def __init__(self, priority, item):
        self.priority = priority
        self.item = item

    def __eq__(self, other):
        if not isinstance(other, __class__):
            return NotImplemented
        return self.priority == other.priority

    def __lt__(self, other):
        if not isinstance(other, __class__):
            return NotImplemented
        return self.priority < other.priority

class NetworkPublisher(Node):
    """ ros2relay NetworkPublisher subscribes to a set of topics on the local system and publishes them to the network
    
        Requires that a NetworkSubscriber be running on the target endpoint
    """

    # priority of the topic, where a lower value indicates a higher priority
    topic_priorities = {}

    topic_sample_rates = {}

    # keep reference to subscriptions
    my_subscriptions = {}

    # each worker thread will have a socket, each worker_id is between 0 and worker_count - 1
    # each workers socket belongs at sockets[worker_id]
    sockets = []
    # locks only used for reconnect on tcp
    socket_locks = []

    # maintain workers to join later
    workers = []

    # need to do some testing with 1000 as max value for priority queue
    message_queue = queue.PriorityQueue(1000)


    def __init__(self):
        super().__init__('ros2relay_net_publisher')

        self._declare_parameters()
        self._set_local_params()

        for idx, tType in enumerate(self.topic_types):
            module_parts = tType.split('.')
            module_name = module_parts[0] + '.' + module_parts[1]
            module = import_module(module_name)
            msg = getattr(module, module_parts[2])
            self.topic_priorities[self.topics[idx]] = self.topic_priority_list[idx]
            self.topic_sample_rates[self.topics[idx]] = self.sample_rates[idx]

            func = partial(self.listener_callback, self.topics[idx])

            self.my_subscriptions[self.topics[idx]] = self.create_subscription(
                msg,
                self.topics[idx],
                func,
                10
            )

            self.get_logger().info(f'Initializing topic "{self.topics[idx]}" : {tType} - sample rate : {self.sample_rates[idx]}')

        self.running = True

        for i in range(0, self.worker_count):
            self.socket_locks.append(TimeoutLock())
            self.init_socket_with_rety(i)

        # as worker threads can access the socket list, initialize workers in separate loop after initial sockets
        # to keep concurrence. Each worker thread only accesses its own position in the array once initialized
        for i in range(0, self.worker_count):
            self.workers.append(threading.Thread(target=self.work, args=((i,))))
            self.workers[i].start()

        self.get_logger().info(f"{self.worker_count} workers started. Sending to {self.host}:{self.port} mode = {self.mode}")

        self.metric_handler = MessageMetricsHandler(num_handlers=self.worker_count, count_drops=True)

        timer_period = 1  # seconds
        self.metric_publisher = self.create_timer(timer_period, self.metric_handler.publish_metrics)

    def _set_local_params(self):
        self.topics = self.get_parameter('topics').get_parameter_value().string_array_value
        self.topic_types = self.get_parameter('topicTypes').get_parameter_value().string_array_value
        self.mode = self.get_parameter('mode').get_parameter_value().string_value 
        self.host = self.get_parameter('server').get_parameter_value().string_value
        self.port = self.get_parameter('port').get_parameter_value().integer_value
        self.topic_priority_list = self.get_parameter('topicPriorities').get_parameter_value().integer_array_value
        sampleRateParam = self.get_parameter('sampleRates').get_parameter_value()
        self.sample_rates = None

        required_params = [
            ('topics', self.topics),
            ('topicTypes', self.topic_types),
            ('mode', self.mode),
            ('host', self.host),
            ('port', self.port)]

        for (paramName, param) in required_params:
            if ((isinstance(param, list) or isinstance(param, str)) and len(param) == 0) or param == 0:
                raise ValueError(f"{paramName} is a required parameter and was not set")

        if not self.topic_priority_list:
            self.topic_priority_list = [0 for topic in self.topics]
            
        if len(self.topics) != len(self.topic_types):
            raise ValueError("topic and topicTypes parameters should be equal in size." +
                                f"topic size: {len(self.topics)}, topicTypes size: {len(self.topic_types)}")

        if len(sampleRateParam.integer_array_value) != 0:
            if len(sampleRateParam.integer_array_value) != len(self.topics):
                raise ValueError('if sampleRates parameter is set as array, length of array must be equal to number of topics')

            self.sample_rates = sampleRateParam.integer_array_value

        print(self.sample_rates)

        if self.sample_rates is None and sampleRateParam.integer_value != 0:
            # same sample rate for each topic
            self.sample_rates = [sampleRateParam.integer_value for topic in self.topics]

        if self.sample_rates is None:
            self.get_logger().info('sample rates was not set, sending all topics data')
            self.sample_rates = [1 for topic in self.topics]

        # if tcp, this value should be less than or equal to the number of clients the net_subscriber can handle
        self.worker_count = self.get_parameter('numWorkers').get_parameter_value().integer_value

    def _declare_parameters(self):
        self.declare_parameter('server')
        self.declare_parameter('port')
        self.declare_parameter('topics')
        self.declare_parameter('topicTypes')
        self.declare_parameter('topicPriorities')
        self.declare_parameter('mode', 'tcp')
        self.declare_parameter('numWorkers')
        self.declare_parameter('sampleRates')
        
    def init_socket_with_rety(self, worker_id):
        """ attempts to initialize the socket with retries for the worker_id. retries is only attempted for tcp connections """

        if self.mode == "tcp":
            # acquire lock for this socket in 100 ms or abandon, another thread is handling the socket reconnect
            with self.socket_locks[worker_id].acquire_timeout(0.1):
                connected = False
                while not connected:
                    try:
                        self._init_socket_tcp(worker_id)
                        connected = True
                        self.get_logger().info('Connection successful!')
                    except Exception as e:
                        self.get_logger().error(f"Error initializing socket exception: {str(e)} worker id {workerId}")
                        for i in range(1, 5):
                            self.get_logger().info(f'Retrying in {5-i}')
                            time.sleep(1)
        elif self.mode == "udp": 
            self._init_socket_udp(worker_id)
        else:
            raise Exception("Mode must be one of 'udp' or 'tcp'")
        
    def _init_socket_tcp(self, worker_id):
        """
        initializes a tcp socket. If the socket was already initialized then it attempts to close the socket before assigning it to our
        active sockets
        """

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.host, self.port))
        if len(self.sockets) - 1 < worker_id:
            self.sockets.append(MessageSocket(sock))
        else:
            # socket was already initialized, MessageSocket implements a try:catch
            self.sockets[worker_id].close()
            self.sockets[worker_id] = MessageSocket(sock)

    def _init_socket_udp(self, worker_id):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        if len(self.sockets) - 1 < worker_id:
            self.sockets.append(MessageSocket(sock, (self.host, self.port)))
        else:
            # socket was already initialized, MessageSocket implements a try:catch
            self.sockets[worker_id].close()
            self.sockets[worker_id] = MessageSocket(sock, (self.host, self.port))

    def work(self, worker_id):
        """
        work thread, retrieve items from the priority queue and send the message
        """

        try:
            while self.running:
                # blocking request - timeout 3 seconds
                messageSent = False
                try:
                    # throws queue.Empty exception if it fails to get an item in 3 seconds
                    priorityItem = self.message_queue.get(True, 3)
                    self.send_message(priorityItem.item, worker_id)
                    messageSent = True

                except (ConnectionResetError, BrokenPipeError, ConnectionResetError) as e:
                    # should maybe record number of times connection breaks? Will get wordy
                    self.get_logger().error(f"Error sending socket message: {str(e)}")
                    self.init_socket_with_rety(worker_id)
                except queue.Empty:
                    priorityItem = None
                    pass
                finally:
                    # give one more attempt at sending the message if we failed
                    if not messageSent and priorityItem is not None:
                        try:
                            self.send_message(priorityItem.item, worker_id)
                        except:
                            pass
        except Exception as ex:
            self.get_logger().error(f"Worker thread {worker_id} exitting unexpectedly with error: {str(ex)}")
        finally:
            self.get_logger().info(f"Worker thread {worker_id} finishing.")


    def listener_callback(self, topic, msg):
        """ 
            attempts to send the message to the remote server 
            if this fails - it will try to re-initialize the socket. The message will attempt
            a single retry on the message, otherwise it will be lost and all subsequent
            messsages until the connection is re-established
        """
        netMessage = SocketMessage(mType=MessageType.MESSAGE, mTopic=topic, mPayload=msg)
        item = PrioritizedItem(priority=self.topic_priorities[topic], item=netMessage)

        try:
            self.message_queue.put_nowait(item)
        except queue.Full as ex:
            ## TODO handle queue full issue - shouldn't hit this too often, we either need more workers or too much data is being sent
            # self.get_logger().error(f'Queue is full! {str(ex)}')
            self.metric_handler.increment_dropped()
        except Exception as ex:
            # some other error
            self.get_logger().error(f'Error queuing message {str(ex)}')

    def send_message(self, message, worker_id):
        if self.mode != 'tcp' and self.mode != 'udp':
            raise Exception(f'Mode is set to {self.mode}. Accepted modes are "udp" or "tcp"')

        if self.mode == 'tcp':
            bytesSent, time_taken = self.sockets[worker_id].send_message(message)
        elif self.mode == 'udp':
            bytesSent, time_taken = self.sockets[worker_id].sendto(message)

        if bytesSent and bytesSent > 0:
            self.metric_handler.handle_message(worker_id, bytesSent, time_taken)
            # time_taken in seconds floating point


    def shutdown(self):
        self.running = False

        for i in range(0, self.worker_count):
            try:
                self.sockets[i].close()
            except Exception as ex:
                self.get_logger().warning(f"Exception closing down worker socket {i}, exception: {str(ex)}")

        for i in range(0, self.worker_count):
            self.get_logger().info(f"Joining worker thread {i}")
            # 5 second wait before skipping thred
            self.workers[i].join(5)


def main(args=None):
    rclpy.init(args=args)

    network_publisher = NetworkPublisher()

    try:
        rclpy.spin(network_publisher)

        network_publisher.shutdown()
        network_publisher.destroy_node()
        rclpy.shutdown()
    except Exception as ex:
        traceback.print_exc()

        print("!! SIGINT received - attempting to clean up remaining threads...please wait...")
        network_publisher.shutdown()
        network_publisher.destroy_node()


if __name__ == '__main__':
    main()
