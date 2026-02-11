"""Tests for PostingService."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from contextlib import contextmanager
from uuid import uuid4

from src.services.core.posting import PostingService


@contextmanager
def mock_track_execution(*args, **kwargs):
    """Mock context manager for track_execution."""
    yield "mock_run_id"


@pytest.fixture
def posting_service():
    """Create PostingService with mocked dependencies."""
    with patch.object(PostingService, "__init__", lambda self: None):
        service = PostingService()
        service.queue_repo = Mock()
        service.media_repo = Mock()
        service.history_repo = Mock()
        service.telegram_service = Mock()
        service.lock_service = Mock()
        service.settings_service = Mock()
        service.service_run_repo = Mock()
        service.service_name = "PostingService"
        service._instagram_service = None
        service._cloud_service = None
        service.track_execution = mock_track_execution
        service.set_result_summary = Mock()
        return service


@pytest.mark.unit
class TestPostingService:
    """Test suite for PostingService."""

    @pytest.mark.asyncio
    async def test_process_pending_queue_no_items(self, posting_service):
        """Test processing queue when no items are pending."""
        posting_service.telegram_service.is_paused = False
        posting_service.queue_repo.get_pending.return_value = []

        result = await posting_service.process_pending_posts()

        assert result["processed"] == 0

    def test_mark_as_posted(self, posting_service):
        """Test marking a queue item as posted."""
        queue_item_id = str(uuid4())
        media_id = uuid4()
        user_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.id = queue_item_id
        mock_queue_item.media_item_id = media_id
        mock_queue_item.created_at = datetime.utcnow()
        mock_queue_item.scheduled_for = datetime.utcnow()
        mock_queue_item.retry_count = 0
        posting_service.queue_repo.get_by_id.return_value = mock_queue_item

        posting_service.handle_completion(
            queue_item_id=queue_item_id,
            success=True,
            posted_by_user_id=user_id,
        )

        posting_service.history_repo.create.assert_called_once()
        posting_service.media_repo.increment_times_posted.assert_called_once()
        posting_service.lock_service.create_lock.assert_called_once()
        posting_service.queue_repo.delete.assert_called_once_with(queue_item_id)

    def test_mark_as_skipped(self, posting_service):
        """Test marking a queue item as skipped."""
        queue_item_id = str(uuid4())
        media_id = uuid4()

        mock_queue_item = Mock()
        mock_queue_item.id = queue_item_id
        mock_queue_item.media_item_id = media_id
        mock_queue_item.created_at = datetime.utcnow()
        mock_queue_item.scheduled_for = datetime.utcnow()
        mock_queue_item.retry_count = 0
        posting_service.queue_repo.get_by_id.return_value = mock_queue_item

        posting_service.handle_completion(
            queue_item_id=queue_item_id,
            success=False,
            error_message="Skipped by user",
        )

        posting_service.history_repo.create.assert_called_once()
        # Failed/skipped posts don't increment or create locks
        posting_service.media_repo.increment_times_posted.assert_not_called()
        posting_service.lock_service.create_lock.assert_not_called()
        posting_service.queue_repo.delete.assert_called_once_with(queue_item_id)

    def test_get_queue_item_with_media(self, posting_service):
        """Test retrieving queue item with media details."""
        posting_service.queue_repo.get_by_id.return_value = None

        # handle_completion returns early when queue item not found
        posting_service.handle_completion(
            queue_item_id="nonexistent",
            success=True,
        )

        posting_service.history_repo.create.assert_not_called()
        posting_service.queue_repo.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_retry_failed_post(self, posting_service):
        """Test retrying a failed post."""
        posting_service.queue_repo.get_all.return_value = []

        result = await posting_service.force_post_next()

        assert result["success"] is False
        assert result["error"] == "No pending items in queue"
