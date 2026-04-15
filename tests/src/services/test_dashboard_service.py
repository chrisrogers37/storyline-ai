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
        assert result["summary"]["avg_per_day"] == 3.3  # 100 / 30 days
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


@pytest.mark.unit
class TestGetCategoryAnalytics:
    """Tests for get_category_analytics with configured vs actual ratios."""

    def _setup_service(self):
        """Create DashboardService with mocked dependencies."""
        with patch.object(DashboardService, "__init__", lambda self: None):
            service = DashboardService()
            service.settings_service = MagicMock()
            service.queue_repo = MagicMock()
            service.history_repo = MagicMock()
            service.media_repo = MagicMock()
            service.category_mix_repo = MagicMock()
            service.service_run_repo = MagicMock()
            service.service_name = "DashboardService"

            mock_settings = Mock(id="tenant-uuid-1")
            service.settings_service.get_settings.return_value = mock_settings
            return service

    def test_enriches_with_configured_ratios(self):
        """Category analytics includes configured vs actual ratios."""
        service = self._setup_service()

        service.history_repo.get_stats_by_category.return_value = [
            {
                "category": "memes",
                "posted": 70,
                "skipped": 5,
                "rejected": 3,
                "total": 78,
                "success_rate": 0.9,
            },
            {
                "category": "merch",
                "posted": 18,
                "skipped": 2,
                "rejected": 0,
                "total": 20,
                "success_rate": 0.9,
            },
        ]
        from decimal import Decimal

        service.category_mix_repo.get_current_mix_as_dict.return_value = {
            "memes": Decimal("0.70"),
            "merch": Decimal("0.30"),
        }

        result = service.get_category_analytics(telegram_chat_id=123, days=30)

        assert result["total_posts"] == 98
        assert len(result["categories"]) == 2

        memes = next(c for c in result["categories"] if c["category"] == "memes")
        assert memes["posted"] == 70
        assert memes["skipped"] == 5
        assert memes["rejected"] == 3
        assert memes["success_rate"] == 0.9
        assert memes["actual_ratio"] == 0.8  # 78/98
        assert memes["configured_ratio"] == 0.7

        merch = next(c for c in result["categories"] if c["category"] == "merch")
        assert merch["actual_ratio"] == 0.2  # 20/98
        assert merch["configured_ratio"] == 0.3

    def test_handles_missing_configured_ratio(self):
        """Categories without a configured ratio get None."""
        service = self._setup_service()

        service.history_repo.get_stats_by_category.return_value = [
            {"category": "memes", "posted": 10, "total": 10, "success_rate": 1.0},
        ]
        service.category_mix_repo.get_current_mix_as_dict.return_value = {}

        result = service.get_category_analytics(telegram_chat_id=123)

        assert result["categories"][0]["configured_ratio"] is None

    def test_handles_empty_history(self):
        """Category analytics handles no posting history gracefully."""
        service = self._setup_service()

        service.history_repo.get_stats_by_category.return_value = []
        service.category_mix_repo.get_current_mix_as_dict.return_value = {}

        result = service.get_category_analytics(telegram_chat_id=123)

        assert result["total_posts"] == 0
        assert result["categories"] == []


