import rclpy

#ros imports
from rclpy.node import Node
from std_msgs.msg import String
from std_msgs.msg import Int64


class SimplePublisher(Node):
    """ 
        ros2relay NetworkSubscriber "subscribes" to the NetworkPublisher and publishes them on the local ros2 network

        expects to receive these events from NetworkPublisher on the remote host
    """

    topic_modules = {}
    my_publishers = {}

    def __init__(self):
        super().__init__('simple_publisher')
        self.publisher_1 =  self.create_publisher(
                String,
                "topic",
                10
            )
        self.publisher_2 =  self.create_publisher(
                Int64,
                "topic_num",
                10
            )

        timer_period = 0.5  # seconds
        self.timer = self.create_timer(timer_period, self.timer_callback)
        self.i = 0

    def timer_callback(self):
        msg = String()
        msg.data = "Hello there " + str(self.i) + "!"
        self.publisher_1.publish(msg)

        msg2 = Int64()
        msg2.data = self.i*2
        self.publisher_2.publish(msg2)

        self.get_logger().info(f'Publishing: "{msg.data}"')
        self.get_logger().info(f'Publishing "{msg2.data}"')

        self.i += 1

def main(args=None):
    rclpy.init(args=args)
    print(args)

    simple_publisher = SimplePublisher()

    rclpy.spin(simple_publisher)

    # Destroy the node explicitly
    # (optional - otherwise it will be done automatically
    # when the garbage collector destroys the node object)
    simple_publisher.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()