"""Tests for CloudStorageService."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from contextlib import contextmanager
from datetime import datetime, timedelta
import tempfile
from pathlib import Path

from src.exceptions import MediaUploadError


@contextmanager
def mock_track_execution(*args, **kwargs):
    """Mock context manager for track_execution."""
    yield "mock_run_id"


@pytest.mark.unit
class TestCloudStorageService:
    """Test suite for CloudStorageService."""

    @pytest.fixture
    def cloud_service(self):
        """Create CloudStorageService with mocked dependencies."""
        with patch("src.services.integrations.cloud_storage.cloudinary"):
            with patch("src.services.integrations.cloud_storage.settings") as mock_settings:
                with patch("src.services.base_service.ServiceRunRepository"):
                    mock_settings.CLOUDINARY_CLOUD_NAME = "test_cloud"
                    mock_settings.CLOUDINARY_API_KEY = "test_key"
                    mock_settings.CLOUDINARY_API_SECRET = "test_secret"
                    mock_settings.CLOUD_UPLOAD_RETENTION_HOURS = 24

                    from src.services.integrations.cloud_storage import CloudStorageService
                    service = CloudStorageService()
                    service.track_execution = mock_track_execution
                    service.set_result_summary = Mock()
                    yield service

    @pytest.fixture
    def temp_image_file(self):
        """Create a temporary image file for testing."""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".jpg", delete=False) as f:
            # Write minimal JPEG header
            f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00')
            temp_path = Path(f.name)

        yield temp_path

        # Cleanup
        if temp_path.exists():
            temp_path.unlink()

    @pytest.fixture
    def temp_video_file(self):
        """Create a temporary video file for testing."""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".mp4", delete=False) as f:
            f.write(b'\x00\x00\x00\x1c\x66\x74\x79\x70')  # MP4 header bytes
            temp_path = Path(f.name)

        yield temp_path

        # Cleanup
        if temp_path.exists():
            temp_path.unlink()

    # ==================== is_configured Tests ====================

    @patch("src.services.base_service.ServiceRunRepository")
    @patch("src.services.integrations.cloud_storage.settings")
    def test_is_configured_all_credentials_present(self, mock_settings, mock_repo):
        """Test is_configured returns True when all credentials set."""
        mock_settings.CLOUDINARY_CLOUD_NAME = "cloud"
        mock_settings.CLOUDINARY_API_KEY = "key"
        mock_settings.CLOUDINARY_API_SECRET = "secret"

        with patch("src.services.integrations.cloud_storage.cloudinary"):
            from src.services.integrations.cloud_storage import CloudStorageService
            service = CloudStorageService()
            assert service.is_configured() is True

    @patch("src.services.base_service.ServiceRunRepository")
    @patch("src.services.integrations.cloud_storage.settings")
    def test_is_configured_missing_cloud_name(self, mock_settings, mock_repo):
        """Test is_configured returns False when cloud_name missing."""
        mock_settings.CLOUDINARY_CLOUD_NAME = None
        mock_settings.CLOUDINARY_API_KEY = "key"
        mock_settings.CLOUDINARY_API_SECRET = "secret"

        with patch("src.services.integrations.cloud_storage.cloudinary"):
            from src.services.integrations.cloud_storage import CloudStorageService
            service = CloudStorageService()
            assert service.is_configured() is False

    @patch("src.services.base_service.ServiceRunRepository")
    @patch("src.services.integrations.cloud_storage.settings")
    def test_is_configured_missing_api_key(self, mock_settings, mock_repo):
        """Test is_configured returns False when api_key missing."""
        mock_settings.CLOUDINARY_CLOUD_NAME = "cloud"
        mock_settings.CLOUDINARY_API_KEY = None
        mock_settings.CLOUDINARY_API_SECRET = "secret"

        with patch("src.services.integrations.cloud_storage.cloudinary"):
            from src.services.integrations.cloud_storage import CloudStorageService
            service = CloudStorageService()
            assert service.is_configured() is False

    @patch("src.services.base_service.ServiceRunRepository")
    @patch("src.services.integrations.cloud_storage.settings")
    def test_is_configured_missing_api_secret(self, mock_settings, mock_repo):
        """Test is_configured returns False when api_secret missing."""
        mock_settings.CLOUDINARY_CLOUD_NAME = "cloud"
        mock_settings.CLOUDINARY_API_KEY = "key"
        mock_settings.CLOUDINARY_API_SECRET = None

        with patch("src.services.integrations.cloud_storage.cloudinary"):
            from src.services.integrations.cloud_storage import CloudStorageService
            service = CloudStorageService()
            assert service.is_configured() is False

    # ==================== upload_media Tests ====================

    @patch("src.services.integrations.cloud_storage.cloudinary")
    def test_upload_media_success(self, mock_cloudinary, cloud_service, temp_image_file):
        """Test successful media upload."""
        mock_cloudinary.uploader.upload.return_value = {
            "secure_url": "https://res.cloudinary.com/test/image/upload/test_image.jpg",
            "public_id": "storyline/test_image",
            "bytes": 12345,
            "format": "jpg",
            "width": 1080,
            "height": 1920,
        }

        result = cloud_service.upload_media(str(temp_image_file))

        assert result["url"] == "https://res.cloudinary.com/test/image/upload/test_image.jpg"
        assert result["public_id"] == "storyline/test_image"
        assert result["size_bytes"] == 12345
        assert result["format"] == "jpg"
        assert "uploaded_at" in result
        assert "expires_at" in result
        assert result["expires_at"] > result["uploaded_at"]

    @patch("src.services.integrations.cloud_storage.cloudinary")
    def test_upload_media_custom_folder(self, mock_cloudinary, cloud_service, temp_image_file):
        """Test upload with custom folder."""
        mock_cloudinary.uploader.upload.return_value = {
            "secure_url": "https://res.cloudinary.com/test/image/upload/custom/image.jpg",
            "public_id": "custom/image",
            "bytes": 1000,
            "format": "jpg",
        }

        cloud_service.upload_media(str(temp_image_file), folder="custom")

        # Verify folder was passed to upload
        call_kwargs = mock_cloudinary.uploader.upload.call_args[1]
        assert call_kwargs["folder"] == "custom"

    @patch("src.services.integrations.cloud_storage.cloudinary")
    def test_upload_media_custom_public_id(self, mock_cloudinary, cloud_service, temp_image_file):
        """Test upload with custom public_id."""
        mock_cloudinary.uploader.upload.return_value = {
            "secure_url": "https://example.com/image.jpg",
            "public_id": "my_custom_id",
            "bytes": 1000,
            "format": "jpg",
        }

        cloud_service.upload_media(str(temp_image_file), public_id="my_custom_id")

        call_kwargs = mock_cloudinary.uploader.upload.call_args[1]
        assert call_kwargs["public_id"] == "my_custom_id"

    @patch("src.services.integrations.cloud_storage.cloudinary")
    def test_upload_media_video_resource_type(self, mock_cloudinary, cloud_service, temp_video_file):
        """Test that video files use video resource type."""
        mock_cloudinary.uploader.upload.return_value = {
            "secure_url": "https://example.com/video.mp4",
            "public_id": "test_video",
            "bytes": 50000,
            "format": "mp4",
        }

        cloud_service.upload_media(str(temp_video_file))

        call_kwargs = mock_cloudinary.uploader.upload.call_args[1]
        assert call_kwargs["resource_type"] == "video"

    def test_upload_media_file_not_found(self, cloud_service):
        """Test upload raises error for non-existent file."""
        with pytest.raises(MediaUploadError, match="File not found"):
            cloud_service.upload_media("/path/to/nonexistent/file.jpg")

    def test_upload_media_path_is_directory(self, cloud_service, tmp_path):
        """Test upload raises error when path is a directory."""
        with pytest.raises(MediaUploadError, match="not a file"):
            cloud_service.upload_media(str(tmp_path))

    @patch("src.services.integrations.cloud_storage.cloudinary")
    def test_upload_media_cloudinary_error(self, mock_cloudinary, cloud_service, temp_image_file):
        """Test upload handles Cloudinary errors."""
        # Create a mock exception class
        mock_cloudinary.exceptions = MagicMock()
        mock_cloudinary.exceptions.Error = Exception
        mock_cloudinary.uploader.upload.side_effect = Exception("Upload failed")

        with pytest.raises(MediaUploadError, match="Cloudinary upload failed"):
            cloud_service.upload_media(str(temp_image_file))

    # ==================== delete_media Tests ====================

    @patch("src.services.integrations.cloud_storage.cloudinary")
    def test_delete_media_success(self, mock_cloudinary, cloud_service):
        """Test successful media deletion."""
        mock_cloudinary.uploader.destroy.return_value = {"result": "ok"}

        result = cloud_service.delete_media("storyline/test_image")

        assert result is True
        mock_cloudinary.uploader.destroy.assert_called_once_with("storyline/test_image")

    @patch("src.services.integrations.cloud_storage.cloudinary")
    def test_delete_media_not_found(self, mock_cloudinary, cloud_service):
        """Test delete returns False when image not found."""
        mock_cloudinary.uploader.destroy.return_value = {"result": "not found"}

        result = cloud_service.delete_media("nonexistent")

        assert result is False

    @patch("src.services.integrations.cloud_storage.cloudinary")
    def test_delete_media_error(self, mock_cloudinary, cloud_service):
        """Test delete handles errors gracefully."""
        mock_cloudinary.exceptions = MagicMock()
        mock_cloudinary.exceptions.Error = Exception
        mock_cloudinary.uploader.destroy.side_effect = Exception("Delete failed")

        result = cloud_service.delete_media("test_id")

        assert result is False

    # ==================== get_url Tests ====================

    @patch("src.services.integrations.cloud_storage.cloudinary")
    def test_get_url_success(self, mock_cloudinary, cloud_service):
        """Test getting URL for existing resource."""
        mock_cloudinary.api.resource.return_value = {
            "secure_url": "https://res.cloudinary.com/test/image.jpg"
        }

        url = cloud_service.get_url("test_image")

        assert url == "https://res.cloudinary.com/test/image.jpg"

    @patch("src.services.integrations.cloud_storage.cloudinary")
    def test_get_url_not_found(self, mock_cloudinary, cloud_service):
        """Test get_url returns None when resource not found."""
        mock_cloudinary.exceptions = MagicMock()
        mock_cloudinary.exceptions.NotFound = type("NotFound", (Exception,), {})
        mock_cloudinary.api.resource.side_effect = mock_cloudinary.exceptions.NotFound()

        url = cloud_service.get_url("nonexistent")

        assert url is None

    @patch("src.services.integrations.cloud_storage.cloudinary")
    def test_get_url_error(self, mock_cloudinary, cloud_service):
        """Test get_url handles errors gracefully."""
        mock_cloudinary.exceptions = MagicMock()
        mock_cloudinary.exceptions.NotFound = type("NotFound", (Exception,), {})
        mock_cloudinary.exceptions.Error = Exception
        mock_cloudinary.api.resource.side_effect = Exception("API Error")

        url = cloud_service.get_url("test_id")

        assert url is None

    # ==================== cleanup_expired Tests ====================

    @patch("src.services.integrations.cloud_storage.cloudinary")
    def test_cleanup_expired_deletes_old_resources(self, mock_cloudinary, cloud_service):
        """Test cleanup deletes resources older than retention period."""
        # Old resource (48 hours ago)
        old_date = (datetime.utcnow() - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")
        # New resource (1 hour ago)
        new_date = (datetime.utcnow() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

        mock_cloudinary.api.resources.return_value = {
            "resources": [
                {"public_id": "storyline/old_image", "created_at": old_date},
                {"public_id": "storyline/new_image", "created_at": new_date},
            ]
        }
        mock_cloudinary.uploader.destroy.return_value = {"result": "ok"}

        deleted_count = cloud_service.cleanup_expired()

        # Only the old resource should be deleted
        assert deleted_count == 1
        mock_cloudinary.uploader.destroy.assert_called_once_with("storyline/old_image")

    @patch("src.services.integrations.cloud_storage.cloudinary")
    def test_cleanup_expired_no_old_resources(self, mock_cloudinary, cloud_service):
        """Test cleanup returns 0 when no old resources."""
        recent_date = (datetime.utcnow() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

        mock_cloudinary.api.resources.return_value = {
            "resources": [
                {"public_id": "storyline/recent", "created_at": recent_date},
            ]
        }

        deleted_count = cloud_service.cleanup_expired()

        assert deleted_count == 0
        mock_cloudinary.uploader.destroy.assert_not_called()

    @patch("src.services.integrations.cloud_storage.cloudinary")
    def test_cleanup_expired_handles_api_error(self, mock_cloudinary, cloud_service):
        """Test cleanup handles API errors gracefully."""
        mock_cloudinary.exceptions = MagicMock()
        mock_cloudinary.exceptions.Error = Exception
        mock_cloudinary.api.resources.side_effect = Exception("API Error")

        deleted_count = cloud_service.cleanup_expired()

        assert deleted_count == 0

    @patch("src.services.integrations.cloud_storage.cloudinary")
    def test_cleanup_expired_custom_folder(self, mock_cloudinary, cloud_service):
        """Test cleanup uses custom folder parameter."""
        mock_cloudinary.api.resources.return_value = {"resources": []}

        cloud_service.cleanup_expired(folder="custom_folder")

        call_kwargs = mock_cloudinary.api.resources.call_args[1]
        assert call_kwargs["prefix"] == "custom_folder"

    # ==================== _get_resource_type Tests ====================

    def test_get_resource_type_image_extensions(self, cloud_service):
        """Test resource type detection for image files."""
        assert cloud_service._get_resource_type(Path("test.jpg")) == "image"
        assert cloud_service._get_resource_type(Path("test.jpeg")) == "image"
        assert cloud_service._get_resource_type(Path("test.png")) == "image"
        assert cloud_service._get_resource_type(Path("test.gif")) == "image"

    def test_get_resource_type_video_extensions(self, cloud_service):
        """Test resource type detection for video files."""
        assert cloud_service._get_resource_type(Path("test.mp4")) == "video"
        assert cloud_service._get_resource_type(Path("test.mov")) == "video"
        assert cloud_service._get_resource_type(Path("test.avi")) == "video"
        assert cloud_service._get_resource_type(Path("test.webm")) == "video"

    def test_get_resource_type_case_insensitive(self, cloud_service):
        """Test resource type detection is case insensitive."""
        assert cloud_service._get_resource_type(Path("test.MP4")) == "video"
        assert cloud_service._get_resource_type(Path("test.JPG")) == "image"
