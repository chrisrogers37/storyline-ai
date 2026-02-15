"""Unit tests for OAuthService."""

import json
import uuid
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.services.core.oauth_service import OAuthService


@contextmanager
def mock_track_execution(*args, **kwargs):
    yield str(uuid.uuid4())


class TestStateTokenGeneration:
    """Test state token creation and validation."""

    @pytest.fixture(autouse=True)
    def setup_service(self):
        """Set up test fixtures."""
        with patch.object(OAuthService, "__init__", lambda self: None):
            self.service = OAuthService()
            self.service.service_run_repo = Mock()
            self.service.service_name = "OAuthService"
            self.service.account_service = Mock()
            self.service._encryption = None

    @patch("src.services.core.oauth_service.TokenEncryption")
    def test_create_state_token_encrypts_chat_id(self, MockEncryption):
        """State token contains chat_id in encrypted payload."""
        mock_encryption = MockEncryption.return_value
        mock_encryption.encrypt.return_value = "encrypted_state"
        self.service._encryption = mock_encryption

        result = self.service._create_state_token(-1001234567890)

        assert result == "encrypted_state"
        call_args = mock_encryption.encrypt.call_args[0][0]
        payload = json.loads(call_args)
        assert payload["chat_id"] == -1001234567890
        assert "nonce" in payload

    @patch("src.services.core.oauth_service.TokenEncryption")
    def test_validate_state_token_returns_chat_id(self, MockEncryption):
        """Valid state token returns the embedded chat_id."""
        mock_cipher = MagicMock()
        payload = json.dumps({"chat_id": -1001234567890, "nonce": "abc123"})
        mock_cipher.decrypt.return_value = payload.encode()

        mock_encryption = MockEncryption.return_value
        mock_encryption._cipher = mock_cipher
        self.service._encryption = mock_encryption

        result = self.service.validate_state_token("some_state")

        assert result == -1001234567890
        mock_cipher.decrypt.assert_called_once()
        _, kwargs = mock_cipher.decrypt.call_args
        assert kwargs["ttl"] == 600

    @patch("src.services.core.oauth_service.TokenEncryption")
    def test_validate_state_token_expired_raises(self, MockEncryption):
        """Expired state token raises ValueError."""
        from cryptography.fernet import InvalidToken

        mock_cipher = MagicMock()
        mock_cipher.decrypt.side_effect = InvalidToken()

        mock_encryption = MockEncryption.return_value
        mock_encryption._cipher = mock_cipher
        self.service._encryption = mock_encryption

        with pytest.raises(ValueError, match="Invalid or expired"):
            self.service.validate_state_token("expired_state")

    @patch("src.services.core.oauth_service.TokenEncryption")
    def test_validate_state_token_invalid_payload_raises(self, MockEncryption):
        """State token with missing chat_id raises ValueError."""
        mock_cipher = MagicMock()
        mock_cipher.decrypt.return_value = json.dumps({"nonce": "abc"}).encode()

        mock_encryption = MockEncryption.return_value
        mock_encryption._cipher = mock_cipher
        self.service._encryption = mock_encryption

        with pytest.raises(ValueError, match="Invalid payload"):
            self.service.validate_state_token("bad_state")

    @patch("src.services.core.oauth_service.TokenEncryption")
    def test_state_token_nonce_is_unique(self, MockEncryption):
        """Each state token gets a unique nonce."""
        mock_encryption = MockEncryption.return_value
        payloads = []
        mock_encryption.encrypt.side_effect = lambda p: payloads.append(p) or "token"
        self.service._encryption = mock_encryption

        self.service._create_state_token(-100123)
        self.service._create_state_token(-100123)

        nonce1 = json.loads(payloads[0])["nonce"]
        nonce2 = json.loads(payloads[1])["nonce"]
        assert nonce1 != nonce2


