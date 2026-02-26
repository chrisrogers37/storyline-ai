"""Setup wizard endpoints for onboarding Mini App."""

from fastapi import APIRouter, HTTPException

from src.repositories.chat_settings_repository import ChatSettingsRepository
from src.services.core.media_sync import MediaSyncService
from src.services.core.oauth_service import OAuthService
from src.services.core.scheduler import SchedulerService
from src.services.core.settings_service import SettingsService
from src.services.integrations.google_drive import GoogleDriveService
from src.services.integrations.google_drive_oauth import GoogleDriveOAuthService
from src.utils.logger import logger

from .helpers import (
    GDRIVE_FOLDER_RE,
    _get_setup_state,
    _validate_request,
    service_error_handler,
)
from .models import (
    CompleteRequest,
    InitRequest,
    MediaFolderRequest,
    ScheduleRequest,
    StartIndexingRequest,
)

router = APIRouter(tags=["onboarding"])


@router.post("/init")
async def onboarding_init(request: InitRequest):
    """Validate initData and return current setup state for this chat."""
    user_info = _validate_request(request.init_data, request.chat_id)

    setup_state = _get_setup_state(request.chat_id)

    # Set initial onboarding step if not yet started
    if not setup_state.get("onboarding_completed") and not setup_state.get(
        "onboarding_step"
    ):
        with SettingsService() as settings_service:
            settings_service.set_onboarding_step(request.chat_id, "welcome")
        setup_state["onboarding_step"] = "welcome"

    return {
        "chat_id": request.chat_id,
        "user": user_info,
        "setup_state": setup_state,
    }


@router.get("/oauth-url/{provider}")
async def onboarding_oauth_url(
    provider: str,
    init_data: str,
    chat_id: int,
):
    """Return OAuth authorization URL for a provider."""
    _validate_request(init_data, chat_id)

    if provider == "instagram":
        with OAuthService() as service, service_error_handler():
            auth_url = service.generate_authorization_url(chat_id)
        return {"auth_url": auth_url}

    elif provider == "google-drive":
        with GoogleDriveOAuthService() as service, service_error_handler():
            auth_url = service.generate_authorization_url(chat_id)
        return {"auth_url": auth_url}

    else:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")


@router.post("/media-folder")
async def onboarding_media_folder(request: MediaFolderRequest):
    """Set the Google Drive media folder for this chat."""
    _validate_request(request.init_data, request.chat_id)

    # Extract folder ID from URL
    match = GDRIVE_FOLDER_RE.search(request.folder_url)
    if not match:
        raise HTTPException(
            status_code=400,
            detail="Invalid Google Drive folder URL. "
            "Expected: https://drive.google.com/drive/folders/...",
        )

    folder_id = match.group(1)

    # Validate folder access using user's OAuth credentials
    with GoogleDriveService() as gdrive_service:
        try:
            provider = gdrive_service.get_provider_for_chat(
                request.chat_id, root_folder_id=folder_id
            )
            # List files to verify access and get count
            files = provider.list_files()
            file_count = len(files)

            # Extract unique categories (subfolder names)
            categories = list({f.get("category", "uncategorized") for f in files})
        except Exception as e:
            logger.error(f"Failed to access Google Drive folder: {e}")
            raise HTTPException(
                status_code=400,
                detail="Cannot access this folder. Make sure you've shared it "
                "with the connected Google account.",
            )

    # Persist folder config to per-chat settings
    with SettingsService() as settings_service:
        settings_service.update_setting(
            request.chat_id, "media_source_type", "google_drive"
        )
        settings_service.update_setting(request.chat_id, "media_source_root", folder_id)
        settings_service.update_setting(request.chat_id, "media_sync_enabled", True)
        settings_service.set_onboarding_step(request.chat_id, "media_folder")

    return {
        "folder_id": folder_id,
        "file_count": file_count,
        "categories": sorted(categories),
        "saved": True,
    }


@router.post("/start-indexing")
async def onboarding_start_indexing(request: StartIndexingRequest):
    """Trigger media indexing for this chat's configured folder.

    Requires that media-folder has already been validated and saved.
    Calls MediaSyncService.sync() with the chat's per-tenant config.
    """
    _validate_request(request.init_data, request.chat_id)

    with ChatSettingsRepository() as settings_repo:
        chat_settings = settings_repo.get_or_create(request.chat_id)
        source_type = chat_settings.media_source_type
        source_root = chat_settings.media_source_root

    if not source_root:
        raise HTTPException(
            status_code=400,
            detail="No media folder configured. Complete the media folder step first.",
        )

    with MediaSyncService() as sync_service:
        try:
            result = sync_service.sync(
                source_type=source_type,
                source_root=source_root,
                triggered_by="onboarding",
                telegram_chat_id=request.chat_id,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Media indexing failed during onboarding: {e}")
            raise HTTPException(
                status_code=500,
                detail="Media indexing failed. Please try again or use /sync later.",
            )

    # Update onboarding step
    with SettingsService() as step_service:
        step_service.set_onboarding_step(request.chat_id, "indexing")

    return {
        "indexed": True,
        "new": result.new,
        "updated": result.updated,
        "unchanged": result.unchanged,
        "deactivated": result.deactivated,
        "errors": result.errors,
        "total_processed": result.total_processed,
    }


@router.post("/schedule")
async def onboarding_schedule(request: ScheduleRequest):
    """Save posting schedule configuration."""
    _validate_request(request.init_data, request.chat_id)

    with SettingsService() as settings_service, service_error_handler():
        settings_service.update_setting(
            request.chat_id, "posts_per_day", request.posts_per_day
        )
        settings_service.update_setting(
            request.chat_id, "posting_hours_start", request.posting_hours_start
        )
        settings_service.update_setting(
            request.chat_id, "posting_hours_end", request.posting_hours_end
        )
        settings_service.set_onboarding_step(request.chat_id, "schedule")

    return {
        "posts_per_day": request.posts_per_day,
        "posting_hours_start": request.posting_hours_start,
        "posting_hours_end": request.posting_hours_end,
    }


@router.post("/complete")
async def onboarding_complete(request: CompleteRequest):
    """Mark onboarding as finished, auto-configure dependent settings."""
    _validate_request(request.init_data, request.chat_id)

    with SettingsService() as settings_service:
        # Auto-configure dependent settings based on what was connected
        setup_state = _get_setup_state(request.chat_id)

        if setup_state["instagram_connected"]:
            settings_service.update_setting(
                request.chat_id, "enable_instagram_api", True
            )

        if setup_state.get("media_folder_configured"):
            settings_service.update_setting(request.chat_id, "media_sync_enabled", True)

        # NOTE: dry_run_mode stays True. User flips it manually later.

        settings_service.complete_onboarding(request.chat_id)

    result = {"onboarding_completed": True, "schedule_created": False}

    if request.create_schedule:
        with SchedulerService() as scheduler:
            try:
                schedule_result = scheduler.create_schedule(
                    days=request.schedule_days,
                    telegram_chat_id=request.chat_id,
                )
                result["schedule_created"] = True
                result["schedule_summary"] = {
                    "scheduled": schedule_result.get("scheduled", 0),
                    "total_slots": schedule_result.get("total_slots", 0),
                    "days": request.schedule_days,
                }
            except Exception as e:
                logger.error(f"Failed to create schedule during onboarding: {e}")
                result["schedule_error"] = str(e)

    return result
