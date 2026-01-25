"""Token repository - CRUD operations for API tokens."""
from typing import Optional, List
from datetime import datetime, timedelta

from src.repositories.base_repository import BaseRepository
from src.models.api_token import ApiToken


class TokenRepository(BaseRepository):
    """Repository for ApiToken CRUD operations."""

    def __init__(self):
        super().__init__()

    def get_token(
        self,
        service_name: str,
        token_type: str = "access_token",
        instagram_account_id: Optional[str] = None,
    ) -> Optional[ApiToken]:
        """
        Get token by service name, type, and optionally account.

        Args:
            service_name: Service identifier (e.g., 'instagram')
            token_type: Token type (e.g., 'access_token', 'refresh_token')
            instagram_account_id: UUID of Instagram account (for multi-account support)

        Returns:
            ApiToken or None if not found
        """
        query = self.db.query(ApiToken).filter(
            ApiToken.service_name == service_name,
            ApiToken.token_type == token_type,
        )

        # Filter by account if specified
        if instagram_account_id:
            query = query.filter(ApiToken.instagram_account_id == instagram_account_id)
        else:
            # For backward compatibility, match tokens without account ID
            query = query.filter(ApiToken.instagram_account_id.is_(None))

        result = query.first()
        self.end_read_transaction()
        return result

    def get_token_for_account(
        self,
        instagram_account_id: str,
        token_type: str = "access_token",
    ) -> Optional[ApiToken]:
        """
        Get Instagram token for a specific account.

        Convenience method for multi-account Instagram support.

        Args:
            instagram_account_id: UUID of Instagram account
            token_type: Token type (default: 'access_token')

        Returns:
            ApiToken or None if not found
        """
        result = self.db.query(ApiToken).filter(
            ApiToken.service_name == "instagram",
            ApiToken.token_type == token_type,
            ApiToken.instagram_account_id == instagram_account_id,
        ).first()
        self.end_read_transaction()
        return result

    def get_all_instagram_tokens(self, token_type: str = "access_token") -> List[ApiToken]:
        """
        Get all Instagram tokens (for token refresh iteration).

        Args:
            token_type: Token type (default: 'access_token')

        Returns:
            List of ApiToken for all Instagram accounts
        """
        result = self.db.query(ApiToken).filter(
            ApiToken.service_name == "instagram",
            ApiToken.token_type == token_type,
        ).all()
        self.end_read_transaction()
        return result

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
        issued_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        scopes: Optional[List[str]] = None,
        metadata: Optional[dict] = None,
        instagram_account_id: Optional[str] = None,
    ) -> ApiToken:
        """
        Create or update a token (UPSERT pattern).

        If a token exists for the service/type/account combination, it's updated.
        Otherwise, a new token is created.

        Args:
            service_name: Service identifier
            token_type: Token type
            token_value: Encrypted token value
            issued_at: When the token was issued (defaults to now)
            expires_at: When the token expires (None = never)
            scopes: OAuth scopes granted
            metadata: Additional service-specific data
            instagram_account_id: UUID of Instagram account (for multi-account support)

        Returns:
            Created or updated ApiToken
        """
        if issued_at is None:
            issued_at = datetime.utcnow()

        existing = self.get_token(service_name, token_type, instagram_account_id)

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
                instagram_account_id=instagram_account_id,
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
