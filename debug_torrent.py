import os
from torrent import Torrent

def debug_torrent(file_path):
    print(f"Checking file: {file_path}")
    print(f"File exists: {os.path.exists(file_path)}")
    print(f"File size: {os.path.getsize(file_path)} bytes")
    
    try:
        # Use the Torrent class to load and debug
        torrent = Torrent()
        result = torrent.load_from_path(file_path)
        
        if result:
            print("✓ Torrent loaded successfully!")
            print(f"Name: {torrent.name}")
            print(f"Size: {torrent.total_length} bytes")
            print(f"Pieces: {torrent.number_of_pieces}")
        else:
            print("✗ Failed to load torrent")
            
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_torrent("torrents/debian-13.1.0-amd64-netinst.iso.torrent")