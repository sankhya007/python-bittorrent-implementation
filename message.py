import random
import socket
import struct
import bitstring
import logging


class WrongMessageException(Exception):
    pass


class MessageDispatcher:
    def __init__(self, payload):
        self.payload = payload

    def dispatch(self):
        if len(self.payload) < 4:
            logging.warning(f"Message too short: {len(self.payload)} bytes")
            return None

        try:
            payload_length = struct.unpack(">I", self.payload[:4])[0]
            
            # Validate payload length
            if payload_length > 10 * 1024 * 1024:  # 10MB max
                logging.error(f"Payload too large: {payload_length} bytes")
                return None
                
            if payload_length == 0:
                # Keep-alive message
                return KeepAlive.from_bytes(self.payload)
                
            if len(self.payload) < 5:  # Need at least 4 + 1 bytes for message ID
                logging.warning(f"Incomplete message: {len(self.payload)} bytes")
                return None
                
            message_id = struct.unpack(">B", self.payload[4:5])[0]

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
            logging.warning(f"Unknown message id: {message_id}")
            raise WrongMessageException(f"Wrong message id: {message_id}")

        try:
            return map_id_to_message[message_id].from_bytes(self.payload)
        except Exception as e:
            logging.error(f"Failed to parse message type {message_id}: {e}")
            return None


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
    def __init__(self, info_hash, peer_id=b'-PC0001-000000000000'):
        super().__init__()
        if len(info_hash) != 20:
            raise ValueError(f"Info hash must be 20 bytes, got {len(info_hash)}")
        if len(peer_id) != 20:
            raise ValueError(f"Peer ID must be 20 bytes, got {len(peer_id)}")
            
        self.info_hash = info_hash
        self.peer_id = peer_id
        self.total_length = 1 + HANDSHAKE_PSTR_LEN + 8 + 20 + 20

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
        if len(payload) < 1:
            raise WrongMessageException("Handshake too short")
            
        pstrlen, = struct.unpack(">B", payload[:1])
        
        if pstrlen != HANDSHAKE_PSTR_LEN:
            raise WrongMessageException(f"Invalid protocol string length: {pstrlen}")
            
        expected_length = 1 + pstrlen + 8 + 20 + 20
        if len(payload) < expected_length:
            raise WrongMessageException(f"Handshake incomplete: {len(payload)} < {expected_length}")
            
        pstr, reserved, info_hash, peer_id = struct.unpack(
            f">{pstrlen}s8s20s20s", payload[1:expected_length])
            
        if pstr != HANDSHAKE_PSTR_V1:
            raise WrongMessageException(f"Invalid protocol string: {pstr}")
            
        return Handshake(info_hash, peer_id)


class KeepAlive(Message):
    def to_bytes(self):
        return struct.pack(">I", 0)

    @classmethod
    def from_bytes(cls, payload):
        if len(payload) < 4:
            raise WrongMessageException("Keep-alive message too short")
            
        payload_length = struct.unpack(">I", payload[:4])[0]
        if payload_length != 0:
            raise WrongMessageException("Not a Keep Alive message")
        return KeepAlive()


class Choke(Message):
    message_id = 0

    def to_bytes(self):
        return struct.pack(">IB", 1, self.message_id)

    @classmethod
    def from_bytes(cls, payload):
        if len(payload) < 5:
            raise WrongMessageException("Choke message too short")
            
        payload_length, message_id = struct.unpack(">IB", payload[:5])
        if payload_length != 1:
            raise WrongMessageException(f"Invalid choke payload length: {payload_length}")
        if message_id != cls.message_id:
            raise WrongMessageException("Not a Choke message")
        return Choke()


class UnChoke(Message):
    message_id = 1

    def to_bytes(self):
        return struct.pack(">IB", 1, self.message_id)

    @classmethod
    def from_bytes(cls, payload):
        if len(payload) < 5:
            raise WrongMessageException("UnChoke message too short")
            
        payload_length, message_id = struct.unpack(">IB", payload[:5])
        if payload_length != 1:
            raise WrongMessageException(f"Invalid unchoke payload length: {payload_length}")
        if message_id != cls.message_id:
            raise WrongMessageException("Not an UnChoke message")
        return UnChoke()


class Interested(Message):
    message_id = 2

    def to_bytes(self):
        return struct.pack(">IB", 1, self.message_id)

    @classmethod
    def from_bytes(cls, payload):
        if len(payload) < 5:
            raise WrongMessageException("Interested message too short")
            
        payload_length, message_id = struct.unpack(">IB", payload[:5])
        if payload_length != 1:
            raise WrongMessageException(f"Invalid interested payload length: {payload_length}")
        if message_id != cls.message_id:
            raise WrongMessageException("Not an Interested message")
        return Interested()


