"""Interaction service - tracks all user interactions with the bot."""
from typing import Optional

from src.repositories.interaction_repository import InteractionRepository
from src.models.user_interaction import UserInteraction
from src.utils.logger import logger


class InteractionService:
    """
    Service for tracking user interactions.

    Responsibilities:
    - Log all user interactions (commands, callbacks)
    - Provide analytics queries
    - NOT responsible for handling the interactions themselves

    Note: This service does NOT extend BaseService because:
    1. Interaction logging is fire-and-forget (shouldn't add overhead)
    2. Would create recursive tracking if we tracked interaction logging itself
    """

    def __init__(self):
        self.interaction_repo = InteractionRepository()

    # ─────────────────────────────────────────────────────────────
    # Logging Methods
    # ─────────────────────────────────────────────────────────────

    def log_command(
        self,
        user_id: str,
        command: str,
        context: Optional[dict] = None,
        telegram_chat_id: Optional[int] = None,
        telegram_message_id: Optional[int] = None,
    ) -> Optional[UserInteraction]:
        """
        Log a command interaction (e.g., /queue, /status).

        Args:
            user_id: UUID of the user
            command: Command name (e.g., '/queue', '/status')
            context: Optional context data
            telegram_chat_id: Telegram chat ID
            telegram_message_id: Telegram message ID

        Returns:
            Created UserInteraction record, or None if logging failed
        """
        try:
            return self.interaction_repo.create(
                user_id=user_id,
                interaction_type="command",
                interaction_name=command,
                context=context,
                telegram_chat_id=telegram_chat_id,
                telegram_message_id=telegram_message_id,
            )
        except Exception as e:
            # Don't let logging failures break the main flow
            logger.warning(f"Failed to log command interaction: {e}")
            return None

    def log_callback(
        self,
        user_id: str,
        callback_name: str,
        context: Optional[dict] = None,
        telegram_chat_id: Optional[int] = None,
        telegram_message_id: Optional[int] = None,
    ) -> Optional[UserInteraction]:
        """
        Log a callback interaction (e.g., posted, skip, reject).

        Args:
            user_id: UUID of the user
            callback_name: Callback name (e.g., 'posted', 'skip')
            context: Optional context data (queue_item_id, media_id, etc.)
            telegram_chat_id: Telegram chat ID
            telegram_message_id: Telegram message ID

        Returns:
            Created UserInteraction record, or None if logging failed
        """
        try:
            return self.interaction_repo.create(
                user_id=user_id,
                interaction_type="callback",
                interaction_name=callback_name,
                context=context,
                telegram_chat_id=telegram_chat_id,
                telegram_message_id=telegram_message_id,
            )
        except Exception as e:
            # Don't let logging failures break the main flow
            logger.warning(f"Failed to log callback interaction: {e}")
            return None

    def log_message(
        self,
        user_id: str,
        message_type: str,
        context: Optional[dict] = None,
        telegram_chat_id: Optional[int] = None,
        telegram_message_id: Optional[int] = None,
    ) -> Optional[UserInteraction]:
        """
        Log a message interaction (reserved for future use).

        Args:
            user_id: UUID of the user
            message_type: Type of message
            context: Optional context data
            telegram_chat_id: Telegram chat ID
            telegram_message_id: Telegram message ID

        Returns:
            Created UserInteraction record, or None if logging failed
        """
        try:
            return self.interaction_repo.create(
                user_id=user_id,
                interaction_type="message",
                interaction_name=message_type,
                context=context,
                telegram_chat_id=telegram_chat_id,
                telegram_message_id=telegram_message_id,
            )
        except Exception as e:
            logger.warning(f"Failed to log message interaction: {e}")
            return None

    # ─────────────────────────────────────────────────────────────
    # Analytics Methods
    # ─────────────────────────────────────────────────────────────

    def get_user_stats(self, user_id: str, days: int = 30) -> dict:
        """
        Get interaction statistics for a specific user.

        Args:
            user_id: UUID of the user
            days: Number of days to look back

        Returns:
            {
                "total_interactions": 45,
                "posts_marked": 20,
                "posts_skipped": 15,
                "posts_rejected": 2,
                "commands_used": {"queue": 5, "status": 3},
            }
        """
        return self.interaction_repo.get_user_stats(user_id, days)

    def get_team_activity(self, days: int = 30) -> dict:
        """
        Get team-wide activity statistics.

        Args:
            days: Number of days to look back

        Returns:
            {
                "total_interactions": 150,
                "active_users": 3,
                "interactions_by_type": {...},
                "interactions_by_name": {...},
            }
        """
        return self.interaction_repo.get_team_activity(days)

    def get_content_decisions(self, days: int = 30) -> dict:
        """
        Get statistics on content decisions (posted vs skipped vs rejected).

        Args:
            days: Number of days to look back

        Returns:
            {
                "total_decisions": 50,
                "posted": 35,
                "skipped": 12,
                "rejected": 3,
                "posted_percentage": 70.0,
                "skip_percentage": 24.0,
                "rejection_rate": 6.0,
            }
        """
        return self.interaction_repo.get_content_decisions(days)

    def get_recent_interactions(self, days: int = 7, limit: int = 100) -> list:
        """
        Get recent interactions for activity feed.

        Args:
            days: Number of days to look back
            limit: Maximum number of interactions to return

        Returns:
            List of UserInteraction records
        """
        return self.interaction_repo.get_recent(days=days, limit=limit)
