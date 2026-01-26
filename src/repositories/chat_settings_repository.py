"""Chat settings repository - CRUD operations for runtime settings."""

from typing import Optional
from datetime import datetime

from src.repositories.base_repository import BaseRepository
from src.models.chat_settings import ChatSettings
from src.config.settings import settings as env_settings


class ChatSettingsRepository(BaseRepository):
    """
    Repository for ChatSettings CRUD operations.

    Implements .env fallback: If no DB record exists, creates one
    from current .env values on first access.
    """

    def get_by_chat_id(self, telegram_chat_id: int) -> Optional[ChatSettings]:
        """Get settings for a specific chat."""
        result = (
            self.db.query(ChatSettings)
            .filter(ChatSettings.telegram_chat_id == telegram_chat_id)
            .first()
        )
        self.end_read_transaction()
        return result

    def get_or_create(self, telegram_chat_id: int) -> ChatSettings:
        """
        Get settings for chat, creating from .env defaults if not exists.

        This is the primary access method - ensures a record always exists.
        """
        existing = (
            self.db.query(ChatSettings)
            .filter(ChatSettings.telegram_chat_id == telegram_chat_id)
            .first()
        )

        if existing:
            self.end_read_transaction()
            return existing

        # Bootstrap from .env values
        chat_settings = ChatSettings(
            telegram_chat_id=telegram_chat_id,
            dry_run_mode=env_settings.DRY_RUN_MODE,
            enable_instagram_api=env_settings.ENABLE_INSTAGRAM_API,
            is_paused=False,
            posts_per_day=env_settings.POSTS_PER_DAY,
            posting_hours_start=env_settings.POSTING_HOURS_START,
            posting_hours_end=env_settings.POSTING_HOURS_END,
            show_verbose_notifications=True,
        )
        self.db.add(chat_settings)
        self.db.commit()
        self.db.refresh(chat_settings)
        return chat_settings

    def update(self, telegram_chat_id: int, **kwargs) -> ChatSettings:
        """
        Update settings for a chat.

        Args:
            telegram_chat_id: Chat to update
            **kwargs: Fields to update (dry_run_mode, is_paused, etc.)

        Returns:
            Updated ChatSettings record
        """
        chat_settings = self.get_or_create(telegram_chat_id)

        for key, value in kwargs.items():
            if hasattr(chat_settings, key):
                setattr(chat_settings, key, value)

        chat_settings.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(chat_settings)
        return chat_settings

    def set_paused(
        self, telegram_chat_id: int, is_paused: bool, user_id: Optional[str] = None
    ) -> ChatSettings:
        """
        Set pause state with tracking.

        Args:
            telegram_chat_id: Chat to update
            is_paused: New pause state
            user_id: UUID of user who changed state
        """
        update_data = {
            "is_paused": is_paused,
            "paused_at": datetime.utcnow() if is_paused else None,
            "paused_by_user_id": user_id if is_paused else None,
        }
        return self.update(telegram_chat_id, **update_data)
