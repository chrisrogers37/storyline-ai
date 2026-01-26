"""Instagram account model - stores connected Instagram accounts."""

from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from src.config.database import Base


class InstagramAccount(Base):
    """
    Represents a connected Instagram account.

    Separation of concerns:
    - This model stores IDENTITY (who is the account?)
    - api_tokens stores CREDENTIALS (how do we authenticate?)
    - chat_settings stores SELECTION (which account is active?)
    """

    __tablename__ = "instagram_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Account identification
    display_name = Column(String(100), nullable=False)
    instagram_account_id = Column(String(50), nullable=False, unique=True)
    instagram_username = Column(String(50))

    # Status
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tokens = relationship("ApiToken", back_populates="instagram_account")

    def __repr__(self):
        return f"<InstagramAccount {self.display_name} (@{self.instagram_username})>"
