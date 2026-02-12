# Phase 01: Media Source Provider Abstraction

**PR Title**: refactor: introduce media source provider abstraction layer
**Risk Level**: Low (internal refactor, no new external integrations)
**Estimated Effort**: Medium (8 new files, 7 modified files)
**Branch**: `enhance/cloud-media-enhancements/phase-01-provider-abstraction`

---

## Context

The system currently sources all media from the local filesystem (Raspberry Pi). Every service that touches media files assumes local paths — `open(file_path, "rb")`, `Path.exists()`, `file_path.endswith(".mp4")`, etc.

To support cloud media sources (Google Drive, S3) in later phases, we need an abstraction layer that decouples all file access from the filesystem. This phase:

1. Defines an abstract `MediaSourceProvider` interface
2. Wraps existing filesystem access as `LocalMediaProvider`
3. Decouples the entire posting pipeline from local file assumptions
4. Adds `source_type` and `source_identifier` columns to track where media originates

**User intent**: "A user comes to use the product, they hook in their Google Drive folder, the system indexes their media, everything works from that external location." This phase builds the foundation that makes that possible.

---

## Dependencies

- **Depends on**: Nothing (this is the foundation)
- **Unlocks**: Phase 02 (Google Drive Provider), Phase 03 (Scheduled Sync), Phase 04 (Configuration)

---

## Detailed Implementation Plan

### Step 1: Database Migration & Model Update

#### New File: `scripts/migrations/011_media_source_columns.sql`

```sql
-- Migration 011: Add media source columns for provider abstraction
-- Phase 01 of cloud media enhancement
--
-- Adds source_type and source_identifier columns to media_items.
-- These columns allow the system to track where media originated from
-- (local filesystem, Google Drive, S3, etc.).
--
-- For existing records:
--   source_type = 'local' (default)
--   source_identifier = file_path (backfilled from existing column)

BEGIN;

-- Add source columns
ALTER TABLE media_items
    ADD COLUMN source_type VARCHAR(50) NOT NULL DEFAULT 'local',
    ADD COLUMN source_identifier TEXT;

-- Backfill source_identifier from file_path for all existing records
UPDATE media_items SET source_identifier = file_path WHERE source_identifier IS NULL;

-- Create composite index for provider-based lookups
CREATE INDEX idx_media_items_source_type_identifier
    ON media_items (source_type, source_identifier);

-- Record migration
INSERT INTO schema_version (version, description, applied_at)
VALUES (11, 'Add media source columns (source_type, source_identifier)', NOW());

COMMIT;
```

#### Modify: `src/models/media_item.py`

**Current code (lines 30-37):**
```python
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # File information
    file_path = Column(Text, nullable=False, unique=True, index=True)
    file_name = Column(Text, nullable=False)
    file_size = Column(BigInteger, nullable=False)
    file_hash = Column(Text, nullable=False, index=True)  # SHA256 of content
    mime_type = Column(String(100))
```

**New code (replace lines 30-37):**
```python
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # File information
    file_path = Column(Text, nullable=False, unique=True, index=True)
    file_name = Column(Text, nullable=False)
    file_size = Column(BigInteger, nullable=False)
    file_hash = Column(Text, nullable=False, index=True)  # SHA256 of content
    mime_type = Column(String(100))

    # Media source (provider abstraction - Phase 01 Cloud Media)
    source_type = Column(String(50), nullable=False, default="local")
    source_identifier = Column(Text)  # Provider-specific ID (path for local, file_id for Drive)
```

No new imports needed — `String` and `Text` are already imported.

---

### Step 2: Provider Abstraction Layer (New Files)

#### New File: `src/services/media_sources/__init__.py`

```python
"""Media source providers for abstracting file access across local, cloud, and remote sources."""
```

#### New File: `src/services/media_sources/base_provider.py`

