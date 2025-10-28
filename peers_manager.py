import time
import select
import socket
import errno
import random
import logging
from threading import Thread

import message
import peer


class PeersManager(Thread):
    def __init__(self, torrent, pieces_manager):
        Thread.__init__(self)
        self.peers = []
        self.torrent = torrent
        self.pieces_manager = pieces_manager
        self.is_active = True
        self.daemon = True
        self.last_peer_cleanup = time.time()

    def get_random_peer_having_piece(self, index):
        """Get a random peer that has the requested piece"""
        ready_peers = []

        for peer in self.peers:
            if (peer.is_eligible() and peer.is_unchoked() and 
                peer.am_interested() and peer.has_piece(index) and peer.healthy):
                ready_peers.append(peer)

        return random.choice(ready_peers) if ready_peers else None

    def has_unchoked_peers(self):
        """Check if we have any unchoked peers"""
        for peer in self.peers:
            if peer.is_unchoked() and peer.healthy:
                return True
        return False

    def unchoked_peers_count(self):
        """Count number of unchoked peers"""
        count = 0
        for peer in self.peers:
            if peer.is_unchoked() and peer.healthy:
                count += 1
        return count

    def get_active_peers_count(self):
        """Count number of active peers (handshaked and healthy)"""
        count = 0
        for peer in self.peers:
            if peer.healthy and peer.has_handshaked:
                count += 1
        return count

    @staticmethod
    def _read_from_socket(sock):
        """Read data from socket without blocking"""
        data = b''
        
        while True:
            try:
                buff = sock.recv(4096)
                if len(buff) <= 0:
                    break
                data += buff
            except socket.error as e:
                err = e.args[0]
                if err != errno.EAGAIN and err != errno.EWOULDBLOCK:
                    logging.debug(f"Socket error: {err}")
                break
            except Exception:
                logging.exception("Recv failed")
                break
        
        return data

    def run(self):
        """Main loop for managing peer connections"""
        logging.info("PeersManager started")
        
        while self.is_active:
            # Clean up dead peers periodically
            current_time = time.time()
            if current_time - self.last_peer_cleanup > 30:  # Cleanup every 30 seconds
                self._cleanup_dead_peers()
                self.last_peer_cleanup = current_time

            # Get list of sockets to read from
            read_sockets = [peer.socket for peer in self.peers if peer.healthy and peer.socket]
            
            if not read_sockets:
                time.sleep(0.1)
                continue

            try:
                read_list, _, _ = select.select(read_sockets, [], [], 1.0)
            except (ValueError, OSError) as e:
                logging.debug(f"Select error: {e}")
                time.sleep(0.1)
                continue

            for sock in read_list:
                peer_obj = self.get_peer_by_socket(sock)
                if not peer_obj or not peer_obj.healthy:
                    continue

                try:
                    # Read data from peer
                    payload = self._read_from_socket(sock)
                    if not payload:
                        logging.info(f"Peer {peer_obj.ip} disconnected (no data)")
                        self.remove_peer(peer_obj)
                        continue
                        
                    peer_obj.read_buffer += payload

                    # Process messages
                    message_count = 0
                    for msg in peer_obj.get_messages():
                        self._process_new_message(msg, peer_obj)
                        message_count += 1
                        
                    if message_count > 0:
                        logging.debug(f"Processed {message_count} messages from {peer_obj.ip}")
                        
                except Exception as e:
                    logging.error(f"Error handling peer {peer_obj.ip}: {e}")
                    self.remove_peer(peer_obj)

    def _cleanup_dead_peers(self):
        """Remove peers that are no longer healthy"""
        initial_count = len(self.peers)
        dead_peers = [p for p in self.peers if not p.healthy]
        
        for dead_peer in dead_peers:
            self.remove_peer(dead_peer)
            
        if dead_peers:
            logging.info(f"Cleaned up {len(dead_peers)} dead peers. Active: {len(self.peers)}")

    def _do_handshake(self, peer_obj):
        """Perform handshake with peer"""
        try:
            handshake = message.Handshake(self.torrent.info_hash, self.torrent.peer_id)
            peer_obj.send_to_peer(handshake.to_bytes())
            logging.info(f"Sent handshake to {peer_obj.ip}")
            return True
        except Exception as e:
            logging.error(f"Handshake failed with {peer_obj.ip}: {e}")
            return False

    def add_peer(self, peer_obj):
        """Add a new peer to manage"""
        # Check if peer already exists
        for existing_peer in self.peers:
            if (existing_peer.ip == peer_obj.ip and 
                existing_peer.port == peer_obj.port):
                logging.debug(f"Peer {peer_obj.ip} already exists, skipping")
                return False

        if self._do_handshake(peer_obj):
            self.peers.append(peer_obj)
            logging.info(f"Added peer {peer_obj.ip}:{peer_obj.port}")
            
            # Send "Interested" message immediately after handshake
            try:
                interested_msg = message.Interested().to_bytes()
                peer_obj.send_to_peer(interested_msg)
                logging.info(f"Sent 'Interested' to {peer_obj.ip}")
            except Exception as e:
                logging.error(f"Failed to send 'Interested' to {peer_obj.ip}: {e}")
                # Don't remove peer for this error - they might still work
            
            return True
        return False

    def add_peers(self, peers_list):
        """Add multiple peers"""
        added_count = 0
        for peer_obj in peers_list:
            if self.add_peer(peer_obj):
                added_count += 1
        logging.info(f"Added {added_count} new peers")
        return added_count

    def remove_peer(self, peer_obj):
        """Remove a peer"""
        if peer_obj in self.peers:
            try:
                if peer_obj.socket:
                    peer_obj.socket.close()
            except Exception as e:
                logging.debug(f"Error closing socket for {peer_obj.ip}: {e}")
            
            self.peers.remove(peer_obj)
            logging.info(f"Removed peer {peer_obj.ip}:{peer_obj.port}")
            return True
        return False

    def get_peer_by_socket(self, sock):
        """Find peer by socket"""
        for peer_obj in self.peers:
            if peer_obj.socket == sock:
                return peer_obj
        return None

    def get_peer_by_ip(self, ip, port):
        """Find peer by IP and port"""
        for peer_obj in self.peers:
            if peer_obj.ip == ip and peer_obj.port == port:
                return peer_obj
        return None

    def _process_new_message(self, new_message, peer_obj):
        """Process incoming message from peer with peer scoring"""
        try:
            if isinstance(new_message, message.Handshake) or isinstance(new_message, message.KeepAlive):
                logging.debug(f"Handshake or KeepAlive from {peer_obj.ip}")
                
            elif isinstance(new_message, message.Choke):
                peer_obj.handle_choke()
                logging.info(f"Peer {peer_obj.ip} CHOKED us")
                
            elif isinstance(new_message, message.UnChoke):
                peer_obj.handle_unchoke()
                logging.info(f"🎉 Peer {peer_obj.ip} UNCHOKED us! Ready to download!")
                
            elif isinstance(new_message, message.Interested):
                peer_obj.handle_interested()
                logging.debug(f"Peer {peer_obj.ip} is interested in our pieces")
                
            elif isinstance(new_message, message.NotInterested):
                peer_obj.handle_not_interested()
                logging.debug(f"Peer {peer_obj.ip} is not interested")
                
            elif isinstance(new_message, message.Have):
                peer_obj.handle_have(new_message)
                logging.debug(f"Peer {peer_obj.ip} has piece {new_message.piece_index}")
                
                # Update rarest pieces if available
                if hasattr(self.pieces_manager, 'rarest_pieces'):
                    self.pieces_manager.rarest_pieces.update_peer_bitfield(
                        peer_obj.bit_field, peer_obj
                    )
                
            elif isinstance(new_message, message.BitField):
                peer_obj.handle_bitfield(new_message)
                logging.info(f"Peer {peer_obj.ip} sent bitfield with {peer_obj.bit_field.count(1)} pieces")
                
                # Update rarest pieces
                if hasattr(self.pieces_manager, 'rarest_pieces'):
                    self.pieces_manager.rarest_pieces.update_peer_bitfield(
                        peer_obj.bit_field, peer_obj
                    )
                
            elif isinstance(new_message, message.Request):
                peer_obj.handle_request(new_message)
                logging.debug(f"Peer {peer_obj.ip} requested piece {new_message.piece_index}")
                
            elif isinstance(new_message, message.Piece):
                # Handle piece data - send to pieces manager
                piece_data = peer_obj.handle_piece(new_message)
                if piece_data:
                    # Track that we received data from this peer - UPDATE PEER SCORE!
                    piece_index, block_offset, block_data = piece_data
                    bytes_received = len(block_data)
                    
                    # Update peer score - we received data from this peer!
                    if hasattr(self.pieces_manager, 'peer_scorer'):
                        self.pieces_manager.peer_scorer.update_peer_score(
                            hash(peer_obj), 
                            bytes_received=bytes_received
                        )
                        logging.debug(f"📥 Received {bytes_received} bytes from {peer_obj.ip} (piece {piece_index})")
                    
                    self.pieces_manager.receive_block_piece(piece_data)
                
            elif isinstance(new_message, message.Cancel):
                peer_obj.handle_cancel()
                logging.debug(f"Peer {peer_obj.ip} canceled request")
                
            elif isinstance(new_message, message.Port):
                peer_obj.handle_port_request()
                logging.debug(f"Peer {peer_obj.ip} sent port message")
                
            else:
                logging.warning(f"Unknown message type from {peer_obj.ip}: {type(new_message).__name__}")
                
        except Exception as e:
            logging.error(f"Error processing message from {peer_obj.ip}: {e}")
            # Don't remove peer for message processing errors

    def get_peer_stats(self):
        """Get statistics about current peers"""
        total_peers = len(self.peers)
        healthy_peers = sum(1 for p in self.peers if p.healthy)
        handshaked_peers = sum(1 for p in self.peers if p.has_handshaked)
        unchoked_peers = sum(1 for p in self.peers if p.is_unchoked())
        interested_peers = sum(1 for p in self.peers if p.am_interested())
        
        return {
            'total_peers': total_peers,
            'healthy_peers': healthy_peers,
            'handshaked_peers': handshaked_peers,
            'unchoked_peers': unchoked_peers,
            'interested_peers': interested_peers
        }

    def log_peer_states(self):
        """Log current state of all peers for debugging"""
        stats = self.get_peer_stats()
        logging.info(f"Peer stats: {stats['healthy_peers']}/{stats['total_peers']} healthy, "
                   f"{stats['unchoked_peers']} unchoked, {stats['handshaked_peers']} handshaked")
        
        for i, peer_obj in enumerate(self.peers):
            if peer_obj.healthy:
                states = []
                if peer_obj.has_handshaked: states.append("✓ Handshaked")
                if peer_obj.is_choking(): states.append("🚫 Choking")
                if peer_obj.is_unchoked(): states.append("✅ Unchoked")
                if peer_obj.am_interested(): states.append("🎯 Interested")
                if peer_obj.is_interested(): states.append("📥 Peer-Interested")
                
                status = " | ".join(states) if states else "❓ Unknown"
                piece_count = peer_obj.bit_field.count(1) if hasattr(peer_obj, 'bit_field') else 0
                logging.info(f"  {i+1}. {peer_obj.ip}:{peer_obj.port} - {status} - {piece_count} pieces")
            else:
                logging.info(f"  {i+1}. {peer_obj.ip}:{peer_obj.port} - ❌ Unhealthy")

    def stop(self):
        """Stop the peers manager and clean up all peers"""
        logging.info("Stopping PeersManager...")
        self.is_active = False
        
        # Close all peer connections
        for peer_obj in self.peers:
            try:
                if peer_obj.socket:
                    peer_obj.socket.close()
            except Exception as e:
                logging.debug(f"Error closing socket for {peer_obj.ip}: {e}")
        
        self.peers.clear()
        logging.info("PeersManager stopped and all peers cleaned up")