"""Tests for StartCommandRouter — 5-branch /start handler."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.services.core.start_command_router import StartCommandRouter, _escape_md2


@pytest.fixture
def mock_service():
    """Minimal TelegramService mock for router tests."""
    service = Mock()
    service._get_or_create_user = Mock()
    service.interaction_service = Mock()
    service.membership_repo = Mock()
    service.bot = AsyncMock()
    service.bot.get_me = AsyncMock(return_value=Mock(username="test_bot"))
    return service


@pytest.fixture
def router(mock_service):
    """StartCommandRouter with mocked TelegramService."""
    return StartCommandRouter(mock_service)


def _make_update(chat_type="private", chat_id=12345, user_id=67890, message_id=1):
    """Build a mock Telegram Update."""
    update = AsyncMock()
    update.effective_chat = Mock()
    update.effective_chat.id = chat_id
    update.effective_chat.type = chat_type
    update.effective_user = Mock()
    update.effective_user.id = user_id
    update.message = AsyncMock()
    update.message.message_id = message_id
    update.message.reply_text = AsyncMock()
    return update


def _make_context(args=None):
    """Build a mock Telegram context."""
    context = Mock()
    context.args = args or []
    context.user_data = {}
    return context


# ──────────────────────────────────────────────────────────────
# handle_start — routing logic
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
class TestHandleStartRouting:
    async def test_group_with_startgroup_payload(self, router):
        """Group chat + setup_ payload → _handle_startgroup_link."""
        update = _make_update(chat_type="group")
        context = _make_context(args=["setup_sess-1"])
        router.service._get_or_create_user.return_value = Mock(id="user-1")

        with patch.object(
            router, "_handle_startgroup_link", new_callable=AsyncMock
        ) as mock_link:
            await router.handle_start(update, context)

        mock_link.assert_called_once()

    async def test_group_without_payload(self, router):
        """Group chat + no payload → _handle_group_start."""
        update = _make_update(chat_type="group")
        context = _make_context()
        router.service._get_or_create_user.return_value = Mock(id="user-1")

        with patch.object(
            router, "_handle_group_start", new_callable=AsyncMock
        ) as mock_group:
            await router.handle_start(update, context)

        mock_group.assert_called_once()

    async def test_dm_with_active_session(self, router):
        """DM + active onboarding session → _handle_resume_onboarding."""
        update = _make_update(chat_type="private")
        context = _make_context()
        user = Mock(id="user-1")
        router.service._get_or_create_user.return_value = user

        mock_session = Mock()
        mock_conv = Mock()
        mock_conv.get_current_session.return_value = mock_session
        mock_conv.__enter__ = Mock(return_value=mock_conv)
        mock_conv.__exit__ = Mock(return_value=False)

        with (
            patch(
                "src.services.core.start_command_router.ConversationService",
                return_value=mock_conv,
            ),
            patch.object(
                router, "_handle_resume_onboarding", new_callable=AsyncMock
            ) as mock_resume,
        ):
            await router.handle_start(update, context)

        mock_resume.assert_called_once()

    async def test_dm_returning_user(self, router):
        """DM + no session + memberships → _handle_returning_user."""
        update = _make_update(chat_type="private")
        context = _make_context()
        user = Mock(id="user-1")
        router.service._get_or_create_user.return_value = user

        mock_conv = Mock()
        mock_conv.get_current_session.return_value = None
        mock_conv.__enter__ = Mock(return_value=mock_conv)
        mock_conv.__exit__ = Mock(return_value=False)

        mock_membership = Mock()
        mock_membership.get_for_user.return_value = [Mock()]
        mock_membership.__enter__ = Mock(return_value=mock_membership)
        mock_membership.__exit__ = Mock(return_value=False)

        with (
            patch(
                "src.services.core.start_command_router.ConversationService",
                return_value=mock_conv,
            ),
            patch(
                "src.services.core.start_command_router.MembershipRepository",
                return_value=mock_membership,
            ),
            patch.object(
                router, "_handle_returning_user", new_callable=AsyncMock
            ) as mock_returning,
        ):
            await router.handle_start(update, context)

        mock_returning.assert_called_once()

    async def test_dm_new_user(self, router):
        """DM + no session + no memberships → _handle_new_user."""
        update = _make_update(chat_type="private")
        context = _make_context()
        user = Mock(id="user-1")
        router.service._get_or_create_user.return_value = user

        mock_conv = Mock()
        mock_conv.get_current_session.return_value = None
        mock_conv.__enter__ = Mock(return_value=mock_conv)
        mock_conv.__exit__ = Mock(return_value=False)

        mock_membership = Mock()
        mock_membership.get_for_user.return_value = []
        mock_membership.__enter__ = Mock(return_value=mock_membership)
        mock_membership.__exit__ = Mock(return_value=False)

        with (
            patch(
                "src.services.core.start_command_router.ConversationService",
                return_value=mock_conv,
            ),
            patch(
                "src.services.core.start_command_router.MembershipRepository",
                return_value=mock_membership,
            ),
            patch.object(
                router, "_handle_new_user", new_callable=AsyncMock
            ) as mock_new,
        ):
            await router.handle_start(update, context)

        mock_new.assert_called_once()

    async def test_always_logs_interaction(self, router):
        """Interaction is logged regardless of branch."""
        update = _make_update(chat_type="private")
        context = _make_context()
        user = Mock(id="user-1")
        router.service._get_or_create_user.return_value = user

        mock_conv = Mock()
        mock_conv.get_current_session.return_value = None
        mock_conv.__enter__ = Mock(return_value=mock_conv)
        mock_conv.__exit__ = Mock(return_value=False)

        mock_membership = Mock()
        mock_membership.get_for_user.return_value = []
        mock_membership.__enter__ = Mock(return_value=mock_membership)
        mock_membership.__exit__ = Mock(return_value=False)

        with (
            patch(
                "src.services.core.start_command_router.ConversationService",
                return_value=mock_conv,
            ),
            patch(
                "src.services.core.start_command_router.MembershipRepository",
                return_value=mock_membership,
            ),
            patch.object(router, "_handle_new_user", new_callable=AsyncMock),
        ):
            await router.handle_start(update, context)

        router.service.interaction_service.log_command.assert_called_once()


# ──────────────────────────────────────────────────────────────
# _handle_startgroup_link
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
class TestHandleStartgroupLink:
    async def test_valid_session_links_group(self, router):
        """Valid session + correct user → links group and sends confirmation."""
        update = _make_update(chat_type="group")
        user = Mock(id="user-1")

        session = Mock(
            user_id="user-1",
            step="awaiting_group",
            pending_instance_name="My Brand",
        )
        mock_conv = Mock()
        mock_conv.get_session_by_id.return_value = session
        mock_conv.link_group_to_instance = Mock()
        mock_conv.__enter__ = Mock(return_value=mock_conv)
        mock_conv.__exit__ = Mock(return_value=False)

        with patch(
            "src.services.core.start_command_router.ConversationService",
            return_value=mock_conv,
        ):
            await router._handle_startgroup_link(update, user, "setup_sess-1")

        update.message.reply_text.assert_called_once()
        assert "set up" in update.message.reply_text.call_args[0][0]

    async def test_invalid_session_shows_error(self, router):
        """Invalid session ID → error message."""
        update = _make_update(chat_type="group")
        user = Mock(id="user-1")

        mock_conv = Mock()
        mock_conv.get_session_by_id.return_value = None
        mock_conv.__enter__ = Mock(return_value=mock_conv)
        mock_conv.__exit__ = Mock(return_value=False)

        with patch(
            "src.services.core.start_command_router.ConversationService",
            return_value=mock_conv,
        ):
            await router._handle_startgroup_link(update, user, "setup_bad-id")

        update.message.reply_text.assert_called_once()
        assert "Invalid" in update.message.reply_text.call_args[0][0]

    async def test_wrong_user_shows_error(self, router):
        """Session belongs to different user → error message."""
        update = _make_update(chat_type="group")
        user = Mock(id="user-1")

        session = Mock(user_id="other-user", step="awaiting_group")
        mock_conv = Mock()
        mock_conv.get_session_by_id.return_value = session
        mock_conv.__enter__ = Mock(return_value=mock_conv)
        mock_conv.__exit__ = Mock(return_value=False)

        with patch(
            "src.services.core.start_command_router.ConversationService",
            return_value=mock_conv,
        ):
            await router._handle_startgroup_link(update, user, "setup_sess-1")

        update.message.reply_text.assert_called_once()
        assert "Invalid" in update.message.reply_text.call_args[0][0]

    async def test_wrong_step_shows_error(self, router):
        """Session not in 'awaiting_group' step → error."""
        update = _make_update(chat_type="group")
        user = Mock(id="user-1")

        session = Mock(user_id="user-1", step="naming")
        mock_conv = Mock()
        mock_conv.get_session_by_id.return_value = session
        mock_conv.__enter__ = Mock(return_value=mock_conv)
        mock_conv.__exit__ = Mock(return_value=False)

        with patch(
            "src.services.core.start_command_router.ConversationService",
            return_value=mock_conv,
        ):
            await router._handle_startgroup_link(update, user, "setup_sess-1")

        update.message.reply_text.assert_called_once()
        assert "not waiting for a group" in update.message.reply_text.call_args[0][0]

    async def test_dm_notification_failure_is_silent(self, router):
        """If DM notification to user fails, it's silently ignored."""
        update = _make_update(chat_type="group")
        user = Mock(id="user-1")

        session = Mock(
            user_id="user-1",
            step="awaiting_group",
            pending_instance_name="Test",
        )
        mock_conv = Mock()
        mock_conv.get_session_by_id.return_value = session
        mock_conv.__enter__ = Mock(return_value=mock_conv)
        mock_conv.__exit__ = Mock(return_value=False)

        router.service.bot.send_message = AsyncMock(side_effect=Exception("DM blocked"))

        with patch(
            "src.services.core.start_command_router.ConversationService",
            return_value=mock_conv,
        ):
            await router._handle_startgroup_link(update, user, "setup_sess-1")

        # Should not raise, group message still sent
        update.message.reply_text.assert_called_once()


