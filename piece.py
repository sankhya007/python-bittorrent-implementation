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
        
        self._init_blocks()

    def update_block_status(self):
        """If block is pending for too long, set it free"""
        for i, block in enumerate(self.blocks):
            if block.state == State.PENDING and (time.time() - block.last_seen) > 5:
                self.blocks[i] = Block()

    def set_block(self, offset: int, data: bytes):
        """Set block data at given offset"""
        index = int(offset / BLOCK_SIZE)
        
        if not self.is_full and not self.blocks[index].state == State.FULL:
            self.blocks[index].data = data
            self.blocks[index].state = State.FULL

    def get_block(self, block_offset: int, block_length: int) -> bytes:
        """Get block data from piece"""
        if self.is_full:
            return self.raw_data[block_offset:block_offset + block_length]
        return b''

    def get_empty_block(self):
        """Get next empty block to download"""
        if self.is_full:
            return None

        for block_index, block in enumerate(self.blocks):
            if block.state == State.FREE:
                self.blocks[block_index].state = State.PENDING
                self.blocks[block_index].last_seen = time.time()
                return self.piece_index, block_index * BLOCK_SIZE, block.block_size

        return None

    def are_all_blocks_full(self) -> bool:
        """Check if all blocks in this piece are full"""
        for block in self.blocks:
            if block.state == State.FREE or block.state == State.PENDING:
                return False
        return True

    def set_to_full(self) -> bool:
        """Merge blocks and verify piece hash"""
        if not self.are_all_blocks_full():
            return False

        data = self._merge_blocks()
        
        if not self._valid_blocks(data):
            self._init_blocks()
            return False

        self.is_full = True
        self.raw_data = data
        return True

    def _init_blocks(self):
        """Initialize blocks for this piece"""
        self.blocks = []
        
        if self.number_of_blocks > 1:
            for i in range(self.number_of_blocks):
                self.blocks.append(Block())
            
            # Last block might be smaller
            if (self.piece_size % BLOCK_SIZE) > 0:
                self.blocks[self.number_of_blocks - 1].block_size = self.piece_size % BLOCK_SIZE
        else:
            self.blocks.append(Block(block_size=self.piece_size))

    def _merge_blocks(self) -> bytes:
        """Merge all blocks into piece data"""
        buf = b''
        for block in self.blocks:
            buf += block.data
        return buf

    def _valid_blocks(self, piece_raw_data: bytes) -> bool:
        """Verify piece hash matches expected hash"""
        hashed_piece_raw_data = hashlib.sha1(piece_raw_data).digest()
        
        if hashed_piece_raw_data == self.piece_hash:
            return True
            
        logging.warning(f"Piece {self.piece_index} hash mismatch")
        return False