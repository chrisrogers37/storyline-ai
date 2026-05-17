"""In-memory authentication failure monitoring with Telegram alerting."""

import time
import threading

import httpx

from src.config.settings import settings
from src.utils.logger import logger

FAILURE_THRESHOLD = 5
WINDOW_SECONDS = 600  # 10 minutes

_lock = threading.Lock()
_failures: dict[str, list[float]] = {}


def record_failure(source: str, reason: str) -> None:
    """Record an auth failure and alert if threshold is exceeded.

    Args:
        source: Identifier for the failure origin (IP address or chat_id).
        reason: Human-readable failure reason for the log/alert.
    """
    now = time.time()
    cutoff = now - WINDOW_SECONDS

    with _lock:
        timestamps = _failures.get(source, [])
        # Prune expired entries
        timestamps = [t for t in timestamps if t > cutoff]
        timestamps.append(now)
        _failures[source] = timestamps
        count = len(timestamps)

    logger.warning("Auth failure #%d from %s: %s", count, source, reason)

    if count == FAILURE_THRESHOLD:
        _send_alert(source, count)


def _send_alert(source: str, count: int) -> None:
    """Send a Telegram alert to the admin chat (fire-and-forget)."""
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.ADMIN_TELEGRAM_CHAT_ID
    text = (
        f"Auth alert: {count} failures from {source} "
        f"in the last {WINDOW_SECONDS // 60} min"
    )

    try:
        resp = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=5.0,
        )
        resp.raise_for_status()
    except httpx.HTTPError:
        logger.error("Failed to send auth-failure alert for %s", source)


def reset() -> None:
    """Clear all tracked failures. Useful for testing."""
    with _lock:
        _failures.clear()
