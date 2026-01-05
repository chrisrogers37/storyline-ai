"""Media lock service - TTL lock management."""
from typing import Optional

from src.services.base_service import BaseService
from src.repositories.lock_repository import LockRepository
from src.config.settings import settings
from src.utils.logger import logger


class MediaLockService(BaseService):
    """TTL lock management to prevent premature reposts."""

    def __init__(self):
        super().__init__()
        self.lock_repo = LockRepository()

    def create_lock(
        self,
        media_item_id: str,
        ttl_days: Optional[int] = None,
        lock_reason: str = "recent_post",
        created_by_user_id: Optional[str] = None,
    ) -> bool:
        """
        Create a TTL lock for a media item.

        Args:
            media_item_id: ID of media item to lock
            ttl_days: Days to lock (default: from settings, None for permanent)
            lock_reason: Reason for lock ('recent_post', 'manual_hold', 'seasonal', 'permanent_reject')
            created_by_user_id: User who created the lock (optional)

        Returns:
            True if lock created successfully
        """
        # Default to settings if not specified (but allow explicit None for permanent locks)
        if ttl_days is None and lock_reason != "permanent_reject":
            ttl_days = settings.REPOST_TTL_DAYS

        # Check if already locked
        if self.is_locked(media_item_id):
            logger.warning(f"Media {media_item_id} is already locked")
            return False

        self.lock_repo.create(
            media_item_id=media_item_id,
            ttl_days=ttl_days,
            lock_reason=lock_reason,
            created_by_user_id=created_by_user_id,
        )

        if ttl_days is None:
            logger.info(f"Created permanent lock for media {media_item_id} (reason: {lock_reason})")
        else:
            logger.info(f"Created {ttl_days}-day lock for media {media_item_id} (reason: {lock_reason})")
        return True

    def create_permanent_lock(
        self,
        media_item_id: str,
        created_by_user_id: Optional[str] = None,
    ) -> bool:
        """
        Create a permanent lock for a media item (infinite TTL).

        Args:
            media_item_id: ID of media item to permanently lock
            created_by_user_id: User who created the lock (optional)

        Returns:
            True if lock created successfully
        """
        return self.create_lock(
            media_item_id=media_item_id,
            ttl_days=None,
            lock_reason="permanent_reject",
            created_by_user_id=created_by_user_id,
        )

    def is_locked(self, media_item_id: str) -> bool:
        """Check if media item is currently locked."""
        return self.lock_repo.is_locked(media_item_id)

    def get_active_lock(self, media_item_id: str):
        """Get active lock for media item (if any)."""
        return self.lock_repo.get_active_lock(media_item_id)

    def remove_lock(self, lock_id: str) -> bool:
        """Manually remove a lock."""
        return self.lock_repo.delete(lock_id)

    def cleanup_expired_locks(self) -> int:
        """
        Delete all expired locks.

        Returns:
            Number of locks cleaned up
        """
        with self.track_execution("cleanup_expired_locks") as run_id:
            count = self.lock_repo.cleanup_expired()

            self.set_result_summary(run_id, {"locks_cleaned": count})

            logger.info(f"Cleaned up {count} expired locks")
            return count
