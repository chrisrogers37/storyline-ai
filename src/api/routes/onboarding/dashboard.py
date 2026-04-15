"""Dashboard detail endpoints for onboarding Mini App."""

from fastapi import APIRouter, Query

from src.services.core.dashboard_service import DashboardService
from src.services.core.health_check import HealthCheckService
from src.services.core.instagram_account_service import InstagramAccountService
from src.services.core.settings_service import SettingsService

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

    with DashboardService() as service:
        return service.get_queue_detail(chat_id, limit=limit)


@router.get("/history-detail")
async def onboarding_history_detail(
    init_data: str,
    chat_id: int,
    limit: int = Query(default=10, ge=1, le=50),
):
    """Return recent posting history with media info for dashboard."""
    _validate_request(init_data, chat_id)

    with DashboardService() as service:
        return service.get_history_detail(chat_id, limit=limit)


@router.get("/media-stats")
async def onboarding_media_stats(
    init_data: str,
    chat_id: int,
):
    """Return media library breakdown by category for dashboard."""
    _validate_request(init_data, chat_id)

    with DashboardService() as service:
        return service.get_media_stats(chat_id)


@router.get("/accounts")
async def onboarding_accounts(
    init_data: str,
    chat_id: int,
):
    """List all active Instagram accounts with active account for this chat marked."""
    _validate_request(init_data, chat_id)

    with (
        InstagramAccountService() as account_service,
        SettingsService() as settings_service,
    ):
        accounts = account_service.list_accounts(include_inactive=False)
        chat_settings = settings_service.get_settings(chat_id)
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


@router.get("/analytics/schedule-recommendations")
async def onboarding_schedule_recommendations(
    init_data: str,
    chat_id: int,
    days: int = Query(default=90, ge=7, le=365),
):
    """Return posting time recommendations based on approval patterns."""
    _validate_request(init_data, chat_id)

    with DashboardService() as service:
        return service.get_schedule_recommendations(chat_id, days=days)


@router.get("/analytics/categories")
async def onboarding_analytics_categories(
    init_data: str,
    chat_id: int,
    days: int = Query(default=30, ge=1, le=365),
):
    """Return per-category performance with configured vs actual ratios."""
    _validate_request(init_data, chat_id)

    with DashboardService() as service:
        return service.get_category_analytics(chat_id, days=days)


@router.get("/analytics/schedule-preview")
async def onboarding_schedule_preview(
    init_data: str,
    chat_id: int,
    slots: int = Query(default=10, ge=1, le=50),
):
    """Return upcoming scheduled slots with predicted categories."""
    _validate_request(init_data, chat_id)

    with DashboardService() as service:
        return service.get_schedule_preview(chat_id, slots=slots)


@router.get("/analytics/content-reuse")
async def onboarding_content_reuse(
    init_data: str,
    chat_id: int,
):
    """Return content reuse insights — evergreen vs one-shot media."""
    _validate_request(init_data, chat_id)

    with DashboardService() as service:
        return service.get_content_reuse_insights(chat_id)


@router.get("/analytics/service-health")
async def onboarding_service_health(
    init_data: str,
    chat_id: int,
    hours: int = Query(default=24, ge=1, le=168),
):
    """Return service execution telemetry from service_runs table."""
    _validate_request(init_data, chat_id)

    with DashboardService() as service:
        return service.get_service_health_stats(hours=hours)


@router.get("/analytics")
async def onboarding_analytics(
    init_data: str,
    chat_id: int,
    days: int = Query(default=30, ge=1, le=365),
):
    """Return aggregated posting analytics for the dashboard."""
    _validate_request(init_data, chat_id)

    with DashboardService() as service:
        return service.get_analytics(chat_id, days=days)


@router.get("/system-status")
async def onboarding_system_status(
    init_data: str,
    chat_id: int,
):
    """Return system health checks for the dashboard status card."""
    _validate_request(init_data, chat_id)

    with HealthCheckService() as health_service:
        return health_service.check_all()
