"""Input validation and configuration validation."""

import re
from pathlib import Path
from typing import List, Optional, Tuple

from src.config.settings import settings
from src.utils.logger import logger

# Derive expected schema version from migration filenames (NNN_description.sql).
MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "migrations"


def _latest_migration_version() -> Optional[int]:
    """Return the highest migration version number from scripts/migrations/."""
    if not MIGRATIONS_DIR.is_dir():
        return None
    versions = []
    for f in MIGRATIONS_DIR.iterdir():
        m = re.match(r"^(\d+)_", f.name)
        if m:
            versions.append(int(m.group(1)))
    return max(versions) if versions else None


class ConfigValidator:
    """Validate configuration on startup."""

    @staticmethod
    def validate_all() -> Tuple[bool, List[str]]:
        """
        Validate all configuration settings.

        Returns:
            (is_valid, error_messages)
        """
        errors = []

        # Validate posting schedule
        if settings.POSTS_PER_DAY < 1 or settings.POSTS_PER_DAY > 10:
            errors.append("POSTS_PER_DAY must be between 1 and 10")

        # Handle wrap-around posting hours (e.g., 22-2 means 22:00 to 02:00 next day)
        if settings.POSTING_HOURS_START < 0 or settings.POSTING_HOURS_START > 23:
            errors.append("POSTING_HOURS_START must be between 0-23 (UTC)")

        if settings.POSTING_HOURS_END < 0 or settings.POSTING_HOURS_END > 23:
            errors.append("POSTING_HOURS_END must be between 0-23 (UTC)")

        # Validate repost TTL
        if settings.REPOST_TTL_DAYS < 1:
            errors.append("REPOST_TTL_DAYS must be at least 1")

        # Validate Telegram config
        if not settings.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN is required")
        else:
            # Probe Telegram for token validity. Without this, python-telegram-bot's
            # lazy validation means a rotated/revoked token only surfaces on the
            # first polling attempt, often masked as a generic outage. We saw
            # exactly this in production: token rotated externally, env not
            # updated, "app feels down" for hours. A 1s HTTP call at boot
            # surfaces it within seconds.
            token_error = ConfigValidator._check_telegram_token(
                settings.TELEGRAM_BOT_TOKEN
            )
            if token_error:
                errors.append(token_error)

        if not settings.TELEGRAM_CHANNEL_ID:
            errors.append("TELEGRAM_CHANNEL_ID is required")

        if not settings.ADMIN_TELEGRAM_CHAT_ID:
            errors.append("ADMIN_TELEGRAM_CHAT_ID is required")

        # Validate Instagram config (if API enabled)
        if settings.ENABLE_INSTAGRAM_API:
            if not settings.CLOUDINARY_CLOUD_NAME:
                errors.append(
                    "Cloudinary config required when ENABLE_INSTAGRAM_API=true"
                )

        # Validate database config
        if not settings.DB_NAME:
            errors.append("DB_NAME is required")

        # Validate paths — auto-create MEDIA_DIR for cloud deployments
        media_dir = Path(settings.MEDIA_DIR)
        if not media_dir.exists():
            try:
                media_dir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                errors.append(
                    f"MEDIA_DIR does not exist and could not be created: "
                    f"{settings.MEDIA_DIR} ({e})"
                )

        is_valid = len(errors) == 0
        return is_valid, errors

    @staticmethod
    def _check_telegram_token(token: str) -> Optional[str]:
        """Call Telegram's getMe to verify the token is accepted.

        Returns an error string if the token is rejected; None if accepted
        or if the check itself is inconclusive (network error, etc. — we
        don't want to block startup on a transient network blip).
        """
        import requests

        try:
            resp = requests.get(
                f"https://api.telegram.org/bot{token}/getMe", timeout=3.0
            )
        except requests.RequestException as exc:
            logger.warning(
                f"Telegram getMe check failed inconclusively ({type(exc).__name__}); "
                "continuing startup. Token validity will be checked again on first poll."
            )
            return None

        if resp.status_code == 200:
            return None
        if resp.status_code == 401:
            return (
                "TELEGRAM_BOT_TOKEN rejected by Telegram (HTTP 401). "
                "Token is invalid or has been revoked — rotate via @BotFather "
                "and update the env var."
            )
        return (
            f"Telegram getMe returned HTTP {resp.status_code}; "
            "token may be invalid or Telegram is degraded."
        )

    @staticmethod
    def check_schema_version() -> None:
        """Check that the database schema matches the latest migration.

        Queries the schema_version table and compares against migration files
        in scripts/migrations/. Logs a warning on mismatch but does not block
        startup — the operator is expected to apply migrations manually.
        """
        from sqlalchemy import text

        from src.config.database import engine

        expected = _latest_migration_version()
        if expected is None:
            logger.warning("Schema version check skipped — no migration files found")
            return

        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text("SELECT MAX(version) FROM schema_version")
                ).scalar()
                db_version = int(row) if row is not None else 0
        except Exception as exc:  # noqa: BLE001 — schema check is advisory, swallow all errors
            logger.warning(f"Schema version check failed: {exc}")
            return

        if db_version < expected:
            logger.warning(
                f"Database schema is behind: DB at version {db_version}, "
                f"latest migration is {expected}. "
                f"Run pending migrations ({db_version + 1}–{expected}) before "
                f"relying on new features."
            )
        elif db_version > expected:
            logger.warning(
                f"Database schema ({db_version}) is ahead of migration files "
                f"({expected}) — are migration files missing from this deploy?"
            )
        else:
            logger.info(f"✓ Database schema is up to date (version {db_version})")
