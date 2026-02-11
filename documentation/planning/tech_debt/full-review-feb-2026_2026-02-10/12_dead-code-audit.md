# Audit and Remove Dead Code

**Status**: ✅ COMPLETE
**Started**: 2026-02-10
**Completed**: 2026-02-10

| Field | Value |
|---|---|
| **PR Title** | `refactor: remove confirmed dead code from repository layer` |
| **Risk Level** | Low |
| **Effort** | Small (2-3 hours) |
| **Dependencies** | Phase 08, Phase 09 (tests must be in place to verify removal is safe) |
| **Blocks** | None |
| **Files Modified** | `src/repositories/interaction_repository.py`, `src/repositories/history_repository.py`, `src/repositories/service_run_repository.py`, `src/repositories/queue_repository.py`, `src/repositories/token_repository.py`, `src/repositories/media_repository.py`, `src/repositories/category_mix_repository.py` |

---

## Problem Description

Multiple repository methods are defined but never called from any production code (`src/` or `cli/`). Some are referenced only in test files (which test the method itself, not any caller). Dead code increases maintenance burden -- developers must read and understand methods that serve no purpose, and changes to shared infrastructure must account for methods nobody uses.

This phase audits every candidate method, confirms whether it is truly unused, and removes confirmed dead code. For methods that are unused today but may be needed for planned features (Phase 3+), we add an annotation comment instead of removing them.

**Important**: The audit found that several originally-suspected methods are actually used from CLI commands. Those are marked as "KEEP" below. Only confirmed-unused methods should be removed.

---

## Pre-Audit Results

Before implementing, the following `grep` searches were run against the entire codebase (`src/`, `cli/`, `tests/`) to determine usage. "Production usage" means the method is called from `src/` or `cli/` (not just from test files that test the method itself).

### `src/repositories/category_mix_repository.py`

| Method | Production Usage | Test-Only Usage | Verdict |
|---|---|---|---|
| `get_categories_without_ratio()` | `cli/commands/media.py:167` | `test_category_mix_repository.py` | **KEEP** -- used in CLI |
| `get_category_ratio()` | None | `test_category_mix_repository.py` | **REMOVE** |
| `get_history()` | `cli/commands/media.py:321` | None | **KEEP** -- used in CLI |
| `get_mix_at_date()` | None | None | **REMOVE** |
| `has_current_mix()` | `cli/commands/media.py:163` | `test_category_mix_repository.py` | **KEEP** -- used in CLI |
| `set_mix()` | `cli/commands/media.py:190,230` | `test_category_mix_repository.py` | **KEEP** -- used in CLI |

### `src/repositories/interaction_repository.py`

| Method | Production Usage | Test-Only Usage | Verdict |
|---|---|---|---|
| `count_by_name()` | None | `test_interaction_repository.py` | **REMOVE** |
| `count_by_user()` | None | `test_interaction_repository.py` | **REMOVE** |
| `get_by_name()` | None | `test_interaction_repository.py` | **REMOVE** |
| `get_by_type()` | None | `test_interaction_repository.py` | **REMOVE** |
| `get_by_user()` | None | `test_interaction_repository.py` | **REMOVE** |

### `src/repositories/history_repository.py`

| Method | Production Usage | Test-Only Usage | Verdict |
|---|---|---|---|
| `get_by_user_id()` | None | `test_history_repository.py` | **REMOVE** |
| `get_stats()` | None | `test_history_repository.py` | **REMOVE** |

### `src/repositories/service_run_repository.py`

| Method | Production Usage | Test-Only Usage | Verdict |
|---|---|---|---|
| `get_failed_runs()` | None | `test_service_run_repository.py` | **ANNOTATE** -- likely needed for Phase 3 monitoring |
| `get_recent_runs()` | None (in `src/` or `cli/`) | `test_base_service.py` (integration test) | **ANNOTATE** -- likely needed for Phase 3 monitoring |

### `src/repositories/queue_repository.py`

| Method | Production Usage | Test-Only Usage | Verdict |
|---|---|---|---|
| `delete_all_pending()` | `cli/commands/queue.py:174` | None | **KEEP** -- used in CLI |
| `schedule_retry()` | None | `test_queue_repository.py` | **ANNOTATE** -- planned for retry system |

