"""Tests for Google Drive CLI commands."""

import pytest
from unittest.mock import patch
from click.testing import CliRunner

from cli.commands.google_drive import (
    connect_google_drive,
    disconnect_google_drive,
    google_drive_status,
)


@pytest.mark.unit
class TestConnectGoogleDriveCommand:
    """Tests for the connect-google-drive CLI command."""

    @patch("src.services.integrations.google_drive.GoogleDriveService")
    @patch("cli.commands.google_drive.settings")
    def test_connect_success(self, mock_settings, mock_service_class, tmp_path):
        """Test connect-google-drive with valid credentials file."""
        mock_settings.ENCRYPTION_KEY = "test-key-123"

        mock_service = mock_service_class.return_value
        mock_service.connect.return_value = True
        mock_service.validate_access.return_value = {
            "valid": True,
            "file_count": 25,
            "categories": ["memes", "merch"],
        }

        creds_file = tmp_path / "service_account.json"
        creds_file.write_text('{"type": "service_account"}')

        runner = CliRunner()
        result = runner.invoke(
            connect_google_drive,
            ["--credentials-file", str(creds_file), "--folder-id", "folder123"],
        )

        assert result.exit_code == 0
        assert "connected" in result.output.lower()
        assert "25" in result.output
        mock_service.connect.assert_called_once()

    @patch("cli.commands.google_drive.settings")
    def test_connect_no_encryption_key(self, mock_settings, tmp_path):
        """Test connect-google-drive fails when ENCRYPTION_KEY is not set."""
        mock_settings.ENCRYPTION_KEY = None

        creds_file = tmp_path / "service_account.json"
        creds_file.write_text('{"type": "service_account"}')

        runner = CliRunner()
        result = runner.invoke(
            connect_google_drive,
            ["--credentials-file", str(creds_file), "--folder-id", "folder123"],
        )

        assert result.exit_code == 0
        assert "ENCRYPTION_KEY" in result.output

    @patch("src.services.integrations.google_drive.GoogleDriveService")
    @patch("cli.commands.google_drive.settings")
    def test_connect_service_raises_value_error(
        self, mock_settings, mock_service_class, tmp_path
    ):
        """Test connect-google-drive handles ValueError from service."""
        mock_settings.ENCRYPTION_KEY = "test-key-123"

        mock_service = mock_service_class.return_value
        mock_service.connect.side_effect = ValueError("Invalid credentials JSON")

        creds_file = tmp_path / "service_account.json"
        creds_file.write_text("not valid json")

        runner = CliRunner()
        result = runner.invoke(
            connect_google_drive,
            ["--credentials-file", str(creds_file), "--folder-id", "folder123"],
        )

        assert result.exit_code == 0
        assert "Error" in result.output


@pytest.mark.unit
class TestGoogleDriveStatusCommand:
    """Tests for the google-drive-status CLI command."""

    @patch("src.services.integrations.google_drive.GoogleDriveService")
    def test_status_connected(self, mock_service_class):
        """Test google-drive-status when connected."""
        mock_service = mock_service_class.return_value
        mock_service.get_connection_status.return_value = {
            "connected": True,
            "credential_type": "service_account",
            "service_account_email": "bot@project.iam.gserviceaccount.com",
            "root_folder_id": "folder_abc123",
        }
        mock_service.validate_access.return_value = {
            "valid": True,
            "file_count": 42,
            "categories": ["memes", "merch", "promos"],
        }

        runner = CliRunner()
        result = runner.invoke(google_drive_status)

        assert result.exit_code == 0
        assert "Connected" in result.output
        assert "bot@project.iam.gserviceaccount.com" in result.output
        assert "42" in result.output

    @patch("src.services.integrations.google_drive.GoogleDriveService")
    def test_status_not_connected(self, mock_service_class):
        """Test google-drive-status when not connected."""
        mock_service = mock_service_class.return_value
        mock_service.get_connection_status.return_value = {
            "connected": False,
            "error": "No credentials configured",
        }

        runner = CliRunner()
        result = runner.invoke(google_drive_status)

        assert result.exit_code == 0
        assert "Not Connected" in result.output
        assert "connect-google-drive" in result.output


@pytest.mark.unit
class TestDisconnectGoogleDriveCommand:
    """Tests for the disconnect-google-drive CLI command."""

    @patch("src.services.integrations.google_drive.GoogleDriveService")
    def test_disconnect_success(self, mock_service_class):
        """Test disconnect-google-drive with user confirmation."""
        mock_service = mock_service_class.return_value
        mock_service.get_connection_status.return_value = {
            "connected": True,
            "service_account_email": "bot@project.iam.gserviceaccount.com",
        }
        mock_service.disconnect.return_value = True

        runner = CliRunner()
        result = runner.invoke(disconnect_google_drive, input="y\n")

        assert result.exit_code == 0
        assert "disconnected" in result.output.lower()
        mock_service.disconnect.assert_called_once()

    @patch("src.services.integrations.google_drive.GoogleDriveService")
    def test_disconnect_cancelled_by_user(self, mock_service_class):
        """Test disconnect-google-drive when user declines confirmation."""
        mock_service = mock_service_class.return_value
        mock_service.get_connection_status.return_value = {
            "connected": True,
            "service_account_email": "bot@project.iam.gserviceaccount.com",
        }

        runner = CliRunner()
        result = runner.invoke(disconnect_google_drive, input="n\n")

        assert result.exit_code == 0
        assert "Cancelled" in result.output
        mock_service.disconnect.assert_not_called()

    @patch("src.services.integrations.google_drive.GoogleDriveService")
    def test_disconnect_not_connected(self, mock_service_class):
        """Test disconnect-google-drive when no connection exists."""
        mock_service = mock_service_class.return_value
        mock_service.get_connection_status.return_value = {
            "connected": False,
        }

        runner = CliRunner()
        result = runner.invoke(disconnect_google_drive)

        assert result.exit_code == 0
        assert "No Google Drive connection" in result.output