```python
"""Abstract base class for media source providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class MediaFileInfo:
    """Metadata for a media file from any provider.

    Attributes:
        identifier: Provider-specific unique ID (file_path for local, file_id for Drive)
        name: Display filename (e.g., "image.jpg")
        size_bytes: File size in bytes
        mime_type: MIME type string (e.g., "image/jpeg")
        folder: Category/folder name (e.g., "memes"), or None if at root
        modified_at: Last modification timestamp, or None if unavailable
        hash: Provider-side content hash if available, or None
    """

    identifier: str
    name: str
    size_bytes: int
    mime_type: str
    folder: Optional[str] = None
    modified_at: Optional[datetime] = None
    hash: Optional[str] = None


class MediaSourceProvider(ABC):
    """Abstract interface for media source providers.

    All media access in the system should go through a provider instance.
    This enables swapping local filesystem for Google Drive, S3, etc.

    Providers are lightweight objects -- they do NOT extend BaseService and
    are not tracked in service_runs. They are used by services that do have
    tracking (e.g., MediaIngestionService, PostingService).
    """

    @abstractmethod
    def list_files(self, folder: Optional[str] = None) -> list[MediaFileInfo]:
        """List available media files.

        Args:
            folder: Optional folder/category name to filter by.
                    If None, lists all files across all folders.

        Returns:
            List of MediaFileInfo objects for all matching files.
        """

    @abstractmethod
    def download_file(self, file_identifier: str) -> bytes:
        """Download file content as bytes.

        Args:
            file_identifier: Provider-specific unique ID for the file.

        Returns:
            Raw file bytes.

        Raises:
            FileNotFoundError: If file_identifier does not exist.
        """

    @abstractmethod
    def get_file_info(self, file_identifier: str) -> Optional[MediaFileInfo]:
        """Get file metadata without downloading content.

        Args:
            file_identifier: Provider-specific unique ID for the file.

        Returns:
            MediaFileInfo if file exists, None otherwise.
        """

    @abstractmethod
    def file_exists(self, file_identifier: str) -> bool:
        """Check whether a file exists.

        Args:
            file_identifier: Provider-specific unique ID for the file.

        Returns:
            True if the file exists and is accessible.
        """

    @abstractmethod
    def get_folders(self) -> list[str]:
        """List top-level folders (categories).

        Returns:
            List of folder/category names.
        """

    @abstractmethod
    def is_configured(self) -> bool:
        """Check whether this provider has valid configuration.

        Returns:
            True if the provider can operate (paths exist, credentials valid, etc.).
        """

    @abstractmethod
    def calculate_file_hash(self, file_identifier: str) -> str:
        """Calculate content hash for deduplication.

        Args:
            file_identifier: Provider-specific unique ID for the file.

        Returns:
            Hex string of SHA256 hash.

        Raises:
            FileNotFoundError: If file_identifier does not exist.
        """
```

#### New File: `src/services/media_sources/local_provider.py`

