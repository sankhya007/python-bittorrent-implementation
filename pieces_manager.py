import piece
import bitstring
import logging
import os
import message 
import time


class PiecesManager:
    def __init__(self, torrent):
        self.torrent = torrent
        self.number_of_pieces = int(torrent.number_of_pieces)
        self.bitfield = bitstring.BitArray(self.number_of_pieces)
        self.pieces = self._generate_pieces()
        self.files = self._load_files()
        self.complete_pieces = 0
        self.peer_scorer = None  # Will be set by main.py
        self.total_downloaded = 0
        self.start_time = time.time()

        # Validate piece count
        if len(self.pieces) != self.number_of_pieces:
            logging.error(f"Piece count mismatch: expected {self.number_of_pieces}, got {len(self.pieces)}")
            # Adjust to actual count
            self.number_of_pieces = len(self.pieces)

        # Link files to pieces with bounds checking
        for file_info in self.files:
            piece_id = file_info['piece_index']
            if piece_id < len(self.pieces):
                self.pieces[piece_id].files.append(file_info)

        # Initialize file structure
        self._initialize_files()
        
        logging.info(f"PiecesManager initialized with {self.number_of_pieces} pieces")

    def _initialize_files(self):
        """Create and pre-allocate files with correct sizes"""
        logging.info("Initializing file structure...")
        
        created_files = 0
        for file_info in self.torrent.file_names:
            path = file_info["path"]
            length = file_info["length"]
            
            try:
                # Create directory if needed
                dir_path = os.path.dirname(path)
                if dir_path and not os.path.exists(dir_path):
                    os.makedirs(dir_path, exist_ok=True)
                    logging.debug(f"Created directory: {dir_path}")
                
                # Create file with correct size if it doesn't exist or is wrong size
                if not os.path.exists(path) or os.path.getsize(path) != length:
                    with open(path, 'wb') as f:
                        # Pre-allocate file space efficiently
                        if length > 1024 * 1024:  # For large files, use sparse allocation
                            f.seek(length - 1)
                            f.write(b'\x00')
                        else:
                            # For small files, write actual zeros
                            f.write(b'\x00' * length)
                    
                    logging.debug(f"Initialized file: {path} ({length} bytes)")
                    created_files += 1
                else:
                    logging.debug(f"File already exists with correct size: {path}")
                    
            except Exception as e:
                logging.error(f"Failed to initialize file {path}: {e}")
                # Continue with other files rather than failing completely
        
        logging.info(f"Initialized {created_files} files")

    def update_bitfield(self, piece_index: int):
        """Update bitfield when piece is completed"""
        if 0 <= piece_index < len(self.bitfield):
            self.bitfield[piece_index] = 1
            logging.debug(f"Updated bitfield: piece {piece_index} completed")

    def receive_block_piece(self, piece_data):
        """Receive a block and update piece with peer scoring"""
        piece_index, block_offset, block_data = piece_data
        
        # Validate inputs
        if (piece_index >= len(self.pieces) or 
            piece_index < 0 or 
            not block_data):
            logging.error(f"Invalid block data: piece_index={piece_index}, data_len={len(block_data) if block_data else 0}")
            return

        piece_obj = self.pieces[piece_index]
        
        if piece_obj.is_full:
            logging.debug(f"Piece {piece_index} already complete, ignoring block")
            return

        # Update the block
        piece_obj.set_block(block_offset, block_data)
        self.total_downloaded += len(block_data)

        # Check if piece is complete
        if piece_obj.are_all_blocks_full():
            if piece_obj.set_to_full():
                self.complete_pieces += 1
                self.update_bitfield(piece_index)
                self._write_piece_to_disk(piece_index)
                
                # Update rarest pieces if available
                if hasattr(self, 'rarest_pieces'):
                    self.rarest_pieces.remove_completed_piece(piece_index)
                
                logging.info(f"🎉 Piece {piece_index} completed! "
                           f"Progress: {self.complete_pieces}/{self.number_of_pieces} "
                           f"({self.get_completion_percentage():.1f}%)")

    def get_block(self, piece_index: int, block_offset: int, block_length: int) -> bytes:
        """Get block data from completed piece"""
        if (piece_index < len(self.pieces) and 
            self.pieces[piece_index].is_full):
            return self.pieces[piece_index].get_block(block_offset, block_length)
        return None

    def all_pieces_completed(self) -> bool:
        """Check if all pieces are downloaded"""
        return self.complete_pieces >= self.number_of_pieces

    def get_completion_percentage(self):
        """Get download completion percentage"""
        if self.number_of_pieces == 0:
            return 0.0
        return (self.complete_pieces / self.number_of_pieces) * 100.0

    def get_download_speed(self):
        """Get current download speed in KB/s"""
        elapsed = time.time() - self.start_time
        if elapsed > 0:
            return (self.total_downloaded / 1024) / elapsed
        return 0

    def _generate_pieces(self):
        """Generate all pieces from torrent info with error handling"""
        pieces = []
        
        if not hasattr(self.torrent, 'pieces') or not self.torrent.pieces:
            logging.error("No pieces data in torrent")
            return pieces
            
        piece_hashes = self.torrent.pieces
        last_piece = self.number_of_pieces - 1

        for i in range(self.number_of_pieces):
            try:
                start = i * 20
                end = start + 20
                
                if end > len(piece_hashes):
                    logging.error(f"Invalid piece hash range for piece {i}")
                    piece_hash = b'\x00' * 20  # Fallback hash
                else:
                    piece_hash = piece_hashes[start:end]

                if i == last_piece:
                    # Last piece might be smaller
                    piece_length = self.torrent.total_length - (last_piece * self.torrent.piece_length)
                    if piece_length <= 0:
                        logging.error(f"Invalid last piece length: {piece_length}")
                        piece_length = self.torrent.piece_length
                else:
                    piece_length = self.torrent.piece_length

                pieces.append(piece.Piece(i, piece_length, piece_hash))
                
            except Exception as e:
                logging.error(f"Failed to create piece {i}: {e}")
                # Continue with next piece rather than failing completely

        logging.info(f"Generated {len(pieces)} pieces")
        return pieces

    def _load_files(self):
        """Map files to pieces for writing with error handling"""
        files = []
        piece_offset = 0
        piece_size_used = 0

        if not hasattr(self.torrent, 'file_names') or not self.torrent.file_names:
            logging.error("No file names in torrent")
            return files

        for file_info in self.torrent.file_names:
            current_size_file = file_info["length"]
            file_offset = 0

            while current_size_file > 0:
                piece_index = int(piece_offset / self.torrent.piece_length)
                
                # Safety check
                if piece_index >= len(self.pieces):
                    logging.error(f"Piece index {piece_index} out of range for file {file_info['path']}")
                    break
                    
                piece_size = self.pieces[piece_index].piece_size - piece_size_used

                if current_size_file - piece_size < 0:
                    # File ends in this piece
                    file_data = {
                        "length": current_size_file,
                        "piece_index": piece_index,
                        "file_offset": file_offset,
                        "piece_offset": piece_size_used,
                        "path": file_info["path"]
                    }
                    piece_offset += current_size_file
                    file_offset += current_size_file
                    piece_size_used += current_size_file
                    current_size_file = 0
                else:
                    # File continues to next piece
                    current_size_file -= piece_size
                    file_data = {
                        "length": piece_size,
                        "piece_index": piece_index,
                        "file_offset": file_offset,
                        "piece_offset": piece_size_used,
                        "path": file_info["path"]
                    }
                    piece_offset += piece_size
                    file_offset += piece_size
                    piece_size_used = 0

                files.append(file_data)

        logging.info(f"Mapped {len(files)} file segments to pieces")
        return files

    def _write_piece_to_disk(self, piece_index: int):
        """Write completed piece to disk with error handling"""
        if piece_index >= len(self.pieces):
            logging.error(f"Cannot write piece {piece_index} - out of range")
            return
            
        piece_obj = self.pieces[piece_index]
        if not piece_obj.raw_data:
            logging.error(f"Piece {piece_index} has no data to write")
            return

        successful_writes = 0
        total_writes = len(piece_obj.files)
        
        for file_info in piece_obj.files:
            path = file_info["path"]
            file_offset = file_info["file_offset"]
            piece_offset = file_info["piece_offset"]
            length = file_info["length"]

            try:
                # Create directory if needed
                dir_path = os.path.dirname(path)
                if dir_path and not os.path.exists(dir_path):
                    os.makedirs(dir_path, exist_ok=True)
                
                # Write to file
                with open(path, 'r+b') as f:
                    f.seek(file_offset)
                    data_to_write = piece_obj.raw_data[piece_offset:piece_offset + length]
                    f.write(data_to_write)
                    
                successful_writes += 1
                logging.debug(f"Written {length} bytes to {path} at offset {file_offset}")
                    
            except FileNotFoundError:
                # File doesn't exist yet - create it
                try:
                    with open(path, 'wb') as f:
                        # Ensure file is correct size
                        if file_offset + length > os.path.getsize(path) if os.path.exists(path) else 0:
                            f.truncate(file_offset + length)
                        f.seek(file_offset)
                        data_to_write = piece_obj.raw_data[piece_offset:piece_offset + length]
                        f.write(data_to_write)
                        
                    successful_writes += 1
                    logging.debug(f"Created and written {length} bytes to {path}")
                    
                except Exception as e:
                    logging.error(f"Failed to create and write file {path}: {e}")
                    
            except Exception as e:
                logging.error(f"Failed to write to file {path}: {e}")

        if successful_writes == total_writes:
            logging.debug(f"Successfully wrote piece {piece_index} to all {successful_writes} files")
        else:
            logging.warning(f"Piece {piece_index}: {successful_writes}/{total_writes} files written successfully")

    def get_download_stats(self):
        """Get comprehensive download statistics"""
        elapsed = time.time() - self.start_time
        stats = {
            'completed_pieces': self.complete_pieces,
            'total_pieces': self.number_of_pieces,
            'completion_percentage': self.get_completion_percentage(),
            'downloaded_bytes': self.total_downloaded,
            'download_speed_kbps': self.get_download_speed(),
            'elapsed_time': elapsed,
            'eta_seconds': 0
        }
        
        # Calculate ETA if we're downloading
        if stats['download_speed_kbps'] > 0.1:
            remaining_bytes = self.torrent.total_length - self.total_downloaded
            stats['eta_seconds'] = remaining_bytes / (stats['download_speed_kbps'] * 1024)
            
        return stats

    # REMOVE these methods - they don't belong here and duplicate peers_manager functionality
    # def unchoked_peers_count(self):
    # def log_peer_states(self): 
    # def _process_new_message(self, new_message, peer_obj):