"""Onboarding session repository - CRUD for DM onboarding state."""

from typing import Optional
from datetime import datetime

from src.repositories.base_repository import BaseRepository
from src.models.onboarding_session import OnboardingSession


class OnboardingRepository(BaseRepository):
    """Repository for OnboardingSession CRUD operations."""

    def get_active_for_user(self, user_id: str) -> Optional[OnboardingSession]:
        """Get the active onboarding session for a user (if any)."""
        result = (
            self.db.query(OnboardingSession)
            .filter(
                OnboardingSession.user_id == user_id,
                OnboardingSession.expires_at > datetime.utcnow(),
                OnboardingSession.step != "complete",
            )
            .first()
        )
        self.end_read_transaction()
        return result

    def get_by_id(self, session_id: str) -> Optional[OnboardingSession]:
        """Get an onboarding session by ID."""
        result = (
            self.db.query(OnboardingSession)
            .filter(OnboardingSession.id == session_id)
            .first()
        )
        self.end_read_transaction()
        return result

    def create(
        self,
        user_id: str,
        expires_at: datetime,
    ) -> OnboardingSession:
        """Create a new onboarding session.

        Replaces any existing session for this user (including expired ones)
        to avoid hitting the UNIQUE(user_id) constraint.
        """
        existing = (
            self.db.query(OnboardingSession)
            .filter(OnboardingSession.user_id == user_id)
            .first()
        )
        if existing:
            self.db.delete(existing)
            self.db.commit()

        session = OnboardingSession(
            user_id=user_id,
            expires_at=expires_at,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def update_step(
        self,
        session_id: str,
        step: str,
        pending_instance_name: Optional[str] = None,
        pending_chat_settings_id: Optional[str] = None,
    ) -> Optional[OnboardingSession]:
        """Advance the onboarding session to the next step."""
        session = self.get_by_id(session_id)
        if not session:
            return None

        session.step = step
        if pending_instance_name is not None:
            session.pending_instance_name = pending_instance_name
        if pending_chat_settings_id is not None:
            session.pending_chat_settings_id = pending_chat_settings_id
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_expired(self) -> list[OnboardingSession]:
        """Return all expired onboarding sessions (before deletion)."""
        return (
            self.db.query(OnboardingSession)
            .filter(OnboardingSession.expires_at <= datetime.utcnow())
            .all()
        )

    def delete_expired(self) -> int:
        """Delete all expired onboarding sessions.

        Called by the scheduler loop to clean up stale sessions.
        Returns number of sessions deleted.
        """
        count = (
            self.db.query(OnboardingSession)
            .filter(OnboardingSession.expires_at <= datetime.utcnow())
            .delete()
        )
        self.db.commit()
        return count
