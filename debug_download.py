# debug_download.py
#!/usr/bin/env python3

import os
import time
from torrent import Torrent
from pieces_manager import PiecesManager

def debug_download_process(torrent_path):
    print("🔍 DEBUGGING DOWNLOAD PROCESS")
    print("=" * 50)
    
    # Load torrent
    torrent = Torrent().load_from_path(torrent_path)
    if not torrent:
        print("❌ Failed to load torrent")
        return
    
    print(f"📁 Torrent: {torrent.name}")
    print(f"📊 Size: {torrent.total_length} bytes")
    print(f"🧩 Pieces: {torrent.number_of_pieces}")
    
    # Check if files already exist
    print("\n📋 CHECKING EXISTING FILES:")
    for file_info in torrent.file_names:
        path = file_info["path"]
        expected_size = file_info["length"]
        
        if os.path.exists(path):
            actual_size = os.path.getsize(path)
            status = "✅ CORRECT" if actual_size == expected_size else "❌ WRONG SIZE"
            print(f"  {path}: {actual_size}/{expected_size} bytes - {status}")
        else:
            print(f"  {path}: ❌ MISSING")
    
    # Initialize pieces manager
    print("\n🧩 INITIALIZING PIECES MANAGER:")
    pieces_manager = PiecesManager(torrent)
    
    # Check piece states
    print("\n🔍 CHECKING PIECE STATES:")
    completed_pieces = 0
    for i, piece in enumerate(pieces_manager.pieces):
        if piece.is_full:
            completed_pieces += 1
            print(f"  Piece {i}: ✅ ALREADY COMPLETE")
        else:
            print(f"  Piece {i}: ⏳ NEEDS DOWNLOAD - {piece.get_completion_percentage():.1f}%")
    
    print(f"\n📊 SUMMARY: {completed_pieces}/{len(pieces_manager.pieces)} pieces already complete")
    
    if completed_pieces == len(pieces_manager.pieces):
        print("🚨 ALL PIECES ALREADY MARKED AS COMPLETE!")
        print("💡 This is why download appears instant")
        print("💡 Check if files were created by previous runs")
    else:
        print("✅ Some pieces need downloading - process should work normally")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python debug_download.py <torrent_file>")
        sys.exit(1)
    
    debug_download_process(sys.argv[1])