```python
"""Local filesystem media source provider."""

import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.services.media_sources.base_provider import MediaFileInfo, MediaSourceProvider
from src.utils.file_hash import calculate_file_hash
from src.utils.logger import logger


class LocalMediaProvider(MediaSourceProvider):
    """Media source provider for local filesystem.

    Wraps standard filesystem operations behind the MediaSourceProvider
    interface. The base_path is the root directory containing media files,
    and subfolders are treated as categories.

    Args:
        base_path: Root directory for media files (e.g., "/home/pi/media")
        supported_extensions: Set of lowercase file extensions to include.
            Defaults to the standard set used by MediaIngestionService.
    """

    DEFAULT_SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".mp4", ".mov"}

    def __init__(
        self,
        base_path: str,
        supported_extensions: Optional[set[str]] = None,
    ):
        self.base_path = Path(base_path)
        self.supported_extensions = (
            supported_extensions or self.DEFAULT_SUPPORTED_EXTENSIONS
        )

    def list_files(self, folder: Optional[str] = None) -> list[MediaFileInfo]:
        """List media files in the base directory or a specific subfolder."""
        if not self.base_path.exists():
            logger.warning(f"Base path does not exist: {self.base_path}")
            return []

        if folder:
            search_path = self.base_path / folder
            if not search_path.exists():
                logger.warning(f"Folder does not exist: {search_path}")
                return []
        else:
            search_path = self.base_path

        results = []
        for file_path in search_path.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in self.supported_extensions:
                continue

            info = self._build_file_info(file_path)
            if info:
                results.append(info)

        return results

    def download_file(self, file_identifier: str) -> bytes:
        """Read file bytes from local filesystem."""
        path = Path(file_identifier)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_identifier}")
        return path.read_bytes()

    def get_file_info(self, file_identifier: str) -> Optional[MediaFileInfo]:
        """Get metadata for a local file."""
        path = Path(file_identifier)
        if not path.exists() or not path.is_file():
            return None
        return self._build_file_info(path)

    def file_exists(self, file_identifier: str) -> bool:
        """Check if a local file exists."""
        return Path(file_identifier).is_file()

    def get_folders(self) -> list[str]:
        """List immediate subdirectories of base_path (categories)."""
        if not self.base_path.exists():
            return []

        folders = [
            d.name
            for d in sorted(self.base_path.iterdir())
            if d.is_dir() and not d.name.startswith(".")
        ]
        return folders

    def is_configured(self) -> bool:
        """Check if the base path exists and is a directory."""
        return self.base_path.exists() and self.base_path.is_dir()

    def calculate_file_hash(self, file_identifier: str) -> str:
        """Calculate SHA256 hash of local file content."""
        path = Path(file_identifier)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_identifier}")
        return calculate_file_hash(path)

    def _build_file_info(self, file_path: Path) -> Optional[MediaFileInfo]:
        """Build a MediaFileInfo from a local file path."""
        try:
            stat = file_path.stat()
            mime_type, _ = mimetypes.guess_type(str(file_path))

            # Extract folder (category) relative to base_path
            folder = None
            try:
                relative = file_path.relative_to(self.base_path)
                parts = relative.parts
                if len(parts) > 1:
                    folder = parts[0]
            except ValueError:
                pass

            return MediaFileInfo(
                identifier=str(file_path),
                name=file_path.name,
                size_bytes=stat.st_size,
                mime_type=mime_type or "application/octet-stream",
                folder=folder,
                modified_at=datetime.fromtimestamp(stat.st_mtime),
            )
        except OSError as e:
            logger.warning(f"Could not stat file {file_path}: {e}")
            return None
```

#### New File: `src/services/media_sources/factory.py`

```python
"""Factory for creating media source provider instances."""

from src.services.media_sources.base_provider import MediaSourceProvider
from src.services.media_sources.local_provider import LocalMediaProvider
from src.config.settings import settings
from src.utils.logger import logger


class MediaSourceFactory:
    """Factory for creating MediaSourceProvider instances.

    Currently supports:
        - 'local': LocalMediaProvider (filesystem-based)

    Future phases will add:
        - 'google_drive': GoogleDriveProvider
        - 's3': S3Provider
    """

    _providers: dict[str, type[MediaSourceProvider]] = {
        "local": LocalMediaProvider,
    }

    @classmethod
    def create(cls, source_type: str, **kwargs) -> MediaSourceProvider:
        """Create a provider instance for the given source type.

        Args:
            source_type: Provider type string (e.g., 'local', 'google_drive').
            **kwargs: Provider-specific configuration. For 'local', accepts
                'base_path' (defaults to settings.MEDIA_DIR).

        Returns:
            Configured MediaSourceProvider instance.

        Raises:
            ValueError: If source_type is not supported.
        """
        if source_type not in cls._providers:
            supported = ", ".join(sorted(cls._providers.keys()))
            raise ValueError(
                f"Unsupported media source type: '{source_type}'. "
                f"Supported types: {supported}"
            )

        provider_class = cls._providers[source_type]

        if source_type == "local":
            base_path = kwargs.get("base_path", settings.MEDIA_DIR)
            return provider_class(base_path=base_path)

        return provider_class(**kwargs)

    @classmethod
    def get_provider_for_media_item(cls, media_item) -> MediaSourceProvider:
        """Get the appropriate provider for an existing media item.

        Uses the media_item's source_type to create the correct provider.
        Falls back to 'local' if source_type is not set (backwards compat).

        Args:
            media_item: A MediaItem model instance.

        Returns:
            Configured MediaSourceProvider instance.
        """
        source_type = getattr(media_item, "source_type", None) or "local"
        return cls.create(source_type)

    @classmethod
    def register_provider(
        cls, source_type: str, provider_class: type[MediaSourceProvider]
    ) -> None:
        """Register a new provider type (used by future phases)."""
        cls._providers[source_type] = provider_class
        logger.info(f"Registered media source provider: {source_type}")
```

