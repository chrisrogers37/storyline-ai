"""Tests for PostingService."""

import pytest
from datetime import datetime

from src.services.core.posting import PostingService
from src.repositories.media_repository import MediaRepository
from src.repositories.user_repository import UserRepository
from src.repositories.queue_repository import QueueRepository
from src.repositories.history_repository import HistoryRepository


@pytest.mark.unit
class TestPostingService:
    """Test suite for PostingService."""

    def test_process_pending_queue_no_items(self, test_db):
        """Test processing queue when no items are pending."""
        service = PostingService(db=test_db)

        result = service.process_pending_queue()

        assert result["processed"] == 0

    def test_mark_as_posted(self, test_db):
        """Test marking a queue item as posted."""
        media_repo = MediaRepository(test_db)
        user_repo = UserRepository(test_db)
        queue_repo = QueueRepository(test_db)
        history_repo = HistoryRepository(test_db)

        # Create test data
        media = media_repo.create(
            file_path="/test/posted.jpg",
            file_name="posted.jpg",
            file_hash="posted890",
            file_size_bytes=100000,
            mime_type="image/jpeg",
        )

        user = user_repo.create(telegram_user_id=700001)

        queue_item = queue_repo.create(
            media_id=media.id,
            scheduled_user_id=user.id,
            scheduled_time=datetime.utcnow(),
        )

        service = PostingService(db=test_db)

        # Mark as posted
        result = service.mark_as_posted(
            queue_id=queue_item.id, posted_by_user_id=user.id
        )

        assert result["status"] == "posted"

        # Verify queue status updated
        updated_queue = queue_repo.get_by_id(queue_item.id)
        assert updated_queue.status == "posted"

        # Verify history created
        history_records = history_repo.get_by_media_id(media.id)
        assert len(history_records) >= 1

        # Verify media post count incremented
        updated_media = media_repo.get_by_id(media.id)
        assert updated_media.times_posted == 1

    def test_mark_as_skipped(self, test_db):
        """Test marking a queue item as skipped."""
        media_repo = MediaRepository(test_db)
        user_repo = UserRepository(test_db)
        queue_repo = QueueRepository(test_db)
        history_repo = HistoryRepository(test_db)

        # Create test data
        media = media_repo.create(
            file_path="/test/skipped.jpg",
            file_name="skipped.jpg",
            file_hash="skipped890",
            file_size_bytes=95000,
            mime_type="image/jpeg",
        )

        user = user_repo.create(telegram_user_id=700002)

        queue_item = queue_repo.create(
            media_id=media.id,
            scheduled_user_id=user.id,
            scheduled_time=datetime.utcnow(),
        )

        service = PostingService(db=test_db)

        # Mark as skipped
        result = service.mark_as_skipped(
            queue_id=queue_item.id,
            skipped_by_user_id=user.id,
            reason="Not relevant today",
        )

        assert result["status"] == "skipped"

        # Verify queue status updated
        updated_queue = queue_repo.get_by_id(queue_item.id)
        assert updated_queue.status == "skipped"

        # Verify history created with skipped status
        history_records = history_repo.get_by_media_id(media.id)
        assert len(history_records) >= 1
        assert history_records[0].status == "skipped"

        # Verify media post count NOT incremented
        updated_media = media_repo.get_by_id(media.id)
        assert updated_media.times_posted == 0

    def test_get_queue_item_with_media(self, test_db):
        """Test retrieving queue item with media details."""
        media_repo = MediaRepository(test_db)
        user_repo = UserRepository(test_db)
        queue_repo = QueueRepository(test_db)

        media = media_repo.create(
            file_path="/test/details.jpg",
            file_name="details.jpg",
            file_hash="details890",
            file_size_bytes=90000,
            mime_type="image/jpeg",
        )

        user = user_repo.create(telegram_user_id=700003)

        queue_item = queue_repo.create(
            media_id=media.id,
            scheduled_user_id=user.id,
            scheduled_time=datetime.utcnow(),
        )

        service = PostingService(db=test_db)

        result = service.get_queue_item_with_media(queue_item.id)

        assert result is not None
        assert result["queue_item"].id == queue_item.id
        assert result["media"].id == media.id

    def test_retry_failed_post(self, test_db):
        """Test retrying a failed post."""
        media_repo = MediaRepository(test_db)
        user_repo = UserRepository(test_db)
        queue_repo = QueueRepository(test_db)

        media = media_repo.create(
            file_path="/test/retry.jpg",
            file_name="retry.jpg",
            file_hash="retry890",
            file_size_bytes=85000,
            mime_type="image/jpeg",
        )

        user = user_repo.create(telegram_user_id=700004)

        queue_item = queue_repo.create(
            media_id=media.id,
            scheduled_user_id=user.id,
            scheduled_time=datetime.utcnow(),
        )

        # Mark as failed
        queue_repo.update_status(queue_item.id, "failed", error_message="Test error")

        service = PostingService(db=test_db)

        # Retry
        result = service.retry_failed_post(queue_item.id, retry_minutes=30)

        assert result["status"] == "pending"
        assert result["retry_count"] >= 1
