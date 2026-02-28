"""Integration tests for Instagram posting workflow.

These tests verify:
1. PostingService routing decisions (all posts → Telegram)
2. HealthCheckService Instagram API status reporting
3. HistoryRepository rate limit queries
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta


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
        item.source_type = "local"
        item.source_identifier = "/path/to/story.jpg"
        item.mime_type = "image/jpeg"
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
    async def test_routing_instagram_disabled_goes_to_telegram(
        self, mock_queue_item, mock_media_item_auto
    ):
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

                # Import settings mock into the method
                with patch("src.services.core.posting.settings", mock_settings):
                    result = await service._route_post(
                        mock_queue_item, mock_media_item_auto
                    )

        assert result["method"] == "telegram_manual"
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_routing_requires_interaction_goes_to_telegram(
        self, mock_settings, mock_queue_item, mock_media_item_manual
    ):
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

            with patch("src.services.core.posting.settings", mock_settings):
                result = await service._route_post(
                    mock_queue_item, mock_media_item_manual
                )

        assert result["method"] == "telegram_manual"
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_routing_all_posts_go_to_telegram_first(
        self, mock_settings, mock_queue_item, mock_media_item_auto
    ):
        """Test all scheduled posts go to Telegram for review first.

        As of current architecture, _route_post ALWAYS sends to Telegram.
        Instagram API posting happens via 'Auto Post' button callback.
        """
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

            with patch("src.services.core.posting.settings", mock_settings):
                result = await service._route_post(
                    mock_queue_item, mock_media_item_auto
                )

        # All scheduled posts route to Telegram for human review
        assert result["method"] == "telegram_manual"
        assert result["success"] is True

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
            assert (
                "20/25" in result["message"] or "remaining" in result["message"].lower()
            )

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
            assert (
                "Token" in result["message"] or "invalid" in result["message"].lower()
            )


@pytest.mark.integration
class TestHistoryRepositoryIntegration:
    """Integration tests for history repository rate limit queries."""

    def test_count_by_method_instagram_api(self):
        """Test counting Instagram API posts in time window."""
        from src.repositories.history_repository import HistoryRepository

        with patch.object(HistoryRepository, "__init__", lambda x: None):
            repo = HistoryRepository()

            # Mock _db (not db which is a property)
            mock_session = Mock()
            mock_query = Mock()
            mock_query.filter.return_value = mock_query
            mock_query.with_entities.return_value = mock_query
            mock_query.scalar.return_value = 5
            mock_session.query.return_value = mock_query
            repo._db = mock_session

            since = datetime.utcnow() - timedelta(hours=1)
            result = repo.count_by_method("instagram_api", since)

            assert result == 5
            mock_session.query.assert_called()

    def test_count_by_method_returns_zero_for_none(self):
        """Test count returns 0 when scalar returns None."""
        from src.repositories.history_repository import HistoryRepository

        with patch.object(HistoryRepository, "__init__", lambda x: None):
            repo = HistoryRepository()

            # Mock _db (not db which is a property)
            mock_session = Mock()
            mock_query = Mock()
            mock_query.filter.return_value = mock_query
            mock_query.with_entities.return_value = mock_query
            mock_query.scalar.return_value = None
            mock_session.query.return_value = mock_query
            repo._db = mock_session

            since = datetime.utcnow() - timedelta(hours=1)
            result = repo.count_by_method("instagram_api", since)

            assert result == 0
