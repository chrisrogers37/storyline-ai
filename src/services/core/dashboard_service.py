"""Dashboard service - read-only aggregation queries for the Mini App."""

from datetime import datetime, timezone
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
        """Return queue items with media info and schedule summary."""
        chat_settings_id = self._resolve_chat_settings_id(telegram_chat_id)

        pending_items = self.queue_repo.get_all(
            status="pending", chat_settings_id=chat_settings_id
        )

        # Day summary from all pending items
        day_counts: dict[str, int] = {}
        for item in pending_items:
            day_key = item.scheduled_for.strftime("%Y-%m-%d")
            day_counts[day_key] = day_counts.get(day_key, 0) + 1

        day_summary = [
            {"date": date, "count": count} for date, count in sorted(day_counts.items())
        ]

        # Item list (limited) with media info
        items = []
        for item in pending_items[:limit]:
            media = self.media_repo.get_by_id(str(item.media_item_id))
            items.append(
                {
                    "scheduled_for": item.scheduled_for.isoformat(),
                    "media_name": media.file_name if media else "Unknown",
                    "category": (media.category if media else None) or "uncategorized",
                }
            )

        schedule_end = None
        days_remaining = None
        if pending_items:
            schedule_end = pending_items[-1].scheduled_for.isoformat()
            now = datetime.now(timezone.utc)
            delta = pending_items[-1].scheduled_for.replace(tzinfo=timezone.utc) - now
            days_remaining = max(0, delta.days)

        return {
            "items": items,
            "total_pending": len(pending_items),
            "schedule_end": schedule_end,
            "days_remaining": days_remaining,
            "day_summary": day_summary,
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

        all_active = self.media_repo.get_all(
            is_active=True, chat_settings_id=chat_settings_id
        )

        category_counts: dict[str, int] = {}
        for item in all_active:
            cat = item.category or "uncategorized"
            category_counts[cat] = category_counts.get(cat, 0) + 1

        categories = [
            {"name": name, "count": count}
            for name, count in sorted(
                category_counts.items(), key=lambda x: x[1], reverse=True
            )
        ]

        return {
            "total_active": len(all_active),
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
