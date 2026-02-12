"""Tests for GoogleDriveProvider."""

import hashlib
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest
from googleapiclient.errors import HttpError

from src.exceptions import (
    GoogleDriveAuthError,
    GoogleDriveError,
    GoogleDriveFileNotFoundError,
    GoogleDriveRateLimitError,
)
from src.services.media_sources.base_provider import MediaFileInfo
from src.services.media_sources.google_drive_provider import GoogleDriveProvider


# ==================== Fixtures ====================

FAKE_SERVICE_ACCOUNT_INFO = {
    "type": "service_account",
    "project_id": "test-project",
    "private_key_id": "key123",
    "private_key": "-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----\n",
    "client_email": "test@test-project.iam.gserviceaccount.com",
    "client_id": "123456789",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
}


def _make_http_error(status: int, reason: str = "error") -> HttpError:
    """Create a mock HttpError with the given status code."""
    resp = Mock()
    resp.status = status
    resp.reason = reason
    return HttpError(resp=resp, content=b"error")


@pytest.fixture
def mock_drive_service():
    """Create a mock Google Drive API service."""
    return MagicMock()


@pytest.fixture
def provider(mock_drive_service):
    """Create a GoogleDriveProvider with mocked service."""
    with patch(
        "src.services.media_sources.google_drive_provider."
        "ServiceAccountCredentials.from_service_account_info"
    ):
        p = GoogleDriveProvider(
            root_folder_id="root_folder_123",
            service_account_info=FAKE_SERVICE_ACCOUNT_INFO,
        )
    p._service = mock_drive_service
    return p


# ==================== Init Tests ====================


@pytest.mark.unit
class TestGoogleDriveProviderInit:
    """Tests for provider initialization."""

    def test_init_with_service_account(self):
        """Test initialization with service account credentials."""
        with patch(
            "src.services.media_sources.google_drive_provider."
            "ServiceAccountCredentials.from_service_account_info"
        ) as mock_creds:
            mock_creds.return_value = Mock()
            p = GoogleDriveProvider(
                root_folder_id="folder_abc",
                service_account_info=FAKE_SERVICE_ACCOUNT_INFO,
            )
            assert p.root_folder_id == "folder_abc"
            mock_creds.assert_called_once()

    def test_init_with_oauth_credentials(self):
        """Test initialization with OAuth user credentials."""
        mock_oauth = Mock()
        p = GoogleDriveProvider(
            root_folder_id="folder_abc",
            oauth_credentials=mock_oauth,
        )
        assert p.root_folder_id == "folder_abc"
        assert p._credentials is mock_oauth

    def test_init_no_credentials_raises(self):
        """Test that init raises when no credentials provided."""
        with pytest.raises(GoogleDriveAuthError, match="requires either"):
            GoogleDriveProvider(root_folder_id="folder_abc")


# ==================== is_configured Tests ====================


@pytest.mark.unit
class TestGoogleDriveProviderIsConfigured:
    """Tests for is_configured method."""

    def test_is_configured_success(self, provider, mock_drive_service):
        """Test is_configured returns True when folder is accessible."""
        mock_drive_service.files().get().execute.return_value = {
            "id": "root_folder_123",
            "name": "Media",
        }
        assert provider.is_configured() is True

    def test_is_configured_failure(self, provider, mock_drive_service):
        """Test is_configured returns False when folder is not accessible."""
        mock_drive_service.files().get().execute.side_effect = Exception("fail")
        assert provider.is_configured() is False


# ==================== list_files Tests ====================


@pytest.mark.unit
class TestGoogleDriveProviderListFiles:
    """Tests for list_files method."""

    def test_list_files_root_and_subfolders(self, provider, mock_drive_service):
        """Test listing files from root and subfolders."""
        # Root folder files
        mock_drive_service.files().list().execute.side_effect = [
            # Root files
            {
                "files": [
                    {
                        "id": "file1",
                        "name": "photo.jpg",
                        "mimeType": "image/jpeg",
                        "size": "1024",
                        "modifiedTime": "2026-01-15T10:30:00Z",
                        "md5Checksum": "abc123",
                        "parents": ["root_folder_123"],
                    }
                ]
            },
            # Subfolders
            {"files": [{"id": "subfolder1", "name": "memes"}]},
            # Subfolder files
            {
                "files": [
                    {
                        "id": "file2",
                        "name": "meme.png",
                        "mimeType": "image/png",
                        "size": "2048",
                        "modifiedTime": "2026-01-16T12:00:00Z",
                        "md5Checksum": "def456",
                        "parents": ["subfolder1"],
                    }
                ]
            },
        ]

        files = provider.list_files()

        assert len(files) == 2
        assert files[0].identifier == "file1"
        assert files[0].folder is None  # Root file
        assert files[1].identifier == "file2"
        assert files[1].folder == "memes"

    def test_list_files_specific_folder(self, provider, mock_drive_service):
        """Test listing files from a specific subfolder."""
        # Cache a subfolder
        provider._folder_cache["subfolder1"] = "memes"

        mock_drive_service.files().list().execute.return_value = {
            "files": [
                {
                    "id": "file1",
                    "name": "meme.jpg",
                    "mimeType": "image/jpeg",
                    "size": "512",
                    "parents": ["subfolder1"],
                }
            ]
        }

        files = provider.list_files(folder="memes")

        assert len(files) == 1
        assert files[0].folder == "memes"

    def test_list_files_nonexistent_folder(self, provider, mock_drive_service):
        """Test listing files from a folder that doesn't exist."""
        mock_drive_service.files().list().execute.return_value = {"files": []}

        files = provider.list_files(folder="nonexistent")

        assert files == []

    def test_list_files_api_error(self, provider, mock_drive_service):
        """Test list_files handles API errors gracefully."""
        mock_drive_service.files().list().execute.side_effect = _make_http_error(500)

        with pytest.raises(GoogleDriveError):
            provider.list_files()


