import logging


class RarestPieces:
    def __init__(self, pieces_manager):
        self.pieces_manager = pieces_manager
        self.rarest_pieces = []

        # Initialize with all pieces
        for piece_index in range(self.pieces_manager.number_of_pieces):
            self.rarest_pieces.append({
                "piece_index": piece_index,
                "number_of_peers": 0,
                "peers": []
            })

    def update_peer_bitfield(self, bitfield, peer):
        """Update piece availability when peer bitfield changes"""
        for piece_info in self.rarest_pieces:
            piece_index = piece_info["piece_index"]
            
            # Skip if piece is already completed
            if self.pieces_manager.pieces[piece_index].is_full:
                continue
                
            # Check if peer has this piece
            if bitfield[piece_index] and peer not in piece_info["peers"]:
                piece_info["peers"].append(peer)
                piece_info["number_of_peers"] = len(piece_info["peers"])

    def remove_completed_piece(self, piece_index):
        """Remove piece from tracking when completed"""
        for i, piece_info in enumerate(self.rarest_pieces):
            if piece_info["piece_index"] == piece_index:
                del self.rarest_pieces[i]
                break

    def get_rarest_piece(self):
        """Get the rarest piece that's not yet completed"""
        if not self.rarest_pieces:
            return None

        # Sort by number of peers (rarest first)
        sorted_pieces = sorted(self.rarest_pieces, key=lambda x: x['number_of_peers'])
        
        for piece_info in sorted_pieces:
            piece_index = piece_info["piece_index"]
            
            # Skip if piece is already being downloaded or completed
            if not self.pieces_manager.pieces[piece_index].is_full:
                return piece_index
                
        return None

    def get_sorted_pieces(self):
        """Get all pieces sorted by rarity"""
        return sorted(self.rarest_pieces, key=lambda x: x['number_of_peers'])