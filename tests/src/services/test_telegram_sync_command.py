"""Tests for /sync command handler."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from uuid import uuid4

from src.services.core.telegram_service import TelegramService
from src.services.core.telegram_commands import TelegramCommandHandlers


@pytest.fixture
def mock_command_handlers():
    """Create TelegramCommandHandlers with mocked service dependencies."""
    with (
        patch("src.services.core.telegram_service.settings") as mock_settings,
        patch(
            "src.services.core.telegram_service.UserRepository"
        ) as mock_user_repo_class,
        patch(
            "src.services.core.telegram_service.QueueRepository"
        ) as mock_queue_repo_class,
        patch(
            "src.services.core.telegram_service.MediaRepository"
        ) as mock_media_repo_class,
        patch(
            "src.services.core.telegram_service.HistoryRepository"
        ) as mock_history_repo_class,
        patch(
            "src.services.core.telegram_service.LockRepository"
        ) as mock_lock_repo_class,
        patch(
            "src.services.core.telegram_service.MediaLockService"
        ) as mock_lock_service_class,
        patch(
            "src.services.core.telegram_service.InteractionService"
        ) as mock_interaction_service_class,
        patch(
            "src.services.core.telegram_service.SettingsService"
        ) as mock_settings_service_class,
        patch(
            "src.services.core.telegram_service.InstagramAccountService"
        ) as mock_ig_account_service_class,
    ):
        mock_settings.TELEGRAM_BOT_TOKEN = "123456:ABC-DEF1234ghIkl"
        mock_settings.TELEGRAM_CHANNEL_ID = -1001234567890
        mock_settings.CAPTION_STYLE = "enhanced"
        mock_settings.SEND_LIFECYCLE_NOTIFICATIONS = False

        service = TelegramService()

        service.user_repo = mock_user_repo_class.return_value
        service.queue_repo = mock_queue_repo_class.return_value
        service.media_repo = mock_media_repo_class.return_value
        service.history_repo = mock_history_repo_class.return_value
        service.lock_repo = mock_lock_repo_class.return_value
        service.lock_service = mock_lock_service_class.return_value
        service.interaction_service = mock_interaction_service_class.return_value
        service.settings_service = mock_settings_service_class.return_value
        service.ig_account_service = mock_ig_account_service_class.return_value

        handlers = TelegramCommandHandlers(service)

        # Setup mock user
        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "admin"
        mock_user.telegram_first_name = "Admin"
        service.user_repo.get_by_telegram_id.return_value = mock_user

        yield handlers


def _make_update(chat_id=-100123):
    """Create a mock Telegram Update object."""
    mock_update = Mock()
    mock_update.effective_user = Mock(
        id=123456, username="admin", first_name="Admin", last_name=None
    )
    mock_update.effective_chat = Mock(id=chat_id)
    mock_update.message = AsyncMock()
    mock_update.message.message_id = 1
    mock_update.message.reply_text = AsyncMock()
    return mock_update


@pytest.mark.unit
@pytest.mark.asyncio
class TestSyncCommand:
    """Tests for /sync command handler."""

    async def test_sync_not_configured(self, mock_command_handlers):
        """/sync when no source root is set shows 'Not Configured' message."""
        mock_update = _make_update()
        mock_context = Mock()

        with patch("src.services.core.telegram_commands.settings") as mock_app_settings:
            mock_app_settings.MEDIA_SOURCE_TYPE = "google_drive"
            mock_app_settings.MEDIA_SOURCE_ROOT = ""
            mock_app_settings.MEDIA_DIR = ""

            await mock_command_handlers.handle_sync(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_text = mock_update.message.reply_text.call_args.args[0]
        assert "Not Configured" in call_text

    async def test_sync_success(self, mock_command_handlers):
        """Successful sync returns result counts in edited message."""
        mock_update = _make_update()
        mock_context = Mock()

        # reply_text returns a message object with edit_text
        mock_status_msg = AsyncMock()
        mock_update.message.reply_text.return_value = mock_status_msg

        mock_result = Mock()
        mock_result.new = 5
        mock_result.updated = 2
        mock_result.deactivated = 1
        mock_result.reactivated = 0
        mock_result.unchanged = 10
        mock_result.errors = 0
        mock_result.total_processed = 18
        mock_result.to_dict.return_value = {
            "new": 5,
            "updated": 2,
            "deactivated": 1,
            "reactivated": 0,
            "unchanged": 10,
            "errors": 0,
        }

        with (
            patch("src.services.core.telegram_commands.settings") as mock_app_settings,
            patch("src.services.core.media_sync.MediaSyncService") as mock_sync_class,
        ):
            mock_app_settings.MEDIA_SOURCE_TYPE = "local"
            mock_app_settings.MEDIA_SOURCE_ROOT = "/media/stories"
            mock_app_settings.MEDIA_DIR = "/media/stories"
            mock_sync_class.return_value.sync.return_value = mock_result

            await mock_command_handlers.handle_sync(mock_update, mock_context)

        # Should have edited the status message with results
        mock_status_msg.edit_text.assert_called_once()
        call_text = mock_status_msg.edit_text.call_args.args[0]
        assert "Sync Complete" in call_text
        assert "New: 5" in call_text
        assert "Total: 18" in call_text

    async def test_sync_with_errors(self, mock_command_handlers):
        """Sync with errors shows error count."""
        mock_update = _make_update()
        mock_context = Mock()
        mock_status_msg = AsyncMock()
        mock_update.message.reply_text.return_value = mock_status_msg

        mock_result = Mock()
        mock_result.new = 3
        mock_result.updated = 0
        mock_result.deactivated = 0
        mock_result.reactivated = 0
        mock_result.unchanged = 7
        mock_result.errors = 2
        mock_result.total_processed = 12
        mock_result.to_dict.return_value = {"new": 3, "errors": 2}

        with (
            patch("src.services.core.telegram_commands.settings") as mock_app_settings,
            patch("src.services.core.media_sync.MediaSyncService") as mock_sync_class,
        ):
            mock_app_settings.MEDIA_SOURCE_TYPE = "local"
            mock_app_settings.MEDIA_SOURCE_ROOT = "/media/stories"
            mock_app_settings.MEDIA_DIR = "/media/stories"
            mock_sync_class.return_value.sync.return_value = mock_result

            await mock_command_handlers.handle_sync(mock_update, mock_context)

        call_text = mock_status_msg.edit_text.call_args.args[0]
        assert "Errors: 2" in call_text

    async def test_sync_exception(self, mock_command_handlers):
        """MediaSyncService.sync() raises ValueError shows 'Sync Failed'."""
        mock_update = _make_update()
        mock_context = Mock()
        mock_status_msg = AsyncMock()
        mock_update.message.reply_text.return_value = mock_status_msg

        with (
            patch("src.services.core.telegram_commands.settings") as mock_app_settings,
            patch("src.services.core.media_sync.MediaSyncService") as mock_sync_class,
        ):
            mock_app_settings.MEDIA_SOURCE_TYPE = "google_drive"
            mock_app_settings.MEDIA_SOURCE_ROOT = "folder123"
            mock_app_settings.MEDIA_DIR = ""
            mock_sync_class.return_value.sync.side_effect = ValueError(
                "Provider not configured"
            )

            await mock_command_handlers.handle_sync(mock_update, mock_context)

        call_text = mock_status_msg.edit_text.call_args.args[0]
        assert "Sync Failed" in call_text

    async def test_sync_local_fallback_to_media_dir(self, mock_command_handlers):
        """When source_root empty and source_type='local', uses MEDIA_DIR."""
        mock_update = _make_update()
        mock_context = Mock()
        mock_status_msg = AsyncMock()
        mock_update.message.reply_text.return_value = mock_status_msg

        mock_result = Mock()
        mock_result.new = 0
        mock_result.updated = 0
        mock_result.deactivated = 0
        mock_result.reactivated = 0
        mock_result.unchanged = 5
        mock_result.errors = 0
        mock_result.total_processed = 5
        mock_result.to_dict.return_value = {"new": 0, "errors": 0}

        with (
            patch("src.services.core.telegram_commands.settings") as mock_app_settings,
            patch("src.services.core.media_sync.MediaSyncService") as mock_sync_class,
        ):
            mock_app_settings.MEDIA_SOURCE_TYPE = "local"
            mock_app_settings.MEDIA_SOURCE_ROOT = ""  # Empty
            mock_app_settings.MEDIA_DIR = "/fallback/media"
            mock_sync_class.return_value.sync.return_value = mock_result

            await mock_command_handlers.handle_sync(mock_update, mock_context)

        # Should have been called with the fallback path
        sync_call = mock_sync_class.return_value.sync.call_args
        assert sync_call.kwargs["source_root"] == "/fallback/media"

    async def test_sync_logs_interaction(self, mock_command_handlers):
        """Verifies interaction_service.log_command called with /sync."""
        mock_update = _make_update()
        mock_context = Mock()
        mock_status_msg = AsyncMock()
        mock_update.message.reply_text.return_value = mock_status_msg

        mock_result = Mock()
        mock_result.new = 1
        mock_result.updated = 0
        mock_result.deactivated = 0
        mock_result.reactivated = 0
        mock_result.unchanged = 0
        mock_result.errors = 0
        mock_result.total_processed = 1
        mock_result.to_dict.return_value = {"new": 1, "errors": 0}

        with (
            patch("src.services.core.telegram_commands.settings") as mock_app_settings,
            patch("src.services.core.media_sync.MediaSyncService") as mock_sync_class,
        ):
            mock_app_settings.MEDIA_SOURCE_TYPE = "local"
            mock_app_settings.MEDIA_SOURCE_ROOT = "/media"
            mock_app_settings.MEDIA_DIR = "/media"
            mock_sync_class.return_value.sync.return_value = mock_result

            await mock_command_handlers.handle_sync(mock_update, mock_context)

        # Verify log_command was called
        log_calls = (
            mock_command_handlers.service.interaction_service.log_command.call_args_list
        )
        sync_calls = [c for c in log_calls if c.kwargs.get("command") == "/sync"]
        assert len(sync_calls) == 1
