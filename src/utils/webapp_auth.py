"""Telegram WebApp initData validation and URL token authentication."""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qs

from src.config.settings import settings

INIT_DATA_TTL = 3600  # 1 hour
URL_TOKEN_TTL = 3600  # 1 hour


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


def generate_url_token(chat_id: int, user_id: int) -> str:
    """Generate a signed URL token for browser-based webapp access.

    Used when WebAppInfo buttons aren't available (e.g. group chats)
    and the webapp is opened via a regular URL button instead.

    Token format: {chat_id}:{user_id}:{timestamp}:{signature}
    """
    timestamp = int(time.time())
    payload = f"{chat_id}:{user_id}:{timestamp}"
    secret_key = hmac.new(
        b"UrlToken", settings.TELEGRAM_BOT_TOKEN.encode(), hashlib.sha256
    ).digest()
    signature = hmac.new(secret_key, payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{signature}"


def validate_url_token(token: str) -> dict:
    """Validate a signed URL token and extract chat/user info.

    Args:
        token: The token string from the URL parameter.

    Returns:
        dict with user_id, chat_id

    Raises:
        ValueError: If signature is invalid or token is expired.
    """
    if not token:
        raise ValueError("Empty token")

    parts = token.split(":")
    if len(parts) != 4:
        raise ValueError("Invalid token format")

    chat_id_str, user_id_str, timestamp_str, received_sig = parts

    try:
        chat_id = int(chat_id_str)
        user_id = int(user_id_str)
        timestamp = int(timestamp_str)
    except (ValueError, TypeError):
        raise ValueError("Invalid token values")

    # Verify signature
    payload = f"{chat_id}:{user_id}:{timestamp}"
    secret_key = hmac.new(
        b"UrlToken", settings.TELEGRAM_BOT_TOKEN.encode(), hashlib.sha256
    ).digest()
    computed_sig = hmac.new(secret_key, payload.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_sig, received_sig):
        raise ValueError("Invalid token signature")

    # Check TTL
    if time.time() - timestamp > URL_TOKEN_TTL:
        raise ValueError("Token expired")

    return {"user_id": user_id, "chat_id": chat_id}
