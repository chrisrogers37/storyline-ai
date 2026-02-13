# Phase 01: Refactor Account Add State Machine

**Status:** 🔧 IN PROGRESS
**Started:** 2026-02-12
**PR Title:** `refactor: extract state handlers from handle_add_account_message()`
**Risk Level:** Medium (refactoring async Telegram handler with user-facing state machine)
**Estimated Effort:** 2-3 hours
**Files Modified:**
- `src/services/core/telegram_accounts.py` (primary)
- `tests/src/services/test_telegram_accounts.py` (add tests)

## Dependencies
- None (first phase)

## Blocks
- Phase 04 (shared Telegram utilities extraction)

## Context

`handle_add_account_message()` in `telegram_accounts.py` (lines 167-482) is the single most complex function in the codebase: **315 lines, 6+ nesting levels, cyclomatic complexity ~12**. It contains a 3-branch state machine with duplicated message cleanup logic at 3 locations and deeply nested API validation. This makes it fragile to modify and impossible to unit test individual branches.

**Bug fix included:** Lines 427-463 contain an exception-variable shadowing bug where an inner `except Exception as e:` overwrites the outer API error, causing error messages to display message-deletion errors instead of the actual API failure.

## Current State

The method structure at lines 167-482:
```
handle_add_account_message(update, context)           # 315 lines
├── if state == "awaiting_display_name" (L177-205)    # 28 lines — save name, advance
├── elif state == "awaiting_account_id" (L207-243)    # 36 lines — validate numeric, advance
└── elif state == "awaiting_token" (L245-480)         # 235 lines — the monster
    ├── Delete token message (L252-255)
    ├── Send "verifying" message (L257-260)
    ├── try: (L262-425)
    │   ├── httpx API call (L268-286)                 # 6 levels deep
    │   ├── Create/update account (L288-317)
    │   ├── Cleanup messages [DUPLICATE 1] (L325-335)
    │   ├── Build keyboard [DUPLICATE] (L362-405)
    │   └── Send success message (L413-425)
    └── except: (L427-480)
        ├── Cleanup messages [DUPLICATE 2] (L434-444)
        ├── except Exception as e: [BUG] (L431)      # shadows outer e
        └── Send error message (L455-478)
```

Cancel handler at lines 484-503 has cleanup [DUPLICATE 3].

## Implementation Steps

### Step 1: Add `ADD_ACCOUNT_CANCEL_KEYBOARD` constant to `telegram_accounts.py`

**File:** `src/services/core/telegram_accounts.py`

Add as a module-level constant near the top of the file (after imports, before the class definition). This constant is only used within the add-account flow, so it belongs in this module — not in `telegram_utils.py`. YAGNI: if Phase 04 needs it shared later, it can be moved then.

```python
ADD_ACCOUNT_CANCEL_KEYBOARD = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton(
                "❌ Cancel", callback_data="account_add_cancel:cancel"
            )
        ]
    ]
)
```

**Note:** `InlineKeyboardButton` and `InlineKeyboardMarkup` are already imported in this file.

### Step 2: Move `import httpx` to module level

**File:** `src/services/core/telegram_accounts.py`

Move `import httpx` from inline (line 258, inside the token handler) to the top of the file after existing third-party imports. This enables clean patching in tests.

No changes needed to the `telegram_utils` import — `ADD_ACCOUNT_CANCEL_KEYBOARD` is now a local constant (Step 1).

### Step 3: Extract `_cleanup_conversation_messages()`

**New private method on `TelegramAccountHandlers`:**

```python
async def _cleanup_conversation_messages(
    self, context, chat_id: int, exclude_message_id: int | None = None
) -> None:
    """Delete tracked add-account conversation messages (best-effort).

    Args:
        context: Telegram CallbackContext with user_data containing message IDs.
        chat_id: Telegram chat ID to delete messages from.
        exclude_message_id: Optional message ID to skip (e.g., one being edited).
    """
    messages_to_delete = context.user_data.get("add_account_messages", [])
    for msg_id in messages_to_delete:
        if exclude_message_id is not None and msg_id == exclude_message_id:
            continue
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception as e:
            logger.debug(f"Could not delete conversation message {msg_id}: {e}")
```

### Step 4: Extract `_build_account_config_keyboard()`

**New private method:**

