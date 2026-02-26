"""Settings and schedule action endpoints for onboarding Mini App."""

from fastapi import APIRouter, HTTPException

from src.repositories.chat_settings_repository import ChatSettingsRepository
from src.repositories.queue_repository import QueueRepository
from src.services.core.instagram_account_service import InstagramAccountService
from src.services.core.media_sync import MediaSyncService
from src.services.core.scheduler import SchedulerService
from src.services.core.settings_service import SettingsService
from src.utils.logger import logger

from .helpers import _validate_request, service_error_handler
from .models import (
    InitRequest,
    RemoveAccountRequest,
    ScheduleActionRequest,
    SwitchAccountRequest,
    ToggleSettingRequest,
    UpdateSettingRequest,
)

router = APIRouter(tags=["onboarding"])


@router.post("/toggle-setting")
async def onboarding_toggle_setting(request: ToggleSettingRequest):
    """Toggle a boolean setting (is_paused, dry_run_mode) from dashboard."""
    _validate_request(request.init_data, request.chat_id)

    allowed_settings = {
        "is_paused",
        "dry_run_mode",
        "enable_instagram_api",
        "show_verbose_notifications",
        "media_sync_enabled",
    }
    if request.setting_name not in allowed_settings:
        raise HTTPException(
            status_code=400,
            detail=f"Setting '{request.setting_name}' cannot be toggled from dashboard. "
            f"Allowed: {', '.join(sorted(allowed_settings))}",
        )

    with SettingsService() as settings_service, service_error_handler():
        new_value = settings_service.toggle_setting(
            request.chat_id, request.setting_name
        )
        return {
            "setting_name": request.setting_name,
            "new_value": new_value,
        }


@router.post("/update-setting")
async def onboarding_update_setting(request: UpdateSettingRequest):
    """Update a numeric setting (posts_per_day, posting hours) from dashboard."""
    _validate_request(request.init_data, request.chat_id)

    allowed_settings = {"posts_per_day", "posting_hours_start", "posting_hours_end"}
    if request.setting_name not in allowed_settings:
        raise HTTPException(
            status_code=400,
            detail=f"Setting '{request.setting_name}' cannot be updated from dashboard. "
            f"Allowed: {', '.join(sorted(allowed_settings))}",
        )

    with SettingsService() as settings_service, service_error_handler():
        settings_service.update_setting(
            request.chat_id, request.setting_name, request.value
        )
        return {
            "setting_name": request.setting_name,
            "new_value": request.value,
        }


@router.post("/switch-account")
async def onboarding_switch_account(request: SwitchAccountRequest):
    """Switch the active Instagram account for this chat."""
    _validate_request(request.init_data, request.chat_id)

    with InstagramAccountService() as account_service, service_error_handler():
        account = account_service.switch_account(
            telegram_chat_id=request.chat_id,
            account_id=request.account_id,
        )
        return {
            "account_id": str(account.id),
            "display_name": account.display_name,
            "instagram_username": account.instagram_username,
        }


@router.post("/remove-account")
async def onboarding_remove_account(request: RemoveAccountRequest):
    """Deactivate (soft-delete) an Instagram account."""
    _validate_request(request.init_data, request.chat_id)

    with InstagramAccountService() as account_service, service_error_handler():
        account = account_service.deactivate_account(
            account_id=request.account_id,
        )
        return {
            "account_id": str(account.id),
            "display_name": account.display_name,
            "removed": True,
        }


@router.post("/sync-media")
async def onboarding_sync_media(request: InitRequest):
    """Trigger media sync from the dashboard.

    Calls MediaSyncService.sync() with the chat's per-tenant config.
    Returns sync result counts (new, updated, deactivated, etc).
    """
    _validate_request(request.init_data, request.chat_id)

    with ChatSettingsRepository() as settings_repo:
        chat_settings = settings_repo.get_or_create(request.chat_id)
        source_type = chat_settings.media_source_type
        source_root = chat_settings.media_source_root

    if not source_root:
        raise HTTPException(
            status_code=400,
            detail="No media folder configured. Set up a media folder first.",
        )

    with MediaSyncService() as sync_service:
        try:
            result = sync_service.sync(
                source_type=source_type,
                source_root=source_root,
                triggered_by="dashboard",
                telegram_chat_id=request.chat_id,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Media sync from dashboard failed: {e}")
            raise HTTPException(
                status_code=500,
                detail="Media sync failed. Please try again.",
            )

    return {
        "new": result.new,
        "updated": result.updated,
        "deactivated": result.deactivated,
        "unchanged": result.unchanged,
        "errors": result.errors,
        "total_processed": result.total_processed,
    }


@router.post("/extend-schedule")
async def onboarding_extend_schedule(request: ScheduleActionRequest):
    """Extend the posting schedule by N days."""
    _validate_request(request.init_data, request.chat_id)

    with SchedulerService() as scheduler:
        try:
            result = scheduler.extend_schedule(
                days=request.days,
                telegram_chat_id=request.chat_id,
            )
            return {
                "scheduled": result.get("scheduled", 0),
                "skipped": result.get("skipped", 0),
                "total_slots": result.get("total_slots", 0),
                "extended_from": result.get("extended_from"),
            }
        except Exception as e:
            logger.error(f"Failed to extend schedule: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/regenerate-schedule")
async def onboarding_regenerate_schedule(request: ScheduleActionRequest):
    """Clear all pending queue items and create a fresh schedule."""
    _validate_request(request.init_data, request.chat_id)

    with (
        ChatSettingsRepository() as settings_repo,
        QueueRepository() as queue_repo,
    ):
        chat_settings = settings_repo.get_or_create(request.chat_id)
        chat_settings_id = str(chat_settings.id)

        deleted = queue_repo.delete_all_pending(chat_settings_id=chat_settings_id)
        logger.info(
            f"Regenerate schedule: cleared {deleted} pending items "
            f"for chat {request.chat_id}"
        )

    with SchedulerService() as scheduler:
        try:
            result = scheduler.create_schedule(
                days=request.days,
                telegram_chat_id=request.chat_id,
            )
            return {
                "scheduled": result.get("scheduled", 0),
                "skipped": result.get("skipped", 0),
                "total_slots": result.get("total_slots", 0),
                "cleared": deleted,
            }
        except Exception as e:
            logger.error(f"Failed to regenerate schedule: {e}")
            raise HTTPException(status_code=500, detail=str(e))
