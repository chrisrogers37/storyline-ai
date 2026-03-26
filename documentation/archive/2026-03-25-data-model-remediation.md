# Data Model Remediation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remediate all 17 findings from the 2026-03-25 data model audit — remove vestigial columns, fix model drift, replace in-memory aggregation with SQL, fix N+1 queries, improve transaction atomicity, and standardize connection cleanup.

**Architecture:** Changes span all layers (models → repositories → services → CLI) plus a new SQL migration. No structural decomposition of god tables (tolerable at current scale per audit). ORM relationships added only where they eliminate N+1 patterns.

**Tech Stack:** Python 3.10+, SQLAlchemy ORM, PostgreSQL (Neon), pytest

---

## File Structure

### Files Modified

| File | Changes |
|------|---------|
| `src/models/posting_queue.py` | Remove 6 vestigial columns, update CHECK constraint |
| `src/models/posting_history.py` | Remove 3 write-only columns (media_metadata, error_message, retry_count) |
| `src/models/media_item.py` | Remove requires_interaction column + link_url comment |
| `src/models/user.py` | Remove team_name, first_seen_at columns |
| `src/models/chat_settings.py` | Remove chat_name, add CHECK constraints to ORM |
| `src/models/media_lock.py` | Add lock_reason CHECK constraint to ORM |
| `src/config/database.py` | Add missing model imports to init_db() |
| `src/repositories/media_repository.py` | Remove requires_interaction param, add count methods |
| `src/repositories/history_repository.py` | Remove dropped params from HistoryCreateParams, add end_read_transaction, add JOIN method |
| `src/repositories/interaction_repository.py` | Rewrite 3 methods with SQL aggregation, add end_read_transaction |
| `src/repositories/user_repository.py` | Remove team_name param, add end_read_transaction |
| `src/repositories/lock_repository.py` | Add count_permanent_locks(), add end_read_transaction |
| `src/repositories/queue_repository.py` | Add JOIN method, add end_read_transaction |
| `src/repositories/category_mix_repository.py` | Add end_read_transaction |
| `src/repositories/service_run_repository.py` | Add end_read_transaction |
| `src/services/core/dashboard_service.py` | Use SQL counts + JOIN methods, fix N+1 |
| `src/services/core/telegram_commands.py` | Use SQL counts instead of loading all media |
| `src/services/core/telegram_callbacks.py` | Fix transaction atomicity (single commit) |
| `src/services/core/media_ingestion.py` | Add get_category_counts() service method |
| `src/services/core/scheduler.py` | Clean up TIMESTAMPTZ workaround comment |
| `cli/commands/media.py` | Use get_category_counts() in display_current_mix + list_categories |

### Files Created

| File | Purpose |
|------|---------|
| `scripts/migrations/020_data_model_cleanup.sql` | Drop columns, update constraints, fix types |
| `tests/src/services/test_dashboard_service.py` | New test file for DashboardService |

### Test Files Modified

| File | Changes |
|------|---------|
| `tests/src/models/test_posting_queue.py` | Remove tests for dropped columns, update CHECK test |
| `tests/src/models/test_posting_history.py` | Remove retry_count default test |
| `tests/src/models/test_media_item.py` | Remove requires_interaction test |
| `tests/src/repositories/test_history_repository.py` | Remove media_metadata from test params |
| `tests/src/repositories/test_interaction_repository.py` | Add tests for SQL aggregation methods |
| `tests/src/repositories/test_media_repository.py` | Remove requires_interaction param tests, add count tests |

---

## Task 1: ORM Model Cleanup — Remove Vestigial Columns

**Findings addressed:** #4 (posting_queue bloat), #5 (posting_history write-only), #6 (requires_interaction), #15 (unused user/chat_settings cols), #16 (retrying status)

**Files:**
- Modify: `src/models/posting_queue.py`
- Modify: `src/models/posting_history.py`
- Modify: `src/models/media_item.py`
- Modify: `src/models/user.py`
- Modify: `src/models/chat_settings.py`
- Modify: `tests/src/models/test_posting_queue.py`
- Modify: `tests/src/models/test_posting_history.py`
- Modify: `tests/src/models/test_media_item.py`

- [ ] **Step 1: Run existing tests to establish baseline**

Run: `cd /Users/chris/Projects/storyline-ai && source venv/bin/activate && pytest tests/src/models/ -v --tb=short`
Expected: All model tests PASS

- [ ] **Step 2: Remove vestigial columns from PostingQueue model**

In `src/models/posting_queue.py`:
- Remove `web_hosted_url` (line 45)
- Remove `web_hosted_public_id` (line 46)
- Remove `retry_count` (line 53)
- Remove `max_retries` (line 54)
- Remove `next_retry_at` (line 55)
- Remove `last_error` (line 56)
- Remove `Text` from imports (no longer needed)
- Remove `Integer` from imports (no longer needed)
- Update CHECK constraint: `"status IN ('pending', 'processing')"` (remove 'retrying')
- Update status comment: `# 'pending', 'processing'`

- [ ] **Step 3: Remove write-only columns from PostingHistory model**

In `src/models/posting_history.py`:
- Remove `media_metadata` (line 41) and its comment (line 39-40)
- Remove `error_message` (line 65)
- Remove `retry_count` (line 66)
- Remove `JSONB` from imports

- [ ] **Step 4: Remove requires_interaction from MediaItem model**

In `src/models/media_item.py`:
- Remove `requires_interaction` column (lines 47-49)
- Update `link_url` comment to remove "(if requires_interaction = TRUE)"