---

### Step 3: Repository Updates

#### Modify: `src/repositories/media_repository.py`

**Add new method after `get_by_hash` (after line 29):**

```python
    def get_by_source_identifier(
        self, source_type: str, source_identifier: str
    ) -> Optional[MediaItem]:
        """Get media item by provider-specific source identifier.

        Args:
            source_type: Provider type (e.g., 'local', 'google_drive')
            source_identifier: Provider-specific unique ID

        Returns:
            MediaItem if found, None otherwise
        """
        return (
            self.db.query(MediaItem)
            .filter(
                MediaItem.source_type == source_type,
                MediaItem.source_identifier == source_identifier,
            )
            .first()
        )
```

**Extend `create()` method signature (lines 67-81).**

Add two new parameters at the end of the signature:
```python
        source_type: str = "local",
        source_identifier: Optional[str] = None,
```

**Update the MediaItem constructor call (lines 84-98).**

Add to the `MediaItem(...)` constructor:
```python
            source_type=source_type,
            source_identifier=source_identifier or file_path,
```

Key: `source_identifier` defaults to `file_path` when not provided, so existing callers work unchanged.

---

### Step 4: CloudStorageService — Add Bytes Upload

#### Modify: `src/services/integrations/cloud_storage.py`

**Add `upload_media_bytes()` method after `upload_media` (after line 135):**

```python
    def upload_media_bytes(
        self,
        file_bytes: bytes,
        filename: str,
        folder: str = "storyline",
        public_id: Optional[str] = None,
    ) -> dict:
        """Upload media bytes to Cloudinary (provider-agnostic).

        Unlike upload_media() which reads from a local file path, this method
        accepts raw bytes. Use this when media comes from a cloud provider
        where the file is not on the local filesystem.

        Args:
            file_bytes: Raw file bytes to upload
            filename: Original filename (used for resource type detection)
            folder: Cloudinary folder/prefix for organization
            public_id: Optional custom identifier (auto-generated if not provided)

        Returns:
            dict with url, public_id, uploaded_at, expires_at, size_bytes, format

        Raises:
            MediaUploadError: If upload fails
        """
        from io import BytesIO

        with self.track_execution(
            method_name="upload_media_bytes",
            input_params={"filename": filename, "folder": folder},
        ) as run_id:
            try:
                path = Path(filename)
                resource_type = self._get_resource_type(path)

                upload_options = {
                    "folder": folder,
                    "resource_type": resource_type,
                    "overwrite": True,
                }

                if public_id:
                    upload_options["public_id"] = public_id

                logger.info(f"Uploading {filename} bytes to Cloudinary ({folder}/)")

                file_buffer = BytesIO(file_bytes)
                result = cloudinary.uploader.upload(file_buffer, **upload_options)

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
                    f"Successfully uploaded {filename} to Cloudinary: {result['public_id']}"
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
                    file_path=filename,
                    provider="cloudinary",
                )
```

