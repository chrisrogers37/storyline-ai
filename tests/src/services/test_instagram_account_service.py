"""Unit tests for InstagramAccountService."""

import pytest
from unittest.mock import Mock, patch
from contextlib import contextmanager
from datetime import datetime
import uuid

from src.services.core.instagram_account_service import InstagramAccountService


@contextmanager
def mock_track_execution(*args, **kwargs):
    """Mock track_execution context manager that yields a fake run_id."""
    yield str(uuid.uuid4())


@pytest.fixture
def mock_account_repo():
    """Create a mock InstagramAccountRepository."""
    return Mock()


@pytest.fixture
def mock_settings_repo():
    """Create a mock ChatSettingsRepository."""
    return Mock()


@pytest.fixture
def mock_token_repo():
    """Create a mock TokenRepository."""
    return Mock()


@pytest.fixture
def service(mock_account_repo, mock_settings_repo, mock_token_repo):
    """Create InstagramAccountService with mocked dependencies."""
    with (
        patch(
            "src.services.core.instagram_account_service.InstagramAccountRepository"
        ) as MockAccountRepo,
        patch(
            "src.services.core.instagram_account_service.ChatSettingsRepository"
        ) as MockSettingsRepo,
        patch(
            "src.services.core.instagram_account_service.TokenRepository"
        ) as MockTokenRepo,
    ):
        MockAccountRepo.return_value = mock_account_repo
        MockSettingsRepo.return_value = mock_settings_repo
        MockTokenRepo.return_value = mock_token_repo

        svc = InstagramAccountService()
        svc.account_repo = mock_account_repo
        svc.settings_repo = mock_settings_repo
        svc.token_repo = mock_token_repo

        # Mock the track_execution and set_result_summary methods
        svc.track_execution = mock_track_execution
        svc.set_result_summary = Mock()

        return svc


@pytest.fixture
def sample_account():
    """Create a sample InstagramAccount mock."""
    account = Mock()
    account.id = uuid.uuid4()
    account.display_name = "Main Brand"
    account.instagram_account_id = "17841234567890"
    account.instagram_username = "brand_main"
    account.is_active = True
    account.created_at = datetime.utcnow()
    account.updated_at = datetime.utcnow()
    return account


@pytest.fixture
def sample_settings():
    """Create sample ChatSettings mock."""
    settings = Mock()
    settings.id = uuid.uuid4()
    settings.telegram_chat_id = -1001234567890
    settings.active_instagram_account_id = None
    return settings


class TestListAccounts:
    """Tests for list_accounts method."""

    def test_list_active_accounts_only(
        self, service, mock_account_repo, sample_account
    ):
        """Should return only active accounts by default."""
        mock_account_repo.get_all_active.return_value = [sample_account]

        result = service.list_accounts()

        assert len(result) == 1
        assert result[0] == sample_account
        mock_account_repo.get_all_active.assert_called_once()

    def test_list_all_accounts_including_inactive(
        self, service, mock_account_repo, sample_account
    ):
        """Should return all accounts when include_inactive=True."""
        inactive_account = Mock()
        inactive_account.is_active = False
        mock_account_repo.get_all.return_value = [sample_account, inactive_account]

        result = service.list_accounts(include_inactive=True)

        assert len(result) == 2
        mock_account_repo.get_all.assert_called_once()


class TestGetActiveAccount:
    """Tests for get_active_account method."""

    def test_returns_active_account_when_set(
        self,
        service,
        mock_account_repo,
        mock_settings_repo,
        sample_account,
        sample_settings,
    ):
        """Should return the active account when one is set."""
        sample_settings.active_instagram_account_id = sample_account.id
        mock_settings_repo.get_or_create.return_value = sample_settings
        mock_account_repo.get_by_id.return_value = sample_account

        result = service.get_active_account(-1001234567890)

        assert result == sample_account
        mock_settings_repo.get_or_create.assert_called_once_with(-1001234567890)
        mock_account_repo.get_by_id.assert_called_once_with(str(sample_account.id))

    def test_returns_none_when_no_account_selected(
        self, service, mock_settings_repo, sample_settings
    ):
        """Should return None when no active account is set."""
        sample_settings.active_instagram_account_id = None
        mock_settings_repo.get_or_create.return_value = sample_settings

        result = service.get_active_account(-1001234567890)

        assert result is None


