"""Tests for InteractionRepository."""

import pytest
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from src.repositories.interaction_repository import InteractionRepository
from src.models.user_interaction import UserInteraction


@pytest.fixture
def mock_db():
    """Create a mock database session with chainable query."""
    session = MagicMock(spec=Session)
    mock_query = MagicMock()
    session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.offset.return_value = mock_query
    return session


@pytest.fixture
def interaction_repo(mock_db):
    """Create InteractionRepository with mocked database session."""
    with patch.object(InteractionRepository, "__init__", lambda self: None):
        repo = InteractionRepository()
        repo._db = mock_db
        return repo


@pytest.mark.unit
class TestInteractionRepository:
    """Test suite for InteractionRepository."""

    def test_create_command_interaction(self, interaction_repo, mock_db):
        """Test creating a command interaction."""
        interaction_repo.create(
            user_id="some-user-id",
            interaction_type="command",
            interaction_name="/status",
            context={"queue_size": 5},
            telegram_chat_id=123456,
            telegram_message_id=789,
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

        added = mock_db.add.call_args[0][0]
        assert isinstance(added, UserInteraction)
        assert added.user_id == "some-user-id"
        assert added.interaction_type == "command"
        assert added.interaction_name == "/status"
        assert added.context == {"queue_size": 5}
        assert added.telegram_chat_id == 123456
        assert added.telegram_message_id == 789

    def test_create_callback_interaction(self, interaction_repo, mock_db):
        """Test creating a callback interaction."""
        interaction_repo.create(
            user_id="some-user-id",
            interaction_type="callback",
            interaction_name="posted",
            context={"queue_item_id": "abc123", "media_filename": "test.jpg"},
        )

        added = mock_db.add.call_args[0][0]
        assert added.interaction_type == "callback"
        assert added.interaction_name == "posted"
        assert added.context["media_filename"] == "test.jpg"

    def test_get_user_stats(self, interaction_repo, mock_db):
        """Test getting aggregated user stats."""
        # Mock interactions returned by the query
        mock_interactions = [
            MagicMock(interaction_type="callback", interaction_name="posted"),
            MagicMock(interaction_type="callback", interaction_name="posted"),
            MagicMock(interaction_type="callback", interaction_name="skip"),
            MagicMock(interaction_type="callback", interaction_name="confirm_reject"),
            MagicMock(interaction_type="command", interaction_name="/status"),
        ]
        mock_query = mock_db.query.return_value
        mock_query.all.return_value = mock_interactions

        stats = interaction_repo.get_user_stats("some-user-id")

        assert stats["total_interactions"] == 5
        assert stats["posts_marked"] == 2
        assert stats["posts_skipped"] == 1
        assert stats["posts_rejected"] == 1
        assert "/status" in stats["commands_used"]

    def test_get_team_activity(self, interaction_repo, mock_db):
        """Test getting team-wide activity."""
        mock_interactions = [
            MagicMock(
                user_id="user1", interaction_type="callback", interaction_name="posted"
            ),
            MagicMock(
                user_id="user2", interaction_type="callback", interaction_name="skip"
            ),
            MagicMock(
                user_id="user1", interaction_type="command", interaction_name="/status"
            ),
        ]
        mock_query = mock_db.query.return_value
        mock_query.all.return_value = mock_interactions

        activity = interaction_repo.get_team_activity()

        assert activity["total_interactions"] == 3
        assert activity["active_users"] == 2
        assert "command" in activity["interactions_by_type"]
        assert "callback" in activity["interactions_by_type"]

    def test_get_content_decisions(self, interaction_repo, mock_db):
        """Test getting content decision breakdown."""
        mock_decisions = [
            MagicMock(interaction_name="posted"),
            MagicMock(interaction_name="posted"),
            MagicMock(interaction_name="skip"),
            MagicMock(interaction_name="confirm_reject"),
        ]
        mock_query = mock_db.query.return_value
        mock_query.all.return_value = mock_decisions

        decisions = interaction_repo.get_content_decisions()

        assert decisions["total_decisions"] == 4
        assert decisions["posted"] == 2
        assert decisions["skipped"] == 1
        assert decisions["rejected"] == 1
        assert decisions["posted_percentage"] == 50.0
        assert "rejection_rate" in decisions

    def test_get_recent(self, interaction_repo, mock_db):
        """Test getting recent interactions."""
        mock_items = [MagicMock(), MagicMock()]
        mock_query = mock_db.query.return_value
        mock_query.all.return_value = mock_items

        result = interaction_repo.get_recent(days=7, limit=10)

        assert len(result) == 2

    def test_context_stores_json(self, interaction_repo, mock_db):
        """Test that context field properly stores JSON data."""
        complex_context = {
            "queue_item_id": "abc-123",
            "media_id": "def-456",
            "nested": {"key": "value"},
            "list": [1, 2, 3],
        }

        interaction_repo.create(
            user_id="some-user-id",
            interaction_type="callback",
            interaction_name="posted",
            context=complex_context,
        )

        added = mock_db.add.call_args[0][0]
        assert added.context == complex_context
        assert added.context["nested"]["key"] == "value"
        assert added.context["list"] == [1, 2, 3]

    def test_get_bot_responses_by_chat(self, interaction_repo, mock_db):
        """Test getting bot responses for a specific chat."""
        mock_responses = [
            MagicMock(telegram_message_id=1001),
            MagicMock(telegram_message_id=1002),
        ]
        mock_query = mock_db.query.return_value
        mock_query.all.return_value = mock_responses

        result = interaction_repo.get_bot_responses_by_chat(-1001234567890, hours=48)

        assert len(result) == 2
        message_ids = [r.telegram_message_id for r in result]
        assert 1001 in message_ids
        assert 1002 in message_ids
        mock_db.query.assert_called_with(UserInteraction)
