"""Cloud storage cleanup loop — removes orphaned uploads hourly."""

import asyncio

from src.config.settings import settings
from src.services.core.loops.heartbeat import record_heartbeat
from src.utils.logger import logger


async def cleanup_cloud_storage_loop(cloud_service):
    """Remove orphaned Cloudinary uploads that outlived their retention window.

    Runs hourly as a safety net — normal flow deletes immediately after posting.
    """
    from src.repositories.media_repository import MediaRepository
    from src.services.integrations.cloud_storage import CLOUD_UPLOAD_FOLDER

    media_repo = MediaRepository()
    logger.info("Starting cloud storage cleanup loop...")

    while True:
        record_heartbeat("cloud_cleanup")
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
            try:
                cloud_service.cleanup_transactions()
            except Exception as cleanup_err:
                logger.warning(
                    f"cleanup_transactions failed for CloudStorageService: {cleanup_err}"
                )
            try:
                media_repo.end_read_transaction()
            except Exception as cleanup_err:
                logger.warning(
                    f"cleanup_transactions failed for MediaRepository: {cleanup_err}"
                )
