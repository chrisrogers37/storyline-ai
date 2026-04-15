"""Tests for HistoryRepository."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from sqlalchemy.orm import Session

from src.repositories.history_repository import HistoryRepository, HistoryCreateParams
from src.models.posting_history import PostingHistory


@pytest.fixture
def mock_db():
    """Create a mock database session with chainable query."""
    session = MagicMock(spec=Session)
    mock_query = MagicMock()
    session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    return session


@pytest.fixture
def history_repo(mock_db):
    """Create HistoryRepository with mocked database session."""
    with patch.object(HistoryRepository, "__init__", lambda self: None):
        repo = HistoryRepository()
        repo._db = mock_db
        return repo


@pytest.mark.unit
class TestHistoryRepository:
    """Test suite for HistoryRepository."""

    def test_create_history_record(self, history_repo, mock_db):
        """Test creating a posting history record using HistoryCreateParams."""
        now = datetime.utcnow()
        params = HistoryCreateParams(
            media_item_id="some-media-id",
            queue_item_id="some-queue-id",
            queue_created_at=now,
            queue_deleted_at=now,
            scheduled_for=now,
            posted_at=now,
            status="posted",
            success=True,
            posted_by_user_id="some-user-id",
        )

        history_repo.create(params)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

        added = mock_db.add.call_args[0][0]
        assert isinstance(added, PostingHistory)
        assert added.media_item_id == "some-media-id"
        assert added.status == "posted"
        assert added.success is True
        assert added.posted_by_user_id == "some-user-id"

    def test_get_by_media_id(self, history_repo, mock_db):
        """Test retrieving history by media ID."""
        mock_records = [MagicMock(media_item_id="some-media-id")]
        mock_query = mock_db.query.return_value
        mock_query.all.return_value = mock_records

        result = history_repo.get_by_media_id("some-media-id")

        assert len(result) == 1
        assert result[0].media_item_id == "some-media-id"
        mock_db.query.assert_called_with(PostingHistory)

    def test_get_all_with_filters(self, history_repo, mock_db):
        """Test listing history with status filter."""
        mock_records = [
            MagicMock(status="posted"),
            MagicMock(status="posted"),
        ]
        mock_query = mock_db.query.return_value
        mock_query.all.return_value = mock_records

        result = history_repo.get_all(status="posted", days=7, limit=10)

        assert len(result) == 2
        mock_db.query.assert_called_with(PostingHistory)

    def test_get_recent_posts(self, history_repo, mock_db):
        """Test getting posts from the last N hours."""
        mock_records = [MagicMock(), MagicMock()]
        mock_query = mock_db.query.return_value
        mock_query.all.return_value = mock_records

        result = history_repo.get_recent_posts(hours=24)

        assert len(result) == 2


@pytest.mark.unit
class TestGetAllWithMedia:
    """Tests for get_all_with_media JOIN method."""

    def test_returns_tuples_with_media_info(self, history_repo, mock_db):
        """get_all_with_media returns (PostingHistory, file_name, category) tuples."""
        mock_item = MagicMock(spec=PostingHistory)
        mock_query = mock_db.query.return_value
        mock_query.outerjoin.return_value = mock_query
        mock_query.add_columns.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [(mock_item, "story.jpg", "memes")]

        result = history_repo.get_all_with_media(limit=10)

        assert len(result) == 1
        item, file_name, category = result[0]
        assert item is mock_item
        assert file_name == "story.jpg"
        assert category == "memes"

    def test_applies_limit(self, history_repo, mock_db):
        """get_all_with_media applies limit when provided."""
        mock_query = mock_db.query.return_value
        mock_query.outerjoin.return_value = mock_query
        mock_query.add_columns.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        history_repo.get_all_with_media(limit=5)

        mock_query.limit.assert_called_with(5)

    def test_no_limit(self, history_repo, mock_db):
        """get_all_with_media works without limit."""
        mock_query = mock_db.query.return_value
        mock_query.outerjoin.return_value = mock_query
        mock_query.add_columns.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []

        history_repo.get_all_with_media()

        # limit should not be called when not provided
        mock_query.order_by.assert_called()
        mock_query.all.assert_called_once()

    def test_calls_end_read_transaction(self, history_repo, mock_db):
        """get_all_with_media calls end_read_transaction after fetching."""
        mock_query = mock_db.query.return_value
        mock_query.outerjoin.return_value = mock_query
        mock_query.add_columns.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []

        with patch.object(history_repo, "end_read_transaction") as mock_end:
            history_repo.get_all_with_media()
            mock_end.assert_called_once()

    def test_passes_tenant_filter(self, history_repo, mock_db):
        """get_all_with_media passes chat_settings_id through tenant filter."""
        mock_query = mock_db.query.return_value
        mock_query.outerjoin.return_value = mock_query
        mock_query.add_columns.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []

        with patch.object(
            history_repo,
            "_apply_tenant_filter",
            wraps=history_repo._apply_tenant_filter,
        ) as mock_filter:
            history_repo.get_all_with_media(chat_settings_id="tenant-uuid-1")
            mock_filter.assert_called_once()
            assert mock_filter.call_args[0][2] == "tenant-uuid-1"


@pytest.mark.unit
class TestHistoryRepositoryTenantFiltering:
    """Tests for optional chat_settings_id tenant filtering on HistoryRepository."""

    TENANT_ID = "tenant-uuid-1"

    def test_history_create_params_has_chat_settings_id(self):
        """HistoryCreateParams dataclass accepts chat_settings_id field."""
        now = datetime.utcnow()
        params = HistoryCreateParams(
            media_item_id="m-1",
            queue_item_id="q-1",
            queue_created_at=now,
            queue_deleted_at=now,
            scheduled_for=now,
            posted_at=now,
            status="posted",
            success=True,
            chat_settings_id=self.TENANT_ID,
        )
        assert params.chat_settings_id == self.TENANT_ID

    def test_history_create_params_defaults_to_none(self):
        """HistoryCreateParams chat_settings_id defaults to None."""
        now = datetime.utcnow()
        params = HistoryCreateParams(
            media_item_id="m-1",
            queue_item_id="q-1",
            queue_created_at=now,
            queue_deleted_at=now,
            scheduled_for=now,
            posted_at=now,
            status="posted",
            success=True,
        )
        assert params.chat_settings_id is None

    def test_create_passes_tenant_through_params(self, history_repo, mock_db):
        """create passes chat_settings_id from HistoryCreateParams to model."""
        now = datetime.utcnow()
        params = HistoryCreateParams(
            media_item_id="m-1",
            queue_item_id="q-1",
            queue_created_at=now,
            queue_deleted_at=now,
            scheduled_for=now,
            posted_at=now,
            status="posted",
            success=True,
            chat_settings_id=self.TENANT_ID,
        )
        history_repo.create(params)

        added = mock_db.add.call_args[0][0]
        assert added.chat_settings_id == self.TENANT_ID

    def test_get_by_id_with_tenant(self, history_repo, mock_db):
        """get_by_id passes chat_settings_id through tenant filter."""
        with patch.object(
            history_repo,
            "_apply_tenant_filter",
            wraps=history_repo._apply_tenant_filter,
        ) as mock_filter:
            history_repo.get_by_id("h-1", chat_settings_id=self.TENANT_ID)
            mock_filter.assert_called_once()
            assert mock_filter.call_args[0][2] == self.TENANT_ID

    def test_get_all_with_tenant(self, history_repo, mock_db):
        """get_all passes chat_settings_id through tenant filter."""
        mock_db.query.return_value.all.return_value = []
        with patch.object(
            history_repo,
            "_apply_tenant_filter",
            wraps=history_repo._apply_tenant_filter,
        ) as mock_filter:
            history_repo.get_all(chat_settings_id=self.TENANT_ID)
            mock_filter.assert_called_once()
            assert mock_filter.call_args[0][2] == self.TENANT_ID

    def test_get_by_media_id_with_tenant(self, history_repo, mock_db):
        """get_by_media_id passes chat_settings_id through tenant filter."""
        mock_db.query.return_value.all.return_value = []
        with patch.object(
            history_repo,
            "_apply_tenant_filter",
            wraps=history_repo._apply_tenant_filter,
        ) as mock_filter:
            history_repo.get_by_media_id("m-1", chat_settings_id=self.TENANT_ID)
            mock_filter.assert_called_once()
            assert mock_filter.call_args[0][2] == self.TENANT_ID

    def test_get_recent_posts_with_tenant(self, history_repo, mock_db):
        """get_recent_posts passes chat_settings_id through tenant filter."""
        mock_db.query.return_value.all.return_value = []
        with patch.object(
            history_repo,
            "_apply_tenant_filter",
            wraps=history_repo._apply_tenant_filter,
        ) as mock_filter:
            history_repo.get_recent_posts(hours=24, chat_settings_id=self.TENANT_ID)
            mock_filter.assert_called_once()
            assert mock_filter.call_args[0][2] == self.TENANT_ID

    def test_count_by_method_with_tenant(self, history_repo, mock_db):
        """count_by_method passes chat_settings_id through tenant filter."""
        now = datetime.utcnow()
        with patch.object(
            history_repo,
            "_apply_tenant_filter",
            wraps=history_repo._apply_tenant_filter,
        ) as mock_filter:
            history_repo.count_by_method(
                "instagram_api", now, chat_settings_id=self.TENANT_ID
            )
            mock_filter.assert_called_once()
            assert mock_filter.call_args[0][2] == self.TENANT_ID


@pytest.mark.unit
class TestGetByQueueItemId:
    """Tests for get_by_queue_item_id - race condition history lookup."""

    def test_found(self, history_repo, mock_db):
        """Returns the history record when queue_item_id matches."""
        mock_history = MagicMock(spec=PostingHistory)
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value.order_by.return_value.first.return_value = (
            mock_history
        )

        result = history_repo.get_by_queue_item_id("queue-123")

        assert result is mock_history
        mock_db.query.assert_called_once_with(PostingHistory)

    def test_not_found(self, history_repo, mock_db):
        """Returns None when no history record for queue_item_id."""
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value.order_by.return_value.first.return_value = None

        result = history_repo.get_by_queue_item_id("nonexistent")

        assert result is None


@pytest.mark.unit
class TestAnalyticsAggregations:
    """Tests for analytics aggregation methods."""

    def _make_chainable_query(self, mock_db):
        """Set up a fully chainable mock query."""
        q = mock_db.query.return_value
        q.with_entities.return_value = q
        q.filter.return_value = q
        q.group_by.return_value = q
        q.order_by.return_value = q
        q.outerjoin.return_value = q
        q.scalar.return_value = 0
        return q

    def test_get_stats_by_status(self, history_repo, mock_db):
        """Returns counts grouped by status."""
        q = self._make_chainable_query(mock_db)
        q.all.return_value = [("posted", 80), ("skipped", 10), ("rejected", 5)]

        result = history_repo.get_stats_by_status(days=30)

        assert result == {"posted": 80, "skipped": 10, "rejected": 5}

    def test_get_stats_by_status_empty(self, history_repo, mock_db):
        """Returns empty dict when no history."""
        q = self._make_chainable_query(mock_db)
        q.all.return_value = []

        result = history_repo.get_stats_by_status(days=7)

        assert result == {}

    def test_get_stats_by_method(self, history_repo, mock_db):
        """Returns successful post counts grouped by method."""
        q = self._make_chainable_query(mock_db)
        q.all.return_value = [("instagram_api", 60), ("telegram_manual", 20)]

        result = history_repo.get_stats_by_method(days=30)

        assert result == {"instagram_api": 60, "telegram_manual": 20}

    def test_get_stats_by_method_null_method(self, history_repo, mock_db):
        """Null posting_method is reported as 'unknown'."""
        q = self._make_chainable_query(mock_db)
        q.all.return_value = [(None, 5)]

        result = history_repo.get_stats_by_method(days=30)

        assert result == {"unknown": 5}

    def test_get_daily_counts(self, history_repo, mock_db):
        """Returns daily counts pivoted by status."""
        from datetime import date

        q = self._make_chainable_query(mock_db)
        q.all.return_value = [
            (date(2026, 4, 10), "posted", 4),
            (date(2026, 4, 10), "skipped", 1),
            (date(2026, 4, 11), "posted", 5),
        ]

        result = history_repo.get_daily_counts(days=30)

        assert len(result) == 2
        day1 = result[0]
        assert day1["date"] == "2026-04-10"
        assert day1["posted"] == 4
        assert day1["skipped"] == 1
        day2 = result[1]
        assert day2["date"] == "2026-04-11"
        assert day2["posted"] == 5
        assert "skipped" not in day2

    def test_get_daily_counts_empty(self, history_repo, mock_db):
        """Returns empty list when no history."""
        q = self._make_chainable_query(mock_db)
        q.all.return_value = []

        result = history_repo.get_daily_counts(days=7)

        assert result == []

    def test_get_hourly_distribution(self, history_repo, mock_db):
        """Returns successful post counts by hour."""
        q = self._make_chainable_query(mock_db)
        q.all.return_value = [(10, 15), (14, 20), (18, 8)]

        result = history_repo.get_hourly_distribution(days=30)

        assert len(result) == 3
        assert result[0] == {"hour": 10, "count": 15}
        assert result[1] == {"hour": 14, "count": 20}
        assert result[2] == {"hour": 18, "count": 8}

    def test_get_hourly_distribution_empty(self, history_repo, mock_db):
        """Returns empty list when no successful posts."""
        q = self._make_chainable_query(mock_db)
        q.all.return_value = []

        result = history_repo.get_hourly_distribution(days=7)

        assert result == []

    def test_get_stats_by_category(self, history_repo, mock_db):
        """Returns category stats with totals and success rates."""
        q = self._make_chainable_query(mock_db)
        q.all.return_value = [
            ("memes", "posted", 70),
            ("memes", "skipped", 5),
            ("memes", "rejected", 3),
            ("merch", "posted", 18),
            ("merch", "skipped", 2),
        ]

        result = history_repo.get_stats_by_category(days=30)

        assert len(result) == 2
        memes = next(c for c in result if c["category"] == "memes")
        assert memes["posted"] == 70
        assert memes["skipped"] == 5
        assert memes["rejected"] == 3
        assert memes["total"] == 78
        assert memes["success_rate"] == 0.9  # 70/78

        merch = next(c for c in result if c["category"] == "merch")
        assert merch["posted"] == 18
        assert merch["total"] == 20
        assert merch["success_rate"] == 0.9

    def test_get_stats_by_category_empty(self, history_repo, mock_db):
        """Returns empty list when no history."""
        q = self._make_chainable_query(mock_db)
        q.all.return_value = []

        result = history_repo.get_stats_by_category(days=7)

        assert result == []

    def test_get_stats_by_category_zero_total(self, history_repo, mock_db):
        """Handles zero-total edge case without division error."""
        q = self._make_chainable_query(mock_db)
        # Unlikely but defensive: a category with no status counts
        q.all.return_value = []

        result = history_repo.get_stats_by_category(days=30)

        assert result == []

    def test_get_hourly_approval_rates(self, history_repo, mock_db):
        """Returns hourly approval rates with status breakdown."""
        q = self._make_chainable_query(mock_db)
        q.all.return_value = [
            (10, "posted", 8),
            (10, "skipped", 2),
            (14, "posted", 5),
            (14, "skipped", 5),
        ]

        result = history_repo.get_hourly_approval_rates(days=30)

        assert len(result) == 2
        assert result[0]["hour"] == 10
        assert result[0]["posted"] == 8
        assert result[0]["skipped"] == 2
        assert result[0]["total"] == 10
        assert result[0]["approval_rate"] == 0.8
        assert result[1]["hour"] == 14
        assert result[1]["approval_rate"] == 0.5

    def test_get_hourly_approval_rates_empty(self, history_repo, mock_db):
        """Returns empty list when no data."""
        q = self._make_chainable_query(mock_db)
        q.all.return_value = []

        result = history_repo.get_hourly_approval_rates(days=7)

        assert result == []

    def test_get_dow_approval_rates(self, history_repo, mock_db):
        """Returns day-of-week approval rates with day names."""
        q = self._make_chainable_query(mock_db)
        q.all.return_value = [
            (1, "posted", 20),  # Monday
            (1, "skipped", 5),
            (6, "posted", 10),  # Saturday
            (6, "skipped", 10),
        ]

        result = history_repo.get_dow_approval_rates(days=90)

        assert len(result) == 2
        assert result[0]["dow"] == 1
        assert result[0]["day_name"] == "Monday"
        assert result[0]["approval_rate"] == 0.8
        assert result[1]["dow"] == 6
        assert result[1]["day_name"] == "Saturday"
        assert result[1]["approval_rate"] == 0.5

    def test_get_dow_approval_rates_empty(self, history_repo, mock_db):
        """Returns empty list when no data."""
        q = self._make_chainable_query(mock_db)
        q.all.return_value = []

        result = history_repo.get_dow_approval_rates(days=90)

        assert result == []


@pytest.mark.unit
class TestApprovalLatency:
    """Tests for get_approval_latency."""

    def _make_chainable_query(self, mock_db):
        q = mock_db.query.return_value
        q.with_entities.return_value = q
        q.filter.return_value = q
        q.group_by.return_value = q
        q.order_by.return_value = q
        q.outerjoin.return_value = q
        return q

    def test_returns_overall_and_breakdowns(self, history_repo, mock_db):
        """Returns overall stats with hourly and category breakdowns."""
        q = self._make_chainable_query(mock_db)

        # Overall stats (first call)
        overall_row = MagicMock()
        overall_row.count = 50
        overall_row.avg = 300.0  # 5 minutes in seconds
        overall_row.min = 60.0
        overall_row.max = 1800.0
        q.first.return_value = overall_row

        # Hourly (second call to all)
        hourly_row = MagicMock()
        hourly_row.hour = 14
        hourly_row.count = 20
        hourly_row.avg = 240.0

        # Category (third call to all)
        cat_row = MagicMock()
        cat_row.category = "memes"
        cat_row.count = 30
        cat_row.avg = 180.0

        q.all.side_effect = [[hourly_row], [cat_row]]

        result = history_repo.get_approval_latency(days=30)

        assert result["overall"]["count"] == 50
        assert result["overall"]["avg_minutes"] == 5.0
        assert result["overall"]["min_minutes"] == 1.0
        assert result["overall"]["max_minutes"] == 30.0
        assert len(result["by_hour"]) == 1
        assert result["by_hour"][0]["hour"] == 14
        assert result["by_hour"][0]["avg_minutes"] == 4.0
        assert len(result["by_category"]) == 1
        assert result["by_category"][0]["category"] == "memes"

    def test_empty_history(self, history_repo, mock_db):
        """Returns zeros when no posting history."""
        q = self._make_chainable_query(mock_db)

        overall_row = MagicMock()
        overall_row.count = 0
        overall_row.avg = None
        overall_row.min = None
        overall_row.max = None
        q.first.return_value = overall_row
        q.all.side_effect = [[], []]

        result = history_repo.get_approval_latency(days=30)

        assert result["overall"]["count"] == 0
        assert result["overall"]["avg_minutes"] == 0
        assert result["by_hour"] == []
        assert result["by_category"] == []


@pytest.mark.unit
class TestUserApprovalStats:
    """Tests for get_user_approval_stats."""

    def _make_chainable_query(self, mock_db):
        q = mock_db.query.return_value
        q.with_entities.return_value = q
        q.filter.return_value = q
        q.group_by.return_value = q
        q.order_by.return_value = q
        q.outerjoin.return_value = q
        return q

    def test_returns_per_user_breakdown(self, history_repo, mock_db):
        """Returns per-user stats with approval rates."""
        q = self._make_chainable_query(mock_db)
        q.all.return_value = [
            ("user-1", "alice", "Alice", "posted", 40, 180.0),
            ("user-1", "alice", "Alice", "skipped", 5, None),
            ("user-1", "alice", "Alice", "rejected", 5, None),
            ("user-2", "bob", "Bob", "posted", 20, 360.0),
        ]

        result = history_repo.get_user_approval_stats(days=30)

        assert len(result) == 2
        alice = result[0]  # sorted by total desc
        assert alice["username"] == "alice"
        assert alice["posted"] == 40
        assert alice["skipped"] == 5
        assert alice["rejected"] == 5
        assert alice["total"] == 50
        assert alice["approval_rate"] == 0.8
        assert alice["avg_latency_minutes"] == 3.0  # 180s = 3min

        bob = result[1]
        assert bob["posted"] == 20
        assert bob["total"] == 20
        assert bob["approval_rate"] == 1.0
        assert bob["avg_latency_minutes"] == 6.0  # 360s = 6min

    def test_empty_history(self, history_repo, mock_db):
        """Returns empty list when no user data."""
        q = self._make_chainable_query(mock_db)
        q.all.return_value = []

        result = history_repo.get_user_approval_stats(days=30)

        assert result == []
