# Phase 04: Extract Shared Telegram Handler Utilities

**Status:** ✅ COMPLETE
**Started:** 2026-02-12
**Completed:** 2026-02-12
**PR Title:** `refactor: extract shared Telegram handler utilities`
**Risk Level:** Low
**Estimated Effort:** 1-2 hours
**Files Modified:**
- `src/services/core/telegram_utils.py` (add 2 utility functions + logger import)
- `src/services/core/telegram_accounts.py` (replace 3 keyboard builds + 3 cleanup loops)
- `tests/src/services/test_telegram_utils.py` (new test file)

## Dependencies
- Phase 01 (telegram_accounts refactor — creates cleanup helper to generalize)
- Phase 03 (autopost/commands refactor — creates extraction points)

## Blocks
- None

## Context

Two patterns are duplicated across Telegram handler files:

**Pattern 1: Account Management Keyboard Building** (~45 lines duplicated 2x)
- `handle_account_selection_menu()` in `telegram_accounts.py` (lines 40-91)
- Add-account success path in `telegram_accounts.py` (lines 362-405)

Both build the same keyboard: account rows with active checkmark → "Add Account" button → "Remove Account" button (conditional) → "Back to Settings" button.

**Pattern 2: Conversation Message Cleanup** (~10 lines duplicated 3x)
- Success path in `handle_add_account_message()` (lines 325-335)
- Error path in `handle_add_account_message()` (lines 434-444)
- Cancel handler `handle_add_account_cancel()` (lines 488-498, with `exclude_id` variant)

All three iterate over `context.user_data["add_account_messages"]`, delete each message via bot API, and silently catch exceptions.

## Implementation Steps

### Step 1: Add `build_account_management_keyboard()` to `telegram_utils.py`

**File:** `src/services/core/telegram_utils.py`

Add after the existing `clear_add_account_state` function (after line 261):

```python
# =========================================================================
# Pattern 5: Account Management Keyboard
# =========================================================================


def build_account_management_keyboard(
    account_data: dict,
) -> list[list[InlineKeyboardButton]]:
    """Build the account list rows + management buttons for the accounts config menu.

    Produces the keyboard rows used by both handle_account_selection_menu()
    and the add-account success confirmation. The caller wraps the result
    in InlineKeyboardMarkup and may prepend/append additional rows.

    The returned rows include:
    1. One row per account with active-checkmark label and switch_account callback
    2. "No accounts configured" placeholder if no accounts exist
    3. "Add Account" button
    4. "Remove Account" button (only if accounts exist)
    5. "Back to Settings" button

    Args:
        account_data: Dict from ig_account_service.get_accounts_for_display(),
                      must contain keys "accounts" (list of dicts with id,
                      display_name, username) and "active_account_id" (str or None).

    Returns:
        List of keyboard rows (list of lists of InlineKeyboardButton).
        The caller wraps this in InlineKeyboardMarkup.
    """
    keyboard: list[list[InlineKeyboardButton]] = []

    # Account selection rows
    if account_data["accounts"]:
        for account in account_data["accounts"]:
            is_active = account["id"] == account_data["active_account_id"]
            label = f"{'✅ ' if is_active else '   '}{account['display_name']}"
            if account["username"]:
                label += f" (@{account['username']})"
            keyboard.append(
                [
                    InlineKeyboardButton(
                        label, callback_data=f"switch_account:{account['id']}"
                    )
                ]
            )
    else:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "No accounts configured", callback_data="accounts_config:noop"
                )
            ]
        )

    # Action buttons
    keyboard.append(
        [
            InlineKeyboardButton(
                "➕ Add Account", callback_data="accounts_config:add"
            ),
        ]
    )

    if account_data["accounts"]:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "🗑️ Remove Account", callback_data="accounts_config:remove"
                ),
            ]
        )

    keyboard.append(
        [
            InlineKeyboardButton(
                "↩️ Back to Settings", callback_data="settings_accounts:back"
            )
        ]
    )

    return keyboard
```

### Step 2: Add `cleanup_conversation_messages()` to `telegram_utils.py`

Add after `build_account_management_keyboard`:

```python
# =========================================================================
# Pattern 6: Conversation Message Cleanup
# =========================================================================


async def cleanup_conversation_messages(
    bot,
    chat_id: int,
    message_ids: list[int],
    exclude_id: int | None = None,
) -> int:
    """Delete a list of tracked conversation messages (best-effort).

    Iterates through message_ids and attempts to delete each one via the
    Telegram Bot API. Failures are logged at DEBUG level and silently
    ignored (the message may have been already deleted or be inaccessible).

    Args:
        bot: The telegram.Bot instance (context.bot).
        chat_id: The Telegram chat ID to delete messages from.
        message_ids: List of message IDs to delete.
        exclude_id: Optional message ID to skip (e.g., a message that will
                    be edited instead of deleted). If None, all IDs are deleted.

    Returns:
        The number of messages successfully deleted.
    """
    deleted = 0
    for msg_id in message_ids:
        if exclude_id is not None and msg_id == exclude_id:
            continue
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
            deleted += 1
        except Exception as e:
            logger.debug(f"Could not delete conversation message {msg_id}: {e}")
    return deleted
```

