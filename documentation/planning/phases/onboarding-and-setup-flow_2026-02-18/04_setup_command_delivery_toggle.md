# Phase 04: `/setup` Command + Smart Delivery Toggle

## Onboarding and Setup Flow -- Phase 04 Implementation Plan

---

## 1. Header

**PR Title**: `feat: rename /settings to /setup, add smart delivery toggle with +24hr auto-reschedule`

**Risk Level**: Low

**Estimated Effort**: Medium (2-3 days)

**Files Created**:
- `tests/src/services/test_posting_delivery_reschedule.py` -- New test file for smart reschedule logic

**Files Modified**:
- `src/services/core/telegram_settings.py` -- Rename command, add Mini App button, update delivery toggle display
- `src/services/core/telegram_service.py` -- Register `/setup` command, keep `/settings` as alias
- `src/services/core/telegram_commands.py` -- Update `/pause` and `/resume` response messages to "delivery" language, trigger immediate reschedule on pause
- `src/services/core/posting.py` -- Add smart reschedule logic when paused
- `src/repositories/queue_repository.py` -- Add `get_overdue_pending_posts()` and `bulk_reschedule_overdue()` methods
- `src/repositories/chat_settings_repository.py` -- Add `get_all_paused()` method for scheduler loop
- `src/main.py` -- Add reschedule loop for paused tenants
- `src/services/core/settings_service.py` -- Add `get_all_paused_chats()` method
- `tests/src/services/test_telegram_settings.py` -- Update existing tests for new button labels, add `/setup` tests
- `tests/src/services/test_posting.py` -- Add tests for smart reschedule behavior
- `tests/src/repositories/test_queue_repository.py` -- Add tests for new repository methods
- `CHANGELOG.md` -- Add Phase 04 entry

**Files Deleted**: None

---

## 2. Context

### Why rename `/settings` to `/setup`?

The `/settings` command currently serves as the in-channel quick-access configuration panel. As we introduce the Mini App (Phase 03), we want the Telegram command to be the "quick setup" entry point that also links to the full web-based settings experience. The name `/setup` better communicates this dual purpose: quick toggles in Telegram plus a gateway to the full Mini App. We keep `/settings` as an alias for backward compatibility so existing muscle memory still works.

### Why smart delivery toggle?

The current `is_paused` behavior simply skips all scheduled posts while paused. When a user unpauses, they are greeted with a pile of overdue posts that either fire all at once or require manual cleanup. The "smart delivery" approach reframes "paused" as "delivery OFF" and automatically bumps overdue items forward by 24 hours. This means:

- Queue items are never lost or stale when delivery is turned off for a day or two.
- When delivery is turned back on, posts resume from sensible future times.
- No manual intervention needed to handle overdue posts after a pause period.

### Critical architectural discovery: the scheduler loop skips paused tenants

The current `run_scheduler_loop()` in `src/main.py` calls `settings_service.get_all_active_chats()` which only returns chats where `is_paused == False`. This means `process_pending_posts()` is never called for paused tenants. Therefore, we cannot rely solely on `process_pending_posts()` to do the rescheduling.

The solution is a dedicated reschedule pass in the scheduler loop that runs against paused tenants, separate from the posting pass that runs against active tenants.

---

## 3. Dependencies

- **Phase 01 (per-chat media source columns)** -- Must be complete because Phase 01 may add columns to `chat_settings` that this phase's settings display needs to reference.
- **Phase 03 (Mini App home screen)** -- Must be complete because the "Open Full Settings" button we add here opens the Mini App URL, which must exist and render.

---

## 4. Detailed Implementation Plan

### Step 1: Add `get_overdue_pending_posts()` to QueueRepository

**File**: `/Users/chris/Projects/storyline-ai/src/repositories/queue_repository.py`

**What**: Add a new method that returns all pending queue items whose `scheduled_for` is in the past.

**Where**: After the existing `get_pending()` method (line 72).

**Code to add** (after line 72, before the `get_all` method):

```python
def get_overdue_pending(
    self, chat_settings_id: Optional[str] = None
) -> List[PostingQueue]:
    """Get all pending queue items whose scheduled_for time has passed.

    Used by the smart delivery reschedule logic to find items that need
    to be bumped forward when delivery is OFF.

    Args:
        chat_settings_id: Optional tenant filter

    Returns:
        List of overdue PostingQueue items, ordered by scheduled_for ASC
    """
    now = datetime.utcnow()
    query = self.db.query(PostingQueue).filter(
        and_(PostingQueue.status == "pending", PostingQueue.scheduled_for <= now)
    )
    query = self._apply_tenant_filter(query, PostingQueue, chat_settings_id)
    return query.order_by(PostingQueue.scheduled_for.asc()).all()

def bulk_reschedule_overdue(
    self, chat_settings_id: Optional[str] = None
) -> int:
    """Bump all overdue pending items forward by +24 hours until they are in the future.

    For each overdue item, repeatedly adds 24 hours to scheduled_for
    until the time is in the future. Commits all changes in a single transaction.

    Args:
        chat_settings_id: Optional tenant filter

    Returns:
        Number of items rescheduled
    """
    overdue_items = self.get_overdue_pending(chat_settings_id=chat_settings_id)
    if not overdue_items:
        return 0

    now = datetime.utcnow()
    for item in overdue_items:
        while item.scheduled_for <= now:
            item.scheduled_for = item.scheduled_for + timedelta(hours=24)

    self.db.commit()
    return len(overdue_items)
```

