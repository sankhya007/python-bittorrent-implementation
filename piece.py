import math
import hashlib
import time
import logging
from block import Block, BLOCK_SIZE, State


class Piece:
    def __init__(self, piece_index: int, piece_size: int, piece_hash: bytes):
        self.piece_index: int = piece_index
        self.piece_size: int = piece_size
        self.piece_hash: bytes = piece_hash
        self.is_full: bool = False
        self.files = []
        self.raw_data: bytes = b''
        self.number_of_blocks: int = int(math.ceil(float(piece_size) / BLOCK_SIZE))
        self.blocks: list[Block] = []
        self.creation_time = time.time()
        self.completion_time = None
        self.hash_verification_count = 0
        
        # Validate inputs
        if piece_size <= 0:
            raise ValueError(f"Invalid piece size: {piece_size}")
        if len(piece_hash) != 20:
            raise ValueError(f"Invalid piece hash length: {len(piece_hash)}")
            
        self._init_blocks()
        
        logging.debug(f"Created piece {piece_index} with {self.number_of_blocks} blocks, size: {piece_size}")

    def update_block_status(self):
        """If block is pending for too long, set it free"""
        current_time = time.time()
        reset_count = 0
        
        for i, block in enumerate(self.blocks):
            if (block.state == State.PENDING and 
                (current_time - block.last_seen) > 10):  # Increased timeout to 10 seconds
                
                # Only reset if we're not complete and block hasn't been updated
                if not self.is_full:
                    # Create new block but preserve any existing data
                    if block.data:
                        logging.debug(f"Resetting pending block {i} in piece {self.piece_index} with data")
                    self.blocks[i] = Block(block_size=block.block_size)
                    reset_count += 1
        
        if reset_count > 0:
            logging.debug(f"Reset {reset_count} pending blocks in piece {self.piece_index}")

    def set_block(self, offset: int, data: bytes):
        """Set block data at given offset with validation"""
        if not data:
            logging.warning(f"Attempted to set empty block data in piece {self.piece_index}")
            return
            
        if self.is_full:
            logging.debug(f"Ignoring block data for completed piece {self.piece_index}")
            return

        block_index = int(offset / BLOCK_SIZE)
        
        # Validate block index
        if block_index < 0 or block_index >= len(self.blocks):
            logging.error(f"Invalid block index {block_index} for piece {self.piece_index} with {len(self.blocks)} blocks")
            return
            
        block = self.blocks[block_index]
        
        # Validate offset matches block boundary
        expected_offset = block_index * BLOCK_SIZE
        if offset != expected_offset:
            logging.warning(f"Block offset mismatch: expected {expected_offset}, got {offset}")

        # Only set if block is not already full
        if block.state != State.FULL:
            # Validate data size matches block size (allow for last block being smaller)
            expected_size = block.block_size
            if len(data) != expected_size:
                logging.warning(f"Block size mismatch in piece {self.piece_index}: expected {expected_size}, got {len(data)}")
                # Truncate or pad data to expected size
                if len(data) > expected_size:
                    data = data[:expected_size]
                else:
                    data = data.ljust(expected_size, b'\x00')
            
            block.data = data
            block.state = State.FULL
            block.last_seen = time.time()
            
            logging.debug(f"Set block {block_index} in piece {self.piece_index}, size: {len(data)}")
        else:
            logging.debug(f"Block {block_index} in piece {self.piece_index} already full")

    def get_block(self, block_offset: int, block_length: int) -> bytes:
        """Get block data from piece with bounds checking"""
        if not self.is_full:
            return b''
            
        if block_offset < 0 or block_length <= 0:
            return b''
            
        # Ensure we don't read beyond piece boundaries
        end_offset = block_offset + block_length
        if end_offset > len(self.raw_data):
            block_length = len(self.raw_data) - block_offset
            if block_length <= 0:
                return b''
                
        return self.raw_data[block_offset:block_offset + block_length]

    def get_empty_block(self):
        """Get next empty block to download with prioritization"""
        if self.is_full:
            return None

        # First, try to find any free block
        for block_index, block in enumerate(self.blocks):
            if block.state == State.FREE:
                return self._prepare_block_request(block_index, block)

        # If no free blocks, check for stale pending blocks
        current_time = time.time()
        for block_index, block in enumerate(self.blocks):
            if (block.state == State.PENDING and 
                (current_time - block.last_seen) > 15):  # Longer timeout for re-request
                logging.debug(f"Re-requesting stale block {block_index} in piece {self.piece_index}")
                return self._prepare_block_request(block_index, block)

        return None

    def _prepare_block_request(self, block_index: int, block: Block):
        """Prepare a block request and mark it as pending"""
        block_offset = block_index * BLOCK_SIZE
        block.state = State.PENDING
        block.last_seen = time.time()
        
        logging.debug(f"Requesting block {block_index} in piece {self.piece_index}, size: {block.block_size}")
        return self.piece_index, block_offset, block.block_size

    def are_all_blocks_full(self) -> bool:
        """Check if all blocks in this piece are full"""
        # Quick check - if we're already marked full, return True
        if self.is_full:
            return True
            
        # Detailed check of all blocks
        for block in self.blocks:
            if block.state != State.FULL:
                return False
        return True

    def get_completion_percentage(self) -> float:
        """Get completion percentage of this piece"""
        if self.is_full:
            return 100.0
            
        full_blocks = sum(1 for block in self.blocks if block.state == State.FULL)
        return (full_blocks / len(self.blocks)) * 100.0

    def set_to_full(self) -> bool:
        """Merge blocks and verify piece hash with comprehensive validation"""
        if not self.are_all_blocks_full():
            logging.debug(f"Piece {self.piece_index} not ready for completion: blocks not all full")
            return False

        # Merge all blocks into single piece data
        data = self._merge_blocks()
        
        # Validate piece size
        if len(data) != self.piece_size:
            logging.error(f"Piece {self.piece_index} size mismatch: expected {self.piece_size}, got {len(data)}")
            self._handle_corruption()
            return False
        
        # Verify piece hash
        if not self._valid_blocks(data):
            self.hash_verification_count += 1
            
            # Allow one retry in case of temporary corruption
            if self.hash_verification_count <= 1:
                logging.warning(f"Piece {self.piece_index} hash mismatch, attempt {self.hash_verification_count}")
                self._init_blocks()  # Reset blocks for re-download
                return False
            else:
                logging.error(f"Piece {self.piece_index} failed hash verification {self.hash_verification_count} times")
                self._handle_corruption()
                return False

        # Mark as complete
        self.is_full = True
        self.raw_data = data
        self.completion_time = time.time()
        download_time = self.completion_time - self.creation_time
        
        logging.info(f"✅ Piece {self.piece_index} verified and completed in {download_time:.2f}s "
                   f"({self.piece_size} bytes, {len(self.blocks)} blocks)")
        return True

    def _handle_corruption(self):
        """Handle corrupted piece data"""
        logging.error(f"Piece {self.piece_index} is corrupted, resetting all blocks")
        self._init_blocks()
        self.raw_data = b''
        self.is_full = False

    def _init_blocks(self):
        """Initialize blocks for this piece with proper sizing"""
        self.blocks = []
        
        if self.number_of_blocks > 1:
            for i in range(self.number_of_blocks):
                block_size = BLOCK_SIZE
                # Last block might be smaller
                if i == self.number_of_blocks - 1:
                    remaining_size = self.piece_size - (i * BLOCK_SIZE)
                    block_size = remaining_size if remaining_size > 0 else BLOCK_SIZE
                
                self.blocks.append(Block(block_size=block_size))
        else:
            # Single block piece
            self.blocks.append(Block(block_size=self.piece_size))

    def _merge_blocks(self) -> bytes:
        """Merge all blocks into piece data efficiently"""
        if not self.blocks:
            return b''
            
        # Pre-allocate buffer for efficiency with large pieces
        total_size = sum(len(block.data) for block in self.blocks)
        buffer = bytearray(total_size)
        offset = 0
        
        for block in self.blocks:
            block_data = block.data
            buffer[offset:offset + len(block_data)] = block_data
            offset += len(block_data)
            
        return bytes(buffer)

    def _valid_blocks(self, piece_raw_data: bytes) -> bool:
        """Verify piece hash matches expected hash with detailed logging"""
        if not piece_raw_data:
            logging.error(f"Piece {self.piece_index} has no data for hash verification")
            return False
            
        if len(piece_raw_data) != self.piece_size:
            logging.error(f"Piece {self.piece_index} data size mismatch for hash verification")
            return False
            
        hashed_piece_raw_data = hashlib.sha1(piece_raw_data).digest()
        
        if hashed_piece_raw_data == self.piece_hash:
            return True
            
        # Log hash mismatch details for debugging
        expected_hash = self.piece_hash.hex()
        actual_hash = hashed_piece_raw_data.hex()
        logging.warning(f"Piece {self.piece_index} hash mismatch")
        logging.warning(f"  Expected: {expected_hash}")
        logging.warning(f"  Actual:   {actual_hash}")
        logging.warning(f"  Data size: {len(piece_raw_data)} bytes")
        
        return False

    def get_stats(self):
        """Get statistics about this piece's download progress"""
        full_blocks = sum(1 for block in self.blocks if block.state == State.FULL)
        pending_blocks = sum(1 for block in self.blocks if block.state == State.PENDING)
        free_blocks = sum(1 for block in self.blocks if block.state == State.FREE)
        
        return {
            'piece_index': self.piece_index,
            'is_full': self.is_full,
            'completion_percentage': self.get_completion_percentage(),
            'blocks_total': len(self.blocks),
            'blocks_full': full_blocks,
            'blocks_pending': pending_blocks,
            'blocks_free': free_blocks,
            'piece_size': self.piece_size,
            'hash_verification_count': self.hash_verification_count
        }