# Phase 06: Refactor Callback Dispatcher to Dictionary Dispatch

**Status**: ✅ COMPLETE
**Started**: 2026-02-10
**Completed**: 2026-02-10

| Field | Value |
|-------|-------|
| **PR Title** | Refactor callback dispatcher to dictionary dispatch |
| **Risk Level** | Low |
| **Effort** | Medium (2-3 hours) |
| **Dependencies** | Phase 05 (telegram_utils extraction) |
| **Blocks** | None |
| **Files Modified** | `src/services/core/telegram_service.py` |

---

## Problem Description

The `_handle_callback()` method in `src/services/core/telegram_service.py` (lines 468-559) is a 90-line if-elif chain with 20+ branches. The method routes callback data from Telegram inline buttons to their respective handler methods. The current structure has these problems:

1. **Readability**: 20+ elif branches make it hard to see the full routing table at a glance. A new developer cannot quickly answer "what handler runs when the user clicks X?"

2. **Nesting depth**: Two actions (`settings_accounts` and `accounts_config`) have sub-routing logic nested inside the elif chain, reaching nesting depth of 5-8 levels:
   ```python
   elif action == "settings_accounts":
       if data == "select":
           await self.accounts.handle_account_selection_menu(user, query)
       elif data == "back":
           await self.settings_handler.refresh_settings_message(query)
   ```

3. **Inconsistent handler signatures**: Some handlers receive `(data, user, query)`, some receive `(user, query)`, some receive `(data, user, query, context)`, and one receives just `(query)`. The elif chain hides these differences. A dispatch table makes the signature requirements explicit.

4. **Growth pattern**: Every new callback action requires adding another elif branch in the middle of a long method. With dictionary dispatch, adding a new action is a single line in the table.

The method currently handles these actions (in order of appearance):

| Action | Handler | Signature |
|--------|---------|-----------|
| `posted` | `self.callbacks.handle_posted` | `(data, user, query)` |
| `skip` | `self.callbacks.handle_skipped` | `(data, user, query)` |
| `autopost` | `self.autopost.handle_autopost` | `(data, user, query)` |
| `back` | `self.callbacks.handle_back` | `(data, user, query)` |
| `reject` | `self.callbacks.handle_reject_confirmation` | `(data, user, query)` |
| `confirm_reject` | `self.callbacks.handle_rejected` | `(data, user, query)` |
| `cancel_reject` | `self.callbacks.handle_cancel_reject` | `(data, user, query)` |
| `resume` | `self.callbacks.handle_resume_callback` | `(data, user, query)` |
| `clear` | `self.callbacks.handle_reset_callback` | `(data, user, query)` |
| `settings_toggle` | `self.settings_handler.handle_settings_toggle` | `(data, user, query)` |
| `settings_refresh` | `self.settings_handler.refresh_settings_message` | `(query)` |
| `settings_edit` | `self.settings_handler.handle_settings_edit_start` | `(data, user, query, context)` |
| `settings_edit_cancel` | `self.settings_handler.handle_settings_edit_cancel` | `(query, context)` |
| `settings_close` | `self.settings_handler.handle_settings_close` | `(query)` |
| `schedule_action` | `self.settings_handler.handle_schedule_action` | `(data, user, query)` |
| `schedule_confirm` | `self.settings_handler.handle_schedule_confirm` | `(data, user, query)` |
| `settings_accounts` | sub-routed | depends on `data` |
| `switch_account` | `self.accounts.handle_account_switch` | `(data, user, query)` |
| `accounts_config` | sub-routed | depends on `data` |
| `account_remove` | `self.accounts.handle_account_remove_confirm` | `(data, user, query)` |
| `account_remove_confirmed` | `self.accounts.handle_account_remove_execute` | `(data, user, query)` |
| `account_add_cancel` | `self.accounts.handle_add_account_cancel` | `(user, query, context)` |
| `select_account` | `self.accounts.handle_post_account_selector` | `(data, user, query)` |
| `sap` | `self.accounts.handle_post_account_switch` | `(data, user, query)` |
| `btp` | `self.accounts.handle_back_to_post` | `(data, user, query)` |

