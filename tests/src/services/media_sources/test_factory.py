"""Tests for MediaSourceFactory."""

import pytest
from unittest.mock import Mock, patch

from src.services.media_sources.base_provider import MediaSourceProvider
from src.services.media_sources.factory import MediaSourceFactory
from src.services.media_sources.local_provider import LocalMediaProvider


@pytest.mark.unit
class TestMediaSourceFactory:
    """Test suite for MediaSourceFactory."""

    @patch("src.services.media_sources.factory.settings")
    def test_create_local_provider(self, mock_settings):
        """Test creating a local provider with explicit base_path."""
        mock_settings.MEDIA_DIR = "/default/media"

        provider = MediaSourceFactory.create("local", base_path="/custom/path")

        assert isinstance(provider, LocalMediaProvider)
        assert str(provider.base_path) == "/custom/path"

    @patch("src.services.media_sources.factory.settings")
    def test_create_local_provider_default_path(self, mock_settings):
        """Test creating a local provider uses settings.MEDIA_DIR as default."""
        mock_settings.MEDIA_DIR = "/default/media"

        provider = MediaSourceFactory.create("local")

        assert isinstance(provider, LocalMediaProvider)
        assert str(provider.base_path) == "/default/media"

    def test_create_unsupported_type(self):
        """Test creating provider with unsupported type raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported media source type"):
            MediaSourceFactory.create("google_drive")

    def test_create_unsupported_type_lists_supported(self):
        """Test error message lists supported types."""
        with pytest.raises(ValueError, match="local"):
            MediaSourceFactory.create("s3")

    @patch("src.services.media_sources.factory.settings")
    def test_get_provider_for_media_item_local(self, mock_settings):
        """Test getting provider for a local media item."""
        mock_settings.MEDIA_DIR = "/media"
        media_item = Mock(source_type="local")

        provider = MediaSourceFactory.get_provider_for_media_item(media_item)

        assert isinstance(provider, LocalMediaProvider)

    @patch("src.services.media_sources.factory.settings")
    def test_get_provider_for_media_item_none_source_type(self, mock_settings):
        """Test getting provider falls back to local when source_type is None."""
        mock_settings.MEDIA_DIR = "/media"
        media_item = Mock(source_type=None)

        provider = MediaSourceFactory.get_provider_for_media_item(media_item)

        assert isinstance(provider, LocalMediaProvider)

    def test_register_provider(self):
        """Test registering a custom provider type."""

        class FakeProvider(MediaSourceProvider):
            def __init__(self, **kwargs):
                pass

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

        # Register and verify
        MediaSourceFactory.register_provider("fake", FakeProvider)
        try:
            provider = MediaSourceFactory.create("fake")
            assert isinstance(provider, FakeProvider)
        finally:
            # Clean up to avoid affecting other tests
            del MediaSourceFactory._providers["fake"]

    @patch("src.services.media_sources.factory.settings")
    def test_get_provider_for_media_item_empty_string_source_type(self, mock_settings):
        """Test getting provider falls back to local when source_type is empty string."""
        mock_settings.MEDIA_DIR = "/media"
        media_item = Mock(source_type="")

        provider = MediaSourceFactory.get_provider_for_media_item(media_item)

        assert isinstance(provider, LocalMediaProvider)
