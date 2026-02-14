# Phase 03: Per-Tenant Scheduler & Posting

**Status:** PENDING
**Risk:** Medium
**Effort:** 4-5 hours
**PR Title:** `feat: per-tenant scheduler loops and posting pipeline`

---

## 1. Problem Statement

The current system is hardcoded to a single tenant. Six source files reference `settings.ADMIN_TELEGRAM_CHAT_ID` to look up chat settings when no chat context is available (scheduler loops, posting loops, startup notifications). Three source files use `settings.TELEGRAM_CHANNEL_ID` as the destination for notifications and sync error messages. This means all scheduling, posting, and notification behavior is locked to one admin chat. Multi-tenant operation requires these to be dynamic, driven by the database.

## 2. Complete Inventory of Hardcoded References (Source Code Only)

Here is every hardcoded reference in production source files (excluding docs, tests, and CI config):

**`settings.ADMIN_TELEGRAM_CHAT_ID` (8 references in 5 files):**

| File | Line | Context |
|------|------|---------|
| `src/services/core/scheduler.py` | 232 | `_generate_time_slots_from_date()` calls `get_settings(settings.ADMIN_TELEGRAM_CHAT_ID)` |
| `src/services/core/scheduler.py` | 330 | `_generate_time_slots()` calls `get_settings(settings.ADMIN_TELEGRAM_CHAT_ID)` |
| `src/services/core/posting.py` | 54 | `_get_chat_settings()` calls `get_settings(settings.ADMIN_TELEGRAM_CHAT_ID)` |
| `src/services/core/telegram_service.py` | 697 | `send_startup_notification()` sends to `settings.ADMIN_TELEGRAM_CHAT_ID` |
| `src/services/core/telegram_service.py` | 732 | `send_shutdown_notification()` sends to `settings.ADMIN_TELEGRAM_CHAT_ID` |
| `src/services/integrations/instagram_api.py` | 151 | `post_story()` defaults `telegram_chat_id` to `ADMIN_TELEGRAM_CHAT_ID` |
| `src/services/integrations/instagram_api.py` | 478, 550, 627 | `is_configured()`, `get_account_info()`, `safety_check_before_post()` default to `ADMIN_TELEGRAM_CHAT_ID` |
| `src/services/integrations/instagram_backfill.py` | 155 | `backfill()` defaults `telegram_chat_id` to `ADMIN_TELEGRAM_CHAT_ID` |
| `cli/commands/instagram.py` | 468, 513 | `add_instagram_account` and `list_instagram_accounts` use `ADMIN_TELEGRAM_CHAT_ID` |

**`settings.TELEGRAM_CHANNEL_ID` (2 references in 2 files):**

| File | Line | Context |
|------|------|---------|
| `src/services/core/telegram_service.py` | 58 | Constructor sets `self.channel_id = settings.TELEGRAM_CHANNEL_ID` |
| `src/main.py` | 179 | `_notify_sync_error()` sends to `settings.TELEGRAM_CHANNEL_ID` |

**`self.channel_id` used pervasively in `telegram_service.py`** (line 58, 94, 100, 296-297, 300, 379, 386, 399): The constructor sets `self.channel_id = settings.TELEGRAM_CHANNEL_ID`, and then all notification-sending methods use `self.channel_id` as the destination. This is correct for single-tenant but needs to become dynamic in multi-tenant.

## 3. Architecture Design

**Core Principle: The Telegram chat that originated a command IS the tenant identity.**

Every Telegram command handler already receives `update.effective_chat.id`. Every callback handler already has `query.message.chat_id`. These are the correct tenant identifiers. The problem is only in the background loops (`main.py`) and in methods called without chat context (scheduler, posting service).

**Three categories of changes:**

1. **Background loops** (main.py): Must iterate over all active tenants
2. **Service methods** called from loops: Must accept `chat_settings_id` or `telegram_chat_id` parameter
3. **Telegram handlers**: Already have chat context; just need to pass it through to services
4. **Lifecycle notifications**: Startup/shutdown should notify all active chats (or just admin)

## 4. Detailed File-by-File Changes

---

