"""Tests for telegram_utils shared utility functions."""

import pytest
from unittest.mock import AsyncMock

from src.services.core.telegram_utils import (
    build_account_management_keyboard,
    cleanup_conversation_messages,
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
