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
        while self.is_active:
            # Get list of sockets to read from
            read_sockets = [peer.socket for peer in self.peers if peer.healthy and peer.socket]
            
            if not read_sockets:
                time.sleep(0.1)
                continue

            try:
                read_list, _, _ = select.select(read_sockets, [], [], 1.0)
            except (ValueError, OSError) as e:
                logging.debug(f"Select error: {e}")
                continue

            for sock in read_list:
                peer_obj = self.get_peer_by_socket(sock)
                if not peer_obj or not peer_obj.healthy:
                    continue

                try:
                    # Read data from peer
                    payload = self._read_from_socket(sock)
                    if not payload:
                        self.remove_peer(peer_obj)
                        continue
                        
                    peer_obj.read_buffer += payload

                    # Process messages
                    for msg in peer_obj.get_messages():
                        self._process_new_message(msg, peer_obj)
                        
                except Exception as e:
                    logging.error(f"Error handling peer {peer_obj.ip}: {e}")
                    self.remove_peer(peer_obj)

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
        if self._do_handshake(peer_obj):
            self.peers.append(peer_obj)
            logging.info(f"Added peer {peer_obj.ip}:{peer_obj.port}")
            
            # Send "Interested" message immediately after handshake
            interested_msg = message.Interested().to_bytes()
            peer_obj.send_to_peer(interested_msg)
            logging.info(f"Sent 'Interested' to {peer_obj.ip}")
            
            return True
        return False

    def add_peers(self, peers_list):
        """Add multiple peers"""
        for peer_obj in peers_list:
            self.add_peer(peer_obj)

    def remove_peer(self, peer_obj):
        """Remove a peer"""
        if peer_obj in self.peers:
            try:
                if peer_obj.socket:
                    peer_obj.socket.close()
            except Exception:
                logging.exception(f"Error closing socket for {peer_obj.ip}")
            
            self.peers.remove(peer_obj)
            logging.info(f"Removed peer {peer_obj.ip}")

    def get_peer_by_socket(self, sock):
        """Find peer by socket"""
        for peer_obj in self.peers:
            if peer_obj.socket == sock:
                return peer_obj
        return None

    def _process_new_message(self, new_message, peer_obj):
        """Process incoming message from peer"""
        if isinstance(new_message, message.Handshake) or isinstance(new_message, message.KeepAlive):
            logging.debug("Handshake or KeepAlive already handled")
            
        elif isinstance(new_message, message.Choke):
            peer_obj.handle_choke()
            
        elif isinstance(new_message, message.UnChoke):
            peer_obj.handle_unchoke()
            
        elif isinstance(new_message, message.Interested):
            peer_obj.handle_interested()
            
        elif isinstance(new_message, message.NotInterested):
            peer_obj.handle_not_interested()
            
        elif isinstance(new_message, message.Have):
            peer_obj.handle_have(new_message)
            
        elif isinstance(new_message, message.BitField):
            peer_obj.handle_bitfield(new_message)
            
        elif isinstance(new_message, message.Request):
            peer_obj.handle_request(new_message)
            
        elif isinstance(new_message, message.Piece):
            # Handle piece data - send to pieces manager
            piece_data = peer_obj.handle_piece(new_message)
            if piece_data:
                self.pieces_manager.receive_block_piece(piece_data)
            
        elif isinstance(new_message, message.Cancel):
            peer_obj.handle_cancel()
            
        elif isinstance(new_message, message.Port):
            peer_obj.handle_port_request()
            
        else:
            logging.warning(f"Unknown message type from {peer_obj.ip}")