- [ ] **Step 5: Remove unused columns from User model**

In `src/models/user.py`:
- Remove `team_name` (line 30)
- Remove `first_seen_at` (line 38)

- [ ] **Step 6: Remove chat_name from ChatSettings model**

In `src/models/chat_settings.py`:
- Remove `chat_name` (line 35)

- [ ] **Step 7: Update model tests**

In `tests/src/models/test_posting_queue.py`:
- Remove `test_retry_count_defaults_to_zero`
- Remove `test_max_retries_defaults_to_three`

In `tests/src/models/test_posting_history.py`:
- Remove `test_retry_count_defaults_to_zero`

In `tests/src/models/test_media_item.py`:
- Remove `test_requires_interaction_defaults_to_false`

- [ ] **Step 8: Run model tests to verify**

Run: `pytest tests/src/models/ -v --tb=short`
Expected: All PASS (fewer tests)

- [ ] **Step 9: Commit**

```bash
git add src/models/ tests/src/models/
git commit -m "refactor: remove vestigial columns from ORM models

Drop 6 columns from posting_queue (retry/web_hosted), 3 from
posting_history (media_metadata/error_message/retry_count),
requires_interaction from media_items, team_name/first_seen_at
from users, chat_name from chat_settings. Update CHECK constraint
to remove vestigial 'retrying' status."
```

---

## Task 2: Model Drift Fixes — Constraints, init_db, DateTime

**Findings addressed:** #2 (TIMESTAMPTZ mismatch), #7 (init_db imports), #8 (missing ORM CHECK constraints), #13 (lock_reason CHECK), #14 (role informational)

**Note on Finding #8 indexes:** The 13 SQL-only indexes are intentionally NOT added to ORM `__table_args__`. The DB is authoritative for indexes; ORM metadata missing them is cosmetic. Adding them risks double-creation issues. Only the 4 CHECK constraints are added to ORM to ensure `create_all()` (used in tests) produces correct constraints.

**Files:**
- Modify: `src/config/database.py`
- Modify: `src/models/chat_settings.py`
- Modify: `src/models/media_lock.py`
- Modify: `src/models/user.py`
- Modify: `src/services/core/scheduler.py`

- [ ] **Step 1: Fix init_db() to import all models**

In `src/config/database.py`, update the import block in `init_db()`:

```python
from src.models import (  # noqa: F401
    user,
    media_item,
    posting_queue,
    posting_history,
    media_lock,
    service_run,
    user_interaction,
    category_mix,
    instagram_account,
    api_token,
    chat_settings,
)
```

- [ ] **Step 2: Add CHECK constraints to ChatSettings ORM**

In `src/models/chat_settings.py`, add `CheckConstraint` to imports and add `__table_args__`:

```python
from sqlalchemy import (
    Column, String, Text, Integer, Boolean, BigInteger, DateTime, ForeignKey,
    CheckConstraint,
)
```

Add at bottom of class (before `__repr__`):

```python
__table_args__ = (
    CheckConstraint(
        "posts_per_day BETWEEN 1 AND 50",
        name="valid_posts_per_day",
    ),
    CheckConstraint(
        "posting_hours_start BETWEEN 0 AND 23",
        name="valid_hours_start",
    ),
    CheckConstraint(
        "posting_hours_end BETWEEN 0 AND 23",
        name="valid_hours_end",
    ),
)
```

- [ ] **Step 3: Add lock_reason CHECK constraint to MediaPostingLock ORM**

In `src/models/media_lock.py`, add `CheckConstraint` to imports and update `__table_args__`:

```python
from sqlalchemy import Column, String, DateTime, UniqueConstraint, CheckConstraint
```

Update `__table_args__`:

```python
__table_args__ = (
    UniqueConstraint(
        "media_item_id",
        "locked_until",
        "chat_settings_id",
        name="unique_active_lock_per_tenant",
    ),
    CheckConstraint(
        "lock_reason IN ('recent_post', 'skip', 'manual_hold', 'seasonal', 'permanent_reject')",
        name="check_lock_reason",
    ),
)
```

- [ ] **Step 4: Add role CHECK constraint to User ORM**

In `src/models/user.py`, add `CheckConstraint` to imports and add `__table_args__`:

```python
from sqlalchemy import Column, String, BigInteger, Boolean, Integer, DateTime, CheckConstraint
```

Add at bottom of class:

```python
__table_args__ = (
    CheckConstraint(
        "role IN ('admin', 'member')",
        name="check_user_role",
    ),
)
```

- [ ] **Step 5: Fix TIMESTAMPTZ/DateTime mismatch**

In `src/models/chat_settings.py`, change `last_post_sent_at`:

```python
last_post_sent_at = Column(DateTime(timezone=True), nullable=True)
```

In `src/services/core/scheduler.py`, remove the timezone workaround (lines 63-65). Now that the ORM declares `DateTime(timezone=True)`, SQLAlchemy will return timezone-aware datetimes consistently. Replace:

```python
last_sent = chat_settings.last_post_sent_at
# Strip tzinfo — DB column is TIMESTAMPTZ but codebase uses naive UTC
if last_sent and last_sent.tzinfo is not None:
    last_sent = last_sent.replace(tzinfo=None)
if last_sent and (now - last_sent).total_seconds() < interval_seconds:
    return False  # Too soon
```

With:

```python
last_sent = chat_settings.last_post_sent_at
if last_sent:
    # ORM now declares timezone=True, so strip tzinfo for naive UTC comparison
    last_sent_naive = last_sent.replace(tzinfo=None) if last_sent.tzinfo else last_sent
    if (now - last_sent_naive).total_seconds() < interval_seconds:
        return False  # Too soon
```