Cloudinary's Python SDK accepts `BytesIO` objects as the first argument to `upload()`. This is documented behavior.

---

### Step 5: MediaIngestionService Refactor

#### Modify: `src/services/core/media_ingestion.py`

**Key changes** (preserve exact same external behavior):

1. **Add imports** (after existing imports):
```python
from src.services.media_sources.base_provider import MediaFileInfo
from src.services.media_sources.local_provider import LocalMediaProvider
```

2. **In `scan_directory()`**: Create a `LocalMediaProvider` instance and pass it to `_index_file`:
```python
provider = LocalMediaProvider(
    base_path=directory_path,
    supported_extensions=self.SUPPORTED_EXTENSIONS,
)
```

3. **In `_index_file()`**: Accept optional `provider` and `file_info` parameters. Use provider for hash calculation when available. Pass `source_type="local"` and `source_identifier=str(file_path)` to `media_repo.create()`.

4. **No behavior change**: `scan_directory` still accepts a directory path string and returns the same result dict `{indexed, skipped, errors, total_files, categories}`.

See full replacement file in the implementation plan appendix. The refactored service uses provider internally but keeps the exact same public API.

---

### Step 6: Posting Pipeline Decoupling

#### 6A. Modify: `src/services/core/telegram_service.py`

**Current (lines 362-370):**
```python
        try:
            # Send photo with buttons
            with open(media_item.file_path, "rb") as photo:
                message = await self.bot.send_photo(
                    chat_id=self.channel_id,
                    photo=photo,
                    caption=caption,
                    reply_markup=reply_markup,
                )
```

**New:**
```python
        try:
            # Get file bytes via provider (supports local and future cloud sources)
            from src.services.media_sources.factory import MediaSourceFactory
            from io import BytesIO

            provider = MediaSourceFactory.get_provider_for_media_item(media_item)
            source_id = getattr(media_item, "source_identifier", None) or media_item.file_path
            file_bytes = provider.download_file(source_id)

            photo_buffer = BytesIO(file_bytes)
            photo_buffer.name = media_item.file_name  # Telegram needs filename hint
            message = await self.bot.send_photo(
                chat_id=self.channel_id,
                photo=photo_buffer,
                caption=caption,
                reply_markup=reply_markup,
            )
```

Uses lazy import pattern (consistent with existing lazy imports at lines 108-112 in this file).

#### 6B. Modify: `src/services/core/telegram_autopost.py`

**Change 1 — Cloudinary upload (lines 140-143):**

Current:
```python
            upload_result = cloud_service.upload_media(
                file_path=media_item.file_path,
                folder="instagram_stories",
            )
```

New:
```python
            from src.services.media_sources.factory import MediaSourceFactory

            provider = MediaSourceFactory.get_provider_for_media_item(media_item)
            source_id = getattr(media_item, "source_identifier", None) or media_item.file_path
            file_bytes = provider.download_file(source_id)

            upload_result = cloud_service.upload_media_bytes(
                file_bytes=file_bytes,
                filename=media_item.file_name,
                folder="instagram_stories",
            )
```

**Change 2 — Media type detection (lines 206-210 AND 283-287):**

Current:
```python
                    media_type = (
                        "VIDEO"
                        if media_item.file_path.lower().endswith((".mp4", ".mov"))
                        else "IMAGE"
                    )
```

New:
```python
                    media_type = (
                        "VIDEO"
                        if media_item.mime_type
                        and media_item.mime_type.startswith("video")
                        else "IMAGE"
                    )
```

This uses the `mime_type` column already stored in the database instead of parsing file extensions from the path. More reliable and provider-agnostic.

#### 6C. Modify: `src/services/core/posting.py`

**Change in `_post_via_instagram` (lines 388-393):**

