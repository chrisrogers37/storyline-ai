"""Tests for Instagram backfill CLI commands."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from click.testing import CliRunner

from cli.commands.backfill import backfill_instagram, backfill_status


@pytest.mark.unit
class TestBackfillInstagramCommand:
    """Tests for the backfill-instagram CLI command."""

    def _make_result(self, **overrides):
        """Helper to build a mock BackfillResult with sensible defaults."""
        defaults = {
            "total_api_items": 10,
            "skipped_duplicate": 0,
            "skipped_unsupported": 0,
            "downloaded": 10,
            "failed": 0,
            "error_details": [],
        }
        defaults.update(overrides)
        return Mock(**defaults)

    @patch("src.services.integrations.instagram_backfill.InstagramBackfillService")
    def test_backfill_dry_run(self, mock_service_class):
        """Test backfill-instagram --dry-run shows preview results."""
        mock_service = mock_service_class.return_value
        mock_service.backfill = AsyncMock(
            return_value=self._make_result(downloaded=0, skipped_duplicate=3)
        )

        runner = CliRunner()
        result = runner.invoke(backfill_instagram, ["--dry-run"])

        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        call_kwargs = mock_service.backfill.call_args.kwargs
        assert call_kwargs["dry_run"] is True

    @patch("src.services.integrations.instagram_backfill.InstagramBackfillService")
    def test_backfill_with_limit(self, mock_service_class):
        """Test backfill-instagram --limit passes limit to service."""
        mock_service = mock_service_class.return_value
        mock_service.backfill = AsyncMock(
            return_value=self._make_result(total_api_items=5, downloaded=5)
        )

        runner = CliRunner()
        result = runner.invoke(backfill_instagram, ["--limit", "5"])

        assert result.exit_code == 0
        call_kwargs = mock_service.backfill.call_args.kwargs
        assert call_kwargs["limit"] == 5

    @patch("src.services.integrations.instagram_backfill.InstagramBackfillService")
    def test_backfill_with_include_stories(self, mock_service_class):
        """Test backfill-instagram --media-type stories shows API note."""
        mock_service = mock_service_class.return_value
        mock_service.backfill = AsyncMock(
            return_value=self._make_result(total_api_items=15, downloaded=15)
        )

        runner = CliRunner()
        result = runner.invoke(backfill_instagram, ["--media-type", "stories"])

        assert result.exit_code == 0
        assert "Stories are only available" in result.output
        call_kwargs = mock_service.backfill.call_args.kwargs
        assert call_kwargs["media_type"] == "stories"

    @patch("src.services.integrations.instagram_backfill.InstagramBackfillService")
    def test_backfill_with_account_id(self, mock_service_class):
        """Test backfill-instagram --account-id passes account to service."""
        mock_service = mock_service_class.return_value
        mock_service.backfill = AsyncMock(return_value=self._make_result())

        runner = CliRunner()
        result = runner.invoke(backfill_instagram, ["--account-id", "abc-123"])

        assert result.exit_code == 0
        call_kwargs = mock_service.backfill.call_args.kwargs
        assert call_kwargs["account_id"] == "abc-123"

    @patch("src.services.integrations.instagram_backfill.InstagramBackfillService")
    def test_backfill_success_shows_results_table(self, mock_service_class):
        """Test backfill-instagram displays results table on success."""
        mock_service = mock_service_class.return_value
        mock_service.backfill = AsyncMock(
            return_value=self._make_result(
                total_api_items=50,
                downloaded=8,
                skipped_duplicate=38,
                skipped_unsupported=2,
                failed=2,
                error_details=["Error downloading item abc: timeout"],
            )
        )

        runner = CliRunner()
        result = runner.invoke(backfill_instagram, [])

        assert result.exit_code == 0
        assert "Complete" in result.output
        assert "8" in result.output  # downloaded
        assert "38" in result.output  # skipped duplicate
        assert "Error details" in result.output
        assert "timeout" in result.output

    @patch("src.services.integrations.instagram_backfill.InstagramBackfillService")
    def test_backfill_exception_shows_error(self, mock_service_class):
        """Test backfill-instagram handles unexpected errors gracefully."""
        mock_service = mock_service_class.return_value
        mock_service.backfill = AsyncMock(
            side_effect=RuntimeError("Instagram API is not configured")
        )

        runner = CliRunner()
        result = runner.invoke(backfill_instagram, [])

        assert result.exit_code == 0
        assert "Backfill failed" in result.output
        assert "not configured" in result.output

    @patch("src.services.integrations.instagram_backfill.InstagramBackfillService")
    def test_backfill_default_options(self, mock_service_class):
        """Test backfill-instagram default options are passed correctly."""
        mock_service = mock_service_class.return_value
        mock_service.backfill = AsyncMock(return_value=self._make_result())

        runner = CliRunner()
        result = runner.invoke(backfill_instagram, [])

        assert result.exit_code == 0
        call_kwargs = mock_service.backfill.call_args.kwargs
        assert call_kwargs["limit"] is None
        assert call_kwargs["media_type"] == "feed"
        assert call_kwargs["since"] is None
        assert call_kwargs["dry_run"] is False
        assert call_kwargs["account_id"] is None
        assert call_kwargs["triggered_by"] == "cli"


@pytest.mark.unit
class TestBackfillStatusCommand:
    """Tests for the backfill-status CLI command."""

    @patch("src.services.integrations.instagram_backfill.InstagramBackfillService")
    def test_backfill_status_with_successful_run(self, mock_service_class):
        """Test backfill-status shows last run details on success."""
        mock_service = mock_service_class.return_value
        mock_service.get_backfill_status.return_value = {
            "last_run": {
                "started_at": "2026-02-10T12:00:00",
                "completed_at": "2026-02-10T12:02:30",
                "success": True,
                "triggered_by": "cli",
                "result": {
                    "total_api_items": 50,
                    "downloaded": 12,
                    "skipped_duplicate": 38,
                    "skipped_unsupported": 0,
                    "failed": 0,
                },
            },
            "total_backfilled": 120,
        }

        runner = CliRunner()
        result = runner.invoke(backfill_status, [])

        assert result.exit_code == 0
        assert "120" in result.output  # total backfilled
        assert "12" in result.output  # downloaded count
        assert "Success" in result.output

    @patch("src.services.integrations.instagram_backfill.InstagramBackfillService")
    def test_backfill_status_no_runs(self, mock_service_class):
        """Test backfill-status when no backfill has been run."""
        mock_service = mock_service_class.return_value
        mock_service.get_backfill_status.return_value = {
            "last_run": None,
            "total_backfilled": 0,
        }

        runner = CliRunner()
        result = runner.invoke(backfill_status, [])

        assert result.exit_code == 0
        assert "No backfill runs recorded" in result.output

    @patch("src.services.integrations.instagram_backfill.InstagramBackfillService")
    def test_backfill_status_failed_run(self, mock_service_class):
        """Test backfill-status with a failed last run."""
        mock_service = mock_service_class.return_value
        mock_service.get_backfill_status.return_value = {
            "last_run": {
                "started_at": "2026-02-10T12:00:00",
                "completed_at": "2026-02-10T12:00:05",
                "success": False,
                "triggered_by": "scheduler",
                "result": None,
            },
            "total_backfilled": 50,
        }

        runner = CliRunner()
        result = runner.invoke(backfill_status, [])

        assert result.exit_code == 0
        assert "Failed" in result.output
        assert "50" in result.output  # total backfilled
