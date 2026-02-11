"""Tests for InstagramAccountRepository."""

import pytest
from unittest.mock import Mock, MagicMock, patch

from src.repositories.instagram_account_repository import InstagramAccountRepository
from src.models.instagram_account import InstagramAccount


@pytest.mark.unit
class TestInstagramAccountRepository:
    """Test suite for InstagramAccountRepository."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()

    @pytest.fixture
    def account_repo(self, mock_db):
        """Create InstagramAccountRepository with mocked database."""
        with patch("src.repositories.base_repository.get_db") as mock_get_db:
            mock_get_db.return_value = iter([mock_db])
            repo = InstagramAccountRepository()
            repo._db = mock_db
            return repo

    def test_get_all_active(self, account_repo, mock_db):
        """Test getting all active accounts."""
        mock_accounts = [
            Mock(display_name="Account A", is_active=True),
            Mock(display_name="Account B", is_active=True),
        ]
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_accounts

        result = account_repo.get_all_active()

        assert len(result) == 2
        mock_db.commit.assert_called_once()  # end_read_transaction

    def test_get_all_includes_inactive(self, account_repo, mock_db):
        """Test getting all accounts including inactive."""
        mock_accounts = [
            Mock(display_name="Active", is_active=True),
            Mock(display_name="Disabled", is_active=False),
        ]
        mock_db.query.return_value.order_by.return_value.all.return_value = (
            mock_accounts
        )

        result = account_repo.get_all()

        assert len(result) == 2

    def test_get_by_id(self, account_repo, mock_db):
        """Test getting account by UUID."""
        mock_account = Mock(id="acc-uuid-1")
        mock_db.query.return_value.filter.return_value.first.return_value = mock_account

        result = account_repo.get_by_id("acc-uuid-1")

        assert result is mock_account

    def test_get_by_username_strips_at(self, account_repo, mock_db):
        """Test that get_by_username strips leading @ from username."""
        mock_account = Mock(instagram_username="brand_main")
        mock_db.query.return_value.filter.return_value.first.return_value = mock_account

        result = account_repo.get_by_username("@brand_main")

        assert result is mock_account

    def test_get_by_instagram_id(self, account_repo, mock_db):
        """Test getting account by Instagram's external ID."""
        mock_account = Mock(instagram_account_id="17841234567890")
        mock_db.query.return_value.filter.return_value.first.return_value = mock_account

        result = account_repo.get_by_instagram_id("17841234567890")

        assert result is mock_account

    def test_create_strips_at_from_username(self, account_repo, mock_db):
        """Test that create strips @ from username."""
        account_repo.create(
            display_name="Test Account",
            instagram_account_id="123456",
            instagram_username="@test_user",
        )

        mock_db.add.assert_called_once()
        added_obj = mock_db.add.call_args[0][0]
        assert isinstance(added_obj, InstagramAccount)
        assert added_obj.instagram_username == "test_user"

    def test_update_account(self, account_repo, mock_db):
        """Test updating account fields."""
        mock_account = Mock(spec=InstagramAccount)
        mock_account.display_name = "Old Name"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_account

        account_repo.update("acc-uuid-1", display_name="New Name")

        assert mock_account.display_name == "New Name"
        mock_db.commit.assert_called()

    def test_update_not_found_raises(self, account_repo, mock_db):
        """Test updating non-existent account raises ValueError."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError, match="not found"):
            account_repo.update("nonexistent", display_name="Test")

    def test_deactivate(self, account_repo, mock_db):
        """Test deactivating an account sets is_active=False."""
        mock_account = Mock(spec=InstagramAccount)
        mock_account.is_active = True
        mock_db.query.return_value.filter.return_value.first.return_value = mock_account

        account_repo.deactivate("acc-uuid-1")

        assert mock_account.is_active is False

    def test_activate(self, account_repo, mock_db):
        """Test activating a deactivated account."""
        mock_account = Mock(spec=InstagramAccount)
        mock_account.is_active = False
        mock_db.query.return_value.filter.return_value.first.return_value = mock_account

        account_repo.activate("acc-uuid-1")

        assert mock_account.is_active is True

    def test_count_active(self, account_repo, mock_db):
        """Test counting active accounts."""
        mock_db.query.return_value.filter.return_value.count.return_value = 3

        result = account_repo.count_active()

        assert result == 3

    def test_get_by_id_prefix(self, account_repo, mock_db):
        """Test getting account by ID prefix (shortened UUID)."""
        mock_account = Mock(id="abcdef12-3456-7890-abcd-ef1234567890")
        mock_db.query.return_value.filter.return_value.first.return_value = mock_account

        result = account_repo.get_by_id_prefix("abcdef12")

        assert result is mock_account
