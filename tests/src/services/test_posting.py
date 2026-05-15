"""Tests for PostingService.

PostingService is now only responsible for the Google Drive disconnect
alert. The alert is gated on chat_settings.gdrive_alerted_at — fires once
per disconnect event and stays silent until the OAuth reconnect callback
clears the flag.
"""

from datetime import datetime, timezone

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


def _chat_settings(alerted_at=None):
    """Build a mock ChatSettings with the given gdrive_alerted_at."""
    cs = Mock()
    cs.gdrive_alerted_at = alerted_at
    return cs


@pytest.mark.unit
class TestSendGdriveAuthAlert:
    """send_gdrive_auth_alert behaves as a state-transition notification."""

    @pytest.mark.asyncio
    @patch("src.services.core.posting.settings")
    async def test_sends_and_persists_timestamp_when_flag_null(
        self, mock_settings, posting_service
    ):
        """First auth error in a disconnect event sends the alert and persists."""
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = -100123
        mock_settings.OAUTH_REDIRECT_BASE_URL = "https://example.com"
        posting_service.telegram_service.bot_token = "test-token"
        posting_service.settings_service.get_settings_if_exists.return_value = (
            _chat_settings(alerted_at=None)
        )

        mock_bot_instance = AsyncMock()
        with patch("telegram.Bot", return_value=mock_bot_instance):
            await posting_service.send_gdrive_auth_alert(-100123)

        mock_bot_instance.send_message.assert_called_once()
        call_kwargs = mock_bot_instance.send_message.call_args.kwargs
        assert "Disconnected" in call_kwargs["text"]
        assert call_kwargs["reply_markup"] is not None

        posting_service.settings_service.set_gdrive_alerted_at.assert_called_once()
        args, _ = posting_service.settings_service.set_gdrive_alerted_at.call_args
        assert args[0] == -100123
        assert isinstance(args[1], datetime)

    @pytest.mark.asyncio
    @patch("src.services.core.posting.settings")
    async def test_skips_send_when_flag_already_set(
        self, mock_settings, posting_service
    ):
        """Second auth error within the same disconnect event is suppressed."""
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = -100123
        mock_settings.OAUTH_REDIRECT_BASE_URL = "https://example.com"
        posting_service.telegram_service.bot_token = "test-token"
        posting_service.settings_service.get_settings_if_exists.return_value = (
            _chat_settings(alerted_at=datetime(2026, 5, 14, tzinfo=timezone.utc))
        )

        with patch("telegram.Bot") as MockBot:
            await posting_service.send_gdrive_auth_alert(-100123)

        MockBot.assert_not_called()
        posting_service.settings_service.set_gdrive_alerted_at.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.services.core.posting.settings")
    async def test_skips_send_when_no_chat_settings(
        self, mock_settings, posting_service
    ):
        """Unknown chat (no chat_settings row) is silently skipped."""
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = -100123
        mock_settings.OAUTH_REDIRECT_BASE_URL = "https://example.com"
        posting_service.telegram_service.bot_token = "test-token"
        posting_service.settings_service.get_settings_if_exists.return_value = None

        with patch("telegram.Bot") as MockBot:
            await posting_service.send_gdrive_auth_alert(-100123)

        MockBot.assert_not_called()
        posting_service.settings_service.set_gdrive_alerted_at.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.services.core.posting.settings")
    async def test_falls_back_to_admin_chat_id(self, mock_settings, posting_service):
        """Uses ADMIN_TELEGRAM_CHAT_ID when no chat_id provided."""
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = -100999
        mock_settings.OAUTH_REDIRECT_BASE_URL = "https://example.com"
        posting_service.telegram_service.bot_token = "test-token"
        posting_service.settings_service.get_settings_if_exists.return_value = (
            _chat_settings(alerted_at=None)
        )

        mock_bot_instance = AsyncMock()
        with patch("telegram.Bot", return_value=mock_bot_instance):
            await posting_service.send_gdrive_auth_alert()

        call_kwargs = mock_bot_instance.send_message.call_args.kwargs
        assert call_kwargs["chat_id"] == -100999
        posting_service.settings_service.get_settings_if_exists.assert_called_once_with(
            -100999
        )

    @pytest.mark.asyncio
    @patch("src.services.core.posting.settings")
    async def test_no_reconnect_button_without_oauth_url(
        self, mock_settings, posting_service
    ):
        """No reconnect button when OAUTH_REDIRECT_BASE_URL is not set."""
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = -100123
        mock_settings.OAUTH_REDIRECT_BASE_URL = None
        posting_service.telegram_service.bot_token = "test-token"
        posting_service.settings_service.get_settings_if_exists.return_value = (
            _chat_settings(alerted_at=None)
        )

        mock_bot_instance = AsyncMock()
        with patch("telegram.Bot", return_value=mock_bot_instance):
            await posting_service.send_gdrive_auth_alert(-100123)

        call_kwargs = mock_bot_instance.send_message.call_args.kwargs
        assert call_kwargs["reply_markup"] is None

    @pytest.mark.asyncio
    @patch("src.services.core.posting.settings")
    async def test_no_chat_id_at_all_returns_early(
        self, mock_settings, posting_service
    ):
        """Returns without sending when no chat_id and no admin default."""
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = None
        posting_service.telegram_service.bot_token = "test-token"

        with patch("telegram.Bot") as MockBot:
            await posting_service.send_gdrive_auth_alert()

        MockBot.assert_not_called()
        posting_service.settings_service.get_settings_if_exists.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.services.core.posting.settings")
    async def test_send_failure_does_not_persist_flag(
        self, mock_settings, posting_service
    ):
        """If the Telegram send fails, the flag is NOT set — allow retry next tick."""
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = -100123
        mock_settings.OAUTH_REDIRECT_BASE_URL = "https://example.com"
        posting_service.telegram_service.bot_token = "test-token"
        posting_service.settings_service.get_settings_if_exists.return_value = (
            _chat_settings(alerted_at=None)
        )

        mock_bot_instance = AsyncMock()
        mock_bot_instance.send_message.side_effect = RuntimeError("Network error")
        with patch("telegram.Bot", return_value=mock_bot_instance):
            await posting_service.send_gdrive_auth_alert(-100123)

        posting_service.settings_service.set_gdrive_alerted_at.assert_not_called()
