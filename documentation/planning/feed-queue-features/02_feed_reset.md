# Workstream 2: Feed Reset (Clear Live Stories)

**Focus**: Allow users to clear/remove live Instagram stories to start a fresh posting cycle.

**Status**: BLOCKED — Instagram Graph API does not support story deletion
**Priority**: Medium — desired feature, but no API path currently exists
**Estimated Effort**: TBD (dependent on API availability)

---

## Problem

Before starting a new day's posting cycle, users sometimes want to clear remaining stories from the previous day. Currently this requires manually opening Instagram and deleting each story one by one.

## Desired Behavior

A "Reset Feed" action (via Telegram button or command) that:
1. Fetches currently-live stories
2. Shows the user what will be removed
3. On confirmation, deletes them from Instagram
4. Confirms completion

## API Research Findings

### DELETE Endpoint Does NOT Exist

**Confirmed**: The Instagram Graph API (v22.0, as of March 2026) does **not** provide a `DELETE /{ig-media-id}` endpoint for stories or any other media type.

- The only supported DELETE operation is `DELETE /{ig-comment-id}` for comments
- There is no official programmatic way to delete stories
- This is a known limitation across all versions of the Graph API

### Alternatives Investigated

| Approach | Feasible? | Notes |
|----------|-----------|-------|
| `DELETE /{ig-media-id}` via Graph API | ❌ No | Endpoint doesn't exist |
| Instagram Private/Mobile API | ❌ No | Violates ToS, accounts get banned |
| Meta Marketing API | ❌ No | Only manages ads, not organic stories |
| Instagram Content Publishing API | ❌ No | Publish-only, no delete |
| Wait for 24h auto-expiration | ✅ Yes | Stories expire naturally, but not "on demand" |

---

## Interim Options (What We CAN Do)

Since automated deletion isn't possible, here are alternative approaches ranked by value:

### Option A: Visibility + Manual Guidance (Recommended)

**Effort**: Low (builds on Workstream 1)

Leverage the Live Story Visibility feature (Workstream 1) to show what's live, then guide the user to Instagram for manual deletion.

```
📱 Live Stories: 5 active
├── 🖼 Image — posted 21h ago (3h remaining)
├── 🖼 Image — posted 18h ago (6h remaining)
├── ...
│
💡 To clear stories, open Instagram and delete manually.
   3h remaining until oldest story expires naturally.
```

**Value**: Users at least know what's live and how long until auto-expiry, reducing the need to open Instagram just to check.

### Option B: Smart Scheduling Around Expiry

**Effort**: Medium

Instead of deleting old stories, schedule new posts to start *after* the oldest story expires. The scheduler already has the concept of posting windows — extend it to account for live story expiry.

```python
# Before scheduling new posts, check when current stories expire
oldest_story_expiry = get_oldest_live_story_expiry()
if oldest_story_expiry:
    # Push first post to after expiry for a "clean" start
    earliest_post_time = max(posting_window_start, oldest_story_expiry)
```

**Value**: Avoids story pile-up without needing deletion.

### Option C: Pause Until Clear

**Effort**: Low

Add a "Pause until feed is clear" option that auto-resumes posting once all current stories have expired (based on their timestamps).

```
⏸ Paused — waiting for 3 stories to expire
   Oldest expires in 3h 12m
   Auto-resume at: 5:42 PM
```

**Value**: Hands-off approach — set it and forget it.

---

## Recommendation

**Implement Option A now** (as part of Workstream 1 — it's essentially the same feature with a help message). **Consider Option B or C later** if the workflow pain point persists.

**Re-evaluate** the DELETE API situation periodically:
- Check Meta's Graph API changelog quarterly
- Monitor the [Meta Developer Blog](https://developers.facebook.com/blog/) for announcements
- The Content Publishing API is still evolving — deletion may be added

## Parking This Workstream

This workstream is **parked** until one of:
1. Meta adds a `DELETE` endpoint for stories
2. User feedback indicates Options B or C are worth building
3. A workaround becomes available

No code changes needed for this workstream beyond what Workstream 1 delivers.

---

## Files Affected

None currently — this workstream is blocked.

If Option B (Smart Scheduling) is pursued later:
- `src/services/core/scheduler_service.py` — Add expiry-aware scheduling
- `src/services/integrations/instagram_api.py` — Already has `get_live_stories()` from WS1

If Option C (Pause Until Clear) is pursued later:
- `src/services/core/posting_service.py` — Add auto-resume logic
- `src/services/core/settings_service.py` — Add "pause until clear" state
