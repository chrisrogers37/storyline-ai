"""Main application entry point - runs scheduler + Telegram bot."""
import asyncio
import sys
from datetime import datetime

from src.config.settings import settings
from src.utils.logger import logger
from src.utils.validators import ConfigValidator
from src.services.core.posting import PostingService
from src.services.core.telegram_service import TelegramService
from src.services.core.media_lock import MediaLockService


async def run_scheduler_loop(posting_service: PostingService):
    """Run scheduler loop - check for pending posts every minute."""
    logger.info("Starting scheduler loop...")

    while True:
        try:
            # Process pending posts
            result = await posting_service.process_pending_posts()

            if result["processed"] > 0:
                logger.info(
                    f"Processed {result['processed']} posts: "
                    f"{result['telegram']} to Telegram, "
                    f"{result['failed']} failed"
                )

        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}", exc_info=True)

        # Wait 1 minute before next check
        await asyncio.sleep(60)


async def cleanup_locks_loop(lock_service: MediaLockService):
    """Run cleanup loop - remove expired locks every hour."""
    logger.info("Starting cleanup loop...")

    while True:
        try:
            # Wait 1 hour
            await asyncio.sleep(3600)

            # Cleanup expired locks
            count = lock_service.cleanup_expired_locks()

            if count > 0:
                logger.info(f"Cleaned up {count} expired locks")

        except Exception as e:
            logger.error(f"Error in cleanup loop: {e}", exc_info=True)


async def main_async():
    """Main async application entry point."""
    logger.info("=" * 60)
    logger.info("Storyline AI - Instagram Story Automation System")
    logger.info("=" * 60)

    # Validate configuration
    is_valid, errors = ConfigValidator.validate_all()

    if not is_valid:
        logger.error("Configuration validation failed:")
        for error in errors:
            logger.error(f"  - {error}")
        sys.exit(1)

    logger.info("✓ Configuration validated successfully")

    # Initialize services
    posting_service = PostingService()
    telegram_service = TelegramService()
    lock_service = MediaLockService()

    # Initialize Telegram bot
    await telegram_service.initialize()

    # Create tasks
    tasks = [
        asyncio.create_task(run_scheduler_loop(posting_service)),
        asyncio.create_task(cleanup_locks_loop(lock_service)),
        asyncio.create_task(telegram_service.start_polling()),
    ]

    logger.info("✓ All services started")
    logger.info(f"✓ Phase: {'Hybrid (API + Telegram)' if settings.ENABLE_INSTAGRAM_API else 'Telegram-Only'}")
    logger.info(f"✓ Dry run mode: {settings.DRY_RUN_MODE}")
    logger.info(f"✓ Posts per day: {settings.POSTS_PER_DAY}")
    logger.info(f"✓ Posting hours: {settings.POSTING_HOURS_START}-{settings.POSTING_HOURS_END} UTC")
    logger.info("=" * 60)

    # Wait for all tasks
    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        logger.info("Received shutdown signal...")

        # Cleanup
        await telegram_service.stop_polling()

        logger.info("✓ Shutdown complete")


def main():
    """Main entry point."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
