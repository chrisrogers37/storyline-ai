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
            "media_sync_enabled": False,
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


@pytest.mark.unit
@pytest.mark.asyncio
class TestAddAccountFlow:
    """Tests for the add-account conversation state machine."""

    def _make_update(self, text="test input", chat_id=-100123, message_id=42):
        """Build a mock Telegram Update for message handling."""
        update = AsyncMock()
        update.message.text = text
        update.message.message_id = message_id
        update.message.reply_text = AsyncMock(
            return_value=Mock(message_id=message_id + 1)
        )
        update.message.delete = AsyncMock()
        update.effective_chat.id = chat_id
        update.effective_user = Mock(id=999, username="tester", first_name="Test")
        return update

    def _make_context(self, state=None, data=None):
        """Build a mock Telegram context with add-account state."""
        context = Mock()
        context.user_data = {}
        if state:
            context.user_data["add_account_state"] = state
            context.user_data["add_account_data"] = data or {}
            context.user_data["add_account_messages"] = [10]
            context.user_data["add_account_chat_id"] = -100123
        context.bot = AsyncMock()
        context.bot.send_message = AsyncMock(
            return_value=Mock(message_id=100, delete=AsyncMock())
        )
        context.bot.delete_message = AsyncMock()
        return context

    # --- Dispatcher tests ---

    async def test_handle_add_account_message_not_in_flow(self, mock_account_handlers):
        """Returns False when no add_account_state in user_data."""
        update = self._make_update()
        context = self._make_context()  # No state set

        result = await mock_account_handlers.handle_add_account_message(update, context)
        assert result is False

    # --- Display name (Step 1) ---

    async def test_handle_display_name_input_advances_state(
        self, mock_account_handlers
    ):
        """Saves display name and advances to awaiting_account_id."""
        update = self._make_update(text="My Brand")
        context = self._make_context(state="awaiting_display_name")

        result = await mock_account_handlers.handle_add_account_message(update, context)

        assert result is True
        assert context.user_data["add_account_state"] == "awaiting_account_id"
        assert context.user_data["add_account_data"]["display_name"] == "My Brand"
        # Verify reply was sent with Step 2 prompt
        update.message.reply_text.assert_called_once()
        call_text = update.message.reply_text.call_args.kwargs.get(
            "text", update.message.reply_text.call_args.args[0]
        )
        assert "Step 2 of 3" in call_text

    # --- Account ID (Step 2) ---

    async def test_handle_account_id_input_validates_numeric(
        self, mock_account_handlers
    ):
        """Rejects non-numeric account ID input."""
        update = self._make_update(text="not-a-number")
        context = self._make_context(state="awaiting_account_id")

        result = await mock_account_handlers.handle_add_account_message(update, context)

        assert result is True
        # State should NOT advance
        assert context.user_data["add_account_state"] == "awaiting_account_id"
        update.message.reply_text.assert_called_once()
        call_text = update.message.reply_text.call_args.kwargs.get(
            "text", update.message.reply_text.call_args.args[0]
        )
        assert "numeric" in call_text

    async def test_handle_account_id_input_saves_and_advances(
        self, mock_account_handlers
    ):
        """Saves numeric account ID and advances to awaiting_token."""
        update = self._make_update(text="123456789")
        context = self._make_context(
            state="awaiting_account_id",
            data={"display_name": "Test"},
        )

        result = await mock_account_handlers.handle_add_account_message(update, context)

        assert result is True
        assert context.user_data["add_account_state"] == "awaiting_token"
        assert context.user_data["add_account_data"]["account_id"] == "123456789"
        call_text = update.message.reply_text.call_args.kwargs.get(
            "text", update.message.reply_text.call_args.args[0]
        )
        assert "Step 3 of 3" in call_text

    # --- Token (Step 3) ---

    async def test_handle_token_input_creates_account(self, mock_account_handlers):
        """Creates new account when API validates and account doesn't exist."""
        update = self._make_update(text="EAABtest123token")
        context = self._make_context(
            state="awaiting_token",
            data={"display_name": "Brand", "account_id": "12345"},
        )

        mock_user = Mock(
            id=uuid4(), telegram_username="tester", telegram_first_name="Test"
        )
        mock_account_handlers.service._get_or_create_user = Mock(return_value=mock_user)
        mock_account_handlers.service._get_display_name = Mock(return_value="@tester")

        mock_account = Mock(
            id=uuid4(), display_name="Brand", instagram_username="brand_ig"
        )
        mock_account_handlers.service.ig_account_service.get_account_by_instagram_id.return_value = None
        mock_account_handlers.service.ig_account_service.add_account.return_value = (
            mock_account
        )
        mock_account_handlers.service.ig_account_service.get_accounts_for_display.return_value = {
            "accounts": [
                {
                    "id": str(mock_account.id),
                    "display_name": "Brand",
                    "username": "brand_ig",
                }
            ],
            "active_account_id": str(mock_account.id),
        }

        # Mock httpx response
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {"username": "brand_ig"}
        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_response)

        with patch(
            "src.services.core.telegram_accounts.httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(
                return_value=mock_http_client
            )
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await mock_account_handlers.handle_add_account_message(
                update, context
            )

        assert result is True
        mock_account_handlers.service.ig_account_service.add_account.assert_called_once()
        # Verify success message sent
        context.bot.send_message.assert_called()
        success_call = context.bot.send_message.call_args
        assert "Added @brand_ig" in success_call.kwargs["text"]

    async def test_handle_token_input_updates_existing_account(
        self, mock_account_handlers
    ):
        """Updates token when account already exists."""
        update = self._make_update(text="EAABtest123token")
        context = self._make_context(
            state="awaiting_token",
            data={"display_name": "Brand", "account_id": "12345"},
        )

        mock_user = Mock(
            id=uuid4(), telegram_username="tester", telegram_first_name="Test"
        )
        mock_account_handlers.service._get_or_create_user = Mock(return_value=mock_user)
        mock_account_handlers.service._get_display_name = Mock(return_value="@tester")

        existing_account = Mock(
            id=uuid4(), display_name="Brand", instagram_username="brand_ig"
        )
        mock_account_handlers.service.ig_account_service.get_account_by_instagram_id.return_value = existing_account
        mock_account_handlers.service.ig_account_service.update_account_token.return_value = existing_account
        mock_account_handlers.service.ig_account_service.get_accounts_for_display.return_value = {
            "accounts": [
                {
                    "id": str(existing_account.id),
                    "display_name": "Brand",
                    "username": "brand_ig",
                }
            ],
            "active_account_id": str(existing_account.id),
        }

        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {"username": "brand_ig"}
        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_response)

        with patch(
            "src.services.core.telegram_accounts.httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(
                return_value=mock_http_client
            )
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await mock_account_handlers.handle_add_account_message(
                update, context
            )

        assert result is True
        mock_account_handlers.service.ig_account_service.update_account_token.assert_called_once()
        # Verify update success message
        success_call = context.bot.send_message.call_args
        assert "Updated token for @brand_ig" in success_call.kwargs["text"]

    async def test_handle_token_input_api_error_shows_error(
        self, mock_account_handlers
    ):
        """Verifies bug fix: API error message is shown, not deletion error."""
        update = self._make_update(text="bad_token")
        context = self._make_context(
            state="awaiting_token",
            data={"display_name": "Brand", "account_id": "12345"},
        )

        mock_user = Mock(id=uuid4())
        mock_account_handlers.service._get_or_create_user = Mock(return_value=mock_user)

        # API returns error
        mock_response = Mock(status_code=400)
        mock_response.json.return_value = {
            "error": {"message": "Invalid OAuth access token"}
        }
        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_response)

        with patch(
            "src.services.core.telegram_accounts.httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(
                return_value=mock_http_client
            )
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await mock_account_handlers.handle_add_account_message(
                update, context
            )

        assert result is True
        # Verify error message shows the user-friendly OAuth error, NOT a deletion error
        error_call = context.bot.send_message.call_args
        error_text = error_call.kwargs["text"]
        assert "Failed to add account" in error_text
        assert "Invalid or expired access token" in error_text

    async def test_handle_token_input_deletes_token_message(
        self, mock_account_handlers
    ):
        """Verifies the token message is deleted for security."""
        update = self._make_update(text="secret_token")
        context = self._make_context(
            state="awaiting_token",
            data={"display_name": "Brand", "account_id": "12345"},
        )

        mock_user = Mock(id=uuid4())
        mock_account_handlers.service._get_or_create_user = Mock(return_value=mock_user)

        # Make API call fail so we can check deletion happened first
        mock_response = Mock(status_code=400)
        mock_response.json.return_value = {"error": {"message": "Bad token"}}
        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_response)

        with patch(
            "src.services.core.telegram_accounts.httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(
                return_value=mock_http_client
            )
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            await mock_account_handlers.handle_add_account_message(update, context)

        # Token message should be deleted for security
        update.message.delete.assert_called_once()

    # --- Cleanup helper ---

    async def test_cleanup_conversation_messages_deletes_tracked(
        self, mock_account_handlers
    ):
        """Deletes all tracked messages from the chat."""
        context = self._make_context()
        context.user_data["add_account_messages"] = [10, 20, 30]

        await mock_account_handlers._cleanup_conversation_messages(
            context, chat_id=-100123
        )

        assert context.bot.delete_message.call_count == 3
        deleted_ids = [
            call.kwargs["message_id"]
            for call in context.bot.delete_message.call_args_list
        ]
        assert deleted_ids == [10, 20, 30]

    async def test_cleanup_conversation_messages_excludes_message(
        self, mock_account_handlers
    ):
        """Skips the excluded message ID during cleanup."""
        context = self._make_context()
        context.user_data["add_account_messages"] = [10, 20, 30]

        await mock_account_handlers._cleanup_conversation_messages(
            context, chat_id=-100123, exclude_message_id=20
        )

        assert context.bot.delete_message.call_count == 2
        deleted_ids = [
            call.kwargs["message_id"]
            for call in context.bot.delete_message.call_args_list
        ]
        assert 20 not in deleted_ids

    # --- Keyboard builder ---

    async def test_build_account_config_keyboard_with_accounts(
        self, mock_account_handlers
    ):
        """Keyboard includes account rows, add, remove, and back buttons."""
        account_data = {
            "accounts": [
                {"id": "acc1", "display_name": "Main", "username": "main_ig"},
                {"id": "acc2", "display_name": "Brand", "username": "brand_ig"},
            ],
            "active_account_id": "acc1",
        }

        markup = mock_account_handlers._build_account_config_keyboard(account_data)

        buttons = [btn for row in markup.inline_keyboard for btn in row]
        button_texts = [b.text for b in buttons]

        # Active account has checkmark
        assert any("✅" in t and "Main" in t for t in button_texts)
        # Inactive account does not
        assert any("Brand" in t and "✅" not in t for t in button_texts)
        # Action buttons present
        assert any("Add Account" in t for t in button_texts)
        assert any("Remove Account" in t for t in button_texts)
        assert any("Back to Settings" in t for t in button_texts)

    async def test_build_account_config_keyboard_no_accounts(
        self, mock_account_handlers
    ):
        """Keyboard shows placeholder when no accounts exist."""
        account_data = {"accounts": [], "active_account_id": None}

        markup = mock_account_handlers._build_account_config_keyboard(account_data)

        buttons = [btn for row in markup.inline_keyboard for btn in row]
        button_texts = [b.text for b in buttons]

        assert any("No accounts configured" in t for t in button_texts)
        assert any("Add Account" in t for t in button_texts)
        # Remove button should NOT appear
        assert not any("Remove Account" in t for t in button_texts)

    # --- Interaction logging ---

    async def test_handle_token_input_logs_interaction(self, mock_account_handlers):
        """Verifies log_callback receives correct action and context dict."""
        update = self._make_update(text="EAABtest123token")
        context = self._make_context(
            state="awaiting_token",
            data={"display_name": "Brand", "account_id": "12345"},
        )

        mock_user = Mock(
            id=uuid4(), telegram_username="tester", telegram_first_name="Test"
        )
        mock_account_handlers.service._get_or_create_user = Mock(return_value=mock_user)
        mock_account_handlers.service._get_display_name = Mock(return_value="@tester")

        mock_account = Mock(
            id=uuid4(), display_name="Brand", instagram_username="brand_ig"
        )
        mock_account_handlers.service.ig_account_service.get_account_by_instagram_id.return_value = None
        mock_account_handlers.service.ig_account_service.add_account.return_value = (
            mock_account
        )
        mock_account_handlers.service.ig_account_service.get_accounts_for_display.return_value = {
            "accounts": [
                {
                    "id": str(mock_account.id),
                    "display_name": "Brand",
                    "username": "brand_ig",
                }
            ],
            "active_account_id": str(mock_account.id),
        }

        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {"username": "brand_ig"}
        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_response)

        with patch(
            "src.services.core.telegram_accounts.httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(
                return_value=mock_http_client
            )
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            await mock_account_handlers.handle_add_account_message(update, context)

        # Verify interaction logged with correct params
        mock_account_handlers.service.interaction_service.log_callback.assert_called_once()
        log_call = (
            mock_account_handlers.service.interaction_service.log_callback.call_args
        )
        assert log_call.kwargs["callback_name"] == "add_account"
        assert log_call.kwargs["context"]["display_name"] == "Brand"
        assert log_call.kwargs["context"]["username"] == "brand_ig"
        assert log_call.kwargs["context"]["was_update"] is False
