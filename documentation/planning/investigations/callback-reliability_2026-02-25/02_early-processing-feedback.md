# Fix 02: Early Processing Feedback Before DB Operations

**Status**: 🔧 IN PROGRESS
**Started**: 2026-02-25

**Investigation**: callback-reliability_2026-02-25
**Root Cause**: #5 — UX Timing (visual feedback only after sync DB ops)
**Impact**: Medium | **Effort**: Low | **Risk**: Low

---

## Problem

When a user clicks "Skip", "Posted", "Reject", or "Auto Post", there is no visible change to the Telegram message until all synchronous DB operations finish:

```
User clicks "Skip"
  │
  ├─ _handle_callback() line 580: query.answer()
  │   → Dismisses loading spinner but message looks EXACTLY the same
  │
  ├─ complete_queue_action() line 51: acquire async lock
  │
  ├─ _do_complete_queue_action() lines 82-109: synchronous DB operations
  │   → history_repo.create()              — 10-500ms
  │   → media_repo.increment_times_posted() — 10-500ms (posted only)
  │   → lock_service.create_lock()          — 10-500ms (posted only)
  │   → queue_repo.delete()                 — 10-500ms
  │   ─── TOTAL: 40ms-30s (30s = pool timeout) ───
  │
  └─ line 112: query.edit_message_caption(caption=...)
      → THIS is the first visible change
```

If DB ops take >1 second, user may click again, triggering confusing "Already processing" toast.

---

## Solution

**Immediately remove the inline keyboard** after acquiring the lock and before DB operations. Use `query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup([]))`.

| Option | Pros | Cons |
|--------|------|------|
| (a) Edit caption to "Processing..." | Clear text | Loses original context |
| **(b) Remove inline keyboard** | Instant signal, prevents re-clicks, preserves caption | Adds ~100-200ms API call |
| (c) query.answer() toast | Zero latency | Already called at line 580, can't call twice |

**Recommendation: (b)** — When buttons disappear, user immediately knows their action was received.

---

## Implementation Steps

### Step 1: Add early feedback in `complete_queue_action()`

**File**: `src/services/core/telegram_callbacks.py`
**Location**: Inside `async with lock:` block (line 56), before `_do_complete_queue_action()`

```python
async with lock:
    try:
        # Immediate visual feedback: remove buttons to signal action received
        try:
            await query.edit_message_reply_markup(
                reply_markup=InlineKeyboardMarkup([])
            )
        except Exception:
            logger.debug(
                f"Could not remove keyboard for queue item {queue_id} "
                f"(message may have been already updated)"
            )

        await self._do_complete_queue_action(
            queue_id, user, query, status, success, caption, callback_name
        )
    finally:
        self.service.cleanup_operation_state(queue_id)
```

The `try/except` around the early edit is critical — if the message was already edited by another callback that won a race, this must not break the main flow.

### Step 2: Add early feedback in `handle_rejected()`

**File**: `src/services/core/telegram_callbacks.py`
**Location**: After `validate_queue_item` (after line 305), before DB operations

Insert after `if not queue_item: return`:
```python
    # Immediate visual feedback: remove buttons to signal action received
    try:
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup([])
        )
    except Exception:
        logger.debug(
            f"Could not remove keyboard for rejected item {queue_id}"
        )
```

### Step 3: Add early feedback in `handle_autopost()`

**File**: `src/services/core/telegram_autopost.py`
**Location**: Inside `async with lock:` block (line 84), before `_locked_autopost()`

Same pattern:
```python
async with lock:
    try:
        # Immediate visual feedback: remove buttons to signal action received
        try:
            await query.edit_message_reply_markup(
                reply_markup=InlineKeyboardMarkup([])
            )
        except Exception:
            logger.debug(
                f"Could not remove keyboard for autopost item {queue_id}"
            )

        await self._locked_autopost(queue_id, user, query, cancel_flag)
    finally:
        self.service.cleanup_operation_state(queue_id)
```

### Step 4: No changes to `edit_message_caption` calls

The existing `query.edit_message_caption(caption=...)` calls still work after keyboard removal — Telegram allows editing caption on a message whose reply_markup was already cleared.

---

## Tests

**File**: `tests/src/services/test_telegram_callbacks.py`

### Test 1: Keyboard removed before DB operations
```python
async def test_keyboard_removed_before_db_operations(self, mock_callback_handlers):
    """Inline keyboard is removed immediately after lock, before DB ops."""
    # Track call order
    call_order = []
    mock_query.edit_message_reply_markup.side_effect = lambda **kw: call_order.append("remove_keyboard")
    service.history_repo.create.side_effect = lambda *a, **kw: call_order.append("history_create")

    await handlers.complete_queue_action(...)

    assert call_order.index("remove_keyboard") < call_order.index("history_create")
```

### Test 2: Early edit failure doesn't break main flow
```python
async def test_keyboard_removal_failure_does_not_break_flow(self, mock_callback_handlers):
    """Early keyboard removal failure still allows DB ops + caption update."""
    mock_query.edit_message_reply_markup.side_effect = BadRequest("Message is not modified")

    await handlers.complete_queue_action(...)

    service.history_repo.create.assert_called_once()
    service.queue_repo.delete.assert_called_once()
    mock_query.edit_message_caption.assert_called_once()
```

### Test 3: Keyboard removed in `handle_rejected`
```python
async def test_rejected_removes_keyboard_before_db_ops(self, mock_callback_handlers):
    """handle_rejected removes keyboard before creating history/locks."""
    # Same call_order pattern as Test 1
```

### Test 4: Keyboard removed in `handle_autopost`

**File**: `tests/src/services/test_telegram_autopost.py`
```python
async def test_autopost_removes_keyboard_before_processing(self, mock_autopost_handler):
    """handle_autopost removes keyboard immediately after lock acquisition."""
```

---

## Files Changed

| File | Change |
|------|--------|
| `src/services/core/telegram_callbacks.py` | Add early `edit_message_reply_markup` in `complete_queue_action()` and `handle_rejected()` |
| `src/services/core/telegram_autopost.py` | Add early `edit_message_reply_markup` in `handle_autopost()` |
| `tests/src/services/test_telegram_callbacks.py` | Add 3 new tests |
| `tests/src/services/test_telegram_autopost.py` | Add 1 new test |
