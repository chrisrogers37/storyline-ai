# Phase 02: Per-Tenant Repository Queries

**Status:** 🔧 IN PROGRESS
**Started:** 2026-02-14
**Risk:** Low
**Effort:** 4-6 hours
**PR Title:** `feat: add optional chat_settings_id tenant filtering to all repository methods`

---

## Context

Phase 01 (Multi-Tenant Data Model) adds a nullable `chat_settings_id` UUID FK column to 5 tables: `media_items`, `posting_queue`, `posting_history`, `media_posting_locks`, and `category_post_case_mix`. Per Architecture Decision AD-2, all FK columns are nullable. `NULL` means legacy single-tenant behavior and existing queries return unchanged results. (`api_tokens` was intentionally excluded — tokens scope through `instagram_accounts`, not directly to tenant.)

Phase 02 updates every public method in the 5 affected repositories to accept an optional `chat_settings_id` parameter. When provided, queries add a `WHERE chat_settings_id = :id` filter. When `None` (the default), behavior is identical to today. No service code changes occur in this phase.

## Dependencies

- **Requires:** Phase 01 (Multi-Tenant Data Model) merged. Specifically:
  - Migration `014_multi_tenant_fk.sql` (or equivalent) deployed
  - `chat_settings_id` column added to all 6 SQLAlchemy models
  - FK relationship to `ChatSettings` defined in each model
- **Required by:** Phase 03 (Per-Tenant Scheduler & Posting)

## Architecture Decision Recap

From `00_OVERVIEW.md` AD-2:
- All tenant FK columns are nullable
- `NULL` = legacy single-tenant behavior (existing queries unchanged)
- Per-tenant queries use `WHERE chat_settings_id = :id`
- This allows gradual migration without breaking the existing Pi deployment

## Pattern

Every query method follows this pattern:

```python
# BEFORE
def get_active(self) -> List[MediaItem]:
    return self.db.query(MediaItem).filter(MediaItem.is_active == True).all()

# AFTER
def get_active(self, chat_settings_id: Optional[str] = None) -> List[MediaItem]:
    query = self.db.query(MediaItem).filter(MediaItem.is_active == True)
    if chat_settings_id:
        query = query.filter(MediaItem.chat_settings_id == chat_settings_id)
    return query.all()
```

For create methods:

```python
# BEFORE
def create(self, file_path: str, ...) -> MediaItem:
    media_item = MediaItem(file_path=file_path, ...)
    ...

# AFTER
def create(self, file_path: str, ..., chat_settings_id: Optional[str] = None) -> MediaItem:
    media_item = MediaItem(file_path=file_path, ..., chat_settings_id=chat_settings_id)
    ...
```

A private helper method on BaseRepository can reduce boilerplate:

```python
# In BaseRepository
def _apply_tenant_filter(self, query, model_class, chat_settings_id: Optional[str]):
    """Apply tenant filter to query if chat_settings_id is provided."""
    if chat_settings_id:
        query = query.filter(model_class.chat_settings_id == chat_settings_id)
    return query
```

---

## File-by-File Method Changes

Below is every public method in each repository that needs updating, with the exact before/after signature change.

---

### 1. `src/repositories/base_repository.py` -- BaseRepository

**New helper method to add:**

```python
def _apply_tenant_filter(self, query, model_class, chat_settings_id: Optional[str] = None):
    """Apply tenant filter if chat_settings_id is provided. No-op when None."""
    if chat_settings_id:
        query = query.filter(model_class.chat_settings_id == chat_settings_id)
    return query
```

**Why a helper:** All 6 repositories repeat the same `if chat_settings_id:` conditional. Centralizing it in `BaseRepository` follows DRY and ensures consistent behavior. The helper is intentionally simple (3 lines) so it is easy to reason about.

No other existing BaseRepository methods change. `check_connection()`, `commit()`, `rollback()`, `end_read_transaction()`, `close()` are not tenant-scoped.

---

### 2. `src/repositories/media_repository.py` -- MediaRepository

