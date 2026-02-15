"""Tests for GoogleDriveOAuthService."""

import json
import uuid
from contextlib import contextmanager

import pytest
from unittest.mock import AsyncMock, Mock, patch

from src.services.integrations.google_drive_oauth import GoogleDriveOAuthService


@contextmanager
def mock_track_execution(*args, **kwargs):
    yield str(uuid.uuid4())


# ==================== State Token Tests ====================


@pytest.mark.unit
class TestGDriveStateTokenGeneration:
    """Tests for Google Drive state token generation."""

    @pytest.fixture(autouse=True)
    def setup_service(self):
        with patch.object(GoogleDriveOAuthService, "__init__", lambda self: None):
            self.service = GoogleDriveOAuthService()
            self.service.service_run_repo = Mock()
            self.service.service_name = "GoogleDriveOAuthService"
            self.service._encryption = None

    @patch("src.services.integrations.google_drive_oauth.TokenEncryption")
    def test_state_token_contains_chat_id(self, MockEncryption):
        """State token payload includes chat_id."""
        mock_encryption = MockEncryption.return_value
        mock_encryption.encrypt.return_value = "encrypted_state"
        self.service._encryption = mock_encryption

        result = self.service._create_state_token(-1001234567890)

        assert result == "encrypted_state"
        call_args = mock_encryption.encrypt.call_args[0][0]
        payload = json.loads(call_args)
        assert payload["chat_id"] == -1001234567890
        assert payload["provider"] == "google_drive"

    @patch("src.services.integrations.google_drive_oauth.TokenEncryption")
    def test_state_token_includes_nonce(self, MockEncryption):
        """State token payload includes a random nonce."""
        mock_encryption = MockEncryption.return_value
        mock_encryption.encrypt.return_value = "encrypted"
        self.service._encryption = mock_encryption

        self.service._create_state_token(-100123)

        call_args = mock_encryption.encrypt.call_args[0][0]
        payload = json.loads(call_args)
        assert "nonce" in payload
        assert len(payload["nonce"]) == 32  # 16 bytes hex

    def test_validate_state_token_extracts_chat_id(self):
        """Valid state token returns chat_id."""
        mock_cipher = Mock()
        mock_cipher.decrypt.return_value = json.dumps(
            {"chat_id": -100123, "provider": "google_drive", "nonce": "abc123"}
        ).encode()
        self.service._encryption = Mock()
        self.service._encryption._cipher = mock_cipher

        result = self.service.validate_state_token("encrypted_state")

        assert result == -100123
        mock_cipher.decrypt.assert_called_once_with(b"encrypted_state", ttl=600)

    def test_validate_state_token_expired_raises(self):
        """Expired state token raises ValueError."""
        mock_cipher = Mock()
        mock_cipher.decrypt.side_effect = Exception("Token expired")
        self.service._encryption = Mock()
        self.service._encryption._cipher = mock_cipher

        with pytest.raises(ValueError, match="Invalid or expired state token"):
            self.service.validate_state_token("expired_token")

    def test_validate_state_token_missing_chat_id_raises(self):
        """State token without chat_id raises ValueError."""
        mock_cipher = Mock()
        mock_cipher.decrypt.return_value = json.dumps(
            {"provider": "google_drive", "nonce": "abc"}
        ).encode()
        self.service._encryption = Mock()
        self.service._encryption._cipher = mock_cipher

        with pytest.raises(ValueError, match="missing chat_id"):
            self.service.validate_state_token("bad_payload")


# ==================== Authorization URL Tests ====================