Current:
```python
        if not cloud_url:
            logger.info(f"Uploading {media_item.file_name} to cloud storage")
            upload_result = self.cloud_service.upload_media(
                file_path=media_item.file_path,
                folder="storyline/stories",
            )
```

New:
```python
        if not cloud_url:
            logger.info(f"Uploading {media_item.file_name} to cloud storage")
            from src.services.media_sources.factory import MediaSourceFactory

            provider = MediaSourceFactory.get_provider_for_media_item(media_item)
            source_id = getattr(media_item, "source_identifier", None) or media_item.file_path
            file_bytes = provider.download_file(source_id)
            upload_result = self.cloud_service.upload_media_bytes(
                file_bytes=file_bytes,
                filename=media_item.file_name,
                folder="storyline/stories",
            )
```

---

## Test Plan

### New Test Files

#### `tests/src/services/media_sources/__init__.py` (empty)

#### `tests/src/services/media_sources/test_base_provider.py`

Tests for the abstract interface and `MediaFileInfo` dataclass:
- `TestMediaFileInfo`: create with required fields, all fields, equality, inequality
- `TestMediaSourceProviderInterface`: cannot instantiate ABC, incomplete subclass fails, complete subclass succeeds

#### `tests/src/services/media_sources/test_local_provider.py`

Uses `tempfile.TemporaryDirectory` fixture with realistic folder structure:
- `test_is_configured_*`: valid dir, nonexistent, file-not-dir
- `test_list_files_*`: all files, by folder, nonexistent folder, returns MediaFileInfo, excludes unsupported
- `test_download_file_*`: success, not found
- `test_get_file_info_*`: success, not found
- `test_file_exists_*`: true, false, directory
- `test_get_folders_*`: returns sorted, nonexistent base
- `test_calculate_file_hash_*`: consistent, different content differs, not found
- `test_custom_supported_extensions`: custom extension filter
- `test_identifier_is_absolute_path`: identifiers are absolute paths

#### `tests/src/services/media_sources/test_factory.py`

- `test_create_local_provider`: creates LocalMediaProvider
- `test_create_local_provider_default_path`: uses settings.MEDIA_DIR
- `test_create_unsupported_type`: raises ValueError
- `test_get_provider_for_media_item_*`: local, None source_type, missing attribute
- `test_register_provider`: custom provider registration

### Updated Test Files

#### `tests/src/services/test_media_ingestion.py`

Add assertions for new fields in 2 existing tests:
```python
assert call_kwargs["source_type"] == "local"
assert "source_identifier" in call_kwargs
```

#### `tests/src/services/test_cloud_storage.py`

Add 4 new tests:
- `test_upload_media_bytes_success`
- `test_upload_media_bytes_video_resource_type`
- `test_upload_media_bytes_custom_folder`
- `test_upload_media_bytes_error_handling`

### Verification Commands

```bash
# Run new provider tests
pytest tests/src/services/media_sources/ -v

# Run updated existing tests
pytest tests/src/services/test_media_ingestion.py -v
pytest tests/src/services/test_cloud_storage.py -v

# Full test suite
pytest

# Lint and format
ruff check src/ tests/
ruff format --check src/ tests/
```

---

## Documentation Updates

- **CHANGELOG.md**: Add entry under `## [Unreleased]` → `### Added` for provider abstraction layer
- **CLAUDE.md**: No changes needed (provider pattern follows existing BaseService/BaseRepository conventions)

---

## Stress Testing & Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Large video file (50MB+) | `download_file()` loads into memory. Acceptable for Phase 01; streaming can be added later. |
| File deleted between index and post | `download_file()` raises `FileNotFoundError`. PostingService should catch and mark queue item as failed. |
| Media item with NULL source_type | Factory falls back to `"local"` via `getattr(media_item, "source_type", None) or "local"` |
| Media item with NULL source_identifier | Pipeline falls back to `file_path` via `getattr(media_item, "source_identifier", None) or media_item.file_path` |
| Cloudinary BytesIO upload with empty bytes | Cloudinary will reject — same error handling as existing file upload path |
| Migration on DB with existing records | `source_type` defaults to `'local'`, `source_identifier` backfilled from `file_path` |

