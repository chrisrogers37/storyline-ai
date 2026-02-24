"""Dashboard detail endpoints for onboarding Mini App."""

from datetime import datetime, timezone

from fastapi import APIRouter, Query

from src.repositories.chat_settings_repository import ChatSettingsRepository
from src.repositories.history_repository import HistoryRepository
from src.repositories.media_repository import MediaRepository
from src.repositories.queue_repository import QueueRepository
from src.services.core.health_check import HealthCheckService
from src.services.core.instagram_account_service import InstagramAccountService

from .helpers import _validate_request

router = APIRouter(tags=["onboarding"])


@router.get("/queue-detail")
async def onboarding_queue_detail(
    init_data: str,
    chat_id: int,
    limit: int = Query(default=10, ge=1, le=50),
):
    """Return detailed queue items with schedule summary for dashboard."""
    _validate_request(init_data, chat_id)

    with (
        ChatSettingsRepository() as settings_repo,
        QueueRepository() as queue_repo,
    ):
        chat_settings = settings_repo.get_or_create(chat_id)
        chat_settings_id = str(chat_settings.id)

        pending_items = queue_repo.get_all(
            status="pending", chat_settings_id=chat_settings_id
        )

        # Build day summary from all pending items
        day_counts: dict[str, int] = {}
        for item in pending_items:
            day_key = item.scheduled_for.strftime("%Y-%m-%d")
            day_counts[day_key] = day_counts.get(day_key, 0) + 1

        day_summary = [
            {"date": date, "count": count} for date, count in sorted(day_counts.items())
        ]

        # Build item list (limited) with media info
        items = []
        with MediaRepository() as media_repo:
            for item in pending_items[:limit]:
                media = media_repo.get_by_id(str(item.media_item_id))
                items.append(
                    {
                        "scheduled_for": item.scheduled_for.isoformat(),
                        "media_name": media.file_name if media else "Unknown",
                        "category": (media.category if media else None)
                        or "uncategorized",
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


@router.get("/history-detail")
async def onboarding_history_detail(
    init_data: str,
    chat_id: int,
    limit: int = Query(default=10, ge=1, le=50),
):
    """Return recent posting history with media info for dashboard."""
    _validate_request(init_data, chat_id)

    with (
        ChatSettingsRepository() as settings_repo,
        HistoryRepository() as history_repo,
    ):
        chat_settings = settings_repo.get_or_create(chat_id)
        chat_settings_id = str(chat_settings.id)

        history_items = history_repo.get_all(
            limit=limit, chat_settings_id=chat_settings_id
        )

        items = []
        with MediaRepository() as media_repo:
            for item in history_items:
                media = media_repo.get_by_id(str(item.media_item_id))
                items.append(
                    {
                        "posted_at": item.posted_at.isoformat(),
                        "media_name": media.file_name if media else "Unknown",
                        "category": (media.category if media else None)
                        or "uncategorized",
                        "status": item.status,
                        "posting_method": item.posting_method,
                    }
                )

        return {"items": items}


@router.get("/media-stats")
async def onboarding_media_stats(
    init_data: str,
    chat_id: int,
):
    """Return media library breakdown by category for dashboard."""
    _validate_request(init_data, chat_id)

    with ChatSettingsRepository() as settings_repo:
        chat_settings = settings_repo.get_or_create(chat_id)
        chat_settings_id = str(chat_settings.id)

        with MediaRepository() as media_repo:
            all_active = media_repo.get_all(
                is_active=True, chat_settings_id=chat_settings_id
            )

            # Count by category
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


@router.get("/accounts")
async def onboarding_accounts(
    init_data: str,
    chat_id: int,
):
    """List all active Instagram accounts with active account for this chat marked."""
    _validate_request(init_data, chat_id)

    with (
        InstagramAccountService() as account_service,
        ChatSettingsRepository() as settings_repo,
    ):
        accounts = account_service.list_accounts(include_inactive=False)
        chat_settings = settings_repo.get_or_create(chat_id)
        active_account_id = (
            str(chat_settings.active_instagram_account_id)
            if chat_settings.active_instagram_account_id
            else None
        )

        items = []
        for acct in accounts:
            items.append(
                {
                    "id": str(acct.id),
                    "display_name": acct.display_name,
                    "instagram_username": acct.instagram_username,
                    "is_active": str(acct.id) == active_account_id,
                }
            )

        return {"accounts": items, "active_account_id": active_account_id}


@router.get("/system-status")
async def onboarding_system_status(
    init_data: str,
    chat_id: int,
):
    """Return system health checks for the dashboard status card."""
    _validate_request(init_data, chat_id)

    health_service = HealthCheckService()
    try:
        result = health_service.check_all()
        return result
    finally:
        health_service.queue_repo.close()
        health_service.history_repo.close()
