# Phase 02: BackfillContext Dataclass for Parameter Reduction

**Status:** ✅ COMPLETE
**Started:** 2026-02-12
**Completed:** 2026-02-12
**PR Title:** `refactor: introduce BackfillContext to reduce parameter bloat`
**Risk Level:** Low (internal refactoring, no behavior change)
**Estimated Effort:** 1-2 hours
**Files Modified:**
- `src/services/integrations/instagram_backfill.py` (primary)
- `tests/src/services/test_instagram_backfill.py` (update all affected tests)

## Dependencies
- None (independent)

## Blocks
- None

## Context

Five internal methods in `InstagramBackfillService` pass 7-8 parameters each, most of which are shared context that doesn't change between calls. This parameter bloat makes the code harder to read, test, and extend.

| Function | Current Params | After |
|---|---|---|
| `_backfill_feed()` | 9 | 3 |
| `_backfill_stories()` | 8 | 2 |
| `_process_media_item()` | 8 | 3 |
| `_process_carousel()` | 7 | 2 |
| `_download_and_index()` | 7 | 6 |

## Implementation Steps

### Step 1: Define BackfillContext dataclass

**File:** `src/services/integrations/instagram_backfill.py`

Add between the `BackfillResult` class (ends ~line 66) and the `InstagramBackfillService` class (starts ~line 69):

```python
@dataclass
class BackfillContext:
    """Shared state passed through the backfill call chain.

    Bundles parameters that are constant for a single backfill() invocation
    and shared across _backfill_feed, _process_media_item, _process_carousel,
    and _download_and_index.
    """

    token: str
    ig_account_id: str
    username: Optional[str]
    dry_run: bool
    known_ig_ids: set
    storage_dir: Path
    result: BackfillResult
```

The `dataclass` import is already present (used by `BackfillResult`).

### Step 2: Update `backfill()` to create BackfillContext

**File:** `src/services/integrations/instagram_backfill.py`, in the `backfill()` method (~lines 101-207)

After credentials are fetched and `known_ig_ids` and `storage_dir` are initialized, create the context object. Find the lines where `_backfill_feed()` and `_backfill_stories()` are called and replace the long keyword-arg calls.

**Before** (around lines 170-207):
```python
        await self._backfill_feed(
            token=token,
            ig_account_id=ig_account_id,
            username=username,
            limit=limit,
            since=since,
            dry_run=dry_run,
            known_ig_ids=known_ig_ids,
            storage_dir=storage_dir,
            result=result,
        )

        if include_stories:
            await self._backfill_stories(
                token=token,
                ig_account_id=ig_account_id,
                username=username,
                limit=stories_limit,
                dry_run=dry_run,
                known_ig_ids=known_ig_ids,
                storage_dir=storage_dir,
                result=result,
            )
```

**After:**
```python
        ctx = BackfillContext(
            token=token,
            ig_account_id=ig_account_id,
            username=username,
            dry_run=dry_run,
            known_ig_ids=known_ig_ids,
            storage_dir=storage_dir,
            result=result,
        )

        await self._backfill_feed(ctx, limit=limit, since=since)

        if include_stories:
            await self._backfill_stories(ctx, limit=stories_limit)
```

### Step 3: Update `_backfill_feed()` signature

**Before** (lines ~210-263, signature):
```python
    async def _backfill_feed(
        self, token, ig_account_id, username, limit, since,
        dry_run, known_ig_ids, storage_dir, result,
    ) -> None:
```

**After:**
```python
    async def _backfill_feed(
        self, ctx: BackfillContext, limit: Optional[int], since: Optional[str],
    ) -> None:
```

Inside the method body, replace all bare references:
- `token` → `ctx.token`
- `ig_account_id` → `ctx.ig_account_id`
- `result.total_api_items` → `ctx.result.total_api_items`
- `known_ig_ids` → `ctx.known_ig_ids`
- `_process_media_item(item=item, token=token, ...)` → `_process_media_item(ctx, item=item, source_label="feed")`

### Step 4: Update `_backfill_stories()` signature

**Before** (lines ~340-390, signature):
```python
    async def _backfill_stories(
        self, token, ig_account_id, username, limit,
        dry_run, known_ig_ids, storage_dir, result,
    ) -> None:
```

**After:**
```python
    async def _backfill_stories(
        self, ctx: BackfillContext, limit: Optional[int],
    ) -> None:
```

Same body substitutions as Step 3.

### Step 5: Update `_process_media_item()` signature

**Before** (lines 392-463, signature):
```python
    async def _process_media_item(
        self, item, token, username, dry_run,
        known_ig_ids, storage_dir, result, source_label,
    ) -> None:
```

**After:**
```python
    async def _process_media_item(
        self, ctx: BackfillContext, item: dict, source_label: str,
    ) -> None:
```

Body substitutions:
- `known_ig_ids` → `ctx.known_ig_ids`
- `result.skipped_duplicate` → `ctx.result.skipped_duplicate`
- `dry_run` → `ctx.dry_run`
- `_process_carousel(item=item, token=...)` → `_process_carousel(ctx, item=item)`
- `_download_and_index(...)` → `_download_and_index(ctx, ig_media_id=..., media_url=..., media_type=..., item=item, source_label=source_label)`

### Step 6: Update `_process_carousel()` signature

**Before** (lines 465-510):
```python
    async def _process_carousel(
        self, item, token, username, dry_run,
        known_ig_ids, storage_dir, result,
    ) -> None:
```

**After:**
```python
    async def _process_carousel(
        self, ctx: BackfillContext, item: dict,
    ) -> None:
```

Body: `token` → `ctx.token`, `result.X` → `ctx.result.X`, collapse `_process_media_item(...)` call.

### Step 7: Update `_download_and_index()` signature

