import time
import socket
import struct
import bitstring
import logging
import message


class Peer:
    def __init__(self, number_of_pieces: int, ip: str, port: int = 6881):
        self.last_call = 0.0
        self.has_handshaked = False
        self.healthy = False
        self.read_buffer = b''
        self.socket = None
        self.ip = ip
        self.port = port
        self.number_of_pieces = number_of_pieces
        self.bit_field = bitstring.BitArray(number_of_pieces)
        self.state = {
            'am_choking': True,
            'am_interested': False,
            'peer_choking': True,
            'peer_interested': False,
        }

    def __hash__(self):
        # FIXED: Return integer, not string
        return hash((self.ip, self.port))

    def __eq__(self, other):
        # Added for proper dictionary usage
        if not isinstance(other, Peer):
            return False
        return self.ip == other.ip and self.port == other.port

    def __str__(self):
        return f"Peer({self.ip}:{self.port})"

    def connect(self) -> bool:
        """Connect to peer"""
        try:
            self.socket = socket.create_connection((self.ip, self.port), timeout=5)
            self.socket.setblocking(False)
            self.healthy = True
            logging.info(f"Connected to peer {self.ip}:{self.port}")
            return True
        except Exception as e:
            logging.debug(f"Failed to connect to {self.ip}:{self.port} - {e}")
            return False

    def send_to_peer(self, msg: bytes):
        """Send message to peer"""
        try:
            if self.socket:
                self.socket.send(msg)
                self.last_call = time.time()
        except Exception as e:
            self.healthy = False
            logging.error(f"Failed to send to peer {self.ip}:{self.port} - {e}")

    def is_eligible(self) -> bool:
        """Check if peer is ready for new requests"""
        now = time.time()
        return (now - self.last_call) > 0.2

    def has_piece(self, index: int) -> bool:
        """Check if peer has the requested piece"""
        if index < len(self.bit_field):
            return self.bit_field[index]
        return False

    def am_choking(self) -> bool:
        return self.state['am_choking']

    def am_unchoking(self) -> bool:
        return not self.am_choking()

    def is_choking(self) -> bool:
        return self.state['peer_choking']

    def is_unchoked(self) -> bool:
        return not self.is_choking()

    def is_interested(self) -> bool:
        return self.state['peer_interested']

    def am_interested(self) -> bool:
        return self.state['am_interested']

    def handle_choke(self):
        """Handle choke message from peer"""
        logging.debug(f"Peer {self.ip} choked us")
        self.state['peer_choking'] = True

    def handle_unchoke(self):
        """Handle unchoke message from peer"""
        logging.debug(f"Peer {self.ip} unchoked us")
        self.state['peer_choking'] = False

    def handle_interested(self):
        """Handle interested message from peer"""
        logging.debug(f"Peer {self.ip} is interested")
        self.state['peer_interested'] = True

        if self.am_choking():
            unchoke = message.UnChoke().to_bytes()
            self.send_to_peer(unchoke)

    def handle_not_interested(self):
        """Handle not interested message from peer"""
        logging.debug(f"Peer {self.ip} is not interested")
        self.state['peer_interested'] = False

    def handle_have(self, have_msg):
        """Handle have message from peer"""
        logging.debug(f"Peer {self.ip} has piece {have_msg.piece_index}")
        self.bit_field[have_msg.piece_index] = True

        if self.is_choking() and not self.state['am_interested']:
            interested = message.Interested().to_bytes()
            self.send_to_peer(interested)
            self.state['am_interested'] = True

    def handle_bitfield(self, bitfield_msg):
        """Handle bitfield message from peer"""
        logging.debug(f"Peer {self.ip} sent bitfield")
        self.bit_field = bitfield_msg.bitfield

        if self.is_choking() and not self.state['am_interested']:
            interested = message.Interested().to_bytes()
            self.send_to_peer(interested)
            self.state['am_interested'] = True

    def handle_request(self, request_msg):
        """Handle request message from peer"""
        logging.debug(f"Peer {self.ip} requested piece {request_msg.piece_index}")
        # This would typically trigger sending the piece data
        # For now, we'll just log it

    def handle_piece(self, piece_msg):
        """Handle piece message from peer"""
        logging.debug(f"Peer {self.ip} sent piece {piece_msg.piece_index}")
        return (piece_msg.piece_index, piece_msg.block_offset, piece_msg.block)

    def _handle_handshake(self) -> bool:
        """Handle handshake message"""
        try:
            handshake_msg = message.Handshake.from_bytes(self.read_buffer)
            self.has_handshaked = True
            self.read_buffer = self.read_buffer[handshake_msg.total_length:]
            logging.debug(f"Handshake completed with {self.ip}")
            return True
        except Exception as e:
            logging.error(f"Handshake failed with {self.ip}: {e}")
            self.healthy = False
            return False

    def _handle_keep_alive(self) -> bool:
        """Handle keep-alive message"""
        try:
            keep_alive = message.KeepAlive.from_bytes(self.read_buffer)
            self.read_buffer = self.read_buffer[keep_alive.total_length:]
            return True
        except message.WrongMessageException:
            return False
        except Exception as e:
            logging.debug(f"Keep-alive error with {self.ip}: {e}")
            return False

    def get_messages(self):
        """Process incoming messages from read buffer"""
        while len(self.read_buffer) > 4 and self.healthy:
            # Handle handshake if not done yet
            if not self.has_handshaked:
                if not self._handle_handshake():
                    break
                continue

            # Handle keep-alive messages
            if self._handle_keep_alive():
                continue

            # Check if we have a complete message
            if len(self.read_buffer) < 4:
                break

            payload_length = struct.unpack(">I", self.read_buffer[:4])[0]
            total_length = payload_length + 4

            if len(self.read_buffer) < total_length:
                break

            # Extract and process message
            payload = self.read_buffer[:total_length]
            self.read_buffer = self.read_buffer[total_length:]

            try:
                received_message = message.MessageDispatcher(payload).dispatch()
                if received_message:
                    yield received_message
            except message.WrongMessageException as e:
                logging.error(f"Wrong message from {self.ip}: {e}")