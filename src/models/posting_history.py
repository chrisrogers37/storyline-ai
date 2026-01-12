"""Posting history model - permanent audit log."""
from sqlalchemy import Column, String, BigInteger, Integer, DateTime, Text, Boolean, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import ForeignKey
from datetime import datetime
import uuid

from src.config.database import Base


class PostingHistory(Base):
    """
    Posting history model.

    Permanent audit log - never deleted.
    Preserves complete record of all posting attempts.
    """

    __tablename__ = "posting_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    media_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("media_items.id"),
        nullable=False,
        index=True
    )
    queue_item_id = Column(UUID(as_uuid=True))  # Link back to queue (nullable after queue cleanup)

    # Queue lifecycle timestamps (preserved from posting_queue)
    queue_created_at = Column(DateTime, nullable=False)  # When item was added to queue
    queue_deleted_at = Column(DateTime, nullable=False)  # When item was removed from queue
    scheduled_for = Column(DateTime, nullable=False, index=True)  # Original scheduled time

    # Media metadata snapshot (at posting time)
    # Alternative to Type 2 SCD for media_items
    media_metadata = Column(JSONB)  # {title, tags, caption, link_url, custom_metadata}

    # Posting outcome
    posted_at = Column(DateTime, nullable=False, index=True)
    status = Column(String(50), nullable=False)  # 'posted', 'failed', 'skipped', 'rejected'
    success = Column(Boolean, nullable=False)

    # Instagram result (if successful)
    instagram_media_id = Column(Text)
    instagram_permalink = Column(Text)
    instagram_story_id = Column(Text)  # Story ID from Meta Graph API

    # Posting method tracking (Phase 2)
    posting_method = Column(String(20), default="telegram_manual")  # 'instagram_api' or 'telegram_manual'

    # User tracking
    posted_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    posted_by_telegram_username = Column(Text)  # Snapshot of username at posting time

    # Error info (if failed)
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)  # How many times we retried

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('posted', 'failed', 'skipped', 'rejected')",
            name="check_history_status"
        ),
    )

    def __repr__(self):
        return f"<PostingHistory {self.id} ({self.status}) posted at {self.posted_at}>"
