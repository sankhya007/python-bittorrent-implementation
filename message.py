import random
import socket
import struct
import bitstring
import logging
import asyncio


class WrongMessageException(Exception):
    pass


class MessageDispatcher:
    def __init__(self, payload):
        self.payload = payload

    def dispatch(self):
        try:
            payload_length, message_id = struct.unpack(">IB", self.payload[:5])
        except Exception as e:
            logging.warning(f"Error when unpacking message: {e}")
            return None

        map_id_to_message = {
            0: Choke,
            1: UnChoke,
            2: Interested,
            3: NotInterested,
            4: Have,
            5: BitField,
            6: Request,
            7: Piece,
            8: Cancel,
            9: Port 
        }

        if message_id not in map_id_to_message:
            raise WrongMessageException("Wrong message id")

        return map_id_to_message[message_id].from_bytes(self.payload)


class Message:
    def to_bytes(self):
        raise NotImplementedError()

    @classmethod
    def from_bytes(cls, payload):
        raise NotImplementedError()


# Handshake Constants
HANDSHAKE_PSTR_V1 = b"BitTorrent protocol"
HANDSHAKE_PSTR_LEN = len(HANDSHAKE_PSTR_V1)


class Handshake(Message):
    payload_length = 68
    total_length = payload_length

    def __init__(self, info_hash, peer_id=b'-PC0001-000000000000'):
        super().__init__()
        self.info_hash = info_hash
        self.peer_id = peer_id

    def to_bytes(self):
        reserved = b'\x00' * 8
        return struct.pack(f">B{HANDSHAKE_PSTR_LEN}s8s20s20s",
                          HANDSHAKE_PSTR_LEN,
                          HANDSHAKE_PSTR_V1,
                          reserved,
                          self.info_hash,
                          self.peer_id)

    @classmethod
    def from_bytes(cls, payload):
        pstrlen, = struct.unpack(">B", payload[:1])
        pstr, reserved, info_hash, peer_id = struct.unpack(
            f">{pstrlen}s8s20s20s", payload[1:cls.total_length])
        return Handshake(info_hash, peer_id)


class KeepAlive(Message):
    payload_length = 0
    total_length = 4

    def to_bytes(self):
        return struct.pack(">I", self.payload_length)

    @classmethod
    def from_bytes(cls, payload):
        payload_length = struct.unpack(">I", payload[:cls.total_length])[0]
        if payload_length != 0:
            raise WrongMessageException("Not a Keep Alive message")
        return KeepAlive()


class Choke(Message):
    message_id = 0
    payload_length = 1
    total_length = 5

    def to_bytes(self):
        return struct.pack(">IB", self.payload_length, self.message_id)

    @classmethod
    def from_bytes(cls, payload):
        payload_length, message_id = struct.unpack(">IB", payload[:cls.total_length])
        if message_id != cls.message_id:
            raise WrongMessageException("Not a Choke message")
        return Choke()


class UnChoke(Message):
    message_id = 1
    payload_length = 1
    total_length = 5

    def to_bytes(self):
        return struct.pack(">IB", self.payload_length, self.message_id)

    @classmethod
    def from_bytes(cls, payload):
        payload_length, message_id = struct.unpack(">IB", payload[:cls.total_length])
        if message_id != cls.message_id:
            raise WrongMessageException("Not an UnChoke message")
        return UnChoke()


class Interested(Message):
    message_id = 2
    payload_length = 1
    total_length = 5

    def to_bytes(self):
        return struct.pack(">IB", self.payload_length, self.message_id)

    @classmethod
    def from_bytes(cls, payload):
        payload_length, message_id = struct.unpack(">IB", payload[:cls.total_length])
        if message_id != cls.message_id:
            raise WrongMessageException("Not an Interested message")
        return Interested()


class NotInterested(Message):
    message_id = 3
    payload_length = 1
    total_length = 5

    def to_bytes(self):
        return struct.pack(">IB", self.payload_length, self.message_id)

    @classmethod
    def from_bytes(cls, payload):
        payload_length, message_id = struct.unpack(">IB", payload[:cls.total_length])
        if message_id != cls.message_id:
            raise WrongMessageException("Not a NotInterested message")
        return NotInterested()