### `src/repositories/token_repository.py`

| Method | Production Usage | Test-Only Usage | Verdict |
|---|---|---|---|
| `delete_all_for_service()` | None | None | **REMOVE** |
| `delete_token()` | None | None | **REMOVE** |
| `get_all_for_service()` | None | None | **REMOVE** |
| `get_expired_tokens()` | None | None | **REMOVE** |

### `src/repositories/media_repository.py`

| Method | Production Usage | Test-Only Usage | Verdict |
|---|---|---|---|
| `get_categories()` | `cli/commands/media.py:156,210,288` | None | **KEEP** -- used in CLI |
| `update_metadata()` | None | None | **ANNOTATE** -- likely needed for future media editing UI |

---

## Step-by-Step Implementation

### Step 0: Verify Each Candidate Before Removal

Before removing any method, the implementer MUST run the verification command for that specific method. Do not trust this document blindly -- the codebase may have changed since this audit.

**Verification command template:**

```bash
# Replace METHOD_NAME with the actual method name
grep -rn "METHOD_NAME" src/ cli/ tests/
```

If the grep finds usage in `src/` or `cli/` (not just `tests/`), **do NOT remove the method**.

---

### Step 1: Remove Dead Code from `src/repositories/category_mix_repository.py`

**Verify before removal:**

```bash
grep -rn "get_category_ratio" src/ cli/
grep -rn "get_mix_at_date" src/ cli/
```

Expected: No results from `src/` or `cli/`.

**Before** (lines 32-67):

```python
    def get_category_ratio(self, category: str) -> Optional[Decimal]:
        """Get current ratio for a specific category."""
        mix = (
            self.db.query(CategoryPostCaseMix)
            .filter(
                CategoryPostCaseMix.category == category,
                CategoryPostCaseMix.is_current,
            )
            .first()
        )
        return mix.ratio if mix else None

    def get_history(self, category: Optional[str] = None) -> List[CategoryPostCaseMix]:
        """Get full history, optionally filtered by category."""
        query = self.db.query(CategoryPostCaseMix)

        if category:
            query = query.filter(CategoryPostCaseMix.category == category)

        return query.order_by(
            CategoryPostCaseMix.category,
            CategoryPostCaseMix.effective_from.desc(),
        ).all()

    def get_mix_at_date(self, target_date: datetime) -> List[CategoryPostCaseMix]:
        """Get the mix that was active at a specific date (for historical analysis)."""
        return (
            self.db.query(CategoryPostCaseMix)
            .filter(
                CategoryPostCaseMix.effective_from <= target_date,
                (CategoryPostCaseMix.effective_to.is_(None))
                | (CategoryPostCaseMix.effective_to > target_date),
            )
            .order_by(CategoryPostCaseMix.category)
            .all()
        )
```

**After** (remove `get_category_ratio` and `get_mix_at_date` only -- keep `get_history` which is used in CLI):

```python
    def get_history(self, category: Optional[str] = None) -> List[CategoryPostCaseMix]:
        """Get full history, optionally filtered by category."""
        query = self.db.query(CategoryPostCaseMix)

        if category:
            query = query.filter(CategoryPostCaseMix.category == category)

        return query.order_by(
            CategoryPostCaseMix.category,
            CategoryPostCaseMix.effective_from.desc(),
        ).all()
```

Also remove the test methods that tested the removed methods from `tests/src/repositories/test_category_mix_repository.py`:

- Remove `test_get_category_ratio` (lines 167-174)
- Remove `test_get_category_ratio_not_found` (lines 176-182)

---

### Step 2: Remove Dead Code from `src/repositories/interaction_repository.py`

**Verify before removal:**

```bash
grep -rn "\.count_by_name\(" src/ cli/
grep -rn "\.count_by_user\(" src/ cli/
grep -rn "\.get_by_name\(" src/ cli/
grep -rn "\.get_by_type\(" src/ cli/
grep -rn "\.get_by_user\(" src/ cli/
```

Expected: No results from `src/` or `cli/`.

**Before** (lines 48-139 -- five methods):