**Why a repository method**: The reschedule logic is a pure data operation (bump timestamps). Putting it in the repository keeps business logic in the service layer (which decides when to call it) while the actual data mutation stays in the repository. The `bulk_reschedule_overdue` method combines the query and update into one call for efficiency.

### Step 2: Add `get_all_paused()` to ChatSettingsRepository

**File**: `/Users/chris/Projects/storyline-ai/src/repositories/chat_settings_repository.py`

**What**: Add a method to retrieve all paused chat settings, for the scheduler loop to run the reschedule pass.

**Where**: After the existing `get_all_active()` method (after line 118).

**Code to add**:

```python
def get_all_paused(self) -> List[ChatSettings]:
    """Get all paused chat settings records.

    Used by the scheduler loop to run smart delivery reschedule
    on paused tenants (bumping overdue items +24hr).

    Returns:
        List of paused ChatSettings, ordered by created_at
    """
    result = (
        self.db.query(ChatSettings)
        .filter(ChatSettings.is_paused == True)  # noqa: E712
        .order_by(ChatSettings.created_at.asc())
        .all()
    )
    self.end_read_transaction()
    return result
```

### Step 3: Add `get_all_paused_chats()` to SettingsService

**File**: `/Users/chris/Projects/storyline-ai/src/services/core/settings_service.py`

**What**: Expose the repository method through the service layer.

**Where**: After the existing `get_all_active_chats()` method (after line 221).

**Code to add**:

```python
def get_all_paused_chats(self) -> List[ChatSettings]:
    """Get all paused chat settings.

    Used by the scheduler loop to run smart delivery reschedule
    on paused tenants.

    Returns:
        List of ChatSettings records where is_paused=True
    """
    return self.settings_repo.get_all_paused()
```

Also add the `List` import if not already present. Check line 1: `from typing import Optional, Any, Dict, List` -- it is already imported.

### Step 4: Add smart reschedule method to PostingService

**File**: `/Users/chris/Projects/storyline-ai/src/services/core/posting.py`

**What**: Add a method that the scheduler loop calls for paused tenants to reschedule their overdue items.

**Where**: After the existing `process_pending_posts()` method (after line 331).

**Code to add**:

```python
def reschedule_overdue_for_paused_chat(
    self, telegram_chat_id: int
) -> dict:
    """Reschedule overdue queue items for a paused (delivery OFF) tenant.

    When delivery is OFF, items whose scheduled_for passes are bumped
    +24 hours (repeatedly until in the future). This keeps the queue
    valid without losing any items.

    Called by the scheduler loop for each paused tenant.

    Args:
        telegram_chat_id: The tenant's Telegram chat ID

    Returns:
        Dict with results: {"rescheduled": int, "chat_id": int}
    """
    chat_settings = self._get_chat_settings(telegram_chat_id)
    chat_settings_id = str(chat_settings.id) if chat_settings else None

    rescheduled = self.queue_repo.bulk_reschedule_overdue(
        chat_settings_id=chat_settings_id
    )

    if rescheduled > 0:
        logger.info(
            f"[delivery=OFF, chat={telegram_chat_id}] "
            f"Rescheduled {rescheduled} overdue items +24hr"
        )

    return {"rescheduled": rescheduled, "chat_id": telegram_chat_id}
```

**Note**: This method is intentionally synchronous (not `async`) because it only does database operations. No `track_execution` wrapper is used to keep it lightweight -- it runs every minute for every paused tenant.

### Step 5: Add reschedule pass to the scheduler loop

**File**: `/Users/chris/Projects/storyline-ai/src/main.py`

**What**: After processing active chats, iterate over paused chats and reschedule their overdue items.

**Where**: Inside `run_scheduler_loop()`, after the existing `if active_chats:` block (after line 76), before the `except` on line 79.

**Current code** (lines 46-78):
```python
if active_chats:
    # Multi-tenant mode: process each tenant's queue
    for chat in active_chats:
        try:
            result = await posting_service.process_pending_posts(
                telegram_chat_id=chat.telegram_chat_id
            )
            # ... logging ...
        except Exception as e:
            # ... error logging ...
else:
    # Legacy single-tenant fallback
    result = await posting_service.process_pending_posts()
    # ... logging ...
```

**Modified code** -- add paused-chat reschedule pass after the active-chat block:

```python
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

    # Smart delivery reschedule for paused tenants
    paused_chats = settings_service.get_all_paused_chats()
    for chat in paused_chats:
        try:
            posting_service.reschedule_overdue_for_paused_chat(
                telegram_chat_id=chat.telegram_chat_id
            )
        except Exception as e:
            logger.error(
                f"Error rescheduling for paused chat "
                f"{chat.telegram_chat_id}: {e}",
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
```

