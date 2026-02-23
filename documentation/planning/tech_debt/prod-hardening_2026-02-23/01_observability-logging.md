# Phase 01: Observability & Logging Gaps

**Status:** ✅ COMPLETE
**Started:** 2026-02-23
**Completed:** 2026-02-23
**PR:** #78
**Risk Level:** LOW
**Type:** Mechanical refactor

## Description

Fix silent exception handlers and docstring print statements in service layer.

### Changes

1. **Docstring `print()` examples** — Replace with comments in:
   - `src/services/integrations/cloud_storage.py` line 29
   - `src/services/integrations/instagram_api.py` line 41

2. **Silent `except Exception:` blocks** — Add `logger.debug()` to 6 status check helpers in `src/services/core/telegram_commands.py`:
   - `_get_sync_status_line` (line 258)
   - `_check_instagram_setup` (line 304)
   - `_check_gdrive_setup` (line 334)
   - `_check_media_setup` (line 352)
   - `_check_schedule_setup` (line 366)
   - `_check_delivery_setup` (line 378)

3. **Intentionally untouched**: `handle_cleanup` (line 539) — deleting already-deleted messages is expected to fail silently.

## Verification

- All existing tests pass unchanged
- `ruff check` and `ruff format` pass
- No `print()` calls remain in service method bodies
