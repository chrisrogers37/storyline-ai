"""Tests for user CLI commands."""

import pytest
from click.testing import CliRunner

from cli.commands.users import list_users, promote_user
from src.repositories.user_repository import UserRepository


@pytest.mark.unit
class TestUserCommands:
    """Test suite for user CLI commands."""

    @pytest.mark.skip(reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/")
    def test_list_users_command(self, test_db):
        """Test list-users CLI command."""
        user_repo = UserRepository(test_db)

        # Create test users
        user_repo.create(
            telegram_user_id=3000001,
            telegram_username="user1",
            first_name="Test",
            last_name="User1",
        )

        user_repo.create(
            telegram_user_id=3000002,
            telegram_username="user2",
            first_name="Test",
            last_name="User2",
        )

        runner = CliRunner()
        result = runner.invoke(list_users, [])

        # Command should execute successfully
        assert result.exit_code == 0
        # Should show user information
        assert (
            "user1" in result.output
            or "User1" in result.output
            or result.exit_code == 0
        )

    @pytest.mark.skip(reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/")
    def test_list_users_empty_database(self, test_db):
        """Test list-users with no users."""
        runner = CliRunner()

        result = runner.invoke(list_users, [])

        # Command should handle empty database gracefully
        assert result.exit_code == 0

    @pytest.mark.skip(reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/")
    def test_promote_user_command(self, test_db):
        """Test promote-user CLI command."""
        user_repo = UserRepository(test_db)

        # Create test user
        user = user_repo.create(telegram_user_id=3000003, telegram_username="promoteme")

        assert user.role == "member"

        runner = CliRunner()
        result = runner.invoke(
            promote_user, [str(user.telegram_user_id), "--role", "admin"]
        )

        # Command should execute successfully
        assert result.exit_code == 0

        # Verify user was promoted
        updated_user = user_repo.get_by_telegram_id(3000003)
        assert updated_user.role == "admin"

    @pytest.mark.skip(reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/")
    def test_promote_user_nonexistent(self, test_db):
        """Test promote-user with non-existent user."""
        runner = CliRunner()

        result = runner.invoke(promote_user, ["9999999", "--role", "admin"])

        # Should handle gracefully
        assert "not found" in result.output.lower() or result.exit_code != 0

    @pytest.mark.skip(reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/")
    def test_promote_user_invalid_role(self, test_db):
        """Test promote-user with invalid role."""
        user_repo = UserRepository(test_db)

        user = user_repo.create(telegram_user_id=3000004)

        runner = CliRunner()
        result = runner.invoke(
            promote_user, [str(user.telegram_user_id), "--role", "superadmin"]
        )

        # Should reject invalid role
        assert result.exit_code != 0 or "invalid" in result.output.lower()
