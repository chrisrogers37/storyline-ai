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


class HistoryRepository(BaseRepository):
    """Repository for PostingHistory CRUD operations."""

    def __init__(self):
        super().__init__()

    def get_by_id(self, history_id: str) -> Optional[PostingHistory]:
        """Get history record by ID."""
        return (
            self.db.query(PostingHistory)
            .filter(PostingHistory.id == history_id)
            .first()
        )

    def get_all(
        self,
        status: Optional[str] = None,
        days: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[PostingHistory]:
        """Get all history records with optional filters."""
        query = self.db.query(PostingHistory)

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
        self, media_id: str, limit: Optional[int] = None
    ) -> List[PostingHistory]:
        """Get all history records for a specific media item."""
        query = (
            self.db.query(PostingHistory)
            .filter(PostingHistory.media_item_id == media_id)
            .order_by(PostingHistory.posted_at.desc())
        )

        if limit:
            query = query.limit(limit)

        return query.all()

    def get_by_user_id(
        self, user_id: str, limit: Optional[int] = None
    ) -> List[PostingHistory]:
        """Get all history records for a specific user."""
        query = (
            self.db.query(PostingHistory)
            .filter(PostingHistory.posted_by_user_id == user_id)
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

    def get_stats(self, days: Optional[int] = 30) -> dict:
        """Get posting statistics."""
        since = datetime.utcnow() - timedelta(days=days) if days else datetime.min

        total = (
            self.db.query(func.count(PostingHistory.id))
            .filter(PostingHistory.posted_at >= since)
            .scalar()
        )

        successful = (
            self.db.query(func.count(PostingHistory.id))
            .filter(and_(PostingHistory.posted_at >= since, PostingHistory.success))
            .scalar()
        )

        failed = (
            self.db.query(func.count(PostingHistory.id))
            .filter(and_(PostingHistory.posted_at >= since, ~PostingHistory.success))
            .scalar()
        )

        return {
            "total": total or 0,
            "successful": successful or 0,
            "failed": failed or 0,
            "success_rate": (successful / total * 100) if total > 0 else 0,
        }

    def get_recent_posts(self, hours: int = 24) -> List[PostingHistory]:
        """Get posts from the last N hours."""
        since = datetime.utcnow() - timedelta(hours=hours)
        return (
            self.db.query(PostingHistory)
            .filter(PostingHistory.posted_at >= since)
            .order_by(PostingHistory.posted_at.desc())
            .all()
        )

    def count_by_method(self, method: str, since: datetime) -> int:
        """
        Count posts by posting method since a given time.

        Used for rate limit calculations (e.g., Instagram API posts in last hour).

        Args:
            method: Posting method ('instagram_api' or 'telegram_manual')
            since: Start of time window

        Returns:
            Count of posts matching criteria
        """
        return (
            self.db.query(func.count(PostingHistory.id))
            .filter(
                and_(
                    PostingHistory.posting_method == method,
                    PostingHistory.posted_at >= since,
                    PostingHistory.success,
                )
            )
            .scalar()
        ) or 0
