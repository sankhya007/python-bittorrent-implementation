import ipaddress
import struct
import peer
import socket
import requests
import logging
from urllib.parse import urlparse
from torrent import bdecode

import peer
from message import UdpTrackerConnection, UdpTrackerAnnounce, UdpTrackerAnnounceOutput


class SockAddr:
    def __init__(self, ip, port, allowed=True):
        self.ip = ip
        self.port = port
        self.allowed = allowed

    def __hash__(self):
        # Return an integer hash based on ip and port
        return hash((self.ip, self.port))

    def __str__(self):
        return f"{self.ip}:{self.port}"

    def __eq__(self, other):
        # Also implement __eq__ for proper dictionary usage
        if not isinstance(other, SockAddr):
            return False
        return self.ip == other.ip and self.port == other.port


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
        """Fixed HTTP tracker with better error handling"""
        params = {
            'info_hash': self.torrent.info_hash,
            'peer_id': self.torrent.peer_id,
            'port': 6881,
            'uploaded': 0,
            'downloaded': 0,
            'left': self.torrent.total_length,
            'compact': 1,
            'numwant': 50,
            'event': 'started'
        }

        try:
            headers = {
                'User-Agent': 'PythonBitTorrent/1.0',
                'Accept': '*/*'
            }
            
            response = requests.get(tracker_url, params=params, headers=headers, timeout=10)
            
            if response.status_code != 200:
                print(f"  HTTP: Tracker returned status {response.status_code}")
                return
                
            try:
                response_data = bdecode(response.content)
            except Exception as e:
                print(f"  HTTP: Failed to decode response: {e}")
                # Try to parse as text for debugging
                print(f"  HTTP: Response preview: {response.content[:100]}")
                return

            if b'failure reason' in response_data:
                reason = response_data[b'failure reason'].decode('utf-8', errors='ignore')
                print(f"  HTTP: Tracker error: {reason}")
                return
                
            if b'peers' in response_data:
                peers_data = response_data[b'peers']
                peer_count = 0
                
                if isinstance(peers_data, bytes):
                    # Compact format
                    peer_count = self._parse_compact_peers(peers_data)
                elif isinstance(peers_data, list):
                    # Dictionary format
                    peer_count = self._parse_dict_peers(peers_data)
                    
                print(f"  HTTP: Found {peer_count} peers")
                
        except requests.exceptions.Timeout:
            print(f"  HTTP: Timeout contacting {tracker_url}")
        except requests.exceptions.ConnectionError:
            print(f"  HTTP: Connection error to {tracker_url}")
        except Exception as e:
            print(f"  HTTP: Unexpected error: {e}")

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
        """Fixed UDP tracker implementation"""
        import socket
        from urllib.parse import urlparse
        
        try:
            parsed = urlparse(announce_url)
            hostname = parsed.hostname
            port = parsed.port or 80
            
            # Resolve hostname
            ip = socket.gethostbyname(hostname)
            print(f"  UDP: Resolved {hostname} -> {ip}:{port}")
            
            # Create socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(8)
            
            # Connect phase
            connect_msg = UdpTrackerConnection()
            sock.sendto(connect_msg.to_bytes(), (ip, port))
            
            try:
                response = sock.recv(4096)
            except socket.timeout:
                print(f"  UDP: Timeout connecting to {hostname}")
                return
            
            if len(response) < 16:
                print(f"  UDP: Invalid connect response from {hostname}")
                return
                
            # Parse connect response
            connect_output = UdpTrackerConnection()
            connect_output.from_bytes(response)
            
            # Announce phase
            announce_msg = UdpTrackerAnnounce(
                connection_id=connect_output.connection_id,
                info_hash=self.torrent.info_hash,
                peer_id=self.torrent.peer_id,
                left=self.torrent.total_length
            )
            
            sock.sendto(announce_msg.to_bytes(), (ip, port))
            
            try:
                response = sock.recv(4096)
            except socket.timeout:
                print(f"  UDP: Timeout announcing to {hostname}")
                return
                
            # Parse announce response
            announce_output = UdpTrackerAnnounceOutput()
            announce_output.from_bytes(response)
            
            # Add discovered peers
            for peer_ip, peer_port in announce_output.peers:
                sock_addr = SockAddr(peer_ip, peer_port)
                if hash(sock_addr) not in self.dict_sock_addr:
                    self.dict_sock_addr[hash(sock_addr)] = sock_addr
            
            print(f"  UDP: {hostname} returned {len(announce_output.peers)} peers")
            
        except socket.gaierror as e:
            print(f"  UDP: Could not resolve {hostname}: {e}")
        except Exception as e:
            print(f"  UDP: Error with {announce_url}: {e}")
        finally:
            if 'sock' in locals():
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