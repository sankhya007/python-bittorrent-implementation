#!/usr/bin/env python3

from torrent import Torrent
from tracker import Tracker
import logging
import os
import sys
import argparse


def setup_logging(verbose=False):
    """Setup appropriate logging level"""
    if verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    else:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        # Suppress noisy debug logs from dependencies
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)


def find_torrent_file(filename=None):
    """Find a torrent file to use for debugging"""
    if filename and os.path.exists(filename):
        return filename
    
    # Try common torrent filenames
    common_files = [
        "debian_enhanced.torrent",
        "ubuntu_enhanced.torrent", 
        "test.torrent",
        "debian-12.2.torrent",
        "ubuntu-22.04.torrent",
        "*.torrent"  # Any torrent file
    ]
    
    for file_pattern in common_files:
        if file_pattern.endswith('.torrent'):
            if os.path.exists(file_pattern):
                return file_pattern
        # For wildcard pattern, find first .torrent file
        elif file_pattern == "*.torrent":
            for file in os.listdir('.'):
                if file.endswith('.torrent'):
                    return file
    
    return None


def debug_trackers(torrent_path=None, verbose=False):
    """Debug tracker connectivity and peer discovery"""
    
    setup_logging(verbose)
    
    # Find torrent file
    if not torrent_path:
        torrent_path = find_torrent_file()
    
    if not torrent_path or not os.path.exists(torrent_path):
        print("❌ No torrent file found!")
        print("💡 Please run one of these first:")
        print("   python download_torrents.py")
        print("   python enhance_torrent.py") 
        print("   Or specify a torrent file: python debug_tracker.py myfile.torrent")
        return False
    
    print("=" * 70)
    print("🔧 TRACKER DEBUGGER")
    print("=" * 70)
    print(f"📁 Torrent file: {torrent_path}")
    
    # Load torrent
    torrent = Torrent().load_from_path(torrent_path)
    if not torrent:
        print("❌ Failed to load torrent file")
        return False
    
    print(f"📋 Torrent: {torrent.name}")
    print(f"📊 Size: {torrent.total_length:,} bytes")
    print(f"🧩 Pieces: {torrent.number_of_pieces}")
    print(f"🌐 Trackers found: {len(torrent.announce_list)}")
    
    # Show trackers with types
    print("\n📡 TRACKER LIST:")
    http_trackers = []
    udp_trackers = []
    other_trackers = []
    
    for i, tracker in enumerate(torrent.announce_list):
        if tracker.startswith('http'):
            http_trackers.append(tracker)
        elif tracker.startswith('udp'):
            udp_trackers.append(tracker)
        else:
            other_trackers.append(tracker)
    
    if udp_trackers:
        print(f"  UDP Trackers ({len(udp_trackers)}):")
        for tracker in udp_trackers[:5]:  # Show first 5
            print(f"    • {tracker}")
        if len(udp_trackers) > 5:
            print(f"    ... and {len(udp_trackers) - 5} more")
    
    if http_trackers:
        print(f"  HTTP Trackers ({len(http_trackers)}):")
        for tracker in http_trackers[:5]:  # Show first 5
            print(f"    • {tracker}")
        if len(http_trackers) > 5:
            print(f"    ... and {len(http_trackers) - 5} more")
    
    if other_trackers:
        print(f"  Other Trackers ({len(other_trackers)}):")
        for tracker in other_trackers:
            print(f"    • {tracker}")
    
    print(f"\n🔍 CONTACTING TRACKERS...")
    
    # Test tracker connectivity
    tracker_obj = Tracker(torrent)
    peers = tracker_obj.get_peers_from_trackers()
    
    print(f"\n📊 RESULTS:")
    print(f"  ✅ Connected peers: {len(peers)}")
    
    if peers:
        print(f"\n👥 PEERS FOUND:")
        for i, (peer_hash, peer_obj) in enumerate(peers.items()):
            status = "✅ Healthy" if peer_obj.healthy else "❌ Unhealthy"
            handshake = "🤝 Handshaked" if peer_obj.has_handshaked else "🚫 No handshake"
            print(f"  {i+1}. {peer_obj.ip}:{peer_obj.port} - {status} - {handshake}")
    else:
        print(f"  💔 No peers found from any tracker")
        print(f"\n💡 TROUBLESHOOTING:")
        print(f"  • Run python test_connectivity.py to check network")
        print(f"  • Try python enhance_torrent.py to add more trackers")
        print(f"  • Try a different torrent file")
        print(f"  • Check firewall/antivirus settings")
    
    # Show detailed peer information if verbose
    if verbose and peers:
        print(f"\n🔍 DETAILED PEER INFO:")
        for peer_hash, peer_obj in peers.items():
            print(f"  Peer: {peer_obj.ip}:{peer_obj.port}")
            print(f"    Healthy: {peer_obj.healthy}")
            print(f"    Handshaked: {peer_obj.has_handshaked}")
            if hasattr(peer_obj, 'bit_field'):
                pieces_count = peer_obj.bit_field.count(1) if hasattr(peer_obj.bit_field, 'count') else 0
                print(f"    Pieces available: {pieces_count}")
            print()
    
    print("=" * 70)
    return len(peers) > 0


def main():
    """Main function with command line support"""
    parser = argparse.ArgumentParser(description='Debug BitTorrent tracker connectivity')
    parser.add_argument('torrent_file', nargs='?', help='Torrent file to debug (optional)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose debug output')
    
    args = parser.parse_args()
    
    success = debug_trackers(args.torrent_file, args.verbose)
    
    if success:
        print("🎉 Debug completed successfully!")
        sys.exit(0)
    else:
        print("💥 Debug found issues - check troubleshooting tips above")
        sys.exit(1)


if __name__ == "__main__":
    main()