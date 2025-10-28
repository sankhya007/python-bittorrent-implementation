from torrent import Torrent
from tracker import Tracker
import logging

# Enable detailed logging
logging.basicConfig(level=logging.DEBUG)

def debug_trackers():
    torrent = Torrent().load_from_path("debian_enhanced.torrent")
    if not torrent:
        print("❌ Failed to load torrent")
        return
    
    print(f"📋 Trackers in torrent: {len(torrent.announce_list)}")
    for i, tracker in enumerate(torrent.announce_list):
        print(f"  {i+1}. {tracker}")
    
    tracker_obj = Tracker(torrent)
    peers = tracker_obj.get_peers_from_trackers()
    
    print(f"🔍 Found {len(peers)} peers")

debug_trackers()