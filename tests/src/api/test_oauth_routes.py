"""Unit tests for OAuth API routes (Instagram and Google Drive)."""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from fastapi.testclient import TestClient

from src.api.app import app


@pytest.fixture
def client():
    return TestClient(app)


class TestOAuthStartEndpoint:
    """Test GET /auth/instagram/start."""

    def test_start_redirects_to_meta(self, client):
        """GET /auth/instagram/start redirects to Meta OAuth."""
        with patch("src.api.routes.oauth.OAuthService") as MockService:
            mock_svc = MockService.return_value
            mock_svc.generate_authorization_url.return_value = (
                "https://www.facebook.com/dialog/oauth?client_id=123"
            )
            mock_svc.close = Mock()

            response = client.get(
                "/auth/instagram/start?chat_id=-1001234567890",
                follow_redirects=False,
            )

        assert response.status_code == 307
        assert "facebook.com" in response.headers["location"]

    def test_start_missing_chat_id_returns_422(self, client):
        """GET /auth/instagram/start without chat_id returns validation error."""
        response = client.get("/auth/instagram/start")
        assert response.status_code == 422

    def test_start_invalid_config_returns_400(self, client):
        """GET /auth/instagram/start with bad config returns 400."""
        with patch("src.api.routes.oauth.OAuthService") as MockService:
            mock_svc = MockService.return_value
            mock_svc.generate_authorization_url.side_effect = ValueError(
                "FACEBOOK_APP_ID not configured"
            )
            mock_svc.close = Mock()

            response = client.get("/auth/instagram/start?chat_id=-1001234567890")

        assert response.status_code == 400
        assert "FACEBOOK_APP_ID" in response.json()["detail"]

    def test_start_calls_close_on_success(self, client):
        """Service is closed after successful redirect."""
        with patch("src.api.routes.oauth.OAuthService") as MockService:
            mock_svc = MockService.return_value
            mock_svc.generate_authorization_url.return_value = (
                "https://www.facebook.com/dialog/oauth"
            )
            mock_svc.close = Mock()

            client.get(
                "/auth/instagram/start?chat_id=-100123",
                follow_redirects=False,
            )

        mock_svc.close.assert_called_once()

    def test_start_calls_close_on_error(self, client):
        """Service is closed even when error occurs."""
        with patch("src.api.routes.oauth.OAuthService") as MockService:
            mock_svc = MockService.return_value
            mock_svc.generate_authorization_url.side_effect = ValueError("bad config")
            mock_svc.close = Mock()

            client.get("/auth/instagram/start?chat_id=-100123")

        mock_svc.close.assert_called_once()


