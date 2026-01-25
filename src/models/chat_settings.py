"""Chat settings model - per-chat runtime configuration."""
from sqlalchemy import Column, String, Integer, Boolean, BigInteger, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from src.config.database import Base


class ChatSettings(Base):
    """
    Per-chat runtime settings with .env fallback support.

    For Phase 1, there will be one record per deployment.
    Phase 3 introduces true multi-tenancy with one record per chat.
    """

    __tablename__ = "chat_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Chat identification
    telegram_chat_id = Column(BigInteger, nullable=False, unique=True, index=True)
    chat_name = Column(String(255))

    # Operational settings
    dry_run_mode = Column(Boolean, default=True)
    enable_instagram_api = Column(Boolean, default=False)
    is_paused = Column(Boolean, default=False)
    paused_at = Column(DateTime)
    paused_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    # Schedule settings
    posts_per_day = Column(Integer, default=3)
    posting_hours_start = Column(Integer, default=14)
    posting_hours_end = Column(Integer, default=2)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ChatSettings chat_id={self.telegram_chat_id} paused={self.is_paused}>"
