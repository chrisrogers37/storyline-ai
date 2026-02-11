# Phase 04: Fix Architecture Violation in SchedulerService

**Status**: ✅ COMPLETE
**Started**: 2026-02-10
**Completed**: 2026-02-10
**PR**: #32

| Field | Value |
|-------|-------|
| **PR Title** | `refactor: route scheduler media selection through repository layer` |
| **Risk Level** | Medium |
| **Effort** | Medium (2-3 hours) |
| **Dependencies** | None |
| **Blocks** | Phase 08, Phase 09 |
| **Files Modified** | `src/services/core/scheduler.py`, `src/repositories/media_repository.py` |

---

## Problem Description

The `SchedulerService._select_media_from_pool()` method (lines 406-458 of `src/services/core/scheduler.py`) violates the project's strict separation-of-concerns architecture documented in `CLAUDE.md`. Specifically:

1. **Direct SQLAlchemy imports in a service**: The method imports `and_`, `exists`, `select`, and `func` from `sqlalchemy` at line 416.
2. **Direct model imports in a service**: The method imports three models (`MediaItem`, `PostingQueue`, `MediaPostingLock`) at lines 417-419. Services should never import models directly except for type hints.
3. **Reaches through the repository to access the raw session**: The method accesses `self.media_repo.db` (the repository's internal `Session` object) at line 421 to build a raw SQLAlchemy query.
4. **Multi-table query logic lives in the service layer**: The method constructs subqueries against `PostingQueue` and `MediaPostingLock` tables, which is exclusively the repository layer's responsibility.

This is the only place in the codebase where a service directly constructs SQLAlchemy queries. Every other database interaction correctly goes through repository methods. This violation makes the code harder to test (you cannot mock the query), harder to maintain (query logic is in the wrong layer), and sets a bad precedent for future development.

---

## Step-by-Step Implementation

### Step 1: Add the new method to `MediaRepository`

Open `src/repositories/media_repository.py`. Add the required imports at the top of the file and add the new method at the end of the class.

**BEFORE** (current imports at top of file, lines 1-8):

```python
"""Media item repository - CRUD operations for media items."""

from typing import Optional, List
from datetime import datetime
from sqlalchemy import func

from src.repositories.base_repository import BaseRepository
from src.models.media_item import MediaItem
```

**AFTER** (add new imports):

```python
"""Media item repository - CRUD operations for media items."""

from typing import Optional, List
from datetime import datetime
from sqlalchemy import func, and_, exists, select

from src.repositories.base_repository import BaseRepository
from src.models.media_item import MediaItem
from src.models.posting_queue import PostingQueue
from src.models.media_lock import MediaPostingLock
```

Then add the following method at the end of the `MediaRepository` class, after the existing `get_duplicates()` method (after line 211):

```python
    def get_next_eligible_for_posting(
        self, category: Optional[str] = None
    ) -> Optional[MediaItem]:
        """
        Get the next eligible media item for posting.

        Filters out inactive, locked, and already-queued items.
        Prioritizes never-posted items, then least-posted, with random tie-breaking.

        Args:
            category: Filter by category, or None for all categories

        Returns:
            The highest-priority eligible MediaItem, or None if no eligible media exists
        """
        query = self.db.query(MediaItem).filter(MediaItem.is_active)

        # Filter by category if specified
        if category:
            query = query.filter(MediaItem.category == category)

        # Exclude already queued items
        queued_subquery = exists(
            select(PostingQueue.id).where(
                PostingQueue.media_item_id == MediaItem.id
            )
        )
        query = query.filter(~queued_subquery)

        # Exclude locked items (both permanent and TTL locks)
        now = datetime.utcnow()
        locked_subquery = exists(
            select(MediaPostingLock.id).where(
                and_(
                    MediaPostingLock.media_item_id == MediaItem.id,
                    # Lock is active if: locked_until is NULL (permanent)
                    # OR locked_until > now (TTL not expired)
                    (MediaPostingLock.locked_until.is_(None))
                    | (MediaPostingLock.locked_until > now),
                )
            )
        )
        query = query.filter(~locked_subquery)

        # Sort by priority:
        # 1. Never posted first (NULLS FIRST)
        # 2. Then least posted
        # 3. Then random (ensures variety when items are tied)
        query = query.order_by(
            MediaItem.last_posted_at.asc().nullsfirst(),
            MediaItem.times_posted.asc(),
            func.random(),
        )

        # Return top result
        return query.first()
```

### Step 2: Simplify `SchedulerService._select_media_from_pool()`

Open `src/services/core/scheduler.py`. Replace the entire `_select_media_from_pool()` method (lines 406-458).

**BEFORE** (current method, lines 406-458):

```python
    def _select_media_from_pool(self, category: Optional[str] = None):
        """
        Select media from a specific pool (category or all).

        Args:
            category: Filter by category, or None for all

        Returns:
            MediaItem or None
        """
        from sqlalchemy import and_, exists, select, func
        from src.models.media_item import MediaItem
        from src.models.posting_queue import PostingQueue
        from src.models.media_lock import MediaPostingLock

        query = self.media_repo.db.query(MediaItem).filter(MediaItem.is_active)

        # Filter by category if specified
        if category:
            query = query.filter(MediaItem.category == category)

        # Exclude already queued items
        queued_subquery = exists(
            select(PostingQueue.id).where(PostingQueue.media_item_id == MediaItem.id)
        )
        query = query.filter(~queued_subquery)

        # Exclude locked items (both permanent and TTL locks)
        now = datetime.utcnow()
        locked_subquery = exists(
            select(MediaPostingLock.id).where(
                and_(
                    MediaPostingLock.media_item_id == MediaItem.id,
                    # Lock is active if: locked_until is NULL (permanent) OR locked_until > now (TTL not expired)
                    (MediaPostingLock.locked_until.is_(None))
                    | (MediaPostingLock.locked_until > now),
                )
            )
        )
        query = query.filter(~locked_subquery)

        # Sort by priority:
        # 1. Never posted first (NULLS FIRST)
        # 2. Then least posted
        # 3. Then random (ensures variety when items are tied on above criteria)
        query = query.order_by(
            MediaItem.last_posted_at.asc().nullsfirst(),
            MediaItem.times_posted.asc(),
            func.random(),
        )

        # Return top result (randomness is built into the query)
        return query.first()
```

**AFTER** (simplified method):

```python
    def _select_media_from_pool(self, category: Optional[str] = None):
        """
        Select media from a specific pool (category or all).

        Delegates to MediaRepository.get_next_eligible_for_posting() which handles
        filtering out locked, queued, and inactive items with proper priority sorting.

        Args:
            category: Filter by category, or None for all

        Returns:
            MediaItem or None
        """
        return self.media_repo.get_next_eligible_for_posting(category=category)
```

### Step 3: Clean up unused imports in `scheduler.py`

After the refactor, verify that the `scheduler.py` file no longer needs the `datetime` import for the `_select_media_from_pool` method. However, `datetime` is still used in `_generate_time_slots()` (line 342) and `_generate_time_slots_from_date()` (line 272), so **do not remove the `datetime` import**.

The final imports at the top of `scheduler.py` should remain unchanged:

```python
from datetime import datetime, timedelta
from typing import Optional, List
import random

from src.services.base_service import BaseService
from src.services.core.settings_service import SettingsService
from src.repositories.media_repository import MediaRepository
from src.repositories.queue_repository import QueueRepository
from src.repositories.lock_repository import LockRepository
from src.repositories.category_mix_repository import CategoryMixRepository
from src.config.settings import settings
from src.utils.logger import logger
```

No imports need to be added or removed. The lazy imports (`from sqlalchemy ...`, `from src.models ...`) that were inside `_select_media_from_pool()` are simply deleted along with the old method body.

### Step 4: Update tests

The existing test file `tests/src/services/test_scheduler.py` mocks `_select_media_from_pool` directly in the `TestSchedulerCategoryAllocation` class (lines 343-378). These tests will continue to work without changes because they mock `_select_media_from_pool` as a callable on the service instance.

However, you should add a new unit test to verify the delegation works correctly. Add the following test to the `TestSchedulerCategoryAllocation` class in `tests/src/services/test_scheduler.py`:

```python
    def test_select_media_from_pool_delegates_to_repository(self, scheduler_service):
        """Test that _select_media_from_pool delegates to media_repo."""
        mock_media = Mock(category="memes", file_name="test.jpg")
        scheduler_service.media_repo.get_next_eligible_for_posting.return_value = (
            mock_media
        )

        result = scheduler_service._select_media_from_pool(category="memes")

        scheduler_service.media_repo.get_next_eligible_for_posting.assert_called_once_with(
            category="memes"
        )
        assert result == mock_media

    def test_select_media_from_pool_passes_none_category(self, scheduler_service):
        """Test that _select_media_from_pool passes None category correctly."""
        scheduler_service.media_repo.get_next_eligible_for_posting.return_value = None

        result = scheduler_service._select_media_from_pool(category=None)

        scheduler_service.media_repo.get_next_eligible_for_posting.assert_called_once_with(
            category=None
        )
        assert result is None
```

You should also add a new test class for the repository method itself. Create tests in `tests/src/repositories/test_media_repository.py` (or add to it if it exists):

```python
@pytest.mark.unit
class TestGetNextEligibleForPosting:
    """Tests for MediaRepository.get_next_eligible_for_posting()."""

    # NOTE: This method contains complex multi-table queries.
    # Full testing requires integration tests with a real database.
    # Unit tests should verify the method exists and accepts the correct parameters.
    # Integration tests should verify the actual query logic.

    @pytest.mark.skip(
        reason="TODO: Integration test - needs real DB to verify multi-table query"
    )
    def test_returns_never_posted_first(self):
        """Integration test: verify never-posted items are prioritized."""
        pass

    @pytest.mark.skip(
        reason="TODO: Integration test - needs real DB to verify multi-table query"
    )
    def test_excludes_locked_items(self):
        """Integration test: verify locked items are excluded."""
        pass

    @pytest.mark.skip(
        reason="TODO: Integration test - needs real DB to verify multi-table query"
    )
    def test_excludes_queued_items(self):
        """Integration test: verify already-queued items are excluded."""
        pass

    @pytest.mark.skip(
        reason="TODO: Integration test - needs real DB to verify multi-table query"
    )
    def test_filters_by_category(self):
        """Integration test: verify category filtering works."""
        pass
```

---

## Verification Checklist

After making changes, verify each item:

- [ ] `ruff check src/services/core/scheduler.py` passes with no errors
- [ ] `ruff check src/repositories/media_repository.py` passes with no errors
- [ ] `ruff format --check src/services/core/scheduler.py` passes
- [ ] `ruff format --check src/repositories/media_repository.py` passes
- [ ] `pytest tests/src/services/test_scheduler.py` -- all existing tests still pass
- [ ] `pytest` -- full test suite still passes
- [ ] `scheduler.py` no longer contains any `from sqlalchemy` imports (search the file)
- [ ] `scheduler.py` no longer contains any `from src.models` imports (search the file)
- [ ] `scheduler.py` no longer references `self.media_repo.db` (search the file)
- [ ] `media_repository.py` contains the new `get_next_eligible_for_posting` method
- [ ] The new repository method imports `PostingQueue` and `MediaPostingLock` models
- [ ] The behavior is identical: same query, same filters, same sort order, same return type

---

## What NOT To Do

1. **Do NOT change the query logic.** This is a pure refactor -- move the code, do not modify it. The query filters, subqueries, and sort order must remain identical. If you change the query behavior, the scheduler will select different media items, which could cause duplicate posts or skip items.

2. **Do NOT add parameters beyond `category`.** The method's interface should be `get_next_eligible_for_posting(category: Optional[str] = None) -> Optional[MediaItem]`. Do not add `limit`, `exclude_ids`, or other parameters. Keep it simple. If additional filtering is needed in the future, that is a separate change.

3. **Do NOT import `PostingQueue` or `MediaPostingLock` in `scheduler.py`.** The whole point of this refactor is to remove those cross-layer imports from the service. If you find yourself adding model imports to the scheduler, you are going in the wrong direction.

4. **Do NOT change `_select_media()` (lines 376-404).** That method is the public-facing selection logic with fallback behavior. It calls `_select_media_from_pool()` and handles the category-exhaustion fallback. Leave it as-is; only the internal `_select_media_from_pool()` method changes.

5. **Do NOT remove the `datetime` import from `scheduler.py`.** It is used by `_generate_time_slots()` and `_generate_time_slots_from_date()`. Only the lazy imports inside the old `_select_media_from_pool()` body are removed.

6. **Do NOT rename `_select_media_from_pool()`.** Tests in `test_scheduler.py` (lines 347, 358, 373-378) mock this method by name. Renaming it would break those tests. The method stays as the thin delegation layer.

7. **Do NOT add the new repository method to `BaseRepository`.** This method is specific to `MediaRepository` because it queries `media_items` with joins to `posting_queue` and `media_posting_locks`. It does not belong in the base class.