```python
    def get_by_user(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[UserInteraction]:
        """Get interactions for a specific user."""
        return (
            self.db.query(UserInteraction)
            .filter(UserInteraction.user_id == user_id)
            .order_by(UserInteraction.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_by_type(
        self,
        interaction_type: str,
        days: int = 30,
        limit: int = 1000,
    ) -> List[UserInteraction]:
        """Get interactions by type within date range."""
        since = datetime.utcnow() - timedelta(days=days)
        return (
            self.db.query(UserInteraction)
            .filter(
                UserInteraction.interaction_type == interaction_type,
                UserInteraction.created_at >= since,
            )
            .order_by(UserInteraction.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_by_name(
        self,
        interaction_name: str,
        days: int = 30,
        limit: int = 1000,
    ) -> List[UserInteraction]:
        """Get interactions by name within date range."""
        since = datetime.utcnow() - timedelta(days=days)
        return (
            self.db.query(UserInteraction)
            .filter(
                UserInteraction.interaction_name == interaction_name,
                UserInteraction.created_at >= since,
            )
            .order_by(UserInteraction.created_at.desc())
            .limit(limit)
            .all()
        )

    ...

    def count_by_user(self, user_id: str, days: int = 30) -> int:
        """Count interactions for a user within date range."""
        since = datetime.utcnow() - timedelta(days=days)
        return (
            self.db.query(func.count(UserInteraction.id))
            .filter(
                UserInteraction.user_id == user_id,
                UserInteraction.created_at >= since,
            )
            .scalar()
        )

    def count_by_name(self, interaction_name: str, days: int = 30) -> int:
        """Count interactions by name within date range."""
        since = datetime.utcnow() - timedelta(days=days)
        return (
            self.db.query(func.count(UserInteraction.id))
            .filter(
                UserInteraction.interaction_name == interaction_name,
                UserInteraction.created_at >= since,
            )
            .scalar()
        )
```

**After**: Remove all five methods. The file should retain: `create()`, `get_by_id()`, `get_recent()`, `get_user_stats()`, `get_team_activity()`, `get_content_decisions()`, and `get_bot_responses_by_chat()`.

Also remove corresponding tests from `tests/src/repositories/test_interaction_repository.py` that tested these methods.

---

### Step 3: Remove Dead Code from `src/repositories/history_repository.py`

**Verify before removal:**

```bash
grep -rn "history_repo\.get_by_user_id\|history_repo\.get_stats\|\.get_stats(" src/ cli/
```

Expected: No results from `src/` or `cli/`.

**Remove these two methods:**

`get_by_user_id()` (lines 63-76):

```python
    def get_by_user_id(
        self, user_id: str, limit: Optional[int] = None
    ) -> List[PostingHistory]:
        """Get all history records for a specific user."""
        query = (
            self.db.query(PostingHistory)
            .filter(PostingHistory.posted_by_user_id == user_id)
            .order_by(PostingHistory.posted_at.desc())
        )

        if limit:
            query = query.limit(limit)

        return query.all()
```

`get_stats()` (lines 123-150):

```python
    def get_stats(self, days: Optional[int] = 30) -> dict:
        """Get posting statistics."""
        since = datetime.utcnow() - timedelta(days=days) if days else datetime.min

        total = (
            self.db.query(func.count(PostingHistory.id))
            .filter(PostingHistory.posted_at >= since)
            .scalar()
        )

        successful = (
            self.db.query(func.count(PostingHistory.id))
            .filter(and_(PostingHistory.posted_at >= since, PostingHistory.success))
            .scalar()
        )

        failed = (
            self.db.query(func.count(PostingHistory.id))
            .filter(and_(PostingHistory.posted_at >= since, ~PostingHistory.success))
            .scalar()
        )

        return {
            "total": total or 0,
            "successful": successful or 0,
            "failed": failed or 0,
            "success_rate": (successful / total * 100) if total > 0 else 0,
        }
```

Also remove corresponding skipped tests from `tests/src/repositories/test_history_repository.py`.

After removal, check if the `and_` import from `sqlalchemy` is still needed (it is used by `count_by_method()`, so keep it).

---

### Step 4: Annotate Methods in `src/repositories/service_run_repository.py`

**Verify before removal:**

```bash
grep -rn "get_failed_runs\|get_recent_runs" src/ cli/
```

