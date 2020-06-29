import rclpy
from rclpy.node import Node

from std_msgs.msg import String
from ros2relay.message_socket.message_socket import MessageSocket

class NetworkPublisher(Node):
    """ ros2relay NetworkPublisher subscribes to a set of topics on the local system and publishes them to the network
    
        Requires that a NetworkSubscriber be running on the target endpoint
    """
    def __init__(self):
        super().__init__('ros2relay_publisher')
        self.declare_parameter('topics')
        print(self.get_parameter('topics').get_parameter_value().string_array_value)
        self.publisher_ = self.create_publisher(String, 'topic', 10)
        timer_period = 0.5  # seconds
        self.timer = self.create_timer(timer_period, self.timer_callback)
        self.i = 0

    def timer_callback(self):
        msg = String()
        msg.data = 'Hello World: %d' % self.i
        self.publisher_.publish(msg)
        self.get_logger().info('Publishing: "%s"' % msg.data)
        self.i += 1


def main(args=None):
    rclpy.init(args=args)

    network_publisher = NetworkPublisher()

    rclpy.spin(network_publisher)

    network_publisher.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()