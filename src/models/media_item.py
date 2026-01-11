"""Media item model - source of truth for all media."""
from sqlalchemy import Column, String, BigInteger, Boolean, Integer, DateTime, Text, ARRAY
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import ForeignKey
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
    file_path = Column(Text, nullable=False, unique=True, index=True)
    file_name = Column(Text, nullable=False)
    file_size = Column(BigInteger, nullable=False)
    file_hash = Column(Text, nullable=False, index=True)  # SHA256 of content
    mime_type = Column(String(100))

    # Routing logic: determines auto vs manual posting
    requires_interaction = Column(Boolean, default=False)  # TRUE = send to Telegram, FALSE = auto-post

    # Category: extracted from parent folder during indexing (e.g., "memes", "merch")
    category = Column(Text, index=True)

    # Optional metadata (flexible for any use case)
    title = Column(Text)  # General purpose title (product name, meme title, etc.)
    link_url = Column(Text)  # Link for sticker (if requires_interaction = TRUE)
    caption = Column(Text)
    tags = Column(ARRAY(Text))  # Array of custom tags (user-defined)
    custom_metadata = Column(JSONB)  # Flexible JSON field for any additional data

    # Tracking
    times_posted = Column(Integer, default=0)
    last_posted_at = Column(DateTime)
    is_active = Column(Boolean, default=True)

    # User tracking
    indexed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<MediaItem {self.file_name} (posted {self.times_posted}x)>"
