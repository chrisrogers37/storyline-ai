"""Conversation service - DM onboarding state machine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Optional

from src.models.onboarding_session import OnboardingSession
from src.repositories.onboarding_repository import OnboardingRepository
from src.services.base_service import BaseService
from src.utils.logger import logger

if TYPE_CHECKING:
    from src.models.chat_settings import ChatSettings

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
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ONBOARDING_TTL_HOURS)
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

    def link_group_to_instance(
        self,
        session: "OnboardingSession",
        chat_id: int,
        user_id: str,
        membership_repo,
    ) -> "ChatSettings":
        """Shared linking flow: create chat_settings, set display_name,
        create owner membership, complete onboarding session.

        Used by startgroup deep link, my_chat_member, and /link command.
        Returns the chat_settings record.

        Idempotent: MembershipRepository.create_membership handles duplicates
        via upsert, so partial failures (e.g. update_step fails after
        create_membership succeeds) are safe to retry.
        """
        from src.services.core.settings_service import SettingsService

        with SettingsService() as settings_service:
            chat_settings = settings_service.get_settings(chat_id)
            if session.pending_instance_name:
                settings_service.update_setting(
                    chat_id, "display_name", session.pending_instance_name
                )

        # Idempotent: returns existing membership if already created
        membership_repo.create_membership(
            user_id=user_id,
            chat_settings_id=str(chat_settings.id),
            instance_role="owner",
        )

        self.onboarding_repo.update_step(
            session_id=str(session.id),
            step="complete",
            pending_chat_settings_id=str(chat_settings.id),
        )

        return chat_settings

    def cleanup_expired(self) -> int:
        """Delete expired onboarding sessions. Call from scheduler loop.

        Logs each expired session as an onboarding_dropout interaction
        before deleting, so we can track where users drop off.
        """
        expired = self.onboarding_repo.get_expired()

        if expired:
            from src.repositories.interaction_repository import (
                InteractionRepository,
            )

            try:
                now = datetime.now(timezone.utc)
                with InteractionRepository() as interaction_repo:
                    for session in expired:
                        duration_minutes = int(
                            (now - session.created_at).total_seconds() / 60
                        )
                        interaction_repo.create(
                            user_id=str(session.user_id),
                            interaction_type="onboarding_dropout",
                            interaction_name=session.step,
                            context={"duration_minutes": duration_minutes},
                        )
            except Exception:
                logger.warning("Failed to log onboarding dropouts", exc_info=True)

        count = self.onboarding_repo.delete_expired()
        if count > 0:
            logger.info(f"Cleaned up {count} expired onboarding session(s)")
        return count
