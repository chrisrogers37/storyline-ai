"""Settings service - runtime configuration management."""

from typing import Optional, Any, Dict, List

from src.services.base_service import BaseService
from src.repositories.chat_settings_repository import ChatSettingsRepository
from src.config.constants import (
    MAX_POSTING_HOUR,
    MAX_POSTS_PER_DAY,
    MIN_POSTING_HOUR,
    MIN_POSTS_PER_DAY,
)
from src.models.chat_settings import ChatSettings
from src.models.user import User
from src.utils.logger import logger


# Allowed settings that can be toggled/changed
TOGGLEABLE_SETTINGS = {
    "dry_run_mode",
    "enable_instagram_api",
    "is_paused",
    "show_verbose_notifications",
    "media_sync_enabled",
}
NUMERIC_SETTINGS = {"posts_per_day", "posting_hours_start", "posting_hours_end"}
TEXT_SETTINGS = {"media_source_type", "media_source_root"}


class SettingsService(BaseService):
    """
    Per-chat settings with .env fallback.

    Resolution order:
    1. DB value for chat (if exists)
    2. .env default (on first access, bootstrapped to DB)

    All setting changes are tracked via ServiceRun for audit.
    """

    def __init__(self):
        super().__init__()
        self.settings_repo = ChatSettingsRepository()

    def get_settings(self, telegram_chat_id: int) -> ChatSettings:
        """
        Get or create settings for a chat.

        Args:
            telegram_chat_id: Telegram chat/channel ID

        Returns:
            ChatSettings record (created from .env if first access)
        """
        return self.settings_repo.get_or_create(telegram_chat_id)

    def toggle_setting(
        self, telegram_chat_id: int, setting_name: str, user: Optional[User] = None
    ) -> bool:
        """
        Toggle a boolean setting.

        Args:
            telegram_chat_id: Chat to update
            setting_name: One of TOGGLEABLE_SETTINGS
            user: User performing the change

        Returns:
            New value after toggle

        Raises:
            ValueError: If setting_name not in TOGGLEABLE_SETTINGS
        """
        if setting_name not in TOGGLEABLE_SETTINGS:
            raise ValueError(f"Setting '{setting_name}' is not toggleable")

        with self.track_execution(
            "toggle_setting",
            user_id=user.id if user else None,
            triggered_by="user",
            input_params={"setting_name": setting_name},
        ) as run_id:
            settings = self.settings_repo.get_or_create(telegram_chat_id)
            old_value = getattr(settings, setting_name)
            new_value = not old_value

            if setting_name == "is_paused":
                self.settings_repo.set_paused(
                    telegram_chat_id, new_value, str(user.id) if user else None
                )
            else:
                self.settings_repo.update(telegram_chat_id, **{setting_name: new_value})

            self.set_result_summary(
                run_id,
                {
                    "setting": setting_name,
                    "old_value": old_value,
                    "new_value": new_value,
                    "changed_by": user.telegram_username if user else "system",
                },
            )

            logger.info(
                f"Setting '{setting_name}' toggled: {old_value} -> {new_value} "
                f"by @{user.telegram_username if user else 'system'}"
            )

            return new_value

    def update_setting(
        self,
        telegram_chat_id: int,
        setting_name: str,
        value: Any,
        user: Optional[User] = None,
    ) -> ChatSettings:
        """
        Update a setting value.

        Args:
            telegram_chat_id: Chat to update
            setting_name: Setting to change
            value: New value
            user: User performing the change

        Returns:
            Updated ChatSettings

        Raises:
            ValueError: If setting_name not valid or value out of range
        """
        if setting_name not in TOGGLEABLE_SETTINGS | NUMERIC_SETTINGS | TEXT_SETTINGS:
            raise ValueError(f"Unknown setting: {setting_name}")

        with self.track_execution(
            "update_setting",
            user_id=user.id if user else None,
            triggered_by="user",
            input_params={"setting_name": setting_name, "value": value},
        ) as run_id:
            settings = self.settings_repo.get_or_create(telegram_chat_id)
            old_value = getattr(settings, setting_name)

            # Validate numeric settings
            if setting_name == "posts_per_day":
                value = int(value)
                if not MIN_POSTS_PER_DAY <= value <= MAX_POSTS_PER_DAY:
                    raise ValueError(
                        f"posts_per_day must be between {MIN_POSTS_PER_DAY} and {MAX_POSTS_PER_DAY}"
                    )
            elif setting_name in ("posting_hours_start", "posting_hours_end"):
                value = int(value)
                if not MIN_POSTING_HOUR <= value <= MAX_POSTING_HOUR:
                    raise ValueError(
                        f"Hour must be between {MIN_POSTING_HOUR} and {MAX_POSTING_HOUR}"
                    )
            elif setting_name == "media_source_type":
                if value is not None and value not in ("local", "google_drive"):
                    raise ValueError(
                        "media_source_type must be 'local', 'google_drive', or None"
                    )

            updated = self.settings_repo.update(
                telegram_chat_id, **{setting_name: value}
            )

            self.set_result_summary(
                run_id,
                {
                    "setting": setting_name,
                    "old_value": old_value,
                    "new_value": value,
                    "changed_by": user.telegram_username if user else "system",
                },
            )

            logger.info(
                f"Setting '{setting_name}' updated: {old_value} -> {value} "
                f"by @{user.telegram_username if user else 'system'}"
            )

            return updated

    def get_settings_display(self, telegram_chat_id: int) -> Dict[str, Any]:
        """
        Get settings formatted for display in Telegram.

        Returns dict with all settings and their display values.
        """
        settings = self.get_settings(telegram_chat_id)

        return {
            "dry_run_mode": settings.dry_run_mode,
            "enable_instagram_api": settings.enable_instagram_api,
            "is_paused": settings.is_paused,
            "paused_at": settings.paused_at,
            "paused_by_user_id": settings.paused_by_user_id,
            "posts_per_day": settings.posts_per_day,
            "posting_hours_start": settings.posting_hours_start,
            "posting_hours_end": settings.posting_hours_end,
            "show_verbose_notifications": settings.show_verbose_notifications,
            "media_sync_enabled": settings.media_sync_enabled,
            "media_source_type": settings.media_source_type,
            "media_source_root": settings.media_source_root,
            "updated_at": settings.updated_at,
        }

    def get_media_source_config(
        self, telegram_chat_id: int
    ) -> tuple[Optional[str], Optional[str]]:
        """Get resolved media source configuration for a chat.

        Resolution order:
        1. Per-chat value from chat_settings (if not NULL)
        2. Global env var fallback

        Args:
            telegram_chat_id: Telegram chat/channel ID

        Returns:
            Tuple of (source_type, source_root)
        """
        from src.config.settings import settings as env_settings

        chat_settings = self.get_settings(telegram_chat_id)

        source_type = chat_settings.media_source_type or env_settings.MEDIA_SOURCE_TYPE
        source_root = chat_settings.media_source_root or env_settings.MEDIA_SOURCE_ROOT

        return source_type, source_root

    def set_onboarding_step(
        self, telegram_chat_id: int, step: Optional[str]
    ) -> ChatSettings:
        """Update the onboarding wizard step for a chat."""
        return self.settings_repo.update(telegram_chat_id, onboarding_step=step)

    def complete_onboarding(self, telegram_chat_id: int) -> ChatSettings:
        """Mark onboarding as completed for a chat."""
        return self.settings_repo.update(
            telegram_chat_id, onboarding_step=None, onboarding_completed=True
        )

    def get_all_active_chats(self) -> List[ChatSettings]:
        """Get all active (non-paused) chat settings.

        Used by the scheduler loop to iterate over all tenants.

        Returns:
            List of ChatSettings records where is_paused=False
        """
        return self.settings_repo.get_all_active()

    def get_all_paused_chats(self) -> List[ChatSettings]:
        """Get all paused chat settings.

        Used by the scheduler loop to run smart delivery reschedule
        on paused tenants.

        Returns:
            List of ChatSettings records where is_paused=True
        """
        return self.settings_repo.get_all_paused()
