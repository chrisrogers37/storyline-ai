# Workstream 1: Live Story Visibility

**Focus**: Fetch and display currently-live Instagram stories so users know what's on their feed without opening the app.

**Status**: Ready for Implementation
**Priority**: High — standalone value, no blockers
**Estimated Effort**: Medium (service + Telegram UI + tests)

---

## Problem

There's no way to see what's currently live on the Instagram story feed from within the Storyline workflow. Users must open the Instagram app to check. This creates a blind spot when deciding whether to post more, skip, or wait.

## Solution

Add a "Live Stories" feature that fetches currently-active stories from the Instagram Graph API and displays them in Telegram.

## API Details

### Endpoint

```
GET https://graph.facebook.com/v22.0/{ig-user-id}/stories
  ?fields=id,media_type,media_url,timestamp
  &access_token={access_token}
```

### Response

```json
{
  "data": [
    {
      "id": "17854360229135492",
      "media_type": "IMAGE",
      "media_url": "https://...",
      "timestamp": "2026-03-08T14:30:00+0000"
    }
  ]
}
```

### Key Facts

- Returns **only** currently-live stories (within 24h window)
- Does NOT return archived or highlighted stories
- Standard `GET /{ig-user-id}/media` does NOT include stories — must use `/stories` edge
- Available fields: `id`, `media_type`, `media_url`, `timestamp`, `caption`, `permalink`, `thumbnail_url`
- Story insights (impressions, reach, taps, exits, replies) available via `GET /{ig-media-id}/insights` but expire after 24h

### Permissions Required

- `instagram_basic` (already have)
- `pages_show_list` (already have)
- `pages_read_engagement` (verify)

### Rate Limits

- Falls under general BUC rate limits: ~200 API calls/hour per user token
- No separate limit for reading stories
- Very affordable — one call returns all live stories

---

## Implementation Plan

### 1. Service Layer: `InstagramAPIService`

Add a `get_live_stories()` method to the existing Instagram API service.

**Location**: `src/services/integrations/instagram_api.py`

```python
async def get_live_stories(self, account_id: int = None) -> list[dict]:
    """Fetch currently-live stories from Instagram.

    Returns list of story objects with id, media_type, media_url, timestamp.
    Returns empty list if Instagram API is disabled or errors occur.
    """
```

**Behavior**:
- Resolve account → get token → call API
- Return parsed story list (id, media_type, timestamp, time remaining)
- Graceful fallback: return empty list + log warning on error
- Respect existing token refresh flow

### 2. Telegram Integration

**Option A — Add to `/status` command** (Recommended):
- Append a "Live Stories" section to the existing `/status` output
- Shows count + timestamps + time remaining for each
- No new command needed, natural home for this data

**Option B — Dedicated `/feed` command**:
- New command showing live story details
- More detailed view with media previews
- Adds command bloat (we just consolidated from 18 → 11)

**Recommended**: Option A. Add to `/status` as a section. If the user wants a detailed view later, we can always add a "View Feed" button that shows the full breakdown.

### 3. Display Format (in `/status`)

```
📊 System Status
├── Media Library: 847 indexed
├── Queue: 12 pending (next: 2:30 PM)
├── ...
│
📱 Live Stories: 5 active
├── 🖼 Image — posted 2h ago (22h remaining)
├── 🖼 Image — posted 5h ago (19h remaining)
├── 🎬 Video — posted 8h ago (16h remaining)
├── 🖼 Image — posted 14h ago (10h remaining)
└── 🖼 Image — posted 21h ago (3h remaining)
```

### 4. Multi-Account Support

- Use `chat_settings.active_instagram_account_id` to determine which account to query
- If no account selected, show prompt to select one
- Follows existing account selection pattern

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `src/services/integrations/instagram_api.py` | Modify | Add `get_live_stories()` method |
| `src/services/core/telegram_commands.py` | Modify | Add live stories section to `/status` |
| `tests/src/services/test_instagram_api.py` | Modify | Tests for `get_live_stories()` |
| `tests/src/services/test_telegram_commands.py` | Modify | Tests for updated `/status` output |

## Dependencies

- Instagram API must be enabled (`ENABLE_INSTAGRAM_API=true`)
- Valid token for the active Instagram account
- When API is disabled, the section simply doesn't appear in `/status`

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Token expired | Existing token refresh handles this; show "token expired" message |
| API rate limited | One call per `/status` invocation is negligible |
| No stories live | Show "No active stories" — still useful info |
| Account not connected | Skip section, show nothing (or "Connect account in /settings") |

## Out of Scope

- Story insights/analytics (future workstream)
- Story media preview thumbnails in Telegram (bandwidth concern)
- Automatic feed monitoring / alerts (over-engineering for now)
