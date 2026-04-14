"""Tests for DashboardService."""

import pytest
from unittest.mock import MagicMock, Mock, patch
from datetime import datetime

from src.services.core.dashboard_service import DashboardService


@pytest.fixture
def dashboard_service():
    """Create DashboardService with mocked dependencies."""
    with patch.object(DashboardService, "__init__", lambda self: None):
        service = DashboardService()
        service.settings_service = MagicMock()
        service.queue_repo = MagicMock()
        service.history_repo = MagicMock()
        service.media_repo = MagicMock()

        # Default: _resolve_chat_settings_id returns a tenant ID
        mock_settings = Mock(id="tenant-uuid-1")
        service.settings_service.get_settings.return_value = mock_settings
        return service


@pytest.mark.unit
class TestGetQueueDetail:
    """Tests for get_queue_detail using JOIN-based queries."""

    def test_returns_items_from_join(self, dashboard_service):
        """get_queue_detail builds items from JOIN tuples, not per-item lookups."""
        pending_item = Mock(
            scheduled_for=datetime(2026, 3, 1, 14, 0),
            status="pending",
        )
        processing_item = Mock(
            scheduled_for=datetime(2026, 3, 1, 18, 0),
            status="processing",
        )

        dashboard_service.queue_repo.get_all_with_media.side_effect = [
            [(pending_item, "meme_01.jpg", "memes")],
            [(processing_item, "merch_01.jpg", "merch")],
        ]
        dashboard_service.history_repo.get_recent_posts.return_value = []

        result = dashboard_service.get_queue_detail(telegram_chat_id=123)

        assert len(result["items"]) == 2
        assert result["items"][0]["media_name"] == "meme_01.jpg"
        assert result["items"][0]["category"] == "memes"
        assert result["items"][0]["status"] == "pending"
        assert result["items"][1]["media_name"] == "merch_01.jpg"
        assert result["items"][1]["status"] == "processing"
        assert result["total_in_flight"] == 2

        # Verify media_repo.get_by_id was NOT called (no N+1)
        dashboard_service.media_repo.get_by_id.assert_not_called()

    def test_handles_null_media_fields(self, dashboard_service):
        """Queue items with missing media use fallback values."""
        item = Mock(
            scheduled_for=datetime(2026, 3, 1, 14, 0),
            status="pending",
        )

        dashboard_service.queue_repo.get_all_with_media.side_effect = [
            [(item, None, None)],  # pending
            [],  # processing
        ]
        dashboard_service.history_repo.get_recent_posts.return_value = []

        result = dashboard_service.get_queue_detail(telegram_chat_id=123)

        assert result["items"][0]["media_name"] == "Unknown"
        assert result["items"][0]["category"] == "uncategorized"

    def test_includes_posts_today_and_last_post(self, dashboard_service):
        """get_queue_detail includes posts_today and last_post_at."""
        dashboard_service.queue_repo.get_all_with_media.side_effect = [[], []]

        post = Mock(posted_at=datetime(2026, 3, 1, 14, 0))
        dashboard_service.history_repo.get_recent_posts.return_value = [post]

        result = dashboard_service.get_queue_detail(telegram_chat_id=123)

        assert result["posts_today"] == 1
        assert result["last_post_at"] == "2026-03-01T14:00:00"

    def test_respects_limit(self, dashboard_service):
        """get_queue_detail limits the number of items returned."""
        items = [
            (
                Mock(scheduled_for=datetime(2026, 3, 1, i, 0), status="pending"),
                f"img_{i}.jpg",
                "cat",
            )
            for i in range(5)
        ]

        dashboard_service.queue_repo.get_all_with_media.side_effect = [
            items,
            [],
        ]
        dashboard_service.history_repo.get_recent_posts.return_value = []

        result = dashboard_service.get_queue_detail(telegram_chat_id=123, limit=3)

        assert len(result["items"]) == 3
        assert result["total_in_flight"] == 5

    def test_empty_queue(self, dashboard_service):
        """get_queue_detail handles empty queue."""
        dashboard_service.queue_repo.get_all_with_media.side_effect = [[], []]
        dashboard_service.history_repo.get_recent_posts.return_value = []

        result = dashboard_service.get_queue_detail(telegram_chat_id=123)

        assert result["items"] == []
        assert result["total_in_flight"] == 0
        assert result["posts_today"] == 0
        assert result["last_post_at"] is None


