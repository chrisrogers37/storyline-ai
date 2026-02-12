# Phase 03: Scheduled Media Sync Engine

**Status**: ✅ COMPLETE
**Started**: 2026-02-12
**Completed**: 2026-02-12
**PR Title**: feat: add scheduled media sync engine
**Risk Level**: Low
**Estimated Effort**: Medium (3 new files, 5 modified files, ~28 new tests)
**Branch**: `enhance/cloud-media-enhancements/phase-03-scheduled-sync`

---

## Context

Phases 01 and 02 established the `MediaSourceProvider` interface (`src/services/media_sources/base_provider.py`), `LocalMediaProvider`, `GoogleDriveProvider`, and the `MediaSourceFactory`. Media can now be listed, downloaded, and hashed from any configured provider.

However, there is no mechanism to **automatically keep the database in sync** with the provider's file inventory. Today, `MediaIngestionService.scan_directory()` is a one-shot CLI command that must be run manually. If files are added, renamed, moved, or deleted on the provider, the database becomes stale.

Phase 03 builds the **Scheduled Media Sync Engine**: a background loop (following the existing `run_scheduler_loop`, `cleanup_locks_loop` patterns in `src/main.py`) that periodically reconciles the provider's file listing with the `media_items` table. It handles:
- **New files**: Index them into `media_items`
- **Deleted files**: Deactivate via `is_active=False` (SCD2 soft-delete pattern)
- **Renamed/moved files**: Detect by hash match, update `file_name`/`file_path`/`source_identifier`
- **Reappeared files**: Reactivate previously deactivated items if the file reappears

**User intent**: "They should sync and be indexed by the database on a schedule. New files, index. Deleted files, turn these off. Renames/moves -- ideally track and update."

---

## Dependencies

- **Depends on**: Phase 01 (Provider Abstraction -- `MediaSourceProvider`, `MediaFileInfo`, `MediaSourceFactory`, migration 011) and Phase 02 (Google Drive Provider -- `GoogleDriveProvider`, `GoogleDriveService`, factory registration). Both must be merged first.
- **Unlocks**: Phase 04 (Configuration UI) can add Telegram `/settings` controls for sync enable/disable and interval tuning.

---

## Detailed Implementation Plan

### Step 1: New Settings in `src/config/settings.py`

#### Modify: `/Users/chris/Projects/storyline-ai/src/config/settings.py`

**Current code (lines 62-69):**
```python
    # Development Settings
    DRY_RUN_MODE: bool = False
    LOG_LEVEL: str = "INFO"

    # Phase 1.5 Settings - Telegram Enhancements
    SEND_LIFECYCLE_NOTIFICATIONS: bool = True
    INSTAGRAM_USERNAME: Optional[str] = None
    CAPTION_STYLE: str = "enhanced"  # or 'simple'
```

**Add before the `# Development Settings` block (insert at line 62):**
```python
    # Media Sync Engine (Phase 03 Cloud Media)
    MEDIA_SYNC_ENABLED: bool = False
    MEDIA_SYNC_INTERVAL_SECONDS: int = 300  # 5 minutes
    MEDIA_SOURCE_TYPE: str = "local"  # 'local' or 'google_drive'
    MEDIA_SOURCE_ROOT: str = ""  # Root path (local) or folder ID (google_drive)

```

**Why these defaults**:
- `MEDIA_SYNC_ENABLED=False` -- opt-in, no behavior change for existing deployments
- `MEDIA_SYNC_INTERVAL_SECONDS=300` -- 5 minutes balances freshness vs API quota (Google Drive quota: 12,000 queries/minute; listing a folder with 100 files uses ~2-3 queries per cycle)
- `MEDIA_SOURCE_TYPE="local"` -- backwards compatible, existing local deployments unchanged
- `MEDIA_SOURCE_ROOT=""` -- empty means "use settings.MEDIA_DIR for local" (resolved in sync service)

---

### Step 2: Repository Additions in `src/repositories/media_repository.py`

#### Modify: `/Users/chris/Projects/storyline-ai/src/repositories/media_repository.py`

