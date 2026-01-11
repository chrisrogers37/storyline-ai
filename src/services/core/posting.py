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

    async def force_post_next(
        self,
        user_id: Optional[str] = None,
        triggered_by: str = "cli",
        force_sent_indicator: bool = False,
    ) -> dict:
        """
        Force-post the next scheduled item immediately.

        This is the shared core method used by both:
        - CLI: `storyline-cli process-queue --force`
        - Telegram: `/next` command

        Behavior:
        1. Gets the earliest pending item (ignores scheduled_for time)
        2. Shifts all subsequent items forward by one slot
        3. Sends the item to Telegram for manual posting
        4. Updates status to "processing"

        Args:
            user_id: User ID (for tracking/attribution)
            triggered_by: Source of the call ("cli", "telegram", etc.)
            force_sent_indicator: If True, adds ⚡ indicator to caption (for /next)

        Returns:
            Dict with results:
            {
                "success": bool,
                "queue_item_id": str or None,
                "media_item": MediaItem or None,
                "shifted_count": int,
                "error": str or None
            }
        """
        with self.track_execution(
            method_name="force_post_next",
            user_id=user_id,
            triggered_by=triggered_by,
        ) as run_id:
            # Get all pending items (earliest first)
            pending_items = self.queue_repo.get_all(status="pending")

            if not pending_items:
                logger.info("No pending items to force-post")
                result = {
                    "success": False,
                    "queue_item_id": None,
                    "media_item": None,
                    "shifted_count": 0,
                    "error": "No pending items in queue",
                }
                self.set_result_summary(run_id, result)
                return result

            # Take the first one (earliest scheduled)
            queue_item = pending_items[0]
            queue_item_id = str(queue_item.id)

            logger.info(
                f"Force-posting queue item {queue_item_id} "
                f"(originally scheduled for {queue_item.scheduled_for})"
            )

            # Get media item
            media_item = self.media_repo.get_by_id(str(queue_item.media_item_id))

            if not media_item:
                logger.error(f"Media item not found: {queue_item.media_item_id}")
                result = {
                    "success": False,
                    "queue_item_id": queue_item_id,
                    "media_item": None,
                    "shifted_count": 0,
                    "error": "Media item not found",
                }
                self.set_result_summary(run_id, result)
                return result

            # Step 1: Shift all subsequent items forward by one slot
            shifted_count = self.queue_repo.shift_slots_forward(queue_item_id)
            if shifted_count > 0:
                logger.info(f"Shifted {shifted_count} items forward after force-post")

            # Step 2: Send to Telegram for manual posting
            try:
                success = await self.telegram_service.send_notification(
                    queue_item_id,
                    force_sent=force_sent_indicator,
                )

                if success:
                    # Update status to processing
                    self.queue_repo.update_status(queue_item_id, "processing")
                    logger.info(f"Force-posted {media_item.file_name} to Telegram")

                    result = {
                        "success": True,
                        "queue_item_id": queue_item_id,
                        "media_item": media_item,
                        "shifted_count": shifted_count,
                        "error": None,
                    }
                else:
                    logger.error(f"Failed to send Telegram notification for {queue_item_id}")
                    result = {
                        "success": False,
                        "queue_item_id": queue_item_id,
                        "media_item": media_item,
                        "shifted_count": shifted_count,
                        "error": "Failed to send Telegram notification",
                    }

            except Exception as e:
                logger.error(f"Error force-posting queue item {queue_item_id}: {e}")
                result = {
                    "success": False,
                    "queue_item_id": queue_item_id,
                    "media_item": media_item,
                    "shifted_count": shifted_count,
                    "error": str(e),
                }

            self.set_result_summary(run_id, result)
            return result

    async def process_next_immediate(self, user_id: Optional[str] = None) -> dict:
        """
        Force-process the next scheduled item immediately (development/testing).

        DEPRECATED: Use force_post_next() instead. This method is kept for
        backwards compatibility and now wraps force_post_next().

        Returns:
            Dict with results: {processed: 1, telegram: 1, automated: 0, failed: 0}
        """
        # Call the new shared method
        result = await self.force_post_next(
            user_id=user_id,
            triggered_by="cli",
            force_sent_indicator=False,
        )

        # Convert to legacy format for backwards compatibility
        if result["success"]:
            return {
                "processed": 1,
                "telegram": 1,
                "automated": 0,
                "failed": 0,
            }
        else:
            return {
                "processed": 0 if result["error"] == "No pending items in queue" else 1,
                "telegram": 0,
                "automated": 0,
                "failed": 0 if result["error"] == "No pending items in queue" else 1,
            }

    async def process_pending_posts(self, user_id: Optional[str] = None) -> dict:
        """
        Process all pending posts ready to be posted.

        Returns:
            Dict with results: {processed: 5, telegram: 5, automated: 0, failed: 0, paused: bool}
        """
        with self.track_execution(
            method_name="process_pending_posts",
            user_id=user_id,
            triggered_by="scheduler" if not user_id else "cli",
        ) as run_id:
            # Check if posting is paused
            if self.telegram_service.is_paused:
                logger.info("Posting is paused - skipping scheduled posts")
                result = {"processed": 0, "telegram": 0, "automated": 0, "failed": 0, "paused": True}
                self.set_result_summary(run_id, result)
                return result

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
