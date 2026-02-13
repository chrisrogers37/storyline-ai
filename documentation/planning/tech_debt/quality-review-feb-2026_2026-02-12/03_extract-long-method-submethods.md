# Phase 03: Extract Sub-Methods from Long Handlers

**Status:** ✅ COMPLETE
**Started:** 2026-02-12
**Completed:** 2026-02-12
**PR Title:** `refactor: break down _do_autopost() and handle_status() long methods`
**Risk Level:** Medium
**Estimated Effort:** 2-3 hours
**Files Modified:**
- `src/services/core/telegram_autopost.py` (primary)
- `src/services/core/telegram_commands.py` (primary)
- `tests/src/services/test_telegram_autopost.py` (add tests)
- `tests/src/services/test_telegram_commands.py` (add tests)

## Dependencies
- None (independent)

## Blocks
- Phase 04 (shared utilities extraction)

## Context

Two methods exceed maintainability thresholds:
- `_do_autopost()` in `telegram_autopost.py`: **152+ lines, 8 params**, mixes upload, posting, recording, and error handling
- `handle_status()` in `telegram_commands.py`: **115 lines, 5 nesting levels**, queries 7+ services inline

## Implementation Steps

### Part A: telegram_autopost.py

#### Step 1: Define `AutopostContext` dataclass

Add at module level (after imports, before class). Bundles shared state that flows through the autopost call chain, avoiding parameter bloat in extracted methods. Follows the same pattern as `BackfillContext` (Phase 02).

```python
@dataclass
class AutopostContext:
    """Shared state passed through the autopost call chain."""

    queue_id: str
    queue_item: object  # PostingQueue model
    media_item: object  # MediaItem model
    user: object  # User model
    query: object  # CallbackQuery
    chat_id: int
    chat_settings: object  # ChatSettings model
    cloud_service: object  # CloudStorageService
    instagram_service: object  # InstagramAPIService
    cancel_flag: object = None  # threading.Event or None
    cloud_url: str | None = None
    cloud_public_id: str | None = None
```

#### Step 2: Extract `_get_account_display()`

Extract the account info lookup into a helper (~lines 350-360).

```python
async def _get_account_display(self, ctx: AutopostContext) -> str:
    """Get formatted account display string for messages."""
    try:
        account_info = await ctx.instagram_service.get_account_info(
            telegram_chat_id=ctx.chat_id
        )
        return f"@{account_info.get('username', 'Unknown')}"
    except Exception:
        return "Unknown account"
```

#### Step 3: Extract `_upload_to_cloudinary()`

Extract lines ~133-176 (the Cloudinary upload section). Sets `ctx.cloud_url` and `ctx.cloud_public_id`.

```python
async def _upload_to_cloudinary(self, ctx: AutopostContext) -> bool:
    """Upload media to Cloudinary for Instagram posting.

    Sets ctx.cloud_url and ctx.cloud_public_id.
    Returns False if cancelled, True on success.
    """
    if ctx.cancel_flag and ctx.cancel_flag.is_set():
        return False

    await ctx.query.edit_message_caption(
        caption="☁️ *Uploading to cloud...*", parse_mode="Markdown"
    )

    cloud_result = ctx.cloud_service.upload_media(ctx.media_item)
    ctx.cloud_url = cloud_result["url"]
    ctx.cloud_public_id = cloud_result["public_id"]

    self.service.media_repo.update_cloud_info(
        media_id=str(ctx.media_item.id),
        cloud_url=ctx.cloud_url,
        cloud_public_id=ctx.cloud_public_id,
        cloud_uploaded_at=datetime.utcnow(),
    )

    return True
```

#### Step 4: Extract `_handle_dry_run()`

Extract the dry-run branch (~lines 180-269).

```python
async def _handle_dry_run(self, ctx: AutopostContext) -> None:
    """Handle dry-run mode: log what would happen, cleanup cloud, show message."""
    # ... dry run caption building and interaction logging
    # ... cloud cleanup
    # ... edit message with dry run result
```

Preserve the exact caption text and interaction logging from the current code.

#### Step 5: Extract `_execute_instagram_post()`

Extract lines ~284-310 (the actual Instagram API call).

```python
async def _execute_instagram_post(self, ctx: AutopostContext) -> str | None:
    """Post media to Instagram via the Graph API.

    Returns:
        Instagram story_id string, or None if cancelled.
    """
    if ctx.cancel_flag and ctx.cancel_flag.is_set():
        return None

    await ctx.query.edit_message_caption(
        caption="⏳ *Posting to Instagram...*", parse_mode="Markdown"
    )

    media_type = (
        "VIDEO" if ctx.media_item.file_path.lower().endswith((".mp4", ".mov")) else "IMAGE"
    )

    if media_type == "IMAGE":
        story_url = ctx.cloud_service.get_story_optimized_url(ctx.cloud_url)
    else:
        story_url = ctx.cloud_url

    post_result = await ctx.instagram_service.post_story(
        media_url=story_url, media_type=media_type, telegram_chat_id=ctx.chat_id,
    )

    story_id = post_result.get("story_id")
    logger.info(f"Posted to Instagram: story_id={story_id}")
    return story_id
```

