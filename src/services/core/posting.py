"""Posting service - Google Drive auth alerts and posting utilities."""

from datetime import datetime, timezone
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
    (state-transition notification) used by the scheduler loop when a
    GoogleDriveAuthError is encountered.
    """

    def __init__(self):
        super().__init__()
        self.telegram_service = TelegramService()
        self.settings_service = SettingsService()

    async def send_gdrive_auth_alert(
        self, telegram_chat_id: Optional[int] = None
    ) -> None:
        """Send a Google Drive reconnect alert to Telegram.

        Gated on chat_settings.gdrive_alerted_at: fires once per disconnect
        event and stays silent until the OAuth reconnect callback clears
        the flag. State lives in Postgres so it survives worker restarts
        and is correctly scoped per chat.
        """
        chat_id = telegram_chat_id or settings.ADMIN_TELEGRAM_CHAT_ID
        if not chat_id:
            return

        chat_settings = self.settings_service.get_settings_if_exists(chat_id)
        if chat_settings is None:
            logger.debug(
                f"Skipping Google Drive auth alert: no chat_settings for {chat_id}"
            )
            return
        if chat_settings.gdrive_alerted_at is not None:
            logger.debug(
                f"Skipping Google Drive auth alert for {chat_id}: "
                "already alerted, awaiting reconnect"
            )
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
            logger.info(f"Sent Google Drive auth alert to chat {chat_id}")

        except Exception as e:  # noqa: BLE001 — best-effort alert
            logger.error(f"Failed to send Google Drive auth alert: {e}")
            return

        self.settings_service.set_gdrive_alerted_at(chat_id, datetime.now(timezone.utc))
