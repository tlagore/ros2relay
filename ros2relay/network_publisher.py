import rclpy
from rclpy.node import Node

from contextlib import contextmanager
from functools import partial
from importlib import import_module
import socket
import threading
import traceback
import time

from std_msgs.msg import String,Int64
from ros2relay.message_socket.message_socket import MessageSocket, SocketMessage, MessageType

class NetworkPublisher(Node):
    """ ros2relay NetworkPublisher subscribes to a set of topics on the local system and publishes them to the network
    
        Requires that a NetworkSubscriber be running on the target endpoint
    """

    connection_lock = threading.Lock()
    topic_modules = {}
    my_subscriptions = {}

    def __init__(self):
        super().__init__('ros2relay_net_publisher')

        self._declare_parameters()
        
        topics = self.get_parameter('topics').get_parameter_value().string_array_value
        topicTypes = self.get_parameter('topicTypes').get_parameter_value().string_array_value
        self.mode = self.get_parameter('mode').get_parameter_value().string_value 
        self.host = self.get_parameter('server').get_parameter_value().string_value
        self.port = self.get_parameter('port').get_parameter_value().integer_value

        self.init_socket_with_rety() 

        for idx, tType in enumerate(topicTypes):
            module_parts = tType.split('.')
            module_name = module_parts[0] + '.' + module_parts[1]
            module = import_module(module_name)
            msg = getattr(module, module_parts[2])
            self.topic_modules[topics[idx]] = msg

            func = partial(self.listener_callback, topics[idx])

            self.my_subscriptions[topics[idx]] = self.create_subscription(
                msg,
                topics[idx],
                func,
                #lambda input : self.listener_callback(input, topics[idx]),
                10
            )
            self.get_logger().info(f'Initializing topic {topics[idx]} with type ')

    
    def _declare_parameters(self):
        self.declare_parameter('server')
        self.declare_parameter('port')
        self.declare_parameter('topics')
        self.declare_parameter('topicTypes')
        self.declare_parameter('mode')

    @contextmanager
    def acquire_timeout(self, lock, timeout):
        result = lock.acquire(timeout=timeout)
        yield result
        if result:
            lock.release()

    def init_socket_with_rety(self):
        """ attempts to initialize the socket with retries. Acquires connection lock so only one thread  """

        if self.mode == "tcp":
            # if we can't acquire the lock in 100ms, abort - don't tie up threads
            with self.acquire_timeout(self.connection_lock, 0.1):
                connected = False
                while not connected:
                    try:
                        self._init_socket()
                        connected = True
                        self.get_logger().info('Connection successful!')
                    except Exception as e:
                        self.get_logger().error(f"Error initializing socket exception: {str(e)}")
                        for i in range(1, 5):
                            self.get_logger().info(f'Retrying in {5-i}')
                            time.sleep(1)
        elif self.mode == "udp": 
            self._init_socket_udp()
        else:
            raise Exception("Mode must be one of 'udp' or 'tcp'")
        
    def _init_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.host, self.port))
        self._socket = MessageSocket(sock)

    def _init_socket_udp(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket = MessageSocket(sock, (self.host, self.port))

    def listener_callback(self, topic, msg):
        """ 
            attempts to send the message to the remote server 
            if this fails - it will try to re-initialize the socket. The message will attempt
            a single retry on the message, otherwise it will be lost and all subsequent
            messsages until the connection is re-established
        """
        messageSent = False

        netMessage = SocketMessage(mType=MessageType.MESSAGE, mTopic=topic, mPayload=msg)
        self.get_logger().info(f'I heard: "{msg.data}" on topic "{topic}"')
        try:
            self.send_message(netMessage)
            messageSent = True
        except (ConnectionResetError, BrokenPipeError, ConnectionResetError) as e:
            self.get_logger().error(f"Error sending socket message: {str(e)}")
            self.init_socket_with_rety()
        finally:
            # give one more attempt at sending the message if we failed
            if not messageSent:
                try:
                    self.send_message(netMessage)
                except:
                    pass

    def send_message(self, message):
        if self.mode == "tcp":
            self._socket.send_message(message)
        else:
            self._socket.sendto(message)


def main(args=None):
    rclpy.init(args=args)

    network_publisher = NetworkPublisher()

    rclpy.spin(network_publisher)

    network_publisher.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()