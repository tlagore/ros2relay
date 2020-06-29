import rclpy
from rclpy.node import Node
from importlib import import_module

#from std_msgs.msg import String
from ros2relay.message_socket.message_socket import MessageSocket

class NetworkPublisher(Node):
    """ ros2relay NetworkPublisher subscribes to a set of topics on the local system and publishes them to the network
    
        Requires that a NetworkSubscriber be running on the target endpoint
    """

    topic_modules = {}
    my_timer_topics = {}
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
                self.listener_callback,
                10
            )
            self.get_logger().info(f'Initializing topic {topics[idx]} with type {msg}')
            self.subscription = self.my_subscriptions[topics[idx]]
            # self.subscription = self.create_subscription(
            # String,
            # 'topic',
            # self.listener_callback,
            # 10)
            # self.subscription  # prevent unused variable warning
        self.get_logger().info('waiting')
        

    def listener_callback(self, msg):
        self.get_logger().info(f'I heard: "{msg.data}"')


def main(args=None):
    rclpy.init(args=args)

    network_publisher = NetworkPublisher()

    rclpy.spin(network_publisher)

    network_publisher.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()