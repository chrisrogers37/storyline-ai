# Analysis: Force Posting and Queue Shift Behavior

**Date**: 2026-01-11
**Status**: ✅ COMPLETED
**Issue**: Queue items don't shift forward when posts are made early via `/next` or `--force`
**Resolution**: Implemented slot-shift logic in shared `force_post_next()` method

> **Historical Note (2026-02-10):** Line numbers reference pre-refactor code (v1.4.0). The `/next` command handler now lives in `telegram_commands.py` (`TelegramCommandHandlers.handle_next()`). The `PostingService.force_post_next()` method location is unchanged.

---

## Summary

When using `/next` (Telegram) or `process-queue --force` (CLI) to post items early, **remaining queue items retain their original scheduled times**. There is no "shift forward" logic to move subsequent posts into the vacated time slots.

**Example of the problem:**
```
Queue before /next (5 times):
├─ Item A: 2026-01-11 10:00  → Posted early at 09:00
├─ Item B: 2026-01-11 14:00  → Posted early at 09:01
├─ Item C: 2026-01-11 18:00  → Posted early at 09:02
├─ Item D: 2026-01-12 10:00  → Posted early at 09:03
├─ Item E: 2026-01-12 14:00  → Posted early at 09:04
├─ Item F: 2026-01-12 18:00  → Still scheduled for 2026-01-12 18:00 (2 days away!)
└─ Item G: 2026-01-13 10:00  → Still scheduled for 2026-01-13 10:00

Expected behavior: Items should shift forward to fill vacated slots
```

---

## Current Implementation Analysis

### 1. Code Path Comparison: `/next` vs `--force`

| Aspect | `/next` Telegram | `--force` CLI |
|--------|------------------|---------------|
| **Entry Point** | `telegram_service.py:351` | `cli/commands/queue.py:50` |
| **Service Method** | `send_notification()` direct | `posting_service.process_next_immediate()` |
| **Queue Query** | `queue_repo.get_all(status="pending")[0]` | `queue_repo.get_all(status="pending")[0]` |
| **Caption** | Shows ⚡ indicator | No indicator |
| **Completion** | User clicks button | User clicks button |

**Answer: They use the SAME queue selection logic** (`get_all(status="pending")[0]`) but different notification paths.

### 2. Queue Selection Logic

Both commands get the earliest pending item:

```python
# queue_repository.py:37-44
def get_all(self, status: Optional[str] = None) -> List[PostingQueue]:
    query = self.db.query(PostingQueue)
    if status:
        query = query.filter(PostingQueue.status == status)
    return query.order_by(PostingQueue.scheduled_for.asc()).all()
```

- Returns ALL pending items sorted by `scheduled_for` ascending
- Takes `[0]` (earliest scheduled)
- **Ignores current time** - will return items scheduled for tomorrow if they're earliest

### 3. What Happens After Force Posting

```
1. /next or --force called
   ↓
2. Get earliest pending item (queue_item[0])
   ↓
3. Send to Telegram channel
   ↓
4. Update status: "pending" → "processing"
   ↓
5. Wait for user button click...
   ↓
6. User clicks Posted/Skip/Reject
   ↓
7. Queue item DELETED from database
   ↓
8. History record created
   ↓
9. Lock created (if Posted)
   ↓
10. ❌ NO SHIFT FORWARD - remaining items unchanged
```

### 4. Current Queue Data Model

```sql
-- posting_queue table
CREATE TABLE posting_queue (
    id UUID PRIMARY KEY,
    media_item_id UUID REFERENCES media_items(id),
    scheduled_for TIMESTAMP NOT NULL,  -- Fixed at creation time
    status VARCHAR(50) DEFAULT 'pending',
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Key issue**: `scheduled_for` is set once at schedule creation and never updated.

---

## Proposed Solution: Slot-Shift on Force Post

### Concept

When force-posting via `/next` or `--force`, shift all subsequent items UP by one slot. Each item inherits the scheduled time of the item before it. The last slot is discarded.

```
Before /next:
├─ Item A: 10:00 ← Force posted
├─ Item B: 14:00
├─ Item C: 18:00
└─ Item D: 22:00

After /next (Item A force-posted):
├─ Item A: NOW → removed from queue after completion
├─ Item B: 10:00 ← Inherits A's slot
├─ Item C: 14:00 ← Inherits B's slot
└─ Item D: 18:00 ← Inherits C's slot
      (22:00 slot discarded - falls off the end)
```

### Key Behavior

1. **Only on force pathway** - Normal scheduled posting does NOT trigger shifts
2. **Shift happens at force-send time** - Not when user clicks Posted/Skip/Reject
3. **Slot inheritance** - Each item takes the time of the item ahead of it
4. **Last slot discarded** - The final scheduled time is dropped
5. **Posted/Skip/Reject unchanged** - Button clicks work the same as before

### Why This Approach

- **Maintains schedule cadence**: If you have 3 posts/day, you still have 3 posts/day
- **Predictable behavior**: Each `/next` shifts everything up exactly one slot
- **Simple mental model**: "I'm pulling the next post forward, everything else moves up"
- **No accumulation**: Multiple `/next` calls each shift by one slot, not by time delta

### Implementation

#### Step 1: Add `shift_slots_forward()` to QueueRepository

```python
# queue_repository.py
def shift_slots_forward(self, from_item_id: str) -> int:
    """
    Shift all pending items forward by one slot.
    Each item inherits the scheduled_for time of the item before it.
    The from_item's time becomes 'now', and its original time goes to the next item.

    Args:
        from_item_id: The item being force-posted (its slot will be inherited by next item)

    Returns:
        Number of items shifted
    """
    # Get all pending items in scheduled order
    pending_items = self.get_all(status="pending")

    if not pending_items:
        return 0

    # Find the index of the force-posted item
    from_index = None
    for i, item in enumerate(pending_items):
        if str(item.id) == from_item_id:
            from_index = i
            break

    if from_index is None:
        return 0

    # Get the times to shift
    # Item at from_index is being force-posted, so items after it shift up
    items_to_shift = pending_items[from_index + 1:]  # Items AFTER the force-posted one

    if not items_to_shift:
        return 0

    # Build list of times: [from_item.scheduled_for, next.scheduled_for, ...]
    times = [pending_items[from_index].scheduled_for]
    for item in items_to_shift[:-1]:  # All but last (last slot is discarded)
        times.append(item.scheduled_for)

    # Assign new times
    for i, item in enumerate(items_to_shift):
        item.scheduled_for = times[i]

    self.db.commit()
    logger.info(f"Shifted {len(items_to_shift)} queue items forward by one slot")
    return len(items_to_shift)
