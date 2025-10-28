import piece
import bitstring
import logging
import os
import message 


class PiecesManager:
    def __init__(self, torrent):
        self.torrent = torrent
        self.number_of_pieces = int(torrent.number_of_pieces)
        self.bitfield = bitstring.BitArray(self.number_of_pieces)
        self.pieces = self._generate_pieces()
        self.files = self._load_files()
        self.complete_pieces = 0
        self.peer_scorer = None  # Will be set by main.py

        # Link files to pieces
        for file_info in self.files:
            piece_id = file_info['piece_index']
            if piece_id < len(self.pieces):
                self.pieces[piece_id].files.append(file_info)

        # Initialize file structure
        self._initialize_files()

    def _initialize_files(self):
        """Create initial file structure with correct sizes"""
        for file_info in self.torrent.file_names:
            path = file_info["path"]
            length = file_info["length"]
            
            try:
                # Create directory if needed
                os.makedirs(os.path.dirname(path), exist_ok=True)
                
                # Create file with correct size
                with open(path, 'wb') as f:
                    f.seek(length - 1)
                    f.write(b'\x00')  # Create sparse file
                    
            except Exception as e:
                logging.error(f"Failed to initialize file {path}: {e}")

    def update_bitfield(self, piece_index: int):
        """Update bitfield when piece is completed"""
        if piece_index < len(self.bitfield):
            self.bitfield[piece_index] = 1

    def receive_block_piece(self, piece_data):
        """Receive a block and update piece"""
        piece_index, block_offset, block_data = piece_data
        
        # Validate piece index
        if piece_index >= len(self.pieces):
            logging.error(f"Invalid piece index: {piece_index}")
            return

        piece_obj = self.pieces[piece_index]
        
        if piece_obj.is_full:
            return

        piece_obj.set_block(block_offset, block_data)

        # Check if piece is complete
        if piece_obj.are_all_blocks_full():
            if piece_obj.set_to_full():
                self.complete_pieces += 1
                self.update_bitfield(piece_index)
                self._write_piece_to_disk(piece_index)
                logging.info(f"✅ Piece {piece_index} completed! Total: {self.complete_pieces}/{self.number_of_pieces}")

    def get_block(self, piece_index: int, block_offset: int, block_length: int) -> bytes:
        """Get block data from completed piece"""
        if (piece_index < len(self.pieces) and 
            self.pieces[piece_index].is_full):
            return self.pieces[piece_index].get_block(block_offset, block_length)
        return None

    def all_pieces_completed(self) -> bool:
        """Check if all pieces are downloaded"""
        return self.complete_pieces >= self.number_of_pieces

    def _generate_pieces(self):
        """Generate all pieces from torrent info"""
        pieces = []
        
        if not hasattr(self.torrent, 'pieces') or not self.torrent.pieces:
            logging.error("No pieces data in torrent")
            return pieces
            
        piece_hashes = self.torrent.pieces
        last_piece = self.number_of_pieces - 1

        for i in range(self.number_of_pieces):
            start = i * 20
            end = start + 20
            
            if end > len(piece_hashes):
                logging.error(f"Invalid piece hash range for piece {i}")
                piece_hash = b'\x00' * 20  # Fallback
            else:
                piece_hash = piece_hashes[start:end]

            if i == last_piece:
                # Last piece might be smaller
                piece_length = self.torrent.total_length - (last_piece * self.torrent.piece_length)
            else:
                piece_length = self.torrent.piece_length

            pieces.append(piece.Piece(i, piece_length, piece_hash))

        return pieces

    def _load_files(self):
        """Map files to pieces for writing"""
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
                if piece_index >= self.number_of_pieces:
                    logging.error(f"Piece index {piece_index} out of range")
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

        return files

    def _write_piece_to_disk(self, piece_index: int):
        """Write completed piece to disk"""
        if piece_index >= len(self.pieces):
            logging.error(f"Cannot write piece {piece_index} - out of range")
            return
            
        piece_data = self.pieces[piece_index].raw_data
        
        for file_info in self.pieces[piece_index].files:
            path = file_info["path"]
            file_offset = file_info["file_offset"]
            piece_offset = file_info["piece_offset"]
            length = file_info["length"]

            try:
                # Create directory if needed
                os.makedirs(os.path.dirname(path), exist_ok=True)
                
                # Write to file
                with open(path, 'r+b') as f:
                    f.seek(file_offset)
                    f.write(piece_data[piece_offset:piece_offset + length])
                    
            except FileNotFoundError:
                # File doesn't exist yet - create it
                try:
                    with open(path, 'wb') as f:
                        # If it's a new file, we might need to seek to position
                        if file_offset > 0:
                            f.seek(file_offset - 1)
                            f.write(b'\x00')  # Create space
                        f.seek(file_offset)
                        f.write(piece_data[piece_offset:piece_offset + length])
                except Exception as e:
                    logging.error(f"Failed to create and write file {path}: {e}")
                    
            except Exception as e:
                logging.error(f"Failed to write to file {path}: {e}")

    # REMOVE these methods - they don't belong here and duplicate peers_manager functionality
    # def unchoked_peers_count(self):
    # def log_peer_states(self): 
    # def _process_new_message(self, new_message, peer_obj):