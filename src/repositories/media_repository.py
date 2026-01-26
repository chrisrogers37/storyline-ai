"""Media item repository - CRUD operations for media items."""

from typing import Optional, List
from datetime import datetime
from sqlalchemy import func

from src.repositories.base_repository import BaseRepository
from src.models.media_item import MediaItem


class MediaRepository(BaseRepository):
    """Repository for MediaItem CRUD operations."""

    def __init__(self):
        super().__init__()

    def get_by_id(self, media_id: str) -> Optional[MediaItem]:
        """Get media item by ID."""
        return self.db.query(MediaItem).filter(MediaItem.id == media_id).first()

    def get_by_path(self, file_path: str) -> Optional[MediaItem]:
        """Get media item by file path."""
        return self.db.query(MediaItem).filter(MediaItem.file_path == file_path).first()

    def get_by_hash(self, file_hash: str) -> List[MediaItem]:
        """Get all media items with the same hash (duplicate content)."""
        return self.db.query(MediaItem).filter(MediaItem.file_hash == file_hash).all()

    def get_all(
        self,
        is_active: Optional[bool] = None,
        requires_interaction: Optional[bool] = None,
        category: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[MediaItem]:
        """Get all media items with optional filters."""
        query = self.db.query(MediaItem)

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

    def get_categories(self) -> List[str]:
        """Get all unique categories."""
        result = (
            self.db.query(MediaItem.category)
            .filter(MediaItem.category.isnot(None))
            .distinct()
            .all()
        )
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
        )
        self.db.add(media_item)
        self.db.commit()
        self.db.refresh(media_item)
        return media_item

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

    def get_duplicates(self) -> List[tuple]:
        """
        Get all duplicate media items (same hash, different paths).

        Returns:
            List of tuples (file_hash, count, paths)
        """
        duplicates = (
            self.db.query(
                MediaItem.file_hash,
                func.count(MediaItem.id).label("count"),
                func.array_agg(MediaItem.file_path).label("paths"),
            )
            .group_by(MediaItem.file_hash)
            .having(func.count(MediaItem.id) > 1)
            .all()
        )

        return [(d.file_hash, d.count, d.paths) for d in duplicates]