### 4.1 `src/repositories/chat_settings_repository.py` -- Add `get_all_active()` method

**Why:** The scheduler loop needs to find all non-paused tenants to process.

**Current code (end of file, after `set_paused`):**
```python
    def set_paused(
        self, telegram_chat_id: int, is_paused: bool, user_id: Optional[str] = None
    ) -> ChatSettings:
        # ... existing ...
```

**Add new method after `set_paused`:**
```python
    def get_all_active(self) -> list[ChatSettings]:
        """Get all non-paused chat settings records.

        Used by the scheduler loop to iterate over all active tenants.
        Returns only records where is_paused is False.

        Returns:
            List of active ChatSettings, ordered by created_at
        """
        result = (
            self.db.query(ChatSettings)
            .filter(ChatSettings.is_paused == False)  # noqa: E712
            .order_by(ChatSettings.created_at.asc())
            .all()
        )
        self.end_read_transaction()
        return result
```

---

### 4.2 `src/services/core/settings_service.py` -- Add `get_all_active_chats()` method

**Why:** The service layer should expose the repository method; callers should not touch repositories directly.

**Add after `get_settings_display()` (end of class):**
```python
    def get_all_active_chats(self) -> list:
        """Get all active (non-paused) chat settings.

        Used by the scheduler loop to iterate over all tenants.

        Returns:
            List of ChatSettings records where is_paused=False
        """
        return self.settings_repo.get_all_active()
```

---

### 4.3 `src/services/core/scheduler.py` -- Accept `telegram_chat_id` parameter

**Why:** Both `_generate_time_slots()` and `_generate_time_slots_from_date()` hardcode `settings.ADMIN_TELEGRAM_CHAT_ID`. They need to accept a chat ID so each tenant gets their own schedule settings (posts_per_day, hours).

**Change 1: `_generate_time_slots()` (line 321-373)**

Before (lines 328-332):
```python
    def _generate_time_slots(self, days: int) -> list[datetime]:
        # ...
        # Get schedule settings from database (falls back to .env if not in DB)
        chat_settings = self.settings_service.get_settings(
            settings.ADMIN_TELEGRAM_CHAT_ID
        )
```

After:
```python
    def _generate_time_slots(
        self, days: int, telegram_chat_id: Optional[int] = None
    ) -> list[datetime]:
        # ...
        # Get schedule settings from database (falls back to .env if not in DB)
        if telegram_chat_id is None:
            telegram_chat_id = settings.ADMIN_TELEGRAM_CHAT_ID
        chat_settings = self.settings_service.get_settings(telegram_chat_id)
```

**Change 2: `_generate_time_slots_from_date()` (line 219-272)**

Before (lines 231-233):
```python
    def _generate_time_slots_from_date(self, start_date, days: int) -> list[datetime]:
        # ...
        # Get schedule settings from database
        chat_settings = self.settings_service.get_settings(
            settings.ADMIN_TELEGRAM_CHAT_ID
        )
```

After:
```python
    def _generate_time_slots_from_date(
        self, start_date, days: int, telegram_chat_id: Optional[int] = None
    ) -> list[datetime]:
        # ...
        # Get schedule settings from database
        if telegram_chat_id is None:
            telegram_chat_id = settings.ADMIN_TELEGRAM_CHAT_ID
        chat_settings = self.settings_service.get_settings(telegram_chat_id)
```

**Change 3: `create_schedule()` (line 30-94) -- thread `telegram_chat_id` through**

Before (line 30):
```python
    def create_schedule(self, days: int = 7, user_id: Optional[str] = None) -> dict:
```

After:
```python
    def create_schedule(
        self,
        days: int = 7,
        user_id: Optional[str] = None,
        telegram_chat_id: Optional[int] = None,
    ) -> dict:
```

And inside `create_schedule`, update line 59:
```python
                # Before:
                time_slots = self._generate_time_slots(days)
                # After:
                time_slots = self._generate_time_slots(days, telegram_chat_id=telegram_chat_id)
```

**Change 4: `extend_schedule()` (line 96-172) -- thread `telegram_chat_id` through**

Before (line 96):
```python
    def extend_schedule(self, days: int = 7, user_id: Optional[str] = None) -> dict:
```

