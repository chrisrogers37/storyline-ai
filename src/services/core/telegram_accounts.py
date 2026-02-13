"""Telegram account handlers - Instagram account management and inline account selection."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.services.core.telegram_utils import (
    build_queue_action_keyboard,
    clear_add_account_state,
    validate_queue_and_media,
    validate_queue_item,
)
from src.utils.logger import logger

if TYPE_CHECKING:
    from src.services.core.telegram_service import TelegramService

ADD_ACCOUNT_CANCEL_KEYBOARD = InlineKeyboardMarkup(
    [[InlineKeyboardButton("❌ Cancel", callback_data="account_add_cancel:cancel")]]
)


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
        reply_markup = self._build_account_config_keyboard(account_data)

        await query.edit_message_text(
            "📸 *Choose Default Account*\n\n"
            "Select an account to set as default, or add/remove accounts.",
            parse_mode="Markdown",
            reply_markup=reply_markup,
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

    async def handle_add_account_start(self, user, query, context):
        """Start the add account conversation flow."""
        chat_id = query.message.chat_id

        # Initialize conversation state
        context.user_data["add_account_state"] = "awaiting_display_name"
        context.user_data["add_account_chat_id"] = chat_id
        context.user_data["add_account_data"] = {}
        # Track message IDs to delete later
        context.user_data["add_account_messages"] = [query.message.message_id]

        keyboard = [
            [
                InlineKeyboardButton(
                    "❌ Cancel", callback_data="account_add_cancel:cancel"
                )
            ]
        ]

        await query.edit_message_text(
            "➕ *Add Instagram Account*\n\n"
            "*Step 1 of 3: Display Name*\n\n"
            "Enter a friendly name for this account:\n"
            "(e.g., 'Main Account', 'Brand Account')\n\n"
            "_Reply with the name_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        await query.answer()

        logger.info(
            f"User {self.service._get_display_name(user)} started add account flow"
        )

    async def handle_add_account_message(self, update, context):
        """Handle text messages during add account conversation.

        Dispatches to the appropriate step handler based on conversation state.
        """
        if "add_account_state" not in context.user_data:
            return False

        state = context.user_data["add_account_state"]
        message_text = update.message.text.strip()

        if state == "awaiting_display_name":
            return await self._handle_display_name_input(update, context, message_text)
        elif state == "awaiting_account_id":
            return await self._handle_account_id_input(update, context, message_text)
        elif state == "awaiting_token":
            return await self._handle_token_input(update, context, message_text)

        return False

    async def handle_add_account_cancel(self, user, query, context):
        """Cancel add account flow."""
        chat_id = query.message.chat_id

        await self._cleanup_conversation_messages(
            context, chat_id, exclude_message_id=query.message.message_id
        )

        clear_add_account_state(context)
        await query.answer("Cancelled")
        await self.handle_account_selection_menu(user, query)

    # =========================================================================
    # Add-account step handlers (private)
    # =========================================================================

    async def _handle_display_name_input(
        self, update, context, message_text: str
    ) -> bool:
        """Handle Step 1: display name input during add-account flow."""
        context.user_data["add_account_messages"].append(update.message.message_id)

        context.user_data["add_account_data"]["display_name"] = message_text
        context.user_data["add_account_state"] = "awaiting_account_id"

        reply = await update.message.reply_text(
            "➕ *Add Instagram Account*\n\n"
            "*Step 2 of 3: Instagram Account ID*\n\n"
            f"Display name: `{message_text}`\n\n"
            "Enter the numeric Account ID from Meta Business Suite:\n\n"
            "_Found in: Settings → Business Assets → Instagram Accounts_\n\n"
            "Reply with the ID",
            parse_mode="Markdown",
            reply_markup=ADD_ACCOUNT_CANCEL_KEYBOARD,
        )
        context.user_data["add_account_messages"].append(reply.message_id)
        return True

    async def _handle_account_id_input(
        self, update, context, message_text: str
    ) -> bool:
        """Handle Step 2: account ID input during add-account flow."""
        context.user_data["add_account_messages"].append(update.message.message_id)

        if not message_text.isdigit():
            reply = await update.message.reply_text(
                "⚠️ Account ID must be numeric. Please try again:",
                parse_mode="Markdown",
            )
            context.user_data["add_account_messages"].append(reply.message_id)
            return True

        context.user_data["add_account_data"]["account_id"] = message_text
        context.user_data["add_account_state"] = "awaiting_token"

        reply = await update.message.reply_text(
            "➕ *Add Instagram Account*\n\n"
            "*Step 3 of 3: Access Token*\n\n"
            f"Display name: `{context.user_data['add_account_data']['display_name']}`\n"
            f"Account ID: `{message_text}`\n\n"
            "⚠️ *Security*: Delete your token message after submitting.\n"
            "(Bots cannot delete user messages in private chats)\n\n"
            "Paste your Instagram Graph API access token:",
            parse_mode="Markdown",
            reply_markup=ADD_ACCOUNT_CANCEL_KEYBOARD,
        )
        context.user_data["add_account_messages"].append(reply.message_id)
        return True

    async def _handle_token_input(self, update, context, message_text: str) -> bool:
        """Handle Step 3: access token input during add-account flow."""
        chat_id = update.effective_chat.id
        user = self.service._get_or_create_user(update.effective_user)

        # Delete the token message immediately for security
        try:
            await update.message.delete()
        except Exception as delete_err:
            logger.warning(f"Could not delete token message: {delete_err}")

        data = context.user_data["add_account_data"]
        verifying_msg = None

        try:
            verifying_msg = await context.bot.send_message(
                chat_id=chat_id,
                text="⏳ Verifying credentials with Instagram API...",
                parse_mode="Markdown",
            )

            account, was_update = await self._validate_instagram_credentials(
                data, message_text, user, chat_id
            )

            # Delete verifying message
            if verifying_msg:
                try:
                    await verifying_msg.delete()
                except Exception:
                    pass

            await self._cleanup_conversation_messages(context, chat_id)
            clear_add_account_state(context)

            # Log interaction
            action = "update_account_token" if was_update else "add_account"
            self.service.interaction_service.log_callback(
                user_id=str(user.id),
                callback_name=action,
                context={
                    "account_id": str(account.id),
                    "display_name": account.display_name,
                    "username": account.instagram_username,
                    "was_update": was_update,
                },
                telegram_chat_id=chat_id,
                telegram_message_id=update.message.message_id,
            )

            action_label = "updated token for" if was_update else "added"
            logger.info(
                f"User {self.service._get_display_name(user)} {action_label} Instagram account: "
                f"{account.display_name} (@{account.instagram_username})"
            )

            # Show success with account config keyboard
            account_data = self.service.ig_account_service.get_accounts_for_display(
                chat_id
            )
            reply_markup = self._build_account_config_keyboard(account_data)

            if was_update:
                action_msg = f"✅ *Updated token for @{account.instagram_username}*"
            else:
                action_msg = f"✅ *Added @{account.instagram_username}*"

            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"{action_msg}\n\n"
                    "⚠️ *Security Note:* Please delete your messages above "
                    "that contain the Account ID and Access Token. "
                    "Bots cannot delete user messages in private chats.\n\n"
                    "📸 *Configure Instagram Accounts*\n\n"
                    "Select an account to make it active, or add/remove accounts."
                ),
                parse_mode="Markdown",
                reply_markup=reply_markup,
            )

        except Exception as e:
            await self._handle_token_error(context, chat_id, verifying_msg, e)

        return True

    # =========================================================================
    # Shared helpers (private)
    # =========================================================================

    async def _cleanup_conversation_messages(
        self, context, chat_id: int, exclude_message_id: int | None = None
    ) -> None:
        """Delete tracked add-account conversation messages (best-effort).

        Args:
            context: Telegram CallbackContext with user_data containing message IDs.
            chat_id: Telegram chat ID to delete messages from.
            exclude_message_id: Optional message ID to skip (e.g., one being edited).
        """
        messages_to_delete = context.user_data.get("add_account_messages", [])
        for msg_id in messages_to_delete:
            if exclude_message_id is not None and msg_id == exclude_message_id:
                continue
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except Exception as e:
                logger.debug(f"Could not delete conversation message {msg_id}: {e}")

    def _build_account_config_keyboard(
        self, account_data: dict
    ) -> InlineKeyboardMarkup:
        """Build the account list keyboard for the config menu.

        Args:
            account_data: Dict from ig_account_service.get_accounts_for_display().

        Returns:
            InlineKeyboardMarkup ready for use in Telegram messages.
        """
        keyboard = []

        if account_data["accounts"]:
            for account in account_data["accounts"]:
                is_active = account["id"] == account_data["active_account_id"]
                label = f"{'✅ ' if is_active else '   '}{account['display_name']}"
                if account["username"]:
                    label += f" (@{account['username']})"
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            label, callback_data=f"switch_account:{account['id']}"
                        )
                    ]
                )
        else:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "No accounts configured", callback_data="accounts_config:noop"
                    )
                ]
            )

        keyboard.append(
            [
                InlineKeyboardButton(
                    "➕ Add Account", callback_data="accounts_config:add"
                )
            ]
        )

        if account_data["accounts"]:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "🗑️ Remove Account", callback_data="accounts_config:remove"
                    )
                ]
            )

        keyboard.append(
            [
                InlineKeyboardButton(
                    "↩️ Back to Settings", callback_data="settings_accounts:back"
                )
            ]
        )

        return InlineKeyboardMarkup(keyboard)

    async def _validate_instagram_credentials(
        self, data: dict, access_token: str, user, chat_id: int
    ) -> tuple:
        """Validate credentials with Instagram API and create/update account.

        Returns:
            Tuple of (account, was_update).

        Raises:
            ValueError: If the API returns an error.
            httpx.HTTPError: On network failures.
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://graph.facebook.com/v18.0/{data['account_id']}",
                params={"fields": "username", "access_token": access_token},
                timeout=30.0,
            )

            if response.status_code != 200:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", "Unknown error")
                raise ValueError(f"Instagram API error: {error_msg}")

            api_data = response.json()
            username = api_data.get("username")

            if not username:
                raise ValueError("Could not fetch username from Instagram API")

        existing = self.service.ig_account_service.get_account_by_instagram_id(
            data["account_id"]
        )

        if existing:
            account = self.service.ig_account_service.update_account_token(
                instagram_account_id=data["account_id"],
                access_token=access_token,
                instagram_username=username,
                user=user,
                set_as_active=True,
                telegram_chat_id=chat_id,
            )
            return account, True
        else:
            account = self.service.ig_account_service.add_account(
                display_name=data["display_name"],
                instagram_account_id=data["account_id"],
                instagram_username=username,
                access_token=access_token,
                user=user,
                set_as_active=True,
                telegram_chat_id=chat_id,
            )
            return account, False

    async def _handle_token_error(
        self, context, chat_id: int, verifying_msg, error: Exception
    ) -> None:
        """Handle errors during token validation and account creation."""
        # Delete verifying message (best-effort)
        if verifying_msg:
            try:
                await verifying_msg.delete()
            except Exception as delete_err:
                logger.debug(f"Could not delete verifying message: {delete_err}")

        await self._cleanup_conversation_messages(context, chat_id)
        clear_add_account_state(context)

        keyboard = [
            [InlineKeyboardButton("🔄 Try Again", callback_data="accounts_config:add")],
            [
                InlineKeyboardButton(
                    "↩️ Back to Settings", callback_data="settings_accounts:back"
                )
            ],
        ]

        error_msg = str(error)
        if "Invalid OAuth" in error_msg or "access token" in error_msg.lower():
            error_msg = "Invalid or expired access token. Please check your token and try again."

        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"❌ *Failed to add account*\n\n{error_msg}\n\n"
                "⚠️ *Security Note:* Please delete your messages above "
                "that contain sensitive data (Account ID, Access Token)."
            ),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

        logger.error(f"Failed to add Instagram account: {error}")

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

    async def rebuild_posting_workflow(self, queue_id: str, query):
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
        reply_markup = build_queue_action_keyboard(
            queue_id,
            enable_instagram_api=chat_settings.enable_instagram_api,
            active_account=active_account,
        )

        await query.edit_message_caption(caption=caption, reply_markup=reply_markup)