**File location:** `/Users/chris/Projects/storyline-ai/src/repositories/media_repository.py`

**Import to add:** `from typing import Optional` (already present)

| # | Method | Current Signature | New Signature | Notes |
|---|--------|-------------------|---------------|-------|
| 1 | `get_by_id` | `get_by_id(self, media_id: str)` | `get_by_id(self, media_id: str, chat_settings_id: Optional[str] = None)` | Filter on lookup |
| 2 | `get_by_path` | `get_by_path(self, file_path: str)` | `get_by_path(self, file_path: str, chat_settings_id: Optional[str] = None)` | Filter on lookup |
| 3 | `get_by_hash` | `get_by_hash(self, file_hash: str)` | `get_by_hash(self, file_hash: str, chat_settings_id: Optional[str] = None)` | Filter on lookup |
| 4 | `get_by_instagram_media_id` | `get_by_instagram_media_id(self, instagram_media_id: str)` | `get_by_instagram_media_id(self, instagram_media_id: str, chat_settings_id: Optional[str] = None)` | Filter for backfill dedup |
| 5 | `get_backfilled_instagram_media_ids` | `get_backfilled_instagram_media_ids(self)` | `get_backfilled_instagram_media_ids(self, chat_settings_id: Optional[str] = None)` | Filter backfill set |
| 6 | `get_by_source_identifier` | `get_by_source_identifier(self, source_type: str, source_identifier: str)` | `get_by_source_identifier(self, source_type: str, source_identifier: str, chat_settings_id: Optional[str] = None)` | Filter on source lookup |
| 7 | `get_active_by_source_type` | `get_active_by_source_type(self, source_type: str)` | `get_active_by_source_type(self, source_type: str, chat_settings_id: Optional[str] = None)` | Filter for sync |
| 8 | `get_inactive_by_source_identifier` | `get_inactive_by_source_identifier(self, source_type: str, source_identifier: str)` | `get_inactive_by_source_identifier(self, source_type: str, source_identifier: str, chat_settings_id: Optional[str] = None)` | Filter for re-appearance |
| 9 | `reactivate` | `reactivate(self, media_id: str)` | No change | Operates on ID; tenant not relevant to single-row update |
| 10 | `update_source_info` | `update_source_info(self, media_id: str, ...)` | No change | Operates on ID |
| 11 | `get_all` | `get_all(self, is_active=None, requires_interaction=None, category=None, limit=None)` | `get_all(self, is_active=None, requires_interaction=None, category=None, limit=None, chat_settings_id: Optional[str] = None)` | Filter list queries |
| 12 | `get_categories` | `get_categories(self)` | `get_categories(self, chat_settings_id: Optional[str] = None)` | Filter category discovery |
| 13 | `create` | `create(self, file_path, file_name, file_hash, file_size_bytes, ...)` | `create(self, file_path, file_name, file_hash, file_size_bytes, ..., chat_settings_id: Optional[str] = None)` | Pass FK to model constructor |
| 14 | `update_metadata` | `update_metadata(self, media_id, ...)` | No change | Operates on ID |
| 15 | `increment_times_posted` | `increment_times_posted(self, media_id)` | No change | Operates on ID |
| 16 | `update_cloud_info` | `update_cloud_info(self, media_id, ...)` | No change | Operates on ID |
| 17 | `deactivate` | `deactivate(self, media_id)` | No change | Operates on ID |
| 18 | `delete` | `delete(self, media_id)` | No change | Operates on ID |
| 19 | `get_duplicates` | `get_duplicates(self)` | `get_duplicates(self, chat_settings_id: Optional[str] = None)` | Duplicates are per-tenant |
| 20 | `get_next_eligible_for_posting` | `get_next_eligible_for_posting(self, category=None)` | `get_next_eligible_for_posting(self, category=None, chat_settings_id: Optional[str] = None)` | Critical: must scope both main query AND subqueries |

