"""Telegram callback handlers - queue action callbacks (posted, skipped, rejected, resume, reset)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from contextlib import contextmanager

from sqlalchemy.exc import OperationalError

from src.config.settings import settings
from src.repositories.history_repository import HistoryCreateParams
from src.services.core.telegram_service import _escape_markdown
from src.services.core.telegram_utils import (
    build_queue_action_keyboard,
    validate_queue_and_media,
    validate_queue_item,
)
from src.utils.logger import logger
from src.utils.resilience import telegram_edit_with_retry
from datetime import datetime, timedelta

if TYPE_CHECKING:
    from src.services.core.telegram_service import TelegramService


class TelegramCallbackHandlers:
    """Handles queue action callback buttons in Telegram.

    Manages posted/skipped/rejected/resume/reset callback flows.
    Uses composition: receives a TelegramService reference for shared state.
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
                except Exception:
                    logger.debug(
                        f"Could not remove keyboard for queue item {queue_id} "
                        f"(message may have been already updated)"
                    )

                await coro
            except Exception as e:
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

    async def complete_queue_action(
        self,
        queue_id: str,
        user,
        query,
        status: str,
        success: bool,
        caption: str,
        callback_name: str,
    ):
        """Shared handler for posted/skipped actions.

        Handles the common workflow: validate queue item, create history,
        delete from queue, update caption, and log interactions.
        For 'posted' status, also increments post count, creates lock, and updates user stats.

        Uses operation locks to prevent duplicate actions from rapid button clicks.
        """
        await self._safe_locked_callback(
            queue_id,
            query,
            callback_name,
            "❌ Error processing action. Please try again or use /next.",
            self._do_complete_queue_action(
                queue_id, user, query, status, success, caption, callback_name
            ),
        )

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
        except Exception:
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
        return HistoryCreateParams(
            media_item_id=str(queue_item.media_item_id),
            queue_item_id=queue_id,
            queue_created_at=queue_item.created_at,
            queue_deleted_at=datetime.utcnow(),
            scheduled_for=queue_item.scheduled_for,
            posted_at=datetime.utcnow(),
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
                self.service.lock_service.create_lock(str(queue_item.media_item_id))
                self.service.user_repo.increment_posts(str(user.id))
            elif status == "skipped":
                self.service.lock_service.create_lock(
                    str(queue_item.media_item_id),
                    ttl_days=settings.SKIP_TTL_DAYS,
                    lock_reason="skip",
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

    async def _do_complete_queue_action(
        self,
        queue_id: str,
        user,
        query,
        status: str,
        success: bool,
        caption: str,
        callback_name: str,
    ):
        """Internal implementation of queue action completion (runs under lock)."""
        # Atomic claim: prevents duplicate processing from rapid double-taps
        queue_item = self.service.queue_repo.claim_for_processing(queue_id)
        if not queue_item:
            # Already claimed by another handler — show contextual message
            await validate_queue_item(self.service, queue_id, query)
            return

        # Execute DB operations with retry-once on SSL/connection errors
        try:
            media_item = self._execute_complete_db_ops(
                queue_id, queue_item, user, status, success
            )
        except OperationalError as e:
            logger.warning(
                f"OperationalError during {callback_name} for queue {queue_id[:8]}, "
                f"refreshing sessions and retrying: {e}"
            )
            self._refresh_repo_sessions()

            # Check if history was already created before the error
            existing_history = self.service.history_repo.get_by_queue_item_id(queue_id)
            if existing_history:
                logger.info(
                    f"History already exists for queue {queue_id[:8]}, "
                    f"cleaning up queue item only"
                )
                self.service.queue_repo.delete(queue_id)
                media_item = self.service.media_repo.get_by_id(
                    str(queue_item.media_item_id)
                )
            else:
                # Re-fetch — may have been deleted by concurrent operation
                queue_item = self.service.queue_repo.get_by_id(queue_id)
                if not queue_item:
                    logger.info(f"Queue item {queue_id[:8]} gone after session refresh")
                    await telegram_edit_with_retry(
                        query.edit_message_caption,
                        caption="⚠️ This item was already processed.",
                    )
                    return

                # Retry once — if this fails, let it propagate
                media_item = self._execute_complete_db_ops(
                    queue_id, queue_item, user, status, success
                )
                logger.info(
                    f"Retry succeeded for {callback_name} on queue {queue_id[:8]}"
                )

        # Update message (retry on transient Telegram failures)
        await telegram_edit_with_retry(
            query.edit_message_caption, caption=caption, parse_mode="Markdown"
        )

        # Log interaction (fire-and-forget, already has its own error handling)
        self.service.interaction_service.log_callback(
            user_id=str(user.id),
            callback_name=callback_name,
            context={
                "queue_item_id": queue_id,
                "media_id": str(queue_item.media_item_id),
                "media_filename": media_item.file_name if media_item else None,
            },
            telegram_chat_id=query.message.chat_id,
            telegram_message_id=query.message.message_id,
        )

        self.service.interaction_service.log_bot_response(
            response_type="caption_update",
            context={
                "caption": caption,
                "action": callback_name,
                "media_filename": media_item.file_name if media_item else None,
                "edited": True,
            },
            telegram_chat_id=query.message.chat_id,
            telegram_message_id=query.message.message_id,
        )

        logger.info(f"Post {status} by {self.service._get_display_name(user)}")

    async def handle_posted(self, queue_id: str, user, query):
        """Handle 'Posted' button click."""
        # Signal any pending autopost to abort
        cancel_flag = self.service.get_cancel_flag(queue_id)
        cancel_flag.set()

        verbose = self.service._is_verbose(query.message.chat_id)
        display_name = self.service._get_display_name(user)
        if verbose:
            caption = f"✅ Marked as posted by {display_name}"
        else:
            caption = f"✅ Posted by {display_name}"

        await self.complete_queue_action(
            queue_id,
            user,
            query,
            status="posted",
            success=True,
            caption=caption,
            callback_name="posted",
        )

    async def handle_skipped(self, queue_id: str, user, query):
        """Handle 'Skip' button click."""
        # Signal any pending autopost to abort
        cancel_flag = self.service.get_cancel_flag(queue_id)
        cancel_flag.set()

        display_name = self.service._get_display_name(user)
        caption = f"⏭️ Skipped by {display_name}"

        await self.complete_queue_action(
            queue_id,
            user,
            query,
            status="skipped",
            success=False,
            caption=caption,
            callback_name="skip",
        )

    async def handle_back(self, queue_id: str, user, query):
        """Handle 'Back' button - restore original queue item message."""
        queue_item, media_item = await validate_queue_and_media(
            self.service, queue_id, query
        )
        if not queue_item:
            return

        # Rebuild original caption
        chat_id = query.message.chat_id
        active_account = self.service.ig_account_service.get_active_account(chat_id)
        caption = self.service._build_caption(
            media_item, queue_item, active_account=active_account
        )

        # Rebuild original keyboard
        chat_settings = self.service.settings_service.get_settings(chat_id)
        reply_markup = build_queue_action_keyboard(
            queue_id,
            enable_instagram_api=chat_settings.enable_instagram_api,
            active_account=active_account,
            account_count=self.service.ig_account_service.count_active_accounts(),
        )

        await telegram_edit_with_retry(
            query.edit_message_caption,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

        logger.info(f"Returned to queue item by {self.service._get_display_name(user)}")

    async def handle_reject_confirmation(self, queue_id: str, user, query):
        """Show confirmation dialog before permanently rejecting media."""
        queue_item = await validate_queue_item(self.service, queue_id, query)
        if not queue_item:
            return

        # Get media item for filename
        media_item = self.service.media_repo.get_by_id(str(queue_item.media_item_id))
        file_name = _escape_markdown(media_item.file_name) if media_item else "Unknown"

        # Build confirmation keyboard (short labels - details in message above)
        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ Yes", callback_data=f"confirm_reject:{queue_id}"
                ),
                InlineKeyboardButton(
                    "❌ No", callback_data=f"cancel_reject:{queue_id}"
                ),
            ]
        ]

        caption = (
            f"⚠️ *Are you sure?*\n\n"
            f"This will permanently reject:\n"
            f"📁 {file_name}\n\n"
            f"The image will never be queued again.\n"
            f"This action cannot be undone."
        )

        await telegram_edit_with_retry(
            query.edit_message_caption,
            caption=caption,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

        # Log interaction (showing confirmation dialog)
        self.service.interaction_service.log_callback(
            user_id=str(user.id),
            callback_name="reject",
            context={
                "queue_item_id": queue_id,
                "media_id": str(queue_item.media_item_id),
                "media_filename": file_name,
            },
            telegram_chat_id=query.message.chat_id,
            telegram_message_id=query.message.message_id,
        )

    async def handle_cancel_reject(self, queue_id: str, user, query):
        """Cancel rejection and restore original buttons."""
        queue_item, media_item = await validate_queue_and_media(
            self.service, queue_id, query
        )
        if not queue_item:
            return

        chat_id = query.message.chat_id

        # Get active account for caption and button
        active_account = self.service.ig_account_service.get_active_account(chat_id)

        # Rebuild original caption
        caption = self.service._build_caption(
            media_item, queue_item, active_account=active_account
        )

        # Get chat settings for enable_instagram_api check (use DB, not env var)
        chat_settings = self.service.settings_service.get_settings(chat_id)

        # Rebuild original keyboard
        reply_markup = build_queue_action_keyboard(
            queue_id,
            enable_instagram_api=chat_settings.enable_instagram_api,
            active_account=active_account,
            account_count=self.service.ig_account_service.count_active_accounts(),
        )

        await telegram_edit_with_retry(
            query.edit_message_caption,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

        # Log interaction
        self.service.interaction_service.log_callback(
            user_id=str(user.id),
            callback_name="cancel_reject",
            context={
                "queue_item_id": queue_id,
                "media_id": str(queue_item.media_item_id),
            },
            telegram_chat_id=query.message.chat_id,
            telegram_message_id=query.message.message_id,
        )

        logger.info(f"Reject cancelled by {self.service._get_display_name(user)}")

    async def handle_rejected(self, queue_id: str, user, query):
        """Handle confirmed rejection - permanently blocks media.

        Uses operation locks to prevent duplicate rejections from rapid clicks.
        """
        # Signal any pending autopost to abort
        cancel_flag = self.service.get_cancel_flag(queue_id)
        cancel_flag.set()

        await self._safe_locked_callback(
            queue_id,
            query,
            "reject",
            "❌ Error rejecting item. Please try again.",
            self._do_handle_rejected(queue_id, user, query),
        )

    async def _do_handle_rejected(self, queue_id: str, user, query):
        """Internal implementation of rejection (runs under lock)."""
        # Atomic claim: prevents duplicate processing from rapid double-taps
        queue_item = self.service.queue_repo.claim_for_processing(queue_id)
        if not queue_item:
            await validate_queue_item(self.service, queue_id, query)
            return

        # Execute DB operations with retry-once on SSL/connection errors
        try:
            media_item = self._execute_reject_db_ops(queue_id, queue_item, user)
        except OperationalError as e:
            logger.warning(
                f"OperationalError during reject for queue {queue_id[:8]}, "
                f"refreshing sessions and retrying: {e}"
            )
            self._refresh_repo_sessions()

            existing_history = self.service.history_repo.get_by_queue_item_id(queue_id)
            if existing_history:
                logger.info(
                    f"History already exists for rejected queue {queue_id[:8]}, "
                    f"cleaning up queue item only"
                )
                self.service.queue_repo.delete(queue_id)
                media_item = self.service.media_repo.get_by_id(
                    str(queue_item.media_item_id)
                )
            else:
                queue_item = self.service.queue_repo.get_by_id(queue_id)
                if not queue_item:
                    logger.info(f"Queue item {queue_id[:8]} gone after session refresh")
                    await telegram_edit_with_retry(
                        query.edit_message_caption,
                        caption="⚠️ This item was already processed.",
                    )
                    return

                media_item = self._execute_reject_db_ops(queue_id, queue_item, user)
                logger.info(f"Retry succeeded for reject on queue {queue_id[:8]}")

        # Update message with clear feedback (respect verbose setting)
        verbose = self.service._is_verbose(query.message.chat_id)
        if verbose:
            file_name = (
                _escape_markdown(media_item.file_name) if media_item else "Unknown"
            )
            caption = (
                f"🚫 *Permanently Rejected*\n\n"
                f"By: {self.service._get_display_name(user)}\n"
                f"File: {file_name}\n\n"
                f"This media will never be queued again."
            )
        else:
            caption = f"🚫 Rejected by {self.service._get_display_name(user)}"
        await telegram_edit_with_retry(
            query.edit_message_caption, caption=caption, parse_mode="Markdown"
        )

        # Log interaction (fire-and-forget)
        self.service.interaction_service.log_callback(
            user_id=str(user.id),
            callback_name="confirm_reject",
            context={
                "queue_item_id": queue_id,
                "media_id": str(queue_item.media_item_id),
                "media_filename": media_item.file_name if media_item else None,
            },
            telegram_chat_id=query.message.chat_id,
            telegram_message_id=query.message.message_id,
        )

        self.service.interaction_service.log_bot_response(
            response_type="caption_update",
            context={
                "caption": caption,
                "action": "rejected",
                "media_filename": media_item.file_name if media_item else None,
                "edited": True,
            },
            telegram_chat_id=query.message.chat_id,
            telegram_message_id=query.message.message_id,
        )

        logger.info(
            f"Post permanently rejected by {self.service._get_display_name(user)}: "
            f"{media_item.file_name if media_item else queue_item.media_item_id}"
        )

    async def handle_resume_callback(self, action: str, user, query):
        """Handle resume callback buttons (reschedule/clear/force)."""
        try:
            await self._do_resume_callback(action, user, query)
        except Exception as e:
            logger.error(
                f"Failed to handle resume:{action}: {type(e).__name__}: {e}",
                exc_info=True,
            )
            await telegram_edit_with_retry(
                query.edit_message_text,
                "❌ Error during resume. Please try /settings.",
                parse_mode="Markdown",
            )

    async def _do_resume_callback(self, action: str, user, query):
        """Internal implementation of resume callback."""
        now = datetime.utcnow()
        all_pending = self.service.queue_repo.get_all(status="pending")
        overdue = [p for p in all_pending if p.scheduled_for < now]

        if action == "reschedule":
            # Reschedule overdue posts to future times
            # Get time slots for rescheduling
            rescheduled = 0
            for i, item in enumerate(overdue):
                # Spread out over next few hours
                new_time = now + timedelta(hours=1 + (i * 0.5))
                self.service.queue_repo.update_scheduled_time(str(item.id), new_time)
                rescheduled += 1

            self.service.set_paused(False, user)
            await telegram_edit_with_retry(
                query.edit_message_text,
                f"📦 *Delivery ON*\n\n"
                f"🔄 Rescheduled {rescheduled} overdue posts.\n"
                f"First post in ~1 hour.",
                parse_mode="Markdown",
            )
            logger.info(
                f"Posting resumed by {self.service._get_display_name(user)}, "
                f"rescheduled {rescheduled} overdue posts"
            )

        elif action == "clear":
            # Clear all overdue posts
            cleared = 0
            for item in overdue:
                self.service.queue_repo.delete(str(item.id))
                cleared += 1

            self.service.set_paused(False, user)
            remaining = len(all_pending) - cleared
            await telegram_edit_with_retry(
                query.edit_message_text,
                f"📦 *Delivery ON*\n\n"
                f"🗑️ Cleared {cleared} overdue posts.\n"
                f"📊 {remaining} scheduled posts remaining.",
                parse_mode="Markdown",
            )
            logger.info(
                f"Posting resumed by {self.service._get_display_name(user)}, "
                f"cleared {cleared} overdue posts"
            )

        elif action == "force":
            # Resume without handling overdue - they'll be processed immediately
            self.service.set_paused(False, user)
            await telegram_edit_with_retry(
                query.edit_message_text,
                f"📦 *Delivery ON*\n\n"
                f"⚠️ {len(overdue)} overdue posts will be processed immediately.",
                parse_mode="Markdown",
            )
            logger.info(
                f"Posting resumed (force) by {self.service._get_display_name(user)}, "
                f"{len(overdue)} overdue posts"
            )

        # Log interaction
        self.service.interaction_service.log_callback(
            user_id=str(user.id),
            callback_name=f"resume:{action}",
            context={"overdue_count": len(overdue), "action": action},
            telegram_chat_id=query.message.chat_id,
            telegram_message_id=query.message.message_id,
        )

    async def handle_reset_callback(self, action: str, user, query):
        """Handle reset queue callback buttons (confirm/cancel).

        Legacy: kept for backward compat with old /reset confirmation messages.
        """
        try:
            if action == "confirm":
                # Reset queue - clear all pending posts
                all_pending = self.service.queue_repo.get_all(status="pending")
                cleared = 0
                for item in all_pending:
                    self.service.queue_repo.delete(str(item.id))
                    cleared += 1

                await telegram_edit_with_retry(
                    query.edit_message_text,
                    f"✅ *Queue Cleared*\n\n"
                    f"🗑️ Removed {cleared} pending posts.\n"
                    f"Media items remain in library.",
                    parse_mode="Markdown",
                )
                logger.info(
                    f"Queue cleared by {self.service._get_display_name(user)}: "
                    f"{cleared} posts removed"
                )

            elif action == "cancel":
                await telegram_edit_with_retry(
                    query.edit_message_text,
                    "❌ *Cancelled*\n\nQueue was not cleared.",
                    parse_mode="Markdown",
                )

            # Log interaction
            self.service.interaction_service.log_callback(
                user_id=str(user.id),
                callback_name=f"clear:{action}",
                context={"action": action},
                telegram_chat_id=query.message.chat_id,
                telegram_message_id=query.message.message_id,
            )
        except Exception as e:
            logger.error(
                f"Failed to handle reset:{action}: {type(e).__name__}: {e}",
                exc_info=True,
            )
            await telegram_edit_with_retry(
                query.edit_message_text,
                "❌ Error clearing queue. Please try again.",
                parse_mode="Markdown",
            )

    async def handle_batch_approve(self, data, user, query):
        """Handle batch_approve:{chat_settings_id} callback — approve all pending items.

        Marks each item as posted, creates history records, and applies
        repost-prevention locks. Processes sequentially so one failure
        doesn't affect others.
        """
        cs_id = data
        chat_id = query.message.chat_id

        try:
            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup([]))
        except Exception:
            pass

        pending = self.service.queue_repo.get_all_with_media(
            status="pending", chat_settings_id=cs_id
        )
        processing = self.service.queue_repo.get_all_with_media(
            status="processing", chat_settings_id=cs_id
        )
        all_items = pending + processing

        if not all_items:
            await telegram_edit_with_retry(
                query.edit_message_text,
                "📭 No pending items to approve.",
                parse_mode="Markdown",
            )
            return

        await telegram_edit_with_retry(
            query.edit_message_text,
            f"⏳ *Batch approving {len(all_items)} items...*",
            parse_mode="Markdown",
        )

        approved = 0
        failed = 0

        for queue_item, file_name, category in all_items:
            queue_id = str(queue_item.id)
            try:
                claimed = self.service.queue_repo.claim_for_processing(queue_id)
                if not claimed:
                    failed += 1
                    continue
                self._execute_complete_db_ops(queue_id, claimed, user, "posted", True)
                approved += 1
            except Exception as e:
                logger.error(
                    f"Batch approve failed for {queue_id[:8]}: {type(e).__name__}: {e}"
                )
                failed += 1

        item_word = "item" if approved == 1 else "items"
        result_text = f"✅ *Batch Approve Complete*\n\n📤 {approved} {item_word} marked as posted\n"
        if failed > 0:
            fail_word = "item" if failed == 1 else "items"
            result_text += f"⚠️ {failed} {fail_word} failed\n"

        await telegram_edit_with_retry(
            query.edit_message_text,
            result_text,
            parse_mode="Markdown",
        )

        self.service.interaction_service.log_callback(
            user_id=str(user.id),
            callback_name="batch_approve",
            context={"approved": approved, "failed": failed},
            telegram_chat_id=chat_id,
            telegram_message_id=query.message.message_id,
        )

        logger.info(
            f"Batch approve by {self.service._get_display_name(user)}: "
            f"{approved} approved, {failed} failed"
        )

    async def handle_batch_approve_cancel(self, data, user, query):
        """Handle batch_approve_cancel callback — cancel batch approval."""
        await telegram_edit_with_retry(
            query.edit_message_text,
            "❌ *Batch approval cancelled.*",
            parse_mode="Markdown",
        )
