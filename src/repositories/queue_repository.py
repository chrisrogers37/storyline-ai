"""Posting queue repository - CRUD operations for posting queue."""
from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_

from src.config.database import get_db
from src.models.posting_queue import PostingQueue


class QueueRepository:
    """Repository for PostingQueue CRUD operations."""

    def __init__(self):
        self.db: Session = next(get_db())

    def get_by_id(self, queue_id: str) -> Optional[PostingQueue]:
        """Get queue item by ID."""
        return self.db.query(PostingQueue).filter(PostingQueue.id == queue_id).first()

    def get_by_media_id(self, media_id: str) -> Optional[PostingQueue]:
        """Get queue item by media ID."""
        return self.db.query(PostingQueue).filter(PostingQueue.media_item_id == media_id).first()

    def get_pending(self, limit: Optional[int] = None) -> List[PostingQueue]:
        """Get all pending queue items ready to process."""
        now = datetime.utcnow()
        query = self.db.query(PostingQueue).filter(
            and_(PostingQueue.status == "pending", PostingQueue.scheduled_for <= now)
        ).order_by(PostingQueue.scheduled_for.asc())

        if limit:
            query = query.limit(limit)

        return query.all()

    def get_all(self, status: Optional[str] = None) -> List[PostingQueue]:
        """Get all queue items, optionally filtered by status."""
        query = self.db.query(PostingQueue)

        if status:
            query = query.filter(PostingQueue.status == status)

        return query.order_by(PostingQueue.scheduled_for.asc()).all()

    def count_pending(self) -> int:
        """Count number of pending items."""
        return self.db.query(PostingQueue).filter(PostingQueue.status == "pending").count()

    def get_oldest_pending(self) -> Optional[PostingQueue]:
        """Get the oldest pending item."""
        return (
            self.db.query(PostingQueue)
            .filter(PostingQueue.status == "pending")
            .order_by(PostingQueue.created_at.asc())
            .first()
        )

    def create(self, media_item_id: str, scheduled_for: datetime) -> PostingQueue:
        """Create a new queue item."""
        queue_item = PostingQueue(media_item_id=media_item_id, scheduled_for=scheduled_for)
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

    def update_scheduled_time(self, queue_id: str, scheduled_for: datetime) -> PostingQueue:
        """Update queue item scheduled time."""
        queue_item = self.get_by_id(queue_id)
        if queue_item:
            queue_item.scheduled_for = scheduled_for
            self.db.commit()
            self.db.refresh(queue_item)
        return queue_item

    def set_telegram_message(self, queue_id: str, message_id: int, chat_id: int) -> PostingQueue:
        """Set Telegram message ID for tracking."""
        queue_item = self.get_by_id(queue_id)
        if queue_item:
            queue_item.telegram_message_id = message_id
            queue_item.telegram_chat_id = chat_id
            self.db.commit()
            self.db.refresh(queue_item)
        return queue_item

    def schedule_retry(self, queue_id: str, error_message: str, retry_delay_minutes: int = 5) -> PostingQueue:
        """Schedule a retry for failed queue item."""
        queue_item = self.get_by_id(queue_id)
        if queue_item:
            queue_item.retry_count += 1
            queue_item.last_error = error_message

            if queue_item.retry_count < queue_item.max_retries:
                queue_item.status = "retrying"
                queue_item.next_retry_at = datetime.utcnow() + timedelta(minutes=retry_delay_minutes)
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

    def delete_all_pending(self) -> int:
        """Delete all pending queue items. Returns count of deleted items."""
        count = self.db.query(PostingQueue).filter(PostingQueue.status == "pending").delete()
        self.db.commit()
        return count

    def shift_slots_forward(self, from_item_id: str) -> int:
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

        Returns:
            Number of items shifted
        """
        from src.utils.logger import logger

        # Get all pending items in scheduled order
        pending_items = self.get_all(status="pending")

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
        items_to_shift = pending_items[from_index + 1:]

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
