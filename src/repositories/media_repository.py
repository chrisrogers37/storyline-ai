"""Media item repository - CRUD operations for media items."""

from typing import Optional, List
from datetime import datetime
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
        query = self.db.query(MediaItem).filter(MediaItem.id == media_id)
        query = self._apply_tenant_filter(query, MediaItem, chat_settings_id)
        return query.first()

    def get_by_path(
        self, file_path: str, chat_settings_id: Optional[str] = None
    ) -> Optional[MediaItem]:
        """Get media item by file path."""
        query = self.db.query(MediaItem).filter(MediaItem.file_path == file_path)
        query = self._apply_tenant_filter(query, MediaItem, chat_settings_id)
        return query.first()

    def get_by_hash(
        self, file_hash: str, chat_settings_id: Optional[str] = None
    ) -> List[MediaItem]:
        """Get all media items with the same hash (duplicate content)."""
        query = self.db.query(MediaItem).filter(MediaItem.file_hash == file_hash)
        query = self._apply_tenant_filter(query, MediaItem, chat_settings_id)
        return query.all()

    def get_by_instagram_media_id(
        self, instagram_media_id: str, chat_settings_id: Optional[str] = None
    ) -> Optional[MediaItem]:
        """Get media item by Instagram Graph API media ID.

        Used by InstagramBackfillService to check if an Instagram media item
        has already been backfilled into the system.
        """
        query = self.db.query(MediaItem).filter(
            MediaItem.instagram_media_id == instagram_media_id
        )
        query = self._apply_tenant_filter(query, MediaItem, chat_settings_id)
        return query.first()

    def get_backfilled_instagram_media_ids(
        self, chat_settings_id: Optional[str] = None
    ) -> set:
        """Get all Instagram media IDs that have been backfilled.

        Returns a set for O(1) lookup during backfill operations.
        This avoids N+1 queries when checking each item during batch backfill.
        """
        query = self.db.query(MediaItem.instagram_media_id).filter(
            MediaItem.instagram_media_id.isnot(None)
        )
        query = self._apply_tenant_filter(query, MediaItem, chat_settings_id)
        results = query.all()
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
        query = self.db.query(MediaItem).filter(
            MediaItem.source_type == source_type,
            MediaItem.source_identifier == source_identifier,
        )
        query = self._apply_tenant_filter(query, MediaItem, chat_settings_id)
        return query.first()

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
        query = self.db.query(MediaItem).filter(
            MediaItem.source_type == source_type,
            MediaItem.is_active == True,  # noqa: E712
        )
        query = self._apply_tenant_filter(query, MediaItem, chat_settings_id)
        return query.all()

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
        query = self.db.query(MediaItem).filter(
            MediaItem.source_type == source_type,
            MediaItem.source_identifier == source_identifier,
            MediaItem.is_active == False,  # noqa: E712
        )
        query = self._apply_tenant_filter(query, MediaItem, chat_settings_id)
        return query.first()

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
        requires_interaction: Optional[bool] = None,
        category: Optional[str] = None,
        limit: Optional[int] = None,
        chat_settings_id: Optional[str] = None,
    ) -> List[MediaItem]:
        """Get all media items with optional filters."""
        query = self.db.query(MediaItem)
        query = self._apply_tenant_filter(query, MediaItem, chat_settings_id)

        if is_active is not None:
            query = query.filter(MediaItem.is_active == is_active)

        if requires_interaction is not None:
            query = query.filter(MediaItem.requires_interaction == requires_interaction)

        if category is not None:
            query = query.filter(MediaItem.category == category)

        query = query.order_by(MediaItem.created_at.desc())

        if limit:
            query = query.limit(limit)

        return query.all()

    def get_categories(self, chat_settings_id: Optional[str] = None) -> List[str]:
        """Get all unique categories."""
        query = self.db.query(MediaItem.category).filter(MediaItem.category.isnot(None))
        query = self._apply_tenant_filter(query, MediaItem, chat_settings_id)
        result = query.distinct().all()
        return [r[0] for r in result]

    def create(
        self,
        file_path: str,
        file_name: str,
        file_hash: str,
        file_size_bytes: int,
        mime_type: Optional[str] = None,
        requires_interaction: bool = False,
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
            requires_interaction=requires_interaction,
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
        """Permanently delete a media item."""
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
        query = self.db.query(
            MediaItem.file_hash,
            func.count(MediaItem.id).label("count"),
            func.array_agg(MediaItem.file_path).label("paths"),
        )
        query = self._apply_tenant_filter(query, MediaItem, chat_settings_id)
        duplicates = (
            query.group_by(MediaItem.file_hash)
            .having(func.count(MediaItem.id) > 1)
            .all()
        )

        return [(d.file_hash, d.count, d.paths) for d in duplicates]

    def get_next_eligible_for_posting(
        self,
        category: Optional[str] = None,
        chat_settings_id: Optional[str] = None,
    ) -> Optional[MediaItem]:
        """
        Get the next eligible media item for posting.

        Filters out inactive, locked, and already-queued items.
        Prioritizes never-posted items, then least-posted, with random tie-breaking.

        Args:
            category: Filter by category, or None for all categories
            chat_settings_id: Optional tenant filter (applied to main query and subqueries)

        Returns:
            The highest-priority eligible MediaItem, or None if no eligible media exists
        """
        query = self.db.query(MediaItem).filter(MediaItem.is_active)
        query = self._apply_tenant_filter(query, MediaItem, chat_settings_id)

        # Filter by category if specified
        if category:
            query = query.filter(MediaItem.category == category)

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
