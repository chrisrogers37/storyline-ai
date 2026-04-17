"""Conversation service - DM onboarding state machine."""

from datetime import datetime, timedelta
from typing import Optional

from src.models.onboarding_session import OnboardingSession
from src.repositories.onboarding_repository import OnboardingRepository
from src.services.base_service import BaseService
from src.utils.logger import logger

ONBOARDING_TTL_HOURS = 24


class ConversationService(BaseService):
    """Wraps onboarding_sessions for the DM instance-creation flow.

    State machine: naming → awaiting_group → complete
    Sessions expire after 24h.
    """

    def __init__(self):
        super().__init__()
        self.onboarding_repo = OnboardingRepository()

    def start_onboarding(self, user_id: str) -> OnboardingSession:
        """Start a new onboarding session (replaces any existing)."""
        expires_at = datetime.utcnow() + timedelta(hours=ONBOARDING_TTL_HOURS)
        session = self.onboarding_repo.create(
            user_id=user_id,
            expires_at=expires_at,
        )
        logger.info(f"Onboarding started for user {user_id}, session {session.id}")
        return session

    def get_current_session(self, user_id: str) -> Optional[OnboardingSession]:
        """Get the active onboarding session for a user, if any."""
        return self.onboarding_repo.get_active_for_user(user_id)

    def get_session_by_id(self, session_id: str) -> Optional[OnboardingSession]:
        """Get an onboarding session by ID (for startgroup deep links)."""
        return self.onboarding_repo.get_by_id(session_id)

    def set_instance_name(
        self, session_id: str, name: str
    ) -> Optional[OnboardingSession]:
        """Record the chosen instance name and advance to awaiting_group."""
        return self.onboarding_repo.update_step(
            session_id=session_id,
            step="awaiting_group",
            pending_instance_name=name,
        )

    def link_group(
        self, session_id: str, chat_settings_id: str
    ) -> Optional[OnboardingSession]:
        """Link a group chat to the pending onboarding session."""
        return self.onboarding_repo.update_step(
            session_id=session_id,
            step="complete",
            pending_chat_settings_id=chat_settings_id,
        )

    def cleanup_expired(self) -> int:
        """Delete expired onboarding sessions. Call from scheduler loop."""
        count = self.onboarding_repo.delete_expired()
        if count > 0:
            logger.info(f"Cleaned up {count} expired onboarding session(s)")
        return count
