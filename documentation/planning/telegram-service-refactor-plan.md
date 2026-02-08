# Telegram Service Refactor Plan

> **Status**: Planning
> **Created**: 2026-02-08
> **Target File**: `src/services/core/telegram_service.py` (3,503 lines)
> **Test File**: `tests/src/services/test_telegram_service.py` (2,428 lines, 27 test classes, ~80 tests)

---

## 1. Problem Statement

`TelegramService` is a 3,503-line monolith handling six distinct responsibilities:
1. **Commands** — 14 `/command` handlers
2. **Callbacks** — Queue action callbacks (posted, skipped, rejected, resume, reset)
3. **Auto-posting** — Instagram API posting flow with safety gates
4. **Settings** — Settings UI, schedule management, conversation flows for edits
5. **Account management** — Add/remove/switch accounts (both from settings and inline post workflow)
6. **Core orchestration** — Lifecycle, notifications, captions, callback routing, user management

The file is difficult to navigate, review, and modify. Each concern has its own natural boundary, making it a clear candidate for decomposition.

---

## 2. Method Inventory

### Complete method listing with proposed destination

| Line | Method | Current Responsibility | Proposed Module |
|------|--------|----------------------|-----------------|
| 30 | `_escape_markdown()` (module-level) | Utility | `telegram_service.py` |
| 36 | `_extract_button_labels()` (module-level) | Utility | `telegram_service.py` |
| 50 | `__init__()` | Setup | `telegram_service.py` |
| 66 | `is_paused` (property) | State | `telegram_service.py` |
| 72 | `set_paused()` | State | `telegram_service.py` |
| 77 | `initialize()` | Handler registration | `telegram_service.py` |
| 128 | `send_notification()` | Notification | `telegram_service.py` |
| 263 | `_build_caption()` | Caption building | `telegram_service.py` |
| 289 | `_build_simple_caption()` | Caption building | `telegram_service.py` |
| 326 | `_build_enhanced_caption()` | Caption building | `telegram_service.py` |
| 376 | `_get_header_emoji()` | Caption building | `telegram_service.py` |
| 397 | `_handle_start()` | Command | `telegram_commands.py` |
| 419 | `_handle_status()` | Command | `telegram_commands.py` |
| 492 | `_handle_queue()` | Command | `telegram_commands.py` |
| 540 | `_handle_next()` | Command | `telegram_commands.py` |
| 601 | `_handle_help()` | Command | `telegram_commands.py` |
| 641 | `_handle_conversation_message()` | Message routing | `telegram_service.py` |
| 661 | `_handle_dryrun()` | Command | `telegram_commands.py` |
| 725 | `_build_settings_message_and_keyboard()` | Settings UI | `telegram_settings.py` |
| 800 | `_handle_settings()` | Command (settings) | `telegram_settings.py` |
| 819 | `_handle_settings_toggle()` | Settings callback | `telegram_settings.py` |
| 843 | `_refresh_settings_message()` | Settings UI | `telegram_settings.py` |
| 856 | `_handle_settings_close()` | Settings callback | `telegram_settings.py` |
| 864 | `_handle_settings_edit_start()` | Settings conversation | `telegram_settings.py` |
| 913 | `_handle_settings_edit_message()` | Settings conversation | `telegram_settings.py` |
| 1076 | `_handle_settings_edit_cancel()` | Settings callback | `telegram_settings.py` |
| 1088 | `_send_settings_message_by_chat_id()` | Settings UI | `telegram_settings.py` |
| 1099 | `_handle_schedule_action()` | Settings callback | `telegram_settings.py` |
| 1167 | `_handle_schedule_confirm()` | Settings callback | `telegram_settings.py` |
| 1222 | `_handle_account_selection_menu()` | Account mgmt | `telegram_accounts.py` |
| 1289 | `_handle_account_switch()` | Account mgmt | `telegram_accounts.py` |
| 1317 | `_handle_add_account_start()` | Account mgmt | `telegram_accounts.py` |
| 1349 | `_handle_add_account_message()` | Account conversation | `telegram_accounts.py` |
| 1661 | `_handle_add_account_cancel()` | Account mgmt | `telegram_accounts.py` |
| 1683 | `_handle_remove_account_menu()` | Account mgmt | `telegram_accounts.py` |
| 1718 | `_handle_account_remove_confirm()` | Account mgmt | `telegram_accounts.py` |
| 1749 | `_handle_account_remove_execute()` | Account mgmt | `telegram_accounts.py` |
| 1782 | `_handle_pause()` | Command | `telegram_commands.py` |
| 1812 | `_handle_resume()` | Command | `telegram_commands.py` |
| 1871 | `_handle_schedule()` | Command | `telegram_commands.py` |
| 1919 | `_handle_stats()` | Command | `telegram_commands.py` |
| 1960 | `_handle_history()` | Command | `telegram_commands.py` |
| 2007 | `_handle_locks()` | Command | `telegram_commands.py` |
| 2039 | `_handle_reset()` | Command | `telegram_commands.py` |
| 2077 | `_handle_cleanup()` | Command | `telegram_commands.py` |
| 2145 | `_handle_callback()` | Callback routing | `telegram_service.py` |
| 2236 | `_complete_queue_action()` | Callback | `telegram_callbacks.py` |
| 2314 | `_handle_posted()` | Callback | `telegram_callbacks.py` |
| 2333 | `_handle_skipped()` | Callback | `telegram_callbacks.py` |
| 2348 | `_handle_autopost()` | Auto-post | `telegram_autopost.py` |
| 2391 | `_do_autopost()` | Auto-post | `telegram_autopost.py` |
| 2735 | `_handle_back()` | Callback | `telegram_callbacks.py` |
| 2790 | `_handle_reject_confirmation()` | Callback | `telegram_callbacks.py` |
| 2841 | `_handle_cancel_reject()` | Callback | `telegram_callbacks.py` |
| 2940 | `_handle_post_account_selector()` | Account (inline) | `telegram_accounts.py` |
| 3019 | `_handle_post_account_switch()` | Account (inline) | `telegram_accounts.py` |
| 3098 | `_handle_back_to_post()` | Account (inline) | `telegram_accounts.py` |
| 3108 | `_rebuild_posting_workflow()` | Account (inline) | `telegram_accounts.py` |
| 3188 | `_handle_rejected()` | Callback | `telegram_callbacks.py` |
| 3264 | `_handle_resume_callback()` | Callback | `telegram_callbacks.py` |
| 3331 | `_handle_reset_callback()` | Callback | `telegram_callbacks.py` |
| 3365 | `_get_or_create_user()` | User mgmt | `telegram_service.py` |
| 3388 | `_is_verbose()` | Utility | `telegram_service.py` |
| 3400 | `_get_display_name()` | Utility | `telegram_service.py` |
| 3409 | `send_startup_notification()` | Lifecycle | `telegram_service.py` |
| 3456 | `send_shutdown_notification()` | Lifecycle | `telegram_service.py` |
| 3491 | `start_polling()` | Lifecycle | `telegram_service.py` |
| 3498 | `stop_polling()` | Lifecycle | `telegram_service.py` |

