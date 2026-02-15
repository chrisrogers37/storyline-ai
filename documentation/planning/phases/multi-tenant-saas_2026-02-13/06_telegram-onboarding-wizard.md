# Phase 06: Telegram Onboarding Mini App

**Status:** 📋 PENDING
**Risk:** Medium
**Effort:** 5-7 hours
**PR Title:** `feat: Telegram Mini App onboarding wizard for self-service setup`

---

## Overview

Phase 06 replaces the static `/start` command with a Telegram Mini App (WebApp) that guides new users through setup: connecting Instagram, connecting Google Drive, picking a media folder, and configuring their posting schedule.

**Why a Mini App instead of in-chat buttons:**
- OAuth steps already open a browser — the UX is smoother if the whole setup lives in a web view
- Rich form inputs (dropdowns, text fields, progress bars) instead of walls of inline buttons
- No chat bloat — setup messages don't pollute the conversation history
- Professional, app-like feel for the onboarding experience
- The setup wizard is a one-time flow, not a daily interaction

**Dependencies:** Phase 03 (per-tenant scheduler), Phase 04 (Instagram OAuth), Phase 05 (Google Drive OAuth) — all complete.

## Architecture

### How It Works

```
User sends /start
    │
    ▼
Bot replies with [Open Setup Wizard] button (WebAppInfo)
    │
    ▼
Telegram opens Mini App in WebView
    │
    ▼
Mini App validates initData with backend
    │
    ▼
Multi-step wizard:
  Step 1: Welcome
  Step 2: Connect Instagram (OAuth redirect)
  Step 3: Connect Google Drive (OAuth redirect)
  Step 4: Pick media folder
  Step 5: Configure schedule
  Step 6: Summary + Create Schedule
    │
    ▼
Mini App closes → Bot sends summary message to chat
```

### Tech Stack

- **Frontend**: Single HTML file + vanilla CSS/JS (no framework). Served by FastAPI.
- **Backend**: FastAPI API endpoints (extends existing `src/api/app.py`)
- **Security**: Telegram `initData` HMAC-SHA256 validation on every API call
- **SDK**: `https://telegram.org/js/telegram-web-app.js` loaded in the HTML

### File Structure

```
src/api/
├── app.py                          # Extend with static files + onboarding routes
├── routes/
│   ├── oauth.py                    # Existing OAuth endpoints
│   └── onboarding.py               # NEW: Mini App API endpoints
└── static/
    └── onboarding/
        ├── index.html              # The Mini App (single page)
        ├── style.css               # Styles
        └── app.js                  # Logic + Telegram WebApp SDK integration
```

## Backend: API Endpoints

### `POST /api/onboarding/init`

Validates `initData`, returns current setup state for this chat.

**Request body**: `{ "init_data": "<telegram_init_data_string>" }`

**Response**:
```json
{
  "chat_id": -1001234567890,
  "user": { "id": 12345, "first_name": "Chris" },
  "setup_state": {
    "instagram_connected": true,
    "instagram_username": "@storyline",
    "gdrive_connected": false,
    "gdrive_email": null,
    "media_folder_id": null,
    "media_file_count": 0,
    "posts_per_day": 3,
    "posting_hours_start": 14,
    "posting_hours_end": 2,
    "onboarding_completed": false
  }
}
```

This endpoint is called when the Mini App loads. It determines which step to show (resume from where the user left off, or start from the beginning).

### `GET /api/onboarding/oauth-url/{provider}?init_data=<string>`

Returns the OAuth authorization URL for Instagram or Google Drive.

**Path param**: `provider` = `instagram` or `google-drive`

**Response**: `{ "auth_url": "https://accounts.google.com/..." }`

The Mini App opens this URL in a new tab. When OAuth completes, the callback endpoint (Phase 04/05) stores the token and returns HTML. The Mini App polls `/api/onboarding/init` to detect when the connection succeeds.

### `POST /api/onboarding/media-folder`

Sets the Google Drive media folder for this chat.

