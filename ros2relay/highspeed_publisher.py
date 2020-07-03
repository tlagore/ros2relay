import rclpy

import threading
import time
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
        super().__init__('highspeed_publisher')
        self.publisher_2 =  self.create_publisher(
                Int64,
                "topic_num",
                10
            )

        self.publisher_1 =  self.create_publisher(
                String,
                "topic",
                10
            )
        
        self.spawner_threads = []
        self.spawner_threads.append(threading.Thread(target=self.hi_pri_work))
        self.spawner_threads.append(threading.Thread(target=self.low_pri_work))

        for i in range(2):
            self.spawner_threads[i].start()

    def low_pri_work(self):
        msg = String()
        msg.data = "This is a message with a higher priority, it also has a higher amount of data."
        while True:
            self.publisher_1.publish(msg)
            time.sleep(0.001)

    def hi_pri_work(self):
        msg = Int64()
        msg.data = 29481
        while True:
            self.publisher_2.publish(msg)
            time.sleep(0.2)

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