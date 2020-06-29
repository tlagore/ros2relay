import rclpy
from rclpy.node import Node
from importlib import import_module

# from std_msgs.msg import String
from ros2relay.message_socket.message_socket import MessageSocket

class NetworkPublisher(Node):
    """ ros2relay NetworkPublisher subscribes to a set of topics on the local system and publishes them to the network
    
        Requires that a NetworkSubscriber be running on the target endpoint
    """

    topic_modules = {}
    timers = {}

    def __init__(self):
        super().__init__('ros2relay_publisher')
        self.declare_parameter('topics')
        self.declare_parameter('topicTypes')
        topics = self.get_parameter('topics').get_parameter_value().string_array_value
        topicTypes = self.get_parameter('topicTypes').get_parameter_value().string_array_value

        timer_period = 1.5  # seconds

        for idx, tType in enumerate(topicTypes):
            module_parts = tType.split('.')
            module_name = module_parts[0] + '.' + module_parts[1]
            module = import_module(module_name)
            msg = getattr(module, module_parts[2])
            self.topic_modules[topics[idx]] = msg
            self.publisher_ = self.create_publisher(msg, topics[idx], 10)
            timer = self.create_timer(timer_period, self.timer_callback)
            self.timers[timer] = topics[idx] 

        self.i = 0

    def timer_callback(self):
        # print(topicName)
        msg = self.topic_modules['topic']()
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