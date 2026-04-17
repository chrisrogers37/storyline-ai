"""Telegram settings handlers - /settings command, toggles, edits, and schedule management."""

from __future__ import annotations

from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.config.constants import (
    MAX_POSTING_HOUR,
    MAX_POSTS_PER_DAY,
    MIN_POSTING_HOUR,
    MIN_POSTS_PER_DAY,
)
from src.config.settings import settings as app_settings
from src.services.core.telegram_utils import (
    CANCEL_KEYBOARD,
    build_webapp_button,
    clear_settings_edit_state,
)
from src.utils.logger import logger

if TYPE_CHECKING:
    from src.services.core.telegram_service import TelegramService


class TelegramSettingsHandlers:
    """Handles /settings command and all settings-related callbacks.

    Manages toggle buttons, numeric setting edits (posts_per_day, hours),
    and queue management (clear queue).
    Uses composition: receives a TelegramService reference for shared state.
    """

    def __init__(self, service: TelegramService):
        self.service = service

    def build_settings_message_and_keyboard(
        self, chat_id: int, *, user_id: int | None = None, is_private: bool = False
    ):
        """Build the settings message text and inline keyboard.

        Returns (message, reply_markup) tuple. Used by handle_settings,
        refresh_settings_message, and send_settings_message_by_chat_id.

        Args:
            chat_id: Telegram chat ID.
            user_id: Telegram user ID (needed for signed URL tokens in groups).
            is_private: True when called from a private chat (uses WebAppInfo).
        """
        settings_data = self.service.settings_service.get_settings_display(chat_id)
        account_data = self.service.ig_account_service.get_accounts_for_display(chat_id)

        message = "⚙️ *Quick Setup*"

        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ Dry Run" if settings_data["dry_run_mode"] else "Dry Run",
                    callback_data="settings_toggle:dry_run_mode",
                ),
            ],
            [
                InlineKeyboardButton(
                    "✅ Instagram API"
                    if settings_data["enable_instagram_api"]
                    else "Instagram API",
                    callback_data="settings_toggle:enable_instagram_api",
                ),
            ],
            [
                InlineKeyboardButton(
                    "📦 Delivery: ❌ OFF"
                    if settings_data["is_paused"]
                    else "📦 Delivery: ✅ ON",
                    callback_data="settings_toggle:is_paused",
                ),
            ],
            [
                InlineKeyboardButton(
                    f"📸 Default: {account_data['active_account_name']}"
                    if account_data["active_account_id"]
                    else "📸 Set Default Account",
                    callback_data="settings_accounts:select",
                ),
            ],
            [
                InlineKeyboardButton(
                    f"📊 Posts/Day: {settings_data['posts_per_day']}",
                    callback_data="settings_edit:posts_per_day",
                ),
            ],
            [
                InlineKeyboardButton(
                    f"🕐 Hours: {settings_data['posting_hours_start']}:00-{settings_data['posting_hours_end']}:00 UTC",
                    callback_data="settings_edit:hours",
                ),
            ],
            [
                InlineKeyboardButton(
                    f"📝 Verbose: {'ON' if settings_data['show_verbose_notifications'] else 'OFF'}",
                    callback_data="settings_toggle:show_verbose_notifications",
                ),
            ],
            [
                InlineKeyboardButton(
                    f"🔄 Media Sync: {'ON' if settings_data['media_sync_enabled'] else 'OFF'}",
                    callback_data="settings_toggle:media_sync_enabled",
                ),
            ],
        ]

        # "Open Full Settings" button (only if Mini App URL is configured)
        if app_settings.OAUTH_REDIRECT_BASE_URL:
            webapp_url = (
                f"{app_settings.OAUTH_REDIRECT_BASE_URL}/webapp/onboarding"
                f"?chat_id={chat_id}"
            )
            settings_button = build_webapp_button(
                text="🔧 Open Full Settings",
                webapp_url=webapp_url,
                chat_type="private" if is_private else "group",
                chat_id=chat_id,
                user_id=user_id or 0,
            )
            keyboard.append([settings_button])

        keyboard.append(
            [InlineKeyboardButton("❌ Close", callback_data="settings_close")]
        )

        return message, InlineKeyboardMarkup(keyboard)

    async def handle_settings(self, update, context):
        """Handle /settings command - show settings menu with toggle buttons."""
        chat_id = update.effective_chat.id
        user = self.service._get_or_create_user(
            update.effective_user, telegram_chat_id=chat_id
        )

        # Log the actual command used (could be /setup or /settings alias)
        command_text = (
            update.message.text.split()[0] if update.message.text else "/setup"
        )
        self.service.interaction_service.log_command(
            user_id=str(user.id),
            command=command_text,
            telegram_chat_id=chat_id,
            telegram_message_id=update.message.message_id,
        )

        message, reply_markup = self.build_settings_message_and_keyboard(
            chat_id,
            user_id=update.effective_user.id,
            is_private=update.effective_chat.type == "private",
        )

        await update.message.reply_text(
            message, parse_mode="Markdown", reply_markup=reply_markup
        )

    async def handle_settings_toggle(self, setting_name: str, user, query):
        """Handle settings toggle button click."""
        chat_id = query.message.chat_id

        try:
            new_value = self.service.settings_service.toggle_setting(
                chat_id, setting_name, user
            )

            # Log the interaction
            self.service.interaction_service.log_callback(
                user_id=str(user.id),
                callback_name=f"settings_toggle:{setting_name}",
                context={"new_value": new_value},
                telegram_chat_id=chat_id,
                telegram_message_id=query.message.message_id,
            )

            # Refresh the settings display
            await self.refresh_settings_message(query)

        except ValueError as e:
            await query.answer(f"Error: {e}", show_alert=True)
        except Exception as e:
            logger.error(f"Failed to toggle {setting_name}: {e}", exc_info=True)
            await query.answer(
                "⚠️ Failed to update setting. Please try again.",
                show_alert=True,
            )

    async def refresh_settings_message(self, query, show_answer: bool = True):
        """Refresh the settings message with current values."""
        chat_id = query.message.chat_id
        user_id = query.from_user.id if query.from_user else None
        is_private = query.message.chat.type == "private"
        message, reply_markup = self.build_settings_message_and_keyboard(
            chat_id, user_id=user_id, is_private=is_private
        )

        await query.edit_message_text(
            text=message,
            parse_mode="Markdown",
            reply_markup=reply_markup,
        )
        if show_answer:
            await query.answer("Setting updated!")

    async def handle_settings_close(self, query):
        """Handle Close button - delete the settings message."""
        try:
            await query.message.delete()
        except Exception as e:
            logger.debug(f"Could not delete settings message: {e}")
            try:
                await query.answer("Could not close menu")
            except Exception:
                pass

    async def handle_settings_edit_start(self, setting_name: str, user, query, context):
        """Start editing a numeric setting (posts_per_day or hours)."""
        chat_id = query.message.chat_id
        chat_settings = self.service.settings_service.get_settings(chat_id)

        if setting_name == "posts_per_day":
            context.user_data["settings_edit_state"] = "awaiting_posts_per_day"
            context.user_data["settings_edit_chat_id"] = chat_id
            context.user_data["settings_edit_message_id"] = query.message.message_id

            await query.edit_message_text(
                f"📊 *Edit Posts Per Day*\n\n"
                f"Current value: *{chat_settings.posts_per_day}*\n\n"
                f"Enter a number between {MIN_POSTS_PER_DAY} and {MAX_POSTS_PER_DAY}:",
                parse_mode="Markdown",
                reply_markup=CANCEL_KEYBOARD,
            )

        elif setting_name == "hours":
            context.user_data["settings_edit_state"] = "awaiting_hours_start"
            context.user_data["settings_edit_chat_id"] = chat_id
            context.user_data["settings_edit_message_id"] = query.message.message_id

            await query.edit_message_text(
                f"🕐 *Edit Posting Hours*\n\n"
                f"Current window: *{chat_settings.posting_hours_start}:00 - {chat_settings.posting_hours_end}:00 UTC*\n\n"
                f"Enter the *start hour* ({MIN_POSTING_HOUR}-{MAX_POSTING_HOUR} UTC):",
                parse_mode="Markdown",
                reply_markup=CANCEL_KEYBOARD,
            )

    async def handle_settings_edit_message(self, update, context):
        """Handle user input for editing settings."""
        if "settings_edit_state" not in context.user_data:
            return False

        state = context.user_data["settings_edit_state"]
        chat_id = context.user_data.get("settings_edit_chat_id")
        message_text = update.message.text.strip()
        user = self.service._get_or_create_user(update.effective_user)

        # Delete user's message to keep chat clean (best-effort)
        try:
            await update.message.delete()
        except Exception as e:
            logger.debug(f"Could not delete user settings input message: {e}")

        if state == "awaiting_posts_per_day":
            try:
                value = int(message_text)
                if not MIN_POSTS_PER_DAY <= value <= MAX_POSTS_PER_DAY:
                    raise ValueError("Out of range")

                # Update the setting
                self.service.settings_service.update_setting(
                    chat_id, "posts_per_day", value, user
                )

                # Clear state and refresh settings
                clear_settings_edit_state(context)

                # Rebuild settings message
                await self.send_settings_message_by_chat_id(chat_id, context)

                logger.info(
                    f"User {self.service._get_display_name(user)} updated posts_per_day to {value}"
                )

            except ValueError:
                # Show error, keep waiting for valid input
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=context.user_data.get("settings_edit_message_id"),
                    text=(
                        "📊 *Edit Posts Per Day*\n\n"
                        f"❌ Invalid input. Please enter a number between {MIN_POSTS_PER_DAY} and {MAX_POSTS_PER_DAY}:"
                    ),
                    parse_mode="Markdown",
                    reply_markup=CANCEL_KEYBOARD,
                )

            return True

        elif state == "awaiting_hours_start":
            try:
                value = int(message_text)
                if not MIN_POSTING_HOUR <= value <= MAX_POSTING_HOUR:
                    raise ValueError("Out of range")

                # Store start hour, ask for end hour
                context.user_data["settings_edit_hours_start"] = value
                context.user_data["settings_edit_state"] = "awaiting_hours_end"

                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=context.user_data.get("settings_edit_message_id"),
                    text=(
                        f"🕐 *Edit Posting Hours*\n\n"
                        f"Start hour: *{value}:00 UTC*\n\n"
                        f"Enter the *end hour* ({MIN_POSTING_HOUR}-{MAX_POSTING_HOUR} UTC):"
                    ),
                    parse_mode="Markdown",
                    reply_markup=CANCEL_KEYBOARD,
                )

            except ValueError:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=context.user_data.get("settings_edit_message_id"),
                    text=(
                        "🕐 *Edit Posting Hours*\n\n"
                        f"❌ Invalid input. Please enter a number between {MIN_POSTING_HOUR} and {MAX_POSTING_HOUR}:"
                    ),
                    parse_mode="Markdown",
                    reply_markup=CANCEL_KEYBOARD,
                )

            return True

        elif state == "awaiting_hours_end":
            try:
                value = int(message_text)
                if not MIN_POSTING_HOUR <= value <= MAX_POSTING_HOUR:
                    raise ValueError("Out of range")

                start_hour = context.user_data.get("settings_edit_hours_start")

                # Update both settings
                self.service.settings_service.update_setting(
                    chat_id, "posting_hours_start", start_hour, user
                )
                self.service.settings_service.update_setting(
                    chat_id, "posting_hours_end", value, user
                )

                # Clear state
                clear_settings_edit_state(context)

                # Rebuild settings message
                await self.send_settings_message_by_chat_id(chat_id, context)

                logger.info(
                    f"User {self.service._get_display_name(user)} updated posting hours to {start_hour}:00-{value}:00 UTC"
                )

            except ValueError:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=context.user_data.get("settings_edit_message_id"),
                    text=(
                        f"🕐 *Edit Posting Hours*\n\n"
                        f"Start hour: *{context.user_data.get('settings_edit_hours_start')}:00 UTC*\n\n"
                        f"❌ Invalid input. Please enter a number between {MIN_POSTING_HOUR} and {MAX_POSTING_HOUR}:"
                    ),
                    parse_mode="Markdown",
                    reply_markup=CANCEL_KEYBOARD,
                )

            return True

        return False

    async def handle_settings_edit_cancel(self, query, context):
        """Cancel settings edit and return to settings menu."""
        # Clear edit state
        clear_settings_edit_state(context)

        # Refresh settings message
        await self.refresh_settings_message(query, show_answer=False)
        await query.answer("Cancelled")

    async def send_settings_message_by_chat_id(self, chat_id: int, context):
        """Send a fresh settings message to a chat (used after editing)."""
        message, reply_markup = self.build_settings_message_and_keyboard(chat_id)

        await context.bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode="Markdown",
            reply_markup=reply_markup,
        )

    async def handle_schedule_action(self, action: str, user, query):
        """Handle schedule management actions.

        With the JIT scheduler, there is no pre-populated schedule to
        extend.  The only action is clearing in-flight queue items.
        """
        chat_id = query.message.chat_id

        if action == "clear_queue":
            # Confirm before clearing (destructive action)
            keyboard = [
                [
                    InlineKeyboardButton(
                        "✅ Yes, Clear Queue",
                        callback_data="schedule_confirm:clear_queue",
                    ),
                    InlineKeyboardButton(
                        "❌ Cancel", callback_data="schedule_confirm:cancel"
                    ),
                ]
            ]

            chat_settings = self.service.settings_service.get_settings(chat_id)
            chat_settings_id = str(chat_settings.id) if chat_settings else None
            pending_count = self.service.queue_repo.count_pending(
                chat_settings_id=chat_settings_id
            )

            await query.edit_message_text(
                f"⚠️ *Clear Queue?*\n\n"
                f"This will remove {pending_count} in-flight item(s) "
                f"waiting for team action.\n\n"
                f"The scheduler will continue selecting new posts automatically.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            await query.answer()

        else:
            # Unknown action — JIT scheduler is automatic
            await query.answer(
                "Schedule is managed automatically by the JIT scheduler.",
                show_alert=True,
            )

    async def handle_schedule_confirm(self, action: str, user, query):
        """Handle schedule confirmation callbacks."""
        chat_id = query.message.chat_id

        if action == "cancel":
            # Return to settings menu
            await self.refresh_settings_message(query, show_answer=False)
            await query.answer("Cancelled")
            return

        if action == "clear_queue":
            await query.answer("Clearing queue...")

            chat_settings = self.service.settings_service.get_settings(chat_id)
            chat_settings_id = str(chat_settings.id) if chat_settings else None
            cleared = self.service.queue_repo.delete_all_pending(
                chat_settings_id=chat_settings_id
            )

            self.service.interaction_service.log_callback(
                user_id=str(user.id),
                callback_name="schedule_action:clear_queue",
                context={"cleared": cleared},
                telegram_chat_id=chat_id,
                telegram_message_id=query.message.message_id,
            )

            logger.info(
                f"Queue cleared by {self.service._get_display_name(user)}: "
                f"{cleared} items"
            )

            await query.answer(f"Cleared {cleared} items!")
            await self.refresh_settings_message(query, show_answer=False)
