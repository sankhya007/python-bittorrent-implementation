🧲 Python BitTorrent Client
============================

A fully-featured, production-ready BitTorrent client implemented from scratch in Python. 
This isn't just another toy implementation - it's a robust, efficient client with smart 
peer selection, comprehensive error handling, and real-world performance optimizations.

📋 Table of Contents
• Features
• Architecture Overview
• Installation
• Quick Start
• Usage Examples
• Advanced Usage
• Project Structure
• Protocol Support
• Performance Features
• Troubleshooting
• Contributing
• License

✨ Features
===========

🚀 Core Capabilities
• Full BitTorrent Protocol - Complete implementation of the BitTorrent specification
• Multi-Tracker Support - HTTP & UDP trackers with automatic fallback
• Smart Peer Selection - Performance-based peer scoring and rarest-piece-first algorithm
• Efficient Downloading - Parallel piece downloads with intelligent request scheduling
• File Management - Support for both single-file and multi-file torrents
• Memory Efficient - Stream-based processing for large files

🎯 Advanced Features
• Peer Scoring System - Dynamic peer performance evaluation
• Rarest-First Algorithm - Optimized piece selection for swarm health
• Comprehensive Error Handling - Network resilience and corruption recovery
• Real-time Progress Tracking - Live download statistics and ETA
• Automatic Retry Logic - Exponential backoff for failed connections
• Connection Pooling - Efficient management of multiple peer connections

🔧 Utility Tools
• Torrent Debugger - Analyze and validate torrent files
• Tracker Debugger - Test tracker connectivity and peer discovery
• Network Diagnostics - Comprehensive connectivity testing
• Torrent Enhancer - Add public trackers to improve availability
• Torrent Downloader - Fetch test torrents automatically

🏗 Architecture Overview
=======================

The client follows a modular, thread-safe architecture:

Main Controller (main.py)
├── Torrent Parser (torrent.py) - Bencode decoding/encoding
├── Tracker Manager (tracker.py) - Peer discovery via HTTP/UDP
├── Peer Manager (peers_manager.py) - Connection pool management
├── Pieces Manager (pieces_manager.py) - Download orchestration
├── Piece Manager (piece.py) - Individual piece handling
├── Block Manager (block.py) - 16KB block operations
└── Rarest Pieces (rarest_piece.py) - Optimized piece selection

📥 Installation
===============

Prerequisites
• Python 3.8 or higher
• 50MB free disk space
• Network connectivity (obviously!)

1. Clone the repository:
git clone https://github.com/yourusername/python-bittorrent-client.git
cd python-bittorrent-client

2. Install dependencies:
pip install requests bitstring

3. Verify installation:
python main.py --help

🚀 Quick Start
==============

1. Get a torrent file:
python download_torrents.py

2. Enhance with public trackers (optional):
python enhance_torrents.py

3. Start downloading:
python main.py ubuntu-22.04.torrent

4. Monitor progress:
📥  15.25% | ⏱️  45m 30s | 🚀  1250.5 KB/s | 🧩   152/1200 | 🔗   8 peers

📖 Usage Examples
=================

Basic Download
python main.py debian-12.2.0-amd64-netinst.iso.torrent

Debug Torrent File
python debug_torrent.py my_torrent.torrent -v

Test Tracker Connectivity
python debug_tracker.py my_torrent.torrent --verbose

Enhance Torrent with Trackers
python enhance_torrent.py ubuntu.torrent -o ubuntu_enhanced.torrent

Test Network Connectivity
python test_connectivity.py

🔧 Advanced Usage
=================

Performance Tuning
# Increase concurrent peers (default: 15)
Edit peers_manager.py: max_peers_connected = 25

# Adjust request timeouts (default: 30s)
Edit peer.py: timeout_seconds = 45

# Modify block size (default: 16KB)
Edit block.py: BLOCK_SIZE = 2 ** 14  # 16KB

Monitoring and Debugging
# Enable detailed logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Real-time peer statistics
python main.py torrent.file 2>&1 | grep "Peer stats"