Expected: `get_recent_runs` is called from `tests/src/services/test_base_service.py` (integration tests that verify the `BaseService.track_execution()` mechanism). These methods are likely needed for Phase 3 monitoring dashboards.

**Do NOT remove these methods.** Instead, annotate them:

**Before** (line 87):

```python
    def get_recent_runs(
```

**After:**

```python
    # NOTE: Unused in production as of 2026-02-10, but used by test_base_service.py
    # integration tests and planned for Phase 3 monitoring dashboard.
    def get_recent_runs(
```

**Before** (line 98):

```python
    def get_failed_runs(
```

**After:**

```python
    # NOTE: Unused in production as of 2026-02-10.
    # Planned for Phase 3 monitoring dashboard and alerting system.
    def get_failed_runs(
```

---

### Step 5: Annotate Method in `src/repositories/queue_repository.py`

**Verify before removal:**

```bash
grep -rn "schedule_retry" src/ cli/
```

Expected: Only defined in `queue_repository.py` and tested in `test_queue_repository.py`.

**Do NOT remove.** Annotate instead:

**Before** (line 133):

```python
    def schedule_retry(
```

**After:**

```python
    # NOTE: Unused in production as of 2026-02-10.
    # Planned for automatic retry system when Instagram API posting fails.
    def schedule_retry(
```

---

### Step 6: Remove Dead Code from `src/repositories/token_repository.py`

**Verify before removal:**

```bash
grep -rn "delete_all_for_service" src/ cli/ tests/
grep -rn "delete_token" src/ cli/ tests/
grep -rn "get_all_for_service" src/ cli/ tests/
grep -rn "get_expired_tokens" src/ cli/ tests/
```

Expected: Only defined in `token_repository.py` -- no callers anywhere (not even in tests).

**Remove these four methods:**

`get_all_for_service()` (lines 101-105):

```python
    def get_all_for_service(self, service_name: str) -> List[ApiToken]:
        """Get all tokens for a service (access and refresh)."""
        return (
            self.db.query(ApiToken).filter(ApiToken.service_name == service_name).all()
        )
```

`get_expired_tokens()` (lines 205-215):

```python
    def get_expired_tokens(self) -> List[ApiToken]:
        """Get all expired tokens."""
        now = datetime.utcnow()
        return (
            self.db.query(ApiToken)
            .filter(
                ApiToken.expires_at.isnot(None),
                ApiToken.expires_at <= now,
            )
            .all()
        )
```

`delete_token()` (lines 217-224):

```python
    def delete_token(self, service_name: str, token_type: str) -> bool:
        """Delete a specific token."""
        token = self.get_token(service_name, token_type)
        if token:
            self.db.delete(token)
            self.db.commit()
            return True
        return False
```

`delete_all_for_service()` (lines 226-234):

```python
    def delete_all_for_service(self, service_name: str) -> int:
        """Delete all tokens for a service. Returns count deleted."""
        count = (
            self.db.query(ApiToken)
            .filter(ApiToken.service_name == service_name)
            .delete()
        )
        self.db.commit()
        return count
```

After removal, the file should retain: `get_token()`, `get_token_for_account()`, `get_all_instagram_tokens()`, `create_or_update()`, `update_last_refreshed()`, and `get_expiring_tokens()`.

---

### Step 7: Annotate Method in `src/repositories/media_repository.py`

**Verify before removal:**

```bash
grep -rn "\.update_metadata\(" src/ cli/ tests/
```

Expected: Only defined in `media_repository.py` -- no callers anywhere.

**Do NOT remove.** This method will be needed when a media editing UI is built (Phase 3). Annotate instead:

**Before** (line 102):

```python
    def update_metadata(
```

**After:**

```python
    # NOTE: Unused in production as of 2026-02-10.
    # Planned for Phase 3 media editing UI (web frontend).
    def update_metadata(
```

---

### Step 8: Clean Up Test Files

After removing production methods, remove the corresponding test methods that tested those methods. Without the source method, the test would fail on import or call.

**Files to update:**

1. `tests/src/repositories/test_category_mix_repository.py`:
   - Remove `test_get_category_ratio` and `test_get_category_ratio_not_found`