# ==================== download_file Tests ====================


@pytest.mark.unit
class TestGoogleDriveProviderDownloadFile:
    """Tests for download_file method."""

    def test_download_file_success(self, provider, mock_drive_service):
        """Test successful file download."""
        mock_request = Mock()
        mock_drive_service.files().get_media.return_value = mock_request

        # Mock MediaIoBaseDownload
        with patch(
            "src.services.media_sources.google_drive_provider.MediaIoBaseDownload"
        ) as mock_download_class:
            mock_downloader = Mock()
            mock_downloader.next_chunk.return_value = (None, True)
            mock_download_class.return_value = mock_downloader

            # Write data to the buffer when download is created
            def capture_buffer(buffer, request):
                buffer.write(b"fake image bytes")
                return mock_downloader

            mock_download_class.side_effect = capture_buffer

            data = provider.download_file("file123")

        assert data == b"fake image bytes"

    def test_download_file_not_found(self, provider, mock_drive_service):
        """Test download raises GoogleDriveFileNotFoundError for 404."""
        mock_drive_service.files().get_media.side_effect = _make_http_error(404)

        with pytest.raises(GoogleDriveFileNotFoundError):
            provider.download_file("missing_file")

    def test_download_file_not_found_is_also_builtin_file_not_found(
        self, provider, mock_drive_service
    ):
        """Test that GoogleDriveFileNotFoundError is also a FileNotFoundError."""
        mock_drive_service.files().get_media.side_effect = _make_http_error(404)

        with pytest.raises(FileNotFoundError):
            provider.download_file("missing_file")


# ==================== get_file_info Tests ====================


@pytest.mark.unit
class TestGoogleDriveProviderGetFileInfo:
    """Tests for get_file_info method."""

    def test_get_file_info_success(self, provider, mock_drive_service):
        """Test getting file info for a valid file."""
        mock_drive_service.files().get().execute.return_value = {
            "id": "file123",
            "name": "photo.jpg",
            "mimeType": "image/jpeg",
            "size": "4096",
            "modifiedTime": "2026-02-01T08:00:00Z",
            "md5Checksum": "hash123",
            "parents": ["root_folder_123"],
        }

        info = provider.get_file_info("file123")

        assert info is not None
        assert info.identifier == "file123"
        assert info.name == "photo.jpg"
        assert info.mime_type == "image/jpeg"
        assert info.size_bytes == 4096
        assert info.hash == "hash123"
        assert info.folder is None  # Parent is root

    def test_get_file_info_not_found(self, provider, mock_drive_service):
        """Test get_file_info returns None for 404."""
        mock_drive_service.files().get().execute.side_effect = _make_http_error(404)

        info = provider.get_file_info("missing_file")

        assert info is None

    def test_get_file_info_unsupported_mime_type(self, provider, mock_drive_service):
        """Test get_file_info returns None for unsupported file types."""
        mock_drive_service.files().get().execute.return_value = {
            "id": "doc123",
            "name": "document.pdf",
            "mimeType": "application/pdf",
            "size": "1024",
            "parents": [],
        }

        info = provider.get_file_info("doc123")

        assert info is None


# ==================== file_exists Tests ====================


@pytest.mark.unit
class TestGoogleDriveProviderFileExists:
    """Tests for file_exists method."""

    def test_file_exists_true(self, provider, mock_drive_service):
        """Test file_exists returns True for existing file."""
        mock_drive_service.files().get().execute.return_value = {"id": "file123"}
        assert provider.file_exists("file123") is True

    def test_file_exists_false(self, provider, mock_drive_service):
        """Test file_exists returns False when file not found."""
        mock_drive_service.files().get().execute.side_effect = _make_http_error(404)
        assert provider.file_exists("missing") is False


# ==================== get_folders Tests ====================


