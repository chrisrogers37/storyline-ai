"""Tests for MediaSyncService."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from src.services.core.media_sync import MediaSyncService, SyncResult
from src.services.media_sources.base_provider import MediaFileInfo


# ==================== SyncResult Tests ====================


@pytest.mark.unit
class TestSyncResult:
    """Tests for SyncResult dataclass."""

    def test_sync_result_defaults(self):
        """All counters start at 0, error_details is empty list."""
        result = SyncResult()

        assert result.new == 0
        assert result.updated == 0
        assert result.deactivated == 0
        assert result.reactivated == 0
        assert result.unchanged == 0
        assert result.errors == 0
        assert result.error_details == []

    def test_sync_result_to_dict(self):
        """Converts correctly, caps error_details at 10 entries."""
        result = SyncResult(new=3, updated=1, errors=12)
        result.error_details = [f"Error {i}" for i in range(12)]

        d = result.to_dict()

        assert d["new"] == 3
        assert d["updated"] == 1
        assert d["deactivated"] == 0
        assert d["reactivated"] == 0
        assert d["unchanged"] == 0
        assert d["errors"] == 12
        assert len(d["error_details"]) == 10  # Capped

    def test_sync_result_to_dict_no_errors(self):
        """Omits error_details key when empty."""
        result = SyncResult(new=5)

        d = result.to_dict()

        assert "error_details" not in d

    def test_sync_result_total_processed(self):
        """Sums new + updated + deactivated + reactivated + unchanged."""
        result = SyncResult(
            new=2, updated=3, deactivated=1, reactivated=1, unchanged=10
        )

        assert result.total_processed == 17

    def test_sync_result_total_processed_excludes_errors(self):
        """Errors are not counted in total_processed."""
        result = SyncResult(new=2, errors=5)

        assert result.total_processed == 2


# ==================== Fixtures ====================


@pytest.fixture
def sync_service():
    """Create MediaSyncService with mocked dependencies."""
    with patch.object(MediaSyncService, "__init__", lambda self: None):
        service = MediaSyncService()
        service.media_repo = Mock()
        service.service_run_repo = Mock()
        # Mock track_execution context manager
        service.track_execution = MagicMock()
        service.track_execution.return_value.__enter__ = Mock(return_value="run-123")
        service.track_execution.return_value.__exit__ = Mock(return_value=False)
        service.set_result_summary = Mock()
        return service


def _make_file_info(
    name="photo.jpg",
    identifier="/media/photo.jpg",
    size_bytes=1024,
    mime_type="image/jpeg",
    folder=None,
    file_hash=None,
):
    """Helper to create a MediaFileInfo instance."""
    return MediaFileInfo(
        name=name,
        identifier=identifier,
        size_bytes=size_bytes,
        mime_type=mime_type,
        folder=folder,
        hash=file_hash,
    )


def _make_db_item(
    item_id="item-1",
    file_name="photo.jpg",
    file_hash="abc123",
    source_identifier="/media/photo.jpg",
    is_active=True,
):
    """Helper to create a mock MediaItem."""
    item = Mock()
    item.id = item_id
    item.file_name = file_name
    item.file_hash = file_hash
    item.source_identifier = source_identifier
    item.is_active = is_active
    return item


# ==================== sync() Core Tests ====================


@pytest.mark.unit
class TestMediaSyncServiceSync:
    """Tests for MediaSyncService.sync() method."""

    @patch("src.services.core.media_sync.settings")
    @patch("src.services.core.media_sync.MediaSourceFactory")
    def test_sync_indexes_new_files(self, mock_factory, mock_settings, sync_service):
        """Provider has files not in DB -- should index them as new."""
        mock_settings.MEDIA_SOURCE_TYPE = "local"
        mock_settings.MEDIA_SOURCE_ROOT = "/media"
        mock_settings.MEDIA_DIR = "/media"

        mock_provider = Mock()
        mock_factory.create.return_value = mock_provider
        mock_provider.is_configured.return_value = True
        mock_provider.list_files.return_value = [
            _make_file_info(name="new.jpg", identifier="/media/new.jpg"),
        ]
        mock_provider.calculate_file_hash.return_value = "hash_new"

        sync_service.media_repo.get_active_by_source_type.return_value = []
        sync_service.media_repo.get_inactive_by_source_identifier.return_value = None

        result = sync_service.sync(triggered_by="cli")

        assert result.new == 1
        sync_service.media_repo.create.assert_called_once()
        call_kwargs = sync_service.media_repo.create.call_args[1]
        assert call_kwargs["file_name"] == "new.jpg"
        assert call_kwargs["source_type"] == "local"
        assert call_kwargs["source_identifier"] == "/media/new.jpg"

    @patch("src.services.core.media_sync.settings")
    @patch("src.services.core.media_sync.MediaSourceFactory")
    def test_sync_detects_deleted_files(
        self, mock_factory, mock_settings, sync_service
    ):
        """DB has items absent from provider -- should deactivate them."""
        mock_settings.MEDIA_SOURCE_TYPE = "local"
        mock_settings.MEDIA_SOURCE_ROOT = "/media"
        mock_settings.MEDIA_DIR = "/media"

        mock_provider = Mock()
        mock_factory.create.return_value = mock_provider
        mock_provider.is_configured.return_value = True
        mock_provider.list_files.return_value = []  # Empty provider

        db_item = _make_db_item(source_identifier="/media/old.jpg")
        sync_service.media_repo.get_active_by_source_type.return_value = [db_item]

        result = sync_service.sync()

        assert result.deactivated == 1
        sync_service.media_repo.deactivate.assert_called_once_with(str(db_item.id))

    @patch("src.services.core.media_sync.settings")
    @patch("src.services.core.media_sync.MediaSourceFactory")
    def test_sync_detects_renamed_files(
        self, mock_factory, mock_settings, sync_service
    ):
        """Provider file has same hash but different identifier -- rename detected."""
        mock_settings.MEDIA_SOURCE_TYPE = "local"
        mock_settings.MEDIA_SOURCE_ROOT = "/media"
        mock_settings.MEDIA_DIR = "/media"

        mock_provider = Mock()
        mock_factory.create.return_value = mock_provider
        mock_provider.is_configured.return_value = True
        mock_provider.list_files.return_value = [
            _make_file_info(
                name="renamed.jpg",
                identifier="/media/renamed.jpg",
                file_hash="same_hash",
            ),
        ]

        db_item = _make_db_item(
            file_name="original.jpg",
            file_hash="same_hash",
            source_identifier="/media/original.jpg",
        )
        sync_service.media_repo.get_active_by_source_type.return_value = [db_item]

        result = sync_service.sync()

        assert result.updated == 1
        sync_service.media_repo.update_source_info.assert_called_once()
        call_kwargs = sync_service.media_repo.update_source_info.call_args[1]
        assert call_kwargs["file_name"] == "renamed.jpg"
        assert call_kwargs["source_identifier"] == "/media/renamed.jpg"

    @patch("src.services.core.media_sync.settings")
    @patch("src.services.core.media_sync.MediaSourceFactory")
    def test_sync_reactivates_files(self, mock_factory, mock_settings, sync_service):
        """Provider has file matching an inactive DB record -- should reactivate."""
        mock_settings.MEDIA_SOURCE_TYPE = "local"
        mock_settings.MEDIA_SOURCE_ROOT = "/media"
        mock_settings.MEDIA_DIR = "/media"

        mock_provider = Mock()
        mock_factory.create.return_value = mock_provider
        mock_provider.is_configured.return_value = True
        mock_provider.list_files.return_value = [
            _make_file_info(name="comeback.jpg", identifier="/media/comeback.jpg"),
        ]
        mock_provider.calculate_file_hash.return_value = "new_hash"

        sync_service.media_repo.get_active_by_source_type.return_value = []
        inactive_item = _make_db_item(
            item_id="inactive-1", file_name="comeback.jpg", is_active=False
        )
        sync_service.media_repo.get_inactive_by_source_identifier.return_value = (
            inactive_item
        )

        result = sync_service.sync()

        assert result.reactivated == 1
        sync_service.media_repo.reactivate.assert_called_once_with("inactive-1")

    @patch("src.services.core.media_sync.settings")
    @patch("src.services.core.media_sync.MediaSourceFactory")
    def test_sync_unchanged_files(self, mock_factory, mock_settings, sync_service):
        """Provider file matches DB record exactly -- no mutations."""
        mock_settings.MEDIA_SOURCE_TYPE = "local"
        mock_settings.MEDIA_SOURCE_ROOT = "/media"
        mock_settings.MEDIA_DIR = "/media"

        mock_provider = Mock()
        mock_factory.create.return_value = mock_provider
        mock_provider.is_configured.return_value = True
        mock_provider.list_files.return_value = [
            _make_file_info(name="same.jpg", identifier="/media/same.jpg"),
        ]

        db_item = _make_db_item(
            file_name="same.jpg", source_identifier="/media/same.jpg"
        )
        sync_service.media_repo.get_active_by_source_type.return_value = [db_item]

        result = sync_service.sync()

        assert result.unchanged == 1
        sync_service.media_repo.create.assert_not_called()
        sync_service.media_repo.update_source_info.assert_not_called()
        sync_service.media_repo.deactivate.assert_not_called()
        sync_service.media_repo.reactivate.assert_not_called()

    @patch("src.services.core.media_sync.settings")
    @patch("src.services.core.media_sync.MediaSourceFactory")
    def test_sync_name_changed_same_identifier(
        self, mock_factory, mock_settings, sync_service
    ):
        """Provider file has same identifier but different name -- update name."""
        mock_settings.MEDIA_SOURCE_TYPE = "local"
        mock_settings.MEDIA_SOURCE_ROOT = "/media"
        mock_settings.MEDIA_DIR = "/media"

        mock_provider = Mock()
        mock_factory.create.return_value = mock_provider
        mock_provider.is_configured.return_value = True
        mock_provider.list_files.return_value = [
            _make_file_info(name="new_name.jpg", identifier="/media/file_id"),
        ]

        db_item = _make_db_item(
            file_name="old_name.jpg", source_identifier="/media/file_id"
        )
        sync_service.media_repo.get_active_by_source_type.return_value = [db_item]

        result = sync_service.sync()

        assert result.updated == 1
        sync_service.media_repo.update_source_info.assert_called_once()
        call_kwargs = sync_service.media_repo.update_source_info.call_args[1]
        assert call_kwargs["file_name"] == "new_name.jpg"

    @patch("src.services.core.media_sync.settings")
    @patch("src.services.core.media_sync.MediaSourceFactory")
    def test_sync_returns_sync_result(self, mock_factory, mock_settings, sync_service):
        """Return type is SyncResult and set_result_summary called."""
        mock_settings.MEDIA_SOURCE_TYPE = "local"
        mock_settings.MEDIA_SOURCE_ROOT = "/media"
        mock_settings.MEDIA_DIR = "/media"

        mock_provider = Mock()
        mock_factory.create.return_value = mock_provider
        mock_provider.is_configured.return_value = True
        mock_provider.list_files.return_value = []
        sync_service.media_repo.get_active_by_source_type.return_value = []

        result = sync_service.sync()

        assert isinstance(result, SyncResult)
        sync_service.set_result_summary.assert_called_once()

    @patch("src.services.core.media_sync.settings")
    @patch("src.services.core.media_sync.MediaSourceFactory")
    def test_sync_provider_not_configured_raises(
        self, mock_factory, mock_settings, sync_service
    ):
        """Provider not configured should raise ValueError."""
        mock_settings.MEDIA_SOURCE_TYPE = "local"
        mock_settings.MEDIA_SOURCE_ROOT = "/media"
        mock_settings.MEDIA_DIR = "/media"

        mock_provider = Mock()
        mock_factory.create.return_value = mock_provider
        mock_provider.is_configured.return_value = False

        with pytest.raises(ValueError, match="not configured"):
            sync_service.sync()


# ==================== sync() Edge Cases ====================


@pytest.mark.unit
class TestMediaSyncServiceEdgeCases:
    """Edge case tests for MediaSyncService.sync()."""

    @patch("src.services.core.media_sync.settings")
    @patch("src.services.core.media_sync.MediaSourceFactory")
    def test_sync_empty_provider_deactivates_all(
        self, mock_factory, mock_settings, sync_service
    ):
        """Empty provider listing deactivates all DB items."""
        mock_settings.MEDIA_SOURCE_TYPE = "local"
        mock_settings.MEDIA_SOURCE_ROOT = "/media"
        mock_settings.MEDIA_DIR = "/media"

        mock_provider = Mock()
        mock_factory.create.return_value = mock_provider
        mock_provider.is_configured.return_value = True
        mock_provider.list_files.return_value = []

        items = [
            _make_db_item(item_id="a", source_identifier="/media/a.jpg"),
            _make_db_item(item_id="b", source_identifier="/media/b.jpg"),
        ]
        sync_service.media_repo.get_active_by_source_type.return_value = items

        result = sync_service.sync()

        assert result.deactivated == 2
        assert sync_service.media_repo.deactivate.call_count == 2

    @patch("src.services.core.media_sync.settings")
    @patch("src.services.core.media_sync.MediaSourceFactory")
    def test_sync_empty_db_indexes_all(self, mock_factory, mock_settings, sync_service):
        """Empty DB indexes all provider files as new."""
        mock_settings.MEDIA_SOURCE_TYPE = "local"
        mock_settings.MEDIA_SOURCE_ROOT = "/media"
        mock_settings.MEDIA_DIR = "/media"

        mock_provider = Mock()
        mock_factory.create.return_value = mock_provider
        mock_provider.is_configured.return_value = True
        mock_provider.list_files.return_value = [
            _make_file_info(name="a.jpg", identifier="/media/a.jpg"),
            _make_file_info(name="b.jpg", identifier="/media/b.jpg"),
            _make_file_info(name="c.jpg", identifier="/media/c.jpg"),
        ]
        mock_provider.calculate_file_hash.return_value = "unique_hash"

        sync_service.media_repo.get_active_by_source_type.return_value = []
        sync_service.media_repo.get_inactive_by_source_identifier.return_value = None

        result = sync_service.sync()

        assert result.new == 3
        assert sync_service.media_repo.create.call_count == 3

    @patch("src.services.core.media_sync.settings")
    @patch("src.services.core.media_sync.MediaSourceFactory")
    def test_sync_error_in_single_file_continues(
        self, mock_factory, mock_settings, sync_service
    ):
        """Error processing one file doesn't stop other files."""
        mock_settings.MEDIA_SOURCE_TYPE = "local"
        mock_settings.MEDIA_SOURCE_ROOT = "/media"
        mock_settings.MEDIA_DIR = "/media"

        mock_provider = Mock()
        mock_factory.create.return_value = mock_provider
        mock_provider.is_configured.return_value = True
        mock_provider.list_files.return_value = [
            _make_file_info(name="good1.jpg", identifier="/media/good1.jpg"),
            _make_file_info(name="bad.jpg", identifier="/media/bad.jpg"),
            _make_file_info(name="good2.jpg", identifier="/media/good2.jpg"),
        ]

        # Hash calculation fails for the second file
        def side_effect_hash(identifier):
            if identifier == "/media/bad.jpg":
                raise Exception("Hash calc failed")
            return "hash_" + identifier

        mock_provider.calculate_file_hash.side_effect = side_effect_hash

        sync_service.media_repo.get_active_by_source_type.return_value = []
        sync_service.media_repo.get_inactive_by_source_identifier.return_value = None

        result = sync_service.sync()

        assert result.new == 2
        assert result.errors == 1
        assert len(result.error_details) == 1
        assert "bad.jpg" in result.error_details[0]

    @patch("src.services.core.media_sync.settings")
    @patch("src.services.core.media_sync.MediaSourceFactory")
    def test_sync_uses_provider_hash_when_available(
        self, mock_factory, mock_settings, sync_service
    ):
        """Provider-side hash used when available; calculate_file_hash NOT called."""
        mock_settings.MEDIA_SOURCE_TYPE = "google_drive"
        mock_settings.MEDIA_SOURCE_ROOT = "folder_123"
        mock_settings.MEDIA_DIR = "/media"

        mock_provider = Mock()
        mock_factory.create.return_value = mock_provider
        mock_provider.is_configured.return_value = True
        mock_provider.list_files.return_value = [
            _make_file_info(
                name="cloud.jpg",
                identifier="file_abc",
                file_hash="provider_hash",
            ),
        ]

        sync_service.media_repo.get_active_by_source_type.return_value = []
        sync_service.media_repo.get_inactive_by_source_identifier.return_value = None

        result = sync_service.sync()

        assert result.new == 1
        mock_provider.calculate_file_hash.assert_not_called()
        call_kwargs = sync_service.media_repo.create.call_args[1]
        assert call_kwargs["file_hash"] == "provider_hash"

    @patch("src.services.core.media_sync.settings")
    @patch("src.services.core.media_sync.MediaSourceFactory")
    def test_sync_falls_back_to_calculated_hash(
        self, mock_factory, mock_settings, sync_service
    ):
        """Falls back to provider.calculate_file_hash when file_info.hash is None."""
        mock_settings.MEDIA_SOURCE_TYPE = "local"
        mock_settings.MEDIA_SOURCE_ROOT = "/media"
        mock_settings.MEDIA_DIR = "/media"

        mock_provider = Mock()
        mock_factory.create.return_value = mock_provider
        mock_provider.is_configured.return_value = True
        mock_provider.list_files.return_value = [
            _make_file_info(name="local.jpg", identifier="/media/local.jpg"),
        ]
        mock_provider.calculate_file_hash.return_value = "calculated_hash"

        sync_service.media_repo.get_active_by_source_type.return_value = []
        sync_service.media_repo.get_inactive_by_source_identifier.return_value = None

        result = sync_service.sync()

        assert result.new == 1
        mock_provider.calculate_file_hash.assert_called_once_with("/media/local.jpg")
        call_kwargs = sync_service.media_repo.create.call_args[1]
        assert call_kwargs["file_hash"] == "calculated_hash"


