"""User-chat membership model - links users to chat instances."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from src.config.database import Base


class UserChatMembership(Base):
    """
    Join table linking users to chat_settings instances.

    Each row represents a user's membership in a specific chat instance.
    Memberships are auto-created on group chat interactions and can be
    deactivated when the bot is removed from a group.
    """

    __tablename__ = "user_chat_memberships"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    chat_settings_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_settings.id"),
        nullable=False,
    )

    # Distinct from users.role which is a system-level concept
    instance_role = Column(String(20), nullable=False, default="member")

    joined_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    is_active = Column(Boolean, nullable=False, default=True)

    user = relationship("User")
    chat_settings = relationship("ChatSettings")

    __table_args__ = (
        UniqueConstraint(
            "user_id", "chat_settings_id", name="unique_user_chat_membership"
        ),
        CheckConstraint(
            "instance_role IN ('owner', 'admin', 'member')",
            name="check_instance_role",
        ),
    )

    def __repr__(self):
        return (
            f"<UserChatMembership user={self.user_id} "
            f"chat={self.chat_settings_id} role={self.instance_role}>"
        )
