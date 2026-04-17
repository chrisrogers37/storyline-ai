"""StartCommandRouter — 5-branch /start handler for multi-account DM flow."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.config.settings import settings
from src.services.core.conversation_service import ConversationService
from src.services.core.dashboard_service import DashboardService
from src.repositories.membership_repository import MembershipRepository
from src.services.core.telegram_utils import build_webapp_button

if TYPE_CHECKING:
    from src.services.core.telegram_service import TelegramService


class StartCommandRouter:
    """Routes /start to the correct handler based on chat type and state.

    Branches:
    1. Group + startgroup payload → link pending onboarding session
    2. Group + no payload → existing group setup (unchanged)
    3. DM + active onboarding session → resume in-progress onboarding
    4. DM + returning user (1+ memberships) → instance list
    5. DM + new user (0 memberships) → start onboarding
    """

    def __init__(self, service: TelegramService):
        self.service = service

    async def handle_start(self, update, context):
        """Main /start entry point."""
        chat_id = update.effective_chat.id
        user = self.service._get_or_create_user(
            update.effective_user, telegram_chat_id=chat_id
        )
        is_dm = update.effective_chat.type == "private"

        if not is_dm:
            # Group context
            payload = context.args[0] if context.args else None
            if payload and payload.startswith("setup_"):
                await self._handle_startgroup_link(update, user, payload)
            else:
                await self._handle_group_start(update, user, chat_id)
        else:
            # DM context
            with ConversationService() as conv_service:
                active_session = conv_service.get_current_session(str(user.id))

            if active_session:
                await self._handle_resume_onboarding(update, user, active_session)
            else:
                with MembershipRepository() as membership_repo:
                    memberships = membership_repo.get_for_user(str(user.id))

                if memberships:
                    await self._handle_returning_user(update, user)
                else:
                    await self._handle_new_user(update, user, context)

        # Log interaction
        self.service.interaction_service.log_command(
            user_id=str(user.id),
            command="/start",
            telegram_chat_id=chat_id,
            telegram_message_id=update.message.message_id,
        )

    # ------------------------------------------------------------------
    # Branch 1: Group + startgroup payload
    # ------------------------------------------------------------------

    async def _handle_startgroup_link(self, update, user, payload):
        """Link this group to a pending onboarding session from DM."""
        session_id = payload[6:]  # strip "setup_"
        chat_id = update.effective_chat.id

        with ConversationService() as conv_service:
            session = conv_service.get_session_by_id(session_id)

        if not session or str(session.user_id) != str(user.id):
            await update.message.reply_text(
                "⚠️ Invalid or expired setup link. "
                "Start a new instance from your DM with the bot."
            )
            return

        if session.step != "awaiting_group":
            await update.message.reply_text(
                "⚠️ This setup session is not waiting for a group. "
                "Start a new instance from your DM."
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
            f"✅ *{name}* is set up\\!\n\n"
            f"Use /status to check health, or set up your media source "
            f"and posting schedule from the dashboard\\.",
            parse_mode="MarkdownV2",
        )

        # Notify in DM
        try:
            await self.service.bot.send_message(
                chat_id=update.effective_user.id,
                text=(
                    f"✅ Your instance *{name}* is linked to this group!\n\n"
                    "Use /start here to manage your instances."
                ),
                parse_mode="Markdown",
            )
        except Exception:
            pass  # DM may be blocked

    # ------------------------------------------------------------------
    # Branch 2: Group + no payload (existing behavior)
    # ------------------------------------------------------------------

    async def _handle_group_start(self, update, user, chat_id):
        """Standard group /start — show onboarding or dashboard button."""
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
                    "Welcome back to *Storyline AI*!\n\n"
                    "Tap the button below to view your dashboard "
                    "and manage your settings."
                )
            else:
                button_text = "Open Setup Wizard"
                message_text = (
                    "Welcome to *Storyline AI*!\n\n"
                    "Let's get you set up. Tap the button below to "
                    "connect your accounts and configure your posting schedule."
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
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
        else:
            await update.message.reply_text(
                "👋 *Storyline AI Bot*\n\n"
                "Commands:\n"
                "/status - System health & overview\n"
                "/next - Force send next post\n"
                "/setup - Quick settings & toggles\n"
                "/help - Show all commands",
                parse_mode="Markdown",
            )

    # ------------------------------------------------------------------
    # Branch 3: DM + active onboarding → resume
    # ------------------------------------------------------------------

    async def _handle_resume_onboarding(self, update, user, session):
        """Resume an in-progress onboarding session."""
        if session.step == "naming":
            await update.message.reply_text(
                "You have an instance setup in progress.\n\n"
                "What do you want to call this instance?\n"
                '_(e.g. "TL Enterprises", "Personal Brand")_',
                parse_mode="Markdown",
            )
        elif session.step == "awaiting_group":
            name = session.pending_instance_name or "your instance"
            bot_username = (await self.service.bot.get_me()).username
            startgroup_url = (
                f"https://t.me/{bot_username}?startgroup=setup_{session.id}"
            )

            keyboard = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("Add to Group Chat", url=startgroup_url)],
                ]
            )
            await update.message.reply_text(
                f"Waiting to link *{name}* to a group chat.\n\n"
                "Add me to the group, or if I'm already there, "
                "run `/link` in that group.",
                parse_mode="Markdown",
                reply_markup=keyboard,
            )

    # ------------------------------------------------------------------
    # Branch 4: DM + returning user → instance list
    # ------------------------------------------------------------------

    async def _handle_returning_user(self, update, user):
        """Show the user's instances with stats and management buttons."""
        with DashboardService() as dash:
            data = dash.get_user_instances(update.effective_user.id)

        instances = data["instances"]
        lines = ["Welcome back to *Storyline AI*\\!\n\nYour instances:"]

        keyboard_rows = []
        for i, inst in enumerate(instances, 1):
            name = inst["display_name"] or f"Chat {inst['telegram_chat_id']}"
            media = inst["media_count"]
            ppd = inst["posts_per_day"]
            status = "⏸️ paused" if inst["is_paused"] else "✅ active"
            lines.append(
                f"{i}\\. *{_escape_md2(name)}* "
                f"\\({media} media · {ppd}/day · {status}\\)"
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

    # ------------------------------------------------------------------
    # Branch 5: DM + new user → start onboarding
    # ------------------------------------------------------------------

    async def _handle_new_user(self, update, user, context):
        """Start the instance creation onboarding flow."""
        with ConversationService() as conv_service:
            session = conv_service.start_onboarding(str(user.id))

        # Store session ID in context for conversation routing
        context.user_data["onboarding_session_id"] = str(session.id)

        await update.message.reply_text(
            "Welcome to *Storyline AI*\\! Let's set up your first posting instance\\.\n\n"
            "What do you want to call this instance?\n"
            '_\\(e\\.g\\. "TL Enterprises", "Personal Brand"\\)_',
            parse_mode="MarkdownV2",
        )


def _escape_md2(text: str) -> str:
    """Escape Telegram MarkdownV2 special characters."""

    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!\\])", r"\\\1", text)
