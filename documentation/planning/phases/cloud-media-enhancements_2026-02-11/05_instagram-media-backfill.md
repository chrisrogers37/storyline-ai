# Phase 05: Instagram Media Backfill

**Status**: 🔧 IN PROGRESS
**Started**: 2026-02-12

**PR Title**: feat: add Instagram media backfill service
**Risk Level**: Medium (new external API integration with rate limits, media download, and storage)
**Estimated Effort**: Large (6 new files, 6 modified files, ~38 new tests)
**Branch**: `enhance/cloud-media-enhancements/phase-05-instagram-backfill`

---

## Context

The first four phases established a provider abstraction layer, Google Drive integration, a scheduled sync engine, and Telegram UI controls for media syncing. These phases addressed the forward-looking workflow: "bring new media into the system, then post it."

Phase 05 addresses the reverse workflow: "pull media that was already posted to Instagram back into the system." This is the "backfill" concept the user described as "insanely helpful." It enables post recycling -- old stories and feed posts can be re-surfaced through the scheduling system for reposting.

**User intent**: "A user could use the Instagram API to save their past media into the storage (backfill) and then add new posts in incrementals."

**Important API limitations**:
- The Instagram Graph API `GET /{ig-user-id}/media` endpoint returns **only feed posts** (photos, videos, carousels, reels). It does NOT return expired stories.
- The `GET /{ig-user-id}/stories` endpoint only returns stories that are **currently live** (within the last 24 hours). Historical stories are NOT available via API.
- `media_url` values returned by the API are **temporary** -- they expire after a short time (typically a few hours). Media must be downloaded promptly after fetching metadata.
- Rate limit: approximately 200 API calls per user per hour on the Graph API (separate from the publishing rate limit of 25/hour).
- Pagination: The media endpoint uses cursor-based pagination with `after` tokens.

**Practical scope**: This feature will primarily backfill **feed posts** (photos, videos, carousels). Stories backfill is limited to whatever is currently live (last 24 hours). The CLI and Telegram command should clearly communicate this limitation.

---

## Dependencies

- **Depends on**: Phase 01 (Provider Abstraction -- `MediaSourceProvider`, `MediaSourceFactory`, migration 011 `source_type`/`source_identifier` on `media_items`), Phase 02 (Google Drive Provider -- for storage target option), existing `InstagramAPIService` and `TokenRefreshService` (for authentication and token management), existing `InstagramAccountService` (for multi-account support)
- **Unlocks**: Content recycling workflows, media library enrichment from past posting history, future analytics correlation (linking backfilled media to historical performance metrics)

---

## Detailed Implementation Plan

### Step 1: Database Migration -- Add Backfill Tracking Columns

We need a way to track which Instagram media IDs have already been backfilled to avoid duplicate downloads. We add an `instagram_media_id` column to `media_items` for this purpose, plus a `backfilled_at` timestamp.

#### New File: `scripts/migrations/013_media_backfill_columns.sql`

```sql
-- Migration 013: Add Instagram backfill tracking columns to media_items
-- Phase 05 of cloud media enhancement
--
-- Adds instagram_media_id and backfilled_at columns to media_items.
-- These columns track which items were imported from Instagram's API
-- and prevent duplicate backfill downloads.
--
-- instagram_media_id: The Instagram Graph API media ID (e.g., "17841405793087218")
-- backfilled_at: When this item was backfilled from Instagram (NULL = not backfilled)

BEGIN;

-- Add backfill tracking columns
ALTER TABLE media_items
    ADD COLUMN instagram_media_id TEXT,
    ADD COLUMN backfilled_at TIMESTAMP;

-- Index for duplicate prevention during backfill
CREATE UNIQUE INDEX idx_media_items_instagram_media_id
    ON media_items (instagram_media_id)
    WHERE instagram_media_id IS NOT NULL;

-- Record migration
INSERT INTO schema_version (version, description, applied_at)
VALUES (13, 'Add Instagram backfill tracking columns (instagram_media_id, backfilled_at)', NOW());

COMMIT;
```

**Design notes**:
- The `instagram_media_id` column gets a partial unique index (only on non-NULL values) to prevent duplicate backfills while allowing the vast majority of existing records (which have NULL) to coexist without constraint violations.
- `backfilled_at` is a timestamp so we can track when the backfill occurred, useful for audit and debugging.

#### Modify: `/Users/chris/Projects/storyline-ai/src/models/media_item.py`

**Current code (lines 53-58):**
```python
    # Cloud storage (Phase 2 - temporary uploads for Instagram API)
    cloud_url = Column(Text)  # Cloudinary URL for Instagram API posting
    cloud_public_id = Column(Text)  # Cloudinary public_id for deletion
    cloud_uploaded_at = Column(DateTime)  # When uploaded to cloud
    cloud_expires_at = Column(DateTime)  # When cloud URL expires
```

**New code (replace lines 53-58):**
```python
    # Cloud storage (Phase 2 - temporary uploads for Instagram API)
    cloud_url = Column(Text)  # Cloudinary URL for Instagram API posting
    cloud_public_id = Column(Text)  # Cloudinary public_id for deletion
    cloud_uploaded_at = Column(DateTime)  # When uploaded to cloud
    cloud_expires_at = Column(DateTime)  # When cloud URL expires

    # Instagram backfill tracking (Phase 05 Cloud Media)
    instagram_media_id = Column(Text, unique=True, index=True)  # Instagram Graph API media ID
    backfilled_at = Column(DateTime)  # When this item was backfilled from Instagram
```

No new imports needed -- `Text`, `DateTime`, and `Column` are already imported.

---

### Step 2: Repository Additions

#### Modify: `/Users/chris/Projects/storyline-ai/src/repositories/media_repository.py`

Add two new methods for backfill duplicate prevention.

**New method 1: `get_by_instagram_media_id()`**

```python
    def get_by_instagram_media_id(self, instagram_media_id: str) -> Optional[MediaItem]:
        """Get media item by Instagram Graph API media ID.

        Used by InstagramBackfillService to check if an Instagram media item
        has already been backfilled into the system.

        Args:
            instagram_media_id: Instagram Graph API media ID (e.g., "17841405793087218")

        Returns:
            MediaItem if found, None otherwise
        """
        return (
            self.db.query(MediaItem)
            .filter(MediaItem.instagram_media_id == instagram_media_id)
            .first()
        )
```

**New method 2: `get_backfilled_instagram_media_ids()`**

