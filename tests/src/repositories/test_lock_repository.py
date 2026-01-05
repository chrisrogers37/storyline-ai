"""Tests for LockRepository."""
import pytest
from datetime import datetime, timedelta

from src.repositories.lock_repository import LockRepository
from src.repositories.media_repository import MediaRepository


@pytest.mark.unit
class TestLockRepository:
    """Test suite for LockRepository."""

    def test_create_lock(self, test_db):
        """Test creating a media lock."""
        media_repo = MediaRepository(test_db)
        lock_repo = LockRepository(test_db)

        # Create media
        media = media_repo.create(
            file_path="/test/locked.jpg",
            file_name="locked.jpg",
            file_hash="locked123",
            file_size_bytes=100000,
            mime_type="image/jpeg"
        )

        # Create lock
        expires_at = datetime.utcnow() + timedelta(days=30)
        lock = lock_repo.create(
            media_id=media.id,
            reason="recent_post",
            expires_at=expires_at
        )

        assert lock.id is not None
        assert lock.media_id == media.id
        assert lock.reason == "recent_post"
        assert lock.expires_at == expires_at

    def test_is_locked_active_lock(self, test_db):
        """Test checking if media is locked with active lock."""
        media_repo = MediaRepository(test_db)
        lock_repo = LockRepository(test_db)

        media = media_repo.create(
            file_path="/test/active_lock.jpg",
            file_name="active_lock.jpg",
            file_hash="active123",
            file_size_bytes=90000,
            mime_type="image/jpeg"
        )

        # Create active lock (expires in future)
        lock_repo.create(
            media_id=media.id,
            reason="recent_post",
            expires_at=datetime.utcnow() + timedelta(days=10)
        )

        is_locked = lock_repo.is_locked(media.id)

        assert is_locked is True

    def test_is_locked_expired_lock(self, test_db):
        """Test checking if media is locked with expired lock."""
        media_repo = MediaRepository(test_db)
        lock_repo = LockRepository(test_db)

        media = media_repo.create(
            file_path="/test/expired_lock.jpg",
            file_name="expired_lock.jpg",
            file_hash="expired123",
            file_size_bytes=85000,
            mime_type="image/jpeg"
        )

        # Create expired lock (expires in past)
        lock_repo.create(
            media_id=media.id,
            reason="recent_post",
            expires_at=datetime.utcnow() - timedelta(days=1)
        )

        is_locked = lock_repo.is_locked(media.id)

        assert is_locked is False

    def test_is_locked_no_lock(self, test_db):
        """Test checking if media is locked with no lock."""
        media_repo = MediaRepository(test_db)
        lock_repo = LockRepository(test_db)

        media = media_repo.create(
            file_path="/test/no_lock.jpg",
            file_name="no_lock.jpg",
            file_hash="nolock123",
            file_size_bytes=80000,
            mime_type="image/jpeg"
        )

        is_locked = lock_repo.is_locked(media.id)

        assert is_locked is False

    def test_get_active_locks(self, test_db):
        """Test retrieving active locks."""
        media_repo = MediaRepository(test_db)
        lock_repo = LockRepository(test_db)

        media = media_repo.create(
            file_path="/test/active.jpg",
            file_name="active.jpg",
            file_hash="active456",
            file_size_bytes=75000,
            mime_type="image/jpeg"
        )

        # Create active lock
        lock_repo.create(
            media_id=media.id,
            reason="recent_post",
            expires_at=datetime.utcnow() + timedelta(days=5)
        )

        active_locks = lock_repo.get_active_locks()

        assert len(active_locks) >= 1

    def test_cleanup_expired(self, test_db):
        """Test cleaning up expired locks."""
        media_repo = MediaRepository(test_db)
        lock_repo = LockRepository(test_db)

        media = media_repo.create(
            file_path="/test/cleanup.jpg",
            file_name="cleanup.jpg",
            file_hash="cleanup123",
            file_size_bytes=70000,
            mime_type="image/jpeg"
        )

        # Create expired lock
        expired_lock = lock_repo.create(
            media_id=media.id,
            reason="recent_post",
            expires_at=datetime.utcnow() - timedelta(hours=1)
        )

        # Cleanup
        deleted_count = lock_repo.cleanup_expired()

        assert deleted_count >= 1

        # Verify lock is deleted
        remaining_lock = lock_repo.get_by_id(expired_lock.id)
        assert remaining_lock is None

    def test_delete_lock(self, test_db):
        """Test deleting a specific lock."""
        media_repo = MediaRepository(test_db)
        lock_repo = LockRepository(test_db)

        media = media_repo.create(
            file_path="/test/delete_lock.jpg",
            file_name="delete_lock.jpg",
            file_hash="dellock123",
            file_size_bytes=65000,
            mime_type="image/jpeg"
        )

        lock = lock_repo.create(
            media_id=media.id,
            reason="manual_hold",
            expires_at=datetime.utcnow() + timedelta(days=7)
        )

        lock_id = lock.id

        # Delete
        lock_repo.delete(lock_id)

        # Verify deleted
        deleted_lock = lock_repo.get_by_id(lock_id)
        assert deleted_lock is None

    def test_get_by_media_id(self, test_db):
        """Test retrieving locks by media ID."""
        media_repo = MediaRepository(test_db)
        lock_repo = LockRepository(test_db)

        media = media_repo.create(
            file_path="/test/by_media_lock.jpg",
            file_name="by_media_lock.jpg",
            file_hash="bymedia123",
            file_size_bytes=60000,
            mime_type="image/jpeg"
        )

        lock_repo.create(
            media_id=media.id,
            reason="seasonal",
            expires_at=datetime.utcnow() + timedelta(days=90)
        )

        locks = lock_repo.get_by_media_id(media.id)

        assert len(locks) >= 1
        assert locks[0].media_id == media.id
