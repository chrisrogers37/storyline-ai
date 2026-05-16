"""Datetime helpers — keep timezone handling consistent across the codebase."""

from datetime import datetime, timezone
from typing import Optional


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Return ``dt`` as a UTC-aware datetime.

    Several DB columns (notably ``api_tokens.expires_at`` and
    ``chat_settings.last_post_sent_at``) are declared as naive ``DateTime``
    but written with the convention "values are UTC". Comparing those to
    ``datetime.now(timezone.utc)`` raises ``TypeError``; this helper
    consolidates the coercion.

    Returns ``None`` unchanged. Already-aware datetimes pass through
    untouched (no unnecessary allocation).
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
