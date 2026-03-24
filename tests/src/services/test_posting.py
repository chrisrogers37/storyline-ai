"""Tests for PostingService (JIT model).

PostingService has been simplified to only handle Google Drive auth alerts.
The main scheduling and sending logic now lives in SchedulerService.
"""

import time

import pytest
from unittest.mock import AsyncMock, Mock, patch

from src.services.core.posting import PostingService


@pytest.fixture
def posting_service():
    """Create PostingService with mocked dependencies."""
    with patch.object(PostingService, "__init__", lambda self: None):
        service = PostingService()
        service.telegram_service = Mock()
        service.settings_service = Mock()
        service.service_run_repo = Mock()
        service.service_name = "PostingService"
        return service


@pytest.mark.unit
class TestSendGdriveAuthAlert:
    """Tests for PostingService.send_gdrive_auth_alert()."""

    @pytest.mark.asyncio
    @patch("src.services.core.posting.settings")
    async def test_rate_limited_skips_send(self, mock_settings, posting_service):
        """send_gdrive_auth_alert is rate-limited to once per hour."""
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = -100123
        mock_settings.OAUTH_REDIRECT_BASE_URL = "https://example.com"
        posting_service.telegram_service.bot_token = "test-token"

        # Set last alert time to now (simulate recent alert)
        PostingService._last_gdrive_alert_time = time.monotonic()

        with patch("telegram.Bot") as MockBot:
            await posting_service.send_gdrive_auth_alert(-100123)

        # Should NOT have sent because rate-limited
        MockBot.assert_not_called()

        # Reset for other tests
        PostingService._last_gdrive_alert_time = 0.0

    @pytest.mark.asyncio
    @patch("src.services.core.posting.settings")
    async def test_sends_when_not_rate_limited(self, mock_settings, posting_service):
        """send_gdrive_auth_alert sends when not recently sent."""
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = -100123
        mock_settings.OAUTH_REDIRECT_BASE_URL = "https://example.com"
        posting_service.telegram_service.bot_token = "test-token"

        # Ensure not rate-limited
        PostingService._last_gdrive_alert_time = 0.0

        mock_bot_instance = AsyncMock()
        with patch("telegram.Bot", return_value=mock_bot_instance):
            await posting_service.send_gdrive_auth_alert(-100123)

        mock_bot_instance.send_message.assert_called_once()
        call_kwargs = mock_bot_instance.send_message.call_args.kwargs
        assert "Disconnected" in call_kwargs["text"]
        assert call_kwargs["reply_markup"] is not None

        # Reset for other tests
        PostingService._last_gdrive_alert_time = 0.0

    @pytest.mark.asyncio
    @patch("src.services.core.posting.settings")
    async def test_falls_back_to_admin_chat_id(self, mock_settings, posting_service):
        """Uses ADMIN_TELEGRAM_CHAT_ID when no chat_id provided."""
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = -100999
        mock_settings.OAUTH_REDIRECT_BASE_URL = "https://example.com"
        posting_service.telegram_service.bot_token = "test-token"

        PostingService._last_gdrive_alert_time = 0.0

        mock_bot_instance = AsyncMock()
        with patch("telegram.Bot", return_value=mock_bot_instance):
            await posting_service.send_gdrive_auth_alert()

        call_kwargs = mock_bot_instance.send_message.call_args.kwargs
        assert call_kwargs["chat_id"] == -100999

        PostingService._last_gdrive_alert_time = 0.0

    @pytest.mark.asyncio
    @patch("src.services.core.posting.settings")
    async def test_no_reconnect_button_without_oauth_url(
        self, mock_settings, posting_service
    ):
        """No reconnect button when OAUTH_REDIRECT_BASE_URL is not set."""
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = -100123
        mock_settings.OAUTH_REDIRECT_BASE_URL = None
        posting_service.telegram_service.bot_token = "test-token"

        PostingService._last_gdrive_alert_time = 0.0

        mock_bot_instance = AsyncMock()
        with patch("telegram.Bot", return_value=mock_bot_instance):
            await posting_service.send_gdrive_auth_alert(-100123)

        call_kwargs = mock_bot_instance.send_message.call_args.kwargs
        assert call_kwargs["reply_markup"] is None

        PostingService._last_gdrive_alert_time = 0.0

    @pytest.mark.asyncio
    @patch("src.services.core.posting.settings")
    async def test_no_chat_id_at_all_returns_early(
        self, mock_settings, posting_service
    ):
        """Returns without sending when no chat_id and no admin default."""
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = None
        posting_service.telegram_service.bot_token = "test-token"

        PostingService._last_gdrive_alert_time = 0.0

        with patch("telegram.Bot") as MockBot:
            await posting_service.send_gdrive_auth_alert()

        MockBot.assert_not_called()

        PostingService._last_gdrive_alert_time = 0.0

    @pytest.mark.asyncio
    @patch("src.services.core.posting.settings")
    async def test_send_failure_caught(self, mock_settings, posting_service):
        """Exceptions during send are caught (not re-raised)."""
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = -100123
        mock_settings.OAUTH_REDIRECT_BASE_URL = "https://example.com"
        posting_service.telegram_service.bot_token = "test-token"

        PostingService._last_gdrive_alert_time = 0.0

        mock_bot_instance = AsyncMock()
        mock_bot_instance.send_message.side_effect = RuntimeError("Network error")
        with patch("telegram.Bot", return_value=mock_bot_instance):
            # Should not raise
            await posting_service.send_gdrive_auth_alert(-100123)

        PostingService._last_gdrive_alert_time = 0.0
