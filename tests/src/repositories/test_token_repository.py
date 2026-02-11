"""Tests for TokenRepository."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta

from src.repositories.token_repository import TokenRepository
from src.models.api_token import ApiToken


@pytest.mark.unit
class TestTokenRepository:
    """Test suite for TokenRepository."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()

    @pytest.fixture
    def token_repo(self, mock_db):
        """Create TokenRepository with mocked database."""
        with patch("src.repositories.base_repository.get_db") as mock_get_db:
            mock_get_db.return_value = iter([mock_db])
            repo = TokenRepository()
            repo._db = mock_db
            return repo

    def test_get_token_found(self, token_repo, mock_db):
        """Test getting a token by service name and type."""
        mock_token = Mock(spec=ApiToken)
        mock_token.service_name = "instagram"
        mock_token.token_type = "access_token"
        # get_token chains two .filter() calls (service/type + account_id)
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = mock_token

        result = token_repo.get_token("instagram", "access_token")

        assert result is mock_token

    def test_get_token_not_found(self, token_repo, mock_db):
        """Test getting a non-existent token returns None."""
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = None

        result = token_repo.get_token("instagram", "access_token")

        assert result is None

    def test_get_token_with_account_id(self, token_repo, mock_db):
        """Test getting a token filtered by account ID."""
        mock_token = Mock(spec=ApiToken)
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = mock_token

        result = token_repo.get_token(
            "instagram", "access_token", instagram_account_id="acc-uuid-1"
        )

        assert result is mock_token

    def test_get_token_for_account(self, token_repo, mock_db):
        """Test convenience method for getting Instagram token by account."""
        mock_token = Mock(spec=ApiToken)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_token

        result = token_repo.get_token_for_account("acc-uuid-1")

        assert result is mock_token

    def test_get_all_instagram_tokens(self, token_repo, mock_db):
        """Test getting all Instagram tokens for refresh iteration."""
        mock_tokens = [Mock(spec=ApiToken), Mock(spec=ApiToken)]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_tokens

        result = token_repo.get_all_instagram_tokens()

        assert len(result) == 2

    def test_create_or_update_creates_new_token(self, token_repo, mock_db):
        """Test create_or_update creates a new token when none exists."""
        # get_token uses double filter chain
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = None

        token_repo.create_or_update(
            service_name="instagram",
            token_type="access_token",
            token_value="encrypted_value",
            issued_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=60),
            scopes=["instagram_basic", "instagram_content_publish"],
            metadata={"method": "cli_wizard"},
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called()
        added_obj = mock_db.add.call_args[0][0]
        assert isinstance(added_obj, ApiToken)
        assert added_obj.service_name == "instagram"
        assert added_obj.token_value == "encrypted_value"

    def test_create_or_update_updates_existing_token(self, token_repo, mock_db):
        """Test create_or_update updates when token already exists."""
        existing_token = Mock(spec=ApiToken)
        existing_token.token_value = "old_encrypted"
        # get_token uses double filter chain
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = existing_token

        token_repo.create_or_update(
            service_name="instagram",
            token_type="access_token",
            token_value="new_encrypted",
            expires_at=datetime.utcnow() + timedelta(days=60),
            scopes=["instagram_basic"],
        )

        mock_db.add.assert_not_called()
        assert existing_token.token_value == "new_encrypted"
        mock_db.commit.assert_called()

    def test_update_last_refreshed(self, token_repo, mock_db):
        """Test updating last_refreshed_at timestamp."""
        mock_token = Mock(spec=ApiToken)
        # update_last_refreshed calls get_token which uses double filter
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = mock_token

        result = token_repo.update_last_refreshed("instagram", "access_token")

        assert result is True
        assert mock_token.last_refreshed_at is not None
        mock_db.commit.assert_called()

    def test_update_last_refreshed_not_found(self, token_repo, mock_db):
        """Test update_last_refreshed returns False when token not found."""
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = None

        result = token_repo.update_last_refreshed("instagram", "access_token")

        assert result is False

    def test_get_expiring_tokens(self, token_repo, mock_db):
        """Test getting tokens expiring within threshold."""
        mock_tokens = [Mock(spec=ApiToken)]
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_tokens

        result = token_repo.get_expiring_tokens(hours_until_expiry=168)

        assert len(result) == 1

    def test_delete_token_found(self, token_repo, mock_db):
        """Test deleting an existing token."""
        mock_token = Mock(spec=ApiToken)
        # delete_token calls get_token which uses double filter
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = mock_token

        result = token_repo.delete_token("instagram", "access_token")

        assert result is True
        mock_db.delete.assert_called_once_with(mock_token)

    def test_delete_token_not_found(self, token_repo, mock_db):
        """Test deleting non-existent token returns False."""
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = None

        result = token_repo.delete_token("instagram", "access_token")

        assert result is False

    def test_delete_all_for_service(self, token_repo, mock_db):
        """Test deleting all tokens for a service."""
        mock_db.query.return_value.filter.return_value.delete.return_value = 3

        result = token_repo.delete_all_for_service("instagram")

        assert result == 3
        mock_db.commit.assert_called()

    def test_get_expired_tokens(self, token_repo, mock_db):
        """Test getting all expired tokens."""
        mock_tokens = [Mock(spec=ApiToken)]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_tokens

        result = token_repo.get_expired_tokens()

        assert len(result) == 1
