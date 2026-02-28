# Phase 02: API Error Handling Deduplication

**Status**: ✅ COMPLETE
**Started**: 2026-02-26
**Completed**: 2026-02-26
**PR**: #88
**PR Title**: Extract service_error_handler to eliminate duplicated ValueError-to-HTTPException patterns
**Risk Level**: Low
**Estimated Effort**: Low (20 min)
**Files Modified**: 3 route files + 1 helper file + 1 new test file
**Dependencies**: None
**Blocks**: None

---

## Context

11 instances of `try: ... except ValueError as e: raise HTTPException(status_code=400, detail=str(e))` across 3 API route files. 9 are clean single-catch patterns; 2 have compound `except ValueError` + `except Exception` handlers that must be left as-is (nesting the context manager would cause the outer `except Exception` to catch the re-raised HTTPException). A context manager replaces the 9 clean instances.

---

## Implementation Plan

### 1. Add `service_error_handler()` to helpers.py

**File**: `src/api/routes/onboarding/helpers.py`

Add a context manager after the existing `_get_setup_state()` function (end of file):

```python
from contextlib import contextmanager

@contextmanager
def service_error_handler():
    """Convert service ValueError exceptions to HTTP 400 responses."""
    try:
        yield
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

### 2. Refactor settings.py (4 of 5 instances)

**File**: `src/api/routes/onboarding/settings.py`

Add `service_error_handler` to the existing helpers import.

Apply to these 4 endpoints (lines ~46-55, ~72-81, ~90-101, ~110-120):
- `onboarding_toggle_setting` (line 46)
- `onboarding_update_setting` (line 72)
- `onboarding_switch_account` (line 90)
- `onboarding_remove_account` (line 110)

**Before** (repeated pattern):
```python
        try:
            new_value = settings_service.toggle_setting(...)
            return {...}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
```

**After**:
```python
        with service_error_handler():
            new_value = settings_service.toggle_setting(...)
            return {...}
```

**SKIP**: `onboarding_sync_media` (line 144) — has compound `except ValueError` + `except Exception` pattern. Nesting the context manager would cause the outer handler to catch the re-raised HTTPException.

### 3. Refactor setup.py (3 of 4 instances)

**File**: `src/api/routes/onboarding/setup.py`

Add `service_error_handler` to the existing helpers import.

Apply to these 3 locations:
- `onboarding_oauth_url` Instagram branch (line 59-62)
- `onboarding_oauth_url` Google Drive branch (line 67-70)
- `onboarding_schedule` (line 188-200)

**SKIP**: `onboarding_start_indexing` (line 151) — same compound pattern as above.

### 4. Refactor oauth.py (2 instances)

**File**: `src/api/routes/oauth.py`

Add import:
```python
from src.api.routes.onboarding.helpers import service_error_handler
```

Apply to these 2 locations:
- `instagram_oauth_start` (lines 26-30)
- `google_drive_oauth_start` (lines 125-129)

Note: Both have `finally: service.close()` blocks — the context manager nests cleanly inside the try/finally.

**DO NOT TOUCH**: Lines 66, 80, 159, 173 — these are OAuth callback patterns (bare `except ValueError: pass` for CSRF recovery, and `except ValueError` returning HTML error pages). Different behavior, not candidates.

---

## Test Plan

Create `tests/src/api/test_helpers.py`:

```python
import pytest
from fastapi import HTTPException

from src.api.routes.onboarding.helpers import service_error_handler


class TestServiceErrorHandler:
    """Tests for the service_error_handler context manager."""

    def test_passes_through_on_success(self):
        """Normal execution passes through unchanged."""
        with service_error_handler():
            result = "success"
        assert result == "success"

    def test_converts_value_error_to_http_400(self):
        """ValueError is converted to HTTPException 400."""
        with pytest.raises(HTTPException) as exc_info:
            with service_error_handler():
                raise ValueError("Invalid input")
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Invalid input"

    def test_propagates_non_value_errors(self):
        """Non-ValueError exceptions propagate unchanged."""
        with pytest.raises(RuntimeError):
            with service_error_handler():
                raise RuntimeError("Something else")
```

Verification commands:
```bash
pytest tests/src/api/ -v
pytest
ruff check src/ tests/
ruff format --check src/ tests/
```

---

## Verification Checklist

- [ ] `service_error_handler()` added to `helpers.py`
- [ ] 9 clean try/except ValueError blocks replaced with context manager
- [ ] 2 compound-pattern instances intentionally left as-is (settings.py:onboarding_sync_media, setup.py:onboarding_start_indexing)
- [ ] Unit tests for the context manager pass
- [ ] Existing API tests pass unchanged
- [ ] `ruff check` and `ruff format` pass
- [ ] CHANGELOG.md updated

---

## What NOT To Do

- **Don't use a decorator** — context manager is more explicit and doesn't change function signatures
- **Don't catch all exceptions** — only ValueError, let other exceptions propagate naturally
- **Don't move the helper out of onboarding/** — `oauth.py` importing from onboarding is acceptable since it's the same API layer; don't over-abstract
- **Don't refactor `_validate_request()`** — it's a different pattern (initData parsing), leave it alone
- **Don't add the handler to endpoints that don't have ValueError catches** — only replace existing patterns
- **Don't refactor compound ValueError+Exception patterns** — nesting the context manager inside a try/except Exception would cause the outer handler to catch the re-raised HTTPException, silently changing error behavior