### Step 6: Register `/setup` command and keep `/settings` as alias

**File**: `/Users/chris/Projects/storyline-ai/src/services/core/telegram_service.py`

**What**: Add `/setup` as the primary command and keep `/settings` as an alias pointing to the same handler.

**Where**: In the `command_map` dictionary inside `initialize()`, around line 125-145.

**Current code** (line 144):
```python
"settings": self.settings_handler.handle_settings,
```

**Modified code** -- add `setup` to the command map:
```python
"settings": self.settings_handler.handle_settings,
"setup": self.settings_handler.handle_settings,
```

Also update the BotCommand list for the autocomplete menu (lines 159-179). Add `setup` and update the description for `settings`:

**Current** (line 173):
```python
BotCommand("settings", "Configure bot settings"),
```

**Modified** -- add `/setup` and mark `/settings` as alias:
```python
BotCommand("setup", "Quick settings + open full setup wizard"),
BotCommand("settings", "Alias for /setup"),
```

### Step 7: Update interaction logging in handle_settings to log both `/setup` and `/settings`

**File**: `/Users/chris/Projects/storyline-ai/src/services/core/telegram_settings.py`

**What**: Update the `handle_settings` method to detect which command was used (`/setup` or `/settings`) and log it correctly.

**Where**: In `handle_settings()`, around line 114-131.

**Current code** (lines 120-125):
```python
self.service.interaction_service.log_command(
    user_id=str(user.id),
    command="/settings",
    telegram_chat_id=chat_id,
    telegram_message_id=update.message.message_id,
)
```

**Modified code** -- detect actual command used:
```python
# Log the actual command used (could be /setup or /settings alias)
command_text = update.message.text.split()[0] if update.message.text else "/setup"
self.service.interaction_service.log_command(
    user_id=str(user.id),
    command=command_text,
    telegram_chat_id=chat_id,
    telegram_message_id=update.message.message_id,
)
```

### Step 8: Update the delivery toggle button label in build_settings_message_and_keyboard

**File**: `/Users/chris/Projects/storyline-ai/src/services/core/telegram_settings.py`

**What**: Replace the "Paused" / "Active" button with a "Delivery: ON/OFF" button.

**Where**: In `build_settings_message_and_keyboard()`, lines 62-68.

**Current code**:
```python
[
    InlineKeyboardButton(
        "⏸️ Paused" if settings_data["is_paused"] else "▶️ Active",
        callback_data="settings_toggle:is_paused",
    ),
],
```

**Modified code**:
```python
[
    InlineKeyboardButton(
        "📦 Delivery: ❌ OFF" if settings_data["is_paused"] else "📦 Delivery: ✅ ON",
        callback_data="settings_toggle:is_paused",
    ),
],
```

### Step 9: Add "Open Full Settings" Mini App button

**File**: `/Users/chris/Projects/storyline-ai/src/services/core/telegram_settings.py`

**What**: Add a WebAppInfo button at the bottom of the keyboard (before the Close button) that opens the Mini App.

**Where**: In `build_settings_message_and_keyboard()`, right before the Close button row (line 109).

**What to add** -- import `WebAppInfo` at the top of the file, then add the button:

At the top of the file, update the import on line 7:

**Current**:
```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
```

**Modified**:
```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
```

Also add the settings import for `OAUTH_REDIRECT_BASE_URL`:

```python
from src.config.settings import settings as app_settings
```

Then in the keyboard definition, insert a new row before the Close button (before the `[InlineKeyboardButton("❌ Close", callback_data="settings_close")]` row):

```python
# "Open Full Settings" button (only if Mini App URL is configured)
if app_settings.OAUTH_REDIRECT_BASE_URL:
    webapp_url = (
        f"{app_settings.OAUTH_REDIRECT_BASE_URL}/webapp/onboarding"
        f"?chat_id={chat_id}"
    )
    keyboard.append(
        [
            InlineKeyboardButton(
                "🔧 Open Full Settings",
                web_app=WebAppInfo(url=webapp_url),
            )
        ]
    )
```

**Important**: The `build_settings_message_and_keyboard` method currently receives `chat_id` as a parameter, so this value is already available.

### Step 10: Update the header message in /setup

**File**: `/Users/chris/Projects/storyline-ai/src/services/core/telegram_settings.py`

**Where**: In `build_settings_message_and_keyboard()`, lines 42-46.

**Current code**:
```python
message = (
    "⚙️ *Bot Settings*\n\n"
    "_Regenerate: Clears queue, creates new schedule_\n"
    "_+7 Days: Extends existing queue_"
)
```

**Modified code**:
```python
message = (
    "⚙️ *Quick Setup*\n\n"
    "_Regenerate: Clears queue, creates new schedule_\n"
    "_+7 Days: Extends existing queue_"
)
```

### Step 11: Update `/pause` and `/resume` commands to use "delivery" language

**File**: `/Users/chris/Projects/storyline-ai/src/services/core/telegram_commands.py`

