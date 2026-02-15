"""API token model for OAuth token storage."""

from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import Column, String, DateTime, Text, UniqueConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.orm import relationship

from src.config.database import Base


class ApiToken(Base):
    """
    API token model for storing OAuth tokens for external services.

    Tokens are encrypted at the application level before storage.
    Supports multiple token types per service (access_token, refresh_token).

    Lifecycle:
    - Initial token created via CLI auth flow or .env bootstrap
    - Tokens refreshed automatically before expiry
    - Old tokens overwritten (UPSERT pattern via unique constraint)
    """

    __tablename__ = "api_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Token identification
    service_name = Column(
        String(50), nullable=False, index=True
    )  # 'instagram', 'shopify'
    token_type = Column(String(50), nullable=False)  # 'access_token', 'refresh_token'

    # Link to Instagram account (NULL for non-Instagram services)
    instagram_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("instagram_accounts.id"),
        nullable=True,
        index=True,
    )

    # Per-tenant scoping (used by Google Drive OAuth tokens)
    chat_settings_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_settings.id"),
        nullable=True,
        index=True,
    )

    # Token data (encrypted at application level)
    token_value = Column(Text, nullable=False)

    # Lifecycle tracking
    issued_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=True, index=True)  # NULL = never expires
    last_refreshed_at = Column(DateTime, nullable=True)

    # OAuth metadata
    scopes = Column(ARRAY(Text), nullable=True)  # Array of granted scopes
    token_metadata = Column(
        JSONB, nullable=True
    )  # Service-specific data (e.g., account_id)

    # Audit timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to InstagramAccount
    instagram_account = relationship("InstagramAccount", back_populates="tokens")

    __table_args__ = (
        # One token per service per account (allows multiple IG accounts with separate tokens)
        UniqueConstraint(
            "service_name",
            "token_type",
            "instagram_account_id",
            name="unique_service_token_type_account",
        ),
    )

    def __repr__(self):
        expires_info = f"expires {self.expires_at}" if self.expires_at else "no expiry"
        return f"<ApiToken {self.service_name}/{self.token_type} ({expires_info})>"

    @property
    def is_expired(self) -> bool:
        """Check if the token has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def hours_until_expiry(self) -> Optional[float]:
        """Get hours until token expires, or None if no expiry."""
        if self.expires_at is None:
            return None
        delta = self.expires_at - datetime.utcnow()
        return max(0, delta.total_seconds() / 3600)
