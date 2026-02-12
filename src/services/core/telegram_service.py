"""Telegram service - bot operations and callbacks."""

import asyncio

from telegram import Bot, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from src.services.base_service import BaseService
from src.repositories.user_repository import UserRepository
from src.repositories.queue_repository import QueueRepository
from src.repositories.history_repository import HistoryRepository
from src.repositories.media_repository import MediaRepository
from src.repositories.lock_repository import LockRepository
from src.services.core.media_lock import MediaLockService
from src.services.core.interaction_service import InteractionService
from src.services.core.settings_service import SettingsService
from src.services.core.instagram_account_service import InstagramAccountService
from src.config.settings import settings
from src.utils.logger import logger
from src import __version__
from datetime import datetime
import re

# Imported after class definition to avoid circular imports at module level
# TelegramCommandHandlers, TelegramCallbackHandlers, TelegramAutopostHandler,
# TelegramSettingsHandlers, TelegramAccountHandlers are imported inside initialize()


def _escape_markdown(text: str) -> str:
    """Escape Telegram Markdown special characters in text."""
    # For Telegram's Markdown mode, escape: _ * ` [
    return re.sub(r"([_*`\[])", r"\\\1", text)


def _extract_button_labels(reply_markup) -> list:
    """Extract button labels from an InlineKeyboardMarkup for logging."""
    if not reply_markup or not hasattr(reply_markup, "inline_keyboard"):
        return []
    labels = []
    for row in reply_markup.inline_keyboard:
        for button in row:
            labels.append(button.text)
    return labels


