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
        queue_item = self.queue_repo.get_by_id(queue_item_id)
        if not queue_item:
            logger.error(f"Queue item not found: {queue_item_id}")
            return False

        media_item = self.media_repo.get_by_id(str(queue_item.media_item_id))
        if not media_item:
            logger.error(f"Media item not found: {queue_item.media_item_id}")
            return False

        # Build caption
        caption = self._build_caption(media_item)

        # Build inline keyboard
        keyboard = [
            [
                InlineKeyboardButton("✅ Posted", callback_data=f"posted:{queue_item_id}"),
                InlineKeyboardButton("⏭️ Skip", callback_data=f"skip:{queue_item_id}"),
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

    def _build_caption(self, media_item) -> str:
        """Build caption for Telegram message."""
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
