# Phase 04: Split Onboarding Routes

**Status:** ✅ COMPLETE
**Started:** 2026-02-23
**Completed:** 2026-02-23
**PR Title:** refactor: split onboarding.py into focused route modules
**Risk:** Medium
**Effort:** Medium (~2-3 hours)
**Depends on:** Phase 03 (resource management cleanup makes this easier)
**Blocks:** None

## Problem

`src/api/routes/onboarding.py` is 859 lines containing 18 endpoints, 10 Pydantic request models, and a 94-line helper function. This makes it hard to navigate, review, and test. The file handles 4 distinct concerns:

1. **Setup wizard** — Initial onboarding flow (init, connect accounts, configure media, schedule, complete)
2. **Dashboard** — Home screen data (queue detail, history, media stats)
3. **Settings** — Toggle/update runtime settings, manage accounts
4. **Schedule actions** — Extend/regenerate schedule

## Target Structure

```
src/api/routes/
├── onboarding/
│   ├── __init__.py        # Re-exports the combined router
│   ├── models.py          # All Pydantic request/response models
│   ├── helpers.py         # _validate_request(), _get_setup_state()
│   ├── setup.py           # Setup wizard endpoints (init, connect, media, schedule, complete)
│   ├── dashboard.py       # Dashboard detail endpoints (queue, history, media-stats)
│   └── settings.py        # Settings + schedule action endpoints (toggle, update, extend, regenerate)
```

## Files to Create/Modify

| File | Action | Content |
|------|--------|---------|
| `src/api/routes/onboarding/__init__.py` | Create | Import and combine routers |
| `src/api/routes/onboarding/models.py` | Create | Move all Pydantic models here |
| `src/api/routes/onboarding/helpers.py` | Create | Move `_validate_request()` and `_get_setup_state()` |
| `src/api/routes/onboarding/setup.py` | Create | Setup wizard endpoints |
| `src/api/routes/onboarding/dashboard.py` | Create | Dashboard detail endpoints |
| `src/api/routes/onboarding/settings.py` | Create | Settings + schedule action endpoints |
| `src/api/routes/onboarding.py` | Delete | Replaced by the package |
| `src/api/app.py` | Modify | Update import path (if needed) |
| `tests/src/api/test_onboarding_routes.py` | Modify | Update imports if directly importing |
| `tests/src/api/test_onboarding_dashboard.py` | Modify | Update imports if directly importing |

## Implementation

### Step 1: Create the package directory

```bash
mkdir -p src/api/routes/onboarding
```

### Step 2: Extract Pydantic models → `models.py`

Move all request model classes from `onboarding.py` to `models.py`:
- `InitRequest`
- `MediaFolderRequest`
- `StartIndexingRequest`
- `ScheduleRequest`
- `CompleteRequest`
- `ToggleSettingRequest`
- `UpdateSettingRequest`
- `SwitchAccountRequest`
- `RemoveAccountRequest`
- `ScheduleActionRequest`

These are currently scattered throughout the file near their endpoint definitions. Collect them all into `models.py` with a single shared import block.

### Step 3: Extract helpers → `helpers.py`

Move these functions:
- `_validate_request(init_data, chat_id)` — validates Telegram init data
- `_get_setup_state(chat_id, chat_settings_id)` — gathers setup state for dashboard

These are used by multiple route modules, so they must live in a shared location.

### Step 4: Split endpoints into route modules

**`setup.py`** — Setup wizard flow (6 endpoints):
- `POST /api/onboarding/init` — Initialize setup / get current state
- `GET /api/onboarding/oauth-url/{provider}` — Get OAuth URL for provider
- `POST /api/onboarding/media-folder` — Set media source folder
- `POST /api/onboarding/start-indexing` — Trigger media indexing
- `POST /api/onboarding/schedule` — Configure posting schedule
- `POST /api/onboarding/complete` — Mark setup as complete

