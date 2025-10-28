# Python BitTorrent Client

A complete BitTorrent client implementation in Python from scratch. Features full protocol support including torrent parsing, tracker communication, peer-to-peer networking, and file downloading.

## Features

- Torrent File Parsing - Custom bencode implementation for .torrent files
- Tracker Communication - HTTP and UDP tracker support
- Peer Protocol - Full BitTorrent peer wire protocol implementation
- Piece Management - Download and verify pieces with SHA-1 hashing
- File Assembly - Support for single and multi-file torrents
- Rarest-Piece Algorithm - Intelligent piece selection for faster downloads
- Progress Tracking - Real-time download progress and speed monitoring

## Quick Start

### Installation

Clone the repository:
git clone https://github.com/yourusername/python-bittorrent-client.git
cd python-bittorrent-client

Install dependencies:
pip install -r requirements.txt

### Usage

python main.py path/to/your.torrent

The downloaded files will be saved in the downloads/ directory.

## Project Structure

python-bittorrent-client/
- main.py                 # Main application entry point
- torrent.py              # Torrent file parsing and metadata
- tracker.py              # HTTP/UDP tracker communication
- peer.py                 # Individual peer connection management
- peers_manager.py        # Multiple peer coordination
- piece.py                # Piece and block management
- pieces_manager.py       # All pieces and file handling
- message.py              # BitTorrent protocol messages
- block.py                # Block state management
- rarest_piece.py         # Rarest-piece-first algorithm
- requirements.txt        # Python dependencies
- LICENSE                 # MIT License
- README.md              # Documentation

## How It Works

1. Torrent Parsing
- Reads .torrent files using custom bencode decoder
- Extracts metadata, piece hashes, and file information
- Calculates info hash for tracker communication

2. Tracker Communication
- Contacts HTTP and UDP trackers to discover peers
- Handles compact and non-compact peer responses
- Manages connection limits and peer selection

3. Peer Protocol
- Implements BitTorrent handshake and message protocol
- Manages peer states (choked/unchoked, interested/not interested)
- Handles piece requests and data transfer

4. Download Process
- Uses rarest-piece-first algorithm for optimal downloading
- Manages 16KB blocks within pieces
- Verifies piece integrity with SHA-1 hashes
- Assembles files from downloaded pieces

## Requirements

- Python 3.8+
- Dependencies: bitstring, requests

## Educational Value

This project is perfect for learning:
- BitTorrent Protocol - Complete protocol implementation
- P2P Networking - Peer-to-peer communication patterns
- Async Programming - Concurrent socket management
- Protocol Design - Message serialization/deserialization
- File I/O - Efficient file writing and management

## Legal Notice

Only use with legal torrents:
- Linux distribution ISOs (Ubuntu, Debian, etc.)
- Open source software
- Creative Commons content
- Your own files

This project is for educational purposes to understand P2P protocols and networking.

## Development Status

Implemented:
- Torrent file parsing
- HTTP/UDP tracker support
- Peer wire protocol
- Piece downloading and verification
- File assembly
- Progress tracking

Planned Features:
- DHT support (trackerless torrents)
- Magnet link support
- Download resumption
- Web interface
- Multiple torrent management

## Contributing

Contributions are welcome! Feel free to:
- Report bugs and issues
- Suggest new features
- Submit pull requests
- Improve documentation

## Resources

- BitTorrent Protocol Specification
- Python asyncio Documentation

## License

This project is licensed under the MIT License - see the LICENSE file for details.

Disclaimer: Use responsibly and only download content you have rights to.
=======
# python-bittorrent-implementation-
Python BitTorrent Client - Complete protocol implementation from scratch. Features torrent parsing, HTTP/UDP trackers, peer connections, piece management, and file downloading. Educational project for learning P2P networking.

