# Fix 05: Duplicate Scheduler Runs for Test/Dev Chats

**Status**: ✅ COMPLETE
**Started**: 2026-02-25

**Investigation**: callback-reliability_2026-02-25
**Root Cause**: #5 from investigation — duplicate `process_pending_posts` per cycle
**Impact**: Low | **Effort**: Low | **Risk**: Low

---

## Problem

`PostingService.process_pending_posts` runs twice per scheduler cycle (duplicate `service_runs` entries at the same second). The `chat_settings` table has two rows:

| Row | dry_run_mode | is_paused | active_instagram_account_id | onboarding_completed |
|-----|---|---|---|---|
| Production | false | false | set | true |
| Test/Dev | true | false | NULL | false |

`get_all_active_chats()` filters only on `is_paused == False`, so both get processed. The dev chat produces no-op runs but still:
- Creates `service_runs` records (observability noise)
- Acquires DB connections (pool pressure)
- Runs settings + queue queries (unnecessary load)

---

## Solution

Filter `get_all_active()` to only return chats that have completed onboarding OR have an active Instagram account:

```python
.filter(
    ChatSettings.is_paused == False,
    or_(
        ChatSettings.onboarding_completed == True,
        ChatSettings.active_instagram_account_id.isnot(None),
    ),
)
```

This naturally excludes half-setup test chats without per-cycle queries.

---

## Implementation Steps

### Step 1: Update repository query

**File**: `src/repositories/chat_settings_repository.py`
**Method**: `get_all_active()` (line 111-114)

Add `or_` import from `sqlalchemy` and update the filter:

```python
from sqlalchemy import or_

# In get_all_active():
result = (
    self.db.query(ChatSettings)
    .filter(
        ChatSettings.is_paused == False,  # noqa: E712
        or_(
            ChatSettings.onboarding_completed == True,  # noqa: E712
            ChatSettings.active_instagram_account_id.isnot(None),
        ),
    )
    .order_by(ChatSettings.created_at.asc())
    .all()
)
```

### Step 2: Update docstrings

**File**: `src/repositories/chat_settings_repository.py` — Update `get_all_active()` docstring to document the new eligibility criteria.

**File**: `src/services/core/settings_service.py` — Update `get_all_active_chats()` docstring at line 245.

---

## Tests

**File**: `tests/src/repositories/test_chat_settings_repository.py`

```python
def test_get_all_active_excludes_incomplete_chats(self, settings_repo, mock_db):
    """get_all_active excludes chats without onboarding or active account."""
    mock_query = mock_db.query.return_value
    mock_query.filter.return_value.order_by.return_value.all.return_value = [
        Mock(is_paused=False, onboarding_completed=True),
    ]
    result = settings_repo.get_all_active()
    assert len(result) == 1
    # Verify .filter() received 2 conditions (is_paused + or_ clause)
    filter_call = mock_query.filter.call_args
    assert len(filter_call[0]) == 2
```

**File**: `tests/src/services/test_settings_service.py`

```python
def test_get_all_active_chats_delegates_to_repo(self):
    """get_all_active_chats returns filtered results from repo."""
```

---

## Verification

After deploying:

```sql
-- Should show only ONE process_pending_posts per cycle
SELECT started_at, method_name
FROM service_runs
WHERE method_name = 'process_pending_posts'
ORDER BY started_at DESC
LIMIT 10;
```

---

## Files Changed

| File | Change |
|------|--------|
| `src/repositories/chat_settings_repository.py` | Add `or_()` filter to `get_all_active()` |
| `src/services/core/settings_service.py` | Update docstring |
| `tests/src/repositories/test_chat_settings_repository.py` | Add filter validation tests |
| `tests/src/services/test_settings_service.py` | Add delegation test |
