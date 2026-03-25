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

        pending_items = self.queue_repo.get_all(
            status="pending", chat_settings_id=chat_settings_id
        )
        processing_items = self.queue_repo.get_all(
            status="processing", chat_settings_id=chat_settings_id
        )
        all_in_flight = pending_items + processing_items

        # Item list (limited) with media info
        items = []
        for item in all_in_flight[:limit]:
            media = self.media_repo.get_by_id(str(item.media_item_id))
            items.append(
                {
                    "scheduled_for": item.scheduled_for.isoformat(),
                    "media_name": media.file_name if media else "Unknown",
                    "category": (media.category if media else None) or "uncategorized",
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

        history_items = self.history_repo.get_all(
            limit=limit, chat_settings_id=chat_settings_id
        )

        items = []
        for item in history_items:
            media = self.media_repo.get_by_id(str(item.media_item_id))
            items.append(
                {
                    "posted_at": item.posted_at.isoformat(),
                    "media_name": media.file_name if media else "Unknown",
                    "category": (media.category if media else None) or "uncategorized",
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

    def get_pending_queue_items(self, chat_settings_id: Optional[str] = None) -> list:
        """Return pending queue items with media details.

        Used by CLI ``list-queue`` command.
        """
        raw_items = self.queue_repo.get_all(
            status="pending", chat_settings_id=chat_settings_id
        )

        items = []
        for item in raw_items:
            media = self.media_repo.get_by_id(str(item.media_item_id))
            items.append(
                {
                    "scheduled_for": item.scheduled_for,
                    "file_name": media.file_name if media else "Unknown",
                    "category": (media.category if media else None) or "-",
                    "status": item.status,
                }
            )
        return items