---

## Verification Checklist

- [ ] Migration `011` applies cleanly on dev database
- [ ] Existing media items have `source_type='local'` and `source_identifier=file_path` after migration
- [ ] `LocalMediaProvider` passes all unit tests with temp directory
- [ ] `MediaSourceFactory.create("local")` returns working provider
- [ ] `MediaSourceFactory.create("google_drive")` raises `ValueError` (not yet registered)
- [ ] `MediaIngestionService.scan_directory()` returns identical results to before refactor
- [ ] Telegram `send_notification` sends photos correctly via BytesIO
- [ ] Autopost flow uploads to Cloudinary via `upload_media_bytes`
- [ ] Media type detection uses `mime_type` column (not file extension)
- [ ] All existing tests pass without modification (except 2 updated assertions)
- [ ] `ruff check` and `ruff format --check` pass
- [ ] CHANGELOG.md updated

---

## What NOT To Do

1. **Do NOT remove `file_path` column or its unique constraint.** It's still needed for backwards compatibility with local media and as the primary identifier for existing records.

2. **Do NOT remove the existing `upload_media(file_path)` method from CloudStorageService.** Keep both `upload_media` and `upload_media_bytes` — the original may still be used by other code paths or tests.

3. **Do NOT make providers extend `BaseService`.** Providers are lightweight data-access objects, not tracked services. They don't need `track_execution` or `set_result_summary`.

4. **Do NOT add Google Drive or S3 logic in this phase.** The factory should raise `ValueError` for unknown types. Provider registration happens in Phase 02+.

5. **Do NOT change the external API of `scan_directory()`.** It still accepts a directory path string and returns the same dict. The refactor is internal only.

6. **Do NOT use `media_item.source_identifier` without fallback.** Always use `getattr(media_item, "source_identifier", None) or media_item.file_path` to handle records that predate the migration.

---

## Files Summary

### New Files (8)
| File | Purpose |
|------|---------|
| `src/services/media_sources/__init__.py` | Module init |
| `src/services/media_sources/base_provider.py` | Abstract interface + MediaFileInfo |
| `src/services/media_sources/local_provider.py` | Local filesystem provider |
| `src/services/media_sources/factory.py` | Provider factory |
| `scripts/migrations/011_media_source_columns.sql` | DB migration |
| `tests/src/services/media_sources/__init__.py` | Test package init |
| `tests/src/services/media_sources/test_base_provider.py` | Interface tests |
| `tests/src/services/media_sources/test_local_provider.py` | Local provider tests (24 tests) |
| `tests/src/services/media_sources/test_factory.py` | Factory tests (8 tests) |

### Modified Files (7)
| File | Changes |
|------|---------|
| `src/models/media_item.py` | Add `source_type`, `source_identifier` columns |
| `src/repositories/media_repository.py` | Add `get_by_source_identifier()`; extend `create()` |
| `src/services/core/media_ingestion.py` | Use LocalMediaProvider internally; pass source fields to repo |
| `src/services/core/telegram_service.py` | Replace `open(file_path)` with provider download + BytesIO |
| `src/services/core/telegram_autopost.py` | Use `upload_media_bytes`; use `mime_type` for type detection |
| `src/services/integrations/cloud_storage.py` | Add `upload_media_bytes()` method |
| `src/services/core/posting.py` | Use provider download + `upload_media_bytes` in `_post_via_instagram` |

### Updated Tests (2)
| File | Changes |
|------|---------|
| `tests/src/services/test_media_ingestion.py` | Assert source_type/source_identifier in 2 tests |
| `tests/src/services/test_cloud_storage.py` | 4 new tests for upload_media_bytes |
