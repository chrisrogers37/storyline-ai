"""Telegram service - bot operations and callbacks."""
from pathlib import Path
from typing import Optional
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, CommandHandler

from src.services.base_service import BaseService
from src.repositories.user_repository import UserRepository
from src.repositories.queue_repository import QueueRepository
from src.repositories.history_repository import HistoryRepository
from src.repositories.media_repository import MediaRepository
from src.repositories.lock_repository import LockRepository
from src.services.core.media_lock import MediaLockService
from src.services.core.interaction_service import InteractionService
from src.config.settings import settings
from src.utils.logger import logger
from datetime import datetime, timedelta


class TelegramService(BaseService):
    """All Telegram bot operations."""

    # Class-level pause state (persists during runtime)
    _paused = False

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
        self.bot = None
        self.application = None

    @property
    def is_paused(self) -> bool:
        """Check if bot posting is paused."""
        return TelegramService._paused

    def set_paused(self, paused: bool):
        """Set pause state."""
        TelegramService._paused = paused

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
        self.application.add_handler(CallbackQueryHandler(self._handle_callback))

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

        # Build caption (pass queue_item for enhanced mode)
        caption = self._build_caption(media_item, queue_item, force_sent=force_sent)

        # Build inline keyboard
        # Note: Instagram button is above Reject so it's not blocked by "Save Image" popup
        keyboard = [
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
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            # Send photo with buttons
            with open(media_item.file_path, "rb") as photo:
                message = await self.bot.send_photo(
                    chat_id=self.channel_id, photo=photo, caption=caption, reply_markup=reply_markup
                )

            # Save telegram message ID
            self.queue_repo.set_telegram_message(queue_item_id, message.message_id, self.channel_id)

            logger.info(f"Sent Telegram notification for {media_item.file_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return False

    def _build_caption(self, media_item, queue_item=None, force_sent: bool = False) -> str:
        """Build caption for Telegram message with enhanced or simple formatting."""

        if settings.CAPTION_STYLE == "enhanced":
            return self._build_enhanced_caption(media_item, queue_item, force_sent=force_sent)
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

    def _build_enhanced_caption(self, media_item, queue_item=None, force_sent: bool = False) -> str:
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

        status_msg = (
            f"✅ *Storyline AI Status*\n\n"
            f"🤖 Bot: Online\n"
            f"📊 Queue: {pending_count} pending\n"
            f"📁 Media Library: {media_count} active\n"
            f"🔒 Locked Items: {locked_count}\n"
            f"⏰ Next Post: {next_post_str}\n"
            f"📤 Last Posted: {last_posted}\n"
            f"📈 Posted (24h): {len(recent_posts)}"
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
        """Handle /next command - force send next scheduled post immediately."""
        user = self._get_or_create_user(update.effective_user)

        # Get next pending item (earliest scheduled, regardless of time)
        all_pending = self.queue_repo.get_all(status="pending")

        if not all_pending:
            await update.message.reply_text(
                "📭 *Queue Empty*\n\nNo posts to send.",
                parse_mode="Markdown"
            )
            return

        # Take the first one (earliest scheduled)
        queue_item = all_pending[0]
        media_item = self.media_repo.get_by_id(str(queue_item.media_item_id))

        if not media_item:
            await update.message.reply_text(
                "⚠️ *Error*\n\nMedia item not found.",
                parse_mode="Markdown"
            )
            return

        # Send the notification to channel (with force_sent flag for caption)
        success = await self.send_notification(str(queue_item.id), force_sent=True)

        if success:
            # Update status to processing
            self.queue_repo.update_status(str(queue_item.id), "processing")
        else:
            # Only send message on failure
            await update.message.reply_text(
                f"❌ *Failed to send*\n\nCheck logs for details.",
                parse_mode="Markdown"
            )

        # Log interaction
        self.interaction_service.log_command(
            user_id=str(user.id),
            command="/next",
            context={
                "queue_item_id": str(queue_item.id),
                "media_id": str(queue_item.media_item_id),
                "media_filename": media_item.file_name,
                "success": success,
            },
            telegram_chat_id=update.effective_chat.id,
            telegram_message_id=update.message.message_id,
        )

        logger.info(f"Force-sent next post by {self._get_display_name(user)}: {media_item.file_name}")

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
            "/pause - Pause automatic posting\n"
            "/resume - Resume posting\n"
            "/status - System health check\n\n"
            "*Info Commands:*\n"
            "/stats - Media library statistics\n"
            "/history N - Show last N posts\n"
            "/locks - View locked items\n"
            "/help - Show this help\n\n"
            "*Button Actions:*\n"
            "✅ Posted - Mark as posted\n"
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

    async def _handle_pause(self, update, context):
        """Handle /pause command - pause automatic posting."""
        user = self._get_or_create_user(update.effective_user)

        if self.is_paused:
            await update.message.reply_text(
                "⏸️ *Already Paused*\n\nAutomatic posting is already paused.\nUse /resume to restart.",
                parse_mode="Markdown"
            )
        else:
            self.set_paused(True)
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
                self.set_paused(False)
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
        scheduler = SchedulerService()

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
        await query.edit_message_caption(caption=f"✅ Marked as posted by {self._get_display_name(user)}")

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
        await query.edit_message_caption(caption=f"⏭️ Skipped by {self._get_display_name(user)}")

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

        logger.info(f"Post skipped by {self._get_display_name(user)}")

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

        # Rebuild original keyboard
        keyboard = [
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
        ]

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

        logger.info(f"Post permanently rejected by {self._get_display_name(user)}: {media_item.file_name if media_item else queue_item.media_item_id}")

    async def _handle_resume_callback(self, action: str, user, query):
        """Handle resume callback buttons (reschedule/clear/force)."""
        now = datetime.utcnow()
        all_pending = self.queue_repo.get_all(status="pending")
        overdue = [p for p in all_pending if p.scheduled_for < now]

        if action == "reschedule":
            # Reschedule overdue posts to future times
            from src.services.core.scheduler import SchedulerService
            scheduler = SchedulerService()

            # Get time slots for rescheduling
            rescheduled = 0
            for i, item in enumerate(overdue):
                # Spread out over next few hours
                new_time = now + timedelta(hours=1 + (i * 0.5))
                self.queue_repo.update_scheduled_time(str(item.id), new_time)
                rescheduled += 1

            self.set_paused(False)
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

            self.set_paused(False)
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
            self.set_paused(False)
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