**What**: Update the response messages for `/pause` and `/resume` to use "delivery" terminology instead of "posting paused/resumed".

#### `/pause` handler (lines 435-463)

**Current response when not already paused** (lines 447-453):
```python
await update.message.reply_text(
    f"⏸️ *Posting Paused*\n\n"
    f"Automatic posting has been paused.\n"
    f"📊 {pending_count} posts still in queue.\n\n"
    f"Use /resume to restart posting.\n"
    f"Use /next to manually send posts.",
    parse_mode="Markdown",
)
```

**Modified**:
```python
await update.message.reply_text(
    f"📦 *Delivery OFF*\n\n"
    f"Automatic delivery has been turned off.\n"
    f"📊 {pending_count} posts still in queue.\n"
    f"Overdue items will be auto-rescheduled +24hr.\n\n"
    f"Use /resume to turn delivery back on.\n"
    f"Use /next to manually send posts.",
    parse_mode="Markdown",
)
```

**Current response when already paused** (lines 440-443):
```python
await update.message.reply_text(
    "⏸️ *Already Paused*\n\nAutomatic posting is already paused.\nUse /resume to restart.",
    parse_mode="Markdown",
)
```

**Modified**:
```python
await update.message.reply_text(
    "📦 *Delivery Already OFF*\n\nDelivery is already turned off.\nUse /resume to turn it back on.",
    parse_mode="Markdown",
)
```

Also add: trigger an immediate reschedule of overdue items when pausing. After `self.service.set_paused(True, user)` on line 445, add:

```python
self.service.set_paused(True, user)

# Immediately reschedule any currently overdue items
from src.services.core.posting import PostingService
with PostingService() as posting_service:
    result = posting_service.reschedule_overdue_for_paused_chat(
        telegram_chat_id=update.effective_chat.id
    )
rescheduled = result.get("rescheduled", 0)

pending_count = self.service.queue_repo.count_pending()
reschedule_note = (
    f"\n🔄 Rescheduled {rescheduled} overdue items +24hr."
    if rescheduled > 0
    else ""
)
await update.message.reply_text(
    f"📦 *Delivery OFF*\n\n"
    f"Automatic delivery has been turned off.\n"
    f"📊 {pending_count} posts still in queue.{reschedule_note}\n"
    f"Overdue items will be auto-rescheduled +24hr.\n\n"
    f"Use /resume to turn delivery back on.\n"
    f"Use /next to manually send posts.",
    parse_mode="Markdown",
)
```

#### `/resume` handler (lines 465-524)

**Current response when not paused** (lines 470-473):
```python
await update.message.reply_text(
    "▶️ *Already Running*\n\nAutomatic posting is already active.",
    parse_mode="Markdown",
)
```

**Modified**:
```python
await update.message.reply_text(
    "📦 *Delivery Already ON*\n\nDelivery is already active.",
    parse_mode="Markdown",
)
```

The overdue-handling flow for `/resume` (lines 481-517) already has excellent UX with the Reschedule/Clear/Resume buttons. Update the text to use "delivery" language:

**Current** (lines 498-506):
```python
await update.message.reply_text(
    f"⚠️ *{len(overdue)} Overdue Posts Found*\n\n"
    f"These posts were scheduled while paused:\n"
    ...
```

**Modified**:
```python
await update.message.reply_text(
    f"⚠️ *{len(overdue)} Overdue Posts Found*\n\n"
    f"These posts were scheduled while delivery was off:\n"
    ...
```

The non-overdue resume path (lines 507-517):

**Current**:
```python
self.service.set_paused(False, user)
await update.message.reply_text(
    f"▶️ *Posting Resumed*\n\n"
    f"Automatic posting is now active.\n"
    f"📊 {len(future)} posts scheduled.",
    parse_mode="Markdown",
)
```

**Modified**:
```python
self.service.set_paused(False, user)
await update.message.reply_text(
    f"📦 *Delivery ON*\n\n"
    f"Automatic delivery is now active.\n"
    f"📊 {len(future)} posts scheduled.",
    parse_mode="Markdown",
)
```

### Step 12: Update `/help` text

**File**: `/Users/chris/Projects/storyline-ai/src/services/core/telegram_commands.py`

**Where**: In `handle_help()`, lines 325-351.

**Current** (line 333):
```python
"/settings - View/toggle bot settings\n"
```

**Modified**:
```python
"/setup - Quick settings + open full setup wizard\n"
```

And also update pause/resume descriptions:

**Current** (lines 334-335):
```python
"/pause - Pause automatic posting\n"
"/resume - Resume posting\n"
```

**Modified**:
```python
"/pause - Turn delivery off (auto-reschedules queue)\n"
"/resume - Turn delivery on\n"
```

### Step 13: Update `/status` display for delivery state

**File**: `/Users/chris/Projects/storyline-ai/src/services/core/telegram_commands.py`

**Where**: In `handle_status()`, line 109.

**Current**:
```python
pause_status = "⏸️ PAUSED" if self.service.is_paused else "▶️ Active"
```

**Modified**:
```python
pause_status = "📦 Delivery OFF" if self.service.is_paused else "📦 Delivery ON"
```

