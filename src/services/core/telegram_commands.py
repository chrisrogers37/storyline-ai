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

    MAX_LOCKS_DISPLAY = 10

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
        media_count = len(self.service.media_repo.get_all(is_active=True))
        locked_count = len(self.service.lock_repo.get_permanent_locks())

        next_post_str = self._get_next_post_display()
        last_posted = self._get_last_posted_display(recent_posts)

        dry_run_status = "🧪 ON" if settings.DRY_RUN_MODE else "🚀 OFF"
        pause_status = "📦 Delivery OFF" if self.service.is_paused else "📦 Delivery ON"
        ig_status = self._get_instagram_api_status()
        sync_status_line = self._get_sync_status_line(chat_id)

        status_msg = (
            f"📊 *Storyline AI Status*\n\n"
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
            f"📁 Library: {media_count} active\n"
            f"🔒 Locked: {locked_count}\n\n"
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
            "*Queue Commands:*\n"
            "/queue - View upcoming posts\n"
            "/next - Force send next post\n"
            "/schedule N - Add N days to queue\n"
            "/reset - Reset queue (clear all pending)\n\n"
            "*Control Commands:*\n"
            "/setup - Quick settings + open full setup wizard\n"
            "/pause - Turn delivery off (auto-reschedules queue)\n"
            "/resume - Turn delivery on\n"
            "/dryrun - Toggle dry run mode\n"
            "/sync - Sync media from source\n"
            "/backfill - Backfill media from Instagram\n"
            "/status - System health check\n"
            "/cleanup - Delete recent bot messages\n\n"
            "*Info Commands:*\n"
            "/stats - Media library statistics\n"
            "/history N - Show last N posts\n"
            "/locks - View locked items\n"
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

    async def handle_dryrun(self, update, context):
        """
        Handle /dryrun command - toggle or check dry run mode.

        Usage:
            /dryrun - Show current status
            /dryrun on - Enable dry run mode
            /dryrun off - Disable dry run mode
        """
        user = self.service._get_or_create_user(update.effective_user)
        chat_id = update.effective_chat.id

        # Get current setting from database
        chat_settings = self.service.settings_service.get_settings(chat_id)

        # Check if user provided an argument
        args = context.args if context.args else []

        if len(args) == 0:
            # No argument - show current status from database
            status = "ON" if chat_settings.dry_run_mode else "OFF"
            emoji = "🧪" if chat_settings.dry_run_mode else "🚀"
            await update.message.reply_text(
                f"{emoji} Dry Run Mode: {status}\n\n"
                f"Use /dryrun on or /dryrun off to change."
            )
        elif args[0].lower() == "on":
            # Update database setting
            self.service.settings_service.update_setting(
                chat_id, "dry_run_mode", True, user
            )
            await update.message.reply_text(
                "🧪 Dry Run Mode: ON\n\n"
                "• Auto Post will upload to Cloudinary but NOT post to Instagram\n"
                "• Automatic posting loop will skip Instagram API calls\n"
                "• Use /dryrun off to resume real posting"
            )
            logger.info(
                f"Dry run mode ENABLED by {self.service._get_display_name(user)}"
            )
        elif args[0].lower() == "off":
            # Update database setting
            self.service.settings_service.update_setting(
                chat_id, "dry_run_mode", False, user
            )
            await update.message.reply_text(
                "🚀 Dry Run Mode: OFF\n\n"
                "• Auto Post will now post to Instagram for real\n"
                "• Automatic posting loop is active\n"
                "• Use /dryrun on to test without posting"
            )
            logger.info(
                f"Dry run mode DISABLED by {self.service._get_display_name(user)}"
            )
        else:
            await update.message.reply_text(
                "❓ Invalid argument.\n\n"
                "Usage:\n"
                "• /dryrun - Show current status\n"
                "• /dryrun on - Enable dry run\n"
                "• /dryrun off - Disable dry run"
            )

        # Log interaction
        self.service.interaction_service.log_command(
            user_id=str(user.id),
            command="/dryrun",
            context={"args": args},
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

    async def handle_schedule(self, update, context):
        """Handle /schedule command - add more days to queue."""
        user = self.service._get_or_create_user(update.effective_user)

        # Parse days argument
        try:
            days = int(context.args[0]) if context.args else 7
            if days < 1 or days > 30:
                raise ValueError("Days must be between 1 and 30")
        except (ValueError, IndexError):
            await update.message.reply_text(
                "⚠️ *Usage:* /schedule N\n\n"
                "Where N is number of days (1-30).\n"
                "Example: /schedule 7",
                parse_mode="Markdown",
            )
            return

        # Import scheduler service here to avoid circular imports
        from src.services.core.scheduler import SchedulerService

        with SchedulerService() as scheduler:
            try:
                result = scheduler.create_schedule(
                    days=days,
                    telegram_chat_id=update.effective_chat.id,
                )
                await update.message.reply_text(
                    f"📅 *Schedule Created*\n\n"
                    f"✅ Scheduled: {result['scheduled']} posts\n"
                    f"⏭️ Skipped: {result['skipped']} (locked/queued)\n"
                    f"📊 Total slots: {result['total_slots']}",
                    parse_mode="Markdown",
                )
                logger.info(
                    f"Schedule created by {self.service._get_display_name(user)}: {days} days, {result['scheduled']} posts"
                )
            except Exception as e:
                await update.message.reply_text(
                    f"❌ *Error*\n\n{str(e)}", parse_mode="Markdown"
                )
                logger.error(f"Schedule creation failed: {e}")

        self.service.interaction_service.log_command(
            user_id=str(user.id),
            command="/schedule",
            context={"days": days},
            telegram_chat_id=update.effective_chat.id,
            telegram_message_id=update.message.message_id,
        )

    async def handle_stats(self, update, context):
        """Handle /stats command - show media library statistics."""
        user = self.service._get_or_create_user(update.effective_user)

        # Gather stats
        all_media = self.service.media_repo.get_all(is_active=True)
        total = len(all_media)
        never_posted = len([m for m in all_media if m.times_posted == 0])
        posted_once = len([m for m in all_media if m.times_posted == 1])
        posted_multiple = len([m for m in all_media if m.times_posted > 1])

        # Lock stats
        permanent_locks = len(self.service.lock_repo.get_permanent_locks())
        temp_locks = len(
            [m for m in all_media if self.service.lock_repo.is_locked(str(m.id))]
        )

        # Queue stats
        pending_count = self.service.queue_repo.count_pending()

        stats_msg = (
            f"📊 *Media Library Stats*\n\n"
            f"*Library:*\n"
            f"├─ Total active: {total}\n"
            f"├─ Never posted: {never_posted}\n"
            f"├─ Posted once: {posted_once}\n"
            f"└─ Posted 2+: {posted_multiple}\n\n"
            f"*Locks:*\n"
            f"├─ Permanent (rejected): {permanent_locks}\n"
            f"└─ Temporary (30-day): {temp_locks - permanent_locks}\n\n"
            f"*Queue:*\n"
            f"└─ Pending posts: {pending_count}"
        )

        await update.message.reply_text(stats_msg, parse_mode="Markdown")

        self.service.interaction_service.log_command(
            user_id=str(user.id),
            command="/stats",
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

    async def handle_locks(self, update, context):
        """Handle /locks command - show locked items."""
        user = self.service._get_or_create_user(update.effective_user)

        permanent = self.service.lock_repo.get_permanent_locks()

        if not permanent:
            await update.message.reply_text(
                "🔓 *No Permanent Locks*\n\nNo items have been permanently rejected.",
                parse_mode="Markdown",
            )
            return

        lines = [f"🔒 *Permanently Locked* ({len(permanent)})\n"]
        for i, lock in enumerate(permanent[: self.MAX_LOCKS_DISPLAY], 1):
            media = self.service.media_repo.get_by_id(str(lock.media_item_id))
            filename = media.file_name if media else "Unknown"
            lines.append(f"{i}. {filename[:30]}")

        if len(permanent) > self.MAX_LOCKS_DISPLAY:
            lines.append(f"\n... and {len(permanent) - self.MAX_LOCKS_DISPLAY} more")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

        self.service.interaction_service.log_command(
            user_id=str(user.id),
            command="/locks",
            context={"total_locks": len(permanent)},
            telegram_chat_id=update.effective_chat.id,
            telegram_message_id=update.message.message_id,
        )

    async def handle_reset(self, update, context):
        """Handle /reset command - reset posting queue with confirmation."""
        user = self.service._get_or_create_user(update.effective_user)

        pending_count = self.service.queue_repo.count_pending()

        if pending_count == 0:
            await update.message.reply_text(
                "📭 *Queue Already Empty*", parse_mode="Markdown"
            )
            return

        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ Yes, Clear All", callback_data="clear:confirm"
                ),
                InlineKeyboardButton("❌ Cancel", callback_data="clear:cancel"),
            ]
        ]

        await update.message.reply_text(
            f"⚠️ *Clear Queue?*\n\n"
            f"This will remove all {pending_count} pending posts.\n"
            f"Media items will remain in the library.\n\n"
            f"This cannot be undone.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

        self.service.interaction_service.log_command(
            user_id=str(user.id),
            command="/reset",
            context={"pending_count": pending_count},
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

    async def handle_backfill(self, update, context):
        """Handle /backfill command -- trigger Instagram media backfill.

        Usage:
            /backfill          - Backfill all feed posts
            /backfill 50       - Backfill up to 50 items
            /backfill dry      - Preview without downloading
            /backfill 50 dry   - Preview up to 50 items
        """
        user = self.service._get_or_create_user(update.effective_user)
        chat_id = update.effective_chat.id

        # Parse optional arguments
        args = context.args or []
        limit = None
        dry_run = False

        for arg in args:
            if arg.isdigit():
                limit = int(arg)
            elif arg.lower() == "dry":
                dry_run = True

        mode = "DRY RUN" if dry_run else "LIVE"
        limit_str = str(limit) if limit else "all"

        status_msg = await update.message.reply_text(
            f"🔄 *Instagram Media Backfill* ({mode})\n\n"
            f"Fetching feed posts from Instagram...\n"
            f"Limit: {limit_str}\n\n"
            f"_This may take a while for large accounts._",
            parse_mode="Markdown",
        )

        try:
            from src.services.integrations.instagram_backfill import (
                InstagramBackfillService,
            )

            backfill_service = InstagramBackfillService()
            result = await backfill_service.backfill(
                telegram_chat_id=chat_id,
                limit=limit,
                media_type="feed",
                dry_run=dry_run,
                triggered_by="telegram",
            )

            action = "Would download" if dry_run else "Downloaded"
            status_emoji = "🏁" if not dry_run else "👀"

            lines = [
                f"{status_emoji} *Backfill {'Preview' if dry_run else 'Complete'}*\n",
                f"📥 {action}: {result.downloaded}",
                f"⏭️ Skipped (duplicate): {result.skipped_duplicate}",
                f"🚫 Skipped (unsupported): {result.skipped_unsupported}",
            ]

            if result.failed > 0:
                lines.append(f"❌ Failed: {result.failed}")

            lines.append(f"📊 Total API items: {result.total_api_items}")

            if result.error_details:
                lines.append("\n⚠️ *Errors:*")
                for e in result.error_details[:3]:
                    lines.append(f"  - {e[:80]}")

            await status_msg.edit_text(
                "\n".join(lines),
                parse_mode="Markdown",
            )

        except Exception as e:
            await status_msg.edit_text(
                f"❌ *Backfill failed*\n\n{str(e)[:200]}",
                parse_mode="Markdown",
            )
            logger.error(f"Backfill from Telegram failed: {e}", exc_info=True)

        self.service.interaction_service.log_command(
            user_id=str(user.id),
            command="/backfill",
            telegram_chat_id=chat_id,
            telegram_message_id=update.message.message_id,
        )

    async def handle_connect(self, update, context):
        """Handle /connect command - generate Instagram OAuth link.

        Usage:
            /connect - Get a link to connect an Instagram account via OAuth
        """
        user = self.service._get_or_create_user(update.effective_user)
        chat_id = update.effective_chat.id

        from src.services.core.oauth_service import OAuthService

        oauth_service = OAuthService()
        try:
            auth_url = oauth_service.generate_authorization_url(chat_id)

            keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("Connect Instagram", url=auth_url)]]
            )

            await update.message.reply_text(
                "\U0001f4f8 *Connect Instagram Account*\n\n"
                "Click the button below to authorize Storyline AI "
                "to post Stories on your behalf.\n\n"
                "_This link expires in 10 minutes._",
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
        except ValueError as e:
            await update.message.reply_text(
                f"\u26a0\ufe0f OAuth not configured: {e}\n\n"
                "Contact your admin to set up FACEBOOK_APP_ID, "
                "FACEBOOK_APP_SECRET, and OAUTH_REDIRECT_BASE_URL.",
            )
        finally:
            oauth_service.close()

        self.service.interaction_service.log_command(
            user_id=str(user.id),
            command="/connect",
            telegram_chat_id=chat_id,
            telegram_message_id=update.message.message_id,
        )

    async def handle_connect_drive(self, update, context):
        """Handle /connect_drive command - generate Google Drive OAuth link.

        Usage:
            /connect_drive - Get a link to connect your Google Drive
        """
        user = self.service._get_or_create_user(update.effective_user)
        chat_id = update.effective_chat.id

        from src.services.integrations.google_drive_oauth import GoogleDriveOAuthService

        gdrive_service = GoogleDriveOAuthService()
        try:
            auth_url = gdrive_service.generate_authorization_url(chat_id)

            keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("Connect Google Drive", url=auth_url)]]
            )

            await update.message.reply_text(
                "\U0001f4c1 *Connect Google Drive*\n\n"
                "Click the button below to authorize Storyline AI "
                "to read media from your Google Drive.\n\n"
                "_This link expires in 10 minutes._",
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
        except ValueError as e:
            await update.message.reply_text(
                f"\u26a0\ufe0f Google Drive OAuth not configured: {e}\n\n"
                "Contact your admin to set up GOOGLE_CLIENT_ID, "
                "GOOGLE_CLIENT_SECRET, and OAUTH_REDIRECT_BASE_URL.",
            )
        finally:
            gdrive_service.close()

        self.service.interaction_service.log_command(
            user_id=str(user.id),
            command="/connect_drive",
            telegram_chat_id=chat_id,
            telegram_message_id=update.message.message_id,
        )
