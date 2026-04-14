"""Notification sending and caption building for Telegram."""

import re

from src.config.settings import settings
from src.exceptions.google_drive import GoogleDriveAuthError
from src.utils.logger import logger


def _is_google_auth_error(exc: Exception) -> bool:
    """Check if an exception is a Google auth/refresh error.

    Walks the ``__cause__`` chain to detect
    ``google.auth.exceptions.RefreshError`` without requiring the
    google-auth package as a hard import (it may not be installed in
    all environments).
    """
    current = exc
    while current is not None:
        type_name = type(current).__qualname__
        module = type(current).__module__ or ""
        if "RefreshError" in type_name and "google" in module:
            return True
        current = getattr(current, "__cause__", None)
    return False


def _escape_md(text: str) -> str:
    """Escape Telegram Markdown special characters in user-generated text."""
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


class TelegramNotificationService:
    """Handles notification sending, caption building, and keyboard construction.

    Uses the composition pattern -- receives a reference to the parent
    ``TelegramService`` for access to bot, repos, and settings.  This is
    the same pattern used by all other handler modules (commands,
    callbacks, autopost, settings, accounts).
    """

    def __init__(self, telegram_service):
        """
        Args:
            telegram_service: Parent TelegramService for access to
                bot, repos, and settings.
        """
        self.service = telegram_service

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
        from telegram import Bot

        # Initialize bot if not already done (for CLI usage)
        if self.service.bot is None:
            self.service.bot = Bot(token=self.service.bot_token)
            logger.debug("Telegram bot initialized for one-time use")

        queue_item = self.service.queue_repo.get_by_id(queue_item_id)
        if not queue_item:
            logger.error(f"Queue item not found: {queue_item_id}")
            return False

        media_item = self.service.media_repo.get_by_id(str(queue_item.media_item_id))
        if not media_item:
            logger.error(f"Media item not found: {queue_item.media_item_id}")
            return False

        # Get chat settings and verbose preference
        chat_settings = self.service.settings_service.get_settings(
            self.service.channel_id
        )
        verbose = self.service._is_verbose(
            self.service.channel_id, chat_settings=chat_settings
        )

        # Get active Instagram account for display
        active_account = self.service.ig_account_service.get_active_account(
            self.service.channel_id
        )

        # Build caption (pass queue_item for enhanced mode)
        caption = self._build_caption(
            media_item,
            queue_item,
            force_sent=force_sent,
            verbose=verbose,
            active_account=active_account,
        )

        # Get account count for keyboard cycle behavior
        account_count = self.service.ig_account_service.count_active_accounts()

        # Build inline keyboard
        from src.services.core.telegram_utils import build_queue_action_keyboard

        reply_markup = build_queue_action_keyboard(
            queue_item_id,
            enable_instagram_api=chat_settings.enable_instagram_api,
            active_account=active_account,
            account_count=account_count,
        )

        try:
            # Get file bytes via provider (supports local and future cloud sources)
            from io import BytesIO

            from src.services.media_sources.factory import MediaSourceFactory

            provider = MediaSourceFactory.get_provider_for_media_item(
                media_item, telegram_chat_id=self.service.channel_id
            )
            file_bytes = provider.download_file(media_item.source_identifier)

            photo_buffer = BytesIO(file_bytes)
            photo_buffer.name = media_item.file_name  # Telegram needs filename hint
            message = await self.service.bot.send_photo(
                chat_id=self.service.channel_id,
                photo=photo_buffer,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode="Markdown",
            )

            # Save telegram message ID
            self.service.queue_repo.set_telegram_message(
                queue_item_id, message.message_id, self.service.channel_id
            )

            # Log outgoing bot response for visibility
            self.service.interaction_service.log_bot_response(
                response_type="photo_notification",
                context={
                    "caption": caption,
                    "buttons": _extract_button_labels(reply_markup),
                    "media_filename": media_item.file_name,
                    "queue_item_id": queue_item_id,
                    "force_sent": force_sent,
                },
                telegram_chat_id=self.service.channel_id,
                telegram_message_id=message.message_id,
            )

            logger.info(f"Sent Telegram notification for {media_item.file_name}")
            return True

        except GoogleDriveAuthError:
            raise
        except Exception as e:
            if _is_google_auth_error(e):
                raise GoogleDriveAuthError(
                    f"Google Drive token expired or revoked: {e}"
                ) from e
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
        lines = []

        if force_sent:
            lines.append("⚡")

        if media_item.title:
            lines.append(f"📸 {_escape_md(media_item.title)}")

        if active_account:
            lines.append(f"📸 Account: {_escape_md(active_account.display_name)}")
        else:
            lines.append("📸 Account: Not set")

        if media_item.caption:
            lines.append(f"\n{_escape_md(media_item.caption)}")

        if media_item.link_url:
            lines.append(f"\n🔗 {media_item.link_url}")

        if media_item.tags:
            tags_str = " ".join([f"#{tag}" for tag in media_item.tags])
            lines.append(f"\n{tags_str}")

        if verbose:
            lines.append(f"\n📝 File: {_escape_md(media_item.file_name)}")
            lines.append(f"🆔 ID: {str(media_item.id)[:8]}")

        return "\n".join(lines)

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

        if force_sent:
            lines.append("⚡")

        if media_item.title:
            lines.append(f"📸 {_escape_md(media_item.title)}")

        if active_account:
            lines.append(f"📸 Account: {_escape_md(active_account.display_name)}")
        else:
            lines.append("📸 Account: Not set")

        if media_item.caption:
            lines.append(f"\n{_escape_md(media_item.caption)}")

        if media_item.link_url:
            lines.append(f"\n🔗 {media_item.link_url}")

        if media_item.tags:
            tags_str = " ".join([f"#{tag}" for tag in media_item.tags])
            lines.append(f"\n{tags_str}")

        # Verbose: debug info + workflow instructions (consistent across modes)
        if verbose:
            lines.append(f"\n📝 File: {media_item.file_name}")
            lines.append(f"🆔 ID: {str(media_item.id)[:8]}")

            lines.append(f"\n{'━' * 20}")
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