---

## Step-by-Step Implementation

### Step 1: Add the dispatch table initialization method

Open `src/services/core/telegram_service.py`. Add a new private method `_build_callback_dispatch_table()` to the `TelegramService` class. Place it after the `initialize()` method (after line 169) and before `send_notification()`.

```python
    def _build_callback_dispatch_table(self) -> dict:
        """Build the callback action dispatch table.

        Returns a dictionary mapping action strings to handler coroutines.
        All handlers in this table use the standard (data, user, query) signature.

        Actions that need special signatures (context, sub-routing, etc.) are
        NOT in this table -- they are handled in _handle_callback_special_cases().
        """
        return {
            # Queue item actions (telegram_callbacks.py)
            "posted": self.callbacks.handle_posted,
            "skip": self.callbacks.handle_skipped,
            "back": self.callbacks.handle_back,
            "reject": self.callbacks.handle_reject_confirmation,
            "confirm_reject": self.callbacks.handle_rejected,
            "cancel_reject": self.callbacks.handle_cancel_reject,
            "resume": self.callbacks.handle_resume_callback,
            "clear": self.callbacks.handle_reset_callback,  # Legacy name for reset
            # Auto-post (telegram_autopost.py)
            "autopost": self.autopost.handle_autopost,
            # Settings (telegram_settings.py)
            "settings_toggle": self.settings_handler.handle_settings_toggle,
            "schedule_action": self.settings_handler.handle_schedule_action,
            "schedule_confirm": self.settings_handler.handle_schedule_confirm,
            # Account management (telegram_accounts.py)
            "switch_account": self.accounts.handle_account_switch,
            "account_remove": self.accounts.handle_account_remove_confirm,
            "account_remove_confirmed": self.accounts.handle_account_remove_execute,
            "select_account": self.accounts.handle_post_account_selector,
            "sap": self.accounts.handle_post_account_switch,
            "btp": self.accounts.handle_back_to_post,
        }
```

### Step 2: Add the special-cases handler method

Add a new method for actions that do not use the standard `(data, user, query)` signature. Place it right after `_build_callback_dispatch_table()`.

```python
    async def _handle_callback_special_cases(self, action, data, user, query, context):
        """Handle callback actions that need special signatures or sub-routing.

        Returns True if the action was handled, False if not recognized.

        Special cases:
        - settings_refresh: takes only (query)
        - settings_edit: takes (data, user, query, context)
        - settings_edit_cancel: takes (query, context)
        - settings_close: takes only (query)
        - settings_accounts: has sub-routing based on data value
        - accounts_config: has sub-routing based on data value
        - account_add_cancel: takes (user, query, context)
        """
        if action == "settings_refresh":
            await self.settings_handler.refresh_settings_message(query)
            return True

        elif action == "settings_edit":
            await self.settings_handler.handle_settings_edit_start(
                data, user, query, context
            )
            return True

        elif action == "settings_edit_cancel":
            await self.settings_handler.handle_settings_edit_cancel(query, context)
            return True

        elif action == "settings_close":
            await self.settings_handler.handle_settings_close(query)
            return True

        elif action == "settings_accounts":
            if data == "select":
                await self.accounts.handle_account_selection_menu(user, query)
            elif data == "back":
                await self.settings_handler.refresh_settings_message(query)
            return True

        elif action == "accounts_config":
            if data == "add":
                await self.accounts.handle_add_account_start(user, query, context)
            elif data == "remove":
                await self.accounts.handle_remove_account_menu(user, query)
            elif data == "noop":
                await query.answer()
            return True

        elif action == "account_add_cancel":
            await self.accounts.handle_add_account_cancel(user, query, context)
            return True

        return False
```

