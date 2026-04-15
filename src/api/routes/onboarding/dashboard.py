"""Dashboard detail endpoints for onboarding Mini App."""

import hashlib
import mimetypes
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile

from src.repositories.media_repository import MediaRepository
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
) -> dict:
    """Return detailed queue items with schedule summary for dashboard."""
    _validate_request(init_data, chat_id)

    with DashboardService() as service:
        return service.get_queue_detail(chat_id, limit=limit)


@router.get("/history-detail")
async def onboarding_history_detail(
    init_data: str,
    chat_id: int,
    limit: int = Query(default=10, ge=1, le=50),
) -> dict:
    """Return recent posting history with media info for dashboard."""
    _validate_request(init_data, chat_id)

    with DashboardService() as service:
        return service.get_history_detail(chat_id, limit=limit)


@router.get("/media-stats")
async def onboarding_media_stats(
    init_data: str,
    chat_id: int,
) -> dict:
    """Return media library breakdown by category for dashboard."""
    _validate_request(init_data, chat_id)

    with DashboardService() as service:
        return service.get_media_stats(chat_id)


@router.get("/accounts")
async def onboarding_accounts(
    init_data: str,
    chat_id: int,
) -> dict:
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
) -> dict:
    """Return posting time recommendations based on approval patterns."""
    _validate_request(init_data, chat_id)

    with DashboardService() as service:
        return service.get_schedule_recommendations(chat_id, days=days)


@router.get("/analytics/categories")
async def onboarding_analytics_categories(
    init_data: str,
    chat_id: int,
    days: int = Query(default=30, ge=1, le=365),
) -> dict:
    """Return per-category performance with configured vs actual ratios."""
    _validate_request(init_data, chat_id)

    with DashboardService() as service:
        return service.get_category_analytics(chat_id, days=days)


@router.get("/analytics/schedule-preview")
async def onboarding_schedule_preview(
    init_data: str,
    chat_id: int,
    slots: int = Query(default=10, ge=1, le=50),
) -> dict:
    """Return upcoming scheduled slots with predicted categories."""
    _validate_request(init_data, chat_id)

    with DashboardService() as service:
        return service.get_schedule_preview(chat_id, slots=slots)


@router.get("/analytics/content-reuse")
async def onboarding_content_reuse(
    init_data: str,
    chat_id: int,
) -> dict:
    """Return content reuse insights — evergreen vs one-shot media."""
    _validate_request(init_data, chat_id)

    with DashboardService() as service:
        return service.get_content_reuse_insights(chat_id)


@router.get("/analytics/service-health")
async def onboarding_service_health(
    init_data: str,
    hours: int = Query(default=24, ge=1, le=168),
) -> dict:
    """Return service execution telemetry from service_runs table.

    Global view — service_runs are system-level, not per-tenant.
    Requires valid init_data for authentication but does not scope by chat.
    """
    # Auth-only validation (no chat_id scoping — service runs are global)
    from src.utils.webapp_auth import validate_init_data

    validate_init_data(init_data)

    with DashboardService() as service:
        return service.get_service_health_stats(hours=hours)


@router.get("/analytics/category-drift")
async def onboarding_category_drift(
    init_data: str,
    chat_id: int,
    days: int = Query(default=7, ge=1, le=90),
) -> dict:
    """Return category mix drift — configured vs actual posting ratios."""
    _validate_request(init_data, chat_id)

    with DashboardService() as service:
        return service.get_category_mix_drift(chat_id, days=days)


@router.get("/analytics/dead-content")
async def onboarding_dead_content(
    init_data: str,
    chat_id: int,
    min_age_days: int = Query(default=30, ge=1, le=365),
) -> dict:
    """Return dead content report — never-posted media items."""
    _validate_request(init_data, chat_id)

    with DashboardService() as service:
        return service.get_dead_content_report(chat_id, min_age_days=min_age_days)


@router.get("/analytics/approval-latency")
async def onboarding_approval_latency(
    init_data: str,
    chat_id: int,
    days: int = Query(default=30, ge=1, le=365),
) -> dict:
    """Return approval latency statistics — time from queue to decision."""
    _validate_request(init_data, chat_id)

    with DashboardService() as service:
        return service.get_approval_latency(chat_id, days=days)


@router.get("/analytics/team-performance")
async def onboarding_team_performance(
    init_data: str,
    chat_id: int,
    days: int = Query(default=30, ge=1, le=365),
) -> dict:
    """Return per-user approval rates and response times."""
    _validate_request(init_data, chat_id)

    with DashboardService() as service:
        return service.get_team_performance(chat_id, days=days)


@router.get("/analytics")
async def onboarding_analytics(
    init_data: str,
    chat_id: int,
    days: int = Query(default=30, ge=1, le=365),
) -> dict:
    """Return aggregated posting analytics for the dashboard."""
    _validate_request(init_data, chat_id)

    with DashboardService() as service:
        return service.get_analytics(chat_id, days=days)


@router.get("/system-status")
async def onboarding_system_status(
    init_data: str,
    chat_id: int,
) -> dict:
    """Return system health checks for the dashboard status card."""
    _validate_request(init_data, chat_id)

    with HealthCheckService() as health_service:
        return health_service.check_all()


