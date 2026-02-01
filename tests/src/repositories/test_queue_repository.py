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

    @pytest.mark.skip(
        reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/"
    )
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
            mime_type="image/jpeg",
        )

        user = user_repo.create(telegram_user_id=300001)

        # Create queue item
        scheduled_time = datetime.utcnow() + timedelta(hours=1)
        queue_item = queue_repo.create(
            media_id=media.id, scheduled_user_id=user.id, scheduled_time=scheduled_time
        )

        assert queue_item.id is not None
        assert queue_item.media_id == media.id
        assert queue_item.scheduled_user_id == user.id
        assert queue_item.status == "pending"
        assert queue_item.retry_count == 0

    @pytest.mark.skip(
        reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/"
    )
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
            mime_type="image/jpeg",
        )

        user = user_repo.create(telegram_user_id=300002)

        # Create pending item (scheduled in past)
        queue_repo.create(
            media_id=media.id,
            scheduled_user_id=user.id,
            scheduled_time=datetime.utcnow() - timedelta(minutes=5),
        )

        pending_items = queue_repo.get_pending()

        assert len(pending_items) >= 1

    @pytest.mark.skip(
        reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/"
    )
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
            mime_type="image/jpeg",
        )

        user = user_repo.create(telegram_user_id=300003)

        queue_item = queue_repo.create(
            media_id=media.id,
            scheduled_user_id=user.id,
            scheduled_time=datetime.utcnow(),
        )

        assert queue_item.status == "pending"

        # Update status
        updated_item = queue_repo.update_status(
            queue_item.id, "posted", telegram_message_id=12345
        )

        assert updated_item.status == "posted"
        assert updated_item.telegram_message_id == 12345

    @pytest.mark.skip(
        reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/"
    )
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
            mime_type="image/jpeg",
        )

        user = user_repo.create(telegram_user_id=300004)

        queue_item = queue_repo.create(
            media_id=media.id,
            scheduled_user_id=user.id,
            scheduled_time=datetime.utcnow(),
        )

        # Mark as failed
        queue_repo.update_status(queue_item.id, "failed", error_message="Test error")

        # Schedule retry
        retried_item = queue_repo.schedule_retry(queue_item.id, retry_minutes=10)

        assert retried_item.status == "pending"
        assert retried_item.retry_count == 1
        assert retried_item.scheduled_time > datetime.utcnow()

    @pytest.mark.skip(
        reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/"
    )
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
            mime_type="image/jpeg",
        )

        user = user_repo.create(telegram_user_id=300005)

        queue_item = queue_repo.create(
            media_id=media.id,
            scheduled_user_id=user.id,
            scheduled_time=datetime.utcnow(),
        )

        item_id = queue_item.id

        # Delete
        queue_repo.delete(item_id)

        # Verify deleted
        deleted_item = queue_repo.get_by_id(item_id)
        assert deleted_item is None

    @pytest.mark.skip(
        reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/"
    )
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
            mime_type="image/jpeg",
        )

        user = user_repo.create(telegram_user_id=300006)

        # Create multiple items
        queue_repo.create(
            media_id=media.id,
            scheduled_user_id=user.id,
            scheduled_time=datetime.utcnow(),
        )

        all_items = queue_repo.list_all(limit=10)

        assert len(all_items) >= 1

    @pytest.mark.skip(
        reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/"
    )
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
            mime_type="image/jpeg",
        )

        user = user_repo.create(telegram_user_id=300007)

        queue_repo.create(
            media_id=media.id,
            scheduled_user_id=user.id,
            scheduled_time=datetime.utcnow(),
        )

        items = queue_repo.get_by_media_id(media.id)

        assert len(items) >= 1
        assert items[0].media_id == media.id


