import ipaddress
import struct
import peer
import socket
import requests
import logging
from urllib.parse import urlparse, quote
from torrent import bdecode

from message import UdpTrackerConnection, UdpTrackerAnnounce, UdpTrackerAnnounceOutput


class SockAddr:
    def __init__(self, ip, port, allowed=True):
        self.ip = ip
        self.port = port
        self.allowed = allowed

    def __hash__(self):
        return hash((self.ip, self.port))

    def __str__(self):
        return f"{self.ip}:{self.port}"

    def __eq__(self, other):
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
        max_peers_try = 50  # Increased to get more peers
        max_peers_connected = 15  # Increased connection limit
        
        print(f"📡 Contacting {len(self.torrent.announce_list)} trackers...")
        
        successful_trackers = 0
        for tracker_url in self.torrent.announce_list:
            if len(self.dict_sock_addr) >= max_peers_try:
                break

            try:
                if tracker_url.startswith("http"):
                    found_peers = self.http_scraper(tracker_url)
                    if found_peers > 0:
                        successful_trackers += 1
                elif tracker_url.startswith("udp"):
                    found_peers = self.udp_scraper(tracker_url)
                    if found_peers > 0:
                        successful_trackers += 1
                else:
                    print(f"⚠️  Unknown tracker scheme: {tracker_url}")
            except Exception as e:
                print(f"❌ Tracker {tracker_url} failed: {e}")

        print(f"✅ {successful_trackers}/{len(self.torrent.announce_list)} trackers responded")
        print(f"🔍 Found {len(self.dict_sock_addr)} potential peers")

        # Try to connect to discovered peers
        connected_count = self.try_peer_connect(max_peers_connected)
        
        print(f"🔗 Connected to {connected_count} peers")
        return self.connected_peers

    def try_peer_connect(self, max_peers):
        """Try to connect to discovered peers"""
        print(f"🔌 Attempting to connect to {len(self.dict_sock_addr)} discovered peers...")
        
        connected_count = 0
        for sock_addr in list(self.dict_sock_addr.values()):
            if connected_count >= max_peers:
                break

            new_peer = peer.Peer(int(self.torrent.number_of_pieces), sock_addr.ip, sock_addr.port)
            if new_peer.connect():
                self.connected_peers[hash(new_peer)] = new_peer
                connected_count += 1
                print(f"✅ Connected to {connected_count}/{max_peers} peers: {new_peer.ip}")

        return connected_count

    def http_scraper(self, tracker_url):
        """Fixed HTTP tracker with proper URL encoding"""
        try:
            # URL encode binary data properly
            info_hash_quoted = quote(self.torrent.info_hash)
            
            params = {
                'info_hash': info_hash_quoted,
                'peer_id': self.torrent.peer_id.decode('latin-1'),
                'port': 6881,
                'uploaded': 0,
                'downloaded': 0,
                'left': self.torrent.total_length,
                'compact': 1,
                'numwant': 50,
                'event': 'started'
            }

            headers = {
                'User-Agent': 'PythonBitTorrent/1.0',
                'Accept': '*/*',
                'Connection': 'close'
            }
            
            print(f"  🌐 HTTP: Contacting {tracker_url}")
            response = requests.get(tracker_url, params=params, headers=headers, timeout=15)
            
            if response.status_code != 200:
                print(f"  ❌ HTTP: Tracker returned status {response.status_code}")
                return 0
                
            try:
                response_data = bdecode(response.content)
            except Exception as e:
                print(f"  ❌ HTTP: Failed to decode response: {e}")
                return 0

            if b'failure reason' in response_data:
                reason = response_data[b'failure reason'].decode('utf-8', errors='ignore')
                print(f"  ❌ HTTP: Tracker error: {reason}")
                return 0
                
            peer_count = 0
            if b'peers' in response_data:
                peers_data = response_data[b'peers']
                
                if isinstance(peers_data, bytes):
                    # Compact format
                    peer_count = self._parse_compact_peers(peers_data)
                elif isinstance(peers_data, list):
                    # Dictionary format
                    peer_count = self._parse_dict_peers(peers_data)
                    
            # Also check for peers in interval (some trackers use different key)
            if b'peers ip' in response_data:
                print("  ℹ️  HTTP: Found peers in 'peers ip' field")
                
            print(f"  ✅ HTTP: Found {peer_count} peers")
            return peer_count
                
        except requests.exceptions.Timeout:
            print(f"  ⏰ HTTP: Timeout contacting {tracker_url}")
            return 0
        except requests.exceptions.ConnectionError:
            print(f"  🔌 HTTP: Connection error to {tracker_url}")
            return 0
        except Exception as e:
            print(f"  ❌ HTTP: Unexpected error: {e}")
            return 0

    def _parse_compact_peers(self, peers_data):
        """Parse compact peer format (6 bytes per peer)"""
        if not peers_data:
            return 0
            
        offset = 0
        peer_count = 0
        while offset + 6 <= len(peers_data):
            try:
                ip_bytes = peers_data[offset:offset+4]
                port_bytes = peers_data[offset+4:offset+6]
                
                ip = socket.inet_ntoa(ip_bytes)
                port = struct.unpack(">H", port_bytes)[0]
                
                # Validate IP and port
                if ip and 1 <= port <= 65535:
                    sock_addr = SockAddr(ip, port)
                    if hash(sock_addr) not in self.dict_sock_addr:
                        self.dict_sock_addr[hash(sock_addr)] = sock_addr
                        peer_count += 1
                
                offset += 6
            except Exception as e:
                print(f"    ⚠️  Failed to parse peer at offset {offset}: {e}")
                break
                
        return peer_count

    def _parse_dict_peers(self, peers_data):
        """Parse dictionary peer format"""
        peer_count = 0
        for peer_info in peers_data:
            try:
                if b'ip' in peer_info and b'port' in peer_info:
                    ip = peer_info[b'ip'].decode('utf-8')
                    port = peer_info[b'port']
                    
                    # Validate IP and port
                    if ip and 1 <= port <= 65535:
                        sock_addr = SockAddr(ip, port)
                        if hash(sock_addr) not in self.dict_sock_addr:
                            self.dict_sock_addr[hash(sock_addr)] = sock_addr
                            peer_count += 1
            except Exception as e:
                print(f"    ⚠️  Failed to parse peer dict: {e}")
                continue
                
        return peer_count

    def udp_scraper(self, announce_url):
        """Fixed UDP tracker implementation"""
        try:
            parsed = urlparse(announce_url)
            hostname = parsed.hostname
            port = parsed.port or 80  # Default UDP tracker port is 80, not 6969
            
            if not hostname:
                print(f"  ❌ UDP: Invalid URL: {announce_url}")
                return 0
            
            print(f"  🌐 UDP: Resolving {hostname}...")
            
            # Resolve hostname
            try:
                ip = socket.gethostbyname(hostname)
            except socket.gaierror as e:
                print(f"  ❌ UDP: Could not resolve {hostname}: {e}")
                return 0
                
            print(f"  🔌 UDP: Connecting to {ip}:{port}")
            
            # Create socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(10)
            
            # Connect phase
            connect_msg = UdpTrackerConnection()
            sock.sendto(connect_msg.to_bytes(), (ip, port))
            
            try:
                response = sock.recv(4096)
            except socket.timeout:
                print(f"  ⏰ UDP: Timeout connecting to {hostname}")
                sock.close()
                return 0
            
            if len(response) < 16:
                print(f"  ❌ UDP: Invalid connect response from {hostname}")
                sock.close()
                return 0
                
            # Parse connect response
            try:
                connect_output = UdpTrackerConnection()
                connect_output.from_bytes(response)
            except Exception as e:
                print(f"  ❌ UDP: Failed to parse connect response: {e}")
                sock.close()
                return 0
            
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
                print(f"  ⏰ UDP: Timeout announcing to {hostname}")
                sock.close()
                return 0
                
            # Parse announce response
            try:
                announce_output = UdpTrackerAnnounceOutput()
                announce_output.from_bytes(response)
            except Exception as e:
                print(f"  ❌ UDP: Failed to parse announce response: {e}")
                sock.close()
                return 0
            
            # Add discovered peers
            peer_count = 0
            for peer_ip, peer_port in announce_output.peers:
                try:
                    # Validate peer data
                    if peer_ip and 1 <= peer_port <= 65535:
                        sock_addr = SockAddr(peer_ip, peer_port)
                        if hash(sock_addr) not in self.dict_sock_addr:
                            self.dict_sock_addr[hash(sock_addr)] = sock_addr
                            peer_count += 1
                except Exception as e:
                    print(f"    ⚠️  Invalid peer data: {e}")
                    continue
            
            print(f"  ✅ UDP: {hostname} returned {peer_count} peers")
            sock.close()
            return peer_count
            
        except socket.gaierror as e:
            print(f"  ❌ UDP: Could not resolve {hostname}: {e}")
            return 0
        except Exception as e:
            print(f"  ❌ UDP: Error with {announce_url}: {e}")
            return 0
        finally:
            if 'sock' in locals():
                try:
                    sock.close()
                except:
                    pass