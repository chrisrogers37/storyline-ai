"""Telegram command handlers - all /command handlers for the bot."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
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
        """Handle /start — delegates to StartCommandRouter."""
        await self.service.start_router.handle_start(update, context)

    async def handle_status(self, update, context):
        """Handle /status command.

        All data is scoped to the current chat's tenant (chat_settings_id)
        and all configuration is read from the database, never from env vars.
        """
        chat_id = update.effective_chat.id
        user = self.service._get_or_create_user(
            update.effective_user, telegram_chat_id=chat_id
        )

        # Load tenant-scoped settings from DB (single source of truth)
        chat_settings = self.service.settings_service.get_settings(chat_id)
        cs_id = str(chat_settings.id)

        # Gather stats — all scoped to this tenant
        recent_posts = self.service.history_repo.get_recent_posts(
            hours=24, chat_settings_id=cs_id
        )
        posting_stats = self.service.media_repo.count_by_posting_status(
            chat_settings_id=cs_id
        )
        never_posted = posting_stats["never_posted"]
        posted_count = posting_stats["posted_once"] + posting_stats["posted_multiple"]

        last_posted = self._get_last_posted_display(recent_posts)
        next_post = self._get_next_post_display(chat_settings)
        ig_status = self._get_instagram_api_status(chat_settings, cs_id)
        sync_status_line = self._get_sync_status_line(chat_settings)

        setup_section = self._get_setup_status(chat_id)

        status_msg = (
            f"📊 *Storyline AI Status*\n\n"
            f"{setup_section}\n\n"
            f"*Instagram API:*\n"
            f"📸 {ig_status}\n\n"
            f"*Media Source:*\n"
            f"{sync_status_line}\n\n"
            f"*Library:*\n"
            f"✅ Posted: {posted_count}\n"
            f"🆕 Never posted: {never_posted}\n\n"
            f"*Activity:*\n"
            f"📤 Last: {last_posted}\n"
            f"⏭️ Next: {next_post}\n"
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
                "posted": posted_count,
                "never_posted": never_posted,
                "posts_24h": len(recent_posts),
            },
            telegram_chat_id=chat_id,
            telegram_message_id=update.message.message_id,
        )

    # ==================== Status Helpers ====================

    def _get_last_posted_display(self, recent_posts) -> str:
        """Get formatted display for last post time."""
        if recent_posts:
            time_diff = datetime.now(timezone.utc) - recent_posts[0].posted_at
            hours = int(time_diff.total_seconds() / 3600)
            return f"{hours}h ago" if hours > 0 else "< 1h ago"
        return "Never"

    @staticmethod
    def _get_next_post_display(chat_settings) -> str:
        """Estimate when the next post is due based on JIT scheduler logic.

        Uses the same formula as SchedulerService.is_slot_due():
        next = last_post_sent_at + (window_hours * 3600 / posts_per_day)
        """
        try:
            if chat_settings.is_paused:
                return "Paused"

            start = chat_settings.posting_hours_start
            end = chat_settings.posting_hours_end
            window_hours = (24 - start) + end if end < start else end - start

            if window_hours <= 0 or chat_settings.posts_per_day <= 0:
                return "Not configured"

            interval_seconds = (window_hours * 3600) / chat_settings.posts_per_day

            last_sent = chat_settings.last_post_sent_at
            if not last_sent:
                return "Due now"

            if last_sent.tzinfo is None:
                last_sent = last_sent.replace(tzinfo=timezone.utc)

            next_due = last_sent + timedelta(seconds=interval_seconds)
            now = datetime.now(timezone.utc)

            if next_due <= now:
                return "Due now"

            diff = next_due - now
            hours = int(diff.total_seconds() / 3600)
            minutes = int((diff.total_seconds() % 3600) / 60)
            time_str = f"{next_due.strftime('%H:%M')} UTC"

            if hours > 0:
                return f"~{hours}h {minutes}m ({time_str})"
            return f"~{minutes}m ({time_str})"
        except Exception:
            return "Unknown"

    @staticmethod
    def _get_instagram_api_status(chat_settings, chat_settings_id: str) -> str:
        """Get formatted Instagram API status string.

        Reads enabled state from chat_settings (DB) and scopes
        rate-limit calculation to the tenant.
        """
        if not chat_settings.enable_instagram_api:
            return "❌ Disabled"

        try:
            from src.services.integrations.instagram_api import InstagramAPIService

            with InstagramAPIService() as ig_service:
                rate_remaining = ig_service.get_rate_limit_remaining(
                    chat_settings_id=chat_settings_id,
                )
            return f"✅ Enabled ({rate_remaining}/25 remaining)"
        except Exception:
            return "✅ Enabled (rate limit unknown)"

    @staticmethod
    def _get_sync_status_line(chat_settings) -> str:
        """Get formatted media sync status (catches all exceptions internally)."""
        try:
            from src.services.core.media_sync import MediaSyncService

            sync_service = MediaSyncService()
            last_sync = sync_service.get_last_sync_info()

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
            "/approveall - Approve all pending posts\n"
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
        chat_id = update.effective_chat.id
        user = self.service._get_or_create_user(
            update.effective_user, telegram_chat_id=chat_id
        )

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

    async def handle_approveall(self, update, context):
        """Handle /approveall command — batch approve all pending queue items.

        Shows a summary of pending items and a confirmation button.
        On confirmation, marks each item as posted with history and lock creation.
        """
        chat_id = update.effective_chat.id
        user = self.service._get_or_create_user(
            update.effective_user, telegram_chat_id=chat_id
        )

        chat_settings = self.service.settings_service.get_settings(chat_id)
        cs_id = str(chat_settings.id)

        # Get all pending queue items with media info
        pending_rows = self.service.queue_repo.get_all_with_media(
            status="pending", chat_settings_id=cs_id
        )
        processing_rows = self.service.queue_repo.get_all_with_media(
            status="processing", chat_settings_id=cs_id
        )
        all_items = pending_rows + processing_rows

        if not all_items:
            await update.message.reply_text(
                "📭 *No Pending Posts*\n\nThere are no items waiting for approval.",
                parse_mode="Markdown",
            )
            return

        # Build summary by category
        category_counts: dict[str, int] = {}
        for _item, _file_name, category in all_items:
            cat = category or "uncategorized"
            category_counts[cat] = category_counts.get(cat, 0) + 1

        summary_parts = [
            f"{count} {cat}" for cat, count in sorted(category_counts.items())
        ]
        summary = ", ".join(summary_parts)

        text = (
            f"📋 *Batch Approve — {len(all_items)} pending posts*\n\n"
            f"Categories: {summary}\n"
            f"Mode: mark as posted\n\n"
            f"Approve all {len(all_items)} items?"
        )

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        f"✅ Approve All ({len(all_items)})",
                        callback_data=f"batch_approve:{cs_id}",
                    ),
                    InlineKeyboardButton(
                        "❌ Cancel", callback_data="batch_approve_cancel"
                    ),
                ],
            ]
        )

        await update.message.reply_text(
            text, parse_mode="Markdown", reply_markup=keyboard
        )

        self.service.interaction_service.log_command(
            user_id=str(user.id),
            command="/approveall",
            context={
                "pending_count": len(all_items),
                "categories": category_counts,
            },
            telegram_chat_id=chat_id,
            telegram_message_id=update.message.message_id,
        )

    async def handle_removed_command(self, update, context):
        """Handle removed commands with a helpful redirect message."""
        command = update.message.text.split()[0].split("@")[0]  # Extract /command

        redirects = {
            "/schedule": "Use /settings to adjust posting cadence, or the dashboard for full controls.",
            "/stats": "Media stats are now included in /status.",
            "/locks": "Lock count is shown in /status. Full list in the dashboard.",
            "/reset": "The JIT scheduler manages the queue automatically.",
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

    # ==================== Multi-Account Commands ====================

    async def handle_link(self, update, context):
        """Handle /link — manual group-to-instance linking fallback.

        Used when the bot is already in the group (so startgroup/my_chat_member
        won't fire). Links the current group to the user's pending onboarding session.

        Note: Does not accept a <session_id> argument (intentional deviation from spec).
        Session lookup is always scoped to the calling user.
        """
        chat_id = update.effective_chat.id
        is_group = update.effective_chat.type in ("group", "supergroup")

        if not is_group:
            await update.message.reply_text(
                "Run /link in the group chat you want to link."
            )
            return

        user = self.service._get_or_create_user(
            update.effective_user, telegram_chat_id=chat_id
        )

        # Verify bot is actually a member of this group
        try:
            bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
            if bot_member.status in ("left", "kicked"):
                await update.message.reply_text(
                    "⚠️ I'm not a member of this group. "
                    "Add me first, then run /link again."
                )
                return
        except Exception:
            await update.message.reply_text(
                "⚠️ I can't verify my membership in this group. "
                "Try removing and re-adding me."
            )
            return

        from src.services.core.conversation_service import ConversationService

        with ConversationService() as conv_service:
            session = conv_service.get_current_session(str(user.id))

        if not session or session.step != "awaiting_group":
            await update.message.reply_text(
                "⚠️ No pending instance setup found.\n\n"
                "Start a new instance by DMing me and running /start."
            )
            return

        with ConversationService() as conv_service:
            conv_service.link_group_to_instance(
                session=session,
                chat_id=chat_id,
                user_id=str(user.id),
                membership_repo=self.service.membership_repo,
            )

        name = session.pending_instance_name or "this group"
        await update.message.reply_text(
            f"✅ *{name}* is linked to this group!\n\n"
            "Use /status to check health, or /setup to configure.",
            parse_mode="Markdown",
        )

        # Notify in DM
        try:
            await self.service.bot.send_message(
                chat_id=update.effective_user.id,
                text=(
                    f"✅ *{name}* is linked!\n\n"
                    "Use /start here to manage your instances."
                ),
                parse_mode="Markdown",
            )
        except Exception:
            pass

        self.service.interaction_service.log_command(
            user_id=str(user.id),
            command="/link",
            telegram_chat_id=chat_id,
            telegram_message_id=update.message.message_id,
        )

    async def handle_name(self, update, context):
        """Handle /name <name> — set display name for this group's instance."""
        chat_id = update.effective_chat.id
        is_group = update.effective_chat.type in ("group", "supergroup")

        if not is_group:
            await update.message.reply_text(
                "Run /name in a group chat to set that instance's name."
            )
            return

        user = self.service._get_or_create_user(
            update.effective_user, telegram_chat_id=chat_id
        )

        name = " ".join(context.args).strip()[:100] if context.args else ""
        if not name:
            await update.message.reply_text(
                "Usage: `/name My Instance Name`",
                parse_mode="Markdown",
            )
            return

        from src.services.core.settings_service import SettingsService

        with SettingsService() as settings_service:
            chat_settings = settings_service.get_settings_if_exists(chat_id)
            if not chat_settings:
                await update.message.reply_text(
                    "⚠️ This group isn't set up yet. Run /start first."
                )
                return
            settings_service.update_setting(chat_id, "display_name", name)

        await update.message.reply_text(
            f"✅ Instance renamed to *{name}*",
            parse_mode="Markdown",
        )

        self.service.interaction_service.log_command(
            user_id=str(user.id),
            command="/name",
            context={"display_name": name},
            telegram_chat_id=chat_id,
            telegram_message_id=update.message.message_id,
        )

    async def handle_instances(self, update, context):
        """Handle /instances — list user's instances in DM."""
        if update.effective_chat.type != "private":
            await update.message.reply_text(
                "Use /instances in a DM with me to see all your instances."
            )
            return

        user = self.service._get_or_create_user(update.effective_user)

        from src.services.core.dashboard_service import DashboardService
        from src.services.core.start_command_router import _escape_md2

        with DashboardService() as dash:
            data = dash.get_user_instances(update.effective_user.id)

        instances = data["instances"]
        if not instances:
            await update.message.reply_text(
                "You don't have any instances yet.\n\n"
                "Run /new to create one, or /start to get started."
            )
            return

        lines = ["Your instances:"]
        keyboard_rows = []
        for i, inst in enumerate(instances, 1):
            name = inst["display_name"] or f"Chat {inst['telegram_chat_id']}"
            media = inst["media_count"]
            ppd = inst["posts_per_day"]
            status = "paused" if inst["is_paused"] else "active"
            lines.append(
                f"{i}\\. *{_escape_md2(name)}* \\({media} media · {ppd}/day · {status}\\)"
            )
            keyboard_rows.append(
                [
                    InlineKeyboardButton(
                        f"Manage {name}",
                        callback_data=f"instance_manage:{inst['chat_settings_id']}",
                    )
                ]
            )

        keyboard_rows.append(
            [InlineKeyboardButton("+ New Instance", callback_data="instance_new")]
        )

        await update.message.reply_text(
            "\n".join(lines),
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard_rows),
        )

        self.service.interaction_service.log_command(
            user_id=str(user.id),
            command="/instances",
            context={"count": len(instances)},
            telegram_chat_id=update.effective_chat.id,
            telegram_message_id=update.message.message_id,
        )

    async def handle_new(self, update, context):
        """Handle /new — shortcut to start new instance creation in DM."""
        if update.effective_chat.type != "private":
            await update.message.reply_text(
                "Use /new in a DM with me to create a new instance."
            )
            return

        user = self.service._get_or_create_user(update.effective_user)

        from src.services.core.conversation_service import ConversationService

        with ConversationService() as conv_service:
            session = conv_service.start_onboarding(str(user.id))

        context.user_data["onboarding_session_id"] = str(session.id)

        await update.message.reply_text(
            "Let's set up a new instance\\!\n\n"
            "What do you want to call it?\n"
            '_\\(e\\.g\\. "TL Enterprises", "Personal Brand"\\)_',
            parse_mode="MarkdownV2",
        )

        self.service.interaction_service.log_command(
            user_id=str(user.id),
            command="/new",
            telegram_chat_id=update.effective_chat.id,
            telegram_message_id=update.message.message_id,
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
