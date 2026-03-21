"""Shared helpers for onboarding API routes."""

import re
from contextlib import contextmanager

from fastapi import HTTPException

from src.services.core.setup_state_service import SetupStateService
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
    with SetupStateService() as service:
        return service.get_setup_state(telegram_chat_id)


@contextmanager
def service_error_handler():
    """Convert service ValueError exceptions to HTTP 400 responses."""
    try:
        yield
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
