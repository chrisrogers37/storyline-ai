"""Media sync service - scheduled reconciliation of media sources with the database."""

from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.exc import SQLAlchemyError

from src.config import defaults
from src.config.settings import settings
from src.repositories.media_repository import MediaRepository
from src.services.base_service import BaseService
from src.services.media_sources.base_provider import (
    MediaFileInfo,
)
from src.services.media_sources.factory import MediaSourceFactory
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
        return (
            self.new
            + self.updated
            + self.deactivated
            + self.reactivated
            + self.unchanged
        )


@dataclass
class SyncContext:
    """Encapsulates shared sync processing state to reduce parameter count."""

    source_type: str
    provider: object
    db_by_identifier: dict
    db_by_hash: dict[str, list]
    seen_identifiers: set[str]
    result: SyncResult


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

    def _resolve_source_config(
        self,
        source_type: Optional[str],
        source_root: Optional[str],
        telegram_chat_id: Optional[int],
    ) -> tuple[str, str]:
        """Resolve source type and root with fallback chain.

        Resolution order: explicit params > per-chat DB config > global env vars.
        """
        if not source_type and not source_root and telegram_chat_id:
            from src.services.core.settings_service import SettingsService

            settings_service = SettingsService()
            try:
                source_type, source_root = settings_service.get_media_source_config(
                    telegram_chat_id
                )
            finally:
                settings_service.close()

        resolved_type = source_type or defaults.DEFAULT_MEDIA_SOURCE_TYPE
        resolved_root = source_root  # None ⇒ unconfigured; caller decides
        if resolved_type == "local" and not resolved_root:
            resolved_root = settings.MEDIA_DIR

        return resolved_type, resolved_root

    def _build_db_lookups(self, source_type: str) -> tuple[list, dict, dict]:
        """Fetch DB records and build O(1) lookup dicts.

        Returns (db_items, db_by_identifier, db_by_hash).
        """
        db_items = self.media_repo.get_active_by_source_type(source_type)
        db_by_identifier = {
            item.source_identifier: item for item in db_items if item.source_identifier
        }
        db_by_hash: dict[str, list] = {}
        for item in db_items:
            db_by_hash.setdefault(item.file_hash, []).append(item)
        return db_items, db_by_identifier, db_by_hash

    def _deactivate_missing_items(self, ctx: SyncContext) -> None:
        """Deactivate DB items whose identifiers were not seen in the provider."""
        for identifier, item in ctx.db_by_identifier.items():
            if identifier not in ctx.seen_identifiers:
                try:
                    self.media_repo.deactivate(str(item.id))
                    ctx.result.deactivated += 1
                    logger.info(
                        f"[MediaSyncService] Deactivated: {item.file_name} "
                        f"(no longer in provider)"
                    )
                except SQLAlchemyError as e:
                    ctx.result.errors += 1
                    error_msg = f"Error deactivating {item.file_name}: {e}"
                    ctx.result.error_details.append(error_msg)
                    logger.error(f"[MediaSyncService] {error_msg}")

    def sync(
        self,
        source_type: Optional[str] = None,
        source_root: Optional[str] = None,
        triggered_by: str = "system",
        telegram_chat_id: Optional[int] = None,
    ) -> SyncResult:
        """Run a full media sync against the configured provider.

        Args:
            source_type: Override chat_settings.media_source_type
            source_root: Override chat_settings.media_source_root
            triggered_by: Who triggered ('system', 'cli', 'scheduler')
            telegram_chat_id: If provided, look up per-chat media source config

        Returns:
            SyncResult with counts for each action taken

        Raises:
            ValueError: If provider is not configured or source_type is invalid
        """
        resolved_type, resolved_root = self._resolve_source_config(
            source_type, source_root, telegram_chat_id
        )

        with self.track_execution(
            method_name="sync",
            triggered_by=triggered_by,
            input_params={
                "source_type": resolved_type,
                "source_root": resolved_root,
            },
        ) as run_id:
            provider = self._create_provider(
                resolved_type, resolved_root, telegram_chat_id
            )
            if not provider.is_configured():
                raise ValueError(
                    f"Media source provider '{resolved_type}' is not configured. "
                    f"Check your settings or run the appropriate setup command."
                )

            logger.info(
                f"[MediaSyncService] Starting sync for {resolved_type} "
                f"(root: {resolved_root})"
            )
            provider_files = provider.list_files()
            logger.info(
                f"[MediaSyncService] Provider reports {len(provider_files)} files"
            )

            db_items, db_by_identifier, db_by_hash = self._build_db_lookups(
                resolved_type
            )
            logger.info(f"[MediaSyncService] Database has {len(db_items)} active items")

            ctx = SyncContext(
                source_type=resolved_type,
                provider=provider,
                db_by_identifier=db_by_identifier,
                db_by_hash=db_by_hash,
                seen_identifiers=set(),
                result=SyncResult(),
            )

            for file_info in provider_files:
                try:
                    self._process_provider_file(file_info, ctx)
                except Exception as e:  # noqa: BLE001 — per-file error must not halt sync
                    self.media_repo.rollback()
                    ctx.result.errors += 1
                    error_msg = f"Error processing {file_info.name}: {e}"
                    ctx.result.error_details.append(error_msg)
                    logger.error(f"[MediaSyncService] {error_msg}")

            self._deactivate_missing_items(ctx)

            logger.info(
                f"[MediaSyncService] Sync complete: "
                f"{ctx.result.new} new, {ctx.result.updated} updated, "
                f"{ctx.result.deactivated} deactivated, "
                f"{ctx.result.reactivated} reactivated, "
                f"{ctx.result.unchanged} unchanged, {ctx.result.errors} errors"
            )

            self.set_result_summary(run_id, ctx.result.to_dict())
            return ctx.result

    def _process_provider_file(
        self, file_info: MediaFileInfo, ctx: SyncContext
    ) -> None:
        """Process a single file from the provider listing.

        Decision tree:
        1. Identifier matches DB record -> unchanged (or update name if changed)
        2. Hash matches existing record -> rename/move
        3. Inactive record with same identifier -> reactivate
        4. No match -> new file, index it
        """
        identifier = file_info.identifier
        ctx.seen_identifiers.add(identifier)

        if self._handle_identifier_match(file_info, ctx):
            return

        file_hash = self._get_file_hash(file_info, ctx.provider)

        if self._handle_hash_match(file_info, file_hash, ctx):
            return

        if self._handle_reactivation(file_info, ctx):
            return

        self._index_new_file(file_info, file_hash, ctx)

    def _handle_identifier_match(
        self, file_info: MediaFileInfo, ctx: SyncContext
    ) -> bool:
        """Case 1: Exact identifier match — update name if changed."""
        existing = ctx.db_by_identifier.get(file_info.identifier)
        if not existing:
            return False

        thumbnail_changed = (
            file_info.thumbnail_url is not None
            and existing.thumbnail_url != file_info.thumbnail_url
        )
        if existing.file_name != file_info.name:
            file_path = self._build_file_path(ctx.source_type, file_info)
            self.media_repo.update_source_info(
                media_id=str(existing.id),
                file_name=file_info.name,
                file_path=file_path,
                thumbnail_url=file_info.thumbnail_url,
            )
            ctx.result.updated += 1
            logger.info(
                f"[MediaSyncService] Updated name: "
                f"{existing.file_name} -> {file_info.name}"
            )
        elif thumbnail_changed:
            self.media_repo.update_source_info(
                media_id=str(existing.id),
                thumbnail_url=file_info.thumbnail_url,
            )
            ctx.result.unchanged += 1
        else:
            ctx.result.unchanged += 1
        return True

    def _handle_hash_match(
        self, file_info: MediaFileInfo, file_hash: str, ctx: SyncContext
    ) -> bool:
        """Case 2: Hash matches an existing active record (rename/move)."""
        if file_hash not in ctx.db_by_hash:
            return False

        existing = ctx.db_by_hash[file_hash][0]
        file_path = self._build_file_path(ctx.source_type, file_info)

        # Skip if another item already holds this file_path to avoid
        # unique constraint violation.
        if self.media_repo.get_by_path(file_path):
            ctx.result.unchanged += 1
            return True

        self.media_repo.update_source_info(
            media_id=str(existing.id),
            file_name=file_info.name,
            file_path=file_path,
            source_identifier=file_info.identifier,
            thumbnail_url=file_info.thumbnail_url,
        )
        ctx.result.updated += 1
        logger.info(
            f"[MediaSyncService] Rename detected: "
            f"{existing.file_name} -> {file_info.name} "
            f"(hash: {file_hash[:8]}...)"
        )
        return True

    def _handle_reactivation(self, file_info: MediaFileInfo, ctx: SyncContext) -> bool:
        """Case 3: Inactive record with same identifier — reactivate."""
        inactive = self.media_repo.get_inactive_by_source_identifier(
            ctx.source_type, file_info.identifier
        )
        if not inactive:
            return False

        self.media_repo.reactivate(str(inactive.id))
        ctx.result.reactivated += 1
        logger.info(f"[MediaSyncService] Reactivated: {inactive.file_name}")
        return True

    def _index_new_file(
        self, file_info: MediaFileInfo, file_hash: str, ctx: SyncContext
    ) -> None:
        """Case 4: Truly new file — check for hash duplicate, then index."""
        # Use in-memory lookup first; this covers same-source-type duplicates.
        # The DB query catches cross-source-type duplicates not in ctx.db_by_hash.
        if file_hash and (
            file_hash in ctx.db_by_hash or self.media_repo.get_active_by_hash(file_hash)
        ):
            ctx.result.unchanged += 1
            logger.info(
                f"[MediaSyncService] Skipped duplicate: {file_info.name} "
                f"(hash {file_hash[:8]}... already exists)"
            )
            return

        file_path = self._build_file_path(ctx.source_type, file_info)
        self.media_repo.create(
            file_path=file_path,
            file_name=file_info.name,
            file_hash=file_hash,
            file_size_bytes=file_info.size_bytes,
            mime_type=file_info.mime_type,
            category=file_info.folder,
            source_type=ctx.source_type,
            source_identifier=file_info.identifier,
            thumbnail_url=file_info.thumbnail_url,
        )
        ctx.result.new += 1
        logger.info(
            f"[MediaSyncService] Indexed new: {file_info.name}"
            + (f" [{file_info.folder}]" if file_info.folder else "")
        )

    def _create_provider(
        self, source_type: str, source_root: str, telegram_chat_id: Optional[int] = None
    ):
        """Create a MediaSourceProvider based on source type and root."""
        if source_type == "local":
            return MediaSourceFactory.create(source_type, base_path=source_root)
        elif source_type == "google_drive":
            chat_id = telegram_chat_id or settings.TELEGRAM_CHANNEL_ID
            return MediaSourceFactory.create(
                source_type,
                root_folder_id=source_root,
                telegram_chat_id=chat_id,
            )
        else:
            return MediaSourceFactory.create(source_type)

    def _get_file_hash(self, file_info: MediaFileInfo, provider) -> str:
        """Get content hash for a file. Uses provider-side hash if available."""
        if file_info.hash:
            return file_info.hash
        return provider.calculate_file_hash(file_info.identifier)

    def _build_file_path(self, source_type: str, file_info: MediaFileInfo) -> str:
        """Build the file_path value for a media item.

        For local: uses the actual filesystem path (the identifier IS the path).
        For cloud: constructs a synthetic path like 'google_drive://file_id'.
        """
        if source_type == "local":
            return file_info.identifier
        else:
            return f"{source_type}://{file_info.identifier}"

    def get_last_sync_info(self) -> Optional[dict]:
        """Get information about the most recent sync run."""
        runs = self.service_run_repo.get_recent_runs(
            service_name="MediaSyncService", limit=1
        )
        if not runs:
            return None

        run = runs[0]
        return {
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": (
                run.completed_at.isoformat() if run.completed_at else None
            ),
            "duration_ms": run.duration_ms,
            "status": run.status,
            "success": run.success,
            "result": run.result_summary,
            "triggered_by": run.triggered_by,
        }
