import rclpy
from rclpy.node import Node

from std_msgs.msg import String


class NetworkSubscriber(Node):
    """ 
        ros2relay NetworkSubscriber "subscribes" to the NetworkPublisher and publishes them on the local ros2 network

        expects to receive these events from NetworkPublisher on the remote host
    """
    def __init__(self):
        super().__init__('ros2relay_subscriber')
        self.declare_parameter('topics')
        self.declare_parameter('topicTypes')
        print(self.get_parameter('topics').get_parameter_value().string_array_value)
        print(self.get_parameter('topicTypes').get_parameter_value().string_array_value)
        
        self.subscription = self.create_subscription(
            String,
            'topic',
            self.listener_callback,
            10)
        self.subscription  # prevent unused variable warning

    def listener_callback(self, msg):
        self.get_logger().info('I heard: "%s"' % msg.data)


def main(args=None):
    rclpy.init(args=args)
    print(args)

    network_subscriber = NetworkSubscriber()

    rclpy.spin(network_subscriber)

    # Destroy the node explicitly
    # (optional - otherwise it will be done automatically
    # when the garbage collector destroys the node object)
    network_subscriber.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()