"""Tests for /status command — DM vs group routing."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.services.core.telegram_commands import TelegramCommandHandlers


@pytest.fixture
def mock_service():
    """Minimal TelegramService mock for command tests."""
    service = Mock()
    service._get_or_create_user = Mock(return_value=Mock(id="user-1"))
    service.interaction_service = Mock()
    service.settings_service = Mock()
    service.history_repo = Mock()
    service.media_repo = Mock()
    return service


@pytest.fixture
def handlers(mock_service):
    return TelegramCommandHandlers(mock_service)


def _make_update(chat_type="private", chat_id=12345, user_id=67890, message_id=1):
    update = AsyncMock()
    update.effective_chat = Mock()
    update.effective_chat.id = chat_id
    update.effective_chat.type = chat_type
    update.effective_user = Mock()
    update.effective_user.id = user_id
    update.message = AsyncMock()
    update.message.message_id = message_id
    update.message.reply_text = AsyncMock()
    return update


# ──────────────────────────────────────────────────────────────
# /status routing
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
class TestStatusRouting:
    async def test_dm_routes_to_dm_handler(self, handlers):
        """DM /status → _handle_dm_status."""
        update = _make_update(chat_type="private")
        context = Mock()

        with patch.object(
            handlers, "_handle_dm_status", new_callable=AsyncMock
        ) as mock_dm:
            await handlers.handle_status(update, context)

        mock_dm.assert_called_once()

    async def test_group_routes_to_group_handler(self, handlers):
        """Group /status → _handle_group_status."""
        update = _make_update(chat_type="group")
        context = Mock()

        with patch.object(
            handlers, "_handle_group_status", new_callable=AsyncMock
        ) as mock_group:
            await handlers.handle_status(update, context)

        mock_group.assert_called_once()


# ──────────────────────────────────────────────────────────────
# /status DM — multi-instance view
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
class TestDmStatus:
    async def test_shows_instance_list(self, handlers):
        """DM /status shows user's instances with manage buttons."""
        mock_dash = Mock()
        mock_dash.get_user_instances.return_value = {
            "instances": [
                {
                    "display_name": "My Brand",
                    "telegram_chat_id": -100123,
                    "media_count": 42,
                    "posts_per_day": 5,
                    "is_paused": False,
                    "last_post_at": None,
                    "chat_settings_id": "cs-1",
                },
            ],
        }
        mock_dash.__enter__ = Mock(return_value=mock_dash)
        mock_dash.__exit__ = Mock(return_value=False)

        update = _make_update(chat_type="private")
        user = Mock(id="user-1")

        with patch(
            "src.services.core.telegram_commands.DashboardService",
            return_value=mock_dash,
        ):
            await handlers._handle_dm_status(update, user)

        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]
        assert "My Brand" in text
        assert "5/day" in text
        assert "42 media" in text
        assert update.message.reply_text.call_args[1]["parse_mode"] == "MarkdownV2"

        # Should have manage button + new instance button
        reply_markup = update.message.reply_text.call_args[1]["reply_markup"]
        assert reply_markup is not None

    async def test_no_instances_shows_new_button(self, handlers):
        """DM /status with no instances shows '+ New Instance' button."""
        mock_dash = Mock()
        mock_dash.get_user_instances.return_value = {"instances": []}
        mock_dash.__enter__ = Mock(return_value=mock_dash)
        mock_dash.__exit__ = Mock(return_value=False)

        update = _make_update(chat_type="private")
        user = Mock(id="user-1")

        with patch(
            "src.services.core.telegram_commands.DashboardService",
            return_value=mock_dash,
        ):
            await handlers._handle_dm_status(update, user)

        text = update.message.reply_text.call_args[0][0]
        assert "No instances configured" in text

    async def test_logs_interaction(self, handlers):
        """DM /status logs the interaction."""
        mock_dash = Mock()
        mock_dash.get_user_instances.return_value = {"instances": []}
        mock_dash.__enter__ = Mock(return_value=mock_dash)
        mock_dash.__exit__ = Mock(return_value=False)

        update = _make_update(chat_type="private")
        user = Mock(id="user-1")

        with patch(
            "src.services.core.telegram_commands.DashboardService",
            return_value=mock_dash,
        ):
            await handlers._handle_dm_status(update, user)

        handlers.service.interaction_service.log_command.assert_called_once()
        call_kwargs = handlers.service.interaction_service.log_command.call_args[1]
        assert call_kwargs["command"] == "/status"
        assert call_kwargs["context"]["view"] == "dm"
