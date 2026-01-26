"""User interaction model - tracks all bot interactions."""

from sqlalchemy import Column, String, BigInteger, DateTime, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import ForeignKey
from datetime import datetime
import uuid

from src.config.database import Base


class UserInteraction(Base):
    """
    User interaction model.

    Tracks all user interactions with the bot for analytics and audit trails.
    Interaction types:
    - 'command': Bot commands (/queue, /status, /help)
    - 'callback': Button callbacks (posted, skip, reject, etc.)
    - 'message': Reserved for future text message interactions
    - 'bot_response': Outgoing messages from bot (for visibility/debugging)
    """

    __tablename__ = "user_interactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Who performed the interaction (nullable for bot_response type)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,  # Allow NULL for bot_response entries
        index=True,
    )

    # What type of interaction
    interaction_type = Column(
        String(50), nullable=False, index=True
    )  # 'command', 'callback', 'message', 'bot_response'
    interaction_name = Column(
        String(100), nullable=False, index=True
    )  # '/queue', 'posted', 'photo_notification', etc.

    # Flexible context data
    context = Column(JSONB)  # {queue_item_id, media_id, caption, buttons, etc.}

    # Telegram metadata
    telegram_chat_id = Column(BigInteger)
    telegram_message_id = Column(BigInteger)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        CheckConstraint(
            "interaction_type IN ('command', 'callback', 'message', 'bot_response')",
            name="check_interaction_type",
        ),
    )

    def __repr__(self):
        return f"<UserInteraction {self.interaction_type}:{self.interaction_name} by {self.user_id}>"