class NotInterested(Message):
    message_id = 3

    def to_bytes(self):
        return struct.pack(">IB", 1, self.message_id)

    @classmethod
    def from_bytes(cls, payload):
        if len(payload) < 5:
            raise WrongMessageException("NotInterested message too short")
            
        payload_length, message_id = struct.unpack(">IB", payload[:5])
        if payload_length != 1:
            raise WrongMessageException(f"Invalid not-interested payload length: {payload_length}")
        if message_id != cls.message_id:
            raise WrongMessageException("Not a NotInterested message")
        return NotInterested()


class Have(Message):
    message_id = 4

    def __init__(self, piece_index):
        super().__init__()
        if piece_index < 0:
            raise ValueError(f"Invalid piece index: {piece_index}")
        self.piece_index = piece_index

    def to_bytes(self):
        return struct.pack(">IBI", 5, self.message_id, self.piece_index)

    @classmethod
    def from_bytes(cls, payload):
        if len(payload) < 9:
            raise WrongMessageException("Have message too short")
            
        payload_length, message_id, piece_index = struct.unpack(">IBI", payload[:9])
        if payload_length != 5:
            raise WrongMessageException(f"Invalid have payload length: {payload_length}")
        if message_id != cls.message_id:
            raise WrongMessageException("Not a Have message")
        if piece_index < 0:
            raise WrongMessageException(f"Invalid piece index in have message: {piece_index}")
        return Have(piece_index)


class BitField(Message):
    message_id = 5

    def __init__(self, bitfield):
        super().__init__()
        self.bitfield = bitfield
        self.bitfield_as_bytes = bitfield.tobytes()
        self.bitfield_length = len(self.bitfield_as_bytes)
        self.payload_length = 1 + self.bitfield_length

    def to_bytes(self):
        return struct.pack(f">IB{self.bitfield_length}s",
                          self.payload_length,
                          self.message_id,
                          self.bitfield_as_bytes)

    @classmethod
    def from_bytes(cls, payload):
        if len(payload) < 5:
            raise WrongMessageException("BitField message too short")
            
        payload_length, message_id = struct.unpack(">IB", payload[:5])
        
        if message_id != cls.message_id:
            raise WrongMessageException("Not a BitField message")
            
        bitfield_length = payload_length - 1
        
        if bitfield_length < 0:
            raise WrongMessageException(f"Invalid bitfield length: {bitfield_length}")
            
        if len(payload) < 5 + bitfield_length:
            raise WrongMessageException(f"BitField message incomplete: {len(payload)} < {5 + bitfield_length}")
            
        raw_bitfield = struct.unpack(f"{bitfield_length}s", payload[5:5 + bitfield_length])[0]
        bitfield = bitstring.BitArray(bytes=raw_bitfield)
        return BitField(bitfield)


class Request(Message):
    message_id = 6

    def __init__(self, piece_index, block_offset, block_length):
        super().__init__()
        if piece_index < 0:
            raise ValueError(f"Invalid piece index: {piece_index}")
        if block_offset < 0:
            raise ValueError(f"Invalid block offset: {block_offset}")
        if block_length <= 0 or block_length > 16384:  # 16KB max
            raise ValueError(f"Invalid block length: {block_length}")
            
        self.piece_index = piece_index
        self.block_offset = block_offset
        self.block_length = block_length

    def to_bytes(self):
        return struct.pack(">IBIII",
                          13,  # payload_length
                          self.message_id,
                          self.piece_index,
                          self.block_offset,
                          self.block_length)

    @classmethod
    def from_bytes(cls, payload):
        if len(payload) < 17:
            raise WrongMessageException("Request message too short")
            
        payload_length, message_id, piece_index, block_offset, block_length = struct.unpack(
            ">IBIII", payload[:17])
            
        if payload_length != 13:
            raise WrongMessageException(f"Invalid request payload length: {payload_length}")
        if message_id != cls.message_id:
            raise WrongMessageException("Not a Request message")
        if piece_index < 0:
            raise WrongMessageException(f"Invalid piece index in request: {piece_index}")
        if block_offset < 0:
            raise WrongMessageException(f"Invalid block offset in request: {block_offset}")
        if block_length <= 0 or block_length > 16384:
            raise WrongMessageException(f"Invalid block length in request: {block_length}")
            
        return Request(piece_index, block_offset, block_length)


class Piece(Message):
    message_id = 7

    def __init__(self, piece_index, block_offset, block):
        super().__init__()
        if piece_index < 0:
            raise ValueError(f"Invalid piece index: {piece_index}")
        if block_offset < 0:
            raise ValueError(f"Invalid block offset: {block_offset}")
        if not block:
            raise ValueError("Block data cannot be empty")
            
        self.piece_index = piece_index
        self.block_offset = block_offset
        self.block = block
        self.block_length = len(block)
        self.payload_length = 9 + self.block_length

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
        
        if message_id != cls.message_id:
            raise WrongMessageException("Not a Piece message")
            
        if payload_length < 9:
            raise WrongMessageException(f"Invalid piece payload length: {payload_length}")
            
        block_length = payload_length - 9
        
        if len(payload) < 13 + block_length:
            raise WrongMessageException(f"Piece message incomplete: {len(payload)} < {13 + block_length}")
            
        if piece_index < 0:
            raise WrongMessageException(f"Invalid piece index in piece message: {piece_index}")
        if block_offset < 0:
            raise WrongMessageException(f"Invalid block offset in piece message: {block_offset}")
            
        block = payload[13:13 + block_length]
        return Piece(piece_index, block_offset, block)