### Corrections to the user's initial grouping

The proposed split in the task description is mostly correct. Changes:

1. **`_handle_conversation_message`** — Stays in `telegram_service.py`, not in commands. It's a router that dispatches to settings and account conversation handlers.

2. **`_handle_settings`** (the `/settings` command) — Goes to `telegram_settings.py` not `telegram_commands.py`. It's tightly coupled with the settings UI, not with other commands.

3. **`_rebuild_posting_workflow`** — Goes to `telegram_accounts.py` not `telegram_callbacks.py`. It's only called from account selection flow.

4. **Schedule callbacks** (`_handle_schedule_action`, `_handle_schedule_confirm`) — Go to `telegram_settings.py`. They're triggered from the settings UI, not from queue item buttons.

---

## 3. Proposed File Structure

```
src/services/core/
├── telegram_service.py        (~450 lines)  Main entry point, orchestrator
├── telegram_commands.py       (~700 lines)  All /command handlers
├── telegram_callbacks.py      (~550 lines)  Queue action callbacks
├── telegram_autopost.py       (~400 lines)  Instagram API posting flow
├── telegram_settings.py       (~550 lines)  Settings UI + schedule management
└── telegram_accounts.py       (~850 lines)  Account management (settings + inline)
```

### 3.1 `telegram_service.py` (~450 lines) — Orchestrator

**Keeps**: Initialization, lifecycle, notifications, captions, routing, utilities.

```python
# Module-level functions
_escape_markdown(text)
_extract_button_labels(reply_markup)

class TelegramService(BaseService):
    # Setup & lifecycle
    __init__()
    initialize()                    # Handler registration (delegates to sub-handlers)
    start_polling()
    stop_polling()

    # State
    is_paused (property)
    set_paused()

    # Notifications & captions
    send_notification()
    _build_caption()
    _build_simple_caption()
    _build_enhanced_caption()
    _get_header_emoji()
    send_startup_notification()
    send_shutdown_notification()

    # Routing
    _handle_callback()             # Main callback router
    _handle_conversation_message() # Text message router

    # Shared utilities
    _get_or_create_user()
    _is_verbose()
    _get_display_name()
```

### 3.2 `telegram_commands.py` (~700 lines)

```python
class TelegramCommandHandlers:
    __init__(service)

    handle_start()
    handle_status()
    handle_queue()
    handle_next()
    handle_help()
    handle_dryrun()
    handle_pause()
    handle_resume()
    handle_schedule()
    handle_stats()
    handle_history()
    handle_locks()
    handle_reset()
    handle_cleanup()
```

### 3.3 `telegram_callbacks.py` (~550 lines)

```python
class TelegramCallbackHandlers:
    __init__(service)

    complete_queue_action()
    handle_posted()
    handle_skipped()
    handle_back()
    handle_reject_confirmation()
    handle_cancel_reject()
    handle_rejected()
    handle_resume_callback()
    handle_reset_callback()
```

### 3.4 `telegram_autopost.py` (~400 lines)

```python
class TelegramAutopostHandler:
    __init__(service)

    handle_autopost()
    _do_autopost()
```

### 3.5 `telegram_settings.py` (~550 lines)

