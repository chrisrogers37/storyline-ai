"""Media posting lock model - TTL-based repost prevention."""
from sqlalchemy import Column, String, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import ForeignKey
from datetime import datetime
import uuid

from src.config.database import Base


class MediaPostingLock(Base):
    """
    Media posting lock model.

    TTL-based locks to prevent premature reposts.
    Locks automatically expire (no manual deletion needed).
    """

    __tablename__ = "media_posting_locks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    media_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("media_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Lock details
    locked_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    locked_until = Column(DateTime, nullable=True, index=True)  # TTL: locked_at + X days, NULL = permanent
    lock_reason = Column(String(100), default="recent_post")  # 'recent_post', 'manual_hold', 'seasonal', 'permanent_reject'

    # Who created the lock
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "media_item_id",
            "locked_until",
            name="unique_active_lock"
        ),
    )

    def __repr__(self):
        return f"<MediaPostingLock {self.media_item_id} until {self.locked_until}>"