#### Step 6: Extract `_record_successful_post()`

Extract lines ~316-345 (history, increment, lock, queue delete, user stats).

```python
def _record_successful_post(self, ctx: AutopostContext, story_id: str) -> None:
    """Record a successful Instagram post in all relevant tables."""
    self.service.history_repo.create(
        HistoryCreateParams(
            media_item_id=str(ctx.queue_item.media_item_id),
            queue_item_id=ctx.queue_id,
            queue_created_at=ctx.queue_item.created_at,
            queue_deleted_at=datetime.utcnow(),
            scheduled_for=ctx.queue_item.scheduled_for,
            posted_at=datetime.utcnow(),
            status="posted",
            success=True,
            posted_by_user_id=str(ctx.user.id),
            posted_by_telegram_username=ctx.user.telegram_username,
            posting_method="instagram_api",
            instagram_story_id=story_id,
        )
    )
    self.service.media_repo.increment_times_posted(str(ctx.queue_item.media_item_id))
    self.service.lock_service.create_lock(str(ctx.queue_item.media_item_id))
    self.service.queue_repo.delete(ctx.queue_id)
    self.service.user_repo.increment_posts(str(ctx.user.id))
```

#### Step 7: Extract `_handle_autopost_error()`

Extract the except block (~lines 413-449).

```python
async def _handle_autopost_error(self, ctx: AutopostContext, e: Exception) -> None:
    """Handle auto-post failure: show error message with recovery options."""
    error_msg = str(e)
    logger.error(f"Auto-post failed: {error_msg}", exc_info=True)

    caption = (
        f"❌ *Auto Post Failed*\n\n"
        f"Error: {error_msg[:200]}\n\n"
        f"You can try again or use manual posting."
    )

    reply_markup = build_error_recovery_keyboard(
        ctx.queue_id, enable_instagram_api=settings.ENABLE_INSTAGRAM_API
    )

    await ctx.query.edit_message_caption(
        caption=caption, reply_markup=reply_markup, parse_mode="Markdown",
    )

    self.service.interaction_service.log_callback(
        user_id=str(ctx.user.id), callback_name="autopost",
        context={
            "queue_item_id": ctx.queue_id,
            "media_id": str(ctx.queue_item.media_item_id),
            "media_filename": ctx.media_item.file_name,
            "dry_run": False, "success": False, "error": error_msg[:200],
        },
        telegram_chat_id=ctx.query.message.chat_id,
        telegram_message_id=ctx.query.message.message_id,
    )
```

#### Step 8: Rewrite `_do_autopost()` as orchestrator

