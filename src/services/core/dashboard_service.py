"""Dashboard service - read-only aggregation queries for the Mini App."""

from typing import Optional

from src.services.base_service import BaseService
from src.services.core.settings_service import SettingsService
from src.repositories.history_repository import HistoryRepository
from src.repositories.media_repository import MediaRepository
from src.repositories.queue_repository import QueueRepository


class DashboardService(BaseService):
    """Read-only aggregation queries for dashboard endpoints.

    Encapsulates the cross-repository joins that the onboarding
    dashboard needs, keeping the API layer free of direct
    repository imports.
    """

    def __init__(self):
        super().__init__()
        self.settings_service = SettingsService()
        self.queue_repo = QueueRepository()
        self.history_repo = HistoryRepository()
        self.media_repo = MediaRepository()

    def _resolve_chat_settings_id(self, telegram_chat_id: int) -> str:
        chat_settings = self.settings_service.get_settings(telegram_chat_id)
        return str(chat_settings.id)

    def get_queue_detail(self, telegram_chat_id: int, limit: int = 10) -> dict:
        """Return in-flight queue items with media info and activity summary.

        JIT semantics: the queue holds only items currently awaiting team
        action (0-5 typical), not a multi-day schedule.
        """
        chat_settings_id = self._resolve_chat_settings_id(telegram_chat_id)

        pending_rows = self.queue_repo.get_all_with_media(
            status="pending", chat_settings_id=chat_settings_id
        )
        processing_rows = self.queue_repo.get_all_with_media(
            status="processing", chat_settings_id=chat_settings_id
        )
        all_in_flight = pending_rows + processing_rows

        # Item list (limited) with media info from JOIN
        items = []
        for item, file_name, category in all_in_flight[:limit]:
            items.append(
                {
                    "scheduled_for": item.scheduled_for.isoformat(),
                    "media_name": file_name if file_name else "Unknown",
                    "category": (category if category else None) or "uncategorized",
                    "status": item.status,
                }
            )

        # Posts today from posting_history
        today_posts = self.history_repo.get_recent_posts(
            hours=24, chat_settings_id=chat_settings_id
        )
        posts_today = len(today_posts)

        # Last post time
        last_post_at = None
        if today_posts:
            last_post_at = today_posts[0].posted_at.isoformat()
        else:
            # Check further back
            recent = self.history_repo.get_recent_posts(
                hours=720, chat_settings_id=chat_settings_id
            )
            if recent:
                last_post_at = recent[0].posted_at.isoformat()

        return {
            "items": items,
            "total_in_flight": len(all_in_flight),
            "posts_today": posts_today,
            "last_post_at": last_post_at,
        }

    def get_history_detail(self, telegram_chat_id: int, limit: int = 10) -> dict:
        """Return recent posting history with media info."""
        chat_settings_id = self._resolve_chat_settings_id(telegram_chat_id)

        history_rows = self.history_repo.get_all_with_media(
            limit=limit, chat_settings_id=chat_settings_id
        )

        items = []
        for item, file_name, category in history_rows:
            items.append(
                {
                    "posted_at": item.posted_at.isoformat(),
                    "media_name": file_name if file_name else "Unknown",
                    "category": (category if category else None) or "uncategorized",
                    "status": item.status,
                    "posting_method": item.posting_method,
                }
            )

        return {"items": items}

    def get_media_stats(self, telegram_chat_id: int) -> dict:
        """Return media library breakdown by category."""
        chat_settings_id = self._resolve_chat_settings_id(telegram_chat_id)

        total_active = self.media_repo.count_active(chat_settings_id=chat_settings_id)
        category_counts = self.media_repo.count_by_category(
            chat_settings_id=chat_settings_id
        )

        categories = [
            {"name": name, "count": count}
            for name, count in sorted(
                category_counts.items(), key=lambda x: x[1], reverse=True
            )
        ]

        return {
            "total_active": total_active,
            "categories": categories,
        }

    def get_analytics(self, telegram_chat_id: int, days: int = 30) -> dict:
        """Return aggregated posting analytics for the dashboard.

        Combines status breakdown, method breakdown, daily counts,
        hourly distribution, and category performance into a single
        response.
        """
        with self.track_execution(
            "get_analytics",
            input_params={"telegram_chat_id": telegram_chat_id, "days": days},
        ) as run_id:
            chat_settings_id = self._resolve_chat_settings_id(telegram_chat_id)

            status_counts = self.history_repo.get_stats_by_status(
                days=days, chat_settings_id=chat_settings_id
            )
            method_counts = self.history_repo.get_stats_by_method(
                days=days, chat_settings_id=chat_settings_id
            )
            daily_counts = self.history_repo.get_daily_counts(
                days=days, chat_settings_id=chat_settings_id
            )
            hourly_dist = self.history_repo.get_hourly_distribution(
                days=days, chat_settings_id=chat_settings_id
            )
            category_stats = self.history_repo.get_stats_by_category(
                days=days, chat_settings_id=chat_settings_id
            )

            total = sum(status_counts.values())
            posted = status_counts.get("posted", 0)
            num_days = max(len(daily_counts), 1)

            result = {
                "summary": {
                    "total_posts": total,
                    "posted": posted,
                    "skipped": status_counts.get("skipped", 0),
                    "rejected": status_counts.get("rejected", 0),
                    "failed": status_counts.get("failed", 0),
                    "success_rate": round(posted / total, 2) if total else 0,
                    "avg_per_day": round(total / num_days, 1),
                },
                "method_breakdown": method_counts,
                "daily_counts": daily_counts,
                "hourly_distribution": hourly_dist,
                "category_breakdown": category_stats,
                "days": days,
            }

            self.set_result_summary(run_id, {"total_posts": total, "days": days})
            return result

    def get_pending_queue_items(self, chat_settings_id: Optional[str] = None) -> list:
        """Return pending queue items with media details.

        Used by CLI ``list-queue`` command.
        """
        rows = self.queue_repo.get_all_with_media(
            status="pending", chat_settings_id=chat_settings_id
        )

        items = []
        for item, file_name, category in rows:
            items.append(
                {
                    "scheduled_for": item.scheduled_for,
                    "file_name": file_name if file_name else "Unknown",
                    "category": (category if category else None) or "-",
                    "status": item.status,
                }
            )
        return items
