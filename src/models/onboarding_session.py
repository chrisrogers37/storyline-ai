"""Onboarding session model - DM-level onboarding state machine."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    String,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from src.config.database import Base


class OnboardingSession(Base):
    """
    Tracks DM-level onboarding state for new instance creation.

    Separate from chat_settings.onboarding_step which tracks per-instance
    setup (Instagram, media, schedule). This table tracks the short-lived
    DM flow: name the instance, link to a group, done.

    One active session per user (UNIQUE on user_id).
    Sessions expire after 24h.
    """

    __tablename__ = "onboarding_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    step = Column(String(50), nullable=False, default="naming")
    pending_instance_name = Column(String(100))
    pending_chat_settings_id = Column(
        UUID(as_uuid=True), ForeignKey("chat_settings.id"), nullable=True
    )
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User")
    pending_chat_settings = relationship("ChatSettings")

    __table_args__ = (
        UniqueConstraint("user_id", name="unique_active_onboarding"),
        CheckConstraint(
            "step IN ('naming', 'awaiting_group', 'complete')",
            name="check_onboarding_step",
        ),
    )

    def __repr__(self):
        return f"<OnboardingSession user={self.user_id} step={self.step}>"