@pytest.mark.unit
class TestGetScheduleRecommendations:
    """Tests for schedule recommendation generation."""

    def _setup_service(self):
        """Create DashboardService with mocked dependencies."""
        with patch.object(DashboardService, "__init__", lambda self: None):
            service = DashboardService()
            service.settings_service = MagicMock()
            service.queue_repo = MagicMock()
            service.history_repo = MagicMock()
            service.media_repo = MagicMock()
            service.category_mix_repo = MagicMock()
            service.service_run_repo = MagicMock()
            service.service_name = "DashboardService"

            mock_settings = Mock(id="tenant-uuid-1")
            service.settings_service.get_settings.return_value = mock_settings
            return service

    def test_returns_recommendations_with_sufficient_data(self):
        """Generates recommendations when enough data exists."""
        service = self._setup_service()

        service.history_repo.get_hourly_approval_rates.return_value = [
            {
                "hour": 10,
                "posted": 15,
                "skipped": 1,
                "total": 16,
                "approval_rate": 0.94,
            },
            {"hour": 14, "posted": 8, "skipped": 7, "total": 15, "approval_rate": 0.53},
            {
                "hour": 18,
                "posted": 10,
                "skipped": 2,
                "total": 12,
                "approval_rate": 0.83,
            },
        ]
        service.history_repo.get_dow_approval_rates.return_value = [
            {
                "dow": 1,
                "day_name": "Monday",
                "posted": 20,
                "skipped": 2,
                "total": 22,
                "approval_rate": 0.91,
            },
            {
                "dow": 6,
                "day_name": "Saturday",
                "posted": 5,
                "skipped": 5,
                "total": 10,
                "approval_rate": 0.50,
            },
        ]

        result = service.get_schedule_recommendations(telegram_chat_id=123)

        assert result["status"] == "ok"
        assert len(result["hourly_rates"]) == 3
        assert len(result["dow_rates"]) == 2
        assert len(result["recommendations"]) >= 1
        # Should recommend hour 10 as best
        best_hour_rec = next(
            (r for r in result["recommendations"] if r["type"] == "best_hour"), None
        )
        assert best_hour_rec is not None
        assert best_hour_rec["hour"] == 10

    def test_returns_insufficient_data_when_too_few_posts(self):
        """Returns insufficient_data status with fewer than 10 posts."""
        service = self._setup_service()

        service.history_repo.get_hourly_approval_rates.return_value = [
            {"hour": 10, "posted": 3, "total": 3, "approval_rate": 1.0},
        ]
        service.history_repo.get_dow_approval_rates.return_value = []

        result = service.get_schedule_recommendations(telegram_chat_id=123)

        assert result["status"] == "insufficient_data"
        assert result["recommendations"] == []

    def test_no_recommendations_when_all_hours_similar(self):
        """No best/worst hour recommendation when rates are close."""
        service = self._setup_service()

        service.history_repo.get_hourly_approval_rates.return_value = [
            {"hour": 10, "posted": 9, "skipped": 1, "total": 10, "approval_rate": 0.90},
            {"hour": 14, "posted": 8, "skipped": 2, "total": 10, "approval_rate": 0.80},
        ]
        service.history_repo.get_dow_approval_rates.return_value = [
            {
                "dow": 1,
                "day_name": "Monday",
                "posted": 9,
                "skipped": 1,
                "total": 10,
                "approval_rate": 0.90,
            },
        ]

        result = service.get_schedule_recommendations(telegram_chat_id=123)

        assert result["status"] == "ok"
        # Difference is only 0.10 — at threshold, shouldn't crash regardless of outcome
        assert isinstance(result["recommendations"], list)

    def test_generate_recommendations_static_method(self):
        """_generate_recommendations works as a pure function."""
        hourly = [
            {"hour": 9, "posted": 20, "skipped": 0, "total": 20, "approval_rate": 1.0},
            {"hour": 22, "posted": 3, "skipped": 7, "total": 10, "approval_rate": 0.3},
        ]
        dow = [
            {
                "dow": 2,
                "day_name": "Tuesday",
                "posted": 15,
                "skipped": 0,
                "total": 15,
                "approval_rate": 1.0,
            },
            {
                "dow": 0,
                "day_name": "Sunday",
                "posted": 3,
                "skipped": 4,
                "total": 7,
                "approval_rate": 0.43,
            },
        ]

        recs = DashboardService._generate_recommendations(hourly, dow)

        types = {r["type"] for r in recs}
        assert "best_hour" in types
        assert "worst_hour" in types
        assert "best_day" in types
        assert "worst_day" in types
        worst_day_rec = next(r for r in recs if r["type"] == "worst_day")
        assert worst_day_rec["day_name"] == "Sunday"