```python
    def get_backfilled_instagram_media_ids(self) -> set:
        """Get all Instagram media IDs that have been backfilled.

        Returns a set for O(1) lookup during backfill operations.
        This avoids N+1 queries when checking each item during batch backfill.

        Returns:
            Set of Instagram media ID strings
        """
        results = (
            self.db.query(MediaItem.instagram_media_id)
            .filter(MediaItem.instagram_media_id.isnot(None))
            .all()
        )
        self.end_read_transaction()
        return {r[0] for r in results}
```

---

### Step 3: Backfill Exceptions

#### New File: `/Users/chris/Projects/storyline-ai/src/exceptions/backfill.py`

```python
"""Instagram backfill related exceptions."""

from typing import Optional

from src.exceptions.base import StorylineError


class BackfillError(StorylineError):
    """General error during Instagram media backfill."""

    def __init__(
        self,
        message: str,
        instagram_media_id: Optional[str] = None,
    ):
        super().__init__(message)
        self.instagram_media_id = instagram_media_id

    def __str__(self) -> str:
        base = super().__str__()
        if self.instagram_media_id:
            return f"{base} (media_id: {self.instagram_media_id})"
        return base


class BackfillMediaExpiredError(BackfillError):
    """Instagram media URL has expired before download completed."""

    def __init__(
        self,
        message: str = "Instagram media URL has expired",
        **kwargs,
    ):
        super().__init__(message, **kwargs)


class BackfillMediaNotFoundError(BackfillError):
    """Instagram media item was not found or is no longer accessible."""

    def __init__(
        self,
        message: str = "Instagram media not found",
        **kwargs,
    ):
        super().__init__(message, **kwargs)
```

#### Modify: `/Users/chris/Projects/storyline-ai/src/exceptions/__init__.py`

**Current code:**
```python
"""Storyline AI exception classes."""

from src.exceptions.base import StorylineError
from src.exceptions.instagram import (
    InstagramAPIError,
    RateLimitError,
    TokenExpiredError,
    MediaUploadError,
)

__all__ = [
    "StorylineError",
    "InstagramAPIError",
    "RateLimitError",
    "TokenExpiredError",
    "MediaUploadError",
]
```

**New code (replace entire file):**
```python
"""Storyline AI exception classes."""

from src.exceptions.base import StorylineError
from src.exceptions.instagram import (
    InstagramAPIError,
    RateLimitError,
    TokenExpiredError,
    MediaUploadError,
)
from src.exceptions.backfill import (
    BackfillError,
    BackfillMediaExpiredError,
    BackfillMediaNotFoundError,
)

__all__ = [
    "StorylineError",
    "InstagramAPIError",
    "RateLimitError",
    "TokenExpiredError",
    "MediaUploadError",
    "BackfillError",
    "BackfillMediaExpiredError",
    "BackfillMediaNotFoundError",
]
```

---

### Step 4: InstagramBackfillService (Core Implementation)

#### New File: `/Users/chris/Projects/storyline-ai/src/services/integrations/instagram_backfill.py`