And line 117:

**Current**:
```python
f"⏯️ Posting: {pause_status}\n"
```

This remains the same -- the variable name changes but the format string stays the same.

### Step 14: Update resume callback handler to use delivery language

**File**: `/Users/chris/Projects/storyline-ai/src/services/core/telegram_callbacks.py`

**Where**: In `handle_resume_callback()`, lines 375-443.

Update the response messages in the three branches (reschedule, clear, force):

For the `reschedule` branch (lines 391-397):
```python
# Current
f"✅ *Posting Resumed*\n\n"
f"🔄 Rescheduled {rescheduled} overdue posts.\n"
f"First post in ~1 hour.",

# Modified
f"📦 *Delivery ON*\n\n"
f"🔄 Rescheduled {rescheduled} overdue posts.\n"
f"First post in ~1 hour.",
```

For the `clear` branch (lines 411-416):
```python
# Current
f"✅ *Posting Resumed*\n\n"

# Modified
f"📦 *Delivery ON*\n\n"
```

For the `force` branch (lines 425-429):
```python
# Current
f"✅ *Posting Resumed*\n\n"

# Modified
f"📦 *Delivery ON*\n\n"
```

---

## 5. Test Plan

### 5a. New test file: `tests/src/services/test_posting_delivery_reschedule.py`

This file tests the smart delivery reschedule logic in isolation.

```python
"""Tests for smart delivery reschedule logic in PostingService."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from contextlib import contextmanager
from uuid import uuid4

from src.services.core.posting import PostingService


@contextmanager
def mock_track_execution(*args, **kwargs):
    """Mock context manager for track_execution."""
    yield "mock_run_id"


@pytest.fixture
def posting_service():
    """Create PostingService with mocked dependencies."""
    with patch.object(PostingService, "__init__", lambda self: None):
        service = PostingService()
        service.queue_repo = Mock()
        service.media_repo = Mock()
        service.history_repo = Mock()
        service.telegram_service = Mock()
        service.lock_service = Mock()
        service.settings_service = Mock()
        service.service_run_repo = Mock()
        service.service_name = "PostingService"
        service._instagram_service = None
        service._cloud_service = None
        service.track_execution = mock_track_execution
        service.set_result_summary = Mock()
        return service


@pytest.mark.unit
class TestRescheduleOverdueForPausedChat:
    """Tests for PostingService.reschedule_overdue_for_paused_chat()."""

    def test_reschedule_calls_bulk_reschedule(self, posting_service):
        """reschedule_overdue_for_paused_chat calls queue_repo.bulk_reschedule_overdue."""
        mock_settings = Mock()
        mock_settings.id = uuid4()
        posting_service.settings_service.get_settings.return_value = mock_settings
        posting_service.queue_repo.bulk_reschedule_overdue.return_value = 3

        result = posting_service.reschedule_overdue_for_paused_chat(
            telegram_chat_id=-100123
        )

        posting_service.queue_repo.bulk_reschedule_overdue.assert_called_once_with(
            chat_settings_id=str(mock_settings.id)
        )
        assert result["rescheduled"] == 3
        assert result["chat_id"] == -100123

    def test_reschedule_with_no_overdue_items(self, posting_service):
        """Returns 0 rescheduled when no items are overdue."""
        mock_settings = Mock()
        mock_settings.id = uuid4()
        posting_service.settings_service.get_settings.return_value = mock_settings
        posting_service.queue_repo.bulk_reschedule_overdue.return_value = 0

        result = posting_service.reschedule_overdue_for_paused_chat(
            telegram_chat_id=-100123
        )

        assert result["rescheduled"] == 0

    def test_reschedule_passes_correct_tenant_id(self, posting_service):
        """Verifies tenant ID is correctly threaded through."""
        mock_settings = Mock()
        mock_settings.id = uuid4()
        posting_service.settings_service.get_settings.return_value = mock_settings
        posting_service.queue_repo.bulk_reschedule_overdue.return_value = 0

        posting_service.reschedule_overdue_for_paused_chat(telegram_chat_id=-200456)

        posting_service.settings_service.get_settings.assert_called_with(-200456)
```

### 5b. Updates to `tests/src/repositories/test_queue_repository.py`

Add tests for `get_overdue_pending()` and `bulk_reschedule_overdue()`:

