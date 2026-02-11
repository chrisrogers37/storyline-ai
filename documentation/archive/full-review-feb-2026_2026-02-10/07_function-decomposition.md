# Phase 07: Decompose Long Functions and Reduce Parameter Counts

✅ COMPLETE | Completed: 2026-02-10 | PR: #35

| Field | Value |
|---|---|
| **PR Title** | `refactor: decompose long functions and reduce parameter counts` |
| **Risk Level** | Medium |
| **Effort** | Large (4-6 hours) |
| **Dependencies** | Phase 03 (BaseRepository.check_connection), Phase 04 (scheduler architecture) |
| **Blocks** | None |
| **Files Modified** | `src/repositories/history_repository.py`, `src/services/core/scheduler.py`, `src/services/core/instagram_account_service.py`, `src/services/integrations/cloud_storage.py`, `src/services/core/health_check.py` |
| **Files Affected (call sites)** | `src/services/core/telegram_callbacks.py`, `src/services/core/telegram_autopost.py`, `src/services/core/posting.py` |

---

## Problem Description

Five files contain functions that are too long or accept too many parameters. Long functions are harder to test in isolation, harder to review during code review, and harder for a new developer to understand at a glance. High parameter counts make call sites error-prone because Python keyword arguments can be silently misordered.

The five worst offenders are:

1. **`history_repository.py:78`** -- `create()` accepts 16 positional/keyword parameters
2. **`scheduler.py:28-117`** -- `create_schedule()` is 90 lines with inline loop logic
3. **`scheduler.py:120-222`** -- `extend_schedule()` is 102 lines and duplicates most of `create_schedule()`
4. **`instagram_account_service.py:146-246`** -- `add_account()` is 100 lines with 8 parameters
5. **`cloud_storage.py:58-158`** -- `upload_media()` is 100 lines with mixed concerns

---

## Target 1: `HistoryRepository.create()` -- 16 Parameters to Dataclass

### Current Code (`src/repositories/history_repository.py:78-121`)

```python
def create(
    self,
    media_item_id: str,
    queue_item_id: str,
    queue_created_at: datetime,
    queue_deleted_at: datetime,
    scheduled_for: datetime,
    posted_at: datetime,
    status: str,
    success: bool,
    media_metadata: Optional[dict] = None,
    instagram_media_id: Optional[str] = None,
    instagram_permalink: Optional[str] = None,
    instagram_story_id: Optional[str] = None,
    posting_method: str = "telegram_manual",
    posted_by_user_id: Optional[str] = None,
    posted_by_telegram_username: Optional[str] = None,
    error_message: Optional[str] = None,
    retry_count: int = 0,
) -> PostingHistory:
```

### Step 1: Define the Dataclass

Add this at the top of `src/repositories/history_repository.py`, between the imports and the `HistoryRepository` class definition (after line 8, before line 10):

```python
from dataclasses import dataclass, field


@dataclass
class HistoryCreateParams:
    """Bundled parameters for creating a posting history record.

    Required fields come first, optional fields have defaults.
    """

    # Required fields
    media_item_id: str
    queue_item_id: str
    queue_created_at: datetime
    queue_deleted_at: datetime
    scheduled_for: datetime
    posted_at: datetime
    status: str
    success: bool

    # Optional fields with defaults
    media_metadata: Optional[dict] = None
    instagram_media_id: Optional[str] = None
    instagram_permalink: Optional[str] = None
    instagram_story_id: Optional[str] = None
    posting_method: str = "telegram_manual"
    posted_by_user_id: Optional[str] = None
    posted_by_telegram_username: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
```

### Step 2: Update the `create()` Method Signature

Replace the current `create()` method (lines 78-121) with:

```python
def create(self, params: HistoryCreateParams) -> PostingHistory:
    """Create a new history record from bundled parameters."""
    history = PostingHistory(
        media_item_id=params.media_item_id,
        queue_item_id=params.queue_item_id,
        queue_created_at=params.queue_created_at,
        queue_deleted_at=params.queue_deleted_at,
        scheduled_for=params.scheduled_for,
        posted_at=params.posted_at,
        status=params.status,
        success=params.success,
        media_metadata=params.media_metadata,
        instagram_media_id=params.instagram_media_id,
        instagram_permalink=params.instagram_permalink,
        instagram_story_id=params.instagram_story_id,
        posting_method=params.posting_method,
        posted_by_user_id=params.posted_by_user_id,
        posted_by_telegram_username=params.posted_by_telegram_username,
        error_message=params.error_message,
        retry_count=params.retry_count,
    )
    self.db.add(history)
    self.db.commit()
    self.db.refresh(history)
    return history
```

