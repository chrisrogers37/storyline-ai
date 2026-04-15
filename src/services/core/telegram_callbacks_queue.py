"""Telegram callback handlers - queue action handlers (posted, skipped, rejected)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from sqlalchemy.exc import OperationalError

from src.services.core.telegram_service import _escape_markdown
from src.services.core.telegram_utils import (
    build_queue_action_keyboard,
    validate_queue_and_media,
    validate_queue_item,
)
from src.utils.logger import logger
from src.utils.resilience import telegram_edit_with_retry

if TYPE_CHECKING:
    from src.services.core.telegram_callbacks_core import TelegramCallbackCore
    from src.services.core.telegram_service import TelegramService


class TelegramCallbackQueueHandlers:
    """Handles queue action callback buttons in Telegram.

    Manages posted/skipped/rejected callback flows.
    Uses composition: receives a TelegramService reference and a
    TelegramCallbackCore instance for shared utilities.
    """

    def __init__(self, service: TelegramService, core: TelegramCallbackCore):
        self.service = service
        self.core = core

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
        await self.core._safe_locked_callback(
            queue_id,
            query,
            callback_name,
            "❌ Error processing action. Please try again or use /next.",
            self._do_complete_queue_action(
                queue_id, user, query, status, success, caption, callback_name
            ),
        )

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
            media_item = self.core._execute_complete_db_ops(
                queue_id, queue_item, user, status, success
            )
        except OperationalError as e:
            logger.warning(
                f"OperationalError during {callback_name} for queue {queue_id[:8]}, "
                f"refreshing sessions and retrying: {e}"
            )
            self.core._refresh_repo_sessions()

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
                media_item = self.core._execute_complete_db_ops(
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

        await self.core._safe_locked_callback(
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
            media_item = self.core._execute_reject_db_ops(queue_id, queue_item, user)
        except OperationalError as e:
            logger.warning(
                f"OperationalError during reject for queue {queue_id[:8]}, "
                f"refreshing sessions and retrying: {e}"
            )
            self.core._refresh_repo_sessions()

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

                media_item = self.core._execute_reject_db_ops(
                    queue_id, queue_item, user
                )
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
