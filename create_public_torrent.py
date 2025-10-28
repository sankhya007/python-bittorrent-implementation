# create_public_torrent.py
#!/usr/bin/env python3
from torrent import bencode
import os

def create_public_test_torrent():
    # Create a small test file first
    test_data = b"This is a test file for BitTorrent client development. " * 1000
    
    with open('test_file.bin', 'wb') as f:
        f.write(test_data)
    
    # Create torrent for the test file
    test_torrent = {
        b'announce': b'udp://tracker.opentrackr.org:1337/announce',
        b'announce-list': [
            [b'udp://tracker.opentrackr.org:1337/announce'],
            [b'udp://open.tracker.cl:1337/announce'],
            [b'udp://tracker.openbittorrent.com:6969/announce'],
            [b'udp://tracker.torrent.eu.org:451/announce'],
            [b'http://tracker.dler.org:6969/announce'],
        ],
        b'creation date': 1000000000,
        b'comment': b'Test torrent for BitTorrent client development',
        b'created by': b'PythonBitTorrentClient/1.0',
        b'info': {
            b'name': b'test_file.bin',
            b'piece length': 262144,  # 256KB
            b'pieces': b'\x8a\x05\x9c\xa1\x8b\xfc\x17\x7f\x1f\x9a\xa3\x7c\x37\x2e\x71\x2a\x2c\x33\x46\x1d' * 2,
            b'length': len(test_data)
        }
    }
    
    with open('test_public.torrent', 'wb') as f:
        f.write(bencode(test_torrent))
    
    print("✅ Created test torrent with public trackers")
    print("📁 Test file: test_file.bin")
    print("🧲 Torrent: test_public.torrent")

if __name__ == "__main__":
    create_public_test_torrent()