class Have(Message):
    message_id = 4
    payload_length = 5
    total_length = 9

    def __init__(self, piece_index):
        super().__init__()
        self.piece_index = piece_index

    def to_bytes(self):
        return struct.pack(">IBI", self.payload_length, self.message_id, self.piece_index)

    @classmethod
    def from_bytes(cls, payload):
        payload_length, message_id, piece_index = struct.unpack(">IBI", payload[:cls.total_length])
        if message_id != cls.message_id:
            raise WrongMessageException("Not a Have message")
        return Have(piece_index)


class BitField(Message):
    message_id = 5

    def __init__(self, bitfield):
        super().__init__()
        self.bitfield = bitfield
        self.bitfield_as_bytes = bitfield.tobytes()
        self.bitfield_length = len(self.bitfield_as_bytes)
        self.payload_length = 1 + self.bitfield_length
        self.total_length = 4 + self.payload_length

    def to_bytes(self):
        return struct.pack(f">IB{self.bitfield_length}s",
                          self.payload_length,
                          self.message_id,
                          self.bitfield_as_bytes)

    @classmethod
    def from_bytes(cls, payload):
        payload_length, message_id = struct.unpack(">IB", payload[:5])
        bitfield_length = payload_length - 1
        
        if message_id != cls.message_id:
            raise WrongMessageException("Not a BitField message")
            
        raw_bitfield = struct.unpack(f"{bitfield_length}s", payload[5:5 + bitfield_length])[0]
        bitfield = bitstring.BitArray(bytes=raw_bitfield)
        return BitField(bitfield)


class Request(Message):
    message_id = 6
    payload_length = 13
    total_length = 17

    def __init__(self, piece_index, block_offset, block_length):
        super().__init__()
        self.piece_index = piece_index
        self.block_offset = block_offset
        self.block_length = block_length

    def to_bytes(self):
        return struct.pack(">IBIII",
                          self.payload_length,
                          self.message_id,
                          self.piece_index,
                          self.block_offset,
                          self.block_length)

    @classmethod
    def from_bytes(cls, payload):
        payload_length, message_id, piece_index, block_offset, block_length = struct.unpack(
            ">IBIII", payload[:cls.total_length])
        if message_id != cls.message_id:
            raise WrongMessageException("Not a Request message")
        return Request(piece_index, block_offset, block_length)


class Piece(Message):
    message_id = 7

    def __init__(self, piece_index, block_offset, block):
        super().__init__()
        self.piece_index = piece_index
        self.block_offset = block_offset
        self.block = block
        self.block_length = len(block)
        self.payload_length = 9 + self.block_length
        self.total_length = 4 + self.payload_length

    def to_bytes(self):
        return struct.pack(f">IBII{self.block_length}s",
                          self.payload_length,
                          self.message_id,
                          self.piece_index,
                          self.block_offset,
                          self.block)

    @classmethod
    def from_bytes(cls, payload):
        if len(payload) < 13:
            raise WrongMessageException("Piece message too short")
            
        payload_length, message_id, piece_index, block_offset = struct.unpack(">IBII", payload[:13])
        block_length = payload_length - 9
        
        if message_id != cls.message_id:
            raise WrongMessageException("Not a Piece message")
            
        block = payload[13:13 + block_length]
        return Piece(piece_index, block_offset, block)


class Cancel(Message):
    message_id = 8
    payload_length = 13
    total_length = 17

    def __init__(self, piece_index, block_offset, block_length):
        super().__init__()
        self.piece_index = piece_index
        self.block_offset = block_offset
        self.block_length = block_length

    def to_bytes(self):
        return struct.pack(">IBIII",
                          self.payload_length,
                          self.message_id,
                          self.piece_index,
                          self.block_offset,
                          self.block_length)

    @classmethod
    def from_bytes(cls, payload):
        payload_length, message_id, piece_index, block_offset, block_length = struct.unpack(
            ">IBIII", payload[:cls.total_length])
        if message_id != cls.message_id:
            raise WrongMessageException("Not a Cancel message")
        return Cancel(piece_index, block_offset, block_length)
    
    
