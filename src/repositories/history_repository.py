"""Posting history repository - CRUD operations for posting history."""

from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime, timedelta, timezone
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
    instagram_media_id: Optional[str] = None
    instagram_permalink: Optional[str] = None
    instagram_story_id: Optional[str] = None
    posting_method: str = "telegram_manual"
    posted_by_user_id: Optional[str] = None
    posted_by_telegram_username: Optional[str] = None
    chat_settings_id: Optional[str] = None
    error_message: Optional[str] = None


class HistoryRepository(BaseRepository):
    """Repository for PostingHistory CRUD operations."""

    def __init__(self):
        super().__init__()

    def get_by_id(
        self, history_id: str, chat_settings_id: Optional[str] = None
    ) -> Optional[PostingHistory]:
        """Get history record by ID."""
        result = (
            self._tenant_query(PostingHistory, chat_settings_id)
            .filter(PostingHistory.id == history_id)
            .first()
        )
        self.end_read_transaction()
        return result

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
            since = datetime.now(timezone.utc) - timedelta(days=days)
            query = query.filter(PostingHistory.posted_at >= since)

        query = query.order_by(PostingHistory.posted_at.desc())

        if limit:
            query = query.limit(limit)

        result = query.all()
        self.end_read_transaction()
        return result

    def get_all_with_media(
        self,
        limit: Optional[int] = None,
        chat_settings_id: Optional[str] = None,
    ) -> list:
        """Get history items with joined media info (file_name, category).

        Returns list of (PostingHistory, file_name, category) tuples.
        """
        from src.models.media_item import MediaItem

        query = (
            self._tenant_query(PostingHistory, chat_settings_id)
            .outerjoin(MediaItem, PostingHistory.media_item_id == MediaItem.id)
            .add_columns(MediaItem.file_name, MediaItem.category)
            .order_by(PostingHistory.posted_at.desc())
        )

        if limit:
            query = query.limit(limit)

        result = query.all()
        self.end_read_transaction()
        return result

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

        result = query.all()
        self.end_read_transaction()
        return result

    def create(self, params: HistoryCreateParams) -> PostingHistory:
        """Create a new history record."""
        from dataclasses import asdict

        history = PostingHistory(**asdict(params))
        self.db.add(history)
        self.db.commit()
        self.db.refresh(history)
        return history

    def get_recent_posts(
        self,
        hours: int = 24,
        chat_settings_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[PostingHistory]:
        """Get posts from the last N hours."""
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        query = (
            self._tenant_query(PostingHistory, chat_settings_id)
            .filter(PostingHistory.posted_at >= since)
            .order_by(PostingHistory.posted_at.desc())
        )
        if limit is not None:
            query = query.limit(limit)
        result = query.all()
        self.end_read_transaction()
        return result

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
        result = (
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
        self.end_read_transaction()
        return result

    def get_by_queue_item_id(self, queue_item_id: str) -> Optional[PostingHistory]:
        """Get the most recent history record for a specific queue item.

        Used to determine what happened to a queue item that's no longer
        in the posting_queue (e.g., after a callback race condition).
        """
        result = (
            self.db.query(PostingHistory)
            .filter(PostingHistory.queue_item_id == queue_item_id)
            .order_by(PostingHistory.posted_at.desc())
            .first()
        )
        self.end_read_transaction()
        return result

    # ------------------------------------------------------------------
    # Analytics aggregations
    # ------------------------------------------------------------------

    def get_stats_by_status(
        self, days: int = 30, chat_settings_id: Optional[str] = None
    ) -> dict:
        """Count posts grouped by status within the given time window.

        Returns: {"posted": N, "skipped": N, "rejected": N, "failed": N}
        """
        since = datetime.now(timezone.utc) - timedelta(days=days)
        rows = (
            self._tenant_query(PostingHistory, chat_settings_id)
            .with_entities(PostingHistory.status, func.count(PostingHistory.id))
            .filter(PostingHistory.posted_at >= since)
            .group_by(PostingHistory.status)
            .all()
        )
        self.end_read_transaction()
        return {status: count for status, count in rows}

    def get_stats_by_method(
        self, days: int = 30, chat_settings_id: Optional[str] = None
    ) -> dict:
        """Count successful posts grouped by posting method.

        Returns: {"instagram_api": N, "telegram_manual": N}
        """
        since = datetime.now(timezone.utc) - timedelta(days=days)
        rows = (
            self._tenant_query(PostingHistory, chat_settings_id)
            .with_entities(PostingHistory.posting_method, func.count(PostingHistory.id))
            .filter(PostingHistory.posted_at >= since, PostingHistory.success)
            .group_by(PostingHistory.posting_method)
            .all()
        )
        self.end_read_transaction()
        return {method or "unknown": count for method, count in rows}

    def get_daily_counts(
        self, days: int = 30, chat_settings_id: Optional[str] = None
    ) -> list:
        """Count posts per day grouped by status.

        Returns list of {"date": "YYYY-MM-DD", "posted": N, "skipped": N, ...}
        """
        from sqlalchemy import cast, Date

        since = datetime.now(timezone.utc) - timedelta(days=days)
        rows = (
            self._tenant_query(PostingHistory, chat_settings_id)
            .with_entities(
                cast(PostingHistory.posted_at, Date).label("day"),
                PostingHistory.status,
                func.count(PostingHistory.id),
            )
            .filter(PostingHistory.posted_at >= since)
            .group_by("day", PostingHistory.status)
            .order_by("day")
            .all()
        )
        self.end_read_transaction()

        # Pivot into {date: {status: count}} then flatten
        by_day: dict = {}
        for day, status, count in rows:
            day_str = day.isoformat()
            if day_str not in by_day:
                by_day[day_str] = {"date": day_str}
            by_day[day_str][status] = count

        return list(by_day.values())

    def get_hourly_distribution(
        self, days: int = 30, chat_settings_id: Optional[str] = None
    ) -> list:
        """Count successful posts by hour of day.

        Returns list of {"hour": 0-23, "count": N}
        """
        from sqlalchemy import extract

        since = datetime.now(timezone.utc) - timedelta(days=days)
        rows = (
            self._tenant_query(PostingHistory, chat_settings_id)
            .with_entities(
                extract("hour", PostingHistory.posted_at).label("hour"),
                func.count(PostingHistory.id),
            )
            .filter(PostingHistory.posted_at >= since, PostingHistory.success)
            .group_by("hour")
            .order_by("hour")
            .all()
        )
        self.end_read_transaction()
        return [{"hour": int(hour), "count": count} for hour, count in rows]

    def get_stats_by_category(
        self, days: int = 30, chat_settings_id: Optional[str] = None
    ) -> list:
        """Count posts grouped by media category and status.

        Joins with media_items to get category.
        Returns list of {"category": str, "posted": N, "skipped": N, ...}
        """
        from src.models.media_item import MediaItem

        since = datetime.now(timezone.utc) - timedelta(days=days)
        coalesced_category = func.coalesce(MediaItem.category, "uncategorized")
        rows = (
            self._tenant_query(PostingHistory, chat_settings_id)
            .outerjoin(MediaItem, PostingHistory.media_item_id == MediaItem.id)
            .with_entities(
                coalesced_category,
                PostingHistory.status,
                func.count(PostingHistory.id),
            )
            .filter(PostingHistory.posted_at >= since)
            .group_by(coalesced_category, PostingHistory.status)
            .order_by(coalesced_category)
            .all()
        )
        self.end_read_transaction()

        # Pivot into {category: {status: count}}
        by_category: dict = {}
        for category, status, count in rows:
            if category not in by_category:
                by_category[category] = {"category": category}
            by_category[category][status] = count

        # Add total and success_rate
        for cat_data in by_category.values():
            total = sum(v for k, v in cat_data.items() if k != "category")
            posted = cat_data.get("posted", 0)
            cat_data["total"] = total
            cat_data["success_rate"] = round(posted / total, 2) if total else 0

        return list(by_category.values())

    def get_hourly_approval_rates(
        self, days: int = 30, chat_settings_id: Optional[str] = None
    ) -> list:
        """Count posts by hour of day grouped by status.

        Returns list of {"hour": 0-23, "posted": N, "skipped": N, ..., "total": N, "approval_rate": float}
        """
        from sqlalchemy import extract

        since = datetime.now(timezone.utc) - timedelta(days=days)
        rows = (
            self._tenant_query(PostingHistory, chat_settings_id)
            .with_entities(
                extract("hour", PostingHistory.posted_at).label("hour"),
                PostingHistory.status,
                func.count(PostingHistory.id),
            )
            .filter(PostingHistory.posted_at >= since)
            .group_by("hour", PostingHistory.status)
            .order_by("hour")
            .all()
        )
        self.end_read_transaction()

        by_hour: dict = {}
        for hour, status, count in rows:
            h = int(hour)
            if h not in by_hour:
                by_hour[h] = {"hour": h}
            by_hour[h][status] = count

        for hour_data in by_hour.values():
            total = sum(v for k, v in hour_data.items() if k != "hour")
            posted = hour_data.get("posted", 0)
            hour_data["total"] = total
            hour_data["approval_rate"] = round(posted / total, 2) if total else 0

        return [by_hour[h] for h in sorted(by_hour)]

    def get_approval_latency(
        self, days: int = 30, chat_settings_id: Optional[str] = None
    ) -> dict:
        """Compute approval latency statistics (time from queue to decision).

        Returns overall stats and per-hour/per-category breakdowns.
        Latency = posted_at - queue_created_at, in seconds.
        Only includes items with status 'posted' (approvals).
        """
        from sqlalchemy import extract

        since = datetime.now(timezone.utc) - timedelta(days=days)
        latency_expr = func.extract(
            "epoch", PostingHistory.posted_at - PostingHistory.queue_created_at
        )

        # Overall stats
        overall = (
            self._tenant_query(PostingHistory, chat_settings_id)
            .with_entities(
                func.count(PostingHistory.id).label("count"),
                func.avg(latency_expr).label("avg"),
                func.min(latency_expr).label("min"),
                func.max(latency_expr).label("max"),
            )
            .filter(
                PostingHistory.posted_at >= since,
                PostingHistory.status == "posted",
                PostingHistory.queue_created_at.isnot(None),
            )
            .first()
        )

        # Per-hour breakdown
        hourly_rows = (
            self._tenant_query(PostingHistory, chat_settings_id)
            .with_entities(
                extract("hour", PostingHistory.posted_at).label("hour"),
                func.count(PostingHistory.id).label("count"),
                func.avg(latency_expr).label("avg"),
            )
            .filter(
                PostingHistory.posted_at >= since,
                PostingHistory.status == "posted",
                PostingHistory.queue_created_at.isnot(None),
            )
            .group_by("hour")
            .order_by("hour")
            .all()
        )

        # Per-category breakdown
        from src.models.media_item import MediaItem

        coalesced_category = func.coalesce(MediaItem.category, "uncategorized")
        category_rows = (
            self._tenant_query(PostingHistory, chat_settings_id)
            .outerjoin(MediaItem, PostingHistory.media_item_id == MediaItem.id)
            .with_entities(
                coalesced_category.label("category"),
                func.count(PostingHistory.id).label("count"),
                func.avg(latency_expr).label("avg"),
            )
            .filter(
                PostingHistory.posted_at >= since,
                PostingHistory.status == "posted",
                PostingHistory.queue_created_at.isnot(None),
            )
            .group_by(coalesced_category)
            .order_by(coalesced_category)
            .all()
        )
        self.end_read_transaction()

        def _seconds_to_minutes(val):
            return round(val / 60, 1) if val else 0

        return {
            "overall": {
                "count": overall.count if overall else 0,
                "avg_minutes": _seconds_to_minutes(overall.avg if overall else 0),
                "min_minutes": _seconds_to_minutes(overall.min if overall else 0),
                "max_minutes": _seconds_to_minutes(overall.max if overall else 0),
            },
            "by_hour": [
                {
                    "hour": int(h.hour),
                    "count": h.count,
                    "avg_minutes": _seconds_to_minutes(h.avg),
                }
                for h in hourly_rows
            ],
            "by_category": [
                {
                    "category": c.category,
                    "count": c.count,
                    "avg_minutes": _seconds_to_minutes(c.avg),
                }
                for c in category_rows
            ],
        }

    def get_user_approval_stats(
        self, days: int = 30, chat_settings_id: Optional[str] = None
    ) -> list:
        """Per-user breakdown of approval decisions and response time.

        Returns list of per-user dicts: posted, skipped, rejected counts,
        approval_rate, and avg_latency_minutes.
        """
        from src.models.user import User

        since = datetime.now(timezone.utc) - timedelta(days=days)
        latency_expr = func.extract(
            "epoch", PostingHistory.posted_at - PostingHistory.queue_created_at
        )

        rows = (
            self._tenant_query(PostingHistory, chat_settings_id)
            .outerjoin(User, PostingHistory.posted_by_user_id == User.id)
            .with_entities(
                PostingHistory.posted_by_user_id,
                User.telegram_username,
                User.telegram_first_name,
                PostingHistory.status,
                func.count(PostingHistory.id).label("count"),
                func.avg(latency_expr).label("avg_latency"),
            )
            .filter(
                PostingHistory.posted_at >= since,
                PostingHistory.posted_by_user_id.isnot(None),
            )
            .group_by(
                PostingHistory.posted_by_user_id,
                User.telegram_username,
                User.telegram_first_name,
                PostingHistory.status,
            )
            .all()
        )
        self.end_read_transaction()

        # Pivot into per-user dicts
        users: dict = {}
        for user_id, username, first_name, status, count, avg_lat in rows:
            uid = str(user_id) if user_id else "unknown"
            if uid not in users:
                users[uid] = {
                    "user_id": uid,
                    "username": username or first_name or "Unknown",
                    "posted": 0,
                    "skipped": 0,
                    "rejected": 0,
                    "total": 0,
                    "avg_latency_minutes": 0,
                    "_latency_sum": 0,
                    "_latency_count": 0,
                }
            users[uid][status] = users[uid].get(status, 0) + count
            users[uid]["total"] += count
            if avg_lat and status == "posted":
                users[uid]["_latency_sum"] += avg_lat * count
                users[uid]["_latency_count"] += count

        result = []
        for user_data in users.values():
            total = user_data["total"]
            posted = user_data.get("posted", 0)
            user_data["approval_rate"] = round(posted / total, 2) if total else 0
            if user_data["_latency_count"] > 0:
                avg_sec = user_data["_latency_sum"] / user_data["_latency_count"]
                user_data["avg_latency_minutes"] = round(avg_sec / 60, 1)
            del user_data["_latency_sum"]
            del user_data["_latency_count"]
            result.append(user_data)

        # Sort by total actions descending
        result.sort(key=lambda x: x["total"], reverse=True)
        return result

    def get_dow_approval_rates(
        self, days: int = 90, chat_settings_id: Optional[str] = None
    ) -> list:
        """Count posts by day of week grouped by status.

        Uses extract('dow') which returns 0=Sunday through 6=Saturday.
        Returns list of {"dow": 0-6, "day_name": str, "posted": N, ..., "approval_rate": float}
        """
        from sqlalchemy import extract

        day_names = [
            "Sunday",
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
        ]

        since = datetime.now(timezone.utc) - timedelta(days=days)
        rows = (
            self._tenant_query(PostingHistory, chat_settings_id)
            .with_entities(
                extract("dow", PostingHistory.posted_at).label("dow"),
                PostingHistory.status,
                func.count(PostingHistory.id),
            )
            .filter(PostingHistory.posted_at >= since)
            .group_by("dow", PostingHistory.status)
            .order_by("dow")
            .all()
        )
        self.end_read_transaction()

        by_dow: dict = {}
        for dow, status, count in rows:
            d = int(dow)
            if d not in by_dow:
                by_dow[d] = {"dow": d, "day_name": day_names[d]}
            by_dow[d][status] = count

        for dow_data in by_dow.values():
            total = sum(v for k, v in dow_data.items() if k not in ("dow", "day_name"))
            posted = dow_data.get("posted", 0)
            dow_data["total"] = total
            dow_data["approval_rate"] = round(posted / total, 2) if total else 0

        return [by_dow[d] for d in sorted(by_dow)]
