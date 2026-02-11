"""Tests for Instagram CLI commands."""

import pytest
from unittest.mock import Mock, patch
from click.testing import CliRunner
from datetime import datetime, timedelta

from cli.commands.instagram import (
    instagram_status,
    add_instagram_account,
    list_instagram_accounts,
    deactivate_instagram_account,
    reactivate_instagram_account,
)


@pytest.mark.unit
class TestInstagramStatusCommand:
    """Tests for the instagram-status CLI command."""

    @patch("cli.commands.instagram.TokenRefreshService")
    @patch("cli.commands.instagram.settings")
    def test_instagram_status_authenticated(self, mock_settings, mock_service_class):
        """Test instagram-status shows authenticated status."""
        mock_service = mock_service_class.return_value
        mock_service.check_token_health.return_value = {
            "valid": True,
            "exists": True,
            "source": "database",
            "expires_at": datetime.utcnow() + timedelta(days=30),
            "expires_in_hours": 720,
            "needs_refresh": False,
            "needs_bootstrap": False,
            "last_refreshed": datetime.utcnow(),
        }
        mock_settings.ENABLE_INSTAGRAM_API = True
        mock_settings.INSTAGRAM_ACCOUNT_ID = "12345"
        mock_settings.FACEBOOK_APP_ID = "app123"
        mock_settings.CLOUDINARY_CLOUD_NAME = "mycloud"

        runner = CliRunner()
        result = runner.invoke(instagram_status)

        assert result.exit_code == 0
        assert "Authenticated" in result.output

    @patch("cli.commands.instagram.TokenRefreshService")
    @patch("cli.commands.instagram.settings")
    def test_instagram_status_not_authenticated(
        self, mock_settings, mock_service_class
    ):
        """Test instagram-status shows not authenticated when no token."""
        mock_service = mock_service_class.return_value
        mock_service.check_token_health.return_value = {
            "valid": False,
            "exists": False,
            "source": None,
            "expires_at": None,
            "error": "No token found",
        }
        mock_settings.ENABLE_INSTAGRAM_API = False
        mock_settings.INSTAGRAM_ACCOUNT_ID = None
        mock_settings.FACEBOOK_APP_ID = None
        mock_settings.CLOUDINARY_CLOUD_NAME = None

        runner = CliRunner()
        result = runner.invoke(instagram_status)

        assert result.exit_code == 0
        assert "Not Authenticated" in result.output


@pytest.mark.unit
class TestAddInstagramAccountCommand:
    """Tests for the add-instagram-account CLI command."""

    @patch("cli.commands.instagram.settings")
    @patch("src.utils.encryption.TokenEncryption")
    @patch("src.services.core.instagram_account_service.InstagramAccountService")
    def test_add_account_success(
        self, mock_service_class, mock_encryption_class, mock_settings
    ):
        """Test successfully adding a new Instagram account."""
        mock_service = mock_service_class.return_value
        mock_account = Mock()
        mock_account.id = "acc-uuid-123"
        mock_account.display_name = "Main Brand"
        mock_account.instagram_account_id = "17841234567890"
        mock_account.instagram_username = "brand_main"
        mock_service.add_account.return_value = mock_account

        mock_encryption = mock_encryption_class.return_value
        mock_encryption.encrypt.return_value = "encrypted_token_value"

        mock_settings.ADMIN_TELEGRAM_CHAT_ID = -100123

        runner = CliRunner()
        result = runner.invoke(
            add_instagram_account,
            [
                "--display-name",
                "Main Brand",
                "--account-id",
                "17841234567890",
                "--username",
                "brand_main",
                "--access-token",
                "A" * 60,
                "--set-active",
            ],
        )

        assert result.exit_code == 0
        assert "successfully" in result.output.lower()
        mock_service.add_account.assert_called_once()

    @patch("src.utils.encryption.TokenEncryption")
    @patch("src.services.core.instagram_account_service.InstagramAccountService")
    def test_add_account_invalid_token(self, mock_service_class, mock_encryption_class):
        """Test adding account with invalid token shows error."""
        runner = CliRunner()
        result = runner.invoke(
            add_instagram_account,
            [
                "--display-name",
                "Test",
                "--account-id",
                "123",
                "--username",
                "test",
                "--access-token",
                "short",
            ],
        )

        assert "Invalid access token" in result.output

    @patch("cli.commands.instagram.settings")
    @patch("src.utils.encryption.TokenEncryption")
    @patch("src.services.core.instagram_account_service.InstagramAccountService")
    def test_add_account_service_error(
        self, mock_service_class, mock_encryption_class, mock_settings
    ):
        """Test adding account when service raises ValueError."""
        mock_service = mock_service_class.return_value
        mock_service.add_account.side_effect = ValueError(
            "Account with this Instagram ID already exists"
        )

        mock_encryption = mock_encryption_class.return_value
        mock_encryption.encrypt.return_value = "encrypted"

        runner = CliRunner()
        result = runner.invoke(
            add_instagram_account,
            [
                "--display-name",
                "Duplicate",
                "--account-id",
                "17841234567890",
                "--username",
                "duplicate",
                "--access-token",
                "A" * 60,
            ],
        )

        assert "already exists" in result.output