**Special attention for `get_next_eligible_for_posting`:** This method contains subqueries for `PostingQueue` and `MediaPostingLock`. When `chat_settings_id` is provided, the tenant filter must be applied to:
1. The main `MediaItem` query
2. The `PostingQueue` subquery (so only queue items from the same tenant are excluded)
3. The `MediaPostingLock` subquery (so only locks from the same tenant are excluded)

**Total methods affected in MediaRepository: 13 modified, 7 unchanged**

---

### 3. `src/repositories/queue_repository.py` -- QueueRepository

**File location:** `/Users/chris/Projects/storyline-ai/src/repositories/queue_repository.py`

| # | Method | Current Signature | New Signature | Notes |
|---|--------|-------------------|---------------|-------|
| 1 | `get_by_id` | `get_by_id(self, queue_id: str)` | `get_by_id(self, queue_id: str, chat_settings_id: Optional[str] = None)` | Filter on lookup |
| 2 | `get_by_id_prefix` | `get_by_id_prefix(self, id_prefix: str)` | `get_by_id_prefix(self, id_prefix: str, chat_settings_id: Optional[str] = None)` | Filter prefix lookup |
| 3 | `get_by_media_id` | `get_by_media_id(self, media_id: str)` | `get_by_media_id(self, media_id: str, chat_settings_id: Optional[str] = None)` | Filter media lookup |
| 4 | `get_pending` | `get_pending(self, limit=None)` | `get_pending(self, limit=None, chat_settings_id: Optional[str] = None)` | Filter pending items |
| 5 | `get_all` | `get_all(self, status=None)` | `get_all(self, status=None, chat_settings_id: Optional[str] = None)` | Filter listing |
| 6 | `count_pending` | `count_pending(self)` | `count_pending(self, chat_settings_id: Optional[str] = None)` | Count per-tenant |
| 7 | `get_oldest_pending` | `get_oldest_pending(self)` | `get_oldest_pending(self, chat_settings_id: Optional[str] = None)` | Filter for next item |
| 8 | `create` | `create(self, media_item_id: str, scheduled_for: datetime)` | `create(self, media_item_id: str, scheduled_for: datetime, chat_settings_id: Optional[str] = None)` | Set FK on create |
| 9 | `update_status` | `update_status(self, queue_id, status)` | No change | Operates on ID |
| 10 | `update_scheduled_time` | `update_scheduled_time(self, queue_id, scheduled_for)` | No change | Operates on ID |
| 11 | `set_telegram_message` | `set_telegram_message(self, queue_id, message_id, chat_id)` | No change | Operates on ID |
| 12 | `schedule_retry` | `schedule_retry(self, queue_id, error_message, retry_delay_minutes=5)` | No change | Operates on ID |
| 13 | `delete` | `delete(self, queue_id)` | No change | Operates on ID |
| 14 | `delete_all_pending` | `delete_all_pending(self)` | `delete_all_pending(self, chat_settings_id: Optional[str] = None)` | Delete per-tenant only |
| 15 | `shift_slots_forward` | `shift_slots_forward(self, from_item_id)` | `shift_slots_forward(self, from_item_id: str, chat_settings_id: Optional[str] = None)` | Must scope to tenant's queue only |

**Special attention for `shift_slots_forward`:** This method calls `self.get_all(status="pending")` internally. That call must be updated to pass through the `chat_settings_id`. The implementation change is:

```python
# Before (line 197)
pending_items = self.get_all(status="pending")

# After
pending_items = self.get_all(status="pending", chat_settings_id=chat_settings_id)
```

**Total methods affected in QueueRepository: 10 modified, 5 unchanged**

---

### 4. `src/repositories/history_repository.py` -- HistoryRepository

**File location:** `/Users/chris/Projects/storyline-ai/src/repositories/history_repository.py`

The `HistoryCreateParams` dataclass also needs a new field.

**HistoryCreateParams change:**

```python
# Add to HistoryCreateParams (in optional fields section)
chat_settings_id: Optional[str] = None
```

