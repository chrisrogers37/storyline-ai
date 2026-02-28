"""Posting queue repository - CRUD operations for posting queue."""

from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy import and_

from src.repositories.base_repository import BaseRepository
from src.models.posting_queue import PostingQueue


class QueueRepository(BaseRepository):
    """Repository for PostingQueue CRUD operations."""

    def __init__(self):
        super().__init__()

    def get_by_id(
        self, queue_id: str, chat_settings_id: Optional[str] = None
    ) -> Optional[PostingQueue]:
        """Get queue item by ID."""
        return (
            self._tenant_query(PostingQueue, chat_settings_id)
            .filter(PostingQueue.id == queue_id)
            .first()
        )

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

        return (
            self._tenant_query(PostingQueue, chat_settings_id)
            .filter(cast(PostingQueue.id, String).like(f"{id_prefix}%"))
            .first()
        )

    def get_by_media_id(
        self, media_id: str, chat_settings_id: Optional[str] = None
    ) -> Optional[PostingQueue]:
        """Get queue item by media ID."""
        return (
            self._tenant_query(PostingQueue, chat_settings_id)
            .filter(PostingQueue.media_item_id == media_id)
            .first()
        )

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

    def get_overdue_pending(
        self, chat_settings_id: Optional[str] = None
    ) -> List[PostingQueue]:
        """Get all pending queue items whose scheduled_for time has passed.

        Used by the smart delivery reschedule logic to find items that need
        to be bumped forward when delivery is OFF.

        Args:
            chat_settings_id: Optional tenant filter

        Returns:
            List of overdue PostingQueue items, ordered by scheduled_for ASC
        """
        now = datetime.utcnow()
        return (
            self._tenant_query(PostingQueue, chat_settings_id)
            .filter(
                and_(
                    PostingQueue.status == "pending", PostingQueue.scheduled_for <= now
                )
            )
            .order_by(PostingQueue.scheduled_for.asc())
            .all()
        )

    def get_all(
        self, status: Optional[str] = None, chat_settings_id: Optional[str] = None
    ) -> List[PostingQueue]:
        """Get all queue items, optionally filtered by status."""
        query = self._tenant_query(PostingQueue, chat_settings_id)

        if status:
            query = query.filter(PostingQueue.status == status)

        return query.order_by(PostingQueue.scheduled_for.asc()).all()

    def count_pending(self, chat_settings_id: Optional[str] = None) -> int:
        """Count number of pending items."""
        return (
            self._tenant_query(PostingQueue, chat_settings_id)
            .filter(PostingQueue.status == "pending")
            .count()
        )

    def get_oldest_pending(
        self, chat_settings_id: Optional[str] = None
    ) -> Optional[PostingQueue]:
        """Get the oldest pending item."""
        return (
            self._tenant_query(PostingQueue, chat_settings_id)
            .filter(PostingQueue.status == "pending")
            .order_by(PostingQueue.created_at.asc())
            .first()
        )

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

    # NOTE: Unused in production as of 2026-02-10.
    # Planned for automatic retry system when Instagram API posting fails.
    def schedule_retry(
        self, queue_id: str, error_message: str, retry_delay_minutes: int = 5
    ) -> PostingQueue:
        """Schedule a retry for failed queue item."""
        queue_item = self.get_by_id(queue_id)
        if queue_item:
            queue_item.retry_count += 1
            queue_item.last_error = error_message

            if queue_item.retry_count < queue_item.max_retries:
                queue_item.status = "retrying"
                queue_item.next_retry_at = datetime.utcnow() + timedelta(
                    minutes=retry_delay_minutes
                )
            else:
                queue_item.status = "failed"

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

    def delete_all_pending(self, chat_settings_id: Optional[str] = None) -> int:
        """Delete all pending queue items. Returns count of deleted items."""
        count = (
            self._tenant_query(PostingQueue, chat_settings_id)
            .filter(PostingQueue.status == "pending")
            .delete()
        )
        self.db.commit()
        return count

    def shift_slots_forward(
        self, from_item_id: str, chat_settings_id: Optional[str] = None
    ) -> int:
        """
        Shift all pending items forward by one slot when force-posting.

        Each item after the force-posted item inherits the scheduled_for time
        of the item before it. The last item's original time slot is discarded.

        Example:
            Before: A(10:00), B(14:00), C(18:00), D(22:00)
            Force-post A at 09:00
            After:  A(09:00->removed), B(10:00), C(14:00), D(18:00)
                    (22:00 slot discarded)

        Args:
            from_item_id: The item being force-posted (its slot will be inherited by next item)
            chat_settings_id: Optional tenant filter

        Returns:
            Number of items shifted
        """
        from src.utils.logger import logger

        # Get all pending items in scheduled order
        pending_items = self.get_all(
            status="pending", chat_settings_id=chat_settings_id
        )

        if not pending_items:
            return 0

        # Find the index of the force-posted item
        from_index = None
        for i, item in enumerate(pending_items):
            if str(item.id) == from_item_id:
                from_index = i
                break

        if from_index is None:
            logger.warning(f"Item {from_item_id} not found in pending queue")
            return 0

        # Get items AFTER the force-posted one
        items_to_shift = pending_items[from_index + 1 :]

        if not items_to_shift:
            logger.info("No items to shift (force-posted item is last in queue)")
            return 0

        # Build list of times to assign: [from_item's time, next's time, ...]
        # We take all times except the last one (which gets discarded)
        times = [pending_items[from_index].scheduled_for]
        for item in items_to_shift[:-1]:
            times.append(item.scheduled_for)

        # Assign new times to each item
        for i, item in enumerate(items_to_shift):
            old_time = item.scheduled_for
            item.scheduled_for = times[i]
            logger.debug(f"Shifted item {item.id}: {old_time} -> {times[i]}")

        self.db.commit()
        logger.info(f"Shifted {len(items_to_shift)} queue items forward by one slot")
        return len(items_to_shift)
