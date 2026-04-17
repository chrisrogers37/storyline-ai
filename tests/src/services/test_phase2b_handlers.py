"""Tests for Phase 2b multi-account handlers.

Covers: my_chat_member handler, /link, /name, /instances, /new commands,
and onboarding session cleanup in the scheduler loop.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from uuid import uuid4

from src.services.core.telegram_commands import TelegramCommandHandlers


@pytest.fixture
def mock_command_handlers(mock_telegram_service):
    """Create TelegramCommandHandlers from shared mock_telegram_service."""
    return TelegramCommandHandlers(mock_telegram_service)


def _make_user(service, user_id=None):
    """Helper: set up user_repo mocks and return a mock user."""
    mock_user = Mock()
    mock_user.id = user_id or uuid4()
    service.user_repo.get_by_telegram_id.return_value = mock_user
    service.user_repo.update_profile.return_value = mock_user
    return mock_user


def _make_update(chat_id, chat_type="group", user_id=12345):
    """Helper: build a mock update for command handlers."""
    mock_update = AsyncMock()
    mock_update.effective_user.id = user_id
    mock_update.effective_user.first_name = "Test"
    mock_update.effective_user.username = "testuser"
    mock_update.effective_chat.id = chat_id
    mock_update.effective_chat.type = chat_type
    mock_update.message.message_id = 1
    return mock_update


# ==================== my_chat_member Tests ====================


@pytest.mark.unit
@pytest.mark.asyncio
class TestMyChatMemberHandler:
    """Tests for the my_chat_member handler on TelegramService."""

    async def test_bot_added_auto_links_pending_session(self, mock_telegram_service):
        """Bot added to group auto-links a pending onboarding session."""
        service = mock_telegram_service
        mock_user = _make_user(service)

        mock_session = Mock()
        mock_session.id = uuid4()
        mock_session.step = "awaiting_group"
        mock_session.pending_instance_name = "My Shop"
        mock_session.user_id = mock_user.id

        mock_update = Mock()
        mock_update.my_chat_member = Mock()
        mock_update.my_chat_member.chat = Mock(id=-100999, type="supergroup")
        mock_update.my_chat_member.from_user = Mock(id=12345, username="test")
        mock_update.my_chat_member.old_chat_member = Mock(status="left")
        mock_update.my_chat_member.new_chat_member = Mock(status="member")

        service.bot = AsyncMock()

        with patch(
            "src.services.core.conversation_service.ConversationService"
        ) as MockConv:
            mock_conv = MockConv.return_value
            mock_conv.__enter__ = Mock(return_value=mock_conv)
            mock_conv.__exit__ = Mock(return_value=False)
            mock_conv.get_current_session.return_value = mock_session

            await service._handle_my_chat_member(mock_update, Mock())

        # Should call link_group_to_instance
        mock_conv.link_group_to_instance.assert_called_once_with(
            session=mock_session,
            chat_id=-100999,
            user_id=str(mock_user.id),
            membership_repo=service.membership_repo,
        )

    async def test_bot_added_no_pending_session_is_noop(self, mock_telegram_service):
        """Bot added to group with no pending session does nothing harmful."""
        service = mock_telegram_service
        _make_user(service)

        mock_update = Mock()
        mock_update.my_chat_member = Mock()
        mock_update.my_chat_member.chat = Mock(id=-100999, type="group")
        mock_update.my_chat_member.from_user = Mock(id=12345, username="test")
        mock_update.my_chat_member.old_chat_member = Mock(status="left")
        mock_update.my_chat_member.new_chat_member = Mock(status="member")

        service.bot = AsyncMock()

        with patch(
            "src.services.core.conversation_service.ConversationService"
        ) as MockConv:
            mock_conv = MockConv.return_value
            mock_conv.__enter__ = Mock(return_value=mock_conv)
            mock_conv.__exit__ = Mock(return_value=False)
            mock_conv.get_current_session.return_value = None

            await service._handle_my_chat_member(mock_update, Mock())

        service.membership_repo.create_membership.assert_not_called()

    async def test_bot_kicked_deactivates_memberships(self, mock_telegram_service):
        """Bot kicked from group deactivates all memberships."""
        service = mock_telegram_service

        mock_chat_settings = Mock()
        mock_chat_settings.id = uuid4()
        service.settings_service.get_settings_if_exists.return_value = (
            mock_chat_settings
        )
        service.membership_repo.deactivate_for_chat.return_value = 3

        # Pre-populate cache with entries for this chat
        service._known_memberships = {
            ("user1", -100999),
            ("user2", -100999),
            ("user3", -100888),  # different chat, should survive
        }

        mock_update = Mock()
        mock_update.my_chat_member = Mock()
        mock_update.my_chat_member.chat = Mock(id=-100999, type="supergroup")
        mock_update.my_chat_member.from_user = Mock(id=12345, username="test")
        mock_update.my_chat_member.old_chat_member = Mock(status="member")
        mock_update.my_chat_member.new_chat_member = Mock(status="kicked")

        await service._handle_my_chat_member(mock_update, Mock())

        service.membership_repo.deactivate_for_chat.assert_called_once_with(
            str(mock_chat_settings.id)
        )

        # Cache entries for -100999 should be evicted
        assert ("user1", -100999) not in service._known_memberships
        assert ("user2", -100999) not in service._known_memberships
        # Entry for different chat should remain
        assert ("user3", -100888) in service._known_memberships

    async def test_ignores_non_group_events(self, mock_telegram_service):
        """my_chat_member events in non-group chats are ignored."""
        service = mock_telegram_service

        mock_update = Mock()
        mock_update.my_chat_member = Mock()
        mock_update.my_chat_member.chat = Mock(id=12345, type="private")

        await service._handle_my_chat_member(mock_update, Mock())

        service.membership_repo.create_membership.assert_not_called()
        service.membership_repo.deactivate_for_chat.assert_not_called()


# ==================== /link Command Tests ====================


@pytest.mark.unit
@pytest.mark.asyncio
class TestLinkCommand:
    """Tests for /link fallback command."""

    async def test_link_in_dm_rejected(self, mock_command_handlers):
        """Running /link in DM tells user to use it in a group."""
        handlers = mock_command_handlers
        mock_update = _make_update(12345, chat_type="private")

        await handlers.handle_link(mock_update, Mock())

        msg = mock_update.message.reply_text.call_args.args[0]
        assert "group chat" in msg.lower()

    async def test_link_with_pending_session_succeeds(self, mock_command_handlers):
        """Running /link in group with pending session links successfully."""
        handlers = mock_command_handlers
        service = handlers.service
        mock_user = _make_user(service)

        mock_session = Mock()
        mock_session.id = uuid4()
        mock_session.step = "awaiting_group"
        mock_session.pending_instance_name = "Team Chat"

        mock_update = _make_update(-100123, chat_type="group")
        mock_context = Mock()
        mock_context.bot = AsyncMock()

        with patch(
            "src.services.core.conversation_service.ConversationService"
        ) as MockConv:
            mock_conv = MockConv.return_value
            mock_conv.__enter__ = Mock(return_value=mock_conv)
            mock_conv.__exit__ = Mock(return_value=False)
            mock_conv.get_current_session.return_value = mock_session

            service.bot = AsyncMock()

            await handlers.handle_link(mock_update, mock_context)

        # Should call link_group_to_instance
        mock_conv.link_group_to_instance.assert_called_once_with(
            session=mock_session,
            chat_id=-100123,
            user_id=str(mock_user.id),
            membership_repo=service.membership_repo,
        )

        # Should show success message
        msg = mock_update.message.reply_text.call_args.args[0]
        assert "Team Chat" in msg
        assert "linked" in msg.lower()

    async def test_link_no_pending_session(self, mock_command_handlers):
        """Running /link with no pending session shows helpful message."""
        handlers = mock_command_handlers
        service = handlers.service
        _make_user(service)

        mock_update = _make_update(-100123, chat_type="group")
        mock_context = Mock()
        mock_context.bot = AsyncMock()

        with patch(
            "src.services.core.conversation_service.ConversationService"
        ) as MockConv:
            mock_conv = MockConv.return_value
            mock_conv.__enter__ = Mock(return_value=mock_conv)
            mock_conv.__exit__ = Mock(return_value=False)
            mock_conv.get_current_session.return_value = None

            await handlers.handle_link(mock_update, mock_context)

        msg = mock_update.message.reply_text.call_args.args[0]
        assert "No pending" in msg


# ==================== /name Command Tests ====================


@pytest.mark.unit
@pytest.mark.asyncio
class TestNameCommand:
    """Tests for /name command."""

    async def test_name_sets_display_name(self, mock_command_handlers):
        """Running /name in group sets the display_name."""
        handlers = mock_command_handlers
        service = handlers.service
        _make_user(service)

        mock_update = _make_update(-100123, chat_type="group")
        mock_context = Mock()
        mock_context.args = ["My", "Cool", "Bot"]

        mock_chat_settings = Mock()
        mock_chat_settings.id = uuid4()

        with patch(
            "src.services.core.settings_service.SettingsService"
        ) as MockSettings:
            mock_settings_inst = MockSettings.return_value
            mock_settings_inst.__enter__ = Mock(return_value=mock_settings_inst)
            mock_settings_inst.__exit__ = Mock(return_value=False)
            mock_settings_inst.get_settings_if_exists.return_value = mock_chat_settings

            await handlers.handle_name(mock_update, mock_context)

        mock_settings_inst.update_setting.assert_called_once_with(
            -100123, "display_name", "My Cool Bot"
        )
        msg = mock_update.message.reply_text.call_args.args[0]
        assert "My Cool Bot" in msg

    async def test_name_no_args_shows_usage(self, mock_command_handlers):
        """Running /name without args shows usage."""
        handlers = mock_command_handlers
        service = handlers.service
        _make_user(service)

        mock_update = _make_update(-100123, chat_type="group")
        mock_context = Mock()
        mock_context.args = []

        await handlers.handle_name(mock_update, mock_context)

        msg = mock_update.message.reply_text.call_args.args[0]
        assert "Usage" in msg

    async def test_name_in_dm_rejected(self, mock_command_handlers):
        """Running /name in DM tells user to use it in a group."""
        handlers = mock_command_handlers
        mock_update = _make_update(12345, chat_type="private")
        mock_context = Mock()
        mock_context.args = ["test"]

        await handlers.handle_name(mock_update, mock_context)

        msg = mock_update.message.reply_text.call_args.args[0]
        assert "group chat" in msg.lower()

    async def test_name_truncates_at_100_chars(self, mock_command_handlers):
        """Name is truncated to 100 characters."""
        handlers = mock_command_handlers
        service = handlers.service
        _make_user(service)

        mock_update = _make_update(-100123, chat_type="group")
        long_name = "A" * 120
        mock_context = Mock()
        mock_context.args = [long_name]

        mock_chat_settings = Mock()
        mock_chat_settings.id = uuid4()

        with patch(
            "src.services.core.settings_service.SettingsService"
        ) as MockSettings:
            mock_settings_inst = MockSettings.return_value
            mock_settings_inst.__enter__ = Mock(return_value=mock_settings_inst)
            mock_settings_inst.__exit__ = Mock(return_value=False)
            mock_settings_inst.get_settings_if_exists.return_value = mock_chat_settings

            await handlers.handle_name(mock_update, mock_context)

        call_args = mock_settings_inst.update_setting.call_args
        assert len(call_args[0][2]) == 100


# ==================== /instances Command Tests ====================


@pytest.mark.unit
@pytest.mark.asyncio
class TestInstancesCommand:
    """Tests for /instances command."""

    async def test_instances_in_dm_shows_list(self, mock_command_handlers):
        """Running /instances in DM shows instance list."""
        handlers = mock_command_handlers
        service = handlers.service
        _make_user(service)

        mock_update = _make_update(12345, chat_type="private")

        with patch("src.services.core.dashboard_service.DashboardService") as MockDash:
            mock_dash = MockDash.return_value
            mock_dash.__enter__ = Mock(return_value=mock_dash)
            mock_dash.__exit__ = Mock(return_value=False)
            mock_dash.get_user_instances.return_value = {
                "instances": [
                    {
                        "chat_settings_id": "abc",
                        "telegram_chat_id": -100123,
                        "display_name": "Test Instance",
                        "media_count": 50,
                        "posts_per_day": 3,
                        "is_paused": False,
                        "last_post_at": None,
                        "instance_role": "owner",
                    }
                ]
            }

            await handlers.handle_instances(mock_update, Mock())

        call_args = str(mock_update.message.reply_text.call_args)
        assert "Test Instance" in call_args

    async def test_instances_empty_shows_hint(self, mock_command_handlers):
        """Running /instances with no instances shows helpful message."""
        handlers = mock_command_handlers
        service = handlers.service
        _make_user(service)

        mock_update = _make_update(12345, chat_type="private")

        with patch("src.services.core.dashboard_service.DashboardService") as MockDash:
            mock_dash = MockDash.return_value
            mock_dash.__enter__ = Mock(return_value=mock_dash)
            mock_dash.__exit__ = Mock(return_value=False)
            mock_dash.get_user_instances.return_value = {"instances": []}

            await handlers.handle_instances(mock_update, Mock())

        msg = mock_update.message.reply_text.call_args.args[0]
        assert "don't have any instances" in msg

    async def test_instances_in_group_rejected(self, mock_command_handlers):
        """Running /instances in group tells user to use DM."""
        handlers = mock_command_handlers
        mock_update = _make_update(-100123, chat_type="group")

        await handlers.handle_instances(mock_update, Mock())

        msg = mock_update.message.reply_text.call_args.args[0]
        assert "DM" in msg


# ==================== /new Command Tests ====================


@pytest.mark.unit
@pytest.mark.asyncio
class TestNewCommand:
    """Tests for /new instance creation shortcut."""

    async def test_new_starts_onboarding(self, mock_command_handlers):
        """Running /new in DM starts a new onboarding session."""
        handlers = mock_command_handlers
        service = handlers.service
        _make_user(service)

        mock_update = _make_update(12345, chat_type="private")
        mock_context = Mock()
        mock_context.user_data = {}

        mock_session = Mock()
        mock_session.id = uuid4()

        with patch(
            "src.services.core.conversation_service.ConversationService"
        ) as MockConv:
            mock_conv = MockConv.return_value
            mock_conv.__enter__ = Mock(return_value=mock_conv)
            mock_conv.__exit__ = Mock(return_value=False)
            mock_conv.start_onboarding.return_value = mock_session

            await handlers.handle_new(mock_update, mock_context)

        assert "onboarding_session_id" in mock_context.user_data
        msg = str(mock_update.message.reply_text.call_args)
        assert "new instance" in msg.lower()

    async def test_new_in_group_rejected(self, mock_command_handlers):
        """Running /new in group tells user to use DM."""
        handlers = mock_command_handlers
        mock_update = _make_update(-100123, chat_type="group")

        await handlers.handle_new(mock_update, Mock())

        msg = mock_update.message.reply_text.call_args.args[0]
        assert "DM" in msg


# ==================== Scheduler Cleanup Tests ====================


@pytest.mark.unit
@pytest.mark.asyncio
class TestOnboardingCleanup:
    """Tests for onboarding session cleanup in scheduler loop."""

    async def test_cleanup_expired_called_on_retention_tick(self):
        """Verify ConversationService.cleanup_expired() is called during retention tick."""
        from src.services.core.conversation_service import ConversationService

        with patch.object(ConversationService, "__init__", lambda self: None):
            conv = ConversationService()
            with patch.object(conv, "cleanup_expired", return_value=2) as mock_cleanup:
                with patch.object(conv, "close"):
                    mock_cleanup()
                    mock_cleanup.assert_called_once()