```python
"""Instagram media backfill service - pull existing media from Instagram into the system."""

import hashlib
import mimetypes
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

from src.services.base_service import BaseService
from src.services.integrations.instagram_api import InstagramAPIService
from src.repositories.media_repository import MediaRepository
from src.config.settings import settings
from src.exceptions import (
    BackfillError,
    BackfillMediaExpiredError,
    BackfillMediaNotFoundError,
    InstagramAPIError,
    RateLimitError,
    TokenExpiredError,
)
from src.utils.logger import logger


@dataclass
class BackfillResult:
    """Tracks the outcome of an Instagram backfill operation.

    Attributes:
        downloaded: Number of media items successfully downloaded and indexed
        skipped_duplicate: Number skipped because they already exist in the database
        skipped_unsupported: Number skipped due to unsupported media type
        failed: Number of items that failed to download or process
        total_api_items: Total number of items returned by the Instagram API
        error_details: List of error description strings (capped at 20)
        dry_run: Whether this was a dry-run (no actual downloads)
    """

    downloaded: int = 0
    skipped_duplicate: int = 0
    skipped_unsupported: int = 0
    failed: int = 0
    total_api_items: int = 0
    error_details: list[str] = field(default_factory=list)
    dry_run: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for result summary storage."""
        result = {
            "downloaded": self.downloaded,
            "skipped_duplicate": self.skipped_duplicate,
            "skipped_unsupported": self.skipped_unsupported,
            "failed": self.failed,
            "total_api_items": self.total_api_items,
            "dry_run": self.dry_run,
        }
        if self.error_details:
            result["error_details"] = self.error_details[:20]
        return result

    @property
    def total_processed(self) -> int:
        """Total items that were evaluated."""
        return (
            self.downloaded
            + self.skipped_duplicate
            + self.skipped_unsupported
            + self.failed
        )


class InstagramBackfillService(BaseService):
    """Pull existing media from Instagram back into the media library.

    Uses the Instagram Graph API to fetch a user's media history (feed posts),
    downloads the media files, stores them to the configured media directory,
    and indexes them in the database.

    Important API constraints:
    - GET /{user-id}/media returns feed posts only (photos, videos, carousels, reels)
    - GET /{user-id}/stories returns only LIVE stories (last 24 hours)
    - media_url values expire after a few hours -- download promptly
    - Rate limit: ~200 API calls/user/hour
    - Pagination: cursor-based with 'after' token
    """

    # Instagram Graph API configuration
    META_GRAPH_BASE = "https://graph.facebook.com/v18.0"

    # Fields to request from the media endpoint
    MEDIA_FIELDS = (
        "id,media_type,media_url,thumbnail_url,timestamp,"
        "caption,permalink,username"
    )

    # Supported media types for backfill
    SUPPORTED_MEDIA_TYPES = {"IMAGE", "VIDEO"}

    # CAROUSEL_ALBUM is fetched but we download its children individually
    CAROUSEL_TYPE = "CAROUSEL_ALBUM"
    CAROUSEL_CHILDREN_FIELDS = "id,media_type,media_url,timestamp"

    # Download configuration
    DOWNLOAD_TIMEOUT = 120.0  # seconds (videos can be large)
    API_TIMEOUT = 30.0
    MAX_PAGES = 100  # Safety limit to prevent infinite pagination
    DEFAULT_PAGE_SIZE = 25

    # Backfill storage subdirectory
    BACKFILL_CATEGORY = "instagram_backfill"

    def __init__(self):
        super().__init__()
        self.instagram_service = InstagramAPIService()
        self.media_repo = MediaRepository()

    async def backfill(
        self,
        telegram_chat_id: Optional[int] = None,
        limit: Optional[int] = None,
        media_type: str = "feed",
        since: Optional[datetime] = None,
        dry_run: bool = False,
        account_id: Optional[str] = None,
        triggered_by: str = "cli",
    ) -> BackfillResult:
        """Run Instagram media backfill.

        Fetches the user's media from Instagram Graph API, downloads each
        item, stores it to the local media directory, and indexes it in
        the database.

        Args:
            telegram_chat_id: Chat to get active account for.
                Defaults to ADMIN_TELEGRAM_CHAT_ID.
            limit: Maximum number of items to backfill (None = all available).
            media_type: Type of media to backfill:
                'feed' = feed posts only (default, most useful)
                'stories' = live stories only (last 24 hours)
                'both' = feed + live stories
            since: Only backfill media newer than this date (None = all).
            dry_run: If True, fetch and count but don't download.
            account_id: Specific Instagram account UUID to use.
            triggered_by: Who triggered the backfill ('cli', 'telegram', 'system').

        Returns:
            BackfillResult with counts for each outcome.

        Raises:
            BackfillError: If backfill cannot proceed (no credentials, etc.)
            TokenExpiredError: If Instagram token is invalid.
        """
        if telegram_chat_id is None:
            telegram_chat_id = settings.ADMIN_TELEGRAM_CHAT_ID

        with self.track_execution(
            method_name="backfill",
            triggered_by=triggered_by,
            input_params={
                "limit": limit,
                "media_type": media_type,
                "since": since.isoformat() if since else None,
                "dry_run": dry_run,
                "account_id": account_id,
            },
        ) as run_id:
            result = BackfillResult(dry_run=dry_run)

            # Get credentials
            token, ig_account_id, username = self._get_credentials(
                telegram_chat_id, account_id
            )

            logger.info(
                f"[InstagramBackfillService] Starting backfill for @{username or ig_account_id} "
                f"(type={media_type}, limit={limit}, dry_run={dry_run})"
            )

            # Pre-load known Instagram media IDs for O(1) duplicate checks
            known_ig_ids = self.media_repo.get_backfilled_instagram_media_ids()
            logger.info(
                f"[InstagramBackfillService] {len(known_ig_ids)} existing backfilled items in DB"
            )

            # Ensure backfill storage directory exists
            storage_dir = self._get_storage_dir()
            if not dry_run:
                storage_dir.mkdir(parents=True, exist_ok=True)

            # Fetch and process media
            if media_type in ("feed", "both"):
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

            if media_type in ("stories", "both"):
                await self._backfill_stories(
                    token=token,
                    ig_account_id=ig_account_id,
                    username=username,
                    limit=limit if media_type == "stories" else None,
                    dry_run=dry_run,
                    known_ig_ids=known_ig_ids,
                    storage_dir=storage_dir,
                    result=result,
                )

            logger.info(
                f"[InstagramBackfillService] Backfill complete: "
                f"{result.downloaded} downloaded, "
                f"{result.skipped_duplicate} duplicates, "
                f"{result.skipped_unsupported} unsupported, "
                f"{result.failed} failed "
                f"(total API items: {result.total_api_items})"
            )

            self.set_result_summary(run_id, result.to_dict())
            return result

    def _get_credentials(
        self,
        telegram_chat_id: int,
        account_id: Optional[str] = None,
    ) -> tuple[str, str, Optional[str]]:
        """Get Instagram API credentials for backfill.

        Args:
            telegram_chat_id: Chat to get active account for.
            account_id: Specific account UUID to use (overrides active).

        Returns:
            Tuple of (token, instagram_account_id, username).

        Raises:
            BackfillError: If no credentials available.
            TokenExpiredError: If token is expired.
        """
        if account_id:
            account = self.instagram_service.account_service.get_account_by_id(
                account_id
            )
            if not account:
                raise BackfillError(f"Instagram account not found: {account_id}")

            token_record = self.instagram_service.token_repo.get_token_for_account(
                account_id, token_type="access_token"
            )
            if not token_record or token_record.is_expired:
                raise TokenExpiredError(
                    f"No valid token for account {account.display_name}"
                )

            decrypted_token = self.instagram_service.encryption.decrypt(
                token_record.token_value
            )
            return (
                decrypted_token,
                account.instagram_account_id,
                account.instagram_username,
            )

        # Use active account credentials (same pattern as InstagramAPIService)
        token, ig_id, username = (
            self.instagram_service._get_active_account_credentials(telegram_chat_id)
        )

        if not token:
            raise BackfillError(
                "No valid Instagram token available. "
                "Configure an account via CLI or /settings."
            )

        if not ig_id:
            raise BackfillError(
                "No Instagram account configured. "
                "Use /settings to select one or add via CLI."
            )

        return (token, ig_id, username)

    async def _backfill_feed(
        self,
        token: str,
        ig_account_id: str,
        username: Optional[str],
        limit: Optional[int],
        since: Optional[datetime],
        dry_run: bool,
        known_ig_ids: set,
        storage_dir: Path,
        result: BackfillResult,
    ) -> None:
        """Fetch and process feed media from Instagram API.

        Handles cursor-based pagination through GET /{user-id}/media.
        """
        items_remaining = limit
        after_cursor = None

        for page_num in range(self.MAX_PAGES):
            page_size = self.DEFAULT_PAGE_SIZE
            if items_remaining is not None:
                page_size = min(page_size, items_remaining)
                if page_size <= 0:
                    break

            media_page = await self._fetch_media_page(
                token=token,
                ig_account_id=ig_account_id,
                after_cursor=after_cursor,
                page_size=page_size,
            )

            items = media_page.get("data", [])
            if not items:
                break

            result.total_api_items += len(items)
            logger.info(
                f"[InstagramBackfillService] Feed page {page_num + 1}: "
                f"{len(items)} items"
            )

            for item in items:
                # Check date filter
                if since and not self._is_after_date(item, since):
                    logger.info(
                        f"[InstagramBackfillService] Reached items older than "
                        f"{since.isoformat()}, stopping."
                    )
                    return

                await self._process_media_item(
                    item=item,
                    token=token,
                    username=username,
                    dry_run=dry_run,
                    known_ig_ids=known_ig_ids,
                    storage_dir=storage_dir,
                    result=result,
                    source_label="feed",
                )

                if items_remaining is not None:
                    items_remaining -= 1
                    if items_remaining <= 0:
                        return

            paging = media_page.get("paging", {})
            after_cursor = paging.get("cursors", {}).get("after")
            if not after_cursor or "next" not in paging:
                break

    async def _backfill_stories(
        self,
        token: str,
        ig_account_id: str,
        username: Optional[str],
        limit: Optional[int],
        dry_run: bool,
        known_ig_ids: set,
        storage_dir: Path,
        result: BackfillResult,
    ) -> None:
        """Fetch and process live stories (last 24 hours only).

        Uses GET /{user-id}/stories. Note: this only returns stories
        that are currently live, NOT historical stories.
        """
        try:
            stories_data = await self._fetch_stories(
                token=token,
                ig_account_id=ig_account_id,
            )
        except InstagramAPIError as e:
            logger.warning(
                f"[InstagramBackfillService] Stories fetch failed: {e}. "
                f"This is expected if the account has no live stories."
            )
            return

        items = stories_data.get("data", [])
        if not items:
            logger.info(
                "[InstagramBackfillService] No live stories found (stories "
                "are only available for 24 hours via API)"
            )
            return

        result.total_api_items += len(items)
        logger.info(
            f"[InstagramBackfillService] Found {len(items)} live stories"
        )

        items_remaining = limit
        for item in items:
            if items_remaining is not None and items_remaining <= 0:
                break

            await self._process_media_item(
                item=item,
                token=token,
                username=username,
                dry_run=dry_run,
                known_ig_ids=known_ig_ids,
                storage_dir=storage_dir,
                result=result,
                source_label="story",
            )

            if items_remaining is not None:
                items_remaining -= 1

    async def _process_media_item(
        self,
        item: dict,
        token: str,
        username: Optional[str],
        dry_run: bool,
        known_ig_ids: set,
        storage_dir: Path,
        result: BackfillResult,
        source_label: str,
    ) -> None:
        """Process a single Instagram media item.

        Decision tree:
        1. Check for duplicate via instagram_media_id
        2. Handle carousel albums (expand to children)
        3. Check if media type is supported
        4. Download and index (or preview in dry-run)
        """
        ig_media_id = item.get("id")
        media_type = item.get("media_type", "")

        # Check for duplicate
        if ig_media_id in known_ig_ids:
            result.skipped_duplicate += 1
            return

        # Handle carousel albums -- expand to children
        if media_type == self.CAROUSEL_TYPE:
            await self._process_carousel(
                item=item,
                token=token,
                username=username,
                dry_run=dry_run,
                known_ig_ids=known_ig_ids,
                storage_dir=storage_dir,
                result=result,
            )
            return

        # Check if media type is supported
        if media_type not in self.SUPPORTED_MEDIA_TYPES:
            result.skipped_unsupported += 1
            return

        # Get media URL
        media_url = item.get("media_url")
        if not media_url and media_type == "VIDEO":
            media_url = item.get("thumbnail_url")

        if not media_url:
            result.failed += 1
            result.error_details.append(
                f"No media_url for {ig_media_id} ({media_type})"
            )
            return

        if dry_run:
            result.downloaded += 1
            known_ig_ids.add(ig_media_id)
            logger.info(
                f"[InstagramBackfillService] [DRY RUN] Would download: "
                f"{ig_media_id} ({media_type}, {source_label})"
            )
            return

        # Download and index
        try:
            await self._download_and_index(
                ig_media_id=ig_media_id,
                media_url=media_url,
                media_type=media_type,
                item=item,
                username=username,
                storage_dir=storage_dir,
                source_label=source_label,
            )
            result.downloaded += 1
            known_ig_ids.add(ig_media_id)
        except Exception as e:
            result.failed += 1
            error_msg = f"Failed to download {ig_media_id}: {e}"
            result.error_details.append(error_msg)
            logger.error(f"[InstagramBackfillService] {error_msg}")

    async def _process_carousel(
        self,
        item: dict,
        token: str,
        username: Optional[str],
        dry_run: bool,
        known_ig_ids: set,
        storage_dir: Path,
        result: BackfillResult,
    ) -> None:
        """Expand a carousel album and process each child media item."""
        carousel_id = item.get("id")
        logger.info(
            f"[InstagramBackfillService] Expanding carousel: {carousel_id}"
        )

        try:
            children_data = await self._fetch_carousel_children(
                token=token,
                carousel_id=carousel_id,
            )
        except InstagramAPIError as e:
            result.failed += 1
            result.error_details.append(
                f"Failed to expand carousel {carousel_id}: {e}"
            )
            return

        children = children_data.get("data", [])
        for child in children:
            result.total_api_items += 1

            # Inherit caption and permalink from parent
            child.setdefault("caption", item.get("caption"))
            child.setdefault("permalink", item.get("permalink"))
            child.setdefault("username", item.get("username"))

            await self._process_media_item(
                item=child,
                token=token,
                username=username,
                dry_run=dry_run,
                known_ig_ids=known_ig_ids,
                storage_dir=storage_dir,
                result=result,
                source_label="carousel",
            )

    async def _download_and_index(
        self,
        ig_media_id: str,
        media_url: str,
        media_type: str,
        item: dict,
        username: Optional[str],
        storage_dir: Path,
        source_label: str,
    ) -> None:
        """Download media from Instagram and index in the database.

        Args:
            ig_media_id: Instagram media ID
            media_url: URL to download media from (temporary, may expire)
            media_type: IMAGE or VIDEO
            item: Full API response item (for metadata)
            username: Instagram username for folder organization
            storage_dir: Local directory to save media
            source_label: 'feed', 'story', or 'carousel'
        """
        # Download media bytes
        file_bytes = await self._download_media(media_url, ig_media_id)

        # Determine filename and extension
        extension = self._get_extension_for_type(media_type, media_url)
        timestamp = item.get("timestamp", "")
        date_prefix = ""
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                date_prefix = dt.strftime("%Y%m%d_%H%M%S_")
            except (ValueError, TypeError):
                pass

        filename = f"{date_prefix}{ig_media_id}{extension}"
        file_path = storage_dir / filename

        # Write to disk
        file_path.write_bytes(file_bytes)

        # Calculate content hash
        file_hash = hashlib.sha256(file_bytes).hexdigest()

        # Determine MIME type
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if not mime_type:
            mime_type = "image/jpeg" if media_type == "IMAGE" else "video/mp4"

        # Index in database
        self.media_repo.create(
            file_path=str(file_path),
            file_name=filename,
            file_hash=file_hash,
            file_size_bytes=len(file_bytes),
            mime_type=mime_type,
            category=self.BACKFILL_CATEGORY,
            source_type="instagram_backfill",
            source_identifier=ig_media_id,
        )

        # Update the instagram_media_id and backfilled_at on the newly created record
        media_item = self.media_repo.get_by_source_identifier(
            "instagram_backfill", ig_media_id
        )
        if media_item:
            media_item.instagram_media_id = ig_media_id
            media_item.backfilled_at = datetime.utcnow()
            self.media_repo.db.commit()

        logger.info(
            f"[InstagramBackfillService] Downloaded and indexed: "
            f"{filename} ({media_type}, {source_label})"
        )

    # ==================== API Calls ====================

    async def _fetch_media_page(
        self,
        token: str,
        ig_account_id: str,
        after_cursor: Optional[str] = None,
        page_size: int = 25,
    ) -> dict:
        """Fetch a page of media from GET /{user-id}/media."""
        params = {
            "fields": self.MEDIA_FIELDS,
            "limit": page_size,
            "access_token": token,
        }
        if after_cursor:
            params["after"] = after_cursor

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.META_GRAPH_BASE}/{ig_account_id}/media",
                params=params,
                timeout=self.API_TIMEOUT,
            )

            self.instagram_service._check_response_errors(response)
            return response.json()

    async def _fetch_stories(
        self,
        token: str,
        ig_account_id: str,
    ) -> dict:
        """Fetch live stories from GET /{user-id}/stories.

        Returns only stories from the last 24 hours.
        """
        params = {
            "fields": self.MEDIA_FIELDS,
            "access_token": token,
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.META_GRAPH_BASE}/{ig_account_id}/stories",
                params=params,
                timeout=self.API_TIMEOUT,
            )

            self.instagram_service._check_response_errors(response)
            return response.json()

    async def _fetch_carousel_children(
        self,
        token: str,
        carousel_id: str,
    ) -> dict:
        """Fetch children of a carousel album.

        GET /{carousel-id}/children?fields=id,media_type,media_url,timestamp
        """
        params = {
            "fields": self.CAROUSEL_CHILDREN_FIELDS,
            "access_token": token,
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.META_GRAPH_BASE}/{carousel_id}/children",
                params=params,
                timeout=self.API_TIMEOUT,
            )

            self.instagram_service._check_response_errors(response)
            return response.json()

    async def _download_media(self, url: str, ig_media_id: str) -> bytes:
        """Download media bytes from an Instagram media URL.

        Args:
            url: Instagram media URL (temporary, may expire)
            ig_media_id: For error context

        Returns:
            Raw file bytes

        Raises:
            BackfillMediaExpiredError: If URL has expired (HTTP 403/410)
            BackfillError: If download fails for other reasons
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    timeout=self.DOWNLOAD_TIMEOUT,
                    follow_redirects=True,
                )

                if response.status_code in (403, 410):
                    raise BackfillMediaExpiredError(
                        f"Media URL expired for {ig_media_id} "
                        f"(HTTP {response.status_code})",
                        instagram_media_id=ig_media_id,
                    )

                if response.status_code == 404:
                    raise BackfillMediaNotFoundError(
                        f"Media not found for {ig_media_id}",
                        instagram_media_id=ig_media_id,
                    )

                if response.status_code != 200:
                    raise BackfillError(
                        f"Download failed for {ig_media_id}: "
                        f"HTTP {response.status_code}",
                        instagram_media_id=ig_media_id,
                    )

                content = response.content
                if not content:
                    raise BackfillError(
                        f"Empty response for {ig_media_id}",
                        instagram_media_id=ig_media_id,
                    )

                return content

        except httpx.RequestError as e:
            raise BackfillError(
                f"Network error downloading {ig_media_id}: {e}",
                instagram_media_id=ig_media_id,
            )

    # ==================== Helpers ====================

    def _get_storage_dir(self) -> Path:
        """Get the local directory to store backfilled media.

        Creates a subdirectory under MEDIA_DIR named 'instagram_backfill'.
        """
        return Path(settings.MEDIA_DIR) / self.BACKFILL_CATEGORY

    def _get_extension_for_type(self, media_type: str, url: str) -> str:
        """Determine file extension from media type and URL."""
        # Try to extract from URL
        try:
            url_path = url.split("?")[0]
            suffix = Path(url_path).suffix.lower()
            if suffix in {".jpg", ".jpeg", ".png", ".gif", ".mp4", ".mov", ".webp"}:
                return suffix
        except (ValueError, IndexError):
            pass

        # Fall back to media type
        if media_type == "VIDEO":
            return ".mp4"
        return ".jpg"

    def _is_after_date(self, item: dict, since: datetime) -> bool:
        """Check if an Instagram item's timestamp is after the 'since' date."""
        timestamp_str = item.get("timestamp", "")
        if not timestamp_str:
            return True

        try:
            item_dt = datetime.fromisoformat(
                timestamp_str.replace("Z", "+00:00")
            ).replace(tzinfo=None)
            return item_dt >= since
        except (ValueError, TypeError):
            return True

    def get_backfill_status(self) -> dict:
        """Get information about backfill history."""
        runs = self.service_run_repo.get_recent_runs(
            service_name="InstagramBackfillService", limit=5
        )

        backfilled_count = len(
            self.media_repo.get_backfilled_instagram_media_ids()
        )

        last_run = None
        if runs:
            run = runs[0]
            last_run = {
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "completed_at": (
                    run.completed_at.isoformat() if run.completed_at else None
                ),
                "success": run.success,
                "result": run.result_summary,
                "triggered_by": run.triggered_by,
            }

        return {
            "total_backfilled": backfilled_count,
            "last_run": last_run,
        }
```