@pytest.mark.unit
class TestGetHistoryDetail:
    """Tests for get_history_detail using JOIN-based queries."""

    def test_returns_items_from_join(self, dashboard_service):
        """get_history_detail builds items from JOIN tuples."""
        history_item = Mock(
            posted_at=datetime(2026, 3, 1, 14, 0),
            status="posted",
            posting_method="instagram_api",
        )

        dashboard_service.history_repo.get_all_with_media.return_value = [
            (history_item, "story_01.jpg", "memes"),
        ]

        result = dashboard_service.get_history_detail(telegram_chat_id=123)

        assert len(result["items"]) == 1
        assert result["items"][0]["media_name"] == "story_01.jpg"
        assert result["items"][0]["category"] == "memes"
        assert result["items"][0]["status"] == "posted"
        assert result["items"][0]["posting_method"] == "instagram_api"

        # Verify media_repo.get_by_id was NOT called (no N+1)
        dashboard_service.media_repo.get_by_id.assert_not_called()

    def test_handles_null_media_fields(self, dashboard_service):
        """History items with missing media use fallback values."""
        item = Mock(
            posted_at=datetime(2026, 3, 1, 14, 0),
            status="skipped",
            posting_method="telegram_manual",
        )

        dashboard_service.history_repo.get_all_with_media.return_value = [
            (item, None, None),
        ]

        result = dashboard_service.get_history_detail(telegram_chat_id=123)

        assert result["items"][0]["media_name"] == "Unknown"
        assert result["items"][0]["category"] == "uncategorized"

    def test_empty_history(self, dashboard_service):
        """get_history_detail handles empty history."""
        dashboard_service.history_repo.get_all_with_media.return_value = []

        result = dashboard_service.get_history_detail(telegram_chat_id=123)

        assert result["items"] == []

    def test_passes_limit_to_repo(self, dashboard_service):
        """get_history_detail passes limit argument to repository."""
        dashboard_service.history_repo.get_all_with_media.return_value = []

        dashboard_service.get_history_detail(telegram_chat_id=123, limit=5)

        dashboard_service.history_repo.get_all_with_media.assert_called_once_with(
            limit=5, chat_settings_id="tenant-uuid-1"
        )


@pytest.mark.unit
class TestGetPendingQueueItems:
    """Tests for get_pending_queue_items using JOIN-based queries."""

    def test_returns_items_from_join(self, dashboard_service):
        """get_pending_queue_items builds items from JOIN tuples."""
        item = Mock(
            scheduled_for=datetime(2026, 3, 1, 14, 0),
            status="pending",
        )

        dashboard_service.queue_repo.get_all_with_media.return_value = [
            (item, "queue_list.jpg", "memes"),
        ]

        result = dashboard_service.get_pending_queue_items()

        assert len(result) == 1
        assert result[0]["file_name"] == "queue_list.jpg"
        assert result[0]["category"] == "memes"
        assert result[0]["status"] == "pending"
        assert result[0]["scheduled_for"] == datetime(2026, 3, 1, 14, 0)

        # Verify media_repo.get_by_id was NOT called (no N+1)
        dashboard_service.media_repo.get_by_id.assert_not_called()

    def test_handles_null_media_fields(self, dashboard_service):
        """Pending items with missing media use fallback values."""
        item = Mock(
            scheduled_for=datetime(2026, 3, 1, 14, 0),
            status="pending",
        )

        dashboard_service.queue_repo.get_all_with_media.return_value = [
            (item, None, None),
        ]

        result = dashboard_service.get_pending_queue_items()

        assert result[0]["file_name"] == "Unknown"
        assert result[0]["category"] == "-"

    def test_passes_chat_settings_id(self, dashboard_service):
        """get_pending_queue_items passes chat_settings_id to repository."""
        dashboard_service.queue_repo.get_all_with_media.return_value = []

        dashboard_service.get_pending_queue_items(chat_settings_id="tenant-123")

        dashboard_service.queue_repo.get_all_with_media.assert_called_once_with(
            status="pending", chat_settings_id="tenant-123"
        )

    def test_empty_queue(self, dashboard_service):
        """get_pending_queue_items handles empty queue."""
        dashboard_service.queue_repo.get_all_with_media.return_value = []

        result = dashboard_service.get_pending_queue_items()

        assert result == []


