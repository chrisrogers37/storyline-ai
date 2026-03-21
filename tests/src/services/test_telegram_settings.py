"""Tests for TelegramSettingsHandlers."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from uuid import uuid4

from src.services.core.telegram_settings import TelegramSettingsHandlers


@pytest.fixture
def mock_settings_handlers(mock_telegram_service):
    """Create TelegramSettingsHandlers from shared mock_telegram_service."""
    handlers = TelegramSettingsHandlers(mock_telegram_service)
    mock_telegram_service.settings_handler = handlers
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
            "media_sync_enabled": False,
            "media_source_type": None,
            "media_source_root": None,
        }
        mock_settings_handlers.service.ig_account_service.get_accounts_for_display.return_value = {
            "active_account_id": "some-id",
            "active_account_name": "Test Account",
        }

        message, markup = mock_settings_handlers.build_settings_message_and_keyboard(
            -100123
        )

        assert "Quick Setup" in message
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
            "media_sync_enabled": False,
            "media_source_type": None,
            "media_source_root": None,
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
            "media_sync_enabled": False,
            "media_source_type": None,
            "media_source_root": None,
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

    def test_delivery_toggle_shows_off_when_paused(self, mock_settings_handlers):
        """Test that delivery button shows OFF when paused."""
        mock_settings_handlers.service.settings_service.get_settings_display.return_value = {
            "dry_run_mode": False,
            "enable_instagram_api": False,
            "is_paused": True,
            "posts_per_day": 3,
            "posting_hours_start": 9,
            "posting_hours_end": 21,
            "show_verbose_notifications": True,
            "media_sync_enabled": False,
            "media_source_type": None,
            "media_source_root": None,
        }
        mock_settings_handlers.service.ig_account_service.get_accounts_for_display.return_value = {
            "active_account_id": None,
            "active_account_name": "Not selected",
        }

        _, markup = mock_settings_handlers.build_settings_message_and_keyboard(-100123)

        all_buttons = [btn for row in markup.inline_keyboard for btn in row]
        delivery_buttons = [b for b in all_buttons if "Delivery" in b.text]
        assert len(delivery_buttons) == 1
        assert "OFF" in delivery_buttons[0].text

    def test_delivery_toggle_shows_on_when_active(self, mock_settings_handlers):
        """Test that delivery button shows ON when not paused."""
        mock_settings_handlers.service.settings_service.get_settings_display.return_value = {
            "dry_run_mode": False,
            "enable_instagram_api": False,
            "is_paused": False,
            "posts_per_day": 3,
            "posting_hours_start": 9,
            "posting_hours_end": 21,
            "show_verbose_notifications": True,
            "media_sync_enabled": False,
            "media_source_type": None,
            "media_source_root": None,
        }
        mock_settings_handlers.service.ig_account_service.get_accounts_for_display.return_value = {
            "active_account_id": None,
            "active_account_name": "Not selected",
        }

        _, markup = mock_settings_handlers.build_settings_message_and_keyboard(-100123)

        all_buttons = [btn for row in markup.inline_keyboard for btn in row]
        delivery_buttons = [b for b in all_buttons if "Delivery" in b.text]
        assert len(delivery_buttons) == 1
        assert "ON" in delivery_buttons[0].text

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
            "media_sync_enabled": False,
            "media_source_type": None,
            "media_source_root": None,
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

    @patch("src.services.core.telegram_settings.app_settings")
    def test_mini_app_button_present_when_configured(
        self, mock_app_settings, mock_settings_handlers
    ):
        """Test that 'Open Full Settings' button appears when OAUTH_REDIRECT_BASE_URL is set."""
        mock_app_settings.OAUTH_REDIRECT_BASE_URL = "https://example.railway.app"
        mock_settings_handlers.service.settings_service.get_settings_display.return_value = {
            "dry_run_mode": False,
            "enable_instagram_api": False,
            "is_paused": False,
            "posts_per_day": 3,
            "posting_hours_start": 9,
            "posting_hours_end": 21,
            "show_verbose_notifications": True,
            "media_sync_enabled": False,
            "media_source_type": None,
            "media_source_root": None,
        }
        mock_settings_handlers.service.ig_account_service.get_accounts_for_display.return_value = {
            "active_account_id": None,
            "active_account_name": "Not selected",
        }

        # In group chats (default), uses signed URL button
        _, markup = mock_settings_handlers.build_settings_message_and_keyboard(-100123)
        all_buttons = [btn for row in markup.inline_keyboard for btn in row]
        mini_app_buttons = [b for b in all_buttons if "Full Settings" in b.text]
        assert len(mini_app_buttons) == 1
        assert mini_app_buttons[0].url is not None
        assert "token=" in mini_app_buttons[0].url

        # In private chats, uses WebAppInfo button
        _, markup_priv = mock_settings_handlers.build_settings_message_and_keyboard(
            -100123, user_id=12345, is_private=True
        )
        all_buttons_priv = [btn for row in markup_priv.inline_keyboard for btn in row]
        mini_app_priv = [b for b in all_buttons_priv if "Full Settings" in b.text]
        assert len(mini_app_priv) == 1
        assert mini_app_priv[0].web_app is not None

    @patch("src.services.core.telegram_settings.app_settings")
    def test_mini_app_button_absent_when_not_configured(
        self, mock_app_settings, mock_settings_handlers
    ):
        """Test that 'Open Full Settings' button is absent when OAUTH_REDIRECT_BASE_URL is None."""
        mock_app_settings.OAUTH_REDIRECT_BASE_URL = None
        mock_settings_handlers.service.settings_service.get_settings_display.return_value = {
            "dry_run_mode": False,
            "enable_instagram_api": False,
            "is_paused": False,
            "posts_per_day": 3,
            "posting_hours_start": 9,
            "posting_hours_end": 21,
            "show_verbose_notifications": True,
            "media_sync_enabled": False,
            "media_source_type": None,
            "media_source_root": None,
        }
        mock_settings_handlers.service.ig_account_service.get_accounts_for_display.return_value = {
            "active_account_id": None,
            "active_account_name": "Not selected",
        }

        _, markup = mock_settings_handlers.build_settings_message_and_keyboard(-100123)

        all_buttons = [btn for row in markup.inline_keyboard for btn in row]
        mini_app_buttons = [b for b in all_buttons if "Full Settings" in b.text]
        assert len(mini_app_buttons) == 0


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
            "media_sync_enabled": False,
            "media_source_type": None,
            "media_source_root": None,
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
        mock_update.message.text = "/settings"

        mock_context = Mock()

        await mock_settings_handlers.handle_settings(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        assert "Quick Setup" in call_args.args[0]

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
            "media_sync_enabled": False,
            "media_source_type": None,
            "media_source_root": None,
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


@pytest.mark.unit
class TestMediaSyncToggleButton:
    """Tests for Media Sync toggle button in settings keyboard."""

    def test_media_sync_toggle_button_shows_on(self, mock_settings_handlers):
        """Settings keyboard shows 'Media Sync: ON' when enabled."""
        mock_settings_handlers.service.settings_service.get_settings_display.return_value = {
            "dry_run_mode": False,
            "enable_instagram_api": False,
            "is_paused": False,
            "posts_per_day": 3,
            "posting_hours_start": 9,
            "posting_hours_end": 21,
            "show_verbose_notifications": True,
            "media_sync_enabled": True,
            "media_source_type": None,
            "media_source_root": None,
        }
        mock_settings_handlers.service.ig_account_service.get_accounts_for_display.return_value = {
            "active_account_id": None,
            "active_account_name": "Not selected",
        }

        _, markup = mock_settings_handlers.build_settings_message_and_keyboard(-100123)

        all_buttons = [btn for row in markup.inline_keyboard for btn in row]
        sync_buttons = [b for b in all_buttons if "Media Sync" in b.text]
        assert len(sync_buttons) == 1
        assert "ON" in sync_buttons[0].text
        assert sync_buttons[0].callback_data == "settings_toggle:media_sync_enabled"

    def test_media_sync_toggle_button_shows_off(self, mock_settings_handlers):
        """Settings keyboard shows 'Media Sync: OFF' when disabled."""
        mock_settings_handlers.service.settings_service.get_settings_display.return_value = {
            "dry_run_mode": False,
            "enable_instagram_api": False,
            "is_paused": False,
            "posts_per_day": 3,
            "posting_hours_start": 9,
            "posting_hours_end": 21,
            "show_verbose_notifications": True,
            "media_sync_enabled": False,
            "media_source_type": None,
            "media_source_root": None,
        }
        mock_settings_handlers.service.ig_account_service.get_accounts_for_display.return_value = {
            "active_account_id": None,
            "active_account_name": "Not selected",
        }

        _, markup = mock_settings_handlers.build_settings_message_and_keyboard(-100123)

        all_buttons = [btn for row in markup.inline_keyboard for btn in row]
        sync_buttons = [b for b in all_buttons if "Media Sync" in b.text]
        assert len(sync_buttons) == 1
        assert "OFF" in sync_buttons[0].text