```python
class TelegramSettingsHandlers:
    __init__(service)

    build_settings_message_and_keyboard()
    handle_settings()
    handle_settings_toggle()
    refresh_settings_message()
    handle_settings_close()
    handle_settings_edit_start()
    handle_settings_edit_message()
    handle_settings_edit_cancel()
    send_settings_message_by_chat_id()
    handle_schedule_action()
    handle_schedule_confirm()
```

### 3.6 `telegram_accounts.py` (~850 lines)

```python
class TelegramAccountHandlers:
    __init__(service)

    # Settings account management
    handle_account_selection_menu()
    handle_account_switch()
    handle_add_account_start()
    handle_add_account_message()
    handle_add_account_cancel()
    handle_remove_account_menu()
    handle_account_remove_confirm()
    handle_account_remove_execute()

    # Inline post account selection
    handle_post_account_selector()
    handle_post_account_switch()
    handle_back_to_post()
    rebuild_posting_workflow()
```

---

## 4. Shared Dependencies Strategy

### 4.1 Options Evaluated

#### Option A: Mixin Pattern
```python
# telegram_commands.py
class TelegramCommandsMixin:
    async def _handle_start(self, update, context): ...

# telegram_service.py
class TelegramService(BaseService, TelegramCommandsMixin, TelegramCallbacksMixin, ...):
    ...
```

**Pros**: Methods remain on `TelegramService`. Handler registration unchanged. `self.` access to all repos/services.

**Cons**: Python resolves names from the module where the function was **defined**, not where the class lives. This means:
- `settings` imported in `telegram_commands.py` resolves from that module
- Test patches at `src.services.core.telegram_service.settings` would **break**
- Each handler module needs its own imports, and tests must patch in the correct module
- Multiple inheritance with ABC (BaseService) adds MRO complexity
- It's organizational, not architectural — `TelegramService` is still conceptually one giant class

#### Option B: Composition (Recommended)
```python
# telegram_commands.py
class TelegramCommandHandlers:
    def __init__(self, service: 'TelegramService'):
        self.service = service

    async def handle_start(self, update, context):
        user = self.service._get_or_create_user(update.effective_user)
        ...
        self.service.interaction_service.log_command(...)

# telegram_service.py
class TelegramService(BaseService):
    def __init__(self):
        ...
        self.commands = TelegramCommandHandlers(self)
        self.callbacks = TelegramCallbackHandlers(self)
        self.autopost = TelegramAutopostHandler(self)
        self.settings_handlers = TelegramSettingsHandlers(self)
        self.account_handlers = TelegramAccountHandlers(self)
```

**Pros**:
- True decomposition — each handler class is independently testable
- Clean dependency direction: handlers depend on service, not vice versa
- Handler registration is straightforward: `CommandHandler("start", self.commands.handle_start)`
- Matches the codebase pattern of services holding other services (PostingService holds TelegramService)
- Each handler module has its own imports, which is natural and explicit
- No MRO complexity

**Cons**:
- Tests must be updated to call `service.commands.handle_start()` instead of `service._handle_start()`
- Handler methods access shared state via `self.service.` instead of `self.`
- Existing `_handle_callback` router needs updating to dispatch to sub-handler objects

#### Option C: Simple Parameter Passing
```python
async def handle_start(update, context, *, user_repo, interaction_service, ...):
```

**Rejected**: Too verbose. Each handler needs 5-10 dependencies. Makes signatures unreadable and tests harder to write.

#### Option D: Inheritance from a Base Handler Class
```python
class TelegramHandlerBase:
    def __init__(self):
        self.user_repo = UserRepository()
        ...

class TelegramCommandHandlers(TelegramHandlerBase):
    ...
```

**Rejected**: Each handler class would create its own repository instances, wasting database connections. The handlers need to share the same repos and services as TelegramService.

### 4.2 Recommendation: Composition (Option B)

Composition is the right choice for this codebase because:

1. **True separation**: Handler classes are real classes with clear boundaries, not just file splits
2. **Testability**: Each handler class can be tested in isolation with a mock service
3. **Consistent patterns**: Matches how PostingService uses TelegramService (composition)
4. **Import safety**: Module-level imports in handler files are natural; patches target the correct module
5. **Future flexibility**: Handler classes can evolve independently (e.g., adding a base handler class later)

### 4.3 Access Pattern for Shared State

Handler classes access shared dependencies through `self.service`:

```python
class TelegramCommandHandlers:
    def __init__(self, service: 'TelegramService'):
        self.service = service

    async def handle_status(self, update, context):
        user = self.service._get_or_create_user(update.effective_user)

        # Access repos
        pending_count = self.service.queue_repo.count_pending()
        recent_posts = self.service.history_repo.get_recent_posts(hours=24)

        # Access settings
        pause_status = "⏸️ PAUSED" if self.service.is_paused else "▶️ Active"

        # Access utilities
        display_name = self.service._get_display_name(user)
        verbose = self.service._is_verbose(chat_id)

        # Log interaction
        self.service.interaction_service.log_command(...)
```

### 4.4 Shorthand Access (Optional Enhancement)

To reduce `self.service.` verbosity, handler classes can expose frequently-used shortcuts:

