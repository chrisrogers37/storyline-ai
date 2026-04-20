"""Tests for ConversationService — DM onboarding state machine."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from src.services.core.conversation_service import (
    ConversationService,
)


@pytest.fixture
def conv_service():
    """ConversationService with mocked __init__ and dependencies."""
    with patch.object(ConversationService, "__init__", lambda self: None):
        service = ConversationService()
        service.onboarding_repo = Mock()
        return service


# ──────────────────────────────────────────────────────────────
# start_onboarding
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestStartOnboarding:
    def test_creates_session_with_ttl(self, conv_service):
        """Creates a session with a 24h expiration."""
        mock_session = Mock(id="sess-1")
        conv_service.onboarding_repo.create.return_value = mock_session

        result = conv_service.start_onboarding("user-1")

        assert result is mock_session
        call_kwargs = conv_service.onboarding_repo.create.call_args[1]
        assert call_kwargs["user_id"] == "user-1"
        # expires_at should be ~24h from now
        delta = call_kwargs["expires_at"] - datetime.now(timezone.utc)
        assert timedelta(hours=23) < delta < timedelta(hours=25)


# ──────────────────────────────────────────────────────────────
# get_current_session / get_session_by_id
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestGetSession:
    def test_get_current_session_returns_active(self, conv_service):
        """Returns the active session for a user."""
        mock_session = Mock()
        conv_service.onboarding_repo.get_active_for_user.return_value = mock_session

        result = conv_service.get_current_session("user-1")

        assert result is mock_session
        conv_service.onboarding_repo.get_active_for_user.assert_called_once_with(
            "user-1"
        )

    def test_get_current_session_returns_none(self, conv_service):
        """Returns None when no active session exists."""
        conv_service.onboarding_repo.get_active_for_user.return_value = None
        assert conv_service.get_current_session("user-1") is None

    def test_get_session_by_id(self, conv_service):
        """Returns session by ID."""
        mock_session = Mock()
        conv_service.onboarding_repo.get_by_id.return_value = mock_session

        result = conv_service.get_session_by_id("sess-1")

        assert result is mock_session
        conv_service.onboarding_repo.get_by_id.assert_called_once_with("sess-1")

    def test_get_session_by_id_not_found(self, conv_service):
        """Returns None for unknown session ID."""
        conv_service.onboarding_repo.get_by_id.return_value = None
        assert conv_service.get_session_by_id("bad-id") is None


# ──────────────────────────────────────────────────────────────
# set_instance_name
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestSetInstanceName:
    def test_advances_to_awaiting_group(self, conv_service):
        """Sets name and advances step to 'awaiting_group'."""
        mock_session = Mock()
        conv_service.onboarding_repo.update_step.return_value = mock_session

        result = conv_service.set_instance_name("sess-1", "My Brand")

        assert result is mock_session
        conv_service.onboarding_repo.update_step.assert_called_once_with(
            session_id="sess-1",
            step="awaiting_group",
            pending_instance_name="My Brand",
        )


# ──────────────────────────────────────────────────────────────
# link_group
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestLinkGroup:
    def test_completes_session(self, conv_service):
        """Links group and advances step to 'complete'."""
        mock_session = Mock()
        conv_service.onboarding_repo.update_step.return_value = mock_session

        result = conv_service.link_group("sess-1", "cs-1")

        assert result is mock_session
        conv_service.onboarding_repo.update_step.assert_called_once_with(
            session_id="sess-1",
            step="complete",
            pending_chat_settings_id="cs-1",
        )


# ──────────────────────────────────────────────────────────────
# link_group_to_instance
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestLinkGroupToInstance:
    def test_creates_settings_membership_and_completes(self, conv_service):
        """Creates chat_settings, sets display_name, creates membership, completes."""
        session = Mock(
            id="sess-1",
            pending_instance_name="My Brand",
        )
        mock_chat_settings = Mock(id="cs-1")
        mock_settings_service = Mock()
        mock_settings_service.get_settings.return_value = mock_chat_settings
        mock_settings_service.__enter__ = Mock(return_value=mock_settings_service)
        mock_settings_service.__exit__ = Mock(return_value=False)

        membership_repo = Mock()

        with patch(
            "src.services.core.settings_service.SettingsService",
            return_value=mock_settings_service,
        ):
            result = conv_service.link_group_to_instance(
                session,
                chat_id=12345,
                user_id="user-1",
                membership_repo=membership_repo,
            )

        assert result is mock_chat_settings
        mock_settings_service.update_setting.assert_called_once_with(
            12345, "display_name", "My Brand"
        )
        membership_repo.create_membership.assert_called_once_with(
            user_id="user-1",
            chat_settings_id="cs-1",
            instance_role="owner",
        )
        conv_service.onboarding_repo.update_step.assert_called_once_with(
            session_id="sess-1",
            step="complete",
            pending_chat_settings_id="cs-1",
        )

    def test_skips_display_name_when_none(self, conv_service):
        """Doesn't set display_name if pending_instance_name is None."""
        session = Mock(id="sess-1", pending_instance_name=None)
        mock_chat_settings = Mock(id="cs-1")
        mock_settings_service = Mock()
        mock_settings_service.get_settings.return_value = mock_chat_settings
        mock_settings_service.__enter__ = Mock(return_value=mock_settings_service)
        mock_settings_service.__exit__ = Mock(return_value=False)

        with patch(
            "src.services.core.settings_service.SettingsService",
            return_value=mock_settings_service,
        ):
            conv_service.link_group_to_instance(
                session, chat_id=12345, user_id="user-1", membership_repo=Mock()
            )

        mock_settings_service.update_setting.assert_not_called()


