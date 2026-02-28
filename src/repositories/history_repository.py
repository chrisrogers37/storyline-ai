"""Posting history repository - CRUD operations for posting history."""

from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy import func, and_

from src.repositories.base_repository import BaseRepository
from src.models.posting_history import PostingHistory


@dataclass
class HistoryCreateParams:
    """Bundled parameters for creating a posting history record.

    Required fields come first, optional fields have defaults.
    """

    # Required fields
    media_item_id: str
    queue_item_id: str
    queue_created_at: datetime
    queue_deleted_at: datetime
    scheduled_for: datetime
    posted_at: datetime
    status: str
    success: bool

    # Optional fields with defaults
    media_metadata: Optional[dict] = None
    instagram_media_id: Optional[str] = None
    instagram_permalink: Optional[str] = None
    instagram_story_id: Optional[str] = None
    posting_method: str = "telegram_manual"
    posted_by_user_id: Optional[str] = None
    posted_by_telegram_username: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    chat_settings_id: Optional[str] = None


class HistoryRepository(BaseRepository):
    """Repository for PostingHistory CRUD operations."""

    def __init__(self):
        super().__init__()

    def get_by_id(
        self, history_id: str, chat_settings_id: Optional[str] = None
    ) -> Optional[PostingHistory]:
        """Get history record by ID."""
        return (
            self._tenant_query(PostingHistory, chat_settings_id)
            .filter(PostingHistory.id == history_id)
            .first()
        )

    def get_all(
        self,
        status: Optional[str] = None,
        days: Optional[int] = None,
        limit: Optional[int] = None,
        chat_settings_id: Optional[str] = None,
    ) -> List[PostingHistory]:
        """Get all history records with optional filters."""
        query = self._tenant_query(PostingHistory, chat_settings_id)

        if status:
            query = query.filter(PostingHistory.status == status)

        if days:
            since = datetime.utcnow() - timedelta(days=days)
            query = query.filter(PostingHistory.posted_at >= since)

        query = query.order_by(PostingHistory.posted_at.desc())

        if limit:
            query = query.limit(limit)

        return query.all()

    def get_by_media_id(
        self,
        media_id: str,
        limit: Optional[int] = None,
        chat_settings_id: Optional[str] = None,
    ) -> List[PostingHistory]:
        """Get all history records for a specific media item."""
        query = (
            self._tenant_query(PostingHistory, chat_settings_id)
            .filter(PostingHistory.media_item_id == media_id)
            .order_by(PostingHistory.posted_at.desc())
        )

        if limit:
            query = query.limit(limit)

        return query.all()

    def create(self, params: HistoryCreateParams) -> PostingHistory:
        """Create a new history record."""
        from dataclasses import asdict

        history = PostingHistory(**asdict(params))
        self.db.add(history)
        self.db.commit()
        self.db.refresh(history)
        return history

    def get_recent_posts(
        self, hours: int = 24, chat_settings_id: Optional[str] = None
    ) -> List[PostingHistory]:
        """Get posts from the last N hours."""
        since = datetime.utcnow() - timedelta(hours=hours)
        return (
            self._tenant_query(PostingHistory, chat_settings_id)
            .filter(PostingHistory.posted_at >= since)
            .order_by(PostingHistory.posted_at.desc())
            .all()
        )

    def count_by_method(
        self, method: str, since: datetime, chat_settings_id: Optional[str] = None
    ) -> int:
        """
        Count posts by posting method since a given time.

        Used for rate limit calculations (e.g., Instagram API posts in last hour).

        Args:
            method: Posting method ('instagram_api' or 'telegram_manual')
            since: Start of time window
            chat_settings_id: Optional tenant filter

        Returns:
            Count of posts matching criteria
        """
        return (
            self._tenant_query(PostingHistory, chat_settings_id)
            .with_entities(func.count(PostingHistory.id))
            .filter(
                and_(
                    PostingHistory.posting_method == method,
                    PostingHistory.posted_at >= since,
                    PostingHistory.success,
                )
            )
            .scalar()
            or 0
        )

    def get_by_queue_item_id(self, queue_item_id: str) -> Optional[PostingHistory]:
        """Get the most recent history record for a specific queue item.

        Used to determine what happened to a queue item that's no longer
        in the posting_queue (e.g., after a callback race condition).
        """
        return (
            self.db.query(PostingHistory)
            .filter(PostingHistory.queue_item_id == queue_item_id)
            .order_by(PostingHistory.posted_at.desc())
            .first()
        )
