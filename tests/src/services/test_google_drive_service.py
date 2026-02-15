"""Tests for GoogleDriveService."""

import json

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.exceptions import GoogleDriveAuthError, GoogleDriveError
from src.services.integrations.google_drive import GoogleDriveService


FAKE_SERVICE_ACCOUNT_JSON = json.dumps(
    {
        "type": "service_account",
        "project_id": "test-project",
        "private_key_id": "key123",
        "private_key": "-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----\n",
        "client_email": "test@test-project.iam.gserviceaccount.com",
        "client_id": "123456789",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
)


@pytest.fixture
def gdrive_service():
    """Create GoogleDriveService with mocked dependencies."""
    with patch.object(GoogleDriveService, "__init__", lambda self: None):
        service = GoogleDriveService()
        service.token_repo = Mock()
        service._encryption = Mock()
        # Mock track_execution context manager
        service.track_execution = MagicMock()
        service.track_execution.return_value.__enter__ = Mock(return_value="run-123")
        service.track_execution.return_value.__exit__ = Mock(return_value=False)
        service.set_result_summary = Mock()
        return service


# ==================== connect Tests ====================


@pytest.mark.unit
class TestGoogleDriveServiceConnect:
    """Tests for connect method."""

    def test_connect_success(self, gdrive_service):
        """Test successful Google Drive connection."""
        with patch(
            "src.services.integrations.google_drive.GoogleDriveProvider"
        ) as mock_provider_class:
            mock_provider = mock_provider_class.return_value
            mock_provider.is_configured.return_value = True

            result = gdrive_service.connect(
                credentials_json=FAKE_SERVICE_ACCOUNT_JSON,
                root_folder_id="folder_abc",
            )

        assert result is True
        gdrive_service._encryption.encrypt.assert_called_once_with(
            FAKE_SERVICE_ACCOUNT_JSON
        )
        gdrive_service.token_repo.create_or_update.assert_called_once()
        call_kwargs = gdrive_service.token_repo.create_or_update.call_args.kwargs
        assert call_kwargs["service_name"] == "google_drive"
        assert call_kwargs["token_type"] == "service_account_json"
        assert call_kwargs["metadata"]["root_folder_id"] == "folder_abc"

    def test_connect_folder_not_accessible(self, gdrive_service):
        """Test connect raises when folder is not accessible."""
        with patch(
            "src.services.integrations.google_drive.GoogleDriveProvider"
        ) as mock_provider_class:
            mock_provider = mock_provider_class.return_value
            mock_provider.is_configured.return_value = False

            with pytest.raises(GoogleDriveError, match="Cannot access"):
                gdrive_service.connect(
                    credentials_json=FAKE_SERVICE_ACCOUNT_JSON,
                    root_folder_id="bad_folder",
                )

        # Should not store credentials
        gdrive_service.token_repo.create_or_update.assert_not_called()

    def test_connect_invalid_json(self, gdrive_service):
        """Test connect raises for invalid JSON credentials."""
        with pytest.raises(ValueError, match="Invalid credentials JSON"):
            gdrive_service.connect(
                credentials_json="not json",
                root_folder_id="folder_abc",
            )

    def test_connect_unsupported_credential_type(self, gdrive_service):
        """Test connect raises for non-service-account credentials."""
        oauth_json = json.dumps({"type": "authorized_user", "client_id": "xyz"})

        with pytest.raises(ValueError, match="Unsupported credential type"):
            gdrive_service.connect(
                credentials_json=oauth_json,
                root_folder_id="folder_abc",
            )


# ==================== get_provider Tests ====================


@pytest.mark.unit
class TestGoogleDriveServiceGetProvider:
    """Tests for get_provider method."""

    def test_get_provider_success(self, gdrive_service):
        """Test creating a provider from stored credentials."""
        mock_token = Mock()
        mock_token.token_value = "encrypted_creds"
        mock_token.token_metadata = {"root_folder_id": "stored_folder_id"}
        gdrive_service.token_repo.get_token.return_value = mock_token
        gdrive_service._encryption.decrypt.return_value = FAKE_SERVICE_ACCOUNT_JSON

        with patch(
            "src.services.integrations.google_drive.GoogleDriveProvider"
        ) as mock_provider_class:
            gdrive_service.get_provider()

        mock_provider_class.assert_called_once_with(
            root_folder_id="stored_folder_id",
            service_account_info=json.loads(FAKE_SERVICE_ACCOUNT_JSON),
        )

    def test_get_provider_no_credentials(self, gdrive_service):
        """Test get_provider raises when no credentials stored."""
        gdrive_service.token_repo.get_token.return_value = None

        with pytest.raises(GoogleDriveAuthError, match="No Google Drive credentials"):
            gdrive_service.get_provider()

    def test_get_provider_override_folder_id(self, gdrive_service):
        """Test get_provider uses override folder ID when provided."""
        mock_token = Mock()
        mock_token.token_value = "encrypted_creds"
        mock_token.token_metadata = {"root_folder_id": "stored_folder_id"}
        gdrive_service.token_repo.get_token.return_value = mock_token
        gdrive_service._encryption.decrypt.return_value = FAKE_SERVICE_ACCOUNT_JSON

        with patch(
            "src.services.integrations.google_drive.GoogleDriveProvider"
        ) as mock_provider_class:
            gdrive_service.get_provider(root_folder_id="override_folder")

        call_kwargs = mock_provider_class.call_args.kwargs
        assert call_kwargs["root_folder_id"] == "override_folder"


# ==================== disconnect Tests ====================


@pytest.mark.unit
class TestGoogleDriveServiceDisconnect:
    """Tests for disconnect method."""

    def test_disconnect_success(self, gdrive_service):
        """Test successful credential removal."""
        gdrive_service.token_repo.delete_token.return_value = True

        result = gdrive_service.disconnect()

        assert result is True
        gdrive_service.token_repo.delete_token.assert_called_once_with(
            "google_drive", "service_account_json"
        )

    def test_disconnect_no_credentials(self, gdrive_service):
        """Test disconnect returns False when nothing to remove."""
        gdrive_service.token_repo.delete_token.return_value = False

        result = gdrive_service.disconnect()

        assert result is False


# ==================== get_connection_status Tests ====================


@pytest.mark.unit
class TestGoogleDriveServiceConnectionStatus:
    """Tests for get_connection_status method."""

    def test_status_connected(self, gdrive_service):
        """Test status when credentials are stored."""
        mock_token = Mock()
        mock_token.token_metadata = {
            "credential_type": "service_account",
            "service_account_email": "test@project.iam.gserviceaccount.com",
            "root_folder_id": "folder_abc",
        }
        gdrive_service.token_repo.get_token.return_value = mock_token

        status = gdrive_service.get_connection_status()

        assert status["connected"] is True
        assert status["credential_type"] == "service_account"
        assert "test@project" in status["service_account_email"]
        assert status["root_folder_id"] == "folder_abc"

    def test_status_not_connected(self, gdrive_service):
        """Test status when no credentials stored."""
        gdrive_service.token_repo.get_token.return_value = None

        status = gdrive_service.get_connection_status()

        assert status["connected"] is False
        assert "error" in status


# ==================== validate_access Tests ====================


@pytest.mark.unit
class TestGoogleDriveServiceValidateAccess:
    """Tests for validate_access method."""

    def test_validate_access_success(self, gdrive_service):
        """Test validate_access when folder is accessible."""
        mock_provider = Mock()
        mock_provider.is_configured.return_value = True
        mock_provider.root_folder_id = "folder_abc"
        mock_provider.get_folders.return_value = ["memes", "merch"]
        mock_provider.list_files.return_value = [Mock(), Mock(), Mock()]

        with patch.object(gdrive_service, "get_provider", return_value=mock_provider):
            result = gdrive_service.validate_access()

        assert result["valid"] is True
        assert result["file_count"] == 3
        assert result["categories"] == ["memes", "merch"]

    def test_validate_access_failure(self, gdrive_service):
        """Test validate_access when credentials are invalid."""
        with patch.object(
            gdrive_service,
            "get_provider",
            side_effect=GoogleDriveAuthError("No credentials"),
        ):
            result = gdrive_service.validate_access()

        assert result["valid"] is False
        assert "No credentials" in result["error"]


# ==================== get_provider_for_chat Tests ====================


@pytest.mark.unit
class TestGoogleDriveServiceProviderForChat:
    """Tests for get_provider_for_chat method."""

    def test_get_provider_for_chat_success(self, gdrive_service):
        """Creates provider from user OAuth credentials."""
        mock_credentials = Mock()
        mock_oauth_service = Mock()
        mock_oauth_service.get_user_credentials.return_value = mock_credentials
        mock_oauth_service.close = Mock()

        with (
            patch(
                "src.services.integrations.google_drive_oauth.GoogleDriveOAuthService",
                return_value=mock_oauth_service,
            ),
            patch(
                "src.services.integrations.google_drive.GoogleDriveProvider"
            ) as MockProvider,
        ):
            gdrive_service.get_provider_for_chat(-100123, "folder_abc")

        MockProvider.assert_called_once_with(
            root_folder_id="folder_abc",
            oauth_credentials=mock_credentials,
        )
        mock_oauth_service.close.assert_called_once()

    def test_get_provider_for_chat_no_credentials_raises(self, gdrive_service):
        """Raises when no OAuth credentials for this chat."""
        mock_oauth_service = Mock()
        mock_oauth_service.get_user_credentials.return_value = None
        mock_oauth_service.close = Mock()

        with patch(
            "src.services.integrations.google_drive_oauth.GoogleDriveOAuthService",
            return_value=mock_oauth_service,
        ):
            with pytest.raises(GoogleDriveAuthError, match="No Google Drive OAuth"):
                gdrive_service.get_provider_for_chat(-100123, "folder_abc")

        mock_oauth_service.close.assert_called_once()

    def test_get_provider_for_chat_no_folder_raises(self, gdrive_service):
        """Raises when no root_folder_id provided."""
        mock_credentials = Mock()
        mock_oauth_service = Mock()
        mock_oauth_service.get_user_credentials.return_value = mock_credentials
        mock_oauth_service.close = Mock()

        with patch(
            "src.services.integrations.google_drive_oauth.GoogleDriveOAuthService",
            return_value=mock_oauth_service,
        ):
            with pytest.raises(GoogleDriveAuthError, match="root_folder_id"):
                gdrive_service.get_provider_for_chat(-100123)
