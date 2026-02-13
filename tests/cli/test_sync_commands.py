"""Tests for media sync CLI commands."""

import pytest
from unittest.mock import Mock, patch
from click.testing import CliRunner

from cli.commands.sync import sync_media, sync_status


@pytest.mark.unit
class TestSyncMediaCommand:
    """Tests for the sync-media CLI command."""

    def _make_result(self, **overrides):
        """Helper to build a mock SyncResult with sensible defaults."""
        defaults = {
            "new": 0,
            "updated": 0,
            "deactivated": 0,
            "reactivated": 0,
            "unchanged": 0,
            "errors": 0,
            "error_details": [],
        }
        defaults.update(overrides)
        return Mock(**defaults)

    @patch("src.services.core.media_sync.MediaSyncService")
    def test_sync_media_success(self, mock_service_class):
        """Test sync-media completes successfully and shows results table."""
        mock_service = mock_service_class.return_value
        mock_service.sync.return_value = self._make_result(
            new=5, updated=2, deactivated=1, unchanged=42
        )

        runner = CliRunner()
        result = runner.invoke(sync_media)

        assert result.exit_code == 0
        assert "Sync complete" in result.output
        assert "5" in result.output  # new files
        mock_service.sync.assert_called_once_with(
            source_type=None,
            source_root=None,
            triggered_by="cli",
        )

    @patch("src.services.core.media_sync.MediaSyncService")
    def test_sync_media_with_source_overrides(self, mock_service_class):
        """Test sync-media with --source-type and --source-root options."""
        mock_service = mock_service_class.return_value
        mock_service.sync.return_value = self._make_result(new=10)

        runner = CliRunner()
        result = runner.invoke(
            sync_media,
            ["--source-type", "google_drive", "--source-root", "folder_xyz"],
        )

        assert result.exit_code == 0
        mock_service.sync.assert_called_once_with(
            source_type="google_drive",
            source_root="folder_xyz",
            triggered_by="cli",
        )

    @patch("src.services.core.media_sync.MediaSyncService")
    def test_sync_media_with_errors_shows_details(self, mock_service_class):
        """Test sync-media displays error details when errors occur."""
        mock_service = mock_service_class.return_value
        mock_service.sync.return_value = self._make_result(
            new=3,
            unchanged=10,
            errors=2,
            error_details=[
                "Error processing corrupt.jpg: Invalid format",
                "Error processing missing.png: File not found",
            ],
        )

        runner = CliRunner()
        result = runner.invoke(sync_media)

        assert result.exit_code == 0
        assert "Error details" in result.output
        assert "corrupt.jpg" in result.output

    @patch("src.services.core.media_sync.MediaSyncService")
    def test_sync_media_value_error(self, mock_service_class):
        """Test sync-media handles ValueError (configuration error)."""
        mock_service = mock_service_class.return_value
        mock_service.sync.side_effect = ValueError(
            "Media source provider 'google_drive' is not configured."
        )

        runner = CliRunner()
        result = runner.invoke(sync_media)

        assert result.exit_code == 0
        assert "Configuration error" in result.output
        assert "not configured" in result.output

    @patch("src.services.core.media_sync.MediaSyncService")
    def test_sync_media_generic_exception(self, mock_service_class):
        """Test sync-media handles unexpected exceptions."""
        mock_service = mock_service_class.return_value
        mock_service.sync.side_effect = RuntimeError("Database connection lost")

        runner = CliRunner()
        result = runner.invoke(sync_media)

        assert result.exit_code == 0
        assert "Sync failed" in result.output
        assert "Database connection lost" in result.output

    def test_sync_media_invalid_source_type(self):
        """Test sync-media rejects invalid --source-type values."""
        runner = CliRunner()
        result = runner.invoke(sync_media, ["--source-type", "dropbox"])

        assert result.exit_code != 0


@pytest.mark.unit
class TestSyncStatusCommand:
    """Tests for the sync-status CLI command."""

    @patch("src.config.settings.settings")
    @patch("src.services.core.media_sync.MediaSyncService")
    def test_sync_status_with_run_history(self, mock_service_class, mock_settings):
        """Test sync-status shows configuration and last run details."""
        mock_settings.MEDIA_SYNC_ENABLED = True
        mock_settings.MEDIA_SOURCE_TYPE = "local"
        mock_settings.MEDIA_SOURCE_ROOT = "/media/stories"
        mock_settings.MEDIA_DIR = "/media/stories"
        mock_settings.MEDIA_SYNC_INTERVAL_SECONDS = 3600

        mock_service = mock_service_class.return_value
        mock_service.get_last_sync_info.return_value = {
            "started_at": "2026-02-10T12:00:00",
            "completed_at": "2026-02-10T12:00:05",
            "duration_ms": 5000,
            "status": "completed",
            "success": True,
            "triggered_by": "system",
            "result": {
                "new": 3,
                "updated": 1,
                "deactivated": 0,
                "reactivated": 0,
                "unchanged": 50,
                "errors": 0,
            },
        }

        runner = CliRunner()
        result = runner.invoke(sync_status)

        assert result.exit_code == 0
        assert "Success" in result.output
        assert "5000ms" in result.output
        assert "3" in result.output  # new files

    @patch("src.config.settings.settings")
    @patch("src.services.core.media_sync.MediaSyncService")
    def test_sync_status_no_runs(self, mock_service_class, mock_settings):
        """Test sync-status when no sync has been performed yet."""
        mock_settings.MEDIA_SYNC_ENABLED = False
        mock_settings.MEDIA_SOURCE_TYPE = "local"
        mock_settings.MEDIA_SOURCE_ROOT = None
        mock_settings.MEDIA_DIR = "/media/stories"
        mock_settings.MEDIA_SYNC_INTERVAL_SECONDS = 3600

        mock_service = mock_service_class.return_value
        mock_service.get_last_sync_info.return_value = None

        runner = CliRunner()
        result = runner.invoke(sync_status)

        assert result.exit_code == 0
        assert "No sync runs recorded" in result.output
        assert "MEDIA_SYNC_ENABLED" in result.output

    @patch("src.config.settings.settings")
    @patch("src.services.core.media_sync.MediaSyncService")
    def test_sync_status_failed_run(self, mock_service_class, mock_settings):
        """Test sync-status with a failed last run."""
        mock_settings.MEDIA_SYNC_ENABLED = True
        mock_settings.MEDIA_SOURCE_TYPE = "local"
        mock_settings.MEDIA_SOURCE_ROOT = "/media/stories"
        mock_settings.MEDIA_DIR = "/media/stories"
        mock_settings.MEDIA_SYNC_INTERVAL_SECONDS = 3600

        mock_service = mock_service_class.return_value
        mock_service.get_last_sync_info.return_value = {
            "started_at": "2026-02-10T12:00:00",
            "completed_at": "2026-02-10T12:00:01",
            "duration_ms": 1000,
            "status": "failed",
            "success": False,
            "triggered_by": "scheduler",
            "result": None,
        }

        runner = CliRunner()
        result = runner.invoke(sync_status)

        assert result.exit_code == 0
        assert "Failed" in result.output
