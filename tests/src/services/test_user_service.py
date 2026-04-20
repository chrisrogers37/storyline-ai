"""Tests for UserService — user management operations."""

from unittest.mock import Mock, patch

import pytest

from src.services.core.user_service import UserService


@pytest.fixture
def user_service():
    """UserService with mocked __init__ and dependencies."""
    with patch.object(UserService, "__init__", lambda self: None):
        service = UserService()
        service.user_repo = Mock()
        return service


# ──────────────────────────────────────────────────────────────
# list_users
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestListUsers:
    def test_returns_all_users(self, user_service):
        """Returns all users without filter."""
        users = [Mock(), Mock()]
        user_service.user_repo.get_all.return_value = users

        result = user_service.list_users()

        assert result == users
        user_service.user_repo.get_all.assert_called_once_with(is_active=None)

    def test_filters_by_active(self, user_service):
        """Passes is_active filter to repository."""
        user_service.user_repo.get_all.return_value = [Mock()]

        result = user_service.list_users(is_active=True)

        assert len(result) == 1
        user_service.user_repo.get_all.assert_called_once_with(is_active=True)

    def test_returns_empty_list(self, user_service):
        """Returns empty list when no users match."""
        user_service.user_repo.get_all.return_value = []

        result = user_service.list_users(is_active=False)

        assert result == []


# ──────────────────────────────────────────────────────────────
# get_by_telegram_id
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestGetByTelegramId:
    def test_returns_user(self, user_service):
        """Returns user when found."""
        user = Mock()
        user_service.user_repo.get_by_telegram_id.return_value = user

        result = user_service.get_by_telegram_id(123456)

        assert result is user
        user_service.user_repo.get_by_telegram_id.assert_called_once_with(123456)

    def test_returns_none_when_not_found(self, user_service):
        """Returns None when user doesn't exist."""
        user_service.user_repo.get_by_telegram_id.return_value = None

        result = user_service.get_by_telegram_id(999999)

        assert result is None


# ──────────────────────────────────────────────────────────────
# promote_user
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestPromoteUser:
    def test_updates_role(self, user_service):
        """Changes user role and returns user."""
        user = Mock(id="user-1")
        user_service.user_repo.get_by_telegram_id.return_value = user

        result = user_service.promote_user(123456, "admin")

        assert result is user
        user_service.user_repo.update_role.assert_called_once_with("user-1", "admin")

    def test_raises_for_unknown_user(self, user_service):
        """Raises ValueError when user not found."""
        user_service.user_repo.get_by_telegram_id.return_value = None

        with pytest.raises(ValueError, match="User not found"):
            user_service.promote_user(999999, "admin")

        user_service.user_repo.update_role.assert_not_called()
