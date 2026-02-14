"""Media item model - source of truth for all media."""

from sqlalchemy import (
    Column,
    String,
    BigInteger,
    Boolean,
    Integer,
    DateTime,
    Text,
    ARRAY,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
import uuid

from src.config.database import Base


class MediaItem(Base):
    """
    Media item model.

    Represents a media file (image/video) indexed in the system.
    """

    __tablename__ = "media_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # File information
    file_path = Column(Text, nullable=False, index=True)
    file_name = Column(Text, nullable=False)
    file_size = Column(BigInteger, nullable=False)
    file_hash = Column(Text, nullable=False, index=True)  # SHA256 of content
    mime_type = Column(String(100))

    # Media source (provider abstraction - Phase 01 Cloud Media)
    source_type = Column(String(50), nullable=False, default="local")
    source_identifier = Column(
        Text
    )  # Provider-specific ID (path for local, file_id for Drive)

    # Routing logic: determines auto vs manual posting
    requires_interaction = Column(
        Boolean, default=False
    )  # TRUE = send to Telegram, FALSE = auto-post

    # Category: extracted from parent folder during indexing (e.g., "memes", "merch")
    category = Column(Text, index=True)

    # Optional metadata (flexible for any use case)
    title = Column(Text)  # General purpose title (product name, meme title, etc.)
    link_url = Column(Text)  # Link for sticker (if requires_interaction = TRUE)
    caption = Column(Text)
    tags = Column(ARRAY(Text))  # Array of custom tags (user-defined)
    custom_metadata = Column(JSONB)  # Flexible JSON field for any additional data

    # Cloud storage (Phase 2 - temporary uploads for Instagram API)
    cloud_url = Column(Text)  # Cloudinary URL for Instagram API posting
    cloud_public_id = Column(Text)  # Cloudinary public_id for deletion
    cloud_uploaded_at = Column(DateTime)  # When uploaded to cloud
    cloud_expires_at = Column(DateTime)  # When cloud URL expires

    # Instagram backfill tracking (Phase 05 Cloud Media)
    instagram_media_id = Column(
        Text, unique=True, index=True
    )  # Instagram Graph API media ID
    backfilled_at = Column(DateTime)  # When this item was backfilled from Instagram

    # Tracking
    times_posted = Column(Integer, default=0)
    last_posted_at = Column(DateTime)
    is_active = Column(Boolean, default=True)

    # User tracking
    indexed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Multi-tenant: which chat owns this media item (NULL = legacy single-tenant)
    chat_settings_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_settings.id"),
        nullable=True,
        index=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "file_path", "chat_settings_id", name="unique_file_path_per_tenant"
        ),
    )

    def __repr__(self):
        return f"<MediaItem {self.file_name} (posted {self.times_posted}x)>"
