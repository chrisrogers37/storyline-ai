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
            MediaSourceFactory.create("dropbox")

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

    def test_get_provider_for_media_item_gdrive_resolves_root_folder(self):
        """For google_drive items, root_folder_id is resolved from chat_settings.

        Regression: previously omitted, which made get_provider_for_chat fail
        with "No root_folder_id configured", the factory's broad except caught
        it, fell back to the service-account path, and surfaced a misleading
        "No Google Drive credentials found" error.
        """
        media_item = Mock(source_type="google_drive")
        chat_settings = Mock(media_source_root="folder-id-abc")

        with (
            patch(
                "src.services.core.settings_service.SettingsService"
            ) as MockSettingsService,
            patch.object(MediaSourceFactory, "create") as mock_create,
        ):
            MockSettingsService.return_value.get_settings_if_exists.return_value = (
                chat_settings
            )

            MediaSourceFactory.get_provider_for_media_item(
                media_item, telegram_chat_id=-100123
            )

        mock_create.assert_called_once_with(
            "google_drive",
            telegram_chat_id=-100123,
            root_folder_id="folder-id-abc",
        )

    def test_get_provider_for_media_item_gdrive_no_chat_settings_omits_root(self):
        """If chat_settings is missing, no root_folder_id is added (fall through to current behavior)."""
        media_item = Mock(source_type="google_drive")

        with (
            patch(
                "src.services.core.settings_service.SettingsService"
            ) as MockSettingsService,
            patch.object(MediaSourceFactory, "create") as mock_create,
        ):
            MockSettingsService.return_value.get_settings_if_exists.return_value = None

            MediaSourceFactory.get_provider_for_media_item(
                media_item, telegram_chat_id=-100123
            )

        mock_create.assert_called_once_with("google_drive", telegram_chat_id=-100123)
