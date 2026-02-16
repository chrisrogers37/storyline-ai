"""Telegram WebApp initData validation for Mini App authentication."""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qs

from src.config.settings import settings

INIT_DATA_TTL = 3600  # 1 hour


def validate_init_data(init_data: str) -> dict:
    """Validate Telegram WebApp initData and extract user info.

    The initData string is signed by Telegram using HMAC-SHA256 with a key
    derived from the bot token. This proves the request came from a real
    Telegram user via the WebApp SDK.

    Args:
        init_data: The raw initData string from Telegram.WebApp.initData

    Returns:
        dict with user_id, first_name

    Raises:
        ValueError: If signature is invalid, data is expired, or hash is missing
    """
    if not init_data:
        raise ValueError("Empty initData")

    parsed = parse_qs(init_data)

    # Extract and remove hash
    received_hash = parsed.pop("hash", [None])[0]
    if not received_hash:
        raise ValueError("Missing hash in initData")

    # Sort remaining params alphabetically, join with newlines
    data_check_string = "\n".join(f"{k}={v[0]}" for k, v in sorted(parsed.items()))

    # HMAC-SHA256: secret = HMAC("WebAppData", bot_token)
    secret_key = hmac.new(
        b"WebAppData", settings.TELEGRAM_BOT_TOKEN.encode(), hashlib.sha256
    ).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise ValueError("Invalid initData signature")

    # Check TTL
    auth_date = int(parsed.get("auth_date", [0])[0])
    if time.time() - auth_date > INIT_DATA_TTL:
        raise ValueError("initData expired")

    # Parse user JSON
    user_json = parsed.get("user", ["{}"])[0]
    user_data = json.loads(user_json)

    result = {
        "user_id": user_data.get("id"),
        "first_name": user_data.get("first_name"),
    }

    # Extract chat_id if present (available when opened from a group chat)
    chat_json = parsed.get("chat", [None])[0]
    if chat_json:
        chat_data = json.loads(chat_json)
        result["chat_id"] = chat_data.get("id")

    return result
