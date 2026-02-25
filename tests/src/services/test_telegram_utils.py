"""Tests for telegram_utils shared utility functions."""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from src.services.core.telegram_utils import (
    _build_already_handled_caption,
    build_account_management_keyboard,
    build_webapp_button,
    cleanup_conversation_messages,
    validate_queue_item,
)


@pytest.mark.unit
class TestBuildAccountManagementKeyboard:
    """Tests for build_account_management_keyboard."""

    def test_builds_keyboard_with_accounts(self):
        """Test keyboard shows accounts with active checkmark."""
        account_data = {
            "accounts": [
                {"id": "acc1", "display_name": "Main", "username": "main_user"},
                {"id": "acc2", "display_name": "Brand", "username": "brand_user"},
            ],
            "active_account_id": "acc1",
        }

        keyboard = build_account_management_keyboard(account_data)

        assert "✅" in keyboard[0][0].text
        assert "Main" in keyboard[0][0].text
        assert "@main_user" in keyboard[0][0].text
        assert keyboard[0][0].callback_data == "switch_account:acc1"

        assert "✅" not in keyboard[1][0].text
        assert "Brand" in keyboard[1][0].text
        assert keyboard[1][0].callback_data == "switch_account:acc2"

    def test_shows_no_accounts_placeholder(self):
        """Test placeholder button when no accounts exist."""
        account_data = {"accounts": [], "active_account_id": None}

        keyboard = build_account_management_keyboard(account_data)

        assert "No accounts configured" in keyboard[0][0].text
        assert keyboard[0][0].callback_data == "accounts_config:noop"

    def test_includes_add_button(self):
        """Test Add Account button is always present."""
        account_data = {"accounts": [], "active_account_id": None}

        keyboard = build_account_management_keyboard(account_data)

        all_buttons = [btn for row in keyboard for btn in row]
        add_buttons = [b for b in all_buttons if "Add Account" in b.text]
        assert len(add_buttons) == 1
        assert add_buttons[0].callback_data == "accounts_config:add"

    def test_includes_remove_button_when_accounts_exist(self):
        """Test Remove Account button present only when accounts exist."""
        account_data = {
            "accounts": [
                {"id": "acc1", "display_name": "Main", "username": "main"},
            ],
            "active_account_id": "acc1",
        }

        keyboard = build_account_management_keyboard(account_data)

        all_buttons = [btn for row in keyboard for btn in row]
        remove_buttons = [b for b in all_buttons if "Remove Account" in b.text]
        assert len(remove_buttons) == 1

    def test_no_remove_button_when_no_accounts(self):
        """Test Remove Account button absent when no accounts."""
        account_data = {"accounts": [], "active_account_id": None}

        keyboard = build_account_management_keyboard(account_data)

        all_buttons = [btn for row in keyboard for btn in row]
        remove_buttons = [b for b in all_buttons if "Remove Account" in b.text]
        assert len(remove_buttons) == 0

    def test_includes_back_button(self):
        """Test Back to Settings button is always last."""
        account_data = {"accounts": [], "active_account_id": None}

        keyboard = build_account_management_keyboard(account_data)

        last_row = keyboard[-1]
        assert "Back to Settings" in last_row[0].text
        assert last_row[0].callback_data == "settings_accounts:back"

    def test_account_without_username(self):
        """Test account label omits username when None."""
        account_data = {
            "accounts": [
                {"id": "acc1", "display_name": "No Username", "username": None},
            ],
            "active_account_id": None,
        }

        keyboard = build_account_management_keyboard(account_data)

        assert "No Username" in keyboard[0][0].text
        assert "@" not in keyboard[0][0].text


@pytest.mark.unit
@pytest.mark.asyncio
class TestCleanupConversationMessages:
    """Tests for cleanup_conversation_messages."""

    async def test_deletes_all_messages(self):
        """Test all message IDs are deleted."""
        bot = AsyncMock()
        result = await cleanup_conversation_messages(
            bot, chat_id=123, message_ids=[1, 2, 3]
        )

        assert result == 3
        assert bot.delete_message.call_count == 3
        bot.delete_message.assert_any_call(chat_id=123, message_id=1)
        bot.delete_message.assert_any_call(chat_id=123, message_id=2)
        bot.delete_message.assert_any_call(chat_id=123, message_id=3)

    async def test_skips_excluded_id(self):
        """Test exclude_id is not deleted."""
        bot = AsyncMock()
        result = await cleanup_conversation_messages(
            bot, chat_id=123, message_ids=[1, 2, 3], exclude_id=2
        )

        assert result == 2
        assert bot.delete_message.call_count == 2
        for call in bot.delete_message.call_args_list:
            assert call.kwargs["message_id"] != 2

    async def test_handles_empty_list(self):
        """Test no errors on empty message list."""
        bot = AsyncMock()
        result = await cleanup_conversation_messages(bot, chat_id=123, message_ids=[])

        assert result == 0
        bot.delete_message.assert_not_called()

    async def test_tolerates_delete_failures(self):
        """Test failures are logged and skipped, not raised."""
        bot = AsyncMock()
        bot.delete_message.side_effect = [None, Exception("Not found"), None]

        result = await cleanup_conversation_messages(
            bot, chat_id=123, message_ids=[1, 2, 3]
        )

        assert result == 2

    async def test_returns_zero_on_all_failures(self):
        """Test returns 0 when all deletes fail."""
        bot = AsyncMock()
        bot.delete_message.side_effect = Exception("Forbidden")

        result = await cleanup_conversation_messages(
            bot, chat_id=123, message_ids=[1, 2]
        )

        assert result == 0


