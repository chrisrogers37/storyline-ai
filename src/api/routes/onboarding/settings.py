"""Settings and schedule action endpoints for onboarding Mini App."""

import httpx
from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import OperationalError

from src.config.settings import settings

from src.models.instagram_account import AUTH_METHOD_MANUAL
from src.services.core.instagram_account_service import InstagramAccountService
from src.services.core.media_sync import MediaSyncService
from src.services.core.scheduler import SchedulerService
from src.services.core.settings_service import SettingsService
from src.services.integrations.google_drive_oauth import GoogleDriveOAuthService
from src.utils.logger import logger

from src.repositories.category_mix_repository import CategoryMixRepository
from src.repositories.media_repository import MediaRepository

from .helpers import _validate_request, service_error_handler
from .models import (
    AddAccountRequest,
    InitRequest,
    RemoveAccountRequest,
    SwitchAccountRequest,
    ToggleSettingRequest,
    UpdateCategoryMixRequest,
    UpdateSettingRequest,
)

router = APIRouter(tags=["onboarding"])


@router.post("/toggle-setting")
async def onboarding_toggle_setting(request: ToggleSettingRequest) -> dict:
    """Toggle a boolean setting (is_paused, dry_run_mode) from dashboard."""
    _validate_request(request.init_data, request.chat_id)

    allowed_settings = {
        "is_paused",
        "dry_run_mode",
        "enable_instagram_api",
        "show_verbose_notifications",
        "media_sync_enabled",
        "enable_ai_captions",
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
async def onboarding_update_setting(request: UpdateSettingRequest) -> dict:
    """Update a numeric setting (posts_per_day, posting hours) from dashboard."""
    _validate_request(request.init_data, request.chat_id)

    allowed_settings = {
        "posts_per_day",
        "posting_hours_start",
        "posting_hours_end",
        "repost_ttl_days",
        "skip_ttl_days",
    }
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
async def onboarding_switch_account(request: SwitchAccountRequest) -> dict:
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
async def onboarding_remove_account(request: RemoveAccountRequest) -> dict:
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


@router.post("/disconnect-gdrive")
async def onboarding_disconnect_gdrive(request: InitRequest) -> dict:
    """Disconnect Google Drive for this chat.

    Deletes OAuth tokens, clears the media folder config, and disables
    media sync. The user can reconnect via the OAuth flow afterward.
    """
    _validate_request(request.init_data, request.chat_id)

    with GoogleDriveOAuthService() as gdrive_service, service_error_handler():
        result = gdrive_service.disconnect_for_chat(request.chat_id)
        return result


@router.post("/sync-media")
async def onboarding_sync_media(request: InitRequest) -> dict:
    """Trigger media sync from the dashboard.

    Calls MediaSyncService.sync() with the chat's per-tenant config.
    Returns sync result counts (new, updated, deactivated, etc).
    """
    _validate_request(request.init_data, request.chat_id)

    with SettingsService() as settings_service:
        source_type, source_root = settings_service.get_media_source_config(
            request.chat_id
        )

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
        except OperationalError as e:
            logger.error(f"Media sync DB error: {e}")
            raise HTTPException(
                status_code=503,
                detail="Database temporarily unavailable. Please try again.",
            )
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


@router.post("/queue-preview")
async def onboarding_queue_preview(request: InitRequest) -> dict:
    """Preview the next N media items that would be selected.

    Computes JIT selections without persisting — shows what the
    scheduler would pick next.
    """
    _validate_request(request.init_data, request.chat_id)

    with SchedulerService() as scheduler:
        previews = scheduler.get_queue_preview(
            telegram_chat_id=request.chat_id, count=5
        )
        return {"items": previews}


@router.post("/add-account")
async def onboarding_add_account(request: AddAccountRequest) -> dict:
    """Add an Instagram account via secure Mini App form.

    Validates credentials against Instagram Graph API, then creates
    or updates the account. Credentials are transmitted via HTTPS
    and never appear in Telegram chat history.
    """
    _validate_request(request.init_data, request.chat_id)

    # Validate credentials against Instagram API
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.meta_graph_base}/{request.instagram_account_id}",
                params={
                    "fields": "username",
                    "access_token": request.access_token,
                },
                timeout=30.0,
            )
    except httpx.HTTPError as e:
        logger.error(f"Instagram API network error during add-account: {e}")
        raise HTTPException(
            status_code=502,
            detail="Could not reach Instagram API. Please try again.",
        )

    if response.status_code != 200:
        error_data = response.json()
        error_msg = error_data.get("error", {}).get("message", "Unknown error")
        # Replace technical OAuth errors with user-friendly message
        if "Invalid OAuth" in error_msg or "access token" in error_msg.lower():
            error_msg = (
                "Invalid access token. Please check it hasn't expired and try again."
            )
        raise HTTPException(status_code=400, detail=error_msg)

    api_data = response.json()
    username = api_data.get("username")
    if not username:
        raise HTTPException(
            status_code=400,
            detail="Could not fetch username from Instagram API.",
        )

    # Create or update account
    with InstagramAccountService() as account_service, service_error_handler():
        existing = account_service.get_account_by_instagram_id(
            request.instagram_account_id
        )

        if existing:
            account = account_service.update_account_token(
                instagram_account_id=request.instagram_account_id,
                access_token=request.access_token,
                instagram_username=username,
                set_as_active=True,
                telegram_chat_id=request.chat_id,
                auth_method=AUTH_METHOD_MANUAL,
            )
            is_update = True
        else:
            account = account_service.add_account(
                display_name=request.display_name,
                instagram_account_id=request.instagram_account_id,
                instagram_username=username,
                access_token=request.access_token,
                set_as_active=True,
                telegram_chat_id=request.chat_id,
                auth_method=AUTH_METHOD_MANUAL,
            )
            is_update = False

        return {
            "account_id": str(account.id),
            "display_name": account.display_name,
            "instagram_username": account.instagram_username,
            "is_update": is_update,
        }