**`dashboard.py`** — Dashboard data (5 endpoints):
- `GET /api/onboarding/queue-detail` — Queue items with media info
- `GET /api/onboarding/history-detail` — Recent posting history
- `GET /api/onboarding/media-stats` — Media library breakdown
- `GET /api/onboarding/accounts` — List Instagram accounts
- `GET /api/onboarding/system-status` — System health check

**`settings.py`** — Settings and actions (7 endpoints):
- `POST /api/onboarding/toggle-setting` — Toggle boolean setting
- `POST /api/onboarding/update-setting` — Update numeric setting
- `POST /api/onboarding/switch-account` — Switch active Instagram account
- `POST /api/onboarding/remove-account` — Remove Instagram account
- `POST /api/onboarding/sync-media` — Trigger media sync
- `POST /api/onboarding/extend-schedule` — Extend schedule by N days
- `POST /api/onboarding/regenerate-schedule` — Clear and rebuild schedule

Each module creates its own `router = APIRouter()` with the appropriate prefix/tags.

### Step 5: Create `__init__.py` to combine routers

```python
"""Onboarding API routes — setup wizard, dashboard, and settings."""

from fastapi import APIRouter

from src.api.routes.onboarding.setup import router as setup_router
from src.api.routes.onboarding.dashboard import router as dashboard_router
from src.api.routes.onboarding.settings import router as settings_router

router = APIRouter()
router.include_router(setup_router)
router.include_router(dashboard_router)
router.include_router(settings_router)
```

### Step 6: Update `app.py` import

Check how `onboarding.py` is imported in `app.py`. If it imports `router` from `src.api.routes.onboarding`, the package `__init__.py` re-exports `router`, so the import path stays the same. Verify this works.

### Step 7: Delete original `onboarding.py`

After verifying all endpoints work via the package import, delete `src/api/routes/onboarding.py`.

### Step 8: Update test patch paths

Both test files use `patch("src.api.routes.onboarding.*")` in 40+ locations to mock repositories and services. After the split, each patch must target the specific submodule where the import lives:
- `patch("src.api.routes.onboarding.helpers.ChatSettingsRepository")` — for helpers.py imports
- `patch("src.api.routes.onboarding.setup.OAuthService")` — for setup.py imports
- `patch("src.api.routes.onboarding.dashboard.QueueRepository")` — for dashboard.py imports
- etc.

Map each patched name to its new submodule based on where the import statement lands.

### Step 9: Consolidate lazy imports

Move inline/lazy imports to module-level in each submodule. After the split, each module is small enough that top-level imports are cleaner:
- `setup.py`: OAuthService, GoogleDriveOAuthService, GoogleDriveService, MediaSyncService, SchedulerService
- `settings.py`: SchedulerService, MediaSyncService
- `dashboard.py`: HealthCheckService

## Test Plan

```bash
# Verify all endpoints still work
pytest tests/src/api/test_onboarding_routes.py -v
pytest tests/src/api/test_onboarding_dashboard.py -v

# Full suite
ruff check src/ tests/ && ruff format --check src/ tests/ && pytest
```

## Verification Checklist

- [ ] All 18 endpoints respond with same status codes and payloads
- [ ] No circular imports between route modules
- [ ] `app.py` imports router without path changes
- [ ] All Pydantic models importable from `onboarding.models`
- [ ] `_validate_request()` and `_get_setup_state()` accessible from all route modules
- [ ] All existing tests pass unchanged
- [ ] `ruff check` and `ruff format` pass
- [ ] Original `onboarding.py` deleted (no leftover file)

## What NOT To Do

- Do NOT change any endpoint paths, request schemas, or response formats. This is a pure code organization refactor.
- Do NOT add new endpoints in this PR. Keep it strictly structural.
- Do NOT move test files — they can stay as `test_onboarding_routes.py` and `test_onboarding_dashboard.py` even if the source is split. Test file splitting is separate work.
- Do NOT change the `_validate_request()` function signature or behavior.
- Do NOT add a `__all__` to `__init__.py` unless imports require it.
- Do NOT change the `/api/onboarding/` prefix — all routes must keep their current URL paths.