Note: The normalization step remains because the codebase uses naive UTC for `now`. The fix is that the ORM column type now correctly reflects the DB column type (`TIMESTAMPTZ`), which means SQLAlchemy metadata and `create_all()` will produce the right type. The runtime behavior is equivalent but the model is now honest about what the DB stores.

- [ ] **Step 6: Run full test suite**

Run: `pytest --tb=short`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/config/database.py src/models/ src/services/core/scheduler.py
git commit -m "fix: resolve model drift — add missing constraints, imports, and DateTime fix

Add all 11 model imports to init_db(). Add CHECK constraints to ORM
for chat_settings (posts_per_day, posting_hours), media_posting_locks
(lock_reason), and users (role). Fix last_post_sent_at to use
DateTime(timezone=True) matching the TIMESTAMPTZ DB column."
```

---

## Task 3: Repository Cleanup — Remove Dropped Column References

**Findings addressed:** Cascading from Task 1 column removals

**Files:**
- Modify: `src/repositories/media_repository.py`
- Modify: `src/repositories/history_repository.py`
- Modify: `src/repositories/user_repository.py`
- Modify: `tests/src/repositories/test_history_repository.py`
- Modify: `tests/src/repositories/test_media_repository.py`

- [ ] **Step 1: Remove requires_interaction from MediaRepository**

In `src/repositories/media_repository.py`:
- Remove `requires_interaction` parameter from `get_all()` (line 214) and its filter block (lines 225-226)
- Remove `requires_interaction` parameter from `create()` (line 256) and its usage (line 275)

- [ ] **Step 2: Remove dropped fields from HistoryCreateParams**

In `src/repositories/history_repository.py`:
- Remove `media_metadata` field from HistoryCreateParams (line 30)
- Remove `error_message` field (line 37)
- Remove `retry_count` field (line 38)

- [ ] **Step 3: Remove team_name from UserRepository.create()**

In `src/repositories/user_repository.py`:
- Remove `team_name` parameter (line 43) and its usage (line 52)

- [ ] **Step 4: Update test fixtures**

In `tests/src/repositories/test_history_repository.py`:
- Remove `media_metadata={"file_name": "history.jpg"}` from test params (line 51)

In `tests/src/repositories/test_media_repository.py`:
- Remove any `requires_interaction` references from test calls

- [ ] **Step 5: Run repository tests**

Run: `pytest tests/src/repositories/ -v --tb=short`
Expected: All PASS

- [ ] **Step 6: Run full test suite to catch cascading failures**

Run: `pytest --tb=short`
Expected: All PASS (fix any cascading failures from removed params)

- [ ] **Step 7: Commit**

```bash
git add src/repositories/ tests/src/repositories/
git commit -m "refactor: remove references to dropped columns from repositories

Remove requires_interaction param from MediaRepository, media_metadata/
error_message/retry_count from HistoryCreateParams, team_name from
UserRepository.create()."
```

---

## Task 4: SQL Aggregation — Replace In-Memory Counting

**Findings addressed:** #1 (in-memory aggregation, 6 code paths)

**Files:**
- Modify: `src/repositories/media_repository.py`
- Modify: `src/repositories/interaction_repository.py`
- Modify: `src/repositories/lock_repository.py`
- Modify: `src/services/core/telegram_commands.py`
- Modify: `src/services/core/dashboard_service.py`
- Modify: `cli/commands/media.py`
- Modify: `tests/src/repositories/test_media_repository.py`
- Modify: `tests/src/repositories/test_interaction_repository.py`

- [ ] **Step 1: Write failing test for MediaRepository.count_active()**

In `tests/src/repositories/test_media_repository.py`, add:

```python
def test_count_active_returns_scalar(self, media_repo, mock_db):
    """Test count_active returns integer count."""
    mock_query = mock_db.query.return_value
    mock_query.with_entities.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.scalar.return_value = 42

    result = media_repo.count_active()

    assert result == 42
```

Run: `pytest tests/src/repositories/test_media_repository.py::TestMediaRepository::test_count_active_returns_scalar -v`
Expected: FAIL (method doesn't exist)

- [ ] **Step 2: Implement MediaRepository.count_active()**

In `src/repositories/media_repository.py`, add `func` to imports from sqlalchemy and add method:

```python
def count_active(self, chat_settings_id: Optional[str] = None) -> int:
    """Count active media items."""
    return (
        self._tenant_query(MediaItem, chat_settings_id)
        .with_entities(func.count(MediaItem.id))
        .filter(MediaItem.is_active.is_(True))
        .scalar()
        or 0
    )
```

Run test: Expected PASS

- [ ] **Step 3: Write failing test for count_by_posting_status()**

```python
def test_count_by_posting_status(self, media_repo, mock_db):
    """Test count_by_posting_status returns dict with counts."""
    mock_query = mock_db.query.return_value
    mock_query.with_entities.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.group_by.return_value = mock_query
    mock_query.all.return_value = [(0, 10), (1, 5), (2, 3)]

    result = media_repo.count_by_posting_status()

    assert result == {"never_posted": 10, "posted_once": 5, "posted_multiple": 3}
