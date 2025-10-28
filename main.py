#!/usr/bin/env python3

import sys
import time
import logging
import os
import message

from torrent import Torrent
from tracker import Tracker
from pieces_manager import PiecesManager
from peers_manager import PeersManager
from rarest_piece import RarestPieces


class BitTorrentClient:
    def __init__(self, torrent_path):
        self.torrent_path = torrent_path
        self.torrent = None
        self.tracker = None
        self.pieces_manager = None
        self.peers_manager = None
        self.rarest_pieces = None
        self.percentage_completed = -1
        self.last_log_line = ""

    def initialize(self):
        """Initialize all components with debug info"""
        print(f"🚀 Initializing client with: {self.torrent_path}")
        
        # Load torrent file
        self.torrent = Torrent().load_from_path(self.torrent_path)
        if not self.torrent:
            logging.error("Failed to load torrent file")
            return False

        print(f"✅ Torrent loaded: {self.torrent.name}")
        print(f"📊 Total size: {self.torrent.total_length} bytes")
        print(f"🧩 Pieces: {self.torrent.number_of_pieces}")
        print(f"🌐 Trackers: {len(self.torrent.announce_list)}")

        # Initialize managers
        self.pieces_manager = PiecesManager(self.torrent)
        self.peers_manager = PeersManager(self.torrent, self.pieces_manager)
        self.rarest_pieces = RarestPieces(self.pieces_manager)
        self.tracker = Tracker(self.torrent)

        print("✅ All components initialized")
        return True

    def start(self):
        """Start the download process"""
        logging.info("Starting BitTorrent client...")
        logging.info(f"Torrent: {self.torrent.name}")
        logging.info(f"Total size: {self.torrent.total_length} bytes")
        logging.info(f"Pieces: {self.torrent.number_of_pieces}")

        # Get peers from trackers
        logging.info("Contacting trackers...")
        peers_dict = self.tracker.get_peers_from_trackers()
        
        if not peers_dict:
            logging.error("No peers found from trackers")
            return False

        # Add peers to manager
        self.peers_manager.add_peers(peers_dict.values())
        
        # Start peers manager thread
        self.peers_manager.start()
        logging.info("Peers manager started")

        # Main download loop
        logging.info("Starting download...")
        self._download_loop()

        return True

    def _download_loop(self):
        """Main download loop with better peer management"""
        last_retry_time = time.time()
        
        while not self.pieces_manager.all_pieces_completed():
            current_time = time.time()
            
            # Retry sending "Interested" every 30 seconds
            if current_time - last_retry_time > 30:
                for peer in self.peers_manager.peers:
                    if peer.healthy and peer.is_choking():
                        interested_msg = message.Interested().to_bytes()
                        peer.send_to_peer(interested_msg)
                        logging.info(f"Retried 'Interested' to {peer.ip}")
                last_retry_time = current_time
            
            # Continue with normal download logic
            self._request_blocks()
            self._display_progression()
            
            time.sleep(1)  # Reduced sleep for more responsive checking

    def _request_blocks(self):
        """Request blocks from peers"""
        for peer in self.peers_manager.peers:
            if peer.healthy and peer.is_unchoked() and peer.am_interested():
                # This peer is ready to send us data
                piece_index = self.rarest_pieces.get_rarest_piece()
                if piece_index is not None and peer.has_piece(piece_index):
                    self._request_piece_blocks(piece_index, peer)

    def _request_piece_blocks(self, piece_index):
        """Request blocks for a specific piece"""
        piece = self.pieces_manager.pieces[piece_index]
        
        # Update block status (free pending blocks that timed out)
        piece.update_block_status()

        # Get empty block to download
        block_data = piece.get_empty_block()
        if not block_data:
            return

        piece_index, block_offset, block_length = block_data
        
        # Find peer that has this piece
        peer = self.peers_manager.get_random_peer_having_piece(piece_index)
        if not peer:
            return

        # Send request to peer
        request_msg = message.Request(piece_index, block_offset, block_length)
        peer.send_to_peer(request_msg.to_bytes())

    def _display_progression(self):
        """Display download progress"""
        downloaded_size = 0
        
        for piece in self.pieces_manager.pieces:
            if piece.is_full:
                downloaded_size += piece.piece_size
            else:
                # Count downloaded blocks in incomplete pieces
                for block in piece.blocks:
                    if block.state == block.state.FULL:
                        downloaded_size += len(block.data)

        if downloaded_size == self.percentage_completed:
            return

        percentage = (downloaded_size / self.torrent.total_length) * 100
        peers_count = self.peers_manager.unchoked_peers_count()
        
        current_line = (f"Peers: {peers_count} - "
                       f"{percentage:.1f}% completed | "
                       f"{self.pieces_manager.complete_pieces}/{self.pieces_manager.number_of_pieces} pieces")

        if current_line != self.last_log_line:
            print(current_line)
            self.last_log_line = current_line

        self.percentage_completed = downloaded_size

    def _cleanup(self):
        """Cleanup resources"""
        if self.peers_manager:
            self.peers_manager.is_active = False
            self.peers_manager.join(timeout=5)


def main():
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Check command line arguments
    if len(sys.argv) != 2:
        print("Usage: python main.py <torrent_file>")
        print("Example: python main.py ubuntu.torrent")
        sys.exit(1)

    torrent_file = sys.argv[1]
    
    if not os.path.exists(torrent_file):
        print(f"Torrent file not found: {torrent_file}")
        sys.exit(1)

    # Create and run client
    client = BitTorrentClient(torrent_file)
    
    if not client.initialize():
        sys.exit(1)

    try:
        client.start()
    except KeyboardInterrupt:
        print("\nDownload interrupted by user")
        client._cleanup()
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        client._cleanup()


if __name__ == "__main__":
    main()