@router.post("/category-mix")
async def onboarding_get_category_mix(request: InitRequest) -> dict:
    """Read the current category mix and library composition for this chat.

    Returns one entry per category present in the chat's active library.
    `configured_ratio` is None for any category without a current row in
    `category_post_case_mix` — the UI uses that to distinguish "no mix
    set, scheduler is unfiltered random" from "explicit 0%".
    """
    _validate_request(request.init_data, request.chat_id)

    with SettingsService() as settings_service, service_error_handler():
        chat_settings = settings_service.get_settings(request.chat_id)
        chat_settings_id = str(chat_settings.id)

    with MediaRepository() as media_repo:
        library_counts = media_repo.count_by_category(chat_settings_id=chat_settings_id)

    with CategoryMixRepository() as mix_repo:
        current = mix_repo.get_current_mix_as_dict(chat_settings_id=chat_settings_id)
        has_explicit_mix = mix_repo.has_current_mix(chat_settings_id=chat_settings_id)

    categories = sorted(set(library_counts.keys()) | set(current.keys()))
    return {
        "has_explicit_mix": has_explicit_mix,
        "categories": [
            {
                "name": name,
                "library_count": int(library_counts.get(name, 0)),
                "configured_ratio": (float(current[name]) if name in current else None),
            }
            for name in categories
        ],
    }


@router.post("/update-category-mix")
async def onboarding_update_category_mix(request: UpdateCategoryMixRequest) -> dict:
    """Replace the category mix with new ratios (Type 2 SCD: expires + creates).

    Validation (sum=1.0 within tolerance, non-negative ratios, no unknown
    categories) is enforced by CategoryMixRepository.set_mix. Returns the
    refreshed mix in the same shape as the GET endpoint so the UI can
    update in place.
    """
    _validate_request(request.init_data, request.chat_id)

    if not request.ratios:
        raise HTTPException(status_code=400, detail="ratios must be non-empty")

    with SettingsService() as settings_service, service_error_handler():
        chat_settings = settings_service.get_settings(request.chat_id)
        chat_settings_id = str(chat_settings.id)

    with MediaRepository() as media_repo:
        library_counts = media_repo.count_by_category(chat_settings_id=chat_settings_id)

    known_categories = set(library_counts.keys())
    unknown = sorted(set(request.ratios.keys()) - known_categories)
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown categories not present in library: {', '.join(unknown)}",
        )

    from decimal import Decimal

    decimal_ratios = {k: Decimal(str(v)) for k, v in request.ratios.items()}

    with CategoryMixRepository() as mix_repo:
        try:
            mix_repo.set_mix(
                ratios=decimal_ratios,
                chat_settings_id=chat_settings_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        current = mix_repo.get_current_mix_as_dict(chat_settings_id=chat_settings_id)

    categories = sorted(set(library_counts.keys()) | set(current.keys()))
    return {
        "has_explicit_mix": True,
        "categories": [
            {
                "name": name,
                "library_count": int(library_counts.get(name, 0)),
                "configured_ratio": (float(current[name]) if name in current else None),
            }
            for name in categories
        ],
    }
