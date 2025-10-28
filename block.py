from enum import Enum
import time

BLOCK_SIZE = 2 ** 14  # 16KB - Standard BitTorrent block size


class State(Enum):
    FREE = 0
    PENDING = 1
    FULL = 2
    
    def __str__(self):
        return self.name


class Block:
    def __init__(self, state: State = State.FREE, block_size: int = BLOCK_SIZE, 
                 data: bytes = b'', last_seen: float = None):
        """
        Represents a block of data in a torrent piece.
        
        Args:
            state: Current state of the block
            block_size: Size of the block in bytes
            data: The actual block data
            last_seen: Timestamp when block was last accessed
        """
        self.state: State = state
        self.block_size: int = block_size
        self.data: bytes = data
        self.last_seen: float = last_seen if last_seen is not None else time.time()
        
        # Validate inputs
        if block_size <= 0:
            raise ValueError(f"Block size must be positive, got {block_size}")
        if block_size > 2 * BLOCK_SIZE:  # Allow some flexibility but not too much
            raise ValueError(f"Block size too large: {block_size}")
        if data and len(data) > block_size:
            raise ValueError(f"Data size {len(data)} exceeds block size {block_size}")

    def __str__(self):
        """Human-readable string representation"""
        state_emoji = {
            State.FREE: "🟢",
            State.PENDING: "🟡", 
            State.FULL: "🔵"
        }
        data_info = f"{len(self.data)}/{self.block_size} bytes" if self.data else "empty"
        return f"{state_emoji.get(self.state, '⚫')} {self.state.name} - {data_info} - seen {time.time() - self.last_seen:.1f}s ago"

    def __repr__(self):
        """Detailed representation for debugging"""
        return (f"Block(state={self.state}, size={self.block_size}, "
                f"data_length={len(self.data)}, last_seen={self.last_seen})")

    def set_data(self, data: bytes) -> bool:
        """
        Set block data and mark as FULL if data matches block size.
        
        Args:
            data: The data to set for this block
            
        Returns:
            bool: True if data was set successfully, False otherwise
        """
        if not data:
            return False
            
        if len(data) > self.block_size:
            # Truncate data that's too large (shouldn't happen in normal operation)
            self.data = data[:self.block_size]
        else:
            self.data = data
            
        # Only mark as FULL if we have complete data
        if len(self.data) == self.block_size:
            self.state = State.FULL
        else:
            # For partial data (like last block in piece), still mark as FULL
            # since we won't get more data for this block
            self.state = State.FULL
            
        self.last_seen = time.time()
        return True

    def mark_pending(self):
        """Mark this block as pending download"""
        self.state = State.PENDING
        self.last_seen = time.time()

    def mark_free(self):
        """Reset block to free state (for retries)"""
        self.state = State.FREE
        self.data = b''
        self.last_seen = time.time()

    def is_stale(self, timeout_seconds: float = 30.0) -> bool:
        """
        Check if this block has been pending for too long.
        
        Args:
            timeout_seconds: How long to wait before considering stale
            
        Returns:
            bool: True if block is stale and should be reset
        """
        if self.state != State.PENDING:
            return False
            
        return (time.time() - self.last_seen) > timeout_seconds

    def is_complete(self) -> bool:
        """Check if block has complete data"""
        return self.state == State.FULL and len(self.data) == self.block_size

    def get_remaining_size(self) -> int:
        """Get remaining bytes needed to complete this block"""
        if self.state == State.FULL:
            return 0
        return self.block_size - len(self.data)

    def validate(self) -> bool:
        """Validate block state and data consistency"""
        if self.state == State.FREE:
            return len(self.data) == 0
        elif self.state == State.PENDING:
            return len(self.data) <= self.block_size
        elif self.state == State.FULL:
            return 0 < len(self.data) <= self.block_size
        return False

    def to_dict(self) -> dict:
        """Convert block to dictionary for serialization/debugging"""
        return {
            'state': self.state.name,
            'block_size': self.block_size,
            'data_length': len(self.data),
            'last_seen': self.last_seen,
            'is_stale': self.is_stale(),
            'is_complete': self.is_complete(),
            'remaining_size': self.get_remaining_size()
        }


# Utility functions for block management
def create_blocks_for_piece(piece_size: int, piece_index: int) -> list['Block']:
    """
    Create all blocks needed for a piece.
    
    Args:
        piece_size: Total size of the piece in bytes
        piece_index: Index of the piece (for debugging)
        
    Returns:
        list[Block]: List of blocks for the piece
    """
    if piece_size <= 0:
        raise ValueError(f"Invalid piece size: {piece_size}")
    
    num_full_blocks = piece_size // BLOCK_SIZE
    last_block_size = piece_size % BLOCK_SIZE
    
    blocks = []
    
    # Create full-sized blocks
    for _ in range(num_full_blocks):
        blocks.append(Block(block_size=BLOCK_SIZE))
    
    # Create last block if needed
    if last_block_size > 0:
        blocks.append(Block(block_size=last_block_size))
    
    return blocks


def calculate_block_range(piece_size: int) -> tuple[int, int]:
    """
    Calculate the range of blocks needed for a piece.
    
    Args:
        piece_size: Size of the piece in bytes
        
    Returns:
        tuple: (number_of_full_blocks, last_block_size)
    """
    num_full_blocks = piece_size // BLOCK_SIZE
    last_block_size = piece_size % BLOCK_SIZE
    
    return num_full_blocks, last_block_size


# Test function for debugging
def test_block_functionality():
    """Test basic block functionality"""
    print("🧪 Testing Block functionality...")
    
    # Test basic block
    block = Block()
    assert block.state == State.FREE
    assert block.block_size == BLOCK_SIZE
    assert len(block.data) == 0
    print("✅ Basic block creation works")
    
    # Test data setting
    test_data = b"x" * BLOCK_SIZE
    block.set_data(test_data)
    assert block.state == State.FULL
    assert block.data == test_data
    print("✅ Data setting works")
    
    # Test partial data (last block scenario)
    small_block = Block(block_size=100)
    small_data = b"x" * 50
    small_block.set_data(small_data)
    assert block.state == State.FULL  # Should still be marked FULL
    print("✅ Partial data handling works")
    
    # Test stale detection
    stale_block = Block(state=State.PENDING)
    assert not stale_block.is_stale(timeout_seconds=1.0)
    import time
    time.sleep(1.1)
    assert stale_block.is_stale(timeout_seconds=1.0)
    print("✅ Stale detection works")
    
    print("🎉 All block tests passed!")


if __name__ == "__main__":
    test_block_functionality()