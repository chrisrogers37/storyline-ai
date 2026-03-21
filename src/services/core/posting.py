"""Posting service - Google Drive auth alerts and posting utilities."""

import time
from typing import Optional

from src.services.base_service import BaseService
from src.services.core.telegram_service import TelegramService
from src.services.core.settings_service import SettingsService
from src.config.settings import settings
from src.utils.logger import logger


class PostingService(BaseService):
    """Posting utilities and Google Drive auth alert management.

    The main scheduling and sending logic has moved to SchedulerService
    (JIT model). PostingService retains the Google Drive auth alert
    (rate-limited proactive notification) used by the scheduler loop
    when a GoogleDriveAuthError is encountered.
    """

    # Rate-limit auth alerts to 1 per hour (class-level shared across instances)
    _last_gdrive_alert_time: float = 0.0

    def __init__(self):
        super().__init__()
        self.telegram_service = TelegramService()
        self.settings_service = SettingsService()

    async def send_gdrive_auth_alert(
        self, telegram_chat_id: Optional[int] = None
    ) -> None:
        """Send a proactive Google Drive reconnect alert to Telegram.

        Rate-limited to at most once per hour to avoid spamming the channel.
        """
        now = time.monotonic()
        if (
            PostingService._last_gdrive_alert_time > 0
            and now - PostingService._last_gdrive_alert_time < 3600
        ):
            logger.debug("Skipping Google Drive auth alert (rate-limited)")
            return

        PostingService._last_gdrive_alert_time = now

        chat_id = telegram_chat_id or settings.ADMIN_TELEGRAM_CHAT_ID
        if not chat_id:
            return

        try:
            from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

            bot = Bot(token=self.telegram_service.bot_token)

            reconnect_url = None
            if settings.OAUTH_REDIRECT_BASE_URL:
                reconnect_url = (
                    f"{settings.OAUTH_REDIRECT_BASE_URL}"
                    f"/auth/google-drive/start?chat_id={chat_id}"
                )

            text = (
                "⚠️ *Google Drive Disconnected*\n\n"
                "Your Google Drive token has expired or been revoked. "
                "Scheduled posts are paused until you reconnect."
            )

            reply_markup = None
            if reconnect_url:
                reply_markup = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "🔗 Reconnect Google Drive", url=reconnect_url
                            )
                        ]
                    ]
                )

            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="Markdown",
                reply_markup=reply_markup,
            )
            logger.info("Sent Google Drive auth alert to Telegram")

        except Exception as e:
            logger.error(f"Failed to send Google Drive auth alert: {e}")
