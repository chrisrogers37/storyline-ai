"""Instagram API credential management, validation, and safety checks."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import httpx

from src.config.settings import settings
from src.utils.logger import logger

if TYPE_CHECKING:
    from src.services.integrations.instagram_api import InstagramAPIService


class InstagramCredentialManager:
    """Manages Instagram API credentials, validation, and safety checks.

    Extracted from InstagramAPIService to keep the parent focused on
    publishing (container creation, polling, publishing) and rate limiting,
    while this class handles credential retrieval, account validation,
    and pre-post safety checks.

    Uses composition: receives a reference to the parent service for access
    to token service, account service, settings service, and repositories.
    """

    # Class-level cache for account info (avoid repeated API calls)
    _account_info_cache: dict = {}

    def __init__(self, api_service: InstagramAPIService):
        self.service = api_service

    def get_active_account_credentials(
        self, telegram_chat_id: int
    ) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Get credentials for the active Instagram account.

        Supports both:
        - Multi-account mode: Uses active account from database
        - Legacy mode: Falls back to .env token if no account configured

        Args:
            telegram_chat_id: Chat to get active account for

        Returns:
            Tuple of (decrypted_token, instagram_account_id, username)
            Any value may be None if not available
        """
        # Try multi-account mode first
        active_account = self.service.account_service.get_active_account(
            telegram_chat_id
        )

        if active_account:
            # Get token for this specific account
            token_record = self.service.token_repo.get_token_for_account(
                str(active_account.id), token_type="access_token"
            )
            if token_record and not token_record.is_expired:
                # Decrypt the token
                try:
                    decrypted_token = self.service.encryption.decrypt(
                        token_record.token_value
                    )
                    return (
                        decrypted_token,
                        active_account.instagram_account_id,
                        active_account.instagram_username,
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to decrypt token for account {active_account.display_name}: {e}"
                    )

            # Token missing or expired for active account
            logger.warning(
                f"No valid token for active account {active_account.display_name}"
            )

        # Fallback to legacy .env mode (for backward compatibility)
        legacy_token = self.service.token_service.get_token("instagram")
        legacy_account_id = settings.INSTAGRAM_ACCOUNT_ID

        if legacy_token and legacy_account_id:
            logger.debug("Using legacy .env Instagram configuration")
            return (legacy_token, legacy_account_id, None)

        return (None, None, None)

    def is_configured(self, telegram_chat_id: Optional[int] = None) -> bool:
        """
        Check if Instagram API is properly configured.

        Supports both multi-account mode and legacy .env mode.

        Args:
            telegram_chat_id: Chat to check (uses ADMIN chat if not specified)
        """
        if not settings.ENABLE_INSTAGRAM_API:
            return False

        if not settings.FACEBOOK_APP_ID:
            return False

        if telegram_chat_id is None:
            telegram_chat_id = settings.ADMIN_TELEGRAM_CHAT_ID

        # Check for multi-account configuration
        active_account = self.service.account_service.get_active_account(
            telegram_chat_id
        )
        if active_account:
            return True

        # Fallback to legacy .env check
        return bool(settings.INSTAGRAM_ACCOUNT_ID)

    def validate_instagram_account_id(self) -> dict:
        """
        Validate that the account ID is configured and appears to be numeric.

        Note: Instagram Business Account IDs come in various formats:
        - Some start with '17841' and are 17 digits
        - Others may be shorter (15-16 digits) with different prefixes
        - The actual validation happens when we call the API

        Returns:
            dict with 'valid', 'account_id', 'reason'
        """
        account_id = settings.INSTAGRAM_ACCOUNT_ID

        if not account_id:
            return {
                "valid": False,
                "account_id": None,
                "reason": "INSTAGRAM_ACCOUNT_ID not configured",
            }

        account_id_str = str(account_id)

        # Basic validation: should be numeric
        if not account_id_str.isdigit():
            return {
                "valid": False,
                "account_id": account_id_str,
                "reason": f"Account ID {account_id_str} is not numeric",
            }

        # Length check (informational only - IDs vary from 15-17+ digits)
        if len(account_id_str) < self.service.MIN_ACCOUNT_ID_LENGTH:
            return {
                "valid": False,
                "account_id": account_id_str,
                "reason": f"Account ID {account_id_str} is too short ({len(account_id_str)} digits)",
            }

        return {
            "valid": True,
            "account_id": account_id_str,
            "reason": "Account ID format is valid",
        }

    async def get_account_info(self, telegram_chat_id: Optional[int] = None) -> dict:
        """
        Fetch Instagram account info (username, name, etc.) from the API.

        Supports both multi-account mode and legacy .env mode.
        Results are cached to avoid repeated API calls.

        Args:
            telegram_chat_id: Chat to get active account for (uses ADMIN chat if not specified)

        Returns:
            dict with 'username', 'name', 'id', or 'error' if failed
        """
        if telegram_chat_id is None:
            telegram_chat_id = settings.ADMIN_TELEGRAM_CHAT_ID

        # Get active account credentials
        token, account_id, username = self.get_active_account_credentials(
            telegram_chat_id
        )

        if not account_id:
            return {"error": "No Instagram account configured"}

        # Return cached result if available
        if account_id in self._account_info_cache:
            return self._account_info_cache[account_id]

        # If we already have username from multi-account mode, return it
        if username:
            result = {
                "id": account_id,
                "username": username,
                "name": None,  # Not stored in our DB, could fetch from API if needed
            }
            self._account_info_cache[account_id] = result
            return result

        if not token:
            return {"error": "No token available", "id": account_id}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.service.META_GRAPH_BASE}/{account_id}",
                    params={
                        "fields": "username,name",
                        "access_token": token,
                    },
                    timeout=30.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    result = {
                        "id": account_id,
                        "username": data.get("username"),
                        "name": data.get("name"),
                    }
                    # Cache the result
                    self._account_info_cache[account_id] = result
                    logger.info(
                        f"Fetched Instagram account info: @{result.get('username')}"
                    )
                    return result
                else:
                    logger.warning(
                        f"Failed to fetch account info: HTTP {response.status_code}"
                    )
                    return {
                        "error": f"HTTP {response.status_code}",
                        "id": account_id,
                    }

        except Exception as e:
            logger.error(f"Error fetching account info: {e}")
            return {"error": str(e), "id": account_id}

    async def validate_media_url(self, url: str) -> dict:
        """
        Validate that a media URL is accessible.

        Args:
            url: Public URL to check

        Returns:
            dict with valid, content_type, size_bytes
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.head(url, timeout=10.0, follow_redirects=True)

                if response.status_code != 200:
                    return {
                        "valid": False,
                        "error": f"HTTP {response.status_code}",
                    }

                content_type = response.headers.get("content-type", "")
                content_length = response.headers.get("content-length")

                return {
                    "valid": True,
                    "content_type": content_type,
                    "size_bytes": int(content_length) if content_length else None,
                }

        except httpx.RequestError as e:
            return {
                "valid": False,
                "error": str(e),
            }

    def safety_check_before_post(self, telegram_chat_id: Optional[int] = None) -> dict:
        """
        CRITICAL SAFETY GATE: Run all safety checks before posting.

        This method MUST be called before any post_story() call.
        Returns detailed validation results.

        Supports both multi-account mode (database) and legacy .env mode.

        Args:
            telegram_chat_id: Chat to check (uses ADMIN chat if not specified)

        Returns:
            dict with 'safe_to_post', 'checks', 'errors'
        """
        if telegram_chat_id is None:
            telegram_chat_id = settings.ADMIN_TELEGRAM_CHAT_ID

        # Get settings from database (not .env)
        chat_settings = self.service.settings_service.get_settings(telegram_chat_id)

        checks = {}
        errors = []
        account_info = None

        # Check 1: Instagram API enabled (from database)
        checks["instagram_api_enabled"] = chat_settings.enable_instagram_api
        if not chat_settings.enable_instagram_api:
            errors.append("Instagram API is disabled in settings")

        # Check 2: Get active account credentials (multi-account or legacy)
        token, account_id, username = self.get_active_account_credentials(
            telegram_chat_id
        )

        checks["account_configured"] = account_id is not None
        checks["token_exists"] = token is not None

        if not account_id:
            # Check if using legacy mode
            if settings.INSTAGRAM_ACCOUNT_ID:
                errors.append(
                    "Active account not selected in database, and no valid token for legacy .env config"
                )
            else:
                errors.append(
                    "No Instagram account configured. Use /settings to select one or add via CLI."
                )

        if not token:
            errors.append(
                "No valid Instagram access token found for the active account"
            )

        if account_id and username:
            account_info = f"@{username}"
        elif account_id:
            account_info = f"ID: {account_id}"

        # Check 3: DRY_RUN_MODE check (not an error, just informational) - from database
        checks["dry_run_mode"] = chat_settings.dry_run_mode

        # Log the safety check
        safe_to_post = len(errors) == 0
        if safe_to_post:
            logger.info(
                f"✅ SAFETY CHECK PASSED: Ready to post to Instagram "
                f"(Account: {account_info}, DRY_RUN: {chat_settings.dry_run_mode})"
            )
        else:
            logger.error(f"❌ SAFETY CHECK FAILED: {errors}")

        return {
            "safe_to_post": safe_to_post,
            "checks": checks,
            "errors": errors,
            "dry_run_mode": chat_settings.dry_run_mode,
            "account": account_info,
        }
