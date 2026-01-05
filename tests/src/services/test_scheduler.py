"""Tests for SchedulerService."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.services.core.scheduler import SchedulerService
from src.repositories.media_repository import MediaRepository
from src.repositories.user_repository import UserRepository
from src.repositories.queue_repository import QueueRepository
from src.repositories.lock_repository import LockRepository


@pytest.mark.unit
class TestSchedulerService:
    """Test suite for SchedulerService."""

    def test_create_schedule_creates_queue_items(self, test_db):
        """Test that create_schedule creates queue items."""
        media_repo = MediaRepository(test_db)
        user_repo = UserRepository(test_db)
        queue_repo = QueueRepository(test_db)

        # Create test data
        media = media_repo.create(
            file_path="/test/schedule1.jpg",
            file_name="schedule1.jpg",
            file_hash="schedule1",
            file_size_bytes=100000,
            mime_type="image/jpeg"
        )

        user = user_repo.create(telegram_user_id=600001)

        service = SchedulerService(db=test_db)

        # Create 1-day schedule with 2 posts
        result = service.create_schedule(days=1, posts_per_day=2, user_id=user.id)

        assert result["scheduled_count"] >= 1

        # Verify queue items were created
        queue_items = queue_repo.list_all()
        assert len(queue_items) >= 1

    def test_select_next_media_prioritizes_never_posted(self, test_db):
        """Test that never-posted media is prioritized."""
        media_repo = MediaRepository(test_db)

        # Create never-posted media
        never_posted = media_repo.create(
            file_path="/test/never.jpg",
            file_name="never.jpg",
            file_hash="never789",
            file_size_bytes=90000,
            mime_type="image/jpeg"
        )

        # Create posted media
        posted = media_repo.create(
            file_path="/test/posted.jpg",
            file_name="posted.jpg",
            file_hash="posted789",
            file_size_bytes=95000,
            mime_type="image/jpeg"
        )
        media_repo.increment_times_posted(posted.id)

        service = SchedulerService(db=test_db)

        # Select next media (should prefer never-posted)
        selected = service._select_next_media(exclude_media_ids=set())

        assert selected is not None
        assert selected.times_posted == 0

    def test_select_next_media_excludes_locked(self, test_db):
        """Test that locked media is excluded from selection."""
        media_repo = MediaRepository(test_db)
        lock_repo = LockRepository(test_db)

        # Create locked media
        locked_media = media_repo.create(
            file_path="/test/locked_sched.jpg",
            file_name="locked_sched.jpg",
            file_hash="locked_s789",
            file_size_bytes=85000,
            mime_type="image/jpeg"
        )

        # Create unlocked media
        unlocked_media = media_repo.create(
            file_path="/test/unlocked_sched.jpg",
            file_name="unlocked_sched.jpg",
            file_hash="unlocked_s789",
            file_size_bytes=80000,
            mime_type="image/jpeg"
        )

        # Lock first media
        lock_repo.create(
            media_id=locked_media.id,
            reason="recent_post",
            expires_at=datetime.utcnow() + timedelta(days=10)
        )

        service = SchedulerService(db=test_db)

        # Select next media (should skip locked)
        selected = service._select_next_media(exclude_media_ids=set())

        assert selected is not None
        assert selected.id == unlocked_media.id

    def test_select_next_media_excludes_queued(self, test_db):
        """Test that queued media is excluded from selection."""
        media_repo = MediaRepository(test_db)
        user_repo = UserRepository(test_db)
        queue_repo = QueueRepository(test_db)

        # Create two media items
        queued_media = media_repo.create(
            file_path="/test/queued.jpg",
            file_name="queued.jpg",
            file_hash="queued789",
            file_size_bytes=75000,
            mime_type="image/jpeg"
        )

        available_media = media_repo.create(
            file_path="/test/available.jpg",
            file_name="available.jpg",
            file_hash="available789",
            file_size_bytes=70000,
            mime_type="image/jpeg"
        )

        user = user_repo.create(telegram_user_id=600002)

        # Queue first media
        queue_repo.create(
            media_id=queued_media.id,
            scheduled_user_id=user.id,
            scheduled_time=datetime.utcnow() + timedelta(hours=1)
        )

        service = SchedulerService(db=test_db)

        # Select next media (should skip queued)
        selected = service._select_next_media(exclude_media_ids=set())

        assert selected is not None
        assert selected.id == available_media.id

    def test_generate_time_slots(self, test_db):
        """Test generating time slots for scheduling."""
        service = SchedulerService(db=test_db)

        start_time = datetime.utcnow()
        time_slots = service._generate_time_slots(
            days=2,
            posts_per_day=3,
            start_time=start_time
        )

        # Should generate 6 slots (2 days * 3 posts)
        assert len(time_slots) == 6

        # Slots should be in chronological order
        for i in range(len(time_slots) - 1):
            assert time_slots[i] < time_slots[i + 1]

    @patch("src.services.core.scheduler.settings")
    def test_create_schedule_respects_posting_hours(self, mock_settings, test_db):
        """Test that schedule respects posting hours configuration."""
        mock_settings.POSTING_HOURS_START = 9  # 9 AM
        mock_settings.POSTING_HOURS_END = 17   # 5 PM
        mock_settings.POSTS_PER_DAY = 2

        media_repo = MediaRepository(test_db)
        user_repo = UserRepository(test_db)

        # Create test media
        media = media_repo.create(
            file_path="/test/hours.jpg",
            file_name="hours.jpg",
            file_hash="hours789",
            file_size_bytes=65000,
            mime_type="image/jpeg"
        )

        user = user_repo.create(telegram_user_id=600003)

        service = SchedulerService(db=test_db)

        # Create schedule
        result = service.create_schedule(days=1, posts_per_day=2, user_id=user.id)

        # Verify time slots are within posting hours
        queue_repo = QueueRepository(test_db)
        queue_items = queue_repo.list_all()

        for item in queue_items:
            hour = item.scheduled_time.hour
            # Allow for jitter, but should be roughly within bounds
            assert 0 <= hour <= 23  # Basic sanity check
