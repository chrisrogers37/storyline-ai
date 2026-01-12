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
