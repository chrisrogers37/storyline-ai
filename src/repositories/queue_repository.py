"""Posting queue repository - CRUD operations for posting queue."""

from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy import and_

from src.repositories.base_repository import BaseRepository
from src.models.posting_queue import PostingQueue
from src.utils.logger import logger


class QueueRepository(BaseRepository):
    """Repository for PostingQueue CRUD operations."""

    def __init__(self):
        super().__init__()

    def get_by_id(
        self, queue_id: str, chat_settings_id: Optional[str] = None
    ) -> Optional[PostingQueue]:
        """Get queue item by ID."""
        result = (
            self._tenant_query(PostingQueue, chat_settings_id)
            .filter(PostingQueue.id == queue_id)
            .first()
        )
        self.end_read_transaction()
        return result

    def claim_for_processing(self, queue_id: str) -> Optional[PostingQueue]:
        """Atomically claim a queue item for callback processing.

        Uses SELECT ... FOR UPDATE SKIP LOCKED so that if two callbacks hit
        the same item concurrently, the second gets None instead of a
        duplicate.

        Items arrive in 'processing' from the scheduler. Callbacks may also
        arrive when items are still 'pending' (e.g. /next force-post).
        We accept both states.

        Returns:
            The claimed PostingQueue item (now in 'processing'), or None if
            already claimed or not found.
        """
        queue_item = (
            self.db.query(PostingQueue)
            .filter(
                PostingQueue.id == queue_id,
                PostingQueue.status.in_(["pending", "processing"]),
            )
            .with_for_update(skip_locked=True)
            .first()
        )
        if queue_item is None:
            return None
        queue_item.status = "processing"
        self.db.commit()
        return queue_item

    def get_by_id_prefix(
        self, id_prefix: str, chat_settings_id: Optional[str] = None
    ) -> Optional[PostingQueue]:
        """Get queue item by ID prefix (for shortened callback data).

        Used when Telegram callback data is too long and we need to use
        shortened UUIDs. Returns the first matching item.

        Args:
            id_prefix: First N characters of a UUID (typically 8)
            chat_settings_id: Optional tenant filter

        Returns:
            PostingQueue item or None if not found
        """
        from sqlalchemy import cast, String

        result = (
            self._tenant_query(PostingQueue, chat_settings_id)
            .filter(cast(PostingQueue.id, String).like(f"{id_prefix}%"))
            .first()
        )
        self.end_read_transaction()
        return result

    def get_by_media_id(
        self, media_id: str, chat_settings_id: Optional[str] = None
    ) -> Optional[PostingQueue]:
        """Get queue item by media ID."""
        result = (
            self._tenant_query(PostingQueue, chat_settings_id)
            .filter(PostingQueue.media_item_id == media_id)
            .first()
        )
        self.end_read_transaction()
        return result

    def get_pending(
        self, limit: Optional[int] = None, chat_settings_id: Optional[str] = None
    ) -> List[PostingQueue]:
        """Get pending queue items ready to process.

        Uses FOR UPDATE SKIP LOCKED to prevent concurrent scheduler
        instances from claiming the same rows.
        """
        now = datetime.utcnow()
        query = self._tenant_query(PostingQueue, chat_settings_id).filter(
            and_(PostingQueue.status == "pending", PostingQueue.scheduled_for <= now)
        )
        query = query.order_by(PostingQueue.scheduled_for.asc())

        if limit:
            query = query.limit(limit)

        query = query.with_for_update(skip_locked=True)

        return query.all()

    def get_all(
        self, status: Optional[str] = None, chat_settings_id: Optional[str] = None
    ) -> List[PostingQueue]:
        """Get all queue items, optionally filtered by status."""
        query = self._tenant_query(PostingQueue, chat_settings_id)

        if status:
            query = query.filter(PostingQueue.status == status)

        result = query.order_by(PostingQueue.scheduled_for.asc()).all()
        self.end_read_transaction()
        return result

    def get_all_with_media(
        self,
        status: Optional[str] = None,
        chat_settings_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list:
        """Get queue items with joined media info (file_name, category).

        Returns list of (PostingQueue, file_name, category) tuples.
        """
        from src.models.media_item import MediaItem

        query = (
            self._tenant_query(PostingQueue, chat_settings_id)
            .outerjoin(MediaItem, PostingQueue.media_item_id == MediaItem.id)
            .add_columns(MediaItem.file_name, MediaItem.category)
        )

        if status:
            query = query.filter(PostingQueue.status == status)

        query = query.order_by(PostingQueue.scheduled_for.asc())
        if limit is not None:
            query = query.limit(limit)
        result = query.all()
        self.end_read_transaction()
        return result

    def count_by_status(
        self,
        statuses: list[str],
        chat_settings_id: Optional[str] = None,
    ) -> int:
        """Count items matching any of the given statuses."""
        result = (
            self._tenant_query(PostingQueue, chat_settings_id)
            .filter(PostingQueue.status.in_(statuses))
            .count()
        )
        self.end_read_transaction()
        return result

    def count_pending(self, chat_settings_id: Optional[str] = None) -> int:
        """Count number of pending items."""
        result = (
            self._tenant_query(PostingQueue, chat_settings_id)
            .filter(PostingQueue.status == "pending")
            .count()
        )
        self.end_read_transaction()
        return result

    def get_oldest_pending(
        self, chat_settings_id: Optional[str] = None
    ) -> Optional[PostingQueue]:
        """Get the oldest pending item."""
        result = (
            self._tenant_query(PostingQueue, chat_settings_id)
            .filter(PostingQueue.status == "pending")
            .order_by(PostingQueue.created_at.asc())
            .first()
        )
        self.end_read_transaction()
        return result

    def create(
        self,
        media_item_id: str,
        scheduled_for: datetime,
        chat_settings_id: Optional[str] = None,
    ) -> PostingQueue:
        """Create a new queue item."""
        queue_item = PostingQueue(
            media_item_id=media_item_id,
            scheduled_for=scheduled_for,
            chat_settings_id=chat_settings_id,
        )
        self.db.add(queue_item)
        self.db.commit()
        self.db.refresh(queue_item)
        return queue_item

    def update_status(self, queue_id: str, status: str) -> PostingQueue:
        """Update queue item status."""
        queue_item = self.get_by_id(queue_id)
        if queue_item:
            queue_item.status = status
            self.db.commit()
            self.db.refresh(queue_item)
        return queue_item

    def update_scheduled_time(
        self, queue_id: str, scheduled_for: datetime
    ) -> PostingQueue:
        """Update queue item scheduled time."""
        queue_item = self.get_by_id(queue_id)
        if queue_item:
            queue_item.scheduled_for = scheduled_for
            self.db.commit()
            self.db.refresh(queue_item)
        return queue_item

    def set_telegram_message(
        self, queue_id: str, message_id: int, chat_id: int
    ) -> PostingQueue:
        """Set Telegram message ID for tracking."""
        queue_item = self.get_by_id(queue_id)
        if queue_item:
            queue_item.telegram_message_id = message_id
            queue_item.telegram_chat_id = chat_id
            self.db.commit()
            self.db.refresh(queue_item)
        return queue_item

    def delete(self, queue_id: str) -> bool:
        """Delete a queue item (after moving to history)."""
        queue_item = self.get_by_id(queue_id)
        if queue_item:
            self.db.delete(queue_item)
            self.db.commit()
            return True
        return False

    def delete_stale_pending(self, max_age_minutes: int = 10) -> int:
        """Delete pending items that were never sent to Telegram.

        Defense-in-depth for items orphaned by crashes or restarts.
        Normal failures delete the queue item immediately in
        _send_to_telegram(); this catches anything that slipped through.

        Args:
            max_age_minutes: Minutes after which an unsent pending item
                is considered stale and deleted (default: 10).

        Returns:
            Number of items deleted.
        """
        cutoff = datetime.utcnow() - timedelta(minutes=max_age_minutes)
        stale = (
            self.db.query(PostingQueue)
            .filter(
                PostingQueue.status == "pending",
                PostingQueue.telegram_message_id.is_(None),
                PostingQueue.created_at <= cutoff,
            )
            .all()
        )

        count = len(stale)
        for item in stale:
            logger.info(
                f"Deleting stale queue item {item.id} "
                f"(status={item.status}, age={datetime.utcnow() - item.created_at})"
            )
            self.db.delete(item)

        if count:
            self.db.commit()
            logger.info(f"Cleaned up {count} stale pending/failed queue items")

        return count

    def discard_abandoned_processing(self, abandon_threshold_hours: int = 24) -> int:
        """Delete queue items stuck in 'processing' for too long.

        Items in 'processing' have already been sent to Telegram and are
        waiting for user action (Posted/Skip/Reject). If nobody acts within
        the threshold, the notification is stale and the item is discarded.

        This intentionally does NOT reset items back to 'pending' — doing so
        would re-send the Telegram notification, creating an infinite
        notify-reset-notify loop.

        Args:
            abandon_threshold_hours: Hours after which a processing item is
                considered abandoned and deleted (default: 24).

        Returns:
            Number of items discarded.
        """
        cutoff = datetime.utcnow() - timedelta(hours=abandon_threshold_hours)
        abandoned = (
            self.db.query(PostingQueue)
            .filter(
                PostingQueue.status == "processing",
                PostingQueue.scheduled_for <= cutoff,
            )
            .all()
        )

        for item in abandoned:
            logger.warning(
                f"Discarding abandoned queue item {item.id} "
                f"(scheduled_for={item.scheduled_for}, "
                f"over {abandon_threshold_hours}h old)"
            )
            self.db.delete(item)

        if abandoned:
            self.db.commit()

        return len(abandoned)

    def get_pending_with_telegram_message(
        self, telegram_chat_id: int
    ) -> List[PostingQueue]:
        """Get pending/processing queue items that have been sent to Telegram.

        Used to find all active notifications for a chat so their captions
        and keyboards can be batch-updated (e.g., after an account switch).

        Args:
            telegram_chat_id: The Telegram chat ID to filter by

        Returns:
            List of PostingQueue items with telegram_message_id set
        """
        result = (
            self.db.query(PostingQueue)
            .filter(
                PostingQueue.telegram_chat_id == telegram_chat_id,
                PostingQueue.telegram_message_id.isnot(None),
                PostingQueue.status.in_(["pending", "processing"]),
            )
            .order_by(PostingQueue.scheduled_for.asc())
            .all()
        )
        self.end_read_transaction()
        return result

    def delete_all_pending(self, chat_settings_id: Optional[str] = None) -> int:
        """Delete all pending queue items. Returns count of deleted items."""
        count = (
            self._tenant_query(PostingQueue, chat_settings_id)
            .filter(PostingQueue.status == "pending")
            .delete()
        )
        self.db.commit()
        return count