After:
```python
    def extend_schedule(
        self,
        days: int = 7,
        user_id: Optional[str] = None,
        telegram_chat_id: Optional[int] = None,
    ) -> dict:
```

And inside `extend_schedule`, update line 138:
```python
                # Before:
                time_slots = self._generate_time_slots_from_date(start_date, days)
                # After:
                time_slots = self._generate_time_slots_from_date(
                    start_date, days, telegram_chat_id=telegram_chat_id
                )
```

---

### 4.4 `src/services/core/posting.py` -- Accept `telegram_chat_id` parameter

**Why:** `_get_chat_settings()` and `process_pending_posts()` hardcode the admin chat. The posting loop needs to process each tenant's queue independently.

**Change 1: `_get_chat_settings()` (line 52-54)**

Before:
```python
    def _get_chat_settings(self):
        """Get settings for the admin chat (for checking dry_run, is_paused, etc.)."""
        return self.settings_service.get_settings(settings.ADMIN_TELEGRAM_CHAT_ID)
```

After:
```python
    def _get_chat_settings(self, telegram_chat_id: Optional[int] = None):
        """Get settings for a chat (for checking dry_run, is_paused, etc.).

        Args:
            telegram_chat_id: Chat to get settings for.
                Falls back to ADMIN_TELEGRAM_CHAT_ID if not specified.
        """
        if telegram_chat_id is None:
            telegram_chat_id = settings.ADMIN_TELEGRAM_CHAT_ID
        return self.settings_service.get_settings(telegram_chat_id)
```

**Change 2: `process_pending_posts()` (line 224-302) -- accept `telegram_chat_id`**

Before (line 224):
```python
    async def process_pending_posts(self, user_id: Optional[str] = None) -> dict:
```

After:
```python
    async def process_pending_posts(
        self, user_id: Optional[str] = None, telegram_chat_id: Optional[int] = None
    ) -> dict:
```

And inside, update the `is_paused` check (line 237):

Before:
```python
            if self.telegram_service.is_paused:
```

After:
```python
            # Check if posting is paused for this chat
            if telegram_chat_id:
                chat_settings = self._get_chat_settings(telegram_chat_id)
                is_paused = chat_settings.is_paused
            else:
                is_paused = self.telegram_service.is_paused

            if is_paused:
```

Note: The `self.telegram_service.is_paused` property checks `self.channel_id` which is still the global admin channel. For the per-tenant path, we check `chat_settings.is_paused` directly. This preserves backward compatibility when called without `telegram_chat_id`.

**Change 3: `_post_via_instagram()` (line 360-462) -- thread `telegram_chat_id`**

The existing call at line 377 already uses `self._get_chat_settings()`. Since `_post_via_instagram` is called with both `queue_item` and `media_item`, and the queue item has `telegram_chat_id` on it (line 50 of posting_queue model), we can extract it:

Before (line 377):
```python
        chat_settings = self._get_chat_settings()
```

After:
```python
        # Use queue item's chat context if available, fall back to admin
        item_chat_id = getattr(queue_item, 'telegram_chat_id', None)
        chat_settings = self._get_chat_settings(item_chat_id)
```

---

### 4.5 `src/main.py` -- Per-tenant scheduler loop

**Why:** The central scheduler loop currently calls `posting_service.process_pending_posts()` globally. It needs to iterate over active tenants.

**Change 1: `run_scheduler_loop()` (lines 22-48)**

Before:
```python
async def run_scheduler_loop(posting_service: PostingService):
    """Run scheduler loop - check for pending posts every minute."""
    global session_posts_sent
    logger.info("Starting scheduler loop...")

    while True:
        try:
            # Process pending posts
            result = await posting_service.process_pending_posts()

            if result["processed"] > 0:
                # Only count successful Telegram posts (not failed ones)
                session_posts_sent += result["telegram"]
                logger.info(
                    f"Processed {result['processed']} posts: "
                    f"{result['telegram']} to Telegram, "
                    f"{result['failed']} failed"
                )

        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}", exc_info=True)
        finally:
            # Clean up open transactions to prevent "idle in transaction"
            posting_service.cleanup_transactions()

        # Wait 1 minute before next check
        await asyncio.sleep(60)
```