class Cancel(Message):
    message_id = 8

    def __init__(self, piece_index, block_offset, block_length):
        super().__init__()
        if piece_index < 0:
            raise ValueError(f"Invalid piece index: {piece_index}")
        if block_offset < 0:
            raise ValueError(f"Invalid block offset: {block_offset}")
        if block_length <= 0:
            raise ValueError(f"Invalid block length: {block_length}")
            
        self.piece_index = piece_index
        self.block_offset = block_offset
        self.block_length = block_length

    def to_bytes(self):
        return struct.pack(">IBIII",
                          13,  # payload_length
                          self.message_id,
                          self.piece_index,
                          self.block_offset,
                          self.block_length)

    @classmethod
    def from_bytes(cls, payload):
        if len(payload) < 17:
            raise WrongMessageException("Cancel message too short")
            
        payload_length, message_id, piece_index, block_offset, block_length = struct.unpack(
            ">IBIII", payload[:17])
            
        if payload_length != 13:
            raise WrongMessageException(f"Invalid cancel payload length: {payload_length}")
        if message_id != cls.message_id:
            raise WrongMessageException("Not a Cancel message")
        if piece_index < 0:
            raise WrongMessageException(f"Invalid piece index in cancel: {piece_index}")
        if block_offset < 0:
            raise WrongMessageException(f"Invalid block offset in cancel: {block_offset}")
        if block_length <= 0:
            raise WrongMessageException(f"Invalid block length in cancel: {block_length}")
            
        return Cancel(piece_index, block_offset, block_length)
    
    
class Port(Message):
    message_id = 9

    def __init__(self, listen_port):
        super().__init__()
        if listen_port < 0 or listen_port > 65535:
            raise ValueError(f"Invalid port number: {listen_port}")
        self.listen_port = listen_port

    def to_bytes(self):
        return struct.pack(">IBI",
                        5,  # payload_length
                        self.message_id,
                        self.listen_port)

    @classmethod
    def from_bytes(cls, payload):
        if len(payload) < 9:
            raise WrongMessageException("Port message too short")
            
        payload_length, message_id, listen_port = struct.unpack(">IBI", payload[:9])
        
        if payload_length != 5:
            raise WrongMessageException(f"Invalid port payload length: {payload_length}")
        if message_id != cls.message_id:
            raise WrongMessageException("Not a Port message")
        if listen_port < 0 or listen_port > 65535:
            raise WrongMessageException(f"Invalid port number in port message: {listen_port}")
                
        return Port(listen_port)


class UdpTrackerConnection:
    """UDP tracker connection message"""
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
        if len(payload) < 16:
            raise ValueError("UDP connection response too short")
            
        # Response: <action (32)><transaction_id (32)><connection_id (64)>
        self.action = struct.unpack('>I', payload[0:4])[0]
        self.transaction_id = struct.unpack('>I', payload[4:8])[0]
        self.connection_id = struct.unpack('>Q', payload[8:16])[0]
        return self


class UdpTrackerAnnounce:
    """UDP tracker announce message"""
    def __init__(self, connection_id, info_hash, peer_id, downloaded=0, left=0, uploaded=0, event=0):
        if len(info_hash) != 20:
            raise ValueError(f"Info hash must be 20 bytes, got {len(info_hash)}")
        if len(peer_id) != 20:
            raise ValueError(f"Peer ID must be 20 bytes, got {len(peer_id)}")
            
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
    """Parse UDP tracker announce response"""
    def __init__(self):
        self.action = None
        self.transaction_id = None
        self.interval = None
        self.leechers = None
        self.seeders = None
        self.peers = []

    def from_bytes(self, payload):
        if len(payload) < 20:
            raise ValueError("UDP announce response too short")
            
        self.action = struct.unpack('>I', payload[0:4])[0]
        self.transaction_id = struct.unpack('>I', payload[4:8])[0]
        self.interval = struct.unpack('>I', payload[8:12])[0]
        self.leechers = struct.unpack('>I', payload[12:16])[0]
        self.seeders = struct.unpack('>I', payload[16:20])[0]
        
        # Parse peers (6 bytes each: 4 IP + 2 port)
        self.peers = []
        offset = 20
        while offset + 6 <= len(payload):
            ip_bytes = payload[offset:offset+4]
            port_bytes = payload[offset+4:offset+6]
            
            try:
                ip = socket.inet_ntoa(ip_bytes)
                port = struct.unpack('>H', port_bytes)[0]
                
                # Validate IP and port
                if ip and 1 <= port <= 65535:
                    self.peers.append((ip, port))
                    
            except Exception as e:
                logging.debug(f"Invalid peer data at offset {offset}: {e}")
                
            offset += 6