### Step 3: Update All Call Sites

There are **5 call sites** across 3 files. Each must be updated to construct a `HistoryCreateParams` first, then pass it.

Add this import to each file:
```python
from src.repositories.history_repository import HistoryCreateParams
```

#### Call Site 1: `src/services/core/telegram_callbacks.py:78-89` (in `_do_complete_queue_action`)

**Before:**
```python
self.service.history_repo.create(
    media_item_id=str(queue_item.media_item_id),
    queue_item_id=queue_id,
    queue_created_at=queue_item.created_at,
    queue_deleted_at=datetime.utcnow(),
    scheduled_for=queue_item.scheduled_for,
    posted_at=datetime.utcnow(),
    status=status,
    success=success,
    posted_by_user_id=str(user.id),
    posted_by_telegram_username=user.telegram_username,
)
```

**After:**
```python
self.service.history_repo.create(HistoryCreateParams(
    media_item_id=str(queue_item.media_item_id),
    queue_item_id=queue_id,
    queue_created_at=queue_item.created_at,
    queue_deleted_at=datetime.utcnow(),
    scheduled_for=queue_item.scheduled_for,
    posted_at=datetime.utcnow(),
    status=status,
    success=success,
    posted_by_user_id=str(user.id),
    posted_by_telegram_username=user.telegram_username,
))
```

#### Call Site 2: `src/services/core/telegram_callbacks.py:392-403` (in `handle_rejected`)

**Before:**
```python
self.service.history_repo.create(
    media_item_id=str(queue_item.media_item_id),
    queue_item_id=queue_id,
    queue_created_at=queue_item.created_at,
    queue_deleted_at=datetime.utcnow(),
    scheduled_for=queue_item.scheduled_for,
    posted_at=datetime.utcnow(),
    status="rejected",
    success=False,
    posted_by_user_id=str(user.id),
    posted_by_telegram_username=user.telegram_username,
)
```

**After:**
```python
self.service.history_repo.create(HistoryCreateParams(
    media_item_id=str(queue_item.media_item_id),
    queue_item_id=queue_id,
    queue_created_at=queue_item.created_at,
    queue_deleted_at=datetime.utcnow(),
    scheduled_for=queue_item.scheduled_for,
    posted_at=datetime.utcnow(),
    status="rejected",
    success=False,
    posted_by_user_id=str(user.id),
    posted_by_telegram_username=user.telegram_username,
))
```

#### Call Site 3: `src/services/core/telegram_autopost.py:306-319` (in `_do_autopost`)

**Before:**
```python
self.service.history_repo.create(
    media_item_id=str(queue_item.media_item_id),
    queue_item_id=queue_id,
    queue_created_at=queue_item.created_at,
    queue_deleted_at=datetime.utcnow(),
    scheduled_for=queue_item.scheduled_for,
    posted_at=datetime.utcnow(),
    status="posted",
    success=True,
    posted_by_user_id=str(user.id),
    posted_by_telegram_username=user.telegram_username,
    posting_method="instagram_api",
    instagram_story_id=story_id,
)
```

**After:**
```python
self.service.history_repo.create(HistoryCreateParams(
    media_item_id=str(queue_item.media_item_id),
    queue_item_id=queue_id,
    queue_created_at=queue_item.created_at,
    queue_deleted_at=datetime.utcnow(),
    scheduled_for=queue_item.scheduled_for,
    posted_at=datetime.utcnow(),
    status="posted",
    success=True,
    posted_by_user_id=str(user.id),
    posted_by_telegram_username=user.telegram_username,
    posting_method="instagram_api",
    instagram_story_id=story_id,
))
```

#### Call Site 4: `src/services/core/posting.py:425-437` (in `_post_via_instagram`)

**Before:**
```python
self.history_repo.create(
    media_item_id=media_item_id,
    queue_item_id=queue_item_id,
    queue_created_at=queue_item.created_at,
    queue_deleted_at=datetime.utcnow(),
    scheduled_for=queue_item.scheduled_for,
    posted_at=datetime.utcnow(),
    status="posted",
    success=True,
    posting_method="instagram_api",
    instagram_story_id=result.get("story_id"),
    retry_count=queue_item.retry_count,
)
```

