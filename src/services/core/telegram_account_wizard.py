"""Multi-step wizard for adding Instagram accounts via Telegram."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.services.core.telegram_utils import (
    build_account_management_keyboard,
    cleanup_conversation_messages,
    clear_add_account_state,
)
from src.utils.logger import logger

if TYPE_CHECKING:
    from src.services.core.telegram_accounts import TelegramAccountHandlers

ADD_ACCOUNT_CANCEL_KEYBOARD = InlineKeyboardMarkup(
    [[InlineKeyboardButton("❌ Cancel", callback_data="account_add_cancel:cancel")]]
)


class TelegramAccountWizard:
    """Multi-step wizard for adding Instagram accounts via Telegram.

    Manages the three-step conversation flow:
    1. Collect display name
    2. Validate numeric Instagram account ID
    3. Validate access token with Instagram API, create/update account

    Uses composition: receives a TelegramAccountHandlers reference
    for access to the parent TelegramService and shared state.
    """

    def __init__(self, accounts_handler: TelegramAccountHandlers):
        self.handler = accounts_handler
        self.service = accounts_handler.service

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

        messages_to_delete = context.user_data.get("add_account_messages", [])
        await cleanup_conversation_messages(
            context.bot,
            chat_id,
            messages_to_delete,
            exclude_id=query.message.message_id,
        )

        clear_add_account_state(context)
        await query.answer("Cancelled")
        await self.handler.handle_account_selection_menu(user, query)

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

            messages_to_delete = context.user_data.get("add_account_messages", [])
            await cleanup_conversation_messages(
                context.bot, chat_id, messages_to_delete
            )
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
            keyboard = build_account_management_keyboard(account_data)

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
                reply_markup=InlineKeyboardMarkup(keyboard),
            )

        except Exception as e:
            await self._handle_token_error(context, chat_id, verifying_msg, e)

        return True

    # =========================================================================
    # Shared helpers (private)
    # =========================================================================

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

        messages_to_delete = context.user_data.get("add_account_messages", [])
        await cleanup_conversation_messages(context.bot, chat_id, messages_to_delete)
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
