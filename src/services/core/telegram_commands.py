"""Telegram command handlers - all /command handlers for the bot."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.config.settings import settings
from src.services.core.telegram_utils import build_webapp_button
from src.utils.logger import logger

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

        with SettingsService() as settings_service:
            chat_settings = settings_service.get_settings(chat_id)
            onboarding_done = chat_settings.onboarding_completed

        if settings.OAUTH_REDIRECT_BASE_URL:
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

            button = build_webapp_button(
                text=button_text,
                webapp_url=webapp_url,
                chat_type=update.effective_chat.type,
                chat_id=chat_id,
                user_id=update.effective_user.id,
            )

            keyboard = InlineKeyboardMarkup([[button]])
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
                "/status - System health & overview\n"
                "/next - Force send next post\n"
                "/setup - Quick settings & toggles\n"
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

        cadence_str = self._get_cadence_display(chat_id)
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
            f"🔄 Cadence: {cadence_str}\n"
            f"📤 Last: {last_posted}\n"
            f"📈 24h: {len(recent_posts)} posts"
        )

        # Add "Open Dashboard" button if Mini App URL is configured
        reply_markup = None
        if settings.OAUTH_REDIRECT_BASE_URL:
            webapp_url = (
                f"{settings.OAUTH_REDIRECT_BASE_URL}/webapp/onboarding"
                f"?chat_id={chat_id}"
            )
            button = build_webapp_button(
                text="📊 Open Dashboard",
                webapp_url=webapp_url,
                chat_type=update.effective_chat.type,
                chat_id=chat_id,
                user_id=update.effective_user.id,
            )
            reply_markup = InlineKeyboardMarkup([[button]])

        await update.message.reply_text(
            status_msg, parse_mode="Markdown", reply_markup=reply_markup
        )

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

    def _get_cadence_display(self, chat_id: int) -> str:
        """Get formatted posting cadence string for /status output."""
        try:
            chat_settings = self.service.settings_service.get_settings(chat_id)
            ppd = chat_settings.posts_per_day
            start = chat_settings.posting_hours_start
            end = chat_settings.posting_hours_end
            return f"{ppd}/day, {start:02d}:00-{end:02d}:00 UTC"
        except Exception:
            return "Unknown"

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
        except Exception as e:
            logger.warning(f"Sync status check failed: {type(e).__name__}: {e}")
            return "🔄 Media Sync: ❓ Check failed"

    # ==================== Setup Status Helpers ====================

    def _get_setup_status(self, chat_id: int) -> str:
        """Build setup completion section for /status output.

        Delegates to SetupStateService for data gathering and formatting.
        """
        from src.services.core.setup_state_service import SetupStateService

        with SetupStateService() as setup_service:
            return setup_service.format_setup_status(chat_id)

    async def handle_next(self, update, context):
        """
        Handle /next command - JIT select and send next post immediately.

        Uses SchedulerService.force_send_next() which:
        1. Selects the next eligible media item (JIT)
        2. Creates an in-flight queue item
        3. Sends to Telegram with ⚡ indicator
        4. Updates last_post_sent_at to prevent immediate follow-up
        """
        user = self.service._get_or_create_user(update.effective_user)

        from src.services.core.scheduler import SchedulerService

        with SchedulerService() as scheduler:
            # Inject the current telegram_service for sending
            scheduler.telegram_service = self.service
            result = await scheduler.force_send_next(
                telegram_chat_id=update.effective_chat.id,
                user_id=str(user.id),
                force_sent_indicator=True,  # Shows ⚡ in caption
            )

        if not result.get("posted"):
            error = result.get("error", "")
            if result.get("reason") == "no_eligible_media":
                await update.message.reply_text(
                    "📭 *No Eligible Media*\n\nNo media available to send.",
                    parse_mode="Markdown",
                )
            elif "google_drive" in str(error).lower():
                await self._send_gdrive_reconnect_message(
                    update, update.effective_chat.id
                )
            else:
                await update.message.reply_text(
                    "❌ *Failed to send*\n\nCheck logs for details.",
                    parse_mode="Markdown",
                )
            return

        # Success - log interaction
        media_item = result.get("media_item")

        self.service.interaction_service.log_command(
            user_id=str(user.id),
            command="/next",
            context={
                "queue_item_id": result.get("queue_item_id"),
                "media_id": str(media_item.id) if media_item else None,
                "media_filename": media_item.file_name if media_item else None,
                "success": True,
            },
            telegram_chat_id=update.effective_chat.id,
            telegram_message_id=update.message.message_id,
        )

        logger.info(
            f"Force-sent next post by {self.service._get_display_name(user)}: "
            f"{media_item.file_name if media_item else '?'}"
        )

    async def handle_help(self, update, context):
        """Handle /help command."""
        user = self.service._get_or_create_user(update.effective_user)

        help_text = (
            "📖 *Storyline AI Help*\n\n"
            "*Commands:*\n"
            "/start - Open dashboard & settings\n"
            "/status - System health & overview\n"
            "/next - Send next post now\n"
            "/setup - Quick settings & toggles\n"
            "/cleanup - Delete recent bot messages\n"
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
        except Exception as e:
            logger.debug(f"Could not auto-delete cleanup messages: {e}")

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
            "/queue": "View your queue in the dashboard. Use /start to open it.",
            "/pause": "Use Quick Controls in the dashboard. Use /start to open it.",
            "/resume": "Use Quick Controls in the dashboard. Use /start to open it.",
            "/history": "View recent activity in the dashboard. Use /start to open it.",
            "/sync": "Sync from the dashboard. Use /start to open it.",
        }

        message = redirects.get(command, "This command has been removed.")
        await update.message.reply_text(
            f"ℹ️ `{command}` has been retired.\n\n{message}",
            parse_mode="Markdown",
        )

    async def _send_gdrive_reconnect_message(self, update, chat_id: int) -> None:
        """Send a Google Drive reconnect message with an inline button."""
        text = (
            "⚠️ *Google Drive Disconnected*\n\n"
            "Your Google Drive token has expired or been revoked. "
            "Reconnect to resume posting."
        )

        reply_markup = None
        if settings.OAUTH_REDIRECT_BASE_URL:
            reconnect_url = (
                f"{settings.OAUTH_REDIRECT_BASE_URL}"
                f"/auth/google-drive/start?chat_id={chat_id}"
            )
            reply_markup = InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔗 Reconnect Google Drive", url=reconnect_url)]]
            )

        await update.message.reply_text(
            text, parse_mode="Markdown", reply_markup=reply_markup
        )
