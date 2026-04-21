"""Tests for TelegramLifecycleHandler — startup/shutdown notifications."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.services.core.telegram_lifecycle import TelegramLifecycleHandler
from src.services.core.telegram_utils import format_last_post


@pytest.fixture
def mock_service():
    """Minimal TelegramService mock for lifecycle tests."""
    service = Mock()
    service.admin_chat_id = 12345
    service.bot = AsyncMock()
    return service


@pytest.fixture
def handler(mock_service):
    return TelegramLifecycleHandler(mock_service)


# ──────────────────────────────────────────────────────────────
# send_startup_notification — multi-instance view
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
class TestSendStartupNotification:
    @patch("src.services.core.telegram_lifecycle.settings")
    async def test_skips_when_notifications_disabled(self, mock_settings, handler):
        mock_settings.SEND_LIFECYCLE_NOTIFICATIONS = False
        await handler.send_startup_notification()
        handler.service.bot.send_message.assert_not_called()

    @patch("src.services.core.telegram_lifecycle.settings")
    async def test_shows_instance_list(self, mock_settings, handler):
        mock_settings.SEND_LIFECYCLE_NOTIFICATIONS = True

        mock_dash = Mock()
        mock_dash.get_user_instances.return_value = {
            "instances": [
                {
                    "display_name": "TL Enterprises",
                    "telegram_chat_id": -100123,
                    "media_count": 50,
                    "posts_per_day": 3,
                    "is_paused": False,
                    "last_post_at": None,
                    "chat_settings_id": "cs-1",
                },
            ],
        }
        mock_dash.__enter__ = Mock(return_value=mock_dash)
        mock_dash.__exit__ = Mock(return_value=False)

        with patch(
            "src.services.core.telegram_lifecycle.DashboardService",
            return_value=mock_dash,
        ):
            await handler.send_startup_notification()

        handler.service.bot.send_message.assert_called_once()
        text = handler.service.bot.send_message.call_args[1]["text"]
        assert "TL Enterprises" in text
        assert "3/day" in text
        assert "50 media" in text
        assert "Started" in text

    @patch("src.services.core.telegram_lifecycle.settings")
    async def test_no_instances(self, mock_settings, handler):
        mock_settings.SEND_LIFECYCLE_NOTIFICATIONS = True

        mock_dash = Mock()
        mock_dash.get_user_instances.return_value = {"instances": []}
        mock_dash.__enter__ = Mock(return_value=mock_dash)
        mock_dash.__exit__ = Mock(return_value=False)

        with patch(
            "src.services.core.telegram_lifecycle.DashboardService",
            return_value=mock_dash,
        ):
            await handler.send_startup_notification()

        text = handler.service.bot.send_message.call_args[1]["text"]
        assert "No instances configured" in text

    @patch("src.services.core.telegram_lifecycle.settings")
    async def test_multiple_instances(self, mock_settings, handler):
        mock_settings.SEND_LIFECYCLE_NOTIFICATIONS = True

        mock_dash = Mock()
        mock_dash.get_user_instances.return_value = {
            "instances": [
                {
                    "display_name": "Brand A",
                    "telegram_chat_id": -100,
                    "media_count": 10,
                    "posts_per_day": 2,
                    "is_paused": False,
                    "last_post_at": "2026-04-20T12:00:00+00:00",
                    "chat_settings_id": "cs-1",
                },
                {
                    "display_name": "Brand B",
                    "telegram_chat_id": -200,
                    "media_count": 5,
                    "posts_per_day": 1,
                    "is_paused": True,
                    "last_post_at": None,
                    "chat_settings_id": "cs-2",
                },
            ],
        }
        mock_dash.__enter__ = Mock(return_value=mock_dash)
        mock_dash.__exit__ = Mock(return_value=False)

        with patch(
            "src.services.core.telegram_lifecycle.DashboardService",
            return_value=mock_dash,
        ):
            await handler.send_startup_notification()

        text = handler.service.bot.send_message.call_args[1]["text"]
        assert "Brand A" in text
        assert "Brand B" in text
        assert "paused" in text


# ──────────────────────────────────────────────────────────────
# format_last_post
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestFormatLastPost:
    def test_none_returns_never(self):
        assert format_last_post(None) == "never"

    def test_recent_post(self):
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        result = format_last_post(now.isoformat())
        assert result == "< 1h ago"

    def test_old_post_shows_days(self):
        from datetime import datetime, timedelta, timezone

        old = datetime.now(timezone.utc) - timedelta(days=3)
        result = format_last_post(old.isoformat())
        assert result == "3d ago"
