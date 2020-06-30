import rclpy
from rclpy.node import Node
from importlib import import_module
import socket
import traceback

#from std_msgs.msg import String
from ros2relay.message_socket.message_socket import MessageSocket, SocketMessage, MessageType

class NetworkPublisher(Node):
    """ ros2relay NetworkPublisher subscribes to a set of topics on the local system and publishes them to the network
    
        Requires that a NetworkSubscriber be running on the target endpoint
    """

    topic_modules = {}
    my_subscriptions = {}

    def __init__(self):
        super().__init__('ros2relay_net_publisher')
        self.declare_parameter('topics')
        self.declare_parameter('topicTypes')
        topics = self.get_parameter('topics').get_parameter_value().string_array_value
        topicTypes = self.get_parameter('topicTypes').get_parameter_value().string_array_value

        timer_period = 1.5  # seconds

        print(topicTypes)
        print(topics)

        for idx, tType in enumerate(topicTypes):
            module_parts = tType.split('.')
            module_name = module_parts[0] + '.' + module_parts[1]
            module = import_module(module_name)
            msg = getattr(module, module_parts[2])
            self.topic_modules[topics[idx]] = msg

            self.my_subscriptions[topics[idx]] = self.create_subscription(
                msg,
                topics[idx],
                lambda msg : self.listener_callback(msg, topics[idx]),
                #self.listener_callback,
                10
            )
            self.get_logger().info(f'Initializing topic {topics[idx]} with type {msg}')
            self.subscription = self.my_subscriptions[topics[idx]]      

        self.init_socket()  

    def init_socket(self):
        try:
            self.declare_parameter('server')
            self.declare_parameter('port')
            self.host = self.get_parameter('server').get_parameter_value().string_value
            self.port = self.get_parameter('port').get_parameter_value().integer_value
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.host, self.port))
            self._socket = MessageSocket(sock)
        except:
            print("error initializing socket")
            traceback.print_exc()


    def listener_callback(self, msg, topic):
        netMessage = SocketMessage(mType=MessageType.MESSAGE, mTopic=topic, mPayload=msg)
        self.get_logger().info(f'I heard: "{msg.data}" on topic "{topic}"')
        self._socket.send_message(netMessage)


def main(args=None):
    rclpy.init(args=args)

    network_publisher = NetworkPublisher()

    rclpy.spin(network_publisher)

    network_publisher.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()