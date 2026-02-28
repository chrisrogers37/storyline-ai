# Phase 03: Repository Query Builder

**Status**: ✅ COMPLETE
**Started**: 2026-02-28
**Completed**: 2026-02-28
**PR**: #90
**PR Title**: Add `_tenant_query()` helper to deduplicate repository tenant filtering
**Risk Level**: Low
**Estimated Effort**: Low (45 min)
**Files Modified**: 7 (1 base + 6 repositories)
**Dependencies**: None
**Blocks**: None

---

## Context

34 instances of the same 3-line pattern across 5 repositories:
```python
query = self.db.query(Model).filter(...)
query = self._apply_tenant_filter(query, Model, chat_settings_id)
return query.first()
```

A `_tenant_query()` helper in BaseRepository eliminates one line per instance and ensures tenant filtering is never forgotten.

---

## Implementation Plan

### 1. Add `_tenant_query()` to BaseRepository

**File**: `src/repositories/base_repository.py`

**After** the existing `_apply_tenant_filter()` method, add:

```python
def _tenant_query(self, model_class, chat_settings_id=None):
    """Start a query with automatic tenant filtering applied."""
    query = self.db.query(model_class)
    return self._apply_tenant_filter(query, model_class, chat_settings_id)
```

### 2. Refactor each repository

For each repository, replace the 3-line pattern with the 2-line equivalent.

**Pattern Before**:
```python
def get_something(self, value, chat_settings_id=None):
    query = self.db.query(Model).filter(Model.col == value)
    query = self._apply_tenant_filter(query, Model, chat_settings_id)
    return query.first()
```

**Pattern After**:
```python
def get_something(self, value, chat_settings_id=None):
    return self._tenant_query(Model, chat_settings_id).filter(
        Model.col == value
    ).first()
```

#### Files and instance counts:

| File | Instances | Notes |
|------|-----------|-------|
| `src/repositories/media_repository.py` | 12 | Largest file, most instances (includes `get_next_eligible_for_posting`) |
| `src/repositories/queue_repository.py` | 9 | |
| `src/repositories/history_repository.py` | 5 | |
| `src/repositories/lock_repository.py` | 5 | |
| `src/repositories/category_mix_repository.py` | 3 | |

**Total**: 34 instances to refactor.

#### Repositories to NOT touch:
- `token_repository.py` — uses service-name + type filters (intentional, not tenant-scoped)
- `instagram_account_repository.py` — non-tenant table
- `user_repository.py` — non-tenant table
- `chat_settings_repository.py` — IS the tenant table
- `interaction_repository.py` — non-tenant table
- `service_run_repository.py` — non-tenant table

### 3. Implementation approach per file

For each repository file:
1. Read the file
2. Identify all `self._apply_tenant_filter(query, Model, chat_settings_id)` calls
3. For each: merge the preceding `self.db.query(Model)` line with the filter call into `self._tenant_query(Model, chat_settings_id)`
4. Preserve any `.filter()` chains that come after
5. Keep the terminal `.first()`, `.all()`, or `.count()` intact

Some methods have additional filters between query creation and tenant filter — for these, use:
```python
self._tenant_query(Model, chat_settings_id).filter(
    Model.col1 == val1,
    Model.col2 == val2
).first()
```

---

## Test Plan

```bash
# 1. Add unit test for _tenant_query
# In tests/src/repositories/test_base_repository.py:
```

```python
def test_tenant_query_applies_filter(self):
    """_tenant_query returns a filtered query."""
    repo = SomeRepository()
    repo.db = Mock()
    mock_query = Mock()
    repo.db.query.return_value = mock_query

    with patch.object(repo, '_apply_tenant_filter', return_value=mock_query) as mock_filter:
        result = repo._tenant_query(SomeModel, chat_settings_id="abc")

    repo.db.query.assert_called_once_with(SomeModel)
    mock_filter.assert_called_once_with(mock_query, SomeModel, "abc")
    assert result == mock_query
```

```bash
# 2. Run all repository tests
pytest tests/src/repositories/ -v

# 3. Run full suite to catch integration issues
pytest

# 4. Lint
ruff check src/ tests/ && ruff format --check src/ tests/
```

---

## Verification Checklist

- [ ] `_tenant_query()` added to `base_repository.py`
- [ ] All 34 instances refactored across 5 files
- [ ] No remaining `self._apply_tenant_filter(` calls in the 5 refactored files (grep to verify)
- [ ] `_apply_tenant_filter` still exists in base_repository.py (don't remove it — `_tenant_query` calls it)
- [ ] Unit test for `_tenant_query` passes
- [ ] All existing repository tests pass unchanged
- [ ] Full `pytest` passes
- [ ] `ruff check` and `ruff format` pass
- [ ] CHANGELOG.md updated

---

## What NOT To Do

- **Don't remove `_apply_tenant_filter()`** — `_tenant_query()` delegates to it; other code may call it directly
- **Don't refactor `token_repository.py`** — it uses intentionally different filtering (service-name + type)
- **Don't change method signatures** — all external callers remain unchanged
- **Don't add `_tenant_query()` calls where `_apply_tenant_filter()` wasn't already used** — this is a refactor, not a security fix
- **Don't collapse multi-filter methods that have complex logic between query creation and execution** — only refactor the straightforward pattern
