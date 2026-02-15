import hashlib
import struct


def derive_seed(master_seed: int, context_id: str, step_id: int) -> int:
    """
    Derives a deterministic 32-bit unsigned integer seed from a master seed, context, and step.

    This function ensures that the derived seed is mathematically determined by the inputs,
    independent of any global state. It uses SHA-256 hashing to mix the inputs and
    truncates the result to fit within standard random generator limits (0 to 2^32 - 1).

    Args:
        master_seed: The core seed (e.g., from CLI args).
        context_id: A string identifier for the domain (e.g., "scene", "layout", "lighting").
        step_id: A numerical identifier (e.g., scene index, frame number).

    Returns:
        A 32-bit unsigned integer suitable for setting random.seed() or numpy.random.seed().
    """
    # Combine inputs into a unique byte sequence
    # We use a separator to avoid potential collisions (e.g., "1" + "11" vs "11" + "1")
    input_str = f"{master_seed}:{context_id}:{step_id}"
    input_bytes = input_str.encode("utf-8")

    # Compute SHA-256 hash
    hash_bytes = hashlib.sha256(input_bytes).digest()

    # Take the first 4 bytes (32 bits)
    # unpack returns a tuple, so we take the first element
    seed_int = struct.unpack(">I", hash_bytes[:4])[0]

    # Ensure the seed fits within the signed 32-bit integer range (0 to 2^31 - 1)
    # This is required because Blender's cycles.seed expects a signed 32-bit int,
    # while numpy.random.seed expects a value < 2^32.
    # By masking with 0x7FFFFFFF, we get a positive integer that satisfies both.
    return seed_int & 0x7FFFFFFF