```

- [ ] **Step 4: Implement count_by_posting_status()**

```python
def count_by_posting_status(self, chat_settings_id: Optional[str] = None) -> dict:
    """Count active media grouped by posting status.

    Returns dict with keys: never_posted, posted_once, posted_multiple.
    """
    from sqlalchemy import case

    query = (
        self._tenant_query(MediaItem, chat_settings_id)
        .with_entities(
            case(
                (MediaItem.times_posted == 0, 0),
                (MediaItem.times_posted == 1, 1),
                else_=2,
            ).label("bucket"),
            func.count(MediaItem.id),
        )
        .filter(MediaItem.is_active.is_(True))
        .group_by("bucket")
    )
    rows = query.all()
    buckets = {row[0]: row[1] for row in rows}
    return {
        "never_posted": buckets.get(0, 0),
        "posted_once": buckets.get(1, 0),
        "posted_multiple": buckets.get(2, 0),
    }
```

- [ ] **Step 5: Write failing test for count_by_category()**

```python
def test_count_by_category(self, media_repo, mock_db):
    """Test count_by_category returns dict of category: count."""
    mock_query = mock_db.query.return_value
    mock_query.with_entities.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.group_by.return_value = mock_query
    mock_query.all.return_value = [("memes", 10), ("merch", 5), (None, 2)]

    result = media_repo.count_by_category()

    assert result == {"memes": 10, "merch": 5, "uncategorized": 2}
```

- [ ] **Step 6: Implement count_by_category()**

```python
def count_by_category(self, chat_settings_id: Optional[str] = None) -> dict:
    """Count active media grouped by category.

    Returns dict of category_name: count. NULL categories are keyed as 'uncategorized'.
    """
    rows = (
        self._tenant_query(MediaItem, chat_settings_id)
        .with_entities(MediaItem.category, func.count(MediaItem.id))
        .filter(MediaItem.is_active.is_(True))
        .group_by(MediaItem.category)
        .all()
    )
    return {(cat or "uncategorized"): count for cat, count in rows}
```

- [ ] **Step 7: Write failing test for LockRepository.count_permanent_locks()**

In `tests/src/repositories/test_lock_repository.py`:

```python
def test_count_permanent_locks(self, lock_repo, mock_db):
    """Test count_permanent_locks returns integer."""
    mock_query = mock_db.query.return_value
    mock_query.with_entities.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.scalar.return_value = 3

    result = lock_repo.count_permanent_locks()

    assert result == 3
```

- [ ] **Step 8: Implement LockRepository.count_permanent_locks()**

In `src/repositories/lock_repository.py`, add `func` import and method:

```python
from sqlalchemy import func

def count_permanent_locks(self, chat_settings_id: Optional[str] = None) -> int:
    """Count permanent locks (locked_until IS NULL)."""
    return (
        self._tenant_query(MediaPostingLock, chat_settings_id)
        .with_entities(func.count(MediaPostingLock.id))
        .filter(MediaPostingLock.locked_until.is_(None))
        .scalar()
        or 0
    )
```

- [ ] **Step 9: Rewrite InteractionRepository aggregation methods with SQL**

In `src/repositories/interaction_repository.py`, rewrite `get_user_stats()`:

```python
def get_user_stats(self, user_id: str, days: int = 30) -> dict:
    """Get aggregated stats for a user using SQL."""
    from sqlalchemy import func, case

    since = datetime.utcnow() - timedelta(days=days)

    row = (
        self.db.query(
            func.count(UserInteraction.id).label("total"),
            func.count(case((UserInteraction.interaction_name == "posted", 1))).label("posted"),
            func.count(case((UserInteraction.interaction_name == "skip", 1))).label("skipped"),
            func.count(case((UserInteraction.interaction_name == "confirm_reject", 1))).label("rejected"),
        )
        .filter(
            UserInteraction.user_id == user_id,
            UserInteraction.created_at >= since,
        )
        .first()
    )

    # Command breakdown still needs GROUP BY
    cmd_rows = (
        self.db.query(
            UserInteraction.interaction_name,
            func.count(UserInteraction.id),
        )
        .filter(
            UserInteraction.user_id == user_id,
            UserInteraction.interaction_type == "command",
            UserInteraction.created_at >= since,
        )
        .group_by(UserInteraction.interaction_name)
        .all()
    )

    return {
        "total_interactions": row.total or 0,
        "posts_marked": row.posted or 0,
        "posts_skipped": row.skipped or 0,
        "posts_rejected": row.rejected or 0,
        "commands_used": {name: count for name, count in cmd_rows},
    }
```

Rewrite `get_team_activity()`:

```python
def get_team_activity(self, days: int = 30) -> dict:
    """Get team-wide activity stats using SQL."""
    from sqlalchemy import func

    since = datetime.utcnow() - timedelta(days=days)
    base_filter = UserInteraction.created_at >= since

    total = (
        self.db.query(func.count(UserInteraction.id))
        .filter(base_filter)
        .scalar() or 0
    )

    active_users = (
        self.db.query(func.count(func.distinct(UserInteraction.user_id)))
        .filter(base_filter)
        .scalar() or 0
    )

    by_type = dict(
        self.db.query(
            UserInteraction.interaction_type,
            func.count(UserInteraction.id),
        )
        .filter(base_filter)
        .group_by(UserInteraction.interaction_type)
        .all()
    )

    by_name = dict(
        self.db.query(
            UserInteraction.interaction_name,
            func.count(UserInteraction.id),
        )
        .filter(base_filter)
        .group_by(UserInteraction.interaction_name)
        .all()
    )

    return {
        "total_interactions": total,
        "active_users": active_users,
        "interactions_by_type": by_type,
        "interactions_by_name": by_name,
    }
