import math
import hashlib
import time
import os
import logging

def bdecode(data):
    """
    Decode bencoded data with better error handling
    """
    def decode_next(data, index=0):
        if index >= len(data):
            return None, index

        try:
            if data[index] == ord('i'):  # integer
                end_index = data.index(ord('e'), index)
                number_str = data[index+1:end_index]
                if not number_str:
                    raise ValueError("Empty integer")
                number = int(number_str)
                return number, end_index + 1

            elif data[index] == ord('l'):  # list
                index += 1
                result = []
                while index < len(data) and data[index] != ord('e'):
                    item, index = decode_next(data, index)
                    result.append(item)
                if index >= len(data) or data[index] != ord('e'):
                    raise ValueError("Unterminated list")
                return result, index + 1

            elif data[index] == ord('d'):  # dictionary
                index += 1
                result = {}
                while index < len(data) and data[index] != ord('e'):
                    key, index = decode_next(data, index)
                    value, index = decode_next(data, index)
                    if not isinstance(key, bytes):
                        raise ValueError("Dictionary key must be bytes")
                    result[key] = value
                if index >= len(data) or data[index] != ord('e'):
                    raise ValueError("Unterminated dictionary")
                return result, index + 1

            elif data[index] in b'0123456789':  # string
                colon_index = data.index(ord(':'), index)
                length_str = data[index:colon_index]
                if not length_str:
                    raise ValueError("Empty string length")
                length = int(length_str)
                start = colon_index + 1
                end = start + length
                if end > len(data):
                    raise ValueError("String length exceeds data size")
                string_data = data[start:end]
                return string_data, end

            else:
                raise ValueError(f"Invalid bencode format at position {index}: {chr(data[index])}")

        except Exception as e:
            raise ValueError(f"Bdecode error at position {index}: {e}")

    try:
        result, _ = decode_next(data)
        return result
    except Exception as e:
        logging.error(f"Bdecode failed: {e}")
        return None

def bencode(data):
    """
    Encode data to bencode format with better error handling
    """
    try:
        if isinstance(data, int):
            return f"i{data}e".encode()
        elif isinstance(data, bytes):
            return f"{len(data)}:".encode() + data
        elif isinstance(data, str):
            return bencode(data.encode('utf-8'))
        elif isinstance(data, list):
            encoded = b"l"
            for item in data:
                encoded += bencode(item)
            encoded += b"e"
            return encoded
        elif isinstance(data, dict):
            encoded = b"d"
            # Sort keys as required by BitTorrent spec
            for key in sorted(data.keys()):
                if not isinstance(key, (bytes, str)):
                    raise ValueError(f"Invalid dictionary key type: {type(key)}")
                encoded += bencode(key)
                encoded += bencode(data[key])
            encoded += b"e"
            return encoded
        else:
            raise ValueError(f"Unsupported data type: {type(data)}")
    except Exception as e:
        logging.error(f"Bencode failed for {type(data)}: {e}")
        raise