class TestGenerateAuthorizationUrl:
    """Test authorization URL generation."""

    @pytest.fixture(autouse=True)
    def setup_service(self):
        """Set up test fixtures."""
        with patch.object(OAuthService, "__init__", lambda self: None):
            self.service = OAuthService()
            self.service.service_run_repo = Mock()
            self.service.service_name = "OAuthService"
            self.service.account_service = Mock()
            self.service._encryption = None

    @patch("src.services.core.oauth_service.settings")
    @patch("src.services.core.oauth_service.TokenEncryption")
    def test_generate_url_includes_required_params(self, MockEncryption, mock_settings):
        """Authorization URL includes all required OAuth params."""
        mock_settings.FACEBOOK_APP_ID = "test_app_id"
        mock_settings.FACEBOOK_APP_SECRET = "test_secret"
        mock_settings.OAUTH_REDIRECT_BASE_URL = "https://api.example.com"
        mock_settings.ENCRYPTION_KEY = "test_key"

        mock_encryption = MockEncryption.return_value
        mock_encryption.encrypt.return_value = "encrypted_state"
        mock_encryption._cipher = MagicMock()
        self.service._encryption = mock_encryption

        url = self.service.generate_authorization_url(-1001234567890)

        assert "client_id=test_app_id" in url
        assert "redirect_uri=" in url
        assert "instagram_basic" in url
        assert "state=encrypted_state" in url
        assert "response_type=code" in url
        assert url.startswith("https://www.facebook.com/dialog/oauth?")

    @patch("src.services.core.oauth_service.settings")
    def test_generate_url_missing_config_raises(self, mock_settings):
        """Missing OAuth config raises ValueError."""
        mock_settings.FACEBOOK_APP_ID = None
        mock_settings.FACEBOOK_APP_SECRET = None
        mock_settings.OAUTH_REDIRECT_BASE_URL = None
        mock_settings.ENCRYPTION_KEY = None

        with pytest.raises(ValueError, match="OAuth not configured"):
            self.service.generate_authorization_url(-1001234567890)

    @patch("src.services.core.oauth_service.settings")
    def test_generate_url_partial_config_lists_missing(self, mock_settings):
        """Partial config error message lists all missing settings."""
        mock_settings.FACEBOOK_APP_ID = "set"
        mock_settings.FACEBOOK_APP_SECRET = None
        mock_settings.OAUTH_REDIRECT_BASE_URL = None
        mock_settings.ENCRYPTION_KEY = "set"

        with pytest.raises(ValueError, match="FACEBOOK_APP_SECRET"):
            self.service.generate_authorization_url(-100123)

    @patch("src.services.core.oauth_service.settings")
    @patch("src.services.core.oauth_service.TokenEncryption")
    def test_redirect_uri_strips_trailing_slash(self, MockEncryption, mock_settings):
        """Redirect URI correctly strips trailing slash from base URL."""
        mock_settings.FACEBOOK_APP_ID = "app_id"
        mock_settings.FACEBOOK_APP_SECRET = "secret"
        mock_settings.OAUTH_REDIRECT_BASE_URL = "https://api.example.com/"
        mock_settings.ENCRYPTION_KEY = "key"

        mock_encryption = MockEncryption.return_value
        mock_encryption.encrypt.return_value = "state"
        self.service._encryption = mock_encryption

        url = self.service.generate_authorization_url(-100123)

        assert "api.example.com%2Fauth%2Finstagram%2Fcallback" in url


class TestExchangeAndStore:
    """Test the full exchange + store flow."""

    @pytest.fixture
    def service(self):
        with patch.object(OAuthService, "__init__", lambda self: None):
            svc = OAuthService()
            svc.service_run_repo = Mock()
            svc.service_name = "OAuthService"
            svc.account_service = Mock()
            svc._encryption = Mock()
            svc.track_execution = mock_track_execution
            svc.set_result_summary = Mock()
            return svc

    @pytest.mark.asyncio
    async def test_exchange_new_account_creates_it(self, service):
        """When Instagram account is new, add_account is called."""
        service.account_service.get_account_by_instagram_id.return_value = None
        service.account_service.add_account.return_value = Mock()

        with (
            patch.object(
                service, "_exchange_code_for_token", new_callable=AsyncMock
            ) as mock_code,
            patch.object(
                service, "_exchange_for_long_lived_token", new_callable=AsyncMock
            ) as mock_long,
            patch.object(
                service, "_get_instagram_account_info", new_callable=AsyncMock
            ) as mock_info,
        ):
            mock_code.return_value = "short_token"
            mock_long.return_value = ("long_token", 5184000)
            mock_info.return_value = {
                "id": "17841234567890",
                "username": "testuser",
            }

            result = await service.exchange_and_store("auth_code", -100123)

        assert result["username"] == "testuser"
        assert result["expires_in_days"] == 60
        service.account_service.add_account.assert_called_once()
        call_kwargs = service.account_service.add_account.call_args[1]
        assert call_kwargs["display_name"] == "@testuser"
        assert call_kwargs["access_token"] == "long_token"
        assert call_kwargs["set_as_active"] is True
        assert call_kwargs["telegram_chat_id"] == -100123

    @pytest.mark.asyncio
    async def test_exchange_existing_account_updates_token(self, service):
        """When Instagram account exists, update_account_token is called."""
        existing = Mock()
        service.account_service.get_account_by_instagram_id.return_value = existing
        service.account_service.update_account_token.return_value = existing

        with (
            patch.object(
                service, "_exchange_code_for_token", new_callable=AsyncMock
            ) as mock_code,
            patch.object(
                service, "_exchange_for_long_lived_token", new_callable=AsyncMock
            ) as mock_long,
            patch.object(
                service, "_get_instagram_account_info", new_callable=AsyncMock
            ) as mock_info,
        ):
            mock_code.return_value = "short_token"
            mock_long.return_value = ("long_token", 5184000)
            mock_info.return_value = {
                "id": "17841234567890",
                "username": "testuser",
            }

            result = await service.exchange_and_store("auth_code", -100123)

        service.account_service.update_account_token.assert_called_once()
        service.account_service.add_account.assert_not_called()
        assert result["username"] == "testuser"

    @pytest.mark.asyncio
    async def test_exchange_no_ig_account_raises(self, service):
        """When no IG business account found, raises ValueError."""
        with (
            patch.object(
                service, "_exchange_code_for_token", new_callable=AsyncMock
            ) as mock_code,
            patch.object(
                service, "_exchange_for_long_lived_token", new_callable=AsyncMock
            ) as mock_long,
            patch.object(
                service, "_get_instagram_account_info", new_callable=AsyncMock
            ) as mock_info,
        ):
            mock_code.return_value = "short_token"
            mock_long.return_value = ("long_token", 5184000)
            mock_info.return_value = None

            with pytest.raises(ValueError, match="Could not find"):
                await service.exchange_and_store("auth_code", -100123)

    @pytest.mark.asyncio
    async def test_exchange_tracks_execution(self, service):
        """exchange_and_store sets result summary for observability."""
        service.account_service.get_account_by_instagram_id.return_value = None
        service.account_service.add_account.return_value = Mock()

        with (
            patch.object(
                service, "_exchange_code_for_token", new_callable=AsyncMock
            ) as mock_code,
            patch.object(
                service, "_exchange_for_long_lived_token", new_callable=AsyncMock
            ) as mock_long,
            patch.object(
                service, "_get_instagram_account_info", new_callable=AsyncMock
            ) as mock_info,
        ):
            mock_code.return_value = "short_token"
            mock_long.return_value = ("long_token", 5184000)
            mock_info.return_value = {
                "id": "12345",
                "username": "testuser",
            }

            await service.exchange_and_store("code", -100123)

        service.set_result_summary.assert_called_once()
        summary = service.set_result_summary.call_args[0][1]
        assert summary["username"] == "testuser"
        assert summary["expires_in_days"] == 60