@pytest.mark.unit
class TestGoogleDriveProviderGetFolders:
    """Tests for get_folders method."""

    def test_get_folders_success(self, provider, mock_drive_service):
        """Test listing subfolders as categories."""
        mock_drive_service.files().list().execute.return_value = {
            "files": [
                {"id": "f1", "name": "memes"},
                {"id": "f2", "name": "merch"},
                {"id": "f3", "name": "announcements"},
            ]
        }

        folders = provider.get_folders()

        assert folders == ["announcements", "memes", "merch"]  # Sorted

    def test_get_folders_empty(self, provider, mock_drive_service):
        """Test get_folders returns empty list when no subfolders."""
        mock_drive_service.files().list().execute.return_value = {"files": []}

        folders = provider.get_folders()

        assert folders == []


# ==================== calculate_file_hash Tests ====================


@pytest.mark.unit
class TestGoogleDriveProviderCalculateFileHash:
    """Tests for calculate_file_hash method."""

    def test_calculate_file_hash_uses_md5_checksum(self, provider, mock_drive_service):
        """Test that md5Checksum from Drive API is used when available."""
        mock_drive_service.files().get().execute.return_value = {
            "id": "file123",
            "md5Checksum": "drive_md5_hash",
        }

        result = provider.calculate_file_hash("file123")

        assert result == "drive_md5_hash"

    def test_calculate_file_hash_fallback_sha256(self, provider, mock_drive_service):
        """Test SHA256 fallback when md5Checksum is not available."""
        mock_drive_service.files().get().execute.return_value = {
            "id": "file123",
        }

        # Mock download_file for fallback
        file_content = b"test file content"
        expected_hash = hashlib.sha256(file_content).hexdigest()

        with patch.object(provider, "download_file", return_value=file_content):
            result = provider.calculate_file_hash("file123")

        assert result == expected_hash

    def test_calculate_file_hash_not_found(self, provider, mock_drive_service):
        """Test calculate_file_hash raises for missing file."""
        mock_drive_service.files().get().execute.side_effect = _make_http_error(404)

        with pytest.raises(GoogleDriveFileNotFoundError):
            provider.calculate_file_hash("missing_file")


# ==================== _handle_http_error Tests ====================


@pytest.mark.unit
class TestGoogleDriveProviderHandleHttpError:
    """Tests for _handle_http_error error mapping."""

    def test_handle_401_raises_auth_error(self, provider):
        """Test 401 is mapped to GoogleDriveAuthError."""
        with pytest.raises(GoogleDriveAuthError):
            provider._handle_http_error(_make_http_error(401), context="test")

    def test_handle_403_raises_auth_error(self, provider):
        """Test 403 is mapped to GoogleDriveAuthError."""
        with pytest.raises(GoogleDriveAuthError):
            provider._handle_http_error(_make_http_error(403), context="test")

    def test_handle_404_raises_not_found(self, provider):
        """Test 404 is mapped to GoogleDriveFileNotFoundError."""
        with pytest.raises(GoogleDriveFileNotFoundError):
            provider._handle_http_error(_make_http_error(404), context="test")

    def test_handle_429_raises_rate_limit(self, provider):
        """Test 429 is mapped to GoogleDriveRateLimitError."""
        with pytest.raises(GoogleDriveRateLimitError) as exc_info:
            provider._handle_http_error(_make_http_error(429), context="test")
        assert exc_info.value.retry_after_seconds == 60

    def test_handle_500_raises_generic_error(self, provider):
        """Test 500 is mapped to GoogleDriveError."""
        with pytest.raises(GoogleDriveError):
            provider._handle_http_error(_make_http_error(500), context="test")


# ==================== _build_file_info Tests ====================


@pytest.mark.unit
class TestGoogleDriveProviderBuildFileInfo:
    """Tests for _build_file_info helper."""

    def test_build_file_info_complete(self, provider):
        """Test building file info from complete metadata."""
        file_meta = {
            "id": "file_abc",
            "name": "story.jpg",
            "mimeType": "image/jpeg",
            "size": "8192",
            "modifiedTime": "2026-01-20T14:30:00Z",
            "md5Checksum": "md5hash",
        }

        info = provider._build_file_info(file_meta, folder_name="memes")

        assert isinstance(info, MediaFileInfo)
        assert info.identifier == "file_abc"
        assert info.name == "story.jpg"
        assert info.mime_type == "image/jpeg"
        assert info.size_bytes == 8192
        assert info.folder == "memes"
        assert info.hash == "md5hash"
        assert isinstance(info.modified_at, datetime)

    def test_build_file_info_missing_id_returns_none(self, provider):
        """Test that missing file ID returns None."""
        file_meta = {"name": "orphan.jpg", "mimeType": "image/jpeg", "size": "100"}

        info = provider._build_file_info(file_meta, folder_name=None)

        assert info is None

    def test_build_file_info_no_modified_time(self, provider):
        """Test building file info when modifiedTime is absent."""
        file_meta = {
            "id": "file_xyz",
            "name": "old.png",
            "mimeType": "image/png",
            "size": "500",
        }

        info = provider._build_file_info(file_meta, folder_name=None)

        assert info is not None
        assert info.modified_at is None
        assert info.hash is None