# ──────────────────────────────────────────────────────────────
# _handle_group_start
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
class TestHandleGroupStart:
    @patch("src.services.core.start_command_router.settings")
    @patch("src.services.core.start_command_router.build_webapp_button")
    async def test_with_oauth_url_and_onboarding_done(
        self, mock_button, mock_settings, router
    ):
        """Onboarding complete → 'Open Storyline' button."""
        mock_settings.OAUTH_REDIRECT_BASE_URL = "https://example.com"
        mock_button.return_value = Mock()

        mock_settings_svc = Mock()
        mock_settings_svc.get_settings.return_value = Mock(onboarding_completed=True)
        mock_settings_svc.__enter__ = Mock(return_value=mock_settings_svc)
        mock_settings_svc.__exit__ = Mock(return_value=False)

        update = _make_update(chat_type="group")
        user = Mock(id="user-1")

        with patch(
            "src.services.core.settings_service.SettingsService",
            return_value=mock_settings_svc,
        ):
            await router._handle_group_start(update, user, 12345)

        update.message.reply_text.assert_called_once()
        assert "Welcome back" in update.message.reply_text.call_args[0][0]

    @patch("src.services.core.start_command_router.settings")
    async def test_without_oauth_url(self, mock_settings, router):
        """No OAuth URL → shows command list instead."""
        mock_settings.OAUTH_REDIRECT_BASE_URL = None

        mock_settings_svc = Mock()
        mock_settings_svc.get_settings.return_value = Mock(onboarding_completed=False)
        mock_settings_svc.__enter__ = Mock(return_value=mock_settings_svc)
        mock_settings_svc.__exit__ = Mock(return_value=False)

        update = _make_update(chat_type="group")
        user = Mock(id="user-1")

        with patch(
            "src.services.core.settings_service.SettingsService",
            return_value=mock_settings_svc,
        ):
            await router._handle_group_start(update, user, 12345)

        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]
        assert "/status" in text
        assert "/next" in text


