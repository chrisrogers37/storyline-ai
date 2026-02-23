"""Onboarding Mini App API endpoints."""

import re

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.repositories.chat_settings_repository import ChatSettingsRepository
from src.repositories.history_repository import HistoryRepository
from src.repositories.media_repository import MediaRepository
from src.repositories.queue_repository import QueueRepository
from src.repositories.token_repository import TokenRepository
from src.services.core.instagram_account_service import InstagramAccountService
from src.services.core.settings_service import SettingsService
from src.utils.logger import logger
from src.utils.webapp_auth import validate_init_data, validate_url_token

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


class StartIndexingRequest(BaseModel):
    init_data: str
    chat_id: int


class ScheduleRequest(BaseModel):
    init_data: str
    chat_id: int
    posts_per_day: int = Field(ge=1, le=50)
    posting_hours_start: int = Field(ge=0, le=23)
    posting_hours_end: int = Field(ge=0, le=23)


class CompleteRequest(BaseModel):
    init_data: str
    chat_id: int
    create_schedule: bool = False
    schedule_days: int = Field(default=7, ge=1, le=30)


class ToggleSettingRequest(BaseModel):
    init_data: str
    chat_id: int
    setting_name: str


class ScheduleActionRequest(BaseModel):
    init_data: str
    chat_id: int
    days: int = Field(default=7, ge=1, le=30)


# --- Helpers ---


def _validate_request(init_data: str, chat_id: int) -> dict:
    """Validate initData or URL token, and verify chat_id matches.

    Accepts either Telegram WebApp initData (from Mini App) or a signed
    URL token (from group chat browser links). The init_data field carries
    whichever credential the frontend provides.

    Raises HTTPException on auth failure or chat_id mismatch.
    """
    # Try Telegram initData first, fall back to URL token
    try:
        user_info = validate_init_data(init_data)
    except ValueError:
        # Not valid initData — try URL token format
        try:
            user_info = validate_url_token(init_data)
        except ValueError as e:
            raise HTTPException(status_code=401, detail=str(e))

    # If auth contains a chat_id, verify it matches the request
    signed_chat_id = user_info.get("chat_id")
    if signed_chat_id is not None and signed_chat_id != chat_id:
        logger.warning(
            f"Chat ID mismatch: auth has {signed_chat_id}, "
            f"request has {chat_id} (user_id={user_info.get('user_id')})"
        )
        raise HTTPException(status_code=403, detail="Chat ID mismatch")

    return user_info


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

        # Check media folder configuration
        media_folder_configured = bool(chat_settings.media_source_root)
        media_folder_id = chat_settings.media_source_root

        # Check if media has been indexed
        media_count = 0
        media_indexed = False
        if media_folder_configured:
            from src.repositories.media_repository import MediaRepository

            media_repo = MediaRepository()
            try:
                active_items = media_repo.get_active_by_source_type(
                    "google_drive", chat_settings_id=chat_settings_id
                )
                media_count = len(active_items)
                media_indexed = media_count > 0
            finally:
                media_repo.close()

        # Dashboard data: queue count, last post time, schedule bounds
        queue_count = 0
        last_post_at = None
        next_post_at = None
        schedule_end_date = None
        try:
            queue_repo = QueueRepository()
            history_repo = HistoryRepository()
            try:
                pending_items = queue_repo.get_all(
                    status="pending", chat_settings_id=chat_settings_id
                )
                queue_count = len(pending_items)
                if pending_items:
                    # Items are ordered by scheduled_for ASC
                    next_post_at = pending_items[0].scheduled_for.isoformat()
                    schedule_end_date = pending_items[-1].scheduled_for.isoformat()
                recent_posts = history_repo.get_recent_posts(
                    hours=720, chat_settings_id=chat_settings_id
                )
                if recent_posts:
                    last_post_at = recent_posts[0].posted_at.isoformat()
            finally:
                queue_repo.close()
                history_repo.close()
        except Exception:
            logger.debug("Failed to fetch queue/history for onboarding init")

        return {
            "instagram_connected": instagram_connected,
            "instagram_username": instagram_username,
            "gdrive_connected": gdrive_connected,
            "gdrive_email": gdrive_email,
            "media_folder_configured": media_folder_configured,
            "media_folder_id": media_folder_id,
            "media_indexed": media_indexed,
            "media_count": media_count,
            "posts_per_day": chat_settings.posts_per_day,
            "posting_hours_start": chat_settings.posting_hours_start,
            "posting_hours_end": chat_settings.posting_hours_end,
            "onboarding_completed": chat_settings.onboarding_completed,
            "onboarding_step": chat_settings.onboarding_step,
            "is_paused": chat_settings.is_paused,
            "dry_run_mode": chat_settings.dry_run_mode,
            "queue_count": queue_count,
            "last_post_at": last_post_at,
            "next_post_at": next_post_at,
            "schedule_end_date": schedule_end_date,
        }
    finally:
        settings_repo.close()
        token_repo.close()


# --- Endpoints ---


