"""File hashing utilities (MD5 of content).

Uses MD5 to match Google Drive's md5Checksum field, ensuring consistent
hash comparisons across local and cloud media sources.
"""

import hashlib
from pathlib import Path


def calculate_file_hash(file_path: Path) -> str:
    """
    Calculate MD5 hash of file content.

    Uses MD5 to match Google Drive's native md5Checksum, enabling
    cross-source deduplication and hash-aware selection.

    Note: Hash is based ONLY on file content, not filename.
    This means:
    - Same image with different names = same hash
    - Different images with same name = different hash

    Args:
        file_path: Path to file

    Returns:
        Hex string of MD5 hash (32 characters)

    Example:
        >>> calculate_file_hash(Path("/path/to/image.jpg"))
        'abc123def456...'
    """
    md5_hash = hashlib.md5()

    with open(file_path, "rb") as f:
        # Read in chunks for memory efficiency
        for byte_block in iter(lambda: f.read(4096), b""):
            md5_hash.update(byte_block)

    return md5_hash.hexdigest()