# ==================== Provider Creation Tests ====================


@pytest.mark.unit
class TestMediaSyncServiceProviderCreation:
    """Tests for _create_provider method."""

    @patch("src.services.core.media_sync.MediaSourceFactory")
    def test_create_provider_local(self, mock_factory, sync_service):
        """Local provider passes base_path."""
        sync_service._create_provider("local", "/media/stories")

        mock_factory.create.assert_called_once_with("local", base_path="/media/stories")

    @patch("src.services.core.media_sync.MediaSourceFactory")
    def test_create_provider_google_drive(self, mock_factory, sync_service):
        """Google Drive provider passes root_folder_id."""
        sync_service._create_provider("google_drive", "folder_xyz")

        mock_factory.create.assert_called_once_with(
            "google_drive", root_folder_id="folder_xyz"
        )

    @patch("src.services.core.media_sync.settings")
    @patch("src.services.core.media_sync.MediaSourceFactory")
    def test_sync_local_fallback_to_media_dir(
        self, mock_factory, mock_settings, sync_service
    ):
        """When source_root is empty and source_type is local, uses MEDIA_DIR."""
        mock_settings.MEDIA_SOURCE_TYPE = "local"
        mock_settings.MEDIA_SOURCE_ROOT = ""
        mock_settings.MEDIA_DIR = "/home/pi/media"

        mock_provider = Mock()
        mock_factory.create.return_value = mock_provider
        mock_provider.is_configured.return_value = True
        mock_provider.list_files.return_value = []
        sync_service.media_repo.get_active_by_source_type.return_value = []

        sync_service.sync()

        mock_factory.create.assert_called_once_with("local", base_path="/home/pi/media")


