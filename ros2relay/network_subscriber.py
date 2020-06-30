from importlib import import_module
import rclpy
import socket
import threading

from ros2relay.message_socket.message_socket import MessageSocket, SocketMessage, MessageType

#ros imports
from rclpy.node import Node
#from std_msgs.msg import String
#from std_msgs.msg import Int64


class NetworkSubscriber(Node):
    """ 
        ros2relay NetworkSubscriber "subscribes" to the NetworkPublisher and publishes them on the local ros2 network

        expects to receive these events from NetworkPublisher on the remote host
    """

    topic_modules = {}
    my_publishers = {}

    def __init__(self):
        super().__init__('ros2relay_net_subscriber')
        self.declare_parameter('topics')
        self.declare_parameter('topicTypes')
        self.declare_parameter('port')
        topics = self.get_parameter('topics').get_parameter_value().string_array_value
        topicTypes = self.get_parameter('topicTypes').get_parameter_value().string_array_value

        print(topicTypes)
        print(topics)

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

        self.init_socket()

        # timer_period = 0.5  # seconds
        # self.timer = self.create_timer(timer_period, self.timer_callback)
        self.i = 0

    def init_socket(self):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.port = self.get_parameter('port').get_parameter_value().integer_value
        self.get_logger().info(f'Intializing listener socket on port "{port}"')
        # note bind is takinga  tuple as one argument
        self._socket.bind(("0.0.0.0", self.port))
        self._running = Trues
        self._listen_thread = threading.Thread(target=self.listen)
        self._listen_thread.start()

    def timer_callback(self):
        idx = 1
        for topic, publisher in self.my_publishers.items():
            # the message type
            msg = self.topic_modules[topic]()
            msg.data = type(msg.data)(self.i * idx)
            publisher.publish(msg)
            self.get_logger().info(f'Publishing: on topic "{topic}" : "{msg.data}"')
            idx+=1

        self.i += 1

    def handle_message(self, client, msg):
        """ handles a message received by a client """
        print("from client {0}, payload: {1}".format(client, msg.payload))

    def handle_client(self, args):
        """  """
        (client, addr) = args
        client_sock = MessageSocket(client)
        try:
            msg = client_sock.recv_message()
            while(msg.type != MessageType.DISCONNECT and self._running):
                self.handle_message(client, msg)
                msg = client_sock.recv_message()

            if not self._running:
                client_sock.close()
            else:
                print("Client {0} has disconneccted".format(addr[0]))
        except:
            print("Error handling client in PiLogee.work. Disconnecting from client {0}".format(addr[0]))

            # traceback.print_exc()


    def listen(self):
        """ listens for clients """
        try:
            while(self._running):
                self._socket.listen(5)
                (client, addr) = self._socket.accept()
                clientThread = threading.Thread(target=self.handle_client, args=((client, addr),))
                clientThread.start()
        except:
            if self._running:
                print("Exception in listen.")
                traceback.print_exc()
            else:
                print("Shutting down")

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