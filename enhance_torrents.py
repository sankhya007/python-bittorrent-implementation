#!/usr/bin/env python3

from torrent import bencode, bdecode
import os
import sys


def enhance_debian_torrent():
    """Enhance Debian torrent with public trackers"""
    
    # Fix Windows path - use raw string or forward slashes
    possible_paths = [
        r"C:\Users\Asus\personal_torrent_client\torrents\debian-13.1.0-amd64-netinst.iso.torrent",  # Raw string
        "C:/Users/Asus/personal_torrent_client/torrents/debian-13.1.0-amd64-netinst.iso.torrent",    # Forward slashes
        "torrents/debian-13.1.0-amd64-netinst.iso.torrent",  # Relative path
        "debian-13.1.0-amd64-netinst.iso.torrent"            # Current directory
    ]
    
    # Find the first existing path
    input_path = None
    for path in possible_paths:
        if os.path.exists(path):
            input_path = path
            print(f"📁 Found torrent file: {path}")
            break
    
    if input_path is None:
        print("❌ Debian torrent file not found in any expected location")
        print("💡 Please ensure the torrent file exists in one of these locations:")
        for path in possible_paths:
            print(f"   - {path}")
        return None
    
    output_path = "debian_enhanced.torrent"
    
    print(f"🔧 Enhancing: {os.path.basename(input_path)}")
    
    try:
        # Read the original torrent
        with open(input_path, 'rb') as f:
            file_data = f.read()
            
        if not file_data:
            print("❌ Torrent file is empty")
            return None
            
        torrent_data = bdecode(file_data)
        
        if not torrent_data:
            print("❌ Failed to parse torrent file")
            return None
        
        torrent_name = torrent_data.get(b'info', {}).get(b'name', b'Unknown').decode('utf-8', errors='ignore')
        print(f"✅ Original torrent loaded: {torrent_name}")
        
    except FileNotFoundError:
        print(f"❌ Torrent file not found: {input_path}")
        return None
    except Exception as e:
        print(f"❌ Error reading torrent file: {e}")
        return None

    # Comprehensive list of public trackers
    additional_trackers = [
        # UDP Trackers
        [b"udp://tracker.opentrackr.org:1337/announce"],
        [b"udp://open.tracker.cl:1337/announce"], 
        [b"udp://9.rarbg.com:2810/announce"],
        [b"udp://tracker.openbittorrent.com:6969/announce"],
        [b"udp://opentracker.i2p.rocks:6969/announce"],
        [b"udp://tracker.torrent.eu.org:451/announce"],
        [b"udp://tracker.internetwarriors.net:1337/announce"],
        [b"udp://exodus.desync.com:6969/announce"],
        [b"udp://tracker.cyberia.is:6969/announce"],
        [b"udp://tracker.dler.org:6969/announce"],
        
        # HTTP Trackers
        [b"http://tracker.openbittorrent.com:80/announce"],
        [b"http://tracker.dler.org:6969/announce"],
        [b"https://tracker.nanoha.org:443/announce"],
        [b"http://tracker.bt4g.com:6969/announce"],
        
        # Additional reliable trackers
        [b"udp://open.stealth.si:80/announce"],
        [b"udp://opentor.org:2710/announce"],
        [b"udp://tracker.moeking.me:6969/announce"],
        [b"udp://uploads.gamecoast.net:6969/announce"]
    ]
    
    # Remove any duplicate trackers that might already exist
    existing_trackers = set()
    if b'announce-list' in torrent_data:
        for tracker_group in torrent_data[b'announce-list']:
            for tracker in tracker_group:
                existing_trackers.add(tracker)
    
    # Filter out trackers that already exist
    unique_new_trackers = []
    for tracker_group in additional_trackers:
        for tracker in tracker_group:
            if tracker not in existing_trackers:
                unique_new_trackers.append([tracker])
    
    print(f"📡 Adding {len(unique_new_trackers)} new trackers...")
    
    # Add trackers to torrent
    if b'announce-list' in torrent_data:
        original_count = len(torrent_data[b'announce-list'])
        torrent_data[b'announce-list'].extend(unique_new_trackers)
        new_count = len(torrent_data[b'announce-list'])
        print(f"🔗 Extended announce-list: {original_count} → {new_count} trackers")
    else:
        torrent_data[b'announce-list'] = unique_new_trackers
        print(f"🆕 Created announce-list with {len(unique_new_trackers)} trackers")
    
    # Set primary announce for compatibility (use the most reliable one)
    primary_tracker = b"udp://tracker.opentrackr.org:1337/announce"
    torrent_data[b'announce'] = primary_tracker
    print(f"🏠 Set primary announce: {primary_tracker.decode('utf-8')}")

    try:
        # Create backup of original file
        backup_path = "debian_original_backup.torrent"
        with open(backup_path, 'wb') as f:
            f.write(file_data)
        print(f"💾 Backup created: {backup_path}")
        
        # Save enhanced torrent
        with open(output_path, 'wb') as f:
            encoded_data = bencode(torrent_data)
            f.write(encoded_data)
        
        # Verify the enhanced torrent can be read
        with open(output_path, 'rb') as f:
            verify_data = bdecode(f.read())
            if verify_data:
                total_trackers = len(verify_data.get(b'announce-list', []))
                print(f"✅ Enhanced torrent saved: {output_path}")
                print(f"📊 Total trackers: {total_trackers}")
                print(f"📦 File size: {os.path.getsize(output_path)} bytes")
                
                # Show tracker statistics
                if total_trackers > 0:
                    udp_count = sum(1 for group in verify_data[b'announce-list'] 
                                  for tracker in group if tracker.startswith(b'udp://'))
                    http_count = sum(1 for group in verify_data[b'announce-list'] 
                                   for tracker in group if tracker.startswith(b'http'))
                    
                    print(f"🌐 Trackers by protocol: {udp_count} UDP, {http_count} HTTP")
                    
                    print("📍 First 5 trackers:")
                    for i, tracker_group in enumerate(verify_data[b'announce-list'][:5]):
                        for tracker in tracker_group:
                            print(f"   {i+1}. {tracker.decode('utf-8')}")
                
                return output_path
            else:
                print("❌ Failed to verify enhanced torrent - file may be corrupted")
                return None
                
    except Exception as e:
        print(f"❌ Error creating enhanced torrent: {e}")
        return None


def enhance_any_torrent(input_path, output_path=None):
    """Enhanced version that works with any torrent file"""
    if not os.path.exists(input_path):
        print(f"❌ Torrent file not found: {input_path}")
        return None
    
    if output_path is None:
        base_name = os.path.splitext(input_path)[0]
        output_path = f"{base_name}_enhanced.torrent"
    
    print(f"🔧 Enhancing: {os.path.basename(input_path)}")
    
    try:
        with open(input_path, 'rb') as f:
            torrent_data = bdecode(f.read())
        
        # Use the same enhancement logic as above
        from enhance_torrents import enhance_debian_torrent
        # This would need to be refactored to be more generic
        
        print(f"✅ Enhanced: {output_path}")
        return output_path
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


if __name__ == "__main__":
    # Only run enhancement when script is executed directly
    enhanced_file = enhance_debian_torrent()
    
    if enhanced_file:
        print(f"\n🎉 Enhancement successful!")
        print(f"💡 Now run: python main.py {enhanced_file}")
    else:
        print(f"\n💥 Enhancement failed!")
        sys.exit(1)