"""Instagram Graph API service for Story posting."""
import asyncio
from datetime import datetime, timedelta
from typing import Optional

import httpx

from src.services.base_service import BaseService
from src.services.integrations.token_refresh import TokenRefreshService
from src.services.integrations.cloud_storage import CloudStorageService
from src.services.core.instagram_account_service import InstagramAccountService
from src.repositories.history_repository import HistoryRepository
from src.repositories.token_repository import TokenRepository
from src.utils.encryption import TokenEncryption
from src.config.settings import settings
from src.exceptions import (
    InstagramAPIError,
    RateLimitError,
    TokenExpiredError,
)
from src.utils.logger import logger


class InstagramAPIService(BaseService):
    """
    Instagram Graph API integration for Stories.

    Handles:
    - Story creation and publishing
    - Media container status polling
    - Rate limit tracking
    - Error categorization

    Usage:
        service = InstagramAPIService()

        # Post a story
        result = await service.post_story(media_url="https://...")
        print(result["story_id"])

        # Check rate limits
        remaining = service.get_rate_limit_remaining()
    """

    # Meta Graph API configuration
    META_GRAPH_BASE = "https://graph.facebook.com/v18.0"
    CONTAINER_STATUS_POLL_INTERVAL = 2  # seconds
    CONTAINER_STATUS_MAX_POLLS = 30  # max ~60 seconds wait

    def __init__(self):
        super().__init__()
        self.token_service = TokenRefreshService()
        self.cloud_service = CloudStorageService()
        self.history_repo = HistoryRepository()
        self.account_service = InstagramAccountService()
        self.token_repo = TokenRepository()
        self.encryption = TokenEncryption()

    def _get_active_account_credentials(
        self,
        telegram_chat_id: int
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
        active_account = self.account_service.get_active_account(telegram_chat_id)

        if active_account:
            # Get token for this specific account
            token_record = self.token_repo.get_token_for_account(
                str(active_account.id),
                token_type="access_token"
            )
            if token_record and not token_record.is_expired:
                # Decrypt the token
                try:
                    decrypted_token = self.encryption.decrypt(token_record.token_value)
                    return (
                        decrypted_token,
                        active_account.instagram_account_id,
                        active_account.instagram_username
                    )
                except Exception as e:
                    logger.error(f"Failed to decrypt token for account {active_account.display_name}: {e}")

            # Token missing or expired for active account
            logger.warning(f"No valid token for active account {active_account.display_name}")

        # Fallback to legacy .env mode (for backward compatibility)
        legacy_token = self.token_service.get_token("instagram")
        legacy_account_id = settings.INSTAGRAM_ACCOUNT_ID

        if legacy_token and legacy_account_id:
            logger.debug("Using legacy .env Instagram configuration")
            return (legacy_token, legacy_account_id, None)

        return (None, None, None)

    async def post_story(
        self,
        media_url: str,
        media_type: str = "IMAGE",
        telegram_chat_id: Optional[int] = None,
    ) -> dict:
        """
        Post a Story to Instagram.

        Flow:
        1. Create media container
        2. Poll until status is FINISHED
        3. Publish the container

        Args:
            media_url: Public URL to media (from CloudStorageService)
            media_type: IMAGE or VIDEO
            telegram_chat_id: Chat ID to get active account for (uses ADMIN chat if not specified)

        Returns:
            dict with:
                - success: bool
                - story_id: str (Instagram media ID)
                - container_id: str
                - timestamp: datetime
                - account_username: str (which account was used)

        Raises:
            InstagramAPIError: On API failure
            RateLimitError: When rate limited
            TokenExpiredError: When token needs refresh
        """
        # Default to admin chat if not specified (for backward compatibility)
        if telegram_chat_id is None:
            telegram_chat_id = settings.ADMIN_TELEGRAM_CHAT_ID

        with self.track_execution(
            method_name="post_story",
            input_params={"media_url": media_url[:50] + "...", "media_type": media_type},
        ) as run_id:
            # Check rate limit first
            remaining = self.get_rate_limit_remaining()
            if remaining <= 0:
                raise RateLimitError(
                    f"Rate limit exhausted. 0/{settings.INSTAGRAM_POSTS_PER_HOUR} remaining."
                )

            # Get active account and its token
            token, account_id, account_username = self._get_active_account_credentials(telegram_chat_id)

            if not token:
                raise TokenExpiredError("No valid Instagram token available for active account")

            if not account_id:
                raise InstagramAPIError("No Instagram account selected. Use /settings to select one.")

            try:
                # Step 1: Create media container
                container_id = await self._create_media_container(
                    token=token,
                    account_id=account_id,
                    media_url=media_url,
                    media_type=media_type,
                )

                logger.info(f"Created media container: {container_id}")

                # Step 2: Poll until FINISHED
                await self._wait_for_container_ready(token, container_id)

                # Step 3: Publish
                story_id = await self._publish_container(
                    token=token,
                    account_id=account_id,
                    container_id=container_id,
                )

                logger.info(f"Published Instagram Story: {story_id}")

                result = {
                    "success": True,
                    "story_id": story_id,
                    "container_id": container_id,
                    "timestamp": datetime.utcnow(),
                    "account_username": account_username,
                    "account_id": account_id,
                }

                self.set_result_summary(run_id, {
                    "success": True,
                    "story_id": story_id,
                    "account": account_username,
                })

                return result

            except httpx.RequestError as e:
                logger.error(f"Network error posting to Instagram: {e}")
                raise InstagramAPIError(f"Network error: {e}")

    async def _create_media_container(
        self,
        token: str,
        account_id: str,
        media_url: str,
        media_type: str,
    ) -> str:
        """Create a media container for the story."""
        async with httpx.AsyncClient() as client:
            # For Stories, use the stories_media endpoint
            params = {
                "access_token": token,
                "media_type": "STORIES",
            }

            if media_type == "VIDEO":
                params["video_url"] = media_url
            else:
                params["image_url"] = media_url

            response = await client.post(
                f"{self.META_GRAPH_BASE}/{account_id}/media",
                data=params,
                timeout=60.0,
            )

            self._check_response_errors(response)

            data = response.json()
            container_id = data.get("id")

            if not container_id:
                raise InstagramAPIError(
                    "No container ID in response",
                    response=data,
                )

            return container_id

    async def _wait_for_container_ready(self, token: str, container_id: str) -> None:
        """Poll container status until FINISHED."""
        async with httpx.AsyncClient() as client:
            for poll_num in range(self.CONTAINER_STATUS_MAX_POLLS):
                response = await client.get(
                    f"{self.META_GRAPH_BASE}/{container_id}",
                    params={
                        "fields": "status_code,status",
                        "access_token": token,
                    },
                    timeout=30.0,
                )

                self._check_response_errors(response)

                data = response.json()
                status_code = data.get("status_code")

                if status_code == "FINISHED":
                    logger.debug(f"Container {container_id} ready after {poll_num + 1} polls")
                    return

                if status_code == "ERROR":
                    error_msg = data.get("status", "Unknown error")
                    raise InstagramAPIError(
                        f"Media container failed: {error_msg}",
                        error_code=status_code,
                        response=data,
                    )

                if status_code == "EXPIRED":
                    raise InstagramAPIError(
                        "Media container expired before publishing",
                        error_code=status_code,
                    )

                # Still processing, wait and retry
                logger.debug(f"Container status: {status_code}, polling again...")
                await asyncio.sleep(self.CONTAINER_STATUS_POLL_INTERVAL)

            # Exhausted polls
            raise InstagramAPIError(
                f"Media container did not finish after {self.CONTAINER_STATUS_MAX_POLLS} polls"
            )

    async def _publish_container(
        self,
        token: str,
        account_id: str,
        container_id: str,
    ) -> str:
        """Publish the media container as a Story."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.META_GRAPH_BASE}/{account_id}/media_publish",
                data={
                    "creation_id": container_id,
                    "access_token": token,
                },
                timeout=60.0,
            )

            self._check_response_errors(response)

            data = response.json()
            story_id = data.get("id")

            if not story_id:
                raise InstagramAPIError(
                    "No story ID in publish response",
                    response=data,
                )

            return story_id

    def _check_response_errors(self, response: httpx.Response) -> None:
        """Check API response for errors and raise appropriate exceptions."""
        if response.status_code == 200:
            return

        try:
            data = response.json()
            error = data.get("error", {})
        except Exception:
            raise InstagramAPIError(
                f"HTTP {response.status_code}: {response.text}",
            )

        error_code = error.get("code")
        error_subcode = error.get("error_subcode")
        error_message = error.get("message", "Unknown error")

        # Rate limit errors
        if error_code == 4 or error_code == 17:
            raise RateLimitError(
                error_message,
                error_code=str(error_code),
                error_subcode=error_subcode,
            )

        # Token errors
        if error_code == 190:
            raise TokenExpiredError(
                error_message,
                error_code=str(error_code),
                error_subcode=error_subcode,
            )

        # OAuth errors
        if error_code in (102, 104):
            raise TokenExpiredError(
                f"OAuth error: {error_message}",
                error_code=str(error_code),
            )

        # General API error
        raise InstagramAPIError(
            error_message,
            error_code=str(error_code) if error_code else None,
            error_subcode=error_subcode,
            response=data,
        )

    def get_rate_limit_remaining(self) -> int:
        """
        Calculate remaining posts based on trailing 60 min history.

        Meta allows approximately 25 content publishing API calls per hour.
        We derive this from our posting history rather than tracking API headers.

        Returns:
            Number of posts remaining in the current hour window
        """
        since = datetime.utcnow() - timedelta(hours=1)
        recent_api_posts = self.history_repo.count_by_method(
            method="instagram_api",
            since=since,
        )
        return max(0, settings.INSTAGRAM_POSTS_PER_HOUR - recent_api_posts)

    def get_rate_limit_status(self) -> dict:
        """
        Get detailed rate limit status.

        Returns:
            dict with remaining, limit, and oldest_post_in_window
        """
        remaining = self.get_rate_limit_remaining()
        used = settings.INSTAGRAM_POSTS_PER_HOUR - remaining

        return {
            "remaining": remaining,
            "limit": settings.INSTAGRAM_POSTS_PER_HOUR,
            "used": used,
            "window": "1 hour",
        }

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
        active_account = self.account_service.get_active_account(telegram_chat_id)
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
        if len(account_id_str) < 10:
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

    # Class-level cache for account info (avoid repeated API calls)
    _account_info_cache: dict = {}

    async def get_account_info(
        self,
        telegram_chat_id: Optional[int] = None
    ) -> dict:
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
        token, account_id, username = self._get_active_account_credentials(telegram_chat_id)

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
                    f"{self.META_GRAPH_BASE}/{account_id}",
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
                    logger.info(f"Fetched Instagram account info: @{result.get('username')}")
                    return result
                else:
                    logger.warning(f"Failed to fetch account info: HTTP {response.status_code}")
                    return {"error": f"HTTP {response.status_code}", "id": account_id}

        except Exception as e:
            logger.error(f"Error fetching account info: {e}")
            return {"error": str(e), "id": account_id}

    def safety_check_before_post(
        self,
        telegram_chat_id: Optional[int] = None
    ) -> dict:
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

        checks = {}
        errors = []
        account_info = None

        # Check 1: Instagram API enabled
        checks["instagram_api_enabled"] = settings.ENABLE_INSTAGRAM_API
        if not settings.ENABLE_INSTAGRAM_API:
            errors.append("ENABLE_INSTAGRAM_API is False")

        # Check 2: Get active account credentials (multi-account or legacy)
        token, account_id, username = self._get_active_account_credentials(telegram_chat_id)

        checks["account_configured"] = account_id is not None
        checks["token_exists"] = token is not None

        if not account_id:
            # Check if using legacy mode
            if settings.INSTAGRAM_ACCOUNT_ID:
                errors.append("Active account not selected in database, and no valid token for legacy .env config")
            else:
                errors.append("No Instagram account configured. Use /settings to select one or add via CLI.")

        if not token:
            errors.append("No valid Instagram access token found for the active account")

        if account_id and username:
            account_info = f"@{username}"
        elif account_id:
            account_info = f"ID: {account_id}"

        # Check 3: DRY_RUN_MODE check (not an error, just informational)
        checks["dry_run_mode"] = settings.DRY_RUN_MODE

        # Log the safety check
        safe_to_post = len(errors) == 0
        if safe_to_post:
            logger.info(
                f"✅ SAFETY CHECK PASSED: Ready to post to Instagram "
                f"(Account: {account_info}, DRY_RUN: {settings.DRY_RUN_MODE})"
            )
        else:
            logger.error(f"❌ SAFETY CHECK FAILED: {errors}")

        return {
            "safe_to_post": safe_to_post,
            "checks": checks,
            "errors": errors,
            "dry_run_mode": settings.DRY_RUN_MODE,
            "account": account_info,
        }
