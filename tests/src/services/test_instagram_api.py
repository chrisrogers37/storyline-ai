"""Tests for InstagramAPIService."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from contextlib import contextmanager
from datetime import datetime

import httpx

from src.exceptions import (
    InstagramAPIError,
    RateLimitError,
    TokenExpiredError,
)


@contextmanager
def mock_track_execution(*args, **kwargs):
    """Mock context manager for track_execution."""
    yield "mock_run_id"


@pytest.mark.unit
class TestInstagramAPIService:
    """Test suite for InstagramAPIService."""

    @pytest.fixture
    def instagram_service(self):
        """Create InstagramAPIService with mocked dependencies."""
        with (
            patch("src.services.integrations.instagram_api.TokenRefreshService"),
            patch("src.services.integrations.instagram_api.CloudStorageService"),
            patch("src.services.integrations.instagram_api.HistoryRepository"),
            patch("src.services.integrations.instagram_api.InstagramAccountService"),
            patch("src.services.integrations.instagram_api.TokenRepository"),
            patch("src.services.integrations.instagram_api.TokenEncryption"),
            patch("src.services.integrations.instagram_api.SettingsService"),
            patch("src.services.base_service.ServiceRunRepository"),
        ):
            from src.services.integrations.instagram_api import (
                InstagramAPIService,
            )

            service = InstagramAPIService()
            service.token_service = Mock()
            service.cloud_service = Mock()
            service.history_repo = Mock()
            service.track_execution = mock_track_execution
            service.set_result_summary = Mock()
            yield service

    # ==================== get_rate_limit_remaining Tests ====================

    @patch("src.services.integrations.instagram_api.settings")
    def test_get_rate_limit_remaining_no_recent_posts(
        self, mock_settings, instagram_service
    ):
        """Test rate limit shows full capacity when no recent posts."""
        mock_settings.INSTAGRAM_POSTS_PER_HOUR = 25
        instagram_service.history_repo.count_by_method.return_value = 0

        result = instagram_service.get_rate_limit_remaining()

        assert result == 25

    @patch("src.services.integrations.instagram_api.settings")
    def test_get_rate_limit_remaining_some_posts(
        self, mock_settings, instagram_service
    ):
        """Test rate limit calculation with recent posts."""
        mock_settings.INSTAGRAM_POSTS_PER_HOUR = 25
        instagram_service.history_repo.count_by_method.return_value = 10

        result = instagram_service.get_rate_limit_remaining()

        assert result == 15

    @patch("src.services.integrations.instagram_api.settings")
    def test_get_rate_limit_remaining_exhausted(self, mock_settings, instagram_service):
        """Test rate limit shows 0 when exhausted."""
        mock_settings.INSTAGRAM_POSTS_PER_HOUR = 25
        instagram_service.history_repo.count_by_method.return_value = 25

        result = instagram_service.get_rate_limit_remaining()

        assert result == 0

    @patch("src.services.integrations.instagram_api.settings")
    def test_get_rate_limit_remaining_over_limit(
        self, mock_settings, instagram_service
    ):
        """Test rate limit doesn't go negative."""
        mock_settings.INSTAGRAM_POSTS_PER_HOUR = 25
        instagram_service.history_repo.count_by_method.return_value = 30

        result = instagram_service.get_rate_limit_remaining()

        assert result == 0

    def test_get_rate_limit_remaining_correct_time_window(self, instagram_service):
        """Test rate limit uses correct 1-hour time window."""
        instagram_service.history_repo.count_by_method.return_value = 0

        with patch("src.services.integrations.instagram_api.settings") as mock_settings:
            mock_settings.INSTAGRAM_POSTS_PER_HOUR = 25
            instagram_service.get_rate_limit_remaining()

        # Verify correct method and time window
        call_args = instagram_service.history_repo.count_by_method.call_args
        assert call_args[1]["method"] == "instagram_api"
        since = call_args[1]["since"]
        # Should be approximately 1 hour ago
        now = datetime.utcnow()
        assert (now - since).total_seconds() < 3610  # Within ~1 hour

    # ==================== get_rate_limit_status Tests ====================

    @patch("src.services.integrations.instagram_api.settings")
    def test_get_rate_limit_status(self, mock_settings, instagram_service):
        """Test rate limit status returns complete info."""
        mock_settings.INSTAGRAM_POSTS_PER_HOUR = 25
        instagram_service.history_repo.count_by_method.return_value = 10

        result = instagram_service.get_rate_limit_status()

        assert result["remaining"] == 15
        assert result["limit"] == 25
        assert result["used"] == 10
        assert result["window"] == "1 hour"

    # ==================== is_configured Tests ====================

    @patch("src.services.integrations.instagram_api.settings")
    def test_is_configured_all_settings(self, mock_settings, instagram_service):
        """Test is_configured returns True when all settings present."""
        mock_settings.ENABLE_INSTAGRAM_API = True
        mock_settings.INSTAGRAM_ACCOUNT_ID = "12345"
        mock_settings.FACEBOOK_APP_ID = "67890"

        assert instagram_service.is_configured() is True

    @patch("src.services.integrations.instagram_api.settings")
    def test_is_configured_missing_enable_flag(self, mock_settings, instagram_service):
        """Test is_configured returns False when feature disabled."""
        mock_settings.ENABLE_INSTAGRAM_API = False
        mock_settings.INSTAGRAM_ACCOUNT_ID = "12345"
        mock_settings.FACEBOOK_APP_ID = "67890"

        assert instagram_service.is_configured() is False

    @patch("src.services.integrations.instagram_api.settings")
    def test_is_configured_missing_account_id(self, mock_settings, instagram_service):
        """Test is_configured returns False when no active account and no legacy ID."""
        mock_settings.ENABLE_INSTAGRAM_API = True
        mock_settings.INSTAGRAM_ACCOUNT_ID = None
        mock_settings.FACEBOOK_APP_ID = "67890"
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = -100123

        # No multi-account active, no legacy account ID
        instagram_service.account_service.get_active_account.return_value = None

        assert instagram_service.is_configured() is False

    @patch("src.services.integrations.instagram_api.settings")
    def test_is_configured_missing_app_id(self, mock_settings, instagram_service):
        """Test is_configured returns False when app ID missing."""
        mock_settings.ENABLE_INSTAGRAM_API = True
        mock_settings.INSTAGRAM_ACCOUNT_ID = "12345"
        mock_settings.FACEBOOK_APP_ID = None

        assert instagram_service.is_configured() is False

    # ==================== _check_response_errors Tests ====================

    def test_check_response_errors_success(self, instagram_service):
        """Test no error raised for 200 response."""
        mock_response = Mock()
        mock_response.status_code = 200

        # Should not raise
        instagram_service._check_response_errors(mock_response)

    def test_check_response_errors_rate_limit_code_4(self, instagram_service):
        """Test RateLimitError for error code 4."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": {"code": 4, "message": "Rate limit exceeded"}
        }

        with pytest.raises(RateLimitError, match="Rate limit exceeded"):
            instagram_service._check_response_errors(mock_response)

    def test_check_response_errors_rate_limit_code_17(self, instagram_service):
        """Test RateLimitError for error code 17."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": {"code": 17, "message": "User request limit reached"}
        }

        with pytest.raises(RateLimitError):
            instagram_service._check_response_errors(mock_response)

    def test_check_response_errors_token_expired_code_190(self, instagram_service):
        """Test TokenExpiredError for error code 190."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            "error": {"code": 190, "message": "Invalid OAuth access token"}
        }

        with pytest.raises(TokenExpiredError):
            instagram_service._check_response_errors(mock_response)

    def test_check_response_errors_oauth_error_102(self, instagram_service):
        """Test TokenExpiredError for OAuth error code 102."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": {"code": 102, "message": "OAuth session expired"}
        }

        with pytest.raises(TokenExpiredError, match="OAuth error"):
            instagram_service._check_response_errors(mock_response)

    def test_check_response_errors_general_api_error(self, instagram_service):
        """Test InstagramAPIError for general errors."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.return_value = {
            "error": {"code": 1, "message": "Internal server error"}
        }

        with pytest.raises(InstagramAPIError, match="Internal server error"):
            instagram_service._check_response_errors(mock_response)

    def test_check_response_errors_invalid_json(self, instagram_service):
        """Test InstagramAPIError when response isn't JSON."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.json.side_effect = Exception("Not JSON")

        with pytest.raises(InstagramAPIError, match="HTTP 500"):
            instagram_service._check_response_errors(mock_response)

    # ==================== post_story Tests ====================

    @pytest.mark.asyncio
    @patch("src.services.integrations.instagram_api.settings")
    async def test_post_story_rate_limit_exhausted(
        self, mock_settings, instagram_service
    ):
        """Test post_story raises RateLimitError when exhausted."""
        mock_settings.INSTAGRAM_POSTS_PER_HOUR = 25
        instagram_service.history_repo.count_by_method.return_value = 25

        with pytest.raises(RateLimitError, match="Rate limit exhausted"):
            await instagram_service.post_story("https://example.com/image.jpg")

    @pytest.mark.asyncio
    @patch("src.services.integrations.instagram_api.settings")
    async def test_post_story_no_token(self, mock_settings, instagram_service):
        """Test post_story raises TokenExpiredError when no token."""
        mock_settings.INSTAGRAM_POSTS_PER_HOUR = 25
        instagram_service.history_repo.count_by_method.return_value = 0
        instagram_service.token_service.get_token.return_value = None

        with pytest.raises(TokenExpiredError, match="No valid Instagram token"):
            await instagram_service.post_story("https://example.com/image.jpg")

    @pytest.mark.asyncio
    @patch("src.services.integrations.instagram_api.settings")
    async def test_post_story_no_account_id(self, mock_settings, instagram_service):
        """Test post_story raises error when no account configured."""
        mock_settings.INSTAGRAM_POSTS_PER_HOUR = 25
        mock_settings.INSTAGRAM_ACCOUNT_ID = None
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = -100123
        instagram_service.history_repo.count_by_method.return_value = 0
        instagram_service.token_service.get_token.return_value = "valid_token"

        # No multi-account active, no legacy account ID → (None, None, None)
        instagram_service.account_service.get_active_account.return_value = None

        with pytest.raises(TokenExpiredError, match="No valid Instagram token"):
            await instagram_service.post_story("https://example.com/image.jpg")

    @pytest.mark.asyncio
    @patch("src.services.integrations.instagram_api.settings")
    async def test_post_story_success(self, mock_settings, instagram_service):
        """Test successful story posting."""
        mock_settings.INSTAGRAM_POSTS_PER_HOUR = 25
        mock_settings.INSTAGRAM_ACCOUNT_ID = "12345678"
        instagram_service.history_repo.count_by_method.return_value = 0
        instagram_service.token_service.get_token.return_value = "valid_token"

        # Mock container creation
        create_response = Mock()
        create_response.status_code = 200
        create_response.json.return_value = {"id": "container_123"}

        # Mock status polling
        status_response = Mock()
        status_response.status_code = 200
        status_response.json.return_value = {"status_code": "FINISHED"}

        # Mock publish
        publish_response = Mock()
        publish_response.status_code = 200
        publish_response.json.return_value = {"id": "story_456"}

        with patch(
            "src.services.integrations.instagram_api.httpx.AsyncClient"
        ) as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_instance.post = AsyncMock(
                side_effect=[create_response, publish_response]
            )
            mock_instance.get = AsyncMock(return_value=status_response)

            result = await instagram_service.post_story("https://example.com/image.jpg")

        assert result["success"] is True
        assert result["story_id"] == "story_456"
        assert result["container_id"] == "container_123"
        assert "timestamp" in result

    @pytest.mark.asyncio
    @patch("src.services.integrations.instagram_api.settings")
    async def test_post_story_network_error(self, mock_settings, instagram_service):
        """Test post_story handles network errors."""
        mock_settings.INSTAGRAM_POSTS_PER_HOUR = 25
        mock_settings.INSTAGRAM_ACCOUNT_ID = "12345678"
        instagram_service.history_repo.count_by_method.return_value = 0
        instagram_service.token_service.get_token.return_value = "valid_token"

        with patch(
            "src.services.integrations.instagram_api.httpx.AsyncClient"
        ) as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_instance.post = AsyncMock(
                side_effect=httpx.RequestError("Connection failed")
            )

            with pytest.raises(InstagramAPIError, match="Network error"):
                await instagram_service.post_story("https://example.com/image.jpg")

    # ==================== _create_media_container Tests ====================

    @pytest.mark.asyncio
    async def test_create_media_container_image(self, instagram_service):
        """Test container creation for image."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "container_123"}

        with patch(
            "src.services.integrations.instagram_api.httpx.AsyncClient"
        ) as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_instance.post = AsyncMock(return_value=mock_response)

            result = await instagram_service._create_media_container(
                token="token",
                account_id="12345",
                media_url="https://example.com/image.jpg",
                media_type="IMAGE",
            )

        assert result == "container_123"

        # Verify image_url was used
        call_kwargs = mock_instance.post.call_args[1]
        assert "image_url" in call_kwargs["data"]

    @pytest.mark.asyncio
    async def test_create_media_container_video(self, instagram_service):
        """Test container creation for video."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "container_456"}

        with patch(
            "src.services.integrations.instagram_api.httpx.AsyncClient"
        ) as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_instance.post = AsyncMock(return_value=mock_response)

            result = await instagram_service._create_media_container(
                token="token",
                account_id="12345",
                media_url="https://example.com/video.mp4",
                media_type="VIDEO",
            )

        assert result == "container_456"

        # Verify video_url was used
        call_kwargs = mock_instance.post.call_args[1]
        assert "video_url" in call_kwargs["data"]

    @pytest.mark.asyncio
    async def test_create_media_container_no_id_in_response(self, instagram_service):
        """Test error when no container ID in response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}  # No "id"

        with patch(
            "src.services.integrations.instagram_api.httpx.AsyncClient"
        ) as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_instance.post = AsyncMock(return_value=mock_response)

            with pytest.raises(InstagramAPIError, match="No container ID"):
                await instagram_service._create_media_container(
                    token="token",
                    account_id="12345",
                    media_url="https://example.com/image.jpg",
                    media_type="IMAGE",
                )

    # ==================== _wait_for_container_ready Tests ====================

    @pytest.mark.asyncio
    async def test_wait_for_container_ready_immediate(self, instagram_service):
        """Test container immediately ready."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status_code": "FINISHED"}

        with patch(
            "src.services.integrations.instagram_api.httpx.AsyncClient"
        ) as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_instance.get = AsyncMock(return_value=mock_response)

            # Should not raise
            await instagram_service._wait_for_container_ready("token", "container_123")

    @pytest.mark.asyncio
    async def test_wait_for_container_ready_error_status(self, instagram_service):
        """Test container fails with ERROR status."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status_code": "ERROR",
            "status": "Media processing failed",
        }

        with patch(
            "src.services.integrations.instagram_api.httpx.AsyncClient"
        ) as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_instance.get = AsyncMock(return_value=mock_response)

            with pytest.raises(InstagramAPIError, match="Media container failed"):
                await instagram_service._wait_for_container_ready(
                    "token", "container_123"
                )

    @pytest.mark.asyncio
    async def test_wait_for_container_ready_expired_status(self, instagram_service):
        """Test container fails with EXPIRED status."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status_code": "EXPIRED"}

        with patch(
            "src.services.integrations.instagram_api.httpx.AsyncClient"
        ) as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_instance.get = AsyncMock(return_value=mock_response)

            with pytest.raises(InstagramAPIError, match="expired before publishing"):
                await instagram_service._wait_for_container_ready(
                    "token", "container_123"
                )

    @pytest.mark.asyncio
    @patch(
        "src.services.integrations.instagram_api.asyncio.sleep", new_callable=AsyncMock
    )
    async def test_wait_for_container_ready_timeout(
        self, mock_sleep, instagram_service
    ):
        """Test container polling times out."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status_code": "IN_PROGRESS"}

        with patch(
            "src.services.integrations.instagram_api.httpx.AsyncClient"
        ) as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_instance.get = AsyncMock(return_value=mock_response)

            with pytest.raises(InstagramAPIError, match="did not finish"):
                await instagram_service._wait_for_container_ready(
                    "token", "container_123"
                )

        # Verify it polled the maximum number of times
        assert (
            mock_instance.get.await_count
            == instagram_service.CONTAINER_STATUS_MAX_POLLS
        )

    # ==================== _publish_container Tests ====================

    @pytest.mark.asyncio
    async def test_publish_container_success(self, instagram_service):
        """Test successful container publishing."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "story_789"}

        with patch(
            "src.services.integrations.instagram_api.httpx.AsyncClient"
        ) as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_instance.post = AsyncMock(return_value=mock_response)

            result = await instagram_service._publish_container(
                token="token",
                account_id="12345",
                container_id="container_123",
            )

        assert result == "story_789"

    @pytest.mark.asyncio
    async def test_publish_container_no_story_id(self, instagram_service):
        """Test error when no story ID in response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}  # No "id"

        with patch(
            "src.services.integrations.instagram_api.httpx.AsyncClient"
        ) as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_instance.post = AsyncMock(return_value=mock_response)

            with pytest.raises(InstagramAPIError, match="No story ID"):
                await instagram_service._publish_container(
                    token="token",
                    account_id="12345",
                    container_id="container_123",
                )

    # ==================== validate_media_url Tests ====================

    @pytest.mark.asyncio
    async def test_validate_media_url_success(self, instagram_service):
        """Test successful URL validation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {
            "content-type": "image/jpeg",
            "content-length": "123456",
        }

        with patch(
            "src.services.integrations.instagram_api.httpx.AsyncClient"
        ) as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_instance.head = AsyncMock(return_value=mock_response)

            result = await instagram_service.validate_media_url(
                "https://example.com/image.jpg"
            )

        assert result["valid"] is True
        assert result["content_type"] == "image/jpeg"
        assert result["size_bytes"] == 123456

    @pytest.mark.asyncio
    async def test_validate_media_url_not_found(self, instagram_service):
        """Test URL validation for 404."""
        mock_response = Mock()
        mock_response.status_code = 404

        with patch(
            "src.services.integrations.instagram_api.httpx.AsyncClient"
        ) as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_instance.head = AsyncMock(return_value=mock_response)

            result = await instagram_service.validate_media_url(
                "https://example.com/missing.jpg"
            )

        assert result["valid"] is False
        assert "404" in result["error"]

    @pytest.mark.asyncio
    async def test_validate_media_url_network_error(self, instagram_service):
        """Test URL validation handles network errors."""
        with patch(
            "src.services.integrations.instagram_api.httpx.AsyncClient"
        ) as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_instance.head = AsyncMock(side_effect=httpx.RequestError("DNS error"))

            result = await instagram_service.validate_media_url(
                "https://example.com/image.jpg"
            )

        assert result["valid"] is False
        assert "DNS error" in result["error"]

    @pytest.mark.asyncio
    async def test_validate_media_url_no_content_length(self, instagram_service):
        """Test URL validation when no content-length header."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "image/png"}

        with patch(
            "src.services.integrations.instagram_api.httpx.AsyncClient"
        ) as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_instance.head = AsyncMock(return_value=mock_response)

            result = await instagram_service.validate_media_url(
                "https://example.com/image.png"
            )

        assert result["valid"] is True
        assert result["size_bytes"] is None
