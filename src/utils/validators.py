"""Input validation and configuration validation."""

from typing import List, Tuple
from pathlib import Path

from src.config.settings import settings


class ConfigValidator:
    """Validate configuration on startup."""

    @staticmethod
    def validate_all() -> Tuple[bool, List[str]]:
        """
        Validate all configuration settings.

        Returns:
            (is_valid, error_messages)
        """
        errors = []

        # Validate posting schedule
        if settings.POSTS_PER_DAY < 1 or settings.POSTS_PER_DAY > 10:
            errors.append("POSTS_PER_DAY must be between 1 and 10")

        # Handle wrap-around posting hours (e.g., 22-2 means 22:00 to 02:00 next day)
        if settings.POSTING_HOURS_START < 0 or settings.POSTING_HOURS_START > 23:
            errors.append("POSTING_HOURS_START must be between 0-23 (UTC)")

        if settings.POSTING_HOURS_END < 0 or settings.POSTING_HOURS_END > 23:
            errors.append("POSTING_HOURS_END must be between 0-23 (UTC)")

        # Validate repost TTL
        if settings.REPOST_TTL_DAYS < 1:
            errors.append("REPOST_TTL_DAYS must be at least 1")

        # Validate Telegram config
        if not settings.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN is required")

        if not settings.TELEGRAM_CHANNEL_ID:
            errors.append("TELEGRAM_CHANNEL_ID is required")

        if not settings.ADMIN_TELEGRAM_CHAT_ID:
            errors.append("ADMIN_TELEGRAM_CHAT_ID is required")

        # Validate Instagram config (if API enabled)
        if settings.ENABLE_INSTAGRAM_API:
            if not settings.CLOUDINARY_CLOUD_NAME:
                errors.append(
                    "Cloudinary config required when ENABLE_INSTAGRAM_API=true"
                )

        # Validate database config
        if not settings.DB_NAME:
            errors.append("DB_NAME is required")

        # Validate paths — auto-create MEDIA_DIR for cloud deployments
        media_dir = Path(settings.MEDIA_DIR)
        if not media_dir.exists():
            try:
                media_dir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                errors.append(
                    f"MEDIA_DIR does not exist and could not be created: "
                    f"{settings.MEDIA_DIR} ({e})"
                )

        is_valid = len(errors) == 0
        return is_valid, errors