```python
@pytest.mark.unit
class TestOverduePendingMethods:
    """Tests for overdue pending queue item methods."""

    def test_get_overdue_pending(self, queue_repo, mock_db):
        """get_overdue_pending returns items with scheduled_for in the past."""
        mock_items = [MagicMock(status="pending"), MagicMock(status="pending")]
        mock_query = mock_db.query.return_value
        mock_query.all.return_value = mock_items

        result = queue_repo.get_overdue_pending()

        assert len(result) == 2
        mock_db.query.assert_called_with(PostingQueue)

    def test_get_overdue_pending_with_tenant(self, queue_repo, mock_db):
        """get_overdue_pending passes chat_settings_id through tenant filter."""
        mock_db.query.return_value.all.return_value = []
        with patch.object(
            queue_repo, "_apply_tenant_filter", wraps=queue_repo._apply_tenant_filter
        ) as mock_filter:
            queue_repo.get_overdue_pending(chat_settings_id="tenant-1")
            mock_filter.assert_called_once()
            assert mock_filter.call_args[0][2] == "tenant-1"

    def test_bulk_reschedule_overdue_bumps_items(self, queue_repo, mock_db):
        """bulk_reschedule_overdue adds 24hr to overdue items until they are future."""
        now = datetime.utcnow()
        item_1 = MagicMock()
        item_1.scheduled_for = now - timedelta(hours=2)  # 2 hours overdue
        item_2 = MagicMock()
        item_2.scheduled_for = now - timedelta(hours=50)  # 50 hours overdue (needs 3 bumps)

        with patch.object(queue_repo, "get_overdue_pending", return_value=[item_1, item_2]):
            count = queue_repo.bulk_reschedule_overdue()

        assert count == 2
        assert item_1.scheduled_for > now  # Should be ~22hr in future
        assert item_2.scheduled_for > now  # Should be ~22hr in future after 3 bumps
        mock_db.commit.assert_called_once()

    def test_bulk_reschedule_overdue_no_items(self, queue_repo, mock_db):
        """bulk_reschedule_overdue returns 0 when no items overdue."""
        with patch.object(queue_repo, "get_overdue_pending", return_value=[]):
            count = queue_repo.bulk_reschedule_overdue()

        assert count == 0
        mock_db.commit.assert_not_called()

    def test_bulk_reschedule_item_far_in_past_needs_multiple_bumps(self, queue_repo, mock_db):
        """An item scheduled 5 days ago needs 5 bumps of +24hr."""
        now = datetime.utcnow()
        item = MagicMock()
        item.scheduled_for = now - timedelta(days=5, hours=1)  # 5 days + 1hr ago

        with patch.object(queue_repo, "get_overdue_pending", return_value=[item]):
            queue_repo.bulk_reschedule_overdue()

        # After 6 bumps of 24hr, should be ~23hr in the future
        assert item.scheduled_for > now
        # Should be less than 24hr in the future (6*24 - 5*24 - 1 = 23hr)
        assert item.scheduled_for < now + timedelta(hours=24)
```

### 5c. Updates to `tests/src/services/test_telegram_settings.py`

Update existing tests and add new ones for the `/setup` changes:

```python
# Update test_paused_toggle_shows_correct_state to check for new label
def test_delivery_toggle_shows_correct_state(self, mock_settings_handlers):
    """Test that delivery button shows OFF when paused, ON when active."""
    mock_settings_handlers.service.settings_service.get_settings_display.return_value = {
        "dry_run_mode": False,
        "enable_instagram_api": False,
        "is_paused": True,
        "posts_per_day": 3,
        "posting_hours_start": 9,
        "posting_hours_end": 21,
        "show_verbose_notifications": True,
        "media_sync_enabled": False,
    }
    mock_settings_handlers.service.ig_account_service.get_accounts_for_display.return_value = {
        "active_account_id": None,
        "active_account_name": "Not selected",
    }

    _, markup = mock_settings_handlers.build_settings_message_and_keyboard(-100123)

    all_buttons = [btn for row in markup.inline_keyboard for btn in row]
    delivery_buttons = [
        b for b in all_buttons if "Delivery" in b.text
    ]
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
    }
    mock_settings_handlers.service.ig_account_service.get_accounts_for_display.return_value = {
        "active_account_id": None,
        "active_account_name": "Not selected",
    }

    _, markup = mock_settings_handlers.build_settings_message_and_keyboard(-100123)

    all_buttons = [btn for row in markup.inline_keyboard for btn in row]
    delivery_buttons = [
        b for b in all_buttons if "Delivery" in b.text
    ]
    assert len(delivery_buttons) == 1
    assert "ON" in delivery_buttons[0].text


def test_setup_header_text(self, mock_settings_handlers):
    """Test that /setup shows 'Quick Setup' header."""
    mock_settings_handlers.service.settings_service.get_settings_display.return_value = {
        "dry_run_mode": False,
        "enable_instagram_api": False,
        "is_paused": False,
        "posts_per_day": 3,
        "posting_hours_start": 9,
        "posting_hours_end": 21,
        "show_verbose_notifications": True,
        "media_sync_enabled": False,
    }
    mock_settings_handlers.service.ig_account_service.get_accounts_for_display.return_value = {
        "active_account_id": None,
        "active_account_name": "Not selected",
    }

    message, _ = mock_settings_handlers.build_settings_message_and_keyboard(-100123)

    assert "Quick Setup" in message


@patch("src.services.core.telegram_settings.app_settings")
def test_mini_app_button_present_when_configured(self, mock_app_settings, mock_settings_handlers):
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
    }
    mock_settings_handlers.service.ig_account_service.get_accounts_for_display.return_value = {
        "active_account_id": None,
        "active_account_name": "Not selected",
    }

    _, markup = mock_settings_handlers.build_settings_message_and_keyboard(-100123)

    all_buttons = [btn for row in markup.inline_keyboard for btn in row]
    mini_app_buttons = [b for b in all_buttons if "Full Settings" in b.text]
    assert len(mini_app_buttons) == 1
    assert mini_app_buttons[0].web_app is not None


@patch("src.services.core.telegram_settings.app_settings")
def test_mini_app_button_absent_when_not_configured(self, mock_app_settings, mock_settings_handlers):
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
    }
    mock_settings_handlers.service.ig_account_service.get_accounts_for_display.return_value = {
        "active_account_id": None,
        "active_account_name": "Not selected",
    }

    _, markup = mock_settings_handlers.build_settings_message_and_keyboard(-100123)

    all_buttons = [btn for row in markup.inline_keyboard for btn in row]
    mini_app_buttons = [b for b in all_buttons if "Full Settings" in b.text]
    assert len(mini_app_buttons) == 0
```

