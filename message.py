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
        
class UdpTrackerConnection(Message):
        """
        connect = <connection_id><action><transaction_id>
            - connection_id = 64-bit integer
            - action = 32-bit integer  
            - transaction_id = 32-bit integer
        """
        def __init__(self):
            super().__init__()
            self.conn_id = struct.pack('>Q', 0x41727101980)  # Magic constant
            self.action = struct.pack('>I', 0)  # Action 0 for connect
            self.trans_id = struct.pack('>I', random.randint(0, 100000))

        def to_bytes(self):
            return self.conn_id + self.action + self.trans_id

        @classmethod
        def from_bytes(cls, payload):
            instance = cls()
            instance.action = struct.unpack('>I', payload[:4])[0]
            instance.trans_id = struct.unpack('>I', payload[4:8])[0]
            instance.conn_id = struct.unpack('>Q', payload[8:16])[0]
            return instance


class UdpTrackerAnnounce(Message):
        """
        Announce message for UDP tracker
        """
        def __init__(self, info_hash, conn_id, peer_id):
            super().__init__()
            self.info_hash = info_hash
            self.conn_id = conn_id
            self.peer_id = peer_id
            self.trans_id = struct.pack('>I', random.randint(0, 100000))
            self.action = struct.pack('>I', 1)  # Action 1 for announce

        def to_bytes(self):
            conn_id = struct.pack('>Q', self.conn_id)
            action = self.action
            trans_id = self.trans_id
            downloaded = struct.pack('>Q', 0)
            left = struct.pack('>Q', self.torrent.total_length)  # You'll need to pass torrent to this class
            uploaded = struct.pack('>Q', 0)
            event = struct.pack('>I', 0)  # 0: none, 1: completed, 2: started, 3: stopped
            ip = struct.pack('>I', 0)
            key = struct.pack('>I', 0)
            num_want = struct.pack('>i', -1)  # -1 for default
            port = struct.pack('>h', 6881)

            msg = (conn_id + action + trans_id + self.info_hash + self.peer_id + 
                downloaded + left + uploaded + event + ip + key + num_want + port)
            return msg

        @classmethod
        def from_bytes(cls, payload):
            # UDP announce responses are handled by UdpTrackerAnnounceOutput
            pass


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
            self.list_sock_addr = []

        def from_bytes(self, payload):
            self.action = struct.unpack('>I', payload[:4])[0]
            self.transaction_id = struct.unpack('>I', payload[4:8])[0]
            self.interval = struct.unpack('>I', payload[8:12])[0]
            self.leechers = struct.unpack('>I', payload[12:16])[0]
            self.seeders = struct.unpack('>I', payload[16:20])[0]
            
            # Parse peer list (6 bytes per peer: 4 for IP, 2 for port)
            self.list_sock_addr = []
            offset = 20
            while offset + 6 <= len(payload):
                ip_bytes = payload[offset:offset+4]
                port_bytes = payload[offset+4:offset+6]
                
                ip = socket.inet_ntoa(ip_bytes)
                port = struct.unpack('>H', port_bytes)[0]
                
                self.list_sock_addr.append((ip, port))
                offset += 6