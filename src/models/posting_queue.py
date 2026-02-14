"""Posting queue model - active work items only."""

from sqlalchemy import (
    Column,
    String,
    BigInteger,
    Integer,
    DateTime,
    Text,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import ForeignKey
from datetime import datetime
import uuid

from src.config.database import Base


class PostingQueue(Base):
    """
    Posting queue model.

    Ephemeral table for active work items.
    Items are deleted after completion and moved to posting_history.
    """

    __tablename__ = "posting_queue"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    media_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("media_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    scheduled_for = Column(DateTime, nullable=False, index=True)
    status = Column(
        String(50), default="pending", nullable=False, index=True
    )  # 'pending', 'processing', 'retrying'

    # Temporary web-hosted URL (e.g., Cloudinary, S3, etc.)
    # Used during posting process, deleted after completion
    web_hosted_url = Column(Text)
    web_hosted_public_id = Column(Text)  # Provider-specific ID for cleanup

    # Telegram tracking (for manual posts)
    telegram_message_id = Column(BigInteger)
    telegram_chat_id = Column(BigInteger)

    # Retry logic
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    next_retry_at = Column(DateTime)
    last_error = Column(Text)

    # Multi-tenant: which chat owns this queue item (NULL = legacy single-tenant)
    chat_settings_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_settings.id"),
        nullable=True,
        index=True,
    )

    # Timestamps (preserved in history)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'retrying')", name="check_status"
        ),
    )

    def __repr__(self):
        return f"<PostingQueue {self.id} ({self.status}) scheduled for {self.scheduled_for}>"
