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

    topic_priorities = {}
    # keep reference to subscriptions
    my_subscriptions = {}
    sockets = []
    workers = []
    message_queue = queue.PriorityQueue(1000)


    def __init__(self):
        super().__init__('ros2relay_net_publisher')

        self._declare_parameters()
        
        topics = self.get_parameter('topics').get_parameter_value().string_array_value
        topicTypes = self.get_parameter('topicTypes').get_parameter_value().string_array_value
        self.mode = self.get_parameter('mode').get_parameter_value().string_value 
        self.host = self.get_parameter('server').get_parameter_value().string_value
        self.port = self.get_parameter('port').get_parameter_value().integer_value
        self.topic_priorities = self.get_parameter('topicPriorities').get_parameter_value().integer_array_value

        # if tcp, this value should be less than or equal to the number of clients the net_subscriber can handle
        # currently hardcoded at 20
        self.worker_count = 20

        for idx, tType in enumerate(topicTypes):
            module_parts = tType.split('.')
            module_name = module_parts[0] + '.' + module_parts[1]
            module = import_module(module_name)
            msg = getattr(module, module_parts[2])

            func = partial(self.listener_callback, topics[idx])

            self.my_subscriptions[topics[idx]] = self.create_subscription(
                msg,
                topics[idx],
                func,
                10
            )

            self.get_logger().info(f'Initializing topic {topics[idx]} with type {tType}')

        self.running = True

        for i in range(0, self.worker_count):
            self.init_socket_with_rety(i)

        # as worker threads can access the socket list, initialize workers in separate loop after initial sockets
        # to keep concurrence. Each worker thread only accesses its own position in the array once initialized
        for i in range(0, self.worker_count):
            self.workers.append(threading.Thread(target=self.work, args=((i,))))
            self.workers[i].start()


    def _declare_parameters(self):
        self.declare_parameter('server')
        self.declare_parameter('port')
        self.declare_parameter('topics')
        self.declare_parameter('topicTypes')
        self.declare_parameter('topicPriorities')
        self.declare_parameter('mode')

    def init_socket_with_rety(self, worker_id):
        """ attempts to initialize the socket with retries. Acquires connection lock so only one thread  """

        if self.mode == "tcp":
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
        initializes a tcp socket. If the socket was already initialized then it attempts to close the socket before assigning it as our active socket
        """

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.host, self.port))
        if len(self.sockets) < worker_id:
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
        self.get_logger().info(f"Worker {worker_id} starting work")

        try:
            while self.running:
                # blocking request - timeout 3 seconds
                messageSent = False
                try:
                    priorityItem = self.message_queue.get(True, 3)
                    self.send_message(priorityItem.item, worker_id)
                    messageSent = True
                except (ConnectionResetError, BrokenPipeError, ConnectionResetError) as e:
                    self.get_logger().error(f"Error sending socket message: {str(e)}")
                    self.init_socket_with_rety(worker_id)
                except queue.Empty:
                    pass
                finally:
                    # give one more attempt at sending the message if we failed
                    if not messageSent:
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
            ## TODO handle queue full issue - shouldn't hit this too often
            self.get_logger().error(f'Error queuing message {str(ex)}')
        except:
            # some other error
            self.get_logger().error(f'Error queuing message {str(ex)}')

    def send_message(self, message, worker_id):
        if self.mode == "tcp":
            self.sockets[worker_id].send_message(message)
        elif self.mode == "udp":
            self.sockets[worker_id].sendto(message)

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
    except:
        print("!! SIGINT received - attempting to clean up remaining threads...please wait...")
        network_publisher.shutdown()
        network_publisher.destroy_node()


if __name__ == '__main__':
    main()