# ──────────────────────────────────────────────────────────────
# _handle_resume_onboarding
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
class TestHandleResumeOnboarding:
    async def test_naming_step(self, router):
        """Active session at 'naming' step → asks for instance name."""
        update = _make_update(chat_type="private")
        user = Mock(id="user-1")
        session = Mock(step="naming")

        await router._handle_resume_onboarding(update, user, session)

        update.message.reply_text.assert_called_once()
        assert "What do you want to call" in update.message.reply_text.call_args[0][0]

    async def test_awaiting_group_step(self, router):
        """Active session at 'awaiting_group' → shows 'Add to Group' button."""
        update = _make_update(chat_type="private")
        user = Mock(id="user-1")
        session = Mock(
            id="sess-1",
            step="awaiting_group",
            pending_instance_name="My Brand",
        )

        await router._handle_resume_onboarding(update, user, session)

        update.message.reply_text.assert_called_once()
        call_kwargs = update.message.reply_text.call_args[1]
        assert call_kwargs.get("reply_markup") is not None


# ──────────────────────────────────────────────────────────────
# _handle_returning_user
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
class TestHandleReturningUser:
    async def test_shows_instances_with_manage_buttons(self, router):
        """Shows user's instances with manage buttons and 'New Instance' option."""
        mock_dash = Mock()
        mock_dash.get_user_instances.return_value = {
            "instances": [
                {
                    "display_name": "My Brand",
                    "telegram_chat_id": -100123,
                    "media_count": 50,
                    "posts_per_day": 3,
                    "is_paused": False,
                    "chat_settings_id": "cs-1",
                },
            ],
        }
        mock_dash.__enter__ = Mock(return_value=mock_dash)
        mock_dash.__exit__ = Mock(return_value=False)

        update = _make_update(chat_type="private")
        user = Mock(id="user-1")

        with patch(
            "src.services.core.start_command_router.DashboardService",
            return_value=mock_dash,
        ):
            await router._handle_returning_user(update, user)

        update.message.reply_text.assert_called_once()
        call_kwargs = update.message.reply_text.call_args[1]
        assert call_kwargs.get("reply_markup") is not None


