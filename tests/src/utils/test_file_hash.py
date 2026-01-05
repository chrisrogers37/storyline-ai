"""Tests for file_hash utility."""
import pytest
from pathlib import Path
import tempfile

from src.utils.file_hash import calculate_file_hash


@pytest.mark.unit
class TestFileHash:
    """Test file hash calculation."""

    def test_calculate_file_hash(self):
        """Test hash calculation for a file."""
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test content")
            temp_path = Path(f.name)

        try:
            # Calculate hash
            file_hash = calculate_file_hash(temp_path)

            # Verify it's a valid SHA256 hex string
            assert len(file_hash) == 64
            assert all(c in "0123456789abcdef" for c in file_hash)

        finally:
            temp_path.unlink()

    def test_same_content_same_hash(self):
        """Test that same content produces same hash."""
        content = "identical content"

        # Create two files with same content
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f1:
            f1.write(content)
            path1 = Path(f1.name)

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f2:
            f2.write(content)
            path2 = Path(f2.name)

        try:
            hash1 = calculate_file_hash(path1)
            hash2 = calculate_file_hash(path2)

            assert hash1 == hash2

        finally:
            path1.unlink()
            path2.unlink()

    def test_different_content_different_hash(self):
        """Test that different content produces different hash."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f1:
            f1.write("content 1")
            path1 = Path(f1.name)

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f2:
            f2.write("content 2")
            path2 = Path(f2.name)

        try:
            hash1 = calculate_file_hash(path1)
            hash2 = calculate_file_hash(path2)

            assert hash1 != hash2

        finally:
            path1.unlink()
            path2.unlink()