class TestBuildWebappButton:
    """Tests for build_webapp_button utility."""

    @patch("src.services.core.telegram_utils.generate_url_token")
    def test_private_chat_uses_webappinfo(self, mock_token):
        """Private chats should use WebAppInfo for inline Mini App."""
        button = build_webapp_button(
            text="Open App",
            webapp_url="https://example.com/app?chat_id=123",
            chat_type="private",
            chat_id=123,
            user_id=456,
        )

        assert button.text == "Open App"
        assert button.web_app is not None
        assert button.web_app.url == "https://example.com/app?chat_id=123"
        assert button.url is None
        mock_token.assert_not_called()

    @patch("src.services.core.telegram_utils.generate_url_token")
    def test_group_chat_uses_signed_url(self, mock_token):
        """Group chats should use signed URL token."""
        mock_token.return_value = "test-token-abc"

        button = build_webapp_button(
            text="Open Dashboard",
            webapp_url="https://example.com/app?chat_id=-100",
            chat_type="group",
            chat_id=-100,
            user_id=789,
        )

        assert button.text == "Open Dashboard"
        assert button.web_app is None
        assert "token=test-token-abc" in button.url
        mock_token.assert_called_once_with(-100, 789)

    @patch("src.services.core.telegram_utils.generate_url_token")
    def test_supergroup_uses_signed_url(self, mock_token):
        """Supergroups should also use signed URL (not WebAppInfo)."""
        mock_token.return_value = "sg-token"

        button = build_webapp_button(
            text="Open",
            webapp_url="https://example.com/app?chat_id=-200",
            chat_type="supergroup",
            chat_id=-200,
            user_id=111,
        )

        assert button.url is not None
        assert button.web_app is None


@pytest.mark.unit
class TestBuildAlreadyHandledCaption:
    """Tests for _build_already_handled_caption helper."""

    def test_posted_via_api(self):
        history = Mock(status="posted", posting_method="instagram_api")
        assert "Already posted via Instagram API" in _build_already_handled_caption(
            history
        )

    def test_posted_via_manual(self):
        history = Mock(status="posted", posting_method="telegram_manual")
        assert "Already marked as posted" in _build_already_handled_caption(history)

    def test_skipped(self):
        history = Mock(status="skipped", posting_method="telegram_manual")
        assert "Already skipped" in _build_already_handled_caption(history)

    def test_rejected(self):
        history = Mock(status="rejected", posting_method="telegram_manual")
        assert "Already rejected" in _build_already_handled_caption(history)

    def test_failed(self):
        history = Mock(status="failed", posting_method="telegram_manual")
        assert "Previous attempt failed" in _build_already_handled_caption(history)

    def test_unknown_status(self):
        history = Mock(status="custom_status", posting_method=None)
        result = _build_already_handled_caption(history)
        assert "Already processed" in result
        assert "custom_status" in result


@pytest.mark.unit
@pytest.mark.asyncio
class TestValidateQueueItem:
    """Tests for validate_queue_item with history-based race detection."""

    async def test_shows_already_posted_api_when_history_posted_via_api(self):
        """Race: item auto-posted, second callback gets contextual message."""
        service = Mock()
        service.queue_repo.get_by_id.return_value = None
        service.history_repo.get_by_queue_item_id.return_value = Mock(
            status="posted", posting_method="instagram_api"
        )
        query = AsyncMock()

        result = await validate_queue_item(service, "q-1", query)

        assert result is None
        caption = (
            query.edit_message_caption.call_args.kwargs.get("caption")
            or query.edit_message_caption.call_args[0][0]
        )
        assert "Already posted via Instagram API" in caption

    async def test_shows_already_skipped(self):
        """Race: item was skipped, second callback shows contextual message."""
        service = Mock()
        service.queue_repo.get_by_id.return_value = None
        service.history_repo.get_by_queue_item_id.return_value = Mock(
            status="skipped", posting_method="telegram_manual"
        )
        query = AsyncMock()

        result = await validate_queue_item(service, "q-2", query)

        assert result is None
        caption = query.edit_message_caption.call_args.kwargs.get("caption", "")
        assert "Already skipped" in caption

    async def test_shows_generic_not_found_when_no_history(self):
        """Neither queue nor history -> generic not found message."""
        service = Mock()
        service.queue_repo.get_by_id.return_value = None
        service.history_repo.get_by_queue_item_id.return_value = None
        query = AsyncMock()

        result = await validate_queue_item(service, "q-3", query)

        assert result is None
        caption = query.edit_message_caption.call_args.kwargs.get("caption", "")
        assert "Queue item not found" in caption

    async def test_returns_queue_item_when_found(self):
        """Normal case: queue item exists, returns it."""
        mock_item = Mock()
        service = Mock()
        service.queue_repo.get_by_id.return_value = mock_item
        query = AsyncMock()

        result = await validate_queue_item(service, "q-4", query)

        assert result is mock_item
        query.edit_message_caption.assert_not_called()
