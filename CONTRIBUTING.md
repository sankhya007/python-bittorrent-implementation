# Contributing to Python BitTorrent Client

First off, thank you for considering contributing to this project! It's people like you that make open source amazing.

## Quick Start

### 1. Fork the Repository
- Click the "Fork" button at the top right of the GitHub page
- This creates your own copy of the repository

### 2. Clone Your Fork
git clone https://github.com/YOUR_USERNAME/python-bittorrent-client.git
cd python-bittorrent-client

### 3. Set Up Development Environment
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install pytest pylint black

### 4. Create a Branch
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-youre-fixing

## How to Contribute

### Reporting Bugs
Before submitting a bug report:
1. Check if the issue already exists in the Issues tab
2. Test with a small torrent file to confirm the issue
3. Check the logs in bittorrent_client.log

When reporting bugs, include:
- Torrent file (if possible) or magnet link
- Steps to reproduce
- Expected vs actual behavior
- Full error logs
- Your environment (OS, Python version)

### Suggesting Enhancements
We love new ideas! When suggesting features:
- Explain why this feature would be useful
- Describe how it should work
- Consider if it aligns with the BitTorrent protocol
- Check if similar functionality exists already

### Pull Requests
1. Keep it focused - One feature/fix per PR
2. Test thoroughly - Test with different torrents
3. Follow code style - Use existing conventions
4. Update documentation - Include docstrings and comments
5. Add tests if possible

## Development Guide

### Code Standards
- Type Hints: Use Python type hints for all functions
- Docstrings: Include comprehensive docstrings
- Logging: Use appropriate logging levels
- Error Handling: Handle exceptions gracefully

Example:
def download_piece(self, piece_index: int, peer: Peer) -> bool:
    Download a specific piece from a peer.
    
    Args:
        piece_index: Index of the piece to download
        peer: Peer object to download from
        
    Returns:
        bool: True if download successful, False otherwise
        
    Raises:
        ValueError: If piece_index is invalid
        ConnectionError: If peer connection fails
    
    try:
        # Your code here
        return True
    except Exception as e:
        logging.error(f"Failed to download piece {piece_index}: {e}")
        return False

### Testing Your Changes
# Run basic functionality tests
python main.py test.torrent

# Test protocol components
python debug_torrent.py test.torrent
python debug_tracker.py test.torrent

# Run connectivity tests
python test_connectivity.py

# Validate torrent enhancement
python enhance_torrent.py test.torrent

### Project Structure
python-bittorrent-client/
├── core/               # Main application logic
│   ├── main.py         # Entry point and client controller
│   ├── torrent.py      # Torrent file parsing
│   ├── tracker.py      # Tracker communication
│   ├── peer.py         # Peer management
│   └── ...
├── utilities/          # Helper scripts
│   ├── debug_torrent.py
│   ├── enhance_torrent.py
│   └── ...
└── tests/              # Test suite

## Good First Issues

New to the project? Start here:

### Beginner-Friendly
- [ ] Add more public trackers to enhance_torrents.py
- [ ] Improve CLI output formatting and colors
- [ ] Add more detailed logging messages
- [ ] Create better example torrent files
- [ ] Improve error messages for common issues

### Intermediate
- [ ] Implement basic DHT functionality
- [ ] Add magnet link support
- [ ] Create a web interface
- [ ] Add configuration file support
- [ ] Implement peer exchange (PEX)

### Advanced
- [ ] Protocol encryption
- [ ] UDP hole punching
- [ ] Performance optimizations
- [ ] Memory usage improvements

## Pull Request Process

1. Update your fork with the latest changes from main:
   git remote add upstream https://github.com/sankhya007/python-bittorrent-client.git
   git fetch upstream
   git merge upstream/main

2. Test your changes thoroughly:
   # Test with small torrents
   python main.py test.torrent
   
   # Test protocol compliance
   python debug_tracker.py test.torrent --verbose

3. Commit your changes with descriptive messages:
   git add .
   git commit -m "feat: add DHT support for trackerless torrents"
   git push origin your-branch-name

4. Submit Pull Request:
   - Use the PR template
   - Describe what your changes do
   - Mention any related issues
   - Include testing details

### PR Title Convention
- feat: New features
- fix: Bug fixes
- docs: Documentation changes
- style: Code style changes
- refactor: Code refactoring
- test: Test-related changes
- chore: Maintenance tasks

## Debugging Tips

### Common Issues
- No peers found: Run python test_connectivity.py and python enhance_torrents.py
- Download stalls: This is normal BitTorrent behavior - peers may be choking
- Connection errors: Check firewall and network settings

### Getting Help
- Check existing issues and discussions
- Create a new issue with detailed information
- Include relevant log files

## Learning Resources

### BitTorrent Protocol
- Official BitTorrent Protocol Specification
- BitTorrent Enhancement Proposals
- Kademlia DHT Paper

### Python Networking
- Python socket programming
- Python threading guide
- Requests library documentation

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Thank You!

Your contributions are greatly appreciated. Whether you're fixing bugs, adding features, improving documentation, or just reporting issues - thank you for helping make this project better!