# Download progress to file
python main.py torrent.file > download.log 2>&1

📁 Project Structure
====================

python-bittorrent-client/
├── core/
│   ├── main.py              # Main client and controller
│   ├── torrent.py           # Torrent file parsing (bencode)
│   ├── tracker.py           # Tracker communication
│   ├── peer.py              # Peer connection management
│   ├── message.py           # Protocol message handling
│   ├── pieces_manager.py    # Download orchestration
│   ├── piece.py             # Piece management
│   ├── block.py             # Block operations
│   ├── peers_manager.py     # Peer connection pool
│   └── rarest_piece.py      # Rarest-first algorithm
├── utilities/
│   ├── debug_torrent.py     # Torrent file analysis
│   ├── debug_tracker.py     # Tracker connectivity testing
│   ├── download_torrents.py # Torrent file fetcher
│   ├── enhance_torrents.py  # Tracker enhancer
│   ├── validate_torrents.py # Torrent validation
│   └── test_connectivity.py # Network diagnostics
├── logs/
│   └── bittorrent_client.log # Automatic logging
└── downloads/               # Completed files

📡 Protocol Support
===================

✅ Fully Implemented
• BitTorrent Protocol v1.0
• HTTP Trackers (announce/scrape)
• UDP Trackers (connection/announce)
• Bencoding (decode/encode)
• Piece/Block protocol
• Peer wire protocol
• Choking/Unchoking algorithm
• Interested/Not Interested
• Have/Piece messages

🔜 Planned Features
• DHT (Distributed Hash Table)
• Magnet URI support
• Peer Exchange (PEX)
• UDP Hole Punching

⚡ Performance Features
======================

Smart Peer Selection
• Dynamic scoring based on transfer speed, reliability, and response time
• Automatic unhealthy peer detection and removal
• Priority given to unchoked, high-performance peers

Efficient Resource Usage
• Non-blocking I/O with select() for socket management
• Memory-mapped file writing for large downloads
• Configurable connection limits to prevent overload

Download Optimization
• Rarest-piece-first algorithm for better swarm participation
• Parallel block requests across multiple peers
• Request pipelining and congestion control

Network Resilience
• Automatic retry with exponential backoff
• Multiple tracker fallback support
• Connection keep-alive and health monitoring

🛠 Troubleshooting
==================

Common Issues and Solutions

❌ "No peers found from trackers"
• Run: python test_connectivity.py
• Try: python enhance_torrents.py
• Check firewall/antivirus settings

❌ "Torrent file invalid or corrupted"
• Run: python debug_torrent.py your_file.torrent
• Verify file integrity: python validate_torrents.py

❌ "Download stalls at low percentage"
• This is normal BitTorrent behavior - peers may be choking
• Client will automatically retry and find new peers
• Monitor peer count: python debug_tracker.py your_file.torrent

❌ "Connection timeouts"
• Check: python test_connectivity.py
• Increase timeouts in peer.py
• Verify network stability

📊 Performance Tips

• Use wired connection instead of WiFi for better stability
• Ensure sufficient disk space (torrent size + 10% buffer)
• Run during off-peak hours for better peer availability
• Use enhance_torrents.py to add more trackers

🤝 Contributing
===============

We welcome contributions! Here's how you can help:

1. Fork the repository
2. Create a feature branch: git checkout -b feature/amazing-feature
3. Commit your changes: git commit -m 'Add amazing feature'
4. Push to the branch: git push origin feature/amazing-feature
5. Open a Pull Request

Areas for Contribution
• DHT implementation
• Web interface
• Performance optimizations
• Additional protocol features
• Documentation improvements
• Bug fixes and testing

🌟 Acknowledgments
==================

This implementation represents a complete ground-up rebuild of the BitTorrent protocol
with modern Python practices, comprehensive error handling, and production-ready
reliability. Special thanks to the BitTorrent protocol specification and the open-source
community for reference implementations and testing resources.

---
**Happy Downloading!** 🎉

For support, create an issue on GitHub or check the troubleshooting guide above.