```python
def _build_account_config_keyboard(self, account_data: dict) -> InlineKeyboardMarkup:
    """Build the account list keyboard for the config menu.

    Args:
        account_data: Dict from ig_account_service.get_accounts_for_display().

    Returns:
        InlineKeyboardMarkup ready for use in Telegram messages.
    """
    keyboard = []

    if account_data["accounts"]:
        for account in account_data["accounts"]:
            is_active = account["id"] == account_data["active_account_id"]
            label = f"{'✅ ' if is_active else '   '}{account['display_name']}"
            if account["username"]:
                label += f" (@{account['username']})"
            keyboard.append(
                [InlineKeyboardButton(label, callback_data=f"switch_account:{account['id']}")]
            )
    else:
        keyboard.append(
            [InlineKeyboardButton("No accounts configured", callback_data="accounts_config:noop")]
        )

    keyboard.append([InlineKeyboardButton("➕ Add Account", callback_data="accounts_config:add")])

    if account_data["accounts"]:
        keyboard.append(
            [InlineKeyboardButton("🗑️ Remove Account", callback_data="accounts_config:remove")]
        )

    keyboard.append(
        [InlineKeyboardButton("↩️ Back to Settings", callback_data="settings_accounts:back")]
    )

    return InlineKeyboardMarkup(keyboard)
```

### Step 5: Extract `_handle_display_name_input()`

Extract the `awaiting_display_name` branch (lines 177-205) into its own method.

```python
async def _handle_display_name_input(self, update, context, message_text: str) -> bool:
    """Handle Step 1: display name input during add-account flow."""
    context.user_data["add_account_messages"].append(update.message.message_id)

    context.user_data["add_account_data"]["display_name"] = message_text
    context.user_data["add_account_state"] = "awaiting_account_id"

    reply = await update.message.reply_text(
        "➕ *Add Instagram Account*\n\n"
        "*Step 2 of 3: Instagram Account ID*\n\n"
        f"Display name: `{message_text}`\n\n"
        "Enter the numeric Account ID from Meta Business Suite:\n\n"
        "_Found in: Settings → Business Assets → Instagram Accounts_\n\n"
        "Reply with the ID",
        parse_mode="Markdown",
        reply_markup=ADD_ACCOUNT_CANCEL_KEYBOARD,
    )
    context.user_data["add_account_messages"].append(reply.message_id)
    return True
```

### Step 6: Extract `_handle_account_id_input()`

Extract the `awaiting_account_id` branch (lines 207-243).

```python
async def _handle_account_id_input(self, update, context, message_text: str) -> bool:
    """Handle Step 2: account ID input during add-account flow."""
    context.user_data["add_account_messages"].append(update.message.message_id)

    if not message_text.isdigit():
        reply = await update.message.reply_text(
            "⚠️ Account ID must be numeric. Please try again:",
            parse_mode="Markdown",
        )
        context.user_data["add_account_messages"].append(reply.message_id)
        return True

    context.user_data["add_account_data"]["account_id"] = message_text
    context.user_data["add_account_state"] = "awaiting_token"

    reply = await update.message.reply_text(
        "➕ *Add Instagram Account*\n\n"
        "*Step 3 of 3: Access Token*\n\n"
        f"Display name: `{context.user_data['add_account_data']['display_name']}`\n"
        f"Account ID: `{message_text}`\n\n"
        "⚠️ *Security*: Delete your token message after submitting.\n"
        "(Bots cannot delete user messages in private chats)\n\n"
        "Paste your Instagram Graph API access token:",
        parse_mode="Markdown",
        reply_markup=ADD_ACCOUNT_CANCEL_KEYBOARD,
    )
    context.user_data["add_account_messages"].append(reply.message_id)
    return True
```

### Step 7: Extract `_validate_instagram_credentials()`

Extract the API call and account create/update logic (lines 257-317).

```python
async def _validate_instagram_credentials(
    self, data: dict, access_token: str, user, chat_id: int
) -> tuple:
    """Validate credentials with Instagram API and create/update account.

    Returns:
        Tuple of (account, was_update).

    Raises:
        ValueError: If the API returns an error.
        httpx.HTTPError: On network failures.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://graph.facebook.com/v18.0/{data['account_id']}",
            params={"fields": "username", "access_token": access_token},
            timeout=30.0,
        )

        if response.status_code != 200:
            error_data = response.json()
            error_msg = error_data.get("error", {}).get("message", "Unknown error")
            raise ValueError(f"Instagram API error: {error_msg}")

        api_data = response.json()
        username = api_data.get("username")

        if not username:
            raise ValueError("Could not fetch username from Instagram API")

    existing = self.service.ig_account_service.get_account_by_instagram_id(data["account_id"])

    if existing:
        account = self.service.ig_account_service.update_account_token(
            instagram_account_id=data["account_id"],
            access_token=access_token,
            instagram_username=username,
            user=user,
            set_as_active=True,
            telegram_chat_id=chat_id,
        )
        return account, True
    else:
        account = self.service.ig_account_service.add_account(
            display_name=data["display_name"],
            instagram_account_id=data["account_id"],
            instagram_username=username,
            access_token=access_token,
            user=user,
            set_as_active=True,
            telegram_chat_id=chat_id,
        )
        return account, False
```

