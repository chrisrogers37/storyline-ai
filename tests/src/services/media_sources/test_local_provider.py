"""Tests for LocalMediaProvider."""

import pytest
import tempfile
from pathlib import Path

from src.services.media_sources.local_provider import LocalMediaProvider


@pytest.fixture
def media_dir():
    """Create a temporary directory with realistic media structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)

        # Create folder structure
        memes = base / "memes"
        merch = base / "merch"
        memes.mkdir()
        merch.mkdir()

        # Create media files
        (memes / "funny.jpg").write_bytes(b"jpeg content here")
        (memes / "cat.png").write_bytes(b"png content here")
        (merch / "shirt.jpg").write_bytes(b"shirt image content")
        (base / "root_image.jpg").write_bytes(b"root level image")

        # Create an unsupported file
        (memes / "readme.txt").write_text("not a media file")

        # Create a hidden directory (should be excluded from folders)
        (base / ".hidden").mkdir()
        (base / ".hidden" / "secret.jpg").write_bytes(b"hidden")

        yield base


@pytest.mark.unit
class TestLocalMediaProvider:
    """Test suite for LocalMediaProvider."""

    # ==================== is_configured Tests ====================

    def test_is_configured_valid_directory(self, media_dir):
        """Test is_configured returns True for existing directory."""
        provider = LocalMediaProvider(str(media_dir))
        assert provider.is_configured() is True

    def test_is_configured_nonexistent_path(self):
        """Test is_configured returns False for non-existent path."""
        provider = LocalMediaProvider("/nonexistent/path/12345")
        assert provider.is_configured() is False

    def test_is_configured_file_not_dir(self):
        """Test is_configured returns False when path is a file."""
        with tempfile.NamedTemporaryFile() as f:
            provider = LocalMediaProvider(f.name)
            assert provider.is_configured() is False

    # ==================== list_files Tests ====================

    def test_list_files_all(self, media_dir):
        """Test listing all media files across all folders."""
        provider = LocalMediaProvider(str(media_dir))
        files = provider.list_files()

        names = {f.name for f in files}
        assert "funny.jpg" in names
        assert "cat.png" in names
        assert "shirt.jpg" in names
        assert "root_image.jpg" in names
        # Unsupported files excluded
        assert "readme.txt" not in names

    def test_list_files_by_folder(self, media_dir):
        """Test listing files filtered by folder."""
        provider = LocalMediaProvider(str(media_dir))
        files = provider.list_files(folder="memes")

        names = {f.name for f in files}
        assert "funny.jpg" in names
        assert "cat.png" in names
        assert "shirt.jpg" not in names

    def test_list_files_nonexistent_folder(self, media_dir):
        """Test listing files from non-existent folder returns empty."""
        provider = LocalMediaProvider(str(media_dir))
        files = provider.list_files(folder="nonexistent")
        assert files == []

    def test_list_files_returns_media_file_info(self, media_dir):
        """Test that list_files returns proper MediaFileInfo objects."""
        provider = LocalMediaProvider(str(media_dir))
        files = provider.list_files(folder="memes")

        assert len(files) >= 2
        for f in files:
            assert f.identifier  # non-empty
            assert f.name  # non-empty
            assert f.size_bytes > 0
            assert f.mime_type  # non-empty
            assert f.modified_at is not None

    def test_list_files_excludes_unsupported(self, media_dir):
        """Test that unsupported extensions are excluded."""
        provider = LocalMediaProvider(str(media_dir))
        files = provider.list_files()

        extensions = {Path(f.name).suffix.lower() for f in files}
        assert ".txt" not in extensions

    def test_list_files_nonexistent_base(self):
        """Test list_files returns empty for non-existent base path."""
        provider = LocalMediaProvider("/nonexistent/path")
        assert provider.list_files() == []

    def test_list_files_folder_extraction(self, media_dir):
        """Test that folder/category is correctly extracted."""
        provider = LocalMediaProvider(str(media_dir))
        files = provider.list_files()

        folder_map = {f.name: f.folder for f in files}
        assert folder_map["funny.jpg"] == "memes"
        assert folder_map["shirt.jpg"] == "merch"
        assert folder_map["root_image.jpg"] is None

    # ==================== download_file Tests ====================

    def test_download_file_success(self, media_dir):
        """Test downloading file returns correct bytes."""
        provider = LocalMediaProvider(str(media_dir))
        file_path = str(media_dir / "memes" / "funny.jpg")

        content = provider.download_file(file_path)
        assert content == b"jpeg content here"

    def test_download_file_not_found(self, media_dir):
        """Test downloading non-existent file raises FileNotFoundError."""
        provider = LocalMediaProvider(str(media_dir))
        with pytest.raises(FileNotFoundError, match="File not found"):
            provider.download_file("/nonexistent/file.jpg")

    # ==================== get_file_info Tests ====================

    def test_get_file_info_success(self, media_dir):
        """Test getting file info for existing file."""
        provider = LocalMediaProvider(str(media_dir))
        file_path = str(media_dir / "memes" / "funny.jpg")

        info = provider.get_file_info(file_path)
        assert info is not None
        assert info.name == "funny.jpg"
        assert info.size_bytes == len(b"jpeg content here")
        assert info.mime_type == "image/jpeg"

    def test_get_file_info_not_found(self, media_dir):
        """Test getting file info for non-existent file returns None."""
        provider = LocalMediaProvider(str(media_dir))
        info = provider.get_file_info("/nonexistent/file.jpg")
        assert info is None

    # ==================== file_exists Tests ====================

    def test_file_exists_true(self, media_dir):
        """Test file_exists returns True for existing file."""
        provider = LocalMediaProvider(str(media_dir))
        assert provider.file_exists(str(media_dir / "memes" / "funny.jpg")) is True

    def test_file_exists_false(self, media_dir):
        """Test file_exists returns False for non-existent file."""
        provider = LocalMediaProvider(str(media_dir))
        assert provider.file_exists("/nonexistent/file.jpg") is False

    def test_file_exists_directory(self, media_dir):
        """Test file_exists returns False for directory path."""
        provider = LocalMediaProvider(str(media_dir))
        assert provider.file_exists(str(media_dir / "memes")) is False

    # ==================== get_folders Tests ====================

    def test_get_folders_returns_sorted(self, media_dir):
        """Test get_folders returns sorted list of subdirectories."""
        provider = LocalMediaProvider(str(media_dir))
        folders = provider.get_folders()

        # Should include memes and merch, exclude .hidden
        assert "memes" in folders
        assert "merch" in folders
        assert ".hidden" not in folders
        assert folders == sorted(folders)

    def test_get_folders_nonexistent_base(self):
        """Test get_folders returns empty for non-existent base."""
        provider = LocalMediaProvider("/nonexistent/path")
        assert provider.get_folders() == []

    # ==================== calculate_file_hash Tests ====================

    def test_calculate_file_hash_consistent(self, media_dir):
        """Test that hash is consistent for same content."""
        provider = LocalMediaProvider(str(media_dir))
        file_path = str(media_dir / "memes" / "funny.jpg")

        hash1 = provider.calculate_file_hash(file_path)
        hash2 = provider.calculate_file_hash(file_path)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex length

    def test_calculate_file_hash_different_content(self, media_dir):
        """Test that different content produces different hashes."""
        provider = LocalMediaProvider(str(media_dir))

        hash1 = provider.calculate_file_hash(str(media_dir / "memes" / "funny.jpg"))
        hash2 = provider.calculate_file_hash(str(media_dir / "memes" / "cat.png"))
        assert hash1 != hash2

    def test_calculate_file_hash_not_found(self, media_dir):
        """Test hash calculation raises for non-existent file."""
        provider = LocalMediaProvider(str(media_dir))
        with pytest.raises(FileNotFoundError, match="File not found"):
            provider.calculate_file_hash("/nonexistent/file.jpg")

    # ==================== Custom Extensions Tests ====================

    def test_custom_supported_extensions(self, media_dir):
        """Test provider with custom extension filter."""
        # Only allow .png files
        provider = LocalMediaProvider(str(media_dir), supported_extensions={".png"})
        files = provider.list_files()

        names = {f.name for f in files}
        assert "cat.png" in names
        assert "funny.jpg" not in names
        assert "shirt.jpg" not in names

    # ==================== Identifier Tests ====================

    def test_identifier_is_absolute_path(self, media_dir):
        """Test that file identifiers are absolute paths."""
        provider = LocalMediaProvider(str(media_dir))
        files = provider.list_files()

        for f in files:
            assert Path(f.identifier).is_absolute()
