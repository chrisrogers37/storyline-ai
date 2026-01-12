"""Token repository - CRUD operations for API tokens."""
from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.models.api_token import ApiToken


class TokenRepository:
    """Repository for ApiToken CRUD operations."""

    def __init__(self):
        self.db: Session = next(get_db())

    def get_token(
        self,
        service_name: str,
        token_type: str = "access_token",
    ) -> Optional[ApiToken]:
        """
        Get token by service name and type.

        Args:
            service_name: Service identifier (e.g., 'instagram')
            token_type: Token type (e.g., 'access_token', 'refresh_token')

        Returns:
            ApiToken or None if not found
        """
        return (
            self.db.query(ApiToken)
            .filter(
                ApiToken.service_name == service_name,
                ApiToken.token_type == token_type,
            )
            .first()
        )

    def get_all_for_service(self, service_name: str) -> List[ApiToken]:
        """Get all tokens for a service (access and refresh)."""
        return (
            self.db.query(ApiToken)
            .filter(ApiToken.service_name == service_name)
            .all()
        )

    def create_or_update(
        self,
        service_name: str,
        token_type: str,
        token_value: str,
        issued_at: datetime,
        expires_at: Optional[datetime] = None,
        scopes: Optional[List[str]] = None,
        metadata: Optional[dict] = None,
    ) -> ApiToken:
        """
        Create or update a token (UPSERT pattern).

        If a token exists for the service/type combination, it's updated.
        Otherwise, a new token is created.

        Args:
            service_name: Service identifier
            token_type: Token type
            token_value: Encrypted token value
            issued_at: When the token was issued
            expires_at: When the token expires (None = never)
            scopes: OAuth scopes granted
            metadata: Additional service-specific data

        Returns:
            Created or updated ApiToken
        """
        existing = self.get_token(service_name, token_type)

        if existing:
            # Update existing token
            existing.token_value = token_value
            existing.issued_at = issued_at
            existing.expires_at = expires_at
            existing.last_refreshed_at = datetime.utcnow()
            if scopes is not None:
                existing.scopes = scopes
            if metadata is not None:
                existing.token_metadata = metadata
            self.db.commit()
            self.db.refresh(existing)
            return existing
        else:
            # Create new token
            token = ApiToken(
                service_name=service_name,
                token_type=token_type,
                token_value=token_value,
                issued_at=issued_at,
                expires_at=expires_at,
                scopes=scopes,
                token_metadata=metadata,
            )
            self.db.add(token)
            self.db.commit()
            self.db.refresh(token)
            return token

    def update_last_refreshed(self, service_name: str, token_type: str) -> bool:
        """Update the last_refreshed_at timestamp."""
        token = self.get_token(service_name, token_type)
        if token:
            token.last_refreshed_at = datetime.utcnow()
            self.db.commit()
            return True
        return False

    def get_expiring_tokens(self, hours_until_expiry: int = 168) -> List[ApiToken]:
        """
        Get all tokens expiring within the specified hours.

        Default is 168 hours (7 days), used to schedule refresh before expiry.

        Args:
            hours_until_expiry: Hours threshold for "expiring soon"

        Returns:
            List of tokens that will expire within the threshold
        """
        cutoff = datetime.utcnow() + timedelta(hours=hours_until_expiry)
        return (
            self.db.query(ApiToken)
            .filter(
                ApiToken.expires_at.isnot(None),
                ApiToken.expires_at <= cutoff,
                ApiToken.expires_at > datetime.utcnow(),  # Not already expired
            )
            .order_by(ApiToken.expires_at.asc())
            .all()
        )

    def get_expired_tokens(self) -> List[ApiToken]:
        """Get all expired tokens."""
        now = datetime.utcnow()
        return (
            self.db.query(ApiToken)
            .filter(
                ApiToken.expires_at.isnot(None),
                ApiToken.expires_at <= now,
            )
            .all()
        )

    def delete_token(self, service_name: str, token_type: str) -> bool:
        """Delete a specific token."""
        token = self.get_token(service_name, token_type)
        if token:
            self.db.delete(token)
            self.db.commit()
            return True
        return False

    def delete_all_for_service(self, service_name: str) -> int:
        """Delete all tokens for a service. Returns count deleted."""
        count = (
            self.db.query(ApiToken)
            .filter(ApiToken.service_name == service_name)
            .delete()
        )
        self.db.commit()
        return count