@router.get("/media-library")
async def onboarding_media_library(
    init_data: str,
    chat_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    category: str | None = Query(default=None),
    posting_status: str | None = Query(default=None),
) -> dict:
    """Return paginated media library with pool health stats."""
    _validate_request(init_data, chat_id)

    with DashboardService() as service:
        return service.get_media_library(
            chat_id,
            page=page,
            page_size=page_size,
            category=category,
            posting_status=posting_status,
        )


# Ephemeral local storage — files survive service restarts but not OS reboots.
# Media records in DB will have stale source_identifier paths after reboot.
# Planned migration: Cloudinary persistent storage (cloud_url columns exist on model).
UPLOAD_DIR = "/tmp/media/uploads"
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "video/mp4",
    "video/quicktime",
}
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB

# Magic bytes for content-type verification (first N bytes → expected MIME)
_MAGIC_SIGNATURES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
}


def _detect_mime_from_magic(content: bytes) -> str | None:
    """Detect MIME type from file magic bytes. Returns None if unrecognized."""
    for signature, mime in _MAGIC_SIGNATURES.items():
        if content[: len(signature)] == signature:
            return mime
    # MP4/QuickTime: check for ftyp box (byte 4-7)
    if len(content) >= 8 and content[4:8] == b"ftyp":
        return "video/mp4"
    return None


@router.post("/upload-media")
async def onboarding_upload_media(
    request: Request,
    init_data: str = Query(...),
    chat_id: int = Query(...),
    file: UploadFile = File(...),
    category: str | None = Form(default=None),
) -> dict:
    """Upload a media file and create a media_item record.

    Files are stored locally and indexed for posting.
    """
    _validate_request(init_data, chat_id)

    # Fast-fail on Content-Length before buffering the file
    content_length = int(request.headers.get("content-length", 0))
    if content_length > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds 50 MB limit")

    # Read file content
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds 50 MB limit")
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    # Validate MIME type from header/extension, then verify with magic bytes
    claimed_mime = (
        file.content_type
        or mimetypes.guess_type(file.filename or "")[0]
        or "application/octet-stream"
    )
    if claimed_mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {claimed_mime}. "
            f"Allowed: {', '.join(sorted(ALLOWED_MIME_TYPES))}",
        )

    actual_mime = _detect_mime_from_magic(content)
    if actual_mime is not None and actual_mime != claimed_mime:
        raise HTTPException(
            status_code=400,
            detail=f"File content ({actual_mime}) does not match declared type ({claimed_mime})",
        )

    file_hash = hashlib.sha256(content).hexdigest()

    # Sanitize filename — strip path components to prevent directory traversal
    safe_name = Path(file.filename or "upload").name
    if not safe_name or safe_name.startswith("."):
        safe_name = "upload"

    # Resolve tenant
    with SettingsService() as settings_service:
        chat_settings = settings_service.get_settings(chat_id)
        chat_settings_id = str(chat_settings.id)

    # Validate category against known categories from DB
    valid_category = None
    if category:
        with MediaRepository() as media_repo:
            known_categories = media_repo.get_categories(
                chat_settings_id=chat_settings_id
            )
        if category in known_categories:
            valid_category = category
        else:
            # Sanitize: strip path separators as defense-in-depth
            sanitized = Path(category).name
            if sanitized and not sanitized.startswith(".") and "/" not in category:
                valid_category = sanitized
            else:
                raise HTTPException(
                    status_code=400, detail=f"Invalid category: {category}"
                )

    # Check for duplicate content
    with MediaRepository() as media_repo:
        existing = media_repo.get_active_by_hash(
            file_hash, chat_settings_id=chat_settings_id
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Duplicate content — matches existing file: {existing.file_name}",
            )

    # Save to disk
    folder = valid_category or "uncategorized"
    save_dir = Path(UPLOAD_DIR) / chat_settings_id / folder
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / safe_name

    # Belt-and-suspenders: verify resolved path is within UPLOAD_DIR
    resolved = save_path.resolve()
    if not str(resolved).startswith(str(Path(UPLOAD_DIR).resolve())):
        raise HTTPException(status_code=400, detail="Invalid file path")

    # Handle filename collisions
    if save_path.exists():
        stem = save_path.stem
        suffix = save_path.suffix
        counter = 1
        while save_path.exists():
            save_path = save_dir / f"{stem}_{counter}{suffix}"
            counter += 1

    save_path.write_bytes(content)

    # Create media_item record
    with MediaRepository() as media_repo:
        media_item = media_repo.create(
            file_path=str(save_path),
            file_name=safe_name,
            file_hash=file_hash,
            file_size_bytes=len(content),
            mime_type=claimed_mime,
            category=valid_category,
            source_type="upload",
            source_identifier=str(save_path),
            chat_settings_id=chat_settings_id,
        )

    return {
        "id": str(media_item.id),
        "file_name": media_item.file_name,
        "category": media_item.category or "uncategorized",
        "file_size": media_item.file_size,
        "mime_type": media_item.mime_type,
        "created_at": media_item.created_at.isoformat(),
    }
