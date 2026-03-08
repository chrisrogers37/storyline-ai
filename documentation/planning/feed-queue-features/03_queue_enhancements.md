# Workstream 3: Queue Management Enhancements

**Focus**: Improve visibility and control over the posting queue — what's scheduled, what's next, and how to manage it.

**Status**: Ready for Implementation
**Priority**: High — direct workflow improvement, no external dependencies
**Estimated Effort**: Medium

---

## Problem

The current queue management has gaps in the daily workflow:

1. **Limited visibility**: `/status` shows queue count but not the full schedule at a glance
2. **No preview**: Can't see what media is coming up without triggering `/next`
3. **No reordering**: Can't bump or deprioritize specific queue items
4. **Stale queue items**: No easy way to swap out a queued item without resetting the entire queue

## Current State

### What Exists

| Feature | Where | Status |
|---------|-------|--------|
| View queue count | `/status` command | ✅ Working |
| View next post | `/next` command (force-sends it) | ✅ Working (but destructive — it posts) |
| Reset entire queue | `/settings` → Regenerate | ✅ Working |
| Queue list (CLI) | `storyline-cli list-queue` | ✅ Working |
| Queue list (Telegram) | `/queue` (retired) | ⚠️ Retired — redirects to Mini App |

### What's Missing

- **Non-destructive queue preview** in Telegram (see schedule without posting)
- **Per-item queue actions** (skip one item, swap, move to end)
- **Schedule overview** (today's remaining posts at a glance)
- **Queue health indicators** (gaps in schedule, overdue items)

---

## Proposed Enhancements

### Enhancement 1: Queue Preview in `/status`

**Effort**: Low
**Value**: High

Add today's remaining queue items to the `/status` output, giving at-a-glance schedule visibility.

```
📊 System Status
├── Media Library: 847 indexed (12 never posted)
├── Queue: 8 pending today
│
📋 Today's Schedule:
├── 🕐 10:30 AM — meme_042.jpg (memes)
├── 🕐 12:15 PM — merch_019.jpg (merch) ← NEXT
├── 🕐  2:00 PM — meme_108.jpg (memes)
├── 🕐  3:45 PM — merch_003.jpg (merch)
├── 🕐  5:30 PM — meme_215.jpg (memes)
└── +3 more tomorrow
```

**Implementation**:
- Query `posting_queue` for items scheduled today, ordered by `scheduled_for`
- Show filename, category, and scheduled time
- Mark the next upcoming item
- Collapse future days into a count

### Enhancement 2: Queue Item Actions

**Effort**: Medium
**Value**: Medium

Add inline buttons on queue preview items for per-item management.

**Actions per item**:
- **👀 Preview** — Send the media file to chat so user can see it
- **⏭ Skip** — Move item to end of queue (reschedule to last slot)
- **🔄 Swap** — Replace with a different media item (random from same category)
- **🚫 Remove** — Remove from queue entirely (without rejecting the media)

**Flow**:
```
User taps "📋 View Queue" button in /status
  → Bot sends paginated queue list with action buttons per item
  → User taps ⏭ on item 3
  → Item 3 moves to end, items 4-8 shift up
  → Bot confirms: "Moved meme_108.jpg to end of queue"
```

### Enhancement 3: Queue Health Indicators

**Effort**: Low
**Value**: Medium

Add warning indicators to `/status` when the queue needs attention:

```
⚠️ Queue Alerts:
├── 🔴 2 items overdue (scheduled before now, not yet sent)
├── 🟡 Gap: no posts scheduled between 2 PM - 5 PM
└── 🟢 Tomorrow: 6 posts scheduled (3 memes, 3 merch)
```

**Indicators**:
- **Overdue items**: Scheduled time has passed but item hasn't been sent
- **Schedule gaps**: Long stretches with no posts during posting hours
- **Low queue**: Fewer than expected posts remaining for the day
- **Category imbalance**: Queue doesn't match configured category ratios

### Enhancement 4: Quick Queue Refill

**Effort**: Low
**Value**: High

A one-tap "Fill today's queue" button when the queue is empty or running low.

```
📋 Queue: Empty — no posts scheduled today

[📋 Fill Today's Queue]  [⚙️ Settings]
```

Tapping the button runs the scheduler for today only (equivalent to `storyline-cli create-schedule --days 1`).

---

## Implementation Priority

| # | Enhancement | Effort | Value | Recommendation |
|---|------------|--------|-------|----------------|
| 1 | Queue Preview in `/status` | Low | High | **Do first** |
| 4 | Quick Queue Refill button | Low | High | **Do second** |
| 3 | Queue Health Indicators | Low | Medium | **Do third** |
| 2 | Queue Item Actions | Medium | Medium | **Do later** (most complex) |

---

## Detailed Implementation: Enhancement 1 (Queue Preview)

### Service Layer

**Modify**: `src/services/core/scheduler_service.py` or `src/repositories/queue_repository.py`

Add method to get today's queue with relevant fields:

```python
def get_todays_queue(self) -> list[dict]:
    """Get today's pending queue items ordered by scheduled time."""
    # Returns: [{scheduled_for, media_filename, category, queue_id}, ...]
```

### Telegram Layer

**Modify**: `src/services/core/telegram_commands.py`

Update `handle_status()` to include queue preview section:

```python
# After existing status sections...
todays_queue = scheduler_service.get_todays_queue()
if todays_queue:
    status_text += format_queue_preview(todays_queue)
```

### Tests

- Test queue preview formatting with 0, 1, 5, and 20+ items
- Test time display (show relative time for past items, absolute for future)
- Test category label display
- Test "NEXT" marker logic (first item after current time)

---

## Detailed Implementation: Enhancement 4 (Quick Refill)

### Telegram Layer

**Modify**: `src/services/core/telegram_commands.py`

Add "Fill Queue" inline button to `/status` when queue is empty:

```python
if not todays_queue:
    keyboard.append([
        InlineKeyboardButton("📋 Fill Today's Queue", callback_data="fill_queue_today")
    ])
```

### Callback Handler

**Modify**: `src/services/core/telegram_callbacks.py`

Handle the `fill_queue_today` callback:

```python
async def handle_fill_queue(self, callback_query):
    """Create schedule for today only."""
    result = scheduler_service.create_schedule(days=1)
    await callback_query.answer(f"✅ Scheduled {result.count} posts for today")
    # Refresh status message with new queue
```

### Safety

- Requires the same permissions as `/settings` → Regenerate
- Shows confirmation if queue already has items: "Queue has 3 items. Add more?"
- Respects category ratios and posting window settings

---

## Files to Create/Modify

| File | Enhancement | Action |
|------|------------|--------|
| `src/repositories/queue_repository.py` | 1 | Add `get_todays_queue()` |
| `src/services/core/telegram_commands.py` | 1, 4 | Queue preview + fill button |
| `src/services/core/telegram_callbacks.py` | 4 | Handle fill_queue callback |
| `tests/src/services/test_telegram_commands.py` | 1 | Queue preview tests |
| `tests/src/services/test_telegram_callbacks.py` | 4 | Fill queue tests |
| `tests/src/repositories/test_queue_repository.py` | 1 | Repository query tests |

## Dependencies

- No external API dependencies — all data is local (posting_queue table)
- Works regardless of Instagram API being enabled or not
- Compatible with multi-account setup (queue is already account-aware)

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| `/status` becomes too long | Collapse to top 3-5 items + "and N more" |
| Queue preview is stale after action | Refresh status message after any queue modification |
| Fill queue conflicts with existing items | Check for existing items, offer "add more" vs "replace" |
| Race condition on queue actions | Reuse existing async lock pattern from callback handlers |