| # | Method | Current Signature | New Signature | Notes |
|---|--------|-------------------|---------------|-------|
| 1 | `get_by_id` | `get_by_id(self, history_id: str)` | `get_by_id(self, history_id: str, chat_settings_id: Optional[str] = None)` | Filter on lookup |
| 2 | `get_all` | `get_all(self, status=None, days=None, limit=None)` | `get_all(self, status=None, days=None, limit=None, chat_settings_id: Optional[str] = None)` | Filter listing |
| 3 | `get_by_media_id` | `get_by_media_id(self, media_id, limit=None)` | `get_by_media_id(self, media_id: str, limit=None, chat_settings_id: Optional[str] = None)` | Filter by media + tenant |
| 4 | `create` | `create(self, params: HistoryCreateParams)` | No signature change (params dataclass gets the field) | `chat_settings_id` flows through `HistoryCreateParams` |
| 5 | `get_recent_posts` | `get_recent_posts(self, hours=24)` | `get_recent_posts(self, hours=24, chat_settings_id: Optional[str] = None)` | Filter recent posts |
| 6 | `count_by_method` | `count_by_method(self, method, since)` | `count_by_method(self, method: str, since: datetime, chat_settings_id: Optional[str] = None)` | Rate limiting per-tenant |

**Note on `count_by_method`:** This is used for Instagram API rate limiting. In multi-tenant mode, rate limits should be per-tenant (each tenant has their own Instagram account and rate limit).

**Total methods affected in HistoryRepository: 5 modified + 1 dataclass field, 1 unchanged**

---

### 5. `src/repositories/lock_repository.py` -- LockRepository

**File location:** `/Users/chris/Projects/storyline-ai/src/repositories/lock_repository.py`

| # | Method | Current Signature | New Signature | Notes |
|---|--------|-------------------|---------------|-------|
| 1 | `get_by_id` | `get_by_id(self, lock_id: str)` | `get_by_id(self, lock_id: str, chat_settings_id: Optional[str] = None)` | Filter on lookup |
| 2 | `get_active_lock` | `get_active_lock(self, media_id: str)` | `get_active_lock(self, media_id: str, chat_settings_id: Optional[str] = None)` | Filter active lock lookup |
| 3 | `is_locked` | `is_locked(self, media_id: str)` | `is_locked(self, media_id: str, chat_settings_id: Optional[str] = None)` | Passes through to `get_active_lock` |
| 4 | `get_all_active` | `get_all_active(self)` | `get_all_active(self, chat_settings_id: Optional[str] = None)` | Filter all active locks |
| 5 | `create` | `create(self, media_item_id, ttl_days, lock_reason="recent_post", created_by_user_id=None)` | `create(self, media_item_id, ttl_days, lock_reason="recent_post", created_by_user_id=None, chat_settings_id: Optional[str] = None)` | Set FK on create |
| 6 | `delete` | `delete(self, lock_id)` | No change | Operates on ID |
| 7 | `get_permanent_locks` | `get_permanent_locks(self)` | `get_permanent_locks(self, chat_settings_id: Optional[str] = None)` | Filter permanent locks |
| 8 | `cleanup_expired` | `cleanup_expired(self)` | `cleanup_expired(self, chat_settings_id: Optional[str] = None)` | Cleanup per-tenant only |

**Note on `is_locked`:** The implementation just delegates to `get_active_lock`, so the pass-through is straightforward:

```python
def is_locked(self, media_id: str, chat_settings_id: Optional[str] = None) -> bool:
    return self.get_active_lock(media_id, chat_settings_id) is not None
```

**Total methods affected in LockRepository: 7 modified, 1 unchanged**

---

### 6. `src/repositories/category_mix_repository.py` -- CategoryMixRepository

**File location:** `/Users/chris/Projects/storyline-ai/src/repositories/category_mix_repository.py`