# ──────────────────────────────────────────────────────────────
# _handle_new_user
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
class TestHandleNewUser:
    async def test_starts_onboarding_and_stores_session_id(self, router):
        """Creates onboarding session and stores session ID in context."""
        mock_conv = Mock()
        mock_conv.start_onboarding.return_value = Mock(id="sess-1")
        mock_conv.__enter__ = Mock(return_value=mock_conv)
        mock_conv.__exit__ = Mock(return_value=False)

        update = _make_update(chat_type="private")
        user = Mock(id="user-1")
        context = _make_context()

        with patch(
            "src.services.core.start_command_router.ConversationService",
            return_value=mock_conv,
        ):
            await router._handle_new_user(update, user, context)

        assert context.user_data["onboarding_session_id"] == "sess-1"
        update.message.reply_text.assert_called_once()


# ──────────────────────────────────────────────────────────────
# _escape_md2
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestEscapeMd2:
    def test_escapes_special_characters(self):
        """Escapes all MarkdownV2 special characters."""
        assert _escape_md2("hello_world") == "hello\\_world"
        assert _escape_md2("test*bold*") == "test\\*bold\\*"
        assert _escape_md2("a.b") == "a\\.b"

    def test_plain_text_unchanged(self):
        """Plain text without special chars passes through unchanged."""
        assert _escape_md2("hello world") == "hello world"
        assert _escape_md2("abc123") == "abc123"
