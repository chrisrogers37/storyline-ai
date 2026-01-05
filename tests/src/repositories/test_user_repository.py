"""Tests for UserRepository."""
import pytest
from uuid import UUID

from src.repositories.user_repository import UserRepository
from src.models.user import User


@pytest.mark.unit
class TestUserRepository:
    """Test suite for UserRepository."""

    def test_create_user(self, test_db):
        """Test creating a new user."""
        repo = UserRepository(test_db)

        user = repo.create(
            telegram_user_id=123456789,
            telegram_username="testuser",
            first_name="Test",
            last_name="User"
        )

        assert user.id is not None
        assert isinstance(user.id, UUID)
        assert user.telegram_user_id == 123456789
        assert user.telegram_username == "testuser"
        assert user.first_name == "Test"
        assert user.last_name == "User"
        assert user.role == "member"
        assert user.total_posts == 0

    def test_get_by_telegram_id(self, test_db):
        """Test retrieving user by Telegram ID."""
        repo = UserRepository(test_db)

        # Create user
        created_user = repo.create(
            telegram_user_id=987654321,
            telegram_username="findme"
        )

        # Retrieve user
        found_user = repo.get_by_telegram_id(987654321)

        assert found_user is not None
        assert found_user.id == created_user.id
        assert found_user.telegram_user_id == 987654321

    def test_get_by_telegram_id_not_found(self, test_db):
        """Test retrieving non-existent user."""
        repo = UserRepository(test_db)

        user = repo.get_by_telegram_id(999999999)

        assert user is None

    def test_get_or_create_existing_user(self, test_db):
        """Test get_or_create with existing user."""
        repo = UserRepository(test_db)

        # Create user
        original_user = repo.create(
            telegram_user_id=111222333,
            telegram_username="existing"
        )

        # Get or create should return existing user
        user, created = repo.get_or_create(
            telegram_user_id=111222333,
            telegram_username="existing"
        )

        assert not created
        assert user.id == original_user.id

    def test_get_or_create_new_user(self, test_db):
        """Test get_or_create with new user."""
        repo = UserRepository(test_db)

        user, created = repo.get_or_create(
            telegram_user_id=444555666,
            telegram_username="newuser"
        )

        assert created
        assert user.telegram_user_id == 444555666

    def test_increment_posts(self, test_db):
        """Test incrementing user post count."""
        repo = UserRepository(test_db)

        user = repo.create(telegram_user_id=777888999)
        assert user.total_posts == 0

        # Increment posts
        updated_user = repo.increment_posts(user.id)

        assert updated_user.total_posts == 1
        assert updated_user.last_seen is not None

    def test_update_role(self, test_db):
        """Test updating user role."""
        repo = UserRepository(test_db)

        user = repo.create(telegram_user_id=111000111)
        assert user.role == "member"

        # Promote to admin
        updated_user = repo.update_role(user.id, "admin")

        assert updated_user.role == "admin"

    def test_list_all_users(self, test_db):
        """Test listing all users."""
        repo = UserRepository(test_db)

        # Create multiple users
        repo.create(telegram_user_id=100001)
        repo.create(telegram_user_id=100002)
        repo.create(telegram_user_id=100003)

        users = repo.list_all()

        assert len(users) >= 3

    def test_get_by_id(self, test_db):
        """Test retrieving user by UUID."""
        repo = UserRepository(test_db)

        user = repo.create(telegram_user_id=200001)

        found_user = repo.get_by_id(user.id)

        assert found_user is not None
        assert found_user.id == user.id
