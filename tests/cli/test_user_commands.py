"""Tests for user CLI commands."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from click.testing import CliRunner

from cli.commands.users import list_users, promote_user


@pytest.mark.unit
class TestListUsersCommand:
    """Tests for the list-users CLI command."""

    @patch("cli.commands.users.UserService")
    def test_list_users_shows_users(self, mock_service_class):
        """Test list-users displays users in a table."""
        mock_service = MagicMock()
        mock_service_class.return_value.__enter__ = Mock(return_value=mock_service)
        mock_service_class.return_value.__exit__ = Mock(return_value=False)

        mock_user = Mock()
        mock_user.telegram_username = "testuser"
        mock_user.telegram_user_id = 1000001
        mock_user.role = "admin"
        mock_user.total_posts = 42
        mock_user.is_active = True

        mock_service.list_users.return_value = [mock_user]

        runner = CliRunner()
        result = runner.invoke(list_users, [])

        assert result.exit_code == 0
        assert "testuser" in result.output
        assert "admin" in result.output

    @patch("cli.commands.users.UserService")
    def test_list_users_empty_database(self, mock_service_class):
        """Test list-users shows message when no users found."""
        mock_service = MagicMock()
        mock_service_class.return_value.__enter__ = Mock(return_value=mock_service)
        mock_service_class.return_value.__exit__ = Mock(return_value=False)

        mock_service.list_users.return_value = []

        runner = CliRunner()
        result = runner.invoke(list_users, [])

        assert result.exit_code == 0
        assert "No users found" in result.output

    @patch("cli.commands.users.UserService")
    def test_list_users_without_username(self, mock_service_class):
        """Test list-users shows telegram ID when username is None."""
        mock_service = MagicMock()
        mock_service_class.return_value.__enter__ = Mock(return_value=mock_service)
        mock_service_class.return_value.__exit__ = Mock(return_value=False)

        mock_user = Mock()
        mock_user.telegram_username = None
        mock_user.telegram_user_id = 2000002
        mock_user.role = "member"
        mock_user.total_posts = 0
        mock_user.is_active = True

        mock_service.list_users.return_value = [mock_user]

        runner = CliRunner()
        result = runner.invoke(list_users, [])

        assert result.exit_code == 0
        assert "2000002" in result.output


@pytest.mark.unit
class TestPromoteUserCommand:
    """Tests for the promote-user CLI command."""

    @patch("cli.commands.users.UserService")
    def test_promote_user_to_admin(self, mock_service_class):
        """Test promote-user successfully promotes a user."""
        mock_service = MagicMock()
        mock_service_class.return_value.__enter__ = Mock(return_value=mock_service)
        mock_service_class.return_value.__exit__ = Mock(return_value=False)

        mock_user = Mock()
        mock_user.id = "uuid-123"
        mock_user.telegram_username = "testuser"
        mock_user.role = "admin"
        mock_service.promote_user.return_value = mock_user

        runner = CliRunner()
        result = runner.invoke(promote_user, ["3000003", "--role", "admin"])

        assert result.exit_code == 0
        mock_service.promote_user.assert_called_once_with(3000003, "admin")

    @patch("cli.commands.users.UserService")
    def test_promote_user_nonexistent(self, mock_service_class):
        """Test promote-user with non-existent user shows error."""
        mock_service = MagicMock()
        mock_service_class.return_value.__enter__ = Mock(return_value=mock_service)
        mock_service_class.return_value.__exit__ = Mock(return_value=False)

        mock_service.promote_user.side_effect = ValueError("User not found: 9999999")

        runner = CliRunner()
        result = runner.invoke(promote_user, ["9999999", "--role", "admin"])

        assert result.exit_code != 0
        assert "User not found" in result.output

    def test_promote_user_invalid_role(self):
        """Test promote-user with invalid role is rejected by Click."""
        runner = CliRunner()
        result = runner.invoke(promote_user, ["3000004", "--role", "superadmin"])

        assert result.exit_code == 2
        assert "Invalid value" in result.output or "invalid" in result.output.lower()