# ──────────────────────────────────────────────────────────────
# cleanup_expired
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestCleanupExpired:
    def test_no_expired_sessions(self, conv_service):
        """Returns 0 when no sessions are expired."""
        conv_service.onboarding_repo.get_expired.return_value = []
        conv_service.onboarding_repo.delete_expired.return_value = 0

        assert conv_service.cleanup_expired() == 0

    def test_logs_dropouts_then_deletes(self, conv_service):
        """Logs onboarding_dropout interactions, then deletes expired sessions."""
        expired = [
            Mock(
                user_id="u-1",
                step="naming",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
            Mock(
                user_id="u-2",
                step="awaiting_group",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
        ]
        conv_service.onboarding_repo.get_expired.return_value = expired
        conv_service.onboarding_repo.delete_expired.return_value = 2

        mock_interaction_repo = Mock()
        mock_interaction_repo.__enter__ = Mock(return_value=mock_interaction_repo)
        mock_interaction_repo.__exit__ = Mock(return_value=False)

        with patch(
            "src.repositories.interaction_repository.InteractionRepository",
            return_value=mock_interaction_repo,
        ):
            result = conv_service.cleanup_expired()

        assert result == 2
        assert mock_interaction_repo.create.call_count == 2

    def test_sqlalchemy_error_during_logging_does_not_block_delete(self, conv_service):
        """If logging dropouts fails, deletion still proceeds."""
        expired = [
            Mock(user_id="u-1", step="naming", created_at=datetime.now(timezone.utc))
        ]
        conv_service.onboarding_repo.get_expired.return_value = expired
        conv_service.onboarding_repo.delete_expired.return_value = 1

        mock_interaction_repo = Mock()
        mock_interaction_repo.__enter__ = Mock(return_value=mock_interaction_repo)
        mock_interaction_repo.__exit__ = Mock(return_value=False)
        mock_interaction_repo.create.side_effect = SQLAlchemyError("db error")

        with patch(
            "src.repositories.interaction_repository.InteractionRepository",
            return_value=mock_interaction_repo,
        ):
            result = conv_service.cleanup_expired()

        assert result == 1
        conv_service.onboarding_repo.delete_expired.assert_called_once()
