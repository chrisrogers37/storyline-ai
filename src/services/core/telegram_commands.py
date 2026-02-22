"""Telegram command handlers - all /command handlers for the bot."""

from __future__ import annotations

from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from src.config.settings import settings
from src.services.core.telegram_service import _escape_markdown
from src.utils.logger import logger

from datetime import datetime
import asyncio

if TYPE_CHECKING:
    from src.services.core.telegram_service import TelegramService


class TelegramCommandHandlers:
    """Handles all /command interactions for the Telegram bot.

    Uses composition pattern: receives a TelegramService reference
    and accesses shared state via self.service.
    """

    def __init__(self, service: TelegramService):
        self.service = service

    async def handle_start(self, update, context):
        """Handle /start command.

        New users: show onboarding Mini App button.
        Returning users: show dashboard summary.
        """
        user = self.service._get_or_create_user(update.effective_user)
        chat_id = update.effective_chat.id

        # Check onboarding status
        from src.services.core.settings_service import SettingsService

        settings_service = SettingsService()
        try:
            chat_settings = settings_service.get_settings(chat_id)
            onboarding_done = chat_settings.onboarding_completed
        finally:
            settings_service.close()

        if settings.OAUTH_REDIRECT_BASE_URL:
            # Always show Mini App button — app decides what to render
            webapp_url = (
                f"{settings.OAUTH_REDIRECT_BASE_URL}/webapp/onboarding"
                f"?chat_id={chat_id}"
            )

            if onboarding_done:
                button_text = "Open Storyline"
                message_text = (
                    "Welcome back to *Storyline AI*\\!\n\n"
                    "Tap the button below to view your dashboard "
                    "and manage your settings\\."
                )
            else:
                button_text = "Open Setup Wizard"
                message_text = (
                    "Welcome to *Storyline AI*\\!\n\n"
                    "Let's get you set up\\. Tap the button below to "
                    "connect your accounts and configure your posting schedule\\."
                )

            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            button_text,
                            web_app=WebAppInfo(url=webapp_url),
                        )
                    ]
                ]
            )
            await update.message.reply_text(
                message_text,
                parse_mode="MarkdownV2",
                reply_markup=keyboard,
            )
        else:
            # Fallback when OAUTH_REDIRECT_BASE_URL not configured
            await update.message.reply_text(
                "👋 *Storyline AI Bot*\n\n"
                "Commands:\n"
                "/queue - View upcoming posts\n"
                "/next - Force send next post\n"
                "/status - Check system status\n"
                "/help - Show all commands",
                parse_mode="Markdown",
            )

        # Log interaction
        self.service.interaction_service.log_command(
            user_id=str(user.id),
            command="/start",
            telegram_chat_id=chat_id,
            telegram_message_id=update.message.message_id,
        )

    async def handle_status(self, update, context):
        """Handle /status command."""
        user = self.service._get_or_create_user(update.effective_user)
        chat_id = update.effective_chat.id

        # Gather stats
        pending_count = self.service.queue_repo.count_pending()
        recent_posts = self.service.history_repo.get_recent_posts(hours=24)
        all_media = self.service.media_repo.get_all(is_active=True)
        media_count = len(all_media)
        never_posted = len([m for m in all_media if m.times_posted == 0])
        posted_once = len([m for m in all_media if m.times_posted == 1])
        posted_multiple = len([m for m in all_media if m.times_posted > 1])
        locked_count = len(self.service.lock_repo.get_permanent_locks())

        next_post_str = self._get_next_post_display()
        last_posted = self._get_last_posted_display(recent_posts)

        dry_run_status = "🧪 ON" if settings.DRY_RUN_MODE else "🚀 OFF"
        pause_status = "📦 Delivery OFF" if self.service.is_paused else "📦 Delivery ON"
        ig_status = self._get_instagram_api_status()
        sync_status_line = self._get_sync_status_line(chat_id)

        setup_section = self._get_setup_status(chat_id)

        status_msg = (
            f"📊 *Storyline AI Status*\n\n"
            f"{setup_section}\n\n"
            f"*System:*\n"
            f"🤖 Bot: Online\n"
            f"⏯️ Posting: {pause_status}\n"
            f"🧪 Dry Run: {dry_run_status}\n\n"
            f"*Instagram API:*\n"
            f"📸 {ig_status}\n\n"
            f"*Media Source:*\n"
            f"{sync_status_line}\n\n"
            f"*Queue & Media:*\n"
            f"📋 Queue: {pending_count} pending\n"
            f"🔒 Locked: {locked_count}\n\n"
            f"*Library:*\n"
            f"📁 Total: {media_count} active\n"
            f"🆕 Never posted: {never_posted}\n"
            f"1️⃣ Posted once: {posted_once}\n"
            f"🔁 Posted 2+: {posted_multiple}\n\n"
            f"*Activity:*\n"
            f"⏰ Next: {next_post_str}\n"
            f"📤 Last: {last_posted}\n"
            f"📈 24h: {len(recent_posts)} posts"
        )

        await update.message.reply_text(status_msg, parse_mode="Markdown")

        self.service.interaction_service.log_command(
            user_id=str(user.id),
            command="/status",
            context={
                "queue_size": pending_count,
                "media_count": media_count,
                "posts_24h": len(recent_posts),
            },
            telegram_chat_id=chat_id,
            telegram_message_id=update.message.message_id,
        )

    # ==================== Status Helpers ====================

    def _get_next_post_display(self) -> str:
        """Get formatted display for next scheduled post time."""
        next_items = self.service.queue_repo.get_pending(limit=1)
        if next_items:
            return next_items[0].scheduled_for.strftime("%H:%M UTC")
        return "None scheduled"

    def _get_last_posted_display(self, recent_posts) -> str:
        """Get formatted display for last post time."""
        if recent_posts:
            time_diff = datetime.utcnow() - recent_posts[0].posted_at
            hours = int(time_diff.total_seconds() / 3600)
            return f"{hours}h ago" if hours > 0 else "< 1h ago"
        return "Never"

    def _get_instagram_api_status(self) -> str:
        """Get formatted Instagram API status string."""
        if settings.ENABLE_INSTAGRAM_API:
            from src.services.integrations.instagram_api import InstagramAPIService

            with InstagramAPIService() as ig_service:
                rate_remaining = ig_service.get_rate_limit_remaining()
            return f"✅ Enabled ({rate_remaining}/{settings.INSTAGRAM_POSTS_PER_HOUR} remaining)"
        return "❌ Disabled"

    def _get_sync_status_line(self, chat_id) -> str:
        """Get formatted media sync status (catches all exceptions internally)."""
        try:
            from src.services.core.media_sync import MediaSyncService

            sync_service = MediaSyncService()
            last_sync = sync_service.get_last_sync_info()
            chat_settings = self.service.settings_service.get_settings(chat_id)

            if not chat_settings.media_sync_enabled:
                return "🔄 Media Sync: ❌ Disabled"
            if not last_sync:
                return "🔄 Media Sync: ⏳ No syncs yet"
            if last_sync["success"]:
                result = last_sync.get("result", {}) or {}
                new_count = result.get("new", 0)
                total = sum(
                    result.get(k, 0)
                    for k in [
                        "new",
                        "updated",
                        "deactivated",
                        "reactivated",
                        "unchanged",
                    ]
                )
                return (
                    f"🔄 Media Sync: ✅ OK"
                    f"\n   └─ Last: {last_sync['started_at'][:16]} "
                    f"({total} items, {new_count} new)"
                )
            return (
                f"🔄 Media Sync: ⚠️ Last sync failed"
                f"\n   └─ {last_sync.get('started_at', 'N/A')[:16]}"
            )
        except Exception:
            return "🔄 Media Sync: ❓ Check failed"

    # ==================== Setup Status Helpers ====================

    def _get_setup_status(self, chat_id: int) -> str:
        """Build setup completion section for /status output.

        Each _check_* method returns (display_line, is_configured).
        Check failures count as "missing" to nudge users toward /start.
        """
        lines = ["*Setup Status:*"]
        checks = [
            self._check_instagram_setup(chat_id),
            self._check_gdrive_setup(chat_id),
            self._check_media_setup(chat_id),
            self._check_schedule_setup(chat_id),
            self._check_delivery_setup(chat_id),
        ]

        missing = 0
        for line_text, is_configured in checks:
            lines.append(line_text)
            if not is_configured:
                missing += 1

        if missing > 0:
            lines.append("\n_Use /start to configure missing items._")

        return "\n".join(lines)

    def _check_instagram_setup(self, chat_id: int) -> tuple[str, bool]:
        """Check Instagram account connection for setup status."""
        try:
            active_account = self.service.ig_account_service.get_active_account(chat_id)
            if active_account and active_account.instagram_username:
                return (
                    f"├── 📸 Instagram: ✅ Connected (@{active_account.instagram_username})",
                    True,
                )
            elif active_account:
                return (
                    f"├── 📸 Instagram: ✅ Connected ({active_account.display_name})",
                    True,
                )
            return ("├── 📸 Instagram: ⚠️ Not connected", False)
        except Exception:
            return ("├── 📸 Instagram: ❓ Check failed", False)

    def _check_gdrive_setup(self, chat_id: int) -> tuple[str, bool]:
        """Check Google Drive OAuth connection for setup status."""
        try:
            from src.repositories.token_repository import TokenRepository

            chat_settings = self.service.settings_service.get_settings(chat_id)
            if not chat_settings:
                return ("├── 📁 Google Drive: ⚠️ Not connected", False)

            token_repo = TokenRepository()
            try:
                gdrive_token = token_repo.get_token_for_chat(
                    "google_drive", "oauth_access", str(chat_settings.id)
                )
                if gdrive_token:
                    email = None
                    if gdrive_token.token_metadata:
                        email = gdrive_token.token_metadata.get("email")
                    if email:
                        return (
                            f"├── 📁 Google Drive: ✅ Connected ({email})",
                            True,
                        )
                    return ("├── 📁 Google Drive: ✅ Connected", True)
                return ("├── 📁 Google Drive: ⚠️ Not connected", False)
            finally:
                token_repo.close()
        except Exception:
            return ("├── 📁 Google Drive: ❓ Check failed", False)

    def _check_media_setup(self, chat_id: int) -> tuple[str, bool]:
        """Check media folder configuration and library size."""
        try:
            media_count = len(self.service.media_repo.get_all(is_active=True))
            if media_count > 0:
                return (f"├── 📂 Media Library: ✅ {media_count} files", True)

            # No media indexed — check if source is configured (per-chat)
            chat_settings = self.service.settings_service.get_settings(chat_id)
            if chat_settings and chat_settings.media_source_root:
                return (
                    "├── 📂 Media Library: ⚠️ Configured (0 files — run /sync)",
                    False,
                )
            return ("├── 📂 Media Library: ⚠️ Not configured", False)
        except Exception:
            return ("├── 📂 Media Library: ❓ Check failed", False)

    def _check_schedule_setup(self, chat_id: int) -> tuple[str, bool]:
        """Check schedule configuration for setup status."""
        try:
            chat_settings = self.service.settings_service.get_settings(chat_id)
            ppd = chat_settings.posts_per_day
            start = chat_settings.posting_hours_start
            end = chat_settings.posting_hours_end
            return (
                f"├── 📅 Schedule: ✅ {ppd}/day, {start:02d}:00-{end:02d}:00 UTC",
                True,
            )
        except Exception:
            return ("├── 📅 Schedule: ❓ Check failed", False)

    def _check_delivery_setup(self, chat_id: int) -> tuple[str, bool]:
        """Check delivery mode (dry run / paused) for setup status."""
        try:
            chat_settings = self.service.settings_service.get_settings(chat_id)
            if chat_settings.is_paused:
                return ("└── 📦 Delivery: ⏸️ PAUSED", True)
            if chat_settings.dry_run_mode:
                return ("└── 📦 Delivery: 🧪 Dry Run (not posting)", True)
            return ("└── 📦 Delivery: ✅ Live", True)
        except Exception:
            return ("└── 📦 Delivery: ❓ Check failed", False)

    async def handle_queue(self, update, context):
        """Handle /queue command - show upcoming scheduled posts."""
        user = self.service._get_or_create_user(update.effective_user)

        # Get ALL pending queue items (not just due ones)
        all_pending = self.service.queue_repo.get_all(status="pending")
        total_count = len(all_pending)
        queue_items = all_pending[:10]  # Show first 10

        if not queue_items:
            await update.message.reply_text(
                "📭 *Queue Empty*\n\nNo posts scheduled.", parse_mode="Markdown"
            )
        else:
            lines = [f"📅 *Upcoming Queue* ({len(queue_items)} of {total_count})\n"]

            for i, item in enumerate(queue_items, 1):
                # Get media info
                media_item = self.service.media_repo.get_by_id(str(item.media_item_id))
                filename = media_item.file_name if media_item else "Unknown"
                category = (
                    media_item.category if media_item and media_item.category else "-"
                )

                # Escape markdown special characters in dynamic content
                filename = _escape_markdown(filename)
                category = _escape_markdown(category)

                # Format scheduled time
                scheduled = item.scheduled_for.strftime("%b %d %H:%M UTC")

                lines.append(f"{i}. 🕐 {scheduled}")
                lines.append(f"    📁 {filename} ({category})\n")

            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

        # Log interaction
        self.service.interaction_service.log_command(
            user_id=str(user.id),
            command="/queue",
            context={
                "items_shown": len(queue_items),
                "total_queue": total_count,
            },
            telegram_chat_id=update.effective_chat.id,
            telegram_message_id=update.message.message_id,
        )

    async def handle_next(self, update, context):
        """
        Handle /next command - force send next scheduled post immediately.

        Uses the shared force_post_next() method which:
        1. Gets the earliest pending item
        2. Shifts all subsequent items forward by one slot
        3. Sends to Telegram with ⚡ indicator
        """
        user = self.service._get_or_create_user(update.effective_user)

        # Use shared force_post_next() method (lazy import to avoid circular import)
        from src.services.core.posting import PostingService

        with PostingService() as posting_service:
            result = await posting_service.force_post_next(
                user_id=str(user.id),
                triggered_by="telegram",
                force_sent_indicator=True,  # Shows ⚡ in caption
            )

        if not result["success"]:
            if result["error"] == "No pending items in queue":
                await update.message.reply_text(
                    "📭 *Queue Empty*\n\nNo posts to send.", parse_mode="Markdown"
                )
            elif result["error"] == "Media item not found":
                await update.message.reply_text(
                    "⚠️ *Error*\n\nMedia item not found.", parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(
                    "❌ *Failed to send*\n\nCheck logs for details.",
                    parse_mode="Markdown",
                )
            return

        # Success - log interaction
        media_item = result["media_item"]
        shifted_count = result["shifted_count"]

        self.service.interaction_service.log_command(
            user_id=str(user.id),
            command="/next",
            context={
                "queue_item_id": result["queue_item_id"],
                "media_id": str(media_item.id) if media_item else None,
                "media_filename": media_item.file_name if media_item else None,
                "success": True,
                "shifted_count": shifted_count,
            },
            telegram_chat_id=update.effective_chat.id,
            telegram_message_id=update.message.message_id,
        )

        shift_msg = f" (shifted {shifted_count} items)" if shifted_count > 0 else ""
        logger.info(
            f"Force-sent next post by {self.service._get_display_name(user)}: "
            f"{media_item.file_name}{shift_msg}"
        )

    async def handle_help(self, update, context):
        """Handle /help command."""
        user = self.service._get_or_create_user(update.effective_user)

        help_text = (
            "📖 *Storyline AI Help*\n\n"
            "*Daily Commands:*\n"
            "/queue - View upcoming posts\n"
            "/next - Send next post now\n"
            "/status - System health & overview\n"
            "/history - Recent post history\n\n"
            "*Control Commands:*\n"
            "/pause - Pause delivery\n"
            "/resume - Resume delivery\n"
            "/setup - Quick settings & toggles\n"
            "/sync - Sync media from source\n"
            "/cleanup - Delete recent bot messages\n\n"
            "*Getting Started:*\n"
            "/start - Open setup wizard\n"
            "/help - Show this help\n\n"
            "*Button Actions:*\n"
            "🤖 Auto Post - Post via Instagram API\n"
            "✅ Posted - Mark as posted (manual)\n"
            "⏭️ Skip - Skip (requeue later)\n"
            "🚫 Reject - Permanently remove"
        )

        await update.message.reply_text(help_text, parse_mode="Markdown")

        # Log interaction
        self.service.interaction_service.log_command(
            user_id=str(user.id),
            command="/help",
            telegram_chat_id=update.effective_chat.id,
            telegram_message_id=update.message.message_id,
        )

    async def handle_pause(self, update, context):
        """Handle /pause command - pause automatic posting."""
        user = self.service._get_or_create_user(update.effective_user)

        if self.service.is_paused:
            await update.message.reply_text(
                "📦 *Delivery Already OFF*\n\nDelivery is already turned off.\nUse /resume to turn it back on.",
                parse_mode="Markdown",
            )
        else:
            self.service.set_paused(True, user)
            pending_count = self.service.queue_repo.count_pending()
            await update.message.reply_text(
                f"📦 *Delivery OFF*\n\n"
                f"Automatic delivery has been turned off.\n"
                f"📊 {pending_count} posts still in queue.\n"
                f"Overdue items will be auto-rescheduled +24hr.\n\n"
                f"Use /resume to turn delivery back on.\n"
                f"Use /next to manually send posts.",
                parse_mode="Markdown",
            )
            logger.info(f"Posting paused by {self.service._get_display_name(user)}")

        self.service.interaction_service.log_command(
            user_id=str(user.id),
            command="/pause",
            context={"was_paused": self.service.is_paused},
            telegram_chat_id=update.effective_chat.id,
            telegram_message_id=update.message.message_id,
        )

    async def handle_resume(self, update, context):
        """Handle /resume command - resume automatic posting."""
        user = self.service._get_or_create_user(update.effective_user)

        if not self.service.is_paused:
            await update.message.reply_text(
                "📦 *Delivery Already ON*\n\nDelivery is already active.",
                parse_mode="Markdown",
            )
        else:
            # Check for overdue posts
            now = datetime.utcnow()
            all_pending = self.service.queue_repo.get_all(status="pending")
            overdue = [p for p in all_pending if p.scheduled_for < now]
            future = [p for p in all_pending if p.scheduled_for >= now]

            if overdue:
                # Show options for handling overdue posts
                keyboard = [
                    [
                        InlineKeyboardButton(
                            "🔄 Reschedule", callback_data="resume:reschedule"
                        ),
                        InlineKeyboardButton(
                            "🗑️ Clear Overdue", callback_data="resume:clear"
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "▶️ Resume Anyway", callback_data="resume:force"
                        ),
                    ],
                ]
                await update.message.reply_text(
                    f"⚠️ *{len(overdue)} Overdue Posts Found*\n\n"
                    f"These posts were scheduled while delivery was off:\n"
                    f"• {len(overdue)} overdue\n"
                    f"• {len(future)} still scheduled\n\n"
                    f"What would you like to do?",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                )
            else:
                self.service.set_paused(False, user)
                await update.message.reply_text(
                    f"📦 *Delivery ON*\n\n"
                    f"Automatic delivery is now active.\n"
                    f"📊 {len(future)} posts scheduled.",
                    parse_mode="Markdown",
                )
                logger.info(
                    f"Posting resumed by {self.service._get_display_name(user)}"
                )

        self.service.interaction_service.log_command(
            user_id=str(user.id),
            command="/resume",
            telegram_chat_id=update.effective_chat.id,
            telegram_message_id=update.message.message_id,
        )

    async def handle_history(self, update, context):
        """Handle /history command - show recent post history."""
        user = self.service._get_or_create_user(update.effective_user)

        # Parse limit argument
        try:
            limit = int(context.args[0]) if context.args else 5
            limit = min(max(limit, 1), 20)  # Clamp between 1 and 20
        except (ValueError, IndexError):
            limit = 5

        recent = self.service.history_repo.get_recent_posts(hours=168)[
            :limit
        ]  # Last 7 days

        if not recent:
            await update.message.reply_text(
                "📜 *No Recent History*\n\nNo posts in the last 7 days.",
                parse_mode="Markdown",
            )
            return

        lines = [f"📜 *Recent Posts* (last {len(recent)})\n"]
        for post in recent:
            status_emoji = (
                "✅"
                if post.status == "posted"
                else "⏭️"
                if post.status == "skipped"
                else "🚫"
            )
            time_str = post.posted_at.strftime("%b %d %H:%M") if post.posted_at else "?"
            username = (
                f"@{post.posted_by_telegram_username}"
                if post.posted_by_telegram_username
                else "system"
            )
            lines.append(f"{status_emoji} {time_str} - {username}")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

        self.service.interaction_service.log_command(
            user_id=str(user.id),
            command="/history",
            context={"limit": limit, "returned": len(recent)},
            telegram_chat_id=update.effective_chat.id,
            telegram_message_id=update.message.message_id,
        )

    async def handle_cleanup(self, update, context):
        """Handle /cleanup command - delete recent bot messages from chat."""
        user = self.service._get_or_create_user(update.effective_user)
        chat_id = update.effective_chat.id

        # Query database for bot messages from last 48 hours
        bot_messages = self.service.interaction_service.get_deletable_bot_messages(
            chat_id
        )

        if not bot_messages:
            await update.message.reply_text(
                "📭 *No Messages to Clean*\n\n"
                "No bot messages found in the last 48 hours.",
                parse_mode="Markdown",
            )
            return

        deleted_count = 0
        failed_count = 0
        total_messages = len(bot_messages)

        # Delete messages (newest first - already sorted by query)
        for interaction in bot_messages:
            message_id = interaction.telegram_message_id
            if not message_id:
                continue
            try:
                await context.bot.delete_message(
                    chat_id=chat_id,
                    message_id=message_id,
                )
                deleted_count += 1
            except Exception as e:
                # Message might be already deleted or inaccessible
                failed_count += 1
                logger.debug(f"Could not delete message {message_id}: {e}")

        # Send ephemeral confirmation (delete after 5 seconds)
        response_text = (
            f"🧹 *Cleanup Complete*\n\n✅ Deleted: {deleted_count} messages\n"
        )
        if failed_count > 0:
            response_text += (
                f"⚠️ Failed: {failed_count} messages\n(May have been already deleted)"
            )

        response = await update.message.reply_text(response_text, parse_mode="Markdown")

        # Log the command
        self.service.interaction_service.log_command(
            user_id=str(user.id),
            command="/cleanup",
            context={
                "total_found": total_messages,
                "deleted": deleted_count,
                "failed": failed_count,
            },
            telegram_chat_id=chat_id,
            telegram_message_id=update.message.message_id,
        )

        # Delete the confirmation message after 5 seconds
        await asyncio.sleep(5)
        try:
            await response.delete()
            await update.message.delete()  # Also delete the user's /cleanup command
        except Exception:
            pass  # Ignore errors if already deleted

    async def handle_sync(self, update, context):
        """Handle /sync command - trigger manual media sync and report results.

        Usage:
            /sync - Run a manual media sync against the configured provider
        """
        user = self.service._get_or_create_user(update.effective_user)
        chat_id = update.effective_chat.id

        # Check if sync is configured
        source_type = settings.MEDIA_SOURCE_TYPE
        source_root = settings.MEDIA_SOURCE_ROOT

        if not source_root and source_type == "local":
            source_root = settings.MEDIA_DIR

        if not source_root:
            await update.message.reply_text(
                "⚠️ *Media Sync Not Configured*\n\n"
                "No media source root is set.\n"
                "Configure `MEDIA_SOURCE_ROOT` in `.env` or connect a Google Drive.",
                parse_mode="Markdown",
            )
            self.service.interaction_service.log_command(
                user_id=str(user.id),
                command="/sync",
                context={"error": "not_configured"},
                telegram_chat_id=chat_id,
                telegram_message_id=update.message.message_id,
            )
            return

        # Send "syncing..." message
        status_msg = await update.message.reply_text(
            f"🔄 *Syncing media...*\n\n"
            f"Source: `{source_type}`\n"
            f"Root: `{source_root[:40]}{'...' if len(source_root) > 40 else ''}`",
            parse_mode="Markdown",
        )

        try:
            from src.services.core.media_sync import MediaSyncService

            sync_service = MediaSyncService()
            result = sync_service.sync(
                source_type=source_type,
                source_root=source_root,
                triggered_by="telegram",
            )

            # Build result message
            lines = ["✅ *Sync Complete*\n"]

            if result.new > 0:
                lines.append(f"📥 New: {result.new}")
            if result.updated > 0:
                lines.append(f"✏️ Updated: {result.updated}")
            if result.deactivated > 0:
                lines.append(f"🗑️ Removed: {result.deactivated}")
            if result.reactivated > 0:
                lines.append(f"♻️ Restored: {result.reactivated}")

            lines.append(f"📁 Unchanged: {result.unchanged}")

            if result.errors > 0:
                lines.append(f"⚠️ Errors: {result.errors}")

            lines.append(f"\n📊 Total: {result.total_processed}")

            await status_msg.edit_text(
                "\n".join(lines),
                parse_mode="Markdown",
            )

            # Log interaction
            self.service.interaction_service.log_command(
                user_id=str(user.id),
                command="/sync",
                context=result.to_dict(),
                telegram_chat_id=chat_id,
                telegram_message_id=update.message.message_id,
            )

            logger.info(
                f"Manual sync triggered by {self.service._get_display_name(user)}: "
                f"{result.new} new, {result.updated} updated, "
                f"{result.deactivated} deactivated"
            )

        except ValueError as e:
            await status_msg.edit_text(
                f"❌ *Sync Failed*\n\n{str(e)}",
                parse_mode="Markdown",
            )
            logger.error(f"Manual sync failed (config): {e}")

        except Exception as e:
            await status_msg.edit_text(
                f"❌ *Sync Failed*\n\n{str(e)[:200]}",
                parse_mode="Markdown",
            )
            logger.error(f"Manual sync failed: {e}", exc_info=True)

    async def handle_removed_command(self, update, context):
        """Handle removed commands with a helpful redirect message."""
        command = update.message.text.split()[0].split("@")[0]  # Extract /command

        redirects = {
            "/schedule": "Use /settings to manage your posting schedule (Regenerate / +7 Days).",
            "/stats": "Media stats are now included in /status.",
            "/locks": "Lock count is shown in /status. Full list in the dashboard.",
            "/reset": "Use /settings → Regenerate to rebuild your queue.",
            "/dryrun": "Use /settings to toggle dry-run mode.",
            "/backfill": "Use the CLI: storyline-cli backfill-instagram",
            "/connect": "Use /start to open the setup wizard and connect Instagram.",
        }

        message = redirects.get(command, "This command has been removed.")
        await update.message.reply_text(
            f"ℹ️ `{command}` has been retired.\n\n{message}",
            parse_mode="Markdown",
        )
