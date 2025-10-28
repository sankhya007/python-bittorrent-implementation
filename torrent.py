import math
import hashlib
import time
import os
import logging

def bdecode(data):
    """
    Decode bencoded data
    """
    def decode_next(data, index=0):
        if index >= len(data):
            return None, index

        if data[index] == ord('i'):  # integer
            end_index = data.index(ord('e'), index)
            number = int(data[index+1:end_index])
            return number, end_index + 1

        elif data[index] == ord('l'):  # list
            index += 1
            result = []
            while data[index] != ord('e'):
                item, index = decode_next(data, index)
                result.append(item)
            return result, index + 1

        elif data[index] == ord('d'):  # dictionary
            index += 1
            result = {}
            while data[index] != ord('e'):
                key, index = decode_next(data, index)
                value, index = decode_next(data, index)
                result[key] = value
            return result, index + 1

        elif data[index] in b'0123456789':  # string
            colon_index = data.index(ord(':'), index)
            length = int(data[index:colon_index])
            start = colon_index + 1
            end = start + length
            string_data = data[start:end]
            return string_data, end

        else:
            raise ValueError(f"Invalid bencode format at position {index}")

    result, _ = decode_next(data)
    return result

def bencode(data):
    """
    Encode data to bencode format
    """
    if isinstance(data, int):
        return f"i{data}e".encode()
    elif isinstance(data, bytes):
        return f"{len(data)}:".encode() + data
    elif isinstance(data, str):
        return bencode(data.encode())
    elif isinstance(data, list):
        encoded = b"l"
        for item in data:
            encoded += bencode(item)
        encoded += b"e"
        return encoded
    elif isinstance(data, dict):
        encoded = b"d"
        for key in sorted(data.keys()):
            encoded += bencode(key)
            encoded += bencode(data[key])
        encoded += b"e"
        return encoded
    else:
        raise ValueError(f"Unsupported data type: {type(data)}")

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
        try:
            with open(path, 'rb') as f:
                # Now use the module-level bdecode function
                self.torrent_file = bdecode(f.read())
        except Exception as e:
            logging.error(f"Failed to parse torrent file: {e}")
            return None

        # Check if this is a valid torrent file
        if not self.torrent_file:
            logging.error("Torrent file is empty or invalid")
            return None
            
        if b'info' not in self.torrent_file:
            logging.error("Torrent file missing 'info' dictionary")
            logging.error(f"Available keys: {list(self.torrent_file.keys())}")
            return None

        # Extract basic info
        info = self.torrent_file[b'info']
        self.piece_length = info[b'piece length']
        self.pieces = info[b'pieces']
        self.name = info[b'name'].decode('utf-8')
        
        # Calculate info hash - use the module-level bencode function
        encoded_info = bencode(info)
        self.info_hash = hashlib.sha1(encoded_info).digest()
        
        # Generate peer ID
        self.peer_id = self._generate_peer_id()
        
        # Get trackers
        self.announce_list = self._get_trackers()
        
        # Initialize files
        self._init_files()
        
        # Calculate number of pieces
        self.number_of_pieces = math.ceil(self.total_length / self.piece_length)
        
        logging.info(f"Loaded torrent: {self.name}")
        logging.info(f"Total length: {self.total_length} bytes")
        logging.info(f"Number of pieces: {self.number_of_pieces}")
        
        return self

    def _init_files(self):
        info = self.torrent_file[b'info']
        
        if b'files' in info:
            # Multi-file torrent
            if not os.path.exists(self.name):
                os.makedirs(self.name, exist_ok=True)
                
            for file_info in info[b'files']:
                path_parts = [part.decode('utf-8') for part in file_info[b'path']]
                file_path = os.path.join(self.name, *path_parts)
                
                # Create directory if needed
                dir_path = os.path.dirname(file_path)
                if not os.path.exists(dir_path):
                    os.makedirs(dir_path, exist_ok=True)
                    
                self.file_names.append({
                    "path": file_path,
                    "length": file_info[b'length']
                })
                self.total_length += file_info[b'length']
        else:
            # Single file torrent
            self.file_names.append({
                "path": self.name,
                "length": info[b'length']
            })
            self.total_length = info[b'length']

    def _get_trackers(self):
        trackers = []
        
        if b'announce-list' in self.torrent_file:
            for tracker_group in self.torrent_file[b'announce-list']:
                for tracker in tracker_group:
                    trackers.append(tracker.decode('utf-8'))
        elif b'announce' in self.torrent_file:
            trackers.append(self.torrent_file[b'announce'].decode('utf-8'))
            
        return trackers

    def _generate_peer_id(self):
        return b'-PC0001-' + os.urandom(12)

    def get_piece_hash(self, piece_index):
        start = piece_index * 20
        end = start + 20
        return self.pieces[start:end]