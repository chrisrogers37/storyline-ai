"""Tests for user CLI commands."""

import pytest
from unittest.mock import Mock, patch
from click.testing import CliRunner

from cli.commands.users import list_users, promote_user


@pytest.mark.unit
class TestListUsersCommand:
    """Tests for the list-users CLI command."""

    @patch("cli.commands.users.UserRepository")
    def test_list_users_shows_users(self, mock_repo_class):
        """Test list-users displays users in a table."""
        mock_repo = mock_repo_class.return_value

        mock_user = Mock()
        mock_user.telegram_username = "testuser"
        mock_user.telegram_user_id = 1000001
        mock_user.role = "admin"
        mock_user.total_posts = 42
        mock_user.is_active = True

        mock_repo.get_all.return_value = [mock_user]

        runner = CliRunner()
        result = runner.invoke(list_users, [])

        assert result.exit_code == 0
        assert "testuser" in result.output
        assert "admin" in result.output
        mock_repo.get_all.assert_called_once()

    @patch("cli.commands.users.UserRepository")
    def test_list_users_empty_database(self, mock_repo_class):
        """Test list-users shows message when no users found."""
        mock_repo = mock_repo_class.return_value
        mock_repo.get_all.return_value = []

        runner = CliRunner()
        result = runner.invoke(list_users, [])

        assert result.exit_code == 0
        assert "No users found" in result.output

    @patch("cli.commands.users.UserRepository")
    def test_list_users_without_username(self, mock_repo_class):
        """Test list-users shows telegram ID when username is None."""
        mock_repo = mock_repo_class.return_value

        mock_user = Mock()
        mock_user.telegram_username = None
        mock_user.telegram_user_id = 2000002
        mock_user.role = "member"
        mock_user.total_posts = 0
        mock_user.is_active = True

        mock_repo.get_all.return_value = [mock_user]

        runner = CliRunner()
        result = runner.invoke(list_users, [])

        assert result.exit_code == 0
        assert "2000002" in result.output


@pytest.mark.unit
class TestPromoteUserCommand:
    """Tests for the promote-user CLI command."""

    @patch("cli.commands.users.UserRepository")
    def test_promote_user_to_admin(self, mock_repo_class):
        """Test promote-user successfully promotes a user."""
        mock_repo = mock_repo_class.return_value

        mock_user = Mock()
        mock_user.id = "uuid-123"
        mock_user.telegram_username = "testuser"
        mock_user.role = "member"
        mock_repo.get_by_telegram_id.return_value = mock_user

        runner = CliRunner()
        result = runner.invoke(promote_user, ["3000003", "--role", "admin"])

        assert result.exit_code == 0
        mock_repo.get_by_telegram_id.assert_called_once_with(3000003)
        mock_repo.update_role.assert_called_once_with("uuid-123", "admin")

    @patch("cli.commands.users.UserRepository")
    def test_promote_user_nonexistent(self, mock_repo_class):
        """Test promote-user with non-existent user shows error."""
        mock_repo = mock_repo_class.return_value
        mock_repo.get_by_telegram_id.return_value = None

        runner = CliRunner()
        result = runner.invoke(promote_user, ["9999999", "--role", "admin"])

        assert result.exit_code != 0
        assert "User not found" in result.output
        mock_repo.update_role.assert_not_called()

    def test_promote_user_invalid_role(self):
        """Test promote-user with invalid role is rejected by Click."""
        runner = CliRunner()
        result = runner.invoke(promote_user, ["3000004", "--role", "superadmin"])

        assert result.exit_code == 2
        assert "Invalid value" in result.output or "invalid" in result.output.lower()