### Step 3: Call `_build_callback_dispatch_table()` from `initialize()`

In the `initialize()` method, add the dispatch table initialization after the sub-handlers are created (after line 117: `self.accounts = TelegramAccountHandlers(self)`).

**BEFORE** (lines 113-118):

```python
        self.commands = TelegramCommandHandlers(self)
        self.callbacks = TelegramCallbackHandlers(self)
        self.autopost = TelegramAutopostHandler(self)
        self.settings_handler = TelegramSettingsHandlers(self)
        self.accounts = TelegramAccountHandlers(self)

        # Register command handlers
```

**AFTER**:

```python
        self.commands = TelegramCommandHandlers(self)
        self.callbacks = TelegramCallbackHandlers(self)
        self.autopost = TelegramAutopostHandler(self)
        self.settings_handler = TelegramSettingsHandlers(self)
        self.accounts = TelegramAccountHandlers(self)

        # Build callback dispatch table (must be after handlers are initialized)
        self._callback_dispatch = self._build_callback_dispatch_table()

        # Register command handlers
```

### Step 4: Replace the entire `_handle_callback()` method

Replace the current `_handle_callback()` method (lines 468-559) with the refactored version.

**BEFORE** (lines 468-559, the complete current method):

```python
    async def _handle_callback(self, update, context):
        """Handle inline button callbacks."""
        try:
            query = update.callback_query

            # Debug: Log ALL callback data to diagnose routing issues
            logger.info(f"\U0001f4de Callback received: {query.data}")

            await query.answer()

            # Parse callback data
            # Split on FIRST colon only, so data can contain multiple colons (e.g., sap:queue_id:account_id)
            parts = query.data.split(":", 1)
            action = parts[0]
            data = parts[1] if len(parts) > 1 else None

            logger.info(f"\U0001f4de Parsed action='{action}', data='{data}'")

            # Get user info
            user = self._get_or_create_user(query.from_user)

            # Queue item callbacks (dispatched to telegram_callbacks.py)
            if action == "posted":
                await self.callbacks.handle_posted(data, user, query)
            elif action == "skip":
                await self.callbacks.handle_skipped(data, user, query)
            elif action == "autopost":
                await self.autopost.handle_autopost(data, user, query)
            elif action == "back":
                await self.callbacks.handle_back(data, user, query)
            elif action == "reject":
                await self.callbacks.handle_reject_confirmation(data, user, query)
            elif action == "confirm_reject":
                await self.callbacks.handle_rejected(data, user, query)
            elif action == "cancel_reject":
                await self.callbacks.handle_cancel_reject(data, user, query)
            # Resume callbacks (dispatched to telegram_callbacks.py)
            elif action == "resume":
                await self.callbacks.handle_resume_callback(data, user, query)
            # Reset queue callbacks (callback data still uses "clear" for backwards compat)
            elif action == "clear":
                await self.callbacks.handle_reset_callback(data, user, query)
            # Settings callbacks (dispatched to telegram_settings.py)
            elif action == "settings_toggle":
                await self.settings_handler.handle_settings_toggle(data, user, query)
            elif action == "settings_refresh":
                await self.settings_handler.refresh_settings_message(query)
            elif action == "settings_edit":
                await self.settings_handler.handle_settings_edit_start(
                    data, user, query, context
                )
            elif action == "settings_edit_cancel":
                await self.settings_handler.handle_settings_edit_cancel(query, context)
            elif action == "settings_close":
                await self.settings_handler.handle_settings_close(query)
            # Schedule management callbacks (dispatched to telegram_settings.py)
            elif action == "schedule_action":
                await self.settings_handler.handle_schedule_action(data, user, query)
            elif action == "schedule_confirm":
                await self.settings_handler.handle_schedule_confirm(data, user, query)
            # Instagram account selection callbacks (dispatched to telegram_accounts.py)
            elif action == "settings_accounts":
                if data == "select":
                    await self.accounts.handle_account_selection_menu(user, query)
                elif data == "back":
                    await self.settings_handler.refresh_settings_message(query)
            elif action == "switch_account":
                await self.accounts.handle_account_switch(data, user, query)
            # Instagram account configuration callbacks (dispatched to telegram_accounts.py)
            elif action == "accounts_config":
                if data == "add":
                    await self.accounts.handle_add_account_start(user, query, context)
                elif data == "remove":
                    await self.accounts.handle_remove_account_menu(user, query)
                elif data == "noop":
                    await query.answer()
            elif action == "account_remove":
                await self.accounts.handle_account_remove_confirm(data, user, query)
            elif action == "account_remove_confirmed":
                await self.accounts.handle_account_remove_execute(data, user, query)
            elif action == "account_add_cancel":
                await self.accounts.handle_add_account_cancel(user, query, context)
            # Inline account selection from posting workflow (Phase 1.7)
            elif action == "select_account":
                await self.accounts.handle_post_account_selector(data, user, query)
            elif action == "sap":  # switch_account_post (shortened for callback limit)
                await self.accounts.handle_post_account_switch(data, user, query)
            elif action == "btp":  # back_to_post (shortened for callback limit)
                await self.accounts.handle_back_to_post(data, user, query)
        finally:
            # Clean up open transactions to prevent "idle in transaction"
            self.cleanup_transactions()
```