**Request body**:
```json
{
  "init_data": "<string>",
  "folder_url": "https://drive.google.com/drive/folders/abc123"
}
```

**Response**:
```json
{
  "folder_id": "abc123",
  "file_count": 47,
  "categories": ["memes", "merch", "products"]
}
```

Extracts the folder ID from the URL, validates access with the user's OAuth token, triggers a quick file count, and stores the folder ID in `chat_settings.media_source_root`.

### `POST /api/onboarding/schedule`

Saves the posting schedule configuration.

**Request body**:
```json
{
  "init_data": "<string>",
  "posts_per_day": 3,
  "posting_hours_start": 9,
  "posting_hours_end": 21
}
```

### `POST /api/onboarding/complete`

Marks onboarding as finished. Optionally creates an initial schedule.

**Request body**:
```json
{
  "init_data": "<string>",
  "create_schedule": true,
  "schedule_days": 7
}
```

**Side effects**:
- Sets `chat_settings.onboarding_completed = True`
- Sets `chat_settings.onboarding_step = NULL`
- If `create_schedule = true`, calls `SchedulerService.create_schedule()`
- Sends a summary message to the Telegram chat via Bot API

## Frontend: Mini App

### Single-Page Wizard

The Mini App is a single HTML page with 6 "screens" toggled via JavaScript. No page reloads, no framework.

**Step 1: Welcome**
- "Welcome to Storyline AI! Let's get you set up."
- Progress bar: step 1 of 5
- "Get Started" button

**Step 2: Connect Instagram**
- Status indicator: connected / not connected
- "Connect Instagram" button → opens OAuth URL in new tab
- Polling indicator while waiting for OAuth callback
- "Skip" link
- Once connected: shows @username, auto-advances

**Step 3: Connect Google Drive**
- Status indicator: connected / not connected
- "Connect Google Drive" button → opens OAuth URL in new tab
- Polling indicator while waiting for OAuth callback
- "Skip" link
- Once connected: shows email, auto-advances

**Step 4: Media Folder**
- Only shown if Google Drive is connected
- Text input: "Paste your Google Drive folder URL"
- "Validate" button → calls `/api/onboarding/media-folder`
- Shows file count and categories on success
- "Skip" link

**Step 5: Schedule**
- Posts per day: button group (1, 3, 5, 7, Custom input)
- Posting hours: preset options (9am-9pm, 12pm-12am, Custom)
- Timezone note: "All times in UTC"

**Step 6: Summary**
- Shows all configuration:
  - Instagram: @username or "Not connected"
  - Media: Google Drive (47 files) or "Not connected"
  - Schedule: 3 stories/day, 9am-9pm UTC
- "Create 7-Day Schedule" toggle (default on)
- "Finish Setup" button → calls `/api/onboarding/complete` → `Telegram.WebApp.close()`

### Telegram WebApp SDK Usage

```javascript
const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();  // Full-height mode

// Get initData for API authentication
const initData = tg.initData;

// Theme-aware styling
document.body.style.backgroundColor = tg.themeParams.bg_color;

// Close the Mini App when done
tg.close();
```

### OAuth Polling Pattern

After the user clicks "Connect Instagram" and the OAuth tab opens:

```javascript
// Poll every 3 seconds to check if OAuth completed
const pollInterval = setInterval(async () => {
    const state = await fetch('/api/onboarding/init', {
        method: 'POST',
        body: JSON.stringify({ init_data: tg.initData })
    }).then(r => r.json());

    if (state.setup_state.instagram_connected) {
        clearInterval(pollInterval);
        showStep('media-source');  // Auto-advance
    }
}, 3000);

// Stop polling after 10 minutes
setTimeout(() => clearInterval(pollInterval), 600000);
```

## Security: initData Validation

Every API call includes `init_data`. The backend validates it using HMAC-SHA256:

```python
# src/utils/webapp_auth.py

import hashlib
import hmac
import time
from urllib.parse import parse_qs

from src.config.settings import settings

INIT_DATA_TTL = 3600  # 1 hour


def validate_init_data(init_data: str) -> dict:
    """Validate Telegram WebApp initData and extract user/chat info.

    Raises ValueError if invalid or expired.
    Returns parsed data dict with user_id, chat_id, etc.
    """
    parsed = parse_qs(init_data)

    # Extract and remove hash
    received_hash = parsed.pop("hash", [None])[0]
    if not received_hash:
        raise ValueError("Missing hash in initData")

    # Sort remaining params alphabetically, join with newlines
    data_check_string = "\n".join(
        f"{k}={v[0]}" for k, v in sorted(parsed.items())
    )

    # HMAC-SHA256 with secret key derived from bot token
    secret_key = hmac.new(
        b"WebAppData", settings.TELEGRAM_BOT_TOKEN.encode(), hashlib.sha256
    ).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise ValueError("Invalid initData signature")

    # Check TTL
    auth_date = int(parsed.get("auth_date", [0])[0])
    if time.time() - auth_date > INIT_DATA_TTL:
        raise ValueError("initData expired")

    # Parse user JSON
    import json
    user_data = json.loads(parsed.get("user", ["{}"])[0])

    return {
        "user_id": user_data.get("id"),
        "first_name": user_data.get("first_name"),
        "chat_id": user_data.get("id"),  # In private chats, chat_id = user_id
    }
```

## Database Changes

### Migration 016: `chat_settings_onboarding.sql`

```sql
BEGIN;

ALTER TABLE chat_settings
    ADD COLUMN IF NOT EXISTS onboarding_step VARCHAR(50) DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS onboarding_completed BOOLEAN DEFAULT FALSE;

-- Backfill: existing chats are already configured (via CLI)
UPDATE chat_settings SET onboarding_completed = TRUE;

INSERT INTO schema_version (version, description, applied_at)
VALUES (16, 'Add onboarding tracking to chat_settings', NOW());

COMMIT;
```

### Model Update: `chat_settings.py`

```python
onboarding_step = Column(String(50), nullable=True)      # Current wizard step
onboarding_completed = Column(Boolean, default=False)     # Setup finished?
```

### Settings Service Updates

```python
def set_onboarding_step(self, telegram_chat_id: int, step: Optional[str]) -> ChatSettings:
    """Update the onboarding step for a chat."""
    return self.settings_repo.update(telegram_chat_id, onboarding_step=step)

def complete_onboarding(self, telegram_chat_id: int) -> ChatSettings:
    """Mark onboarding as completed."""
    return self.settings_repo.update(
        telegram_chat_id, onboarding_step=None, onboarding_completed=True
    )
```

## Modifications to Existing Files

### `src/api/app.py`

- Mount static files: `app.mount("/static", StaticFiles(directory="src/api/static"), name="static")`
- Include onboarding router: `app.include_router(onboarding_router, prefix="/api/onboarding")`
- Add route to serve Mini App HTML: `GET /webapp/onboarding`

### `src/services/core/telegram_service.py`

- Update `/start` handler to send `WebAppInfo` button for new users
- Add `WebAppData` handler for receiving data from Mini App (if needed)
- Keep old `/start` behavior as fallback for returning users (dashboard message)

### `src/services/core/telegram_commands.py`

- Update `handle_start()` to check `onboarding_completed`:
  - New user → send `[Open Setup Wizard]` button with `web_app=WebAppInfo(url=...)`
  - Returning user → send dashboard summary message

### `src/models/chat_settings.py`

- Add `onboarding_step` and `onboarding_completed` columns

### `src/services/core/settings_service.py`

- Add `set_onboarding_step()` and `complete_onboarding()` methods

## Files to Create

| File | Description |
|------|-------------|
| `src/api/routes/onboarding.py` | API endpoints for Mini App |
| `src/api/static/onboarding/index.html` | Mini App HTML |
| `src/api/static/onboarding/style.css` | Mini App styles |
| `src/api/static/onboarding/app.js` | Mini App logic |
| `src/utils/webapp_auth.py` | initData HMAC validation |
| `scripts/migrations/016_chat_settings_onboarding.sql` | DB migration |
| `tests/src/api/test_onboarding_routes.py` | API endpoint tests |
| `tests/src/utils/test_webapp_auth.py` | initData validation tests |

