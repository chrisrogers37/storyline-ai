"""Queue-related dashboard queries — in-flight items and pending queue."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.services.core.dashboard_service import DashboardService


class QueueDashboardQueries:
    """Queue detail and pending item queries for the dashboard."""

    def __init__(self, service: DashboardService):
        self.service = service

    def get_queue_detail(self, telegram_chat_id: int, limit: int = 10) -> dict:
        """Return in-flight queue items with media info and activity summary.

        JIT semantics: the queue holds only items currently awaiting team
        action (0-5 typical), not a multi-day schedule.
        """
        chat_settings_id = self.service.resolve_chat_settings_id(telegram_chat_id)

        pending_rows = self.service.queue_repo.get_all_with_media(
            status="pending", chat_settings_id=chat_settings_id
        )
        processing_rows = self.service.queue_repo.get_all_with_media(
            status="processing", chat_settings_id=chat_settings_id
        )
        all_in_flight = pending_rows + processing_rows

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

        today_posts = self.service.history_repo.get_recent_posts(
            hours=24, chat_settings_id=chat_settings_id
        )
        posts_today = len(today_posts)

        last_post_at = None
        if today_posts:
            last_post_at = today_posts[0].posted_at.isoformat()
        else:
            # Check further back
            recent = self.service.history_repo.get_recent_posts(
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

    def get_pending_queue_items(self, chat_settings_id: Optional[str] = None) -> list:
        """Return pending queue items with media details.

        Used by CLI ``list-queue`` command.
        """
        rows = self.service.queue_repo.get_all_with_media(
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
