import hashlib


class SeedManager:
    """Manages deterministic seed generation hierarchy."""
    
    def __init__(self, master_seed: int):
        self.master_seed = master_seed
        
    def get_shard_seed(self, shard_index: int) -> int:
        """Get a deterministic seed for a specific shard index.
        
        Uses SHA256 hashing of (master_seed, shard_index) to produce
        a deterministic seed in O(1) time.
        """
        # Create a unique string from master seed and shard index
        seed_str = f"{self.master_seed}:{shard_index}"
        
        # Hash it
        hash_hex = hashlib.sha256(seed_str.encode()).hexdigest()
        
        # Take the first 8 characters (32 bits) and convert to int
        # This ensures we stay within standard 32-bit seed ranges
        return int(hash_hex[:8], 16)
