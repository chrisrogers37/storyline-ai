"""Tests for MediaSourceProvider ABC and MediaFileInfo dataclass."""

import pytest
from datetime import datetime

from src.services.media_sources.base_provider import MediaFileInfo, MediaSourceProvider


@pytest.mark.unit
class TestMediaFileInfo:
    """Test suite for MediaFileInfo dataclass."""

    def test_create_with_required_fields(self):
        """Test creating MediaFileInfo with only required fields."""
        info = MediaFileInfo(
            identifier="/path/to/file.jpg",
            name="file.jpg",
            size_bytes=1024,
            mime_type="image/jpeg",
        )
        assert info.identifier == "/path/to/file.jpg"
        assert info.name == "file.jpg"
        assert info.size_bytes == 1024
        assert info.mime_type == "image/jpeg"
        assert info.folder is None
        assert info.modified_at is None
        assert info.hash is None

    def test_create_with_all_fields(self):
        """Test creating MediaFileInfo with all fields populated."""
        now = datetime.utcnow()
        info = MediaFileInfo(
            identifier="drive_file_id_123",
            name="photo.png",
            size_bytes=2048,
            mime_type="image/png",
            folder="memes",
            modified_at=now,
            hash="abc123def456",
        )
        assert info.folder == "memes"
        assert info.modified_at == now
        assert info.hash == "abc123def456"

    def test_equality(self):
        """Test that two MediaFileInfo with same values are equal."""
        info1 = MediaFileInfo(
            identifier="id1", name="f.jpg", size_bytes=100, mime_type="image/jpeg"
        )
        info2 = MediaFileInfo(
            identifier="id1", name="f.jpg", size_bytes=100, mime_type="image/jpeg"
        )
        assert info1 == info2

    def test_inequality(self):
        """Test that two MediaFileInfo with different values are not equal."""
        info1 = MediaFileInfo(
            identifier="id1", name="f.jpg", size_bytes=100, mime_type="image/jpeg"
        )
        info2 = MediaFileInfo(
            identifier="id2", name="f.jpg", size_bytes=100, mime_type="image/jpeg"
        )
        assert info1 != info2


@pytest.mark.unit
class TestMediaSourceProviderInterface:
    """Test suite for the abstract interface."""

    def test_cannot_instantiate_abc(self):
        """Test that MediaSourceProvider cannot be instantiated directly."""
        with pytest.raises(TypeError, match="abstract method"):
            MediaSourceProvider()

    def test_incomplete_subclass_fails(self):
        """Test that a subclass missing methods cannot be instantiated."""

        class IncompleteProvider(MediaSourceProvider):
            def list_files(self, folder=None):
                return []

        with pytest.raises(TypeError, match="abstract method"):
            IncompleteProvider()

    def test_complete_subclass_succeeds(self):
        """Test that a complete subclass can be instantiated."""

        class CompleteProvider(MediaSourceProvider):
            def list_files(self, folder=None):
                return []

            def download_file(self, file_identifier):
                return b""

            def get_file_info(self, file_identifier):
                return None

            def file_exists(self, file_identifier):
                return False

            def get_folders(self):
                return []

            def is_configured(self):
                return True

            def calculate_file_hash(self, file_identifier):
                return "hash"

        provider = CompleteProvider()
        assert provider.is_configured() is True
