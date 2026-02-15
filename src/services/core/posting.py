"""Posting service - orchestrate the posting process."""

import asyncio
from datetime import datetime
from typing import Optional

from src.services.base_service import BaseService
from src.services.core.telegram_service import TelegramService
from src.services.core.media_lock import MediaLockService
from src.services.core.settings_service import SettingsService
from src.repositories.queue_repository import QueueRepository
from src.repositories.media_repository import MediaRepository
from src.repositories.history_repository import HistoryCreateParams, HistoryRepository
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

        # Initialize Instagram API services only when enabled (lazy loading)
        self._instagram_service = None
        self._cloud_service = None

    @property
    def instagram_service(self):
        """Lazy-load Instagram API service."""
        if self._instagram_service is None:
            from src.services.integrations.instagram_api import InstagramAPIService

            self._instagram_service = InstagramAPIService()
        return self._instagram_service

    @property
    def cloud_service(self):
        """Lazy-load cloud storage service."""
        if self._cloud_service is None:
            from src.services.integrations.cloud_storage import CloudStorageService

            self._cloud_service = CloudStorageService()
        return self._cloud_service

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

            # Get all pending posts ready to process
            pending_items = self.queue_repo.get_pending(
                limit=100, chat_settings_id=chat_settings_id
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

    async def _post_via_telegram(self, queue_item) -> bool:
        """
        Send post notification to Telegram.

        Note: This sends notifications EVEN in dry run mode, because the team
        needs to see posts to manually review and post them. Dry run mode only
        affects Instagram API posting, not Telegram notifications.

        Args:
            queue_item: Queue item to process

        Returns:
            True if sent successfully
        """
        try:
            # Send notification to Telegram (even in dry run mode)
            success = await self.telegram_service.send_notification(str(queue_item.id))

            if success:
                # Update queue status to processing
                self.queue_repo.update_status(str(queue_item.id), "processing")
                logger.info(
                    f"Sent Telegram notification for queue item {queue_item.id}"
                )
            else:
                logger.error(
                    f"Failed to send Telegram notification for queue item {queue_item.id}"
                )

            return success

        except Exception as e:
            logger.error(f"Error sending to Telegram: {e}")
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

    async def _post_via_instagram(self, queue_item, media_item) -> dict:
        """
        Post via Instagram API.

        Steps:
        1. Upload to cloud storage (if not already)
        2. Post to Instagram
        3. Record result in history
        4. Create lock
        5. Cleanup cloud storage

        Returns:
            dict with success, story_id, etc.
        """
        queue_item_id = str(queue_item.id)
        media_item_id = str(media_item.id)

        # Use queue item's chat context if available, fall back to admin
        chat_settings = self._get_chat_settings(queue_item.telegram_chat_id)
        if chat_settings.dry_run_mode:
            logger.info(
                f"[DRY RUN] Would post {media_item.file_name} via Instagram API"
            )
            return {"success": True, "dry_run": True}

        # Ensure media is in cloud storage
        cloud_url = getattr(media_item, "cloud_url", None)
        cloud_public_id = getattr(media_item, "cloud_public_id", None)

        if not cloud_url:
            logger.info(f"Uploading {media_item.file_name} to cloud storage")
            from src.services.media_sources.factory import MediaSourceFactory

            provider = MediaSourceFactory.get_provider_for_media_item(media_item)
            file_bytes = provider.download_file(media_item.source_identifier)
            upload_result = self.cloud_service.upload_media(
                file_bytes=file_bytes,
                filename=media_item.file_name,
                folder="storyline/stories",
            )
            cloud_url = upload_result["url"]
            cloud_public_id = upload_result["public_id"]

            # Update media item with cloud info
            self.media_repo.update_cloud_info(
                media_item_id,
                cloud_url=cloud_url,
                cloud_public_id=cloud_public_id,
                cloud_uploaded_at=upload_result["uploaded_at"],
                cloud_expires_at=upload_result["expires_at"],
            )

        # Determine media type
        mime_type = getattr(media_item, "mime_type", "image/jpeg")
        media_type = "VIDEO" if mime_type.startswith("video") else "IMAGE"

        # Apply 9:16 Story transformation for images (blurred background padding)
        if media_type == "IMAGE":
            story_url = self.cloud_service.get_story_optimized_url(cloud_url)
        else:
            # Videos don't need the same transformation
            story_url = cloud_url

        # Post to Instagram
        result = await self.instagram_service.post_story(
            media_url=story_url,
            media_type=media_type,
        )

        if result["success"]:
            # Create history record with instagram_api method
            self.history_repo.create(
                HistoryCreateParams(
                    media_item_id=media_item_id,
                    queue_item_id=queue_item_id,
                    queue_created_at=queue_item.created_at,
                    queue_deleted_at=datetime.utcnow(),
                    scheduled_for=queue_item.scheduled_for,
                    posted_at=datetime.utcnow(),
                    status="posted",
                    success=True,
                    posting_method="instagram_api",
                    instagram_story_id=result.get("story_id"),
                    retry_count=queue_item.retry_count,
                )
            )

            # Update media item and create lock
            self.media_repo.increment_times_posted(media_item_id)
            self.lock_service.create_lock(media_item_id)

            # Delete from queue
            self.queue_repo.delete(queue_item_id)

            logger.info(
                f"Posted {media_item.file_name} to Instagram (story_id: {result.get('story_id')})"
            )

            # Schedule cloud cleanup (don't await)
            asyncio.create_task(
                self._cleanup_cloud_media(media_item_id, cloud_public_id)
            )

        return result

    async def _cleanup_cloud_media(
        self, media_item_id: str, cloud_public_id: str
    ) -> None:
        """
        Clean up cloud storage after successful post.

        Called asynchronously after posting completes.
        """
        try:
            # Small delay to ensure Instagram has processed the media
            await asyncio.sleep(5)

            success = self.cloud_service.delete_media(cloud_public_id)

            if success:
                # Clear cloud info from media item
                self.media_repo.update_cloud_info(
                    media_item_id,
                    cloud_url=None,
                    cloud_public_id=None,
                    cloud_uploaded_at=None,
                    cloud_expires_at=None,
                )
                logger.info(f"Cleaned up cloud storage for media {media_item_id}")
            else:
                logger.warning(
                    f"Failed to clean up cloud storage for media {media_item_id}"
                )

        except Exception as e:
            logger.error(f"Error cleaning up cloud storage: {e}")

    def handle_completion(
        self,
        queue_item_id: str,
        success: bool,
        posted_by_user_id: Optional[str] = None,
        error_message: Optional[str] = None,
        posting_method: str = "telegram_manual",
        instagram_story_id: Optional[str] = None,
    ):
        """
        Handle post completion (move to history, create lock).

        Args:
            queue_item_id: Queue item ID
            success: Whether posting was successful
            posted_by_user_id: User who posted (for manual posts)
            error_message: Error message (if failed)
            posting_method: How the post was made ('telegram_manual' or 'instagram_api')
            instagram_story_id: Instagram story ID if posted via API
        """
        queue_item = self.queue_repo.get_by_id(queue_item_id)

        if not queue_item:
            logger.error(f"Queue item not found: {queue_item_id}")
            return

        # Create history record
        self.history_repo.create(
            HistoryCreateParams(
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
                posting_method=posting_method,
                instagram_story_id=instagram_story_id,
            )
        )

        # If successful, update media item and create lock
        if success:
            self.media_repo.increment_times_posted(str(queue_item.media_item_id))
            self.lock_service.create_lock(str(queue_item.media_item_id))

        # Delete from queue
        self.queue_repo.delete(queue_item_id)

        logger.info(
            f"Completed processing for queue item {queue_item_id} (success={success})"
        )