After:
```python
async def run_scheduler_loop(
    posting_service: PostingService,
    settings_service=None,
):
    """Run scheduler loop - check for pending posts every minute.

    Iterates over all active (non-paused) tenants and processes each
    tenant's pending posts independently.

    Args:
        posting_service: PostingService instance
        settings_service: SettingsService instance for tenant discovery.
            If None, falls back to global single-tenant behavior.
    """
    global session_posts_sent
    logger.info("Starting scheduler loop...")

    while True:
        try:
            if settings_service:
                active_chats = settings_service.get_all_active_chats()
            else:
                active_chats = []

            if active_chats:
                # Multi-tenant mode: process each tenant's queue
                for chat in active_chats:
                    try:
                        result = await posting_service.process_pending_posts(
                            telegram_chat_id=chat.telegram_chat_id
                        )

                        if result["processed"] > 0:
                            session_posts_sent += result["telegram"]
                            logger.info(
                                f"[chat={chat.telegram_chat_id}] "
                                f"Processed {result['processed']} posts: "
                                f"{result['telegram']} to Telegram, "
                                f"{result['failed']} failed"
                            )
                    except Exception as e:
                        logger.error(
                            f"Error processing chat {chat.telegram_chat_id}: {e}",
                            exc_info=True,
                        )
            else:
                # Legacy single-tenant fallback
                result = await posting_service.process_pending_posts()

                if result["processed"] > 0:
                    session_posts_sent += result["telegram"]
                    logger.info(
                        f"Processed {result['processed']} posts: "
                        f"{result['telegram']} to Telegram, "
                        f"{result['failed']} failed"
                    )

        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}", exc_info=True)
        finally:
            posting_service.cleanup_transactions()

        # Wait 1 minute before next check
        await asyncio.sleep(60)
```

**Change 2: `main_async()` -- pass `settings_service` to the scheduler loop**

In `main_async()` (around lines 207-229), add a SettingsService instance and pass it:

After line 209 (`lock_service = MediaLockService()`), add:
```python
    from src.services.core.settings_service import SettingsService
    settings_service = SettingsService()
```

And update the task creation at line 226:
```python
        # Before:
        asyncio.create_task(run_scheduler_loop(posting_service)),
        # After:
        asyncio.create_task(run_scheduler_loop(posting_service, settings_service)),
```

**Change 3: `_notify_sync_error()` (line 166-184) -- use channel_id from service, not global**

Before (line 179):
```python
        await telegram_service.bot.send_message(
            chat_id=settings.TELEGRAM_CHANNEL_ID,
            text=message,
            parse_mode="Markdown",
        )
```

After:
```python
        await telegram_service.bot.send_message(
            chat_id=telegram_service.channel_id,
            text=message,
            parse_mode="Markdown",
        )
```

This replaces a direct `settings.TELEGRAM_CHANNEL_ID` reference with `telegram_service.channel_id`, which is already set to the same value but is more consistent. (In a future phase, `channel_id` on TelegramService would become per-tenant, but that is out of scope here.)

---

### 4.6 `src/services/core/telegram_service.py` -- Parameterize lifecycle notifications

**Why:** `send_startup_notification()` and `send_shutdown_notification()` send to `settings.ADMIN_TELEGRAM_CHAT_ID`. For multi-tenant, these should either notify all active chats, or (simpler) continue to notify only the admin. Since lifecycle events are system-level (not tenant-level), keeping them admin-only is the right design. However, the hardcoded reference should still be replaced with the constructor-cached value for consistency.

**Change 1: Constructor (line 58) -- cache `admin_chat_id`**

After line 58:
```python
        self.channel_id = settings.TELEGRAM_CHANNEL_ID
```

Add:
```python
        self.admin_chat_id = settings.ADMIN_TELEGRAM_CHAT_ID
```

**Change 2: `send_startup_notification()` (line 697)**

Before:
```python
            await self.bot.send_message(
                chat_id=settings.ADMIN_TELEGRAM_CHAT_ID,
```

