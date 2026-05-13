"""Media lock service - TTL lock management."""

from typing import Optional

from sqlalchemy.exc import SQLAlchemyError

from src.services.base_service import BaseService
from src.repositories.audit_repository import AuditRepository
from src.repositories.lock_repository import LockRepository
from src.config import defaults
from src.utils.logger import logger


class MediaLockService(BaseService):
    """TTL lock management to prevent premature reposts."""

    def __init__(self):
        super().__init__()
        self.lock_repo = LockRepository()
        self.audit_repo = AuditRepository()
        self._settings_repo = None  # lazy — many callers don't need it

    def _resolve_ttl(self, lock_reason: str, telegram_chat_id: Optional[int]) -> int:
        """Resolve TTL days for a lock from chat_settings, falling back to
        hardcoded defaults for legacy rows that predate migration 029.
        """
        code_default = (
            defaults.DEFAULT_SKIP_TTL_DAYS
            if lock_reason == "skip"
            else defaults.DEFAULT_REPOST_TTL_DAYS
        )
        if telegram_chat_id is None:
            return code_default

        if self._settings_repo is None:
            # Imported lazily to avoid a circular dep between media_lock and
            # the chat_settings repo (which sits below this service).
            from src.repositories.chat_settings_repository import (
                ChatSettingsRepository,
            )

            self._settings_repo = ChatSettingsRepository()

        chat = self._settings_repo.get_by_chat_id(telegram_chat_id)
        if chat is None:
            return code_default
        per_chat = chat.skip_ttl_days if lock_reason == "skip" else chat.repost_ttl_days
        return per_chat if per_chat is not None else code_default

    def create_lock(
        self,
        media_item_id: str,
        ttl_days: Optional[int] = None,
        lock_reason: str = "recent_post",
        created_by_user_id: Optional[str] = None,
        telegram_chat_id: Optional[int] = None,
    ) -> bool:
        """
        Create a TTL lock for a media item.

        Args:
            media_item_id: ID of media item to lock
            ttl_days: Days to lock. Explicit None for permanent_reject.
                When omitted, resolves to the per-chat override
                (`chat_settings.repost_ttl_days` for 'recent_post',
                `chat_settings.skip_ttl_days` for 'skip') if the caller
                passed `telegram_chat_id`, falling back to the env defaults.
            lock_reason: Reason for lock ('recent_post', 'skip', 'manual_hold', 'seasonal', 'permanent_reject')
            created_by_user_id: User who created the lock (optional)
            telegram_chat_id: Chat scope for per-chat TTL lookup.

        Returns:
            True if lock created successfully
        """
        if ttl_days is None and lock_reason != "permanent_reject":
            ttl_days = self._resolve_ttl(lock_reason, telegram_chat_id)

        # Check if already locked
        if self.is_locked(media_item_id):
            logger.warning(f"Media {media_item_id} is already locked")
            return False

        lock = self.lock_repo.create(
            media_item_id=media_item_id,
            ttl_days=ttl_days,
            lock_reason=lock_reason,
            created_by_user_id=created_by_user_id,
        )

        try:
            self.audit_repo.log(
                entity_type="lock",
                entity_id=str(lock.id),
                action="create",
                new_value={"reason": lock_reason, "ttl_days": ttl_days},
                changed_by_user_id=created_by_user_id,
                chat_settings_id=str(lock.chat_settings_id)
                if lock.chat_settings_id
                else None,
            )
        except SQLAlchemyError:
            logger.warning("Audit log failed for lock create", exc_info=True)

        if ttl_days is None:
            logger.info(
                f"Created permanent lock for media {media_item_id} (reason: {lock_reason})"
            )
        else:
            logger.info(
                f"Created {ttl_days}-day lock for media {media_item_id} (reason: {lock_reason})"
            )
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

    def remove_lock(
        self, lock_id: str, removed_by_user_id: Optional[str] = None
    ) -> bool:
        """Manually remove a lock."""
        lock = self.lock_repo.get_by_id(lock_id)
        if not lock:
            return False
        lock_reason = lock.lock_reason
        lock_chat_settings_id = (
            str(lock.chat_settings_id) if lock.chat_settings_id else None
        )
        result = self.lock_repo.delete(lock_id)
        try:
            self.audit_repo.log(
                entity_type="lock",
                entity_id=lock_id,
                action="delete",
                old_value={"reason": lock_reason},
                changed_by_user_id=removed_by_user_id,
                chat_settings_id=lock_chat_settings_id,
            )
        except SQLAlchemyError:
            logger.warning("Audit log failed for lock delete", exc_info=True)
        return result

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