2. `tests/src/repositories/test_interaction_repository.py`:
   - Remove tests for `get_by_user`, `get_by_type`, `get_by_name`, `count_by_user`, `count_by_name`

3. `tests/src/repositories/test_history_repository.py`:
   - Remove tests for `get_by_user_id` and `get_stats`

---

## Verification Checklist

After all removals and annotations:

```bash
# 1. Linting passes (no unused imports created)
ruff check src/repositories/

# 2. Formatting is correct
ruff format --check src/repositories/

# 3. All tests pass (no test calls removed production methods that still exist)
pytest tests/src/repositories/ -v

# 4. Full test suite passes
pytest

# 5. Verify no broken imports
python -c "from src.repositories.category_mix_repository import CategoryMixRepository"
python -c "from src.repositories.interaction_repository import InteractionRepository"
python -c "from src.repositories.history_repository import HistoryRepository"
python -c "from src.repositories.service_run_repository import ServiceRunRepository"
python -c "from src.repositories.queue_repository import QueueRepository"
python -c "from src.repositories.token_repository import TokenRepository"
python -c "from src.repositories.media_repository import MediaRepository"

# 6. CLI still works (repositories are used by CLI commands)
storyline-cli list-categories
storyline-cli list-queue
storyline-cli list-media
```

---

## Summary of Changes

| File | Methods Removed | Methods Annotated | Methods Kept |
|---|---|---|---|
| `category_mix_repository.py` | `get_category_ratio`, `get_mix_at_date` | None | `get_current_mix`, `get_current_mix_as_dict`, `get_history`, `set_mix`, `has_current_mix`, `get_categories_without_ratio` |
| `interaction_repository.py` | `get_by_user`, `get_by_type`, `get_by_name`, `count_by_user`, `count_by_name` | None | `create`, `get_by_id`, `get_recent`, `get_user_stats`, `get_team_activity`, `get_content_decisions`, `get_bot_responses_by_chat` |
| `history_repository.py` | `get_by_user_id`, `get_stats` | None | `get_by_id`, `get_all`, `get_by_media_id`, `create`, `get_recent_posts`, `count_by_method` |
| `service_run_repository.py` | None | `get_recent_runs`, `get_failed_runs` | All methods kept |
| `queue_repository.py` | None | `schedule_retry` | All methods kept (including `delete_all_pending` which IS used in CLI) |
| `token_repository.py` | `get_all_for_service`, `get_expired_tokens`, `delete_token`, `delete_all_for_service` | None | `get_token`, `get_token_for_account`, `get_all_instagram_tokens`, `create_or_update`, `update_last_refreshed`, `get_expiring_tokens` |
| `media_repository.py` | None | `update_metadata` | All methods kept (including `get_categories` which IS used in CLI) |

**Total: 13 methods removed, 5 methods annotated, all remaining methods verified as used.**

---

## What NOT To Do

1. **Do NOT remove a method without running the grep verification command first.** The codebase may have changed since this audit was written. Always verify before deleting.

2. **Do NOT remove methods that are used in CLI commands.** Several methods that appear unused from `src/` are actually called from `cli/commands/`. The audit above accounts for this, but always check both `src/` AND `cli/`.

3. **Do NOT remove methods that are planned for future phases.** Methods like `schedule_retry()`, `get_recent_runs()`, `get_failed_runs()`, and `update_metadata()` are unused today but are documented in the project's phase plan. Annotate them with a comment instead.

4. **Do NOT remove the test methods first.** Remove the production method first, then remove the corresponding test. If you remove the test but keep the production method, you have reduced coverage for no reason.

5. **Do NOT batch all removals into a single commit.** Group by file (one commit per repository file) so that `git blame` and `git revert` are clean if a removal turns out to be wrong.

6. **Do NOT remove unused imports automatically.** After removing a method, check whether the imports it used are still needed by other methods in the same file. For example, after removing `get_stats()` from `history_repository.py`, verify that `and_` from `sqlalchemy` is still used by `count_by_method()` before removing the import.

7. **Do NOT confuse "used only in tests" with "used in production."** A method that is only called from test files is dead code in production, but the test file itself should also be cleaned up. Both sides must be handled.
