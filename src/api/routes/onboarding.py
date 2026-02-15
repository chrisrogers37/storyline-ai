"""Onboarding Mini App API endpoints."""

import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.repositories.chat_settings_repository import ChatSettingsRepository
from src.repositories.token_repository import TokenRepository
from src.services.core.instagram_account_service import InstagramAccountService
from src.services.core.settings_service import SettingsService
from src.utils.logger import logger
from src.utils.webapp_auth import validate_init_data

router = APIRouter(tags=["onboarding"])

# Google Drive folder URL pattern
GDRIVE_FOLDER_RE = re.compile(
    r"https?://drive\.google\.com/drive/folders/([a-zA-Z0-9_-]+)"
)


# --- Request/Response models ---


class InitRequest(BaseModel):
    init_data: str
    chat_id: int


class MediaFolderRequest(BaseModel):
    init_data: str
    chat_id: int
    folder_url: str


class ScheduleRequest(BaseModel):
    init_data: str
    chat_id: int
    posts_per_day: int
    posting_hours_start: int
    posting_hours_end: int


class CompleteRequest(BaseModel):
    init_data: str
    chat_id: int
    create_schedule: bool = False
    schedule_days: int = 7


# --- Helpers ---


def _validate_request(init_data: str) -> dict:
    """Validate initData and return user info. Raises HTTPException on failure."""
    try:
        return validate_init_data(init_data)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


def _get_setup_state(telegram_chat_id: int) -> dict:
    """Build the current setup state for a chat."""
    settings_repo = ChatSettingsRepository()
    token_repo = TokenRepository()

    try:
        chat_settings = settings_repo.get_or_create(telegram_chat_id)
        chat_settings_id = str(chat_settings.id)

        # Check Instagram connection
        instagram_connected = False
        instagram_username = None
        account_service = InstagramAccountService()
        try:
            active_account = account_service.get_active_account(telegram_chat_id)
            if active_account:
                instagram_connected = True
                instagram_username = active_account.instagram_username
        finally:
            account_service.close()

        # Check Google Drive connection
        gdrive_connected = False
        gdrive_email = None
        gdrive_token = token_repo.get_token_for_chat(
            "google_drive", "oauth_access", chat_settings_id
        )
        if gdrive_token:
            gdrive_connected = True
            # Email stored in token_metadata dict
            if gdrive_token.token_metadata:
                gdrive_email = gdrive_token.token_metadata.get("email")

        return {
            "instagram_connected": instagram_connected,
            "instagram_username": instagram_username,
            "gdrive_connected": gdrive_connected,
            "gdrive_email": gdrive_email,
            "posts_per_day": chat_settings.posts_per_day,
            "posting_hours_start": chat_settings.posting_hours_start,
            "posting_hours_end": chat_settings.posting_hours_end,
            "onboarding_completed": chat_settings.onboarding_completed,
        }
    finally:
        settings_repo.close()
        token_repo.close()


# --- Endpoints ---


@router.post("/init")
async def onboarding_init(request: InitRequest):
    """Validate initData and return current setup state for this chat."""
    user_info = _validate_request(request.init_data)

    setup_state = _get_setup_state(request.chat_id)

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
    _validate_request(init_data)

    if provider == "instagram":
        from src.services.core.oauth_service import OAuthService

        service = OAuthService()
        try:
            auth_url = service.generate_authorization_url(chat_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        finally:
            service.close()
        return {"auth_url": auth_url}

    elif provider == "google-drive":
        from src.services.integrations.google_drive_oauth import (
            GoogleDriveOAuthService,
        )

        service = GoogleDriveOAuthService()
        try:
            auth_url = service.generate_authorization_url(chat_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        finally:
            service.close()
        return {"auth_url": auth_url}

    else:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")


@router.post("/media-folder")
async def onboarding_media_folder(request: MediaFolderRequest):
    """Set the Google Drive media folder for this chat."""
    _validate_request(request.init_data)

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
    from src.services.integrations.google_drive import GoogleDriveService

    gdrive_service = GoogleDriveService()
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
    finally:
        gdrive_service.close()

    # TODO: Store folder_id in chat_settings when media_source_root column exists

    return {
        "folder_id": folder_id,
        "file_count": file_count,
        "categories": sorted(categories),
    }


@router.post("/schedule")
async def onboarding_schedule(request: ScheduleRequest):
    """Save posting schedule configuration."""
    _validate_request(request.init_data)

    settings_service = SettingsService()
    try:
        settings_service.update_setting(
            request.chat_id, "posts_per_day", request.posts_per_day
        )
        settings_service.update_setting(
            request.chat_id, "posting_hours_start", request.posting_hours_start
        )
        settings_service.update_setting(
            request.chat_id, "posting_hours_end", request.posting_hours_end
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        settings_service.close()

    return {
        "posts_per_day": request.posts_per_day,
        "posting_hours_start": request.posting_hours_start,
        "posting_hours_end": request.posting_hours_end,
    }


@router.post("/complete")
async def onboarding_complete(request: CompleteRequest):
    """Mark onboarding as finished, optionally create initial schedule."""
    _validate_request(request.init_data)

    settings_service = SettingsService()
    try:
        settings_service.complete_onboarding(request.chat_id)
    finally:
        settings_service.close()

    result = {"onboarding_completed": True, "schedule_created": False}

    if request.create_schedule:
        from src.services.core.scheduler import SchedulerService

        scheduler = SchedulerService()
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
        finally:
            scheduler.close()

    return result
