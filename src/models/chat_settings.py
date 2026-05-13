"""Chat settings model - per-chat runtime configuration."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    String,
    Text,
    Integer,
    Boolean,
    BigInteger,
    DateTime,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
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
    display_name = Column(String(100), nullable=True)

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

    # Per-chat lock TTLs (NULL = use REPOST_TTL_DAYS / SKIP_TTL_DAYS env defaults)
    repost_ttl_days = Column(Integer, nullable=True)
    skip_ttl_days = Column(Integer, nullable=True)

    # Caption rendering style ('enhanced' = emoji-rich, 'simple' = plain text).
    # NULL = use CAPTION_STYLE env default.
    caption_style = Column(String(20), nullable=True)

    # Whether the worker pushes startup/shutdown lifecycle notifications to
    # this chat. NULL = use SEND_LIFECYCLE_NOTIFICATIONS env default.
    send_lifecycle_notifications = Column(Boolean, nullable=True)

    # JIT scheduler: when the last post was sent to Telegram for this tenant.
    # Used by is_slot_due() to determine when the next slot should fire.
    # NULL = no post sent yet (treat as "slot is due immediately").
    last_post_sent_at = Column(DateTime(timezone=True), nullable=True)

    # Notification settings
    show_verbose_notifications = Column(Boolean, default=True)

    # Media sync (Phase 04 Cloud Media)
    media_sync_enabled = Column(Boolean, default=False)

    # AI caption generation
    enable_ai_captions = Column(Boolean, default=False)

    # Per-chat media source configuration (NULL = use global env var fallback)
    media_source_type = Column(String(50), nullable=True)  # 'local' or 'google_drive'
    media_source_root = Column(
        Text, nullable=True
    )  # path (local) or folder ID (google_drive)

    # Active Instagram account (for multi-account support)
    active_instagram_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("instagram_accounts.id"),
        nullable=True,  # NULL = no account selected yet
    )

    # Onboarding wizard state
    onboarding_step = Column(String(50), nullable=True)  # NULL = not in onboarding
    onboarding_completed = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to active Instagram account
    active_instagram_account = relationship("InstagramAccount")

    __table_args__ = (
        CheckConstraint(
            "posts_per_day BETWEEN 1 AND 50",
            name="valid_posts_per_day",
        ),
        CheckConstraint(
            "posting_hours_start BETWEEN 0 AND 23",
            name="valid_hours_start",
        ),
        CheckConstraint(
            "posting_hours_end BETWEEN 0 AND 23",
            name="valid_hours_end",
        ),
    )

    def __repr__(self):
        return f"<ChatSettings chat_id={self.telegram_chat_id} paused={self.is_paused}>"
