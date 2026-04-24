"""Transaction cleanup loop — prevents idle-in-transaction buildup."""

import asyncio

from src.services.core.loops.heartbeat import record_heartbeat
from src.utils.logger import logger


async def transaction_cleanup_loop(services: list):
    """Periodically clean up idle database transactions from all services.

    This prevents "idle in transaction" connections from piling up,
    which can cause the bot to freeze when handling callbacks.

    Also logs connection pool utilization every cycle so that pool
    exhaustion is visible in logs before it causes freezes.
    """
    from src.utils.resilience import log_pool_status

    while True:
        record_heartbeat("transaction_cleanup")
        await asyncio.sleep(30)
        log_pool_status()

        for service in services:
            try:
                service.cleanup_transactions()
            except Exception as e:
                logger.warning(
                    f"Transaction cleanup failed for {type(service).__name__}: "
                    f"{type(e).__name__}: {e}"
                )
