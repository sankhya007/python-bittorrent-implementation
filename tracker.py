import socket
import struct
import requests
import logging
from urllib.parse import urlparse
import ipaddress

import peer
from message import UdpTrackerConnection, UdpTrackerAnnounce, UdpTrackerAnnounceOutput


class SockAddr:
    def __init__(self, ip, port, allowed=True):
        self.ip = ip
        self.port = port
        self.allowed = allowed

    def __hash__(self):
        return f"{self.ip}:{self.port}"

    def __str__(self):
        return f"{self.ip}:{self.port}"


class Tracker:
    def __init__(self, torrent):
        self.torrent = torrent
        self.connected_peers = {}
        self.dict_sock_addr = {}

    def get_peers_from_trackers(self):
        """Get peers from all trackers in torrent"""
        max_peers_try = 30
        max_peers_connected = 8
        
        logging.info(f"Contacting {len(self.torrent.announce_list)} trackers...")
        
        for tracker_url in self.torrent.announce_list:
            if len(self.dict_sock_addr) >= max_peers_try:
                break

            try:
                if tracker_url.startswith("http"):
                    self.http_scraper(tracker_url)
                elif tracker_url.startswith("udp"):
                    self.udp_scraper(tracker_url)
                else:
                    logging.warning(f"Unknown tracker scheme: {tracker_url}")
            except Exception as e:
                logging.error(f"Tracker {tracker_url} failed: {e}")

        # Try to connect to discovered peers
        self.try_peer_connect(max_peers_connected)
        
        logging.info(f"Connected to {len(self.connected_peers)} peers")
        return self.connected_peers

    def try_peer_connect(self, max_peers):
        """Try to connect to discovered peers"""
        logging.info(f"Trying to connect to {len(self.dict_sock_addr)} discovered peers")
        
        for sock_addr in self.dict_sock_addr.values():
            if len(self.connected_peers) >= max_peers:
                break

            new_peer = peer.Peer(int(self.torrent.number_of_pieces), sock_addr.ip, sock_addr.port)
            if new_peer.connect():
                self.connected_peers[hash(new_peer)] = new_peer
                logging.info(f"Connected to {len(self.connected_peers)}/{max_peers} peers: {new_peer.ip}")

    def http_scraper(self, tracker_url):
        """Scrape HTTP tracker"""
        params = {
            'info_hash': self.torrent.info_hash,
            'peer_id': self.torrent.peer_id,
            'uploaded': 0,
            'downloaded': 0, 
            'port': 6881,
            'left': self.torrent.total_length,
            'event': 'started',
            'compact': 1
        }

        try:
            response = requests.get(tracker_url, params=params, timeout=10)
            response_data = response.content
            
            import bcoding
            decoded_data = bcoding.bdecode(response_data)
            
            if b'peers' in decoded_data:
                peers_data = decoded_data[b'peers']
                
                if isinstance(peers_data, bytes):
                    # Compact format
                    self._parse_compact_peers(peers_data)
                elif isinstance(peers_data, list):
                    # Dictionary format
                    self._parse_dict_peers(peers_data)
                    
            logging.info(f"HTTP tracker {tracker_url} returned {len(self.dict_sock_addr)} peers")
            
        except Exception as e:
            logging.error(f"HTTP tracker {tracker_url} failed: {e}")

    def _parse_compact_peers(self, peers_data):
        """Parse compact peer format (6 bytes per peer)"""
        offset = 0
        while offset + 6 <= len(peers_data):
            ip_bytes = peers_data[offset:offset+4]
            port_bytes = peers_data[offset+4:offset+6]
            
            ip = socket.inet_ntoa(ip_bytes)
            port = struct.unpack(">H", port_bytes)[0]
            
            sock_addr = SockAddr(ip, port)
            self.dict_sock_addr[hash(sock_addr)] = sock_addr
            
            offset += 6

    def _parse_dict_peers(self, peers_data):
        """Parse dictionary peer format"""
        for peer_info in peers_data:
            ip = peer_info[b'ip'].decode('utf-8')
            port = peer_info[b'port']
            
            sock_addr = SockAddr(ip, port)
            self.dict_sock_addr[hash(sock_addr)] = sock_addr

    def udp_scraper(self, announce_url):
        """Scrape UDP tracker"""
        parsed = urlparse(announce_url)
        
        # Resolve hostname
        try:
            ip = socket.gethostbyname(parsed.hostname)
            port = parsed.port or 80
        except Exception as e:
            logging.error(f"Could not resolve UDP tracker hostname: {e}")
            return

        # Skip private IPs
        if ipaddress.ip_address(ip).is_private:
            return

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(8)

        try:
            # Connect phase
            connect_msg = UdpTrackerConnection()
            response = self._send_udp_message((ip, port), sock, connect_msg)
            if not response:
                return

            connect_output = UdpTrackerConnection()
            connect_output.from_bytes(response)

            # Announce phase  
            announce_msg = UdpTrackerAnnounce(self.torrent.info_hash, connect_output.conn_id, self.torrent.peer_id)
            response = self._send_udp_message((ip, port), sock, announce_msg)
            if not response:
                return

            announce_output = UdpTrackerAnnounceOutput()
            announce_output.from_bytes(response)

            # Add discovered peers
            for peer_ip, peer_port in announce_output.list_sock_addr:
                sock_addr = SockAddr(peer_ip, peer_port)
                self.dict_sock_addr[hash(sock_addr)] = sock_addr

            logging.info(f"UDP tracker returned {len(announce_output.list_sock_addr)} peers")

        except Exception as e:
            logging.error(f"UDP tracker error: {e}")
        finally:
            sock.close()

    def _send_udp_message(self, address, sock, message):
        """Send UDP message and wait for response"""
        try:
            sock.sendto(message.to_bytes(), address)
            response, _ = sock.recvfrom(2048)
            return response
        except socket.timeout:
            logging.debug("UDP tracker timeout")
            return None
        except Exception as e:
            logging.error(f"UDP send error: {e}")
            return None