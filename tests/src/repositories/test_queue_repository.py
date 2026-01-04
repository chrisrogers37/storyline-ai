"""Tests for QueueRepository."""
import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from src.repositories.queue_repository import QueueRepository
from src.repositories.media_repository import MediaRepository
from src.repositories.user_repository import UserRepository


@pytest.mark.unit
class TestQueueRepository:
    """Test suite for QueueRepository."""

    def test_create_queue_item(self, test_db):
        """Test creating a new queue item."""
        media_repo = MediaRepository(test_db)
        user_repo = UserRepository(test_db)
        queue_repo = QueueRepository(test_db)

        # Create dependencies
        media = media_repo.create(
            file_path="/test/queue.jpg",
            file_name="queue.jpg",
            file_hash="queue123",
            file_size_bytes=100000,
            mime_type="image/jpeg"
        )

        user = user_repo.create(telegram_user_id=300001)

        # Create queue item
        scheduled_time = datetime.utcnow() + timedelta(hours=1)
        queue_item = queue_repo.create(
            media_id=media.id,
            scheduled_user_id=user.id,
            scheduled_time=scheduled_time
        )

        assert queue_item.id is not None
        assert queue_item.media_id == media.id
        assert queue_item.scheduled_user_id == user.id
        assert queue_item.status == "pending"
        assert queue_item.retry_count == 0

    def test_get_pending_items(self, test_db):
        """Test retrieving pending queue items."""
        media_repo = MediaRepository(test_db)
        user_repo = UserRepository(test_db)
        queue_repo = QueueRepository(test_db)

        media = media_repo.create(
            file_path="/test/pending.jpg",
            file_name="pending.jpg",
            file_hash="pending123",
            file_size_bytes=90000,
            mime_type="image/jpeg"
        )

        user = user_repo.create(telegram_user_id=300002)

        # Create pending item (scheduled in past)
        queue_repo.create(
            media_id=media.id,
            scheduled_user_id=user.id,
            scheduled_time=datetime.utcnow() - timedelta(minutes=5)
        )

        pending_items = queue_repo.get_pending()

        assert len(pending_items) >= 1

    def test_update_status(self, test_db):
        """Test updating queue item status."""
        media_repo = MediaRepository(test_db)
        user_repo = UserRepository(test_db)
        queue_repo = QueueRepository(test_db)

        media = media_repo.create(
            file_path="/test/status.jpg",
            file_name="status.jpg",
            file_hash="status123",
            file_size_bytes=85000,
            mime_type="image/jpeg"
        )

        user = user_repo.create(telegram_user_id=300003)

        queue_item = queue_repo.create(
            media_id=media.id,
            scheduled_user_id=user.id,
            scheduled_time=datetime.utcnow()
        )

        assert queue_item.status == "pending"

        # Update status
        updated_item = queue_repo.update_status(
            queue_item.id,
            "posted",
            telegram_message_id=12345
        )

        assert updated_item.status == "posted"
        assert updated_item.telegram_message_id == 12345

    def test_schedule_retry(self, test_db):
        """Test scheduling a retry for failed queue item."""
        media_repo = MediaRepository(test_db)
        user_repo = UserRepository(test_db)
        queue_repo = QueueRepository(test_db)

        media = media_repo.create(
            file_path="/test/retry.jpg",
            file_name="retry.jpg",
            file_hash="retry123",
            file_size_bytes=95000,
            mime_type="image/jpeg"
        )

        user = user_repo.create(telegram_user_id=300004)

        queue_item = queue_repo.create(
            media_id=media.id,
            scheduled_user_id=user.id,
            scheduled_time=datetime.utcnow()
        )

        # Mark as failed
        queue_repo.update_status(queue_item.id, "failed", error_message="Test error")

        # Schedule retry
        retried_item = queue_repo.schedule_retry(queue_item.id, retry_minutes=10)

        assert retried_item.status == "pending"
        assert retried_item.retry_count == 1
        assert retried_item.scheduled_time > datetime.utcnow()

    def test_delete_queue_item(self, test_db):
        """Test deleting a queue item."""
        media_repo = MediaRepository(test_db)
        user_repo = UserRepository(test_db)
        queue_repo = QueueRepository(test_db)

        media = media_repo.create(
            file_path="/test/delete.jpg",
            file_name="delete.jpg",
            file_hash="delete123",
            file_size_bytes=70000,
            mime_type="image/jpeg"
        )

        user = user_repo.create(telegram_user_id=300005)

        queue_item = queue_repo.create(
            media_id=media.id,
            scheduled_user_id=user.id,
            scheduled_time=datetime.utcnow()
        )

        item_id = queue_item.id

        # Delete
        queue_repo.delete(item_id)

        # Verify deleted
        deleted_item = queue_repo.get_by_id(item_id)
        assert deleted_item is None

    def test_list_all_queue_items(self, test_db):
        """Test listing all queue items."""
        media_repo = MediaRepository(test_db)
        user_repo = UserRepository(test_db)
        queue_repo = QueueRepository(test_db)

        media = media_repo.create(
            file_path="/test/list.jpg",
            file_name="list.jpg",
            file_hash="list123",
            file_size_bytes=60000,
            mime_type="image/jpeg"
        )

        user = user_repo.create(telegram_user_id=300006)

        # Create multiple items
        queue_repo.create(
            media_id=media.id,
            scheduled_user_id=user.id,
            scheduled_time=datetime.utcnow()
        )

        all_items = queue_repo.list_all(limit=10)

        assert len(all_items) >= 1

    def test_get_by_media_id(self, test_db):
        """Test retrieving queue items by media ID."""
        media_repo = MediaRepository(test_db)
        user_repo = UserRepository(test_db)
        queue_repo = QueueRepository(test_db)

        media = media_repo.create(
            file_path="/test/by_media.jpg",
            file_name="by_media.jpg",
            file_hash="by_media123",
            file_size_bytes=65000,
            mime_type="image/jpeg"
        )

        user = user_repo.create(telegram_user_id=300007)

        queue_item = queue_repo.create(
            media_id=media.id,
            scheduled_user_id=user.id,
            scheduled_time=datetime.utcnow()
        )

        items = queue_repo.get_by_media_id(media.id)

        assert len(items) >= 1
        assert items[0].media_id == media.id