Add four new methods. These are placed after the existing `get_by_hash()` method (after Phase 01's `get_by_source_identifier` addition).

**New method 1: `get_active_by_source_type()`**

```python
    def get_active_by_source_type(self, source_type: str) -> List[MediaItem]:
        """Get all active media items for a given source type.

        Used by MediaSyncService to build a lookup dict of known items
        for reconciliation against the provider's file listing.

        Args:
            source_type: Provider type string (e.g., 'local', 'google_drive')

        Returns:
            List of active MediaItem instances for the given source type
        """
        return (
            self.db.query(MediaItem)
            .filter(
                MediaItem.source_type == source_type,
                MediaItem.is_active == True,  # noqa: E712
            )
            .all()
        )
```

**New method 2: `get_inactive_by_source_identifier()`**

```python
    def get_inactive_by_source_identifier(
        self, source_type: str, source_identifier: str
    ) -> Optional[MediaItem]:
        """Get an inactive media item by source identifier.

        Used by MediaSyncService to detect reappeared files that were
        previously deactivated.

        Args:
            source_type: Provider type string
            source_identifier: Provider-specific unique ID

        Returns:
            Inactive MediaItem if found, None otherwise
        """
        return (
            self.db.query(MediaItem)
            .filter(
                MediaItem.source_type == source_type,
                MediaItem.source_identifier == source_identifier,
                MediaItem.is_active == False,  # noqa: E712
            )
            .first()
        )
```

**New method 3: `reactivate()`**

```python
    def reactivate(self, media_id: str) -> MediaItem:
        """Reactivate a previously deactivated media item.

        Used when a file reappears in the provider after being removed.

        Args:
            media_id: UUID of the media item to reactivate

        Returns:
            Reactivated MediaItem
        """
        media_item = self.get_by_id(media_id)
        if media_item:
            media_item.is_active = True
            media_item.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(media_item)
        return media_item
```

**New method 4: `update_source_info()`**

```python
    def update_source_info(
        self,
        media_id: str,
        file_path: Optional[str] = None,
        file_name: Optional[str] = None,
        source_identifier: Optional[str] = None,
    ) -> MediaItem:
        """Update source-related fields for a media item (rename/move tracking).

        Used by MediaSyncService when a file's name or path changes but
        its content hash remains the same.

        Args:
            media_id: UUID of the media item
            file_path: New file path (synthetic path for cloud sources)
            file_name: New display filename
            source_identifier: New provider-specific identifier

        Returns:
            Updated MediaItem
        """
        media_item = self.get_by_id(media_id)
        if media_item:
            if file_path is not None:
                media_item.file_path = file_path
            if file_name is not None:
                media_item.file_name = file_name
            if source_identifier is not None:
                media_item.source_identifier = source_identifier
            media_item.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(media_item)
        return media_item
```

**Import note**: `datetime` is already imported on line 4. `Optional` and `List` are imported on line 3. No new imports needed.

---

### Step 3: MediaSyncService (New File)

#### New File: `/Users/chris/Projects/storyline-ai/src/services/core/media_sync.py`

This is the core of Phase 03. The service extends `BaseService`, uses `track_execution` for observability, and orchestrates the full sync algorithm.

```python
"""Media sync service - scheduled reconciliation of media sources with the database."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.services.base_service import BaseService
from src.repositories.media_repository import MediaRepository
from src.services.media_sources.base_provider import MediaFileInfo
from src.services.media_sources.factory import MediaSourceFactory
from src.config.settings import settings
from src.utils.logger import logger


@dataclass
class SyncResult:
    """Tracks the outcome of a media sync operation.

    Attributes:
        new: Number of newly indexed media items
        updated: Number of items updated (rename/move detected)
        deactivated: Number of items deactivated (file removed from provider)
        reactivated: Number of items reactivated (file reappeared in provider)
        unchanged: Number of items that required no changes
        errors: Number of items that failed to process
        error_details: List of error description strings
    """

    new: int = 0
    updated: int = 0
    deactivated: int = 0
    reactivated: int = 0
    unchanged: int = 0
    errors: int = 0
    error_details: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for result summary storage."""
        result = {
            "new": self.new,
            "updated": self.updated,
            "deactivated": self.deactivated,
            "reactivated": self.reactivated,
            "unchanged": self.unchanged,
            "errors": self.errors,
        }
        if self.error_details:
            result["error_details"] = self.error_details[:10]  # Cap at 10
        return result

    @property
    def total_processed(self) -> int:
        """Total items processed across all categories."""
        return self.new + self.updated + self.deactivated + self.reactivated + self.unchanged


class MediaSyncService(BaseService):
    """Scheduled reconciliation of media source providers with the database.

    Compares the provider's file listing against media_items records and:
    - Indexes new files
    - Deactivates records for deleted files (is_active=False)
    - Detects renames/moves via hash matching and updates file_name/file_path
    - Reactivates previously deactivated items if files reappear

    Uses hash-based identity: the content hash is the immutable identifier
    for a file. If a file moves or is renamed, the hash stays the same,
    allowing the system to track the change rather than treating it as
    a delete + add.
    """

    def __init__(self):
        super().__init__()
        self.media_repo = MediaRepository()

    def sync(
        self,
        source_type: Optional[str] = None,
        source_root: Optional[str] = None,
        triggered_by: str = "system",
    ) -> SyncResult:
        """Run a full media sync against the configured provider.

        Args:
            source_type: Override settings.MEDIA_SOURCE_TYPE
            source_root: Override settings.MEDIA_SOURCE_ROOT
            triggered_by: Who triggered ('system', 'cli', 'scheduler')

        Returns:
            SyncResult with counts for each action taken

        Raises:
            ValueError: If provider is not configured or source_type is invalid
        """
        resolved_source_type = source_type or settings.MEDIA_SOURCE_TYPE
        resolved_source_root = source_root or settings.MEDIA_SOURCE_ROOT

        # For local provider, fall back to MEDIA_DIR if no root specified
        if resolved_source_type == "local" and not resolved_source_root:
            resolved_source_root = settings.MEDIA_DIR

        with self.track_execution(
            method_name="sync",
            triggered_by=triggered_by,
            input_params={
                "source_type": resolved_source_type,
                "source_root": resolved_source_root,
            },
        ) as run_id:
            result = SyncResult()

            # Create provider
            provider = self._create_provider(resolved_source_type, resolved_source_root)

            if not provider.is_configured():
                raise ValueError(
                    f"Media source provider '{resolved_source_type}' is not configured. "
                    f"Check your settings or run the appropriate setup command."
                )

            # Phase 1: Get provider file listing
            logger.info(
                f"[MediaSyncService] Starting sync for {resolved_source_type} "
                f"(root: {resolved_source_root})"
            )
            provider_files = provider.list_files()
            logger.info(f"[MediaSyncService] Provider reports {len(provider_files)} files")

            # Phase 2: Get DB records for this source type
            db_items = self.media_repo.get_active_by_source_type(resolved_source_type)
            logger.info(f"[MediaSyncService] Database has {len(db_items)} active items")

            # Build lookup dicts for O(1) matching
            # Key: source_identifier -> MediaItem
            db_by_identifier = {
                item.source_identifier: item
                for item in db_items
                if item.source_identifier
            }
            # Key: file_hash -> list[MediaItem] (for rename detection)
            db_by_hash: dict[str, list] = {}
            for item in db_items:
                db_by_hash.setdefault(item.file_hash, []).append(item)

            # Track which DB identifiers were seen in the provider
            seen_identifiers: set[str] = set()

            # Phase 3: Process provider files (new, renamed, reactivated, unchanged)
            for file_info in provider_files:
                try:
                    self._process_provider_file(
                        file_info=file_info,
                        source_type=resolved_source_type,
                        provider=provider,
                        db_by_identifier=db_by_identifier,
                        db_by_hash=db_by_hash,
                        seen_identifiers=seen_identifiers,
                        result=result,
                    )
                except Exception as e:
                    result.errors += 1
                    error_msg = f"Error processing {file_info.name}: {e}"
                    result.error_details.append(error_msg)
                    logger.error(f"[MediaSyncService] {error_msg}")

            # Phase 4: Deactivate DB items not seen in provider
            for identifier, item in db_by_identifier.items():
                if identifier not in seen_identifiers:
                    try:
                        self.media_repo.deactivate(str(item.id))
                        result.deactivated += 1
                        logger.info(
                            f"[MediaSyncService] Deactivated: {item.file_name} "
                            f"(no longer in provider)"
                        )
                    except Exception as e:
                        result.errors += 1
                        error_msg = f"Error deactivating {item.file_name}: {e}"
                        result.error_details.append(error_msg)
                        logger.error(f"[MediaSyncService] {error_msg}")

            # Log summary
            logger.info(
                f"[MediaSyncService] Sync complete: "
                f"{result.new} new, {result.updated} updated, "
                f"{result.deactivated} deactivated, {result.reactivated} reactivated, "
                f"{result.unchanged} unchanged, {result.errors} errors"
            )

            self.set_result_summary(run_id, result.to_dict())
            return result

    def _process_provider_file(
        self,
        file_info: MediaFileInfo,
        source_type: str,
        provider,
        db_by_identifier: dict,
        db_by_hash: dict,
        seen_identifiers: set,
        result: SyncResult,
    ) -> None:
        """Process a single file from the provider listing.

        Decision tree:
        1. Identifier matches DB record -> unchanged (or update name if changed)
        2. Identifier not in DB, but hash matches existing record -> rename/move detected
        3. Identifier not in DB, check for inactive record -> reactivate
        4. Identifier not in DB, no hash match -> new file, index it
        """
        identifier = file_info.identifier
        seen_identifiers.add(identifier)

        # Case 1: Exact identifier match in DB
        if identifier in db_by_identifier:
            existing = db_by_identifier[identifier]

            # Check if name changed (move within same identifier -- possible for local)
            if existing.file_name != file_info.name:
                file_path = self._build_file_path(source_type, file_info)
                self.media_repo.update_source_info(
                    media_id=str(existing.id),
                    file_name=file_info.name,
                    file_path=file_path,
                )
                result.updated += 1
                logger.info(
                    f"[MediaSyncService] Updated name: "
                    f"{existing.file_name} -> {file_info.name}"
                )
            else:
                result.unchanged += 1
            return

        # Need hash for further matching
        file_hash = self._get_file_hash(file_info, provider)

        # Case 2: Hash matches an existing active record (rename/move)
        if file_hash in db_by_hash:
            existing_items = db_by_hash[file_hash]
            # Pick the first match (most likely the original)
            existing = existing_items[0]

            file_path = self._build_file_path(source_type, file_info)
            self.media_repo.update_source_info(
                media_id=str(existing.id),
                file_name=file_info.name,
                file_path=file_path,
                source_identifier=identifier,
            )
            result.updated += 1
            logger.info(
                f"[MediaSyncService] Rename detected: "
                f"{existing.file_name} -> {file_info.name} "
                f"(hash: {file_hash[:8]}...)"
            )
            return

        # Case 3: Check for inactive record with same identifier (reactivation)
        inactive = self.media_repo.get_inactive_by_source_identifier(
            source_type, identifier
        )
        if inactive:
            self.media_repo.reactivate(str(inactive.id))
            result.reactivated += 1
            logger.info(
                f"[MediaSyncService] Reactivated: {inactive.file_name}"
            )
            return

        # Case 4: Truly new file -- index it
        file_path = self._build_file_path(source_type, file_info)
        self.media_repo.create(
            file_path=file_path,
            file_name=file_info.name,
            file_hash=file_hash,
            file_size_bytes=file_info.size_bytes,
            mime_type=file_info.mime_type,
            category=file_info.folder,
            source_type=source_type,
            source_identifier=identifier,
        )
        result.new += 1
        logger.info(
            f"[MediaSyncService] Indexed new: {file_info.name}"
            + (f" [{file_info.folder}]" if file_info.folder else "")
        )

    def _create_provider(self, source_type: str, source_root: str):
        """Create a MediaSourceProvider based on source type and root.

        For local: passes source_root as base_path.
        For google_drive: passes source_root as root_folder_id
            (credentials loaded from DB by factory).

        Args:
            source_type: 'local' or 'google_drive'
            source_root: Path for local, folder ID for google_drive

        Returns:
            Configured MediaSourceProvider instance
        """
        if source_type == "local":
            return MediaSourceFactory.create(source_type, base_path=source_root)
        elif source_type == "google_drive":
            return MediaSourceFactory.create(source_type, root_folder_id=source_root)
        else:
            return MediaSourceFactory.create(source_type)

    def _get_file_hash(self, file_info: MediaFileInfo, provider) -> str:
        """Get content hash for a file.

        Uses provider-side hash if available (e.g., Google Drive md5Checksum),
        otherwise downloads and hashes via the provider.

        Args:
            file_info: File metadata from provider listing
            provider: MediaSourceProvider instance

        Returns:
            Hex hash string
        """
        if file_info.hash:
            return file_info.hash
        return provider.calculate_file_hash(file_info.identifier)

    def _build_file_path(self, source_type: str, file_info: MediaFileInfo) -> str:
        """Build the file_path value for a media item.

        For local: uses the actual filesystem path (the identifier IS the path).
        For cloud: constructs a synthetic path like 'google_drive://file_id'
            to satisfy the UNIQUE constraint on media_items.file_path.

        Args:
            source_type: Provider type string
            file_info: File metadata from provider

        Returns:
            Path string to store in media_items.file_path
        """
        if source_type == "local":
            return file_info.identifier
        else:
            return f"{source_type}://{file_info.identifier}"

    def get_last_sync_info(self) -> Optional[dict]:
        """Get information about the most recent sync run.

        Queries the service_runs table for the latest MediaSyncService.sync run.

        Returns:
            Dict with last sync details, or None if never synced
        """
        runs = self.service_run_repo.get_recent_runs(
            service_name="MediaSyncService", limit=1
        )
        if not runs:
            return None

        run = runs[0]
        return {
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "duration_ms": run.duration_ms,
            "status": run.status,
            "success": run.success,
            "result": run.result_summary,
            "triggered_by": run.triggered_by,
        }
```

**Key design decisions:**

1. **Hash-based identity**: `file_hash` is the immutable content identifier. If a file moves or renames, the hash stays the same. We use `db_by_hash` dict for O(1) rename detection.

2. **Provider-side hash when available**: `MediaFileInfo.hash` is populated by GoogleDriveProvider with Drive's `md5Checksum`. This avoids downloading files just to hash them. Falls back to `provider.calculate_file_hash()` for providers without server-side hashes.

3. **Synthetic file_path for cloud sources**: Cloud files don't have real filesystem paths. We construct `google_drive://file_id` to satisfy the `UNIQUE` constraint on `media_items.file_path`. The `source_identifier` column holds the provider-native ID.

4. **No image validation for cloud sources**: The `MediaIngestionService._index_file()` method runs `ImageProcessor.validate_image()` which requires a local file path. Cloud sources skip this -- Instagram API validates at post time. This keeps sync fast and avoids downloading every file.

5. **SyncResult dataclass**: Clean tracking of all outcomes. Stored in `service_runs.result_summary` via `set_result_summary()`.

---

### Step 4: Background Sync Loop in `src/main.py`

#### Modify: `/Users/chris/Projects/storyline-ai/src/main.py`

**Add import (after existing service imports near the top):**

```python
from src.services.core.media_sync import MediaSyncService
```

**Add new async loop function (after `transaction_cleanup_loop`):**

```python
async def media_sync_loop(sync_service: MediaSyncService):
    """Run media sync loop - reconcile provider files with database on schedule."""
    logger.info(
        f"Starting media sync loop "
        f"(interval: {settings.MEDIA_SYNC_INTERVAL_SECONDS}s, "
        f"source: {settings.MEDIA_SOURCE_TYPE})"
    )

    while True:
        try:
            result = sync_service.sync(triggered_by="scheduler")

            if result.total_processed > 0 or result.errors > 0:
                logger.info(
                    f"Media sync completed: "
                    f"{result.new} new, {result.updated} updated, "
                    f"{result.deactivated} deactivated, "
                    f"{result.reactivated} reactivated, "
                    f"{result.errors} errors"
                )

        except Exception as e:
            logger.error(f"Error in media sync loop: {e}", exc_info=True)
        finally:
            sync_service.cleanup_transactions()

        await asyncio.sleep(settings.MEDIA_SYNC_INTERVAL_SECONDS)
```

**Modify `main_async()` to conditionally start the sync loop.**

In the service initialization block (after `lock_service = MediaLockService()`), add:

```python
    # Initialize media sync (if enabled)
    sync_service = None
    if settings.MEDIA_SYNC_ENABLED:
        sync_service = MediaSyncService()
```

In the task creation block, modify to conditionally include the sync task:

**Current code:**
```python
    # Create tasks
    all_services = [posting_service, telegram_service, lock_service]
    tasks = [
        asyncio.create_task(run_scheduler_loop(posting_service)),
        asyncio.create_task(cleanup_locks_loop(lock_service)),
        asyncio.create_task(telegram_service.start_polling()),
        asyncio.create_task(transaction_cleanup_loop(all_services)),
    ]
```

**New code:**
```python
    # Create tasks
    all_services = [posting_service, telegram_service, lock_service]
    tasks = [
        asyncio.create_task(run_scheduler_loop(posting_service)),
        asyncio.create_task(cleanup_locks_loop(lock_service)),
        asyncio.create_task(telegram_service.start_polling()),
    ]

    # Add media sync loop if enabled
    if sync_service:
        all_services.append(sync_service)
        tasks.append(asyncio.create_task(media_sync_loop(sync_service)))

    tasks.append(asyncio.create_task(transaction_cleanup_loop(all_services)))
```

In the startup log block (after dry run mode is logged), add:

```python
    if settings.MEDIA_SYNC_ENABLED:
        logger.info(
            f"✓ Media sync: {settings.MEDIA_SOURCE_TYPE} "
            f"(every {settings.MEDIA_SYNC_INTERVAL_SECONDS}s)"
        )
    else:
        logger.info("✓ Media sync: disabled")
```

---

### Step 5: Health Check Integration

#### Modify: `/Users/chris/Projects/storyline-ai/src/services/core/health_check.py`

**Add a new check method (after `_check_recent_posts`):**

```python
    def _check_media_sync(self) -> dict:
        """Check media sync health."""
        if not settings.MEDIA_SYNC_ENABLED:
            return {
                "healthy": True,
                "message": "Disabled via config",
                "enabled": False,
            }

        try:
            from src.services.core.media_sync import MediaSyncService

            sync_service = MediaSyncService()
            last_sync = sync_service.get_last_sync_info()

            if not last_sync:
                return {
                    "healthy": False,
                    "message": "No sync runs recorded yet",
                    "enabled": True,
                }

            if not last_sync["success"]:
                return {
                    "healthy": False,
                    "message": f"Last sync failed: {last_sync.get('status', 'unknown')}",
                    "enabled": True,
                    "last_run": last_sync["started_at"],
                }

            # Check if last sync is stale (more than 3x interval)
            if last_sync["completed_at"]:
                from datetime import timedelta

                completed = datetime.fromisoformat(last_sync["completed_at"])
                stale_threshold = timedelta(
                    seconds=settings.MEDIA_SYNC_INTERVAL_SECONDS * 3
                )
                if datetime.utcnow() - completed > stale_threshold:
                    return {
                        "healthy": False,
                        "message": (
                            f"Last sync was {last_sync['completed_at']} "
                            f"(stale, expected every {settings.MEDIA_SYNC_INTERVAL_SECONDS}s)"
                        ),
                        "enabled": True,
                        "last_run": last_sync["started_at"],
                    }

            result_summary = last_sync.get("result", {}) or {}
            errors = result_summary.get("errors", 0)

            if errors > 0:
                return {
                    "healthy": True,
                    "message": (
                        f"Last sync OK with {errors} error(s) "
                        f"at {last_sync['started_at']}"
                    ),
                    "enabled": True,
                    "last_run": last_sync["started_at"],
                    "last_result": result_summary,
                }

            return {
                "healthy": True,
                "message": f"Last sync OK at {last_sync['started_at']}",
                "enabled": True,
                "last_run": last_sync["started_at"],
                "last_result": result_summary,
            }

        except Exception as e:
            return {
                "healthy": False,
                "message": f"Sync check error: {str(e)}",
                "enabled": True,
            }
```

**Modify `check_all()` to include the new check:**

**Current code:**
```python
        checks = {
            "database": self._check_database(),
            "telegram": self._check_telegram_config(),
            "instagram_api": self._check_instagram_api(),
            "queue": self._check_queue(),
            "recent_posts": self._check_recent_posts(),
        }
```

**New code:**
```python
        checks = {
            "database": self._check_database(),
            "telegram": self._check_telegram_config(),
            "instagram_api": self._check_instagram_api(),
            "queue": self._check_queue(),
            "recent_posts": self._check_recent_posts(),
            "media_sync": self._check_media_sync(),
        }
```

---

### Step 6: CLI Commands

#### New File: `/Users/chris/Projects/storyline-ai/cli/commands/sync.py`

Two commands: `sync-media` (manual trigger) and `sync-status` (show last sync info).

```python
"""Media sync CLI commands."""

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.command(name="sync-media")
@click.option(
    "--source-type",
    type=click.Choice(["local", "google_drive"]),
    default=None,
    help="Override MEDIA_SOURCE_TYPE from .env",
)
@click.option(
    "--source-root",
    default=None,
    help="Override MEDIA_SOURCE_ROOT (path for local, folder ID for google_drive)",
)
def sync_media(source_type, source_root):
    """Manually trigger a media sync against the configured provider.

    Reconciles the provider's file listing with the database:
    indexes new files, deactivates removed files, detects renames.
    """
    from src.services.core.media_sync import MediaSyncService

    console.print("[bold blue]Running media sync...[/bold blue]\n")

    service = MediaSyncService()

    try:
        result = service.sync(
            source_type=source_type,
            source_root=source_root,
            triggered_by="cli",
        )

        console.print("[bold green]Sync complete![/bold green]\n")

        table = Table(title="Sync Results")
        table.add_column("Action", style="cyan")
        table.add_column("Count", justify="right")

        table.add_row("New files indexed", str(result.new))
        table.add_row("Updated (rename/move)", str(result.updated))
        table.add_row("Deactivated (removed)", str(result.deactivated))
        table.add_row("Reactivated (reappeared)", str(result.reactivated))
        table.add_row("Unchanged", str(result.unchanged))
        table.add_row(
            "Errors",
            f"[red]{result.errors}[/red]" if result.errors > 0 else "0",
        )

        console.print(table)

        if result.error_details:
            console.print("\n[yellow]Error details:[/yellow]")
            for detail in result.error_details[:10]:
                console.print(f"  - {detail}")

    except ValueError as e:
        console.print(f"\n[red]Configuration error:[/red] {e}")
    except Exception as e:
        console.print(f"\n[red]Sync failed:[/red] {e}")


@click.command(name="sync-status")
def sync_status():
    """Show the status of the last media sync run."""
    from src.services.core.media_sync import MediaSyncService
    from src.config.settings import settings

    console.print("[bold blue]Media Sync Status[/bold blue]\n")

    # Show configuration
    config_table = Table(title="Configuration")
    config_table.add_column("Setting", style="cyan")
    config_table.add_column("Value")

    enabled = settings.MEDIA_SYNC_ENABLED
    config_table.add_row(
        "Sync Enabled",
        "[green]Yes[/green]" if enabled else "[red]No[/red]",
    )
    config_table.add_row("Source Type", settings.MEDIA_SOURCE_TYPE)
    config_table.add_row(
        "Source Root",
        settings.MEDIA_SOURCE_ROOT or f"(default: {settings.MEDIA_DIR})",
    )
    config_table.add_row(
        "Interval", f"{settings.MEDIA_SYNC_INTERVAL_SECONDS}s"
    )

    console.print(config_table)

    # Show last sync info
    service = MediaSyncService()
    last_sync = service.get_last_sync_info()

    if not last_sync:
        console.print("\n[yellow]No sync runs recorded yet.[/yellow]")
        if not enabled:
            console.print(
                "[dim]Enable with MEDIA_SYNC_ENABLED=true in .env, "
                "or run 'storyline-cli sync-media' manually.[/dim]"
            )
        return

    console.print()

    sync_table = Table(title="Last Sync Run")
    sync_table.add_column("Property", style="cyan")
    sync_table.add_column("Value")

    status_str = (
        "[green]Success[/green]" if last_sync["success"] else "[red]Failed[/red]"
    )
    sync_table.add_row("Status", status_str)
    sync_table.add_row("Started At", last_sync.get("started_at", "N/A"))
    sync_table.add_row("Completed At", last_sync.get("completed_at", "N/A"))

    duration = last_sync.get("duration_ms")
    if duration is not None:
        sync_table.add_row("Duration", f"{duration}ms")

    sync_table.add_row("Triggered By", last_sync.get("triggered_by", "N/A"))

    console.print(sync_table)

    # Show result summary if available
    result = last_sync.get("result")
    if result:
        console.print()
        result_table = Table(title="Sync Details")
        result_table.add_column("Action", style="cyan")
        result_table.add_column("Count", justify="right")

        result_table.add_row("New", str(result.get("new", 0)))
        result_table.add_row("Updated", str(result.get("updated", 0)))
        result_table.add_row("Deactivated", str(result.get("deactivated", 0)))
        result_table.add_row("Reactivated", str(result.get("reactivated", 0)))
        result_table.add_row("Unchanged", str(result.get("unchanged", 0)))
        errors = result.get("errors", 0)
        result_table.add_row(
            "Errors",
            f"[red]{errors}[/red]" if errors > 0 else "0",
        )

        console.print(result_table)
```

#### Modify: `/Users/chris/Projects/storyline-ai/cli/main.py`

**Add import (after the existing command imports):**

```python
from cli.commands.sync import sync_media, sync_status
```

**Add commands to CLI group (after the last `cli.add_command` call):**

```python
cli.add_command(sync_media)
cli.add_command(sync_status)
```

---

## Test Plan

### New Test File: `/Users/chris/Projects/storyline-ai/tests/src/services/test_media_sync.py`

All tests use the established mocking pattern: `patch` ServiceRunRepository and MediaRepository, mock `track_execution` as a context manager.

#### SyncResult Tests (5 tests)

1. **`test_sync_result_defaults`** -- All counters start at 0, `error_details` is empty list
2. **`test_sync_result_to_dict`** -- Converts correctly, caps error_details at 10 entries
3. **`test_sync_result_to_dict_no_errors`** -- Omits `error_details` key when empty
4. **`test_sync_result_total_processed`** -- Sums `new + updated + deactivated + reactivated + unchanged`
5. **`test_sync_result_total_processed_excludes_errors`** -- Errors not counted in total_processed

#### MediaSyncService.sync() Core Tests (8 tests)

6. **`test_sync_indexes_new_files`** -- Provider has files not in DB. Verify `media_repo.create()` called with correct args including `source_type`, `source_identifier`, `file_hash`, `category`.
7. **`test_sync_detects_deleted_files`** -- DB has items whose identifiers are absent from provider listing. Verify `media_repo.deactivate()` called for each.
8. **`test_sync_detects_renamed_files`** -- Provider has file with same hash but different identifier than DB record. Verify `media_repo.update_source_info()` called with new name, path, and identifier.
9. **`test_sync_reactivates_files`** -- Provider has file matching an inactive DB record's identifier. Verify `media_repo.reactivate()` called.
10. **`test_sync_unchanged_files`** -- Provider file identifier and name match DB record. No repo mutations called. `result.unchanged` incremented.
11. **`test_sync_name_changed_same_identifier`** -- Provider file has same identifier but different `file_info.name`. Verify `update_source_info()` called with new name.
12. **`test_sync_returns_sync_result`** -- Verify return type is `SyncResult` and `set_result_summary` called with `result.to_dict()`.
13. **`test_sync_provider_not_configured_raises`** -- Provider's `is_configured()` returns False. Verify `ValueError` raised.

#### MediaSyncService.sync() Edge Cases (5 tests)

14. **`test_sync_empty_provider_deactivates_all`** -- Provider returns empty file list. All DB items deactivated.
15. **`test_sync_empty_db_indexes_all`** -- DB has no items for this source type. All provider files indexed as new.
16. **`test_sync_error_in_single_file_continues`** -- Provider lists 3 files. Hash calculation fails for file 2. Files 1 and 3 still processed. `result.errors == 1`.
17. **`test_sync_uses_provider_hash_when_available`** -- `file_info.hash` is populated. Verify `provider.calculate_file_hash()` is NOT called.
18. **`test_sync_falls_back_to_calculated_hash`** -- `file_info.hash` is None. Verify `provider.calculate_file_hash()` IS called.

#### Provider Creation Tests (3 tests)

19. **`test_create_provider_local`** -- Verify `MediaSourceFactory.create("local", base_path=...)` called for local source type.
20. **`test_create_provider_google_drive`** -- Verify `MediaSourceFactory.create("google_drive", root_folder_id=...)` called for google_drive source type.
21. **`test_create_provider_local_fallback_to_media_dir`** -- When `source_root` is empty and source_type is local, resolves to `settings.MEDIA_DIR`.

#### File Path Building Tests (2 tests)

22. **`test_build_file_path_local`** -- For `source_type="local"`, returns `file_info.identifier` (the real path).
23. **`test_build_file_path_cloud`** -- For `source_type="google_drive"`, returns `google_drive://file_id`.

#### get_last_sync_info Tests (3 tests)

24. **`test_get_last_sync_info_returns_info`** -- `service_run_repo.get_recent_runs()` returns a run. Verify dict shape.
25. **`test_get_last_sync_info_no_runs`** -- `service_run_repo.get_recent_runs()` returns empty list. Verify returns `None`.
26. **`test_get_last_sync_info_failed_run`** -- Last run has `success=False`. Verify dict includes failure info.

#### Settings Resolution Tests (2 tests)

27. **`test_sync_uses_overridden_source_type`** -- Passing `source_type="google_drive"` overrides `settings.MEDIA_SOURCE_TYPE`.
28. **`test_sync_uses_overridden_source_root`** -- Passing `source_root="/custom/path"` overrides `settings.MEDIA_SOURCE_ROOT`.

### Updated Test File: `/Users/chris/Projects/storyline-ai/tests/src/services/test_health_check.py`

Add 4 new tests to the existing `TestHealthCheckService` class:

29. **`test_check_media_sync_disabled`** -- `settings.MEDIA_SYNC_ENABLED=False`. Returns `healthy=True, enabled=False`.
30. **`test_check_media_sync_healthy`** -- Sync enabled, last run succeeded. Returns `healthy=True`.
31. **`test_check_media_sync_no_runs`** -- Sync enabled, no runs recorded. Returns `healthy=False`.
32. **`test_check_media_sync_stale`** -- Sync enabled, last run completed more than 3x interval ago. Returns `healthy=False`.

### Updated Test File: `/Users/chris/Projects/storyline-ai/tests/src/repositories/test_media_repository.py`

Add 6 new tests for the new repository methods:

33. **`test_get_active_by_source_type`** -- Returns only active items for given source type.
34. **`test_get_inactive_by_source_identifier`** -- Returns inactive item by source_type + identifier.
35. **`test_get_inactive_by_source_identifier_not_found`** -- Returns None when no match.
36. **`test_reactivate_sets_is_active_true`** -- Reactivates item and sets `updated_at`.
37. **`test_update_source_info_updates_fields`** -- Updates file_path, file_name, source_identifier.
38. **`test_update_source_info_partial_update`** -- Only updates fields that are not None.

---

## Documentation Updates

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Added

- **Scheduled Media Sync Engine** - Automatic reconciliation of media sources with database
  - New `MediaSyncService` with full sync algorithm: new file indexing, deleted file deactivation, rename/move detection via hash matching, reactivation of reappeared files
  - Background `media_sync_loop` in `src/main.py` following existing asyncio loop pattern
  - Health check integration: `media_sync` check in `check-health` command
  - New CLI commands: `sync-media` (manual trigger), `sync-status` (last sync info)
  - New settings: `MEDIA_SYNC_ENABLED`, `MEDIA_SYNC_INTERVAL_SECONDS`, `MEDIA_SOURCE_TYPE`, `MEDIA_SOURCE_ROOT`
  - `SyncResult` dataclass for tracking sync outcomes
  - New repository methods: `get_active_by_source_type()`, `get_inactive_by_source_identifier()`, `reactivate()`, `update_source_info()`
```

### CLAUDE.md

Add `sync-media` and `sync-status` to the "SAFE commands you CAN run" section. Add the new settings to the settings table reference.

---

## Stress Testing & Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Provider returns 5000+ files | All files processed. Hash dict lookup is O(1). No memory issue (MediaFileInfo is lightweight). |
| Provider has file with same hash as two DB records | Rename detection picks `existing_items[0]`. The second record remains unmodified. |
| File renamed and another file takes the old name | Old file found by hash match, renamed. New file (different hash) indexed as new. |
| Provider API rate limited mid-sync | `provider.list_files()` raises exception. Caught by outer try/except in `media_sync_loop`. Retried next interval. |
| Database connection lost during sync | `media_repo` methods raise. Caught by per-file try/except. Errors counted in `result.errors`. Next interval retries. |
| Two files with identical content (same hash) in provider | Both indexed (different identifiers). First one matched by hash for rename detection; second one indexed as new. This matches existing `MediaIngestionService` behavior (duplicates allowed with warning). |
| MEDIA_SYNC_ENABLED=false (default) | No sync loop started. Health check shows "Disabled via config". No impact on existing deployments. |
| MEDIA_SYNC_INTERVAL_SECONDS=0 | Will spin continuously. Document that minimum recommended is 60. No code guard needed (user config issue). |
| Cloud file hash is None (e.g., Google Docs export) | Falls back to `provider.calculate_file_hash()` which downloads and hashes. |
| Local file renamed while sync is in progress | File discovered by `list_files()` with old name. Rename detected on next sync cycle. Worst case: one cycle delay. |
| Sync triggered manually via CLI while background loop is running | Both run independently. Repo operations are atomic (commit per item). May see duplicate log entries but no data corruption. |
| Provider credentials expired during sync | `provider.list_files()` raises `GoogleDriveAuthError`. Caught by outer exception handler. Logged as error. Health check shows failure. |

---

## Verification Checklist

- [ ] New settings added to `src/config/settings.py` with correct defaults
- [ ] `storyline-cli sync-media --help` shows usage
- [ ] `storyline-cli sync-status` shows configuration and "No sync runs" when never run
- [ ] `storyline-cli sync-media` with local source indexes files correctly
- [ ] Running sync twice with no changes: second run shows all `unchanged`
- [ ] Adding a new file to provider directory, then re-syncing: shows 1 `new`
- [ ] Removing a file from provider directory, then re-syncing: shows 1 `deactivated`
- [ ] Renaming a file (same content), then re-syncing: shows 1 `updated`
- [ ] `storyline-cli check-health` includes `media_sync` check
- [ ] Health check shows "Disabled via config" when `MEDIA_SYNC_ENABLED=false`
- [ ] Background loop starts when `MEDIA_SYNC_ENABLED=true` in `python -m src.main`
- [ ] Background loop does NOT start when `MEDIA_SYNC_ENABLED=false`
- [ ] All 38+ tests pass: `pytest tests/src/services/test_media_sync.py -v`
- [ ] Existing test suite still passes: `pytest`
- [ ] `ruff check src/ tests/ cli/` passes
- [ ] `ruff format --check src/ tests/ cli/` passes
- [ ] CHANGELOG.md updated

---

## What NOT To Do

1. **Do NOT modify `MediaIngestionService`.** The sync service is a parallel pathway. `scan_directory()` remains for one-time CLI indexing. `MediaSyncService` handles ongoing reconciliation. They serve different purposes.

2. **Do NOT run image validation on cloud-sourced files.** `ImageProcessor.validate_image()` requires a local file path. Cloud files are validated by Instagram API at post time. Downloading every file just to validate would be slow and wasteful of API quota.

3. **Do NOT delete `media_items` records during deactivation.** Always use `is_active=False` (soft delete). This preserves posting history integrity -- `posting_history` references `media_item_id`. Hard-deleting would break those foreign key references.

4. **Do NOT acquire database locks or use transactions across the entire sync.** Each file operation (create, update, deactivate) commits independently. This prevents a single error from rolling back the entire sync and avoids long-held database locks.

5. **Do NOT add MEDIA_SYNC settings to `chat_settings`.** These are deployment-level settings, not per-chat settings. They belong in `.env` / `settings.py`. Per-chat sync controls are Phase 04.

6. **Do NOT make the sync loop async-aware at the provider level.** The provider methods (`list_files`, `calculate_file_hash`) are synchronous. The `media_sync_loop` wraps `sync_service.sync()` in a normal call within an async loop (same pattern as `cleanup_locks_loop` which calls `lock_service.cleanup_expired_locks()`). The `asyncio.sleep()` ensures the event loop is not blocked between sync cycles.

7. **Do NOT add a database migration.** This phase uses only existing columns (`source_type`, `source_identifier` from migration 011, `is_active`, `file_hash`). No new tables or columns needed.

8. **Do NOT attempt to sync in parallel or use threading.** The sync is I/O-bound (provider API calls + DB writes). Running it synchronously within the async loop is the established pattern and avoids concurrency bugs with SQLAlchemy sessions.

---

## Files Summary

### New Files (3)

| File | Purpose |
|------|---------|
| `src/services/core/media_sync.py` | MediaSyncService + SyncResult dataclass |
| `cli/commands/sync.py` | CLI: sync-media, sync-status |
| `tests/src/services/test_media_sync.py` | MediaSyncService tests (~28 tests) |

### Modified Files (5)

| File | Changes |
|------|---------|
| `src/config/settings.py` | Add 4 new settings: MEDIA_SYNC_ENABLED, MEDIA_SYNC_INTERVAL_SECONDS, MEDIA_SOURCE_TYPE, MEDIA_SOURCE_ROOT |
| `src/repositories/media_repository.py` | Add 4 new methods: get_active_by_source_type(), get_inactive_by_source_identifier(), reactivate(), update_source_info() |
| `src/main.py` | Add media_sync_loop() function, conditionally create sync task in main_async() |
| `src/services/core/health_check.py` | Add _check_media_sync() method, include in check_all() |
| `cli/main.py` | Import + register 2 new CLI commands (sync-media, sync-status) |

### Updated Test Files (2)

| File | Changes |
|------|---------|
| `tests/src/services/test_health_check.py` | 4 new tests for _check_media_sync |
| `tests/src/repositories/test_media_repository.py` | 6 new tests for new repository methods |