@pytest.mark.unit
class TestGDriveGenerateAuthorizationUrl:
    """Tests for generate_authorization_url."""

    @pytest.fixture(autouse=True)
    def setup_service(self):
        with patch.object(GoogleDriveOAuthService, "__init__", lambda self: None):
            self.service = GoogleDriveOAuthService()
            self.service.service_run_repo = Mock()
            self.service.service_name = "GoogleDriveOAuthService"
            self.service._encryption = Mock()
            self.service._encryption.encrypt.return_value = "state_token_123"
            self.service.token_repo = Mock()
            self.service.settings_repo = Mock()

    @patch("src.services.integrations.google_drive_oauth.settings")
    def test_url_contains_google_params(self, mock_settings):
        """Generated URL includes all required Google OAuth params."""
        mock_settings.GOOGLE_CLIENT_ID = "test-client-id"
        mock_settings.GOOGLE_CLIENT_SECRET = "test-secret"
        mock_settings.OAUTH_REDIRECT_BASE_URL = "https://api.example.com"
        mock_settings.ENCRYPTION_KEY = "test-key"

        url = self.service.generate_authorization_url(-100123)

        assert "accounts.google.com/o/oauth2/v2/auth" in url
        assert "client_id=test-client-id" in url
        assert "state=state_token_123" in url
        assert "access_type=offline" in url
        assert "prompt=consent" in url
        assert "drive.readonly" in url

    @patch("src.services.integrations.google_drive_oauth.settings")
    def test_url_uses_correct_redirect_uri(self, mock_settings):
        """Redirect URI includes /auth/google-drive/callback path."""
        mock_settings.GOOGLE_CLIENT_ID = "id"
        mock_settings.GOOGLE_CLIENT_SECRET = "secret"
        mock_settings.OAUTH_REDIRECT_BASE_URL = "https://api.example.com"
        mock_settings.ENCRYPTION_KEY = "key"

        url = self.service.generate_authorization_url(-100123)

        assert (
            "redirect_uri=https%3A%2F%2Fapi.example.com%2Fauth%2Fgoogle-drive%2Fcallback"
            in url
        )

    @patch("src.services.integrations.google_drive_oauth.settings")
    def test_missing_client_id_raises(self, mock_settings):
        """Missing GOOGLE_CLIENT_ID raises ValueError."""
        mock_settings.GOOGLE_CLIENT_ID = None
        mock_settings.GOOGLE_CLIENT_SECRET = "secret"
        mock_settings.OAUTH_REDIRECT_BASE_URL = "https://api.example.com"
        mock_settings.ENCRYPTION_KEY = "key"

        with pytest.raises(ValueError, match="GOOGLE_CLIENT_ID"):
            self.service.generate_authorization_url(-100123)

    @patch("src.services.integrations.google_drive_oauth.settings")
    def test_missing_multiple_config_raises(self, mock_settings):
        """Missing multiple settings reports all errors."""
        mock_settings.GOOGLE_CLIENT_ID = None
        mock_settings.GOOGLE_CLIENT_SECRET = None
        mock_settings.OAUTH_REDIRECT_BASE_URL = None
        mock_settings.ENCRYPTION_KEY = None

        with pytest.raises(ValueError, match="GOOGLE_CLIENT_ID.*GOOGLE_CLIENT_SECRET"):
            self.service.generate_authorization_url(-100123)


# ==================== Exchange and Store Tests ====================


@pytest.mark.unit
class TestGDriveExchangeAndStore:
    """Tests for exchange_and_store."""

    @pytest.fixture
    def service(self):
        with patch.object(GoogleDriveOAuthService, "__init__", lambda self: None):
            svc = GoogleDriveOAuthService()
            svc.service_run_repo = Mock()
            svc.service_name = "GoogleDriveOAuthService"
            svc._encryption = Mock()
            svc._encryption.encrypt.return_value = "encrypted_token"
            svc.token_repo = Mock()
            svc.settings_repo = Mock()
            svc.track_execution = mock_track_execution
            svc.set_result_summary = Mock()
            return svc

    @pytest.mark.asyncio
    async def test_exchange_stores_tokens(self, service):
        """Successful exchange stores access and refresh tokens."""
        mock_chat_settings = Mock()
        mock_chat_settings.id = uuid.uuid4()
        service.settings_repo.get_or_create.return_value = mock_chat_settings

        with (
            patch.object(
                service,
                "_exchange_code_for_tokens",
                new_callable=AsyncMock,
            ) as mock_exchange,
            patch.object(
                service,
                "_get_user_email",
                new_callable=AsyncMock,
            ) as mock_email,
        ):
            mock_exchange.return_value = {
                "access_token": "access_123",
                "refresh_token": "refresh_456",
                "expires_in": 3600,
            }
            mock_email.return_value = "user@gmail.com"

            result = await service.exchange_and_store("auth_code", -100123)

        assert result["email"] == "user@gmail.com"
        assert result["expires_in_hours"] == 1
        # Should store both access and refresh tokens
        assert service.token_repo.create_or_update_for_chat.call_count == 2

    @pytest.mark.asyncio
    async def test_exchange_without_refresh_token(self, service):
        """Exchange without refresh_token only stores access token."""
        mock_chat_settings = Mock()
        mock_chat_settings.id = uuid.uuid4()
        service.settings_repo.get_or_create.return_value = mock_chat_settings

        with (
            patch.object(
                service,
                "_exchange_code_for_tokens",
                new_callable=AsyncMock,
            ) as mock_exchange,
            patch.object(
                service,
                "_get_user_email",
                new_callable=AsyncMock,
            ) as mock_email,
        ):
            mock_exchange.return_value = {
                "access_token": "access_123",
                "expires_in": 3600,
            }
            mock_email.return_value = "user@gmail.com"

            result = await service.exchange_and_store("auth_code", -100123)

        assert result["email"] == "user@gmail.com"
        # Only access token stored (no refresh_token)
        assert service.token_repo.create_or_update_for_chat.call_count == 1

    @pytest.mark.asyncio
    async def test_exchange_resolves_chat_settings(self, service):
        """Exchange resolves chat_settings_id from telegram_chat_id."""
        mock_chat_settings = Mock()
        mock_chat_settings.id = uuid.uuid4()
        service.settings_repo.get_or_create.return_value = mock_chat_settings

        with (
            patch.object(
                service,
                "_exchange_code_for_tokens",
                new_callable=AsyncMock,
                return_value={"access_token": "tok", "expires_in": 3600},
            ),
            patch.object(
                service,
                "_get_user_email",
                new_callable=AsyncMock,
                return_value="user@gmail.com",
            ),
        ):
            await service.exchange_and_store("code", -100123)

        service.settings_repo.get_or_create.assert_called_once_with(-100123)