```

Rewrite `get_content_decisions()`:

```python
def get_content_decisions(self, days: int = 30) -> dict:
    """Get content decision breakdown using SQL."""
    from sqlalchemy import func, case

    since = datetime.utcnow() - timedelta(days=days)

    row = (
        self.db.query(
            func.count(UserInteraction.id).label("total"),
            func.count(case((UserInteraction.interaction_name == "posted", 1))).label("posted"),
            func.count(case((UserInteraction.interaction_name == "skip", 1))).label("skipped"),
            func.count(case((UserInteraction.interaction_name == "confirm_reject", 1))).label("rejected"),
        )
        .filter(
            UserInteraction.interaction_type == "callback",
            UserInteraction.interaction_name.in_(["posted", "skip", "confirm_reject"]),
            UserInteraction.created_at >= since,
        )
        .first()
    )

    total = row.total or 0
    posted = row.posted or 0
    skipped = row.skipped or 0
    rejected = row.rejected or 0

    return {
        "total_decisions": total,
        "posted": posted,
        "skipped": skipped,
        "rejected": rejected,
        "posted_percentage": round(posted / total * 100, 1) if total > 0 else 0,
        "skip_percentage": round(skipped / total * 100, 1) if total > 0 else 0,
        "rejection_rate": round(rejected / total * 100, 1) if total > 0 else 0,
    }
```

- [ ] **Step 10: Update /status handler to use SQL counts**

In `src/services/core/telegram_commands.py`, replace lines 108-112:

```python
# Before (loads all media into memory):
all_media = self.service.media_repo.get_all(is_active=True)
media_count = len(all_media)
never_posted = len([m for m in all_media if m.times_posted == 0])
posted_once = len([m for m in all_media if m.times_posted == 1])
posted_multiple = len([m for m in all_media if m.times_posted > 1])
locked_count = len(self.service.lock_repo.get_permanent_locks())
```

With:

```python
# After (SQL COUNT queries):
media_count = self.service.media_repo.count_active()
posting_stats = self.service.media_repo.count_by_posting_status()
never_posted = posting_stats["never_posted"]
posted_once = posting_stats["posted_once"]
posted_multiple = posting_stats["posted_multiple"]
locked_count = self.service.lock_repo.count_permanent_locks()
```

- [ ] **Step 11: Update DashboardService.get_media_stats() to use SQL**

In `src/services/core/dashboard_service.py`, replace `get_media_stats()`:

```python
def get_media_stats(self, telegram_chat_id: int) -> dict:
    """Return media library breakdown by category."""
    chat_settings_id = self._resolve_chat_settings_id(telegram_chat_id)

    total_active = self.media_repo.count_active(chat_settings_id=chat_settings_id)
    category_counts = self.media_repo.count_by_category(chat_settings_id=chat_settings_id)

    categories = [
        {"name": name, "count": count}
        for name, count in sorted(
            category_counts.items(), key=lambda x: x[1], reverse=True
        )
    ]

    return {
        "total_active": total_active,
        "categories": categories,
    }
```

- [ ] **Step 12: Add get_category_counts() to MediaIngestionService**

In `src/services/core/media_ingestion.py`, add a service-layer method (CLI must not access repos directly per CLAUDE.md layer separation):

```python
def get_category_counts(self) -> dict:
    """Return count of active media per category. NULL categories keyed as 'uncategorized'."""
    return self.media_repo.count_by_category()
```

- [ ] **Step 13: Update CLI display_current_mix() and list_categories to use SQL**

In `cli/commands/media.py`, update `display_current_mix()` (line 104):

```python
# Before:
for mix in current_mix:
    count = len(service.list_media(category=mix.category))
```

With:

```python
category_counts = service.get_category_counts()
for mix in current_mix:
    count = category_counts.get(mix.category, 0)
```

Also update the `list_categories` command (line 295):

```python
# Before:
for cat in sorted(categories):
    count = len(service.list_media(category=cat))
```

With:

```python
category_counts = service.get_category_counts()
for cat in sorted(categories):
    count = category_counts.get(cat, 0)
```

- [ ] **Step 14: Run full test suite**

Run: `pytest --tb=short`
Expected: All PASS

- [ ] **Step 15: Commit**

```bash
git add src/repositories/ src/services/ cli/ tests/
git commit -m "perf: replace in-memory aggregation with SQL COUNT/GROUP BY

Add count_active(), count_by_posting_status(), count_by_category() to
MediaRepository. Add count_permanent_locks() to LockRepository. Rewrite
InteractionRepository aggregation methods with SQL. Add get_category_counts()
to MediaIngestionService. Update /status, DashboardService.get_media_stats(),
and CLI display_current_mix()/list_categories to use SQL counts instead of
loading all rows into Python."
```

---

## Task 5: N+1 Query Fixes — DashboardService

**Findings addressed:** #10 (DashboardService N+1), #17 (no ORM relationships)

**Files:**
- Modify: `src/repositories/queue_repository.py`
- Modify: `src/repositories/history_repository.py`
- Modify: `src/services/core/dashboard_service.py`
- Create: `tests/src/services/test_dashboard_service.py`

- [ ] **Step 1: Write failing test for QueueRepository.get_all_with_media()**

In `tests/src/repositories/test_queue_repository.py`, add:

```python
def test_get_all_with_media_returns_tuples(self, queue_repo, mock_db):
    """Test get_all_with_media joins queue items with media info."""
    mock_query = mock_db.query.return_value
    mock_query.outerjoin.return_value = mock_query
    mock_query.add_columns.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.all.return_value = []

    result = queue_repo.get_all_with_media(status="pending")

    assert result == []
    mock_query.outerjoin.assert_called_once()
