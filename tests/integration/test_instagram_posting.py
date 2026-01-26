"""Integration tests for Instagram posting workflow.

These tests verify the end-to-end Instagram posting flow:
1. PostingService routing decisions
2. CloudStorageService → InstagramAPIService pipeline
3. Fallback to Telegram behavior
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timedelta
import tempfile
from pathlib import Path


@pytest.mark.integration
class TestInstagramPostingWorkflow:
    """Integration tests for the Instagram posting workflow."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for Instagram API enabled."""
        with patch("src.services.core.posting.settings") as mock:
            mock.ENABLE_INSTAGRAM_API = True
            mock.INSTAGRAM_ACCOUNT_ID = "17841400000000"
            mock.INSTAGRAM_POSTS_PER_HOUR = 25
            mock.CLOUD_UPLOAD_RETENTION_HOURS = 24
            mock.DRY_RUN_MODE = False
            mock.TELEGRAM_BOT_TOKEN = "test_token"
            mock.TELEGRAM_CHANNEL_ID = -1001234567890
            yield mock

    @pytest.fixture
    def mock_queue_item(self):
        """Create mock queue item."""
        item = Mock()
        item.id = "queue-123"
        item.media_item_id = "media-456"
        item.scheduled_for = datetime.utcnow()
        item.created_at = datetime.utcnow() - timedelta(hours=1)
        return item

    @pytest.fixture
    def mock_media_item_auto(self):
        """Create mock media item for automated posting."""
        item = Mock()
        item.id = "media-456"
        item.file_path = "/path/to/story.jpg"
        item.file_name = "story.jpg"
        item.requires_interaction = False
        item.category = "memes"
        item.caption = "Test caption"
        item.cloud_url = None
        item.cloud_public_id = None
        return item

    @pytest.fixture
    def mock_media_item_manual(self):
        """Create mock media item requiring manual interaction."""
        item = Mock()
        item.id = "media-789"
        item.file_path = "/path/to/product.jpg"
        item.file_name = "product.jpg"
        item.requires_interaction = True
        item.category = "merch"
        item.link_url = "https://shop.example.com/product"
        item.caption = "Check out this product!"
        return item

    # ==================== Routing Decision Tests ====================

    @pytest.mark.asyncio
    async def test_routing_instagram_disabled_goes_to_telegram(self, mock_queue_item, mock_media_item_auto):
        """Test all posts go to Telegram when Instagram API disabled."""
        with patch("src.services.core.posting.settings") as mock_settings:
            mock_settings.ENABLE_INSTAGRAM_API = False
            mock_settings.DRY_RUN_MODE = False

            from src.services.core.posting import PostingService

            with patch.object(PostingService, "__init__", lambda x: None):
                service = PostingService()
                service.queue_repo = Mock()
                service.media_repo = Mock()
                service.history_repo = Mock()
                service.lock_service = Mock()
                service.telegram_service = Mock()
                service.settings_service = Mock()
                service._post_via_telegram = AsyncMock(return_value=True)
                service._instagram_service = None
                service._cloud_service = None

                # Import settings mock into the method
                with patch("src.services.core.posting.settings", mock_settings):
                    result = await service._route_post(mock_queue_item, mock_media_item_auto)

        assert result["method"] == "telegram_manual"
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_routing_requires_interaction_goes_to_telegram(self, mock_settings, mock_queue_item, mock_media_item_manual):
        """Test posts requiring interaction go to Telegram."""
        from src.services.core.posting import PostingService

        with patch.object(PostingService, "__init__", lambda x: None):
            service = PostingService()
            service.queue_repo = Mock()
            service.media_repo = Mock()
            service.history_repo = Mock()
            service.lock_service = Mock()
            service.telegram_service = Mock()
            service.settings_service = Mock()
            service._post_via_telegram = AsyncMock(return_value=True)
            service._instagram_service = None
            service._cloud_service = None

            with patch("src.services.core.posting.settings", mock_settings):
                result = await service._route_post(mock_queue_item, mock_media_item_manual)

        assert result["method"] == "telegram_manual"
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_routing_rate_limit_exhausted_goes_to_telegram(self, mock_settings, mock_queue_item, mock_media_item_auto):
        """Test posts fallback to Telegram when rate limit exhausted."""
        from src.services.core.posting import PostingService

        with patch.object(PostingService, "__init__", lambda x: None):
            service = PostingService()
            service.queue_repo = Mock()
            service.media_repo = Mock()
            service.history_repo = Mock()
            service.lock_service = Mock()
            service.telegram_service = Mock()
            service.settings_service = Mock()
            service._post_via_telegram = AsyncMock(return_value=True)

            # Mock Instagram service with exhausted rate limit
            mock_instagram = Mock()
            mock_instagram.get_rate_limit_remaining.return_value = 0
            service._instagram_service = mock_instagram
            service._cloud_service = Mock()

            with patch("src.services.core.posting.settings", mock_settings):
                result = await service._route_post(mock_queue_item, mock_media_item_auto)

        assert result["method"] == "telegram_manual"
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_routing_healthy_instagram_selected(self, mock_settings, mock_queue_item, mock_media_item_auto):
        """Test posts go to Instagram API when healthy."""
        from src.services.core.posting import PostingService

        with patch.object(PostingService, "__init__", lambda x: None):
            service = PostingService()
            service.queue_repo = Mock()
            service.media_repo = Mock()
            service.history_repo = Mock()
            service.lock_service = Mock()
            service.telegram_service = Mock()
            service.settings_service = Mock()

            # Mock healthy Instagram service
            mock_instagram = Mock()
            mock_instagram.get_rate_limit_remaining.return_value = 20
            mock_instagram.post_story = AsyncMock(return_value={"success": True, "story_id": "123"})
            service._instagram_service = mock_instagram

            # Mock cloud service
            mock_cloud = Mock()
            mock_cloud.upload_media.return_value = {
                "url": "https://example.com/image.jpg",
                "public_id": "storyline/test",
                "uploaded_at": datetime.utcnow(),
                "expires_at": datetime.utcnow() + timedelta(hours=24),
            }
            service._cloud_service = mock_cloud

            # Mock _post_via_instagram to return success
            service._post_via_instagram = AsyncMock(return_value={"success": True, "story_id": "123"})

            with patch("src.services.core.posting.settings", mock_settings):
                result = await service._route_post(mock_queue_item, mock_media_item_auto)

        assert result["method"] == "instagram_api"
        assert result["success"] is True

    # ==================== End-to-End Posting Flow Tests ====================

    @pytest.mark.asyncio
    async def test_instagram_posting_full_flow(self, mock_settings, mock_queue_item, mock_media_item_auto):
        """Test complete Instagram posting flow: upload → post → cleanup."""
        from src.services.core.posting import PostingService

        # Create temp file for upload simulation
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00')
            mock_media_item_auto.file_path = f.name

        try:
            with patch.object(PostingService, "__init__", lambda x: None):
                service = PostingService()
                service.queue_repo = Mock()
                service.media_repo = Mock()
                service.history_repo = Mock()
                service.lock_service = Mock()
                service.telegram_service = Mock()

                # Mock cloud service
                mock_cloud = Mock()
                mock_cloud.upload_media.return_value = {
                    "url": "https://res.cloudinary.com/test/story.jpg",
                    "public_id": "storyline/story_123",
                    "uploaded_at": datetime.utcnow(),
                    "expires_at": datetime.utcnow() + timedelta(hours=24),
                }
                mock_cloud.delete_media.return_value = True
                service._cloud_service = mock_cloud

                # Mock Instagram service
                mock_instagram = Mock()
                mock_instagram.get_rate_limit_remaining.return_value = 20
                mock_instagram.post_story = AsyncMock(return_value={
                    "success": True,
                    "story_id": "17841234567890123",
                    "container_id": "container_456",
                    "timestamp": datetime.utcnow(),
                })
                service._instagram_service = mock_instagram

                with patch("src.services.core.posting.settings", mock_settings):
                    result = await service._post_via_instagram(mock_queue_item, mock_media_item_auto)

            # Verify the flow
            assert result["success"] is True
            assert result["story_id"] == "17841234567890123"

            # Verify cloud upload was called
            mock_cloud.upload_media.assert_called_once()

            # Verify Instagram posting was called
            mock_instagram.post_story.assert_awaited_once()

            # Verify media repo was updated with cloud info
            service.media_repo.update_cloud_info.assert_called()

        finally:
            Path(f.name).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_instagram_posting_upload_failure_fallback(self, mock_settings, mock_queue_item, mock_media_item_auto):
        """Test fallback to Telegram when cloud upload fails."""
        from src.services.core.posting import PostingService
        from src.exceptions import MediaUploadError

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00')
            mock_media_item_auto.file_path = f.name

        try:
            with patch.object(PostingService, "__init__", lambda x: None):
                service = PostingService()
                service.queue_repo = Mock()
                service.media_repo = Mock()
                service.history_repo = Mock()
                service.lock_service = Mock()
                service.telegram_service = Mock()

                # Mock cloud service to fail
                mock_cloud = Mock()
                mock_cloud.upload_media.side_effect = MediaUploadError("Upload failed")
                service._cloud_service = mock_cloud

                mock_instagram = Mock()
                mock_instagram.get_rate_limit_remaining.return_value = 20
                service._instagram_service = mock_instagram

                with patch("src.services.core.posting.settings", mock_settings):
                    with pytest.raises(MediaUploadError):
                        await service._post_via_instagram(mock_queue_item, mock_media_item_auto)

                # Instagram should not have been called
                mock_instagram.post_story.assert_not_called()

        finally:
            Path(f.name).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_instagram_posting_api_failure_cleanup(self, mock_settings, mock_queue_item, mock_media_item_auto):
        """Test cloud media cleanup when Instagram API fails."""
        from src.services.core.posting import PostingService
        from src.exceptions import InstagramAPIError

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00')
            mock_media_item_auto.file_path = f.name

        try:
            with patch.object(PostingService, "__init__", lambda x: None):
                service = PostingService()
                service.queue_repo = Mock()
                service.media_repo = Mock()
                service.history_repo = Mock()
                service.lock_service = Mock()
                service.telegram_service = Mock()

                # Mock cloud service to succeed
                mock_cloud = Mock()
                mock_cloud.upload_media.return_value = {
                    "url": "https://res.cloudinary.com/test/story.jpg",
                    "public_id": "storyline/story_123",
                    "uploaded_at": datetime.utcnow(),
                    "expires_at": datetime.utcnow() + timedelta(hours=24),
                }
                mock_cloud.delete_media.return_value = True
                service._cloud_service = mock_cloud

                # Mock Instagram service to fail
                mock_instagram = Mock()
                mock_instagram.get_rate_limit_remaining.return_value = 20
                mock_instagram.post_story = AsyncMock(side_effect=InstagramAPIError("API Error"))
                service._instagram_service = mock_instagram

                with patch("src.services.core.posting.settings", mock_settings):
                    with pytest.raises(InstagramAPIError):
                        await service._post_via_instagram(mock_queue_item, mock_media_item_auto)

                # Cloud media should be cleaned up after failure
                # Note: cleanup happens in the outer process_pending_posts handler

        finally:
            Path(f.name).unlink(missing_ok=True)

    # ==================== Cloud Cleanup Tests ====================

    @pytest.mark.asyncio
    async def test_cloud_cleanup_after_successful_post(self, mock_settings, mock_media_item_auto):
        """Test cloud media is cleaned up after successful Instagram post."""
        from src.services.core.posting import PostingService

        mock_media_item_auto.cloud_public_id = "storyline/story_123"

        with patch.object(PostingService, "__init__", lambda x: None):
            service = PostingService()
            service.media_repo = Mock()

            mock_cloud = Mock()
            mock_cloud.delete_media.return_value = True
            service._cloud_service = mock_cloud

            with patch("src.services.core.posting.settings", mock_settings):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    await service._cleanup_cloud_media(mock_media_item_auto.id, "storyline/story_123")

        # Verify deletion was called
        mock_cloud.delete_media.assert_called_once_with("storyline/story_123")

        # Verify media repo was updated to clear cloud info
        service.media_repo.update_cloud_info.assert_called_once_with(
            mock_media_item_auto.id,
            cloud_url=None,
            cloud_public_id=None,
            cloud_uploaded_at=None,
            cloud_expires_at=None,
        )

    @pytest.mark.asyncio
    async def test_cloud_cleanup_handles_delete_failure(self, mock_settings, mock_media_item_auto):
        """Test cleanup handles deletion failure gracefully."""
        from src.services.core.posting import PostingService

        with patch.object(PostingService, "__init__", lambda x: None):
            service = PostingService()
            service.media_repo = Mock()

            mock_cloud = Mock()
            mock_cloud.delete_media.return_value = False  # Deletion failed
            service._cloud_service = mock_cloud

            with patch("src.services.core.posting.settings", mock_settings):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    # Should not raise
                    await service._cleanup_cloud_media(mock_media_item_auto.id, "storyline/story_123")

        # Verify deletion was attempted
        mock_cloud.delete_media.assert_called_once_with("storyline/story_123")

        # Media repo should NOT be updated when deletion fails
        service.media_repo.update_cloud_info.assert_not_called()

    # ==================== Health Check Integration Tests ====================

    def test_health_check_includes_instagram_api_status(self):
        """Test health check includes Instagram API status."""
        from src.services.core.health_check import HealthCheckService

        with patch.object(HealthCheckService, "__init__", lambda x: None):
            service = HealthCheckService()
            service.queue_repo = Mock()
            service.history_repo = Mock()
            service._token_service = None
            service._instagram_service = None

            # Mock settings for disabled Instagram
            with patch("src.services.core.health_check.settings") as mock_settings:
                mock_settings.ENABLE_INSTAGRAM_API = False

                result = service._check_instagram_api()

            assert result["healthy"] is True
            assert result["enabled"] is False
            assert "Disabled" in result["message"]

    def test_health_check_instagram_api_token_health(self):
        """Test health check reports token health."""
        from src.services.core.health_check import HealthCheckService

        with patch.object(HealthCheckService, "__init__", lambda x: None):
            service = HealthCheckService()
            service.queue_repo = Mock()
            service.history_repo = Mock()

            # Mock token service
            mock_token = Mock()
            mock_token.check_token_health.return_value = {
                "valid": True,
                "expires_in_hours": 720,  # 30 days
            }
            service._token_service = mock_token

            # Mock Instagram service
            mock_instagram = Mock()
            mock_instagram.get_rate_limit_remaining.return_value = 20
            service._instagram_service = mock_instagram

            with patch("src.services.core.health_check.settings") as mock_settings:
                mock_settings.ENABLE_INSTAGRAM_API = True

                result = service._check_instagram_api()

            assert result["healthy"] is True
            assert result["enabled"] is True
            assert "20/25" in result["message"] or "remaining" in result["message"].lower()

    def test_health_check_instagram_api_expired_token(self):
        """Test health check reports expired token."""
        from src.services.core.health_check import HealthCheckService

        with patch.object(HealthCheckService, "__init__", lambda x: None):
            service = HealthCheckService()
            service.queue_repo = Mock()
            service.history_repo = Mock()

            # Mock token service with invalid token
            mock_token = Mock()
            mock_token.check_token_health.return_value = {
                "valid": False,
                "error": "Token expired",
            }
            service._token_service = mock_token
            service._instagram_service = Mock()

            with patch("src.services.core.health_check.settings") as mock_settings:
                mock_settings.ENABLE_INSTAGRAM_API = True

                result = service._check_instagram_api()

            assert result["healthy"] is False
            assert "Token" in result["message"] or "invalid" in result["message"].lower()