@pytest.mark.unit
class TestShiftSlotsForward:
    """Test suite for QueueRepository.shift_slots_forward()."""

    @pytest.mark.skip(
        reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/"
    )
    def test_shift_slots_forward_basic(self, test_db):
        """Test basic slot shifting - each item inherits the previous slot."""
        from src.models.posting_queue import PostingQueue
        from src.models.media_item import MediaItem

        # Create 4 media items
        media_items = []
        for i in range(4):
            media = MediaItem(
                file_path=f"/test/shift_{i}.jpg",
                file_name=f"shift_{i}.jpg",
                file_hash=f"shifttest{i}_{uuid4().hex[:8]}",
                file_size_bytes=10000,
                mime_type="image/jpeg",
            )
            test_db.add(media)
            test_db.commit()
            test_db.refresh(media)
            media_items.append(media)

        # Create queue items with specific times
        base_time = datetime(2026, 1, 15, 10, 0, 0)
        times = [
            base_time,  # A: 10:00
            base_time + timedelta(hours=4),  # B: 14:00
            base_time + timedelta(hours=8),  # C: 18:00
            base_time + timedelta(hours=12),  # D: 22:00
        ]

        queue_items = []
        for i, (media, sched_time) in enumerate(zip(media_items, times)):
            item = PostingQueue(
                media_item_id=media.id,
                scheduled_for=sched_time,
                status="pending",
            )
            test_db.add(item)
            test_db.commit()
            test_db.refresh(item)
            queue_items.append(item)

        queue_repo = QueueRepository()
        queue_repo.db = test_db

        # Shift from item A (first item)
        shifted = queue_repo.shift_slots_forward(str(queue_items[0].id))

        # Should shift 3 items (B, C, D)
        assert shifted == 3

        # Refresh items to get updated values
        for item in queue_items:
            test_db.refresh(item)

        # Verify times:
        # A: unchanged (10:00) - it's the force-posted item
        # B: should now be 10:00 (A's original time)
        # C: should now be 14:00 (B's original time)
        # D: should now be 18:00 (C's original time)
        # D's original 22:00 is discarded
        assert queue_items[0].scheduled_for == times[0]  # A unchanged
        assert queue_items[1].scheduled_for == times[0]  # B got A's time
        assert queue_items[2].scheduled_for == times[1]  # C got B's time
        assert queue_items[3].scheduled_for == times[2]  # D got C's time

    @pytest.mark.skip(
        reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/"
    )
    def test_shift_slots_forward_last_item(self, test_db):
        """Test shifting when force-posting the last item - no shift needed."""
        from src.models.posting_queue import PostingQueue
        from src.models.media_item import MediaItem

        # Create 2 media items
        media_a = MediaItem(
            file_path="/test/last_a.jpg",
            file_name="last_a.jpg",
            file_hash=f"lasttest_a_{uuid4().hex[:8]}",
            file_size_bytes=10000,
            mime_type="image/jpeg",
        )
        test_db.add(media_a)
        test_db.commit()
        test_db.refresh(media_a)

        media_b = MediaItem(
            file_path="/test/last_b.jpg",
            file_name="last_b.jpg",
            file_hash=f"lasttest_b_{uuid4().hex[:8]}",
            file_size_bytes=10000,
            mime_type="image/jpeg",
        )
        test_db.add(media_b)
        test_db.commit()
        test_db.refresh(media_b)

        # Create queue items
        base_time = datetime(2026, 1, 15, 10, 0, 0)
        item_a = PostingQueue(
            media_item_id=media_a.id,
            scheduled_for=base_time,
            status="pending",
        )
        test_db.add(item_a)
        test_db.commit()
        test_db.refresh(item_a)

        item_b = PostingQueue(
            media_item_id=media_b.id,
            scheduled_for=base_time + timedelta(hours=4),
            status="pending",
        )
        test_db.add(item_b)
        test_db.commit()
        test_db.refresh(item_b)

        queue_repo = QueueRepository()
        queue_repo.db = test_db

        # Shift from item B (last item) - nothing to shift
        shifted = queue_repo.shift_slots_forward(str(item_b.id))

        assert shifted == 0

    @pytest.mark.skip(
        reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/"
    )
    def test_shift_slots_forward_empty_queue(self, test_db):
        """Test shifting with empty queue."""
        queue_repo = QueueRepository()
        queue_repo.db = test_db

        # Use a random UUID that doesn't exist
        shifted = queue_repo.shift_slots_forward(str(uuid4()))

        assert shifted == 0

    @pytest.mark.skip(
        reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/"
    )
    def test_shift_slots_forward_single_item(self, test_db):
        """Test shifting when only one item in queue."""
        from src.models.posting_queue import PostingQueue
        from src.models.media_item import MediaItem

        media = MediaItem(
            file_path="/test/single.jpg",
            file_name="single.jpg",
            file_hash=f"singletest_{uuid4().hex[:8]}",
            file_size_bytes=10000,
            mime_type="image/jpeg",
        )
        test_db.add(media)
        test_db.commit()
        test_db.refresh(media)

        item = PostingQueue(
            media_item_id=media.id,
            scheduled_for=datetime(2026, 1, 15, 10, 0, 0),
            status="pending",
        )
        test_db.add(item)
        test_db.commit()
        test_db.refresh(item)

        queue_repo = QueueRepository()
        queue_repo.db = test_db

        # Shift from single item - nothing behind it
        shifted = queue_repo.shift_slots_forward(str(item.id))

        assert shifted == 0

    @pytest.mark.skip(
        reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/"
    )
    def test_shift_slots_forward_multiple_calls(self, test_db):
        """Test multiple consecutive shifts (simulating multiple /next calls)."""
        from src.models.posting_queue import PostingQueue
        from src.models.media_item import MediaItem

        # Create 5 media items
        media_items = []
        for i in range(5):
            media = MediaItem(
                file_path=f"/test/multi_{i}.jpg",
                file_name=f"multi_{i}.jpg",
                file_hash=f"multitest{i}_{uuid4().hex[:8]}",
                file_size_bytes=10000,
                mime_type="image/jpeg",
            )
            test_db.add(media)
            test_db.commit()
            test_db.refresh(media)
            media_items.append(media)

        # Create queue items: 10:00, 14:00, 18:00, 22:00, 02:00(next day)
        base_time = datetime(2026, 1, 15, 10, 0, 0)
        original_times = [
            base_time,
            base_time + timedelta(hours=4),
            base_time + timedelta(hours=8),
            base_time + timedelta(hours=12),
            base_time + timedelta(hours=16),
        ]

        queue_items = []
        for media, sched_time in zip(media_items, original_times):
            item = PostingQueue(
                media_item_id=media.id,
                scheduled_for=sched_time,
                status="pending",
            )
            test_db.add(item)
            test_db.commit()
            test_db.refresh(item)
            queue_items.append(item)

        queue_repo = QueueRepository()
        queue_repo.db = test_db

        # First /next call - shift from item 0
        shifted1 = queue_repo.shift_slots_forward(str(queue_items[0].id))
        assert shifted1 == 4

        # Refresh items
        for item in queue_items:
            test_db.refresh(item)

        # After first shift:
        # 0: 10:00 (unchanged, force-posted)
        # 1: 10:00 (was 14:00)
        # 2: 14:00 (was 18:00)
        # 3: 18:00 (was 22:00)
        # 4: 22:00 (was 02:00, original last slot discarded)

        # Second /next call - shift from item 1 (now first pending after 0 is removed)
        # Simulating that item 0 has been removed from queue
        queue_items[0].status = "processing"  # Mark as processing (not pending)
        test_db.commit()

        shifted2 = queue_repo.shift_slots_forward(str(queue_items[1].id))
        assert shifted2 == 3  # Items 2, 3, 4

        # Refresh again
        for item in queue_items:
            test_db.refresh(item)

        # After second shift:
        # 1: 10:00 (unchanged, force-posted)
        # 2: 10:00 (was 14:00)
        # 3: 14:00 (was 18:00)
        # 4: 18:00 (was 22:00, 22:00 discarded)
        assert queue_items[2].scheduled_for == original_times[0]  # 10:00
        assert queue_items[3].scheduled_for == original_times[1]  # 14:00
        assert queue_items[4].scheduled_for == original_times[2]  # 18:00
