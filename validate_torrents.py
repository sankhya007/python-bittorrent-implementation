#!/usr/bin/env python3

from debug_torrent import find_torrent_files, debug_torrent
import sys

def validate_all_torrents():
    """Validate all torrent files in the directory"""
    torrent_files = find_torrent_files()
    
    if not torrent_files:
        print("❌ No torrent files found!")
        return False
    
    print(f"🔍 Validating {len(torrent_files)} torrent files...")
    print()
    
    valid_count = 0
    for torrent_file in torrent_files:
        print(f"Checking: {torrent_file}")
        if debug_torrent(torrent_file, verbose=False):
            valid_count += 1
            print("✅ VALID\n")
        else:
            print("❌ INVALID\n")
    
    print(f"📊 Results: {valid_count}/{len(torrent_files)} torrent files are valid")
    return valid_count == len(torrent_files)

if __name__ == "__main__":
    if validate_all_torrents():
        print("🎉 All torrent files are valid!")
        sys.exit(0)
    else:
        print("💥 Some torrent files have issues!")
        sys.exit(1)