```python
class TelegramCommandHandlers:
    def __init__(self, service: 'TelegramService'):
        self.service = service

    # Convenience properties for frequently-accessed deps
    @property
    def queue_repo(self):
        return self.service.queue_repo

    @property
    def interaction_service(self):
        return self.service.interaction_service

    def _get_or_create_user(self, telegram_user):
        return self.service._get_or_create_user(telegram_user)

    def _get_display_name(self, user):
        return self.service._get_display_name(user)

    def _is_verbose(self, chat_id, **kwargs):
        return self.service._is_verbose(chat_id, **kwargs)
```

**Recommendation**: Start without shortcuts. Add them in a follow-up if verbosity becomes a problem during code review. Explicit is better than implicit.

---

## 5. Callback Routing

### 5.1 Current Implementation

`_handle_callback()` (line 2145) is an if/elif chain that parses `action:data` strings and dispatches:

```python
async def _handle_callback(self, update, context):
    parts = query.data.split(":", 1)
    action = parts[0]
    data = parts[1] if len(parts) > 1 else None

    if action == "posted":
        await self._handle_posted(data, user, query)
    elif action == "skip":
        await self._handle_skipped(data, user, query)
    elif action == "autopost":
        await self._handle_autopost(data, user, query)
    # ... 20+ more elif branches
```

### 5.2 Proposed Implementation: Dictionary-Based Dispatch

After the split, the router stays in `telegram_service.py` but dispatches to handler objects:

```python
class TelegramService(BaseService):
    def _build_callback_dispatch_table(self):
        """Build action -> handler mapping from all sub-handlers."""
        return {
            # Queue action callbacks (telegram_callbacks.py)
            "posted": self.callbacks.handle_posted,
            "skip": self.callbacks.handle_skipped,
            "back": self.callbacks.handle_back,
            "reject": self.callbacks.handle_reject_confirmation,
            "confirm_reject": self.callbacks.handle_rejected,
            "cancel_reject": self.callbacks.handle_cancel_reject,
            "resume": self.callbacks.handle_resume_callback,
            "clear": self.callbacks.handle_reset_callback,

            # Auto-post (telegram_autopost.py)
            "autopost": self.autopost.handle_autopost,

            # Settings (telegram_settings.py)
            "settings_toggle": self.settings_handlers.handle_settings_toggle,
            "settings_refresh": lambda d, u, q: self.settings_handlers.refresh_settings_message(q),
            "settings_edit": lambda d, u, q, c=context: self.settings_handlers.handle_settings_edit_start(d, u, q, c),
            "settings_edit_cancel": lambda d, u, q, c=context: self.settings_handlers.handle_settings_edit_cancel(q, c),
            "settings_close": lambda d, u, q: self.settings_handlers.handle_settings_close(q),
            "schedule_action": self.settings_handlers.handle_schedule_action,
            "schedule_confirm": self.settings_handlers.handle_schedule_confirm,

            # Accounts (telegram_accounts.py)
            "switch_account": self.account_handlers.handle_account_switch,
            "account_remove": self.account_handlers.handle_account_remove_confirm,
            "account_remove_confirmed": self.account_handlers.handle_account_remove_execute,
            "select_account": self.account_handlers.handle_post_account_selector,
            "sap": self.account_handlers.handle_post_account_switch,
            "btp": self.account_handlers.handle_back_to_post,
        }

    async def _handle_callback(self, update, context):
        """Route callback queries to appropriate handlers."""
        try:
            query = update.callback_query
            logger.info(f"Callback received: {query.data}")
            await query.answer()

            parts = query.data.split(":", 1)
            action = parts[0]
            data = parts[1] if len(parts) > 1 else None

            user = self._get_or_create_user(query.from_user)

            # Simple dispatch for most callbacks
            handler = self._callback_dispatch.get(action)
            if handler:
                await handler(data, user, query)
                return

            # Multi-value routing (settings_accounts, accounts_config)
            if action == "settings_accounts":
                if data == "select":
                    await self.account_handlers.handle_account_selection_menu(user, query)
                elif data == "back":
                    await self.settings_handlers.refresh_settings_message(query)
            elif action == "accounts_config":
                if data == "add":
                    await self.account_handlers.handle_add_account_start(user, query, context)
                elif data == "remove":
                    await self.account_handlers.handle_remove_account_menu(user, query)
                elif data == "noop":
                    await query.answer()
            elif action == "account_add_cancel":
                await self.account_handlers.handle_add_account_cancel(user, query, context)
            else:
                logger.warning(f"Unknown callback action: {action}")
        finally:
            self.cleanup_transactions()
```

### 5.3 Why not a pure dictionary dispatch?

Some callbacks have non-standard signatures or need `context` (the Telegram `CallbackContext`):
- `settings_edit` needs `context` for user_data conversation state
- `settings_accounts` sub-routes on data value
- `accounts_config` sub-routes on data value
- `account_add_cancel` needs `context`

These cases are handled with explicit if/elif after the dictionary lookup fails. This keeps the common case fast and clean while handling edge cases explicitly.

### 5.4 Alternative: Keep the if/elif chain

The current if/elif chain is perfectly readable at ~40 lines. Converting to a dict dispatch is optional. The key change is that method references point to handler objects instead of `self._handle_*`. Either approach works. The if/elif chain is recommended for the initial refactor to minimize changes.

---

## 6. Handler Registration

### 6.1 Current Implementation

