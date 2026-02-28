# Phase 04: Posting Service Complexity Reduction

**Status**: ✅ COMPLETE
**Started**: 2026-02-28
**Completed**: 2026-02-28
**PR**: #89
**PR Title**: Flatten nesting and extract helpers in PostingService
**Risk Level**: Low
**Estimated Effort**: Low (45 min)
**Files Modified**: 3
**Dependencies**: Phase 01 (dead code removal) ✅
**Blocks**: None

---

## Context

After Phase 01 removed ~260 lines of dead code, `posting.py` is now 386 lines. The remaining issues are:
1. **Deep nesting** (6-7 levels) in `force_post_next()` and `process_pending_posts()`
2. **BaseService pattern violation** — `reschedule_overdue_for_paused_chat()` calls `self.db.commit()` directly instead of going through a repository
3. **Long methods** that combine multiple responsibilities

---

## Implementation Plan

### 1. Fix BaseService violation in reschedule_overdue_for_paused_chat()

**File**: `src/services/core/posting.py` (lines ~333-371)

The method directly calls `self.db.commit()` which violates the repository pattern. Move the bulk update logic into `QueueRepository`.

**Before** (in `posting.py`):
```python
def reschedule_overdue_for_paused_chat(self):
    # ... fetches overdue items ...
    for item in overdue_items:
        item.scheduled_for = new_time
    self.db.commit()  # VIOLATION
```

**After** (in `posting.py`):
```python
def reschedule_overdue_for_paused_chat(self):
    # ... fetches overdue items ...
    if overdue_items:
        self.queue_repo.reschedule_items(overdue_items, timedelta(hours=24))
```

**New method in** `src/repositories/queue_repository.py`:
```python
def reschedule_items(self, items, delta):
    """Reschedule items by adding delta to their scheduled_for time."""
    for item in items:
        item.scheduled_for = item.scheduled_for + delta
    self.db.commit()
```

### 2. Flatten force_post_next() nesting

**File**: `src/services/core/posting.py` (lines ~63-196)

Current structure has 6 levels of nesting. Flatten with early returns and extract helpers.

**Strategy**: Extract the Telegram-send block into a helper method.

**Before** (simplified):
```python
def force_post_next(self, ...):
    with self.track_execution(...) as run_id:
        pending = self.queue_repo.get_next_pending(...)
        if pending:
            media = self.media_repo.get_by_id(pending.media_item_id)
            if media:
                try:
                    success = await self._post_via_telegram(pending.id)
                    if success:
                        # ... update queue, history, locks ...
                        # ... build result dict ...
                        return result
                    else:
                        # ... error handling ...
                except Exception:
                    # ... error handling ...
            else:
                # ... no media handling ...
        else:
            # ... no pending handling ...
```

**After**:
```python
def force_post_next(self, ...):
    with self.track_execution(...) as run_id:
        pending = self.queue_repo.get_next_pending(...)
        if not pending:
            return self._build_force_post_result("empty", ...)

        media = self.media_repo.get_by_id(pending.media_item_id)
        if not media:
            return self._build_force_post_result("no_media", ...)

        return await self._execute_force_post(pending, media, run_id, ...)
```

**New helper methods**:

```python
def _build_force_post_result(self, status, run_id=None, **kwargs):
    """Build standardized result dict for force_post_next."""
    result = {"status": status, **kwargs}
    if run_id:
        self.set_result_summary(run_id, result)
    return result

async def _execute_force_post(self, pending, media, run_id, ...):
    """Execute the force post after validation. Handles send + queue update."""
    try:
        success = await self._post_via_telegram(pending.id)
        if not success:
            return self._build_force_post_result("send_failed", run_id)

        # ... update queue, history, locks (flat, no extra nesting) ...
        return self._build_force_post_result("success", run_id, ...)
    except Exception as e:
        logger.error(f"Force post failed: {e}", exc_info=True)
        return self._build_force_post_result("error", run_id, error=str(e))
```

### 3. Flatten process_pending_posts() nesting

**File**: `src/services/core/posting.py` (lines ~231-331)

Similar strategy — extract the per-item processing into a helper.

**Before** (simplified):
```python
def process_pending_posts(self):
    with self.track_execution(...):
        items = self.queue_repo.get_pending_items(...)
        for item in items:
            media = self.media_repo.get_by_id(item.media_item_id)
            if media:
                try:
                    await self._route_post(item, media)
                    # ... update queue ...
                except Exception:
                    # ... error handling ...
```

**After**:
```python
def process_pending_posts(self):
    with self.track_execution(...):
        items = self.queue_repo.get_pending_items(...)
        for item in items:
            await self._process_single_pending(item)

async def _process_single_pending(self, item):
    """Process a single pending queue item."""
    media = self.media_repo.get_by_id(item.media_item_id)
    if not media:
        logger.warning(f"Media not found for queue item {item.id}")
        return

    try:
        await self._route_post(item, media)
        # ... update queue (flat) ...
    except Exception as e:
        logger.error(f"Failed to process {item.id}: {e}", exc_info=True)
```

---

## Test Plan

```bash
# 1. Run existing posting service tests
pytest tests/src/services/test_posting.py -v

# 2. Add tests for new helper methods
```

```python
# test_build_force_post_result
def test_build_force_post_result_with_status(self, posting_service):
    result = posting_service._build_force_post_result("empty")
    assert result["status"] == "empty"

def test_build_force_post_result_with_kwargs(self, posting_service):
    result = posting_service._build_force_post_result("success", count=5)
    assert result["status"] == "success"
    assert result["count"] == 5

# test_reschedule_items in queue_repository tests
def test_reschedule_items(self, queue_repo):
    items = [Mock(scheduled_for=datetime(2026, 1, 1, 10, 0))]
    queue_repo.reschedule_items(items, timedelta(hours=24))
    assert items[0].scheduled_for == datetime(2026, 1, 2, 10, 0)
    queue_repo.db.commit.assert_called_once()
```

```bash
# 3. Full suite
pytest

# 4. Lint
ruff check src/ tests/ && ruff format --check src/ tests/
```

---

## Verification Checklist

- [ ] No `self.db.commit()` calls in `posting.py` (grep to verify)
- [ ] `reschedule_items()` method added to `queue_repository.py`
- [ ] Maximum nesting depth reduced from 6-7 to 3-4
- [ ] All existing posting tests pass
- [ ] New helper method tests pass
- [ ] `pytest` passes
- [ ] `ruff check` and `ruff format` pass
- [ ] CHANGELOG.md updated

---

## What NOT To Do

- **Don't start this before Phase 01 is merged** — Phase 01 removes dead code, this phase works on the remaining ~445 lines
- **Don't change `_route_post()` or `_post_via_telegram()`** — they're fine as-is
- **Don't add new features** — this is purely a readability refactor
- **Don't change method signatures of public methods** — `force_post_next()` and `process_pending_posts()` must keep their signatures
- **Don't move methods to new files** — the file is ~445 lines after Phase 01, which is acceptable