**After:**
```python
self.history_repo.create(HistoryCreateParams(
    media_item_id=media_item_id,
    queue_item_id=queue_item_id,
    queue_created_at=queue_item.created_at,
    queue_deleted_at=datetime.utcnow(),
    scheduled_for=queue_item.scheduled_for,
    posted_at=datetime.utcnow(),
    status="posted",
    success=True,
    posting_method="instagram_api",
    instagram_story_id=result.get("story_id"),
    retry_count=queue_item.retry_count,
))
```

#### Call Site 5: `src/services/core/posting.py:516-530` (in `handle_completion`)

**Before:**
```python
self.history_repo.create(
    media_item_id=str(queue_item.media_item_id),
    queue_item_id=queue_item_id,
    queue_created_at=queue_item.created_at,
    queue_deleted_at=datetime.utcnow(),
    scheduled_for=queue_item.scheduled_for,
    posted_at=datetime.utcnow(),
    status="posted" if success else "failed",
    success=success,
    posted_by_user_id=posted_by_user_id,
    error_message=error_message,
    retry_count=queue_item.retry_count,
    posting_method=posting_method,
    instagram_story_id=instagram_story_id,
)
```

**After:**
```python
self.history_repo.create(HistoryCreateParams(
    media_item_id=str(queue_item.media_item_id),
    queue_item_id=queue_item_id,
    queue_created_at=queue_item.created_at,
    queue_deleted_at=datetime.utcnow(),
    scheduled_for=queue_item.scheduled_for,
    posted_at=datetime.utcnow(),
    status="posted" if success else "failed",
    success=success,
    posted_by_user_id=posted_by_user_id,
    error_message=error_message,
    retry_count=queue_item.retry_count,
    posting_method=posting_method,
    instagram_story_id=instagram_story_id,
))
```

---

## Target 2: `SchedulerService.create_schedule()` -- 90 Lines to Extracted Helpers

### Current Structure (`src/services/core/scheduler.py:28-117`)

The method currently does three things inline:
1. Generates time slots (line 57)
2. Allocates categories (line 65)
3. Iterates over slots, selects media, and creates queue items (lines 72-100)

Steps 1 and 2 are already extracted into `_generate_time_slots()` and `_allocate_slots_to_categories()`. The remaining inline loop (step 3) should be extracted.

### Step 1: Extract `_fill_schedule_slots()` Helper

Add this new method to `SchedulerService` (after `_summarize_allocation`):

```python
def _fill_schedule_slots(
    self,
    time_slots: list[datetime],
    slot_categories: List[Optional[str]],
) -> tuple[int, int, dict]:
    """
    Fill schedule slots by selecting media and creating queue items.

    Args:
        time_slots: List of datetime slots to fill
        slot_categories: Category assignment per slot (or empty list)

    Returns:
        Tuple of (scheduled_count, skipped_count, category_breakdown)
    """
    scheduled_count = 0
    skipped_count = 0
    category_breakdown = {}

    for i, scheduled_time in enumerate(time_slots):
        target_category = slot_categories[i] if slot_categories else None

        media_item = self._select_media(category=target_category)

        if not media_item:
            logger.warning(
                f"No eligible media found for slot {scheduled_time}"
            )
            skipped_count += 1
            continue

        self.queue_repo.create(
            media_item_id=str(media_item.id), scheduled_for=scheduled_time
        )

        item_category = media_item.category or "uncategorized"
        category_breakdown[item_category] = (
            category_breakdown.get(item_category, 0) + 1
        )

        logger.info(
            f"Scheduled {media_item.file_name} [{item_category}] for {scheduled_time}"
        )
        scheduled_count += 1

    return scheduled_count, skipped_count, category_breakdown
```

### Step 2: Simplify `create_schedule()`

Replace lines 50-117 (the try/except body and result building) with:

