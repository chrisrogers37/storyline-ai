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

    @patch("src.services.core.health_check.get_db")
    def test_check_database_healthy(self, mock_get_db, health_service):
        """Test database check returns healthy when DB is accessible."""
        mock_db = Mock()
        mock_get_db.return_value = iter([mock_db])

        result = health_service._check_database()

        assert result["healthy"] is True
        assert "Database connection OK" in result["message"]

    @patch("src.services.core.health_check.get_db")
    def test_check_database_unhealthy(self, mock_get_db, health_service):
        """Test database check returns unhealthy when DB fails."""
        mock_get_db.side_effect = Exception("Connection refused")

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
        health_service.queue_repo.count_pending.return_value = 60
        health_service.queue_repo.get_oldest_pending.return_value = None

        result = health_service._check_queue()

        assert result["healthy"] is False
        assert "backlog" in result["message"].lower()
        assert result["pending_count"] == 60

    def test_check_queue_stale_items(self, health_service):
        """Test queue check detects stale items."""
        health_service.queue_repo.count_pending.return_value = 5

        # Create mock old queue item
        old_item = Mock()
        old_item.created_at = datetime.utcnow() - timedelta(hours=48)
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

    @patch("src.services.core.health_check.get_db")
    @patch("src.services.core.health_check.settings")
    def test_check_all_all_healthy(self, mock_settings, mock_get_db, health_service):
        """Test check_all returns healthy when all checks pass."""
        # Setup mocks
        mock_db = Mock()
        mock_get_db.return_value = iter([mock_db])
        mock_settings.TELEGRAM_BOT_TOKEN = "123456:ABC"
        mock_settings.TELEGRAM_CHANNEL_ID = -1001234567890
        health_service.queue_repo.count_pending.return_value = 5
        health_service.queue_repo.get_oldest_pending.return_value = None
        mock_post = Mock(success=True)
        health_service.history_repo.get_recent_posts.return_value = [mock_post]

        result = health_service.check_all()

        assert result["status"] == "healthy"
        assert "database" in result["checks"]
        assert "telegram" in result["checks"]
        assert "queue" in result["checks"]
        assert "recent_posts" in result["checks"]
        assert "timestamp" in result

    @patch("src.services.core.health_check.get_db")
    @patch("src.services.core.health_check.settings")
    def test_check_all_some_unhealthy(self, mock_settings, mock_get_db, health_service):
        """Test check_all returns unhealthy when any check fails."""
        # Database healthy
        mock_db = Mock()
        mock_get_db.return_value = iter([mock_db])

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
            patch("src.services.core.health_check.get_db") as mock_get_db,
            patch("src.services.core.health_check.settings") as mock_settings,
        ):
            mock_db = Mock()
            mock_get_db.return_value = iter([mock_db])
            mock_settings.TELEGRAM_BOT_TOKEN = "token"
            mock_settings.TELEGRAM_CHANNEL_ID = -123
            health_service.queue_repo.count_pending.return_value = 0
            health_service.queue_repo.get_oldest_pending.return_value = None
            health_service.history_repo.get_recent_posts.return_value = []

            result = health_service.check_all()

            assert "timestamp" in result
            # Verify it's a valid ISO timestamp
            datetime.fromisoformat(result["timestamp"])