class TestSwitchAccount:
    """Tests for switch_account method."""

    def test_switch_to_valid_account(
        self,
        service,
        mock_account_repo,
        mock_settings_repo,
        sample_account,
        sample_settings,
    ):
        """Should switch to a valid active account."""
        mock_account_repo.get_by_id.return_value = sample_account
        mock_settings_repo.get_or_create.return_value = sample_settings
        mock_settings_repo.update.return_value = sample_settings

        result = service.switch_account(-1001234567890, str(sample_account.id))

        assert result == sample_account
        mock_settings_repo.update.assert_called_once()

    def test_switch_to_nonexistent_account_raises_error(
        self, service, mock_account_repo
    ):
        """Should raise ValueError when account doesn't exist."""
        mock_account_repo.get_by_id.return_value = None

        with pytest.raises(ValueError, match="not found"):
            service.switch_account(-1001234567890, "nonexistent-id")

    def test_switch_to_inactive_account_raises_error(
        self, service, mock_account_repo, sample_account
    ):
        """Should raise ValueError when trying to switch to inactive account."""
        sample_account.is_active = False
        mock_account_repo.get_by_id.return_value = sample_account

        with pytest.raises(ValueError, match="disabled"):
            service.switch_account(-1001234567890, str(sample_account.id))


class TestAddAccount:
    """Tests for add_account method."""

    def test_add_new_account_successfully(
        self, service, mock_account_repo, mock_token_repo, sample_account
    ):
        """Should create account and store token."""
        mock_account_repo.get_by_instagram_id.return_value = None
        mock_account_repo.get_by_username.return_value = None
        mock_account_repo.create.return_value = sample_account

        result = service.add_account(
            display_name="Main Brand",
            instagram_account_id="17841234567890",
            instagram_username="brand_main",
            access_token="encrypted_token_value",
        )

        assert result == sample_account
        mock_account_repo.create.assert_called_once()
        mock_token_repo.create_or_update.assert_called_once()

    def test_add_duplicate_account_by_id_raises_error(
        self, service, mock_account_repo, sample_account
    ):
        """Should raise ValueError when account ID already exists."""
        mock_account_repo.get_by_instagram_id.return_value = sample_account

        with pytest.raises(ValueError, match="already exists"):
            service.add_account(
                display_name="Duplicate",
                instagram_account_id="17841234567890",
                instagram_username="different_user",
                access_token="token",
            )

    def test_add_duplicate_account_by_username_raises_error(
        self, service, mock_account_repo, sample_account
    ):
        """Should raise ValueError when username already exists."""
        mock_account_repo.get_by_instagram_id.return_value = None
        mock_account_repo.get_by_username.return_value = sample_account

        with pytest.raises(ValueError, match="already exists"):
            service.add_account(
                display_name="Duplicate",
                instagram_account_id="999999999",
                instagram_username="brand_main",
                access_token="token",
            )

    def test_add_account_and_set_as_active(
        self,
        service,
        mock_account_repo,
        mock_token_repo,
        mock_settings_repo,
        sample_account,
        sample_settings,
    ):
        """Should set account as active when set_as_active=True."""
        mock_account_repo.get_by_instagram_id.return_value = None
        mock_account_repo.get_by_username.return_value = None
        mock_account_repo.create.return_value = sample_account
        mock_settings_repo.update.return_value = sample_settings

        service.add_account(
            display_name="Main Brand",
            instagram_account_id="17841234567890",
            instagram_username="brand_main",
            access_token="token",
            set_as_active=True,
            telegram_chat_id=-1001234567890,
        )

        mock_settings_repo.update.assert_called_once()