### Step 8: Extract `_handle_token_error()`

This **fixes the exception-shadowing bug** by receiving the error as an explicit parameter.

```python
async def _handle_token_error(
    self, context, chat_id: int, verifying_msg, error: Exception
) -> None:
    """Handle errors during token validation and account creation."""
    # Delete verifying message (best-effort)
    if verifying_msg:
        try:
            await verifying_msg.delete()
        except Exception as delete_err:
            logger.debug(f"Could not delete verifying message: {delete_err}")

    await self._cleanup_conversation_messages(context, chat_id)
    clear_add_account_state(context)

    keyboard = [
        [InlineKeyboardButton("🔄 Try Again", callback_data="accounts_config:add")],
        [InlineKeyboardButton("↩️ Back to Settings", callback_data="settings_accounts:back")],
    ]

    error_msg = str(error)
    if "Invalid OAuth" in error_msg or "access token" in error_msg.lower():
        error_msg = "Invalid or expired access token. Please check your token and try again."

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"❌ *Failed to add account*\n\n{error_msg}\n\n"
            "⚠️ *Security Note:* Please delete your messages above "
            "that contain sensitive data (Account ID, Access Token)."
        ),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    logger.error(f"Failed to add Instagram account: {error}")
```

### Step 9: Extract `_handle_token_input()`

Compose from the helpers above:

```python
async def _handle_token_input(self, update, context, message_text: str) -> bool:
    """Handle Step 3: access token input during add-account flow."""
    chat_id = update.effective_chat.id
    user = self.service._get_or_create_user(update.effective_user)

    # Delete the token message immediately for security
    try:
        await update.message.delete()
    except Exception as delete_err:
        logger.warning(f"Could not delete token message: {delete_err}")

    data = context.user_data["add_account_data"]
    verifying_msg = None

    try:
        verifying_msg = await context.bot.send_message(
            chat_id=chat_id,
            text="⏳ Verifying credentials with Instagram API...",
            parse_mode="Markdown",
        )

        account, was_update = await self._validate_instagram_credentials(
            data, message_text, user, chat_id
        )

        # Delete verifying message
        if verifying_msg:
            try:
                await verifying_msg.delete()
            except Exception:
                pass

        await self._cleanup_conversation_messages(context, chat_id)
        clear_add_account_state(context)

        # Log interaction
        action = "update_account_token" if was_update else "add_account"
        self.service.interaction_service.log_callback(
            user_id=str(user.id),
            callback_name=action,
            context={
                "account_id": str(account.id),
                "display_name": account.display_name,
                "username": account.instagram_username,
                "was_update": was_update,
            },
            telegram_chat_id=chat_id,
            telegram_message_id=update.message.message_id,
        )

        action_label = "updated token for" if was_update else "added"
        logger.info(
            f"User {self.service._get_display_name(user)} {action_label} Instagram account: "
            f"{account.display_name} (@{account.instagram_username})"
        )

        # Show success with account config keyboard
        account_data = self.service.ig_account_service.get_accounts_for_display(chat_id)
        reply_markup = self._build_account_config_keyboard(account_data)

        if was_update:
            action_msg = f"✅ *Updated token for @{account.instagram_username}*"
        else:
            action_msg = f"✅ *Added @{account.instagram_username}*"

        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"{action_msg}\n\n"
                "⚠️ *Security Note:* Please delete your messages above "
                "that contain the Account ID and Access Token. "
                "Bots cannot delete user messages in private chats.\n\n"
                "📸 *Configure Instagram Accounts*\n\n"
                "Select an account to make it active, or add/remove accounts."
            ),
            parse_mode="Markdown",
            reply_markup=reply_markup,
        )

    except Exception as e:
        await self._handle_token_error(context, chat_id, verifying_msg, e)

    return True
```

### Step 10: Rewrite `handle_add_account_message()` as dispatcher

Replace the entire 315-line method with:

```python
async def handle_add_account_message(self, update, context):
    """Handle text messages during add account conversation.

    Dispatches to the appropriate step handler based on conversation state.
    """
    if "add_account_state" not in context.user_data:
        return False

    state = context.user_data["add_account_state"]
    message_text = update.message.text.strip()

    if state == "awaiting_display_name":
        return await self._handle_display_name_input(update, context, message_text)
    elif state == "awaiting_account_id":
        return await self._handle_account_id_input(update, context, message_text)
    elif state == "awaiting_token":
        return await self._handle_token_input(update, context, message_text)

    return False
```

### Step 11: Simplify `handle_account_selection_menu()` (lines 36-98)

Replace the inline keyboard building with the helper:

```python
async def handle_account_selection_menu(self, user, query):
    """Show Instagram account configuration menu."""
    chat_id = query.message.chat_id
    account_data = self.service.ig_account_service.get_accounts_for_display(chat_id)
    reply_markup = self._build_account_config_keyboard(account_data)

    await query.edit_message_text(
        "📸 *Choose Default Account*\n\n"
        "Select an account to set as default, or add/remove accounts.",
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )
    await query.answer()
```

### Step 12: Simplify `handle_add_account_cancel()` (lines 484-503)

```python
async def handle_add_account_cancel(self, user, query, context):
    """Cancel add account flow."""
    chat_id = query.message.chat_id

    await self._cleanup_conversation_messages(
        context, chat_id, exclude_message_id=query.message.message_id
    )

    clear_add_account_state(context)
    await query.answer("Cancelled")
    await self.handle_account_selection_menu(user, query)
```

### Step 13: Add tests for extracted methods

**File:** `tests/src/services/test_telegram_accounts.py`

Add a new test class with at minimum these tests:

1. `test_handle_add_account_message_not_in_flow` — returns False when no state
2. `test_handle_display_name_input_advances_state` — saves name, advances to step 2
3. `test_handle_account_id_input_validates_numeric` — rejects non-numeric
4. `test_handle_account_id_input_saves_and_advances` — saves ID, advances to step 3
5. `test_handle_token_input_creates_account` — mock httpx, verify creation
6. `test_handle_token_input_updates_existing_account` — verify update path
7. `test_handle_token_input_api_error_shows_error` — verify error handling (validates bug fix)
8. `test_handle_token_input_deletes_token_message` — security verification
9. `test_cleanup_conversation_messages_deletes_tracked` — verify cleanup
10. `test_cleanup_conversation_messages_excludes_message` — verify exclude_id
11. `test_build_account_config_keyboard_with_accounts` — verify keyboard structure
12. `test_build_account_config_keyboard_no_accounts` — verify placeholder
13. `test_handle_token_input_logs_interaction` — verify `log_callback` receives correct action and context dict

Mock `httpx.AsyncClient` at `src.services.core.telegram_accounts.httpx.AsyncClient` (since httpx is now a module-level import).

## Verification Checklist

- [ ] All existing tests pass: `pytest tests/src/services/test_telegram_accounts.py -v`
- [ ] New tests added (13+ test methods minimum)
- [ ] Full test suite green: `pytest`
- [ ] Ruff lint clean: `ruff check src/services/core/telegram_accounts.py`
- [ ] Ruff format clean: `ruff format --check src/services/core/telegram_accounts.py`
- [ ] No behavior changes to public interface
- [ ] Exception-shadowing bug fixed (error messages show API error, not deletion error)
- [ ] `import httpx` moved to module level
- [ ] CHANGELOG.md updated

## Bug Fix Included

**Exception variable shadowing** (lines 427-463): The outer `except Exception as e:` catches the API error. Inside that handler, lines 431-432 have another `except Exception as e:` for message deletion, which reassigns `e`. Then `str(e)` at line 463 may show the deletion error instead of the API error. The fix passes the original exception as an explicit `error` parameter to `_handle_token_error()`.

## What NOT To Do

- **Do NOT change the public API** of `handle_add_account_message()` — it must still accept `(self, update, context)` and return `bool`. Call site at `telegram_service.py:558` depends on this.
- **Do NOT change callback_data strings** — routing in `telegram_service.py` depends on exact strings like `"accounts_config:add"`.
- **Do NOT merge `_cleanup_conversation_messages` into `clear_add_account_state`** — different responsibilities (async I/O vs sync dict clearing).
- **Do NOT extract the posting-workflow account selector keyboard** (`handle_post_account_selector`) — it uses different callback prefixes (`sap:`) and shortened UUIDs.
- **Do NOT change any methods outside the add-account flow** (remove, post-selector, etc.).