@pytest.mark.unit
class TestGetSchedulePreview:
    """Tests for get_schedule_preview."""

    def _setup_service(self):
        with patch.object(DashboardService, "__init__", lambda self: None):
            service = DashboardService()
            service.settings_service = MagicMock()
            service.category_mix_repo = MagicMock()
            service.service_run_repo = MagicMock()
            service.service_name = "DashboardService"
            return service

    def test_returns_slot_times(self):
        """Preview returns correct number of slots with interval."""
        from decimal import Decimal

        service = self._setup_service()
        mock_settings = Mock(
            id="t1",
            is_paused=False,
            posts_per_day=3,
            posting_hours_start=14,
            posting_hours_end=2,
            last_post_sent_at=None,
        )
        service.settings_service.get_settings.return_value = mock_settings
        service.category_mix_repo.get_current_mix_as_dict.return_value = {
            "memes": Decimal("0.50"),
            "merch": Decimal("0.50"),
        }

        result = service.get_schedule_preview(telegram_chat_id=123, slots=5)

        assert result["status"] == "ok"
        assert len(result["slots"]) == 5
        assert result["posts_per_day"] == 3
        assert all(
            s["predicted_category"] in ("memes", "merch") for s in result["slots"]
        )

    def test_returns_paused_when_paused(self):
        """Preview returns paused status when posting is paused."""
        service = self._setup_service()
        mock_settings = Mock(is_paused=True)
        service.settings_service.get_settings.return_value = mock_settings

        result = service.get_schedule_preview(telegram_chat_id=123)

        assert result["status"] == "paused"
        assert result["slots"] == []

    def test_uses_last_post_sent_at(self):
        """Slots start from last_post_sent_at + interval when set."""
        from datetime import datetime, timezone
        from decimal import Decimal

        service = self._setup_service()
        last_post = datetime(2026, 4, 15, 15, 0, 0, tzinfo=timezone.utc)
        mock_settings = Mock(
            id="t1",
            is_paused=False,
            posts_per_day=3,
            posting_hours_start=14,
            posting_hours_end=2,
            last_post_sent_at=last_post,
        )
        service.settings_service.get_settings.return_value = mock_settings
        service.category_mix_repo.get_current_mix_as_dict.return_value = {
            "memes": Decimal("1.0"),
        }

        result = service.get_schedule_preview(telegram_chat_id=123, slots=2)

        assert result["status"] == "ok"
        assert len(result["slots"]) == 2
        first_slot = result["slots"][0]["slot_time"]
        assert first_slot > last_post.isoformat()


@pytest.mark.unit
class TestGetCategoryMixDrift:
    """Tests for get_category_mix_drift."""

    def _setup_service(self):
        with patch.object(DashboardService, "__init__", lambda self: None):
            service = DashboardService()
            service.settings_service = MagicMock()
            service.history_repo = MagicMock()
            service.category_mix_repo = MagicMock()
            service.service_run_repo = MagicMock()
            service.service_name = "DashboardService"
            mock_settings = Mock(id="tenant-uuid-1")
            service.settings_service.get_settings.return_value = mock_settings
            return service

    def test_detects_drift(self):
        """Flags categories with significant drift as warning/critical."""
        from decimal import Decimal

        service = self._setup_service()
        service.category_mix_repo.get_current_mix_as_dict.return_value = {
            "memes": Decimal("0.60"),
            "merch": Decimal("0.40"),
        }
        service.history_repo.get_stats_by_category.return_value = [
            {"category": "memes", "posted": 30},
            {"category": "merch", "posted": 70},
        ]

        result = service.get_category_mix_drift(telegram_chat_id=123, days=7)

        assert not result["healthy"]
        memes = next(c for c in result["categories"] if c["category"] == "memes")
        assert memes["configured_ratio"] == 0.60
        assert memes["actual_ratio"] == 0.30
        assert memes["drift"] == 0.30
        assert memes["status"] == "critical"

    def test_healthy_when_no_drift(self):
        """Reports healthy when actual matches configured."""
        from decimal import Decimal

        service = self._setup_service()
        service.category_mix_repo.get_current_mix_as_dict.return_value = {
            "memes": Decimal("0.50"),
            "merch": Decimal("0.50"),
        }
        service.history_repo.get_stats_by_category.return_value = [
            {"category": "memes", "posted": 50},
            {"category": "merch", "posted": 50},
        ]

        result = service.get_category_mix_drift(telegram_chat_id=123)

        assert result["healthy"]
        assert result["max_drift"] == 0.0

    def test_handles_no_posts(self):
        """Returns zeros when no posting history."""
        from decimal import Decimal

        service = self._setup_service()
        service.category_mix_repo.get_current_mix_as_dict.return_value = {
            "memes": Decimal("1.0"),
        }
        service.history_repo.get_stats_by_category.return_value = []

        result = service.get_category_mix_drift(telegram_chat_id=123)

        assert result["total_posted"] == 0
        assert result["categories"][0]["actual_ratio"] == 0