# ==================== Get User Credentials Tests ====================


@pytest.mark.unit
class TestGDriveGetUserCredentials:
    """Tests for get_user_credentials."""

    @pytest.fixture(autouse=True)
    def setup_service(self):
        with patch.object(GoogleDriveOAuthService, "__init__", lambda self: None):
            self.service = GoogleDriveOAuthService()
            self.service.service_run_repo = Mock()
            self.service.service_name = "GoogleDriveOAuthService"
            self.service._encryption = Mock()
            self.service.token_repo = Mock()
            self.service.settings_repo = Mock()

    def test_no_chat_settings_returns_none(self):
        """Returns None when chat has no settings."""
        self.service.settings_repo.get_by_chat_id.return_value = None

        result = self.service.get_user_credentials(-100123)

        assert result is None

    def test_no_access_token_returns_none(self):
        """Returns None when no access token stored."""
        mock_settings = Mock()
        mock_settings.id = uuid.uuid4()
        self.service.settings_repo.get_by_chat_id.return_value = mock_settings
        self.service.token_repo.get_token_for_chat.return_value = None

        result = self.service.get_user_credentials(-100123)

        assert result is None

    @patch("src.services.integrations.google_drive_oauth.settings")
    def test_constructs_credentials_from_tokens(self, mock_settings):
        """Constructs google.oauth2 Credentials from stored tokens."""
        mock_settings.GOOGLE_CLIENT_ID = "client-id"
        mock_settings.GOOGLE_CLIENT_SECRET = "client-secret"

        mock_chat = Mock()
        mock_chat.id = uuid.uuid4()
        self.service.settings_repo.get_by_chat_id.return_value = mock_chat

        mock_access = Mock()
        mock_access.token_value = "encrypted_access"
        mock_refresh = Mock()
        mock_refresh.token_value = "encrypted_refresh"

        def get_token_side_effect(service_name, token_type, chat_id):
            if token_type == "oauth_access":
                return mock_access
            return mock_refresh

        self.service.token_repo.get_token_for_chat.side_effect = get_token_side_effect
        self.service._encryption.decrypt.side_effect = lambda v: f"decrypted_{v}"

        with patch("google.oauth2.credentials.Credentials") as MockCreds:
            MockCreds.return_value = Mock()
            result = self.service.get_user_credentials(-100123)

        assert result is not None
        MockCreds.assert_called_once()
        call_kwargs = MockCreds.call_args[1]
        assert call_kwargs["token"] == "decrypted_encrypted_access"
        assert call_kwargs["refresh_token"] == "decrypted_encrypted_refresh"
        assert call_kwargs["client_id"] == "client-id"


# ==================== Notify Telegram Tests ====================


@pytest.mark.unit
class TestGDriveNotifyTelegram:
    """Tests for notify_telegram."""

    @pytest.fixture(autouse=True)
    def setup_service(self):
        with patch.object(GoogleDriveOAuthService, "__init__", lambda self: None):
            self.service = GoogleDriveOAuthService()
            self.service.service_run_repo = Mock()
            self.service.service_name = "GoogleDriveOAuthService"

    @patch("src.services.integrations.google_drive_oauth.settings")
    @patch("src.services.integrations.google_drive_oauth.Bot")
    @pytest.mark.asyncio
    async def test_notify_sends_message(self, MockBot, mock_settings):
        """Notification sends message to correct chat."""
        mock_settings.TELEGRAM_BOT_TOKEN = "bot:token"
        mock_bot = MockBot.return_value
        mock_bot.send_message = AsyncMock()

        await self.service.notify_telegram(-100123, "Connected!", success=True)

        mock_bot.send_message.assert_called_once()
        call_kwargs = mock_bot.send_message.call_args[1]
        assert call_kwargs["chat_id"] == -100123
        assert "Connected!" in call_kwargs["text"]

    @patch("src.services.integrations.google_drive_oauth.settings")
    @patch("src.services.integrations.google_drive_oauth.Bot")
    @pytest.mark.asyncio
    async def test_notify_failure_includes_warning_emoji(self, MockBot, mock_settings):
        """Failure notification uses warning emoji."""
        mock_settings.TELEGRAM_BOT_TOKEN = "bot:token"
        mock_bot = MockBot.return_value
        mock_bot.send_message = AsyncMock()

        await self.service.notify_telegram(-100123, "Failed", success=False)

        call_kwargs = mock_bot.send_message.call_args[1]
        assert "\u26a0\ufe0f" in call_kwargs["text"]

    @patch("src.services.integrations.google_drive_oauth.settings")
    @patch("src.services.integrations.google_drive_oauth.Bot")
    @pytest.mark.asyncio
    async def test_notify_swallows_errors(self, MockBot, mock_settings):
        """Notification errors are logged but not raised."""
        mock_settings.TELEGRAM_BOT_TOKEN = "bot:token"
        mock_bot = MockBot.return_value
        mock_bot.send_message = AsyncMock(side_effect=Exception("Network error"))

        # Should not raise
        await self.service.notify_telegram(-100123, "test", success=True)
