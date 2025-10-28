#!/usr/bin/env python3

import os
import sys
from torrent import bencode, bdecode


def enhance_torrent(input_path=None, output_path=None, backup=True):
    """
    Enhance a torrent file by adding public trackers
    
    Args:
        input_path: Path to input torrent file (optional)
        output_path: Path for enhanced torrent file (optional) 
        backup: Whether to create backup of original file
    """
    
    # If no input provided, try to find common torrent files
    if input_path is None:
        possible_files = [
            "ubuntu-25.10-desktop-amd64.iso.torrent",
            "debian_enhanced.torrent", 
            "ubuntu_enhanced.torrent",
            "test.torrent"
        ]
        
        for file in possible_files:
            if os.path.exists(file):
                input_path = file
                print(f"📁 Found torrent file: {file}")
                break
        else:
            print("❌ No torrent file found. Please specify input path.")
            return None
    
    # Validate input file
    if not os.path.exists(input_path):
        print(f"❌ Torrent file not found: {input_path}")
        return None
    
    # Set output path if not provided
    if output_path is None:
        base_name = os.path.splitext(input_path)[0]
        output_path = f"{base_name}_enhanced.torrent"
    
    print(f"🔧 Enhancing torrent: {os.path.basename(input_path)}")
    print(f"💾 Output: {output_path}")
    
    try:
        # Read and parse torrent file
        with open(input_path, 'rb') as f:
            torrent_data = f.read()
            
        if not torrent_data:
            print("❌ Torrent file is empty")
            return None
            
        decoded_data = bdecode(torrent_data)
        if not decoded_data:
            print("❌ Failed to parse torrent file")
            return None
        
        print(f"✅ Torrent loaded: {decoded_data.get(b'info', {}).get(b'name', b'unknown').decode('utf-8', errors='ignore')}")
        
    except Exception as e:
        print(f"❌ Error reading torrent file: {e}")
        return None

    # Comprehensive list of public trackers (updated and verified)
    public_trackers = [
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
        [b"udp://open.stealth.si:80/announce"],
        [b"udp://opentor.org:2710/announce"],
        [b"udp://tracker.moeking.me:6969/announce"],
        
        # HTTP Trackers  
        [b"http://tracker.openbittorrent.com:80/announce"],
        [b"http://tracker.dler.org:6969/announce"],
        [b"https://tracker.nanoha.org:443/announce"],
        [b"http://tracker.bt4g.com:6969/announce"],
        [b"https://tracker.lilithraws.org:443/announce"],
        [b"http://vps02.net.orel.ru:80/announce"],
        
        # Additional reliable trackers
        [b"udp://uploads.gamecoast.net:6969/announce"],
        [b"udp://tracker1.bt.moack.co.kr:80/announce"],
        [b"udp://sanincode.com:6969/announce"],
        [b"udp://tracker.e-utp.net:6969/announce"]
    ]

    # Remove duplicates and ensure proper encoding
    unique_trackers = []
    seen_trackers = set()
    
    for tracker_group in public_trackers:
        for tracker in tracker_group:
            if tracker not in seen_trackers:
                seen_trackers.add(tracker)
                unique_trackers.append([tracker])
    
    print(f"📡 Adding {len(unique_trackers)} public trackers...")
    
    # Add trackers to torrent
    if b'announce-list' in decoded_data:
        # Remove any existing duplicates
        existing_trackers = []
        existing_seen = set()
        
        for tracker_group in decoded_data[b'announce-list']:
            for tracker in tracker_group:
                if tracker not in existing_seen:
                    existing_seen.add(tracker)
                    existing_trackers.append([tracker])
        
        # Combine existing and new trackers
        combined_trackers = existing_trackers + unique_trackers
        decoded_data[b'announce-list'] = combined_trackers
        print(f"🔗 Combined with {len(existing_trackers)} existing trackers")
    else:
        decoded_data[b'announce-list'] = unique_trackers
        print("🆕 Created new announce-list")
    
    # Ensure we have a primary announce URL
    if b'announce' not in decoded_data and unique_trackers:
        decoded_data[b'announce'] = unique_trackers[0][0]
        print(f"🏠 Set primary announce: {unique_trackers[0][0].decode('utf-8')}")

    try:
        # Create backup if requested
        if backup and input_path != output_path:
            backup_path = f"{input_path}.backup"
            with open(backup_path, 'wb') as f:
                f.write(torrent_data)
            print(f"💾 Backup created: {backup_path}")
        
        # Write enhanced torrent
        with open(output_path, 'wb') as f:
            f.write(bencode(decoded_data))
        
        # Verify the enhanced torrent can be read
        with open(output_path, 'rb') as f:
            verify_data = bdecode(f.read())
            if verify_data:
                tracker_count = len(verify_data.get(b'announce-list', []))
                print(f"✅ Enhanced torrent saved: {output_path}")
                print(f"📊 Total trackers: {tracker_count}")
                print(f"📁 Torrent name: {verify_data.get(b'info', {}).get(b'name', b'unknown').decode('utf-8', errors='ignore')}")
                
                # Show some tracker examples
                if tracker_count > 0:
                    print("🌐 Sample trackers added:")
                    for i, tracker_group in enumerate(verify_data[b'announce-list'][:3]):
                        for tracker in tracker_group:
                            print(f"   {i+1}. {tracker.decode('utf-8')}")
                    if tracker_count > 3:
                        print(f"   ... and {tracker_count - 3} more trackers")
                
                return output_path
            else:
                print("❌ Failed to verify enhanced torrent")
                return None
                
    except Exception as e:
        print(f"❌ Error writing enhanced torrent: {e}")
        return None


def main():
    """Main function to handle command line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhance torrent files with public trackers')
    parser.add_argument('input', nargs='?', help='Input torrent file path')
    parser.add_argument('-o', '--output', help='Output torrent file path')
    parser.add_argument('--no-backup', action='store_true', help='Skip creating backup')
    
    args = parser.parse_args()
    
    result = enhance_torrent(
        input_path=args.input,
        output_path=args.output,
        backup=not args.no_backup
    )
    
    if result:
        print(f"\n🎉 Success! Use this command to download:")
        print(f"   python main.py {result}")
    else:
        print("\n💥 Failed to enhance torrent file")
        sys.exit(1)


if __name__ == "__main__":
    main()