"""Main application entry point - runs scheduler + Telegram bot."""

import asyncio
import signal
import sys
from time import time

from src.config.settings import settings
from src.utils.logger import logger
from src.utils.validators import ConfigValidator
from src.services.core.posting import PostingService
from src.services.core.telegram_service import TelegramService
from src.services.core.media_lock import MediaLockService
from src.services.core.media_sync import MediaSyncService

# Track session statistics
session_start_time = None
session_posts_sent = 0
shutdown_in_progress = False


async def run_scheduler_loop(
    posting_service: PostingService,
    settings_service=None,
):
    """Run scheduler loop - check for pending posts every minute.

    Iterates over all active (non-paused) tenants and processes each
    tenant's pending posts independently.

    Args:
        posting_service: PostingService instance
        settings_service: SettingsService instance for tenant discovery.
            If None, falls back to global single-tenant behavior.
    """
    global session_posts_sent
    logger.info("Starting scheduler loop...")

    while True:
        try:
            if settings_service:
                active_chats = settings_service.get_all_active_chats()
            else:
                active_chats = []

            if active_chats:
                # Multi-tenant mode: process each tenant's queue
                for chat in active_chats:
                    try:
                        result = await posting_service.process_pending_posts(
                            telegram_chat_id=chat.telegram_chat_id
                        )

                        if result["processed"] > 0:
                            session_posts_sent += result["telegram"]
                            logger.info(
                                f"[chat={chat.telegram_chat_id}] "
                                f"Processed {result['processed']} posts: "
                                f"{result['telegram']} to Telegram, "
                                f"{result['failed']} failed"
                            )
                    except Exception as e:
                        logger.error(
                            f"Error processing chat {chat.telegram_chat_id}: {e}",
                            exc_info=True,
                        )
            else:
                # Legacy single-tenant fallback
                result = await posting_service.process_pending_posts()

                if result["processed"] > 0:
                    session_posts_sent += result["telegram"]
                    logger.info(
                        f"Processed {result['processed']} posts: "
                        f"{result['telegram']} to Telegram, "
                        f"{result['failed']} failed"
                    )

        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}", exc_info=True)
        finally:
            posting_service.cleanup_transactions()

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
        finally:
            # Clean up open transactions
            lock_service.cleanup_transactions()


async def transaction_cleanup_loop(services: list):
    """
    Periodically clean up idle database transactions from all services.

    This prevents "idle in transaction" connections from piling up,
    which can cause the bot to freeze when handling callbacks.
    """
    while True:
        await asyncio.sleep(30)  # Run every 30 seconds
        for service in services:
            try:
                service.cleanup_transactions()
            except Exception:
                pass  # Suppress cleanup errors


async def media_sync_loop(
    sync_service: MediaSyncService,
    telegram_service=None,
):
    """Run media sync loop - reconcile provider files with database on schedule.

    Args:
        sync_service: The MediaSyncService instance
        telegram_service: Optional TelegramService for error notifications
    """
    logger.info(
        f"Starting media sync loop "
        f"(interval: {settings.MEDIA_SYNC_INTERVAL_SECONDS}s, "
        f"source: {settings.MEDIA_SOURCE_TYPE})"
    )

    # Track consecutive failures for notification suppression
    consecutive_failures = 0
    last_error_notified = None

    while True:
        try:
            result = sync_service.sync(triggered_by="scheduler")

            if result.total_processed > 0 or result.errors > 0:
                logger.info(
                    f"Media sync completed: "
                    f"{result.new} new, {result.updated} updated, "
                    f"{result.deactivated} deactivated, "
                    f"{result.reactivated} reactivated, "
                    f"{result.errors} errors"
                )

            # Reset failure counter on success
            if result.errors == 0:
                consecutive_failures = 0
                last_error_notified = None

            # Notify on sync errors (first occurrence or every 10th consecutive)
            elif result.errors > 0 and telegram_service:
                consecutive_failures += 1
                error_summary = "; ".join(result.error_details[:3])

                if consecutive_failures == 1 or consecutive_failures % 10 == 0:
                    await _notify_sync_error(
                        telegram_service,
                        f"⚠️ *Media Sync Errors*\n\n"
                        f"Sync completed with {result.errors} error(s).\n"
                        f"Consecutive failures: {consecutive_failures}\n\n"
                        f"Details: {error_summary[:300]}",
                    )

        except Exception as e:
            logger.error(f"Error in media sync loop: {e}", exc_info=True)

            consecutive_failures += 1
            error_str = str(e)

            if telegram_service and (
                consecutive_failures == 1 or error_str != last_error_notified
            ):
                last_error_notified = error_str
                await _notify_sync_error(
                    telegram_service,
                    f"🔴 *Media Sync Failed*\n\n"
                    f"Error: `{type(e).__name__}`\n"
                    f"Details: {str(e)[:200]}\n\n"
                    f"Consecutive failures: {consecutive_failures}\n"
                    f"Sync will retry in {settings.MEDIA_SYNC_INTERVAL_SECONDS}s.",
                )

        finally:
            sync_service.cleanup_transactions()

        await asyncio.sleep(settings.MEDIA_SYNC_INTERVAL_SECONDS)


