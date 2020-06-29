import rclpy
from rclpy.node import Node

from std_msgs.msg import String
from std_msgs.msg import Int64


class NetworkSubscriber(Node):
    """ 
        ros2relay NetworkSubscriber "subscribes" to the NetworkPublisher and publishes them on the local ros2 network

        expects to receive these events from NetworkPublisher on the remote host
    """
    def __init__(self):
        super().__init__('ros2relay_net_subscriber')
        self.publisher_ = self.create_publisher(String, 'topic', 10)
        self.publisher2 = self.create_publisher(Int64, 'num_topic', 10)
        timer_period = 0.5  # seconds
        self.timer = self.create_timer(timer_period, self.timer_callback)
        self.i = 0

    def timer_callback(self):
        msg = String()
        msg.data = 'Hello World: %d' % self.i
        self.publisher_.publish(msg)
        self.get_logger().info('Publishing: "%s"' % msg.data)

        numMsg = Int64()
        numMsg.data = self.i * 2
        self.publisher2.publish(numMsg)
        self.get_logger().info(f'Publishing num: "{numMsg.data}"')

        self.i += 1


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