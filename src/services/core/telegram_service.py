"""Telegram service - bot operations and callbacks."""
from pathlib import Path
from typing import Optional
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

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
from datetime import datetime, timedelta
import re


def _escape_markdown(text: str) -> str:
    """Escape Telegram Markdown special characters in text."""
    # For Telegram's Markdown mode, escape: _ * ` [
    return re.sub(r'([_*`\[])', r'\\\1', text)


def _extract_button_labels(reply_markup) -> list:
    """Extract button labels from an InlineKeyboardMarkup for logging."""
    if not reply_markup or not hasattr(reply_markup, 'inline_keyboard'):
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

        # Add handlers
        self.application.add_handler(CommandHandler("start", self._handle_start))
        self.application.add_handler(CommandHandler("status", self._handle_status))
        self.application.add_handler(CommandHandler("queue", self._handle_queue))
        self.application.add_handler(CommandHandler("next", self._handle_next))
        self.application.add_handler(CommandHandler("pause", self._handle_pause))
        self.application.add_handler(CommandHandler("resume", self._handle_resume))
        self.application.add_handler(CommandHandler("schedule", self._handle_schedule))
        self.application.add_handler(CommandHandler("stats", self._handle_stats))
        self.application.add_handler(CommandHandler("history", self._handle_history))
        self.application.add_handler(CommandHandler("locks", self._handle_locks))
        self.application.add_handler(CommandHandler("clear", self._handle_clear))
        self.application.add_handler(CommandHandler("help", self._handle_help))
        self.application.add_handler(CommandHandler("dryrun", self._handle_dryrun))
        self.application.add_handler(CommandHandler("settings", self._handle_settings))
        self.application.add_handler(CallbackQueryHandler(self._handle_callback))
        # Message handler for conversation flows (add account, etc.)
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self._handle_conversation_message
        ))

        logger.info("Telegram bot initialized")

    async def send_notification(self, queue_item_id: str, force_sent: bool = False) -> bool:
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

        # Get verbose setting from chat settings
        chat_settings = self.settings_service.get_settings(self.channel_id)
        verbose = chat_settings.show_verbose_notifications if chat_settings.show_verbose_notifications is not None else True

        # Build caption (pass queue_item for enhanced mode)
        caption = self._build_caption(media_item, queue_item, force_sent=force_sent, verbose=verbose)

        # Build inline keyboard
        # Layout: Auto Post (if enabled) → Manual workflow → Reject
        keyboard = []

        # Add Auto Post button if Instagram API is enabled
        if settings.ENABLE_INSTAGRAM_API:
            keyboard.append([
                InlineKeyboardButton(
                    "🤖 Auto Post to Instagram",
                    callback_data=f"autopost:{queue_item_id}"
                ),
            ])

        # Manual workflow buttons
        keyboard.extend([
            [
                InlineKeyboardButton("✅ Posted", callback_data=f"posted:{queue_item_id}"),
                InlineKeyboardButton("⏭️ Skip", callback_data=f"skip:{queue_item_id}"),
            ],
            [
                InlineKeyboardButton("📱 Open Instagram", url="https://www.instagram.com/"),
            ],
            [
                InlineKeyboardButton("🚫 Reject", callback_data=f"reject:{queue_item_id}"),
            ]
        ])
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            # Send photo with buttons
            with open(media_item.file_path, "rb") as photo:
                message = await self.bot.send_photo(
                    chat_id=self.channel_id, photo=photo, caption=caption, reply_markup=reply_markup
                )

            # Save telegram message ID
            self.queue_repo.set_telegram_message(queue_item_id, message.message_id, self.channel_id)

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

    def _build_caption(self, media_item, queue_item=None, force_sent: bool = False, verbose: bool = True) -> str:
        """Build caption for Telegram message with enhanced or simple formatting."""

        if settings.CAPTION_STYLE == "enhanced":
            return self._build_enhanced_caption(media_item, queue_item, force_sent=force_sent, verbose=verbose)
        else:
            return self._build_simple_caption(media_item, force_sent=force_sent)

    def _build_simple_caption(self, media_item, force_sent: bool = False) -> str:
        """Build simple caption (original format)."""
        caption_parts = []

        # Subtle indicator for force-sent posts
        if force_sent:
            caption_parts.append("⚡")

        if media_item.title:
            caption_parts.append(f"📸 {media_item.title}")

        if media_item.caption:
            caption_parts.append(media_item.caption)

        if media_item.link_url:
            caption_parts.append(f"🔗 {media_item.link_url}")

        if media_item.tags:
            tags_str = " ".join([f"#{tag}" for tag in media_item.tags])
            caption_parts.append(tags_str)

        caption_parts.append(f"\n📝 File: {media_item.file_name}")
        caption_parts.append(f"🆔 ID: {str(media_item.id)[:8]}")

        return "\n\n".join(caption_parts)

    def _build_enhanced_caption(self, media_item, queue_item=None, force_sent: bool = False, verbose: bool = True) -> str:
        """Build enhanced caption with better formatting."""
        lines = []

        # Subtle indicator for force-sent posts (just a lightning bolt at the start)
        if force_sent:
            lines.append("⚡")

        # Title and metadata
        if media_item.title:
            lines.append(f"📸 {media_item.title}")

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
            lines.append(f"1️⃣ Click & hold image → Save")
            lines.append(f"2️⃣ Tap \"Open Instagram\" below")
            lines.append(f"3️⃣ Post your story!")

        return "\n".join(lines)

    def _get_header_emoji(self, tags) -> str:
        """Get header emoji based on tags."""
        if not tags:
            return "📸"

        tags_lower = [tag.lower() for tag in tags]

        # Map tags to emojis
        if any(tag in tags_lower for tag in ['meme', 'funny', 'humor']):
            return "😂"
        elif any(tag in tags_lower for tag in ['product', 'shop', 'store', 'sale']):
            return "🛍️"
        elif any(tag in tags_lower for tag in ['quote', 'inspiration', 'motivational']):
            return "✨"
        elif any(tag in tags_lower for tag in ['announcement', 'news', 'update']):
            return "📢"
        elif any(tag in tags_lower for tag in ['question', 'poll', 'interactive']):
            return "💬"
        else:
            return "📸"

    async def _handle_start(self, update, context):
        """Handle /start command."""
        user = self._get_or_create_user(update.effective_user)

        await update.message.reply_text(
            "👋 *Storyline AI Bot*\n\n"
            "Commands:\n"
            "/queue - View upcoming posts\n"
            "/next - Force send next post\n"
            "/status - Check system status\n"
            "/help - Show all commands",
            parse_mode="Markdown"
        )

        # Log interaction
        self.interaction_service.log_command(
            user_id=str(user.id),
            command="/start",
            telegram_chat_id=update.effective_chat.id,
            telegram_message_id=update.message.message_id,
        )

    async def _handle_status(self, update, context):
        """Handle /status command."""
        user = self._get_or_create_user(update.effective_user)

        # Gather stats
        pending_count = self.queue_repo.count_pending()
        recent_posts = self.history_repo.get_recent_posts(hours=24)
        media_count = len(self.media_repo.get_all(is_active=True))
        locked_count = len(self.lock_repo.get_permanent_locks())

        # Get next scheduled post
        next_items = self.queue_repo.get_pending(limit=1)
        if next_items:
            next_time = next_items[0].scheduled_for
            next_post_str = next_time.strftime("%H:%M UTC")
        else:
            next_post_str = "None scheduled"

        # Last post time
        if recent_posts:
            time_diff = datetime.utcnow() - recent_posts[0].posted_at
            hours = int(time_diff.total_seconds() / 3600)
            last_posted = f"{hours}h ago" if hours > 0 else "< 1h ago"
        else:
            last_posted = "Never"

        # Mode indicators
        dry_run_status = "🧪 ON" if settings.DRY_RUN_MODE else "🚀 OFF"
        pause_status = "⏸️ PAUSED" if self.is_paused else "▶️ Active"

        # Instagram API status
        if settings.ENABLE_INSTAGRAM_API:
            from src.services.integrations.instagram_api import InstagramAPIService
            with InstagramAPIService() as ig_service:
                rate_remaining = ig_service.get_rate_limit_remaining()
            ig_status = f"✅ Enabled ({rate_remaining}/{settings.INSTAGRAM_POSTS_PER_HOUR} remaining)"
        else:
            ig_status = "❌ Disabled"

        status_msg = (
            f"📊 *Storyline AI Status*\n\n"
            f"*System:*\n"
            f"🤖 Bot: Online\n"
            f"⏯️ Posting: {pause_status}\n"
            f"🧪 Dry Run: {dry_run_status}\n\n"
            f"*Instagram API:*\n"
            f"📸 {ig_status}\n\n"
            f"*Queue & Media:*\n"
            f"📋 Queue: {pending_count} pending\n"
            f"📁 Library: {media_count} active\n"
            f"🔒 Locked: {locked_count}\n\n"
            f"*Activity:*\n"
            f"⏰ Next: {next_post_str}\n"
            f"📤 Last: {last_posted}\n"
            f"📈 24h: {len(recent_posts)} posts"
        )

        await update.message.reply_text(status_msg, parse_mode="Markdown")

        # Log interaction
        self.interaction_service.log_command(
            user_id=str(user.id),
            command="/status",
            context={
                "queue_size": pending_count,
                "media_count": media_count,
                "posts_24h": len(recent_posts),
            },
            telegram_chat_id=update.effective_chat.id,
            telegram_message_id=update.message.message_id,
        )

    async def _handle_queue(self, update, context):
        """Handle /queue command - show upcoming scheduled posts."""
        user = self._get_or_create_user(update.effective_user)

        # Get ALL pending queue items (not just due ones)
        all_pending = self.queue_repo.get_all(status="pending")
        total_count = len(all_pending)
        queue_items = all_pending[:10]  # Show first 10

        if not queue_items:
            await update.message.reply_text(
                "📭 *Queue Empty*\n\nNo posts scheduled.",
                parse_mode="Markdown"
            )
        else:
            lines = [f"📅 *Upcoming Queue* ({len(queue_items)} of {total_count})\n"]

            for i, item in enumerate(queue_items, 1):
                # Get media info
                media_item = self.media_repo.get_by_id(str(item.media_item_id))
                filename = media_item.file_name if media_item else "Unknown"
                category = media_item.category if media_item and media_item.category else "-"

                # Escape markdown special characters in dynamic content
                filename = _escape_markdown(filename)
                category = _escape_markdown(category)

                # Format scheduled time
                scheduled = item.scheduled_for.strftime("%b %d %H:%M UTC")

                lines.append(f"{i}. 🕐 {scheduled}")
                lines.append(f"    📁 {filename} ({category})\n")

            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

        # Log interaction
        self.interaction_service.log_command(
            user_id=str(user.id),
            command="/queue",
            context={
                "items_shown": len(queue_items),
                "total_queue": total_count,
            },
            telegram_chat_id=update.effective_chat.id,
            telegram_message_id=update.message.message_id,
        )

    async def _handle_next(self, update, context):
        """
        Handle /next command - force send next scheduled post immediately.

        Uses the shared force_post_next() method which:
        1. Gets the earliest pending item
        2. Shifts all subsequent items forward by one slot
        3. Sends to Telegram with ⚡ indicator
        """
        user = self._get_or_create_user(update.effective_user)

        # Use shared force_post_next() method (lazy import to avoid circular import)
        from src.services.core.posting import PostingService
        with PostingService() as posting_service:
            result = await posting_service.force_post_next(
                user_id=str(user.id),
                triggered_by="telegram",
                force_sent_indicator=True,  # Shows ⚡ in caption
            )

        if not result["success"]:
            if result["error"] == "No pending items in queue":
                await update.message.reply_text(
                    "📭 *Queue Empty*\n\nNo posts to send.",
                    parse_mode="Markdown"
                )
            elif result["error"] == "Media item not found":
                await update.message.reply_text(
                    "⚠️ *Error*\n\nMedia item not found.",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(
                    f"❌ *Failed to send*\n\nCheck logs for details.",
                    parse_mode="Markdown"
                )
            return

        # Success - log interaction
        media_item = result["media_item"]
        shifted_count = result["shifted_count"]

        self.interaction_service.log_command(
            user_id=str(user.id),
            command="/next",
            context={
                "queue_item_id": result["queue_item_id"],
                "media_id": str(media_item.id) if media_item else None,
                "media_filename": media_item.file_name if media_item else None,
                "success": True,
                "shifted_count": shifted_count,
            },
            telegram_chat_id=update.effective_chat.id,
            telegram_message_id=update.message.message_id,
        )

        shift_msg = f" (shifted {shifted_count} items)" if shifted_count > 0 else ""
        logger.info(
            f"Force-sent next post by {self._get_display_name(user)}: "
            f"{media_item.file_name}{shift_msg}"
        )

    async def _handle_help(self, update, context):
        """Handle /help command."""
        user = self._get_or_create_user(update.effective_user)

        help_text = (
            "📖 *Storyline AI Help*\n\n"
            "*Queue Commands:*\n"
            "/queue - View upcoming posts\n"
            "/next - Force send next post\n"
            "/schedule N - Add N days to queue\n"
            "/clear - Clear all pending posts\n\n"
            "*Control Commands:*\n"
            "/settings - View/toggle bot settings\n"
            "/pause - Pause automatic posting\n"
            "/resume - Resume posting\n"
            "/dryrun - Toggle dry run mode\n"
            "/status - System health check\n\n"
            "*Info Commands:*\n"
            "/stats - Media library statistics\n"
            "/history N - Show last N posts\n"
            "/locks - View locked items\n"
            "/help - Show this help\n\n"
            "*Button Actions:*\n"
            "🤖 Auto Post - Post via Instagram API\n"
            "✅ Posted - Mark as posted (manual)\n"
            "⏭️ Skip - Skip (requeue later)\n"
            "🚫 Reject - Permanently remove"
        )

        await update.message.reply_text(help_text, parse_mode="Markdown")

        # Log interaction
        self.interaction_service.log_command(
            user_id=str(user.id),
            command="/help",
            telegram_chat_id=update.effective_chat.id,
            telegram_message_id=update.message.message_id,
        )

    async def _handle_conversation_message(self, update, context):
        """
        Handle text messages for active conversations.

        Routes to appropriate conversation handler based on state in context.user_data.
        """
        # Check for add account conversation
        if "add_account_state" in context.user_data:
            handled = await self._handle_add_account_message(update, context)
            if handled:
                return

        # Message not part of any conversation - ignore silently

    async def _handle_dryrun(self, update, context):
        """
        Handle /dryrun command - toggle or check dry run mode.

        Usage:
            /dryrun - Show current status
            /dryrun on - Enable dry run mode
            /dryrun off - Disable dry run mode
        """
        user = self._get_or_create_user(update.effective_user)

        # Check if user provided an argument
        args = context.args if context.args else []

        if len(args) == 0:
            # No argument - show current status
            status = "ON" if settings.DRY_RUN_MODE else "OFF"
            emoji = "🧪" if settings.DRY_RUN_MODE else "🚀"
            await update.message.reply_text(
                f"{emoji} Dry Run Mode: {status}\n\n"
                f"Use /dryrun on or /dryrun off to change."
            )
        elif args[0].lower() == "on":
            settings.DRY_RUN_MODE = True
            await update.message.reply_text(
                "🧪 Dry Run Mode: ON\n\n"
                "• Auto Post will upload to Cloudinary but NOT post to Instagram\n"
                "• Automatic posting loop will skip Instagram API calls\n"
                "• Use /dryrun off to resume real posting"
            )
            logger.info(f"Dry run mode ENABLED by {self._get_display_name(user)}")
        elif args[0].lower() == "off":
            settings.DRY_RUN_MODE = False
            await update.message.reply_text(
                "🚀 Dry Run Mode: OFF\n\n"
                "• Auto Post will now post to Instagram for real\n"
                "• Automatic posting loop is active\n"
                "• Use /dryrun on to test without posting"
            )
            logger.info(f"Dry run mode DISABLED by {self._get_display_name(user)}")
        else:
            await update.message.reply_text(
                "❓ Invalid argument.\n\n"
                "Usage:\n"
                "• /dryrun - Show current status\n"
                "• /dryrun on - Enable dry run\n"
                "• /dryrun off - Disable dry run"
            )

        # Log interaction
        self.interaction_service.log_command(
            user_id=str(user.id),
            command="/dryrun",
            context={"args": args},
            telegram_chat_id=update.effective_chat.id,
            telegram_message_id=update.message.message_id,
        )

    async def _handle_settings(self, update, context):
        """Handle /settings command - show settings menu with toggle buttons."""
        user = self._get_or_create_user(update.effective_user)
        chat_id = update.effective_chat.id

        # Log interaction
        self.interaction_service.log_command(
            user_id=str(user.id),
            command="/settings",
            telegram_chat_id=chat_id,
            telegram_message_id=update.message.message_id,
        )

        settings_data = self.settings_service.get_settings_display(chat_id)
        account_data = self.ig_account_service.get_accounts_for_display(chat_id)

        # Build message with explanation
        message = (
            "⚙️ *Bot Settings*\n\n"
            "_Regenerate: Clears queue, creates new schedule_\n"
            "_+7 Days: Extends existing queue_"
        )

        # Build inline keyboard with toggles
        keyboard = [
            # Row 1: Dry Run toggle
            [
                InlineKeyboardButton(
                    "✅ Dry Run" if settings_data["dry_run_mode"] else "Dry Run",
                    callback_data="settings_toggle:dry_run_mode"
                ),
            ],
            # Row 2: Instagram API toggle
            [
                InlineKeyboardButton(
                    "✅ Instagram API" if settings_data["enable_instagram_api"] else "Instagram API",
                    callback_data="settings_toggle:enable_instagram_api"
                ),
            ],
            # Row 3: Pause toggle
            [
                InlineKeyboardButton(
                    "⏸️ Paused" if settings_data["is_paused"] else "▶️ Active",
                    callback_data="settings_toggle:is_paused"
                ),
            ],
            # Row 4: Instagram Account config
            [
                InlineKeyboardButton(
                    f"📸 @{account_data['active_account_username']}" if account_data["active_account_username"] else "📸 Configure Accounts",
                    callback_data="settings_accounts:select"
                ),
            ],
            # Row 5: Info display (non-interactive)
            [
                InlineKeyboardButton(
                    f"📊 Posts/Day: {settings_data['posts_per_day']}",
                    callback_data="settings_info:posts_per_day"
                ),
            ],
            # Row 6: Posting hours
            [
                InlineKeyboardButton(
                    f"🕐 Hours: {settings_data['posting_hours_start']}:00-{settings_data['posting_hours_end']}:00 UTC",
                    callback_data="settings_info:hours"
                ),
            ],
            # Row 7: Verbose notifications toggle
            [
                InlineKeyboardButton(
                    f"📝 Verbose: {'ON' if settings_data['show_verbose_notifications'] else 'OFF'}",
                    callback_data="settings_toggle:show_verbose_notifications"
                ),
            ],
            # Row 8: Schedule management
            [
                InlineKeyboardButton("🔄 Regenerate", callback_data="schedule_action:regenerate"),
                InlineKeyboardButton("📅 +7 Days", callback_data="schedule_action:extend"),
            ],
            # Row 9: Close button
            [
                InlineKeyboardButton("❌ Close", callback_data="settings_close"),
            ],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            message,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

    async def _handle_settings_toggle(self, setting_name: str, user, query):
        """Handle settings toggle button click."""
        chat_id = query.message.chat_id

        try:
            new_value = self.settings_service.toggle_setting(chat_id, setting_name, user)

            # Log the interaction
            self.interaction_service.log_callback(
                user_id=str(user.id),
                callback_name=f"settings_toggle:{setting_name}",
                context={"new_value": new_value},
                telegram_chat_id=chat_id,
                telegram_message_id=query.message.message_id,
            )

            # Refresh the settings display
            await self._refresh_settings_message(query)

        except ValueError as e:
            await query.answer(f"Error: {e}", show_alert=True)

    async def _refresh_settings_message(self, query, show_answer: bool = True):
        """Refresh the settings message with current values."""
        chat_id = query.message.chat_id
        settings_data = self.settings_service.get_settings_display(chat_id)
        account_data = self.ig_account_service.get_accounts_for_display(chat_id)

        # Rebuild message with explanation
        message = (
            "⚙️ *Bot Settings*\n\n"
            "_Regenerate: Clears queue, creates new schedule_\n"
            "_+7 Days: Extends existing queue_"
        )

        # Rebuild keyboard with updated values
        keyboard = [
            [InlineKeyboardButton(
                "✅ Dry Run" if settings_data["dry_run_mode"] else "Dry Run",
                callback_data="settings_toggle:dry_run_mode"
            )],
            [InlineKeyboardButton(
                "✅ Instagram API" if settings_data["enable_instagram_api"] else "Instagram API",
                callback_data="settings_toggle:enable_instagram_api"
            )],
            [InlineKeyboardButton(
                "⏸️ Paused" if settings_data["is_paused"] else "▶️ Active",
                callback_data="settings_toggle:is_paused"
            )],
            [InlineKeyboardButton(
                f"📸 @{account_data['active_account_username']}" if account_data["active_account_username"] else "📸 Configure Accounts",
                callback_data="settings_accounts:select"
            )],
            [InlineKeyboardButton(
                f"📊 Posts/Day: {settings_data['posts_per_day']}",
                callback_data="settings_info:posts_per_day"
            )],
            [InlineKeyboardButton(
                f"🕐 Hours: {settings_data['posting_hours_start']}:00-{settings_data['posting_hours_end']}:00 UTC",
                callback_data="settings_info:hours"
            )],
            [InlineKeyboardButton(
                f"📝 Verbose: {'ON' if settings_data['show_verbose_notifications'] else 'OFF'}",
                callback_data="settings_toggle:show_verbose_notifications"
            )],
            [
                InlineKeyboardButton("🔄 Regenerate", callback_data="schedule_action:regenerate"),
                InlineKeyboardButton("📅 +7 Days", callback_data="schedule_action:extend"),
            ],
            [InlineKeyboardButton("❌ Close", callback_data="settings_close")],
        ]

        await query.edit_message_text(
            text=message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        if show_answer:
            await query.answer("Setting updated!")

    async def _handle_settings_close(self, query):
        """Handle Close button - delete the settings message."""
        try:
            await query.message.delete()
        except Exception as e:
            logger.warning(f"Could not delete settings message: {e}")
            await query.answer("Could not close menu")

    async def _handle_schedule_action(self, action: str, user, query):
        """Handle schedule management actions (regenerate/extend)."""
        chat_id = query.message.chat_id

        # Import scheduler service here to avoid circular imports
        from src.services.core.scheduler import SchedulerService

        if action == "regenerate":
            # Confirm before regenerating (destructive action)
            keyboard = [
                [
                    InlineKeyboardButton("✅ Yes, Regenerate", callback_data="schedule_confirm:regenerate"),
                    InlineKeyboardButton("❌ Cancel", callback_data="schedule_confirm:cancel"),
                ]
            ]

            pending_count = self.queue_repo.count_pending()

            await query.edit_message_text(
                f"⚠️ *Regenerate Schedule?*\n\n"
                f"This will:\n"
                f"• Clear all {pending_count} pending posts\n"
                f"• Create a new 7-day schedule\n\n"
                f"This cannot be undone.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            await query.answer()

        elif action == "extend":
            # Extend immediately (non-destructive)
            await query.answer("Extending schedule...")

            with SchedulerService() as scheduler:
                try:
                    result = scheduler.extend_schedule(days=7, user_id=str(user.id))

                    # Log interaction
                    self.interaction_service.log_callback(
                        user_id=str(user.id),
                        callback_name="schedule_action:extend",
                        context={
                            "scheduled": result["scheduled"],
                            "skipped": result["skipped"],
                            "extended_from": result.get("extended_from"),
                        },
                        telegram_chat_id=chat_id,
                        telegram_message_id=query.message.message_id,
                    )

                    # Show result and return to settings
                    await query.answer(f"Added {result['scheduled']} posts!")
                    logger.info(f"Schedule extended by {self._get_display_name(user)}: +{result['scheduled']} posts")

                    # Refresh settings menu
                    await self._refresh_settings_message(query, show_answer=False)

                except Exception as e:
                    logger.error(f"Schedule extension failed: {e}")
                    await query.answer(f"Error: {str(e)[:100]}", show_alert=True)

    async def _handle_schedule_confirm(self, action: str, user, query):
        """Handle schedule confirmation callbacks."""
        chat_id = query.message.chat_id

        if action == "cancel":
            # Return to settings menu
            await self._refresh_settings_message(query, show_answer=False)
            await query.answer("Cancelled")
            return

        if action == "regenerate":
            from src.services.core.scheduler import SchedulerService

            await query.answer("Regenerating schedule...")

            # Clear queue
            all_pending = self.queue_repo.get_all(status="pending")
            cleared = 0
            for item in all_pending:
                self.queue_repo.delete(str(item.id))
                cleared += 1

            # Create new schedule
            with SchedulerService() as scheduler:
                try:
                    result = scheduler.create_schedule(days=7, user_id=str(user.id))

                    # Log interaction
                    self.interaction_service.log_callback(
                        user_id=str(user.id),
                        callback_name="schedule_action:regenerate",
                        context={
                            "cleared": cleared,
                            "scheduled": result["scheduled"],
                            "skipped": result["skipped"],
                        },
                        telegram_chat_id=chat_id,
                        telegram_message_id=query.message.message_id,
                    )

                    logger.info(
                        f"Schedule regenerated by {self._get_display_name(user)}: "
                        f"cleared {cleared}, scheduled {result['scheduled']}"
                    )

                    # Show result and return to settings
                    await query.answer(f"Cleared {cleared}, added {result['scheduled']} posts!")
                    await self._refresh_settings_message(query, show_answer=False)

                except Exception as e:
                    logger.error(f"Schedule regeneration failed: {e}")
                    await query.answer(f"Error: {str(e)[:100]}", show_alert=True)

    async def _handle_account_selection_menu(self, user, query):
        """Show Instagram account configuration menu."""
        chat_id = query.message.chat_id
        account_data = self.ig_account_service.get_accounts_for_display(chat_id)

        # Build account management keyboard
        keyboard = []

        # List existing accounts with select option
        if account_data["accounts"]:
            for account in account_data["accounts"]:
                is_active = account["id"] == account_data["active_account_id"]
                label = f"{'✅ ' if is_active else '   '}{account['display_name']}"
                if account["username"]:
                    label += f" (@{account['username']})"
                keyboard.append([
                    InlineKeyboardButton(
                        label,
                        callback_data=f"switch_account:{account['id']}"
                    )
                ])
        else:
            keyboard.append([
                InlineKeyboardButton(
                    "No accounts configured",
                    callback_data="accounts_config:noop"
                )
            ])

        # Action buttons row
        keyboard.append([
            InlineKeyboardButton("➕ Add Account", callback_data="accounts_config:add"),
        ])

        # Only show remove option if there are accounts
        if account_data["accounts"]:
            keyboard.append([
                InlineKeyboardButton("🗑️ Remove Account", callback_data="accounts_config:remove"),
            ])

        # Back button
        keyboard.append([
            InlineKeyboardButton("↩️ Back to Settings", callback_data="settings_accounts:back")
        ])

        await query.edit_message_text(
            "📸 *Configure Instagram Accounts*\n\n"
            "Select an account to make it active, or add/remove accounts.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await query.answer()

    async def _handle_account_switch(self, account_id: str, user, query):
        """Handle switching to a different Instagram account."""
        chat_id = query.message.chat_id

        try:
            account = self.ig_account_service.switch_account(chat_id, account_id, user)

            # Log the interaction
            self.interaction_service.log_callback(
                user_id=str(user.id),
                callback_name=f"switch_account:{account_id}",
                context={
                    "account_id": account_id,
                    "display_name": account.display_name,
                    "username": account.instagram_username
                },
                telegram_chat_id=chat_id,
                telegram_message_id=query.message.message_id,
            )

            await query.answer(f"Switched to @{account.instagram_username}")

            # Return to settings menu with updated values
            await self._refresh_settings_message(query, show_answer=False)

        except ValueError as e:
            await query.answer(f"Error: {e}", show_alert=True)

    async def _handle_add_account_start(self, user, query, context):
        """Start the add account conversation flow."""
        chat_id = query.message.chat_id

        # Initialize conversation state
        context.user_data["add_account_state"] = "awaiting_display_name"
        context.user_data["add_account_chat_id"] = chat_id
        context.user_data["add_account_data"] = {}
        # Track message IDs to delete later
        context.user_data["add_account_messages"] = [query.message.message_id]

        keyboard = [
            [InlineKeyboardButton("❌ Cancel", callback_data="account_add_cancel:cancel")]
        ]

        await query.edit_message_text(
            "➕ *Add Instagram Account*\n\n"
            "*Step 1 of 3: Display Name*\n\n"
            "Enter a friendly name for this account:\n"
            "(e.g., 'Main Account', 'Brand Account')\n\n"
            "_Reply with the name_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await query.answer()

        logger.info(f"User {self._get_display_name(user)} started add account flow")

    async def _handle_add_account_message(self, update, context):
        """Handle text messages during add account conversation."""
        if "add_account_state" not in context.user_data:
            return False  # Not in add account flow

        state = context.user_data["add_account_state"]
        user = self._get_or_create_user(update.effective_user)
        chat_id = update.effective_chat.id
        message_text = update.message.text.strip()

        if state == "awaiting_display_name":
            # Track user's message for cleanup
            context.user_data["add_account_messages"].append(update.message.message_id)

            # Save display name and ask for account ID
            context.user_data["add_account_data"]["display_name"] = message_text
            context.user_data["add_account_state"] = "awaiting_account_id"

            keyboard = [
                [InlineKeyboardButton("❌ Cancel", callback_data="account_add_cancel:cancel")]
            ]

            reply = await update.message.reply_text(
                "➕ *Add Instagram Account*\n\n"
                "*Step 2 of 3: Instagram Account ID*\n\n"
                f"Display name: `{message_text}`\n\n"
                "Enter the numeric Account ID from Meta Business Suite:\n\n"
                "_Found in: Settings → Business Assets → Instagram Accounts_\n\n"
                "Reply with the ID",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
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
                    parse_mode="Markdown"
                )
                context.user_data["add_account_messages"].append(reply.message_id)
                return True

            context.user_data["add_account_data"]["account_id"] = message_text
            context.user_data["add_account_state"] = "awaiting_token"

            keyboard = [
                [InlineKeyboardButton("❌ Cancel", callback_data="account_add_cancel:cancel")]
            ]

            reply = await update.message.reply_text(
                "➕ *Add Instagram Account*\n\n"
                "*Step 3 of 3: Access Token*\n\n"
                f"Display name: `{context.user_data['add_account_data']['display_name']}`\n"
                f"Account ID: `{message_text}`\n\n"
                "⚠️ *Security*: Your token message will be deleted immediately.\n\n"
                "Paste your Instagram Graph API access token:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
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
                    parse_mode="Markdown"
                )

                # Fetch username from Instagram API
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"https://graph.facebook.com/v18.0/{data['account_id']}",
                        params={
                            "fields": "username",
                            "access_token": access_token
                        },
                        timeout=30.0
                    )

                    if response.status_code != 200:
                        error_data = response.json()
                        error_msg = error_data.get("error", {}).get("message", "Unknown error")
                        raise ValueError(f"Instagram API error: {error_msg}")

                    api_data = response.json()
                    username = api_data.get("username")

                    if not username:
                        raise ValueError("Could not fetch username from Instagram API")

                # Check if account already exists
                existing_account = self.ig_account_service.get_account_by_instagram_id(
                    data["account_id"]
                )

                if existing_account:
                    # Update the existing account's token
                    account = self.ig_account_service.update_account_token(
                        instagram_account_id=data["account_id"],
                        access_token=access_token,
                        instagram_username=username,
                        user=user,
                        set_as_active=True,
                        telegram_chat_id=chat_id
                    )
                    was_update = True
                else:
                    # Create the account with fetched username
                    account = self.ig_account_service.add_account(
                        display_name=data["display_name"],
                        instagram_account_id=data["account_id"],
                        instagram_username=username,
                        access_token=access_token,
                        user=user,
                        set_as_active=True,
                        telegram_chat_id=chat_id
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
                        await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                    except Exception:
                        pass  # Message may already be deleted

                # Clear conversation state
                context.user_data.pop("add_account_state", None)
                context.user_data.pop("add_account_data", None)
                context.user_data.pop("add_account_chat_id", None)
                context.user_data.pop("add_account_messages", None)

                # Log interaction
                self.interaction_service.log_callback(
                    user_id=str(user.id),
                    callback_name="update_account_token" if was_update else "add_account",
                    context={
                        "account_id": str(account.id),
                        "display_name": account.display_name,
                        "username": account.instagram_username,
                        "was_update": was_update
                    },
                    telegram_chat_id=chat_id,
                    telegram_message_id=update.message.message_id,
                )

                action = "updated token for" if was_update else "added"
                logger.info(
                    f"User {self._get_display_name(user)} {action} Instagram account: "
                    f"{account.display_name} (@{account.instagram_username})"
                )

                # Show Configure Accounts menu with success message
                account_data = self.ig_account_service.get_accounts_for_display(chat_id)
                keyboard = []

                for acc in account_data["accounts"]:
                    is_active = acc["id"] == account_data["active_account_id"]
                    label = f"{'✅ ' if is_active else '   '}{acc['display_name']}"
                    if acc["username"]:
                        label += f" (@{acc['username']})"
                    keyboard.append([
                        InlineKeyboardButton(
                            label,
                            callback_data=f"switch_account:{acc['id']}"
                        )
                    ])

                keyboard.append([
                    InlineKeyboardButton("➕ Add Account", callback_data="accounts_config:add"),
                ])
                if account_data["accounts"]:
                    keyboard.append([
                        InlineKeyboardButton("🗑️ Remove Account", callback_data="accounts_config:remove"),
                    ])
                keyboard.append([
                    InlineKeyboardButton("↩️ Back to Settings", callback_data="settings_accounts:back")
                ])

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
                    reply_markup=InlineKeyboardMarkup(keyboard)
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
                        await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                    except Exception:
                        pass

                # Clear state on error
                context.user_data.pop("add_account_state", None)
                context.user_data.pop("add_account_data", None)
                context.user_data.pop("add_account_chat_id", None)
                context.user_data.pop("add_account_messages", None)

                keyboard = [
                    [InlineKeyboardButton("🔄 Try Again", callback_data="accounts_config:add")],
                    [InlineKeyboardButton("↩️ Back to Settings", callback_data="settings_accounts:back")]
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
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

                logger.error(f"Failed to add Instagram account: {e}")

            return True

        return False

    async def _handle_add_account_cancel(self, user, query, context):
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
        await self._handle_account_selection_menu(user, query)

    async def _handle_remove_account_menu(self, user, query):
        """Show menu to select account to remove."""
        chat_id = query.message.chat_id
        account_data = self.ig_account_service.get_accounts_for_display(chat_id)

        keyboard = []

        for account in account_data["accounts"]:
            is_active = account["id"] == account_data["active_account_id"]
            label = f"🗑️ {account['display_name']}"
            if account["username"]:
                label += f" (@{account['username']})"
            if is_active:
                label += " ⚠️ ACTIVE"
            keyboard.append([
                InlineKeyboardButton(
                    label,
                    callback_data=f"account_remove:{account['id']}"
                )
            ])

        keyboard.append([
            InlineKeyboardButton("↩️ Back", callback_data="settings_accounts:select")
        ])

        await query.edit_message_text(
            "🗑️ *Remove Instagram Account*\n\n"
            "Select an account to remove:\n\n"
            "_Note: Removing an account deactivates it. Tokens and history are preserved._",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await query.answer()

    async def _handle_account_remove_confirm(self, account_id: str, user, query):
        """Show confirmation before removing account."""
        account = self.ig_account_service.get_account_by_id(account_id)

        if not account:
            await query.answer("Account not found", show_alert=True)
            return

        keyboard = [
            [
                InlineKeyboardButton("✅ Yes, Remove", callback_data=f"account_remove_confirmed:{account_id}"),
                InlineKeyboardButton("❌ Cancel", callback_data="settings_accounts:select"),
            ]
        ]

        await query.edit_message_text(
            f"⚠️ *Confirm Remove Account*\n\n"
            f"Are you sure you want to remove:\n\n"
            f"📸 *{account.display_name}*\n"
            f"Username: @{account.instagram_username}\n\n"
            f"_The account can be reactivated later via CLI._",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await query.answer()

    async def _handle_account_remove_execute(self, account_id: str, user, query):
        """Execute account removal (deactivation)."""
        chat_id = query.message.chat_id

        try:
            account = self.ig_account_service.deactivate_account(account_id, user)

            # Log interaction
            self.interaction_service.log_callback(
                user_id=str(user.id),
                callback_name=f"remove_account:{account_id}",
                context={
                    "account_id": account_id,
                    "display_name": account.display_name,
                    "username": account.instagram_username
                },
                telegram_chat_id=chat_id,
                telegram_message_id=query.message.message_id,
            )

            await query.answer(f"Removed @{account.instagram_username}")

            logger.info(
                f"User {self._get_display_name(user)} removed Instagram account: "
                f"{account.display_name} (@{account.instagram_username})"
            )

            # Return to account config menu
            await self._handle_account_selection_menu(user, query)

        except ValueError as e:
            await query.answer(f"Error: {e}", show_alert=True)

    async def _handle_pause(self, update, context):
        """Handle /pause command - pause automatic posting."""
        user = self._get_or_create_user(update.effective_user)

        if self.is_paused:
            await update.message.reply_text(
                "⏸️ *Already Paused*\n\nAutomatic posting is already paused.\nUse /resume to restart.",
                parse_mode="Markdown"
            )
        else:
            self.set_paused(True, user)
            pending_count = self.queue_repo.count_pending()
            await update.message.reply_text(
                f"⏸️ *Posting Paused*\n\n"
                f"Automatic posting has been paused.\n"
                f"📊 {pending_count} posts still in queue.\n\n"
                f"Use /resume to restart posting.\n"
                f"Use /next to manually send posts.",
                parse_mode="Markdown"
            )
            logger.info(f"Posting paused by {self._get_display_name(user)}")

        self.interaction_service.log_command(
            user_id=str(user.id),
            command="/pause",
            context={"was_paused": self.is_paused},
            telegram_chat_id=update.effective_chat.id,
            telegram_message_id=update.message.message_id,
        )

    async def _handle_resume(self, update, context):
        """Handle /resume command - resume automatic posting."""
        user = self._get_or_create_user(update.effective_user)

        if not self.is_paused:
            await update.message.reply_text(
                "▶️ *Already Running*\n\nAutomatic posting is already active.",
                parse_mode="Markdown"
            )
        else:
            # Check for overdue posts
            now = datetime.utcnow()
            all_pending = self.queue_repo.get_all(status="pending")
            overdue = [p for p in all_pending if p.scheduled_for < now]
            future = [p for p in all_pending if p.scheduled_for >= now]

            if overdue:
                # Show options for handling overdue posts
                keyboard = [
                    [
                        InlineKeyboardButton("🔄 Reschedule", callback_data="resume:reschedule"),
                        InlineKeyboardButton("🗑️ Clear Overdue", callback_data="resume:clear"),
                    ],
                    [
                        InlineKeyboardButton("▶️ Resume Anyway", callback_data="resume:force"),
                    ]
                ]
                await update.message.reply_text(
                    f"⚠️ *{len(overdue)} Overdue Posts Found*\n\n"
                    f"These posts were scheduled while paused:\n"
                    f"• {len(overdue)} overdue\n"
                    f"• {len(future)} still scheduled\n\n"
                    f"What would you like to do?",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                self.set_paused(False, user)
                await update.message.reply_text(
                    f"▶️ *Posting Resumed*\n\n"
                    f"Automatic posting is now active.\n"
                    f"📊 {len(future)} posts scheduled.",
                    parse_mode="Markdown"
                )
                logger.info(f"Posting resumed by {self._get_display_name(user)}")

        self.interaction_service.log_command(
            user_id=str(user.id),
            command="/resume",
            telegram_chat_id=update.effective_chat.id,
            telegram_message_id=update.message.message_id,
        )

    async def _handle_schedule(self, update, context):
        """Handle /schedule command - add more days to queue."""
        user = self._get_or_create_user(update.effective_user)

        # Parse days argument
        try:
            days = int(context.args[0]) if context.args else 7
            if days < 1 or days > 30:
                raise ValueError("Days must be between 1 and 30")
        except (ValueError, IndexError):
            await update.message.reply_text(
                "⚠️ *Usage:* /schedule N\n\n"
                "Where N is number of days (1-30).\n"
                "Example: /schedule 7",
                parse_mode="Markdown"
            )
            return

        # Import scheduler service here to avoid circular imports
        from src.services.core.scheduler import SchedulerService
        with SchedulerService() as scheduler:
            try:
                result = scheduler.create_schedule(days=days)
                await update.message.reply_text(
                    f"📅 *Schedule Created*\n\n"
                    f"✅ Scheduled: {result['scheduled']} posts\n"
                    f"⏭️ Skipped: {result['skipped']} (locked/queued)\n"
                    f"📊 Total slots: {result['total_slots']}",
                    parse_mode="Markdown"
                )
                logger.info(f"Schedule created by {self._get_display_name(user)}: {days} days, {result['scheduled']} posts")
            except Exception as e:
                await update.message.reply_text(
                    f"❌ *Error*\n\n{str(e)}",
                    parse_mode="Markdown"
                )
                logger.error(f"Schedule creation failed: {e}")

        self.interaction_service.log_command(
            user_id=str(user.id),
            command="/schedule",
            context={"days": days},
            telegram_chat_id=update.effective_chat.id,
            telegram_message_id=update.message.message_id,
        )

    async def _handle_stats(self, update, context):
        """Handle /stats command - show media library statistics."""
        user = self._get_or_create_user(update.effective_user)

        # Gather stats
        all_media = self.media_repo.get_all(is_active=True)
        total = len(all_media)
        never_posted = len([m for m in all_media if m.times_posted == 0])
        posted_once = len([m for m in all_media if m.times_posted == 1])
        posted_multiple = len([m for m in all_media if m.times_posted > 1])

        # Lock stats
        permanent_locks = len(self.lock_repo.get_permanent_locks())
        temp_locks = len([m for m in all_media if self.lock_repo.is_locked(str(m.id))])

        # Queue stats
        pending_count = self.queue_repo.count_pending()

        stats_msg = (
            f"📊 *Media Library Stats*\n\n"
            f"*Library:*\n"
            f"├─ Total active: {total}\n"
            f"├─ Never posted: {never_posted}\n"
            f"├─ Posted once: {posted_once}\n"
            f"└─ Posted 2+: {posted_multiple}\n\n"
            f"*Locks:*\n"
            f"├─ Permanent (rejected): {permanent_locks}\n"
            f"└─ Temporary (30-day): {temp_locks - permanent_locks}\n\n"
            f"*Queue:*\n"
            f"└─ Pending posts: {pending_count}"
        )

        await update.message.reply_text(stats_msg, parse_mode="Markdown")

        self.interaction_service.log_command(
            user_id=str(user.id),
            command="/stats",
            telegram_chat_id=update.effective_chat.id,
            telegram_message_id=update.message.message_id,
        )

    async def _handle_history(self, update, context):
        """Handle /history command - show recent post history."""
        user = self._get_or_create_user(update.effective_user)

        # Parse limit argument
        try:
            limit = int(context.args[0]) if context.args else 5
            limit = min(max(limit, 1), 20)  # Clamp between 1 and 20
        except (ValueError, IndexError):
            limit = 5

        recent = self.history_repo.get_recent_posts(hours=168)[:limit]  # Last 7 days

        if not recent:
            await update.message.reply_text(
                "📜 *No Recent History*\n\nNo posts in the last 7 days.",
                parse_mode="Markdown"
            )
            return

        lines = [f"📜 *Recent Posts* (last {len(recent)})\n"]
        for post in recent:
            status_emoji = "✅" if post.status == "posted" else "⏭️" if post.status == "skipped" else "🚫"
            time_str = post.posted_at.strftime("%b %d %H:%M") if post.posted_at else "?"
            username = f"@{post.posted_by_telegram_username}" if post.posted_by_telegram_username else "system"
            lines.append(f"{status_emoji} {time_str} - {username}")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

        self.interaction_service.log_command(
            user_id=str(user.id),
            command="/history",
            context={"limit": limit, "returned": len(recent)},
            telegram_chat_id=update.effective_chat.id,
            telegram_message_id=update.message.message_id,
        )

    async def _handle_locks(self, update, context):
        """Handle /locks command - show locked items."""
        user = self._get_or_create_user(update.effective_user)

        permanent = self.lock_repo.get_permanent_locks()

        if not permanent:
            await update.message.reply_text(
                "🔓 *No Permanent Locks*\n\nNo items have been permanently rejected.",
                parse_mode="Markdown"
            )
            return

        lines = [f"🔒 *Permanently Locked* ({len(permanent)})\n"]
        for i, lock in enumerate(permanent[:10], 1):  # Show max 10
            media = self.media_repo.get_by_id(str(lock.media_item_id))
            filename = media.file_name if media else "Unknown"
            lines.append(f"{i}. {filename[:30]}")

        if len(permanent) > 10:
            lines.append(f"\n... and {len(permanent) - 10} more")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

        self.interaction_service.log_command(
            user_id=str(user.id),
            command="/locks",
            context={"total_locks": len(permanent)},
            telegram_chat_id=update.effective_chat.id,
            telegram_message_id=update.message.message_id,
        )

    async def _handle_clear(self, update, context):
        """Handle /clear command - clear pending queue with confirmation."""
        user = self._get_or_create_user(update.effective_user)

        pending_count = self.queue_repo.count_pending()

        if pending_count == 0:
            await update.message.reply_text(
                "📭 *Queue Already Empty*",
                parse_mode="Markdown"
            )
            return

        keyboard = [
            [
                InlineKeyboardButton("✅ Yes, Clear All", callback_data="clear:confirm"),
                InlineKeyboardButton("❌ Cancel", callback_data="clear:cancel"),
            ]
        ]

        await update.message.reply_text(
            f"⚠️ *Clear Queue?*\n\n"
            f"This will remove all {pending_count} pending posts.\n"
            f"Media items will remain in the library.\n\n"
            f"This cannot be undone.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        self.interaction_service.log_command(
            user_id=str(user.id),
            command="/clear",
            context={"pending_count": pending_count},
            telegram_chat_id=update.effective_chat.id,
            telegram_message_id=update.message.message_id,
        )

    async def _handle_callback(self, update, context):
        """Handle inline button callbacks."""
        try:
            query = update.callback_query
            await query.answer()

            # Parse callback data
            parts = query.data.split(":")
            action = parts[0]
            data = parts[1] if len(parts) > 1 else None

            # Get user info
            user = self._get_or_create_user(query.from_user)

            # Queue item callbacks
            if action == "posted":
                await self._handle_posted(data, user, query)
            elif action == "skip":
                await self._handle_skipped(data, user, query)
            elif action == "autopost":
                await self._handle_autopost(data, user, query)
            elif action == "back":
                await self._handle_back(data, user, query)
            elif action == "reject":
                await self._handle_reject_confirmation(data, user, query)
            elif action == "confirm_reject":
                await self._handle_rejected(data, user, query)
            elif action == "cancel_reject":
                await self._handle_cancel_reject(data, user, query)
            # Resume callbacks
            elif action == "resume":
                await self._handle_resume_callback(data, user, query)
            # Clear callbacks
            elif action == "clear":
                await self._handle_clear_callback(data, user, query)
            # Settings callbacks
            elif action == "settings_toggle":
                await self._handle_settings_toggle(data, user, query)
            elif action == "settings_refresh":
                await self._refresh_settings_message(query)
            elif action == "settings_info":
                # Info buttons are non-interactive, just acknowledge
                await query.answer("Use CLI to change this setting")
            elif action == "settings_close":
                await self._handle_settings_close(query)
            # Schedule management callbacks
            elif action == "schedule_action":
                await self._handle_schedule_action(data, user, query)
            elif action == "schedule_confirm":
                await self._handle_schedule_confirm(data, user, query)
            # Instagram account selection callbacks
            elif action == "settings_accounts":
                if data == "select":
                    await self._handle_account_selection_menu(user, query)
                elif data == "back":
                    await self._refresh_settings_message(query)
            elif action == "switch_account":
                await self._handle_account_switch(data, user, query)
            # Instagram account configuration callbacks
            elif action == "accounts_config":
                if data == "add":
                    await self._handle_add_account_start(user, query, context)
                elif data == "remove":
                    await self._handle_remove_account_menu(user, query)
                elif data == "noop":
                    await query.answer()
            elif action == "account_remove":
                await self._handle_account_remove_confirm(data, user, query)
            elif action == "account_remove_confirmed":
                await self._handle_account_remove_execute(data, user, query)
            elif action == "account_add_cancel":
                await self._handle_add_account_cancel(user, query, context)
        finally:
            # Clean up open transactions to prevent "idle in transaction"
            self.cleanup_transactions()

    async def _handle_posted(self, queue_id: str, user, query):
        """Handle 'Posted' button click."""
        queue_item = self.queue_repo.get_by_id(queue_id)

        if not queue_item:
            await query.edit_message_caption(caption="⚠️ Queue item not found")
            return

        # Get media item
        media_item = self.media_repo.get_by_id(str(queue_item.media_item_id))

        # Create history record
        self.history_repo.create(
            media_item_id=str(queue_item.media_item_id),
            queue_item_id=queue_id,
            queue_created_at=queue_item.created_at,
            queue_deleted_at=datetime.utcnow(),
            scheduled_for=queue_item.scheduled_for,
            posted_at=datetime.utcnow(),
            status="posted",
            success=True,
            posted_by_user_id=str(user.id),
            posted_by_telegram_username=user.telegram_username,
        )

        # Update media item
        self.media_repo.increment_times_posted(str(queue_item.media_item_id))

        # Create 30-day lock to prevent reposting
        self.lock_service.create_lock(str(queue_item.media_item_id))

        # Delete from queue
        self.queue_repo.delete(queue_id)

        # Update user stats
        self.user_repo.increment_posts(str(user.id))

        # Update message
        new_caption = f"✅ Marked as posted by {self._get_display_name(user)}"
        await query.edit_message_caption(caption=new_caption)

        # Log interaction
        self.interaction_service.log_callback(
            user_id=str(user.id),
            callback_name="posted",
            context={
                "queue_item_id": queue_id,
                "media_id": str(queue_item.media_item_id),
                "media_filename": media_item.file_name if media_item else None,
            },
            telegram_chat_id=query.message.chat_id,
            telegram_message_id=query.message.message_id,
        )

        # Log outgoing bot response
        self.interaction_service.log_bot_response(
            response_type="caption_update",
            context={
                "caption": new_caption,
                "action": "posted",
                "media_filename": media_item.file_name if media_item else None,
                "edited": True,
            },
            telegram_chat_id=query.message.chat_id,
            telegram_message_id=query.message.message_id,
        )

        logger.info(f"Post marked as completed by {self._get_display_name(user)}")

    async def _handle_skipped(self, queue_id: str, user, query):
        """Handle 'Skip' button click."""
        queue_item = self.queue_repo.get_by_id(queue_id)

        if not queue_item:
            await query.edit_message_caption(caption="⚠️ Queue item not found")
            return

        # Get media item for context
        media_item = self.media_repo.get_by_id(str(queue_item.media_item_id))

        # Create history record
        self.history_repo.create(
            media_item_id=str(queue_item.media_item_id),
            queue_item_id=queue_id,
            queue_created_at=queue_item.created_at,
            queue_deleted_at=datetime.utcnow(),
            scheduled_for=queue_item.scheduled_for,
            posted_at=datetime.utcnow(),
            status="skipped",
            success=False,
            posted_by_user_id=str(user.id),
            posted_by_telegram_username=user.telegram_username,
        )

        # Delete from queue
        self.queue_repo.delete(queue_id)

        # Update message
        new_caption = f"⏭️ Skipped by {self._get_display_name(user)}"
        await query.edit_message_caption(caption=new_caption)

        # Log interaction
        self.interaction_service.log_callback(
            user_id=str(user.id),
            callback_name="skip",
            context={
                "queue_item_id": queue_id,
                "media_id": str(queue_item.media_item_id),
                "media_filename": media_item.file_name if media_item else None,
            },
            telegram_chat_id=query.message.chat_id,
            telegram_message_id=query.message.message_id,
        )

        # Log outgoing bot response
        self.interaction_service.log_bot_response(
            response_type="caption_update",
            context={
                "caption": new_caption,
                "action": "skipped",
                "media_filename": media_item.file_name if media_item else None,
                "edited": True,
            },
            telegram_chat_id=query.message.chat_id,
            telegram_message_id=query.message.message_id,
        )

        logger.info(f"Post skipped by {self._get_display_name(user)}")

    async def _handle_autopost(self, queue_id: str, user, query):
        """
        Handle 'Auto Post' button click.

        This uploads the media to Cloudinary and posts to Instagram via API.
        Includes CRITICAL safety gates to prevent accidental Facebook posting.
        """
        queue_item = self.queue_repo.get_by_id(queue_id)

        if not queue_item:
            await query.edit_message_caption(caption="⚠️ Queue item not found")
            return

        # Get media item
        media_item = self.media_repo.get_by_id(str(queue_item.media_item_id))
        if not media_item:
            await query.edit_message_caption(caption="⚠️ Media item not found")
            return

        # ============================================
        # CRITICAL SAFETY GATES
        # ============================================
        from src.services.integrations.instagram_api import InstagramAPIService
        from src.services.integrations.cloud_storage import CloudStorageService

        # Create services and ensure cleanup on exit
        instagram_service = InstagramAPIService()
        cloud_service = CloudStorageService()
        try:
            await self._do_autopost(queue_id, queue_item, media_item, user, query, instagram_service, cloud_service)
        finally:
            # Ensure services are cleaned up to prevent connection pool exhaustion
            instagram_service.close()
            cloud_service.close()

    async def _do_autopost(self, queue_id, queue_item, media_item, user, query, instagram_service, cloud_service):
        """Internal method to perform auto-post with pre-created services."""

        # Run comprehensive safety check
        safety_result = instagram_service.safety_check_before_post()

        if not safety_result["safe_to_post"]:
            error_list = "\n".join([f"• {e}" for e in safety_result["errors"]])
            caption = (
                f"🚫 *SAFETY CHECK FAILED*\n\n"
                f"Cannot auto-post due to:\n{error_list}\n\n"
                f"Please check your configuration."
            )
            await query.edit_message_caption(caption=caption, parse_mode="Markdown")
            logger.error(f"Auto-post safety check failed: {safety_result['errors']}")
            return

        # ============================================
        # UPLOAD TO CLOUDINARY (runs in both dry run and real mode)
        # ============================================
        try:
            # Update message to show progress
            await query.edit_message_caption(
                caption=f"⏳ *Uploading to Cloudinary...*",
                parse_mode="Markdown"
            )

            # Step 1: Upload to Cloudinary (uses passed-in cloud_service)
            upload_result = cloud_service.upload_media(
                file_path=media_item.file_path,
                folder="instagram_stories",
            )

            cloud_url = upload_result.get("url")
            cloud_public_id = upload_result.get("public_id")

            if not cloud_url:
                raise Exception(f"Cloudinary upload failed: No URL returned")

            logger.info(f"Uploaded to Cloudinary: {cloud_public_id}")

            # Update media item with cloud info
            self.media_repo.update_cloud_info(
                media_id=str(media_item.id),
                cloud_url=cloud_url,
                cloud_public_id=cloud_public_id,
                cloud_uploaded_at=datetime.utcnow(),
            )

            # ============================================
            # DRY RUN MODE - Stop before Instagram API
            # ============================================
            if settings.DRY_RUN_MODE:
                # Dry run: only show Test Again and Back buttons
                # Don't show Posted/Skip/Reject to prevent accidental marking
                keyboard = [
                    [
                        InlineKeyboardButton(
                            "🔄 Test Again",
                            callback_data=f"autopost:{queue_id}"
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "↩️ Back to Queue Item",
                            callback_data=f"back:{queue_id}"
                        ),
                    ],
                ]

                # Escape filename for Markdown
                escaped_filename = _escape_markdown(media_item.file_name)

                # Fetch account username from API (cached)
                account_info = await instagram_service.get_account_info()
                if account_info.get("username"):
                    account_display = f"@{account_info['username']}"
                else:
                    account_display = f"ID: {settings.INSTAGRAM_ACCOUNT_ID}"

                # Apply the same transformation we'd use for Instagram
                media_type = "VIDEO" if media_item.file_path.lower().endswith(('.mp4', '.mov')) else "IMAGE"
                if media_type == "IMAGE":
                    preview_url = cloud_service.get_story_optimized_url(cloud_url)
                else:
                    preview_url = cloud_url

                caption = (
                    f"🧪 DRY RUN - Cloudinary Upload Complete\n\n"
                    f"📁 File: {media_item.file_name}\n"
                    f"📸 Account: {account_display}\n\n"
                    f"✅ Cloudinary upload: Success\n"
                    f"🔗 Preview (with blur): {preview_url}\n\n"
                    f"⏸️ Stopped before Instagram API\n"
                    f"(DRY_RUN_MODE=true)\n\n"
                    f"• No Instagram post made\n"
                    f"• No history recorded\n"
                    f"• No TTL lock created\n"
                    f"• Queue item preserved\n\n"
                    f"Tested by: {self._get_display_name(user)}"
                )
                await query.edit_message_caption(
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                )

                # Log interaction (dry run - but Cloudinary worked)
                self.interaction_service.log_callback(
                    user_id=str(user.id),
                    callback_name="autopost",
                    context={
                        "queue_item_id": queue_id,
                        "media_id": str(queue_item.media_item_id),
                        "media_filename": media_item.file_name,
                        "cloud_url": cloud_url,
                        "cloud_public_id": cloud_public_id,
                        "dry_run": True,
                    },
                    telegram_chat_id=query.message.chat_id,
                    telegram_message_id=query.message.message_id,
                )

                logger.info(f"[DRY RUN] Cloudinary upload complete, stopped before Instagram API. User: {self._get_display_name(user)}, File: {media_item.file_name}")
                return

            # ============================================
            # REAL POSTING - Continue to Instagram API
            # ============================================
            # Step 2: Post to Instagram
            await query.edit_message_caption(
                caption=f"⏳ *Posting to Instagram...*",
                parse_mode="Markdown"
            )

            # Determine media type
            media_type = "VIDEO" if media_item.file_path.lower().endswith(('.mp4', '.mov')) else "IMAGE"

            # Apply 9:16 Story transformation (blurred background padding)
            if media_type == "IMAGE":
                story_url = cloud_service.get_story_optimized_url(cloud_url)
            else:
                # Videos don't need the same transformation
                story_url = cloud_url

            post_result = await instagram_service.post_story(
                media_url=story_url,
                media_type=media_type,
            )

            story_id = post_result.get("story_id")
            logger.info(f"Posted to Instagram: story_id={story_id}")

            # Step 3: Cleanup Cloudinary (optional - can keep for debugging)
            # cloud_service.delete_media(cloud_public_id)

            # Step 4: Create history record
            self.history_repo.create(
                media_item_id=str(queue_item.media_item_id),
                queue_item_id=queue_id,
                queue_created_at=queue_item.created_at,
                queue_deleted_at=datetime.utcnow(),
                scheduled_for=queue_item.scheduled_for,
                posted_at=datetime.utcnow(),
                status="posted",
                success=True,
                posted_by_user_id=str(user.id),
                posted_by_telegram_username=user.telegram_username,
                posting_method="instagram_api",
                instagram_story_id=story_id,
            )

            # Update media item
            self.media_repo.increment_times_posted(str(queue_item.media_item_id))

            # Create 30-day lock to prevent reposting
            self.lock_service.create_lock(str(queue_item.media_item_id))

            # Delete from queue
            self.queue_repo.delete(queue_id)

            # Update user stats
            self.user_repo.increment_posts(str(user.id))

            # Success message - check verbose setting
            chat_settings = self.settings_service.get_settings(query.message.chat_id)
            verbose = chat_settings.show_verbose_notifications if chat_settings.show_verbose_notifications is not None else True

            # Fetch account username from API (cached)
            account_info = await instagram_service.get_account_info()
            if account_info.get("username"):
                account_display = f"@{account_info['username']}"
            else:
                account_display = f"ID: {settings.INSTAGRAM_ACCOUNT_ID}"

            if verbose:
                # Verbose ON: Show detailed info
                escaped_filename = _escape_markdown(media_item.file_name)
                caption = (
                    f"✅ *Posted to Instagram!*\n\n"
                    f"📁 {escaped_filename}\n"
                    f"📸 Account: {account_display}\n"
                    f"🆔 Story ID: {story_id[:20]}...\n\n"
                    f"Posted by: {self._get_display_name(user)}"
                )
            else:
                # Verbose OFF: Show minimal info
                caption = f"✅ Posted to {account_display}"

            await query.edit_message_caption(caption=caption, parse_mode="Markdown")

            # Log interaction
            self.interaction_service.log_callback(
                user_id=str(user.id),
                callback_name="autopost",
                context={
                    "queue_item_id": queue_id,
                    "media_id": str(queue_item.media_item_id),
                    "media_filename": media_item.file_name,
                    "instagram_story_id": story_id,
                    "dry_run": False,
                    "success": True,
                },
                telegram_chat_id=query.message.chat_id,
                telegram_message_id=query.message.message_id,
            )

            # Log outgoing bot response
            self.interaction_service.log_bot_response(
                response_type="caption_update",
                context={
                    "caption": caption,
                    "action": "autopost_success",
                    "media_filename": media_item.file_name,
                    "instagram_story_id": story_id,
                    "edited": True,
                },
                telegram_chat_id=query.message.chat_id,
                telegram_message_id=query.message.message_id,
            )

            logger.info(f"Auto-posted to Instagram by {self._get_display_name(user)}: {media_item.file_name} (story_id={story_id})")

        except Exception as e:
            # Error handling
            error_msg = str(e)
            logger.error(f"Auto-post failed: {error_msg}", exc_info=True)

            caption = (
                f"❌ *Auto Post Failed*\n\n"
                f"Error: {error_msg[:200]}\n\n"
                f"You can try again or use manual posting."
            )

            # Rebuild keyboard with all buttons
            keyboard = []
            if settings.ENABLE_INSTAGRAM_API:
                keyboard.append([
                    InlineKeyboardButton(
                        "🔄 Retry Auto Post",
                        callback_data=f"autopost:{queue_id}"
                    ),
                ])
            keyboard.extend([
                [
                    InlineKeyboardButton("✅ Posted", callback_data=f"posted:{queue_id}"),
                    InlineKeyboardButton("⏭️ Skip", callback_data=f"skip:{queue_id}"),
                ],
                [
                    InlineKeyboardButton("📱 Open Instagram", url="https://www.instagram.com/"),
                ],
                [
                    InlineKeyboardButton("🚫 Reject", callback_data=f"reject:{queue_id}"),
                ]
            ])

            await query.edit_message_caption(
                caption=caption,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )

            # Log interaction (failure)
            self.interaction_service.log_callback(
                user_id=str(user.id),
                callback_name="autopost",
                context={
                    "queue_item_id": queue_id,
                    "media_id": str(queue_item.media_item_id),
                    "media_filename": media_item.file_name,
                    "dry_run": False,
                    "success": False,
                    "error": error_msg[:200],
                },
                telegram_chat_id=query.message.chat_id,
                telegram_message_id=query.message.message_id,
            )

    async def _handle_back(self, queue_id: str, user, query):
        """Handle 'Back' button - restore original queue item message."""
        queue_item = self.queue_repo.get_by_id(queue_id)

        if not queue_item:
            await query.edit_message_caption(caption="⚠️ Queue item not found")
            return

        media_item = self.media_repo.get_by_id(str(queue_item.media_item_id))

        if not media_item:
            await query.edit_message_caption(caption="⚠️ Media item not found")
            return

        # Rebuild original caption
        caption = self._build_caption(media_item, queue_item)

        # Rebuild original keyboard (including Auto Post if enabled)
        keyboard = []
        if settings.ENABLE_INSTAGRAM_API:
            keyboard.append([
                InlineKeyboardButton(
                    "🤖 Auto Post to Instagram",
                    callback_data=f"autopost:{queue_id}"
                ),
            ])
        keyboard.extend([
            [
                InlineKeyboardButton("✅ Posted", callback_data=f"posted:{queue_id}"),
                InlineKeyboardButton("⏭️ Skip", callback_data=f"skip:{queue_id}"),
            ],
            [
                InlineKeyboardButton("📱 Open Instagram", url="https://www.instagram.com/"),
            ],
            [
                InlineKeyboardButton("🚫 Reject", callback_data=f"reject:{queue_id}"),
            ]
        ])

        await query.edit_message_caption(
            caption=caption,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        logger.info(f"Returned to queue item by {self._get_display_name(user)}")

    async def _handle_reject_confirmation(self, queue_id: str, user, query):
        """Show confirmation dialog before permanently rejecting media."""
        queue_item = self.queue_repo.get_by_id(queue_id)

        if not queue_item:
            await query.edit_message_caption(caption="⚠️ Queue item not found")
            return

        # Get media item for filename
        media_item = self.media_repo.get_by_id(str(queue_item.media_item_id))
        file_name = media_item.file_name if media_item else "Unknown"

        # Build confirmation keyboard (short labels - details in message above)
        keyboard = [
            [
                InlineKeyboardButton("✅ Yes", callback_data=f"confirm_reject:{queue_id}"),
                InlineKeyboardButton("❌ No", callback_data=f"cancel_reject:{queue_id}"),
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
            parse_mode="Markdown"
        )

        # Log interaction (showing confirmation dialog)
        self.interaction_service.log_callback(
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

    async def _handle_cancel_reject(self, queue_id: str, user, query):
        """Cancel rejection and restore original buttons."""
        queue_item = self.queue_repo.get_by_id(queue_id)

        if not queue_item:
            await query.edit_message_caption(caption="⚠️ Queue item not found")
            return

        # Get media item for caption rebuild
        media_item = self.media_repo.get_by_id(str(queue_item.media_item_id))

        if not media_item:
            await query.edit_message_caption(caption="⚠️ Media item not found")
            return

        # Rebuild original caption
        caption = self._build_caption(media_item, queue_item)

        # Rebuild original keyboard (including Auto Post if enabled)
        keyboard = []
        if settings.ENABLE_INSTAGRAM_API:
            keyboard.append([
                InlineKeyboardButton(
                    "🤖 Auto Post to Instagram",
                    callback_data=f"autopost:{queue_id}"
                ),
            ])
        keyboard.extend([
            [
                InlineKeyboardButton("✅ Posted", callback_data=f"posted:{queue_id}"),
                InlineKeyboardButton("⏭️ Skip", callback_data=f"skip:{queue_id}"),
            ],
            [
                InlineKeyboardButton("📱 Open Instagram", url="https://www.instagram.com/"),
            ],
            [
                InlineKeyboardButton("🚫 Reject", callback_data=f"reject:{queue_id}"),
            ]
        ])

        await query.edit_message_caption(
            caption=caption,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        # Log interaction
        self.interaction_service.log_callback(
            user_id=str(user.id),
            callback_name="cancel_reject",
            context={
                "queue_item_id": queue_id,
                "media_id": str(queue_item.media_item_id),
            },
            telegram_chat_id=query.message.chat_id,
            telegram_message_id=query.message.message_id,
        )

        logger.info(f"Reject cancelled by {self._get_display_name(user)}")

    async def _handle_rejected(self, queue_id: str, user, query):
        """Handle confirmed rejection - permanently blocks media."""
        queue_item = self.queue_repo.get_by_id(queue_id)

        if not queue_item:
            await query.edit_message_caption(caption="⚠️ Queue item not found")
            return

        # Get media item for filename
        media_item = self.media_repo.get_by_id(str(queue_item.media_item_id))

        # Create history record
        self.history_repo.create(
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
        )

        # Create PERMANENT lock (infinite TTL)
        self.lock_service.create_permanent_lock(
            str(queue_item.media_item_id),
            created_by_user_id=str(user.id)
        )

        # Delete from queue
        self.queue_repo.delete(queue_id)

        # Update message with clear feedback
        caption = (
            f"🚫 *Permanently Rejected*\n\n"
            f"By: {self._get_display_name(user)}\n"
            f"File: {media_item.file_name if media_item else 'Unknown'}\n\n"
            f"This media will never be queued again."
        )
        await query.edit_message_caption(caption=caption, parse_mode="Markdown")

        # Log interaction
        self.interaction_service.log_callback(
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
        self.interaction_service.log_bot_response(
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

        logger.info(f"Post permanently rejected by {self._get_display_name(user)}: {media_item.file_name if media_item else queue_item.media_item_id}")

    async def _handle_resume_callback(self, action: str, user, query):
        """Handle resume callback buttons (reschedule/clear/force)."""
        now = datetime.utcnow()
        all_pending = self.queue_repo.get_all(status="pending")
        overdue = [p for p in all_pending if p.scheduled_for < now]

        if action == "reschedule":
            # Reschedule overdue posts to future times
            # Get time slots for rescheduling
            rescheduled = 0
            for i, item in enumerate(overdue):
                # Spread out over next few hours
                new_time = now + timedelta(hours=1 + (i * 0.5))
                self.queue_repo.update_scheduled_time(str(item.id), new_time)
                rescheduled += 1

            self.set_paused(False, user)
            await query.edit_message_text(
                f"✅ *Posting Resumed*\n\n"
                f"🔄 Rescheduled {rescheduled} overdue posts.\n"
                f"First post in ~1 hour.",
                parse_mode="Markdown"
            )
            logger.info(f"Posting resumed by {self._get_display_name(user)}, rescheduled {rescheduled} overdue posts")

        elif action == "clear":
            # Clear all overdue posts
            cleared = 0
            for item in overdue:
                self.queue_repo.delete(str(item.id))
                cleared += 1

            self.set_paused(False, user)
            remaining = len(all_pending) - cleared
            await query.edit_message_text(
                f"✅ *Posting Resumed*\n\n"
                f"🗑️ Cleared {cleared} overdue posts.\n"
                f"📊 {remaining} scheduled posts remaining.",
                parse_mode="Markdown"
            )
            logger.info(f"Posting resumed by {self._get_display_name(user)}, cleared {cleared} overdue posts")

        elif action == "force":
            # Resume without handling overdue - they'll be processed immediately
            self.set_paused(False, user)
            await query.edit_message_text(
                f"✅ *Posting Resumed*\n\n"
                f"⚠️ {len(overdue)} overdue posts will be processed immediately.",
                parse_mode="Markdown"
            )
            logger.info(f"Posting resumed (force) by {self._get_display_name(user)}, {len(overdue)} overdue posts")

        # Log interaction
        self.interaction_service.log_callback(
            user_id=str(user.id),
            callback_name=f"resume:{action}",
            context={"overdue_count": len(overdue), "action": action},
            telegram_chat_id=query.message.chat_id,
            telegram_message_id=query.message.message_id,
        )

    async def _handle_clear_callback(self, action: str, user, query):
        """Handle clear queue callback buttons (confirm/cancel)."""
        if action == "confirm":
            # Clear all pending posts
            all_pending = self.queue_repo.get_all(status="pending")
            cleared = 0
            for item in all_pending:
                self.queue_repo.delete(str(item.id))
                cleared += 1

            await query.edit_message_text(
                f"✅ *Queue Cleared*\n\n"
                f"🗑️ Removed {cleared} pending posts.\n"
                f"Media items remain in library.",
                parse_mode="Markdown"
            )
            logger.info(f"Queue cleared by {self._get_display_name(user)}: {cleared} posts removed")

        elif action == "cancel":
            await query.edit_message_text(
                f"❌ *Cancelled*\n\nQueue was not cleared.",
                parse_mode="Markdown"
            )

        # Log interaction
        self.interaction_service.log_callback(
            user_id=str(user.id),
            callback_name=f"clear:{action}",
            context={"action": action},
            telegram_chat_id=query.message.chat_id,
            telegram_message_id=query.message.message_id,
        )

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
                f"🤖 v1.0.1"
            )

            # Send to admin
            await self.bot.send_message(
                chat_id=settings.ADMIN_TELEGRAM_CHAT_ID,
                text=message,
                parse_mode="Markdown"
            )

            logger.info("Startup notification sent to admin")

        except Exception as e:
            logger.error(f"Failed to send startup notification: {e}")

    async def send_shutdown_notification(self, uptime_seconds: int = 0, posts_sent: int = 0):
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
                parse_mode="Markdown"
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
