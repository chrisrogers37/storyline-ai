# Phase 01: Multi-Tenant Data Model

**Status:** 🔧 IN PROGRESS
**Started:** 2026-02-14
**Risk:** Medium
**Effort:** 3-4 hours
**PR Title:** `feat: add chat_settings_id FK to 5 core tables for multi-tenant data model`

## Files Modified

| File | Action |
|------|--------|
| `src/models/media_item.py` | Add `chat_settings_id` FK column, move `file_path` uniqueness to table-level constraint |
| `src/models/posting_queue.py` | Add `chat_settings_id` FK column |
| `src/models/posting_history.py` | Add `chat_settings_id` FK column |
| `src/models/media_lock.py` | Add `chat_settings_id` FK column, rename unique constraint |
| `src/models/category_mix.py` | Add `chat_settings_id` FK column |
| `scripts/migrations/014_multi_tenant_chat_settings_fk.sql` | **NEW** — DDL for all 5 tables |
| `tests/src/models/test_media_item.py` | Update uniqueness assertion, add tenant column tests |
| `tests/src/models/test_posting_queue.py` | Add tenant column test |
| `tests/src/models/test_posting_history.py` | **NEW** — Full model test suite |
| `tests/src/models/test_media_lock.py` | **NEW** — Full model test suite |
| `tests/src/models/test_category_mix.py` | **NEW** — Full model test suite |
| `CHANGELOG.md` | Update `## [Unreleased]` |

**Removed from scope** (challenge round decision):
- `src/models/api_token.py` — tokens are scoped via their service account (instagram_accounts), not directly to tenant. Direct tenant FK on api_tokens would be redundant. When instagram_accounts gets `chat_settings_id` in Phase 02/03, tokens are transitively scoped.
- ORM `relationship("ChatSettings")` on all models — FK columns + indexes only. No one will traverse from child → ChatSettings via ORM. Add relationships later if an actual access pattern emerges.

## Context

This phase lays the data foundation for multi-tenancy. Five tenant-scoped tables get a nullable `chat_settings_id` FK column pointing to `chat_settings.id`. The `chat_settings` table is the **tenant identity** — each Telegram chat (group or DM) is one tenant.

