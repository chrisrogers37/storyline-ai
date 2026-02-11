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
            media_metadata={"file_name": "history.jpg"},
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

    def test_get_by_user_id(self, history_repo, mock_db):
        """Test retrieving history by user ID."""
        mock_records = [MagicMock(posted_by_user_id="some-user-id")]
        mock_query = mock_db.query.return_value
        mock_query.all.return_value = mock_records

        result = history_repo.get_by_user_id("some-user-id")

        assert len(result) == 1
        assert result[0].posted_by_user_id == "some-user-id"

    def test_get_stats(self, history_repo, mock_db):
        """Test getting posting statistics."""
        # get_stats makes 3 separate scalar queries
        mock_db.query.return_value.filter.return_value.scalar.side_effect = [10, 8, 2]

        stats = history_repo.get_stats(days=30)

        assert stats["total"] == 10
        assert stats["successful"] == 8
        assert stats["failed"] == 2
        assert stats["success_rate"] == 80.0

    def test_get_stats_empty(self, history_repo, mock_db):
        """Test stats with no posts returns zeros."""
        mock_db.query.return_value.filter.return_value.scalar.side_effect = [0, 0, 0]

        stats = history_repo.get_stats(days=30)

        assert stats["total"] == 0
        assert stats["successful"] == 0
        assert stats["failed"] == 0
        assert stats["success_rate"] == 0

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