# ==================== File Path Building Tests ====================


@pytest.mark.unit
class TestMediaSyncServiceFilePath:
    """Tests for _build_file_path method."""

    def test_build_file_path_local(self, sync_service):
        """Local source type returns the identifier as-is."""
        file_info = _make_file_info(identifier="/media/stories/photo.jpg")

        path = sync_service._build_file_path("local", file_info)

        assert path == "/media/stories/photo.jpg"

    def test_build_file_path_cloud(self, sync_service):
        """Cloud source type returns synthetic path."""
        file_info = _make_file_info(identifier="file_abc123")

        path = sync_service._build_file_path("google_drive", file_info)

        assert path == "google_drive://file_abc123"


# ==================== get_last_sync_info Tests ====================


@pytest.mark.unit
class TestMediaSyncServiceLastSyncInfo:
    """Tests for get_last_sync_info method."""

    def test_get_last_sync_info_returns_info(self, sync_service):
        """Returns dict shape when runs exist."""
        mock_run = Mock()
        mock_run.started_at = datetime(2026, 2, 12, 10, 0, 0)
        mock_run.completed_at = datetime(2026, 2, 12, 10, 0, 5)
        mock_run.duration_ms = 5000
        mock_run.status = "completed"
        mock_run.success = True
        mock_run.result_summary = {"new": 3, "errors": 0}
        mock_run.triggered_by = "scheduler"

        sync_service.service_run_repo.get_recent_runs.return_value = [mock_run]

        info = sync_service.get_last_sync_info()

        assert info is not None
        assert info["success"] is True
        assert info["duration_ms"] == 5000
        assert info["triggered_by"] == "scheduler"
        assert info["result"] == {"new": 3, "errors": 0}
        assert "2026-02-12" in info["started_at"]

    def test_get_last_sync_info_no_runs(self, sync_service):
        """Returns None when no runs exist."""
        sync_service.service_run_repo.get_recent_runs.return_value = []

        info = sync_service.get_last_sync_info()

        assert info is None

    def test_get_last_sync_info_failed_run(self, sync_service):
        """Returns failure info for failed run."""
        mock_run = Mock()
        mock_run.started_at = datetime(2026, 2, 12, 10, 0, 0)
        mock_run.completed_at = None
        mock_run.duration_ms = None
        mock_run.status = "failed"
        mock_run.success = False
        mock_run.result_summary = None
        mock_run.triggered_by = "cli"

        sync_service.service_run_repo.get_recent_runs.return_value = [mock_run]

        info = sync_service.get_last_sync_info()

        assert info["success"] is False
        assert info["status"] == "failed"
        assert info["completed_at"] is None


