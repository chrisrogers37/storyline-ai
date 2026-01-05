"""File hashing utilities (SHA256 of content)."""
import hashlib
from pathlib import Path


def calculate_file_hash(file_path: Path) -> str:
    """
    Calculate SHA256 hash of file content.

    Note: Hash is based ONLY on file content, not filename.
    This means:
    - Same image with different names = same hash
    - Different images with same name = different hash

    Args:
        file_path: Path to file

    Returns:
        Hex string of SHA256 hash

    Example:
        >>> calculate_file_hash(Path("/path/to/image.jpg"))
        'abc123def456...'
    """
    sha256_hash = hashlib.sha256()

    with open(file_path, "rb") as f:
        # Read in chunks for memory efficiency
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    return sha256_hash.hexdigest()
