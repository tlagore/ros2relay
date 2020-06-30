from importlib import import_module
import rclpy
import socket
import threading
import traceback

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
    listener_threads = []
    topic_modules = {}
    my_publishers = {}

    def __init__(self):
        super().__init__('ros2relay_net_subscriber')

        self._declare_parameters()
        
        topics = self.get_parameter('topics').get_parameter_value().string_array_value
        topicTypes = self.get_parameter('topicTypes').get_parameter_value().string_array_value
        self.mode = self.get_parameter('mode').get_parameter_value().string_value
        self.port = self.get_parameter('port').get_parameter_value().integer_value
        self.num_listeners = self.get_parameter('num_listeners').get_parameter_value().integer_value

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

        self.i = 0

    def _declare_parameters(self):
        self.declare_parameter('topics')
        self.declare_parameter('topicTypes')
        self.declare_parameter('port')
        self.declare_parameter('mode')
        self.declare_parameter('num_listeners')

    def init_socket(self):
        self.get_logger().info(f'Intializing listener socket on port "{self.port}" - mode: {self.mode}')

        if self.mode == "tcp":
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # note bind is takinga  tuple as one argument
            self._socket.bind(("0.0.0.0", self.port))
            self._running = True
            self._listen_thread = threading.Thread(target=self.listen)
            self._listen_thread.start()
        elif self.mode == "udp":
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(("0.0.0.0", self.port))
            self._socket = MessageSocket(sock)
            self._running = True
            for i in range(0, self.num_listeners):
                self.listener_threads.append(threading.Thread(target=self.listen))
                self.listener_threads[i].start()
        else:
            raise Exception("Mode parameter must be one of 'udp' or 'tcp'")

    def handle_message(self, msg):
        """ handles a message received by a client """
        print("topic: {0} payload: {1}".format(msg.topic, msg.payload.data))

    def handle_client(self, args):
        """  """
        (client, addr) = args
        client_sock = MessageSocket(client)
        try:
            msg = client_sock.recv_message()
            while(msg.type != MessageType.DISCONNECT and self._running):
                self.handle_message(msg)
                msg = client_sock.recv_message()

            if not self._running:
                client_sock.close()
            else:
                print("Client {0} has disconneccted".format(addr[0]))
        except:
            print("Error handling client in PiLogee.work. Disconnecting from client {0}".format(addr[0]))

            traceback.print_exc()

    def listen(self):
        """ listens for clients """

        self.get_logger().info('Listening for clients')

        try:
            if self.mode == "tcp":
                while self._running:
                    self._socket.listen(5)
                    (client, addr) = self._socket.accept()
                    clientThread = threading.Thread(target=self.handle_client, args=((client, addr),))
                    clientThread.start()
            else:
                while self._running:
                    msg = self._socket.recvfrom(2048)
                    self.get_logger().info(f'Got message')
                    if msg is not None:
                        self.handle_message(msg)
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