```python
def create_schedule(self, days: int = 7, user_id: Optional[str] = None) -> dict:
    """
    Generate posting schedule for the next N days.

    Uses category ratios to allocate slots across categories.
    """
    with self.track_execution(
        method_name="create_schedule",
        user_id=user_id,
        triggered_by="cli" if user_id else "system",
        input_params={"days": days},
    ) as run_id:
        error_message = None

        try:
            time_slots = self._generate_time_slots(days)
            total_slots = len(time_slots)

            logger.info(
                f"Generating schedule for {days} days ({total_slots} slots)"
            )

            slot_categories = self._allocate_slots_to_categories(total_slots)

            if slot_categories:
                logger.info(
                    f"Category allocation: {self._summarize_allocation(slot_categories)}"
                )

            scheduled_count, skipped_count, category_breakdown = (
                self._fill_schedule_slots(time_slots, slot_categories)
            )

        except Exception as e:
            error_message = str(e)
            logger.error(f"Error during scheduling: {e}")
            scheduled_count, skipped_count, category_breakdown = 0, 0, {}
            total_slots = 0

        result = {
            "scheduled": scheduled_count,
            "skipped": skipped_count,
            "total_slots": total_slots,
            "category_breakdown": category_breakdown,
        }

        if error_message:
            result["error"] = error_message

        self.set_result_summary(run_id, result)
        return result
```

---

## Target 3: `SchedulerService.extend_schedule()` -- Extract Shared Logic

### Current Problem (`src/services/core/scheduler.py:120-222`)

`extend_schedule()` duplicates the entire inner loop from `create_schedule()`. The only differences are:

1. It finds the last scheduled time and starts from the day after (lines 147-157)
2. It calls `_generate_time_slots_from_date()` instead of `_generate_time_slots()` (line 162)
3. The result dict includes an `extended_from` key (line 213)

Lines 167-203 (category allocation + slot filling loop) are **identical** to `create_schedule()`.

### Step: Rewrite `extend_schedule()` Using `_fill_schedule_slots()`

Replace the entire method body (lines 120-222) with:

```python
def extend_schedule(self, days: int = 7, user_id: Optional[str] = None) -> dict:
    """
    Extend existing schedule by adding more days.

    Unlike create_schedule(), this preserves existing queue items
    and appends new slots starting after the last scheduled time.
    """
    with self.track_execution(
        method_name="extend_schedule",
        user_id=user_id,
        triggered_by="telegram" if user_id else "system",
        input_params={"days": days},
    ) as run_id:
        error_message = None
        total_slots = 0
        last_scheduled = None

        try:
            # Find the last scheduled time in the queue
            all_pending = self.queue_repo.get_all(status="pending")

            if all_pending:
                last_scheduled = max(item.scheduled_for for item in all_pending)
                start_date = last_scheduled.date() + timedelta(days=1)
            else:
                start_date = datetime.utcnow().date()

            logger.info(f"Extending schedule from {start_date} for {days} days")

            time_slots = self._generate_time_slots_from_date(start_date, days)
            total_slots = len(time_slots)

            logger.info(f"Generated {total_slots} new time slots")

            slot_categories = self._allocate_slots_to_categories(total_slots)

            if slot_categories:
                logger.info(
                    f"Category allocation: {self._summarize_allocation(slot_categories)}"
                )

            scheduled_count, skipped_count, category_breakdown = (
                self._fill_schedule_slots(time_slots, slot_categories)
            )

        except Exception as e:
            error_message = str(e)
            logger.error(f"Error during schedule extension: {e}")
            scheduled_count, skipped_count, category_breakdown = 0, 0, {}

        result = {
            "scheduled": scheduled_count,
            "skipped": skipped_count,
            "total_slots": total_slots,
            "extended_from": last_scheduled.isoformat() if last_scheduled else None,
            "category_breakdown": category_breakdown,
        }

        if error_message:
            result["error"] = error_message

        self.set_result_summary(run_id, result)
        return result
```

This eliminates **35 lines of duplicated code** (the entire for-loop and category tracking logic).

---

## Target 4: `InstagramAccountService.add_account()` -- 8 Params to Extracted Helpers

### Current Code (`src/services/core/instagram_account_service.py:146-246`)

The method handles three concerns:
1. Validation (duplicate checks, lines 186-199)
2. Account + token creation (lines 202-220)
3. Optional active-account assignment (lines 222-230)

### Step 1: Extract `_validate_new_account()`

Add this method to `InstagramAccountService`:

```python
def _validate_new_account(
    self, instagram_account_id: str, instagram_username: str
) -> None:
    """
    Validate that an account does not already exist.

    Raises:
        ValueError: If account already exists by ID or username
    """
    existing = self.account_repo.get_by_instagram_id(instagram_account_id)
    if existing:
        raise ValueError(
            f"Account with ID {instagram_account_id} already exists "
            f"as '{existing.display_name}'"
        )

    existing_by_username = self.account_repo.get_by_username(instagram_username)
    if existing_by_username:
        raise ValueError(
            f"Account @{instagram_username} already exists "
            f"as '{existing_by_username.display_name}'"
        )
```

### Step 2: Extract `_create_account_with_token()`

```python
def _create_account_with_token(
    self,
    display_name: str,
    instagram_account_id: str,
    instagram_username: str,
    access_token: str,
    token_expires_at: Optional[datetime] = None,
) -> InstagramAccount:
    """
    Create the account record and store its encrypted token.

    Returns:
        The created InstagramAccount
    """
    account = self.account_repo.create(
        display_name=display_name,
        instagram_account_id=instagram_account_id,
        instagram_username=instagram_username,
    )

    encrypted_token = self.encryption.encrypt(access_token)
    self.token_repo.create_or_update(
        service_name="instagram",
        token_type="access_token",
        token_value=encrypted_token,
        expires_at=token_expires_at,
        instagram_account_id=str(account.id),
        metadata={
            "account_id": instagram_account_id,
            "username": instagram_username,
        },
    )

    return account
```

### Step 3: Simplify `add_account()`

```python
def add_account(
    self,
    display_name: str,
    instagram_account_id: str,
    instagram_username: str,
    access_token: str,
    token_expires_at: Optional[datetime] = None,
    user: Optional[User] = None,
    set_as_active: bool = False,
    telegram_chat_id: Optional[int] = None,
) -> InstagramAccount:
    """Add a new Instagram account with its token."""
    with self.track_execution(
        "add_account",
        user_id=user.id if user else None,
        triggered_by="user",
        input_params={
            "display_name": display_name,
            "instagram_username": instagram_username,
        },
    ) as run_id:
        self._validate_new_account(instagram_account_id, instagram_username)

        account = self._create_account_with_token(
            display_name=display_name,
            instagram_account_id=instagram_account_id,
            instagram_username=instagram_username,
            access_token=access_token,
            token_expires_at=token_expires_at,
        )

        if set_as_active:
            if not telegram_chat_id:
                raise ValueError(
                    "telegram_chat_id required when set_as_active=True"
                )
            self.settings_repo.update(
                telegram_chat_id, active_instagram_account_id=str(account.id)
            )

        self.set_result_summary(
            run_id,
            {
                "account_id": str(account.id),
                "display_name": display_name,
                "username": instagram_username,
                "set_as_active": set_as_active,
            },
        )

        logger.info(
            f"Added Instagram account: {display_name} (@{instagram_username})"
        )

        return account
```

The method drops from 100 lines to ~45 lines. The parameter count stays at 8 (which is acceptable since `set_as_active` and `telegram_chat_id` are truly optional behavior toggles), but the method body is now easy to follow.

---

## Target 5: `CloudStorageService.upload_media()` -- 100 Lines to Extracted Helpers

### Current Code (`src/services/integrations/cloud_storage.py:58-158`)

The method handles four concerns:
1. File validation (lines 88-102)
2. Upload options preparation (lines 105-115)
3. Executing the upload (lines 119-135)
4. Building the result dict (lines 126-148)

### Step 1: Extract `_validate_file_path()`

```python
def _validate_file_path(self, file_path: str) -> Path:
    """
    Validate file exists and is a regular file.

    Args:
        file_path: Local path to media file

    Returns:
        Path object

    Raises:
        MediaUploadError: If file not found or not a file
    """
    path = Path(file_path)

    if not path.exists():
        raise MediaUploadError(
            f"File not found: {file_path}",
            file_path=file_path,
            provider="cloudinary",
        )

    if not path.is_file():
        raise MediaUploadError(
            f"Path is not a file: {file_path}",
            file_path=file_path,
            provider="cloudinary",
        )

    return path
```

### Step 2: Extract `_build_upload_options()`