class TestOAuthCallbackEndpoint:
    """Test GET /auth/instagram/callback."""

    def test_callback_success_returns_html(self, client):
        """Successful callback returns HTML success page."""
        with patch("src.api.routes.oauth.OAuthService") as MockService:
            mock_svc = MockService.return_value
            mock_svc.validate_state_token.return_value = -1001234567890
            mock_svc.exchange_and_store = AsyncMock(
                return_value={
                    "username": "testuser",
                    "account_id": "17841234567890",
                    "expires_in_days": 60,
                }
            )
            mock_svc.notify_telegram = AsyncMock()
            mock_svc.close = Mock()

            response = client.get(
                "/auth/instagram/callback?code=AUTH_CODE&state=VALID_STATE"
            )

        assert response.status_code == 200
        assert "testuser" in response.text
        assert "Connected" in response.text

    def test_callback_user_denied_returns_cancelled_page(self, client):
        """User denial returns cancellation HTML page."""
        with patch("src.api.routes.oauth.OAuthService") as MockService:
            mock_svc = MockService.return_value
            mock_svc.validate_state_token.return_value = -1001234567890
            mock_svc.notify_telegram = AsyncMock()
            mock_svc.close = Mock()

            response = client.get(
                "/auth/instagram/callback?"
                "error=access_denied&error_reason=user_denied"
                "&error_description=User+denied&state=VALID_STATE"
            )

        assert response.status_code == 200
        assert "Cancelled" in response.text

    def test_callback_denial_notifies_telegram(self, client):
        """User denial sends notification to Telegram."""
        with patch("src.api.routes.oauth.OAuthService") as MockService:
            mock_svc = MockService.return_value
            mock_svc.validate_state_token.return_value = -100123
            mock_svc.notify_telegram = AsyncMock()
            mock_svc.close = Mock()

            client.get("/auth/instagram/callback?error=access_denied&state=VALID_STATE")

        mock_svc.notify_telegram.assert_called_once()
        call_kwargs = mock_svc.notify_telegram.call_args[1]
        assert call_kwargs["success"] is False

    def test_callback_expired_state_returns_expired_page(self, client):
        """Expired state token returns link-expired HTML page."""
        with patch("src.api.routes.oauth.OAuthService") as MockService:
            mock_svc = MockService.return_value
            mock_svc.validate_state_token.side_effect = ValueError("expired")
            mock_svc.close = Mock()

            response = client.get(
                "/auth/instagram/callback?code=AUTH_CODE&state=EXPIRED_STATE"
            )

        assert response.status_code == 200
        assert "Expired" in response.text

    def test_callback_missing_code_returns_400(self, client):
        """Missing authorization code returns 400."""
        with patch("src.api.routes.oauth.OAuthService") as MockService:
            mock_svc = MockService.return_value
            # No error param, no code param — should hit the missing code check
            # But state is still validated first
            mock_svc.close = Mock()

            response = client.get("/auth/instagram/callback?state=VALID_STATE")

        assert response.status_code == 400

    def test_callback_exchange_failure_returns_error_page(self, client):
        """Exchange failure returns generic error HTML page."""
        with patch("src.api.routes.oauth.OAuthService") as MockService:
            mock_svc = MockService.return_value
            mock_svc.validate_state_token.return_value = -100123
            mock_svc.exchange_and_store = AsyncMock(
                side_effect=ValueError("Code exchange failed")
            )
            mock_svc.close = Mock()

            response = client.get(
                "/auth/instagram/callback?code=BAD_CODE&state=VALID_STATE"
            )

        assert response.status_code == 200
        assert "Connection Failed" in response.text

    def test_callback_success_notifies_telegram(self, client):
        """Successful connection sends Telegram notification."""
        with patch("src.api.routes.oauth.OAuthService") as MockService:
            mock_svc = MockService.return_value
            mock_svc.validate_state_token.return_value = -100123
            mock_svc.exchange_and_store = AsyncMock(
                return_value={
                    "username": "myaccount",
                    "account_id": "123",
                    "expires_in_days": 60,
                }
            )
            mock_svc.notify_telegram = AsyncMock()
            mock_svc.close = Mock()

            client.get("/auth/instagram/callback?code=GOOD_CODE&state=VALID_STATE")

        mock_svc.notify_telegram.assert_called_once()
        call_args = mock_svc.notify_telegram.call_args
        assert call_args[1]["success"] is True
        assert "myaccount" in call_args[0][1]

    def test_callback_calls_close_always(self, client):
        """Service is closed regardless of outcome."""
        with patch("src.api.routes.oauth.OAuthService") as MockService:
            mock_svc = MockService.return_value
            mock_svc.validate_state_token.side_effect = ValueError("bad")
            mock_svc.close = Mock()

            client.get("/auth/instagram/callback?code=CODE&state=STATE")

        mock_svc.close.assert_called_once()


# ==================== Google Drive OAuth Routes ====================


