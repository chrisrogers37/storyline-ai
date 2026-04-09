"""Tests for MediaLifecycleService."""

import pytest
from unittest.mock import Mock, patch

from src.services.core.media_lifecycle import MediaLifecycleService


@pytest.fixture
def lifecycle_service():
    """Create MediaLifecycleService with mocked dependencies."""
    with patch.object(MediaLifecycleService, "__init__", lambda self: None):
        service = MediaLifecycleService()
        service.service_run_repo = Mock()
        service.service_name = "MediaLifecycleService"
        service.media_repo = Mock()
        service.cloud_service = Mock()
        return service


@pytest.mark.unit
class TestDeleteMediaItem:
    """Tests for delete_media_item method."""

    def test_deletes_with_cloud_resource(self, lifecycle_service):
        """Delete media item that has a Cloudinary resource attached."""
        media_item = Mock(cloud_public_id="instagram_stories/abc123")
        lifecycle_service.media_repo.get_by_id.return_value = media_item
        lifecycle_service.media_repo.delete.return_value = True
        lifecycle_service.cloud_service.is_configured.return_value = True
        lifecycle_service.cloud_service.delete_media.return_value = True

        result = lifecycle_service.delete_media_item("media-uuid")

        assert result is True
        lifecycle_service.cloud_service.delete_media.assert_called_once_with(
            "instagram_stories/abc123"
        )
        lifecycle_service.media_repo.delete.assert_called_once_with("media-uuid")

    def test_deletes_without_cloud_resource(self, lifecycle_service):
        """Delete media item that has no Cloudinary resource."""
        media_item = Mock(cloud_public_id=None)
        lifecycle_service.media_repo.get_by_id.return_value = media_item
        lifecycle_service.media_repo.delete.return_value = True
        lifecycle_service.cloud_service.is_configured.return_value = True

        result = lifecycle_service.delete_media_item("media-uuid")

        assert result is True
        lifecycle_service.cloud_service.delete_media.assert_not_called()
        lifecycle_service.media_repo.delete.assert_called_once_with("media-uuid")

    def test_cloud_failure_still_deletes_db(self, lifecycle_service):
        """Cloudinary failure should not prevent DB deletion."""
        media_item = Mock(cloud_public_id="instagram_stories/abc123")
        lifecycle_service.media_repo.get_by_id.return_value = media_item
        lifecycle_service.media_repo.delete.return_value = True
        lifecycle_service.cloud_service.is_configured.return_value = True
        lifecycle_service.cloud_service.delete_media.side_effect = Exception(
            "Cloudinary timeout"
        )

        result = lifecycle_service.delete_media_item("media-uuid")

        assert result is True
        lifecycle_service.media_repo.delete.assert_called_once_with("media-uuid")

    def test_not_found_returns_false(self, lifecycle_service):
        """Return False when media item does not exist."""
        lifecycle_service.media_repo.get_by_id.return_value = None

        result = lifecycle_service.delete_media_item("nonexistent")

        assert result is False
        lifecycle_service.cloud_service.delete_media.assert_not_called()
        lifecycle_service.media_repo.delete.assert_not_called()

    def test_skips_cloud_when_not_configured(self, lifecycle_service):
        """Skip Cloudinary delete when credentials are not configured."""
        media_item = Mock(cloud_public_id="instagram_stories/abc123")
        lifecycle_service.media_repo.get_by_id.return_value = media_item
        lifecycle_service.media_repo.delete.return_value = True
        lifecycle_service.cloud_service.is_configured.return_value = False

        result = lifecycle_service.delete_media_item("media-uuid")

        assert result is True
        lifecycle_service.cloud_service.delete_media.assert_not_called()
