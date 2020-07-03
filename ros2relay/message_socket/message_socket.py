from enum import Enum
import os
import pickle
import platform
import socket
import struct
import sys
import threading
import time

class MessageSocket:
    """Reliable socket to ensure delivery of Messages """

    def __init__(self, socket, host=None):
        """constructor for MessageSocket client
        
        socket: An initialized socket
        host: (host, port) tuple of the binding if a server socket
        """
        self._socket = socket
        self._host = host
        
    def send_message(self, message):
        """ sends a message to be received by another MessageSocket """
        messageBytes = pickle.dumps(message)

        messageLen = len(messageBytes)
        header = struct.pack("IIII", messageLen, messageLen, messageLen, messageLen)
            
        self._socket.sendall(header)
        self._socket.sendall(messageBytes)

        return len(messageBytes)

    def recv_message(self):
        """ Receives a message and returns it unpickled """
        
        header = self.recvall(16) 

        messageSize = self.get_msg_size(header)
        messageBytes = self.recvall(messageSize)
        
        message = pickle.loads(messageBytes)
        return message

    def send_raw(self, data):
        """ """
        self._socket.sendall(data)


    def recv_raw(self, amount):
        """ """
        messageBytes = self.recvall(amount)
        return messageBytes

    def get_msg_size(self, header):
        """ unpacks header information and returns the length of the message """
        return struct.unpack("IIII", header)[0]
    
    def recvall(self, length):
        """ receives as many bytes as length from socket """
        data = bytes([])
        while len(data) < length:
            packet = self._socket.recv(length - len(data))
            if not packet:
                return None
            data+= packet
        return data

    def sendto(self, message):
        messageBytes = pickle.dumps(message)
        self._socket.sendto(messageBytes, self._host)
        return len(messageBytes)

    def recvfrom(self, numBytes):
        (data, address) = self._socket.recvfrom(numBytes)
        try:
            messageSize = len(data)
            message = pickle.loads(data)
            return (message, messageSize)
        except:
            return (None, None)
        #return self._socket.recvfrom(numBytes)

    def close(self):
        try:
            self._socket.close()
        except Exception as ex:
            print(f"!! Error closing socket {ex}", file=sys.stderr)
                                    
    def __del__(self):
        """destructor for chat client"""
        try:
            self._socket.close()
        except:
            print("Error closing socket", file=sys.stderr)


class MessageError(Exception):
    def __init__(self, message):
        self._message = message

    def __str__(self):
        return repr(self._message)

class MessageType(Enum):
    HANDSHAKE = 0
    MESSAGE = 1
    DISCONNECT = 2

class SocketMessage:
    """ """
    def __init__(self, mType=None, mTopic=None, mPayload=None):
        if mType is None:
            raise MessageError("Object of type 'SocketMessage' must be assigned a type.")

        if mPayload is None:
            raise MessageError("Object of type 'SocketMessage' cannot have an empty payload.")

        if mTopic is None:
            raise MessageError("Object of type 'SocketMessage' cannot have an empty topic.")

        self._type = mType
        self._topic = mTopic
        self._payload = mPayload

    @property
    def type(self):
        return self._type

    @property
    def payload(self):
        return self._payload

    @property
    def topic(self):
        return self._topic