```python
async def initialize(self):
    self.application.add_handler(CommandHandler("start", self._handle_start))
    self.application.add_handler(CommandHandler("status", self._handle_status))
    # ... 14 more command handlers
    self.application.add_handler(CallbackQueryHandler(self._handle_callback))
    self.application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, self._handle_conversation_message
    ))
```

### 6.2 After Refactor

```python
async def initialize(self):
    self.bot = Bot(token=self.bot_token)
    self.application = Application.builder().token(self.bot_token).build()

    # Initialize sub-handlers (after bot/application are created)
    self.commands = TelegramCommandHandlers(self)
    self.callbacks = TelegramCallbackHandlers(self)
    self.autopost = TelegramAutopostHandler(self)
    self.settings_handlers = TelegramSettingsHandlers(self)
    self.account_handlers = TelegramAccountHandlers(self)

    # Build callback dispatch table
    self._callback_dispatch = self._build_callback_dispatch_table()

    # Register command handlers
    command_map = {
        "start": self.commands.handle_start,
        "status": self.commands.handle_status,
        "queue": self.commands.handle_queue,
        "next": self.commands.handle_next,
        "pause": self.commands.handle_pause,
        "resume": self.commands.handle_resume,
        "schedule": self.commands.handle_schedule,
        "stats": self.commands.handle_stats,
        "history": self.commands.handle_history,
        "locks": self.commands.handle_locks,
        "reset": self.commands.handle_reset,
        "cleanup": self.commands.handle_cleanup,
        "help": self.commands.handle_help,
        "dryrun": self.commands.handle_dryrun,
        "settings": self.settings_handlers.handle_settings,
    }
    for cmd, handler in command_map.items():
        self.application.add_handler(CommandHandler(cmd, handler))

    # Register callback and message handlers
    self.application.add_handler(CallbackQueryHandler(self._handle_callback))
    self.application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, self._handle_conversation_message
    ))

    # Register command autocomplete menu (unchanged)
    commands = [
        BotCommand("start", "Initialize bot and show welcome"),
        # ... same as current
    ]
    await self.bot.set_my_commands(commands)
```

### 6.3 Key Decision: When to Create Sub-Handlers

Sub-handlers are created in `initialize()`, not `__init__()`. This is because:
- `__init__()` creates repos/services (database connections)
- `initialize()` creates the bot and application (async)
- Sub-handlers need the service to be fully constructed first
- Creating them in `initialize()` ensures all deps are available

**Important**: `send_notification()` can be called without `initialize()` (from CLI usage). This is handled because `send_notification()` stays on `TelegramService` and doesn't need sub-handlers.

---

## 7. `_handle_conversation_message` Routing

### Current

```python
async def _handle_conversation_message(self, update, context):
    if "add_account_state" in context.user_data:
        handled = await self._handle_add_account_message(update, context)
        if handled: return

    if "settings_edit_state" in context.user_data:
        handled = await self._handle_settings_edit_message(update, context)
        if handled: return
```

### After Refactor

```python
async def _handle_conversation_message(self, update, context):
    if "add_account_state" in context.user_data:
        handled = await self.account_handlers.handle_add_account_message(update, context)
        if handled: return

    if "settings_edit_state" in context.user_data:
        handled = await self.settings_handlers.handle_settings_edit_message(update, context)
        if handled: return
```

This stays in `telegram_service.py` as a thin router.

---

## 8. Test Migration Plan

### 8.1 Current Test Structure

```
tests/src/services/test_telegram_service.py  (2,428 lines, 27 classes)
```

All tests use the `mock_telegram_service` fixture which:
1. Patches all imports at `src.services.core.telegram_service.*`
2. Creates a `TelegramService()` instance
3. Replaces repos/services with mocks
4. Tests call methods like `service._handle_start(update, context)`

### 8.2 Target Test Structure

```
tests/src/services/
├── test_telegram_service.py       (~200 lines)  Core, routing, utilities
├── test_telegram_commands.py      (~600 lines)  Command handler tests
├── test_telegram_callbacks.py     (~450 lines)  Callback handler tests
├── test_telegram_autopost.py      (~200 lines)  Auto-post tests (future)
├── test_telegram_settings.py      (~300 lines)  Settings tests
└── test_telegram_accounts.py      (~500 lines)  Account management tests
```

### 8.3 Test Class → File Mapping

