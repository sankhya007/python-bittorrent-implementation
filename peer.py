import time
import socket
import struct
import bitstring
import logging
import message


class Peer:
    def __init__(self, number_of_pieces: int, ip: str, port: int = 6881):
        self.last_call = 0.0
        self.last_activity = time.time()
        self.has_handshaked = False
        self.healthy = False
        self.read_buffer = b''
        self.socket = None
        self.ip = ip
        self.port = port
        self.number_of_pieces = number_of_pieces
        self.bit_field = bitstring.BitArray(number_of_pieces)
        
        # Performance tracking
        self.bytes_sent = 0
        self.bytes_received = 0
        self.pieces_received = 0
        self.connection_time = None
        self.last_keepalive = time.time()
        
        # Connection state
        self.state = {
            'am_choking': True,
            'am_interested': False,
            'peer_choking': True,
            'peer_interested': False,
        }
        
        # Request tracking
        self.pending_requests = {}  # {request_id: (piece_index, block_offset, timestamp)}
        self.next_request_id = 0

    def __hash__(self):
        return hash((self.ip, self.port))

    def __eq__(self, other):
        if not isinstance(other, Peer):
            return False
        return self.ip == other.ip and self.port == other.port

    def __str__(self):
        status = "✅" if self.healthy else "❌"
        handshake = "🤝" if self.has_handshaked else "🚫"
        unchoked = "✅" if self.is_unchoked() else "🚫"
        return f"Peer({self.ip}:{self.port}) {status}{handshake}{unchoked}"

    def connect(self) -> bool:
        """Connect to peer with comprehensive error handling"""
        try:
            self.connection_time = time.time()
            self.socket = socket.create_connection((self.ip, self.port), timeout=10)
            self.socket.setblocking(False)
            
            # Set socket options for better performance
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            
            self.healthy = True
            self.last_activity = time.time()
            
            logging.info(f"✅ Connected to peer {self.ip}:{self.port}")
            return True
            
        except socket.timeout:
            logging.debug(f"⏰ Connection timeout to {self.ip}:{self.port}")
            return False
        except ConnectionRefusedError:
            logging.debug(f"🚫 Connection refused by {self.ip}:{self.port}")
            return False
        except Exception as e:
            logging.debug(f"❌ Failed to connect to {self.ip}:{self.port} - {e}")
            return False

    def send_to_peer(self, msg: bytes, max_retries=2) -> bool:
        """Send message to peer with retry logic"""
        if not self.socket or not self.healthy:
            return False

        for attempt in range(max_retries + 1):
            try:
                # Set timeout for send operation
                self.socket.settimeout(10.0)
                sent = self.socket.send(msg)
                
                if sent == len(msg):
                    self.bytes_sent += sent
                    self.last_call = time.time()
                    self.last_activity = time.time()
                    return True
                else:
                    logging.warning(f"Partial send to {self.ip}: {sent}/{len(msg)} bytes")
                    
            except socket.timeout:
                logging.warning(f"Send timeout to {self.ip} (attempt {attempt + 1}/{max_retries + 1})")
                if attempt == max_retries:
                    self.healthy = False
                    return False
                    
            except BlockingIOError:
                # Socket buffer full, try again after short delay
                if attempt < max_retries:
                    time.sleep(0.01)
                    continue
                else:
                    logging.warning(f"Socket buffer full for {self.ip}")
                    return False
                    
            except Exception as e:
                logging.error(f"Failed to send to peer {self.ip}:{self.port} - {e}")
                self.healthy = False
                return False
        
        return False

    def send_keepalive(self):
        """Send keepalive message to maintain connection"""
        if time.time() - self.last_keepalive > 120:  # Send every 2 minutes
            try:
                keepalive_msg = message.KeepAlive().to_bytes()
                if self.send_to_peer(keepalive_msg):
                    self.last_keepalive = time.time()
                    logging.debug(f"Sent keepalive to {self.ip}")
            except Exception as e:
                logging.debug(f"Failed to send keepalive to {self.ip}: {e}")

    def is_eligible(self) -> bool:
        """Check if peer is ready for new requests"""
        now = time.time()
        time_since_last_call = now - self.last_call
        
        # Don't spam the peer - minimum 100ms between requests
        if time_since_last_call < 0.1:
            return False
            
        # Check if peer is still responsive
        if now - self.last_activity > 60:  # 1 minute without activity
            logging.warning(f"Peer {self.ip} appears unresponsive")
            self.healthy = False
            return False
            
        return (self.healthy and 
                self.has_handshaked and 
                self.is_unchoked() and 
                self.am_interested())

    def has_piece(self, index: int) -> bool:
        """Check if peer has the requested piece"""
        if 0 <= index < len(self.bit_field):
            return self.bit_field[index]
        return False

    def get_available_pieces_count(self) -> int:
        """Get number of pieces this peer has"""
        return self.bit_field.count(1) if hasattr(self.bit_field, 'count') else 0

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
        logging.info(f"Peer {self.ip} CHOKED us")
        self.state['peer_choking'] = True
        self.last_activity = time.time()

    def handle_unchoke(self):
        """Handle unchoke message from peer"""
        logging.info(f"🎉 Peer {self.ip} UNCHOKED us! Ready to download!")
        self.state['peer_choking'] = False
        self.last_activity = time.time()

    def handle_interested(self):
        """Handle interested message from peer"""
        logging.debug(f"Peer {self.ip} is interested in our pieces")
        self.state['peer_interested'] = True
        self.last_activity = time.time()

        if self.am_choking():
            try:
                unchoke = message.UnChoke().to_bytes()
                self.send_to_peer(unchoke)
                self.state['am_choking'] = False
            except Exception as e:
                logging.error(f"Failed to send unchoke to {self.ip}: {e}")

    def handle_not_interested(self):
        """Handle not interested message from peer"""
        logging.debug(f"Peer {self.ip} is not interested")
        self.state['peer_interested'] = False
        self.last_activity = time.time()

    def handle_have(self, have_msg):
        """Handle have message from peer"""
        piece_index = have_msg.piece_index
        if 0 <= piece_index < len(self.bit_field):
            if not self.bit_field[piece_index]:  # Only log if it's new
                logging.debug(f"Peer {self.ip} has piece {piece_index}")
            self.bit_field[piece_index] = True
        else:
            logging.warning(f"Peer {self.ip} sent invalid piece index: {piece_index}")

        self.last_activity = time.time()

        if self.is_choking() and not self.state['am_interested']:
            try:
                interested = message.Interested().to_bytes()
                if self.send_to_peer(interested):
                    self.state['am_interested'] = True
            except Exception as e:
                logging.error(f"Failed to send interested to {self.ip}: {e}")

    def handle_bitfield(self, bitfield_msg):
        """Handle bitfield message from peer"""
        logging.info(f"Peer {self.ip} sent bitfield with {bitfield_msg.bitfield.count(1)} pieces")
        
        # Validate bitfield size
        if len(bitfield_msg.bitfield) == self.number_of_pieces:
            self.bit_field = bitfield_msg.bitfield
        else:
            logging.warning(f"Peer {self.ip} sent invalid bitfield size: {len(bitfield_msg.bitfield)}")
            # Try to use what we can
            min_size = min(len(bitfield_msg.bitfield), self.number_of_pieces)
            self.bit_field[:min_size] = bitfield_msg.bitfield[:min_size]

        self.last_activity = time.time()

        if self.is_choking() and not self.state['am_interested']:
            try:
                interested = message.Interested().to_bytes()
                if self.send_to_peer(interested):
                    self.state['am_interested'] = True
            except Exception as e:
                logging.error(f"Failed to send interested to {self.ip}: {e}")

    def handle_request(self, request_msg):
        """Handle request message from peer"""
        logging.debug(f"Peer {self.ip} requested piece {request_msg.piece_index}")
        self.last_activity = time.time()
        # In a full implementation, this would trigger sending the requested piece

    def handle_piece(self, piece_msg):
        """Handle piece message from peer"""
        logging.debug(f"Peer {self.ip} sent piece {piece_msg.piece_index}, offset {piece_msg.block_offset}, size {len(piece_msg.block)}")
        
        self.bytes_received += len(piece_msg.block) + 13  # Include message overhead
        self.pieces_received += 1
        self.last_activity = time.time()
        
        return (piece_msg.piece_index, piece_msg.block_offset, piece_msg.block)

    def handle_cancel(self, cancel_msg):
        """Handle cancel message from peer"""
        logging.debug(f"Peer {self.ip} canceled request for piece {cancel_msg.piece_index}")
        self.last_activity = time.time()

    def handle_port(self, port_msg):
        """Handle port message from peer"""
        logging.debug(f"Peer {self.ip} sent port {port_msg.listen_port}")
        self.last_activity = time.time()

    def _handle_handshake(self) -> bool:
        """Handle handshake message"""
        try:
            handshake_msg = message.Handshake.from_bytes(self.read_buffer)
            self.has_handshaked = True
            self.read_buffer = self.read_buffer[handshake_msg.total_length:]
            self.last_activity = time.time()
            logging.info(f"✅ Handshake completed with {self.ip}")
            return True
        except Exception as e:
            logging.error(f"❌ Handshake failed with {self.ip}: {e}")
            self.healthy = False
            return False

    def _handle_keep_alive(self) -> bool:
        """Handle keep-alive message"""
        try:
            keep_alive = message.KeepAlive.from_bytes(self.read_buffer)
            self.read_buffer = self.read_buffer[keep_alive.total_length:]
            self.last_activity = time.time()
            self.last_keepalive = time.time()
            return True
        except message.WrongMessageException:
            return False
        except Exception as e:
            logging.debug(f"Keep-alive error with {self.ip}: {e}")
            return False

    def get_messages(self):
        """Process incoming messages from read buffer"""
        processed_count = 0
        max_messages_per_call = 50  # Prevent starvation
        
        while (len(self.read_buffer) > 4 and 
               self.healthy and 
               processed_count < max_messages_per_call):
            
            # Handle handshake if not done yet
            if not self.has_handshaked:
                if not self._handle_handshake():
                    break
                processed_count += 1
                continue

            # Handle keep-alive messages
            if self._handle_keep_alive():
                processed_count += 1
                continue

            # Check if we have a complete message
            if len(self.read_buffer) < 4:
                break

            payload_length = struct.unpack(">I", self.read_buffer[:4])[0]
            
            # Validate payload length
            if payload_length > 10 * 1024 * 1024:  # 10MB max
                logging.error(f"Invalid payload length from {self.ip}: {payload_length}")
                self.healthy = False
                break
                
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
                    processed_count += 1
            except message.WrongMessageException as e:
                logging.error(f"Wrong message from {self.ip}: {e}")
                # Don't break the connection for wrong messages
            except Exception as e:
                logging.error(f"Error processing message from {self.ip}: {e}")
                # Don't break the connection for processing errors

    def is_ready_for_requests(self):
        """Check if peer is ready to receive piece requests"""
        return (self.healthy and 
                self.has_handshaked and 
                self.is_unchoked() and 
                self.am_interested())

    def get_stats(self):
        """Get performance statistics for this peer"""
        uptime = time.time() - self.connection_time if self.connection_time else 0
        
        return {
            'ip': self.ip,
            'port': self.port,
            'healthy': self.healthy,
            'handshaked': self.has_handshaked,
            'unchoked': self.is_unchoked(),
            'interested': self.am_interested(),
            'available_pieces': self.get_available_pieces_count(),
            'bytes_sent': self.bytes_sent,
            'bytes_received': self.bytes_received,
            'pieces_received': self.pieces_received,
            'uptime_seconds': uptime,
            'last_activity': time.time() - self.last_activity
        }

    def close(self):
        """Close connection to peer"""
        try:
            if self.socket:
                self.socket.close()
        except Exception as e:
            logging.debug(f"Error closing socket for {self.ip}: {e}")
        finally:
            self.socket = None
            self.healthy = False