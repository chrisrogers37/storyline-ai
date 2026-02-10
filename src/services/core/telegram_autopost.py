"""Telegram auto-post handler - Instagram API posting flow with safety gates."""

from __future__ import annotations

from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.services.core.telegram_service import _escape_markdown
from src.config.settings import settings
from src.utils.logger import logger
from datetime import datetime

if TYPE_CHECKING:
    from src.services.core.telegram_service import TelegramService


class TelegramAutopostHandler:
    """Handles Instagram API auto-posting flow with safety gates.

    CRITICAL: This handler contains safety gates that prevent accidental
    posting to Instagram. Do not modify the safety check flow without
    careful review.

    Uses composition: receives a TelegramService reference for shared state.
    """

    def __init__(self, service: TelegramService):
        self.service = service

    async def handle_autopost(self, queue_id: str, user, query):
        """
        Handle 'Auto Post' button click.

        This uploads the media to Cloudinary and posts to Instagram via API.
        Includes CRITICAL safety gates to prevent accidental Facebook posting.

        Uses operation locks to prevent duplicate auto-posts from rapid clicks.
        Checks cancellation flags so terminal actions (Posted/Skip/Reject) can abort.
        """
        lock = self.service.get_operation_lock(queue_id)
        if lock.locked():
            await query.answer("⏳ Already processing...", show_alert=False)
            return

        cancel_flag = self.service.get_cancel_flag(queue_id)
        cancel_flag.clear()

        async with lock:
            try:
                await self._locked_autopost(queue_id, user, query, cancel_flag)
            finally:
                self.service.cleanup_operation_state(queue_id)

    async def _locked_autopost(self, queue_id, user, query, cancel_flag):
        """Autopost implementation that runs under the operation lock."""
        queue_item = self.service.queue_repo.get_by_id(queue_id)

        if not queue_item:
            await query.edit_message_caption(caption="⚠️ Queue item not found")
            return

        # Get media item
        media_item = self.service.media_repo.get_by_id(str(queue_item.media_item_id))
        if not media_item:
            await query.edit_message_caption(caption="⚠️ Media item not found")
            return

        # ============================================
        # CRITICAL SAFETY GATES
        # ============================================
        from src.services.integrations.instagram_api import InstagramAPIService
        from src.services.integrations.cloud_storage import CloudStorageService

        # Create services and ensure cleanup on exit
        instagram_service = InstagramAPIService()
        cloud_service = CloudStorageService()
        try:
            await self._do_autopost(
                queue_id,
                queue_item,
                media_item,
                user,
                query,
                instagram_service,
                cloud_service,
                cancel_flag,
            )
        finally:
            # Ensure services are cleaned up to prevent connection pool exhaustion
            instagram_service.close()
            cloud_service.close()

    async def _do_autopost(
        self,
        queue_id,
        queue_item,
        media_item,
        user,
        query,
        instagram_service,
        cloud_service,
        cancel_flag=None,
    ):
        """Internal method to perform auto-post with pre-created services."""
        chat_id = query.message.chat_id

        # Get settings from database (not .env)
        chat_settings = self.service.settings_service.get_settings(chat_id)

        # Run comprehensive safety check
        safety_result = instagram_service.safety_check_before_post(
            telegram_chat_id=chat_id
        )

        if not safety_result["safe_to_post"]:
            error_list = "\n".join([f"• {e}" for e in safety_result["errors"]])
            caption = (
                f"🚫 *SAFETY CHECK FAILED*\n\n"
                f"Cannot auto-post due to:\n{error_list}\n\n"
                f"Please check your configuration."
            )
            await query.edit_message_caption(caption=caption, parse_mode="Markdown")
            logger.error(f"Auto-post safety check failed: {safety_result['errors']}")
            return

        # ============================================
        # UPLOAD TO CLOUDINARY (runs in both dry run and real mode)
        # ============================================
        try:
            # Update message to show progress
            await query.edit_message_caption(
                caption="⏳ *Uploading to Cloudinary...*", parse_mode="Markdown"
            )

            # Step 1: Upload to Cloudinary (uses passed-in cloud_service)
            upload_result = cloud_service.upload_media(
                file_path=media_item.file_path,
                folder="instagram_stories",
            )

            cloud_url = upload_result.get("url")
            cloud_public_id = upload_result.get("public_id")

            if not cloud_url:
                raise Exception("Cloudinary upload failed: No URL returned")

            logger.info(f"Uploaded to Cloudinary: {cloud_public_id}")

            # Check cancellation after Cloudinary upload
            if cancel_flag and cancel_flag.is_set():
                logger.info(
                    f"Auto-post cancelled after Cloudinary upload for {media_item.file_name}"
                )
                await query.edit_message_caption(
                    caption="❌ Auto-post cancelled (another action was taken)"
                )
                return

            # Update media item with cloud info
            self.service.media_repo.update_cloud_info(
                media_id=str(media_item.id),
                cloud_url=cloud_url,
                cloud_public_id=cloud_public_id,
                cloud_uploaded_at=datetime.utcnow(),
            )

            # ============================================
            # DRY RUN MODE - Stop before Instagram API
            # ============================================
            if chat_settings.dry_run_mode:
                # Dry run: only show Test Again and Back buttons
                # Don't show Posted/Skip/Reject to prevent accidental marking
                keyboard = [
                    [
                        InlineKeyboardButton(
                            "🔄 Test Again",
                            callback_data=f"autopost:{queue_id}",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "↩️ Back to Queue Item",
                            callback_data=f"back:{queue_id}",
                        ),
                    ],
                ]

                # Fetch account username from API (cached)
                account_info = await instagram_service.get_account_info(
                    telegram_chat_id=chat_id
                )
                if account_info.get("username"):
                    account_display = f"@{account_info['username']}"
                else:
                    account_display = "Unknown account"

                # Check verbose setting (reuse already-loaded chat_settings)
                verbose = self.service._is_verbose(chat_id, chat_settings=chat_settings)

                if verbose:
                    # Apply the same transformation we'd use for Instagram
                    media_type = (
                        "VIDEO"
                        if media_item.file_path.lower().endswith((".mp4", ".mov"))
                        else "IMAGE"
                    )
                    if media_type == "IMAGE":
                        preview_url = cloud_service.get_story_optimized_url(cloud_url)
                    else:
                        preview_url = cloud_url

                    caption = (
                        f"🧪 DRY RUN - Cloudinary Upload Complete\n\n"
                        f"📁 File: {media_item.file_name}\n"
                        f"📸 Account: {account_display}\n\n"
                        f"✅ Cloudinary upload: Success\n"
                        f"🔗 Preview (with blur): {preview_url}\n\n"
                        f"⏸️ Stopped before Instagram API\n"
                        f"(DRY_RUN_MODE=true)\n\n"
                        f"• No Instagram post made\n"
                        f"• No history recorded\n"
                        f"• No TTL lock created\n"
                        f"• Queue item preserved\n\n"
                        f"Tested by: {self.service._get_display_name(user)}"
                    )
                else:
                    caption = (
                        f"🧪 DRY RUN ✅\n\n"
                        f"📸 Account: {account_display}\n"
                        f"Tested by: {self.service._get_display_name(user)}"
                    )
                await query.edit_message_caption(
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                )

                # Log interaction (dry run - but Cloudinary worked)
                self.service.interaction_service.log_callback(
                    user_id=str(user.id),
                    callback_name="autopost",
                    context={
                        "queue_item_id": queue_id,
                        "media_id": str(queue_item.media_item_id),
                        "media_filename": media_item.file_name,
                        "cloud_url": cloud_url,
                        "cloud_public_id": cloud_public_id,
                        "dry_run": True,
                    },
                    telegram_chat_id=query.message.chat_id,
                    telegram_message_id=query.message.message_id,
                )

                logger.info(
                    f"[DRY RUN] Cloudinary upload complete, stopped before Instagram API. "
                    f"User: {self.service._get_display_name(user)}, "
                    f"File: {media_item.file_name}"
                )
                return

            # ============================================
            # REAL POSTING - Continue to Instagram API
            # ============================================
            # Check cancellation before Instagram API call
            if cancel_flag and cancel_flag.is_set():
                logger.info(
                    f"Auto-post cancelled before Instagram API for {media_item.file_name}"
                )
                await query.edit_message_caption(
                    caption="❌ Auto-post cancelled (another action was taken)"
                )
                return

            # Step 2: Post to Instagram
            await query.edit_message_caption(
                caption="⏳ *Posting to Instagram...*", parse_mode="Markdown"
            )

            # Determine media type
            media_type = (
                "VIDEO"
                if media_item.file_path.lower().endswith((".mp4", ".mov"))
                else "IMAGE"
            )

            # Apply 9:16 Story transformation (blurred background padding)
            if media_type == "IMAGE":
                story_url = cloud_service.get_story_optimized_url(cloud_url)
            else:
                # Videos don't need the same transformation
                story_url = cloud_url

            post_result = await instagram_service.post_story(
                media_url=story_url,
                media_type=media_type,
                telegram_chat_id=chat_id,
            )

            story_id = post_result.get("story_id")
            logger.info(f"Posted to Instagram: story_id={story_id}")

            # Step 3: Cleanup Cloudinary (optional - can keep for debugging)
            # cloud_service.delete_media(cloud_public_id)

            # Step 4: Create history record
            self.service.history_repo.create(
                media_item_id=str(queue_item.media_item_id),
                queue_item_id=queue_id,
                queue_created_at=queue_item.created_at,
                queue_deleted_at=datetime.utcnow(),
                scheduled_for=queue_item.scheduled_for,
                posted_at=datetime.utcnow(),
                status="posted",
                success=True,
                posted_by_user_id=str(user.id),
                posted_by_telegram_username=user.telegram_username,
                posting_method="instagram_api",
                instagram_story_id=story_id,
            )

            # Update media item
            self.service.media_repo.increment_times_posted(
                str(queue_item.media_item_id)
            )

            # Create 30-day lock to prevent reposting
            self.service.lock_service.create_lock(str(queue_item.media_item_id))

            # Delete from queue
            self.service.queue_repo.delete(queue_id)

            # Update user stats
            self.service.user_repo.increment_posts(str(user.id))

            # Success message (reuse already-loaded chat_settings)
            verbose = self.service._is_verbose(chat_id, chat_settings=chat_settings)

            # Fetch account username from API (cached)
            account_info = await instagram_service.get_account_info(
                telegram_chat_id=chat_id
            )
            if account_info.get("username"):
                account_display = f"@{account_info['username']}"
            else:
                account_display = "Unknown account"

            if verbose:
                # Verbose ON: Show detailed info
                escaped_filename = _escape_markdown(media_item.file_name)
                caption = (
                    f"✅ *Posted to Instagram!*\n\n"
                    f"📁 {escaped_filename}\n"
                    f"📸 Account: {account_display}\n"
                    f"🆔 Story ID: {story_id[:20]}...\n\n"
                    f"Posted by: {self.service._get_display_name(user)}"
                )
            else:
                # Verbose OFF: Show minimal info (always include user)
                caption = (
                    f"✅ Posted to {account_display} by "
                    f"{self.service._get_display_name(user)}"
                )

            await query.edit_message_caption(caption=caption, parse_mode="Markdown")

            # Log interaction
            self.service.interaction_service.log_callback(
                user_id=str(user.id),
                callback_name="autopost",
                context={
                    "queue_item_id": queue_id,
                    "media_id": str(queue_item.media_item_id),
                    "media_filename": media_item.file_name,
                    "instagram_story_id": story_id,
                    "dry_run": False,
                    "success": True,
                },
                telegram_chat_id=query.message.chat_id,
                telegram_message_id=query.message.message_id,
            )

            # Log outgoing bot response
            self.service.interaction_service.log_bot_response(
                response_type="caption_update",
                context={
                    "caption": caption,
                    "action": "autopost_success",
                    "media_filename": media_item.file_name,
                    "instagram_story_id": story_id,
                    "edited": True,
                },
                telegram_chat_id=query.message.chat_id,
                telegram_message_id=query.message.message_id,
            )

            logger.info(
                f"Auto-posted to Instagram by {self.service._get_display_name(user)}: "
                f"{media_item.file_name} (story_id={story_id})"
            )

        except Exception as e:
            # Error handling
            error_msg = str(e)
            logger.error(f"Auto-post failed: {error_msg}", exc_info=True)

            caption = (
                f"❌ *Auto Post Failed*\n\n"
                f"Error: {error_msg[:200]}\n\n"
                f"You can try again or use manual posting."
            )

            # Rebuild keyboard with all buttons
            keyboard = []
            if settings.ENABLE_INSTAGRAM_API:
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            "🔄 Retry Auto Post",
                            callback_data=f"autopost:{queue_id}",
                        ),
                    ]
                )
            keyboard.extend(
                [
                    [
                        InlineKeyboardButton(
                            "✅ Posted", callback_data=f"posted:{queue_id}"
                        ),
                        InlineKeyboardButton(
                            "⏭️ Skip", callback_data=f"skip:{queue_id}"
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "📱 Open Instagram",
                            url="https://www.instagram.com/",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "🚫 Reject", callback_data=f"reject:{queue_id}"
                        ),
                    ],
                ]
            )

            await query.edit_message_caption(
                caption=caption,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )

            # Log interaction (failure)
            self.service.interaction_service.log_callback(
                user_id=str(user.id),
                callback_name="autopost",
                context={
                    "queue_item_id": queue_id,
                    "media_id": str(queue_item.media_item_id),
                    "media_filename": media_item.file_name,
                    "dry_run": False,
                    "success": False,
                    "error": error_msg[:200],
                },
                telegram_chat_id=query.message.chat_id,
                telegram_message_id=query.message.message_id,
            )
