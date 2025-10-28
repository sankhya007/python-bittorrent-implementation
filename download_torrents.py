import requests
import os

def download_torrent(url, filename):
    try:
        print(f"Downloading {filename}...")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        with open(filename, 'wb') as f:
            f.write(response.content)
        print(f"✅ Downloaded: {filename} ({len(response.content)} bytes)")
        return True
    except Exception as e:
        print(f"❌ Failed to download {filename}: {e}")
        return False

# Try multiple torrent sources
torrents = [
    ("https://cdimage.debian.org/debian-cd/current/amd64/bt-cd/debian-12.2.0-amd64-netinst.iso.torrent", "debian-new.torrent"),
    ("https://download.fedoraproject.org/pub/fedora/linux/releases/40/Workstation/x86_64/iso/Fedora-Workstation-Live-x86_64-40-1.14.torrent", "fedora.torrent"),
    ("https://torrent.ubuntu.com/ubuntu/releases/22.04.4/torrents/ubuntu-22.04.4-desktop-amd64.iso.torrent", "ubuntu-new.torrent")
]

for url, filename in torrents:
    if download_torrent(url, filename):
        break
else:
    print("All torrent downloads failed. Creating a test torrent file...")
    
    # Create a minimal test torrent
    test_torrent = {
        b'announce': b'http://tracker.example.com:6969/announce',
        b'info': {
            b'name': b'test-file.txt',
            b'piece length': 262144,
            b'pieces': b'\x00' * 20,  # Fake piece hash
            b'length': 1024
        }
    }
    
    from torrent import bencode
    with open('test.torrent', 'wb') as f:
        f.write(bencode(test_torrent))
    print("✅ Created test.torrent for debugging")