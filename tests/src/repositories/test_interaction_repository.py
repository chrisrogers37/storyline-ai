"""Tests for InteractionRepository."""

import pytest
from uuid import UUID

from src.repositories.interaction_repository import InteractionRepository


@pytest.mark.unit
class TestInteractionRepository:
    """Test suite for InteractionRepository."""

    @pytest.mark.skip(reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/")
    def test_create_command_interaction(self, test_db):
        """Test creating a command interaction."""
        # First create a user to reference
        from src.repositories.user_repository import UserRepository

        user_repo = UserRepository()
        user = user_repo.create(telegram_user_id=900001)

        repo = InteractionRepository()
        interaction = repo.create(
            user_id=str(user.id),
            interaction_type="command",
            interaction_name="/status",
            context={"queue_size": 5},
            telegram_chat_id=123456,
            telegram_message_id=789,
        )

        assert interaction.id is not None
        assert isinstance(interaction.id, UUID)
        assert interaction.interaction_type == "command"
        assert interaction.interaction_name == "/status"
        assert interaction.context == {"queue_size": 5}
        assert interaction.telegram_chat_id == 123456

    @pytest.mark.skip(reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/")
    def test_create_callback_interaction(self, test_db):
        """Test creating a callback interaction."""
        from src.repositories.user_repository import UserRepository

        user_repo = UserRepository()
        user = user_repo.create(telegram_user_id=900002)

        repo = InteractionRepository()
        interaction = repo.create(
            user_id=str(user.id),
            interaction_type="callback",
            interaction_name="posted",
            context={"queue_item_id": "abc123", "media_filename": "test.jpg"},
        )

        assert interaction.interaction_type == "callback"
        assert interaction.interaction_name == "posted"
        assert interaction.context["media_filename"] == "test.jpg"

    @pytest.mark.skip(reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/")
    def test_get_by_user(self, test_db):
        """Test getting interactions by user."""
        from src.repositories.user_repository import UserRepository

        user_repo = UserRepository()
        user = user_repo.create(telegram_user_id=900003)

        repo = InteractionRepository()

        # Create multiple interactions
        repo.create(
            user_id=str(user.id), interaction_type="command", interaction_name="/status"
        )
        repo.create(
            user_id=str(user.id), interaction_type="callback", interaction_name="posted"
        )
        repo.create(
            user_id=str(user.id), interaction_type="command", interaction_name="/queue"
        )

        interactions = repo.get_by_user(str(user.id))

        assert len(interactions) == 3

    @pytest.mark.skip(reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/")
    def test_get_by_type(self, test_db):
        """Test getting interactions by type."""
        from src.repositories.user_repository import UserRepository

        user_repo = UserRepository()
        user = user_repo.create(telegram_user_id=900004)

        repo = InteractionRepository()

        # Create mixed interactions
        repo.create(
            user_id=str(user.id), interaction_type="command", interaction_name="/status"
        )
        repo.create(
            user_id=str(user.id), interaction_type="callback", interaction_name="posted"
        )
        repo.create(
            user_id=str(user.id), interaction_type="command", interaction_name="/queue"
        )

        commands = repo.get_by_type("command")
        callbacks = repo.get_by_type("callback")

        assert len([i for i in commands if str(i.user_id) == str(user.id)]) >= 2
        assert len([i for i in callbacks if str(i.user_id) == str(user.id)]) >= 1

    @pytest.mark.skip(reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/")
    def test_get_by_name(self, test_db):
        """Test getting interactions by name."""
        from src.repositories.user_repository import UserRepository

        user_repo = UserRepository()
        user = user_repo.create(telegram_user_id=900005)

        repo = InteractionRepository()

        # Create interactions with same name
        repo.create(
            user_id=str(user.id), interaction_type="callback", interaction_name="posted"
        )
        repo.create(
            user_id=str(user.id), interaction_type="callback", interaction_name="posted"
        )
        repo.create(
            user_id=str(user.id), interaction_type="callback", interaction_name="skip"
        )

        posted = repo.get_by_name("posted")

        assert len([i for i in posted if str(i.user_id) == str(user.id)]) >= 2

    @pytest.mark.skip(reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/")
    def test_count_by_user(self, test_db):
        """Test counting interactions by user."""
        from src.repositories.user_repository import UserRepository

        user_repo = UserRepository()
        user = user_repo.create(telegram_user_id=900006)

        repo = InteractionRepository()

        # Create interactions
        repo.create(
            user_id=str(user.id), interaction_type="command", interaction_name="/status"
        )
        repo.create(
            user_id=str(user.id), interaction_type="callback", interaction_name="posted"
        )

        count = repo.count_by_user(str(user.id))

        assert count >= 2

    @pytest.mark.skip(reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/")
    def test_count_by_name(self, test_db):
        """Test counting interactions by name."""
        from src.repositories.user_repository import UserRepository

        user_repo = UserRepository()
        user = user_repo.create(telegram_user_id=900007)

        repo = InteractionRepository()

        # Create interactions
        repo.create(
            user_id=str(user.id), interaction_type="callback", interaction_name="posted"
        )
        repo.create(
            user_id=str(user.id), interaction_type="callback", interaction_name="posted"
        )
        repo.create(
            user_id=str(user.id), interaction_type="callback", interaction_name="skip"
        )

        posted_count = repo.count_by_name("posted")
        skip_count = repo.count_by_name("skip")

        assert posted_count >= 2
        assert skip_count >= 1

    @pytest.mark.skip(reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/")
    def test_get_user_stats(self, test_db):
        """Test getting aggregated user stats."""
        from src.repositories.user_repository import UserRepository

        user_repo = UserRepository()
        user = user_repo.create(telegram_user_id=900008)

        repo = InteractionRepository()

        # Create diverse interactions
        repo.create(
            user_id=str(user.id), interaction_type="callback", interaction_name="posted"
        )
        repo.create(
            user_id=str(user.id), interaction_type="callback", interaction_name="posted"
        )
        repo.create(
            user_id=str(user.id), interaction_type="callback", interaction_name="skip"
        )
        repo.create(
            user_id=str(user.id),
            interaction_type="callback",
            interaction_name="confirm_reject",
        )
        repo.create(
            user_id=str(user.id), interaction_type="command", interaction_name="/status"
        )

        stats = repo.get_user_stats(str(user.id))

        assert stats["total_interactions"] >= 5
        assert stats["posts_marked"] >= 2
        assert stats["posts_skipped"] >= 1
        assert stats["posts_rejected"] >= 1
        assert "/status" in stats["commands_used"]

    @pytest.mark.skip(reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/")
    def test_get_team_activity(self, test_db):
        """Test getting team-wide activity."""
        from src.repositories.user_repository import UserRepository

        user_repo = UserRepository()
        user1 = user_repo.create(telegram_user_id=900009)
        user2 = user_repo.create(telegram_user_id=900010)

        repo = InteractionRepository()

        # Create interactions from multiple users
        repo.create(
            user_id=str(user1.id),
            interaction_type="callback",
            interaction_name="posted",
        )
        repo.create(
            user_id=str(user2.id), interaction_type="callback", interaction_name="skip"
        )
        repo.create(
            user_id=str(user1.id),
            interaction_type="command",
            interaction_name="/status",
        )

        activity = repo.get_team_activity()

        assert activity["total_interactions"] >= 3
        assert activity["active_users"] >= 2
        assert "command" in activity["interactions_by_type"]
        assert "callback" in activity["interactions_by_type"]

    @pytest.mark.skip(reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/")
    def test_get_content_decisions(self, test_db):
        """Test getting content decision breakdown."""
        from src.repositories.user_repository import UserRepository

        user_repo = UserRepository()
        user = user_repo.create(telegram_user_id=900011)

        repo = InteractionRepository()

        # Create decision callbacks
        repo.create(
            user_id=str(user.id), interaction_type="callback", interaction_name="posted"
        )
        repo.create(
            user_id=str(user.id), interaction_type="callback", interaction_name="posted"
        )
        repo.create(
            user_id=str(user.id), interaction_type="callback", interaction_name="skip"
        )
        repo.create(
            user_id=str(user.id),
            interaction_type="callback",
            interaction_name="confirm_reject",
        )

        decisions = repo.get_content_decisions()

        assert decisions["total_decisions"] >= 4
        assert decisions["posted"] >= 2
        assert decisions["skipped"] >= 1
        assert decisions["rejected"] >= 1
        assert "posted_percentage" in decisions
        assert "rejection_rate" in decisions

    @pytest.mark.skip(reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/")
    def test_get_recent(self, test_db):
        """Test getting recent interactions."""
        from src.repositories.user_repository import UserRepository

        user_repo = UserRepository()
        user = user_repo.create(telegram_user_id=900012)

        repo = InteractionRepository()

        # Create interactions
        repo.create(
            user_id=str(user.id), interaction_type="command", interaction_name="/status"
        )
        repo.create(
            user_id=str(user.id), interaction_type="callback", interaction_name="posted"
        )

        recent = repo.get_recent(days=7, limit=10)

        assert len(recent) >= 2

    @pytest.mark.skip(reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/")
    def test_context_stores_json(self, test_db):
        """Test that context field properly stores JSON data."""
        from src.repositories.user_repository import UserRepository

        user_repo = UserRepository()
        user = user_repo.create(telegram_user_id=900013)

        repo = InteractionRepository()

        complex_context = {
            "queue_item_id": "abc-123",
            "media_id": "def-456",
            "nested": {"key": "value"},
            "list": [1, 2, 3],
        }

        interaction = repo.create(
            user_id=str(user.id),
            interaction_type="callback",
            interaction_name="posted",
            context=complex_context,
        )

        assert interaction.context == complex_context
        assert interaction.context["nested"]["key"] == "value"
        assert interaction.context["list"] == [1, 2, 3]

    @pytest.mark.skip(reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/")
    def test_get_bot_responses_by_chat(self, test_db):
        """Test getting bot responses for a specific chat within 48 hours."""
        repo = InteractionRepository()

        chat_id = -1001234567890

        # Create bot_response interactions with telegram_message_id
        repo.create(
            user_id=None,
            interaction_type="bot_response",
            interaction_name="photo_notification",
            context={"caption": "Test caption"},
            telegram_chat_id=chat_id,
            telegram_message_id=1001,
        )
        repo.create(
            user_id=None,
            interaction_type="bot_response",
            interaction_name="status_message",
            context={},
            telegram_chat_id=chat_id,
            telegram_message_id=1002,
        )
        # Different chat - should not be returned
        repo.create(
            user_id=None,
            interaction_type="bot_response",
            interaction_name="photo_notification",
            telegram_chat_id=-1009999999999,
            telegram_message_id=2001,
        )
        # Command interaction - should not be returned
        from src.repositories.user_repository import UserRepository
        user_repo = UserRepository()
        user = user_repo.create(telegram_user_id=900020)
        repo.create(
            user_id=str(user.id),
            interaction_type="command",
            interaction_name="/status",
            telegram_chat_id=chat_id,
            telegram_message_id=3001,
        )

        responses = repo.get_bot_responses_by_chat(chat_id, hours=48)

        # Should only get bot_response types for the specified chat
        assert len(responses) == 2
        message_ids = [r.telegram_message_id for r in responses]
        assert 1001 in message_ids
        assert 1002 in message_ids
        assert 2001 not in message_ids  # Different chat
        assert 3001 not in message_ids  # Not a bot_response

    @pytest.mark.skip(reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/")
    def test_get_bot_responses_by_chat_excludes_null_message_ids(self, test_db):
        """Test that responses without telegram_message_id are excluded."""
        repo = InteractionRepository()

        chat_id = -1001234567890

        # Create response with message_id
        repo.create(
            user_id=None,
            interaction_type="bot_response",
            interaction_name="photo_notification",
            telegram_chat_id=chat_id,
            telegram_message_id=1001,
        )
        # Create response without message_id
        repo.create(
            user_id=None,
            interaction_type="bot_response",
            interaction_name="photo_notification",
            telegram_chat_id=chat_id,
            telegram_message_id=None,
        )

        responses = repo.get_bot_responses_by_chat(chat_id, hours=48)

        assert len(responses) == 1
        assert responses[0].telegram_message_id == 1001
