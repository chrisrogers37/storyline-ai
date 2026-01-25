"""Settings service - runtime configuration management."""
from typing import Optional, Any, Dict

from src.services.base_service import BaseService
from src.repositories.chat_settings_repository import ChatSettingsRepository
from src.models.chat_settings import ChatSettings
from src.models.user import User
from src.utils.logger import logger


# Allowed settings that can be toggled/changed
TOGGLEABLE_SETTINGS = {"dry_run_mode", "enable_instagram_api", "is_paused"}
NUMERIC_SETTINGS = {"posts_per_day", "posting_hours_start", "posting_hours_end"}


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
        self,
        telegram_chat_id: int,
        setting_name: str,
        user: Optional[User] = None
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
            input_params={"setting_name": setting_name}
        ) as run_id:
            settings = self.settings_repo.get_or_create(telegram_chat_id)
            old_value = getattr(settings, setting_name)
            new_value = not old_value

            if setting_name == "is_paused":
                self.settings_repo.set_paused(
                    telegram_chat_id,
                    new_value,
                    str(user.id) if user else None
                )
            else:
                self.settings_repo.update(telegram_chat_id, **{setting_name: new_value})

            self.set_result_summary(run_id, {
                "setting": setting_name,
                "old_value": old_value,
                "new_value": new_value,
                "changed_by": user.telegram_username if user else "system"
            })

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
        user: Optional[User] = None
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
        if setting_name not in TOGGLEABLE_SETTINGS | NUMERIC_SETTINGS:
            raise ValueError(f"Unknown setting: {setting_name}")

        with self.track_execution(
            "update_setting",
            user_id=user.id if user else None,
            triggered_by="user",
            input_params={"setting_name": setting_name, "value": value}
        ) as run_id:
            settings = self.settings_repo.get_or_create(telegram_chat_id)
            old_value = getattr(settings, setting_name)

            # Validate numeric settings
            if setting_name == "posts_per_day":
                value = int(value)
                if not 1 <= value <= 50:
                    raise ValueError("posts_per_day must be between 1 and 50")
            elif setting_name in ("posting_hours_start", "posting_hours_end"):
                value = int(value)
                if not 0 <= value <= 23:
                    raise ValueError("Hour must be between 0 and 23")

            updated = self.settings_repo.update(telegram_chat_id, **{setting_name: value})

            self.set_result_summary(run_id, {
                "setting": setting_name,
                "old_value": old_value,
                "new_value": value,
                "changed_by": user.telegram_username if user else "system"
            })

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
            "updated_at": settings.updated_at,
        }