async def _notify_sync_error(telegram_service, message: str):
    """Send sync error notification to admin channel if verbose notifications enabled.

    Consolidated helper — checks verbose setting, sends message, suppresses errors.
    """
    try:
        chat_settings = telegram_service.settings_service.get_settings(
            telegram_service.channel_id
        )
        if not chat_settings.show_verbose_notifications:
            return

        await telegram_service.bot.send_message(
            chat_id=telegram_service.channel_id,
            text=message,
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.warning(f"Failed to send sync error notification: {e}")


async def main_async():
    """Main async application entry point."""
    global session_start_time

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
    from src.services.core.settings_service import SettingsService

    posting_service = PostingService()
    telegram_service = TelegramService()
    lock_service = MediaLockService()
    settings_service = SettingsService()

    # Initialize media sync (if enabled)
    sync_service = None
    if settings.MEDIA_SYNC_ENABLED:
        sync_service = MediaSyncService()

    # Initialize Telegram bot
    await telegram_service.initialize()

    # Send startup notification
    session_start_time = time()
    await telegram_service.send_startup_notification()

    # Create tasks
    all_services = [posting_service, telegram_service, lock_service]
    tasks = [
        asyncio.create_task(run_scheduler_loop(posting_service, settings_service)),
        asyncio.create_task(cleanup_locks_loop(lock_service)),
        asyncio.create_task(telegram_service.start_polling()),
    ]

    # Add media sync loop if enabled
    if sync_service:
        all_services.append(sync_service)
        tasks.append(
            asyncio.create_task(
                media_sync_loop(sync_service, telegram_service=telegram_service)
            )
        )

    tasks.append(asyncio.create_task(transaction_cleanup_loop(all_services)))

    logger.info("✓ All services started")
    logger.info(
        f"✓ Phase: {'Hybrid (API + Telegram)' if settings.ENABLE_INSTAGRAM_API else 'Telegram-Only'}"
    )
    logger.info(f"✓ Dry run mode: {settings.DRY_RUN_MODE}")
    if settings.MEDIA_SYNC_ENABLED:
        logger.info(
            f"✓ Media sync: {settings.MEDIA_SOURCE_TYPE} "
            f"(every {settings.MEDIA_SYNC_INTERVAL_SECONDS}s)"
        )
    else:
        logger.info("✓ Media sync: disabled")
    logger.info(f"✓ Posts per day: {settings.POSTS_PER_DAY}")
    logger.info(
        f"✓ Posting hours: {settings.POSTING_HOURS_START}-{settings.POSTING_HOURS_END} UTC"
    )
    logger.info("=" * 60)

    # Setup signal handlers for graceful shutdown
    async def shutdown_handler(sig):
        """Handle shutdown signals gracefully."""
        global shutdown_in_progress

        # Guard against duplicate signals
        if shutdown_in_progress:
            logger.info(f"Shutdown already in progress, ignoring {sig.name} signal")
            return
        shutdown_in_progress = True

        logger.info(f"Received {sig.name} signal...")

        # Calculate uptime
        uptime = int(time() - session_start_time) if session_start_time else 0

        # Send shutdown notification
        try:
            await telegram_service.send_shutdown_notification(
                uptime_seconds=uptime, posts_sent=session_posts_sent
            )
        except Exception as e:
            logger.warning(f"Failed to send shutdown notification: {e}")

        # Cleanup
        try:
            await telegram_service.stop_polling()
        except Exception as e:
            logger.warning(f"Error stopping Telegram polling: {e}")

        # Cancel all tasks
        for task in tasks:
            task.cancel()

        logger.info("✓ Shutdown complete")

    # Register signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig, lambda s=sig: asyncio.create_task(shutdown_handler(s))
        )

    # Wait for all tasks
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        # Tasks were cancelled during shutdown
        pass
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt...")
        await shutdown_handler(signal.SIGINT)


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