class TestDeactivateAccount:
    """Tests for deactivate_account method."""

    def test_deactivate_active_account(
        self, service, mock_account_repo, sample_account
    ):
        """Should soft-delete account by marking inactive."""
        deactivated = Mock()
        deactivated.is_active = False
        mock_account_repo.deactivate.return_value = deactivated

        result = service.deactivate_account(str(sample_account.id))

        assert result.is_active is False
        mock_account_repo.deactivate.assert_called_once_with(str(sample_account.id))


class TestReactivateAccount:
    """Tests for reactivate_account method."""

    def test_reactivate_inactive_account(
        self, service, mock_account_repo, sample_account
    ):
        """Should reactivate a previously deactivated account."""
        sample_account.is_active = False
        reactivated = Mock()
        reactivated.is_active = True
        mock_account_repo.activate.return_value = reactivated

        result = service.reactivate_account(str(sample_account.id))

        assert result.is_active is True
        mock_account_repo.activate.assert_called_once_with(str(sample_account.id))


class TestGetAccountsForDisplay:
    """Tests for get_accounts_for_display method."""

    def test_formats_accounts_for_telegram_display(
        self,
        service,
        mock_account_repo,
        mock_settings_repo,
        sample_account,
        sample_settings,
    ):
        """Should return properly formatted account data for Telegram UI."""
        mock_account_repo.get_all_active.return_value = [sample_account]
        sample_settings.active_instagram_account_id = sample_account.id
        mock_settings_repo.get_or_create.return_value = sample_settings
        mock_account_repo.get_by_id.return_value = sample_account

        result = service.get_accounts_for_display(-1001234567890)

        assert "accounts" in result
        assert len(result["accounts"]) == 1
        assert result["accounts"][0]["display_name"] == "Main Brand"
        assert result["accounts"][0]["username"] == "brand_main"
        assert result["active_account_id"] == str(sample_account.id)
        assert result["active_account_name"] == "Main Brand"
        assert result["active_account_username"] == "brand_main"

    def test_handles_no_active_account(
        self,
        service,
        mock_account_repo,
        mock_settings_repo,
        sample_account,
        sample_settings,
    ):
        """Should handle case when no account is selected."""
        mock_account_repo.get_all_active.return_value = [sample_account]
        sample_settings.active_instagram_account_id = None
        mock_settings_repo.get_or_create.return_value = sample_settings

        result = service.get_accounts_for_display(-1001234567890)

        assert result["active_account_id"] is None
        assert result["active_account_name"] == "Not selected"
        assert result["active_account_username"] is None


class TestGetTokenForActiveAccount:
    """Tests for get_token_for_active_account method."""

    def test_returns_token_for_active_account(
        self,
        service,
        mock_account_repo,
        mock_settings_repo,
        mock_token_repo,
        sample_account,
        sample_settings,
    ):
        """Should return access token for the currently active account."""
        sample_settings.active_instagram_account_id = sample_account.id
        mock_settings_repo.get_or_create.return_value = sample_settings
        mock_account_repo.get_by_id.return_value = sample_account

        mock_token = Mock()
        mock_token.token_value = "encrypted_access_token"
        mock_token_repo.get_token_for_account.return_value = mock_token

        result = service.get_token_for_active_account(-1001234567890)

        assert result == "encrypted_access_token"

    def test_returns_none_when_no_active_account(
        self, service, mock_settings_repo, sample_settings
    ):
        """Should return None when no active account is set."""
        sample_settings.active_instagram_account_id = None
        mock_settings_repo.get_or_create.return_value = sample_settings

        result = service.get_token_for_active_account(-1001234567890)

        assert result is None


