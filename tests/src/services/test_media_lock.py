"""Tests for MediaLockService."""
import pytest
from datetime import datetime, timedelta

from src.services.core.media_lock import MediaLockService
from src.repositories.media_repository import MediaRepository
from src.repositories.lock_repository import LockRepository


@pytest.mark.unit
class TestMediaLockService:
    """Test suite for MediaLockService."""

    def test_create_lock(self, test_db):
        """Test creating a media lock."""
        media_repo = MediaRepository(test_db)

        media = media_repo.create(
            file_path="/test/lock_test.jpg",
            file_name="lock_test.jpg",
            file_hash="lock_test789",
            file_size_bytes=100000,
            mime_type="image/jpeg"
        )

        service = MediaLockService(db=test_db)

        lock = service.create_lock(
            media_id=media.id,
            reason="test_lock",
            lock_duration_days=30
        )

        assert lock is not None
        assert lock.media_id == media.id
        assert lock.reason == "test_lock"

    def test_is_locked(self, test_db):
        """Test checking if media is locked."""
        media_repo = MediaRepository(test_db)
        lock_repo = LockRepository(test_db)

        media = media_repo.create(
            file_path="/test/is_locked.jpg",
            file_name="is_locked.jpg",
            file_hash="is_locked789",
            file_size_bytes=95000,
            mime_type="image/jpeg"
        )

        service = MediaLockService(db=test_db)

        # Initially not locked
        assert service.is_locked(media.id) is False

        # Create lock
        service.create_lock(media.id, "test", lock_duration_days=10)

        # Now should be locked
        assert service.is_locked(media.id) is True

    def test_cleanup_expired_locks(self, test_db):
        """Test cleaning up expired locks."""
        media_repo = MediaRepository(test_db)
        lock_repo = LockRepository(test_db)

        media = media_repo.create(
            file_path="/test/cleanup.jpg",
            file_name="cleanup.jpg",
            file_hash="cleanup789",
            file_size_bytes=90000,
            mime_type="image/jpeg"
        )

        # Create expired lock
        lock_repo.create(
            media_id=media.id,
            reason="expired",
            expires_at=datetime.utcnow() - timedelta(days=1)
        )

        service = MediaLockService(db=test_db)

        result = service.cleanup_expired_locks()

        assert result["deleted_count"] >= 1

    def test_remove_lock(self, test_db):
        """Test manually removing a lock."""
        media_repo = MediaRepository(test_db)

        media = media_repo.create(
            file_path="/test/remove_lock.jpg",
            file_name="remove_lock.jpg",
            file_hash="remove789",
            file_size_bytes=85000,
            mime_type="image/jpeg"
        )

        service = MediaLockService(db=test_db)

        # Create lock
        lock = service.create_lock(media.id, "manual", lock_duration_days=5)

        # Remove lock
        service.remove_lock(lock.id)

        # Verify removed
        assert service.is_locked(media.id) is False

    def test_get_active_locks(self, test_db):
        """Test retrieving active locks."""
        media_repo = MediaRepository(test_db)

        media = media_repo.create(
            file_path="/test/active_locks.jpg",
            file_name="active_locks.jpg",
            file_hash="active789",
            file_size_bytes=80000,
            mime_type="image/jpeg"
        )

        service = MediaLockService(db=test_db)

        # Create active lock
        service.create_lock(media.id, "active_test", lock_duration_days=15)

        active_locks = service.get_active_locks()

        assert len(active_locks) >= 1

    def test_lock_after_posting(self, test_db):
        """Test creating lock after posting media."""
        media_repo = MediaRepository(test_db)

        media = media_repo.create(
            file_path="/test/post_lock.jpg",
            file_name="post_lock.jpg",
            file_hash="postlock789",
            file_size_bytes=75000,
            mime_type="image/jpeg"
        )

        service = MediaLockService(db=test_db)

        # Lock after posting (default 30 days)
        lock = service.lock_after_posting(media.id)

        assert lock is not None
        assert lock.reason == "recent_post"
        assert service.is_locked(media.id) is True
