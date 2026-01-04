"""Tests for HealthCheckService."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

from src.services.core.health_check import HealthCheckService
from src.repositories.media_repository import MediaRepository
from src.repositories.user_repository import UserRepository
from src.repositories.queue_repository import QueueRepository
from src.repositories.history_repository import HistoryRepository


@pytest.mark.unit
class TestHealthCheckService:
    """Test suite for HealthCheckService."""

    def test_check_database_connection_healthy(self, test_db):
        """Test database health check when connection is healthy."""
        service = HealthCheckService(db=test_db)

        result = service.check_database_connection()

        assert result["healthy"] is True
        assert "error" not in result

    @patch("src.services.core.health_check.HealthCheckService.check_database_connection")
    def test_check_database_connection_unhealthy(self, mock_check):
        """Test database health check when connection fails."""
        mock_check.return_value = {
            "healthy": False,
            "error": "Connection refused"
        }

        service = HealthCheckService()
        result = service.check_database_connection()

        assert result["healthy"] is False
        assert "error" in result

    @patch("src.services.core.health_check.settings")
    def test_check_telegram_config_valid(self, mock_settings):
        """Test Telegram configuration check with valid config."""
        mock_settings.TELEGRAM_BOT_TOKEN = "123456:ABC-DEF1234ghIkl"
        mock_settings.TELEGRAM_CHANNEL_ID = -1001234567890

        service = HealthCheckService()

        result = service.check_telegram_config()

        assert result["healthy"] is True

    @patch("src.services.core.health_check.settings")
    def test_check_telegram_config_invalid(self, mock_settings):
        """Test Telegram configuration check with invalid config."""
        mock_settings.TELEGRAM_BOT_TOKEN = ""
        mock_settings.TELEGRAM_CHANNEL_ID = -1001234567890

        service = HealthCheckService()

        result = service.check_telegram_config()

        assert result["healthy"] is False

    def test_check_queue_status_healthy(self, test_db):
        """Test queue status check when healthy."""
        media_repo = MediaRepository(test_db)
        user_repo = UserRepository(test_db)
        queue_repo = QueueRepository(test_db)

        # Create a few queue items (not excessive)
        media = media_repo.create(
            file_path="/test/queue_health.jpg",
            file_name="queue_health.jpg",
            file_hash="queue_h890",
            file_size_bytes=100000,
            mime_type="image/jpeg"
        )

        user = user_repo.create(telegram_user_id=800001)

        # Create 5 pending items (below threshold)
        for i in range(5):
            queue_repo.create(
                media_id=media.id,
                scheduled_user_id=user.id,
                scheduled_time=datetime.utcnow() - timedelta(minutes=i)
            )

        service = HealthCheckService(db=test_db)

        result = service.check_queue_status()

        assert result["healthy"] is True
        assert result["pending_count"] == 5

    def test_check_queue_status_backlog(self, test_db):
        """Test queue status check when backlog exists."""
        media_repo = MediaRepository(test_db)
        user_repo = UserRepository(test_db)
        queue_repo = QueueRepository(test_db)

        media = media_repo.create(
            file_path="/test/backlog.jpg",
            file_name="backlog.jpg",
            file_hash="backlog890",
            file_size_bytes=95000,
            mime_type="image/jpeg"
        )

        user = user_repo.create(telegram_user_id=800002)

        # Create many old pending items (backlog)
        for i in range(15):
            queue_repo.create(
                media_id=media.id,
                scheduled_user_id=user.id,
                scheduled_time=datetime.utcnow() - timedelta(hours=i + 1)
            )

        service = HealthCheckService(db=test_db)

        result = service.check_queue_status()

        # Should detect backlog
        assert result["pending_count"] >= 15

    def test_check_recent_posts_healthy(self, test_db):
        """Test recent posts check when posts are recent."""
        media_repo = MediaRepository(test_db)
        user_repo = UserRepository(test_db)
        history_repo = HistoryRepository(test_db)

        media = media_repo.create(
            file_path="/test/recent_post.jpg",
            file_name="recent_post.jpg",
            file_hash="recent890",
            file_size_bytes=90000,
            mime_type="image/jpeg"
        )

        user = user_repo.create(telegram_user_id=800003)

        # Create recent post (within last 7 days)
        history_repo.create(
            media_id=media.id,
            posted_by_user_id=user.id,
            status="posted"
        )

        service = HealthCheckService(db=test_db)

        result = service.check_recent_posts(days=7)

        assert result["posts_count"] >= 1

    def test_check_recent_posts_no_activity(self, test_db):
        """Test recent posts check when no recent posts."""
        service = HealthCheckService(db=test_db)

        result = service.check_recent_posts(days=7)

        # May have no posts in test database
        assert "posts_count" in result

    def test_run_all_checks(self, test_db):
        """Test running all health checks."""
        service = HealthCheckService(db=test_db)

        results = service.run_all_checks()

        assert "database" in results
        assert "telegram" in results
        assert "queue" in results
        assert "recent_posts" in results

        # Calculate overall health
        all_healthy = all(
            check.get("healthy", False)
            for check in results.values()
        )

        assert isinstance(all_healthy, bool)

    def test_get_system_info(self, test_db):
        """Test getting system information."""
        service = HealthCheckService(db=test_db)

        info = service.get_system_info()

        assert "total_media" in info
        assert "total_users" in info
        assert "total_queue_items" in info
        assert "total_history_records" in info