```

#### Step 2: Call shift in force-post pathways

**In TelegramService `/next` handler:**

```python
# telegram_service.py - _handle_next()
async def _handle_next(self, update, context):
    # ... existing code to get queue_item ...

    # Shift remaining items forward BEFORE sending notification
    shifted = self.queue_repo.shift_slots_forward(str(queue_item.id))
    if shifted > 0:
        logger.info(f"Shifted {shifted} items forward after /next")

    # Update the force-posted item to NOW
    queue_item.scheduled_for = datetime.utcnow()
    self.db.commit()

    # ... rest of existing code ...
```

**In PostingService `process_next_immediate()`:**

```python
# posting_service.py - process_next_immediate()
async def process_next_immediate(self, user_id: Optional[str] = None) -> dict:
    # ... existing code to get queue_item ...

    # Shift remaining items forward
    shifted = self.queue_repo.shift_slots_forward(str(queue_item.id))
    if shifted > 0:
        logger.info(f"Shifted {shifted} items forward after --force")

    # Update the force-posted item to NOW
    queue_item.scheduled_for = datetime.utcnow()
    self.db.commit()

    # ... rest of existing code ...
```

### Example: Multiple /next Calls

```
Initial queue:
├─ A: 10:00
├─ B: 14:00
├─ C: 18:00
├─ D: 22:00
└─ E: (next day) 10:00

After /next #1 (A force-posted at 09:00):
├─ A: 09:00 → processing/removed
├─ B: 10:00 ← was 14:00
├─ C: 14:00 ← was 18:00
├─ D: 18:00 ← was 22:00
└─ E: 22:00 ← was next day 10:00

After /next #2 (B force-posted at 09:01):
├─ B: 09:01 → processing/removed
├─ C: 10:00 ← was 14:00
├─ D: 14:00 ← was 18:00
└─ E: 18:00 ← was 22:00
      (22:00 slot discarded)

After /next #3 (C force-posted at 09:02):
├─ C: 09:02 → processing/removed
├─ D: 10:00 ← was 14:00
└─ E: 14:00 ← was 18:00
      (18:00 slot discarded)
```

### Edge Cases

1. **Empty queue after force-posted item**: No shift needed
2. **Only one item in queue**: No shift needed (nothing behind it)
3. **Item already in "processing" status**: Only shift "pending" items
4. **Concurrent /next calls**: Each call shifts independently (order matters)

---

## Files to Modify

| File | Change |
|------|--------|
| `src/repositories/queue_repository.py` | Add `shift_slots_forward()` method |
| `src/services/core/telegram_service.py` | Call shift in `_handle_next()` |
| `src/services/core/posting_service.py` | Call shift in `process_next_immediate()` |
| `tests/src/repositories/test_queue_repository.py` | Tests for slot-shift logic |
| `tests/src/services/test_telegram_service.py` | Tests for /next with shifting |
| `tests/src/services/test_posting.py` | Tests for --force with shifting |

---

## Summary

| Question | Answer |
|----------|--------|
| Do `/next` and `--force` use same code paths? | **Partially** - same queue selection, different notification paths |
| What happens to remaining items currently? | **Nothing** - they keep original scheduled times |
| Is there shift-forward logic currently? | **No** - not implemented |
| Recommended solution | Add `shift_slots_forward()` called at force-send time |
| When does shift happen? | At `/next` or `--force` execution, NOT on button click |
| What gets shifted? | All pending items AFTER the force-posted item |
| What happens to last slot? | Discarded (falls off the end) |

---

## Implementation Status

1. [x] Implement `QueueRepository.shift_slots_forward()` - `src/repositories/queue_repository.py:127`
2. [x] Create shared `PostingService.force_post_next()` - `src/services/core/posting.py:26`
3. [x] Update `TelegramService._handle_next()` to use shared method - `src/services/core/telegram_service.py:351`
4. [x] Update CLI `--force` to use shared method - `cli/commands/queue.py:50`
5. [x] Add unit tests for slot-shift logic - `tests/src/repositories/test_queue_repository.py:225`
6. [ ] Update /queue display to show shifted times (optional enhancement)

## Files Changed

| File | Change |
|------|--------|
| `src/repositories/queue_repository.py` | Added `shift_slots_forward()` method |
| `src/services/core/posting.py` | Added shared `force_post_next()` method |
| `src/services/core/telegram_service.py` | Updated `_handle_next()` to use shared method |
| `cli/commands/queue.py` | Updated `--force` to use shared method and show shift count |
| `tests/src/repositories/test_queue_repository.py` | Added 5 tests for slot-shift logic |