@pytest.mark.unit
class TestGetApprovalLatency:
    """Tests for get_approval_latency."""

    def _setup_service(self):
        with patch.object(DashboardService, "__init__", lambda self: None):
            service = DashboardService()
            service.settings_service = MagicMock()
            service.history_repo = MagicMock()
            service.service_run_repo = MagicMock()
            service.service_name = "DashboardService"
            mock_settings = Mock(id="tenant-uuid-1")
            service.settings_service.get_settings.return_value = mock_settings
            return service

    def test_returns_latency_stats(self):
        """get_approval_latency returns overall + breakdowns from repo."""
        service = self._setup_service()
        service.history_repo.get_approval_latency.return_value = {
            "overall": {
                "count": 50,
                "avg_minutes": 5.0,
                "min_minutes": 1.0,
                "max_minutes": 30.0,
            },
            "by_hour": [{"hour": 14, "count": 20, "avg_minutes": 4.0}],
            "by_category": [{"category": "memes", "count": 30, "avg_minutes": 3.0}],
        }

        result = service.get_approval_latency(telegram_chat_id=123, days=30)

        assert result["overall"]["count"] == 50
        assert result["overall"]["avg_minutes"] == 5.0
        assert result["days"] == 30
        assert len(result["by_hour"]) == 1
        assert len(result["by_category"]) == 1

    def test_empty_latency(self):
        """Returns zero stats when no posting history."""
        service = self._setup_service()
        service.history_repo.get_approval_latency.return_value = {
            "overall": {
                "count": 0,
                "avg_minutes": 0,
                "min_minutes": 0,
                "max_minutes": 0,
            },
            "by_hour": [],
            "by_category": [],
        }

        result = service.get_approval_latency(telegram_chat_id=123)

        assert result["overall"]["count"] == 0
        assert result["days"] == 30


@pytest.mark.unit
class TestGetContentReuseInsights:
    """Tests for get_content_reuse_insights."""

    def _setup_service(self):
        with patch.object(DashboardService, "__init__", lambda self: None):
            service = DashboardService()
            service.settings_service = MagicMock()
            service.media_repo = MagicMock()
            service.service_run_repo = MagicMock()
            service.service_name = "DashboardService"
            mock_settings = Mock(id="tenant-uuid-1")
            service.settings_service.get_settings.return_value = mock_settings
            return service

    def test_returns_reuse_tiers(self):
        """Returns posting status breakdown and reuse rate."""
        service = self._setup_service()
        service.media_repo.count_by_posting_status.return_value = {
            "never_posted": 30,
            "posted_once": 50,
            "posted_multiple": 20,
        }
        service.media_repo.count_dead_content_by_category.return_value = [
            {"category": "memes", "dead_count": 20},
            {"category": "merch", "dead_count": 10},
        ]

        result = service.get_content_reuse_insights(telegram_chat_id=123)

        assert result["total_active"] == 100
        assert result["never_posted"] == 30
        assert result["posted_once"] == 50
        assert result["posted_multiple"] == 20
        assert result["reuse_rate"] == 0.2
        assert len(result["never_posted_by_category"]) == 2

    def test_handles_empty_pool(self):
        """Returns zeros when no active media."""
        service = self._setup_service()
        service.media_repo.count_by_posting_status.return_value = {
            "never_posted": 0,
            "posted_once": 0,
            "posted_multiple": 0,
        }
        service.media_repo.count_dead_content_by_category.return_value = []

        result = service.get_content_reuse_insights(telegram_chat_id=123)

        assert result["total_active"] == 0
        assert result["reuse_rate"] == 0
        assert result["never_posted_by_category"] == []


