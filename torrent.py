import math
import hashlib
import time
import os
import logging


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
                import bcoding
                self.torrent_file = bcoding.bdecode(f)
        except Exception as e:
            logging.error(f"Failed to parse torrent file: {e}")
            return None

        # Extract basic info
        info = self.torrent_file[b'info']
        self.piece_length = info[b'piece length']
        self.pieces = info[b'pieces']
        self.name = info[b'name'].decode('utf-8')
        
        # Calculate info hash
        import bcoding
        encoded_info = bcoding.bencode(info)
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