@router.post("/init")
async def onboarding_init(request: InitRequest):
    """Validate initData and return current setup state for this chat."""
    user_info = _validate_request(request.init_data, request.chat_id)

    setup_state = _get_setup_state(request.chat_id)

    # Set initial onboarding step if not yet started
    if not setup_state.get("onboarding_completed") and not setup_state.get(
        "onboarding_step"
    ):
        settings_service = SettingsService()
        try:
            settings_service.set_onboarding_step(request.chat_id, "welcome")
        finally:
            settings_service.close()
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

    # Persist folder config to per-chat settings
    settings_service = SettingsService()
    try:
        settings_service.update_setting(
            request.chat_id, "media_source_type", "google_drive"
        )
        settings_service.update_setting(request.chat_id, "media_source_root", folder_id)
        settings_service.update_setting(request.chat_id, "media_sync_enabled", True)
        settings_service.set_onboarding_step(request.chat_id, "media_folder")
    finally:
        settings_service.close()

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

    settings_repo = ChatSettingsRepository()
    try:
        chat_settings = settings_repo.get_or_create(request.chat_id)
        source_type = chat_settings.media_source_type
        source_root = chat_settings.media_source_root
    finally:
        settings_repo.close()

    if not source_root:
        raise HTTPException(
            status_code=400,
            detail="No media folder configured. Complete the media folder step first.",
        )

    from src.services.core.media_sync import MediaSyncService

    sync_service = MediaSyncService()
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
    finally:
        sync_service.close()

    # Update onboarding step
    step_service = SettingsService()
    try:
        step_service.set_onboarding_step(request.chat_id, "indexing")
    finally:
        step_service.close()

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
        settings_service.set_onboarding_step(request.chat_id, "schedule")
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
    """Mark onboarding as finished, auto-configure dependent settings."""
    _validate_request(request.init_data, request.chat_id)

    settings_service = SettingsService()
    try:
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


# --- Dashboard Detail Endpoints ---


@router.get("/queue-detail")
async def onboarding_queue_detail(
    init_data: str,
    chat_id: int,
    limit: int = Query(default=10, ge=1, le=50),
):
    """Return detailed queue items with schedule summary for dashboard."""
    _validate_request(init_data, chat_id)

    settings_repo = ChatSettingsRepository()
    queue_repo = QueueRepository()
    try:
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
        media_repo = MediaRepository()
        try:
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
        finally:
            media_repo.close()

        schedule_end = None
        days_remaining = None
        if pending_items:
            from datetime import datetime, timezone

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
    finally:
        settings_repo.close()
        queue_repo.close()


@router.get("/history-detail")
async def onboarding_history_detail(
    init_data: str,
    chat_id: int,
    limit: int = Query(default=10, ge=1, le=50),
):
    """Return recent posting history with media info for dashboard."""
    _validate_request(init_data, chat_id)

    settings_repo = ChatSettingsRepository()
    history_repo = HistoryRepository()
    try:
        chat_settings = settings_repo.get_or_create(chat_id)
        chat_settings_id = str(chat_settings.id)

        history_items = history_repo.get_all(
            limit=limit, chat_settings_id=chat_settings_id
        )

        items = []
        media_repo = MediaRepository()
        try:
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
        finally:
            media_repo.close()

        return {"items": items}
    finally:
        settings_repo.close()
        history_repo.close()


@router.get("/media-stats")
async def onboarding_media_stats(
    init_data: str,
    chat_id: int,
):
    """Return media library breakdown by category for dashboard."""
    _validate_request(init_data, chat_id)

    settings_repo = ChatSettingsRepository()
    try:
        chat_settings = settings_repo.get_or_create(chat_id)
        chat_settings_id = str(chat_settings.id)

        media_repo = MediaRepository()
        try:
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
        finally:
            media_repo.close()
    finally:
        settings_repo.close()


@router.post("/toggle-setting")
async def onboarding_toggle_setting(request: ToggleSettingRequest):
    """Toggle a boolean setting (is_paused, dry_run_mode) from dashboard."""
    _validate_request(request.init_data, request.chat_id)

    allowed_settings = {"is_paused", "dry_run_mode"}
    if request.setting_name not in allowed_settings:
        raise HTTPException(
            status_code=400,
            detail=f"Setting '{request.setting_name}' cannot be toggled from dashboard. "
            f"Allowed: {', '.join(sorted(allowed_settings))}",
        )

    settings_service = SettingsService()
    try:
        new_value = settings_service.toggle_setting(
            request.chat_id, request.setting_name
        )
        return {
            "setting_name": request.setting_name,
            "new_value": new_value,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        settings_service.close()


@router.post("/extend-schedule")
async def onboarding_extend_schedule(request: ScheduleActionRequest):
    """Extend the posting schedule by N days."""
    _validate_request(request.init_data, request.chat_id)

    from src.services.core.scheduler import SchedulerService

    scheduler = SchedulerService()
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
    finally:
        scheduler.close()


@router.post("/regenerate-schedule")
async def onboarding_regenerate_schedule(request: ScheduleActionRequest):
    """Clear all pending queue items and create a fresh schedule."""
    _validate_request(request.init_data, request.chat_id)

    settings_repo = ChatSettingsRepository()
    queue_repo = QueueRepository()
    try:
        chat_settings = settings_repo.get_or_create(request.chat_id)
        chat_settings_id = str(chat_settings.id)

        deleted = queue_repo.delete_all_pending(chat_settings_id=chat_settings_id)
        logger.info(
            f"Regenerate schedule: cleared {deleted} pending items "
            f"for chat {request.chat_id}"
        )
    finally:
        settings_repo.close()
        queue_repo.close()

    from src.services.core.scheduler import SchedulerService

    scheduler = SchedulerService()
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
    finally:
        scheduler.close()
