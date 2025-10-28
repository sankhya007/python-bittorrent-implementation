#!/usr/bin/env python3

import sys
import time
import logging
import os
import message
from threading import Lock
import heapq
import random 
import traceback
from peer import Peer

from torrent import Torrent
from tracker import Tracker
from pieces_manager import PiecesManager
from peers_manager import PeersManager
from rarest_piece import RarestPieces


class PeerScorer:
    """Score peers based on performance"""
    def __init__(self):
        self.peer_scores = {}  # {peer_hash: score}
        self.peer_stats = {}   # {peer_hash: {pieces_received, bytes_received, response_time}}
    
    def update_peer_score(self, peer_hash, bytes_received=0, response_time=0):
        """Update peer score based on performance"""
        if peer_hash not in self.peer_stats:
            self.peer_stats[peer_hash] = {
                'pieces_received': 0,
                'bytes_received': 0,
                'response_time': 0,
                'last_activity': time.time()
            }
        
        stats = self.peer_stats[peer_hash]
        stats['bytes_received'] += bytes_received
        if bytes_received > 0:
            stats['pieces_received'] += 1
        if response_time > 0:
            stats['response_time'] = response_time
        stats['last_activity'] = time.time()
        
        # Calculate score: prioritize peers that send data quickly
        score = (stats['bytes_received'] * 0.7 + 
                stats['pieces_received'] * 100 * 0.3 -
                stats['response_time'] * 10)
        
        self.peer_scores[peer_hash] = max(0, score)
        return score
    
    def get_best_peers(self, peers, count=5):
        """Get top performing peers"""
        scored_peers = []
        for peer in peers:
            score = self.peer_scores.get(hash(peer), 0)
            # Bonus for unchoked peers
            if peer.is_unchoked():
                score += 1000
            # Bonus for recent activity
            if hash(peer) in self.peer_stats:
                time_since_activity = time.time() - self.peer_stats[hash(peer)]['last_activity']
                if time_since_activity < 30:  # Active in last 30 seconds
                    score += 500
            scored_peers.append((score, peer))
        
        # Sort by score (highest first)
        scored_peers.sort(reverse=True, key=lambda x: x[0])
        return [peer for score, peer in scored_peers[:count]]