| # | Method | Current Signature | New Signature | Notes |
|---|--------|-------------------|---------------|-------|
| 1 | `get_current_mix` | `get_current_mix(self)` | `get_current_mix(self, chat_settings_id: Optional[str] = None)` | Filter current mix |
| 2 | `get_current_mix_as_dict` | `get_current_mix_as_dict(self)` | `get_current_mix_as_dict(self, chat_settings_id: Optional[str] = None)` | Delegates to `get_current_mix` |
| 3 | `get_history` | `get_history(self, category=None)` | `get_history(self, category=None, chat_settings_id: Optional[str] = None)` | Filter history |
| 4 | `set_mix` | `set_mix(self, ratios, user_id=None)` | `set_mix(self, ratios, user_id=None, chat_settings_id: Optional[str] = None)` | Set FK on create + scope expire query |
| 5 | `has_current_mix` | `has_current_mix(self)` | `has_current_mix(self, chat_settings_id: Optional[str] = None)` | Check per-tenant |
| 6 | `get_categories_without_ratio` | `get_categories_without_ratio(self, categories)` | `get_categories_without_ratio(self, categories: List[str], chat_settings_id: Optional[str] = None)` | Delegates to `get_current_mix_as_dict` |
| 7 | `_validate_ratios` | `_validate_ratios(self, ratios)` | No change | Validation logic is tenant-independent |

**Special attention for `set_mix`:** This method does two things: (a) expires old records and (b) creates new records. Both operations must be tenant-scoped:
- Expiring old records: `get_current_mix(chat_settings_id=chat_settings_id)` to get only this tenant's records
- Creating new records: pass `chat_settings_id` to the `CategoryPostCaseMix` constructor

```python
def set_mix(self, ratios, user_id=None, chat_settings_id: Optional[str] = None):
    self._validate_ratios(ratios)
    now = datetime.utcnow()

    # Expire only THIS tenant's current records
    current_records = self.get_current_mix(chat_settings_id=chat_settings_id)
    for record in current_records:
        record.effective_to = now
        record.is_current = False

    # Create new records with tenant FK
    new_records = []
    for category, ratio in ratios.items():
        new_record = CategoryPostCaseMix(
            category=category,
            ratio=ratio,
            effective_from=now,
            effective_to=None,
            is_current=True,
            created_by_user_id=user_id,
            chat_settings_id=chat_settings_id,  # NEW
        )
        self.db.add(new_record)
        new_records.append(new_record)
    ...
```

**Total methods affected in CategoryMixRepository: 6 modified, 1 unchanged**

---

### ~~7. `src/repositories/token_repository.py` -- TokenRepository~~

**REMOVED (Challenge Round):** `api_tokens` does not have a `chat_settings_id` column. Phase 01 intentionally excluded `api_tokens` — tokens scope through `instagram_accounts` (their service account), not directly to tenant. No TokenRepository changes needed in Phase 02.

---

## Model Changes Required (Phase 01 prerequisite, documented here for reference)

These model changes are Phase 01's responsibility, but this plan documents the expected column names that Phase 02 repository code will reference:

Each of the 5 models gets:

```python
# In each model file
chat_settings_id = Column(
    UUID(as_uuid=True),
    ForeignKey("chat_settings.id"),
    nullable=True,  # NULL = legacy single-tenant
    index=True,
)
```

The column name `chat_settings_id` is consistent across all 5 models. Phase 02 code references `ModelClass.chat_settings_id` in all filter expressions.

---

## Test Plan

Each repository test file needs new test cases covering the tenant filtering behavior. The pattern is consistent:

**For every query method that gains `chat_settings_id`:**
1. Test that calling without `chat_settings_id` works as before (backward compatibility)
2. Test that calling with `chat_settings_id` adds the filter to the query chain

**For every create method that gains `chat_settings_id`:**
1. Test that creating without `chat_settings_id` sets `None` on the model
2. Test that creating with `chat_settings_id` sets the value on the model

### Test Files to Update