class TestGDriveOAuthStartEndpoint:
    """Test GET /auth/google-drive/start."""

    def test_start_redirects_to_google(self, client):
        """GET /auth/google-drive/start redirects to Google consent screen."""
        with patch("src.api.routes.oauth.GoogleDriveOAuthService") as MockService:
            mock_svc = MockService.return_value
            mock_svc.generate_authorization_url.return_value = (
                "https://accounts.google.com/o/oauth2/v2/auth?client_id=123"
            )
            mock_svc.close = Mock()

            response = client.get(
                "/auth/google-drive/start?chat_id=-1001234567890",
                follow_redirects=False,
            )

        assert response.status_code == 307
        assert "accounts.google.com" in response.headers["location"]

    def test_start_missing_chat_id_returns_422(self, client):
        """GET /auth/google-drive/start without chat_id returns validation error."""
        response = client.get("/auth/google-drive/start")
        assert response.status_code == 422

    def test_start_invalid_config_returns_400(self, client):
        """GET /auth/google-drive/start with bad config returns 400."""
        with patch("src.api.routes.oauth.GoogleDriveOAuthService") as MockService:
            mock_svc = MockService.return_value
            mock_svc.generate_authorization_url.side_effect = ValueError(
                "GOOGLE_CLIENT_ID not configured"
            )
            mock_svc.close = Mock()

            response = client.get("/auth/google-drive/start?chat_id=-100123")

        assert response.status_code == 400
        assert "GOOGLE_CLIENT_ID" in response.json()["detail"]

    def test_start_calls_close_on_success(self, client):
        """Service is closed after successful redirect."""
        with patch("src.api.routes.oauth.GoogleDriveOAuthService") as MockService:
            mock_svc = MockService.return_value
            mock_svc.generate_authorization_url.return_value = (
                "https://accounts.google.com/o/oauth2/v2/auth"
            )
            mock_svc.close = Mock()

            client.get(
                "/auth/google-drive/start?chat_id=-100123",
                follow_redirects=False,
            )

        mock_svc.close.assert_called_once()

    def test_start_calls_close_on_error(self, client):
        """Service is closed even when error occurs."""
        with patch("src.api.routes.oauth.GoogleDriveOAuthService") as MockService:
            mock_svc = MockService.return_value
            mock_svc.generate_authorization_url.side_effect = ValueError("bad")
            mock_svc.close = Mock()

            client.get("/auth/google-drive/start?chat_id=-100123")

        mock_svc.close.assert_called_once()


class TestGDriveOAuthCallbackEndpoint:
    """Test GET /auth/google-drive/callback."""

    def test_callback_success_returns_html(self, client):
        """Successful callback returns Google Drive success page."""
        with patch("src.api.routes.oauth.GoogleDriveOAuthService") as MockService:
            mock_svc = MockService.return_value
            mock_svc.validate_state_token.return_value = -100123
            mock_svc.exchange_and_store = AsyncMock(
                return_value={"email": "user@gmail.com", "expires_in_hours": 1}
            )
            mock_svc.notify_telegram = AsyncMock()
            mock_svc.close = Mock()

            response = client.get(
                "/auth/google-drive/callback?code=AUTH_CODE&state=VALID_STATE"
            )

        assert response.status_code == 200
        assert "user@gmail.com" in response.text
        assert "Google Drive Connected" in response.text

    def test_callback_user_denied_returns_cancelled_page(self, client):
        """User denial returns cancellation HTML page."""
        with patch("src.api.routes.oauth.GoogleDriveOAuthService") as MockService:
            mock_svc = MockService.return_value
            mock_svc.validate_state_token.return_value = -100123
            mock_svc.notify_telegram = AsyncMock()
            mock_svc.close = Mock()

            response = client.get(
                "/auth/google-drive/callback?error=access_denied&state=VALID_STATE"
            )

        assert response.status_code == 200
        assert "Cancelled" in response.text

    def test_callback_denial_notifies_telegram(self, client):
        """User denial sends notification to Telegram."""
        with patch("src.api.routes.oauth.GoogleDriveOAuthService") as MockService:
            mock_svc = MockService.return_value
            mock_svc.validate_state_token.return_value = -100123
            mock_svc.notify_telegram = AsyncMock()
            mock_svc.close = Mock()

            client.get(
                "/auth/google-drive/callback?error=access_denied&state=VALID_STATE"
            )

        mock_svc.notify_telegram.assert_called_once()
        call_kwargs = mock_svc.notify_telegram.call_args[1]
        assert call_kwargs["success"] is False

    def test_callback_expired_state_returns_expired_page(self, client):
        """Expired state token returns link-expired HTML page."""
        with patch("src.api.routes.oauth.GoogleDriveOAuthService") as MockService:
            mock_svc = MockService.return_value
            mock_svc.validate_state_token.side_effect = ValueError("expired")
            mock_svc.close = Mock()

            response = client.get(
                "/auth/google-drive/callback?code=AUTH_CODE&state=EXPIRED"
            )

        assert response.status_code == 200
        assert "Expired" in response.text

    def test_callback_missing_code_returns_400(self, client):
        """Missing authorization code returns 400."""
        with patch("src.api.routes.oauth.GoogleDriveOAuthService") as MockService:
            mock_svc = MockService.return_value
            mock_svc.close = Mock()

            response = client.get("/auth/google-drive/callback?state=VALID_STATE")

        assert response.status_code == 400

    def test_callback_exchange_failure_returns_error_page(self, client):
        """Exchange failure returns generic error HTML page."""
        with patch("src.api.routes.oauth.GoogleDriveOAuthService") as MockService:
            mock_svc = MockService.return_value
            mock_svc.validate_state_token.return_value = -100123
            mock_svc.exchange_and_store = AsyncMock(
                side_effect=ValueError("Exchange failed")
            )
            mock_svc.close = Mock()

            response = client.get(
                "/auth/google-drive/callback?code=BAD&state=VALID_STATE"
            )

        assert response.status_code == 200
        assert "Connection Failed" in response.text

    def test_callback_success_notifies_telegram(self, client):
        """Successful connection sends Telegram notification."""
        with patch("src.api.routes.oauth.GoogleDriveOAuthService") as MockService:
            mock_svc = MockService.return_value
            mock_svc.validate_state_token.return_value = -100123
            mock_svc.exchange_and_store = AsyncMock(
                return_value={"email": "user@gmail.com", "expires_in_hours": 1}
            )
            mock_svc.notify_telegram = AsyncMock()
            mock_svc.close = Mock()

            client.get("/auth/google-drive/callback?code=GOOD&state=VALID_STATE")

        mock_svc.notify_telegram.assert_called_once()
        call_args = mock_svc.notify_telegram.call_args
        assert call_args[1]["success"] is True
        assert "user@gmail.com" in call_args[0][1]

    def test_callback_calls_close_always(self, client):
        """Service is closed regardless of outcome."""
        with patch("src.api.routes.oauth.GoogleDriveOAuthService") as MockService:
            mock_svc = MockService.return_value
            mock_svc.validate_state_token.side_effect = ValueError("bad")
            mock_svc.close = Mock()

            client.get("/auth/google-drive/callback?code=CODE&state=STATE")

        mock_svc.close.assert_called_once()