**Before** (lines 512-565):
```python
    async def _download_and_index(
        self, ig_media_id, media_url, media_type,
        item, username, storage_dir, source_label,
    ) -> None:
```

**After:**
```python
    async def _download_and_index(
        self, ctx: BackfillContext, ig_media_id: str, media_url: str,
        media_type: str, item: dict, source_label: str,
    ) -> None:
```

Body: `storage_dir` → `ctx.storage_dir`. Note `username` was passed but **never used** in the method body — it's now available on `ctx.username` if ever needed.

### Step 8: Update test file imports

**File:** `tests/src/services/test_instagram_backfill.py`, lines 17-20

**Before:**
```python
from src.services.integrations.instagram_backfill import (
    BackfillResult,
    InstagramBackfillService,
)
```

**After:**
```python
from src.services.integrations.instagram_backfill import (
    BackfillContext,
    BackfillResult,
    InstagramBackfillService,
)
```

### Step 9: Add `make_ctx` fixture

Add after the existing `mock_backfill_service` fixture (~line 101):

```python
@pytest.fixture
def make_ctx():
    """Factory fixture to create BackfillContext with sensible defaults."""
    def _make(
        token="tok", ig_account_id="ig_123", username="user",
        dry_run=False, known_ig_ids=None, storage_dir=None, result=None,
    ):
        return BackfillContext(
            token=token, ig_account_id=ig_account_id, username=username,
            dry_run=dry_run,
            known_ig_ids=known_ig_ids if known_ig_ids is not None else set(),
            storage_dir=storage_dir or Path("/tmp"),
            result=result or BackfillResult(),
        )
    return _make
```

### Step 10: Update all affected tests

**Pattern for each test:** Replace keyword args with `ctx`, read results from `ctx.result`.

Example transformation for `test_downloads_images`:

**Before:**
```python
    async def test_downloads_images(self, mock_backfill_service):
        result = BackfillResult()
        known_ig_ids = set()
        storage_dir = Path("/tmp/test_backfill")
        # ... mock setup ...
        await mock_backfill_service._backfill_feed(
            token="tok", ig_account_id="ig_123", username="user",
            limit=None, since=None, dry_run=False,
            known_ig_ids=known_ig_ids, storage_dir=storage_dir, result=result,
        )
        assert result.downloaded == 1
```

**After:**
```python
    async def test_downloads_images(self, mock_backfill_service, make_ctx):
        ctx = make_ctx(storage_dir=Path("/tmp/test_backfill"))
        # ... mock setup unchanged ...
        await mock_backfill_service._backfill_feed(ctx, limit=None, since=None)
        assert ctx.result.downloaded == 1
```

**Apply this pattern to all 19 tests** in `TestBackfillFeed` (7), `TestBackfillCarousel` (4), `TestBackfillStories` (3), `TestDownloadAndIndex` (2), `TestProcessMediaItemErrors` (3).

For tests needing specific values:
- `test_skips_duplicates`: `make_ctx(known_ig_ids={"existing_id"})`
- `test_dry_run_no_download`: `make_ctx(dry_run=True)`
- `TestDownloadAndIndex`: `make_ctx(storage_dir=tmp_path)`

### Step 11: Add BackfillContext unit tests

Add after `TestBackfillResult` class:

```python
@pytest.mark.unit
class TestBackfillContext:
    """Tests for the BackfillContext dataclass."""

    def test_creation(self):
        result = BackfillResult()
        ctx = BackfillContext(
            token="abc", ig_account_id="ig_99", username="testuser",
            dry_run=True, known_ig_ids={"id1"},
            storage_dir=Path("/tmp/test"), result=result,
        )
        assert ctx.token == "abc"
        assert ctx.ig_account_id == "ig_99"
        assert ctx.dry_run is True

    def test_mutable_fields_shared(self):
        known = set()
        result = BackfillResult()
        ctx = BackfillContext(
            token="t", ig_account_id="ig", username=None,
            dry_run=False, known_ig_ids=known,
            storage_dir=Path("/tmp"), result=result,
        )
        ctx.known_ig_ids.add("new_id")
        assert "new_id" in known
        ctx.result.downloaded += 1
        assert result.downloaded == 1
```

## Verification Checklist

- [x] `BackfillContext` dataclass defined between `BackfillResult` and `InstagramBackfillService`
- [x] `backfill()` creates context and passes to `_backfill_feed()` / `_backfill_stories()`
- [x] No bare references to old param names remain (search for `known_ig_ids`, `storage_dir` without `ctx.` prefix)
- [x] API call methods (`_fetch_media_page`, `_fetch_stories`, etc.) are NOT changed
- [x] Helper methods (`_get_storage_dir`, `_get_extension_for_type`, etc.) are NOT changed
- [x] `BackfillContext` imported in test file
- [x] `make_ctx` fixture added
- [x] All 20 affected tests updated to use `ctx`
- [x] 2 new `TestBackfillContext` tests added
- [x] `ruff check src/ tests/` passes
- [x] `pytest tests/src/services/test_instagram_backfill.py` — all 48 pass
- [x] `pytest` — full suite passes (723 passed, 38 skipped)
- [x] CHANGELOG.md updated

## What NOT To Do

- **Do NOT add `limit`, `since`, or `source_label` to BackfillContext** — these vary per call site.
- **Do NOT change the `backfill()` public method signature** — callers don't need to know about BackfillContext.
- **Do NOT refactor `_fetch_media_page`, `_fetch_stories`, `_fetch_carousel_children`, `_download_media`** — clean signatures already.
- **Do NOT change BackfillResult** — it remains separate; BackfillContext holds a reference.
- **Do NOT make BackfillContext frozen** — `known_ig_ids` and `result` are modified in place.