| Test File | Estimated New Tests |
|-----------|-------------------|
| `tests/src/repositories/test_media_repository.py` | ~15 (13 methods, plus subquery edge case for `get_next_eligible_for_posting`) |
| `tests/src/repositories/test_queue_repository.py` | ~12 (10 methods, plus `shift_slots_forward` pass-through) |
| `tests/src/repositories/test_history_repository.py` | ~7 (5 methods + dataclass field + create pass-through) |
| `tests/src/repositories/test_lock_repository.py` | ~9 (7 methods, plus `is_locked` pass-through) |
| `tests/src/repositories/test_category_mix_repository.py` | ~8 (6 methods, plus `set_mix` expire scope + create scope) |
| `tests/src/repositories/test_base_repository.py` | ~2 (new `_apply_tenant_filter` helper) |

**Total estimated new tests: ~53**

### Example Test Pattern (for `MediaRepository.get_all`)

```python
def test_get_all_without_tenant_filter(self, media_repo, mock_db):
    """Test that get_all without chat_settings_id returns all items (backward compat)."""
    mock_items = [MagicMock(), MagicMock()]
    mock_query = mock_db.query.return_value
    mock_query.all.return_value = mock_items

    result = media_repo.get_all(is_active=True)

    assert len(result) == 2
    # Verify no extra .filter() call for chat_settings_id

def test_get_all_with_tenant_filter(self, media_repo, mock_db):
    """Test that get_all with chat_settings_id adds tenant filter."""
    mock_items = [MagicMock()]
    mock_query = mock_db.query.return_value
    mock_query.all.return_value = mock_items

    result = media_repo.get_all(is_active=True, chat_settings_id="tenant-uuid-1")

    assert len(result) == 1
    # Verify .filter() was called with chat_settings_id argument
```

### Example Test Pattern (for `MediaRepository.create`)

```python
def test_create_media_item_with_tenant(self, media_repo, mock_db):
    """Test creating media item with chat_settings_id."""
    media_repo.create(
        file_path="/test/image.jpg",
        file_name="image.jpg",
        file_hash="abc123",
        file_size_bytes=102400,
        chat_settings_id="tenant-uuid-1",
    )

    added_item = mock_db.add.call_args[0][0]
    assert added_item.chat_settings_id == "tenant-uuid-1"

def test_create_media_item_without_tenant(self, media_repo, mock_db):
    """Test creating media item without chat_settings_id (backward compat)."""
    media_repo.create(
        file_path="/test/image.jpg",
        file_name="image.jpg",
        file_hash="abc123",
        file_size_bytes=102400,
    )

    added_item = mock_db.add.call_args[0][0]
    assert added_item.chat_settings_id is None
```

### Example Test for BaseRepository Helper

```python
def test_apply_tenant_filter_with_id(self, base_repo):
    """Test _apply_tenant_filter adds filter when chat_settings_id provided."""
    mock_query = MagicMock()
    filtered = base_repo._apply_tenant_filter(mock_query, MediaItem, "tenant-1")
    mock_query.filter.assert_called_once()

def test_apply_tenant_filter_without_id(self, base_repo):
    """Test _apply_tenant_filter is no-op when chat_settings_id is None."""
    mock_query = MagicMock()
    result = base_repo._apply_tenant_filter(mock_query, MediaItem, None)
    mock_query.filter.assert_not_called()
    assert result is mock_query
```

---

## Implementation Order

1. **BaseRepository** -- Add `_apply_tenant_filter` helper + tests
2. **MediaRepository** -- Largest file, most methods, do first to establish pattern
3. **QueueRepository** -- Second most methods, includes `shift_slots_forward` internal call
4. **HistoryRepository** -- Includes `HistoryCreateParams` dataclass change
5. **LockRepository** -- Straightforward application of pattern
6. **CategoryMixRepository** -- `set_mix` needs careful tenant scoping on both expire and create

---

## Verification Checklist

