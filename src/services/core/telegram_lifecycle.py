"""Lifecycle notifications for the Telegram bot (startup/shutdown)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from src.config.settings import settings
from src.utils.logger import logger
from src import __version__

if TYPE_CHECKING:
    from src.services.core.telegram_service import TelegramService


class TelegramLifecycleHandler:
    """Sends startup and shutdown notifications to the admin chat."""

    def __init__(self, service: TelegramService):
        self.service = service

    async def send_startup_notification(self):
        """Send startup notification to admin with system status."""
        if not settings.SEND_LIFECYCLE_NOTIFICATIONS:
            return

        try:
            pending_count = self.service.queue_repo.count_pending()
            media_count = len(self.service.media_repo.get_all(is_active=True))
            recent_posts = self.service.history_repo.get_recent_posts(hours=24)
            last_post_time = recent_posts[0].posted_at if recent_posts else None

            if last_post_time:
                time_diff = datetime.now(timezone.utc) - last_post_time
                hours = int(time_diff.total_seconds() / 3600)
                last_posted = f"{hours}h ago" if hours > 0 else "< 1h ago"
            else:
                last_posted = "Never"

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

            await self.service.bot.send_message(
                chat_id=self.service.admin_chat_id,
                text=message,
                parse_mode="Markdown",
            )

            logger.info("Startup notification sent to admin")

        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to send startup notification: {e}")

    async def send_shutdown_notification(
        self, uptime_seconds: int = 0, posts_sent: int = 0
    ):
        """Send shutdown notification to admin with session summary."""
        if not settings.SEND_LIFECYCLE_NOTIFICATIONS:
            return

        try:
            hours = int(uptime_seconds / 3600)
            minutes = int((uptime_seconds % 3600) / 60)
            uptime_str = f"{hours}h {minutes}m"

            message = (
                f"🔴 *Storyline AI Stopped*\n\n"
                f"📊 *Session Summary:*\n"
                f"├─ Uptime: {uptime_str}\n"
                f"├─ Posts sent: {posts_sent}\n"
                f"└─ Shutdown: Graceful\n\n"
                f"See you next time! 👋"
            )

            await self.service.bot.send_message(
                chat_id=self.service.admin_chat_id,
                text=message,
                parse_mode="Markdown",
            )

            logger.info("Shutdown notification sent to admin")

        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to send shutdown notification: {e}")
