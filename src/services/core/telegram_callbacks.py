"""Telegram callback handlers - queue action callbacks (posted, skipped, rejected, resume, reset)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.config.settings import settings
from src.repositories.history_repository import HistoryCreateParams
from src.services.core.telegram_utils import (
    build_queue_action_keyboard,
    validate_queue_and_media,
    validate_queue_item,
)
from src.utils.logger import logger
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
        lock = self.service.get_operation_lock(queue_id)
        if lock.locked():
            await query.answer("⏳ Already processing this item...", show_alert=False)
            return

        async with lock:
            try:
                # Immediate visual feedback: remove buttons to signal action received
                try:
                    await query.edit_message_reply_markup(
                        reply_markup=InlineKeyboardMarkup([])
                    )
                except Exception:
                    logger.debug(
                        f"Could not remove keyboard for queue item {queue_id} "
                        f"(message may have been already updated)"
                    )

                await self._do_complete_queue_action(
                    queue_id, user, query, status, success, caption, callback_name
                )
            finally:
                self.service.cleanup_operation_state(queue_id)

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
        queue_item = await validate_queue_item(self.service, queue_id, query)
        if not queue_item:
            return

        media_item = self.service.media_repo.get_by_id(str(queue_item.media_item_id))

        # Create history record
        self.service.history_repo.create(
            HistoryCreateParams(
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
        )

        # Posted-specific: track reposting and user stats
        if status == "posted":
            self.service.media_repo.increment_times_posted(
                str(queue_item.media_item_id)
            )
            self.service.lock_service.create_lock(str(queue_item.media_item_id))
            self.service.user_repo.increment_posts(str(user.id))

        # Delete from queue
        self.service.queue_repo.delete(queue_id)

        # Update message
        await query.edit_message_caption(caption=caption)

        # Log interaction
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

        # Log outgoing bot response
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
        caption = self.service._build_caption(media_item, queue_item)

        # Rebuild original keyboard
        reply_markup = build_queue_action_keyboard(
            queue_id, enable_instagram_api=settings.ENABLE_INSTAGRAM_API
        )

        await query.edit_message_caption(caption=caption, reply_markup=reply_markup)

        logger.info(f"Returned to queue item by {self.service._get_display_name(user)}")

    async def handle_reject_confirmation(self, queue_id: str, user, query):
        """Show confirmation dialog before permanently rejecting media."""
        queue_item = await validate_queue_item(self.service, queue_id, query)
        if not queue_item:
            return

        # Get media item for filename
        media_item = self.service.media_repo.get_by_id(str(queue_item.media_item_id))
        file_name = media_item.file_name if media_item else "Unknown"

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

        await query.edit_message_caption(
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
        )

        await query.edit_message_caption(caption=caption, reply_markup=reply_markup)

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
        """Handle confirmed rejection - permanently blocks media."""
        # Signal any pending autopost to abort
        cancel_flag = self.service.get_cancel_flag(queue_id)
        cancel_flag.set()

        queue_item = await validate_queue_item(self.service, queue_id, query)
        if not queue_item:
            return

        # Immediate visual feedback: remove buttons to signal action received
        try:
            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup([]))
        except Exception:
            logger.debug(f"Could not remove keyboard for rejected item {queue_id}")

        # Get media item for filename
        media_item = self.service.media_repo.get_by_id(str(queue_item.media_item_id))

        # Create history record
        self.service.history_repo.create(
            HistoryCreateParams(
                media_item_id=str(queue_item.media_item_id),
                queue_item_id=queue_id,
                queue_created_at=queue_item.created_at,
                queue_deleted_at=datetime.utcnow(),
                scheduled_for=queue_item.scheduled_for,
                posted_at=datetime.utcnow(),
                status="rejected",
                success=False,
                posted_by_user_id=str(user.id),
                posted_by_telegram_username=user.telegram_username,
                chat_settings_id=str(queue_item.chat_settings_id)
                if queue_item.chat_settings_id
                else None,
            )
        )

        # Create PERMANENT lock (infinite TTL)
        self.service.lock_service.create_permanent_lock(
            str(queue_item.media_item_id), created_by_user_id=str(user.id)
        )

        # Delete from queue
        self.service.queue_repo.delete(queue_id)

        # Update message with clear feedback (respect verbose setting)
        verbose = self.service._is_verbose(query.message.chat_id)
        if verbose:
            caption = (
                f"🚫 *Permanently Rejected*\n\n"
                f"By: {self.service._get_display_name(user)}\n"
                f"File: {media_item.file_name if media_item else 'Unknown'}\n\n"
                f"This media will never be queued again."
            )
        else:
            caption = f"🚫 Rejected by {self.service._get_display_name(user)}"
        await query.edit_message_caption(caption=caption, parse_mode="Markdown")

        # Log interaction
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

        # Log outgoing bot response
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
            await query.edit_message_text(
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
            await query.edit_message_text(
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
            await query.edit_message_text(
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
        if action == "confirm":
            # Reset queue - clear all pending posts
            all_pending = self.service.queue_repo.get_all(status="pending")
            cleared = 0
            for item in all_pending:
                self.service.queue_repo.delete(str(item.id))
                cleared += 1

            await query.edit_message_text(
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
            await query.edit_message_text(
                "❌ *Cancelled*\n\nQueue was not cleared.", parse_mode="Markdown"
            )

        # Log interaction
        self.service.interaction_service.log_callback(
            user_id=str(user.id),
            callback_name=f"clear:{action}",
            context={"action": action},
            telegram_chat_id=query.message.chat_id,
            telegram_message_id=query.message.message_id,
        )
