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

    def __init__(self, socket):
        """constructor for chat client"""
        self._socket = socket
        
    def send_message(self, message):
        """ sends a message to be received by another MessageSocket """
        messageBytes = pickle.dumps(message)

        messageLen = len(messageBytes)
        header = struct.pack("IIII", messageLen, messageLen, messageLen, messageLen)
            
        self._socket.sendall(header)
        self._socket.sendall(messageBytes)

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


    def close(self):
        try:
            self._socket.close()
        except:
            print("!! Error closing socket", file=sys.stderr)
                                    
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
    def cipher(self):
        return self._cipher