After:
```python
            await self.bot.send_message(
                chat_id=self.admin_chat_id,
```

**Change 3: `send_shutdown_notification()` (line 732)**

Before:
```python
            await self.bot.send_message(
                chat_id=settings.ADMIN_TELEGRAM_CHAT_ID,
```

After:
```python
            await self.bot.send_message(
                chat_id=self.admin_chat_id,
```

---

### 4.7 `src/services/core/telegram_commands.py` -- Pass chat context to scheduler

**Why:** The `/schedule` command creates a schedule but does not pass the chat context. This means the schedule uses the admin chat's settings (posts_per_day, hours) instead of the requesting chat's settings.

**Change: `handle_schedule()` (line 486-532)**

Before (line 509):
```python
                result = scheduler.create_schedule(days=days)
```

After:
```python
                result = scheduler.create_schedule(
                    days=days,
                    telegram_chat_id=update.effective_chat.id,
                )
```

This is the only command handler change needed for Phase 03. The `/next`, `/queue`, `/pause`, `/resume` handlers already work with the correct chat context because they operate on queue items (which have `telegram_chat_id` set when the notification is sent) and check `self.service.is_paused` (which reads from the channel_id stored in the constructor). These will need further changes in a later phase when `channel_id` becomes per-tenant on TelegramService, but for Phase 03 they are correct.

---

### 4.8 `src/services/integrations/instagram_api.py` -- Keep defaults, no changes needed

The four references in `instagram_api.py` (lines 151, 478, 550, 627) all follow this pattern:
```python
        if telegram_chat_id is None:
            telegram_chat_id = settings.ADMIN_TELEGRAM_CHAT_ID
```

These are **default fallbacks** for when callers do not provide a `telegram_chat_id`. All Telegram-initiated calls (autopost handler, backfill command) already pass `chat_id` explicitly. The only caller that does not is `_post_via_instagram` in the posting service, which we are fixing in section 4.4. Therefore, these defaults are backward-compatible safety nets and do NOT need to change in Phase 03. They ensure CLI commands (which lack Telegram context) still work.

**Decision: No changes to `instagram_api.py` in Phase 03.**

---

### 4.9 `src/services/integrations/instagram_backfill.py` -- No changes needed

Same pattern as instagram_api.py -- the default fallback at line 155 is only used when `telegram_chat_id` is not provided (CLI usage). The Telegram handler at `telegram_commands.py` line 911 already passes `chat_id` explicitly. No changes needed.

---

### 4.10 `cli/commands/instagram.py` -- No changes needed

Lines 468 and 513 use `settings.ADMIN_TELEGRAM_CHAT_ID` for CLI-specific operations (adding accounts, listing active account). CLI commands are admin operations that naturally operate in the admin context. No changes needed.

---

### 4.11 `src/utils/validators.py` -- No changes needed

Lines 44-45 validate that `ADMIN_TELEGRAM_CHAT_ID` is configured. This remains correct -- the system still requires an admin chat ID for system-level operations and startup validation. No changes needed.

---

## 5. Summary of All File Changes

| File | Type of Change | Lines Changed |
|------|---------------|---------------|
| `src/repositories/chat_settings_repository.py` | Add `get_all_active()` method | +15 lines |
| `src/services/core/settings_service.py` | Add `get_all_active_chats()` method | +10 lines |
| `src/services/core/scheduler.py` | Add `telegram_chat_id` param to 4 methods | ~20 lines modified |
| `src/services/core/posting.py` | Add `telegram_chat_id` param to 2 methods | ~15 lines modified |
| `src/main.py` | Multi-tenant loop + pass settings_service | ~40 lines modified |
| `src/services/core/telegram_service.py` | Cache `admin_chat_id`, use in lifecycle methods | ~6 lines modified |
| `src/services/core/telegram_commands.py` | Pass `telegram_chat_id` in `/schedule` | 3 lines modified |