| Test Class | Current Method Under Test | Target Test File |
|-----------|--------------------------|-----------------|
| `TestGetDisplayName` | `_get_display_name` | `test_telegram_service.py` |
| `TestButtonLayout` | Keyboard structure | `test_telegram_service.py` |
| `TestProfileSync` | `_get_or_create_user` | `test_telegram_service.py` |
| `TestTelegramService` | Init, `_get_or_create_user`, `_build_caption` | `test_telegram_service.py` |
| `TestIsVerbose` | `_is_verbose` | `test_telegram_service.py` |
| `TestVerboseEnhancedCaption` | `_build_enhanced_caption` | `test_telegram_service.py` |
| `TestVerboseSimpleCaption` | `_build_simple_caption` | `test_telegram_service.py` |
| `TestBuildSettingsKeyboard` | `_build_settings_message_and_keyboard` | `test_telegram_settings.py` |
| `TestQueueCommand` | `_handle_queue` | `test_telegram_commands.py` |
| `TestNextCommand` | `_handle_next` | `test_telegram_commands.py` |
| `TestPauseCommand` | `_handle_pause` | `test_telegram_commands.py` |
| `TestResumeCommand` | `_handle_resume` | `test_telegram_commands.py` |
| `TestScheduleCommand` | `_handle_schedule` | `test_telegram_commands.py` |
| `TestStatsCommand` | `_handle_stats` | `test_telegram_commands.py` |
| `TestHistoryCommand` | `_handle_history` | `test_telegram_commands.py` |
| `TestLocksCommand` | `_handle_locks` | `test_telegram_commands.py` |
| `TestResetCommand` | `_handle_reset` | `test_telegram_commands.py` |
| `TestRejectConfirmation` | Reject flow | `test_telegram_callbacks.py` |
| `TestCompleteQueueAction` | `_complete_queue_action` | `test_telegram_callbacks.py` |
| `TestVerbosePostedSkipped` | `_handle_posted`, `_handle_skipped` | `test_telegram_callbacks.py` |
| `TestVerboseRejected` | `_handle_rejected` | `test_telegram_callbacks.py` |
| `TestResumeCallbacks` | `_handle_resume_callback` | `test_telegram_callbacks.py` |
| `TestResetCallbacks` | `_handle_reset_callback` | `test_telegram_callbacks.py` |
| `TestPauseIntegration` | PostingService integration | `test_telegram_commands.py` |
| `TestInlineAccountSelector` | Account selector UI | `test_telegram_accounts.py` |
| `TestAccountSelectorCallbacks` | Account selector callbacks | `test_telegram_accounts.py` |

### 8.4 Fixture Changes

#### Old fixture (patches `telegram_service` module):
```python
@pytest.fixture
def mock_telegram_service():
    with (
        patch("src.services.core.telegram_service.settings") as mock_settings,
        patch("src.services.core.telegram_service.UserRepository") as mock_user_repo_class,
        ...
    ):
        service = TelegramService()
        service.user_repo = mock_user_repo_class.return_value
        ...
        yield service
```

#### New fixtures for handler tests:
```python
# tests/conftest_telegram.py or within each test file

@pytest.fixture
def mock_service():
    """Create TelegramService with mocked dependencies (shared base)."""
    with (
        patch("src.services.core.telegram_service.settings") as mock_settings,
        patch("src.services.core.telegram_service.UserRepository") as mock_user_repo_class,
        ...
    ):
        mock_settings.TELEGRAM_BOT_TOKEN = "123456:ABC-DEF"
        mock_settings.TELEGRAM_CHANNEL_ID = -1001234567890
        mock_settings.CAPTION_STYLE = "enhanced"
        mock_settings.SEND_LIFECYCLE_NOTIFICATIONS = False

        service = TelegramService()
        service.user_repo = mock_user_repo_class.return_value
        service.queue_repo = mock_queue_repo_class.return_value
        # ... same pattern
        yield service


@pytest.fixture
def mock_command_handlers(mock_service):
    """Create TelegramCommandHandlers with mocked service."""
    return TelegramCommandHandlers(mock_service)


@pytest.fixture
def mock_callback_handlers(mock_service):
    """Create TelegramCallbackHandlers with mocked service."""
    return TelegramCallbackHandlers(mock_service)
```

#### Test method call changes:
```python
# Before:
await mock_telegram_service._handle_queue(mock_update, mock_context)

# After:
await mock_command_handlers.handle_queue(mock_update, mock_context)
```

### 8.5 Import Path Changes

Handler methods that reference module-level imports (like `settings`, `_escape_markdown`) will resolve from their new modules. Tests need to patch accordingly:

```python
# Before (all patches target telegram_service module):
patch("src.services.core.telegram_service.settings")

# After (patches target the module where the code lives):
# For commands:
patch("src.services.core.telegram_commands.settings")  # If commands import settings
# For service-level code:
patch("src.services.core.telegram_service.settings")   # Unchanged
```

**Mitigation**: Most handler methods access `settings` through `self.service.settings_service` (database-backed settings), not the module-level `settings` object. Only a few methods reference `settings` directly:
- `_handle_status` — checks `settings.ENABLE_INSTAGRAM_API`, `settings.DRY_RUN_MODE`
- `_handle_autopost` / `_do_autopost` — checks `settings.ENABLE_INSTAGRAM_API`
- `send_notification` — stays in `telegram_service.py`
- `send_startup_notification` / `send_shutdown_notification` — stay in `telegram_service.py`

For commands that reference `settings` directly, they should either:
1. Import `settings` in their own module (and patches adjust)
2. Or access it via `self.service` (e.g., add a property on TelegramService)

**Recommendation**: Import `settings` in each handler module that needs it. Keep patches targeting the module where the code runs. This is explicit and correct.

---

## 9. Migration Strategy

### 9.1 Recommendation: 3 Incremental PRs

Each PR must pass linting (`ruff check`), formatting (`ruff format --check`), and tests (`pytest`) at every intermediate state. No PR should leave the codebase in a broken state.

### PR 1: Foundation + Commands (~700 lines moved)

