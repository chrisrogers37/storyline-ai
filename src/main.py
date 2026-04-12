"""Main application entry point - runs scheduler + Telegram bot."""

import asyncio
import signal
import sys
from time import time

from typing import Coroutine

from src.config.settings import settings
from src.utils.logger import logger
from src.utils.validators import ConfigValidator
from src.services.core.posting import PostingService
from src.services.core.scheduler import SchedulerService
from src.services.core.telegram_service import TelegramService
from src.services.core.media_lock import MediaLockService
from src.services.core.media_sync import MediaSyncService
from src.repositories.queue_repository import QueueRepository
from src.repositories.service_run_repository import ServiceRunRepository
from src.exceptions.google_drive import GoogleDriveAuthError

# Track session statistics
session_start_time = None
session_posts_sent = 0
shutdown_in_progress = False

# Retention policy: delete service_runs older than 7 days
SERVICE_RUNS_RETENTION_DAYS = 7
# Run retention once per hour (60 ticks at 1-minute intervals)
RETENTION_INTERVAL_TICKS = 60


async def _guarded(name: str, coro: Coroutine) -> None:
    """Run a coroutine and log (not propagate) unhandled exceptions.

    Prevents a crash in one background loop from killing the whole worker
    via asyncio.gather().
    """
    try:
        await coro
    except asyncio.CancelledError:
        raise  # let shutdown propagate
    except Exception:
        logger.critical(f"Background task '{name}' crashed", exc_info=True)


async def run_scheduler_loop(
    scheduler_service: SchedulerService,
    posting_service: PostingService,
    settings_service=None,
):
    """Run JIT scheduler loop — check for due slots every minute.

    For each active tenant, calls scheduler_service.process_slot() which
    checks is_slot_due() and, if a slot is due, selects media and sends
    to Telegram.  No service_run is created for no-op ticks.

    Also runs hourly retention cleanup on the service_runs table.

    Args:
        scheduler_service: SchedulerService instance (handles JIT logic)
        posting_service: PostingService instance (handles GDrive alerts)
        settings_service: SettingsService for tenant discovery.
            If None, falls back to global single-tenant behavior.
    """
    global session_posts_sent
    logger.info("Starting JIT scheduler loop...")

    queue_repo = QueueRepository()
    service_run_repo = ServiceRunRepository()
    retention_tick_counter = 0

    while True:
        try:
            # Discard queue items abandoned in 'processing' for over 24h.
            # Items enter 'processing' when sent to Telegram — they stay
            # there until a user clicks a button. Items older than 24h
            # are stale notifications that will never be acted on.
            discarded = queue_repo.discard_abandoned_processing()
            if discarded > 0:
                logger.warning(
                    f"Discarded {discarded} abandoned processing item(s) (>24h old)"
                )

            if settings_service:
                active_chats = settings_service.get_all_active_chats()
            else:
                active_chats = []

            if active_chats:
                for chat in active_chats:
                    chat_id = chat.telegram_chat_id
                    try:
                        result = await scheduler_service.process_slot(
                            telegram_chat_id=chat_id
                        )

                        if result.get("posted"):
                            session_posts_sent += 1
                            logger.info(
                                f"[chat={chat_id}] "
                                f"Posted: {result.get('media_file', '?')} "
                                f"[{result.get('category', '?')}]"
                            )

                    except GoogleDriveAuthError:
                        logger.error(
                            f"Google Drive auth error for chat {chat_id}",
                            exc_info=True,
                        )
                        await posting_service.send_gdrive_auth_alert(chat_id)

                    except Exception as e:
                        logger.error(
                            f"Error processing chat {chat_id}: {e}",
                            exc_info=True,
                        )
                # No paused-chat reschedule needed — JIT skips paused tenants

        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}", exc_info=True)
        finally:
            scheduler_service.cleanup_transactions()
            posting_service.cleanup_transactions()

        # Hourly retention: purge old service_runs to prevent table bloat
        retention_tick_counter += 1
        if retention_tick_counter >= RETENTION_INTERVAL_TICKS:
            retention_tick_counter = 0
            try:
                deleted = service_run_repo.delete_older_than(
                    SERVICE_RUNS_RETENTION_DAYS
                )
                if deleted > 0:
                    logger.info(
                        f"Retention: deleted {deleted} service_runs older than "
                        f"{SERVICE_RUNS_RETENTION_DAYS} days"
                    )
            except Exception as e:
                logger.warning(f"Service runs retention cleanup failed: {e}")
            finally:
                service_run_repo.end_read_transaction()

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