### 5d. Updates to `tests/src/services/test_posting.py`

The existing `test_process_pending_posts_tenant_paused` test checks that paused returns early. Add a note that rescheduling is now handled by a separate method (no change to the test itself -- it should still pass because `process_pending_posts` still returns early for paused tenants).

---

## 6. Documentation Updates

### CHANGELOG.md entry

Add under `## [Unreleased]`:

```markdown
### Changed

- **`/settings` renamed to `/setup`** - Primary command is now `/setup` for quick settings access; `/settings` remains as an alias for backward compatibility
  - Header changed from "Bot Settings" to "Quick Setup"
  - Added "Open Full Settings" button that launches the Mini App (when `OAUTH_REDIRECT_BASE_URL` is configured)

- **"Paused" reframed as "Delivery OFF"** - All pause/resume UI and messaging now uses "delivery" language
  - Settings toggle: "Paused" / "Active" replaced with "Delivery: ON/OFF"
  - `/pause` response: "Posting Paused" replaced with "Delivery OFF"
  - `/resume` response: "Posting Resumed" replaced with "Delivery ON"
  - `/status` display: updated to show "Delivery ON/OFF"

### Added

- **Smart delivery reschedule** - When delivery is OFF, overdue queue items are automatically bumped +24 hours instead of piling up
  - Runs every minute in the scheduler loop for all paused tenants
  - Items far in the past get multiple +24hr bumps until they are in the future
  - Immediate reschedule triggered when `/pause` is invoked
  - New `QueueRepository.get_overdue_pending()` and `bulk_reschedule_overdue()` methods
  - New `PostingService.reschedule_overdue_for_paused_chat()` method
  - New `SettingsService.get_all_paused_chats()` / `ChatSettingsRepository.get_all_paused()` for scheduler loop
```

### CLAUDE.md updates

In the Telegram Bot Commands Reference table, add the `/setup` command:

```markdown
| `/setup` | Quick settings + open setup wizard | `telegram_settings.py` |
| `/settings` | Alias for /setup | `telegram_settings.py` |
```

Update the `/pause` and `/resume` descriptions to mention delivery language.

---

## 7. Stress Testing and Edge Cases

### Edge Case 1: Items scheduled far in the past (need multiple +24hr bumps)

**Scenario**: A tenant paused delivery 5 days ago. There are 15 queue items whose `scheduled_for` was 3-5 days in the past.

**Expected behavior**: `bulk_reschedule_overdue()` loops `while item.scheduled_for <= now` adding 24 hours each iteration. An item scheduled 5 days ago gets 5-6 bumps. This is O(n * k) where k is typically small (max ~30 bumps for a month-old item).

**Test**: `test_bulk_reschedule_item_far_in_past_needs_multiple_bumps` covers this.

### Edge Case 2: Empty queue when pausing

**Scenario**: User runs `/pause` but the queue is empty.

**Expected behavior**: `reschedule_overdue_for_paused_chat()` calls `bulk_reschedule_overdue()` which calls `get_overdue_pending()` returning an empty list, returns 0. The response message shows "0 posts still in queue" and no reschedule note.

**Test**: `test_reschedule_with_no_overdue_items` covers this.

### Edge Case 3: Unpausing with rescheduled items

**Scenario**: Items were bumped +24hr while delivery was OFF. User turns delivery back on.

**Expected behavior**: Items now have future `scheduled_for` times. They will be processed normally by `process_pending_posts()` when their time comes. No special handling needed -- the existing resume flow already handles this correctly.

### Edge Case 4: Race condition -- reschedule runs while user is toggling pause

**Scenario**: The scheduler loop is running `reschedule_overdue_for_paused_chat()` at the exact moment a user clicks the delivery toggle.

**Expected behavior**: Both operations use SQLAlchemy's session. The reschedule commits first, then the toggle commits. Since the toggle only changes `is_paused` and the reschedule only changes `scheduled_for`, they operate on different columns and there is no conflict. In the worst case, an extra unnecessary reschedule runs (harmless -- items are already in the future so `get_overdue_pending()` returns empty).

### Edge Case 5: Legacy single-tenant mode