**Key design decisions**:

1. **Reuses `InstagramAPIService._get_active_account_credentials()` and `_check_response_errors()`**: No credential management duplication.

2. **Carousel expansion**: Fetches children via `GET /{carousel-id}/children` and processes each individually.

3. **Date filter with early termination**: Instagram returns items newest-first. When encountering items older than `since`, we stop pagination entirely.

4. **`instagram_backfill` as source_type**: Uses a distinct source_type so the sync engine does not try to reconcile backfilled media against any provider.

5. **Local storage to `MEDIA_DIR/instagram_backfill/`**: Keeps backfilled media organized and acts as its own category.

6. **Content hash (SHA256)**: Matches the existing `file_hash` pattern, enabling cross-source dedup.

---

### Step 5: CLI Commands

#### New File: `/Users/chris/Projects/storyline-ai/cli/commands/backfill.py`

```python
"""Instagram backfill CLI commands."""

import asyncio
from datetime import datetime
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


@click.command(name="backfill-instagram")
@click.option(
    "--limit",
    type=int,
    default=None,
    help="Maximum number of items to backfill (default: all)",
)
@click.option(
    "--media-type",
    type=click.Choice(["feed", "stories", "both"]),
    default="feed",
    help="Type of media to backfill (default: feed)",
)
@click.option(
    "--since",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
    help="Only backfill media newer than this date (YYYY-MM-DD)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview what would be backfilled without downloading",
)
@click.option(
    "--account-id",
    type=str,
    default=None,
    help="Instagram account UUID to backfill from (default: active account)",
)
def backfill_instagram(
    limit: Optional[int],
    media_type: str,
    since: Optional[datetime],
    dry_run: bool,
    account_id: Optional[str],
):
    """Backfill media from Instagram into the local media library.

    Downloads previously posted media (feed posts, stories) from the
    Instagram Graph API and indexes them in the database. This enables
    post recycling -- old content can be re-surfaced through scheduling.

    NOTE: Stories are only available via the API for the last 24 hours.
    Feed posts are available as far back as the account's history.

    Examples:

        storyline-cli backfill-instagram

        storyline-cli backfill-instagram --limit 50

        storyline-cli backfill-instagram --dry-run

        storyline-cli backfill-instagram --since 2025-01-01

        storyline-cli backfill-instagram --account-id abc123...
    """
    from src.services.integrations.instagram_backfill import (
        InstagramBackfillService,
    )

    mode = "[yellow]DRY RUN[/yellow]" if dry_run else "[green]LIVE[/green]"
    console.print(
        Panel.fit(
            f"[bold blue]Instagram Media Backfill[/bold blue] ({mode})\n\n"
            f"Media type: {media_type}\n"
            f"Limit: {limit or 'all'}\n"
            f"Since: {since.strftime('%Y-%m-%d') if since else 'all time'}\n"
            f"Account: {account_id or 'active account'}",
            title="Storyline AI",
        )
    )

    if media_type in ("stories", "both"):
        console.print(
            "\n[yellow]Note:[/yellow] Stories are only available via the "
            "Instagram API for the last 24 hours. Historical stories "
            "cannot be retrieved.\n"
        )

    service = InstagramBackfillService()

    try:
        result = asyncio.run(
            service.backfill(
                limit=limit,
                media_type=media_type,
                since=since,
                dry_run=dry_run,
                account_id=account_id,
                triggered_by="cli",
            )
        )

        status = "[yellow]DRY RUN[/yellow]" if dry_run else "[bold green]Complete[/bold green]"
        console.print(f"\nBackfill {status}\n")

        table = Table(title="Backfill Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", justify="right")

        action = "Would download" if dry_run else "Downloaded"
        table.add_row(action, str(result.downloaded))
        table.add_row("Skipped (duplicate)", str(result.skipped_duplicate))
        table.add_row("Skipped (unsupported)", str(result.skipped_unsupported))
        table.add_row(
            "Failed",
            f"[red]{result.failed}[/red]" if result.failed > 0 else "0",
        )
        table.add_row("Total API items", str(result.total_api_items))

        console.print(table)

        if result.error_details:
            console.print("\n[yellow]Error details:[/yellow]")
            for detail in result.error_details[:10]:
                console.print(f"  - {detail}")

    except Exception as e:
        console.print(f"\n[red]Backfill failed:[/red] {e}")


@click.command(name="backfill-status")
def backfill_status():
    """Show Instagram backfill history and statistics."""
    from src.services.integrations.instagram_backfill import (
        InstagramBackfillService,
    )

    console.print("[bold blue]Instagram Backfill Status[/bold blue]\n")

    service = InstagramBackfillService()
    status = service.get_backfill_status()

    overview_table = Table(title="Overview")
    overview_table.add_column("Metric", style="cyan")
    overview_table.add_column("Value")
    overview_table.add_row(
        "Total Backfilled Items", str(status["total_backfilled"])
    )
    console.print(overview_table)

    last_run = status.get("last_run")
    if not last_run:
        console.print("\n[yellow]No backfill runs recorded yet.[/yellow]")
        console.print(
            "[dim]Run 'storyline-cli backfill-instagram --dry-run' "
            "to preview.[/dim]"
        )
        return

    console.print()

    run_table = Table(title="Last Backfill Run")
    run_table.add_column("Property", style="cyan")
    run_table.add_column("Value")

    run_table.add_row(
        "Status",
        "[green]Success[/green]" if last_run["success"] else "[red]Failed[/red]",
    )
    run_table.add_row("Started At", last_run.get("started_at", "N/A"))
    run_table.add_row("Completed At", last_run.get("completed_at", "N/A"))
    run_table.add_row("Triggered By", last_run.get("triggered_by", "N/A"))

    console.print(run_table)

    result = last_run.get("result")
    if result:
        console.print()
        detail_table = Table(title="Last Run Details")
        detail_table.add_column("Metric", style="cyan")
        detail_table.add_column("Count", justify="right")

        detail_table.add_row("Downloaded", str(result.get("downloaded", 0)))
        detail_table.add_row(
            "Skipped (duplicate)", str(result.get("skipped_duplicate", 0))
        )
        detail_table.add_row(
            "Skipped (unsupported)", str(result.get("skipped_unsupported", 0))
        )
        failed = result.get("failed", 0)
        detail_table.add_row(
            "Failed",
            f"[red]{failed}[/red]" if failed > 0 else "0",
        )
        detail_table.add_row(
            "Total API Items", str(result.get("total_api_items", 0))
        )
        detail_table.add_row(
            "Dry Run",
            "Yes" if result.get("dry_run") else "No",
        )

        console.print(detail_table)
```

