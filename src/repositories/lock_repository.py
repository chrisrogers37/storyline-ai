"""Media lock repository - CRUD operations for media locks."""
from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.models.media_lock import MediaPostingLock


class LockRepository:
    """Repository for MediaPostingLock CRUD operations."""

    def __init__(self):
        self.db: Session = next(get_db())

    def get_by_id(self, lock_id: str) -> Optional[MediaPostingLock]:
        """Get lock by ID."""
        return self.db.query(MediaPostingLock).filter(MediaPostingLock.id == lock_id).first()

    def get_active_lock(self, media_id: str) -> Optional[MediaPostingLock]:
        """Get active lock for media item (if any)."""
        now = datetime.utcnow()
        return (
            self.db.query(MediaPostingLock)
            .filter(
                MediaPostingLock.media_item_id == media_id,
                # Lock is active if: locked_until is NULL (permanent) OR locked_until > now
                (MediaPostingLock.locked_until.is_(None)) | (MediaPostingLock.locked_until > now)
            )
            .first()
        )

    def is_locked(self, media_id: str) -> bool:
        """Check if media item is currently locked."""
        return self.get_active_lock(media_id) is not None

    def get_all_active(self) -> List[MediaPostingLock]:
        """Get all active locks."""
        now = datetime.utcnow()
        return (
            self.db.query(MediaPostingLock)
            .filter(
                (MediaPostingLock.locked_until.is_(None)) | (MediaPostingLock.locked_until > now)
            )
            .order_by(MediaPostingLock.locked_until.asc().nulls_last())
            .all()
        )

    def create(
        self,
        media_item_id: str,
        ttl_days: Optional[int],
        lock_reason: str = "recent_post",
        created_by_user_id: Optional[str] = None,
    ) -> MediaPostingLock:
        """Create a new TTL lock. If ttl_days is None, creates permanent lock."""
        if ttl_days is None:
            locked_until = None  # Permanent lock
        else:
            locked_until = datetime.utcnow() + timedelta(days=ttl_days)

        lock = MediaPostingLock(
            media_item_id=media_item_id,
            locked_until=locked_until,
            lock_reason=lock_reason,
            created_by_user_id=created_by_user_id,
        )
        self.db.add(lock)
        self.db.commit()
        self.db.refresh(lock)
        return lock

    def delete(self, lock_id: str) -> bool:
        """Delete a lock."""
        lock = self.get_by_id(lock_id)
        if lock:
            self.db.delete(lock)
            self.db.commit()
            return True
        return False

    def get_permanent_locks(self) -> List[MediaPostingLock]:
        """Get all permanent locks (locked_until IS NULL)."""
        return (
            self.db.query(MediaPostingLock)
            .filter(MediaPostingLock.locked_until.is_(None))
            .order_by(MediaPostingLock.created_at.desc())
            .all()
        )

    def cleanup_expired(self) -> int:
        """Delete all expired locks. Returns count of deleted locks."""
        now = datetime.utcnow()
        count = (
            self.db.query(MediaPostingLock)
            .filter(
                MediaPostingLock.locked_until.isnot(None),  # Don't delete permanent locks
                MediaPostingLock.locked_until <= now
            )
            .delete()
        )
        self.db.commit()
        return count