async def cleanup_cloud_storage_loop(cloud_service):
    """Remove orphaned Cloudinary uploads that outlived their retention window.

    Runs hourly as a safety net — normal flow deletes immediately after posting.
    """
    from src.repositories.media_repository import MediaRepository
    from src.services.integrations.cloud_storage import CLOUD_UPLOAD_FOLDER

    media_repo = MediaRepository()
    logger.info("Starting cloud storage cleanup loop...")

    while True:
        try:
            await asyncio.sleep(3600)

            cloud_count = cloud_service.cleanup_expired(folder=CLOUD_UPLOAD_FOLDER)
            db_count = media_repo.clear_stale_cloud_info(
                retention_hours=settings.CLOUD_UPLOAD_RETENTION_HOURS
            )

            if cloud_count > 0 or db_count > 0:
                logger.info(
                    f"Cloud storage cleanup: {cloud_count} Cloudinary resources deleted, "
                    f"{db_count} stale DB references cleared"
                )

        except Exception as e:
            logger.error(f"Error in cloud storage cleanup loop: {e}", exc_info=True)
        finally:
            cloud_service.cleanup_transactions()
            media_repo.end_read_transaction()


async def transaction_cleanup_loop(services: list):
    """
    Periodically clean up idle database transactions from all services.

    This prevents "idle in transaction" connections from piling up,
    which can cause the bot to freeze when handling callbacks.

    Also logs connection pool utilization every cycle so that pool
    exhaustion is visible in logs before it causes freezes.
    """
    from src.utils.resilience import log_pool_status

    while True:
        await asyncio.sleep(30)  # Run every 30 seconds

        # Log pool status for monitoring
        log_pool_status()

        for service in services:
            try:
                service.cleanup_transactions()
            except Exception as e:
                logger.warning(
                    f"Transaction cleanup failed for {type(service).__name__}: "
                    f"{type(e).__name__}: {e}"
                )


async def media_sync_loop(
    sync_service: MediaSyncService,
    settings_service=None,
    telegram_service=None,
):
    """Run media sync loop - reconcile provider files with database on schedule.

    Iterates over all tenants with media_sync_enabled=True and syncs each
    independently. Falls back to global env var behavior if no tenants
    have sync enabled.

    Args:
        sync_service: The MediaSyncService instance
        settings_service: SettingsService for tenant discovery
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
            # Multi-tenant: sync each tenant with media_sync_enabled=True
            sync_enabled_chats = []
            if settings_service:
                sync_enabled_chats = settings_service.get_all_sync_enabled_chats()

            if sync_enabled_chats:
                for chat in sync_enabled_chats:
                    try:
                        result = sync_service.sync(
                            telegram_chat_id=chat.telegram_chat_id,
                            triggered_by="scheduler",
                        )

                        if result.total_processed > 0 or result.errors > 0:
                            logger.info(
                                f"[chat={chat.telegram_chat_id}] "
                                f"Media sync completed: "
                                f"{result.new} new, {result.updated} updated, "
                                f"{result.deactivated} deactivated, "
                                f"{result.reactivated} reactivated, "
                                f"{result.errors} errors"
                            )
                    except Exception as e:
                        logger.error(
                            f"[chat={chat.telegram_chat_id}] Media sync error: {e}",
                            exc_info=True,
                        )
            else:
                # Legacy fallback: single-tenant using global env vars
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
            consecutive_failures = 0
            last_error_notified = None

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
            if settings_service:
                settings_service.cleanup_transactions()

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

    scheduler_service = SchedulerService()
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

    # Inject telegram_service into scheduler for sending notifications
    scheduler_service.telegram_service = telegram_service

    # Send startup notification
    session_start_time = time()
    await telegram_service.send_startup_notification()

    # Create tasks
    all_services = [
        scheduler_service,
        posting_service,
        telegram_service,
        lock_service,
        settings_service,
    ]
    tasks = [
        asyncio.create_task(
            _guarded(
                "scheduler",
                run_scheduler_loop(
                    scheduler_service, posting_service, settings_service
                ),
            )
        ),
        asyncio.create_task(_guarded("lock_cleanup", cleanup_locks_loop(lock_service))),
        asyncio.create_task(telegram_service.start_polling()),
    ]

    # Add cloud storage cleanup loop if Cloudinary is configured
    from src.services.integrations.cloud_storage import CloudStorageService

    cloud_service = CloudStorageService()
    if cloud_service.is_configured():
        all_services.append(cloud_service)
        tasks.append(
            asyncio.create_task(
                _guarded("cloud_cleanup", cleanup_cloud_storage_loop(cloud_service))
            )
        )

    # Add media sync loop if enabled
    if sync_service:
        all_services.append(sync_service)
        tasks.append(
            asyncio.create_task(
                _guarded(
                    "media_sync",
                    media_sync_loop(
                        sync_service,
                        settings_service=settings_service,
                        telegram_service=telegram_service,
                    ),
                )
            )
        )

    tasks.append(
        asyncio.create_task(
            _guarded("transaction_cleanup", transaction_cleanup_loop(all_services))
        )
    )

    logger.info("✓ All services started (JIT scheduler)")
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
