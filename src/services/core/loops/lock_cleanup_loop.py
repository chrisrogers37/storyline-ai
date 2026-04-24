"""Lock cleanup loop — removes expired media locks hourly."""

import asyncio

from src.services.core.loops.heartbeat import record_heartbeat
from src.services.core.media_lock import MediaLockService
from src.utils.logger import logger


async def cleanup_locks_loop(lock_service: MediaLockService):
    """Run cleanup loop - remove expired locks every hour."""
    logger.info("Starting cleanup loop...")

    while True:
        record_heartbeat("lock_cleanup")
        try:
            await asyncio.sleep(3600)
            count = lock_service.cleanup_expired_locks()

            if count > 0:
                logger.info(f"Cleaned up {count} expired locks")

        except Exception as e:
            logger.error(f"Error in cleanup loop: {e}", exc_info=True)
        finally:
            try:
                lock_service.cleanup_transactions()
            except Exception as cleanup_err:
                logger.warning(
                    f"cleanup_transactions failed for MediaLockService: {cleanup_err}"
                )
