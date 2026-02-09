"""Tests for TelegramSettingsHandlers."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from uuid import uuid4

from src.services.core.telegram_service import TelegramService
from src.services.core.telegram_settings import TelegramSettingsHandlers


@pytest.fixture
def mock_settings_handlers():
    """Create TelegramSettingsHandlers with mocked service dependencies."""
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

        # Make repos accessible for test assertions
        service.user_repo = mock_user_repo_class.return_value
        service.queue_repo = mock_queue_repo_class.return_value
        service.media_repo = mock_media_repo_class.return_value
        service.history_repo = mock_history_repo_class.return_value
        service.lock_repo = mock_lock_repo_class.return_value
        service.lock_service = mock_lock_service_class.return_value
        service.interaction_service = mock_interaction_service_class.return_value
        service.settings_service = mock_settings_service_class.return_value
        service.ig_account_service = mock_ig_account_service_class.return_value

        handlers = TelegramSettingsHandlers(service)
        service.settings_handler = handlers

        yield handlers


@pytest.mark.unit
class TestBuildSettingsKeyboard:
    """Tests for build_settings_message_and_keyboard helper."""

    def test_returns_message_and_markup(self, mock_settings_handlers):
        """Test helper returns (message, InlineKeyboardMarkup) tuple."""
        mock_settings_handlers.service.settings_service.get_settings_display.return_value = {
            "dry_run_mode": False,
            "enable_instagram_api": True,
            "is_paused": False,
            "posts_per_day": 3,
            "posting_hours_start": 9,
            "posting_hours_end": 21,
            "show_verbose_notifications": True,
        }
        mock_settings_handlers.service.ig_account_service.get_accounts_for_display.return_value = {
            "active_account_id": "some-id",
            "active_account_name": "Test Account",
        }

        message, markup = mock_settings_handlers.build_settings_message_and_keyboard(
            -100123
        )

        assert "Bot Settings" in message
        assert markup is not None

    def test_verbose_toggle_button_shows_state(self, mock_settings_handlers):
        """Test that verbose button shows correct ON/OFF state."""
        mock_settings_handlers.service.settings_service.get_settings_display.return_value = {
            "dry_run_mode": False,
            "enable_instagram_api": False,
            "is_paused": False,
            "posts_per_day": 3,
            "posting_hours_start": 9,
            "posting_hours_end": 21,
            "show_verbose_notifications": False,
        }
        mock_settings_handlers.service.ig_account_service.get_accounts_for_display.return_value = {
            "active_account_id": None,
            "active_account_name": "Not selected",
        }

        _, markup = mock_settings_handlers.build_settings_message_and_keyboard(-100123)

        # Find verbose button in keyboard
        all_buttons = [btn for row in markup.inline_keyboard for btn in row]
        verbose_buttons = [b for b in all_buttons if "Verbose" in b.text]
        assert len(verbose_buttons) == 1
        assert "OFF" in verbose_buttons[0].text

    def test_dry_run_toggle_shows_checkmark_when_enabled(self, mock_settings_handlers):
        """Test that dry run button shows checkmark when enabled."""
        mock_settings_handlers.service.settings_service.get_settings_display.return_value = {
            "dry_run_mode": True,
            "enable_instagram_api": False,
            "is_paused": False,
            "posts_per_day": 3,
            "posting_hours_start": 9,
            "posting_hours_end": 21,
            "show_verbose_notifications": True,
        }
        mock_settings_handlers.service.ig_account_service.get_accounts_for_display.return_value = {
            "active_account_id": None,
            "active_account_name": "Not selected",
        }

        _, markup = mock_settings_handlers.build_settings_message_and_keyboard(-100123)

        all_buttons = [btn for row in markup.inline_keyboard for btn in row]
        dry_run_buttons = [b for b in all_buttons if "Dry Run" in b.text]
        assert len(dry_run_buttons) == 1
        assert "✅" in dry_run_buttons[0].text

    def test_paused_toggle_shows_correct_state(self, mock_settings_handlers):
        """Test that pause button shows Paused vs Active."""
        mock_settings_handlers.service.settings_service.get_settings_display.return_value = {
            "dry_run_mode": False,
            "enable_instagram_api": False,
            "is_paused": True,
            "posts_per_day": 3,
            "posting_hours_start": 9,
            "posting_hours_end": 21,
            "show_verbose_notifications": True,
        }
        mock_settings_handlers.service.ig_account_service.get_accounts_for_display.return_value = {
            "active_account_id": None,
            "active_account_name": "Not selected",
        }

        _, markup = mock_settings_handlers.build_settings_message_and_keyboard(-100123)

        all_buttons = [btn for row in markup.inline_keyboard for btn in row]
        pause_buttons = [
            b for b in all_buttons if "Paused" in b.text or "Active" in b.text
        ]
        assert len(pause_buttons) == 1
        assert "Paused" in pause_buttons[0].text

    def test_keyboard_has_schedule_buttons(self, mock_settings_handlers):
        """Test that keyboard includes Regenerate and +7 Days buttons."""
        mock_settings_handlers.service.settings_service.get_settings_display.return_value = {
            "dry_run_mode": False,
            "enable_instagram_api": False,
            "is_paused": False,
            "posts_per_day": 3,
            "posting_hours_start": 9,
            "posting_hours_end": 21,
            "show_verbose_notifications": True,
        }
        mock_settings_handlers.service.ig_account_service.get_accounts_for_display.return_value = {
            "active_account_id": None,
            "active_account_name": "Not selected",
        }

        _, markup = mock_settings_handlers.build_settings_message_and_keyboard(-100123)

        all_buttons = [btn for row in markup.inline_keyboard for btn in row]
        regenerate = [b for b in all_buttons if "Regenerate" in b.text]
        extend = [b for b in all_buttons if "+7 Days" in b.text]
        assert len(regenerate) == 1
        assert len(extend) == 1


@pytest.mark.unit
@pytest.mark.asyncio
class TestSettingsCommand:
    """Tests for /settings command handler."""

    async def test_handle_settings_sends_menu(self, mock_settings_handlers):
        """Test that /settings sends the settings menu."""
        mock_settings_handlers.service.settings_service.get_settings_display.return_value = {
            "dry_run_mode": False,
            "enable_instagram_api": False,
            "is_paused": False,
            "posts_per_day": 3,
            "posting_hours_start": 9,
            "posting_hours_end": 21,
            "show_verbose_notifications": True,
        }
        mock_settings_handlers.service.ig_account_service.get_accounts_for_display.return_value = {
            "active_account_id": None,
            "active_account_name": "Not selected",
        }

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "admin"
        mock_settings_handlers.service.user_repo.get_by_telegram_id.return_value = None
        mock_settings_handlers.service.user_repo.create.return_value = mock_user

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123456, username="admin", first_name="Admin", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        await mock_settings_handlers.handle_settings(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        assert "Bot Settings" in call_args.args[0]

    async def test_handle_settings_toggle_updates_setting(self, mock_settings_handlers):
        """Test that toggling a setting calls settings_service.toggle_setting."""
        mock_user = Mock()
        mock_user.id = uuid4()

        mock_settings_handlers.service.settings_service.toggle_setting.return_value = (
            True
        )
        mock_settings_handlers.service.settings_service.get_settings_display.return_value = {
            "dry_run_mode": True,
            "enable_instagram_api": False,
            "is_paused": False,
            "posts_per_day": 3,
            "posting_hours_start": 9,
            "posting_hours_end": 21,
            "show_verbose_notifications": True,
        }
        mock_settings_handlers.service.ig_account_service.get_accounts_for_display.return_value = {
            "active_account_id": None,
            "active_account_name": "Not selected",
        }

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        await mock_settings_handlers.handle_settings_toggle(
            "dry_run_mode", mock_user, mock_query
        )

        mock_settings_handlers.service.settings_service.toggle_setting.assert_called_once_with(
            -100123, "dry_run_mode", mock_user
        )

    async def test_handle_settings_close_deletes_message(self, mock_settings_handlers):
        """Test that close button deletes the settings message."""
        mock_query = AsyncMock()
        mock_query.message = AsyncMock()

        await mock_settings_handlers.handle_settings_close(mock_query)

        mock_query.message.delete.assert_called_once()
