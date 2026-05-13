"""Lifecycle notifications for the Telegram bot (startup/shutdown)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.config.settings import settings
from src.services.core.dashboard_service import DashboardService
from src.services.core.telegram_utils import escape_markdown, format_last_post
from src.utils.logger import logger
from src import __version__

if TYPE_CHECKING:
    from src.services.core.telegram_service import TelegramService


class TelegramLifecycleHandler:
    """Sends startup and shutdown notifications to the admin chat."""

    def __init__(self, service: TelegramService):
        self.service = service

    def _lifecycle_notifications_enabled(self) -> bool:
        """Resolve the per-admin-chat lifecycle-notifications preference.

        Reads ``chat_settings.send_lifecycle_notifications`` for the admin
        chat; falls back to the env default when the chat row or column
        value is missing (e.g. first boot before bootstrap, or chats from
        before migration 030).
        """
        try:
            chat = self.service.settings_service.get_settings_if_exists(
                self.service.admin_chat_id
            )
        except Exception:  # noqa: BLE001 — never block startup on a DB hiccup
            return bool(settings.SEND_LIFECYCLE_NOTIFICATIONS)
        if chat is None or chat.send_lifecycle_notifications is None:
            return bool(settings.SEND_LIFECYCLE_NOTIFICATIONS)
        return bool(chat.send_lifecycle_notifications)

    async def send_startup_notification(self):
        """Send startup notification to admin with multi-instance overview."""
        if not self._lifecycle_notifications_enabled():
            return

        try:
            with DashboardService() as dash:
                data = dash.get_user_instances(self.service.admin_chat_id)

            instances = data["instances"]
            lines = ["🟢 *Storydump Started*\n"]

            if instances:
                lines.append("Your instances:")
                for i, inst in enumerate(instances, 1):
                    raw_name = (
                        inst["display_name"] or f"Chat {inst['telegram_chat_id']}"
                    )
                    name = escape_markdown(raw_name)
                    media = inst["media_count"]
                    ppd = inst["posts_per_day"]
                    last = format_last_post(inst["last_post_at"])
                    status = "⏸️ paused" if inst["is_paused"] else "✅ active"
                    lines.append(
                        f"{i}. *{name}* — {ppd}/day, {media} media, "
                        f"last post {last} ({status})"
                    )
            else:
                lines.append("No instances configured yet.")

            lines.append(f"\n🤖 v{__version__}")

            await self.service.bot.send_message(
                chat_id=self.service.admin_chat_id,
                text="\n".join(lines),
                parse_mode="Markdown",
            )

            logger.info("Startup notification sent to admin")

        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to send startup notification: {e}")

    async def send_shutdown_notification(
        self, uptime_seconds: int = 0, posts_sent: int = 0
    ):
        """Send shutdown notification to admin with session summary."""
        if not self._lifecycle_notifications_enabled():
            return

        try:
            hours = int(uptime_seconds / 3600)
            minutes = int((uptime_seconds % 3600) / 60)
            uptime_str = f"{hours}h {minutes}m"

            message = (
                f"🔴 *Storydump Stopped*\n\n"
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
