"""Notification sending and caption building for Telegram."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.config.settings import settings
from src.utils.logger import logger


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

        # Build inline keyboard
        reply_markup = self._build_keyboard(
            queue_item_id, chat_settings, active_account
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

        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return False

    def _build_keyboard(self, queue_item_id, chat_settings, active_account):
        """Build inline keyboard buttons for the notification.

        Layout: Auto Post (if enabled) -> Status actions -> Instagram actions
        """
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
                        "🚫 Reject",
                        callback_data=f"reject:{queue_item_id}",
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
                        "📱 Open Instagram",
                        url="https://www.instagram.com/",
                    ),
                ],
            ]
        )
        return InlineKeyboardMarkup(keyboard)

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
