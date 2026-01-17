"""Instagram Graph API service for Story posting."""
import asyncio
from datetime import datetime, timedelta
from typing import Optional

import httpx

from src.services.base_service import BaseService
from src.services.integrations.token_refresh import TokenRefreshService
from src.services.integrations.cloud_storage import CloudStorageService
from src.repositories.history_repository import HistoryRepository
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

    async def post_story(
        self,
        media_url: str,
        media_type: str = "IMAGE",
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

        Returns:
            dict with:
                - success: bool
                - story_id: str (Instagram media ID)
                - container_id: str
                - timestamp: datetime

        Raises:
            InstagramAPIError: On API failure
            RateLimitError: When rate limited
            TokenExpiredError: When token needs refresh
        """
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

            # Get access token
            token = self.token_service.get_token("instagram")
            if not token:
                raise TokenExpiredError("No valid Instagram token available")

            account_id = settings.INSTAGRAM_ACCOUNT_ID
            if not account_id:
                raise InstagramAPIError("INSTAGRAM_ACCOUNT_ID not configured")

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
                }

                self.set_result_summary(run_id, {
                    "success": True,
                    "story_id": story_id,
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

    def is_configured(self) -> bool:
        """Check if Instagram API is properly configured."""
        return all([
            settings.ENABLE_INSTAGRAM_API,
            settings.INSTAGRAM_ACCOUNT_ID,
            settings.FACEBOOK_APP_ID,
        ])

    def validate_instagram_account_id(self) -> dict:
        """
        SAFETY GATE: Validate that the account ID is an Instagram Business Account,
        NOT a Facebook Page ID.

        Instagram Business Account IDs:
        - Start with '17841' (Meta's Instagram ID prefix)
        - Are 17 digits long

        Facebook Page IDs:
        - Are typically 15-16 digits
        - Do NOT start with '17841'

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

        # Safety check 1: Must start with Instagram prefix
        if not account_id_str.startswith("17841"):
            return {
                "valid": False,
                "account_id": account_id_str,
                "reason": f"DANGER: Account ID {account_id_str} does NOT start with '17841'. "
                          "This may be a Facebook Page ID, NOT an Instagram Business Account ID. "
                          "Posting to this ID could post to Facebook instead of Instagram!",
            }

        # Safety check 2: Should be 17 digits
        if len(account_id_str) != 17:
            logger.warning(
                f"Instagram Account ID {account_id_str} is {len(account_id_str)} digits "
                f"(expected 17). This may still be valid but verify in Meta Business Suite."
            )

        return {
            "valid": True,
            "account_id": account_id_str,
            "reason": "Account ID appears to be a valid Instagram Business Account ID",
        }

    # Class-level cache for account info (avoid repeated API calls)
    _account_info_cache: dict = {}

    async def get_account_info(self) -> dict:
        """
        Fetch Instagram account info (username, name, etc.) from the API.

        Results are cached to avoid repeated API calls.

        Returns:
            dict with 'username', 'name', 'id', or 'error' if failed
        """
        account_id = settings.INSTAGRAM_ACCOUNT_ID

        # Return cached result if available
        if account_id in self._account_info_cache:
            return self._account_info_cache[account_id]

        token = self.token_service.get_token("instagram")
        if not token:
            return {"error": "No token available"}

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

    def safety_check_before_post(self) -> dict:
        """
        CRITICAL SAFETY GATE: Run all safety checks before posting.

        This method MUST be called before any post_story() call.
        Returns detailed validation results.

        Returns:
            dict with 'safe_to_post', 'checks', 'errors'
        """
        checks = {}
        errors = []

        # Check 1: Instagram API enabled
        checks["instagram_api_enabled"] = settings.ENABLE_INSTAGRAM_API
        if not settings.ENABLE_INSTAGRAM_API:
            errors.append("ENABLE_INSTAGRAM_API is False")

        # Check 2: Validate Instagram Account ID format
        id_validation = self.validate_instagram_account_id()
        checks["account_id_valid"] = id_validation["valid"]
        if not id_validation["valid"]:
            errors.append(id_validation["reason"])

        # Check 3: Token exists
        token = self.token_service.get_token("instagram")
        checks["token_exists"] = token is not None
        if not token:
            errors.append("No Instagram access token found")

        # Check 4: DRY_RUN_MODE check (not an error, just informational)
        checks["dry_run_mode"] = settings.DRY_RUN_MODE

        # Log the safety check
        safe_to_post = len(errors) == 0
        if safe_to_post:
            logger.info(
                f"✅ SAFETY CHECK PASSED: Ready to post to Instagram "
                f"(Account ID: {settings.INSTAGRAM_ACCOUNT_ID}, DRY_RUN: {settings.DRY_RUN_MODE})"
            )
        else:
            logger.error(f"❌ SAFETY CHECK FAILED: {errors}")

        return {
            "safe_to_post": safe_to_post,
            "checks": checks,
            "errors": errors,
            "dry_run_mode": settings.DRY_RUN_MODE,
        }
