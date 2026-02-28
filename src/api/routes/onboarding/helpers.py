"""Shared helpers for onboarding API routes."""

import re
from contextlib import contextmanager
from datetime import datetime, timedelta

from fastapi import HTTPException

from src.repositories.chat_settings_repository import ChatSettingsRepository
from src.repositories.history_repository import HistoryRepository
from src.repositories.media_repository import MediaRepository
from src.repositories.queue_repository import QueueRepository
from src.repositories.token_repository import TokenRepository
from src.services.core.instagram_account_service import InstagramAccountService
from src.utils.logger import logger
from src.utils.webapp_auth import validate_init_data, validate_url_token

# Google Drive folder URL pattern
GDRIVE_FOLDER_RE = re.compile(
    r"https?://drive\.google\.com/drive/folders/([a-zA-Z0-9_-]+)"
)


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
    with (
        ChatSettingsRepository() as settings_repo,
        TokenRepository() as token_repo,
    ):
        chat_settings = settings_repo.get_or_create(telegram_chat_id)
        chat_settings_id = str(chat_settings.id)

        # Check Instagram connection
        instagram_connected = False
        instagram_username = None
        with InstagramAccountService() as account_service:
            active_account = account_service.get_active_account(telegram_chat_id)
            if active_account:
                instagram_connected = True
                instagram_username = active_account.instagram_username

        # Check Google Drive connection
        gdrive_connected = False
        gdrive_email = None
        gdrive_needs_reconnect = False
        gdrive_token = token_repo.get_token_for_chat(
            "google_drive", "oauth_access", chat_settings_id
        )
        if gdrive_token:
            gdrive_connected = True
            # Email stored in token_metadata dict
            if gdrive_token.token_metadata:
                gdrive_email = gdrive_token.token_metadata.get("email")
            # Detect stale token (expired >7 days ago)
            if (
                gdrive_token.expires_at
                and gdrive_token.expires_at < datetime.utcnow() - timedelta(days=7)
            ):
                gdrive_needs_reconnect = True

        # Check media folder configuration
        media_folder_configured = bool(chat_settings.media_source_root)
        media_folder_id = chat_settings.media_source_root

        # Check if media has been indexed
        media_count = 0
        media_indexed = False
        if media_folder_configured:
            with MediaRepository() as media_repo:
                active_items = media_repo.get_active_by_source_type(
                    "google_drive", chat_settings_id=chat_settings_id
                )
                media_count = len(active_items)
                media_indexed = media_count > 0

        # Dashboard data: queue count, last post time, schedule bounds
        queue_count = 0
        last_post_at = None
        next_post_at = None
        schedule_end_date = None
        try:
            with QueueRepository() as queue_repo, HistoryRepository() as history_repo:
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
        except Exception:
            logger.debug("Failed to fetch queue/history for onboarding init")

        return {
            "instagram_connected": instagram_connected,
            "instagram_username": instagram_username,
            "gdrive_connected": gdrive_connected,
            "gdrive_email": gdrive_email,
            "gdrive_needs_reconnect": gdrive_needs_reconnect,
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
            "enable_instagram_api": chat_settings.enable_instagram_api,
            "show_verbose_notifications": chat_settings.show_verbose_notifications,
            "media_sync_enabled": chat_settings.media_sync_enabled,
            "queue_count": queue_count,
            "last_post_at": last_post_at,
            "next_post_at": next_post_at,
            "schedule_end_date": schedule_end_date,
        }


@contextmanager
def service_error_handler():
    """Convert service ValueError exceptions to HTTP 400 responses."""
    try:
        yield
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