**Also add the logger import** at the top of `telegram_utils.py` (around line 11, after existing imports):

```python
from src.utils.logger import logger
```

### Step 3: Update imports in `telegram_accounts.py`

**BEFORE** (lines 9-14):
```python
from src.services.core.telegram_utils import (
    build_queue_action_keyboard,
    clear_add_account_state,
    validate_queue_and_media,
    validate_queue_item,
)
```

**AFTER**:
```python
from src.services.core.telegram_utils import (
    build_account_management_keyboard,
    build_queue_action_keyboard,
    cleanup_conversation_messages,
    clear_add_account_state,
    validate_queue_and_media,
    validate_queue_item,
)
```

### Step 4: Replace `handle_account_selection_menu()` keyboard building (lines 40-91)

**BEFORE** (lines 36-98):
```python
    async def handle_account_selection_menu(self, user, query):
        """Show Instagram account configuration menu."""
        chat_id = query.message.chat_id
        account_data = self.service.ig_account_service.get_accounts_for_display(chat_id)

        # Build account management keyboard
        keyboard = []

        # List existing accounts with select option
        if account_data["accounts"]:
            for account in account_data["accounts"]:
                is_active = account["id"] == account_data["active_account_id"]
                label = f"{'✅ ' if is_active else '   '}{account['display_name']}"
                if account["username"]:
                    label += f" (@{account['username']})"
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            label, callback_data=f"switch_account:{account['id']}"
                        )
                    ]
                )
        else:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "No accounts configured", callback_data="accounts_config:noop"
                    )
                ]
            )

        # Action buttons row
        keyboard.append(
            [
                InlineKeyboardButton(
                    "➕ Add Account", callback_data="accounts_config:add"
                ),
            ]
        )

        # Only show remove option if there are accounts
        if account_data["accounts"]:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "🗑️ Remove Account", callback_data="accounts_config:remove"
                    ),
                ]
            )

        # Back button
        keyboard.append(
            [
                InlineKeyboardButton(
                    "↩️ Back to Settings", callback_data="settings_accounts:back"
                )
            ]
        )

        await query.edit_message_text(
            "📸 *Choose Default Account*\n\n"
            "Select an account to set as default, or add/remove accounts.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        await query.answer()
```

**AFTER**:
```python
    async def handle_account_selection_menu(self, user, query):
        """Show Instagram account configuration menu."""
        chat_id = query.message.chat_id
        account_data = self.service.ig_account_service.get_accounts_for_display(chat_id)

        keyboard = build_account_management_keyboard(account_data)

        await query.edit_message_text(
            "📸 *Choose Default Account*\n\n"
            "Select an account to set as default, or add/remove accounts.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        await query.answer()
```

### Step 5: Replace add-account success keyboard building (lines 362-405)

**BEFORE** (lines 362-405, inside `handle_add_account_message()` success path):
```python
                # Show Configure Accounts menu with success message
                account_data = self.service.ig_account_service.get_accounts_for_display(
                    chat_id
                )
                keyboard = []

                for acc in account_data["accounts"]:
                    is_active = acc["id"] == account_data["active_account_id"]
                    label = f"{'✅ ' if is_active else '   '}{acc['display_name']}"
                    if acc["username"]:
                        label += f" (@{acc['username']})"
                    keyboard.append(
                        [
                            InlineKeyboardButton(
                                label,
                                callback_data=f"switch_account:{acc['id']}",
                            )
                        ]
                    )

                keyboard.append(
                    [
                        InlineKeyboardButton(
                            "➕ Add Account", callback_data="accounts_config:add"
                        ),
                    ]
                )
                if account_data["accounts"]:
                    keyboard.append(
                        [
                            InlineKeyboardButton(
                                "🗑️ Remove Account",
                                callback_data="accounts_config:remove",
                            ),
                        ]
                    )
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            "↩️ Back to Settings",
                            callback_data="settings_accounts:back",
                        )
                    ]
                )
```

**AFTER**:
```python
                # Show Configure Accounts menu with success message
                account_data = self.service.ig_account_service.get_accounts_for_display(
                    chat_id
                )
                keyboard = build_account_management_keyboard(account_data)
```

The `await context.bot.send_message(...)` call that follows remains unchanged — it already uses `InlineKeyboardMarkup(keyboard)` as `reply_markup`.

### Step 6: Replace message cleanup loops (3 locations)

**Location A** — Success path, lines 325-335:

**BEFORE**:
```python
                # Delete all tracked conversation messages
                messages_to_delete = context.user_data.get("add_account_messages", [])
                for msg_id in messages_to_delete:
                    try:
                        await context.bot.delete_message(
                            chat_id=chat_id, message_id=msg_id
                        )
                    except Exception as e:
                        logger.debug(
                            f"Could not delete conversation message {msg_id}: {e}"
                        )
```

