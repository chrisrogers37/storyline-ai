"""Tests for InteractionService."""

import pytest
from unittest.mock import Mock
from uuid import uuid4

from src.services.core.interaction_service import InteractionService


@pytest.fixture
def interaction_service():
    """Create InteractionService with mocked repository."""
    service = InteractionService()
    service.interaction_repo = Mock()
    return service


@pytest.fixture
def mock_interaction():
    """Create a mock interaction record."""
    interaction = Mock()
    interaction.id = uuid4()
    interaction.user_id = uuid4()
    interaction.interaction_type = "command"
    interaction.interaction_name = "/status"
    interaction.context = {"queue_size": 5}
    return interaction


class TestLogCommand:
    """Tests for log_command method."""

    def test_log_command_success(self, interaction_service, mock_interaction):
        """Test logging a command interaction."""
        interaction_service.interaction_repo.create.return_value = mock_interaction
        user_id = str(uuid4())

        result = interaction_service.log_command(
            user_id=user_id,
            command="/status",
            context={"queue_size": 5},
            telegram_chat_id=123456,
            telegram_message_id=789,
        )

        assert result == mock_interaction
        interaction_service.interaction_repo.create.assert_called_once_with(
            user_id=user_id,
            interaction_type="command",
            interaction_name="/status",
            context={"queue_size": 5},
            telegram_chat_id=123456,
            telegram_message_id=789,
        )

    def test_log_command_handles_exception(self, interaction_service):
        """Test that log_command returns None on error."""
        interaction_service.interaction_repo.create.side_effect = Exception("DB error")
        user_id = str(uuid4())

        result = interaction_service.log_command(
            user_id=user_id,
            command="/status",
        )

        assert result is None

    def test_log_command_minimal_params(self, interaction_service, mock_interaction):
        """Test logging command with minimal parameters."""
        interaction_service.interaction_repo.create.return_value = mock_interaction
        user_id = str(uuid4())

        result = interaction_service.log_command(
            user_id=user_id,
            command="/help",
        )

        assert result == mock_interaction
        interaction_service.interaction_repo.create.assert_called_once()


class TestLogCallback:
    """Tests for log_callback method."""

    def test_log_callback_posted(self, interaction_service, mock_interaction):
        """Test logging a 'posted' callback."""
        mock_interaction.interaction_type = "callback"
        mock_interaction.interaction_name = "posted"
        interaction_service.interaction_repo.create.return_value = mock_interaction
        user_id = str(uuid4())
        queue_item_id = str(uuid4())

        result = interaction_service.log_callback(
            user_id=user_id,
            callback_name="posted",
            context={
                "queue_item_id": queue_item_id,
                "media_id": str(uuid4()),
            },
            telegram_chat_id=123456,
            telegram_message_id=789,
        )

        assert result == mock_interaction
        interaction_service.interaction_repo.create.assert_called_once()
        call_args = interaction_service.interaction_repo.create.call_args
        assert call_args.kwargs["interaction_type"] == "callback"
        assert call_args.kwargs["interaction_name"] == "posted"

    def test_log_callback_skip(self, interaction_service, mock_interaction):
        """Test logging a 'skip' callback."""
        mock_interaction.interaction_name = "skip"
        interaction_service.interaction_repo.create.return_value = mock_interaction
        user_id = str(uuid4())

        result = interaction_service.log_callback(
            user_id=user_id,
            callback_name="skip",
            context={"queue_item_id": str(uuid4())},
        )

        assert result == mock_interaction

    def test_log_callback_reject(self, interaction_service, mock_interaction):
        """Test logging a 'reject' callback."""
        mock_interaction.interaction_name = "reject"
        interaction_service.interaction_repo.create.return_value = mock_interaction
        user_id = str(uuid4())

        result = interaction_service.log_callback(
            user_id=user_id,
            callback_name="reject",
        )

        assert result == mock_interaction

    def test_log_callback_handles_exception(self, interaction_service):
        """Test that log_callback returns None on error."""
        interaction_service.interaction_repo.create.side_effect = Exception("DB error")
        user_id = str(uuid4())

        result = interaction_service.log_callback(
            user_id=user_id,
            callback_name="posted",
        )

        assert result is None