#### Modify: `/Users/chris/Projects/storyline-ai/cli/main.py`

**Add import (after existing command imports):**

```python
from cli.commands.backfill import backfill_instagram, backfill_status
```

**Add commands to CLI group (after the last `cli.add_command` call):**

```python
cli.add_command(backfill_instagram)
cli.add_command(backfill_status)
```

---

### Step 6: Telegram `/backfill` Command

#### Modify: `/Users/chris/Projects/storyline-ai/src/services/core/telegram_commands.py`

**Add new method to `TelegramCommandHandlers` class (after `handle_sync`):**

```python
    async def handle_backfill(self, update, context):
        """Handle /backfill command -- trigger Instagram media backfill.

        Usage:
            /backfill          - Backfill all feed posts
            /backfill 50       - Backfill up to 50 items
            /backfill dry      - Preview without downloading
            /backfill 50 dry   - Preview up to 50 items
        """
        user = self.service._get_or_create_user(update.effective_user)
        chat_id = update.effective_chat.id

        # Parse optional arguments
        args = context.args or []
        limit = None
        dry_run = False

        for arg in args:
            if arg.isdigit():
                limit = int(arg)
            elif arg.lower() == "dry":
                dry_run = True

        mode = "DRY RUN" if dry_run else "LIVE"
        limit_str = str(limit) if limit else "all"

        status_msg = await update.message.reply_text(
            f"🔄 *Instagram Media Backfill* ({mode})\n\n"
            f"Fetching feed posts from Instagram...\n"
            f"Limit: {limit_str}\n\n"
            f"_This may take a while for large accounts._",
            parse_mode="Markdown",
        )

        try:
            from src.services.integrations.instagram_backfill import (
                InstagramBackfillService,
            )

            backfill_service = InstagramBackfillService()
            result = await backfill_service.backfill(
                telegram_chat_id=chat_id,
                limit=limit,
                media_type="feed",
                dry_run=dry_run,
                triggered_by="telegram",
            )

            action = "Would download" if dry_run else "Downloaded"
            status_emoji = "🏁" if not dry_run else "👀"

            lines = [
                f"{status_emoji} *Backfill {'Preview' if dry_run else 'Complete'}*\n",
                f"📥 {action}: {result.downloaded}",
                f"⏭️ Skipped (duplicate): {result.skipped_duplicate}",
                f"🚫 Skipped (unsupported): {result.skipped_unsupported}",
            ]

            if result.failed > 0:
                lines.append(f"❌ Failed: {result.failed}")

            lines.append(f"📊 Total API items: {result.total_api_items}")

            if result.error_details:
                lines.append("\n⚠️ *Errors:*")
                for e in result.error_details[:3]:
                    lines.append(f"  - {e[:80]}")

            await status_msg.edit_text(
                "\n".join(lines),
                parse_mode="Markdown",
            )

        except Exception as e:
            await status_msg.edit_text(
                f"❌ *Backfill failed*\n\n{str(e)[:200]}",
                parse_mode="Markdown",
            )
            logger.error(f"Backfill from Telegram failed: {e}", exc_info=True)

        self.service.interaction_service.log_command(
            user_id=str(user.id),
            command="/backfill",
            telegram_chat_id=chat_id,
            telegram_message_id=update.message.message_id,
        )
```

