import piece
import bitstring
import logging
import os
import message 


class PiecesManager:
    
    def _process_new_message(self, new_message, peer_obj):
        """Process incoming message from peer with debug info"""
        message_type = type(new_message).__name__
        logging.debug(f"Received {message_type} from {peer_obj.ip}")
        
        if isinstance(new_message, message.Choke):
            peer_obj.handle_choke()
            logging.info(f"Peer {peer_obj.ip} CHOKED us")
            
        elif isinstance(new_message, message.UnChoke):
            peer_obj.handle_unchoke()
            logging.info(f"🎉 Peer {peer_obj.ip} UNCHOKED us! Ready to download!")
            
        elif isinstance(new_message, message.Interested):
            peer_obj.handle_interested()
            logging.info(f"Peer {peer_obj.ip} is interested in our pieces")
            
        # ... rest of your message handling ...
    
    def __init__(self, torrent):
        self.torrent = torrent
        self.number_of_pieces = int(torrent.number_of_pieces)
        self.bitfield = bitstring.BitArray(self.number_of_pieces)
        self.pieces = self._generate_pieces()
        self.files = self._load_files()
        self.complete_pieces = 0

        # Link files to pieces
        for file_info in self.files:
            piece_id = file_info['piece_index']
            self.pieces[piece_id].files.append(file_info)

    def update_bitfield(self, piece_index: int):
        """Update bitfield when piece is completed"""
        self.bitfield[piece_index] = 1

    def receive_block_piece(self, piece_data):
        """Receive a block and update piece"""
        piece_index, block_offset, block_data = piece_data
        
        if self.pieces[piece_index].is_full:
            return

        self.pieces[piece_index].set_block(block_offset, block_data)

        # Check if piece is complete
        if self.pieces[piece_index].are_all_blocks_full():
            if self.pieces[piece_index].set_to_full():
                self.complete_pieces += 1
                self.update_bitfield(piece_index)
                self._write_piece_to_disk(piece_index)

    def get_block(self, piece_index: int, block_offset: int, block_length: int) -> bytes:
        """Get block data from completed piece"""
        if piece_index < len(self.pieces) and self.pieces[piece_index].is_full:
            return self.pieces[piece_index].get_block(block_offset, block_length)
        return None

    def all_pieces_completed(self) -> bool:
        """Check if all pieces are downloaded"""
        for piece in self.pieces:
            if not piece.is_full:
                return False
        return True

    def _generate_pieces(self):
        """Generate all pieces from torrent info"""
        pieces = []
        last_piece = self.number_of_pieces - 1

        for i in range(self.number_of_pieces):
            start = i * 20
            end = start + 20
            piece_hash = self.torrent.pieces[start:end]

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

        for file_info in self.torrent.file_names:
            current_size_file = file_info["length"]
            file_offset = 0

            while current_size_file > 0:
                piece_index = int(piece_offset / self.torrent.piece_length)
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
                # File doesn't exist yet
                with open(path, 'wb') as f:
                    f.seek(file_offset)
                    f.write(piece_data[piece_offset:piece_offset + length])
            except Exception as e:
                logging.error(f"Failed to write to file {path}: {e}")