class Port(Message):
        """
        PORT = <length><message id><port number>
            - length = 5 (4 bytes)
            - message id = 9 (1 byte)
            - port number = listen_port (4 bytes)
        """
        message_id = 9
        payload_length = 5
        total_length = 9

        def __init__(self, listen_port):
            super().__init__()
            self.listen_port = listen_port

        def to_bytes(self):
            return struct.pack(">IBI",
                            self.payload_length,
                            self.message_id,
                            self.listen_port)

        @classmethod
        def from_bytes(cls, payload):
            payload_length, message_id, listen_port = struct.unpack(">IBI", payload[:cls.total_length])
            
            if message_id != cls.message_id:
                raise WrongMessageException("Not a Port message")
                
            return Port(listen_port)
        
class UdpTrackerConnection:
    """
    UDP tracker connection message
    """
    def __init__(self):
        self.action = 0  # 0 for connect
        self.transaction_id = random.randint(0, 0xFFFFFFFF)
        self.connection_id = None

    def to_bytes(self):
        # Protocol: <connection_id (64)><action (32)><transaction_id (32)>
        # For initial connect, connection_id is the magic constant
        conn_id = struct.pack('>Q', 0x41727101980)  # Magic constant
        action = struct.pack('>I', self.action)
        trans_id = struct.pack('>I', self.transaction_id)
        return conn_id + action + trans_id

    def from_bytes(self, payload):
        # Response: <action (32)><transaction_id (32)><connection_id (64)>
        self.action = struct.unpack('>I', payload[0:4])[0]
        self.transaction_id = struct.unpack('>I', payload[4:8])[0]
        self.connection_id = struct.unpack('>Q', payload[8:16])[0]
        return self


class UdpTrackerAnnounce:
    """
    UDP tracker announce message
    """
    def __init__(self, connection_id, info_hash, peer_id, downloaded=0, left=0, uploaded=0, event=0):
        self.connection_id = connection_id
        self.action = 1  # 1 for announce
        self.transaction_id = random.randint(0, 0xFFFFFFFF)
        self.info_hash = info_hash
        self.peer_id = peer_id
        self.downloaded = downloaded
        self.left = left
        self.uploaded = uploaded
        self.event = event  # 0: none, 1: completed, 2: started, 3: stopped

    def to_bytes(self):
        # Protocol: <connection_id (64)><action (32)><transaction_id (32)><info_hash (20)>
        #           <peer_id (20)><downloaded (64)><left (64)><uploaded (64)><event (32)>
        #           <ip (32)><key (32)><num_want (32)><port (16)>
        msg = struct.pack('>Q', self.connection_id)
        msg += struct.pack('>I', self.action)
        msg += struct.pack('>I', self.transaction_id)
        msg += self.info_hash
        msg += self.peer_id
        msg += struct.pack('>Q', self.downloaded)
        msg += struct.pack('>Q', self.left)
        msg += struct.pack('>Q', self.uploaded)
        msg += struct.pack('>I', self.event)
        msg += struct.pack('>I', 0)  # IP address (0 = default)
        msg += struct.pack('>I', 0)  # Key
        msg += struct.pack('>i', -1)  # num_want (-1 = default)
        msg += struct.pack('>H', 6881)  # Port
        return msg


class UdpTrackerAnnounceOutput:
    """
    Parse UDP tracker announce response
    """
    def __init__(self):
        self.action = None
        self.transaction_id = None
        self.interval = None
        self.leechers = None
        self.seeders = None
        self.peers = []

    def from_bytes(self, payload):
        if len(payload) < 20:
            raise ValueError("Response too short")
            
        self.action = struct.unpack('>I', payload[0:4])[0]
        self.transaction_id = struct.unpack('>I', payload[4:8])[0]
        self.interval = struct.unpack('>I', payload[8:12])[0]
        self.leechers = struct.unpack('>I', payload[12:16])[0]
        self.seeders = struct.unpack('>I', payload[16:20])[0]
        
        # Parse peers (6 bytes each: 4 IP + 2 port)
        offset = 20
        while offset + 6 <= len(payload):
            ip_bytes = payload[offset:offset+4]
            port_bytes = payload[offset+4:offset+6]
            
            ip = socket.inet_ntoa(ip_bytes)
            port = struct.unpack('>H', port_bytes)[0]
            
            self.peers.append((ip, port))
            offset += 6