#### Modify: `/Users/chris/Projects/storyline-ai/src/services/core/telegram_service.py`

**Register `/backfill` in the command_map (after the `"sync"` entry):**

```python
            "backfill": self.commands.handle_backfill,
```

**Add to BotCommand autocomplete list (after the `sync` entry):**

```python
            BotCommand("backfill", "Backfill media from Instagram"),
```

**Update `/help` text in `telegram_commands.py` to include `/backfill`:**

Add under "Control Commands":
```python
            "/backfill - Backfill media from Instagram\n"
```

---

## Test Plan

### New Test File: `tests/src/services/test_instagram_backfill.py`

#### BackfillResult Tests (5 tests)

1. **`test_backfill_result_defaults`** -- All counters start at 0, `error_details` is empty, `dry_run` is False.
2. **`test_backfill_result_to_dict`** -- Converts correctly, caps error_details at 20.
3. **`test_backfill_result_to_dict_no_errors`** -- Omits `error_details` key when empty.
4. **`test_backfill_result_total_processed`** -- Sums `downloaded + skipped_duplicate + skipped_unsupported + failed`.
5. **`test_backfill_result_dry_run_flag`** -- Correctly stores dry_run=True.

#### Credential Resolution Tests (4 tests)

6. **`test_get_credentials_active_account`** -- Uses `_get_active_account_credentials` when no account_id.
7. **`test_get_credentials_specific_account`** -- Looks up account by ID when account_id provided.
8. **`test_get_credentials_no_token_raises`** -- Raises `BackfillError` when no token.
9. **`test_get_credentials_no_account_raises`** -- Raises `BackfillError` when no account.

