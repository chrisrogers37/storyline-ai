"""Instagram Graph API service for Story posting."""

import asyncio
from datetime import datetime, timedelta
from typing import Optional

import httpx

from src.services.base_service import BaseService
from src.services.integrations.instagram_credentials import InstagramCredentialManager
from src.services.integrations.token_refresh import TokenRefreshService
from src.services.integrations.cloud_storage import CloudStorageService
from src.services.core.instagram_account_service import InstagramAccountService
from src.services.core.settings_service import SettingsService
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
        # result["story_id"] → The Instagram story ID

        # Check rate limits
        remaining = service.get_rate_limit_remaining()
    """

    # Meta Graph API configuration
    META_GRAPH_BASE = "https://graph.facebook.com/v18.0"
    CONTAINER_STATUS_POLL_INTERVAL = 2  # seconds
    CONTAINER_STATUS_MAX_POLLS = 30  # max ~60 seconds wait
    MIN_ACCOUNT_ID_LENGTH = 10  # Instagram account IDs are typically 15-17 digits

    def __init__(self):
        super().__init__()
        self.token_service = TokenRefreshService()
        self.cloud_service = CloudStorageService()
        self.history_repo = HistoryRepository()
        self.account_service = InstagramAccountService()
        self.token_repo = TokenRepository()
        self.encryption = TokenEncryption()
        self.settings_service = SettingsService()
        self.credentials = InstagramCredentialManager(self)

    def _get_active_account_credentials(
        self, telegram_chat_id: int
    ) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """Get credentials for the active Instagram account. Delegates to credentials."""
        return self.credentials.get_active_account_credentials(telegram_chat_id)

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
            input_params={
                "media_url": media_url[:50] + "...",
                "media_type": media_type,
            },
        ) as run_id:
            # Check rate limit first
            remaining = self.get_rate_limit_remaining()
            if remaining <= 0:
                raise RateLimitError(
                    f"Rate limit exhausted. 0/{settings.INSTAGRAM_POSTS_PER_HOUR} remaining."
                )

            # Get active account and its token
            token, account_id, account_username = self._get_active_account_credentials(
                telegram_chat_id
            )

            if not token:
                raise TokenExpiredError(
                    "No valid Instagram token available for active account"
                )

            if not account_id:
                raise InstagramAPIError(
                    "No Instagram account selected. Use /settings to select one."
                )

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

                self.set_result_summary(
                    run_id,
                    {
                        "success": True,
                        "story_id": story_id,
                        "account": account_username,
                    },
                )

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
                    logger.debug(
                        f"Container {container_id} ready after {poll_num + 1} polls"
                    )
                    return

                if status_code == "ERROR":
                    error_msg = data.get("status", "Unknown error")
                    raise InstagramAPIError(
                        f"Media container failed: {error_msg}",
                        error_code=status_code,
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
        """Validate that a media URL is accessible. Delegates to credentials."""
        return await self.credentials.validate_media_url(url)

    def is_configured(self, telegram_chat_id: Optional[int] = None) -> bool:
        """Check if Instagram API is properly configured. Delegates to credentials."""
        return self.credentials.is_configured(telegram_chat_id)

    def validate_instagram_account_id(self) -> dict:
        """Validate that the account ID is configured. Delegates to credentials."""
        return self.credentials.validate_instagram_account_id()

    async def get_account_info(self, telegram_chat_id: Optional[int] = None) -> dict:
        """Fetch Instagram account info. Delegates to credentials."""
        return await self.credentials.get_account_info(telegram_chat_id)

    def safety_check_before_post(self, telegram_chat_id: Optional[int] = None) -> dict:
        """CRITICAL SAFETY GATE: Run all safety checks. Delegates to credentials."""
        return self.credentials.safety_check_before_post(telegram_chat_id)
