"""Posting service - orchestrate the posting process."""

from datetime import datetime, timedelta
from typing import Optional

from src.services.base_service import BaseService
from src.services.core.telegram_service import TelegramService
from src.services.core.media_lock import MediaLockService
from src.services.core.settings_service import SettingsService
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
        self.settings_service = SettingsService()

    def _get_chat_settings(self, telegram_chat_id: Optional[int] = None):
        """Get settings for a chat (for checking dry_run, is_paused, etc.).

        Args:
            telegram_chat_id: Chat to get settings for.
                Falls back to ADMIN_TELEGRAM_CHAT_ID if not specified.
        """
        if telegram_chat_id is None:
            telegram_chat_id = settings.ADMIN_TELEGRAM_CHAT_ID
        return self.settings_service.get_settings(telegram_chat_id)

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
                    logger.error(
                        f"Failed to send Telegram notification for {queue_item_id}"
                    )
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

            # Create serializable summary (media_item is SQLAlchemy object)
            summary = {
                "success": result["success"],
                "queue_item_id": result["queue_item_id"],
                "media_file_name": media_item.file_name if media_item else None,
                "shifted_count": result["shifted_count"],
                "error": result["error"],
            }
            self.set_result_summary(run_id, summary)
            return result

    async def process_pending_posts(
        self, user_id: Optional[str] = None, telegram_chat_id: Optional[int] = None
    ) -> dict:
        """
        Process all pending posts ready to be posted.

        Args:
            user_id: User who triggered processing (for observability)
            telegram_chat_id: Chat to process posts for. When provided,
                uses per-tenant pause state and tenant-scoped queue queries.
                Falls back to global behavior when None.

        Returns:
            Dict with results: {processed: 5, telegram: 5, automated: 0, failed: 0, paused: bool}
        """
        with self.track_execution(
            method_name="process_pending_posts",
            user_id=user_id,
            triggered_by="scheduler" if not user_id else "cli",
        ) as run_id:
            # Check if posting is paused for this chat
            if telegram_chat_id:
                chat_settings = self._get_chat_settings(telegram_chat_id)
                is_paused = chat_settings.is_paused
            else:
                is_paused = self.telegram_service.is_paused

            if is_paused:
                logger.info("Posting is paused - skipping scheduled posts")
                result = {
                    "processed": 0,
                    "telegram": 0,
                    "automated": 0,
                    "failed": 0,
                    "paused": True,
                }
                self.set_result_summary(run_id, result)
                return result

            processed_count = 0
            telegram_count = 0
            automated_count = 0
            failed_count = 0

            # Resolve chat_settings_id for tenant-scoped queue queries
            # (chat_settings was already fetched in the pause check above)
            chat_settings_id = None
            if telegram_chat_id:
                chat_settings_id = str(chat_settings.id) if chat_settings else None

            # Get next pending post (1 per cycle to space out deliveries)
            pending_items = self.queue_repo.get_pending(
                limit=1, chat_settings_id=chat_settings_id
            )

            logger.info(f"Processing {len(pending_items)} pending posts")

            for queue_item in pending_items:
                try:
                    # Get media item
                    media_item = self.media_repo.get_by_id(
                        str(queue_item.media_item_id)
                    )

                    if not media_item:
                        logger.error(
                            f"Media item not found: {queue_item.media_item_id}"
                        )
                        failed_count += 1
                        continue

                    # Route based on settings and media type
                    route_result = await self._route_post(queue_item, media_item)

                    if route_result["method"] == "instagram_api":
                        if route_result["success"]:
                            automated_count += 1
                        else:
                            failed_count += 1
                    else:  # telegram_manual
                        if route_result["success"]:
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

    def reschedule_overdue_for_paused_chat(self, telegram_chat_id: int) -> dict:
        """Reschedule overdue queue items for a paused (delivery OFF) tenant.

        When delivery is OFF, items whose scheduled_for passes are bumped
        +24 hours (repeatedly until in the future). This keeps the queue
        valid without losing any items.

        Called by the scheduler loop for each paused tenant.

        Args:
            telegram_chat_id: The tenant's Telegram chat ID

        Returns:
            Dict with results: {"rescheduled": int, "chat_id": int}
        """
        chat_settings = self._get_chat_settings(telegram_chat_id)
        chat_settings_id = str(chat_settings.id) if chat_settings else None

        overdue_items = self.queue_repo.get_overdue_pending(
            chat_settings_id=chat_settings_id
        )
        if not overdue_items:
            return {"rescheduled": 0, "chat_id": telegram_chat_id}

        now = datetime.utcnow()
        for item in overdue_items:
            while item.scheduled_for <= now:
                item.scheduled_for = item.scheduled_for + timedelta(hours=24)

        self.queue_repo.db.commit()
        rescheduled = len(overdue_items)

        if rescheduled > 0:
            logger.info(
                f"[delivery=OFF, chat={telegram_chat_id}] "
                f"Rescheduled {rescheduled} overdue items +24hr"
            )

        return {"rescheduled": rescheduled, "chat_id": telegram_chat_id}

    async def _post_via_telegram(self, queue_item) -> bool:
        """
        Send post notification to Telegram.

        Note: This sends notifications EVEN in dry run mode, because the team
        needs to see posts to manually review and post them. Dry run mode only
        affects Instagram API posting, not Telegram notifications.

        Claims the queue item (status → "processing") BEFORE sending to
        prevent duplicate sends if the next scheduler cycle fires before
        the Telegram API responds. Rolls back to "pending" on failure.

        Args:
            queue_item: Queue item to process

        Returns:
            True if sent successfully
        """
        queue_item_id = str(queue_item.id)
        try:
            # Claim the item BEFORE sending to prevent duplicate sends.
            # The next scheduler cycle will skip this item because it's
            # no longer "pending".
            self.queue_repo.update_status(queue_item_id, "processing")

            # Send notification to Telegram (even in dry run mode)
            success = await self.telegram_service.send_notification(queue_item_id)

            if success:
                logger.info(
                    f"Sent Telegram notification for queue item {queue_item.id}"
                )
            else:
                # Send failed — release the item back to pending
                logger.error(
                    f"Failed to send Telegram notification for queue item {queue_item.id}"
                )
                self.queue_repo.update_status(queue_item_id, "pending")

            return success

        except Exception as e:
            logger.error(f"Error sending to Telegram: {e}")
            # Release the item back to pending on exception
            try:
                self.queue_repo.update_status(queue_item_id, "pending")
            except Exception:
                pass  # Best-effort rollback
            return False

    async def _route_post(self, queue_item, media_item) -> dict:
        """
        Route post to Telegram for human approval.

        ALL scheduled posts go through Telegram first for review/approval.
        The Instagram API is only used when a user explicitly clicks "Auto Post"
        in the Telegram bot interface.

        This ensures:
        1. Human review of all content before posting
        2. Ability to skip inappropriate content
        3. Control over what gets posted to Instagram

        Returns:
            dict with method ('telegram_manual') and success bool
        """
        # ALL scheduled posts go to Telegram for approval
        # Instagram API posting happens via the "Auto Post" button callback
        success = await self._post_via_telegram(queue_item)
        return {"method": "telegram_manual", "success": success}
