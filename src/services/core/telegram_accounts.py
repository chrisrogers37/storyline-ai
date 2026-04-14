"""Telegram account handlers - Instagram account management and inline account selection."""

from __future__ import annotations

from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.config.settings import settings as app_settings
from src.services.core.telegram_utils import (
    build_account_management_keyboard,
    build_queue_action_keyboard,
    build_webapp_button,
    validate_queue_and_media,
    validate_queue_item,
)
from src.utils.logger import logger

if TYPE_CHECKING:
    from src.services.core.telegram_service import TelegramService


class TelegramAccountHandlers:
    """Handles Instagram account management in Telegram.

    Manages account selection menus, add/remove flows, inline account
    switching from posting workflow, and the back-to-post rebuild.
    Uses composition: receives a TelegramService reference for shared state.
    """

    ID_DISPLAY_LENGTH = 8  # Truncate UUIDs for Telegram's 64-byte callback limit

    def __init__(self, service: TelegramService):
        self.service = service

    async def handle_account_selection_menu(self, user, query):
        """Show Instagram account configuration menu."""
        chat_id = query.message.chat_id
        account_data = self.service.ig_account_service.get_accounts_for_display(chat_id)
        keyboard = build_account_management_keyboard(account_data)

        await query.edit_message_text(
            "📸 *Choose Default Account*\n\n"
            "Select an account to set as default, or add/remove accounts.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        await query.answer()

    async def handle_account_switch(self, account_id: str, user, query):
        """Handle switching to a different Instagram account."""
        chat_id = query.message.chat_id

        try:
            account = self.service.ig_account_service.switch_account(
                chat_id, account_id, user
            )

            # Log the interaction
            self.service.interaction_service.log_callback(
                user_id=str(user.id),
                callback_name=f"switch_account:{account_id}",
                context={
                    "account_id": account_id,
                    "display_name": account.display_name,
                    "username": account.instagram_username,
                },
                telegram_chat_id=chat_id,
                telegram_message_id=query.message.message_id,
            )

            await query.answer(f"Switched to @{account.instagram_username}")

            # Return to settings menu with updated values
            await self.service.settings_handler.refresh_settings_message(
                query, show_answer=False
            )

        except ValueError as e:
            await query.answer(f"Error: {e}", show_alert=True)

    async def handle_add_account_via_webapp(self, user, query):
        """Redirect to Mini App for secure account input.

        Instead of collecting credentials in chat messages, opens the
        Mini App dashboard where the user can add accounts securely.
        """
        chat_id = query.message.chat_id
        user_id = query.from_user.id if query.from_user else 0
        chat_type = query.message.chat.type

        webapp_url = (
            f"{app_settings.OAUTH_REDIRECT_BASE_URL}/webapp/onboarding"
            f"?chat_id={chat_id}"
        )

        webapp_button = build_webapp_button(
            text="Open Dashboard",
            webapp_url=webapp_url,
            chat_type=chat_type,
            chat_id=chat_id,
            user_id=user_id,
        )

        keyboard = InlineKeyboardMarkup(
            [
                [webapp_button],
                [
                    InlineKeyboardButton(
                        "↩️ Back", callback_data="settings_accounts:select"
                    )
                ],
            ]
        )

        await query.edit_message_text(
            "📸 *Add Instagram Account*\n\n"
            "Open the dashboard to add an account securely.\n"
            "Your credentials will be transmitted via HTTPS and "
            "won't appear in chat history.",
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
        await query.answer()

    async def handle_remove_account_menu(self, user, query):
        """Show menu to select account to remove."""
        chat_id = query.message.chat_id
        account_data = self.service.ig_account_service.get_accounts_for_display(chat_id)

        keyboard = []

        for account in account_data["accounts"]:
            is_active = account["id"] == account_data["active_account_id"]
            label = f"🗑️ {account['display_name']}"
            if account["username"]:
                label += f" (@{account['username']})"
            if is_active:
                label += " ⚠️ ACTIVE"
            keyboard.append(
                [
                    InlineKeyboardButton(
                        label, callback_data=f"account_remove:{account['id']}"
                    )
                ]
            )

        keyboard.append(
            [InlineKeyboardButton("↩️ Back", callback_data="settings_accounts:select")]
        )

        await query.edit_message_text(
            "🗑️ *Remove Instagram Account*\n\n"
            "Select an account to remove:\n\n"
            "_Note: Removing an account deactivates it. Tokens and history are preserved._",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        await query.answer()

    async def handle_account_remove_confirm(self, account_id: str, user, query):
        """Show confirmation before removing account."""
        account = self.service.ig_account_service.get_account_by_id(account_id)

        if not account:
            await query.answer("Account not found", show_alert=True)
            return

        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ Yes, Remove",
                    callback_data=f"account_remove_confirmed:{account_id}",
                ),
                InlineKeyboardButton(
                    "❌ Cancel", callback_data="settings_accounts:select"
                ),
            ]
        ]

        await query.edit_message_text(
            f"⚠️ *Confirm Remove Account*\n\n"
            f"Are you sure you want to remove:\n\n"
            f"📸 *{account.display_name}*\n"
            f"Username: @{account.instagram_username}\n\n"
            f"_The account can be reactivated later via CLI._",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        await query.answer()

    async def handle_account_remove_execute(self, account_id: str, user, query):
        """Execute account removal (deactivation)."""
        chat_id = query.message.chat_id

        try:
            account = self.service.ig_account_service.deactivate_account(
                account_id, user
            )

            # Log interaction
            self.service.interaction_service.log_callback(
                user_id=str(user.id),
                callback_name=f"remove_account:{account_id}",
                context={
                    "account_id": account_id,
                    "display_name": account.display_name,
                    "username": account.instagram_username,
                },
                telegram_chat_id=chat_id,
                telegram_message_id=query.message.message_id,
            )

            await query.answer(f"Removed @{account.instagram_username}")

            logger.info(
                f"User {self.service._get_display_name(user)} removed Instagram account: "
                f"{account.display_name} (@{account.instagram_username})"
            )

            # Return to account config menu
            await self.handle_account_selection_menu(user, query)

        except ValueError as e:
            await query.answer(f"Error: {e}", show_alert=True)

    # =========================================================================
    # Inline Account Selection from Posting Workflow (Phase 1.7)
    # =========================================================================

    async def handle_post_account_selector(self, queue_id: str, user, query):
        """Show account selector submenu for a specific post.

        This is a simplified account selector that only allows switching -
        no add/remove options. For full account management, use /settings.
        """
        chat_id = query.message.chat_id

        # Get queue item to preserve context
        queue_item = await validate_queue_item(self.service, queue_id, query)
        if not queue_item:
            return

        # Get all accounts
        account_data = self.service.ig_account_service.get_accounts_for_display(chat_id)

        # Build keyboard with all accounts (simplified - no add/remove)
        keyboard = []
        for acc in account_data["accounts"]:
            is_active = acc["id"] == account_data["active_account_id"]
            # Show friendly name AND @username for clarity
            label = f"{'✅ ' if is_active else '   '}{acc['display_name']}"
            if acc["username"]:
                label += f" (@{acc['username']})"
            # Use shortened callback format: sap:{queue_id}:{account_id}
            # Using first 8 chars of UUIDs to stay within 64 byte limit
            short_queue_id = (
                queue_id[: self.ID_DISPLAY_LENGTH]
                if len(queue_id) > self.ID_DISPLAY_LENGTH
                else queue_id
            )
            short_account_id = (
                acc["id"][: self.ID_DISPLAY_LENGTH]
                if len(acc["id"]) > self.ID_DISPLAY_LENGTH
                else acc["id"]
            )
            keyboard.append(
                [
                    InlineKeyboardButton(
                        label,
                        callback_data=f"sap:{short_queue_id}:{short_account_id}",
                    )
                ]
            )

        if not account_data["accounts"]:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "No accounts configured",
                        callback_data=f"btp:{queue_id[:8]}",
                    )
                ]
            )

        # Back button (no Add/Remove options in posting workflow)
        short_queue_id = (
            queue_id[: self.ID_DISPLAY_LENGTH]
            if len(queue_id) > self.ID_DISPLAY_LENGTH
            else queue_id
        )
        keyboard.append(
            [
                InlineKeyboardButton(
                    "↩️ Back to Post",
                    callback_data=f"btp:{short_queue_id}",
                )
            ]
        )

        await query.edit_message_caption(
            caption=(
                "📸 *Select Instagram Account*\n\n"
                "Which account should this post be attributed to?"
            ),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

        # Log interaction
        self.service.interaction_service.log_callback(
            user_id=str(user.id),
            callback_name="select_account",
            context={
                "queue_item_id": queue_id,
            },
            telegram_chat_id=chat_id,
            telegram_message_id=query.message.message_id,
        )

    async def handle_post_account_switch(self, data: str, user, query):
        """Handle account switch from posting workflow.

        Callback data format: "sap:{short_queue_id}:{short_account_id}"
        Uses shortened IDs to stay within Telegram's 64 byte callback limit.
        """
        parts = data.split(":")
        if len(parts) != 2:
            await query.answer("Invalid data", show_alert=True)
            return

        short_queue_id = parts[0]
        short_account_id = parts[1]
        chat_id = query.message.chat_id

        # Find full queue_id by prefix match
        queue_item = self.service.queue_repo.get_by_id_prefix(short_queue_id)
        if not queue_item:
            await query.edit_message_caption(caption="⚠️ Queue item not found")
            return

        # Find full account_id by prefix match
        account = self.service.ig_account_service.get_account_by_id_prefix(
            short_account_id
        )
        if not account:
            await query.answer("Account not found", show_alert=True)
            return

        try:
            logger.info(
                f"Switching account for chat {chat_id}: {account.display_name} "
                f"(ID: {str(account.id)[:8]}...)"
            )

            # Switch account
            switched_account = self.service.ig_account_service.switch_account(
                chat_id, str(account.id), user
            )

            logger.info(
                f"Successfully switched to {switched_account.display_name} "
                f"for chat {chat_id}"
            )

            # Log interaction
            self.service.interaction_service.log_callback(
                user_id=str(user.id),
                callback_name="switch_account_from_post",
                context={
                    "queue_item_id": str(queue_item.id),
                    "account_id": str(account.id),
                    "account_username": switched_account.instagram_username,
                },
                telegram_chat_id=chat_id,
                telegram_message_id=query.message.message_id,
            )

            # Show success toast (friendly name)
            await query.answer(f"✅ Switched to {switched_account.display_name}")

            logger.info(
                f"Rebuilding account selector menu for queue {str(queue_item.id)[:8]}..."
            )

            # Stay in account selection menu to show updated checkmark
            # User can click "Back to Post" to return to posting workflow
            await self.handle_post_account_selector(str(queue_item.id), user, query)

            # Batch-update all OTHER pending messages to show the new account
            await self._batch_update_pending_captions(
                chat_id, switched_account, exclude_message_id=query.message.message_id
            )

            logger.info("Successfully rebuilt account selector menu")

        except ValueError as e:
            logger.error(f"ValueError during account switch: {e}", exc_info=True)
            await query.answer(f"Error: {e}", show_alert=True)
        except Exception as e:
            # Catch all other exceptions (DB errors, Telegram errors, etc.)
            logger.error(f"Unexpected error during account switch: {e}", exc_info=True)
            await query.answer(
                f"⚠️ Error switching account: {str(e)[:50]}", show_alert=True
            )

    async def handle_back_to_post(self, short_queue_id: str, user, query):
        """Return to posting workflow without changing account."""
        # Find full queue_id by prefix match
        queue_item = self.service.queue_repo.get_by_id_prefix(short_queue_id)
        if not queue_item:
            await query.edit_message_caption(caption="⚠️ Queue item not found")
            return

        await self.rebuild_posting_workflow(str(queue_item.id), query)

    async def handle_cycle_account(self, queue_id: str, user, query):
        """Cycle to the next Instagram account with a single tap.

        Used when there are 2-3 accounts — replaces the submenu with a
        single-tap cycle button. Switches the active account to the next
        one in the list and rebuilds the current message inline.
        """
        chat_id = query.message.chat_id

        queue_item = await validate_queue_item(self.service, queue_id, query)
        if not queue_item:
            return

        account_data = self.service.ig_account_service.get_accounts_for_display(chat_id)
        accounts = account_data["accounts"]
        active_id = account_data["active_account_id"]

        if len(accounts) < 2:
            await query.answer("Only one account configured", show_alert=False)
            return

        # Find current index and cycle to next
        current_idx = next(
            (i for i, a in enumerate(accounts) if a["id"] == active_id), 0
        )
        next_idx = (current_idx + 1) % len(accounts)
        next_account_id = accounts[next_idx]["id"]

        try:
            switched = self.service.ig_account_service.switch_account(
                chat_id, next_account_id, user
            )

            self.service.interaction_service.log_callback(
                user_id=str(user.id),
                callback_name="cycle_account",
                context={
                    "queue_item_id": str(queue_item.id),
                    "account_id": next_account_id,
                    "account_username": switched.instagram_username,
                },
                telegram_chat_id=chat_id,
                telegram_message_id=query.message.message_id,
            )

            await query.answer(f"📸 {switched.display_name}")

            account_count = len(accounts)

            # Rebuild this message with updated account
            await self.rebuild_posting_workflow(
                str(queue_item.id), query, account_count=account_count
            )

            # Batch-update all other pending messages
            await self._batch_update_pending_captions(
                chat_id,
                switched,
                exclude_message_id=query.message.message_id,
                account_count=account_count,
            )

        except ValueError as e:
            await query.answer(f"Error: {e}", show_alert=True)
        except Exception as e:
            logger.error(f"Error cycling account: {e}", exc_info=True)
            await query.answer(f"⚠️ Error: {str(e)[:50]}", show_alert=True)

    async def rebuild_posting_workflow(
        self, queue_id: str, query, *, account_count: int | None = None
    ):
        """Rebuild the original posting workflow message.

        Used after account selection or when returning from submenu.
        """
        queue_item, media_item = await validate_queue_and_media(
            self.service, queue_id, query
        )
        if not queue_item:
            return

        chat_id = query.message.chat_id

        # Get active account for caption and button
        active_account = self.service.ig_account_service.get_active_account(chat_id)

        # Rebuild caption with current account
        caption = self.service._build_caption(
            media_item, queue_item, active_account=active_account
        )

        # Rebuild keyboard with account selector
        chat_settings = self.service.settings_service.get_settings(chat_id)
        if account_count is None:
            account_count = self.service.ig_account_service.count_active_accounts()
        reply_markup = build_queue_action_keyboard(
            queue_id,
            enable_instagram_api=chat_settings.enable_instagram_api,
            active_account=active_account,
            account_count=account_count,
        )

        await query.edit_message_caption(
            caption=caption, reply_markup=reply_markup, parse_mode="Markdown"
        )

    async def _batch_update_pending_captions(
        self,
        chat_id: int,
        new_account,
        exclude_message_id: int | None = None,
        account_count: int | None = None,
    ):
        """Update captions and keyboards on all pending messages after account switch.

        Edits every active notification in the chat to reflect the new active
        account, so users don't see stale account names on other pending posts.

        Args:
            chat_id: Telegram chat ID
            new_account: The newly active InstagramAccount
            exclude_message_id: Message ID to skip (already updated by caller)
            account_count: Pre-fetched account count (avoids redundant DB query)
        """
        pending_items = self.service.queue_repo.get_pending_with_telegram_message(
            chat_id
        )
        chat_settings = self.service.settings_service.get_settings(chat_id)
        if account_count is None:
            account_count = self.service.ig_account_service.count_active_accounts()
        verbose = self.service._is_verbose(chat_id, chat_settings=chat_settings)
        updated = 0

        for queue_item in pending_items:
            if (
                exclude_message_id is not None
                and queue_item.telegram_message_id == exclude_message_id
            ):
                continue

            try:
                media_item = self.service.media_repo.get_by_id(
                    str(queue_item.media_item_id)
                )
                if not media_item:
                    continue

                caption = self.service._build_caption(
                    media_item,
                    queue_item,
                    verbose=verbose,
                    active_account=new_account,
                )
                reply_markup = build_queue_action_keyboard(
                    str(queue_item.id),
                    enable_instagram_api=chat_settings.enable_instagram_api,
                    active_account=new_account,
                    account_count=account_count,
                )

                await self.service.bot.edit_message_caption(
                    chat_id=chat_id,
                    message_id=queue_item.telegram_message_id,
                    caption=caption,
                    reply_markup=reply_markup,
                    parse_mode="Markdown",
                )
                updated += 1
            except Exception as e:
                logger.debug(
                    f"Could not update caption for queue item "
                    f"{str(queue_item.id)[:8]}: {e}"
                )

        if updated:
            logger.info(
                f"Batch-updated {updated} pending message(s) with new account: "
                f"{new_account.display_name}"
            )