class TestAutoSelectAccount:
    """Tests for auto_select_account_if_single method."""

    def test_auto_selects_when_single_account_and_none_selected(
        self,
        service,
        mock_account_repo,
        mock_settings_repo,
        sample_account,
        sample_settings,
    ):
        """Should auto-select when exactly one account exists and none is selected."""
        sample_settings.active_instagram_account_id = None
        mock_settings_repo.get_or_create.return_value = sample_settings
        mock_account_repo.get_all_active.return_value = [sample_account]
        mock_settings_repo.update.return_value = sample_settings

        result = service.auto_select_account_if_single(-1001234567890)

        assert result == sample_account
        mock_settings_repo.update.assert_called_once()

    def test_does_not_auto_select_when_account_already_selected(
        self,
        service,
        mock_account_repo,
        mock_settings_repo,
        sample_account,
        sample_settings,
    ):
        """Should not auto-select when an account is already selected."""
        sample_settings.active_instagram_account_id = sample_account.id
        mock_settings_repo.get_or_create.return_value = sample_settings
        mock_account_repo.get_by_id.return_value = sample_account

        result = service.auto_select_account_if_single(-1001234567890)

        assert result is None

    def test_does_not_auto_select_when_multiple_accounts(
        self,
        service,
        mock_account_repo,
        mock_settings_repo,
        sample_account,
        sample_settings,
    ):
        """Should not auto-select when multiple accounts exist."""
        sample_settings.active_instagram_account_id = None
        mock_settings_repo.get_or_create.return_value = sample_settings

        second_account = Mock()
        second_account.id = uuid.uuid4()
        mock_account_repo.get_all_active.return_value = [sample_account, second_account]

        result = service.auto_select_account_if_single(-1001234567890)

        assert result is None


class TestSeparationOfConcerns:
    """Tests validating the architectural separation of concerns."""

    def test_service_uses_correct_repositories(self):
        """Service should use separate repos for accounts, settings, and tokens."""
        with (
            patch(
                "src.services.core.instagram_account_service.InstagramAccountRepository"
            ),
            patch("src.services.core.instagram_account_service.ChatSettingsRepository"),
            patch("src.services.core.instagram_account_service.TokenRepository"),
        ):
            service = InstagramAccountService()

            # Verify all three repos are initialized
            assert hasattr(service, "account_repo")
            assert hasattr(service, "settings_repo")
            assert hasattr(service, "token_repo")

    def test_account_identity_separate_from_credentials(
        self, service, mock_account_repo, mock_token_repo, sample_account
    ):
        """Account creation should create both account (identity) and token (credentials) separately."""
        mock_account_repo.get_by_instagram_id.return_value = None
        mock_account_repo.get_by_username.return_value = None
        mock_account_repo.create.return_value = sample_account

        service.add_account(
            display_name="Test",
            instagram_account_id="123",
            instagram_username="test",
            access_token="token",
        )

        # Account repo handles identity
        mock_account_repo.create.assert_called_once()

        # Token repo handles credentials (with FK link)
        mock_token_repo.create_or_update.assert_called_once()
        call_args = mock_token_repo.create_or_update.call_args
        assert call_args.kwargs["instagram_account_id"] == str(sample_account.id)


class TestMultiAccountScenarios:
    """Tests for multi-account usage scenarios."""

    def test_can_have_multiple_accounts(self, service, mock_account_repo):
        """Should support multiple Instagram accounts."""
        account1 = Mock()
        account1.id = uuid.uuid4()
        account1.display_name = "Brand Main"

        account2 = Mock()
        account2.id = uuid.uuid4()
        account2.display_name = "Brand Promo"

        mock_account_repo.get_all_active.return_value = [account1, account2]

        result = service.list_accounts()

        assert len(result) == 2

    def test_different_chats_can_have_different_active_accounts(
        self, service, mock_account_repo, mock_settings_repo
    ):
        """Different chats could theoretically have different active accounts."""
        # This tests the architecture supports per-chat account selection
        settings1 = Mock()
        settings1.active_instagram_account_id = uuid.uuid4()

        settings2 = Mock()
        settings2.active_instagram_account_id = uuid.uuid4()

        mock_settings_repo.get_or_create.side_effect = [settings1, settings2]

        account1 = Mock()
        account2 = Mock()
        mock_account_repo.get_by_id.side_effect = [account1, account2]

        # Get active account for two different chats
        result1 = service.get_active_account(-100111111)
        result2 = service.get_active_account(-100222222)

        assert result1 == account1
        assert result2 == account2