@pytest.mark.unit
class TestListInstagramAccountsCommand:
    """Tests for the list-instagram-accounts CLI command."""

    @patch("cli.commands.instagram.settings")
    @patch("src.repositories.token_repository.TokenRepository")
    @patch("src.services.core.instagram_account_service.InstagramAccountService")
    def test_list_accounts_shows_table(
        self, mock_service_class, mock_token_repo_class, mock_settings
    ):
        """Test listing accounts displays table with account info."""
        mock_service = mock_service_class.return_value

        mock_account = Mock()
        mock_account.id = "acc-1"
        mock_account.display_name = "Main Brand"
        mock_account.instagram_username = "brand_main"
        mock_account.instagram_account_id = "17841234567890"
        mock_account.is_active = True

        mock_service.list_accounts.return_value = [mock_account]
        mock_service.get_active_account.return_value = mock_account
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = -100123

        mock_token_repo = mock_token_repo_class.return_value
        mock_token = Mock()
        mock_token.is_expired = False
        mock_token.hours_until_expiry.return_value = 720
        mock_token_repo.get_token_for_account.return_value = mock_token

        runner = CliRunner()
        result = runner.invoke(list_instagram_accounts)

        assert result.exit_code == 0
        assert "Main Brand" in result.output

    @patch("cli.commands.instagram.settings")
    @patch("src.repositories.token_repository.TokenRepository")
    @patch("src.services.core.instagram_account_service.InstagramAccountService")
    def test_list_accounts_empty(
        self, mock_service_class, mock_token_repo_class, mock_settings
    ):
        """Test listing accounts when no accounts configured."""
        mock_service = mock_service_class.return_value
        mock_service.list_accounts.return_value = []
        mock_service.get_active_account.return_value = None
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = -100123

        runner = CliRunner()
        result = runner.invoke(list_instagram_accounts)

        assert result.exit_code == 0
        assert "No Instagram accounts configured" in result.output


@pytest.mark.unit
class TestDeactivateReactivateCommands:
    """Tests for deactivate/reactivate Instagram account commands."""

    @patch("src.services.core.instagram_account_service.InstagramAccountService")
    def test_deactivate_account_success(self, mock_service_class):
        """Test deactivating an existing account."""
        mock_service = mock_service_class.return_value
        mock_account = Mock()
        mock_account.display_name = "Old Account"
        mock_account.instagram_username = "old_brand"
        mock_account.is_active = True
        mock_service.get_account_by_username.return_value = mock_account

        runner = CliRunner()
        result = runner.invoke(deactivate_instagram_account, ["old_brand"], input="y\n")

        assert result.exit_code == 0
        assert "deactivated" in result.output
        mock_service.deactivate_account.assert_called_once()

    @patch("src.services.core.instagram_account_service.InstagramAccountService")
    def test_deactivate_account_not_found(self, mock_service_class):
        """Test deactivating a non-existent account."""
        mock_service = mock_service_class.return_value
        mock_service.get_account_by_username.return_value = None
        mock_service.get_account_by_id.return_value = None

        runner = CliRunner()
        result = runner.invoke(deactivate_instagram_account, ["nonexistent"])

        assert "not found" in result.output

    @patch("src.services.core.instagram_account_service.InstagramAccountService")
    def test_reactivate_account_success(self, mock_service_class):
        """Test reactivating a deactivated account."""
        mock_service = mock_service_class.return_value
        mock_account = Mock()
        mock_account.id = "acc-1"
        mock_account.display_name = "Restored Account"
        mock_account.instagram_username = "restored"
        mock_account.is_active = False
        mock_service.get_account_by_username.return_value = mock_account

        runner = CliRunner()
        result = runner.invoke(reactivate_instagram_account, ["restored"])

        assert result.exit_code == 0
        assert "reactivated" in result.output
        mock_service.reactivate_account.assert_called_once()

    @patch("src.services.core.instagram_account_service.InstagramAccountService")
    def test_reactivate_already_active(self, mock_service_class):
        """Test reactivating an account that is already active."""
        mock_service = mock_service_class.return_value
        mock_account = Mock()
        mock_account.display_name = "Active Account"
        mock_account.is_active = True
        mock_service.get_account_by_username.return_value = mock_account

        runner = CliRunner()
        result = runner.invoke(reactivate_instagram_account, ["active_account"])

        assert "already active" in result.output
