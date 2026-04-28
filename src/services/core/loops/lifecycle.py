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
    """Log a summary of active services and configuration after startup."""
    logger.info("\u2713 All services started (JIT scheduler)")
    logger.info(
        f"\u2713 Phase: {'Hybrid (API + Telegram)' if settings.ENABLE_INSTAGRAM_API else 'Telegram-Only'}"
    )
    logger.info(f"\u2713 Dry run mode: {settings.DRY_RUN_MODE}")
    if settings.MEDIA_SYNC_ENABLED:
        logger.info(
            f"\u2713 Media sync: {settings.MEDIA_SOURCE_TYPE} "
            f"(every {settings.MEDIA_SYNC_INTERVAL_SECONDS}s)"
        )
    else:
        logger.info("\u2713 Media sync: disabled")
    logger.info(f"\u2713 Posts per day: {settings.POSTS_PER_DAY}")
    logger.info(
        f"\u2713 Posting hours: {settings.POSTING_HOURS_START}-{settings.POSTING_HOURS_END} UTC"
    )
    logger.info("=" * 60)
