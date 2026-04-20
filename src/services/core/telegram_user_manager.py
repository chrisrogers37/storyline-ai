"""User management for Telegram bot interactions.

Handles user creation/sync, group membership tracking, and display name
resolution. Uses a process-local membership cache to avoid redundant DB
queries on repeated interactions from the same user in the same group.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.utils.logger import logger

if TYPE_CHECKING:
    from src.services.core.telegram_service import TelegramService


class TelegramUserManager:
    """Manages Telegram user lifecycle — creation, profile sync, membership."""

    def __init__(self, service: TelegramService):
        self.service = service
        self._known_memberships: set[tuple[str, int]] = set()

    def get_or_create_user(self, telegram_user, telegram_chat_id=None):
        """Get or create user from Telegram data, syncing profile on each interaction.

        If telegram_chat_id is provided and is a group chat (< 0), also ensures
        a user_chat_membership exists linking this user to that chat's instance.
        """
        user = self.service.user_repo.get_by_telegram_id(telegram_user.id)

        if not user:
            user = self.service.user_repo.create(
                telegram_user_id=telegram_user.id,
                telegram_username=telegram_user.username,
                telegram_first_name=telegram_user.first_name,
                telegram_last_name=telegram_user.last_name,
            )
            logger.info(f"New user discovered: {self.get_display_name(user)}")
        else:
            user = self.service.user_repo.update_profile(
                str(user.id),
                telegram_username=telegram_user.username,
                telegram_first_name=telegram_user.first_name,
                telegram_last_name=telegram_user.last_name,
            )

        if telegram_chat_id is not None and telegram_chat_id < 0:
            self._ensure_membership(user, telegram_chat_id)

        return user

    def _ensure_membership(self, user, telegram_chat_id):
        """Ensure a membership exists linking user to a group chat instance.

        Uses a process-local cache to avoid DB queries on repeated
        interactions from the same user in the same group.
        """
        cache_key = (str(user.id), telegram_chat_id)
        if cache_key in self._known_memberships:
            return

        try:
            chat_settings = self.service.settings_service.get_settings_if_exists(
                telegram_chat_id
            )
            if not chat_settings:
                return
            self.service.membership_repo.create_membership(
                user_id=str(user.id),
                chat_settings_id=str(chat_settings.id),
            )
            self._known_memberships.add(cache_key)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Membership auto-create failed: {e}")

    def evict_memberships_for_chat(self, chat_id: int):
        """Evict cached memberships for a chat (e.g., when bot is kicked)."""
        to_evict = {k for k in self._known_memberships if k[1] == chat_id}
        self._known_memberships -= to_evict
        return len(to_evict)

    def get_display_name(self, user) -> str:
        """Get best available display name for user (username > first_name > user_id)."""
        if user.telegram_username:
            return f"@{user.telegram_username}"
        elif user.telegram_first_name:
            return user.telegram_first_name
        else:
            return f"User {user.telegram_user_id}"
