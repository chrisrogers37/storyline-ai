"""Tests for LockRepository."""

import pytest
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from src.repositories.lock_repository import LockRepository
from src.models.media_lock import MediaPostingLock


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
def lock_repo(mock_db):
    """Create LockRepository with mocked database session."""
    with patch.object(LockRepository, "__init__", lambda self: None):
        repo = LockRepository()
        repo._db = mock_db
        return repo


@pytest.mark.unit
class TestLockRepository:
    """Test suite for LockRepository."""

    def test_create_lock_with_ttl(self, lock_repo, mock_db):
        """Test creating a TTL media lock."""
        lock_repo.create(
            media_item_id="some-media-id",
            ttl_days=30,
            lock_reason="recent_post",
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

        added_lock = mock_db.add.call_args[0][0]
        assert isinstance(added_lock, MediaPostingLock)
        assert added_lock.media_item_id == "some-media-id"
        assert added_lock.lock_reason == "recent_post"
        assert added_lock.locked_until is not None

    def test_create_permanent_lock(self, lock_repo, mock_db):
        """Test creating a permanent lock (ttl_days=None)."""
        lock_repo.create(
            media_item_id="some-media-id",
            ttl_days=None,
            lock_reason="permanent_reject",
            created_by_user_id="some-user-id",
        )

        added_lock = mock_db.add.call_args[0][0]
        assert added_lock.locked_until is None
        assert added_lock.lock_reason == "permanent_reject"
        assert added_lock.created_by_user_id == "some-user-id"

    def test_is_locked_active_lock(self, lock_repo, mock_db):
        """Test checking if media is locked with active lock."""
        mock_lock = MagicMock(spec=MediaPostingLock)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_lock

        result = lock_repo.is_locked("some-media-id")

        assert result is True

    def test_is_locked_no_lock(self, lock_repo, mock_db):
        """Test checking if media is locked with no lock."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = lock_repo.is_locked("some-media-id")

        assert result is False

    def test_get_all_active(self, lock_repo, mock_db):
        """Test retrieving all active locks."""
        mock_locks = [
            MagicMock(spec=MediaPostingLock),
            MagicMock(spec=MediaPostingLock),
        ]
        mock_query = mock_db.query.return_value
        mock_query.all.return_value = mock_locks

        result = lock_repo.get_all_active()

        assert len(result) == 2
        mock_db.query.assert_called_with(MediaPostingLock)

    def test_cleanup_expired(self, lock_repo, mock_db):
        """Test cleaning up expired locks."""
        mock_db.query.return_value.filter.return_value.delete.return_value = 3

        result = lock_repo.cleanup_expired()

        assert result == 3
        mock_db.commit.assert_called_once()

    def test_delete_lock(self, lock_repo, mock_db):
        """Test deleting a specific lock."""
        mock_lock = MagicMock(spec=MediaPostingLock)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_lock

        result = lock_repo.delete("some-lock-id")

        assert result is True
        mock_db.delete.assert_called_once_with(mock_lock)
        mock_db.commit.assert_called_once()

    def test_delete_lock_not_found(self, lock_repo, mock_db):
        """Test deleting a non-existent lock."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = lock_repo.delete("nonexistent-id")

        assert result is False
        mock_db.delete.assert_not_called()
