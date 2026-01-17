"""Tests for TokenRefreshService."""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from contextlib import contextmanager
from datetime import datetime, timedelta

from src.exceptions import TokenExpiredError


@contextmanager
def mock_track_execution(*args, **kwargs):
    """Mock context manager for track_execution."""
    yield "mock_run_id"


@pytest.mark.unit
class TestTokenRefreshService:
    """Test suite for TokenRefreshService."""

    @pytest.fixture
    def token_service(self):
        """Create TokenRefreshService with mocked dependencies."""
        with patch("src.services.integrations.token_refresh.TokenRepository") as mock_repo_class:
            with patch("src.services.integrations.token_refresh.TokenEncryption") as mock_encryption_class:
                with patch("src.services.base_service.ServiceRunRepository"):
                    from src.services.integrations.token_refresh import TokenRefreshService
                    service = TokenRefreshService()
                    service.token_repo = Mock()
                    service._encryption = Mock()
                    service.track_execution = mock_track_execution
                    service.set_result_summary = Mock()
                    yield service

    @pytest.fixture
    def mock_db_token(self):
        """Create a mock database token."""
        token = Mock()
        token.token_value = "encrypted_token_value"
        token.is_expired = False
        token.expires_at = datetime.utcnow() + timedelta(days=30)
        token.last_refreshed_at = datetime.utcnow() - timedelta(days=10)

        def hours_until_expiry():
            if token.expires_at is None:
                return None
            delta = token.expires_at - datetime.utcnow()
            return delta.total_seconds() / 3600

        token.hours_until_expiry = hours_until_expiry
        return token

    # ==================== get_token Tests ====================

    def test_get_token_from_database(self, token_service, mock_db_token):
        """Test get_token returns decrypted token from database."""
        token_service.token_repo.get_token.return_value = mock_db_token
        token_service._encryption.decrypt.return_value = "decrypted_secret_token"

        result = token_service.get_token("instagram")

        assert result == "decrypted_secret_token"
        token_service.token_repo.get_token.assert_called_once_with("instagram", "access_token")
        token_service._encryption.decrypt.assert_called_once_with("encrypted_token_value")

    def test_get_token_expired_raises_error(self, token_service, mock_db_token):
        """Test get_token raises TokenExpiredError for expired token."""
        mock_db_token.is_expired = True
        token_service.token_repo.get_token.return_value = mock_db_token

        with pytest.raises(TokenExpiredError, match="has expired"):
            token_service.get_token("instagram")

    def test_get_token_decrypt_error_returns_none(self, token_service, mock_db_token):
        """Test get_token returns None when decryption fails."""
        token_service.token_repo.get_token.return_value = mock_db_token
        token_service._encryption.decrypt.side_effect = ValueError("Decryption failed")

        result = token_service.get_token("instagram")

        assert result is None

    @patch("src.services.integrations.token_refresh.settings")
    def test_get_token_fallback_to_env(self, mock_settings, token_service):
        """Test get_token falls back to .env when not in database."""
        token_service.token_repo.get_token.return_value = None
        mock_settings.INSTAGRAM_ACCESS_TOKEN = "env_token_value"

        # Mock bootstrap_from_env to not actually do anything
        token_service.bootstrap_from_env = Mock(return_value=True)

        result = token_service.get_token("instagram")

        assert result == "env_token_value"
        token_service.bootstrap_from_env.assert_called_once_with("instagram")

    @patch("src.services.integrations.token_refresh.settings")
    def test_get_token_no_token_anywhere(self, mock_settings, token_service):
        """Test get_token returns None when no token exists."""
        token_service.token_repo.get_token.return_value = None
        mock_settings.INSTAGRAM_ACCESS_TOKEN = None

        result = token_service.get_token("instagram")

        assert result is None

    def test_get_token_custom_token_type(self, token_service, mock_db_token):
        """Test get_token with custom token type."""
        token_service.token_repo.get_token.return_value = mock_db_token
        token_service._encryption.decrypt.return_value = "refresh_token"

        result = token_service.get_token("instagram", token_type="refresh_token")

        token_service.token_repo.get_token.assert_called_once_with("instagram", "refresh_token")

    # ==================== bootstrap_from_env Tests ====================

    @patch("src.services.integrations.token_refresh.settings")
    def test_bootstrap_from_env_success(self, mock_settings, token_service):
        """Test successful bootstrap from environment."""
        mock_settings.INSTAGRAM_ACCESS_TOKEN = "env_token"
        token_service._encryption.encrypt.return_value = "encrypted_env_token"

        result = token_service.bootstrap_from_env("instagram")

        assert result is True
        token_service._encryption.encrypt.assert_called_once_with("env_token")
        token_service.token_repo.create_or_update.assert_called_once()

        # Verify the call arguments
        call_kwargs = token_service.token_repo.create_or_update.call_args[1]
        assert call_kwargs["service_name"] == "instagram"
        assert call_kwargs["token_type"] == "access_token"
        assert call_kwargs["token_value"] == "encrypted_env_token"
        assert "issued_at" in call_kwargs
        assert "expires_at" in call_kwargs
        assert "metadata" in call_kwargs
        assert call_kwargs["metadata"]["bootstrapped_from"] == "env"

    @patch("src.services.integrations.token_refresh.settings")
    def test_bootstrap_from_env_no_env_token(self, mock_settings, token_service):
        """Test bootstrap returns False when no env token."""
        mock_settings.INSTAGRAM_ACCESS_TOKEN = None

        result = token_service.bootstrap_from_env("instagram")

        assert result is False
        token_service.token_repo.create_or_update.assert_not_called()

    @patch("src.services.integrations.token_refresh.settings")
    def test_bootstrap_from_env_expiry_calculation(self, mock_settings, token_service):
        """Test that bootstrap sets 60-day expiry."""
        mock_settings.INSTAGRAM_ACCESS_TOKEN = "token"
        token_service._encryption.encrypt.return_value = "encrypted"

        before_call = datetime.utcnow()
        token_service.bootstrap_from_env("instagram")
        after_call = datetime.utcnow()

        call_kwargs = token_service.token_repo.create_or_update.call_args[1]
        expires_at = call_kwargs["expires_at"]
        issued_at = call_kwargs["issued_at"]

        # Verify issued_at is within the call window
        assert before_call <= issued_at <= after_call

        # Verify 60-day expiry
        expected_expiry_min = before_call + timedelta(days=60)
        expected_expiry_max = after_call + timedelta(days=60)
        assert expected_expiry_min <= expires_at <= expected_expiry_max

    # ==================== check_token_health Tests ====================

    def test_check_token_health_valid_token(self, token_service, mock_db_token):
        """Test health check for valid token."""
        mock_db_token.expires_at = datetime.utcnow() + timedelta(days=30)
        token_service.token_repo.get_token.return_value = mock_db_token

        result = token_service.check_token_health("instagram")

        assert result["valid"] is True
        assert result["exists"] is True
        assert result["source"] == "database"
        assert result["needs_refresh"] is False
        assert result["error"] is None

    def test_check_token_health_expired_token(self, token_service, mock_db_token):
        """Test health check for expired token."""
        mock_db_token.is_expired = True
        mock_db_token.expires_at = datetime.utcnow() - timedelta(days=1)
        token_service.token_repo.get_token.return_value = mock_db_token

        result = token_service.check_token_health("instagram")

        assert result["valid"] is False
        assert result["exists"] is True
        assert result["error"] == "Token expired"

    def test_check_token_health_needs_refresh(self, token_service, mock_db_token):
        """Test health check identifies tokens needing refresh."""
        # Token expires in 5 days (within 7-day buffer)
        mock_db_token.expires_at = datetime.utcnow() + timedelta(days=5)
        token_service.token_repo.get_token.return_value = mock_db_token

        result = token_service.check_token_health("instagram")

        assert result["valid"] is True
        assert result["needs_refresh"] is True

    def test_check_token_health_no_refresh_needed(self, token_service, mock_db_token):
        """Test health check when token doesn't need refresh."""
        # Token expires in 30 days (outside 7-day buffer)
        mock_db_token.expires_at = datetime.utcnow() + timedelta(days=30)
        token_service.token_repo.get_token.return_value = mock_db_token

        result = token_service.check_token_health("instagram")

        assert result["valid"] is True
        assert result["needs_refresh"] is False

    @patch("src.services.integrations.token_refresh.settings")
    def test_check_token_health_env_fallback(self, mock_settings, token_service):
        """Test health check when token only in .env."""
        token_service.token_repo.get_token.return_value = None
        mock_settings.INSTAGRAM_ACCESS_TOKEN = "env_token"

        result = token_service.check_token_health("instagram")

        assert result["valid"] is True
        assert result["exists"] is True
        assert result["source"] == "env"
        assert result["needs_bootstrap"] is True

    @patch("src.services.integrations.token_refresh.settings")
    def test_check_token_health_no_token(self, mock_settings, token_service):
        """Test health check when no token exists."""
        token_service.token_repo.get_token.return_value = None
        mock_settings.INSTAGRAM_ACCESS_TOKEN = None

        result = token_service.check_token_health("instagram")

        assert result["valid"] is False
        assert result["exists"] is False
        assert "No token found" in result["error"]

    # ==================== refresh_instagram_token Tests ====================

    @pytest.mark.asyncio
    async def test_refresh_instagram_token_success(self, token_service, mock_db_token):
        """Test successful token refresh."""
        token_service.token_repo.get_token.return_value = mock_db_token
        token_service._encryption.decrypt.return_value = "current_token"
        token_service._encryption.encrypt.return_value = "encrypted_new_token"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_refreshed_token",
            "expires_in": 5184000,  # 60 days
        }

        with patch("src.services.integrations.token_refresh.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.get = AsyncMock(return_value=mock_response)

            result = await token_service.refresh_instagram_token()

        assert result is True
        token_service._encryption.encrypt.assert_called_once_with("new_refreshed_token")
        token_service.token_repo.create_or_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_instagram_token_no_existing_token(self, token_service):
        """Test refresh fails when no token exists."""
        token_service.token_repo.get_token.return_value = None

        result = await token_service.refresh_instagram_token()

        assert result is False

    @pytest.mark.asyncio
    async def test_refresh_instagram_token_api_error(self, token_service, mock_db_token):
        """Test refresh handles API errors."""
        token_service.token_repo.get_token.return_value = mock_db_token
        token_service._encryption.decrypt.return_value = "current_token"

        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": {"message": "Invalid token"}
        }

        with patch("src.services.integrations.token_refresh.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.get = AsyncMock(return_value=mock_response)

            result = await token_service.refresh_instagram_token()

        assert result is False
        token_service.token_repo.create_or_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_refresh_instagram_token_network_error(self, token_service, mock_db_token):
        """Test refresh handles network errors."""
        import httpx

        token_service.token_repo.get_token.return_value = mock_db_token
        token_service._encryption.decrypt.return_value = "current_token"

        with patch("src.services.integrations.token_refresh.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.get = AsyncMock(side_effect=httpx.RequestError("Network error"))

            result = await token_service.refresh_instagram_token()

        assert result is False

    @pytest.mark.asyncio
    async def test_refresh_instagram_token_no_token_in_response(self, token_service, mock_db_token):
        """Test refresh handles missing token in response."""
        token_service.token_repo.get_token.return_value = mock_db_token
        token_service._encryption.decrypt.return_value = "current_token"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}  # No access_token

        with patch("src.services.integrations.token_refresh.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.get = AsyncMock(return_value=mock_response)

            result = await token_service.refresh_instagram_token()

        assert result is False

    # ==================== get_tokens_needing_refresh Tests ====================

    def test_get_tokens_needing_refresh(self, token_service):
        """Test getting tokens that need refresh."""
        from src.services.integrations.token_refresh import TokenRefreshService
        mock_tokens = [Mock(), Mock()]
        token_service.token_repo.get_expiring_tokens.return_value = mock_tokens

        result = token_service.get_tokens_needing_refresh()

        assert result == mock_tokens
        token_service.token_repo.get_expiring_tokens.assert_called_once_with(
            hours_until_expiry=TokenRefreshService.REFRESH_BUFFER_HOURS
        )

    # ==================== _get_env_token Tests ====================

    @patch("src.services.integrations.token_refresh.settings")
    def test_get_env_token_instagram(self, mock_settings, token_service):
        """Test getting Instagram token from env."""
        mock_settings.INSTAGRAM_ACCESS_TOKEN = "instagram_env_token"

        result = token_service._get_env_token("instagram", "access_token")

        assert result == "instagram_env_token"

    @patch("src.services.integrations.token_refresh.settings")
    def test_get_env_token_unknown_service(self, mock_settings, token_service):
        """Test getting token for unknown service returns None."""
        result = token_service._get_env_token("unknown_service", "access_token")

        assert result is None

    @patch("src.services.integrations.token_refresh.settings")
    def test_get_env_token_wrong_token_type(self, mock_settings, token_service):
        """Test getting wrong token type returns None."""
        mock_settings.INSTAGRAM_ACCESS_TOKEN = "token"

        result = token_service._get_env_token("instagram", "refresh_token")

        assert result is None
