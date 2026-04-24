"""Media sync loop — reconciles provider files with database on schedule."""

import asyncio

from src.config.settings import settings
from src.services.core.loops.heartbeat import record_heartbeat
from src.services.core.media_sync import MediaSyncService
from src.utils.logger import logger


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
        record_heartbeat("media_sync")
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
                    f"\U0001f534 *Media Sync Failed*\n\n"
                    f"Error: `{type(e).__name__}`\n"
                    f"Details: {str(e)[:200]}\n\n"
                    f"Consecutive failures: {consecutive_failures}\n"
                    f"Sync will retry in {settings.MEDIA_SYNC_INTERVAL_SECONDS}s.",
                )

        finally:
            try:
                sync_service.cleanup_transactions()
            except Exception as cleanup_err:
                logger.warning(
                    f"cleanup_transactions failed for MediaSyncService: {cleanup_err}"
                )
            if settings_service:
                try:
                    settings_service.cleanup_transactions()
                except Exception as cleanup_err:
                    logger.warning(
                        f"cleanup_transactions failed for SettingsService: {cleanup_err}"
                    )

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
