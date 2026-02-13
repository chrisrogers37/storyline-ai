# Phase 07: CLI Command Tests + Cleanup

**Status:** 🔧 IN PROGRESS
**Started:** 2026-02-13
**PR Title:** `test: add CLI command tests for backfill/sync/gdrive + minor cleanup`
**Risk Level:** Low
**Estimated Effort:** 2-3 hours
**Files Modified:**
- `tests/cli/test_backfill_commands.py` (new)
- `tests/cli/test_google_drive_commands.py` (new)
- `tests/cli/test_sync_commands.py` (new)
- `src/repositories/__init__.py` (add 2 missing exports)
- `src/repositories/service_run_repository.py` (fix stale comment)

## Dependencies
- None (independent, but naturally last)

## Blocks
- None

## Context

Three CLI command modules added during the Cloud Media Enhancements session (PRs #41-#45) have 0 tests:
- `cli/commands/backfill.py` — `backfill-instagram` and `backfill-status` commands
- `cli/commands/google_drive.py` — `connect-google-drive`, `google-drive-status`, `disconnect-google-drive` commands
- `cli/commands/sync.py` — `sync-media` and `sync-status` commands

Additionally, two minor cleanup items from the tech debt scan:
- **L1**: `ChatSettingsRepository` and `InstagramAccountRepository` missing from `src/repositories/__init__.py` exports
- **L2**: Stale comment on `get_recent_runs()` in `service_run_repository.py` says "Unused in production" but it IS used by `InstagramBackfillService.get_backfill_status()` and `MediaSyncService.get_last_sync_info()`

**Note on dependency updates (L3):** The 9 outdated packages were reviewed. None require changes to `requirements.txt` — `cryptography` is already pinned with `>=41.0.0` (accepts the upgrade), and the rest are transitive dependencies or dev tools not pinned in `requirements.txt`. Running `pip install --upgrade` in the local venv is a developer convenience step, not a committed change.

## Implementation Steps

### Part A: CLI Command Tests

#### Step 1: Create `tests/cli/test_backfill_commands.py`

**Important:** `InstagramBackfillService` is imported lazily inside each command function body. Patch at the source module: `src.services.integrations.instagram_backfill.InstagramBackfillService`. The `backfill()` method is `async def`, so use `AsyncMock`.

```python
"""Tests for Instagram backfill CLI commands."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from click.testing import CliRunner

from cli.commands.backfill import backfill_instagram, backfill_status


@pytest.mark.unit
class TestBackfillInstagramCommand:
    """Tests for the backfill-instagram CLI command."""

    @patch("src.services.integrations.instagram_backfill.InstagramBackfillService")
    def test_backfill_dry_run(self, mock_service_class):
        """Test backfill-instagram --dry-run shows what would be downloaded."""
        mock_service = mock_service_class.return_value
        mock_result = Mock()
        mock_result.total_api_items = 10
        mock_result.skipped_duplicate = 3
        mock_result.downloaded = 0
        mock_result.errors = 0
        mock_result.error_details = []

        mock_service.backfill = AsyncMock(return_value=mock_result)

        runner = CliRunner()
        result = runner.invoke(backfill_instagram, ["--dry-run"])

        assert result.exit_code == 0
        assert "Dry run" in result.output or "dry" in result.output.lower()
        mock_service.backfill.assert_called_once()
        call_kwargs = mock_service.backfill.call_args.kwargs
        assert call_kwargs.get("dry_run") is True

    @patch("src.services.integrations.instagram_backfill.InstagramBackfillService")
    def test_backfill_with_limit(self, mock_service_class):
        """Test backfill-instagram --limit limits the number of items."""
        mock_service = mock_service_class.return_value
        mock_result = Mock()
        mock_result.total_api_items = 5
        mock_result.skipped_duplicate = 0
        mock_result.downloaded = 5
        mock_result.errors = 0
        mock_result.error_details = []

        mock_service.backfill = AsyncMock(return_value=mock_result)

        runner = CliRunner()
        result = runner.invoke(backfill_instagram, ["--limit", "5"])

        assert result.exit_code == 0
        call_kwargs = mock_service.backfill.call_args.kwargs
        assert call_kwargs.get("limit") == 5

    @patch("src.services.integrations.instagram_backfill.InstagramBackfillService")
    def test_backfill_with_stories(self, mock_service_class):
        """Test backfill-instagram --include-stories flag."""
        mock_service = mock_service_class.return_value
        mock_result = Mock()
        mock_result.total_api_items = 15
        mock_result.skipped_duplicate = 0
        mock_result.downloaded = 15
        mock_result.errors = 0
        mock_result.error_details = []

        mock_service.backfill = AsyncMock(return_value=mock_result)

        runner = CliRunner()
        result = runner.invoke(backfill_instagram, ["--include-stories"])

        assert result.exit_code == 0
        call_kwargs = mock_service.backfill.call_args.kwargs
        assert call_kwargs.get("include_stories") is True

    @patch("src.services.integrations.instagram_backfill.InstagramBackfillService")
    def test_backfill_with_errors(self, mock_service_class):
        """Test backfill-instagram shows error details when errors occur."""
        mock_service = mock_service_class.return_value
        mock_result = Mock()
        mock_result.total_api_items = 10
        mock_result.skipped_duplicate = 0
        mock_result.downloaded = 8
        mock_result.errors = 2
        mock_result.error_details = [
            "Error downloading item abc123: Connection timeout",
            "Error downloading item def456: 404 Not Found",
        ]

        mock_service.backfill = AsyncMock(return_value=mock_result)

        runner = CliRunner()
        result = runner.invoke(backfill_instagram, [])

        assert result.exit_code == 0
        assert "Error" in result.output
        assert "abc123" in result.output or "Connection timeout" in result.output

    @patch("src.services.integrations.instagram_backfill.InstagramBackfillService")
    def test_backfill_value_error(self, mock_service_class):
        """Test backfill-instagram handles config errors (missing credentials)."""
        mock_service = mock_service_class.return_value
        mock_service.backfill = AsyncMock(
            side_effect=ValueError("Instagram API is not configured")
        )

        runner = CliRunner()
        result = runner.invoke(backfill_instagram, [])

        assert result.exit_code == 0
        assert "not configured" in result.output or "Error" in result.output

    @patch("src.services.integrations.instagram_backfill.InstagramBackfillService")
    def test_backfill_generic_exception(self, mock_service_class):
        """Test backfill-instagram handles unexpected errors."""
        mock_service = mock_service_class.return_value
        mock_service.backfill = AsyncMock(
            side_effect=RuntimeError("Network unreachable")
        )

        runner = CliRunner()
        result = runner.invoke(backfill_instagram, [])

        assert result.exit_code == 0
        assert "failed" in result.output.lower() or "Error" in result.output


@pytest.mark.unit
class TestBackfillStatusCommand:
    """Tests for the backfill-status CLI command."""

    @patch("src.services.integrations.instagram_backfill.InstagramBackfillService")
    def test_backfill_status_with_history(self, mock_service_class):
        """Test backfill-status shows last run details."""
        mock_service = mock_service_class.return_value
        mock_service.get_backfill_status.return_value = {
            "last_run": {
                "started_at": "2026-02-10T12:00:00",
                "completed_at": "2026-02-10T12:02:30",
                "duration_ms": 150000,
                "success": True,
                "result": {
                    "total_api_items": 50,
                    "downloaded": 12,
                    "skipped_duplicate": 38,
                    "errors": 0,
                },
            },
            "total_backfilled": 120,
        }

        runner = CliRunner()
        result = runner.invoke(backfill_status, [])

        assert result.exit_code == 0
        assert "12" in result.output  # downloaded count
        assert "120" in result.output  # total backfilled

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
        assert "No backfill" in result.output or "never" in result.output.lower()

    @patch("src.services.integrations.instagram_backfill.InstagramBackfillService")
    def test_backfill_status_failed_run(self, mock_service_class):
        """Test backfill-status with a failed last run."""
        mock_service = mock_service_class.return_value
        mock_service.get_backfill_status.return_value = {
            "last_run": {
                "started_at": "2026-02-10T12:00:00",
                "completed_at": "2026-02-10T12:00:05",
                "duration_ms": 5000,
                "success": False,
                "result": None,
            },
            "total_backfilled": 50,
        }

        runner = CliRunner()
        result = runner.invoke(backfill_status, [])

        assert result.exit_code == 0
        assert "Failed" in result.output or "failed" in result.output

    @patch("src.services.integrations.instagram_backfill.InstagramBackfillService")
    def test_backfill_status_service_error(self, mock_service_class):
        """Test backfill-status handles service errors gracefully."""
        mock_service = mock_service_class.return_value
        mock_service.get_backfill_status.side_effect = RuntimeError("DB connection lost")

        runner = CliRunner()
        result = runner.invoke(backfill_status, [])

        assert result.exit_code == 0
        assert "Error" in result.output or "failed" in result.output.lower()

    @patch("src.services.integrations.instagram_backfill.InstagramBackfillService")
    def test_backfill_status_verbose(self, mock_service_class):
        """Test backfill-status --verbose shows extra details."""
        mock_service = mock_service_class.return_value
        mock_service.get_backfill_status.return_value = {
            "last_run": {
                "started_at": "2026-02-10T12:00:00",
                "completed_at": "2026-02-10T12:02:30",
                "duration_ms": 150000,
                "success": True,
                "result": {
                    "total_api_items": 50,
                    "downloaded": 12,
                    "skipped_duplicate": 38,
                    "errors": 0,
                },
            },
            "total_backfilled": 120,
        }

        runner = CliRunner()
        result = runner.invoke(backfill_status, ["--verbose"])

        assert result.exit_code == 0
        assert "150000" in result.output or "150" in result.output  # duration
```

#### Step 2: Create `tests/cli/test_google_drive_commands.py`

**Important:** `GoogleDriveService` is imported lazily inside each command function body. Patch at the source module: `src.services.integrations.google_drive.GoogleDriveService`. The `settings` object is also imported lazily.

```python
"""Tests for Google Drive CLI commands."""

import pytest
from unittest.mock import Mock, patch
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
        creds_file.write_text('{"type": "service_account", "client_email": "test@gserviceaccount.com"}')

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
        mock_service.connect.side_effect = ValueError("Invalid credentials JSON: xyz")

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
```

#### Step 3: Create `tests/cli/test_sync_commands.py`

**Important:** `MediaSyncService` is imported lazily inside each command function body. Patch at source: `src.services.core.media_sync.MediaSyncService`. The `settings` object in `sync_status` is also imported lazily — patch at `src.config.settings.settings`.

```python
"""Tests for media sync CLI commands."""

import pytest
from unittest.mock import Mock, patch
from click.testing import CliRunner

from cli.commands.sync import sync_media, sync_status


@pytest.mark.unit
class TestSyncMediaCommand:
    """Tests for the sync-media CLI command."""

    @patch("src.services.core.media_sync.MediaSyncService")
    def test_sync_media_success(self, mock_service_class):
        """Test sync-media completes successfully and shows results table."""
        mock_service = mock_service_class.return_value
        mock_result = Mock()
        mock_result.new = 5
        mock_result.updated = 2
        mock_result.deactivated = 1
        mock_result.reactivated = 0
        mock_result.unchanged = 42
        mock_result.errors = 0
        mock_result.error_details = []

        mock_service.sync.return_value = mock_result

        runner = CliRunner()
        result = runner.invoke(sync_media)

        assert result.exit_code == 0
        assert "Sync complete" in result.output
        assert "5" in result.output
        mock_service.sync.assert_called_once_with(
            source_type=None,
            source_root=None,
            triggered_by="cli",
        )

    @patch("src.services.core.media_sync.MediaSyncService")
    def test_sync_media_with_source_overrides(self, mock_service_class):
        """Test sync-media with --source-type and --source-root options."""
        mock_service = mock_service_class.return_value
        mock_result = Mock()
        mock_result.new = 10
        mock_result.updated = 0
        mock_result.deactivated = 0
        mock_result.reactivated = 0
        mock_result.unchanged = 0
        mock_result.errors = 0
        mock_result.error_details = []

        mock_service.sync.return_value = mock_result

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
        mock_result = Mock()
        mock_result.new = 3
        mock_result.updated = 0
        mock_result.deactivated = 0
        mock_result.reactivated = 0
        mock_result.unchanged = 10
        mock_result.errors = 2
        mock_result.error_details = [
            "Error processing corrupt.jpg: Invalid format",
            "Error processing missing.png: File not found",
        ]

        mock_service.sync.return_value = mock_result

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
        assert "3" in result.output

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
```

### Part B: Cleanup

#### Step 4: Update `src/repositories/__init__.py`

Add the 2 missing repository exports.

**BEFORE** (current, ends at line 25):
```python
from src.repositories.token_repository import TokenRepository

__all__ = [
    "BaseRepository",
    "UserRepository",
    "MediaRepository",
    "QueueRepository",
    "HistoryRepository",
    "LockRepository",
    "ServiceRunRepository",
    "InteractionRepository",
    "CategoryMixRepository",
    "TokenRepository",
]
```

**AFTER**:
```python
from src.repositories.token_repository import TokenRepository
from src.repositories.chat_settings_repository import ChatSettingsRepository
from src.repositories.instagram_account_repository import InstagramAccountRepository

__all__ = [
    "BaseRepository",
    "UserRepository",
    "MediaRepository",
    "QueueRepository",
    "HistoryRepository",
    "LockRepository",
    "ServiceRunRepository",
    "InteractionRepository",
    "CategoryMixRepository",
    "TokenRepository",
    "ChatSettingsRepository",
    "InstagramAccountRepository",
]
```

#### Step 5: Fix stale comment in `service_run_repository.py`

**File:** `src/repositories/service_run_repository.py`, lines 87-88

**BEFORE**:
```python
    # NOTE: Unused in production as of 2026-02-10, but used by test_base_service.py
    # integration tests and planned for Phase 3 monitoring dashboard.
```

**AFTER**:
```python
    # Used by InstagramBackfillService.get_backfill_status() and
    # MediaSyncService.get_last_sync_info(), plus test_base_service.py integration tests.
```

**Note:** The comment on `get_failed_runs()` (lines 100-101) is still accurate — it truly IS unused in production. No change needed there.

### Part C: CHANGELOG.md Update

Add under `## [Unreleased]`:

```markdown
### Added
- **CLI Command Tests** - Unit tests for 3 previously untested CLI modules
  - `tests/cli/test_backfill_commands.py` - 11 tests covering `backfill-instagram` and `backfill-status`
  - `tests/cli/test_google_drive_commands.py` - 8 tests covering `connect-google-drive`, `google-drive-status`, `disconnect-google-drive`
  - `tests/cli/test_sync_commands.py` - 10 tests covering `sync-media` and `sync-status`

### Fixed
- **Repository exports** - Added `ChatSettingsRepository` and `InstagramAccountRepository` to `src/repositories/__init__.py`
- **Stale comment** - Updated `get_recent_runs()` comment in `service_run_repository.py` to reflect actual production usage
```

## Verification Checklist

- [ ] `ruff check tests/cli/test_backfill_commands.py tests/cli/test_google_drive_commands.py tests/cli/test_sync_commands.py src/repositories/__init__.py src/repositories/service_run_repository.py`
- [ ] `ruff format --check` on all changed files
- [ ] `pytest tests/cli/test_backfill_commands.py tests/cli/test_google_drive_commands.py tests/cli/test_sync_commands.py -v` — all new tests pass
- [ ] `pytest` — full test suite passes
- [ ] `python -c "from src.repositories import ChatSettingsRepository, InstagramAccountRepository; print('OK')"` — imports work
- [ ] No `test_db` fixture used in any new test
- [ ] All tests marked `@pytest.mark.unit`
- [ ] `AsyncMock` used for all async service methods (`backfill()`)
- [ ] CHANGELOG.md updated

## What NOT To Do

1. **Do NOT patch at `cli.commands.backfill.InstagramBackfillService`** — the import is lazy (inside function body), so the name doesn't exist on the module at patch time. Always patch at the source module.

2. **Do NOT use `test_db` fixtures** — these are pure unit tests that mock all service dependencies.

3. **Do NOT add `conftest.py` or fixtures to `tests/cli/`** — no shared fixtures needed.

4. **Do NOT modify any service or CLI command code** — the only production code changes are the `__init__.py` export additions and the comment fix.

5. **Do NOT pin transitive dependencies in `requirements.txt`** — packages like `pycparser`, `anyio`, `greenlet` are not directly depended on and should not be pinned.

6. **Do NOT forget to use `AsyncMock`** for the backfill tests — `InstagramBackfillService.backfill()` is `async def`. Using a regular `Mock` will cause `asyncio.run()` to fail.

7. **Do NOT use `@pytest.mark.skip`** — these are properly mocked unit tests and should run without a database.

8. **Do NOT use `input` parameter in `CliRunner.invoke()`** unless the command uses `click.confirm()` — only `disconnect_google_drive` uses a confirmation prompt.

9. **Do NOT update the comment on `get_failed_runs()`** (line 100-101) — that comment is still accurate.
