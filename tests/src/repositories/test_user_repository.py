"""Tests for UserRepository."""

import pytest
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from src.repositories.user_repository import UserRepository
from src.models.user import User


@pytest.fixture
def mock_db():
    """Create a mock database session with chainable query."""
    session = MagicMock(spec=Session)
    mock_query = MagicMock()
    session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    return session


@pytest.fixture
def user_repo(mock_db):
    """Create UserRepository with mocked database session."""
    with patch.object(UserRepository, "__init__", lambda self: None):
        repo = UserRepository()
        repo._db = mock_db
        return repo


@pytest.mark.unit
class TestUserRepository:
    """Test suite for UserRepository."""

    def test_create_user(self, user_repo, mock_db):
        """Test creating a new user."""
        user_repo.create(
            telegram_user_id=123456789,
            telegram_username="testuser",
            telegram_first_name="Test",
            telegram_last_name="User",
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

        added_user = mock_db.add.call_args[0][0]
        assert isinstance(added_user, User)
        assert added_user.telegram_user_id == 123456789
        assert added_user.telegram_username == "testuser"
        assert added_user.telegram_first_name == "Test"
        assert added_user.telegram_last_name == "User"
        assert added_user.role == "member"

    def test_create_user_with_role(self, user_repo, mock_db):
        """Test creating a user with custom role."""
        user_repo.create(
            telegram_user_id=123456789,
            telegram_username="admin",
            role="admin",
        )

        added_user = mock_db.add.call_args[0][0]
        assert added_user.role == "admin"

    def test_get_by_telegram_id(self, user_repo, mock_db):
        """Test retrieving user by Telegram ID."""
        mock_user = MagicMock(telegram_user_id=987654321)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        result = user_repo.get_by_telegram_id(987654321)

        assert result is mock_user
        assert result.telegram_user_id == 987654321
        mock_db.query.assert_called_with(User)

    def test_get_by_telegram_id_not_found(self, user_repo, mock_db):
        """Test retrieving non-existent user returns None."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = user_repo.get_by_telegram_id(999999999)

        assert result is None

    def test_increment_posts(self, user_repo, mock_db):
        """Test incrementing user post count."""
        mock_user = MagicMock()
        mock_user.total_posts = 0
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        user_repo.increment_posts("some-user-id")

        assert mock_user.total_posts == 1
        assert mock_user.last_seen_at is not None
        mock_db.commit.assert_called_once()

    def test_update_role(self, user_repo, mock_db):
        """Test updating user role."""
        mock_user = MagicMock()
        mock_user.role = "member"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        user_repo.update_role("some-user-id", "admin")

        assert mock_user.role == "admin"
        mock_db.commit.assert_called_once()

    def test_get_all_users(self, user_repo, mock_db):
        """Test listing all users."""
        mock_users = [MagicMock(), MagicMock(), MagicMock()]
        mock_query = mock_db.query.return_value
        mock_query.all.return_value = mock_users

        result = user_repo.get_all()

        assert len(result) == 3
        mock_db.query.assert_called_with(User)

    def test_get_by_id(self, user_repo, mock_db):
        """Test retrieving user by UUID."""
        mock_user = MagicMock(id="some-uuid")
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        result = user_repo.get_by_id("some-uuid")

        assert result is mock_user

    def test_update_profile(self, user_repo, mock_db):
        """Test updating user profile data."""
        mock_user = MagicMock()
        mock_user.telegram_username = "oldname"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        user_repo.update_profile(
            "some-user-id",
            telegram_username="newname",
            telegram_first_name="New",
            telegram_last_name="Person",
        )

        assert mock_user.telegram_username == "newname"
        assert mock_user.telegram_first_name == "New"
        assert mock_user.telegram_last_name == "Person"
        assert mock_user.last_seen_at is not None
        mock_db.commit.assert_called_once()

    def test_update_profile_adds_username(self, user_repo, mock_db):
        """Test adding username to user who didn't have one."""
        mock_user = MagicMock()
        mock_user.telegram_username = None
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        user_repo.update_profile(
            "some-user-id",
            telegram_username="newlyaddedusername",
            telegram_first_name="NoUsername",
        )

        assert mock_user.telegram_username == "newlyaddedusername"

    def test_update_profile_removes_username(self, user_repo, mock_db):
        """Test removing username from user profile."""
        mock_user = MagicMock()
        mock_user.telegram_username = "hasusername"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        user_repo.update_profile(
            "some-user-id",
            telegram_username=None,
            telegram_first_name="Has",
        )

        assert mock_user.telegram_username is None

    def test_update_profile_nonexistent_user(self, user_repo, mock_db):
        """Test updating profile of non-existent user returns None."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = user_repo.update_profile(
            "00000000-0000-0000-0000-000000000000",
            telegram_username="nobody",
            telegram_first_name="Nobody",
        )

        assert result is None
        mock_db.commit.assert_not_called()
