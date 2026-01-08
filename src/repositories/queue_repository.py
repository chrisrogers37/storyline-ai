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