# =============================================================================
# Security: XSS prevention in HTML pages
# =============================================================================


class TestOAuthHtmlEscaping:
    """Verify user-supplied values are HTML-escaped in success/error pages."""

    def test_instagram_username_is_escaped(self, client):
        """Username with HTML/JS is escaped in success page."""
        xss_username = '"><script>alert(1)</script>'

        with patch("src.api.routes.oauth.OAuthService") as MockService:
            mock_svc = MockService.return_value
            mock_svc.validate_state_token.return_value = -100123
            mock_svc.exchange_and_store = AsyncMock(
                return_value={
                    "username": xss_username,
                    "expires_in_days": 60,
                }
            )
            mock_svc.notify_telegram = AsyncMock()
            mock_svc.close = Mock()

            response = client.get(
                "/auth/instagram/callback?code=AUTH_CODE&state=VALID_STATE"
            )

        assert response.status_code == 200
        assert "<script>" not in response.text
        assert "&lt;script&gt;" in response.text

    def test_gdrive_email_is_escaped(self, client):
        """Email with HTML is escaped in Google Drive success page."""
        xss_email = "<img src=x onerror=alert(1)>"

        with patch("src.api.routes.oauth.GoogleDriveOAuthService") as MockService:
            mock_svc = MockService.return_value
            mock_svc.validate_state_token.return_value = -100123
            mock_svc.exchange_and_store = AsyncMock(
                return_value={
                    "email": xss_email,
                    "expires_in_hours": 1,
                }
            )
            mock_svc.notify_telegram = AsyncMock()
            mock_svc.close = Mock()

            response = client.get(
                "/auth/google-drive/callback?code=AUTH_CODE&state=VALID_STATE"
            )

        assert response.status_code == 200
        assert "<img src=" not in response.text
        assert "&lt;img" in response.text