```

- [ ] **Step 2: Implement QueueRepository.get_all_with_media()**

```python
def get_all_with_media(
    self,
    status: Optional[str] = None,
    chat_settings_id: Optional[str] = None,
) -> List[tuple]:
    """Get queue items with joined media info (file_name, category).

    Returns list of (PostingQueue, file_name, category) tuples.
    Avoids N+1 by using a single JOIN query.
    """
    from src.models.media_item import MediaItem

    query = (
        self._tenant_query(PostingQueue, chat_settings_id)
        .outerjoin(MediaItem, PostingQueue.media_item_id == MediaItem.id)
        .add_columns(MediaItem.file_name, MediaItem.category)
    )

    if status:
        query = query.filter(PostingQueue.status == status)

    return query.order_by(PostingQueue.scheduled_for.asc()).all()
```

- [ ] **Step 3: Implement HistoryRepository.get_all_with_media()**

```python
def get_all_with_media(
    self,
    limit: Optional[int] = None,
    chat_settings_id: Optional[str] = None,
) -> List[tuple]:
    """Get history items with joined media info (file_name, category).

    Returns list of (PostingHistory, file_name, category) tuples.
    """
    from src.models.media_item import MediaItem

    query = (
        self._tenant_query(PostingHistory, chat_settings_id)
        .outerjoin(MediaItem, PostingHistory.media_item_id == MediaItem.id)
        .add_columns(MediaItem.file_name, MediaItem.category)
        .order_by(PostingHistory.posted_at.desc())
    )

    if limit:
        query = query.limit(limit)

    return query.all()
```

- [ ] **Step 4: Update DashboardService to use JOIN methods**

Replace `get_queue_detail()`:

```python
def get_queue_detail(self, telegram_chat_id: int, limit: int = 10) -> dict:
    chat_settings_id = self._resolve_chat_settings_id(telegram_chat_id)

    pending = self.queue_repo.get_all_with_media(
        status="pending", chat_settings_id=chat_settings_id
    )
    processing = self.queue_repo.get_all_with_media(
        status="processing", chat_settings_id=chat_settings_id
    )
    all_in_flight = pending + processing

    items = [
        {
            "scheduled_for": item.scheduled_for.isoformat(),
            "media_name": file_name or "Unknown",
            "category": (category or "uncategorized"),
            "status": item.status,
        }
        for item, file_name, category in all_in_flight[:limit]
    ]

    today_posts = self.history_repo.get_recent_posts(
        hours=24, chat_settings_id=chat_settings_id
    )
    posts_today = len(today_posts)

    last_post_at = None
    if today_posts:
        last_post_at = today_posts[0].posted_at.isoformat()
    else:
        recent = self.history_repo.get_recent_posts(
            hours=720, chat_settings_id=chat_settings_id
        )
        if recent:
            last_post_at = recent[0].posted_at.isoformat()

    return {
        "items": items,
        "total_in_flight": len(all_in_flight),
        "posts_today": posts_today,
        "last_post_at": last_post_at,
    }
```

Replace `get_history_detail()`:

```python
def get_history_detail(self, telegram_chat_id: int, limit: int = 10) -> dict:
    chat_settings_id = self._resolve_chat_settings_id(telegram_chat_id)

    rows = self.history_repo.get_all_with_media(
        limit=limit, chat_settings_id=chat_settings_id
    )

    items = [
        {
            "posted_at": item.posted_at.isoformat(),
            "media_name": file_name or "Unknown",
            "category": (category or "uncategorized"),
            "status": item.status,
            "posting_method": item.posting_method,
        }
        for item, file_name, category in rows
    ]

    return {"items": items}
```

Replace `get_pending_queue_items()`:

```python
def get_pending_queue_items(self, chat_settings_id: Optional[str] = None) -> list:
    rows = self.queue_repo.get_all_with_media(
        status="pending", chat_settings_id=chat_settings_id
    )

    return [
        {
            "scheduled_for": item.scheduled_for,
            "file_name": file_name or "Unknown",
            "category": (category or "-"),
            "status": item.status,
        }
        for item, file_name, category in rows
    ]
```

- [ ] **Step 5: Run full test suite**

Run: `pytest --tb=short`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/repositories/ src/services/ tests/
git commit -m "perf: fix N+1 queries in DashboardService with JOIN methods

Add get_all_with_media() to QueueRepository and HistoryRepository that
join queue/history items with media info in a single SQL query. Update
all three DashboardService methods to use JOINs instead of per-item
media_repo.get_by_id() lookups."
```

---

## Task 6: Transaction Atomicity Fix

**Findings addressed:** #3 (non-atomic callback writes)

**Files:**
- Modify: `src/services/core/telegram_callbacks.py`

The core issue: `_shared_session()` shares one session but each repo method calls `self.db.commit()` internally, so writes commit incrementally. Fix: suppress auto-commit during shared session ops, commit once at end.

- [ ] **Step 1: Update _shared_session to use autoflush-only mode**

Replace `_shared_session()` with a version that defers commits:

```python
@contextmanager
def _shared_session(self):
    """Share one DB session with deferred commit for atomic operations.

    Individual repo methods call commit(), but within this context
    manager we replace commit() with flush() so changes accumulate
    without being committed. A single commit at the end makes the
    entire operation atomic.
    """
    repos = [
        self.service.history_repo,
        self.service.media_repo,
        self.service.queue_repo,
        self.service.user_repo,
        self.service.lock_service.lock_repo,
    ]
    primary_session = self.service.history_repo.db
    originals = {}

    # Swap sessions
    for repo in repos:
        originals[id(repo)] = repo._db
        repo.use_session(primary_session)

    # Monkey-patch commit to flush instead (defers actual commit)
    original_commit = primary_session.commit
    primary_session.commit = primary_session.flush

    try:
        yield
        # All ops succeeded — do the real commit
        original_commit()
    except Exception:
        primary_session.rollback()
        raise
    finally:
        # Restore commit and sessions
        primary_session.commit = original_commit
        for repo in repos:
            if id(repo) in originals:
                repo.use_session(originals[id(repo)])
```

