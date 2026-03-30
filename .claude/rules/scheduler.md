---
paths:
  - "src/services/core/scheduler*"
---

# Scheduler Algorithm (JIT)

The scheduler polls on a loop. Each tick, `is_slot_due()` checks if enough time has elapsed since the last post. If due, `process_slot()` selects media on-demand.

## Selection Logic (priority order)

1. **Filter eligible**: `is_active = TRUE`, not locked, not already queued, matches target category
2. **Sort by**: `last_posted_at ASC NULLS FIRST` → `times_posted ASC` → `RANDOM()`
3. **Slot timing**: `interval_hours = (POSTING_HOURS_END - POSTING_HOURS_START) / POSTS_PER_DAY`
4. **Category selection**: `_pick_category_for_slot()` weighted by ratio, fallback to any category

## After Posting

- Create 30-day TTL lock automatically
- Increment `times_posted`
- Update `last_posted_at`
