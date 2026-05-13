"""Startup validation, service summary logging, and session state."""

import sys

from src.config.settings import settings
from src.utils.logger import logger
from src.utils.validators import ConfigValidator


class _SessionState:
    """Mutable session state shared between main_async and background loops."""

    def __init__(self):
        self.start_time: float | None = None
        self.posts_sent: int = 0
        self.shutdown_in_progress: bool = False


# Singleton instance — import this to read/write session state.
session_state = _SessionState()


def validate_and_log_startup() -> None:
    """Validate configuration and check database schema version.

    Exits the process if configuration is invalid.
    """
    logger.info("=" * 60)
    logger.info("Storydump - Instagram Story Automation System")
    logger.info("=" * 60)

    is_valid, errors = ConfigValidator.validate_all()

    if not is_valid:
        logger.error("Configuration validation failed:")
        for error in errors:
            logger.error(f"  - {error}")
        sys.exit(1)

    logger.info("\u2713 Configuration validated successfully")
    ConfigValidator.check_schema_version()


def log_service_summary() -> None:
    """Log a summary of active services and configuration after startup.

    Per-chat values (posts/day, posting hours, dry run, IG API, media
    sync) now live on chat_settings \u2014 they vary per tenant and aren't
    meaningful to print here. Only system-wide knobs are logged.
    """
    logger.info("\u2713 All services started (JIT scheduler)")
    logger.info(
        f"\u2713 Media sync loop: every {settings.MEDIA_SYNC_INTERVAL_SECONDS}s "
        "(per-chat enable in chat_settings.media_sync_enabled)"
    )
    logger.info("=" * 60)