class Torrent:
    def __init__(self):
        self.torrent_file = {}
        self.total_length = 0
        self.piece_length = 0
        self.pieces = b''
        self.info_hash = b''
        self.peer_id = b''
        self.announce_list = []
        self.file_names = []
        self.number_of_pieces = 0
        self.name = ''

    def load_from_path(self, path):
        """Load and parse torrent file with comprehensive error handling"""
        try:
            if not os.path.exists(path):
                logging.error(f"Torrent file not found: {path}")
                return None
                
            file_size = os.path.getsize(path)
            if file_size == 0:
                logging.error("Torrent file is empty")
                return None
                
            print(f"📁 Loading torrent: {os.path.basename(path)} ({file_size} bytes)")
            
            with open(path, 'rb') as f:
                file_data = f.read()
                self.torrent_file = bdecode(file_data)
                
        except Exception as e:
            logging.error(f"Failed to read/decode torrent file: {e}")
            return None

        # Validate torrent structure
        if not self.torrent_file:
            logging.error("Torrent file is empty or invalid")
            return None
            
        if b'info' not in self.torrent_file:
            logging.error("Torrent file missing 'info' dictionary")
            available_keys = [k.decode('utf-8', errors='replace') for k in self.torrent_file.keys()]
            logging.error(f"Available keys: {available_keys}")
            return None

        try:
            info = self.torrent_file[b'info']
            
            # Extract basic info with validation
            self.piece_length = info.get(b'piece length', 0)
            if self.piece_length <= 0:
                logging.error("Invalid piece length in torrent")
                return None
                
            self.pieces = info.get(b'pieces', b'')
            if not self.pieces:
                logging.error("No pieces data in torrent")
                return None
                
            # Decode name safely
            name_bytes = info.get(b'name', b'unknown')
            try:
                self.name = name_bytes.decode('utf-8')
            except UnicodeDecodeError:
                self.name = name_bytes.decode('utf-8', errors='replace')
                logging.warning(f"Used replacement characters for torrent name: {self.name}")
            
            # Calculate info hash
            encoded_info = bencode(info)
            if not encoded_info:
                logging.error("Failed to encode info dictionary")
                return None
                
            self.info_hash = hashlib.sha1(encoded_info).digest()
            
            # Generate peer ID
            self.peer_id = self._generate_peer_id()
            
            # Get trackers
            self.announce_list = self._get_trackers()
            
            # Initialize files
            if not self._init_files():
                return None
            
            # Calculate number of pieces
            piece_data_length = len(self.pieces)
            if piece_data_length % 20 != 0:
                logging.error(f"Invalid pieces data length: {piece_data_length} (not divisible by 20)")
                return None
                
            self.number_of_pieces = piece_data_length // 20
            
            # Validate piece count matches calculated
            calculated_pieces = math.ceil(self.total_length / self.piece_length)
            if self.number_of_pieces != calculated_pieces:
                logging.warning(f"Piece count mismatch: announced={self.number_of_pieces}, calculated={calculated_pieces}")
                # Use the calculated value as it's more reliable
                self.number_of_pieces = calculated_pieces
            
            print(f"✅ Torrent loaded: {self.name}")
            print(f"📊 Total size: {self._format_size(self.total_length)}")
            print(f"🧩 Pieces: {self.number_of_pieces}")
            print(f"🌐 Trackers: {len(self.announce_list)}")
            
            return self
            
        except Exception as e:
            logging.error(f"Failed to process torrent info: {e}")
            return None

    def _init_files(self):
        """Initialize file structure with error handling"""
        info = self.torrent_file[b'info']
        self.file_names = []
        self.total_length = 0
        
        try:
            if b'files' in info:
                # Multi-file torrent
                print("📂 Multi-file torrent detected")
                
                # Create root directory
                if not os.path.exists(self.name):
                    os.makedirs(self.name, exist_ok=True)
                    
                for file_info in info[b'files']:
                    if b'path' not in file_info or b'length' not in file_info:
                        logging.warning("Skipping file with missing path or length")
                        continue
                        
                    # Decode path parts safely
                    path_parts = []
                    for part in file_info[b'path']:
                        try:
                            decoded_part = part.decode('utf-8')
                        except UnicodeDecodeError:
                            decoded_part = part.decode('utf-8', errors='replace')
                        path_parts.append(decoded_part)
                    
                    file_path = os.path.join(self.name, *path_parts)
                    
                    # Create directory if needed
                    dir_path = os.path.dirname(file_path)
                    if dir_path and not os.path.exists(dir_path):
                        os.makedirs(dir_path, exist_ok=True)
                        
                    file_length = file_info[b'length']
                    self.file_names.append({
                        "path": file_path,
                        "length": file_length
                    })
                    self.total_length += file_length
                    
                    print(f"  📄 {file_path} ({self._format_size(file_length)})")
                    
            else:
                # Single file torrent
                print("📄 Single-file torrent detected")
                file_length = info.get(b'length', 0)
                if file_length <= 0:
                    logging.error("Invalid file length in single-file torrent")
                    return False
                    
                self.file_names.append({
                    "path": self.name,
                    "length": file_length
                })
                self.total_length = file_length
                print(f"  📄 {self.name} ({self._format_size(file_length)})")
                
            if self.total_length <= 0:
                logging.error("Total torrent size is 0 or negative")
                return False
                
            return True
            
        except Exception as e:
            logging.error(f"Failed to initialize files: {e}")
            return False

    def _get_trackers(self):
        """Extract tracker URLs with error handling"""
        trackers = []
        
        try:
            # Try announce-list first (more common)
            if b'announce-list' in self.torrent_file:
                for tracker_group in self.torrent_file[b'announce-list']:
                    for tracker in tracker_group:
                        try:
                            tracker_url = tracker.decode('utf-8').strip()
                            if tracker_url and tracker_url not in trackers:
                                trackers.append(tracker_url)
                        except UnicodeDecodeError:
                            try:
                                tracker_url = tracker.decode('utf-8', errors='replace').strip()
                                if tracker_url and tracker_url not in trackers:
                                    trackers.append(tracker_url)
                                    logging.warning(f"Used replacement characters for tracker URL: {tracker_url}")
                            except:
                                logging.warning(f"Skipping invalid tracker URL: {tracker}")
            
            # Fall back to single announce
            if not trackers and b'announce' in self.torrent_file:
                try:
                    tracker_url = self.torrent_file[b'announce'].decode('utf-8').strip()
                    if tracker_url:
                        trackers.append(tracker_url)
                except UnicodeDecodeError:
                    try:
                        tracker_url = self.torrent_file[b'announce'].decode('utf-8', errors='replace').strip()
                        if tracker_url:
                            trackers.append(tracker_url)
                    except:
                        logging.warning("Failed to decode announce URL")
            
            # Remove duplicates while preserving order
            seen = set()
            unique_trackers = []
            for tracker in trackers:
                if tracker not in seen:
                    seen.add(tracker)
                    unique_trackers.append(tracker)
                    
            return unique_trackers
            
        except Exception as e:
            logging.error(f"Failed to extract trackers: {e}")
            return []

    def _generate_peer_id(self):
        """Generate peer ID that looks like a common client"""
        # qBittorrent-like ID (more likely to be accepted)
        # Format: -qB4500- + random bytes
        import random
        client_id = b'-qB4500-'
        random_bytes = bytes([random.randint(0, 255) for _ in range(12)])
        return client_id + random_bytes
        
        # Or Transmission-like
        # return b'-TR3000-' + os.urandom(12)

    def get_piece_hash(self, piece_index):
        """Get SHA1 hash for a specific piece"""
        if piece_index < 0 or piece_index >= self.number_of_pieces:
            raise ValueError(f"Invalid piece index: {piece_index}")
            
        start = piece_index * 20
        end = start + 20
        
        if end > len(self.pieces):
            raise ValueError(f"Piece index out of range: {piece_index}")
            
        return self.pieces[start:end]

    def _format_size(self, bytes):
        """Format bytes to human readable size"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes < 1024.0:
                return f"{bytes:.2f} {unit}"
            bytes /= 1024.0
        return f"{bytes:.2f} TB"

    def validate_piece_index(self, piece_index):
        """Validate if piece index is within bounds"""
        return 0 <= piece_index < self.number_of_pieces

    def get_piece_size(self, piece_index):
        """Get size of a specific piece (last piece might be smaller)"""
        if not self.validate_piece_index(piece_index):
            raise ValueError(f"Invalid piece index: {piece_index}")
            
        if piece_index == self.number_of_pieces - 1:
            # Last piece
            return self.total_length - (piece_index * self.piece_length)
        else:
            return self.piece_length