**AFTER** (the complete refactored method):

```python
    async def _handle_callback(self, update, context):
        """Handle inline button callbacks.

        Uses a two-tier dispatch approach:
        1. Dictionary lookup for standard (data, user, query) handlers
        2. Special-case method for handlers with non-standard signatures or sub-routing
        """
        try:
            query = update.callback_query

            logger.info(f"\U0001f4de Callback received: {query.data}")

            await query.answer()

            # Parse callback data
            # Split on FIRST colon only, so data can contain colons (e.g., sap:queue_id:account_id)
            parts = query.data.split(":", 1)
            action = parts[0]
            data = parts[1] if len(parts) > 1 else None

            logger.info(f"\U0001f4de Parsed action='{action}', data='{data}'")

            # Get user info
            user = self._get_or_create_user(query.from_user)

            # Tier 1: Standard dispatch (data, user, query) handlers
            handler = self._callback_dispatch.get(action)
            if handler:
                await handler(data, user, query)
                return

            # Tier 2: Special cases (non-standard signatures, sub-routing)
            handled = await self._handle_callback_special_cases(
                action, data, user, query, context
            )
            if handled:
                return

            logger.warning(f"Unknown callback action: {action}")

        finally:
            # Clean up open transactions to prevent "idle in transaction"
            self.cleanup_transactions()
```

### Step 5: Verify no other references to the old structure

Search for any code that references `_handle_callback` to ensure nothing depends on the internal structure of the method:

```bash
grep -rn "_handle_callback" src/
```

Expected results:
- `telegram_service.py` line 141: `self.application.add_handler(CallbackQueryHandler(self._handle_callback))` -- this is the registration point and does not change.

No other files should reference `_handle_callback`.

---

## Verification Checklist

