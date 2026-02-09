"""Tests for TelegramAccountHandlers."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from uuid import uuid4

from src.services.core.telegram_service import TelegramService
from src.services.core.telegram_settings import TelegramSettingsHandlers
from src.services.core.telegram_accounts import TelegramAccountHandlers


@pytest.fixture
def mock_account_handlers():
    """Create TelegramAccountHandlers with mocked service dependencies."""
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

        # Wire up cross-handler references
        service.settings_handler = TelegramSettingsHandlers(service)
        handlers = TelegramAccountHandlers(service)
        service.accounts = handlers

        yield handlers


@pytest.mark.unit
@pytest.mark.asyncio
class TestAccountSelectorCallbacks:
    """Tests for account selector callback handlers."""

    async def test_handle_post_account_selector_shows_accounts(
        self, mock_account_handlers
    ):
        """Test that account selector menu shows all configured accounts."""
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.id = queue_id
        mock_account_handlers.service.queue_repo.get_by_id.return_value = (
            mock_queue_item
        )

        mock_account_handlers.service.ig_account_service = Mock()
        mock_account_handlers.service.ig_account_service.get_accounts_for_display.return_value = {
            "accounts": [
                {"id": "acc1", "display_name": "Main Account", "username": "main"},
                {"id": "acc2", "display_name": "Brand Account", "username": "brand"},
            ],
            "active_account_id": "acc1",
        }

        mock_user = Mock()
        mock_user.id = uuid4()

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        await mock_account_handlers.handle_post_account_selector(
            queue_id, mock_user, mock_query
        )

        # Verify edit_message_caption was called
        mock_query.edit_message_caption.assert_called_once()
        call_args = mock_query.edit_message_caption.call_args
        assert "Select Instagram Account" in call_args.kwargs["caption"]

    async def test_handle_back_to_post_rebuilds_workflow(self, mock_account_handlers):
        """Test that back_to_post returns to the posting workflow."""
        queue_id = str(uuid4())
        short_queue_id = queue_id[:8]

        mock_queue_item = Mock()
        mock_queue_item.id = queue_id
        mock_queue_item.media_item_id = uuid4()
        mock_account_handlers.service.queue_repo.get_by_id_prefix.return_value = (
            mock_queue_item
        )
        mock_account_handlers.service.queue_repo.get_by_id.return_value = (
            mock_queue_item
        )

        mock_media_item = Mock()
        mock_media_item.title = "Test"
        mock_media_item.caption = None
        mock_media_item.link_url = None
        mock_media_item.tags = []
        mock_account_handlers.service.media_repo.get_by_id.return_value = (
            mock_media_item
        )

        mock_account_handlers.service.ig_account_service = Mock()
        mock_account_handlers.service.ig_account_service.get_active_account.return_value = None

        mock_account_handlers.service.settings_service = Mock()
        mock_account_handlers.service.settings_service.get_settings.return_value = Mock(
            enable_instagram_api=False
        )

        mock_user = Mock()
        mock_user.id = uuid4()

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        await mock_account_handlers.handle_back_to_post(
            short_queue_id, mock_user, mock_query
        )

        # Should call edit_message_caption to rebuild the posting workflow
        mock_query.edit_message_caption.assert_called()

    async def test_handle_post_account_switch_stays_in_selector(
        self, mock_account_handlers
    ):
        """Test that switching account stays in selector menu to show updated checkmark."""
        queue_id = str(uuid4())
        account_id = str(uuid4())
        short_queue_id = queue_id[:8]
        short_account_id = account_id[:8]
        chat_id = -100123

        # Mock queue item
        mock_queue_item = Mock()
        mock_queue_item.id = queue_id
        mock_account_handlers.service.queue_repo.get_by_id_prefix.return_value = (
            mock_queue_item
        )
        mock_account_handlers.service.queue_repo.get_by_id.return_value = (
            mock_queue_item
        )

        # Mock account
        mock_account = Mock()
        mock_account.id = account_id
        mock_account.display_name = "Test Account"
        mock_account.instagram_username = "testaccount"
        mock_account_handlers.service.ig_account_service = Mock()
        mock_account_handlers.service.ig_account_service.get_account_by_id_prefix.return_value = mock_account
        mock_account_handlers.service.ig_account_service.switch_account.return_value = (
            mock_account
        )
        mock_account_handlers.service.ig_account_service.get_accounts_for_display.return_value = {
            "accounts": [
                {
                    "id": account_id,
                    "display_name": "Test Account",
                    "username": "testaccount",
                }
            ],
            "active_account_id": account_id,
        }

        mock_user = Mock()
        mock_user.id = uuid4()

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=chat_id, message_id=1)

        # Call the handler
        data = f"{short_queue_id}:{short_account_id}"
        await mock_account_handlers.handle_post_account_switch(
            data, mock_user, mock_query
        )

        # Verify switch_account was called
        mock_account_handlers.service.ig_account_service.switch_account.assert_called_once_with(
            chat_id, account_id, mock_user
        )

        # Verify success toast was shown
        mock_query.answer.assert_called_once_with("✅ Switched to Test Account")

        # Verify edit_message_caption was called (account selector menu rebuilt)
        mock_query.edit_message_caption.assert_called_once()
        call_args = mock_query.edit_message_caption.call_args
        assert "Select Instagram Account" in call_args.kwargs["caption"]


@pytest.mark.unit
@pytest.mark.asyncio
class TestAccountSelectionMenu:
    """Tests for account selection menu."""

    async def test_shows_accounts_with_active_checkmark(self, mock_account_handlers):
        """Test that account menu shows checkmark on active account."""
        mock_account_handlers.service.ig_account_service.get_accounts_for_display.return_value = {
            "accounts": [
                {"id": "acc1", "display_name": "Main", "username": "main"},
                {"id": "acc2", "display_name": "Brand", "username": "brand"},
            ],
            "active_account_id": "acc1",
        }

        mock_user = Mock()
        mock_user.id = uuid4()

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        await mock_account_handlers.handle_account_selection_menu(mock_user, mock_query)

        mock_query.edit_message_text.assert_called_once()
        call_args = mock_query.edit_message_text.call_args
        assert "Choose Default Account" in call_args.kwargs.get(
            "text", call_args.args[0] if call_args.args else ""
        )

    async def test_shows_no_accounts_message(self, mock_account_handlers):
        """Test that menu shows placeholder when no accounts configured."""
        mock_account_handlers.service.ig_account_service.get_accounts_for_display.return_value = {
            "accounts": [],
            "active_account_id": None,
        }

        mock_user = Mock()
        mock_user.id = uuid4()

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        await mock_account_handlers.handle_account_selection_menu(mock_user, mock_query)

        mock_query.edit_message_text.assert_called_once()
        # Verify keyboard contains "No accounts configured"
        call_kwargs = mock_query.edit_message_text.call_args.kwargs
        markup = call_kwargs["reply_markup"]
        all_buttons = [btn for row in markup.inline_keyboard for btn in row]
        no_accounts = [b for b in all_buttons if "No accounts" in b.text]
        assert len(no_accounts) == 1

    async def test_account_switch_calls_service(self, mock_account_handlers):
        """Test that switching account delegates to ig_account_service."""
        mock_account = Mock()
        mock_account.display_name = "Brand"
        mock_account.instagram_username = "brand"
        mock_account_handlers.service.ig_account_service.switch_account.return_value = (
            mock_account
        )

        # Set up settings handler for refresh
        mock_account_handlers.service.settings_service.get_settings_display.return_value = {
            "dry_run_mode": False,
            "enable_instagram_api": False,
            "is_paused": False,
            "posts_per_day": 3,
            "posting_hours_start": 9,
            "posting_hours_end": 21,
            "show_verbose_notifications": True,
        }
        mock_account_handlers.service.ig_account_service.get_accounts_for_display.return_value = {
            "active_account_id": "acc1",
            "active_account_name": "Brand",
        }

        mock_user = Mock()
        mock_user.id = uuid4()

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        await mock_account_handlers.handle_account_switch("acc1", mock_user, mock_query)

        mock_account_handlers.service.ig_account_service.switch_account.assert_called_once_with(
            -100123, "acc1", mock_user
        )

    async def test_remove_account_confirm_shows_account_details(
        self, mock_account_handlers
    ):
        """Test that remove confirmation shows account name and username."""
        mock_account = Mock()
        mock_account.display_name = "Test Account"
        mock_account.instagram_username = "testuser"
        mock_account_handlers.service.ig_account_service.get_account_by_id.return_value = mock_account

        mock_user = Mock()
        mock_user.id = uuid4()

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        await mock_account_handlers.handle_account_remove_confirm(
            "acc1", mock_user, mock_query
        )

        mock_query.edit_message_text.assert_called_once()
        call_text = mock_query.edit_message_text.call_args.kwargs.get(
            "text", mock_query.edit_message_text.call_args.args[0]
        )
        assert "Test Account" in call_text
        assert "@testuser" in call_text

    async def test_remove_account_not_found(self, mock_account_handlers):
        """Test that remove shows alert when account not found."""
        mock_account_handlers.service.ig_account_service.get_account_by_id.return_value = None

        mock_user = Mock()
        mock_user.id = uuid4()

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        await mock_account_handlers.handle_account_remove_confirm(
            "nonexistent", mock_user, mock_query
        )

        mock_query.answer.assert_called_once_with("Account not found", show_alert=True)

    async def test_remove_account_execute_deactivates(self, mock_account_handlers):
        """Test that remove execute calls deactivate_account."""
        mock_account = Mock()
        mock_account.display_name = "Test"
        mock_account.instagram_username = "test"
        mock_account_handlers.service.ig_account_service.deactivate_account.return_value = mock_account
        mock_account_handlers.service.ig_account_service.get_accounts_for_display.return_value = {
            "accounts": [],
            "active_account_id": None,
        }

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "admin"
        mock_user.telegram_first_name = "Admin"

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        await mock_account_handlers.handle_account_remove_execute(
            "acc1", mock_user, mock_query
        )

        mock_account_handlers.service.ig_account_service.deactivate_account.assert_called_once_with(
            "acc1", mock_user
        )
