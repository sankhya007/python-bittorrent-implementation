import logging
import heapq
import time


class RarestPieces:
    def __init__(self, pieces_manager):
        self.pieces_manager = pieces_manager
        self.rarest_pieces = []  # Min-heap for efficient rarest piece access
        self.piece_info_map = {}  # Quick lookup by piece_index
        self.last_optimization = time.time()
        
        self._initialize_pieces()
        
        logging.info(f"RarestPieces initialized with {len(self.rarest_pieces)} pieces")

    def _initialize_pieces(self):
        """Initialize all pieces with efficient data structures"""
        self.rarest_pieces = []
        self.piece_info_map = {}
        
        for piece_index in range(self.pieces_manager.number_of_pieces):
            piece_info = {
                "piece_index": piece_index,
                "number_of_peers": 0,
                "peers": set(),  # Use set for O(1) lookups
                "last_accessed": time.time()
            }
            
            # Add to both structures
            heapq.heappush(self.rarest_pieces, (piece_info["number_of_peers"], piece_index, piece_info))
            self.piece_info_map[piece_index] = piece_info

    def update_peer_bitfield(self, bitfield, peer):
        """Update piece availability when peer bitfield changes"""
        if not bitfield or len(bitfield) != self.pieces_manager.number_of_pieces:
            logging.warning(f"Invalid bitfield length from peer {peer.ip}")
            return

        updated_pieces = 0
        for piece_index in range(min(len(bitfield), self.pieces_manager.number_of_pieces)):
            # Skip completed pieces
            if (piece_index >= len(self.pieces_manager.pieces) or 
                self.pieces_manager.pieces[piece_index].is_full):
                continue
                
            if bitfield[piece_index]:
                if self._add_peer_to_piece(piece_index, peer):
                    updated_pieces += 1

        if updated_pieces > 0:
            logging.debug(f"Updated {updated_pieces} pieces for peer {peer.ip}")

    def _add_peer_to_piece(self, piece_index, peer):
        """Add a peer to a piece's availability list"""
        if piece_index not in self.piece_info_map:
            logging.warning(f"Piece {piece_index} not found in piece_info_map")
            return False

        piece_info = self.piece_info_map[piece_index]
        
        if peer not in piece_info["peers"]:
            piece_info["peers"].add(peer)
            old_count = piece_info["number_of_peers"]
            piece_info["number_of_peers"] = len(piece_info["peers"])
            piece_info["last_accessed"] = time.time()
            
            # If count changed, we need to re-heapify (done lazily in get_rarest_piece)
            return old_count != piece_info["number_of_peers"]
        
        return False

    def remove_peer_from_all_pieces(self, peer):
        """Remove a peer from all pieces (when peer disconnects)"""
        removed_count = 0
        for piece_info in self.piece_info_map.values():
            if peer in piece_info["peers"]:
                piece_info["peers"].discard(peer)
                piece_info["number_of_peers"] = len(piece_info["peers"])
                removed_count += 1
        
        if removed_count > 0:
            logging.debug(f"Removed peer {peer.ip} from {removed_count} pieces")

    def remove_completed_piece(self, piece_index):
        """Remove piece from tracking when completed"""
        if piece_index in self.piece_info_map:
            # Mark as completed but don't remove from map (for stats)
            piece_info = self.piece_info_map[piece_index]
            piece_info["completed"] = True
            piece_info["peers"].clear()
            piece_info["number_of_peers"] = 0
            
            logging.debug(f"Marked piece {piece_index} as completed")

    def get_rarest_piece(self, excluded_pieces=None):
        """Get the rarest piece that's not yet completed"""
        if not self.rarest_pieces:
            return None

        # Rebuild heap periodically for efficiency
        self._optimize_if_needed()

        excluded_set = set(excluded_pieces) if excluded_pieces else set()
        
        # Create temporary min-heap with only available pieces
        available_pieces = []
        for piece_info in self.piece_info_map.values():
            piece_index = piece_info["piece_index"]
            
            # Skip if completed, being downloaded, or excluded
            if (piece_info.get("completed") or 
                piece_index in excluded_set or
                piece_index >= len(self.pieces_manager.pieces) or
                self.pieces_manager.pieces[piece_index].is_full):
                continue
                
            # Only consider pieces that have at least one peer
            if piece_info["number_of_peers"] > 0:
                heapq.heappush(available_pieces, 
                             (piece_info["number_of_peers"], 
                              piece_info["last_accessed"], 
                              piece_index))

        if available_pieces:
            # Get the rarest piece (lowest peer count)
            rarest_count, last_accessed, rarest_index = heapq.heappop(available_pieces)
            
            # Update access time
            if rarest_index in self.piece_info_map:
                self.piece_info_map[rarest_index]["last_accessed"] = time.time()
            
            logging.debug(f"Selected rarest piece {rarest_index} with {rarest_count} peers")
            return rarest_index
        
        logging.debug("No available pieces found for download")
        return None

    def get_rarest_pieces(self, count=5, excluded_pieces=None):
        """Get multiple rarest pieces for parallel downloading"""
        if not self.rarest_pieces:
            return []

        self._optimize_if_needed()
        excluded_set = set(excluded_pieces) if excluded_pieces else set()
        
        available_pieces = []
        for piece_info in self.piece_info_map.values():
            piece_index = piece_info["piece_index"]
            
            if (piece_info.get("completed") or 
                piece_index in excluded_set or
                piece_index >= len(self.pieces_manager.pieces) or
                self.pieces_manager.pieces[piece_index].is_full):
                continue
                
            if piece_info["number_of_peers"] > 0:
                available_pieces.append((
                    piece_info["number_of_peers"],
                    piece_info["last_accessed"],
                    piece_index
                ))

        # Sort by rarity (lowest peer count first) then by recent access
        available_pieces.sort(key=lambda x: (x[0], x[1]))
        
        result = [piece_index for _, _, piece_index in available_pieces[:count]]
        
        # Update access times
        for piece_index in result:
            if piece_index in self.piece_info_map:
                self.piece_info_map[piece_index]["last_accessed"] = time.time()
        
        logging.debug(f"Selected {len(result)} rarest pieces: {result}")
        return result

    def _optimize_if_needed(self):
        """Rebuild heap if it's been a while or if it's too inefficient"""
        current_time = time.time()
        if current_time - self.last_optimization > 30:  # Rebuild every 30 seconds
            self._rebuild_heap()
            self.last_optimization = current_time

    def _rebuild_heap(self):
        """Rebuild the heap from scratch for efficiency"""
        logging.debug("Rebuilding rarest pieces heap")
        self.rarest_pieces = []
        for piece_index, piece_info in self.piece_info_map.items():
            if not piece_info.get("completed"):
                heapq.heappush(self.rarest_pieces, 
                             (piece_info["number_of_peers"], piece_index, piece_info))

    def get_piece_availability(self, piece_index):
        """Get availability information for a specific piece"""
        if piece_index in self.piece_info_map:
            info = self.piece_info_map[piece_index]
            return {
                "piece_index": piece_index,
                "peer_count": info["number_of_peers"],
                "completed": info.get("completed", False),
                "peers": list(info["peers"])
            }
        return None

    def get_availability_stats(self):
        """Get statistics about piece availability"""
        total_pieces = len(self.piece_info_map)
        completed_pieces = sum(1 for info in self.piece_info_map.values() 
                             if info.get("completed"))
        available_pieces = sum(1 for info in self.piece_info_map.values() 
                             if info["number_of_peers"] > 0 and not info.get("completed"))
        
        # Calculate average availability
        if available_pieces > 0:
            total_peers = sum(info["number_of_peers"] 
                            for info in self.piece_info_map.values() 
                            if not info.get("completed"))
            avg_availability = total_peers / available_pieces
        else:
            avg_availability = 0
            
        return {
            "total_pieces": total_pieces,
            "completed_pieces": completed_pieces,
            "available_pieces": available_pieces,
            "average_availability": avg_availability
        }

    def get_sorted_pieces(self, max_count=20):
        """Get pieces sorted by rarity (for debugging)"""
        available_pieces = []
        for piece_info in self.piece_info_map.values():
            if not piece_info.get("completed"):
                available_pieces.append({
                    "piece_index": piece_info["piece_index"],
                    "number_of_peers": piece_info["number_of_peers"],
                    "peers": list(piece_info["peers"])
                })
        
        sorted_pieces = sorted(available_pieces, key=lambda x: x['number_of_peers'])
        return sorted_pieces[:max_count]

    def log_availability_stats(self):
        """Log current availability statistics"""
        stats = self.get_availability_stats()
        logging.info(
            f"Piece availability: {stats['completed_pieces']}/{stats['total_pieces']} "
            f"completed, {stats['available_pieces']} available, "
            f"avg {stats['average_availability']:.1f} peers per piece"
        )