# ==================== Settings Resolution Tests ====================


@pytest.mark.unit
class TestMediaSyncServiceSettingsResolution:
    """Tests for settings override behavior in sync()."""

    @patch("src.services.core.media_sync.settings")
    @patch("src.services.core.media_sync.MediaSourceFactory")
    def test_sync_uses_overridden_source_type(
        self, mock_factory, mock_settings, sync_service
    ):
        """Passing source_type overrides settings.MEDIA_SOURCE_TYPE."""
        mock_settings.MEDIA_SOURCE_TYPE = "local"
        mock_settings.MEDIA_SOURCE_ROOT = "folder_id"
        mock_settings.MEDIA_DIR = "/media"

        mock_provider = Mock()
        mock_factory.create.return_value = mock_provider
        mock_provider.is_configured.return_value = True
        mock_provider.list_files.return_value = []
        sync_service.media_repo.get_active_by_source_type.return_value = []

        sync_service.sync(source_type="google_drive")

        mock_factory.create.assert_called_once_with(
            "google_drive", root_folder_id="folder_id"
        )

    @patch("src.services.core.media_sync.settings")
    @patch("src.services.core.media_sync.MediaSourceFactory")
    def test_sync_uses_overridden_source_root(
        self, mock_factory, mock_settings, sync_service
    ):
        """Passing source_root overrides settings.MEDIA_SOURCE_ROOT."""
        mock_settings.MEDIA_SOURCE_TYPE = "local"
        mock_settings.MEDIA_SOURCE_ROOT = "/default/path"
        mock_settings.MEDIA_DIR = "/media"

        mock_provider = Mock()
        mock_factory.create.return_value = mock_provider
        mock_provider.is_configured.return_value = True
        mock_provider.list_files.return_value = []
        sync_service.media_repo.get_active_by_source_type.return_value = []

        sync_service.sync(source_root="/custom/path")

        mock_factory.create.assert_called_once_with("local", base_path="/custom/path")
