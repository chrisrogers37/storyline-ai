"""Media sync service - scheduled reconciliation of media sources with the database."""

from dataclasses import dataclass, field
from typing import Optional

from src.config.settings import settings
from src.repositories.media_repository import MediaRepository
from src.services.base_service import BaseService
from src.services.media_sources.base_provider import MediaFileInfo
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
        telegram_chat_id: Optional[int] = None,
    ) -> SyncResult:
        """Run a full media sync against the configured provider.

        Args:
            source_type: Override settings.MEDIA_SOURCE_TYPE
            source_root: Override settings.MEDIA_SOURCE_ROOT
            triggered_by: Who triggered ('system', 'cli', 'scheduler')
            telegram_chat_id: If provided, look up per-chat media source config

        Returns:
            SyncResult with counts for each action taken

        Raises:
            ValueError: If provider is not configured or source_type is invalid
        """
        # Resolution order: explicit params > per-chat DB config > global env vars
        if not source_type and not source_root and telegram_chat_id:
            from src.services.core.settings_service import SettingsService

            settings_service = SettingsService()
            try:
                source_type, source_root = settings_service.get_media_source_config(
                    telegram_chat_id
                )
            finally:
                settings_service.close()

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
            provider = self._create_provider(
                resolved_source_type, resolved_source_root, telegram_chat_id
            )

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
            logger.info(
                f"[MediaSyncService] Provider reports {len(provider_files)} files"
            )

            # Phase 2: Get DB records for this source type
            db_items = self.media_repo.get_active_by_source_type(resolved_source_type)
            logger.info(f"[MediaSyncService] Database has {len(db_items)} active items")

            # Build lookup dicts for O(1) matching
            db_by_identifier = {
                item.source_identifier: item
                for item in db_items
                if item.source_identifier
            }
            db_by_hash: dict[str, list] = {}
            for item in db_items:
                db_by_hash.setdefault(item.file_hash, []).append(item)

            # Track which DB identifiers were seen in the provider
            seen_identifiers: set[str] = set()

            # Phase 3: Process provider files
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
        2. Identifier not in DB, but hash matches existing record -> rename/move
        3. Identifier not in DB, check for inactive record -> reactivate
        4. Identifier not in DB, no hash match -> new file, index it
        """
        identifier = file_info.identifier
        seen_identifiers.add(identifier)

        # Case 1: Exact identifier match in DB
        if identifier in db_by_identifier:
            existing = db_by_identifier[identifier]

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
            logger.info(f"[MediaSyncService] Reactivated: {inactive.file_name}")
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