**AFTER**:
```python
                # Delete all tracked conversation messages
                messages_to_delete = context.user_data.get("add_account_messages", [])
                await cleanup_conversation_messages(
                    context.bot, chat_id, messages_to_delete
                )
```

**Location B** — Error path, lines 434-444:

**BEFORE**:
```python
                # Delete all tracked conversation messages
                messages_to_delete = context.user_data.get("add_account_messages", [])
                for msg_id in messages_to_delete:
                    try:
                        await context.bot.delete_message(
                            chat_id=chat_id, message_id=msg_id
                        )
                    except Exception as e:
                        logger.debug(
                            f"Could not delete conversation message {msg_id} during error cleanup: {e}"
                        )
```

**AFTER**:
```python
                # Delete all tracked conversation messages
                messages_to_delete = context.user_data.get("add_account_messages", [])
                await cleanup_conversation_messages(
                    context.bot, chat_id, messages_to_delete
                )
```

**Location C** — Cancel handler, lines 488-498:

**BEFORE**:
```python
        # Delete all tracked conversation messages (except the current one which we'll edit)
        messages_to_delete = context.user_data.get("add_account_messages", [])
        current_msg_id = query.message.message_id
        for msg_id in messages_to_delete:
            if msg_id != current_msg_id:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                except Exception as e:
                    logger.debug(
                        f"Could not delete conversation message {msg_id} during cancel: {e}"
                    )
```

**AFTER**:
```python
        # Delete all tracked conversation messages (except the current one which we'll edit)
        messages_to_delete = context.user_data.get("add_account_messages", [])
        await cleanup_conversation_messages(
            context.bot, chat_id, messages_to_delete, exclude_id=query.message.message_id
        )
```

### Step 7: Write unit tests for the new utilities

Create `tests/src/services/test_telegram_utils.py`:

```python
"""Tests for telegram_utils shared utility functions."""

import pytest
from unittest.mock import AsyncMock, Mock

from telegram import InlineKeyboardButton

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
        result = await cleanup_conversation_messages(
            bot, chat_id=123, message_ids=[]
        )

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
```

## Verification Checklist

- [x] `ruff check src/services/core/telegram_utils.py` passes
- [x] `ruff check src/services/core/telegram_accounts.py` passes
- [x] `ruff format --check src/services/core/` passes
- [x] `pytest tests/src/services/test_telegram_utils.py` passes (all new tests)
- [x] `pytest tests/src/services/test_telegram_accounts.py` passes (all existing tests)
- [x] `pytest tests/src/services/test_telegram_settings.py` passes (unchanged but imports from same module)
- [x] `pytest` full test suite passes (762 passed, 38 skipped)
- [x] No remaining `for acc in account_data["accounts"]` / `for account in account_data["accounts"]` pattern with `switch_account:` callback in `telegram_accounts.py` except inside `handle_post_account_selector` (which uses `sap:` callbacks and is intentionally not extracted)
- [x] No remaining `for msg_id in messages_to_delete` loops in `telegram_accounts.py`
- [x] `telegram_accounts.py` imports `build_account_management_keyboard` and `cleanup_conversation_messages` from `telegram_utils`
- [x] `telegram_utils.py` imports `logger` from `src.utils.logger`
- [x] Keyboard button text, callback_data values, and button ordering are identical to the originals
- [x] `build_account_management_keyboard` is a pure function (no service calls, no side effects)
- [x] `cleanup_conversation_messages` is an async function that returns the count of deleted messages
- [x] CHANGELOG.md updated

## What NOT To Do

1. **Do NOT extract the `handle_post_account_selector` keyboard building (lines 628-653).** That variant uses shortened UUIDs and `sap:` callback prefixes for Telegram's 64-byte callback limit. Forcing it into `build_account_management_keyboard` would require complex parameterization. The added complexity outweighs the deduplication benefit for a single call site.

2. **Do NOT extract the `handle_remove_account_menu` keyboard building (lines 510-525).** That variant uses different label formatting (trash emoji prefix, "ACTIVE" warning suffix) and `account_remove:` callbacks. It is a distinct UI pattern, not a duplicate.

3. **Do NOT move `_escape_markdown` or `_extract_button_labels` into `telegram_utils.py` in this phase.** Those functions are defined in `telegram_service.py` and imported from there by other modules. Moving them would touch additional files and tests.

4. **Do NOT add the `logger` import via a wildcard or barrel import.** Use the explicit `from src.utils.logger import logger` form consistent with every other module.

5. **Do NOT change the numeric validation patterns.** The `isdigit()` calls in `telegram_accounts.py` and `telegram_commands.py` are used in completely different contexts. They are not truly duplicated logic.

6. **Do NOT make `build_account_management_keyboard` accept `InlineKeyboardMarkup` directly.** Return raw rows so the caller retains flexibility to prepend/append custom rows before wrapping.

7. **Do NOT change `cleanup_conversation_messages` to access `context.user_data` directly.** The function should receive a plain list of message IDs. This keeps it testable without mocking Telegram internals.

8. **Do NOT add business logic to `telegram_utils.py`.** This module contains only UI-level utilities. No database queries, no posting logic, no interaction logging.