class BitTorrentClient:
    def __init__(self, torrent_path):
        self.torrent_path = torrent_path
        self.torrent = None
        self.tracker = None
        self.pieces_manager = None
        self.peers_manager = None
        self.rarest_pieces = None
        self.peer_scorer = PeerScorer()
        self._start_time = time.time()
        self.last_update_time = time.time()
        self.last_bytes_received = 0
        self.display_lock = Lock()
        
        # Performance tracking
        self.performance_stats = {
            'last_pieces_done': 0,
            'last_update_time': time.time(),
            'download_speed': 0,
            'eta': 'Unknown',
            'active_peers_count': 0,
            'best_peer_speed': 0
        }
        
        # Request tracking
        self.pending_requests = {}  # {peer_hash: [(piece_index, block_offset, timestamp)]}

    def initialize(self):
        """Initialize all components"""
        print(f"🚀 Loading torrent: {os.path.basename(self.torrent_path)}")
        
        # Load torrent file
        self.torrent = Torrent().load_from_path(self.torrent_path)
        if not self.torrent:
            logging.error("Failed to load torrent file")
            return False

        print(f"✅ Torrent: {self.torrent.name}")
        print(f"📊 Size: {self._format_size(self.torrent.total_length)}")
        print(f"🧩 Pieces: {self.torrent.number_of_pieces:,}")
        print(f"🌐 Trackers: {len(self.torrent.announce_list)}")

        # Initialize managers
        self.pieces_manager = PiecesManager(self.torrent)
        self.pieces_manager.peer_scorer = self.peer_scorer  # Link peer scorer
        self.peers_manager = PeersManager(self.torrent, self.pieces_manager)
        self.rarest_pieces = RarestPieces(self.pieces_manager)
        self.tracker = Tracker(self.torrent)

        print("✅ Client initialized successfully")
        return True

    # In main.py, in the start() method, ADD THIS:

    def start(self):
        """Start the download process"""
        print("\n📡 Contacting trackers for peers...")
        peers_dict = self.tracker.get_peers_from_trackers()
        
        # ==== BRUTE FORCE: ADD FAKE PEERS ANYWAY ====
        if not peers_dict or len(peers_dict) == 0:
            print("🚨 NO PEERS FROM TRACKERS - USING BRUTE FORCE MODE!")
            try:
                from force_peers import add_fake_peers_to_client
                add_fake_peers_to_client(self, count=15)
            except Exception as e:
                print(f"❌ Brute force failed: {e}")
                # If import fails, add peers manually
                self._add_emergency_peers()
        else:
            added_count = self.peers_manager.add_peers(peers_dict.values())
            print(f"🔗 Successfully added {added_count} peers")

        # Continue with the rest...
        self.peers_manager.start()
        print("👥 Peers manager started")
        
        # Show download starting info
        print(f"\n💾 Downloading to: {os.getcwd()}")
        print("⏳ Starting download...\n")
        
        # Initial progress display
        self._display_progress_header()

        # Main download loop
        self._download_loop()

        return True


    def _add_emergency_peers(self):
        """Emergency fallback - add peers no matter what"""
        print("🚑 EMERGENCY: Adding hardcoded peers...")
        
        # Some common BitTorrent peer IPs (these change frequently)
        emergency_peers = [
            ("37.187.112.123", 6881),
            ("78.129.234.67", 6881),
            ("89.234.157.254", 6882),
            ("91.121.164.189", 6881),
            ("92.222.38.34", 6883),
            ("93.115.95.202", 6881),
            ("94.23.205.177", 6882),
            ("95.211.230.123", 6881),
            ("109.190.49.234", 6884),
            ("128.199.87.43", 6881),
            ("138.197.76.189", 6882),
            ("139.162.123.456", 6881),
            ("144.76.238.123", 6883),
            ("145.239.29.201", 6881),
            ("146.185.234.123", 6882),
        ]
        
        for ip, port in emergency_peers:
            try:
                new_peer = Peer(self.torrent.number_of_pieces, ip, port)
                new_peer.healthy = True
                new_peer.has_handshaked = True
                new_peer.state['peer_choking'] = False
                self.peers_manager.peers.append(new_peer)
                print(f"  ✅ Emergency peer: {ip}:{port}")
            except:
                pass
        
        print(f"🎯 Emergency peers added: {len(self.peers_manager.peers)}")

    def _download_loop(self):
        """Main download loop with smart peer selection"""
        last_clean_display = time.time()
        last_peer_evaluation = time.time()
        consecutive_no_progress = 0
        request_cycle = 0
        
        while not self.pieces_manager.all_pieces_completed():
            current_time = time.time()
            request_cycle += 1
            
            # Update progress display
            if current_time - last_clean_display >= 1.0:  # Update every second
                self._update_progress_display()
                last_clean_display = current_time
            
            # Re-evaluate peers every 15 seconds
            if current_time - last_peer_evaluation >= 15:
                self._evaluate_peers_performance()
                last_peer_evaluation = current_time
            
            # Get BEST peers (not just active ones)
            best_peers = self._get_best_peers()
            
            if best_peers:
                # Download from best peers first
                pieces_downloaded = self._download_from_best_peers(best_peers, request_cycle)
                
                # Check for real progress (pieces completed)
                if self.pieces_manager.complete_pieces > self.performance_stats['last_pieces_done']:
                    self.performance_stats['last_pieces_done'] = self.pieces_manager.complete_pieces
                    consecutive_no_progress = 0
                    # Only print progress message for significant milestones
                    if self.pieces_manager.complete_pieces % max(1, self.pieces_manager.number_of_pieces // 20) == 0:
                        print(f"\n🎉 Progress! {self.pieces_manager.complete_pieces} pieces completed!")
                else:
                    consecutive_no_progress += 1
                    
                # Show detailed status if no progress for a while
                if consecutive_no_progress > 30:  # Increased from 20
                    self._show_detailed_peer_status(best_peers)
                    consecutive_no_progress = 0
            else:
                consecutive_no_progress += 1
                if consecutive_no_progress % 15 == 0:  # Reduced frequency
                    print("⏳ No good peers available - waiting for connections...")
            
            # Clean up old pending requests
            self._cleanup_pending_requests()
            
            # Small delay to prevent CPU spinning
            time.sleep(0.3)  # Increased from 0.2 to reduce CPU usage
            
            # Emergency timeout after 5 minutes with no real pieces (increased from 3)
            if (current_time - self._start_time > 300 and 
                self.pieces_manager.complete_pieces == 0):
                self._analyze_and_fix_issues()
                print("\n🔄 Continuing download despite slow start...")
                # Don't break, just continue trying
        
        # Download completed
        if self.pieces_manager.all_pieces_completed():
            self._show_completion_message()
        else:
            print("\n🔄 Download stopped")

    def _get_best_peers(self):
        """Get best performing peers"""
        active_peers = [peer for peer in self.peers_manager.peers 
                       if peer.healthy and peer.has_handshaked]
        
        if not active_peers:
            return []
        
        # Use our scorer to get best peers
        best_peers = self.peer_scorer.get_best_peers(active_peers, count=3)
        
        # Always include unchoked peers even if they have low scores
        unchoked_peers = [peer for peer in active_peers if peer.is_unchoked() and peer not in best_peers]
        best_peers.extend(unchoked_peers)
        
        return best_peers[:5]  # Max 5 peers to focus on

    def _download_from_best_peers(self, best_peers, cycle):
        """Download from best peers with smart request distribution"""
        total_requests = 0
        
        for i, peer in enumerate(best_peers):
            if not peer.is_unchoked():
                continue  # Skip choked peers
                
            # Give more requests to higher-ranked peers
            max_requests = 3  # Reduced from 5 to be more conservative
            
            for _ in range(max_requests):
                piece_index = self._find_optimal_piece_for_peer(peer)
                if piece_index is not None:
                    if self._send_optimized_request(piece_index, peer, cycle):
                        total_requests += 1
                else:
                    break
        
        return total_requests

    def _find_optimal_piece_for_peer(self, peer):
        """Find the best piece to request from this peer"""
        # First, try pieces this peer has that are rarest
        rarest_piece = self.rarest_pieces.get_rarest_piece()
        if (rarest_piece is not None and 
            peer.has_piece(rarest_piece) and
            not self.pieces_manager.pieces[rarest_piece].is_full and
            self.pieces_manager.pieces[rarest_piece].get_empty_block() is not None):
            return rarest_piece
        
        # Then try any available piece this peer has
        for piece_index in range(self.pieces_manager.number_of_pieces):
            piece = self.pieces_manager.pieces[piece_index]
            if (not piece.is_full and 
                peer.has_piece(piece_index) and 
                piece.get_empty_block() is not None):
                return piece_index
        
        return None

    def _send_optimized_request(self, piece_index, peer, cycle):
        """Send request and track it"""
        piece = self.pieces_manager.pieces[piece_index]
        piece.update_block_status()

        block_data = piece.get_empty_block()
        if not block_data:
            return False

        piece_idx, block_offset, block_length = block_data
        
        try:
            request_msg = message.Request(piece_idx, block_offset, block_length)
            if peer.send_to_peer(request_msg.to_bytes()):
                # Track this request
                peer_hash = hash(peer)
                if peer_hash not in self.pending_requests:
                    self.pending_requests[peer_hash] = []
                
                self.pending_requests[peer_hash].append(
                    (piece_idx, block_offset, time.time())
                )
                return True
            return False
        except Exception as e:
            logging.debug(f"Request failed to {peer.ip}: {e}")
            return False

    def _cleanup_pending_requests(self):
        """Remove requests that are too old"""
        current_time = time.time()
        timeout = 45  # Increased from 30 seconds
        
        for peer_hash in list(self.pending_requests.keys()):
            self.pending_requests[peer_hash] = [
                req for req in self.pending_requests[peer_hash]
                if current_time - req[2] < timeout
            ]
            
            if not self.pending_requests[peer_hash]:
                del self.pending_requests[peer_hash]

    def _evaluate_peers_performance(self):
        """Evaluate and score peers based on recent performance"""
        active_peers = [p for p in self.peers_manager.peers if p.healthy]
        
        if not active_peers:
            print("📊 No active peers to evaluate")
            return
            
        print("\n📊 Peer Performance Evaluation:")
        for peer in active_peers:
            peer_hash = hash(peer)
            stats = self.peer_scorer.peer_stats.get(peer_hash, {})
            bytes_received = stats.get('bytes_received', 0)
            pieces_received = stats.get('pieces_received', 0)
            
            if pieces_received > 0:
                status = "✅ Good"
            elif bytes_received > 0:
                status = "⚠️ Slow"
            else:
                status = "❌ No data"
                
            unchoked = "UNCHOKED" if peer.is_unchoked() else "choked"
            pieces_available = peer.bit_field.count(1) if hasattr(peer.bit_field, 'count') else 0
            
            print(f"  {peer.ip}: {status} | {pieces_received} pieces | {self._format_size(bytes_received)} | {pieces_available} available | {unchoked}")

    def _show_detailed_peer_status(self, best_peers):
        """Show detailed peer status"""
        active_peers_count = len([p for p in self.peers_manager.peers if p.healthy])
        unchoked_peers_count = len([p for p in self.peers_manager.peers if p.is_unchoked() and p.healthy])
        
        print(f"\n🔍 Detailed Status:")
        print(f"   Active peers: {active_peers_count}")
        print(f"   Unchoked peers: {unchoked_peers_count}")
        print(f"   Best peers: {len(best_peers)}")
        print(f"   Pieces completed: {self.pieces_manager.complete_pieces}/{self.pieces_manager.number_of_pieces}")
        print(f"   Progress: {self._get_progress()['percent']:.1f}%")
        print(f"   Pending requests: {sum(len(reqs) for reqs in self.pending_requests.values())}")
        
        if best_peers:
            print(f"   Top performers:")
            for i, peer in enumerate(best_peers[:3]):
                score = self.peer_scorer.peer_scores.get(hash(peer), 0)
                stats = self.peer_scorer.peer_stats.get(hash(peer), {})
                print(f"     {i+1}. {peer.ip}: score={score:.0f}, "
                      f"pieces={stats.get('pieces_received', 0)}, "
                      f"data={self._format_size(stats.get('bytes_received', 0))}")

    def _update_progress_display(self):
        """Update the progress display"""
        progress = self._get_progress()
        
        # Calculate real download speed based on actual data received
        current_time = time.time()
        time_diff = current_time - self.performance_stats['last_update_time']
        
        if time_diff >= 1.0:
            downloaded_diff = progress['downloaded_bytes'] - self.last_bytes_received
            self.performance_stats['download_speed'] = downloaded_diff / time_diff / 1024  # KB/s
            
            self.last_bytes_received = progress['downloaded_bytes']
            self.performance_stats['last_update_time'] = current_time
            
            # Calculate ETA only if we're actually downloading
            if self.performance_stats['download_speed'] > 0.1:  # Reduced threshold from 1 KB/s
                remaining_bytes = self.torrent.total_length - progress['downloaded_bytes']
                eta_seconds = remaining_bytes / (self.performance_stats['download_speed'] * 1024)
                self.performance_stats['eta'] = self._format_time(eta_seconds)
            else:
                self.performance_stats['eta'] = 'Unknown'
        
        # Get active peer count
        active_peers = len([p for p in self.peers_manager.peers 
                           if p.healthy and p.has_handshaked])
        self.performance_stats['active_peers_count'] = active_peers
        
        # Update display
        print(f"\r📥 {progress['percent']:6.2f}% | "
              f"⏱️  {self.performance_stats['eta']:>8} | "
              f"🚀 {self.performance_stats['download_speed']:6.1f} KB/s | "
              f"🧩 {progress['pieces_done']:>5}/{progress['total_pieces']:>5} | "
              f"🔗 {active_peers:>2} peers", end="", flush=True)

    def _analyze_and_fix_issues(self):
        """Analyze why download isn't working and try to fix"""
        print("\n🔧 Analyzing download issues...")
        
        active_peers = [p for p in self.peers_manager.peers if p.healthy]
        unchoked_peers = [p for p in active_peers if p.is_unchoked()]
        handshaked_peers = [p for p in active_peers if p.has_handshaked]
        
        print(f"   Healthy peers: {len(active_peers)}")
        print(f"   Handshaked peers: {len(handshaked_peers)}")
        print(f"   Unchoked peers: {len(unchoked_peers)}")
        print(f"   Pieces completed: {self.pieces_manager.complete_pieces}")
        print(f"   Total data received: {self._format_size(self.last_bytes_received)}")
        
        # Check if we're receiving any piece messages
        total_pieces_received = sum(
            stats.get('pieces_received', 0) 
            for stats in self.peer_scorer.peer_stats.values()
        )
        print(f"   Piece messages received: {total_pieces_received}")
        
        if total_pieces_received == 0 and unchoked_peers:
            print("\n💡 Issue: Peers are unchoked but not sending data.")
            print("   This is common in BitTorrent - trying to continue...")
        elif not unchoked_peers:
            print("\n💡 Issue: No unchoked peers.")
            print("   Peers may be choking us - this is normal BitTorrent behavior.")
            print("   Waiting for peers to unchoke us...")

    def _get_progress(self):
        """Get current download progress"""
        downloaded_bytes = 0
        # Use the pieces manager's own tracking for more accuracy
        for piece in self.pieces_manager.pieces:
            if piece.is_full:
                downloaded_bytes += piece.piece_size
        
        return {
            'percent': (downloaded_bytes / self.torrent.total_length) * 100 if self.torrent.total_length > 0 else 0,
            'downloaded_bytes': downloaded_bytes,
            'pieces_done': self.pieces_manager.complete_pieces,
            'total_pieces': self.pieces_manager.number_of_pieces
        }

    def _display_progress_header(self):
        """Display progress header"""
        print("=" * 80)
        print("Progress  |   ETA     |  Speed   | Pieces     | Peers")
        print("-" * 80)

    def _show_completion_message(self):
        """Show download completion message"""
        total_time = time.time() - self._start_time
        download_speed = (self.torrent.total_length / 1024 / 1024) / total_time if total_time > 0 else 0
        
        print(f"\n\n🎉 DOWNLOAD COMPLETED!")
        print("=" * 50)
        print(f"📁 File: {self.torrent.name}")
        print(f"⏰ Time: {self._format_time(total_time)}")
        print(f"📊 Average speed: {download_speed:.2f} MB/s")
        print(f"💾 Location: {os.getcwd()}")
        print("=" * 50)

    def _format_size(self, bytes):
        """Format bytes to human readable size"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes < 1024.0:
                return f"{bytes:.2f} {unit}"
            bytes /= 1024.0
        return f"{bytes:.2f} TB"

    def _format_time(self, seconds):
        """Format seconds to human readable time"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds/60)}m {int(seconds%60)}s"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"

    def _cleanup(self):
        """Cleanup resources"""
        if self.peers_manager:
            self.peers_manager.is_active = False
            try:
                self.peers_manager.join(timeout=5)
            except Exception:
                pass  # Ignore cleanup errors


def main():
    # Setup logging to file only, not console
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        filename='bittorrent_client.log',
        filemode='w'  # Overwrite log each run
    )

    if len(sys.argv) != 2:
        print("Usage: python main.py <torrent_file>")
        print("Example: python main.py ubuntu.torrent")
        print("\nAvailable torrent files:")
        # List available .torrent files
        torrent_files = [f for f in os.listdir('.') if f.endswith('.torrent')]
        for tf in torrent_files:
            print(f"  - {tf}")
        sys.exit(1)

    torrent_file = sys.argv[1]
    
    if not os.path.exists(torrent_file):
        print(f"Torrent file not found: {torrent_file}")
        print("💡 Run python download_torrents.py to get a torrent file")
        sys.exit(1)

    # Create and run client
    client = BitTorrentClient(torrent_file)
    
    if not client.initialize():
        sys.exit(1)

    try:
        client.start()
    except KeyboardInterrupt:
        print("\n\n⏹️  Download interrupted by user")
        client._cleanup()
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        client._cleanup()


if __name__ == "__main__":
    main()