## Files to Modify

| File | Change |
|------|--------|
| `src/api/app.py` | Mount static files, add onboarding router |
| `src/models/chat_settings.py` | Add onboarding columns |
| `src/services/core/settings_service.py` | Add onboarding convenience methods |
| `src/services/core/telegram_commands.py` | Update `/start` to open Mini App |
| `src/services/core/telegram_service.py` | Register updated `/start` handler |

## Implementation Sequence

1. **Migration + model** — Add onboarding columns to `chat_settings`
2. **Settings service** — Add `set_onboarding_step()` and `complete_onboarding()`
3. **initData validator** — Create `src/utils/webapp_auth.py`
4. **API endpoints** — Create `src/api/routes/onboarding.py`
5. **Update FastAPI app** — Mount static files, add router
6. **Mini App frontend** — Create HTML/CSS/JS files
7. **Update /start command** — Send `WebAppInfo` button
8. **Write tests** — Backend tests (API endpoints, initData validation, settings)
9. **Verification** — Full test suite, lint, manual check
10. **CHANGELOG + PR**

## Test Plan

### Backend Tests

**`tests/src/utils/test_webapp_auth.py`**:
- `test_valid_init_data_returns_user_info` — Happy path
- `test_missing_hash_raises` — No hash field
- `test_invalid_signature_raises` — Tampered data
- `test_expired_init_data_raises` — Past TTL
- `test_missing_user_data_handled` — Graceful degradation

**`tests/src/api/test_onboarding_routes.py`**:
- `test_init_returns_setup_state` — Returns current config
- `test_init_invalid_data_returns_401` — Bad initData rejected
- `test_oauth_url_returns_instagram_url` — Instagram OAuth URL
- `test_oauth_url_returns_gdrive_url` — Google Drive OAuth URL
- `test_media_folder_valid_url` — Parses folder ID, returns file count
- `test_media_folder_invalid_url` — Rejects bad URL
- `test_schedule_saves_config` — Updates chat_settings
- `test_complete_marks_onboarding_done` — Sets completed flag
- `test_complete_creates_schedule` — Calls SchedulerService when requested

**`tests/src/services/test_settings_service.py`** (extend existing):
- `test_set_onboarding_step` — Updates column
- `test_complete_onboarding` — Sets completed + clears step

### Frontend Tests

Frontend is vanilla JS — no unit test framework needed. Verified manually via:
- Open Mini App in Telegram test bot
- Walk through each step
- Verify OAuth polling works
- Verify schedule saves correctly
- Verify close sends summary to chat

## What NOT To Do

1. **Do NOT use a JS framework** (React, Vue, etc.) — vanilla JS keeps it simple and dependency-free
2. **Do NOT add Jinja2** — serve static HTML, use the API for dynamic data
3. **Do NOT trust initData without validation** — always verify HMAC on every API call
4. **Do NOT auto-create schedules** — the "Create Schedule" toggle is explicit user action
5. **Do NOT block other bot commands during onboarding** — `/help`, `/settings`, etc. still work
6. **Do NOT store sensitive data in the Mini App** — all tokens stay in the database, never sent to frontend

## Verification Checklist

- [ ] `/start` shows "Open Setup Wizard" button for new users
- [ ] `/start` shows dashboard summary for returning users
- [ ] Mini App loads and validates initData
- [ ] Instagram OAuth flow works (connect + polling detection)
- [ ] Google Drive OAuth flow works (connect + polling detection)
- [ ] Media folder URL is parsed and validated
- [ ] Schedule configuration saves to `chat_settings`
- [ ] "Finish Setup" marks onboarding complete and sends chat summary
- [ ] Mini App respects Telegram theme (dark/light mode)
- [ ] initData validation rejects tampered/expired data
- [ ] Ruff lint and format pass
- [ ] All tests pass
- [ ] CHANGELOG.md updated
