"""Telegram auto-post handler - Instagram API posting flow with safety gates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.config.settings import settings
from src.exceptions.instagram import (
    InstagramAPIError,
    MediaUploadError,
    RateLimitError,
    TokenExpiredError,
)
from src.repositories.history_repository import HistoryCreateParams
from src.services.core.telegram_service import _escape_markdown
from src.services.core.telegram_utils import (
    build_error_recovery_keyboard,
    validate_queue_item,
)
from src.utils.logger import logger
from datetime import datetime

if TYPE_CHECKING:
    from src.services.core.telegram_service import TelegramService


@dataclass
class AutopostContext:
    """Shared state passed through the autopost call chain.

    Bundles parameters that are constant for a single _do_autopost() invocation
    and shared across _upload_to_cloudinary, _handle_dry_run,
    _execute_instagram_post, _record_successful_post, etc.
    """

    queue_id: str
    queue_item: object
    media_item: object
    user: object
    query: object
    chat_id: int
    chat_settings: object
    cloud_service: object
    instagram_service: object
    cancel_flag: object = None
    cloud_url: str | None = None
    cloud_public_id: str | None = None


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
        queue_item = await validate_queue_item(self.service, queue_id, query)
        if not queue_item:
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
        """Internal method to perform auto-post with pre-created services.

        Orchestrates: safety check → upload → dry-run check → post → record.
        """
        chat_id = query.message.chat_id
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

        ctx = AutopostContext(
            queue_id=queue_id,
            queue_item=queue_item,
            media_item=media_item,
            user=user,
            query=query,
            chat_id=chat_id,
            chat_settings=chat_settings,
            cloud_service=cloud_service,
            instagram_service=instagram_service,
            cancel_flag=cancel_flag,
        )

        try:
            if not await self._upload_to_cloudinary(ctx):
                return

            if ctx.chat_settings.dry_run_mode:
                await self._handle_dry_run(ctx)
                return

            story_id = await self._execute_instagram_post(ctx)
            if story_id is None:
                return

            self._record_successful_post(ctx, story_id)
            await self._send_success_message(ctx, story_id)

        except Exception as e:
            await self._handle_autopost_error(ctx, e)

    # ==================== Extracted Helpers ====================

    async def _get_account_display(self, ctx: AutopostContext) -> str:
        """Get formatted account display string for messages."""
        try:
            account_info = await ctx.instagram_service.get_account_info(
                telegram_chat_id=ctx.chat_id
            )
            return f"@{account_info.get('username', 'Unknown')}"
        except Exception:
            return "Unknown account"

    async def _upload_to_cloudinary(self, ctx: AutopostContext) -> bool:
        """Upload media to Cloudinary for Instagram posting.

        Sets ctx.cloud_url and ctx.cloud_public_id.
        Returns False if cancelled, True on success.
        """
        await ctx.query.edit_message_caption(
            caption="⏳ *Uploading to Cloudinary...*", parse_mode="Markdown"
        )

        from src.services.media_sources.factory import MediaSourceFactory

        provider = MediaSourceFactory.get_provider_for_media_item(
            ctx.media_item, telegram_chat_id=ctx.chat_id
        )
        file_bytes = provider.download_file(ctx.media_item.source_identifier)

        upload_result = ctx.cloud_service.upload_media(
            file_bytes=file_bytes,
            filename=ctx.media_item.file_name,
            folder="instagram_stories",
        )

        ctx.cloud_url = upload_result.get("url")
        ctx.cloud_public_id = upload_result.get("public_id")

        if not ctx.cloud_url:
            raise Exception("Cloudinary upload failed: No URL returned")

        logger.info(f"Uploaded to Cloudinary: {ctx.cloud_public_id}")

        if ctx.cancel_flag and ctx.cancel_flag.is_set():
            logger.info(
                f"Auto-post cancelled after Cloudinary upload for {ctx.media_item.file_name}"
            )
            await ctx.query.edit_message_caption(
                caption="❌ Auto-post cancelled (another action was taken)"
            )
            return False

        self.service.media_repo.update_cloud_info(
            media_id=str(ctx.media_item.id),
            cloud_url=ctx.cloud_url,
            cloud_public_id=ctx.cloud_public_id,
            cloud_uploaded_at=datetime.utcnow(),
        )

        return True

    async def _handle_dry_run(self, ctx: AutopostContext) -> None:
        """Handle dry-run mode: log what would happen, cleanup cloud, show message."""
        keyboard = [
            [
                InlineKeyboardButton(
                    "🔄 Test Again",
                    callback_data=f"autopost:{ctx.queue_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "↩️ Back to Queue Item",
                    callback_data=f"back:{ctx.queue_id}",
                ),
            ],
        ]

        account_display = await self._get_account_display(ctx)
        verbose = self.service._is_verbose(ctx.chat_id, chat_settings=ctx.chat_settings)

        if verbose:
            media_type = (
                "VIDEO"
                if ctx.media_item.mime_type
                and ctx.media_item.mime_type.startswith("video")
                else "IMAGE"
            )
            if media_type == "IMAGE":
                preview_url = ctx.cloud_service.get_story_optimized_url(ctx.cloud_url)
            else:
                preview_url = ctx.cloud_url

            caption = (
                f"🧪 DRY RUN - Cloudinary Upload Complete\n\n"
                f"📁 File: {ctx.media_item.file_name}\n"
                f"📸 Account: {account_display}\n\n"
                f"✅ Cloudinary upload: Success\n"
                f"🔗 Preview (with blur): {preview_url}\n\n"
                f"⏸️ Stopped before Instagram API\n"
                f"(DRY_RUN_MODE=true)\n\n"
                f"• No Instagram post made\n"
                f"• No history recorded\n"
                f"• No TTL lock created\n"
                f"• Queue item preserved\n\n"
                f"Tested by: {self.service._get_display_name(ctx.user)}"
            )
        else:
            caption = (
                f"🧪 DRY RUN ✅\n\n"
                f"📸 Account: {account_display}\n"
                f"Tested by: {self.service._get_display_name(ctx.user)}"
            )
        await ctx.query.edit_message_caption(
            caption=caption,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

        self.service.interaction_service.log_callback(
            user_id=str(ctx.user.id),
            callback_name="autopost",
            context={
                "queue_item_id": ctx.queue_id,
                "media_id": str(ctx.queue_item.media_item_id),
                "media_filename": ctx.media_item.file_name,
                "cloud_url": ctx.cloud_url,
                "cloud_public_id": ctx.cloud_public_id,
                "dry_run": True,
            },
            telegram_chat_id=ctx.query.message.chat_id,
            telegram_message_id=ctx.query.message.message_id,
        )

        logger.info(
            f"[DRY RUN] Cloudinary upload complete, stopped before Instagram API. "
            f"User: {self.service._get_display_name(ctx.user)}, "
            f"File: {ctx.media_item.file_name}"
        )

    async def _execute_instagram_post(self, ctx: AutopostContext) -> str | None:
        """Post media to Instagram via the Graph API.

        Returns:
            Instagram story_id string, or None if cancelled.
        """
        if ctx.cancel_flag and ctx.cancel_flag.is_set():
            logger.info(
                f"Auto-post cancelled before Instagram API for {ctx.media_item.file_name}"
            )
            await ctx.query.edit_message_caption(
                caption="❌ Auto-post cancelled (another action was taken)"
            )
            return None

        await ctx.query.edit_message_caption(
            caption="⏳ *Posting to Instagram...*", parse_mode="Markdown"
        )

        media_type = (
            "VIDEO"
            if ctx.media_item.file_path.lower().endswith((".mp4", ".mov"))
            else "IMAGE"
        )

        if media_type == "IMAGE":
            story_url = ctx.cloud_service.get_story_optimized_url(ctx.cloud_url)
        else:
            story_url = ctx.cloud_url

        post_result = await ctx.instagram_service.post_story(
            media_url=story_url,
            media_type=media_type,
            telegram_chat_id=ctx.chat_id,
        )

        story_id = post_result.get("story_id")
        logger.info(f"Posted to Instagram: story_id={story_id}")
        return story_id

    def _record_successful_post(self, ctx: AutopostContext, story_id: str) -> None:
        """Record a successful Instagram post in all relevant tables."""
        self.service.history_repo.create(
            HistoryCreateParams(
                media_item_id=str(ctx.queue_item.media_item_id),
                queue_item_id=ctx.queue_id,
                queue_created_at=ctx.queue_item.created_at,
                queue_deleted_at=datetime.utcnow(),
                scheduled_for=ctx.queue_item.scheduled_for,
                posted_at=datetime.utcnow(),
                status="posted",
                success=True,
                posted_by_user_id=str(ctx.user.id),
                posted_by_telegram_username=ctx.user.telegram_username,
                posting_method="instagram_api",
                instagram_story_id=story_id,
            )
        )
        self.service.media_repo.increment_times_posted(
            str(ctx.queue_item.media_item_id)
        )
        self.service.lock_service.create_lock(str(ctx.queue_item.media_item_id))
        self.service.queue_repo.delete(ctx.queue_id)
        self.service.user_repo.increment_posts(str(ctx.user.id))

    async def _send_success_message(self, ctx: AutopostContext, story_id: str) -> None:
        """Send success message and log interaction after a successful post."""
        verbose = self.service._is_verbose(ctx.chat_id, chat_settings=ctx.chat_settings)
        account_display = await self._get_account_display(ctx)

        if verbose:
            escaped_filename = _escape_markdown(ctx.media_item.file_name)
            caption = (
                f"✅ *Posted to Instagram!*\n\n"
                f"📁 {escaped_filename}\n"
                f"📸 Account: {account_display}\n"
                f"🆔 Story ID: {story_id[:20]}...\n\n"
                f"Posted by: {self.service._get_display_name(ctx.user)}"
            )
        else:
            caption = (
                f"✅ Posted to {account_display} by "
                f"{self.service._get_display_name(ctx.user)}"
            )

        await ctx.query.edit_message_caption(caption=caption, parse_mode="Markdown")

        self.service.interaction_service.log_callback(
            user_id=str(ctx.user.id),
            callback_name="autopost",
            context={
                "queue_item_id": ctx.queue_id,
                "media_id": str(ctx.queue_item.media_item_id),
                "media_filename": ctx.media_item.file_name,
                "instagram_story_id": story_id,
                "dry_run": False,
                "success": True,
            },
            telegram_chat_id=ctx.query.message.chat_id,
            telegram_message_id=ctx.query.message.message_id,
        )

        self.service.interaction_service.log_bot_response(
            response_type="caption_update",
            context={
                "caption": caption,
                "action": "autopost_success",
                "media_filename": ctx.media_item.file_name,
                "instagram_story_id": story_id,
                "edited": True,
            },
            telegram_chat_id=ctx.query.message.chat_id,
            telegram_message_id=ctx.query.message.message_id,
        )

        logger.info(
            f"Auto-posted to Instagram by {self.service._get_display_name(ctx.user)}: "
            f"{ctx.media_item.file_name} (story_id={story_id})"
        )

    async def _handle_autopost_error(self, ctx: AutopostContext, e: Exception) -> None:
        """Handle auto-post failure: show error message with recovery options."""
        logger.error(f"Auto-post failed: {e}", exc_info=True)

        user_msg = self._get_user_friendly_error(e)
        caption = (
            f"❌ *Auto Post Failed*\n\n"
            f"{user_msg}\n\n"
            f"You can try again or use manual posting."
        )

        reply_markup = build_error_recovery_keyboard(
            ctx.queue_id, enable_instagram_api=settings.ENABLE_INSTAGRAM_API
        )

        await ctx.query.edit_message_caption(
            caption=caption,
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

        self.service.interaction_service.log_callback(
            user_id=str(ctx.user.id),
            callback_name="autopost",
            context={
                "queue_item_id": ctx.queue_id,
                "media_id": str(ctx.queue_item.media_item_id),
                "media_filename": ctx.media_item.file_name,
                "dry_run": False,
                "success": False,
                "error": str(e)[:200],
            },
            telegram_chat_id=ctx.query.message.chat_id,
            telegram_message_id=ctx.query.message.message_id,
        )

    @staticmethod
    def _get_user_friendly_error(e: Exception) -> str:
        """Map internal exceptions to user-friendly error messages."""
        if isinstance(e, MediaUploadError):
            return "Failed to prepare media for Instagram. This is a server issue — please contact the admin."
        if isinstance(e, RateLimitError):
            return "Instagram rate limit reached. Please try again later."
        if isinstance(e, TokenExpiredError):
            return "Instagram connection has expired. Please reconnect your account in Settings."
        if isinstance(e, InstagramAPIError):
            return f"Instagram rejected the post: {e}"
        return f"An unexpected error occurred: {str(e)[:150]}"
