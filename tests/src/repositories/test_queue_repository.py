"""Tests for QueueRepository."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from src.repositories.queue_repository import QueueRepository
from src.models.posting_queue import PostingQueue


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
def queue_repo(mock_db):
    """Create QueueRepository with mocked database session."""
    with patch.object(QueueRepository, "__init__", lambda self: None):
        repo = QueueRepository()
        repo._db = mock_db
        return repo


@pytest.mark.unit
class TestQueueRepository:
    """Test suite for QueueRepository."""

    def test_create_queue_item(self, queue_repo, mock_db):
        """Test creating a new queue item."""
        scheduled_time = datetime.utcnow() + timedelta(hours=1)
        media_item_id = str(uuid4())

        queue_repo.create(
            media_item_id=media_item_id,
            scheduled_for=scheduled_time,
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

        added_item = mock_db.add.call_args[0][0]
        assert isinstance(added_item, PostingQueue)
        assert added_item.media_item_id == media_item_id
        assert added_item.scheduled_for == scheduled_time

    def test_get_pending_items(self, queue_repo, mock_db):
        """Test retrieving pending queue items."""
        mock_items = [MagicMock(status="pending"), MagicMock(status="pending")]
        mock_query = mock_db.query.return_value
        mock_query.all.return_value = mock_items

        result = queue_repo.get_pending()

        assert len(result) == 2
        mock_db.query.assert_called_with(PostingQueue)

    def test_update_status(self, queue_repo, mock_db):
        """Test updating queue item status."""
        mock_item = MagicMock()
        mock_item.status = "pending"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_item

        queue_repo.update_status("some-id", "posted")

        assert mock_item.status == "posted"
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(mock_item)

    def test_update_status_not_found(self, queue_repo, mock_db):
        """Test updating status of non-existent queue item."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = queue_repo.update_status("nonexistent-id", "posted")

        assert result is None
        mock_db.commit.assert_not_called()

    def test_schedule_retry(self, queue_repo, mock_db):
        """Test scheduling a retry for failed queue item."""
        mock_item = MagicMock()
        mock_item.retry_count = 0
        mock_item.max_retries = 3
        mock_db.query.return_value.filter.return_value.first.return_value = mock_item

        queue_repo.schedule_retry(
            "some-id", error_message="Test error", retry_delay_minutes=10
        )

        assert mock_item.retry_count == 1
        assert mock_item.status == "retrying"
        assert mock_item.last_error == "Test error"
        assert mock_item.next_retry_at is not None
        mock_db.commit.assert_called_once()

    def test_schedule_retry_max_retries_exceeded(self, queue_repo, mock_db):
        """Test that exceeding max retries marks item as failed."""
        mock_item = MagicMock()
        mock_item.retry_count = 2
        mock_item.max_retries = 3
        mock_db.query.return_value.filter.return_value.first.return_value = mock_item

        queue_repo.schedule_retry("some-id", error_message="Final failure")

        assert mock_item.retry_count == 3
        assert mock_item.status == "failed"

    def test_delete_queue_item(self, queue_repo, mock_db):
        """Test deleting a queue item."""
        mock_item = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_item

        result = queue_repo.delete("some-id")

        assert result is True
        mock_db.delete.assert_called_once_with(mock_item)
        mock_db.commit.assert_called_once()

    def test_delete_queue_item_not_found(self, queue_repo, mock_db):
        """Test deleting a non-existent queue item."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = queue_repo.delete("nonexistent-id")

        assert result is False
        mock_db.delete.assert_not_called()

    def test_get_all_queue_items(self, queue_repo, mock_db):
        """Test listing all queue items."""
        mock_items = [MagicMock(), MagicMock()]
        mock_query = mock_db.query.return_value
        mock_query.all.return_value = mock_items

        result = queue_repo.get_all()

        assert len(result) == 2
        mock_db.query.assert_called_with(PostingQueue)

    def test_get_by_media_id(self, queue_repo, mock_db):
        """Test retrieving queue item by media ID."""
        media_id = str(uuid4())
        mock_item = MagicMock(media_item_id=media_id)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_item

        result = queue_repo.get_by_media_id(media_id)

        assert result is mock_item
        assert result.media_item_id == media_id

    def test_count_pending(self, queue_repo, mock_db):
        """Test counting pending items."""
        mock_db.query.return_value.filter.return_value.count.return_value = 5

        result = queue_repo.count_pending()

        assert result == 5


@pytest.mark.unit
class TestShiftSlotsForward:
    """Tests for QueueRepository.shift_slots_forward().

    This method involves complex in-place updates across multiple queue items.
    Full testing requires integration tests with a real database.
    """

    @pytest.mark.skip(
        reason="Integration test - needs real DB for multi-row time slot shifting"
    )
    def test_shift_slots_forward_basic(self):
        """Integration test: basic slot shifting."""
        pass

    @pytest.mark.skip(
        reason="Integration test - needs real DB for multi-row time slot shifting"
    )
    def test_shift_slots_forward_last_item(self):
        """Integration test: shifting when force-posting the last item."""
        pass

    @pytest.mark.skip(
        reason="Integration test - needs real DB for multi-row time slot shifting"
    )
    def test_shift_slots_forward_empty_queue(self):
        """Integration test: shifting with empty queue."""
        pass

    @pytest.mark.skip(
        reason="Integration test - needs real DB for multi-row time slot shifting"
    )
    def test_shift_slots_forward_single_item(self):
        """Integration test: shifting when only one item in queue."""
        pass

    @pytest.mark.skip(
        reason="Integration test - needs real DB for multi-row time slot shifting"
    )
    def test_shift_slots_forward_multiple_calls(self):
        """Integration test: multiple consecutive shifts."""
        pass
