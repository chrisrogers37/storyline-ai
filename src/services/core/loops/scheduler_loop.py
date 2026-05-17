"""JIT scheduler loop — checks for due posting slots every minute.

Also runs hourly retention cleanup, pool health checks, and token
health checks as sub-tasks within the scheduler tick cycle.
"""

import asyncio
from time import time

from src.exceptions.google_drive import GoogleDriveAuthError
from src.repositories.queue_repository import QueueRepository
from src.repositories.service_run_repository import ServiceRunRepository
from src.services.core.health_check import HealthCheckService
from src.services.core.loops.heartbeat import record_heartbeat
from src.services.core.loops.lifecycle import session_state
from src.services.core.posting import PostingService
from src.services.core.scheduler import SchedulerService
from src.utils.logger import logger

# Retention policy: delete service_runs older than 7 days
SERVICE_RUNS_RETENTION_DAYS = 7
# Run retention once per hour (60 ticks at 1-minute intervals)
RETENTION_INTERVAL_TICKS = 60
# Pool depletion check interval (hourly, same cadence as retention)
POOL_CHECK_INTERVAL_TICKS = 60
# Throttle pool alerts to once per 24h per chat
POOL_ALERT_COOLDOWN_SECONDS = 86400


async def _scheduler_tick(
    scheduler_service: SchedulerService,
    posting_service: PostingService,
    settings_service,
    queue_repo: QueueRepository,
    *,
    first_tick: bool = False,
) -> list:
    """Process one scheduler tick: discard stale queue items, process due slots.

    Args:
        first_tick: True on the first tick after worker startup.
            Passed to process_slot so catch-up posts reset to now
            instead of advancing gradually.

    Returns the list of active chats discovered this tick (used by health checks).
    """
    # Discard queue items abandoned in 'processing' for over 24h.
    # queue_repo is a standalone repository (not owned by a BaseService), so
    # the outer loop's cleanup_transactions() doesn't roll it back on error.
    # Without this guard a single failed query would leave the session in a
    # broken transaction and every subsequent tick would PendingRollbackError
    # for the lifetime of the worker — observed in production.
    try:
        discarded = queue_repo.discard_abandoned_processing()
    except Exception:
        queue_repo.rollback()
        raise

    if discarded > 0:
        logger.warning(f"Discarded {discarded} abandoned processing item(s) (>24h old)")

    if settings_service:
        active_chats = settings_service.get_all_active_chats()
    else:
        active_chats = []

    if not active_chats:
        # Throttle to once per 10 minutes (every 10th tick) to avoid log spam
        _no_active_chats_tick_count = (
            getattr(_scheduler_tick, "_no_active_ticks", 0) + 1
        )
        _scheduler_tick._no_active_ticks = _no_active_chats_tick_count
        if _no_active_chats_tick_count == 1 or _no_active_chats_tick_count % 10 == 0:
            logger.warning(
                "Scheduler tick: no active chats found "
                "(check onboarding_completed / active_instagram_account_id)"
            )
    else:
        _scheduler_tick._no_active_ticks = 0

    if active_chats:
        for chat in active_chats:
            chat_id = chat.telegram_chat_id
            try:
                result = await scheduler_service.process_slot(
                    telegram_chat_id=chat_id, first_tick=first_tick
                )

                if result.get("posted"):
                    session_state.posts_sent += 1
                    logger.info(
                        f"[chat={chat_id}] "
                        f"Posted: {result.get('media_file', '?')} "
                        f"[{result.get('category', '?')}]"
                    )

                    # Send quiet notification for auto-approved items
                    if (
                        result.get("auto_approved")
                        and scheduler_service.telegram_service
                    ):
                        try:
                            bot = scheduler_service.telegram_service.application.bot
                            await bot.send_message(
                                chat_id=chat_id,
                                text=(
                                    f"\u2705 Auto-approved: "
                                    f"{result.get('media_file', '?')} "
                                    f"[{result.get('category', '?')}]"
                                ),
                            )
                        except Exception:
                            pass

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

    return active_chats


async def _retention_cleanup_tick(
    service_run_repo: ServiceRunRepository,
) -> None:
    """Purge old service_runs to prevent table bloat."""
    try:
        deleted = service_run_repo.delete_older_than(SERVICE_RUNS_RETENTION_DAYS)
        if deleted > 0:
            logger.info(
                f"Retention: deleted {deleted} service_runs older than "
                f"{SERVICE_RUNS_RETENTION_DAYS} days"
            )
    except Exception as e:
        logger.warning(f"Service runs retention cleanup failed: {e}")
    finally:
        try:
            service_run_repo.end_read_transaction()
        except Exception as cleanup_err:
            logger.warning(
                f"cleanup_transactions failed for ServiceRunRepository: {cleanup_err}"
            )


