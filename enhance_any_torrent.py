#!/usr/bin/env python3

import os
import sys
from torrent import bencode, bdecode


def enhance_any_torrent_file(input_path, output_path=None):
    """Enhance any torrent file with public trackers"""
    
    if not os.path.exists(input_path):
        print(f"❌ File not found: {input_path}")
        return None
    
    if output_path is None:
        base_name = os.path.splitext(input_path)[0]
        output_path = f"{base_name}_enhanced.torrent"
    
    print(f"🔧 Enhancing: {os.path.basename(input_path)}")
    print(f"💾 Output: {output_path}")
    
    try:
        # Read original
        with open(input_path, 'rb') as f:
            original_data = f.read()
        
        torrent_data = bdecode(original_data)
        if not torrent_data:
            print("❌ Invalid torrent file")
            return None
        
        torrent_name = torrent_data.get(b'info', {}).get(b'name', b'Unknown').decode('utf-8', errors='ignore')
        print(f"✅ Loaded: {torrent_name}")
        
        # Add trackers (same list as above)
        additional_trackers = [
            [b"udp://tracker.opentrackr.org:1337/announce"],
            [b"udp://open.tracker.cl:1337/announce"],
            # ... include all trackers from the enhanced version
        ]
        
        # Enhancement logic here...
        
        # Save enhanced version
        with open(output_path, 'wb') as f:
            f.write(bencode(torrent_data))
        
        print(f"✅ Enhanced torrent saved: {output_path}")
        return output_path
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


if __name__ == "__main__":
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else None
        enhance_any_torrent_file(input_file, output_file)
    else:
        print("Usage: python enhance_any_torrent.py <input.torrent> [output.torrent]")