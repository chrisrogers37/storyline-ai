"""Media item repository - CRUD operations for media items."""

from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy import func, and_, exists, select

from src.repositories.base_repository import BaseRepository
from src.models.media_item import MediaItem
from src.models.posting_queue import PostingQueue
from src.models.media_lock import MediaPostingLock


class MediaRepository(BaseRepository):
    """Repository for MediaItem CRUD operations."""

    def __init__(self):
        super().__init__()

    def get_by_id(
        self, media_id: str, chat_settings_id: Optional[str] = None
    ) -> Optional[MediaItem]:
        """Get media item by ID."""
        result = (
            self._tenant_query(MediaItem, chat_settings_id)
            .filter(MediaItem.id == media_id)
            .first()
        )
        self.end_read_transaction()
        return result

    def get_by_path(
        self, file_path: str, chat_settings_id: Optional[str] = None
    ) -> Optional[MediaItem]:
        """Get media item by file path."""
        result = (
            self._tenant_query(MediaItem, chat_settings_id)
            .filter(MediaItem.file_path == file_path)
            .first()
        )
        self.end_read_transaction()
        return result

    def get_by_hash(
        self, file_hash: str, chat_settings_id: Optional[str] = None
    ) -> List[MediaItem]:
        """Get all media items with the same hash (duplicate content)."""
        result = (
            self._tenant_query(MediaItem, chat_settings_id)
            .filter(MediaItem.file_hash == file_hash)
            .all()
        )
        self.end_read_transaction()
        return result

    def get_by_instagram_media_id(
        self, instagram_media_id: str, chat_settings_id: Optional[str] = None
    ) -> Optional[MediaItem]:
        """Get media item by Instagram Graph API media ID.

        Used by InstagramBackfillService to check if an Instagram media item
        has already been backfilled into the system.
        """
        result = (
            self._tenant_query(MediaItem, chat_settings_id)
            .filter(MediaItem.instagram_media_id == instagram_media_id)
            .first()
        )
        self.end_read_transaction()
        return result

    def get_backfilled_instagram_media_ids(
        self, chat_settings_id: Optional[str] = None
    ) -> set:
        """Get all Instagram media IDs that have been backfilled.

        Returns a set for O(1) lookup during backfill operations.
        This avoids N+1 queries when checking each item during batch backfill.
        """
        results = (
            self._tenant_query(MediaItem, chat_settings_id)
            .with_entities(MediaItem.instagram_media_id)
            .filter(MediaItem.instagram_media_id.isnot(None))
            .all()
        )
        self.end_read_transaction()
        return {r[0] for r in results}

    def get_by_source_identifier(
        self,
        source_type: str,
        source_identifier: str,
        chat_settings_id: Optional[str] = None,
    ) -> Optional[MediaItem]:
        """Get media item by provider-specific source identifier.

        Args:
            source_type: Provider type (e.g., 'local', 'google_drive')
            source_identifier: Provider-specific unique ID
            chat_settings_id: Optional tenant filter

        Returns:
            MediaItem if found, None otherwise
        """
        result = (
            self._tenant_query(MediaItem, chat_settings_id)
            .filter(
                MediaItem.source_type == source_type,
                MediaItem.source_identifier == source_identifier,
            )
            .first()
        )
        self.end_read_transaction()
        return result

    def get_active_by_source_type(
        self, source_type: str, chat_settings_id: Optional[str] = None
    ) -> List[MediaItem]:
        """Get all active media items for a given source type.

        Used by MediaSyncService to build a lookup dict of known items
        for reconciliation against the provider's file listing.

        Args:
            source_type: Provider type string (e.g., 'local', 'google_drive')
            chat_settings_id: Optional tenant filter

        Returns:
            List of active MediaItem instances for the given source type
        """
        result = (
            self._tenant_query(MediaItem, chat_settings_id)
            .filter(
                MediaItem.source_type == source_type,
                MediaItem.is_active == True,  # noqa: E712
            )
            .all()
        )
        self.end_read_transaction()
        return result

    def get_inactive_by_source_identifier(
        self,
        source_type: str,
        source_identifier: str,
        chat_settings_id: Optional[str] = None,
    ) -> Optional[MediaItem]:
        """Get an inactive media item by source identifier.

        Used by MediaSyncService to detect reappeared files that were
        previously deactivated.

        Args:
            source_type: Provider type string
            source_identifier: Provider-specific unique ID
            chat_settings_id: Optional tenant filter

        Returns:
            Inactive MediaItem if found, None otherwise
        """
        result = (
            self._tenant_query(MediaItem, chat_settings_id)
            .filter(
                MediaItem.source_type == source_type,
                MediaItem.source_identifier == source_identifier,
                MediaItem.is_active == False,  # noqa: E712
            )
            .first()
        )
        self.end_read_transaction()
        return result

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

    def get_all(
        self,
        is_active: Optional[bool] = None,
        category: Optional[str] = None,
        limit: Optional[int] = None,
        chat_settings_id: Optional[str] = None,
    ) -> List[MediaItem]:
        """Get all media items with optional filters."""
        query = self._tenant_query(MediaItem, chat_settings_id)

        if is_active is not None:
            query = query.filter(MediaItem.is_active == is_active)

        if category is not None:
            query = query.filter(MediaItem.category == category)

        query = query.order_by(MediaItem.created_at.desc())

        if limit:
            query = query.limit(limit)

        result = query.all()
        self.end_read_transaction()
        return result

    def get_categories(self, chat_settings_id: Optional[str] = None) -> List[str]:
        """Get all unique categories."""
        result = (
            self._tenant_query(MediaItem, chat_settings_id)
            .with_entities(MediaItem.category)
            .filter(MediaItem.category.isnot(None))
            .distinct()
            .all()
        )
        self.end_read_transaction()
        return [r[0] for r in result]

    def create(
        self,
        file_path: str,
        file_name: str,
        file_hash: str,
        file_size_bytes: int,
        mime_type: Optional[str] = None,
        category: Optional[str] = None,
        title: Optional[str] = None,
        link_url: Optional[str] = None,
        caption: Optional[str] = None,
        tags: Optional[List[str]] = None,
        custom_metadata: Optional[dict] = None,
        indexed_by_user_id: Optional[str] = None,
        source_type: str = "local",
        source_identifier: Optional[str] = None,
        chat_settings_id: Optional[str] = None,
    ) -> MediaItem:
        """Create a new media item."""
        media_item = MediaItem(
            file_path=file_path,
            file_name=file_name,
            file_hash=file_hash,
            file_size=file_size_bytes,
            mime_type=mime_type,
            category=category,
            title=title,
            link_url=link_url,
            caption=caption,
            tags=tags,
            custom_metadata=custom_metadata,
            indexed_by_user_id=indexed_by_user_id,
            source_type=source_type,
            source_identifier=source_identifier or file_path,
            chat_settings_id=chat_settings_id,
        )
        self.db.add(media_item)
        self.db.commit()
        self.db.refresh(media_item)
        return media_item

    # NOTE: Unused in production as of 2026-02-10.
    # Planned for Phase 3 media editing UI (web frontend).
    def update_metadata(
        self,
        media_id: str,
        title: Optional[str] = None,
        link_url: Optional[str] = None,
        caption: Optional[str] = None,
        tags: Optional[List[str]] = None,
        custom_metadata: Optional[dict] = None,
    ) -> MediaItem:
        """Update media item metadata."""
        media_item = self.get_by_id(media_id)
        if media_item:
            if title is not None:
                media_item.title = title
            if link_url is not None:
                media_item.link_url = link_url
            if caption is not None:
                media_item.caption = caption
            if tags is not None:
                media_item.tags = tags
            if custom_metadata is not None:
                media_item.custom_metadata = custom_metadata

            media_item.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(media_item)
        return media_item

    def increment_times_posted(self, media_id: str) -> MediaItem:
        """Increment times posted counter and update last_posted_at."""
        media_item = self.get_by_id(media_id)
        if media_item:
            media_item.times_posted += 1
            media_item.last_posted_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(media_item)
        return media_item

    def update_cloud_info(
        self,
        media_id: str,
        cloud_url: Optional[str] = None,
        cloud_public_id: Optional[str] = None,
        cloud_uploaded_at: Optional[datetime] = None,
        cloud_expires_at: Optional[datetime] = None,
    ) -> MediaItem:
        """
        Update cloud storage information for a media item.

        Used when uploading to/deleting from Cloudinary for Instagram API posting.
        Pass None values to clear the cloud info after successful posting.

        Args:
            media_id: Media item ID
            cloud_url: Cloudinary URL (or None to clear)
            cloud_public_id: Cloudinary public_id (or None to clear)
            cloud_uploaded_at: Upload timestamp (or None to clear)
            cloud_expires_at: URL expiry timestamp (or None to clear)

        Returns:
            Updated MediaItem
        """
        media_item = self.get_by_id(media_id)
        if media_item:
            media_item.cloud_url = cloud_url
            media_item.cloud_public_id = cloud_public_id
            media_item.cloud_uploaded_at = cloud_uploaded_at
            media_item.cloud_expires_at = cloud_expires_at
            media_item.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(media_item)
        return media_item

    def clear_stale_cloud_info(self, retention_hours: int) -> int:
        """Clear cloud storage fields on media items past the retention window.

        Called by the safety-net cleanup loop after Cloudinary resources have
        been deleted. Prevents stale URLs from lingering in the database.

        Args:
            retention_hours: Items uploaded more than this many hours ago are cleared.

        Returns:
            Number of rows updated.
        """
        cutoff = datetime.utcnow() - timedelta(hours=retention_hours)
        count = (
            self.db.query(MediaItem)
            .filter(
                MediaItem.cloud_public_id.isnot(None),
                MediaItem.cloud_uploaded_at.isnot(None),
                MediaItem.cloud_uploaded_at < cutoff,
            )
            .update(
                {
                    MediaItem.cloud_url: None,
                    MediaItem.cloud_public_id: None,
                    MediaItem.cloud_uploaded_at: None,
                    MediaItem.cloud_expires_at: None,
                },
                synchronize_session="fetch",
            )
        )
        self.db.commit()
        return count

    def deactivate(self, media_id: str) -> MediaItem:
        """Deactivate a media item."""
        media_item = self.get_by_id(media_id)
        if media_item:
            media_item.is_active = False
            media_item.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(media_item)
        return media_item

    def delete(self, media_id: str) -> bool:
        """Permanently delete a media item.

        WARNING: Does not clean up Cloudinary resources. Use
        MediaLifecycleService.delete_media_item() for full cleanup.
        """
        media_item = self.get_by_id(media_id)
        if media_item:
            self.db.delete(media_item)
            self.db.commit()
            return True
        return False

    def get_duplicates(self, chat_settings_id: Optional[str] = None) -> List[tuple]:
        """
        Get all duplicate media items (same hash, different paths).

        Returns:
            List of tuples (file_hash, count, paths)
        """
        duplicates = (
            self._tenant_query(MediaItem, chat_settings_id)
            .with_entities(
                MediaItem.file_hash,
                func.count(MediaItem.id).label("count"),
                func.array_agg(MediaItem.file_path).label("paths"),
            )
            .group_by(MediaItem.file_hash)
            .having(func.count(MediaItem.id) > 1)
            .all()
        )

        self.end_read_transaction()
        return [(d.file_hash, d.count, d.paths) for d in duplicates]

    def count_active(self, chat_settings_id: Optional[str] = None) -> int:
        """Count active media items."""
        result = (
            self._tenant_query(MediaItem, chat_settings_id)
            .with_entities(func.count(MediaItem.id))
            .filter(MediaItem.is_active.is_(True))
            .scalar()
        )
        self.end_read_transaction()
        return result or 0

    def count_inactive(self, chat_settings_id: Optional[str] = None) -> int:
        """Count inactive media items."""
        result = (
            self._tenant_query(MediaItem, chat_settings_id)
            .with_entities(func.count(MediaItem.id))
            .filter(MediaItem.is_active.is_(False))
            .scalar()
        )
        self.end_read_transaction()
        return result or 0

    def count_by_posting_status(self, chat_settings_id: Optional[str] = None) -> dict:
        """Count active media grouped by posting status."""
        from sqlalchemy import case

        query = (
            self._tenant_query(MediaItem, chat_settings_id)
            .with_entities(
                case(
                    (MediaItem.times_posted == 0, 0),
                    (MediaItem.times_posted == 1, 1),
                    else_=2,
                ).label("bucket"),
                func.count(MediaItem.id),
            )
            .filter(MediaItem.is_active.is_(True))
            .group_by("bucket")
        )
        rows = query.all()
        self.end_read_transaction()
        buckets = {row[0]: row[1] for row in rows}
        return {
            "never_posted": buckets.get(0, 0),
            "posted_once": buckets.get(1, 0),
            "posted_multiple": buckets.get(2, 0),
        }

    def count_dead_content_by_category(
        self, min_age_days: int = 30, chat_settings_id: Optional[str] = None
    ) -> list:
        """Count active items that have never been posted, grouped by category.

        "Dead content" = is_active=True, times_posted=0, and older than min_age_days.
        Returns list of {"category": str, "dead_count": int}.
        """
        from datetime import timezone

        cutoff = datetime.now(timezone.utc) - timedelta(days=min_age_days)
        coalesced = func.coalesce(MediaItem.category, "uncategorized")
        rows = (
            self._tenant_query(MediaItem, chat_settings_id)
            .with_entities(coalesced.label("category"), func.count(MediaItem.id))
            .filter(
                MediaItem.is_active.is_(True),
                MediaItem.times_posted == 0,
                MediaItem.created_at <= cutoff,
            )
            .group_by(coalesced)
            .order_by(coalesced)
            .all()
        )
        self.end_read_transaction()
        return [{"category": cat, "dead_count": count} for cat, count in rows]

    def count_by_category(self, chat_settings_id: Optional[str] = None) -> dict:
        """Count active media grouped by category."""
        rows = (
            self._tenant_query(MediaItem, chat_settings_id)
            .with_entities(MediaItem.category, func.count(MediaItem.id))
            .filter(MediaItem.is_active.is_(True))
            .group_by(MediaItem.category)
            .all()
        )
        self.end_read_transaction()
        return {(cat or "uncategorized"): count for cat, count in rows}

    def get_next_eligible_for_posting(
        self,
        category: Optional[str] = None,
        chat_settings_id: Optional[str] = None,
        exclude_ids: Optional[List[str]] = None,
    ) -> Optional[MediaItem]:
        """
        Get the next eligible media item for posting.

        Filters out inactive, locked, already-queued, and hash-duplicate-of-locked items.
        Prioritizes never-posted items, then least-posted, with random tie-breaking.

        Args:
            category: Filter by category, or None for all categories
            chat_settings_id: Optional tenant filter (applied to main query and subqueries)
            exclude_ids: Optional list of media item IDs to exclude (for preview)

        Returns:
            The highest-priority eligible MediaItem, or None if no eligible media exists
        """
        query = self._tenant_query(MediaItem, chat_settings_id).filter(
            MediaItem.is_active
        )

        # Filter by category if specified
        if category:
            query = query.filter(MediaItem.category == category)

        # Exclude specific IDs (used by queue preview)
        if exclude_ids:
            query = query.filter(~MediaItem.id.in_(exclude_ids))

        # Exclude already queued items (tenant-scoped subquery)
        queued_where = [PostingQueue.media_item_id == MediaItem.id]
        if chat_settings_id:
            queued_where.append(PostingQueue.chat_settings_id == chat_settings_id)
        queued_subquery = exists(select(PostingQueue.id).where(and_(*queued_where)))
        query = query.filter(~queued_subquery)

        # Exclude locked items (both permanent and TTL locks, tenant-scoped subquery)
        now = datetime.utcnow()
        lock_where = [
            MediaPostingLock.media_item_id == MediaItem.id,
            (MediaPostingLock.locked_until.is_(None))
            | (MediaPostingLock.locked_until > now),
        ]
        if chat_settings_id:
            lock_where.append(MediaPostingLock.chat_settings_id == chat_settings_id)
        locked_subquery = exists(select(MediaPostingLock.id).where(and_(*lock_where)))
        query = query.filter(~locked_subquery)

        # Exclude items whose file_hash matches any currently-locked item's hash
        # (prevents posting duplicate files stored under different filenames)
        locked_hashes_subquery = (
            select(MediaItem.file_hash)
            .join(MediaPostingLock, MediaPostingLock.media_item_id == MediaItem.id)
            .where(
                (MediaPostingLock.locked_until.is_(None))
                | (MediaPostingLock.locked_until > now)
            )
            .where(MediaItem.file_hash.isnot(None))
        )
        query = query.filter(
            (MediaItem.file_hash.is_(None))
            | (~MediaItem.file_hash.in_(locked_hashes_subquery))
        )

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
        result = query.first()
        self.end_read_transaction()
        return result

    def get_active_by_hash(
        self, file_hash: str, chat_settings_id: Optional[str] = None
    ) -> Optional[MediaItem]:
        """Get an active media item by file hash."""
        result = (
            self._tenant_query(MediaItem, chat_settings_id)
            .filter(MediaItem.is_active.is_(True), MediaItem.file_hash == file_hash)
            .first()
        )
        self.end_read_transaction()
        return result

    def count_eligible(self, chat_settings_id: Optional[str] = None) -> int:
        """Count media items eligible for posting right now.

        Excludes inactive, locked, queued, and hash-duplicates of locked items.
        """
        now = datetime.utcnow()
        query = (
            self._tenant_query(MediaItem, chat_settings_id)
            .with_entities(func.count(MediaItem.id))
            .filter(MediaItem.is_active.is_(True))
        )

        # Exclude queued
        queued_where = [PostingQueue.media_item_id == MediaItem.id]
        if chat_settings_id:
            queued_where.append(PostingQueue.chat_settings_id == chat_settings_id)
        query = query.filter(
            ~exists(select(PostingQueue.id).where(and_(*queued_where)))
        )

        # Exclude locked
        lock_where = [
            MediaPostingLock.media_item_id == MediaItem.id,
            (MediaPostingLock.locked_until.is_(None))
            | (MediaPostingLock.locked_until > now),
        ]
        if chat_settings_id:
            lock_where.append(MediaPostingLock.chat_settings_id == chat_settings_id)
        query = query.filter(
            ~exists(select(MediaPostingLock.id).where(and_(*lock_where)))
        )

        # Exclude hash-duplicates of locked items
        locked_hashes_subquery = (
            select(MediaItem.file_hash)
            .join(MediaPostingLock, MediaPostingLock.media_item_id == MediaItem.id)
            .where(
                (MediaPostingLock.locked_until.is_(None))
                | (MediaPostingLock.locked_until > now)
            )
            .where(MediaItem.file_hash.isnot(None))
        )
        query = query.filter(
            (MediaItem.file_hash.is_(None))
            | (~MediaItem.file_hash.in_(locked_hashes_subquery))
        )

        result = query.scalar()
        self.end_read_transaction()
        return result or 0

    def count_eligible_by_category(
        self, chat_settings_id: Optional[str] = None
    ) -> dict:
        """Count eligible media per category (not locked, not queued, not hash-duped)."""
        now = datetime.utcnow()
        query = (
            self._tenant_query(MediaItem, chat_settings_id)
            .with_entities(MediaItem.category, func.count(MediaItem.id))
            .filter(MediaItem.is_active.is_(True))
        )

        queued_where = [PostingQueue.media_item_id == MediaItem.id]
        if chat_settings_id:
            queued_where.append(PostingQueue.chat_settings_id == chat_settings_id)
        query = query.filter(
            ~exists(select(PostingQueue.id).where(and_(*queued_where)))
        )

        lock_where = [
            MediaPostingLock.media_item_id == MediaItem.id,
            (MediaPostingLock.locked_until.is_(None))
            | (MediaPostingLock.locked_until > now),
        ]
        if chat_settings_id:
            lock_where.append(MediaPostingLock.chat_settings_id == chat_settings_id)
        query = query.filter(
            ~exists(select(MediaPostingLock.id).where(and_(*lock_where)))
        )

        locked_hashes_subquery = (
            select(MediaItem.file_hash)
            .join(MediaPostingLock, MediaPostingLock.media_item_id == MediaItem.id)
            .where(
                (MediaPostingLock.locked_until.is_(None))
                | (MediaPostingLock.locked_until > now)
            )
            .where(MediaItem.file_hash.isnot(None))
        )
        query = query.filter(
            (MediaItem.file_hash.is_(None))
            | (~MediaItem.file_hash.in_(locked_hashes_subquery))
        )

        rows = query.group_by(MediaItem.category).all()
        self.end_read_transaction()
        return {(cat or "uncategorized"): count for cat, count in rows}

    def get_duplicate_hash_groups(
        self, chat_settings_id: Optional[str] = None
    ) -> List[dict]:
        """Get groups of active items sharing the same file_hash.

        Returns list of dicts: {hash, count, file_names, ids}.
        """
        subq = (
            self._tenant_query(MediaItem, chat_settings_id)
            .with_entities(
                MediaItem.file_hash,
                func.count(MediaItem.id).label("cnt"),
            )
            .filter(
                MediaItem.is_active.is_(True),
                MediaItem.file_hash.isnot(None),
            )
            .group_by(MediaItem.file_hash)
            .having(func.count(MediaItem.id) > 1)
            .subquery()
        )

        rows = (
            self.db.query(
                MediaItem.file_hash,
                MediaItem.id,
                MediaItem.file_name,
                MediaItem.times_posted,
                MediaItem.last_posted_at,
            )
            .join(subq, MediaItem.file_hash == subq.c.file_hash)
            .filter(MediaItem.is_active.is_(True))
            .order_by(MediaItem.file_hash, MediaItem.times_posted.desc())
            .all()
        )
        self.end_read_transaction()

        # Group by hash
        groups: dict = {}
        for row in rows:
            h = row.file_hash
            if h not in groups:
                groups[h] = {"hash": h, "items": []}
            groups[h]["items"].append(
                {
                    "id": str(row.id),
                    "file_name": row.file_name,
                    "times_posted": row.times_posted,
                    "last_posted_at": row.last_posted_at,
                }
            )
        return list(groups.values())

    def deactivate_by_ids(self, media_ids: List[str]) -> int:
        """Bulk deactivate media items by ID list. Returns count deactivated."""
        if not media_ids:
            return 0
        count = (
            self.db.query(MediaItem)
            .filter(MediaItem.id.in_(media_ids))
            .update({MediaItem.is_active: False}, synchronize_session="fetch")
        )
        self.db.commit()
        return count