- [ ] **Step 2: Run callback tests**

Run: `pytest tests/src/services/test_telegram_callbacks.py -v --tb=short`
Expected: All PASS

- [ ] **Step 3: Run full test suite**

Run: `pytest --tb=short`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/services/core/telegram_callbacks.py
git commit -m "fix: make callback DB operations atomic with deferred commit

Replace incremental commits in _shared_session with flush-then-commit
pattern. Individual repo methods now flush (not commit) within the shared
session, and a single commit at the end makes the entire callback operation
atomic. Prevents partial writes on crash."
```

---

## Task 7: Standardize end_read_transaction()

**Findings addressed:** #9 (inconsistent cleanup)

**Files:**
- Modify: `src/repositories/history_repository.py`
- Modify: `src/repositories/interaction_repository.py`
- Modify: `src/repositories/lock_repository.py`
- Modify: `src/repositories/queue_repository.py`
- Modify: `src/repositories/user_repository.py`
- Modify: `src/repositories/category_mix_repository.py`
- Modify: `src/repositories/service_run_repository.py`
- Modify: `src/repositories/media_repository.py`

Strategy: Add `self.end_read_transaction()` after all read-only methods (those that don't call `self.db.commit()`). The repos that already have this pattern (ChatSettingsRepository, TokenRepository, InstagramAccountRepository) serve as the template.

- [ ] **Step 1: Add end_read_transaction to HistoryRepository read methods**

Add `self.end_read_transaction()` after each `.all()` or `.first()` or `.scalar()` call in:
- `get_by_id()` — after `.first()`
- `get_all()` — after `.all()`
- `get_by_media_id()` — after `.all()`
- `get_recent_posts()` — after `.all()`
- `count_by_method()` — after `.scalar()`
- `get_by_queue_item_id()` — after `.first()`

Pattern (for each method):
```python
result = query.first()  # or .all() or .scalar()
self.end_read_transaction()
return result
```

- [ ] **Step 2: Add end_read_transaction to QueueRepository read methods**

Methods: `get_by_id()`, `get_by_id_prefix()`, `get_by_media_id()`, `get_all()`, `count_pending()`, `get_oldest_pending()`, `get_all_with_media()`

Note: Do NOT add to `get_pending()` or `claim_for_processing()` — these use `FOR UPDATE` locks and are part of write transactions.

- [ ] **Step 3: Add end_read_transaction to remaining repositories**

- `InteractionRepository`: `get_recent()`, `get_user_stats()`, `get_team_activity()`, `get_content_decisions()`
- `LockRepository`: `get_by_id()`, `get_active_lock()`, `is_locked()`, `get_all_active()`, `get_permanent_locks()`, `count_permanent_locks()`
- `UserRepository`: `get_by_id()`, `get_by_telegram_id()`, `get_all()`
- `CategoryMixRepository`: `get_current_mix()`, `get_current_mix_as_dict()`, `get_history()`, `has_current_mix()`, `get_categories_without_ratio()`
- `ServiceRunRepository`: `get_by_id()`, `get_recent_runs()`, `get_failed_runs()`
- `MediaRepository`: `get_by_id()`, `get_by_path()`, `get_by_hash()`, `get_by_instagram_media_id()`, `get_by_source_identifier()`, `get_active_by_source_type()`, `get_inactive_by_source_identifier()`, `get_all()`, `get_categories()`, `get_duplicates()`, `get_next_eligible_for_posting()`, `count_active()`, `count_by_posting_status()`, `count_by_category()`, `get_all_with_media()` (if added)

Note: `get_backfilled_instagram_media_ids()` already has it.

- [ ] **Step 4: Run full test suite**

Run: `pytest --tb=short`
Expected: All PASS (mock tests unaffected since end_read_transaction is a no-op on mocks)

- [ ] **Step 5: Commit**

```bash
git add src/repositories/
git commit -m "fix: standardize end_read_transaction across all repositories

Add end_read_transaction() after all read-only query methods to
prevent 'idle in transaction' connections from accumulating between
the 30s cleanup cycles. Follows the pattern already established in
ChatSettingsRepository, TokenRepository, and InstagramAccountRepository."
```

---

## Task 8: SQL Migration for Production

**Findings addressed:** All schema changes from Tasks 1-2

**Files:**
- Create: `scripts/migrations/020_data_model_cleanup.sql`

- [ ] **Step 1: Write the migration**

```sql
-- Migration 020: Data Model Cleanup
-- Drops vestigial columns, adds missing constraints, fixes types
-- From: Data Model Audit 2026-03-25

BEGIN;

-- =================================================================
-- 1. Drop vestigial columns from posting_queue
-- =================================================================
ALTER TABLE posting_queue DROP COLUMN IF EXISTS web_hosted_url;
ALTER TABLE posting_queue DROP COLUMN IF EXISTS web_hosted_public_id;
ALTER TABLE posting_queue DROP COLUMN IF EXISTS retry_count;
ALTER TABLE posting_queue DROP COLUMN IF EXISTS max_retries;
ALTER TABLE posting_queue DROP COLUMN IF EXISTS next_retry_at;
ALTER TABLE posting_queue DROP COLUMN IF EXISTS last_error;