#### Feed Backfill Tests (8 tests)

10. **`test_backfill_feed_downloads_images`** -- IMAGE items downloaded and indexed.
11. **`test_backfill_feed_skips_duplicates`** -- Items in `known_ig_ids` skipped.
12. **`test_backfill_feed_handles_pagination`** -- Multiple pages fetched via cursor.
13. **`test_backfill_feed_respects_limit`** -- Stops after `limit` items.
14. **`test_backfill_feed_respects_since_filter`** -- Stops at items older than `since`.
15. **`test_backfill_feed_dry_run_no_download`** -- dry_run=True, no download, counts updated.
16. **`test_backfill_feed_handles_videos`** -- VIDEO items produce `.mp4` files.
17. **`test_backfill_feed_empty_response`** -- Empty data array, no items processed.

#### Carousel Tests (3 tests)

18. **`test_backfill_carousel_expands_children`** -- CAROUSEL_ALBUM fetches children.
19. **`test_backfill_carousel_inherits_caption`** -- Children inherit parent caption.
20. **`test_backfill_carousel_child_failure_continues`** -- One child fails, others process.

#### Stories Tests (3 tests)

21. **`test_backfill_stories_fetches_live`** -- Calls stories endpoint.
22. **`test_backfill_stories_empty_ok`** -- No live stories, returns gracefully.
23. **`test_backfill_stories_api_error_handled`** -- API error caught and logged.

#### Download Tests (5 tests)

24. **`test_download_media_success`** -- Returns bytes on HTTP 200.
25. **`test_download_media_expired_url`** -- HTTP 403/410 raises `BackfillMediaExpiredError`.
26. **`test_download_media_not_found`** -- HTTP 404 raises `BackfillMediaNotFoundError`.
27. **`test_download_media_network_error`** -- `httpx.RequestError` raises `BackfillError`.
28. **`test_download_media_empty_response`** -- Empty body raises `BackfillError`.

#### Index & Storage Tests (4 tests)

29. **`test_download_and_index_creates_record`** -- `media_repo.create()` called with correct args.
30. **`test_download_and_index_filename_format`** -- Filename follows `YYYYMMDD_HHMMSS_{id}.{ext}`.
31. **`test_get_extension_for_type_image`** -- Returns `.jpg` for IMAGE.
32. **`test_get_extension_for_type_video`** -- Returns `.mp4` for VIDEO.

#### Helper Tests (3 tests)

33. **`test_is_after_date_newer`** -- Returns True for items newer than since.
34. **`test_is_after_date_older`** -- Returns False for items older than since.
35. **`test_get_storage_dir`** -- Returns `MEDIA_DIR/instagram_backfill`.

#### Status Tests (3 tests)

36. **`test_backfill_status_no_runs`** -- Returns `total_backfilled=0`, `last_run=None`.
37. **`test_backfill_status_with_history`** -- Returns correct counts and last run.
38. **`test_backfill_error_in_single_item_continues`** -- One fails, rest process.

### New Test File: `tests/src/exceptions/test_backfill_exceptions.py`

3 tests for the exception hierarchy:

39. **`test_backfill_error_str`** -- Includes `instagram_media_id` in string.
40. **`test_backfill_media_expired_error`** -- Inherits from `BackfillError`.
41. **`test_backfill_media_not_found_error`** -- Inherits from `BackfillError`.

### Updated Test File: `tests/src/repositories/test_media_repository.py`