- [x] `_apply_tenant_filter` exists on `BaseRepository` and is used consistently
- [x] All 13 `MediaRepository` query/create methods updated
- [x] All 10 `QueueRepository` query/create methods updated
- [x] `HistoryCreateParams` dataclass has `chat_settings_id` field
- [x] All 5 `HistoryRepository` query methods updated
- [x] All 7 `LockRepository` query/create methods updated
- [x] All 6 `CategoryMixRepository` query/create methods updated
- [x] `QueueRepository.shift_slots_forward` passes `chat_settings_id` to `self.get_all`
- [x] `LockRepository.is_locked` passes `chat_settings_id` to `self.get_active_lock`
- [x] `CategoryMixRepository.get_current_mix_as_dict` passes `chat_settings_id` to `self.get_current_mix`
- [x] `CategoryMixRepository.get_categories_without_ratio` passes `chat_settings_id` through
- [x] `CategoryMixRepository.set_mix` passes `chat_settings_id` to both expire query and create
- [x] `MediaRepository.get_next_eligible_for_posting` applies tenant filter to main query AND subqueries
- [x] All existing tests still pass (backward compatibility -- `chat_settings_id=None` default)
- [x] New tests added for every modified method (both with and without tenant filter)
- [x] `ruff check src/ tests/` passes
- [x] `ruff format --check src/ tests/` passes
- [x] `pytest` passes (1046 passed, 21 skipped)
- [x] CHANGELOG.md updated

---

## What NOT To Do

1. **Do NOT modify any service code.** Services are Phase 03. Only repository files change in this phase.
2. **Do NOT modify any CLI command code.** CLI will be updated when services are updated in Phase 03.
3. **Do NOT modify any Telegram handler code.** Handlers call services, not repositories.
4. **Do NOT add `chat_settings_id` to methods that operate on primary key IDs.** Methods like `update_status(queue_id, status)`, `reactivate(media_id)`, `increment_times_posted(media_id)` etc. already have a unique row identified by PK. Adding tenant filtering would be redundant and could mask bugs (if the PK exists but belongs to a different tenant, that is a logic error that should be caught upstream in the service layer, not silently ignored by the repository).
5. **Do NOT make `chat_settings_id` required anywhere.** All parameters are `Optional[str] = None` for backward compatibility.
6. **Do NOT add migration files.** Phase 01 handles the migration. Phase 02 only touches Python code.
7. **Do NOT change the `ChatSettingsRepository`, `InstagramAccountRepository`, or `TokenRepository`.** `chat_settings` IS the tenant table, `instagram_accounts` is linked through it, and `api_tokens` was excluded from tenant FK (tokens scope through `instagram_accounts`).
8. **Do NOT change the `BaseRepository.check_connection()` method.** It is a static health check, not tenant-scoped.
9. **Do NOT use the helper method for `get_next_eligible_for_posting` subqueries.** The subqueries use `exists(select(...).where(...))` syntax which does not use `self.db.query()`. The tenant filter must be applied directly in the `where` clause of each subquery.

---

## Critical Files for Implementation
- `/Users/chris/Projects/storyline-ai/src/repositories/base_repository.py` - Add `_apply_tenant_filter` helper method used by all 5 repositories
- `/Users/chris/Projects/storyline-ai/src/repositories/media_repository.py` - Largest repository (13 methods to update), includes complex `get_next_eligible_for_posting` with subqueries
- `/Users/chris/Projects/storyline-ai/src/repositories/queue_repository.py` - 10 methods to update, `shift_slots_forward` has internal delegation that must pass tenant ID through
- `/Users/chris/Projects/storyline-ai/src/repositories/history_repository.py` - 5 methods + `HistoryCreateParams` dataclass update
- `/Users/chris/Projects/storyline-ai/src/repositories/lock_repository.py` - 7 methods to update, `is_locked` pass-through
- `/Users/chris/Projects/storyline-ai/src/repositories/category_mix_repository.py` - `set_mix` requires tenant scoping on both SCD expire and create operations
- `/Users/chris/Projects/storyline-ai/src/repositories/history_repository.py` - Requires `HistoryCreateParams` dataclass update in addition to method signatures