**Scenario**: `settings_service` is None in the scheduler loop (no multi-tenant mode).

**Expected behavior**: The legacy fallback path does not call `get_all_paused_chats()`. In legacy mode, the existing `process_pending_posts()` behavior applies (check `telegram_service.is_paused`, skip if paused). The smart reschedule does not run in legacy mode. This is acceptable because legacy mode is a transitional state.

### Edge Case 6: `/settings` alias still works

**Scenario**: User types `/settings` instead of `/setup`.

**Expected behavior**: Both commands call the same handler (`handle_settings`). The command map registers both. The interaction log records the actual command typed.

### Edge Case 7: Mini App URL not configured

**Scenario**: `OAUTH_REDIRECT_BASE_URL` is None (local development without Railway).

**Expected behavior**: The "Open Full Settings" button is simply not shown. The conditional check `if app_settings.OAUTH_REDIRECT_BASE_URL:` prevents it from appearing.

---

## 8. Verification Checklist

After implementation, run these commands to verify:

```bash
# 1. Lint check
source venv/bin/activate && ruff check src/ tests/ cli/

# 2. Format check
ruff format --check src/ tests/ cli/

# 3. Run all tests
pytest

# 4. Run specific new tests
pytest tests/src/services/test_posting_delivery_reschedule.py -v
pytest tests/src/services/test_telegram_settings.py -v
pytest tests/src/repositories/test_queue_repository.py -v
pytest tests/src/services/test_posting.py -v

# 5. Verify /setup and /settings alias both registered
grep -n '"setup"\|"settings"' src/services/core/telegram_service.py

# 6. Verify delivery toggle label
grep -n "Delivery" src/services/core/telegram_settings.py

# 7. Verify no "Paused" / "Active" labels remain (except in tests that might reference old names)
grep -rn '"Paused"\|"Active"' src/services/core/telegram_settings.py
# Should show 0 matches (all replaced with Delivery ON/OFF)

# 8. Verify Mini App button
grep -n "WebAppInfo\|Full Settings" src/services/core/telegram_settings.py

# 9. Verify bulk_reschedule_overdue method exists
grep -n "def bulk_reschedule_overdue\|def get_overdue_pending" src/repositories/queue_repository.py

# 10. Verify scheduler loop has paused-chat reschedule pass
grep -n "get_all_paused_chats\|reschedule_overdue_for_paused" src/main.py
```

---

## 9. "What NOT To Do"

1. **Do NOT remove the `is_paused` column** from `chat_settings`. We reuse it. `is_paused = True` means "delivery OFF". No migration needed.

2. **Do NOT add a new database column** for the delivery state. The `is_paused` boolean is sufficient. We are only changing the UI label, not the data model.

3. **Do NOT break `/pause` and `/resume` commands**. They still work exactly as before -- they toggle `is_paused`. The only difference is the response message text and the addition of immediate reschedule on pause.

4. **Do NOT put the reschedule logic inside `process_pending_posts()`**. That method is never called for paused tenants because `get_all_active_chats()` filters them out. The reschedule must happen in a separate pass in the scheduler loop.

5. **Do NOT remove the existing overdue handling in `/resume`**. The Reschedule/Clear/Resume buttons in the resume flow are still valuable UX. The smart reschedule reduces the chance of large overdue pileups but does not eliminate the possibility (e.g., if someone pauses for < 24 hours, some items may still be overdue but not yet bumped).

6. **Do NOT make `reschedule_overdue_for_paused_chat()` async**. It only does synchronous database operations. Making it async would require awaiting it in the scheduler loop unnecessarily.

7. **Do NOT modify `src/models/chat_settings.py`**. This file is owned by Phase 01 for any schema changes. Phase 04 only changes UI and service logic.

8. **Do NOT modify `src/api/routes/onboarding.py` or `src/api/static/onboarding/`**. Those are owned by Phases 02 and 03 respectively.

9. **Do NOT use `update_scheduled_time()` in a loop** for the bulk reschedule. That method calls `commit()` after each update. Use `bulk_reschedule_overdue()` which commits once for all items.

10. **Do NOT forget to update the existing `test_paused_toggle_shows_correct_state` test**. It currently looks for "Paused" in the button text. After this change, it needs to look for "Delivery" and "OFF" instead.

---

### Critical Files for Implementation
- `/Users/chris/Projects/storyline-ai/src/services/core/telegram_settings.py` - Primary file: rename command header, add Mini App button, change delivery toggle label
- `/Users/chris/Projects/storyline-ai/src/repositories/queue_repository.py` - Add `get_overdue_pending()` and `bulk_reschedule_overdue()` methods for smart reschedule
- `/Users/chris/Projects/storyline-ai/src/main.py` - Add paused-tenant reschedule pass to scheduler loop (critical architectural change)
- `/Users/chris/Projects/storyline-ai/src/services/core/telegram_service.py` - Register `/setup` command and keep `/settings` alias
- `/Users/chris/Projects/storyline-ai/src/services/core/telegram_commands.py` - Update `/pause`, `/resume`, `/help`, `/status` messages to delivery language, add immediate reschedule on pause