**Nullable FKs** are critical: `NULL` means "legacy single-tenant data." This allows the existing Raspberry Pi deployment to continue working without any data migration. All existing rows simply have `NULL` as their tenant, and existing queries (which don't filter by `chat_settings_id`) continue to work identically.

**api_tokens excluded**: Tokens are scoped through their owning service account (e.g., `instagram_accounts`), not directly to tenant. When `instagram_accounts` gets its own `chat_settings_id` in Phase 02/03, tokens are transitively tenant-scoped.

**No ORM relationships**: Only FK columns and indexes are added. No `relationship("ChatSettings")` on child models — queries will filter by `WHERE chat_settings_id = :id`, not navigate ORM relationships.

This phase touches **only models and the migration**. No repository queries, no service logic, no CLI changes. Those are Phases 02 and 03.

## Dependencies

- **Depends on:** Nothing (this is the foundation)
- **Unlocks:** Phase 02 (Per-Tenant Repository Queries)

## Detailed Implementation Plan

### Step 1: Update `src/models/media_item.py`

This is the most complex change because `file_path` currently has **column-level** `unique=True`, which must move to a **table-level** `UniqueConstraint` that includes `chat_settings_id`.

**BEFORE** (current imports):
```python
from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
```

**AFTER** (imports — add `ForeignKey` to main import, add `UniqueConstraint`):
```python
from sqlalchemy import (
    Column,
    String,
    BigInteger,
    Boolean,
    Integer,
    DateTime,
    Text,
    ARRAY,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
```
(Note: `ForeignKey` was previously imported on a separate line — consolidate into main import block.)

**BEFORE** (current `file_path` column):
```python
    file_path = Column(Text, nullable=False, unique=True, index=True)
```

**AFTER** (remove `unique=True`):
```python
    file_path = Column(Text, nullable=False, index=True)
```

Add after `updated_at` (before `__repr__`):
```python
    # Multi-tenant: which chat owns this media item (NULL = legacy single-tenant)
    chat_settings_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_settings.id"),
        nullable=True,
        index=True,
    )
```

Add `__table_args__` (MediaItem currently has no `__table_args__`):
```python
    __table_args__ = (
        UniqueConstraint("file_path", "chat_settings_id", name="unique_file_path_per_tenant"),
    )
```

**Important**: PostgreSQL treats `NULL` as distinct in unique constraints. That means two rows with `file_path='foo.jpg'` and `chat_settings_id=NULL` would NOT violate this constraint. To preserve legacy uniqueness for `NULL`-tenant rows, the migration adds a partial unique index (see Step 7). The model-level constraint is correct for non-NULL tenants; the partial index handles the NULL case at the database level.

**Why nullable with no default?** We don't set `default=None` explicitly because SQLAlchemy columns are nullable by default. That is the correct behavior for legacy data -- but it means two different legacy rows could have the same `file_path` with NULL tenant. Since existing data already enforces uniqueness on `file_path` alone (via the old constraint), and we drop that old constraint in the migration, we add a partial unique index for the `NULL` case in the migration SQL (see Step 7).

### Step 2: Update `src/models/posting_queue.py`

No import changes needed (`ForeignKey` already imported).

Add after `last_error`, before `created_at`:
```python
    # Multi-tenant: which chat owns this queue item (NULL = legacy single-tenant)
    chat_settings_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_settings.id"),
        nullable=True,
        index=True,
    )
```

`__table_args__` stays as-is (only has `CheckConstraint`). No unique constraint changes needed.

### Step 3: Update `src/models/posting_history.py`

No import changes needed (`ForeignKey` already imported).

Add after `retry_count`, before `created_at`:
```python
    # Multi-tenant: which chat owns this history record (NULL = legacy single-tenant)
    chat_settings_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_settings.id"),
        nullable=True,
        index=True,
    )
```

No unique constraint changes needed.

### Step 4: Update `src/models/media_lock.py`

No import changes needed (`ForeignKey` and `UniqueConstraint` already imported).

Add after `created_by_user_id`, before `created_at`:
```python
    # Multi-tenant: which chat owns this lock (NULL = legacy single-tenant)
    chat_settings_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_settings.id"),
        nullable=True,
        index=True,
    )
```

Update `__table_args__` to include `chat_settings_id` in the unique constraint:
```python
    __table_args__ = (
        UniqueConstraint(
            "media_item_id", "locked_until", "chat_settings_id",
            name="unique_active_lock_per_tenant",
        ),
    )
```

**Rationale**: Adding `chat_settings_id` ensures the lock constraint is correct per-tenant. We drop the old constraint and create the new one in the migration.

### Step 5: Update `src/models/category_mix.py`

No import changes needed (`ForeignKey` already imported).

Add after `created_by_user_id`, before `__table_args__`:
```python
    # Multi-tenant: which chat owns this ratio config (NULL = legacy single-tenant)
    chat_settings_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_settings.id"),
        nullable=True,
        index=True,
    )
```

`__table_args__` stays as-is -- it only has a `CheckConstraint` on `ratio`, no unique constraints to modify.

### Step 6: Create Migration `scripts/migrations/014_multi_tenant_chat_settings_fk.sql`

This is the most critical file. It must:
1. Add 6 nullable FK columns
2. Create indexes on all 6
3. Drop old unique constraints that are being replaced
4. Create new unique constraints that include `chat_settings_id`
5. Add a partial unique index for `media_items.file_path` where `chat_settings_id IS NULL` (to preserve legacy uniqueness)
6. Record migration version 14

```sql
-- Migration 014: Add chat_settings_id FK to 6 tables for multi-tenant data model
-- Phase 01 of multi-tenant transition
--
-- Adds a nullable chat_settings_id UUID foreign key column to:
--   1. media_items
--   2. posting_queue
--   3. posting_history
--   4. media_posting_locks
--   5. category_post_case_mix
--
-- api_tokens excluded: tokens are scoped via their service account (instagram_accounts),
-- not directly to tenant.
--
-- All FKs are NULLABLE: NULL means legacy single-tenant data.
-- This ensures full backward compatibility with existing data.
--
-- Unique constraint changes:
--   - media_items: UNIQUE(file_path) -> UNIQUE(file_path, chat_settings_id)
--     + partial index for NULL chat_settings_id to preserve legacy uniqueness
--   - media_posting_locks: UNIQUE(media_item_id, locked_until) -> UNIQUE(media_item_id, locked_until, chat_settings_id)

BEGIN;

-- ============================================================
-- 1. media_items
-- ============================================================

ALTER TABLE media_items
    ADD COLUMN chat_settings_id UUID REFERENCES chat_settings(id);

CREATE INDEX IF NOT EXISTS idx_media_items_chat_settings_id
    ON media_items(chat_settings_id)
    WHERE chat_settings_id IS NOT NULL;

-- Drop old column-level unique constraint on file_path
ALTER TABLE media_items
    DROP CONSTRAINT IF EXISTS media_items_file_path_key;

-- New composite unique constraint: file_path per tenant
ALTER TABLE media_items
    ADD CONSTRAINT unique_file_path_per_tenant
    UNIQUE (file_path, chat_settings_id);

-- Partial unique index for legacy rows (chat_settings_id IS NULL)
-- Without this, multiple NULL-tenant rows with the same file_path would be allowed
-- because PostgreSQL treats NULLs as distinct in unique constraints.
CREATE UNIQUE INDEX IF NOT EXISTS idx_media_items_file_path_legacy_unique
    ON media_items(file_path)
    WHERE chat_settings_id IS NULL;

-- ============================================================
-- 2. posting_queue
-- ============================================================

ALTER TABLE posting_queue
    ADD COLUMN chat_settings_id UUID REFERENCES chat_settings(id);

CREATE INDEX IF NOT EXISTS idx_posting_queue_chat_settings_id
    ON posting_queue(chat_settings_id)
    WHERE chat_settings_id IS NOT NULL;

-- No unique constraint changes needed for posting_queue

-- ============================================================
-- 3. posting_history
-- ============================================================

ALTER TABLE posting_history
    ADD COLUMN chat_settings_id UUID REFERENCES chat_settings(id);

CREATE INDEX IF NOT EXISTS idx_posting_history_chat_settings_id
    ON posting_history(chat_settings_id)
    WHERE chat_settings_id IS NOT NULL;

-- No unique constraint changes needed for posting_history

-- ============================================================
-- 4. media_posting_locks
-- ============================================================

ALTER TABLE media_posting_locks
    ADD COLUMN chat_settings_id UUID REFERENCES chat_settings(id);

CREATE INDEX IF NOT EXISTS idx_media_posting_locks_chat_settings_id
    ON media_posting_locks(chat_settings_id)
    WHERE chat_settings_id IS NOT NULL;

-- Drop old unique constraint and create tenant-scoped version
ALTER TABLE media_posting_locks
    DROP CONSTRAINT IF EXISTS unique_active_lock;

ALTER TABLE media_posting_locks
    ADD CONSTRAINT unique_active_lock_per_tenant
    UNIQUE (media_item_id, locked_until, chat_settings_id);

-- ============================================================
-- 5. category_post_case_mix
-- ============================================================

ALTER TABLE category_post_case_mix
    ADD COLUMN chat_settings_id UUID REFERENCES chat_settings(id);

CREATE INDEX IF NOT EXISTS idx_category_post_case_mix_chat_settings_id
    ON category_post_case_mix(chat_settings_id)
    WHERE chat_settings_id IS NOT NULL;

-- No unique constraint changes needed (only has check constraint on ratio)

-- ============================================================
-- Record migration
-- ============================================================

INSERT INTO schema_version (version, description, applied_at)
VALUES (14, 'Add chat_settings_id FK to 5 tables for multi-tenant data model', NOW());

COMMIT;
```

### Step 7: Update Existing Model Tests

**Update `tests/src/models/test_media_item.py`**

Add these tests to the existing `TestMediaItemModel` class:

```python
    def test_chat_settings_id_nullable(self):
        assert MediaItem.chat_settings_id.nullable is True

    def test_file_path_is_not_column_level_unique(self):
        """file_path uniqueness moved to table-level UniqueConstraint with chat_settings_id."""
        assert MediaItem.file_path.unique is not True

    def test_has_unique_file_path_per_tenant_constraint(self):
        constraint_names = [
            c.name
            for c in MediaItem.__table_args__
            if hasattr(c, "name")
        ]
        assert "unique_file_path_per_tenant" in constraint_names
```

Also update the existing test `test_file_path_is_unique` -- this test currently asserts `MediaItem.file_path.unique is True`. It must be changed to verify the table-level constraint instead:

```python
    def test_file_path_uniqueness_is_per_tenant(self):
        """file_path is unique per tenant via table-level UniqueConstraint, not column-level."""
        # Column-level unique is removed
        assert MediaItem.file_path.unique is not True
        # Table-level constraint exists
        constraint_names = [
            c.name
            for c in MediaItem.__table_args__
            if hasattr(c, "name")
        ]
        assert "unique_file_path_per_tenant" in constraint_names
```

**Update `tests/src/models/test_posting_queue.py`**

Add to the existing `TestPostingQueueModel` class:

```python
    def test_chat_settings_id_nullable(self):
        assert PostingQueue.chat_settings_id.nullable is True
```

### Step 8: Create New Model Test Files

**Create `tests/src/models/test_posting_history.py`**:

```python
"""Tests for PostingHistory model definition."""

import uuid
from datetime import datetime

import pytest

from src.models.posting_history import PostingHistory


@pytest.mark.unit
class TestPostingHistoryModel:
    """Tests for PostingHistory model column definitions and defaults."""

    def test_tablename(self):
        assert PostingHistory.__tablename__ == "posting_history"

    def test_id_default_generates_uuids(self):
        default_fn = PostingHistory.id.default.arg
        assert callable(default_fn)
        assert default_fn.__name__ == "uuid4"

    def test_media_item_id_not_nullable(self):
        assert PostingHistory.media_item_id.nullable is False

    def test_posted_at_not_nullable(self):
        assert PostingHistory.posted_at.nullable is False

    def test_status_not_nullable(self):
        assert PostingHistory.status.nullable is False

    def test_success_not_nullable(self):
        assert PostingHistory.success.nullable is False

    def test_retry_count_defaults_to_zero(self):
        assert PostingHistory.retry_count.default.arg == 0

    def test_posting_method_defaults_to_telegram_manual(self):
        assert PostingHistory.posting_method.default.arg == "telegram_manual"

    def test_chat_settings_id_nullable(self):
        assert PostingHistory.chat_settings_id.nullable is True

    def test_has_check_constraint(self):
        constraint_names = [
            c.name for c in PostingHistory.__table_args__ if hasattr(c, "name")
        ]
        assert "check_history_status" in constraint_names

    def test_repr_format(self):
        item = PostingHistory(
            id=uuid.uuid4(),
            status="posted",
            posted_at=datetime(2026, 2, 12, 14, 0),
        )
        result = repr(item)
        assert "posted" in result
        assert "2026" in result
```

**Create `tests/src/models/test_media_lock.py`**:

```python
"""Tests for MediaPostingLock model definition."""

import uuid

import pytest

from src.models.media_lock import MediaPostingLock


@pytest.mark.unit
class TestMediaPostingLockModel:
    """Tests for MediaPostingLock model column definitions and defaults."""

    def test_tablename(self):
        assert MediaPostingLock.__tablename__ == "media_posting_locks"

    def test_id_default_generates_uuids(self):
        default_fn = MediaPostingLock.id.default.arg
        assert callable(default_fn)
        assert default_fn.__name__ == "uuid4"

    def test_media_item_id_not_nullable(self):
        assert MediaPostingLock.media_item_id.nullable is False

    def test_locked_at_not_nullable(self):
        assert MediaPostingLock.locked_at.nullable is False

    def test_locked_until_nullable(self):
        assert MediaPostingLock.locked_until.nullable is True

    def test_lock_reason_defaults_to_recent_post(self):
        assert MediaPostingLock.lock_reason.default.arg == "recent_post"

    def test_chat_settings_id_nullable(self):
        assert MediaPostingLock.chat_settings_id.nullable is True

    def test_has_tenant_scoped_unique_constraint(self):
        constraint_names = [
            c.name for c in MediaPostingLock.__table_args__ if hasattr(c, "name")
        ]
        assert "unique_active_lock_per_tenant" in constraint_names

    def test_old_unique_constraint_removed(self):
        constraint_names = [
            c.name for c in MediaPostingLock.__table_args__ if hasattr(c, "name")
        ]
        assert "unique_active_lock" not in constraint_names

    def test_repr_format(self):
        item_id = uuid.uuid4()
        item = MediaPostingLock(media_item_id=item_id, locked_until=None)
        result = repr(item)
        assert str(item_id) in result
```

**Create `tests/src/models/test_category_mix.py`**:

```python
"""Tests for CategoryPostCaseMix model definition."""

from decimal import Decimal

import pytest

from src.models.category_mix import CategoryPostCaseMix


@pytest.mark.unit
class TestCategoryPostCaseMixModel:
    """Tests for CategoryPostCaseMix model column definitions and defaults."""

    def test_tablename(self):
        assert CategoryPostCaseMix.__tablename__ == "category_post_case_mix"

    def test_id_default_generates_uuids(self):
        default_fn = CategoryPostCaseMix.id.default.arg
        assert callable(default_fn)
        assert default_fn.__name__ == "uuid4"

    def test_category_not_nullable(self):
        assert CategoryPostCaseMix.category.nullable is False

    def test_ratio_not_nullable(self):
        assert CategoryPostCaseMix.ratio.nullable is False

    def test_effective_from_not_nullable(self):
        assert CategoryPostCaseMix.effective_from.nullable is False

    def test_is_current_defaults_to_true(self):
        assert CategoryPostCaseMix.is_current.default.arg is True

    def test_chat_settings_id_nullable(self):
        assert CategoryPostCaseMix.chat_settings_id.nullable is True

    def test_has_ratio_check_constraint(self):
        constraint_names = [
            c.name for c in CategoryPostCaseMix.__table_args__ if hasattr(c, "name")
        ]
        assert "check_ratio_range" in constraint_names

    def test_repr_current(self):
        item = CategoryPostCaseMix(
            category="memes", ratio=Decimal("0.7000"), is_current=True
        )
        result = repr(item)
        assert "memes" in result
        assert "70.0%" in result
        assert "current" in result

    def test_repr_expired(self):
        from datetime import datetime

        item = CategoryPostCaseMix(
            category="merch",
            ratio=Decimal("0.3000"),
            is_current=False,
            effective_to=datetime(2026, 1, 15),
        )
        result = repr(item)
        assert "merch" in result
        assert "expired" in result
```

### Step 9: Run Pre-Commit Checks

After all changes, run:

```bash
source venv/bin/activate
ruff check src/models/ tests/src/models/
ruff format src/models/ tests/src/models/
pytest tests/src/models/ -v
pytest -v  # Full suite to verify nothing is broken
```

## Test Plan

### Unit Tests (automated)

All tests listed in Steps 8-9 above verify:
- `chat_settings_id` column is nullable on all 6 models
- Old unique constraints are removed from `__table_args__`
- New tenant-scoped unique constraints exist in `__table_args__`
- `file_path` no longer has column-level `unique=True` on MediaItem
- Existing tests for other columns still pass
- `repr` methods still work correctly

### Integration Test (manual, post-merge)

On the Raspberry Pi (production), run the migration manually:

```bash
# SSH to Pi
ssh crogberrypi

# Backup database first
pg_dump -U storyline_user -d storyline_ai > /tmp/pre_014_backup.sql

# Apply migration
cat scripts/migrations/014_multi_tenant_chat_settings_fk.sql | sudo -u postgres psql -d storyline_ai

# Verify columns exist
sudo -u postgres psql -d storyline_ai -c "\d media_items" | grep chat_settings_id
sudo -u postgres psql -d storyline_ai -c "\d posting_queue" | grep chat_settings_id
sudo -u postgres psql -d storyline_ai -c "\d posting_history" | grep chat_settings_id
sudo -u postgres psql -d storyline_ai -c "\d media_posting_locks" | grep chat_settings_id
sudo -u postgres psql -d storyline_ai -c "\d category_post_case_mix" | grep chat_settings_id

# Verify all existing data has NULL chat_settings_id (expected)
sudo -u postgres psql -d storyline_ai -c "SELECT COUNT(*) FROM media_items WHERE chat_settings_id IS NOT NULL;"
# Expected: 0

# Verify migration version recorded
sudo -u postgres psql -d storyline_ai -c "SELECT * FROM schema_version WHERE version = 14;"

# Verify application still works (safe read-only commands)
storyline-cli check-health
storyline-cli list-queue
storyline-cli list-media
```

## Verification Checklist

- [ ] All 5 model files have `chat_settings_id` column with `nullable=True`
- [ ] All 5 model files have `ForeignKey("chat_settings.id")`
- [ ] All 5 model files have `index=True` on the new column
- [ ] No `relationship("ChatSettings")` added (FK columns only)
- [ ] `media_item.py`: `file_path` column no longer has `unique=True`
- [ ] `media_item.py`: has `__table_args__` with `UniqueConstraint("file_path", "chat_settings_id", ...)`
- [ ] `media_lock.py`: `__table_args__` constraint renamed from `unique_active_lock` to `unique_active_lock_per_tenant` and includes `chat_settings_id`
- [ ] `api_token.py`: NOT modified (tokens scoped via service accounts)
- [ ] Migration file is `014_multi_tenant_chat_settings_fk.sql`
- [ ] Migration covers 5 tables (not api_tokens)
- [ ] Migration inserts `schema_version` row with `version = 14`
- [ ] Migration wrapped in `BEGIN; ... COMMIT;`
- [ ] Migration uses `DROP CONSTRAINT IF EXISTS` for safety
- [ ] Migration includes partial unique index for legacy `NULL` `chat_settings_id` on `media_items.file_path`
- [ ] All existing model tests still pass
- [ ] New tests exist for `chat_settings_id` on all 5 models
- [ ] `ruff check` passes
- [ ] `ruff format --check` passes
- [ ] `pytest` passes
- [ ] CHANGELOG.md updated under `## [Unreleased]`

## What NOT To Do

1. **Do NOT modify any repository files** (`src/repositories/*.py`). No query changes, no `WHERE` clause additions. That is Phase 02.

2. **Do NOT modify any service files** (`src/services/**/*.py`). No tenant-passing logic. That is Phase 03.

3. **Do NOT modify `src/models/chat_settings.py`**. Do NOT add `back_populates` relationships from ChatSettings to the 6 child tables. That would create circular complexity and is not needed until a future phase requires navigating from ChatSettings to its children.

4. **Do NOT add `NOT NULL` constraints or default values** on `chat_settings_id`. It must be nullable with no default. Existing data must remain valid with `NULL` values.

5. **Do NOT add `ON DELETE CASCADE`** to the `chat_settings_id` FK. If a ChatSettings row is deleted, we do NOT want to cascade-delete all associated media items, history, etc. The correct behavior is to error on delete (default `RESTRICT` behavior) until the data is re-assigned or cleaned up.

6. **Do NOT backfill existing data** with a `chat_settings_id`. That is a data migration task for a later phase, after repository and service layers can propagate tenant context.

7. **Do NOT modify `scripts/setup_database.sql`**. The base schema file represents the initial schema. All changes after the initial schema are done through numbered migration files.

8. **Do NOT modify `src/config/database.py`** or **`src/models/__init__.py`**. No new model files are being created, only existing models are being modified.

9. **Do NOT create partial indexes with non-standard names**. Follow the convention: `idx_{tablename}_{columnname}`.

10. **Do NOT run `storyline-cli process-queue`, `storyline-cli create-schedule`, or `python -m src.main`**. These are dangerous commands that post to Instagram or modify production data.
