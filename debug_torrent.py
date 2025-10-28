#!/usr/bin/env python3

import os
import sys
import argparse
from torrent import Torrent


def find_torrent_files():
    """Find all torrent files in current directory and subdirectories"""
    torrent_files = []
    
    # Check current directory
    for file in os.listdir('.'):
        if file.endswith('.torrent'):
            torrent_files.append(file)
    
    # Check torrents subdirectory
    torrents_dir = 'torrents'
    if os.path.exists(torrents_dir) and os.path.isdir(torrents_dir):
        for file in os.listdir(torrents_dir):
            if file.endswith('.torrent'):
                torrent_files.append(os.path.join(torrents_dir, file))
    
    return sorted(torrent_files)


def debug_torrent(file_path, verbose=False):
    """Debug a torrent file with comprehensive information"""
    print("=" * 70)
    print("🔧 TORRENT FILE DEBUGGER")
    print("=" * 70)
    
    # Basic file info
    print(f"📁 File: {file_path}")
    print(f"📄 Exists: {os.path.exists(file_path)}")
    
    if not os.path.exists(file_path):
        print("❌ File not found!")
        return False
    
    file_size = os.path.getsize(file_path)
    print(f"💾 Size: {file_size:,} bytes")
    
    if file_size == 0:
        print("❌ File is empty!")
        return False
    
    try:
        # Try to load with Torrent class
        print(f"\n🔄 Loading torrent...")
        torrent = Torrent()
        result = torrent.load_from_path(file_path)
        
        if not result:
            print("❌ Failed to load torrent file")
            return False
        
        print("✅ Torrent loaded successfully!")
        
        # Basic torrent info
        print(f"\n📋 BASIC INFO:")
        print(f"  Name: {torrent.name}")
        print(f"  Total size: {torrent.total_length:,} bytes ({torrent.total_length / 1024 / 1024 / 1024:.2f} GB)")
        print(f"  Piece length: {torrent.piece_length:,} bytes")
        print(f"  Number of pieces: {torrent.number_of_pieces:,}")
        print(f"  Piece hashes length: {len(torrent.pieces)} bytes")
        
        # File structure
        print(f"\n📁 FILE STRUCTURE:")
        if hasattr(torrent, 'file_names') and torrent.file_names:
            if len(torrent.file_names) == 1:
                file_info = torrent.file_names[0]
                print(f"  Single file: {file_info['path']}")
                print(f"    Size: {file_info['length']:,} bytes")
            else:
                print(f"  Multi-file torrent: {len(torrent.file_names)} files")
                total_files_size = sum(f['length'] for f in torrent.file_names)
                print(f"    Total files size: {total_files_size:,} bytes")
                
                if verbose:
                    for i, file_info in enumerate(torrent.file_names[:10]):  # Show first 10 files
                        size_mb = file_info['length'] / 1024 / 1024
                        print(f"    {i+1}. {file_info['path']} ({size_mb:.1f} MB)")
                    if len(torrent.file_names) > 10:
                        print(f"    ... and {len(torrent.file_names) - 10} more files")
        else:
            print("  ❌ No file information found")
        
        # Trackers
        print(f"\n🌐 TRACKERS:")
        if hasattr(torrent, 'announce_list') and torrent.announce_list:
            print(f"  Found {len(torrent.announce_list)} trackers")
            
            # Categorize trackers
            http_trackers = [t for t in torrent.announce_list if t.startswith('http')]
            udp_trackers = [t for t in torrent.announce_list if t.startswith('udp')]
            other_trackers = [t for t in torrent.announce_list if not t.startswith(('http', 'udp'))]
            
            if udp_trackers:
                print(f"    UDP: {len(udp_trackers)} trackers")
                if verbose:
                    for tracker in udp_trackers[:5]:
                        print(f"      • {tracker}")
            
            if http_trackers:
                print(f"    HTTP: {len(http_trackers)} trackers")
                if verbose:
                    for tracker in http_trackers[:5]:
                        print(f"      • {tracker}")
            
            if other_trackers:
                print(f"    Other: {len(other_trackers)} trackers")
                if verbose:
                    for tracker in other_trackers:
                        print(f"      • {tracker}")
            
            if not verbose and (len(udp_trackers) > 5 or len(http_trackers) > 5):
                print(f"    Use -v to see all trackers")
        else:
            print("  ❌ No trackers found")
        
        # Info hash
        print(f"\n🔐 INFO HASH:")
        if hasattr(torrent, 'info_hash') and torrent.info_hash:
            print(f"  SHA1: {torrent.info_hash.hex()}")
        else:
            print("  ❌ No info hash calculated")
        
        # Piece information
        print(f"\n🧩 PIECE INFORMATION:")
        if torrent.number_of_pieces > 0:
            avg_piece_size = torrent.total_length / torrent.number_of_pieces
            print(f"  Average piece size: {avg_piece_size:,.0f} bytes")
            print(f"  Last piece size: {torrent.total_length - ((torrent.number_of_pieces - 1) * torrent.piece_length):,} bytes")
            
            # Show first few piece hashes if verbose
            if verbose and torrent.number_of_pieces > 0:
                print(f"  First 3 piece hashes:")
                for i in range(min(3, torrent.number_of_pieces)):
                    piece_hash = torrent.get_piece_hash(i)
                    print(f"    Piece {i}: {piece_hash.hex()}")
        else:
            print("  ❌ No pieces information")
        
        # Validation
        print(f"\n✅ VALIDATION:")
        issues = []
        
        if torrent.total_length <= 0:
            issues.append("Total length is 0 or negative")
        
        if torrent.piece_length <= 0:
            issues.append("Piece length is 0 or negative")
        
        if torrent.number_of_pieces <= 0:
            issues.append("Number of pieces is 0 or negative")
        
        if not hasattr(torrent, 'announce_list') or not torrent.announce_list:
            issues.append("No trackers found")
        
        piece_hashes_length = len(torrent.pieces) if hasattr(torrent, 'pieces') else 0
        expected_hashes_length = torrent.number_of_pieces * 20
        if piece_hashes_length != expected_hashes_length:
            issues.append(f"Piece hashes length mismatch: {piece_hashes_length} vs expected {expected_hashes_length}")
        
        if issues:
            print("  ❌ Issues found:")
            for issue in issues:
                print(f"    • {issue}")
        else:
            print("  ✅ Torrent file appears valid")
        
        return True
        
    except Exception as e:
        print(f"❌ Error loading torrent: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return False


def main():
    """Main function with command line support"""
    parser = argparse.ArgumentParser(description='Debug torrent file information')
    parser.add_argument('file', nargs='?', help='Torrent file to debug (optional)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Show verbose information')
    parser.add_argument('-l', '--list', action='store_true', help='List all available torrent files')
    
    args = parser.parse_args()
    
    # List available torrent files
    if args.list or not args.file:
        torrent_files = find_torrent_files()
        if torrent_files:
            print("📁 Available torrent files:")
            for i, file in enumerate(torrent_files):
                size = os.path.getsize(file) if os.path.exists(file) else 0
                print(f"  {i+1}. {file} ({size:,} bytes)")
            
            if not args.file:
                if torrent_files:
                    args.file = torrent_files[0]
                    print(f"\n🔧 Debugging first file: {args.file}")
                else:
                    print("❌ No torrent files found!")
                    print("💡 Run python download_torrents.py first")
                    sys.exit(1)
        else:
            print("❌ No torrent files found!")
            print("💡 Run python download_torrents.py first")
            sys.exit(1)
    
    # Debug the specified file
    success = debug_torrent(args.file, args.verbose)
    
    print("=" * 70)
    if success:
        print("🎉 Torrent debug completed successfully!")
    else:
        print("💥 Torrent file has issues!")
        sys.exit(1)


if __name__ == "__main__":
    main()