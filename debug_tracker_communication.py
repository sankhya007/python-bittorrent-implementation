# debug_tracker_communication.py
#!/usr/bin/env python3

import requests
from urllib.parse import quote
from torrent import Torrent

def debug_tracker_request(torrent_path):
    print("🔍 DEBUGGING TRACKER COMMUNICATION")
    print("=" * 50)
    
    # Load torrent
    torrent = Torrent().load_from_path(torrent_path)
    if not torrent:
        print("❌ Failed to load torrent")
        return
    
    print(f"📁 Torrent: {torrent.name}")
    print(f"🔐 Info Hash: {torrent.info_hash.hex()}")
    print(f"👤 Peer ID: {torrent.peer_id.hex()}")
    
    # Test with Ubuntu tracker
    tracker_url = "https://torrent.ubuntu.com/announce"
    
    # URL encode binary data properly
    info_hash_quoted = quote(torrent.info_hash)
    
    params = {
        'info_hash': info_hash_quoted,
        'peer_id': torrent.peer_id.decode('latin-1'),
        'port': 6881,
        'uploaded': 0,
        'downloaded': 0,
        'left': torrent.total_length,
        'compact': 1,
        'numwant': 50,
        'event': 'started'
    }
    
    print(f"\n🌐 Testing tracker: {tracker_url}")
    print(f"📤 Parameters:")
    for key, value in params.items():
        if key == 'info_hash':
            print(f"  {key}: {value} (raw: {torrent.info_hash.hex()})")
        elif key == 'peer_id':
            print(f"  {key}: {value} (raw: {torrent.peer_id.hex()})")
        else:
            print(f"  {key}: {value}")
    
    try:
        headers = {
            'User-Agent': 'PythonBitTorrent/1.0',
            'Accept': '*/*'
        }
        
        response = requests.get(tracker_url, params=params, headers=headers, timeout=10)
        
        print(f"\n📥 Response:")
        print(f"  Status: {response.status_code}")
        print(f"  Headers: {dict(response.headers)}")
        print(f"  Content: {response.content}")
        
        if response.status_code == 200:
            try:
                from torrent import bdecode
                decoded = bdecode(response.content)
                print(f"  Decoded: {decoded}")
            except:
                print(f"  Could not decode response")
        
    except Exception as e:
        print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python debug_tracker_communication.py <torrent_file>")
        sys.exit(1)

    debug_tracker_request(sys.argv[1])