class TelegramService(BaseService):
    """All Telegram bot operations."""

    def __init__(self):
        super().__init__()
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.channel_id = settings.TELEGRAM_CHANNEL_ID
        self.user_repo = UserRepository()
        self.queue_repo = QueueRepository()
        self.history_repo = HistoryRepository()
        self.media_repo = MediaRepository()
        self.lock_repo = LockRepository()
        self.lock_service = MediaLockService()
        self.interaction_service = InteractionService()
        self.settings_service = SettingsService()
        self.ig_account_service = InstagramAccountService()
        self.bot = None
        self.application = None
        self._operation_locks: dict[str, asyncio.Lock] = {}
        self._cancel_flags: dict[str, asyncio.Event] = {}
        self._callback_dispatch: dict = {}

    def get_operation_lock(self, queue_id: str) -> asyncio.Lock:
        """Get or create an asyncio lock for a queue item."""
        if queue_id not in self._operation_locks:
            self._operation_locks[queue_id] = asyncio.Lock()
        return self._operation_locks[queue_id]

    def get_cancel_flag(self, queue_id: str) -> asyncio.Event:
        """Get or create a cancellation flag for a queue item."""
        if queue_id not in self._cancel_flags:
            self._cancel_flags[queue_id] = asyncio.Event()
        return self._cancel_flags[queue_id]

    def cleanup_operation_state(self, queue_id: str):
        """Clean up lock and cancel flag after operation completes."""
        self._operation_locks.pop(queue_id, None)
        self._cancel_flags.pop(queue_id, None)

    @property
    def is_paused(self) -> bool:
        """Check if bot posting is paused (from database)."""
        chat_settings = self.settings_service.get_settings(self.channel_id)
        return chat_settings.is_paused

    def set_paused(self, paused: bool, user=None):
        """Set pause state (persisted to database)."""
        if self.is_paused != paused:
            self.settings_service.toggle_setting(self.channel_id, "is_paused", user)

    async def initialize(self):
        """Initialize Telegram bot."""
        self.bot = Bot(token=self.bot_token)
        self.application = Application.builder().token(self.bot_token).build()

        # Initialize sub-handlers (after bot/application are created)
        from src.services.core.telegram_commands import TelegramCommandHandlers
        from src.services.core.telegram_callbacks import TelegramCallbackHandlers
        from src.services.core.telegram_autopost import TelegramAutopostHandler
        from src.services.core.telegram_settings import TelegramSettingsHandlers
        from src.services.core.telegram_accounts import TelegramAccountHandlers

        self.commands = TelegramCommandHandlers(self)
        self.callbacks = TelegramCallbackHandlers(self)
        self.autopost = TelegramAutopostHandler(self)
        self.settings_handler = TelegramSettingsHandlers(self)
        self.accounts = TelegramAccountHandlers(self)

        # Build callback dispatch table (must be after handlers are initialized)
        self._callback_dispatch = self._build_callback_dispatch_table()

        # Register command handlers
        command_map = {
            "start": self.commands.handle_start,
            "status": self.commands.handle_status,
            "queue": self.commands.handle_queue,
            "next": self.commands.handle_next,
            "pause": self.commands.handle_pause,
            "resume": self.commands.handle_resume,
            "schedule": self.commands.handle_schedule,
            "stats": self.commands.handle_stats,
            "history": self.commands.handle_history,
            "locks": self.commands.handle_locks,
            "reset": self.commands.handle_reset,
            "cleanup": self.commands.handle_cleanup,
            "help": self.commands.handle_help,
            "dryrun": self.commands.handle_dryrun,
            "settings": self.settings_handler.handle_settings,
        }
        for cmd, handler in command_map.items():
            self.application.add_handler(CommandHandler(cmd, handler))

        # Register callback and message handlers
        self.application.add_handler(CallbackQueryHandler(self._handle_callback))
        # Message handler for conversation flows (add account, etc.)
        self.application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND, self._handle_conversation_message
            )
        )

        # Register commands with Telegram for autocomplete menu
        commands = [
            BotCommand("start", "Initialize bot and show welcome"),
            BotCommand("status", "Show system health and queue status"),
            BotCommand("help", "Show all available commands"),
            BotCommand("queue", "View pending scheduled posts"),
            BotCommand("next", "Force-send next scheduled post"),
            BotCommand("pause", "Pause automatic posting"),
            BotCommand("resume", "Resume posting"),
            BotCommand("schedule", "Create N days of posting schedule"),
            BotCommand("stats", "Show media library statistics"),
            BotCommand("history", "Show recent post history"),
            BotCommand("locks", "View permanently rejected items"),
            BotCommand("reset", "Reset posting queue to empty"),
            BotCommand("cleanup", "Delete recent bot messages"),
            BotCommand("settings", "Configure bot settings"),
            BotCommand("dryrun", "Toggle dry-run mode"),
        ]
        await self.bot.set_my_commands(commands)

        logger.info("Telegram bot initialized with command menu")

    def _build_callback_dispatch_table(self) -> dict:
        """Build the callback action dispatch table.

        Returns a dictionary mapping action strings to handler coroutines.
        All handlers in this table use the standard (data, user, query) signature.

        Actions that need special signatures (context, sub-routing, etc.) are
        NOT in this table -- they are handled in _handle_callback_special_cases().
        """
        return {
            # Queue item actions (telegram_callbacks.py)
            "posted": self.callbacks.handle_posted,
            "skip": self.callbacks.handle_skipped,
            "back": self.callbacks.handle_back,
            "reject": self.callbacks.handle_reject_confirmation,
            "confirm_reject": self.callbacks.handle_rejected,
            "cancel_reject": self.callbacks.handle_cancel_reject,
            "resume": self.callbacks.handle_resume_callback,
            "clear": self.callbacks.handle_reset_callback,  # Legacy name for reset
            # Auto-post (telegram_autopost.py)
            "autopost": self.autopost.handle_autopost,
            # Settings (telegram_settings.py)
            "settings_toggle": self.settings_handler.handle_settings_toggle,
            "schedule_action": self.settings_handler.handle_schedule_action,
            "schedule_confirm": self.settings_handler.handle_schedule_confirm,
            # Account management (telegram_accounts.py)
            "switch_account": self.accounts.handle_account_switch,
            "account_remove": self.accounts.handle_account_remove_confirm,
            "account_remove_confirmed": self.accounts.handle_account_remove_execute,
            "select_account": self.accounts.handle_post_account_selector,
            "sap": self.accounts.handle_post_account_switch,
            "btp": self.accounts.handle_back_to_post,
        }

    async def _handle_callback_special_cases(self, action, data, user, query, context):
        """Handle callback actions that need special signatures or sub-routing.

        Returns True if the action was handled, False if not recognized.

        Special cases:
        - settings_refresh: takes only (query)
        - settings_edit: takes (data, user, query, context)
        - settings_edit_cancel: takes (query, context)
        - settings_close: takes only (query)
        - settings_accounts: has sub-routing based on data value
        - accounts_config: has sub-routing based on data value
        - account_add_cancel: takes (user, query, context)
        """
        if action == "settings_refresh":
            await self.settings_handler.refresh_settings_message(query)
            return True

        elif action == "settings_edit":
            await self.settings_handler.handle_settings_edit_start(
                data, user, query, context
            )
            return True

        elif action == "settings_edit_cancel":
            await self.settings_handler.handle_settings_edit_cancel(query, context)
            return True

        elif action == "settings_close":
            await self.settings_handler.handle_settings_close(query)
            return True

        elif action == "settings_accounts":
            if data == "select":
                await self.accounts.handle_account_selection_menu(user, query)
            elif data == "back":
                await self.settings_handler.refresh_settings_message(query)
            return True

        elif action == "accounts_config":
            if data == "add":
                await self.accounts.handle_add_account_start(user, query, context)
            elif data == "remove":
                await self.accounts.handle_remove_account_menu(user, query)
            elif data == "noop":
                await query.answer()
            return True

        elif action == "account_add_cancel":
            await self.accounts.handle_add_account_cancel(user, query, context)
            return True

        return False

    async def send_notification(
        self, queue_item_id: str, force_sent: bool = False
    ) -> bool:
        """
        Send posting notification to Telegram channel.

        Args:
            queue_item_id: Queue item ID
            force_sent: Whether this was triggered by /next command

        Returns:
            True if sent successfully
        """
        # Initialize bot if not already done (for CLI usage)
        if self.bot is None:
            self.bot = Bot(token=self.bot_token)
            logger.debug("Telegram bot initialized for one-time use")

        queue_item = self.queue_repo.get_by_id(queue_item_id)
        if not queue_item:
            logger.error(f"Queue item not found: {queue_item_id}")
            return False

        media_item = self.media_repo.get_by_id(str(queue_item.media_item_id))
        if not media_item:
            logger.error(f"Media item not found: {queue_item.media_item_id}")
            return False

        # Get chat settings and verbose preference
        chat_settings = self.settings_service.get_settings(self.channel_id)
        verbose = self._is_verbose(self.channel_id, chat_settings=chat_settings)

        # Get active Instagram account for display
        active_account = self.ig_account_service.get_active_account(self.channel_id)

        # Build caption (pass queue_item for enhanced mode)
        caption = self._build_caption(
            media_item,
            queue_item,
            force_sent=force_sent,
            verbose=verbose,
            active_account=active_account,
        )

        # Build inline keyboard
        # Layout: Auto Post (if enabled) → Status actions → Instagram actions
        keyboard = []

        # Add Auto Post button if Instagram API is enabled (from database settings)
        if chat_settings.enable_instagram_api:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "🤖 Auto Post to Instagram",
                        callback_data=f"autopost:{queue_item_id}",
                    ),
                ]
            )

        # Status action buttons (grouped together)
        keyboard.extend(
            [
                [
                    InlineKeyboardButton(
                        "✅ Posted", callback_data=f"posted:{queue_item_id}"
                    ),
                    InlineKeyboardButton(
                        "⏭️ Skip", callback_data=f"skip:{queue_item_id}"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "🚫 Reject", callback_data=f"reject:{queue_item_id}"
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
                        callback_data=f"select_account:{queue_item_id}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "📱 Open Instagram", url="https://www.instagram.com/"
                    ),
                ],
            ]
        )
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            # Get file bytes via provider (supports local and future cloud sources)
            from io import BytesIO

            from src.services.media_sources.factory import MediaSourceFactory

            provider = MediaSourceFactory.get_provider_for_media_item(media_item)
            file_bytes = provider.download_file(media_item.source_identifier)

            photo_buffer = BytesIO(file_bytes)
            photo_buffer.name = media_item.file_name  # Telegram needs filename hint
            message = await self.bot.send_photo(
                chat_id=self.channel_id,
                photo=photo_buffer,
                caption=caption,
                reply_markup=reply_markup,
            )

            # Save telegram message ID
            self.queue_repo.set_telegram_message(
                queue_item_id, message.message_id, self.channel_id
            )

            # Log outgoing bot response for visibility
            self.interaction_service.log_bot_response(
                response_type="photo_notification",
                context={
                    "caption": caption,
                    "buttons": _extract_button_labels(reply_markup),
                    "media_filename": media_item.file_name,
                    "queue_item_id": queue_item_id,
                    "force_sent": force_sent,
                },
                telegram_chat_id=self.channel_id,
                telegram_message_id=message.message_id,
            )

            logger.info(f"Sent Telegram notification for {media_item.file_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return False

    def _build_caption(
        self,
        media_item,
        queue_item=None,
        force_sent: bool = False,
        verbose: bool = True,
        active_account=None,
    ) -> str:
        """Build caption for Telegram message with enhanced or simple formatting."""

        if settings.CAPTION_STYLE == "enhanced":
            return self._build_enhanced_caption(
                media_item,
                queue_item,
                force_sent=force_sent,
                verbose=verbose,
                active_account=active_account,
            )
        else:
            return self._build_simple_caption(
                media_item,
                force_sent=force_sent,
                verbose=verbose,
                active_account=active_account,
            )

    def _build_simple_caption(
        self,
        media_item,
        force_sent: bool = False,
        verbose: bool = True,
        active_account=None,
    ) -> str:
        """Build simple caption (original format)."""
        caption_parts = []

        # Subtle indicator for force-sent posts
        if force_sent:
            caption_parts.append("⚡")

        if media_item.title:
            caption_parts.append(f"📸 {media_item.title}")

        # Account indicator
        if active_account:
            caption_parts.append(f"📸 Account: {active_account.display_name}")

        if media_item.caption:
            caption_parts.append(media_item.caption)

        if media_item.link_url:
            caption_parts.append(f"🔗 {media_item.link_url}")

        if media_item.tags:
            tags_str = " ".join([f"#{tag}" for tag in media_item.tags])
            caption_parts.append(tags_str)

        if verbose:
            caption_parts.append(f"\n📝 File: {media_item.file_name}")
            caption_parts.append(f"🆔 ID: {str(media_item.id)[:8]}")

        return "\n\n".join(caption_parts)

    def _build_enhanced_caption(
        self,
        media_item,
        queue_item=None,
        force_sent: bool = False,
        verbose: bool = True,
        active_account=None,
    ) -> str:
        """Build enhanced caption with better formatting."""
        lines = []

        # Subtle indicator for force-sent posts (just a lightning bolt at the start)
        if force_sent:
            lines.append("⚡")

        # Title and metadata
        if media_item.title:
            lines.append(f"📸 {media_item.title}")

        # Active account indicator (for multi-account awareness)
        if active_account:
            lines.append(f"📸 Account: {active_account.display_name}")
        else:
            lines.append("📸 Account: Not set")

        # Caption
        if media_item.caption:
            lines.append(f"\n{media_item.caption}")

        # Link
        if media_item.link_url:
            lines.append(f"\n🔗 {media_item.link_url}")

        # Tags
        if media_item.tags:
            tags_str = " ".join([f"#{tag}" for tag in media_item.tags])
            lines.append(f"\n{tags_str}")

        # Only show workflow instructions if verbose mode is ON
        if verbose:
            # Separator
            lines.append(f"\n{'━' * 20}")

            # Workflow instructions
            lines.append("1️⃣ Click & hold image → Save")
            lines.append('2️⃣ Tap "Open Instagram" below')
            lines.append("3️⃣ Post your story!")

        return "\n".join(lines)

    def _get_header_emoji(self, tags) -> str:
        """Get header emoji based on tags."""
        if not tags:
            return "📸"

        tags_lower = [tag.lower() for tag in tags]

        # Map tags to emojis
        if any(tag in tags_lower for tag in ["meme", "funny", "humor"]):
            return "😂"
        elif any(tag in tags_lower for tag in ["product", "shop", "store", "sale"]):
            return "🛍️"
        elif any(tag in tags_lower for tag in ["quote", "inspiration", "motivational"]):
            return "✨"
        elif any(tag in tags_lower for tag in ["announcement", "news", "update"]):
            return "📢"
        elif any(tag in tags_lower for tag in ["question", "poll", "interactive"]):
            return "💬"
        else:
            return "📸"

    # Command handlers have been moved to telegram_commands.py
    # Callback handlers have been moved to telegram_callbacks.py
    # Auto-post handler has been moved to telegram_autopost.py
    # Settings handlers have been moved to telegram_settings.py
    # Account handlers have been moved to telegram_accounts.py

    async def _handle_conversation_message(self, update, context):
        """
        Handle text messages for active conversations.

        Routes to appropriate conversation handler based on state in context.user_data.
        """
        # Check for add account conversation
        if "add_account_state" in context.user_data:
            handled = await self.accounts.handle_add_account_message(update, context)
            if handled:
                return

        # Check for settings edit conversation
        if "settings_edit_state" in context.user_data:
            handled = await self.settings_handler.handle_settings_edit_message(
                update, context
            )
            if handled:
                return

        # Message not part of any conversation - ignore silently

    async def _handle_callback(self, update, context):
        """Handle inline button callbacks.

        Uses a two-tier dispatch approach:
        1. Dictionary lookup for standard (data, user, query) handlers
        2. Special-case method for handlers with non-standard signatures or sub-routing
        """
        try:
            query = update.callback_query

            logger.info(f"📞 Callback received: {query.data}")

            await query.answer()

            # Parse callback data
            # Split on FIRST colon only, so data can contain colons (e.g., sap:queue_id:account_id)
            parts = query.data.split(":", 1)
            action = parts[0]
            data = parts[1] if len(parts) > 1 else None

            logger.info(f"📞 Parsed action='{action}', data='{data}'")

            # Get user info
            user = self._get_or_create_user(query.from_user)

            # Tier 1: Standard dispatch (data, user, query) handlers
            handler = self._callback_dispatch.get(action)
            if handler:
                await handler(data, user, query)
                return

            # Tier 2: Special cases (non-standard signatures, sub-routing)
            handled = await self._handle_callback_special_cases(
                action, data, user, query, context
            )
            if handled:
                return

            logger.warning(f"Unknown callback action: {action}")

        finally:
            # Clean up open transactions to prevent "idle in transaction"
            self.cleanup_transactions()

    def _get_or_create_user(self, telegram_user):
        """Get or create user from Telegram data, syncing profile on each interaction."""
        user = self.user_repo.get_by_telegram_id(telegram_user.id)

        if not user:
            user = self.user_repo.create(
                telegram_user_id=telegram_user.id,
                telegram_username=telegram_user.username,
                telegram_first_name=telegram_user.first_name,
                telegram_last_name=telegram_user.last_name,
            )
            logger.info(f"New user discovered: {self._get_display_name(user)}")
        else:
            # Sync profile data on each interaction (username may have changed/been added)
            user = self.user_repo.update_profile(
                str(user.id),
                telegram_username=telegram_user.username,
                telegram_first_name=telegram_user.first_name,
                telegram_last_name=telegram_user.last_name,
            )

        return user

    def _is_verbose(self, chat_id, chat_settings=None) -> bool:
        """Check if verbose notifications are enabled for a chat.

        Accepts optional pre-loaded chat_settings to avoid redundant DB queries
        when the caller already has settings loaded.
        """
        if chat_settings is None:
            chat_settings = self.settings_service.get_settings(chat_id)
        if chat_settings.show_verbose_notifications is not None:
            return chat_settings.show_verbose_notifications
        return True

    def _get_display_name(self, user) -> str:
        """Get best available display name for user (username > first_name > user_id)."""
        if user.telegram_username:
            return f"@{user.telegram_username}"
        elif user.telegram_first_name:
            return user.telegram_first_name
        else:
            return f"User {user.telegram_user_id}"

    async def send_startup_notification(self):
        """Send startup notification to admin with system status."""
        if not settings.SEND_LIFECYCLE_NOTIFICATIONS:
            return

        try:
            # Gather system status
            pending_count = self.queue_repo.count_pending()
            media_count = len(self.media_repo.get_all(is_active=True))
            recent_posts = self.history_repo.get_recent_posts(hours=24)
            last_post_time = recent_posts[0].posted_at if recent_posts else None

            # Format last posted time
            if last_post_time:
                time_diff = datetime.utcnow() - last_post_time
                hours = int(time_diff.total_seconds() / 3600)
                last_posted = f"{hours}h ago" if hours > 0 else "< 1h ago"
            else:
                last_posted = "Never"

            # Build message
            message = (
                f"🟢 *Storyline AI Started*\n\n"
                f"📊 *System Status:*\n"
                f"├─ Database: ✅ Connected\n"
                f"├─ Telegram: ✅ Bot online\n"
                f"├─ Queue: {pending_count} pending posts\n"
                f"└─ Last posted: {last_posted}\n\n"
                f"⚙️ *Configuration:*\n"
                f"├─ Posts/day: {settings.POSTS_PER_DAY}\n"
                f"├─ Window: {settings.POSTING_HOURS_START:02d}:00-{settings.POSTING_HOURS_END:02d}:00 UTC\n"
                f"└─ Media indexed: {media_count} items\n\n"
                f"🤖 v{__version__}"
            )

            # Send to admin
            await self.bot.send_message(
                chat_id=settings.ADMIN_TELEGRAM_CHAT_ID,
                text=message,
                parse_mode="Markdown",
            )

            logger.info("Startup notification sent to admin")

        except Exception as e:
            logger.error(f"Failed to send startup notification: {e}")

    async def send_shutdown_notification(
        self, uptime_seconds: int = 0, posts_sent: int = 0
    ):
        """Send shutdown notification to admin with session summary."""
        if not settings.SEND_LIFECYCLE_NOTIFICATIONS:
            return

        try:
            # Format uptime
            hours = int(uptime_seconds / 3600)
            minutes = int((uptime_seconds % 3600) / 60)
            uptime_str = f"{hours}h {minutes}m"

            # Build message
            message = (
                f"🔴 *Storyline AI Stopped*\n\n"
                f"📊 *Session Summary:*\n"
                f"├─ Uptime: {uptime_str}\n"
                f"├─ Posts sent: {posts_sent}\n"
                f"└─ Shutdown: Graceful\n\n"
                f"See you next time! 👋"
            )

            # Send to admin
            await self.bot.send_message(
                chat_id=settings.ADMIN_TELEGRAM_CHAT_ID,
                text=message,
                parse_mode="Markdown",
            )

            logger.info("Shutdown notification sent to admin")

        except Exception as e:
            logger.error(f"Failed to send shutdown notification: {e}")

    async def start_polling(self):
        """Start bot polling."""
        logger.info("Starting Telegram bot polling...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()

    async def stop_polling(self):
        """Stop bot polling."""
        logger.info("Stopping Telegram bot polling...")
        await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()