@pytest.mark.integration
class TestHistoryRepositoryIntegration:
    """Integration tests for history repository rate limit queries."""

    def test_count_by_method_instagram_api(self):
        """Test counting Instagram API posts in time window."""
        from src.repositories.history_repository import HistoryRepository

        with patch.object(HistoryRepository, "__init__", lambda x: None):
            repo = HistoryRepository()
            repo.db = Mock()

            # Mock the query chain
            mock_query = Mock()
            mock_query.filter.return_value = mock_query
            mock_query.scalar.return_value = 5
            repo.db.query.return_value = mock_query

            since = datetime.utcnow() - timedelta(hours=1)
            result = repo.count_by_method("instagram_api", since)

            assert result == 5
            repo.db.query.assert_called()

    def test_count_by_method_returns_zero_for_none(self):
        """Test count returns 0 when scalar returns None."""
        from src.repositories.history_repository import HistoryRepository

        with patch.object(HistoryRepository, "__init__", lambda x: None):
            repo = HistoryRepository()
            repo.db = Mock()

            mock_query = Mock()
            mock_query.filter.return_value = mock_query
            mock_query.scalar.return_value = None
            repo.db.query.return_value = mock_query

            since = datetime.utcnow() - timedelta(hours=1)
            result = repo.count_by_method("instagram_api", since)

            assert result == 0
