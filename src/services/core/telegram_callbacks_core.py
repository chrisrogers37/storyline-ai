"""Telegram callback handlers - shared utilities and DB operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from telegram import InlineKeyboardMarkup

from contextlib import contextmanager

from src.repositories.history_repository import HistoryCreateParams
from src.utils.logger import logger
from src.utils.resilience import telegram_edit_with_retry
from datetime import datetime, timezone

if TYPE_CHECKING:
    from src.services.core.telegram_service import TelegramService


class TelegramCallbackCore:
    """Shared utilities for Telegram callback handlers.

    Provides operation locking, shared DB sessions, and common DB
    operations used by both queue and admin handlers.
    """

    def __init__(self, service: TelegramService):
        self.service = service

    async def _safe_locked_callback(
        self,
        queue_id: str,
        query,
        callback_name: str,
        error_msg: str,
        coro,
    ):
        """Run a callback under an operation lock with keyboard removal and error handling.

        Shared wrapper for ``complete_queue_action`` and ``handle_rejected``,
        which both follow the same pattern: acquire lock, remove keyboard,
        run the real work, show error on failure, and clean up.

        Args:
            queue_id: Queue item ID (used for lock key and cleanup).
            query: Telegram callback query (for UI feedback).
            callback_name: Human-readable name for logging.
            error_msg: Caption to show if the callback raises.
            coro: Awaitable that does the actual work.
        """
        lock = self.service.get_operation_lock(queue_id)
        if lock.locked():
            coro.close()  # Prevent "coroutine was never awaited" warning
            await query.answer("⏳ Already processing this item...", show_alert=False)
            return

        async with lock:
            try:
                # Immediate visual feedback: remove buttons to signal action received.
                # Best-effort — message may already be updated by a concurrent handler.
                try:
                    await query.edit_message_reply_markup(
                        reply_markup=InlineKeyboardMarkup([])
                    )
                except Exception:  # noqa: BLE001
                    logger.debug(
                        f"Could not remove keyboard for queue item {queue_id} "
                        f"(message may have been already updated)"
                    )

                await coro
            except Exception as e:  # noqa: BLE001
                logger.error(
                    f"Failed to complete {callback_name} for queue {queue_id[:8]}: "
                    f"{type(e).__name__}: {e}",
                    exc_info=True,
                )
                await telegram_edit_with_retry(
                    query.edit_message_caption,
                    caption=error_msg,
                )
            finally:
                self.service.cleanup_operation_state(queue_id)

    @contextmanager
    def _shared_session(self):
        """Share one DB session with deferred commit for atomic operations.

        Individual repo methods call commit(), but within this context
        manager we replace commit() with flush() so changes accumulate
        without being committed. A single commit at the end makes the
        entire operation atomic.
        """
        repos = [
            self.service.history_repo,
            self.service.media_repo,
            self.service.queue_repo,
            self.service.user_repo,
            self.service.lock_service.lock_repo,
        ]
        primary_session = self.service.history_repo.db
        originals = {}

        # Swap sessions
        for repo in repos:
            originals[id(repo)] = repo._db
            repo.use_session(primary_session)

        # Monkey-patch commit to flush instead (defers actual commit)
        original_commit = primary_session.commit
        primary_session.commit = primary_session.flush

        try:
            yield
            # All ops succeeded — do the real commit
            original_commit()
        except Exception:  # noqa: BLE001 — rollback on any failure, then re-raise
            primary_session.rollback()
            raise
        finally:
            # Restore commit and sessions
            primary_session.commit = original_commit
            for repo in repos:
                if id(repo) in originals:
                    repo.use_session(originals[id(repo)])

    def _create_history_params(self, queue_id, queue_item, user, status, success):
        """Build HistoryCreateParams for a queue action."""
        now = datetime.now(timezone.utc)
        return HistoryCreateParams(
            media_item_id=str(queue_item.media_item_id),
            queue_item_id=queue_id,
            queue_created_at=queue_item.created_at,
            queue_deleted_at=now,
            scheduled_for=queue_item.scheduled_for,
            posted_at=now,
            status=status,
            success=success,
            posted_by_user_id=str(user.id),
            posted_by_telegram_username=user.telegram_username,
            chat_settings_id=str(queue_item.chat_settings_id)
            if queue_item.chat_settings_id
            else None,
        )

    def _execute_complete_db_ops(self, queue_id, queue_item, user, status, success):
        """Execute core DB operations for completing a queue action.

        Uses a shared session across all repos to minimize connection pool
        usage and provide consistent failure behavior.

        Separated to enable retry on OperationalError.
        Returns the media_item.
        """
        with self._shared_session():
            media_item = self.service.media_repo.get_by_id(
                str(queue_item.media_item_id)
            )

            self.service.history_repo.create(
                self._create_history_params(queue_id, queue_item, user, status, success)
            )

            if status == "posted":
                self.service.media_repo.increment_times_posted(
                    str(queue_item.media_item_id)
                )
                self.service.lock_service.create_lock(
                    str(queue_item.media_item_id),
                    telegram_chat_id=queue_item.telegram_chat_id,
                )
                self.service.user_repo.increment_posts(str(user.id))
            elif status == "skipped":
                self.service.lock_service.create_lock(
                    str(queue_item.media_item_id),
                    lock_reason="skip",
                    telegram_chat_id=queue_item.telegram_chat_id,
                )

            self.service.queue_repo.delete(queue_id)
            return media_item

    def _execute_reject_db_ops(self, queue_id, queue_item, user):
        """Execute core DB operations for rejecting a queue item.

        Uses a shared session across all repos to minimize connection pool
        usage and provide consistent failure behavior.

        Separated to enable retry on OperationalError.
        Returns the media_item.
        """
        with self._shared_session():
            media_item = self.service.media_repo.get_by_id(
                str(queue_item.media_item_id)
            )

            self.service.history_repo.create(
                self._create_history_params(
                    queue_id, queue_item, user, "rejected", False
                )
            )

            self.service.lock_service.create_permanent_lock(
                str(queue_item.media_item_id), created_by_user_id=str(user.id)
            )

            self.service.queue_repo.delete(queue_id)
            return media_item

    def _refresh_repo_sessions(self):
        """Force session refresh on all repos used by callback DB operations."""
        for repo in [
            self.service.history_repo,
            self.service.media_repo,
            self.service.queue_repo,
            self.service.user_repo,
        ]:
            repo.end_read_transaction()
        self.service.lock_service.lock_repo.end_read_transaction()