**Files explicitly NOT changed** (and why):
- `src/config/settings.py` -- `ADMIN_TELEGRAM_CHAT_ID` and `TELEGRAM_CHANNEL_ID` remain as required config fields. They are needed for backward compatibility and system-level operations.
- `src/services/integrations/instagram_api.py` -- Defaults are correct safety nets.
- `src/services/integrations/instagram_backfill.py` -- Same as above.
- `cli/commands/instagram.py` -- CLI operates in admin context by design.
- `src/utils/validators.py` -- Startup validation still correct.

## 6. Test Plan

### 6.1 New Tests

**`tests/src/repositories/test_chat_settings_repository.py` -- Add test for `get_all_active()`:**
```python
def test_get_all_active_returns_unpaused_chats(self, ...):
    """get_all_active returns only non-paused ChatSettings."""
    # Create 3 chat settings: 2 active, 1 paused
    # Call get_all_active()
    # Assert returns 2 records
    # Assert paused record is excluded

def test_get_all_active_returns_empty_when_all_paused(self, ...):
    """get_all_active returns empty list when all chats are paused."""

def test_get_all_active_returns_empty_when_no_records(self, ...):
    """get_all_active returns empty list when no chat_settings exist."""
```

**`tests/src/services/test_settings_service.py` -- Add test for `get_all_active_chats()`:**
```python
def test_get_all_active_chats_delegates_to_repository(self, ...):
    """get_all_active_chats delegates to settings_repo.get_all_active."""
    service.settings_repo.get_all_active.return_value = [mock_chat1, mock_chat2]
    result = service.get_all_active_chats()
    assert len(result) == 2
    service.settings_repo.get_all_active.assert_called_once()
```

### 6.2 Updated Tests

**`tests/src/services/test_scheduler.py`:**
- Update `test_create_schedule_creates_queue_items` -- verify `telegram_chat_id` is passed through
- Update `test_generate_time_slots` -- verify it accepts `telegram_chat_id` param
- Add `test_create_schedule_uses_chat_specific_settings` -- verify different chat_ids produce different schedules
- Add `test_generate_time_slots_falls_back_to_admin_when_no_chat_id` -- verify backward compatibility

**`tests/src/services/test_posting.py`:**
- Update `test_process_pending_queue_no_items` -- test with `telegram_chat_id` param
- Add `test_process_pending_posts_with_tenant_chat_id` -- verify per-tenant filtering
- Add `test_get_chat_settings_with_explicit_chat_id` -- verify the parameterized method
- Add `test_get_chat_settings_falls_back_to_admin` -- verify backward compat

**`tests/src/services/test_telegram_commands.py`:**
- Update `test_handle_schedule` (if it exists) -- verify `telegram_chat_id` is passed to `create_schedule`

**New test file: `tests/src/test_main_scheduler_loop.py`:**
```python
@pytest.mark.asyncio
async def test_scheduler_loop_iterates_over_active_chats():
    """Scheduler loop processes each active chat's queue independently."""

@pytest.mark.asyncio
async def test_scheduler_loop_falls_back_to_global_when_no_tenants():
    """Scheduler loop uses global posting when no active chats exist."""

@pytest.mark.asyncio
async def test_scheduler_loop_skips_failed_tenant():
    """One tenant's error does not prevent other tenants from processing."""
```

### 6.3 Existing Tests That Must Continue Passing

All existing tests should still pass because:
- New parameters are all `Optional` with defaults
- The fallback behavior (`if telegram_chat_id is None: telegram_chat_id = settings.ADMIN_TELEGRAM_CHAT_ID`) preserves existing behavior
- No function signatures are changed in a breaking way

The existing test mocks for `mock_settings.ADMIN_TELEGRAM_CHAT_ID = -100123` will continue to work because the fallback still uses that value.

## 7. Verification Checklist

