#!/usr/bin/env python3

import requests
import os
import time
from torrent import bencode, bdecode


def download_torrent(url, filename, max_retries=3):
    """Download a torrent file with retry logic and progress tracking"""
    for attempt in range(max_retries):
        try:
            print(f"⬇️  Downloading {filename}... (attempt {attempt + 1}/{max_retries})")
            
            # Set a reasonable timeout and headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, timeout=15, headers=headers, stream=True)
            response.raise_for_status()
            
            # Get file size for progress tracking
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # Show progress for large files
                        if total_size > 0:
                            percent = (downloaded_size / total_size) * 100
                            print(f"   Progress: {percent:.1f}% ({downloaded_size}/{total_size} bytes)", end='\r')
            
            file_size = os.path.getsize(filename)
            print(f"✅ Downloaded: {filename} ({file_size} bytes)")
            
            # Validate the torrent file
            if validate_torrent_file(filename):
                return True
            else:
                print(f"❌ Downloaded file is not a valid torrent: {filename}")
                os.remove(filename)  # Remove invalid file
                return False
                
        except requests.exceptions.Timeout:
            print(f"⏰ Timeout downloading {filename}")
        except requests.exceptions.ConnectionError:
            print(f"🔌 Connection error downloading {filename}")
        except requests.exceptions.HTTPError as e:
            print(f"🌐 HTTP error {e.response.status_code} downloading {filename}")
        except Exception as e:
            print(f"❌ Error downloading {filename}: {e}")
        
        # Wait before retry
        if attempt < max_retries - 1:
            wait_time = 2 ** attempt  # Exponential backoff
            print(f"⏳ Retrying in {wait_time} seconds...")
            time.sleep(wait_time)
    
    return False


def validate_torrent_file(filename):
    """Validate that a file is a proper torrent file"""
    try:
        with open(filename, 'rb') as f:
            torrent_data = f.read()
        
        if not torrent_data:
            print(f"   ⚠️  File is empty: {filename}")
            return False
        
        decoded = bdecode(torrent_data)
        if not decoded:
            print(f"   ⚠️  Invalid bencode format: {filename}")
            return False
        
        # Check for required torrent fields
        if b'info' not in decoded:
            print(f"   ⚠️  Missing 'info' dictionary: {filename}")
            return False
        
        info = decoded[b'info']
        required_fields = [b'name', b'piece length', b'pieces']
        for field in required_fields:
            if field not in info:
                print(f"   ⚠️  Missing required field '{field.decode()}': {filename}")
                return False
        
        # Check piece hashes
        pieces = info[b'pieces']
        if len(pieces) % 20 != 0:
            print(f"   ⚠️  Invalid pieces length: {len(pieces)}")
            return False
        
        torrent_name = info[b'name'].decode('utf-8', errors='ignore')
        print(f"   ✅ Valid torrent: {torrent_name}")
        return True
        
    except Exception as e:
        print(f"   ⚠️  Validation error: {e}")
        return False


def create_better_test_torrent():
    """Create a more realistic test torrent file"""
    print("🛠️  Creating a realistic test torrent file...")
    
    # Create a more realistic test torrent
    test_torrent = {
        b'announce': b'udp://tracker.opentrackr.org:1337/announce',
        b'announce-list': [
            [b'udp://tracker.opentrackr.org:1337/announce'],
            [b'udp://open.tracker.cl:1337/announce'],
            [b'udp://tracker.openbittorrent.com:6969/announce']
        ],
        b'creation date': int(time.time()),
        b'comment': b'Test torrent for BitTorrent client development',
        b'created by': b'PythonBitTorrentClient/1.0',
        b'info': {
            b'name': b'ubuntu-test-file.iso',
            b'piece length': 262144,  # 256KB
            b'pieces': b'\x8a\x05\x9c\xa1\x8b\xfc\x17\x7f\x1f\x9a\xa3\x7c\x37\x2e\x71\x2a\x2c\x33\x46\x1d' * 10,  # Fake but valid-looking hashes
            b'length': 2621440  # 2.5MB test file
        }
    }
    
    try:
        with open('test.torrent', 'wb') as f:
            f.write(bencode(test_torrent))
        
        file_size = os.path.getsize('test.torrent')
        print(f"✅ Created realistic test.torrent ({file_size} bytes)")
        
        if validate_torrent_file('test.torrent'):
            return True
        else:
            print("❌ Created test torrent is invalid")
            return False
            
    except Exception as e:
        print(f"❌ Failed to create test torrent: {e}")
        return False


def download_torrents():
    """Download torrent files from multiple sources"""
    print("🌐 Attempting to download torrent files...")
    
    # Updated torrent URLs (more reliable sources)
    torrents = [
        # Ubuntu torrents (usually reliable)
        ("https://releases.ubuntu.com/22.04.4/ubuntu-22.04.4-desktop-amd64.iso.torrent", "ubuntu-22.04.torrent"),
        ("https://cdimage.debian.org/debian-cd/current/amd64/bt-cd/debian-12.2.0-amd64-netinst.iso.torrent", "debian-12.2.torrent"),
        
        # Alternative Ubuntu mirror
        ("https://torrent.ubuntu.com/ubuntu/releases/jammy/ubuntu-22.04.3-desktop-amd64.iso.torrent", "ubuntu-22.04.3.torrent"),
        
        # Linux Mint (reliable and popular)
        ("https://mirrors.kernel.org/linuxmint/stable/21.2/linuxmint-21.2-cinnamon-64bit.iso.torrent", "linuxmint.torrent"),
        
        # Small test torrents
        ("https://www.torrent.eu.org/torrents/ubuntu-22.04.3-desktop-amd64.iso.torrent", "ubuntu-test.torrent"),
    ]
    
    downloaded_files = []
    
    for url, filename in torrents:
        # Skip if file already exists and is valid
        if os.path.exists(filename) and validate_torrent_file(filename):
            print(f"📁 Using existing torrent: {filename}")
            downloaded_files.append(filename)
            continue
            
        if download_torrent(url, filename):
            downloaded_files.append(filename)
            # Stop after first successful download to be polite to servers
            print("🎉 Successfully downloaded a torrent file!")
            break
        else:
            print(f"💔 Failed to download: {filename}")
    
    return downloaded_files


def main():
    """Main function to handle torrent downloading"""
    print("=" * 60)
    print("📥 TORRENT DOWNLOADER")
    print("=" * 60)
    
    # Create torrents directory if it doesn't exist
    os.makedirs("torrents", exist_ok=True)
    
    # Try to download torrents
    downloaded_files = download_torrents()
    
    if downloaded_files:
        print(f"\n🎉 Success! Downloaded {len(downloaded_files)} torrent file(s):")
        for file in downloaded_files:
            file_size = os.path.getsize(file)
            print(f"   📄 {file} ({file_size} bytes)")
        
        # Suggest which file to use
        recommended_file = downloaded_files[0]
        print(f"\n💡 Recommended usage:")
        print(f"   python main.py {recommended_file}")
        
        # Also suggest enhancing the torrent
        print(f"   python enhance_torrent.py  # To add more trackers")
        
    else:
        print("\n💔 All torrent downloads failed!")
        print("🛠️  Creating a realistic test torrent...")
        
        if create_better_test_torrent():
            print(f"\n💡 Usage:")
            print(f"   python main.py test.torrent")
        else:
            print("❌ Failed to create test torrent!")
            print("💡 Please manually place a .torrent file in this directory")
    
    print("=" * 60)


if __name__ == "__main__":
    main()