class TestNotifyTelegram:
    """Test Telegram notification."""

    @pytest.fixture
    def service(self):
        with patch.object(OAuthService, "__init__", lambda self: None):
            svc = OAuthService()
            svc.service_run_repo = Mock()
            svc.service_name = "OAuthService"
            svc.account_service = Mock()
            svc._encryption = Mock()
            return svc

    @pytest.mark.asyncio
    @patch("src.services.core.oauth_service.settings")
    @patch("src.services.core.oauth_service.Bot")
    async def test_notify_sends_success_message(self, MockBot, mock_settings):
        """Success notification sends message with camera emoji."""
        mock_settings.TELEGRAM_BOT_TOKEN = "test_token"
        mock_bot = MockBot.return_value
        mock_bot.send_message = AsyncMock()

        with patch.object(OAuthService, "__init__", lambda self: None):
            service = OAuthService()
            service.service_run_repo = Mock()
            service.service_name = "OAuthService"
            service.account_service = Mock()
            service._encryption = Mock()

            await service.notify_telegram(-100123, "Connected!", success=True)

        mock_bot.send_message.assert_called_once()
        call_kwargs = mock_bot.send_message.call_args[1]
        assert call_kwargs["chat_id"] == -100123
        assert "\U0001f4f8" in call_kwargs["text"]

    @pytest.mark.asyncio
    @patch("src.services.core.oauth_service.settings")
    @patch("src.services.core.oauth_service.Bot")
    async def test_notify_sends_failure_message(self, MockBot, mock_settings):
        """Failure notification sends message with warning emoji."""
        mock_settings.TELEGRAM_BOT_TOKEN = "test_token"
        mock_bot = MockBot.return_value
        mock_bot.send_message = AsyncMock()

        with patch.object(OAuthService, "__init__", lambda self: None):
            service = OAuthService()
            service.service_run_repo = Mock()
            service.service_name = "OAuthService"
            service.account_service = Mock()
            service._encryption = Mock()

            await service.notify_telegram(-100123, "Failed", success=False)

        call_kwargs = mock_bot.send_message.call_args[1]
        assert "\u26a0\ufe0f" in call_kwargs["text"]

    @pytest.mark.asyncio
    @patch("src.services.core.oauth_service.settings")
    @patch("src.services.core.oauth_service.Bot")
    async def test_notify_handles_send_error_gracefully(self, MockBot, mock_settings):
        """Telegram send failure is logged, not raised."""
        mock_settings.TELEGRAM_BOT_TOKEN = "test_token"
        mock_bot = MockBot.return_value
        mock_bot.send_message = AsyncMock(side_effect=Exception("Network error"))

        with patch.object(OAuthService, "__init__", lambda self: None):
            service = OAuthService()
            service.service_run_repo = Mock()
            service.service_name = "OAuthService"
            service.account_service = Mock()
            service._encryption = Mock()

            # Should not raise
            await service.notify_telegram(-100123, "test", success=True)
