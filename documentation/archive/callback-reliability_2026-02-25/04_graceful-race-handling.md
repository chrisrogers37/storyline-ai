# Fix 04: Graceful Race Condition Handling in Callback Validation

**Status**: ✅ COMPLETE
**Started**: 2026-02-25

**Investigation**: callback-reliability_2026-02-25
**Root Cause**: #4 — Race Condition (autopost deletes item before skip runs)
**Impact**: Low | **Effort**: Low | **Risk**: Low

---

## Problem

When a user clicks "Auto Post" then "Skip" (or vice versa), the first action completes and deletes the queue item. The second callback calls `validate_queue_item()` which finds no queue item and shows:

```
⚠️ Queue item not found
```

This is confusing — the user doesn't know if the item was posted, skipped, or rejected. There's no logging when this happens, making it invisible to operators.

**Evidence**: autopost completed at 04:39:32, skip callback at 04:39:50 — no "Post skipped" log, no meaningful feedback.

---

## Solution

Enhance `validate_queue_item()` to check `posting_history` when the queue item is missing, then show a contextual message.

**Before**: `queue_repo.get_by_id() → None → "Queue item not found"`

**After**:
```
queue_repo.get_by_id() → None
  → history_repo.get_by_queue_item_id(queue_id)
    → Found: "✅ Already posted via Instagram" / "⏭️ Already skipped" / "🚫 Already rejected"
    → Not found: "⚠️ Queue item not found" (truly missing, unchanged)
  → Log at INFO/WARNING level
```

---

## Implementation Steps

### Step 1: Add `get_by_queue_item_id()` to HistoryRepository

**File**: `src/repositories/history_repository.py`

```python
def get_by_queue_item_id(self, queue_item_id: str) -> Optional[PostingHistory]:
    """Get the most recent history record for a specific queue item.

    Used to determine what happened to a queue item that's no longer
    in the posting_queue (e.g., after a callback race condition).
    """
    return (
        self.db.query(PostingHistory)
        .filter(PostingHistory.queue_item_id == queue_item_id)
        .order_by(PostingHistory.posted_at.desc())
        .first()
    )
```

### Step 2: Add caption builder helper

**File**: `src/services/core/telegram_utils.py`

```python
def _build_already_handled_caption(history) -> str:
    """Build user-friendly caption for a queue item already handled."""
    status = history.status
    method = history.posting_method

    if status == "posted":
        if method == "instagram_api":
            return "✅ Already posted via Instagram API"
        return "✅ Already marked as posted"
    elif status == "skipped":
        return "⏭️ Already skipped"
    elif status == "rejected":
        return "🚫 Already rejected"
    elif status == "failed":
        return "❌ Previous attempt failed — item removed from queue"
    else:
        return f"ℹ️ Already processed (status: {status})"
```

### Step 3: Update `validate_queue_item()`

**File**: `src/services/core/telegram_utils.py`

Replace the `if not queue_item:` block:

```python
queue_item = service.queue_repo.get_by_id(queue_id)
if not queue_item:
    # Check posting_history for what happened to this queue item
    history = service.history_repo.get_by_queue_item_id(queue_id)
    if history:
        caption = _build_already_handled_caption(history)
        logger.info(
            f"Callback race: queue item {queue_id[:8]} already "
            f"{history.status} (posting_method={history.posting_method})"
        )
    else:
        caption = "⚠️ Queue item not found"
        logger.warning(f"Queue item {queue_id[:8]} not found in queue or history")
    await query.edit_message_caption(caption=caption)
    return None
return queue_item
```

### Step 4: No changes to callers

All callers already follow `if not queue_item: return` pattern. Fix is encapsulated.

---

## Tests

**File**: `tests/src/services/test_telegram_utils.py`

### `TestValidateQueueItem`

```python
async def test_shows_already_posted_api_when_history_posted_via_api(self):
    """Race: item auto-posted, second callback gets contextual message."""
    service.queue_repo.get_by_id.return_value = None
    service.history_repo.get_by_queue_item_id.return_value = Mock(
        status="posted", posting_method="instagram_api"
    )
    result = await validate_queue_item(service, "q-1", query)
    assert result is None
    assert "Already posted via Instagram API" in query.edit_message_caption.call_args[...]

async def test_shows_already_skipped(self):
    # history.status == "skipped" → "Already skipped"

async def test_shows_already_rejected(self):
    # history.status == "rejected" → "Already rejected"

async def test_shows_generic_not_found_when_no_history(self):
    # Neither queue nor history → "Queue item not found"

async def test_logs_race_condition_at_info_level(self):
    # Verify INFO log with "Callback race:" prefix

async def test_logs_warning_when_truly_missing(self):
    # Verify WARNING log when in neither queue nor history
```

### `TestBuildAlreadyHandledCaption`

```python
def test_posted_via_api(self):     # → "Already posted via Instagram API"
def test_posted_via_manual(self):  # → "Already marked as posted"
def test_skipped(self):            # → "Already skipped"
def test_rejected(self):           # → "Already rejected"
def test_failed(self):             # → "Previous attempt failed"
def test_unknown_status(self):     # → "Already processed (status: ...)"
```

### `TestHistoryRepository`

**File**: `tests/src/repositories/test_history_repository.py`

```python
def test_get_by_queue_item_id_found(self):
def test_get_by_queue_item_id_not_found(self):
```

---

## Files Changed

| File | Change |
|------|--------|
| `src/repositories/history_repository.py` | Add `get_by_queue_item_id()` (~15 lines) |
| `src/services/core/telegram_utils.py` | Add `_build_already_handled_caption()`, update `validate_queue_item()` (~40 lines) |
| `tests/src/services/test_telegram_utils.py` | Add 2 test classes (14 tests, ~100 lines) |
| `tests/src/repositories/test_history_repository.py` | Add 2 tests (~15 lines) |