**Scope**:
1. Create `telegram_commands.py` with `TelegramCommandHandlers` class
2. Move all 14 command handlers from `telegram_service.py`
3. Update `TelegramService.initialize()` to register commands via `self.commands`
4. Update `_handle_conversation_message()` (no change needed yet)
5. Move command tests from `test_telegram_service.py` to `test_telegram_commands.py`
6. Update CHANGELOG.md

**Why commands first**: Commands are the most independent handlers. They don't call each other. They have no cross-dependencies with callbacks. This is the lowest-risk extraction.

**Files changed**:
- `src/services/core/telegram_commands.py` (new)
- `src/services/core/telegram_service.py` (remove command methods, update initialize)
- `tests/src/services/test_telegram_commands.py` (new, moved from test_telegram_service.py)
- `tests/src/services/test_telegram_service.py` (remove moved test classes)
- `CHANGELOG.md`

### PR 2: Callbacks + Auto-post (~950 lines moved)

**Scope**:
1. Create `telegram_callbacks.py` with `TelegramCallbackHandlers`
2. Create `telegram_autopost.py` with `TelegramAutopostHandler`
3. Move queue action callbacks and autopost handlers
4. Update `_handle_callback()` router to dispatch to handler objects
5. Move corresponding tests

**Why together**: Callbacks and autopost share the same dispatch entry point (`_handle_callback`). Moving them together avoids updating the router twice.

**Files changed**:
- `src/services/core/telegram_callbacks.py` (new)
- `src/services/core/telegram_autopost.py` (new)
- `src/services/core/telegram_service.py` (remove methods, update router)
- `tests/src/services/test_telegram_callbacks.py` (new)
- `tests/src/services/test_telegram_autopost.py` (new, initially may be empty if no autopost tests exist)
- `tests/src/services/test_telegram_service.py` (remove moved tests)
- `CHANGELOG.md`

### PR 3: Settings + Accounts (~1,400 lines moved)

**Scope**:
1. Create `telegram_settings.py` with `TelegramSettingsHandlers`
2. Create `telegram_accounts.py` with `TelegramAccountHandlers`
3. Move settings UI handlers, schedule management, account management
4. Update `_handle_callback()` router (remaining settings/account branches)
5. Update `_handle_conversation_message()` to route to handler objects
6. Move corresponding tests
7. Final cleanup of `telegram_service.py`

**Why last**: Settings and accounts have the most cross-dependencies (conversation state, nested menus, account selection from posting workflow). They also have the most complex callback routing.

**Files changed**:
- `src/services/core/telegram_settings.py` (new)
- `src/services/core/telegram_accounts.py` (new)
- `src/services/core/telegram_service.py` (final cleanup)
- `tests/src/services/test_telegram_settings.py` (new)
- `tests/src/services/test_telegram_accounts.py` (new)
- `tests/src/services/test_telegram_service.py` (final, only core tests remain)
- `CHANGELOG.md`

### 9.2 Alternative: Single PR

**Pros**: One atomic change, no intermediate states to worry about.

**Cons**:
- 3,500+ lines changed in a single PR is difficult to review
- If any part breaks, the entire PR is blocked
- Merge conflicts with any concurrent work on telegram_service.py
- Rollback is all-or-nothing

**Recommendation**: Use incremental PRs. Each is independently reviewable and reversible.

---

## 10. Risk Assessment

### 10.1 High Risk: Callback Routing Breaks

**What**: A callback action string isn't routed correctly after the dispatcher is updated.

**Impact**: Button clicks in Telegram do nothing or throw errors. Users can't post, skip, or manage queue items.

**Mitigation**:
- The existing `TestRejectConfirmation.test_callback_routes_to_confirm_reject` and `test_callback_routes_to_cancel_reject` tests verify callback routing. Add similar tests for every action.
- Create a dedicated `TestCallbackRouting` class that tests every action string routes to the correct handler.
- Manual testing: after each PR, verify in the real Telegram chat that all buttons work.

### 10.2 High Risk: Auto-Post Safety Gates Bypassed

**What**: During extraction, a safety check is accidentally removed or reordered in `_do_autopost`.

**Impact**: Posts to Instagram without proper validation. Could post to wrong account or bypass dry-run mode.

**Mitigation**:
- `_handle_autopost` and `_do_autopost` move together as a unit (no splitting of the safety flow)
- Add explicit test for safety gate: mock `safety_check_before_post` to return unsafe, verify no post is made
- The auto-post handler is isolated in its own file, making safety review easier

### 10.3 Medium Risk: Import Path Changes Break Test Patches

**What**: Tests patch `src.services.core.telegram_service.settings` but code now imports `settings` from a different module.

**Impact**: Tests pass but don't actually test the real code paths (patches don't intercept).

**Mitigation**:
- Audit every `from src.config.settings import settings` in new handler modules
- Ensure test patches target the module where the import lives
- Run tests with `--tb=long` to catch unexpected behaviors
- Add a test that verifies the settings mock is actually intercepting (assert mock was called)

### 10.4 Medium Risk: Handler Registration Missing

**What**: A command or callback handler isn't registered with the Application after refactor.

**Impact**: `/command` or button doesn't respond.

**Mitigation**:
- Create a test that verifies all expected handlers are registered after `initialize()`
- Compare registered handler count before and after refactor
- The `command_map` dict in `initialize()` makes it easy to verify completeness