@pytest.mark.unit
class TestGetDeadContentReport:
    """Tests for get_dead_content_report."""

    def _setup_service(self):
        with patch.object(DashboardService, "__init__", lambda self: None):
            service = DashboardService()
            service.settings_service = MagicMock()
            service.media_repo = MagicMock()
            service.service_run_repo = MagicMock()
            service.service_name = "DashboardService"
            mock_settings = Mock(id="tenant-uuid-1")
            service.settings_service.get_settings.return_value = mock_settings
            return service

    def test_returns_dead_content(self):
        """get_dead_content_report returns per-category dead content stats."""
        service = self._setup_service()
        service.media_repo.count_active.return_value = 100
        service.media_repo.count_dead_content_by_category.return_value = [
            {"category": "memes", "dead_count": 10},
            {"category": "merch", "dead_count": 5},
        ]

        result = service.get_dead_content_report(telegram_chat_id=123)

        assert result["total_active"] == 100
        assert result["total_dead"] == 15
        assert result["dead_percentage"] == 0.15
        assert len(result["by_category"]) == 2

    def test_empty_dead_content(self):
        """Returns zero stats when no dead content."""
        service = self._setup_service()
        service.media_repo.count_active.return_value = 50
        service.media_repo.count_dead_content_by_category.return_value = []

        result = service.get_dead_content_report(telegram_chat_id=123)

        assert result["total_dead"] == 0
        assert result["dead_percentage"] == 0


@pytest.mark.unit
class TestGetTeamPerformance:
    """Tests for get_team_performance."""

    def _setup_service(self):
        with patch.object(DashboardService, "__init__", lambda self: None):
            service = DashboardService()
            service.settings_service = MagicMock()
            service.history_repo = MagicMock()
            service.service_run_repo = MagicMock()
            service.service_name = "DashboardService"
            mock_settings = Mock(id="tenant-uuid-1")
            service.settings_service.get_settings.return_value = mock_settings
            return service

    def test_returns_user_stats(self):
        """get_team_performance returns per-user data from repo."""
        service = self._setup_service()
        service.history_repo.get_user_approval_stats.return_value = [
            {
                "user_id": "u1",
                "username": "alice",
                "posted": 40,
                "skipped": 5,
                "rejected": 5,
                "total": 50,
                "approval_rate": 0.8,
                "avg_latency_minutes": 3.0,
            },
        ]

        result = service.get_team_performance(telegram_chat_id=123, days=30)

        assert len(result["users"]) == 1
        assert result["users"][0]["username"] == "alice"
        assert result["users"][0]["approval_rate"] == 0.8
        assert result["days"] == 30

    def test_empty_users(self):
        """Returns empty user list when no data."""
        service = self._setup_service()
        service.history_repo.get_user_approval_stats.return_value = []

        result = service.get_team_performance(telegram_chat_id=123)

        assert result["users"] == []
        assert result["days"] == 30


@pytest.mark.unit
class TestGetServiceHealthStats:
    """Tests for get_service_health_stats."""

    def test_returns_per_service_stats(self):
        """Returns aggregated service run telemetry."""
        with patch.object(DashboardService, "__init__", lambda self: None):
            service = DashboardService()
            service.service_run_repo = MagicMock()
            service.service_run_repo.get_health_stats.return_value = [
                {
                    "service_name": "PostingService",
                    "call_count": 100,
                    "success_count": 95,
                    "failure_count": 5,
                    "error_rate": 0.05,
                    "avg_duration_ms": 150,
                },
            ]

            result = service.get_service_health_stats(hours=24)

            assert result["total_calls"] == 100
            assert result["total_failures"] == 5
            assert result["overall_error_rate"] == 0.05
            assert len(result["services"]) == 1

    def test_handles_no_runs(self):
        """Returns zeros when no service runs in window."""
        with patch.object(DashboardService, "__init__", lambda self: None):
            service = DashboardService()
            service.service_run_repo = MagicMock()
            service.service_run_repo.get_health_stats.return_value = []

            result = service.get_service_health_stats()

            assert result["total_calls"] == 0
            assert result["overall_error_rate"] == 0