-- Update CHECK constraint to remove 'retrying'
ALTER TABLE posting_queue DROP CONSTRAINT IF EXISTS check_status;
ALTER TABLE posting_queue ADD CONSTRAINT check_status
    CHECK (status IN ('pending', 'processing'));

-- =================================================================
-- 2. Drop write-only columns from posting_history
-- =================================================================
ALTER TABLE posting_history DROP COLUMN IF EXISTS media_metadata;
ALTER TABLE posting_history DROP COLUMN IF EXISTS error_message;
ALTER TABLE posting_history DROP COLUMN IF EXISTS retry_count;

-- =================================================================
-- 3. Drop requires_interaction from media_items
-- =================================================================
DROP INDEX IF EXISTS idx_media_items_requires_interaction;
ALTER TABLE media_items DROP COLUMN IF EXISTS requires_interaction;

-- =================================================================
-- 4. Drop unused columns from users
-- =================================================================
ALTER TABLE users DROP COLUMN IF EXISTS team_name;
ALTER TABLE users DROP COLUMN IF EXISTS first_seen_at;

-- Add role CHECK constraint
ALTER TABLE users DROP CONSTRAINT IF EXISTS check_user_role;
ALTER TABLE users ADD CONSTRAINT check_user_role
    CHECK (role IN ('admin', 'member'));

-- =================================================================
-- 5. Drop chat_name from chat_settings
-- =================================================================
ALTER TABLE chat_settings DROP COLUMN IF EXISTS chat_name;

-- =================================================================
-- 6. Add lock_reason CHECK constraint
-- =================================================================
ALTER TABLE media_posting_locks DROP CONSTRAINT IF EXISTS check_lock_reason;
ALTER TABLE media_posting_locks ADD CONSTRAINT check_lock_reason
    CHECK (lock_reason IN ('recent_post', 'skip', 'manual_hold', 'seasonal', 'permanent_reject'));

-- =================================================================
-- 7. Record migration
-- =================================================================
INSERT INTO schema_version (version, description, applied_at)
VALUES (20, 'Data model cleanup: drop vestigial columns, add constraints', NOW());

COMMIT;
```

- [ ] **Step 2: Commit migration**

```bash
git add scripts/migrations/020_data_model_cleanup.sql
git commit -m "db: add migration 020 for data model cleanup

Drops vestigial columns (posting_queue retry/web_hosted, posting_history
metadata/error/retry, media_items requires_interaction, users team_name/
first_seen_at, chat_settings chat_name). Adds CHECK constraints for
lock_reason and user role. Updates posting_queue status CHECK."
```

---

## Task 9: Update CHANGELOG.md

- [ ] **Step 1: Add changelog entries under [Unreleased]**

Add entries covering all changes:

```markdown
### Changed
- **SQL Aggregation** — `/status`, dashboard stats, and interaction analytics now use SQL `COUNT`/`GROUP BY` instead of loading all rows into Python memory
- **Dashboard N+1 Fix** — Queue and history detail endpoints now use JOIN queries instead of per-item media lookups
- **Transaction Atomicity** — Telegram callback DB operations now commit atomically (single commit) instead of incrementally
- **Connection Cleanup** — All repository read methods now call `end_read_transaction()` to prevent idle-in-transaction connections

### Removed
- **posting_queue** — Dropped vestigial columns: `web_hosted_url`, `web_hosted_public_id`, `retry_count`, `max_retries`, `next_retry_at`, `last_error`; removed `retrying` from status CHECK
- **posting_history** — Dropped unused columns: `media_metadata`, `error_message`, `retry_count`
- **media_items** — Dropped unimplemented `requires_interaction` column and its index
- **users** — Dropped unused `team_name` and `first_seen_at` columns
- **chat_settings** — Dropped unused `chat_name` column

### Fixed
- **Model Drift** — `init_db()` now imports all 11 models (was missing 5)
- **Model Drift** — Added CHECK constraints to ORM models matching existing DB constraints (chat_settings ranges, lock_reason, user role)
- **DateTime Mismatch** — `chat_settings.last_post_sent_at` ORM now declares `DateTime(timezone=True)` matching the `TIMESTAMPTZ` DB column
```

- [ ] **Step 2: Commit changelog**

```bash
git add CHANGELOG.md
git commit -m "docs: update CHANGELOG for data model remediation"
```

---

## Task 10: Final Verification

- [ ] **Step 1: Run lint**

```bash
source venv/bin/activate && ruff check src/ tests/ cli/ && ruff format --check src/ tests/ cli/
```

- [ ] **Step 2: Run full test suite**

```bash
pytest --tb=short
```

- [ ] **Step 3: Verify no remaining references to dropped columns**

```bash
# Should return zero hits in src/ (excluding migration files)
grep -rn "requires_interaction\|web_hosted_url\|web_hosted_public_id\|media_metadata\|\.retry_count\|\.max_retries\|\.next_retry_at\|\.last_error\|\.team_name\|\.first_seen_at\|\.chat_name" src/ cli/ --include="*.py" | grep -v "migration"
```

- [ ] **Step 4: Fix any issues found, then final commit if needed**

---

## Verification

1. `ruff check src/ tests/ cli/` — zero errors
2. `ruff format --check src/ tests/ cli/` — all formatted
3. `pytest` — all tests pass
4. `grep` for dropped column names — zero references in `src/` and `cli/`
5. Migration SQL is syntactically valid and idempotent (`IF EXISTS`)