Replace body with ~55 lines: create `AutopostContext`, then call sub-methods in sequence: safety check → upload → dry-run check → post → record → success message, with try/except calling `_handle_autopost_error`. Keep the 8-parameter signature unchanged (callers don't see `AutopostContext`).

### Part B: telegram_commands.py

#### Step 9: Extract `_get_next_post_display()`

```python
def _get_next_post_display(self) -> str:
    """Get formatted display for next scheduled post time."""
    next_items = self.service.queue_repo.get_pending(limit=1)
    if next_items:
        return next_items[0].scheduled_for.strftime("%H:%M UTC")
    return "None scheduled"
```

#### Step 10: Extract `_get_last_posted_display()`

```python
def _get_last_posted_display(self, recent_posts) -> str:
    """Get formatted display for last post time."""
    if recent_posts:
        time_diff = datetime.utcnow() - recent_posts[0].posted_at
        hours = int(time_diff.total_seconds() / 3600)
        return f"{hours}h ago" if hours > 0 else "< 1h ago"
    return "Never"
```

#### Step 11: Extract `_get_instagram_api_status()`

```python
def _get_instagram_api_status(self) -> str:
    """Get formatted Instagram API status string."""
    if settings.ENABLE_INSTAGRAM_API:
        from src.services.integrations.instagram_api import InstagramAPIService
        with InstagramAPIService() as ig_service:
            rate_remaining = ig_service.get_rate_limit_remaining()
        return f"✅ Enabled ({rate_remaining}/{settings.INSTAGRAM_POSTS_PER_HOUR} remaining)"
    return "❌ Disabled"
```

#### Step 12: Extract `_get_sync_status_line()`

Extract lines 94-133 (the most deeply nested section at 5 levels).

```python
def _get_sync_status_line(self, chat_id) -> str:
    """Get formatted media sync status (catches all exceptions internally)."""
    try:
        from src.services.core.media_sync import MediaSyncService
        sync_service = MediaSyncService()
        last_sync = sync_service.get_last_sync_info()
        chat_settings = self.service.settings_service.get_settings(chat_id)

        if not chat_settings.media_sync_enabled:
            return "🔄 Media Sync: ❌ Disabled"
        if not last_sync:
            return "🔄 Media Sync: ⏳ No syncs yet"
        if last_sync["success"]:
            result = last_sync.get("result", {}) or {}
            new_count = result.get("new", 0)
            total = sum(result.get(k, 0) for k in ["new", "updated", "deactivated", "reactivated", "unchanged"])
            return (
                f"🔄 Media Sync: ✅ OK"
                f"\n   └─ Last: {last_sync['started_at'][:16]} ({total} items, {new_count} new)"
            )
        return f"🔄 Media Sync: ⚠️ Last sync failed\n   └─ {last_sync.get('started_at', 'N/A')[:16]}"
    except Exception:
        return "🔄 Media Sync: ❓ Check failed"
```

#### Step 13: Rewrite `handle_status()` to compose from helpers

Drops from 115 lines to ~50 lines. Max nesting drops from 5 to 2.

### Part C: Add Tests

#### Step 14: Add `AutopostContext` tests

Add `TestAutopostContext` class verifying dataclass creation and mutable field defaults.

#### Step 15: Add autopost helper tests

Add tests for all 6 extracted autopost methods. Use a `make_autopost_ctx` factory fixture (similar to Phase 02's `make_ctx`).

| Test Class | Methods Tested | Test Cases |
|-----------|---------------|------------|
| `TestAutopostContext` | dataclass | creation, default fields |
| `TestGetAccountDisplay` | `_get_account_display` | success, exception fallback |
| `TestUploadToCloudinary` | `_upload_to_cloudinary` | success (sets ctx fields), cancelled returns False |
| `TestHandleDryRun` | `_handle_dry_run` | edits message with dry-run caption, cleans up cloud |
| `TestExecuteInstagramPost` | `_execute_instagram_post` | success returns story_id, cancelled returns None, IMAGE vs VIDEO media type |
| `TestRecordSuccessfulPost` | `_record_successful_post` | calls all 5 repo operations (history, increment, lock, delete queue, user stats) |
| `TestHandleAutopostError` | `_handle_autopost_error` | edits message with error caption, logs interaction |

Existing integration-level tests (`handle_autopost()` → `_do_autopost()`) continue to pass unchanged.

#### Step 16: Add status helper tests

Add tests for all 4 status helpers + end-to-end `handle_status()`.

| Test Class | Methods Tested | Test Cases |
|-----------|---------------|------------|
| `TestGetNextPostDisplay` | `_get_next_post_display` | with pending items, empty queue |
| `TestGetLastPostedDisplay` | `_get_last_posted_display` | recent post (hours ago), very recent (< 1h), no posts |
| `TestGetInstagramApiStatus` | `_get_instagram_api_status` | enabled with rate limit, disabled |
| `TestGetSyncStatusLine` | `_get_sync_status_line` | disabled, no syncs yet, successful sync, failed sync, exception |
| `TestStatusCommand` | `handle_status` | end-to-end: sends formatted message with all sections |

## Verification Checklist

- [x] `AutopostContext` dataclass defined at module level in `telegram_autopost.py`
- [x] All 7 extracted autopost methods take `ctx: AutopostContext` (not bare params)
- [x] `ruff check src/services/core/telegram_autopost.py src/services/core/telegram_commands.py`
- [x] `ruff format --check` passes
- [x] `pytest tests/src/services/test_telegram_autopost.py -v` — all 20 tests pass (6 existing + 14 new)
- [x] `pytest tests/src/services/test_telegram_commands.py -v` — all 36 tests pass (23 existing + 13 new)
- [x] `pytest` — full suite passes (750 passed, 38 skipped)
- [x] `_do_autopost()` is under 60 lines (~50, was 353)
- [x] `handle_status()` is under 55 lines (~50, was 115)
- [x] Lazy imports preserved (MediaSyncService, InstagramAPIService inside methods)
- [x] CHANGELOG.md updated

## What NOT To Do

- **Do NOT change signatures of `handle_autopost()`, `_locked_autopost()`, or `_do_autopost()`**
- **Do NOT change user-visible caption text, emoji, or Markdown formatting**
- **Do NOT change the order of operations in `_do_autopost()`** — safety check → upload → dry-run → post → record is critical
- **Do NOT extract the safety check** (lines 114-128) — it's only 15 lines and reads well as a guard clause
- **Do NOT refactor other commands** (`handle_sync`, `handle_backfill`, etc.) — out of scope
- **Do NOT create new files** — extracted methods stay as private methods on the same class
