"""Main application entry point - runs scheduler + Telegram bot."""

import asyncio
import os
import signal
import sys
from time import time

from src.services.core.loops.guarded import guarded
from src.services.core.loops.lifecycle import (
    log_service_summary,
    session_state,
    validate_and_log_startup,
)
from src.services.core.loops.scheduler_loop import run_scheduler_loop
from src.services.core.loops.lock_cleanup_loop import cleanup_locks_loop
from src.services.core.loops.cloud_cleanup_loop import cleanup_cloud_storage_loop
from src.services.core.loops.transaction_cleanup_loop import transaction_cleanup_loop
from src.services.core.loops.media_sync_loop import media_sync_loop
from src.utils.logger import logger

_HEALTH_RESPONSE = (
    b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 2\r\n\r\nok"
)


async def _health_check_server():
    """Minimal HTTP server so Railway's health check gets a 200 on /health."""
    port = int(os.environ.get("PORT", 8080))

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            await reader.readline()  # consume request line
            writer.write(_HEALTH_RESPONSE)
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(handle, "0.0.0.0", port)
    logger.info(f"Health check server listening on port {port}")
    async with server:
        await server.serve_forever()


async def main_async():
    """Main async application entry point."""
    validate_and_log_startup()

    # Initialize services
    from src.services.core.settings_service import SettingsService
    from src.services.core.posting import PostingService
    from src.services.core.scheduler import SchedulerService
    from src.services.core.telegram_service import TelegramService
    from src.services.core.media_lock import MediaLockService
    from src.services.core.media_sync import MediaSyncService

    scheduler_service = SchedulerService()
    posting_service = PostingService()
    telegram_service = TelegramService()
    lock_service = MediaLockService()
    settings_service = SettingsService()

    # Media sync runs unconditionally — the loop iterates per-chat and skips
    # chats with media_sync_enabled=False. No env gate.
    sync_service = MediaSyncService()

    await telegram_service.initialize()
    scheduler_service.telegram_service = telegram_service

    # Send startup notification
    session_state.start_time = time()
    await telegram_service.send_startup_notification()

    # Create tasks
    all_services = [
        scheduler_service,
        posting_service,
        telegram_service,
        lock_service,
        settings_service,
    ]
    bot = telegram_service.bot

    tasks = [
        asyncio.create_task(
            guarded(
                "scheduler",
                run_scheduler_loop(
                    scheduler_service, posting_service, settings_service
                ),
                bot=bot,
            )
        ),
        asyncio.create_task(
            guarded("lock_cleanup", cleanup_locks_loop(lock_service), bot=bot)
        ),
        asyncio.create_task(telegram_service.start_polling()),
        asyncio.create_task(_health_check_server()),
    ]

    # Add cloud storage cleanup loop if Cloudinary is configured
    from src.services.integrations.cloud_storage import CloudStorageService

    cloud_service = CloudStorageService()
    if cloud_service.is_configured():
        all_services.append(cloud_service)
        tasks.append(
            asyncio.create_task(
                guarded(
                    "cloud_cleanup",
                    cleanup_cloud_storage_loop(cloud_service),
                    bot=bot,
                )
            )
        )

    # Add media sync loop if enabled
    if sync_service:
        all_services.append(sync_service)
        tasks.append(
            asyncio.create_task(
                guarded(
                    "media_sync",
                    media_sync_loop(
                        sync_service,
                        settings_service=settings_service,
                        telegram_service=telegram_service,
                    ),
                    bot=bot,
                )
            )
        )

    tasks.append(
        asyncio.create_task(
            guarded(
                "transaction_cleanup",
                transaction_cleanup_loop(all_services),
                bot=bot,
            )
        )
    )

    log_service_summary()

    # Setup signal handlers for graceful shutdown
    async def shutdown_handler(sig):
        """Handle shutdown signals gracefully."""
        # Guard against duplicate signals
        if session_state.shutdown_in_progress:
            logger.info(f"Shutdown already in progress, ignoring {sig.name} signal")
            return
        session_state.shutdown_in_progress = True

        logger.info(f"Received {sig.name} signal...")

        # Calculate uptime
        uptime = (
            int(time() - session_state.start_time) if session_state.start_time else 0
        )

        # Send shutdown notification
        try:
            await telegram_service.send_shutdown_notification(
                uptime_seconds=uptime, posts_sent=session_state.posts_sent
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

        logger.info("\u2713 Shutdown complete")

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