### 10.5 Medium Risk: Conversation State Broken

**What**: `context.user_data` conversation state for add-account or settings-edit flows doesn't work across module boundaries.

**Impact**: Multi-step flows (add account: name → ID → token) break mid-flow.

**Mitigation**:
- `context.user_data` is managed by python-telegram-bot and is independent of which class handles it
- The `_handle_conversation_message` router checks state keys, not handler identity
- Test the full conversation flow: start → input → input → completion

### 10.6 Low Risk: `_escape_markdown` / `_extract_button_labels` Not Found

**What**: Handler modules reference module-level functions that stay in `telegram_service.py`.

**Impact**: ImportError or NameError at runtime.

**Mitigation**:
- These functions stay in `telegram_service.py` (they're used by `send_notification` which stays)
- Handler modules that need `_escape_markdown` (currently: `_handle_queue` in commands) should import it: `from src.services.core.telegram_service import _escape_markdown`
- Or move these to a shared `telegram_utils.py` if used across 3+ modules

### 10.7 Low Risk: `self.bot is None` Edge Case

**What**: `send_notification()` handles the case where `bot` hasn't been initialized (CLI usage). After refactor, sub-handlers assume `self.service.bot` exists.

**Impact**: None for sub-handlers — they're only created in `initialize()` which creates the bot first. But worth noting.

**Mitigation**: Document that sub-handlers are only available after `initialize()`.

---

## 11. Verification Checklist

After each PR, verify:

- [ ] `ruff check src/ tests/` — No linting errors
- [ ] `ruff format --check src/ tests/` — Formatting correct
- [ ] `pytest` — All tests pass (including skipped tests count unchanged)
- [ ] `python -c "from src.services.core.telegram_service import TelegramService"` — Import works
- [ ] Method count: Verify TelegramService has expected methods remaining
- [ ] Callback routing: Every action string in `_handle_callback` resolves to a valid handler
- [ ] Handler registration: Count of registered CommandHandlers matches expected (15)
- [ ] No circular imports between handler modules

### Manual Verification (after all PRs):

- [ ] `/start` responds
- [ ] `/status` shows correct info
- [ ] `/queue` lists pending items
- [ ] `/next` force-sends a post
- [ ] `/settings` shows settings menu with working toggles
- [ ] Auto Post button triggers autopost flow (in dry-run mode)
- [ ] Posted/Skip/Reject buttons work
- [ ] Account selector opens and switches accounts
- [ ] Add/Remove account conversation flows complete
- [ ] `/pause` and `/resume` with overdue handling work
- [ ] `/cleanup` deletes bot messages

---

## 12. Estimated File Sizes After Refactor

| File | Lines (est.) | Responsibility |
|------|-------------|----------------|
| `telegram_service.py` | ~450 | Orchestrator, lifecycle, captions, routing, utilities |
| `telegram_commands.py` | ~700 | 14 command handlers |
| `telegram_callbacks.py` | ~550 | Queue action callbacks (posted/skipped/rejected/resume/reset) |
| `telegram_autopost.py` | ~400 | Instagram API auto-posting with safety gates |
| `telegram_settings.py` | ~550 | Settings UI, schedule management, conversation flows |
| `telegram_accounts.py` | ~850 | Account CRUD + inline post account selection |
| **Total** | ~3,500 | Same total, but organized |

---

## 13. Open Questions

1. **Should `_escape_markdown` and `_extract_button_labels` move to a shared `telegram_utils.py`?**
   Currently only used by `telegram_service.py`. If commands also need `_escape_markdown` (currently `_handle_queue` uses it), a shared utility file avoids cross-module imports. Decision: move to `telegram_utils.py` if needed by 2+ handler modules.

2. **Should we rename handler methods to drop the `_handle_` prefix?**
   Currently `_handle_start` → could become `handle_start` (public method on handler class). The underscore prefix indicated "private method on TelegramService." On a handler class, these are the public interface. **Recommendation**: Yes, drop the leading underscore. Use `handle_start`, `handle_posted`, etc.

3. **Should sub-handlers inherit from a common `TelegramHandlerBase`?**
   A base class could provide shared access patterns and reduce boilerplate. **Recommendation**: Not in the initial refactor. Add later if a pattern emerges across 3+ handler classes.

4. **Should we add type hints for the `service` parameter?**
   `TYPE_CHECKING` import avoids circular imports: `if TYPE_CHECKING: from src.services.core.telegram_service import TelegramService`. **Recommendation**: Yes, add type hints in each handler module.

---

## 14. Summary

| Aspect | Decision |
|--------|----------|
| **Architecture** | Composition — handler classes receive a `service` reference |
| **File count** | 6 files (1 existing + 5 new) |
| **Callback routing** | Keep if/elif chain in `telegram_service.py`, dispatch to handler objects |
| **Handler registration** | Dict-based in `initialize()`, pointing to handler methods |
| **Test strategy** | Split tests alongside code, update fixtures and method calls |
| **Migration** | 3 incremental PRs: Commands → Callbacks+Autopost → Settings+Accounts |
| **Method naming** | Drop `_` prefix on handler methods (public API of handler classes) |
| **Shared deps** | Access via `self.service.*` (no shortcuts initially) |
