# debug_peers.py
#!/usr/bin/env python3
import sys
import os

# Add current directory to path so we can import your modules
sys.path.append('.')

from main import BitTorrentClient

def debug_peers_status(torrent_path):
    print("🔍 DEBUGGING PEERS STATUS")
    print("=" * 50)
    
    # Initialize client
    client = BitTorrentClient(torrent_path)
    if not client.initialize():
        print("❌ Failed to initialize client")
        return
    
    # Start the process
    print("\n📡 Starting peer discovery...")
    client.start()
    
    # Check peers status
    print(f"\n👥 PEERS STATUS:")
    print(f"  Total peers: {len(client.peers_manager.peers)}")
    print(f"  Healthy peers: {sum(1 for p in client.peers_manager.peers if p.healthy)}")
    print(f"  Handshaked peers: {sum(1 for p in client.peers_manager.peers if p.has_handshaked)}")
    print(f"  Unchoked peers: {sum(1 for p in client.peers_manager.peers if p.is_unchoked())}")
    
    # Show individual peer status
    for i, peer in enumerate(client.peers_manager.peers):
        status = "✅" if peer.healthy else "❌"
        handshake = "🤝" if peer.has_handshaked else "🚫"
        unchoked = "✅" if peer.is_unchoked() else "🚫"
        print(f"  {i+1}. {peer.ip}:{peer.port} {status}{handshake}{unchoked}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python debug_peers.py <torrent_file>")
        sys.exit(1)
    
    debug_peers_status(sys.argv[1])