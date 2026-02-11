"""Tests for MediaLockService."""

import pytest
from unittest.mock import Mock, patch
from contextlib import contextmanager
from uuid import uuid4

from src.services.core.media_lock import MediaLockService


@contextmanager
def mock_track_execution(*args, **kwargs):
    """Mock context manager for track_execution."""
    yield "mock_run_id"


@pytest.fixture
def lock_service():
    """Create MediaLockService with mocked dependencies."""
    with patch.object(MediaLockService, "__init__", lambda self: None):
        service = MediaLockService()
        service.lock_repo = Mock()
        service.service_run_repo = Mock()
        service.service_name = "MediaLockService"
        service.track_execution = mock_track_execution
        service.set_result_summary = Mock()
        return service


@pytest.mark.unit
class TestMediaLockService:
    """Test suite for MediaLockService."""

    def test_create_lock(self, lock_service):
        """Test creating a media lock."""
        media_id = str(uuid4())
        lock_service.lock_repo.is_locked.return_value = False

        with patch("src.services.core.media_lock.settings") as mock_settings:
            mock_settings.REPOST_TTL_DAYS = 30
            result = lock_service.create_lock(media_id, ttl_days=30)

        assert result is True
        lock_service.lock_repo.create.assert_called_once()
        call_kwargs = lock_service.lock_repo.create.call_args.kwargs
        assert call_kwargs["media_item_id"] == media_id
        assert call_kwargs["lock_reason"] == "recent_post"

    def test_is_locked(self, lock_service):
        """Test checking if media is locked."""
        media_id = str(uuid4())

        # Not locked
        lock_service.lock_repo.is_locked.return_value = False
        assert lock_service.is_locked(media_id) is False

        # Locked
        lock_service.lock_repo.is_locked.return_value = True
        assert lock_service.is_locked(media_id) is True

    def test_cleanup_expired_locks(self, lock_service):
        """Test cleaning up expired locks."""
        lock_service.lock_repo.cleanup_expired.return_value = 3

        result = lock_service.cleanup_expired_locks()

        lock_service.lock_repo.cleanup_expired.assert_called_once()
        assert result == 3

    def test_remove_lock(self, lock_service):
        """Test manually removing a lock."""
        lock_id = str(uuid4())
        lock_service.lock_repo.delete.return_value = True

        result = lock_service.remove_lock(lock_id)

        assert result is True
        lock_service.lock_repo.delete.assert_called_once_with(lock_id)

    def test_get_active_locks(self, lock_service):
        """Test retrieving active locks."""
        media_id = str(uuid4())
        mock_lock = Mock()
        lock_service.lock_repo.get_active_lock.return_value = mock_lock

        result = lock_service.get_active_lock(media_id)

        assert result == mock_lock
        lock_service.lock_repo.get_active_lock.assert_called_once_with(media_id)

    def test_lock_after_posting(self, lock_service):
        """Test creating lock after posting media."""
        media_id = str(uuid4())
        lock_service.lock_repo.is_locked.return_value = False

        with patch("src.services.core.media_lock.settings") as mock_settings:
            mock_settings.REPOST_TTL_DAYS = 30
            result = lock_service.create_lock(media_id)

        assert result is True
        lock_service.lock_repo.create.assert_called_once()
        call_kwargs = lock_service.lock_repo.create.call_args.kwargs
        assert call_kwargs["media_item_id"] == media_id
        assert call_kwargs["lock_reason"] == "recent_post"
        assert call_kwargs["ttl_days"] == 30
