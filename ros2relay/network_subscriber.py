from importlib import import_module
import rclpy
import socket
import threading
import traceback

from ros2relay.message_socket.message_socket import MessageSocket, SocketMessage, MessageType
from ros2relay.message_socket.message_metrics import MessageMetricsHandler

from rclpy.node import Node

class MessageMetrics:
    def __init__(self):
        """ """
        self.byte_sum = 0
        self.message_count = 0

    def increment_message_count(self, message_size):
        self.message_count += 1
        self.byte_sum += message_size

    def get_and_reset_metrics(self):
        m_count = self.message_count
        b_sum = self.byte_sum

        self.message_count = 0
        self.byte_sum = 0

        return (m_count, b_sum)


class MessageMetricsHandler:
    metric_handlers = []
    
    def __init__(self, num_handlers):
        """ """
        for i in range(num_handlers):
            self.metric_handlers.append(MessageMetrics())

    def handle_message(self, handler, message_size):
        if handler > len(self.metric_handlers) - 1 or handler < 0:
            raise ValueError(f"Handler must be between 0 and {len(self.metric_handlers) - 1}")

        self.metric_handlers[handler].increment_message_count(message_size)

    def publish_metrics(self):
        """ """
        # list of tuples (message_count, byte_sum) for each worker
        vals = [m.get_and_reset_metrics() for m in self.metric_handlers]

        # summed tuple, [sum(message_count), sum(byte_sum)]
        sums = [sum(x) for x in zip(*vals)]

        message = f"Messages processed/second: {sums[0]}. KBytes processed/second: {(sums[1] / 1024):.2f}"
        print(message.ljust(len(message)+20), end='')
        print("\r", end='')


class NetworkSubscriber(Node):
    """ 
        ros2relay NetworkSubscriber "subscribes" to the NetworkPublisher and publishes them on the local ros2 network

        expects to receive these events from NetworkPublisher on the remote host
    """
    listener_threads = []
    topic_modules = {}
    sockets = []

    """ [topic] = publisher """
    my_publishers = {}

    def __init__(self):
        super().__init__('ros2relay_net_subscriber')

        self._declare_parameters()
        
        topics = self.get_parameter('topics').get_parameter_value().string_array_value
        topicTypes = self.get_parameter('topicTypes').get_parameter_value().string_array_value
        self.mode = self.get_parameter('mode').get_parameter_value().string_value
        self.port = self.get_parameter('port').get_parameter_value().integer_value
        self.num_listeners = self.get_parameter('num_listeners').get_parameter_value().integer_value

        # loop through topics & import their types dynamically
        for idx, tType in enumerate(topicTypes):
            module_parts = tType.split('.')
            module_name = module_parts[0] + '.' + module_parts[1]
            module = import_module(module_name)
            msg = getattr(module, module_parts[2])
            self.topic_modules[topics[idx]] = msg

            # create publisher for each topic
            self.my_publishers[topics[idx]] = self.create_publisher(
                msg,
                topics[idx],
                10
            )

        self.metric_handler = MessageMetricsHandler(self.num_listeners)

        self.init_socket()

        timer_period = 1  # seconds
        self.metric_publisher = self.create_timer(timer_period, self.metric_handler.publish_metrics)

    def _declare_parameters(self):
        self.declare_parameter('topics')
        self.declare_parameter('topicTypes')
        self.declare_parameter('port')
        self.declare_parameter('mode')
        self.declare_parameter('num_listeners')

    def init_socket(self):
        self.get_logger().info(f'Intializing listener socket on port "{self.port}" - mode: {self.mode}')

        if self.mode == "tcp":
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # note bind is takinga  tuple as one argument
            self._socket.bind(("0.0.0.0", self.port))
            self._running = True
            # tcp has only one worker
            self._listen_thread = threading.Thread(target=self.listen, args=((0,)))
            self._listen_thread.start()
        elif self.mode == "udp":   
            for i in range(0, self.num_listeners):
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

                try:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                except AttributeError as ex:
                    self.get_logger().fatal(f'Error when attempting to set socket to reuse port: {traceback.format_exc()}')
                    raise ex

                sock.bind(("0.0.0.0", self.port))
                self.sockets.append(MessageSocket(sock))
                self._running = True
                self.listener_threads.append(threading.Thread(target=self.listen, args=((i,))))
                self.listener_threads[i].start()
            
            # sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # sock.bind(("0.0.0.0", self.port))
            # self._socket = MessageSocket(sock)

            # for i in range(0, self.num_listeners):
            #     self._running = True
            #     self.listener_threads.append(threading.Thread(target=self.listen, args=((i,))))
            #     self.listener_threads[i].start()
        else:
            raise Exception("Mode parameter must be one of 'udp' or 'tcp'")

    def handle_message(self, msg):
        """ handles a message received by a client """
        # self.my_publishers[msg.topic].publish(msg.payload)

    def handle_client(self, args):
        """  """
        (client, addr) = args
        client_sock = MessageSocket(client)
        try:
            msg = client_sock.recv_message()
            while(msg.type != MessageType.DISCONNECT and self._running):
                self.handle_message(msg)
                msg = client_sock.recv_message()

            if not self._running:
                client_sock.close()
            else:
                print("Client {0} has disconneccted".format(addr[0]))
        except:
            print("Error handling client. Disconnecting from client {0}".format(addr[0]))

            traceback.print_exc()

    def listen(self, worker_id):
        """ listens for clients """

        try:
            if self.mode == "tcp":
                self.get_logger().info(f'Worker {worker_id} listening for clients. Mode={s}')

                while self._running:
                    self._socket.listen(self.num_listeners)
                    (client, addr) = self._socket.accept()
                    self.get_logger().info(f"Worker Got a client {client}")
                    clientThread = threading.Thread(target=self.handle_client, args=((client, addr),))
                    clientThread.start()
            else:
                self.get_logger().info(f'Worker {worker_id} listening for messages. Mode={self.mode}')

                while self._running:
                    (msg, msgSize) = self.sockets[worker_id].recvfrom(65535)
                    if msg is not None:
                        self.metric_handler.handle_message(worker_id, msgSize)
                        self.handle_message(msg)
        except:
            if self._running:
                print("Exception in listen.")
                traceback.print_exc()
            else:
                print("Shutting down")

    def shutdown(self):
        self.get_logger().warning("Received shutdown signal.")
        self._running = False
        self._socket.close()
        for i in range(self.num_listeners):
            self.get_logger().info(f"Joining worker thread {i}")
            listener_threads[i].join(5)

def main(args=None):
    rclpy.init(args=args)
    print(args)

    network_subscriber = NetworkSubscriber()

    try:
        rclpy.spin(network_subscriber)

        network_subscriber.shutdown()
        # Destroy the node explicitly
        # (optional - otherwise it will be done automatically
        # when the garbage collector destroys the node object)
        network_subscriber.destroy_node()
        rclpy.shutdown()
    except Exception as ex:
        traceback.print_exc()
        
        network_subscriber.shutdown()
        network_subscriber.destroy_node()
        rclpy.shutdown()
           


if __name__ == '__main__':
    main()