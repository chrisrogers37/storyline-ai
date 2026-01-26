"""Token refresh service for managing OAuth tokens."""
from datetime import datetime, timedelta
from typing import Optional

import httpx

from src.services.base_service import BaseService
from src.repositories.token_repository import TokenRepository
from src.repositories.instagram_account_repository import InstagramAccountRepository
from src.utils.encryption import TokenEncryption
from src.config.settings import settings
from src.exceptions import TokenExpiredError
from src.utils.logger import logger


class TokenRefreshService(BaseService):
    """
    Manage OAuth tokens for external services.

    Handles:
    - Token retrieval (DB first, fallback to .env)
    - Automatic refresh before expiry
    - Token health monitoring
    - Bootstrap from .env to DB

    Usage:
        service = TokenRefreshService()

        # Get current valid token
        token = service.get_token("instagram")

        # Check token health
        health = service.check_token_health("instagram")
        if health["needs_refresh"]:
            await service.refresh_instagram_token()
    """

    # Meta Graph API endpoints
    META_GRAPH_BASE = "https://graph.facebook.com/v18.0"
    META_TOKEN_REFRESH_ENDPOINT = f"{META_GRAPH_BASE}/oauth/access_token"

    # Refresh buffer: refresh tokens this many hours before expiry
    REFRESH_BUFFER_HOURS = 168  # 7 days

    def __init__(self):
        super().__init__()
        self.token_repo = TokenRepository()
        self.account_repo = InstagramAccountRepository()
        self._encryption: Optional[TokenEncryption] = None

    @property
    def encryption(self) -> TokenEncryption:
        """Lazy-load encryption to avoid errors when ENCRYPTION_KEY not set."""
        if self._encryption is None:
            self._encryption = TokenEncryption()
        return self._encryption

    def get_token(self, service: str, token_type: str = "access_token") -> Optional[str]:
        """
        Get current valid token for a service.

        Strategy:
        1. Check database for stored token
        2. If not in DB, check .env settings
        3. If in .env but not DB, bootstrap to DB

        Args:
            service: Service name (e.g., 'instagram')
            token_type: Token type (default: 'access_token')

        Returns:
            Decrypted token string, or None if not available

        Raises:
            TokenExpiredError: If token exists but is expired
        """
        # Check database first
        db_token = self.token_repo.get_token(service, token_type)

        if db_token:
            # Check if expired
            if db_token.is_expired:
                logger.warning(f"Token for {service}/{token_type} has expired")
                raise TokenExpiredError(
                    f"Token for {service} has expired. Please refresh or re-authenticate."
                )

            # Decrypt and return
            try:
                return self.encryption.decrypt(db_token.token_value)
            except ValueError as e:
                logger.error(f"Failed to decrypt token for {service}: {e}")
                return None

        # Fallback to .env settings
        env_token = self._get_env_token(service, token_type)

        if env_token:
            logger.info(f"Using {service} token from .env (will bootstrap to DB)")
            # Bootstrap to database for future use
            self.bootstrap_from_env(service)
            return env_token

        return None

    def _get_env_token(self, service: str, token_type: str) -> Optional[str]:
        """Get token from environment settings."""
        if service == "instagram" and token_type == "access_token":
            return settings.INSTAGRAM_ACCESS_TOKEN
        # Add other services here as needed
        return None

    def bootstrap_from_env(self, service: str) -> bool:
        """
        Copy token from .env to database for automatic refresh management.

        This should be called once when first setting up a service,
        or automatically when get_token() finds .env token but no DB token.

        Args:
            service: Service name to bootstrap

        Returns:
            True if bootstrap successful
        """
        with self.track_execution(
            method_name="bootstrap_from_env",
            input_params={"service": service},
        ) as run_id:
            env_token = self._get_env_token(service, "access_token")

            if not env_token:
                logger.warning(f"No .env token found for {service}")
                self.set_result_summary(run_id, {"success": False, "reason": "no_env_token"})
                return False

            # Encrypt the token
            encrypted = self.encryption.encrypt(env_token)

            # Meta long-lived tokens expire after 60 days
            # We don't know the exact issue date, so assume issued now
            issued_at = datetime.utcnow()
            expires_at = issued_at + timedelta(days=60)

            # Store in database
            self.token_repo.create_or_update(
                service_name=service,
                token_type="access_token",
                token_value=encrypted,
                issued_at=issued_at,
                expires_at=expires_at,
                metadata={
                    "bootstrapped_from": "env",
                    "bootstrapped_at": issued_at.isoformat(),
                },
            )

            logger.info(f"Bootstrapped {service} token from .env to database")
            self.set_result_summary(run_id, {"success": True, "service": service})
            return True

    async def refresh_instagram_token(
        self,
        instagram_account_id: Optional[str] = None
    ) -> bool:
        """
        Refresh Instagram long-lived access token.

        Meta's long-lived tokens last 60 days but can be refreshed.
        A refreshed token is valid for another 60 days.

        Supports both:
        - Multi-account mode: Pass instagram_account_id to refresh specific account
        - Legacy mode: Pass None to refresh the legacy token (no account FK)

        Args:
            instagram_account_id: UUID of Instagram account to refresh (None for legacy)

        Returns:
            True if refresh successful

        Raises:
            TokenExpiredError: If current token is invalid/expired
        """
        account_label = instagram_account_id or "legacy"

        with self.track_execution(
            method_name="refresh_instagram_token",
            input_params={"account_id": account_label}
        ) as run_id:
            # Get current token
            if instagram_account_id:
                db_token = self.token_repo.get_token_for_account(
                    instagram_account_id,
                    token_type="access_token"
                )
            else:
                db_token = self.token_repo.get_token("instagram", "access_token")

            if not db_token:
                logger.error(f"No Instagram token found to refresh for {account_label}")
                self.set_result_summary(run_id, {"success": False, "reason": "no_token"})
                return False

            current_token = self.encryption.decrypt(db_token.token_value)

            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        self.META_TOKEN_REFRESH_ENDPOINT,
                        params={
                            "grant_type": "ig_refresh_token",
                            "access_token": current_token,
                        },
                        timeout=30.0,
                    )

                    if response.status_code != 200:
                        error_data = response.json()
                        logger.error(f"Instagram token refresh failed for {account_label}: {error_data}")
                        self.set_result_summary(run_id, {
                            "success": False,
                            "status_code": response.status_code,
                            "error": error_data,
                        })
                        return False

                    data = response.json()
                    new_token = data.get("access_token")
                    expires_in = data.get("expires_in", 5184000)  # Default 60 days in seconds

                    if not new_token:
                        logger.error(f"No access_token in refresh response for {account_label}")
                        self.set_result_summary(run_id, {"success": False, "reason": "no_token_in_response"})
                        return False

                    # Store the new token
                    issued_at = datetime.utcnow()
                    expires_at = issued_at + timedelta(seconds=expires_in)

                    encrypted = self.encryption.encrypt(new_token)

                    self.token_repo.create_or_update(
                        service_name="instagram",
                        token_type="access_token",
                        token_value=encrypted,
                        issued_at=issued_at,
                        expires_at=expires_at,
                        metadata={
                            "refreshed_at": issued_at.isoformat(),
                            "expires_in_seconds": expires_in,
                        },
                        instagram_account_id=instagram_account_id,
                    )

                    logger.info(
                        f"Instagram token refreshed successfully for {account_label}. "
                        f"New expiry: {expires_at.isoformat()}"
                    )

                    self.set_result_summary(run_id, {
                        "success": True,
                        "account": account_label,
                        "expires_at": expires_at.isoformat(),
                        "expires_in_days": expires_in // 86400,
                    })
                    return True

            except httpx.RequestError as e:
                logger.error(f"Network error refreshing Instagram token for {account_label}: {e}")
                self.set_result_summary(run_id, {"success": False, "error": str(e)})
                return False

    async def refresh_all_instagram_tokens(self) -> dict:
        """
        Refresh all Instagram tokens that need refreshing.

        Iterates through all Instagram accounts and refreshes tokens
        that are expiring within the buffer window.

        Returns:
            dict with:
                - refreshed: int - count of successfully refreshed tokens
                - failed: int - count of failed refreshes
                - skipped: int - count skipped (not expiring soon)
                - details: list - per-account results
        """
        with self.track_execution(method_name="refresh_all_instagram_tokens") as run_id:
            results = {
                "refreshed": 0,
                "failed": 0,
                "skipped": 0,
                "details": [],
            }

            # Get all Instagram tokens
            all_tokens = self.token_repo.get_all_instagram_tokens()

            for token in all_tokens:
                account_id = str(token.instagram_account_id) if token.instagram_account_id else None
                account_label = account_id or "legacy"

                # Check if needs refresh
                hours_until_expiry = token.hours_until_expiry()
                needs_refresh = (
                    hours_until_expiry is not None
                    and hours_until_expiry <= self.REFRESH_BUFFER_HOURS
                )

                if not needs_refresh:
                    results["skipped"] += 1
                    results["details"].append({
                        "account": account_label,
                        "status": "skipped",
                        "reason": f"Not expiring soon ({int(hours_until_expiry or 0)}h remaining)",
                    })
                    continue

                # Refresh this token
                success = await self.refresh_instagram_token(instagram_account_id=account_id)

                if success:
                    results["refreshed"] += 1
                    results["details"].append({
                        "account": account_label,
                        "status": "refreshed",
                    })
                else:
                    results["failed"] += 1
                    results["details"].append({
                        "account": account_label,
                        "status": "failed",
                    })

            logger.info(
                f"Token refresh complete: {results['refreshed']} refreshed, "
                f"{results['failed']} failed, {results['skipped']} skipped"
            )

            self.set_result_summary(run_id, results)
            return results

    def check_token_health(self, service: str) -> dict:
        """
        Check token status for a service.

        Returns:
            dict with:
                - valid: bool - whether token exists and is not expired
                - exists: bool - whether token record exists
                - expires_at: datetime or None
                - expires_in_hours: float or None
                - needs_refresh: bool - whether refresh should be scheduled
                - last_refreshed: datetime or None
                - error: str or None - error message if invalid
        """
        db_token = self.token_repo.get_token(service, "access_token")

        if not db_token:
            # Check .env fallback
            env_token = self._get_env_token(service, "access_token")
            if env_token:
                return {
                    "valid": True,
                    "exists": True,
                    "source": "env",
                    "expires_at": None,
                    "expires_in_hours": None,
                    "needs_refresh": False,
                    "needs_bootstrap": True,
                    "last_refreshed": None,
                    "error": None,
                }

            return {
                "valid": False,
                "exists": False,
                "source": None,
                "expires_at": None,
                "expires_in_hours": None,
                "needs_refresh": False,
                "needs_bootstrap": False,
                "last_refreshed": None,
                "error": f"No token found for {service}",
            }

        expires_in_hours = db_token.hours_until_expiry()
        needs_refresh = (
            expires_in_hours is not None
            and expires_in_hours <= self.REFRESH_BUFFER_HOURS
        )

        return {
            "valid": not db_token.is_expired,
            "exists": True,
            "source": "database",
            "expires_at": db_token.expires_at,
            "expires_in_hours": expires_in_hours,
            "needs_refresh": needs_refresh,
            "needs_bootstrap": False,
            "last_refreshed": db_token.last_refreshed_at,
            "error": "Token expired" if db_token.is_expired else None,
        }

    def get_tokens_needing_refresh(self) -> list:
        """Get all tokens that need to be refreshed soon."""
        return self.token_repo.get_expiring_tokens(hours_until_expiry=self.REFRESH_BUFFER_HOURS)
