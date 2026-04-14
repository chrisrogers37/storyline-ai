"""Tests for HealthCheckService."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from src.services.core.health_check import HealthCheckService


@pytest.mark.unit
class TestHealthCheckService:
    """Test suite for HealthCheckService."""

    @pytest.fixture
    def health_service(self):
        """Create HealthCheckService with mocked dependencies."""
        service = HealthCheckService()
        service.queue_repo = Mock()
        service.history_repo = Mock()
        return service

    @patch("src.services.core.health_check.BaseRepository")
    def test_check_database_healthy(self, mock_base_repo, health_service):
        """Test database check returns healthy when DB is accessible."""
        result = health_service._check_database()

        mock_base_repo.check_connection.assert_called_once()
        assert result["healthy"] is True
        assert "Database connection OK" in result["message"]

    @patch("src.services.core.health_check.BaseRepository")
    def test_check_database_unhealthy(self, mock_base_repo, health_service):
        """Test database check returns unhealthy when DB fails."""
        mock_base_repo.check_connection.side_effect = Exception("Connection refused")

        result = health_service._check_database()

        assert result["healthy"] is False
        assert "Database error" in result["message"]

    @patch("src.services.core.health_check.settings")
    def test_check_telegram_config_valid(self, mock_settings, health_service):
        """Test Telegram config check with valid configuration."""
        mock_settings.TELEGRAM_BOT_TOKEN = "123456:ABC-DEF1234ghIkl"
        mock_settings.TELEGRAM_CHANNEL_ID = -1001234567890

        result = health_service._check_telegram_config()

        assert result["healthy"] is True
        assert "Telegram configuration OK" in result["message"]

    @patch("src.services.core.health_check.settings")
    def test_check_telegram_config_missing_token(self, mock_settings, health_service):
        """Test Telegram config check with missing token."""
        mock_settings.TELEGRAM_BOT_TOKEN = ""
        mock_settings.TELEGRAM_CHANNEL_ID = -1001234567890

        result = health_service._check_telegram_config()

        assert result["healthy"] is False
        assert "token" in result["message"].lower()

    @patch("src.services.core.health_check.settings")
    def test_check_telegram_config_missing_channel(self, mock_settings, health_service):
        """Test Telegram config check with missing channel ID."""
        mock_settings.TELEGRAM_BOT_TOKEN = "123456:ABC"
        mock_settings.TELEGRAM_CHANNEL_ID = None

        result = health_service._check_telegram_config()

        assert result["healthy"] is False
        assert "channel" in result["message"].lower()

    def test_check_queue_healthy(self, health_service):
        """Test queue check returns healthy with normal queue."""
        health_service.queue_repo.count_pending.return_value = 5
        health_service.queue_repo.get_oldest_pending.return_value = None

        result = health_service._check_queue()

        assert result["healthy"] is True
        assert result["pending_count"] == 5

    def test_check_queue_backlog(self, health_service):
        """Test queue check detects backlog when too many pending."""
        health_service.queue_repo.count_pending.return_value = 15
        health_service.queue_repo.get_oldest_pending.return_value = None

        result = health_service._check_queue()

        assert result["healthy"] is False
        assert "backlog" in result["message"].lower()
        assert result["pending_count"] == 15

    def test_check_queue_stale_items(self, health_service):
        """Test queue check detects stale items."""
        health_service.queue_repo.count_pending.return_value = 5

        # Create mock old queue item
        old_item = Mock()
        old_item.created_at = datetime.utcnow() - timedelta(hours=8)
        health_service.queue_repo.get_oldest_pending.return_value = old_item

        result = health_service._check_queue()

        assert result["healthy"] is False
        assert "hours" in result["message"].lower()

    def test_check_queue_error(self, health_service):
        """Test queue check handles errors gracefully."""
        health_service.queue_repo.count_pending.side_effect = Exception("DB error")

        result = health_service._check_queue()

        assert result["healthy"] is False
        assert "error" in result["message"].lower()

    def test_check_recent_posts_healthy(self, health_service):
        """Test recent posts check with healthy post history."""
        mock_post1 = Mock(success=True)
        mock_post2 = Mock(success=True)
        mock_post3 = Mock(success=False)
        health_service.history_repo.get_recent_posts.return_value = [
            mock_post1,
            mock_post2,
            mock_post3,
        ]

        result = health_service._check_recent_posts()

        assert result["healthy"] is True
        assert result["recent_count"] == 3
        assert result["successful_count"] == 2
        assert "2/3" in result["message"]

    def test_check_recent_posts_no_activity(self, health_service):
        """Test recent posts check with no posts."""
        health_service.history_repo.get_recent_posts.return_value = []

        result = health_service._check_recent_posts()

        assert result["healthy"] is False
        assert "no posts" in result["message"].lower()
        assert result["recent_count"] == 0

    def test_check_recent_posts_error(self, health_service):
        """Test recent posts check handles errors gracefully."""
        health_service.history_repo.get_recent_posts.side_effect = Exception("DB error")

        result = health_service._check_recent_posts()

        assert result["healthy"] is False
        assert "error" in result["message"].lower()

    @patch("src.services.core.health_check.BaseRepository")
    @patch("src.services.core.health_check.settings")
    def test_check_all_all_healthy(self, mock_settings, mock_base_repo, health_service):
        """Test check_all returns healthy when all checks pass."""
        # Setup mocks
        mock_settings.TELEGRAM_BOT_TOKEN = "123456:ABC"
        mock_settings.TELEGRAM_CHANNEL_ID = -1001234567890
        mock_settings.ENABLE_INSTAGRAM_API = False  # Disable Instagram API check
        mock_settings.MEDIA_SYNC_ENABLED = False  # Disable media sync check
        health_service.queue_repo.count_pending.return_value = 5
        health_service.queue_repo.get_oldest_pending.return_value = None
        mock_post = Mock(success=True)
        health_service.history_repo.get_recent_posts.return_value = [mock_post]

        # Mock media pool: no active chats → healthy
        health_service._settings_service = Mock()
        health_service._settings_service.get_all_active_chats.return_value = []

        # Mock loop liveness so all loops report alive
        all_alive = {
            name: {"alive": True, "message": "OK", "expected_interval_s": 60}
            for name in [
                "scheduler",
                "lock_cleanup",
                "cloud_cleanup",
                "media_sync",
                "transaction_cleanup",
            ]
        }
        with patch("src.main.get_loop_liveness", return_value=all_alive):
            result = health_service.check_all()

        assert result["status"] == "healthy"
        assert "database" in result["checks"]
        assert "telegram" in result["checks"]
        assert "instagram_api" in result["checks"]
        assert "queue" in result["checks"]
        assert "recent_posts" in result["checks"]
        assert "media_sync" in result["checks"]
        assert "media_pool" in result["checks"]
        assert "loop_liveness" in result["checks"]
        assert "timestamp" in result

    @patch("src.services.core.health_check.BaseRepository")
    @patch("src.services.core.health_check.settings")
    def test_check_all_some_unhealthy(
        self, mock_settings, mock_base_repo, health_service
    ):
        """Test check_all returns unhealthy when any check fails."""
        # Telegram unhealthy
        mock_settings.TELEGRAM_BOT_TOKEN = ""
        mock_settings.TELEGRAM_CHANNEL_ID = None

        # Queue healthy
        health_service.queue_repo.count_pending.return_value = 5
        health_service.queue_repo.get_oldest_pending.return_value = None

        # Recent posts healthy
        mock_post = Mock(success=True)
        health_service.history_repo.get_recent_posts.return_value = [mock_post]

        result = health_service.check_all()

        assert result["status"] == "unhealthy"
        assert result["checks"]["database"]["healthy"] is True
        assert result["checks"]["telegram"]["healthy"] is False

    def test_check_all_returns_timestamp(self, health_service):
        """Test check_all includes ISO timestamp."""
        # Mock all dependencies to avoid real checks
        with (
            patch("src.services.core.health_check.BaseRepository"),
            patch("src.services.core.health_check.settings") as mock_settings,
        ):
            mock_settings.TELEGRAM_BOT_TOKEN = "token"
            mock_settings.TELEGRAM_CHANNEL_ID = -123
            health_service.queue_repo.count_pending.return_value = 0
            health_service.queue_repo.get_oldest_pending.return_value = None
            health_service.history_repo.get_recent_posts.return_value = []

            result = health_service.check_all()

            assert "timestamp" in result
            # Verify it's a valid ISO timestamp
            datetime.fromisoformat(result["timestamp"])

    # ==================== Media Sync Health Check Tests ====================

    @patch("src.services.core.health_check.settings")
    def test_check_media_sync_disabled(self, mock_settings, health_service):
        """Returns healthy with enabled=False when sync disabled."""
        mock_settings.MEDIA_SYNC_ENABLED = False

        result = health_service._check_media_sync()

        assert result["healthy"] is True
        assert result["enabled"] is False
        assert "Disabled" in result["message"]

    @patch("src.services.core.health_check.settings")
    def test_check_media_sync_healthy(self, mock_settings, health_service):
        """Returns healthy when provider accessible and last sync succeeded."""
        mock_settings.MEDIA_SYNC_ENABLED = True
        mock_settings.MEDIA_SOURCE_TYPE = "local"
        mock_settings.MEDIA_SOURCE_ROOT = "/media/stories"
        mock_settings.MEDIA_SYNC_INTERVAL_SECONDS = 300

        mock_sync_info = {
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
            "success": True,
            "status": "completed",
            "result": {"new": 2, "errors": 0},
            "duration_ms": 1500,
            "triggered_by": "scheduler",
        }

        with (
            patch("src.services.core.media_sync.MediaSyncService") as mock_sync_class,
            patch(
                "src.services.media_sources.factory.MediaSourceFactory"
            ) as mock_factory,
        ):
            mock_sync_class.return_value.get_last_sync_info.return_value = (
                mock_sync_info
            )
            mock_provider = Mock()
            mock_provider.is_configured.return_value = True
            mock_factory.create.return_value = mock_provider

            result = health_service._check_media_sync()

        assert result["healthy"] is True
        assert result["enabled"] is True
        assert result["source_type"] == "local"
        assert "OK" in result["message"]

    @patch("src.services.core.health_check.settings")
    def test_check_media_sync_no_runs(self, mock_settings, health_service):
        """Returns unhealthy when no sync runs recorded."""
        mock_settings.MEDIA_SYNC_ENABLED = True
        mock_settings.MEDIA_SOURCE_TYPE = "local"
        mock_settings.MEDIA_SOURCE_ROOT = "/media/stories"

        with (
            patch("src.services.core.media_sync.MediaSyncService") as mock_sync_class,
            patch(
                "src.services.media_sources.factory.MediaSourceFactory"
            ) as mock_factory,
        ):
            mock_sync_class.return_value.get_last_sync_info.return_value = None
            mock_provider = Mock()
            mock_provider.is_configured.return_value = True
            mock_factory.create.return_value = mock_provider

            result = health_service._check_media_sync()

        assert result["healthy"] is False
        assert result["enabled"] is True
        assert "No sync runs" in result["message"]

    @patch("src.services.core.health_check.settings")
    def test_check_media_sync_stale(self, mock_settings, health_service):
        """Returns unhealthy when last sync is stale (>3x interval)."""
        mock_settings.MEDIA_SYNC_ENABLED = True
        mock_settings.MEDIA_SOURCE_TYPE = "local"
        mock_settings.MEDIA_SOURCE_ROOT = "/media/stories"
        mock_settings.MEDIA_SYNC_INTERVAL_SECONDS = 300  # 5 min

        # Last sync was 30 minutes ago (6x the interval)
        old_time = datetime.utcnow() - timedelta(minutes=30)
        mock_sync_info = {
            "started_at": old_time.isoformat(),
            "completed_at": old_time.isoformat(),
            "success": True,
            "status": "completed",
            "result": {"new": 0, "errors": 0},
            "duration_ms": 500,
            "triggered_by": "scheduler",
        }

        with (
            patch("src.services.core.media_sync.MediaSyncService") as mock_sync_class,
            patch(
                "src.services.media_sources.factory.MediaSourceFactory"
            ) as mock_factory,
        ):
            mock_sync_class.return_value.get_last_sync_info.return_value = (
                mock_sync_info
            )
            mock_provider = Mock()
            mock_provider.is_configured.return_value = True
            mock_factory.create.return_value = mock_provider

            result = health_service._check_media_sync()

        assert result["healthy"] is False
        assert "stale" in result["message"]

    @patch("src.services.core.health_check.settings")
    def test_check_media_sync_provider_not_accessible(
        self, mock_settings, health_service
    ):
        """Returns unhealthy when provider is not accessible."""
        mock_settings.MEDIA_SYNC_ENABLED = True
        mock_settings.MEDIA_SOURCE_TYPE = "google_drive"
        mock_settings.MEDIA_SOURCE_ROOT = "folder123"

        with patch(
            "src.services.media_sources.factory.MediaSourceFactory"
        ) as mock_factory:
            mock_provider = Mock()
            mock_provider.is_configured.return_value = False
            mock_factory.create.return_value = mock_provider

            result = health_service._check_media_sync()

        assert result["healthy"] is False
        assert result["enabled"] is True
        assert "not accessible" in result["message"]
        assert result["source_type"] == "google_drive"

    @patch("src.services.core.health_check.settings")
    def test_check_media_sync_last_run_failed(self, mock_settings, health_service):
        """Returns unhealthy when last sync run failed."""
        mock_settings.MEDIA_SYNC_ENABLED = True
        mock_settings.MEDIA_SOURCE_TYPE = "local"
        mock_settings.MEDIA_SOURCE_ROOT = "/media/stories"

        mock_sync_info = {
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": None,
            "success": False,
            "status": "failed",
            "result": None,
            "duration_ms": 100,
            "triggered_by": "scheduler",
        }

        with (
            patch("src.services.core.media_sync.MediaSyncService") as mock_sync_class,
            patch(
                "src.services.media_sources.factory.MediaSourceFactory"
            ) as mock_factory,
        ):
            mock_sync_class.return_value.get_last_sync_info.return_value = (
                mock_sync_info
            )
            mock_provider = Mock()
            mock_provider.is_configured.return_value = True
            mock_factory.create.return_value = mock_provider

            result = health_service._check_media_sync()

        assert result["healthy"] is False
        assert "failed" in result["message"].lower()
        assert result["source_type"] == "local"

    # ==================== Media Pool Health Check Tests ====================

    @pytest.fixture
    def pool_service(self):
        """Create HealthCheckService with mocked pool dependencies."""
        service = HealthCheckService()
        service.queue_repo = Mock()
        service.history_repo = Mock()
        service._media_repo = Mock()
        service._settings_service = Mock()
        return service

    @pytest.fixture
    def mock_chat(self):
        """Create a mock chat_settings for pool tests."""
        chat = Mock()
        chat.id = 1
        chat.posts_per_day = 4
        chat.telegram_chat_id = -123
        return chat

    def test_check_media_pool_for_chat_healthy(self, pool_service, mock_chat):
        """Pool check returns healthy when all categories have plenty of runway."""
        pool_service._media_repo.count_eligible_by_category.return_value = {
            "memes": 50,
            "merch": 30,
        }

        result = pool_service.check_media_pool_for_chat(-123, chat_settings=mock_chat)

        assert result["total_eligible"] == 80
        assert result["posts_per_day"] == 4
        assert len(result["categories"]) == 2
        assert result["warnings"] == []
        # 2 categories, 4 posts/day -> 2 posts/day each
        # memes: 50/2 = 25 days, merch: 30/2 = 15 days
        memes_cat = next(c for c in result["categories"] if c["category"] == "memes")
        assert memes_cat["runway_days"] == 25.0
        assert memes_cat["eligible"] == 50

    def test_check_media_pool_for_chat_warning(self, pool_service, mock_chat):
        """Pool check returns warnings when a category is running low."""
        pool_service._media_repo.count_eligible_by_category.return_value = {
            "memes": 10,  # 10/2 = 5 days -> warning
            "merch": 30,  # 30/2 = 15 days -> OK
        }

        result = pool_service.check_media_pool_for_chat(-123, chat_settings=mock_chat)

        assert len(result["warnings"]) == 1
        assert "memes" in result["warnings"][0]
        assert "LOW" in result["warnings"][0]

    def test_check_media_pool_for_chat_critical(self, pool_service, mock_chat):
        """Pool check returns critical warning when category nearly empty."""
        pool_service._media_repo.count_eligible_by_category.return_value = {
            "memes": 2,  # 2/2 = 1 day -> critical
            "merch": 30,
        }

        result = pool_service.check_media_pool_for_chat(-123, chat_settings=mock_chat)

        assert len(result["warnings"]) == 1
        assert "CRITICAL" in result["warnings"][0]
        assert "memes" in result["warnings"][0]

    def test_check_media_pool_for_chat_empty(self, pool_service, mock_chat):
        """Pool check handles no eligible media gracefully."""
        pool_service._media_repo.count_eligible_by_category.return_value = {}

        result = pool_service.check_media_pool_for_chat(-123, chat_settings=mock_chat)

        assert result["total_eligible"] == 0
        assert len(result["categories"]) == 0
        assert "No eligible media" in result["warnings"][0]

    def test_check_media_pool_for_chat_single_category(self, pool_service):
        """Pool check works with single category (full posts_per_day allocation)."""
        mock_chat = Mock()
        mock_chat.id = 1
        mock_chat.posts_per_day = 3
        mock_chat.telegram_chat_id = -123

        pool_service._media_repo.count_eligible_by_category.return_value = {
            "memes": 15,  # 15/3 = 5 days -> warning
        }

        result = pool_service.check_media_pool_for_chat(-123, chat_settings=mock_chat)

        assert len(result["categories"]) == 1
        cat = result["categories"][0]
        assert cat["posts_per_day_share"] == 3.0
        assert cat["runway_days"] == 5.0
        assert len(result["warnings"]) == 1

    def test_check_media_pool_aggregated_healthy(self, pool_service, mock_chat):
        """Aggregated pool check returns healthy across all tenants."""
        mock_chat.posts_per_day = 2
        pool_service._settings_service.get_all_active_chats.return_value = [mock_chat]
        pool_service._media_repo.count_eligible_by_category.return_value = {
            "memes": 50,
        }

        result = pool_service._check_media_pool()

        assert result["healthy"] is True
        assert ">" in result["message"]

    def test_check_media_pool_aggregated_warning(self, pool_service, mock_chat):
        """Aggregated pool check returns unhealthy when worst category is low."""
        pool_service._settings_service.get_all_active_chats.return_value = [mock_chat]
        pool_service._media_repo.count_eligible_by_category.return_value = {
            "memes": 5,  # 5/4 = 1.25 days -> critical
        }

        result = pool_service._check_media_pool()

        assert result["healthy"] is False
        assert "Critical" in result["message"]
        assert result["worst_category"]["category"] == "memes"

    def test_check_media_pool_no_active_chats(self, pool_service):
        """Aggregated pool check handles no active chats."""
        pool_service._settings_service.get_all_active_chats.return_value = []

        result = pool_service._check_media_pool()

        assert result["healthy"] is True
        assert "No active chats" in result["message"]

    def test_format_pool_alert_with_warnings(self, pool_service):
        """Format alert returns text when categories are low."""
        pool_info = {
            "categories": [
                {"category": "memes", "eligible": 3, "runway_days": 1.5},
                {"category": "merch", "eligible": 50, "runway_days": 25.0},
            ],
            "warnings": ["LOW: 'memes'..."],
        }

        result = pool_service.format_pool_alert(pool_info)

        assert result is not None
        assert "memes" in result
        assert "3 items left" in result
        assert "merch" not in result  # merch is above threshold

    def test_format_pool_alert_no_warnings(self, pool_service):
        """Format alert returns None when all categories are healthy."""
        pool_info = {
            "categories": [
                {"category": "memes", "eligible": 50, "runway_days": 25.0},
            ],
            "warnings": [],
        }

        result = pool_service.format_pool_alert(pool_info)

        assert result is None

    # ==================== Google Drive Token Health Tests ====================

    @pytest.fixture
    def token_service(self):
        """Create HealthCheckService with mocked token dependencies."""
        service = HealthCheckService()
        service.queue_repo = Mock()
        service.history_repo = Mock()
        service._settings_service = Mock()
        service._token_service = Mock()
        return service

    def _gdrive_chat(self):
        """Create a mock chat configured for Google Drive."""
        chat = Mock()
        chat.id = 1
        chat.telegram_chat_id = -123
        chat.media_sync_enabled = True
        chat.media_source_type = "google_drive"
        return chat

    def test_gdrive_token_healthy(self, token_service):
        """Returns healthy when token has plenty of time left."""
        chat = self._gdrive_chat()
        token_service._token_service.check_token_health_for_chat.return_value = {
            "valid": True,
            "exists": True,
            "expires_in_hours": 30 * 24,  # 30 days
            "needs_refresh": False,
            "error": None,
        }

        result = token_service.check_gdrive_token_for_chat(-123, chat_settings=chat)

        assert result["healthy"] is True
        assert result["expires_in_days"] == 30.0

    def test_gdrive_token_warning(self, token_service):
        """Returns unhealthy when token expires within warning threshold."""
        chat = self._gdrive_chat()
        token_service._token_service.check_token_health_for_chat.return_value = {
            "valid": True,
            "exists": True,
            "expires_in_hours": 3 * 24,  # 3 days
            "needs_refresh": True,
            "error": None,
        }

        result = token_service.check_gdrive_token_for_chat(-123, chat_settings=chat)

        assert result["healthy"] is False
        assert result["expires_in_days"] == 3.0
        assert "3 days" in result["message"]

    def test_gdrive_token_expired(self, token_service):
        """Returns unhealthy when token is already expired."""
        chat = self._gdrive_chat()
        token_service._token_service.check_token_health_for_chat.return_value = {
            "valid": False,
            "exists": True,
            "expires_in_hours": 0,
            "needs_refresh": False,
            "error": "Token expired",
        }

        result = token_service.check_gdrive_token_for_chat(-123, chat_settings=chat)

        assert result["healthy"] is False
        assert "expired" in result["message"]

    def test_gdrive_token_not_found(self, token_service):
        """Returns unhealthy when no token exists."""
        chat = self._gdrive_chat()
        token_service._token_service.check_token_health_for_chat.return_value = {
            "valid": False,
            "exists": False,
            "expires_in_hours": None,
            "needs_refresh": False,
            "error": "No google_drive token found for this chat",
        }

        result = token_service.check_gdrive_token_for_chat(-123, chat_settings=chat)

        assert result["healthy"] is False
        assert "No Google Drive token" in result["message"]

    def test_gdrive_token_sync_disabled(self, token_service):
        """Returns healthy with enabled=False when sync is disabled."""
        chat = Mock()
        chat.media_sync_enabled = False

        result = token_service.check_gdrive_token_for_chat(-123, chat_settings=chat)

        assert result["healthy"] is True
        assert result["enabled"] is False

    def test_gdrive_token_local_source(self, token_service):
        """Returns healthy with enabled=False when source is local."""
        chat = Mock()
        chat.media_sync_enabled = True
        chat.media_source_type = "local"

        result = token_service.check_gdrive_token_for_chat(-123, chat_settings=chat)

        assert result["healthy"] is True
        assert result["enabled"] is False

    def test_format_token_alert_expiring(self, token_service):
        """Format alert includes expiry countdown and re-auth link."""
        token_info = {"healthy": False, "expires_in_days": 3}

        with patch("src.services.core.health_check.settings") as mock_settings:
            mock_settings.OAUTH_REDIRECT_BASE_URL = "https://example.com"
            result = token_service.format_token_alert(token_info, -123)

        assert result is not None
        assert "3 day" in result
        assert "/auth/google-drive/start?chat_id=-123" in result

    def test_format_token_alert_expired(self, token_service):
        """Format alert for already-expired token."""
        token_info = {"healthy": False, "expires_in_days": 0}

        with patch("src.services.core.health_check.settings") as mock_settings:
            mock_settings.OAUTH_REDIRECT_BASE_URL = "https://example.com"
            result = token_service.format_token_alert(token_info, -123)

        assert result is not None
        assert "expired" in result
        assert "paused" in result

    def test_format_token_alert_healthy(self, token_service):
        """Format alert returns None for healthy token."""
        token_info = {"healthy": True, "expires_in_days": 30}

        result = token_service.format_token_alert(token_info, -123)

        assert result is None
