"""Posting service - orchestrate the posting process."""
from datetime import datetime
from typing import Optional

from src.services.base_service import BaseService
from src.services.core.telegram_service import TelegramService
from src.services.core.media_lock import MediaLockService
from src.repositories.queue_repository import QueueRepository
from src.repositories.media_repository import MediaRepository
from src.repositories.history_repository import HistoryRepository
from src.config.settings import settings
from src.utils.logger import logger


class PostingService(BaseService):
    """Orchestrate the posting process."""

    def __init__(self):
        super().__init__()
        self.queue_repo = QueueRepository()
        self.media_repo = MediaRepository()
        self.history_repo = HistoryRepository()
        self.telegram_service = TelegramService()
        self.lock_service = MediaLockService()

    async def process_pending_posts(self, user_id: Optional[str] = None) -> dict:
        """
        Process all pending posts ready to be posted.

        Returns:
            Dict with results: {processed: 5, telegram: 5, automated: 0, failed: 0}
        """
        with self.track_execution(
            method_name="process_pending_posts",
            user_id=user_id,
            triggered_by="scheduler" if not user_id else "cli",
        ) as run_id:
            processed_count = 0
            telegram_count = 0
            automated_count = 0
            failed_count = 0

            # Get all pending posts ready to process
            pending_items = self.queue_repo.get_pending(limit=100)

            logger.info(f"Processing {len(pending_items)} pending posts")

            for queue_item in pending_items:
                try:
                    # Get media item
                    media_item = self.media_repo.get_by_id(str(queue_item.media_item_id))

                    if not media_item:
                        logger.error(f"Media item not found: {queue_item.media_item_id}")
                        failed_count += 1
                        continue

                    # Route based on settings
                    if settings.ENABLE_INSTAGRAM_API and not media_item.requires_interaction:
                        # Phase 2: Automated posting via Instagram API
                        # (Not implemented in Phase 1)
                        logger.info(f"Would auto-post {media_item.file_name} (API not implemented)")
                        automated_count += 1
                    else:
                        # Phase 1: Send to Telegram for manual posting
                        success = await self._post_via_telegram(queue_item)

                        if success:
                            telegram_count += 1
                        else:
                            failed_count += 1

                    processed_count += 1

                except Exception as e:
                    logger.error(f"Error processing queue item {queue_item.id}: {e}")
                    failed_count += 1

            result = {
                "processed": processed_count,
                "telegram": telegram_count,
                "automated": automated_count,
                "failed": failed_count,
            }

            self.set_result_summary(run_id, result)

            return result

    async def _post_via_telegram(self, queue_item) -> bool:
        """
        Send post notification to Telegram.

        Args:
            queue_item: Queue item to process

        Returns:
            True if sent successfully
        """
        if settings.DRY_RUN_MODE:
            logger.info(f"[DRY RUN] Would send Telegram notification for queue item {queue_item.id}")
            return True

        try:
            # Send notification to Telegram
            success = await self.telegram_service.send_notification(str(queue_item.id))

            if success:
                # Update queue status to processing
                self.queue_repo.update_status(str(queue_item.id), "processing")
                logger.info(f"Sent Telegram notification for queue item {queue_item.id}")
            else:
                logger.error(f"Failed to send Telegram notification for queue item {queue_item.id}")

            return success

        except Exception as e:
            logger.error(f"Error sending to Telegram: {e}")
            return False

    def handle_completion(
        self,
        queue_item_id: str,
        success: bool,
        posted_by_user_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        """
        Handle post completion (move to history, create lock).

        Args:
            queue_item_id: Queue item ID
            success: Whether posting was successful
            posted_by_user_id: User who posted (for manual posts)
            error_message: Error message (if failed)
        """
        queue_item = self.queue_repo.get_by_id(queue_item_id)

        if not queue_item:
            logger.error(f"Queue item not found: {queue_item_id}")
            return

        # Create history record
        self.history_repo.create(
            media_item_id=str(queue_item.media_item_id),
            queue_item_id=queue_item_id,
            queue_created_at=queue_item.created_at,
            queue_deleted_at=datetime.utcnow(),
            scheduled_for=queue_item.scheduled_for,
            posted_at=datetime.utcnow(),
            status="posted" if success else "failed",
            success=success,
            posted_by_user_id=posted_by_user_id,
            error_message=error_message,
            retry_count=queue_item.retry_count,
        )

        # If successful, update media item and create lock
        if success:
            self.media_repo.increment_times_posted(str(queue_item.media_item_id))
            self.lock_service.create_lock(str(queue_item.media_item_id))

        # Delete from queue
        self.queue_repo.delete(queue_item_id)

        logger.info(f"Completed processing for queue item {queue_item_id} (success={success})")
