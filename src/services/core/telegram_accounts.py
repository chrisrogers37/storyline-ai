"""Telegram account handlers - Instagram account management and inline account selection."""

from __future__ import annotations

from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.utils.logger import logger

if TYPE_CHECKING:
    from src.services.core.telegram_service import TelegramService


class TelegramAccountHandlers:
    """Handles Instagram account management in Telegram.

    Manages account selection menus, add/remove flows, inline account
    switching from posting workflow, and the back-to-post rebuild.
    Uses composition: receives a TelegramService reference for shared state.
    """

    def __init__(self, service: TelegramService):
        self.service = service

    async def handle_account_selection_menu(self, user, query):
        """Show Instagram account configuration menu."""
        chat_id = query.message.chat_id
        account_data = self.service.ig_account_service.get_accounts_for_display(chat_id)

        # Build account management keyboard
        keyboard = []

        # List existing accounts with select option
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

        # Action buttons row
        keyboard.append(
            [
                InlineKeyboardButton(
                    "➕ Add Account", callback_data="accounts_config:add"
                ),
            ]
        )

        # Only show remove option if there are accounts
        if account_data["accounts"]:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "🗑️ Remove Account", callback_data="accounts_config:remove"
                    ),
                ]
            )

        # Back button
        keyboard.append(
            [
                InlineKeyboardButton(
                    "↩️ Back to Settings", callback_data="settings_accounts:back"
                )
            ]
        )

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
        """Handle text messages during add account conversation."""
        if "add_account_state" not in context.user_data:
            return False  # Not in add account flow

        state = context.user_data["add_account_state"]
        user = self.service._get_or_create_user(update.effective_user)
        chat_id = update.effective_chat.id
        message_text = update.message.text.strip()

        if state == "awaiting_display_name":
            # Track user's message for cleanup
            context.user_data["add_account_messages"].append(update.message.message_id)

            # Save display name and ask for account ID
            context.user_data["add_account_data"]["display_name"] = message_text
            context.user_data["add_account_state"] = "awaiting_account_id"

            keyboard = [
                [
                    InlineKeyboardButton(
                        "❌ Cancel", callback_data="account_add_cancel:cancel"
                    )
                ]
            ]

            reply = await update.message.reply_text(
                "➕ *Add Instagram Account*\n\n"
                "*Step 2 of 3: Instagram Account ID*\n\n"
                f"Display name: `{message_text}`\n\n"
                "Enter the numeric Account ID from Meta Business Suite:\n\n"
                "_Found in: Settings → Business Assets → Instagram Accounts_\n\n"
                "Reply with the ID",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            # Track bot's reply for cleanup
            context.user_data["add_account_messages"].append(reply.message_id)
            return True

        elif state == "awaiting_account_id":
            # Track user's message for cleanup
            context.user_data["add_account_messages"].append(update.message.message_id)

            # Validate it's numeric
            if not message_text.isdigit():
                reply = await update.message.reply_text(
                    "⚠️ Account ID must be numeric. Please try again:",
                    parse_mode="Markdown",
                )
                context.user_data["add_account_messages"].append(reply.message_id)
                return True

            context.user_data["add_account_data"]["account_id"] = message_text
            context.user_data["add_account_state"] = "awaiting_token"

            keyboard = [
                [
                    InlineKeyboardButton(
                        "❌ Cancel", callback_data="account_add_cancel:cancel"
                    )
                ]
            ]

            reply = await update.message.reply_text(
                "➕ *Add Instagram Account*\n\n"
                "*Step 3 of 3: Access Token*\n\n"
                f"Display name: `{context.user_data['add_account_data']['display_name']}`\n"
                f"Account ID: `{message_text}`\n\n"
                "⚠️ *Security*: Delete your token message after submitting.\n"
                "(Bots cannot delete user messages in private chats)\n\n"
                "Paste your Instagram Graph API access token:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            context.user_data["add_account_messages"].append(reply.message_id)
            return True

        elif state == "awaiting_token":
            # Delete the message with the token immediately for security
            try:
                await update.message.delete()
            except Exception as e:
                logger.warning(f"Could not delete token message: {e}")

            # Attempt to create the account
            data = context.user_data["add_account_data"]
            access_token = message_text

            # First, validate the token by fetching account info from Instagram API
            try:
                import httpx

                # Send a "verifying" message
                verifying_msg = await context.bot.send_message(
                    chat_id=chat_id,
                    text="⏳ Verifying credentials with Instagram API...",
                    parse_mode="Markdown",
                )

                # Fetch username from Instagram API
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"https://graph.facebook.com/v18.0/{data['account_id']}",
                        params={"fields": "username", "access_token": access_token},
                        timeout=30.0,
                    )

                    if response.status_code != 200:
                        error_data = response.json()
                        error_msg = error_data.get("error", {}).get(
                            "message", "Unknown error"
                        )
                        raise ValueError(f"Instagram API error: {error_msg}")

                    api_data = response.json()
                    username = api_data.get("username")

                    if not username:
                        raise ValueError("Could not fetch username from Instagram API")

                # Check if account already exists
                existing_account = (
                    self.service.ig_account_service.get_account_by_instagram_id(
                        data["account_id"]
                    )
                )

                if existing_account:
                    # Update the existing account's token
                    account = self.service.ig_account_service.update_account_token(
                        instagram_account_id=data["account_id"],
                        access_token=access_token,
                        instagram_username=username,
                        user=user,
                        set_as_active=True,
                        telegram_chat_id=chat_id,
                    )
                    was_update = True
                else:
                    # Create the account with fetched username
                    account = self.service.ig_account_service.add_account(
                        display_name=data["display_name"],
                        instagram_account_id=data["account_id"],
                        instagram_username=username,
                        access_token=access_token,
                        user=user,
                        set_as_active=True,
                        telegram_chat_id=chat_id,
                    )
                    was_update = False

                # Delete verifying message
                try:
                    await verifying_msg.delete()
                except Exception:
                    pass

                # Delete all tracked conversation messages
                messages_to_delete = context.user_data.get("add_account_messages", [])
                for msg_id in messages_to_delete:
                    try:
                        await context.bot.delete_message(
                            chat_id=chat_id, message_id=msg_id
                        )
                    except Exception:
                        pass  # Message may already be deleted

                # Clear conversation state
                context.user_data.pop("add_account_state", None)
                context.user_data.pop("add_account_data", None)
                context.user_data.pop("add_account_chat_id", None)
                context.user_data.pop("add_account_messages", None)

                # Log interaction
                self.service.interaction_service.log_callback(
                    user_id=str(user.id),
                    callback_name="update_account_token"
                    if was_update
                    else "add_account",
                    context={
                        "account_id": str(account.id),
                        "display_name": account.display_name,
                        "username": account.instagram_username,
                        "was_update": was_update,
                    },
                    telegram_chat_id=chat_id,
                    telegram_message_id=update.message.message_id,
                )

                action = "updated token for" if was_update else "added"
                logger.info(
                    f"User {self.service._get_display_name(user)} {action} Instagram account: "
                    f"{account.display_name} (@{account.instagram_username})"
                )

                # Show Configure Accounts menu with success message
                account_data = self.service.ig_account_service.get_accounts_for_display(
                    chat_id
                )
                keyboard = []

                for acc in account_data["accounts"]:
                    is_active = acc["id"] == account_data["active_account_id"]
                    label = f"{'✅ ' if is_active else '   '}{acc['display_name']}"
                    if acc["username"]:
                        label += f" (@{acc['username']})"
                    keyboard.append(
                        [
                            InlineKeyboardButton(
                                label,
                                callback_data=f"switch_account:{acc['id']}",
                            )
                        ]
                    )

                keyboard.append(
                    [
                        InlineKeyboardButton(
                            "➕ Add Account", callback_data="accounts_config:add"
                        ),
                    ]
                )
                if account_data["accounts"]:
                    keyboard.append(
                        [
                            InlineKeyboardButton(
                                "🗑️ Remove Account",
                                callback_data="accounts_config:remove",
                            ),
                        ]
                    )
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            "↩️ Back to Settings",
                            callback_data="settings_accounts:back",
                        )
                    ]
                )

                # Build success message with security warning
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
                # Delete verifying message if it exists
                try:
                    await verifying_msg.delete()
                except Exception:
                    pass

                # Delete all tracked conversation messages
                messages_to_delete = context.user_data.get("add_account_messages", [])
                for msg_id in messages_to_delete:
                    try:
                        await context.bot.delete_message(
                            chat_id=chat_id, message_id=msg_id
                        )
                    except Exception:
                        pass

                # Clear state on error
                context.user_data.pop("add_account_state", None)
                context.user_data.pop("add_account_data", None)
                context.user_data.pop("add_account_chat_id", None)
                context.user_data.pop("add_account_messages", None)

                keyboard = [
                    [
                        InlineKeyboardButton(
                            "🔄 Try Again", callback_data="accounts_config:add"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "↩️ Back to Settings",
                            callback_data="settings_accounts:back",
                        )
                    ],
                ]

                error_msg = str(e)
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

                logger.error(f"Failed to add Instagram account: {e}")

            return True

        return False

    async def handle_add_account_cancel(self, user, query, context):
        """Cancel add account flow."""
        chat_id = query.message.chat_id

        # Delete all tracked conversation messages (except the current one which we'll edit)
        messages_to_delete = context.user_data.get("add_account_messages", [])
        current_msg_id = query.message.message_id
        for msg_id in messages_to_delete:
            if msg_id != current_msg_id:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                except Exception:
                    pass

        context.user_data.pop("add_account_state", None)
        context.user_data.pop("add_account_data", None)
        context.user_data.pop("add_account_chat_id", None)
        context.user_data.pop("add_account_messages", None)

        await query.answer("Cancelled")
        await self.handle_account_selection_menu(user, query)

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
        queue_item = self.service.queue_repo.get_by_id(queue_id)
        if not queue_item:
            await query.edit_message_caption(caption="⚠️ Queue item not found")
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
            short_queue_id = queue_id[:8] if len(queue_id) > 8 else queue_id
            short_account_id = acc["id"][:8] if len(acc["id"]) > 8 else acc["id"]
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
        short_queue_id = queue_id[:8] if len(queue_id) > 8 else queue_id
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
        queue_item = self.service.queue_repo.get_by_id(queue_id)
        if not queue_item:
            await query.edit_message_caption(caption="⚠️ Queue item not found")
            return

        media_item = self.service.media_repo.get_by_id(str(queue_item.media_item_id))
        if not media_item:
            await query.edit_message_caption(caption="⚠️ Media item not found")
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
        keyboard = []

        if chat_settings.enable_instagram_api:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "🤖 Auto Post to Instagram",
                        callback_data=f"autopost:{queue_id}",
                    ),
                ]
            )

        # Status action buttons (grouped together)
        keyboard.extend(
            [
                [
                    InlineKeyboardButton(
                        "✅ Posted", callback_data=f"posted:{queue_id}"
                    ),
                    InlineKeyboardButton("⏭️ Skip", callback_data=f"skip:{queue_id}"),
                ],
                [
                    InlineKeyboardButton(
                        "🚫 Reject", callback_data=f"reject:{queue_id}"
                    ),
                ],
            ]
        )

        # Instagram-related buttons (grouped together)
        account_label = (
            f"📸 {active_account.display_name}" if active_account else "📸 No Account"
        )
        keyboard.extend(
            [
                [
                    InlineKeyboardButton(
                        account_label,
                        callback_data=f"select_account:{queue_id}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "📱 Open Instagram", url="https://www.instagram.com/"
                    ),
                ],
            ]
        )

        await query.edit_message_caption(
            caption=caption, reply_markup=InlineKeyboardMarkup(keyboard)
        )