- [ ] `ruff check src/services/core/telegram_service.py` passes
- [ ] `ruff format --check src/services/core/telegram_service.py` passes
- [ ] `pytest tests/src/services/test_telegram_service.py` passes
- [ ] `pytest tests/src/services/test_telegram_callbacks.py` passes
- [ ] `pytest tests/src/services/test_telegram_accounts.py` passes
- [ ] `pytest tests/src/services/test_telegram_settings.py` passes
- [ ] `pytest` full test suite passes
- [ ] The `_callback_dispatch` dictionary contains exactly 20 entries (count the keys)
- [ ] The `_handle_callback_special_cases` method handles exactly 7 actions: `settings_refresh`, `settings_edit`, `settings_edit_cancel`, `settings_close`, `settings_accounts`, `accounts_config`, `account_add_cancel`
- [ ] All 27 callback actions from the original elif chain are accounted for (20 in dispatch + 7 in special cases = 27 total)
- [ ] The `_callback_dispatch` table is initialized in `initialize()`, AFTER `self.commands`, `self.callbacks`, `self.autopost`, `self.settings_handler`, and `self.accounts` are created
- [ ] The `finally: self.cleanup_transactions()` block is preserved
- [ ] The `query.data.split(":", 1)` parsing logic is preserved (first colon only)
- [ ] The `logger.info` calls for callback debugging are preserved
- [ ] `await query.answer()` is still called before any dispatch
- [ ] Unknown actions now log a warning instead of being silently ignored

**Manual testing** (if bot is running in dry-run mode):

- [ ] Click "Posted" button on a queue item notification
- [ ] Click "Skip" button
- [ ] Click "Reject" button, then "Yes" to confirm
- [ ] Click "Reject" button, then "No" to cancel
- [ ] Click account selector button, select an account, click "Back to Post"
- [ ] Open `/settings`, toggle Dry Run, toggle Verbose, edit Posts/Day
- [ ] Open `/settings`, click "Regenerate", then cancel
- [ ] Open `/settings`, click "+7 Days"

---

## What NOT To Do

1. **Do NOT initialize `_callback_dispatch` as a class-level attribute.** The dispatch table references `self.callbacks`, `self.autopost`, `self.settings_handler`, and `self.accounts`, which are only created during `initialize()`. If you try to build the table in `__init__()`, these attributes will not exist yet and you will get `AttributeError`. The table MUST be built after the handlers are initialized.

2. **Do NOT use `lambda` wrappers in the dispatch table.** For example, do NOT write:
   ```python
   "settings_refresh": lambda d, u, q: self.settings_handler.refresh_settings_message(q),
   ```
   This hides the actual function signature and makes debugging harder. Instead, keep handlers with non-standard signatures in `_handle_callback_special_cases()` where the signature adaptation is explicit and documented.

3. **Do NOT merge the special cases into the dispatch table using adapter functions.** It is tempting to create wrapper functions so that all 27 actions live in one dictionary. Do not do this. The explicit separation between "standard signature" and "special cases" documents the interface contract and makes it immediately obvious which handlers need `context` or have sub-routing.

4. **Do NOT change the `query.data.split(":", 1)` parsing.** The first-colon-only split is critical for actions like `sap` which encode multiple IDs: `sap:queue_id:account_id`. Changing this to `split(":")` would break account selection in the posting workflow.

5. **Do NOT remove the `await query.answer()` call.** Telegram requires that every callback query be answered to dismiss the loading spinner on the button. This must happen before dispatch, not inside individual handlers, because some handlers may edit the message before answering.

6. **Do NOT add error handling inside individual dispatch entries.** The `try/finally` block in `_handle_callback` already ensures transaction cleanup. Adding try/except inside the dispatch would duplicate error handling and could mask bugs.

7. **Do NOT change the `logger.info` format strings.** The emoji prefix `\U0001f4de` and the format `Parsed action='{action}', data='{data}'` are used for debugging callback routing issues in production logs. Changing them would break existing log searches and dashboards.

8. **Do NOT reorder the dispatch table entries.** While Python dicts are insertion-ordered since 3.7, the logical grouping (queue actions, auto-post, settings, accounts) matches the comments in the original elif chain and makes the table scannable. Maintain these groups with comment headers as shown in the implementation.

9. **Do NOT add a catch-all `else` that raises an exception.** The `logger.warning(f"Unknown callback action: {action}")` is the correct behavior. Telegram may deliver callbacks for buttons from old messages that reference actions that have since been renamed or removed. Raising an exception would crash the bot; logging a warning lets the operator investigate.
