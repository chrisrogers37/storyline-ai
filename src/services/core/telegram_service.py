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
from src.services.core.media_lock import MediaLockService
from src.config.settings import settings
from src.utils.logger import logger
from datetime import datetime


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
        self.lock_service = MediaLockService()
        self.bot = None
        self.application = None

    async def initialize(self):
        """Initialize Telegram bot."""
        self.bot = Bot(token=self.bot_token)
        self.application = Application.builder().token(self.bot_token).build()

        # Add handlers
        self.application.add_handler(CommandHandler("start", self._handle_start))
        self.application.add_handler(CommandHandler("status", self._handle_status))
        self.application.add_handler(CallbackQueryHandler(self._handle_callback))

        logger.info("Telegram bot initialized")

    async def send_notification(self, queue_item_id: str) -> bool:
        """
        Send posting notification to Telegram channel.

        Args:
            queue_item_id: Queue item ID

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
        caption = self._build_caption(media_item, queue_item)

        # Build inline keyboard
        keyboard = [
            [
                InlineKeyboardButton("✅ Posted", callback_data=f"posted:{queue_item_id}"),
                InlineKeyboardButton("⏭️ Skip", callback_data=f"skip:{queue_item_id}"),
            ],
            [
                InlineKeyboardButton("🚫 Reject", callback_data=f"reject:{queue_item_id}"),
            ],
            [
                InlineKeyboardButton("📱 Open Instagram", url="https://www.instagram.com/"),
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

    def _build_caption(self, media_item, queue_item=None) -> str:
        """Build caption for Telegram message with enhanced or simple formatting."""

        if settings.CAPTION_STYLE == "enhanced":
            return self._build_enhanced_caption(media_item, queue_item)
        else:
            return self._build_simple_caption(media_item)

    def _build_simple_caption(self, media_item) -> str:
        """Build simple caption (original format)."""
        caption_parts = []

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

    def _build_enhanced_caption(self, media_item, queue_item=None) -> str:
        """Build enhanced caption with better formatting."""
        lines = []

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
        await update.message.reply_text("👋 Storyline AI Bot\n\nUse /status to check queue status.")

    async def _handle_status(self, update, context):
        """Handle /status command."""
        pending_count = self.queue_repo.count_pending()
        recent_posts = self.history_repo.get_recent_posts(hours=24)

        status_msg = f"📊 Queue Status\n\n"
        status_msg += f"Pending: {pending_count}\n"
        status_msg += f"Posted (24h): {len(recent_posts)}"

        await update.message.reply_text(status_msg)

    async def _handle_callback(self, update, context):
        """Handle inline button callbacks."""
        query = update.callback_query
        await query.answer()

        # Parse callback data
        action, queue_id = query.data.split(":")

        # Get user info
        user = self._get_or_create_user(query.from_user)

        if action == "posted":
            await self._handle_posted(queue_id, user, query)
        elif action == "skip":
            await self._handle_skipped(queue_id, user, query)
        elif action == "reject":
            await self._handle_rejected(queue_id, user, query)

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
        await query.edit_message_caption(caption=f"✅ Marked as posted by @{user.telegram_username}")

        logger.info(f"Post marked as completed by {user.telegram_username}")

    async def _handle_skipped(self, queue_id: str, user, query):
        """Handle 'Skip' button click."""
        queue_item = self.queue_repo.get_by_id(queue_id)

        if not queue_item:
            await query.edit_message_caption(caption="⚠️ Queue item not found")
            return

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
        await query.edit_message_caption(caption=f"⏭️ Skipped by @{user.telegram_username}")

        logger.info(f"Post skipped by {user.telegram_username}")

    async def _handle_rejected(self, queue_id: str, user, query):
        """Handle 'Reject' button click - permanently blocks media."""
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
            f"By: @{user.telegram_username}\n"
            f"File: {media_item.file_name if media_item else 'Unknown'}\n\n"
            f"This media will never be queued again."
        )
        await query.edit_message_caption(caption=caption, parse_mode="Markdown")

        logger.info(f"Post permanently rejected by {user.telegram_username}: {media_item.file_name if media_item else queue_item.media_item_id}")

    def _get_or_create_user(self, telegram_user):
        """Get or create user from Telegram data."""
        user = self.user_repo.get_by_telegram_id(telegram_user.id)

        if not user:
            user = self.user_repo.create(
                telegram_user_id=telegram_user.id,
                telegram_username=telegram_user.username,
                telegram_first_name=telegram_user.first_name,
                telegram_last_name=telegram_user.last_name,
            )
            logger.info(f"New user discovered: @{telegram_user.username}")
        else:
            self.user_repo.update_last_seen(str(user.id))

        return user

    async def send_startup_notification(self):
        """Send startup notification to admin with system status."""
        if not settings.SEND_LIFECYCLE_NOTIFICATIONS:
            return

        try:
            # Gather system status
            pending_count = self.queue_repo.count_pending()
            media_count = len(self.media_repo.get_all(active_only=True))
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