- [ ] `get_all_active()` returns only non-paused chat settings
- [ ] `SchedulerService.create_schedule(telegram_chat_id=X)` uses chat X's settings (posts_per_day, hours)
- [ ] `SchedulerService.create_schedule()` (no arg) falls back to `ADMIN_TELEGRAM_CHAT_ID`
- [ ] `PostingService.process_pending_posts(telegram_chat_id=X)` checks chat X's pause state
- [ ] `PostingService.process_pending_posts()` (no arg) falls back to `self.telegram_service.is_paused`
- [ ] Scheduler loop in main.py iterates over all active tenants
- [ ] Scheduler loop gracefully handles empty tenant list (falls back to global)
- [ ] Scheduler loop handles per-tenant errors without stopping other tenants
- [ ] `/schedule 7` in Telegram passes `update.effective_chat.id` to `create_schedule`
- [ ] Startup/shutdown notifications still go to admin chat
- [ ] Sync error notifications use `telegram_service.channel_id` not `settings.TELEGRAM_CHANNEL_ID`
- [ ] All existing tests pass without modification (backward compatibility)
- [ ] `ruff check src/ tests/ cli/` passes
- [ ] `ruff format --check src/ tests/ cli/` passes
- [ ] `pytest` passes

## 8. What NOT To Do

1. **Do NOT remove `ADMIN_TELEGRAM_CHAT_ID` or `TELEGRAM_CHANNEL_ID` from `settings.py`**. These are still needed for system-level operations (startup notification, CLI commands, ConfigValidator).

2. **Do NOT change `TelegramService.channel_id` to be dynamic yet**. Making `send_notification()` route to per-tenant channels is a Phase 06 concern (onboarding wizard). In Phase 03, all notifications still go to the single configured channel.

3. **Do NOT add `chat_settings_id` FK to `posting_queue` table**. That is Phase 01/02 work (data model changes). Phase 03 assumes the FK already exists or can filter by chat context at the service layer.

4. **Do NOT make queue filtering per-tenant in the repository layer**. That is Phase 02 work. Phase 03 only threads the chat context through to `_get_chat_settings()` so that pause-state and posting-settings are per-tenant. The queue itself is still global in Phase 03 -- queue items are shared across tenants until Phase 02 adds tenant-scoped queries.

5. **Do NOT change CLI commands** to require a `--chat-id` flag. CLI is admin tooling and correctly uses `ADMIN_TELEGRAM_CHAT_ID`.

6. **Do NOT change `instagram_api.py` default fallbacks**. They are backward-compatible safety nets for CLI and system-level callers.

7. **Do NOT add multi-tenant media library support**. Media items are shared in Phase 03. Per-tenant media libraries are a future phase.

## 9. Migration / Deployment Notes

- No database migrations needed for Phase 03. All changes are in Python code.
- The `chat_settings` table already exists (migration 006).
- The `get_all_active()` query works on the existing table schema.
- Deployment is a simple code update -- no data migration, no schema changes.
- Backward compatible -- a deployment with zero `chat_settings` records will use the legacy single-tenant path.

## 10. Sequencing Within This Phase

Recommended implementation order:

1. **Repository + Service layer** (`chat_settings_repository.py`, `settings_service.py`) -- Add `get_all_active()` / `get_all_active_chats()` with tests
2. **Scheduler** (`scheduler.py`) -- Thread `telegram_chat_id` through with tests
3. **Posting** (`posting.py`) -- Thread `telegram_chat_id` through with tests
4. **Telegram handlers** (`telegram_commands.py`) -- Pass chat context in `/schedule`
5. **TelegramService** (`telegram_service.py`) -- Cache `admin_chat_id`, replace in lifecycle methods
6. **Main loop** (`main.py`) -- Per-tenant scheduler loop with tests
7. **Final pass** -- Verify all `ADMIN_TELEGRAM_CHAT_ID` references are either parameterized or documented as intentional

## Critical Files for Implementation

- `/Users/chris/Projects/storyline-ai/src/main.py` - Core loop to update: per-tenant scheduler iteration
- `/Users/chris/Projects/storyline-ai/src/services/core/scheduler.py` - Thread `telegram_chat_id` through time-slot generation
- `/Users/chris/Projects/storyline-ai/src/services/core/posting.py` - Thread `telegram_chat_id` through `process_pending_posts` and `_get_chat_settings`
- `/Users/chris/Projects/storyline-ai/src/repositories/chat_settings_repository.py` - Add `get_all_active()` for tenant discovery
- `/Users/chris/Projects/storyline-ai/src/services/core/telegram_service.py` - Replace hardcoded `settings.ADMIN_TELEGRAM_CHAT_ID` in lifecycle notifications