async def _pool_health_tick(
    active_chats: list,
    scheduler_service: SchedulerService,
    health_check_service: HealthCheckService,
    pool_alert_last_sent: dict[int, float],
) -> None:
    """Check media pool depletion and send alerts for low categories."""
    try:
        if active_chats and scheduler_service.telegram_service:
            now = time()
            bot = scheduler_service.telegram_service.application.bot
            # Prune stale entries for chats no longer active
            active_ids = {c.telegram_chat_id for c in active_chats}
            for stale_id in set(pool_alert_last_sent) - active_ids:
                del pool_alert_last_sent[stale_id]

            for chat in active_chats:
                chat_id = chat.telegram_chat_id
                if (
                    now - pool_alert_last_sent.get(chat_id, 0)
                    < POOL_ALERT_COOLDOWN_SECONDS
                ):
                    continue

                pool_info = health_check_service.check_media_pool_for_chat(
                    chat_id, chat_settings=chat
                )
                alert_text = health_check_service.format_pool_alert(pool_info)
                if alert_text:
                    await bot.send_message(chat_id=chat_id, text=alert_text)
                    pool_alert_last_sent[chat_id] = now
                    logger.info(
                        f"[chat={chat_id}] Sent pool depletion alert: "
                        f"{len(pool_info['warnings'])} warning(s)"
                    )
    except Exception as e:
        logger.warning(f"Pool depletion check failed: {e}")


async def _token_health_tick(
    active_chats: list,
    scheduler_service: SchedulerService,
    health_check_service: HealthCheckService,
    token_alert_last_sent: dict[int, float],
) -> None:
    """Check Google Drive token health and send alerts for expiring tokens."""
    try:
        if active_chats and scheduler_service.telegram_service:
            now_t = time()
            bot = scheduler_service.telegram_service.application.bot
            active_ids = {c.telegram_chat_id for c in active_chats}
            for stale_id in set(token_alert_last_sent) - active_ids:
                del token_alert_last_sent[stale_id]

            for chat in active_chats:
                chat_id = chat.telegram_chat_id
                if (
                    now_t - token_alert_last_sent.get(chat_id, 0)
                    < POOL_ALERT_COOLDOWN_SECONDS
                ):
                    continue

                token_info = health_check_service.check_gdrive_token_for_chat(
                    chat_id, chat_settings=chat
                )
                alert_text = health_check_service.format_token_alert(
                    token_info, chat_id
                )
                if alert_text:
                    await bot.send_message(chat_id=chat_id, text=alert_text)
                    token_alert_last_sent[chat_id] = now_t
                    logger.info(
                        f"[chat={chat_id}] Sent token health alert: "
                        f"{token_info.get('message', '')}"
                    )
    except Exception as e:
        logger.warning(f"Token health check failed: {e}")


async def run_scheduler_loop(
    scheduler_service: SchedulerService,
    posting_service: PostingService,
    settings_service=None,
):
    """Run JIT scheduler loop — check for due slots every minute.

    For each active tenant, calls scheduler_service.process_slot() which
    checks is_slot_due() and, if a slot is due, selects media and sends
    to Telegram.  No service_run is created for no-op ticks.

    Also runs hourly retention cleanup, pool health checks, and token
    health checks.

    Args:
        scheduler_service: SchedulerService instance (handles JIT logic)
        posting_service: PostingService instance (handles GDrive alerts)
        settings_service: SettingsService for tenant discovery.
            If None, falls back to global single-tenant behavior.
    """
    logger.info("Starting JIT scheduler loop...")

    queue_repo = QueueRepository()
    service_run_repo = ServiceRunRepository()
    health_check_service = HealthCheckService()
    retention_tick_counter = 0
    pool_check_tick_counter = 0
    pool_alert_last_sent: dict[int, float] = {}
    token_alert_last_sent: dict[int, float] = {}
    is_first_tick = True

    while True:
        record_heartbeat("scheduler")

        # --- Scheduler tick: process due slots ---
        active_chats = []
        try:
            active_chats = await _scheduler_tick(
                scheduler_service,
                posting_service,
                settings_service,
                queue_repo,
                first_tick=is_first_tick,
            )
            is_first_tick = False
        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}", exc_info=True)
        finally:
            for svc in (scheduler_service, posting_service, settings_service):
                if svc is None:
                    continue
                try:
                    svc.cleanup_transactions()
                except Exception as cleanup_err:
                    logger.warning(
                        f"cleanup_transactions failed for "
                        f"{type(svc).__name__}: {cleanup_err}"
                    )

        # --- Hourly retention: purge old service_runs ---
        retention_tick_counter += 1
        if retention_tick_counter >= RETENTION_INTERVAL_TICKS:
            retention_tick_counter = 0
            await _retention_cleanup_tick(service_run_repo)

        # --- Hourly: clean up expired onboarding sessions ---
        if retention_tick_counter == 0:
            try:
                from src.services.core.conversation_service import ConversationService

                with ConversationService() as conv_service:
                    conv_service.cleanup_expired()
            except Exception as e:
                logger.warning(f"Onboarding session cleanup failed: {e}")

        # --- Hourly health checks: pool depletion + token health ---
        pool_check_tick_counter += 1
        if pool_check_tick_counter >= POOL_CHECK_INTERVAL_TICKS:
            pool_check_tick_counter = 0
            try:
                await asyncio.gather(
                    _pool_health_tick(
                        active_chats,
                        scheduler_service,
                        health_check_service,
                        pool_alert_last_sent,
                    ),
                    _token_health_tick(
                        active_chats,
                        scheduler_service,
                        health_check_service,
                        token_alert_last_sent,
                    ),
                )
            finally:
                try:
                    health_check_service.cleanup_transactions()
                except Exception as cleanup_err:
                    logger.warning(
                        f"cleanup_transactions failed for "
                        f"HealthCheckService: {cleanup_err}"
                    )

        await asyncio.sleep(60)