class TestAnalytics:
    """Tests for analytics methods."""

    def test_get_user_stats(self, interaction_service):
        """Test getting user stats."""
        expected_stats = {
            "total_interactions": 10,
            "posts_marked": 5,
            "posts_skipped": 3,
            "posts_rejected": 1,
            "commands_used": {"/status": 1},
        }
        interaction_service.interaction_repo.get_user_stats.return_value = (
            expected_stats
        )
        user_id = str(uuid4())

        result = interaction_service.get_user_stats(user_id, days=30)

        assert result == expected_stats
        interaction_service.interaction_repo.get_user_stats.assert_called_once_with(
            user_id, 30
        )

    def test_get_team_activity(self, interaction_service):
        """Test getting team activity stats."""
        expected_activity = {
            "total_interactions": 50,
            "active_users": 3,
            "interactions_by_type": {"command": 10, "callback": 40},
            "interactions_by_name": {"posted": 30, "skip": 8, "/status": 10},
        }
        interaction_service.interaction_repo.get_team_activity.return_value = (
            expected_activity
        )

        result = interaction_service.get_team_activity(days=7)

        assert result == expected_activity
        interaction_service.interaction_repo.get_team_activity.assert_called_once_with(
            7
        )

    def test_get_content_decisions(self, interaction_service):
        """Test getting content decision breakdown."""
        expected_decisions = {
            "total_decisions": 40,
            "posted": 30,
            "skipped": 8,
            "rejected": 2,
            "posted_percentage": 75.0,
            "skip_percentage": 20.0,
            "rejection_rate": 5.0,
        }
        interaction_service.interaction_repo.get_content_decisions.return_value = (
            expected_decisions
        )

        result = interaction_service.get_content_decisions(days=30)

        assert result == expected_decisions
        interaction_service.interaction_repo.get_content_decisions.assert_called_once_with(
            30
        )

    def test_get_recent_interactions(self, interaction_service):
        """Test getting recent interactions."""
        mock_interactions = [Mock(), Mock(), Mock()]
        interaction_service.interaction_repo.get_recent.return_value = mock_interactions

        result = interaction_service.get_recent_interactions(days=7, limit=100)

        assert result == mock_interactions
        interaction_service.interaction_repo.get_recent.assert_called_once_with(
            days=7, limit=100
        )


class TestLogMessage:
    """Tests for log_message method."""

    def test_log_message_success(self, interaction_service, mock_interaction):
        """Test logging a message interaction."""
        mock_interaction.interaction_type = "message"
        interaction_service.interaction_repo.create.return_value = mock_interaction
        user_id = str(uuid4())

        result = interaction_service.log_message(
            user_id=user_id,
            message_type="text",
            context={"text": "hello"},
        )

        assert result == mock_interaction
        call_args = interaction_service.interaction_repo.create.call_args
        assert call_args.kwargs["interaction_type"] == "message"

    def test_log_message_handles_exception(self, interaction_service):
        """Test that log_message returns None on error."""
        interaction_service.interaction_repo.create.side_effect = Exception("DB error")

        result = interaction_service.log_message(
            user_id=str(uuid4()),
            message_type="text",
        )

        assert result is None


class TestGetDeletableBotMessages:
    """Tests for get_deletable_bot_messages method."""

    def test_get_deletable_bot_messages_success(self, interaction_service):
        """Test getting deletable bot messages for a chat."""
        # Create mock bot response interactions
        mock_responses = [
            Mock(telegram_message_id=1001, interaction_name="photo_notification"),
            Mock(telegram_message_id=1002, interaction_name="status_message"),
            Mock(telegram_message_id=1003, interaction_name="queue_listing"),
        ]
        interaction_service.interaction_repo.get_bot_responses_by_chat.return_value = (
            mock_responses
        )
        chat_id = -1001234567890

        result = interaction_service.get_deletable_bot_messages(chat_id)

        assert result == mock_responses
        assert len(result) == 3
        interaction_service.interaction_repo.get_bot_responses_by_chat.assert_called_once_with(
            chat_id, hours=48
        )

    def test_get_deletable_bot_messages_empty(self, interaction_service):
        """Test getting deletable bot messages when none exist."""
        interaction_service.interaction_repo.get_bot_responses_by_chat.return_value = []
        chat_id = -1001234567890

        result = interaction_service.get_deletable_bot_messages(chat_id)

        assert result == []
        interaction_service.interaction_repo.get_bot_responses_by_chat.assert_called_once_with(
            chat_id, hours=48
        )

    def test_get_deletable_bot_messages_uses_48_hour_window(self, interaction_service):
        """Test that the method uses the 48-hour Telegram deletion limit."""
        interaction_service.interaction_repo.get_bot_responses_by_chat.return_value = []
        chat_id = -1001234567890

        interaction_service.get_deletable_bot_messages(chat_id)

        # Verify the 48-hour window is used (Telegram API limit)
        interaction_service.interaction_repo.get_bot_responses_by_chat.assert_called_once_with(
            chat_id, hours=48
        )