@pytest.mark.unit
class TestGetAnalytics:
    """Tests for get_analytics aggregation."""

    def _setup_analytics_service(self):
        """Create DashboardService with mocked dependencies for analytics."""
        with patch.object(DashboardService, "__init__", lambda self: None):
            service = DashboardService()
            service.settings_service = MagicMock()
            service.queue_repo = MagicMock()
            service.history_repo = MagicMock()
            service.media_repo = MagicMock()
            service.service_run_repo = MagicMock()
            service.service_name = "DashboardService"

            mock_settings = Mock(id="tenant-uuid-1")
            service.settings_service.get_settings.return_value = mock_settings
            return service

    def test_returns_complete_analytics(self):
        """get_analytics returns all expected sections."""
        service = self._setup_analytics_service()

        service.history_repo.get_stats_by_status.return_value = {
            "posted": 80,
            "skipped": 10,
            "rejected": 5,
            "failed": 5,
        }
        service.history_repo.get_stats_by_method.return_value = {
            "instagram_api": 60,
            "telegram_manual": 20,
        }
        service.history_repo.get_daily_counts.return_value = [
            {"date": "2026-04-10", "posted": 4, "skipped": 1},
            {"date": "2026-04-11", "posted": 5},
        ]
        service.history_repo.get_hourly_distribution.return_value = [
            {"hour": 10, "count": 15},
            {"hour": 14, "count": 20},
        ]
        service.history_repo.get_stats_by_category.return_value = [
            {
                "category": "memes",
                "posted": 50,
                "skipped": 8,
                "total": 58,
                "success_rate": 0.86,
            },
        ]

        result = service.get_analytics(telegram_chat_id=123, days=30)

        assert result["summary"]["total_posts"] == 100
        assert result["summary"]["posted"] == 80
        assert result["summary"]["success_rate"] == 0.8
        assert result["summary"]["avg_per_day"] == 50.0  # 100 / 2 days
        assert result["method_breakdown"]["instagram_api"] == 60
        assert len(result["daily_counts"]) == 2
        assert len(result["hourly_distribution"]) == 2
        assert len(result["category_breakdown"]) == 1
        assert result["days"] == 30

    def test_handles_empty_history(self):
        """get_analytics handles no posting history gracefully."""
        service = self._setup_analytics_service()

        service.history_repo.get_stats_by_status.return_value = {}
        service.history_repo.get_stats_by_method.return_value = {}
        service.history_repo.get_daily_counts.return_value = []
        service.history_repo.get_hourly_distribution.return_value = []
        service.history_repo.get_stats_by_category.return_value = []

        result = service.get_analytics(telegram_chat_id=123)

        assert result["summary"]["total_posts"] == 0
        assert result["summary"]["success_rate"] == 0
        assert result["summary"]["avg_per_day"] == 0
        assert result["daily_counts"] == []

    def test_passes_days_and_tenant(self):
        """get_analytics passes days and chat_settings_id to all repo methods."""
        service = self._setup_analytics_service()

        service.history_repo.get_stats_by_status.return_value = {}
        service.history_repo.get_stats_by_method.return_value = {}
        service.history_repo.get_daily_counts.return_value = []
        service.history_repo.get_hourly_distribution.return_value = []
        service.history_repo.get_stats_by_category.return_value = []

        service.get_analytics(telegram_chat_id=123, days=7)

        service.history_repo.get_stats_by_status.assert_called_once_with(
            days=7, chat_settings_id="tenant-uuid-1"
        )
        service.history_repo.get_stats_by_method.assert_called_once_with(
            days=7, chat_settings_id="tenant-uuid-1"
        )
        service.history_repo.get_daily_counts.assert_called_once_with(
            days=7, chat_settings_id="tenant-uuid-1"
        )