```python
def _build_upload_options(
    self, path: Path, folder: str, public_id: Optional[str]
) -> dict:
    """Build the Cloudinary upload options dict."""
    resource_type = self._get_resource_type(path)

    options = {
        "folder": folder,
        "resource_type": resource_type,
        "overwrite": True,
    }

    if public_id:
        options["public_id"] = public_id

    return options
```

### Step 3: Simplify `upload_media()`

```python
def upload_media(
    self,
    file_path: str,
    folder: str = "storyline",
    public_id: Optional[str] = None,
) -> dict:
    """Upload media file to Cloudinary."""
    with self.track_execution(
        method_name="upload_media",
        input_params={"file_path": file_path, "folder": folder},
    ) as run_id:
        path = self._validate_file_path(file_path)
        upload_options = self._build_upload_options(path, folder, public_id)

        try:
            logger.info(f"Uploading {path.name} to Cloudinary ({folder}/)")

            result = cloudinary.uploader.upload(str(path), **upload_options)

            uploaded_at = datetime.utcnow()
            expires_at = uploaded_at + timedelta(
                hours=settings.CLOUD_UPLOAD_RETENTION_HOURS
            )

            upload_result = {
                "url": result["secure_url"],
                "public_id": result["public_id"],
                "uploaded_at": uploaded_at,
                "expires_at": expires_at,
                "size_bytes": result.get("bytes", 0),
                "format": result.get("format", ""),
                "width": result.get("width"),
                "height": result.get("height"),
            }

            logger.info(
                f"Successfully uploaded {path.name} to Cloudinary: {result['public_id']}"
            )

            self.set_result_summary(
                run_id,
                {
                    "success": True,
                    "public_id": result["public_id"],
                    "size_bytes": result.get("bytes", 0),
                },
            )

            return upload_result

        except cloudinary.exceptions.Error as e:
            logger.error(f"Cloudinary upload failed: {e}")
            raise MediaUploadError(
                f"Cloudinary upload failed: {e}",
                file_path=file_path,
                provider="cloudinary",
            )
```

This reduces `upload_media()` from 100 lines to ~50 lines.

---

## Verification Checklist

After making all changes:

- [ ] Run `ruff check src/repositories/history_repository.py src/services/core/scheduler.py src/services/core/instagram_account_service.py src/services/integrations/cloud_storage.py src/services/core/posting.py src/services/core/telegram_callbacks.py src/services/core/telegram_autopost.py`
- [ ] Run `ruff format src/repositories/history_repository.py src/services/core/scheduler.py src/services/core/instagram_account_service.py src/services/integrations/cloud_storage.py src/services/core/posting.py src/services/core/telegram_callbacks.py src/services/core/telegram_autopost.py`
- [ ] Run `pytest` -- all existing tests must pass
- [ ] Verify `HistoryCreateParams` import works in all three call-site files
- [ ] Verify `_fill_schedule_slots()` is called from both `create_schedule()` and `extend_schedule()`
- [ ] Grep for `history_repo.create(` -- every occurrence should now pass a `HistoryCreateParams` object, never bare kwargs
- [ ] Verify no new test files are needed (the public API is unchanged in behavior; only internal structure changed)
- [ ] Verify `_validate_new_account` raises `ValueError` with the same messages as the original inline code
- [ ] Run the existing scheduler category allocation tests: `pytest tests/src/services/test_scheduler.py::TestSchedulerCategoryAllocation -v` -- these must still pass

---

## What NOT To Do

1. **Do NOT change the `PostingHistory` model.** The dataclass is a repository-layer convenience, not an ORM change.
2. **Do NOT change the behavior of any extracted function.** Every extraction must be a pure refactor -- same inputs produce the same outputs.
3. **Do NOT add new parameters to `HistoryCreateParams` beyond what `create()` currently accepts.** The goal is to bundle existing parameters, not expand the interface.
4. **Do NOT remove the `track_execution` context managers.** They are required for observability.
5. **Do NOT extract the `_select_media_from_pool()` method further.** It is already well-isolated and contains necessary SQLAlchemy query logic that does not benefit from further splitting.
6. **Do NOT create a separate file for `HistoryCreateParams`.** It belongs in `history_repository.py` directly above the class that uses it, keeping the data transfer object co-located with its consumer.
7. **Do NOT refactor `health_check.py`.** On review, `_check_instagram_api()` (lines 89-164) is long but each branch is a simple conditional return. Extracting sub-functions would scatter the logic without improving clarity. Leave it as-is.