42. **`test_get_by_instagram_media_id`** -- Returns item by Instagram ID.
43. **`test_get_backfilled_instagram_media_ids`** -- Returns set of all backfilled IDs.

---

## Documentation Updates

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Added

- **Instagram Media Backfill** - Pull existing media from Instagram back into the system
  - New `InstagramBackfillService` for fetching feed posts, live stories, and carousel albums from Instagram Graph API
  - New CLI commands: `backfill-instagram` (with --limit, --media-type, --since, --dry-run, --account-id), `backfill-status`
  - New Telegram command: `/backfill [limit] [dry]`
  - Carousel album expansion: downloads each child image/video individually
  - Cursor-based pagination for large media libraries
  - Duplicate prevention via `instagram_media_id` tracking column
  - Content-level dedup via SHA256 hash comparison
  - Date filtering with early termination (--since flag)
  - Dry-run mode for previewing without downloading
  - Multi-account support via --account-id flag
  - New exception hierarchy: `BackfillError`, `BackfillMediaExpiredError`, `BackfillMediaNotFoundError`
  - Database migration 013: `instagram_media_id` and `backfilled_at` columns on `media_items`
```

### CLAUDE.md Updates

- Add `backfill-instagram --dry-run` and `backfill-status` to "SAFE commands" section
- Add `/backfill` to the Telegram Bot Commands Reference table
- Add migration 013 to the migration history table

---

## Stress Testing & Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Account with 5000+ feed posts | Pagination handles up to MAX_PAGES=100 pages of 25 = 2500 items. Use `--limit` or `--since` for massive accounts. |
| Media URL expired between fetch and download | HTTP 403/410 caught, `BackfillMediaExpiredError` raised. Item counted as `failed`. Others continue. |
| Rate limit hit during backfill | `_check_response_errors()` raises `RateLimitError`. Backfill stops. Retry later or use `--limit`. |
| Token expires during long backfill | `TokenExpiredError` raised. Backfill stops. Refresh token and retry. |
| Duplicate backfill (running twice) | Second run skips all via `known_ig_ids` set. Result shows all `skipped_duplicate`. |
| Carousel with 10 children | All 10 fetched and processed individually. |
| Video file (50MB+) | `DOWNLOAD_TIMEOUT=120s` handles large files. |
| Empty feed (new account) | Empty data array. All zeros in result. |
| Disk full during download | `write_bytes()` raises `OSError`. Caught per-item, counted as `failed`. |
| MEDIA_DIR does not exist | `mkdir(parents=True, exist_ok=True)` creates it. |
| `--dry-run` mode | No files downloaded, no DB records. Counts only. |
| `--since` with future date | No items match. All zeros. |

---

## Verification Checklist

- [ ] Migration `013` applies cleanly on dev database
- [ ] Existing media items have `instagram_media_id = NULL` after migration
- [ ] Partial unique index prevents duplicate `instagram_media_id` values
- [ ] `storyline-cli backfill-instagram --help` shows all options
- [ ] `storyline-cli backfill-status` shows "No runs recorded yet" initially
- [ ] `storyline-cli backfill-instagram --dry-run` completes without downloading
- [ ] `storyline-cli backfill-instagram --limit 5` downloads exactly 5 items
- [ ] Downloaded files appear in `MEDIA_DIR/instagram_backfill/`
- [ ] Filename format: `YYYYMMDD_HHMMSS_{ig_media_id}.{ext}`
- [ ] DB records have `source_type='instagram_backfill'` and `instagram_media_id` populated
- [ ] Running backfill twice skips all previously downloaded items
- [ ] Carousel albums expand to individual child images
- [ ] `--since 2025-01-01` only downloads posts from 2025 onwards
- [ ] Telegram `/backfill` command works and shows results
- [ ] Telegram `/backfill dry` shows preview
- [ ] Telegram `/backfill 10` limits to 10 items
- [ ] `backfill-status` shows correct totals after a run
- [ ] All 43+ tests pass
- [ ] `ruff check src/ tests/ cli/` passes
- [ ] `ruff format --check src/ tests/ cli/` passes
- [ ] CHANGELOG.md updated

---

## What NOT To Do

1. **Do NOT try to retrieve historical stories.** The Instagram Graph API only returns stories from the last 24 hours. Do not attempt workarounds or scraping.

2. **Do NOT store Instagram media URLs in `media_items`.** They are temporary and expire. Only store downloaded bytes. The `instagram_media_id` is safe (public identifier).

3. **Do NOT bypass `InstagramAPIService._check_response_errors()`.** Reuse it for consistent error classification.

4. **Do NOT run backfill automatically on a schedule.** This is on-demand only. NOT added to any background loop.

5. **Do NOT delete or modify existing `media_items` during backfill.** Purely additive. Duplicates are skipped, not updated.

6. **Do NOT download to temporary locations.** Write directly to `MEDIA_DIR/instagram_backfill/`.

7. **Do NOT use `MediaIngestionService.scan_directory()` after backfill.** The backfill service handles indexing directly.

8. **Do NOT add `instagram_backfill` category to `category_post_case_mix`.** It's an organizational label. Users can reassign later.

9. **Do NOT make `BackfillResult` extend `SyncResult`.** Different operations, different semantics.

10. **Do NOT stream media to disk.** Load into memory then write. Consistent with provider pattern and acceptable for Instagram media sizes.

---

## Files Summary

### New Files (6)

| File | Purpose |
|------|---------|
| `src/services/integrations/instagram_backfill.py` | InstagramBackfillService + BackfillResult |
| `src/exceptions/backfill.py` | Exception hierarchy (3 classes) |
| `cli/commands/backfill.py` | CLI: backfill-instagram, backfill-status |
| `scripts/migrations/013_media_backfill_columns.sql` | DB migration |
| `tests/src/services/test_instagram_backfill.py` | Service tests (~38 tests) |
| `tests/src/exceptions/test_backfill_exceptions.py` | Exception tests (3 tests) |

### Modified Files (6)

| File | Changes |
|------|---------|
| `src/models/media_item.py` | Add `instagram_media_id`, `backfilled_at` columns |
| `src/repositories/media_repository.py` | Add `get_by_instagram_media_id()`, `get_backfilled_instagram_media_ids()` |
| `src/exceptions/__init__.py` | Export 3 new backfill exceptions |
| `src/services/core/telegram_commands.py` | Add `handle_backfill()` method |
| `src/services/core/telegram_service.py` | Register `/backfill` command |
| `cli/main.py` | Import + register 2 new CLI commands |

### Updated Test Files (1)

| File | Changes |
|------|---------|
| `tests/src/repositories/test_media_repository.py` | 2 new tests for backfill repo methods |
