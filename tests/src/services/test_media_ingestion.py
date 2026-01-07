"""Tests for MediaIngestionService."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import os

from src.services.core.media_ingestion import MediaIngestionService


@pytest.mark.unit
class TestMediaIngestionService:
    """Test suite for MediaIngestionService."""

    @pytest.fixture
    def ingestion_service(self):
        """Create MediaIngestionService with mocked dependencies."""
        with patch("src.services.core.media_ingestion.MediaRepository"):
            with patch("src.services.base_service.ServiceRunRepository"):
                service = MediaIngestionService()
                service.media_repo = Mock()
                service.image_processor = Mock()
                # Mock the track_execution context manager
                service.track_execution = MagicMock()
                service.track_execution.return_value.__enter__ = Mock(return_value="run-123")
                service.track_execution.return_value.__exit__ = Mock(return_value=False)
                service.set_result_summary = Mock()
                return service

    def test_scan_directory_validates_path_exists(self, ingestion_service):
        """Test that scan_directory raises ValueError for non-existent path."""
        with pytest.raises(ValueError, match="Directory does not exist"):
            ingestion_service.scan_directory("/nonexistent/path/12345")

    def test_scan_directory_validates_path_is_directory(self, ingestion_service):
        """Test that scan_directory raises ValueError for file path."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            try:
                with pytest.raises(ValueError, match="not a directory"):
                    ingestion_service.scan_directory(tmp.name)
            finally:
                os.unlink(tmp.name)

    def test_scan_directory_filters_supported_extensions(self, ingestion_service):
        """Test that only supported file formats are indexed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            (Path(temp_dir) / "image.jpg").write_bytes(b"jpg content")
            (Path(temp_dir) / "readme.txt").write_bytes(b"text content")
            (Path(temp_dir) / "photo.png").write_bytes(b"png content")

            # Mock to avoid actual indexing
            ingestion_service.media_repo.get_by_path.return_value = None
            ingestion_service.media_repo.get_by_hash.return_value = []

            # Mock image processor validation
            mock_validation = Mock()
            mock_validation.is_valid = True
            mock_validation.warnings = []
            ingestion_service.image_processor.validate_image.return_value = mock_validation

            result = ingestion_service.scan_directory(temp_dir)

            # Should skip .txt file (not in SUPPORTED_EXTENSIONS)
            assert result["skipped"] >= 1
            # Should index .jpg and .png files
            assert result["indexed"] >= 2

    def test_scan_directory_returns_correct_counts(self, ingestion_service):
        """Test that scan_directory returns correct result counts."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a supported image file
            (Path(temp_dir) / "test.jpg").write_bytes(b"test image")

            # Mock dependencies
            ingestion_service.media_repo.get_by_path.return_value = None
            ingestion_service.media_repo.get_by_hash.return_value = []
            mock_validation = Mock(is_valid=True, warnings=[])
            ingestion_service.image_processor.validate_image.return_value = mock_validation

            result = ingestion_service.scan_directory(temp_dir)

            assert "indexed" in result
            assert "skipped" in result
            assert "errors" in result
            assert "total_files" in result
            assert result["total_files"] == result["indexed"] + result["skipped"] + result["errors"]

    def test_scan_directory_recursive(self, ingestion_service):
        """Test that recursive scan finds files in subdirectories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create subdirectory with image
            subdir = Path(temp_dir) / "subdir"
            subdir.mkdir()
            (subdir / "nested.jpg").write_bytes(b"nested image")

            # Mock dependencies
            ingestion_service.media_repo.get_by_path.return_value = None
            ingestion_service.media_repo.get_by_hash.return_value = []
            mock_validation = Mock(is_valid=True, warnings=[])
            ingestion_service.image_processor.validate_image.return_value = mock_validation

            result = ingestion_service.scan_directory(temp_dir, recursive=True)

            assert result["indexed"] >= 1

    def test_scan_directory_non_recursive(self, ingestion_service):
        """Test that non-recursive scan doesn't find files in subdirectories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create subdirectory with image
            subdir = Path(temp_dir) / "subdir"
            subdir.mkdir()
            (subdir / "nested.jpg").write_bytes(b"nested image")

            result = ingestion_service.scan_directory(temp_dir, recursive=False)

            # Nested file should not be found
            assert result["indexed"] == 0

    def test_index_file_skips_existing(self, ingestion_service):
        """Test that _index_file skips already indexed files."""
        mock_existing = Mock()
        ingestion_service.media_repo.get_by_path.return_value = mock_existing

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(b"test content")
            try:
                # Should return early without creating new record
                ingestion_service._index_file(Path(tmp.name), user_id=None)

                # Should not call create since file already exists
                ingestion_service.media_repo.create.assert_not_called()
            finally:
                os.unlink(tmp.name)

    @patch("src.services.core.media_ingestion.calculate_file_hash")
    def test_index_file_creates_media_item(self, mock_hash, ingestion_service):
        """Test that _index_file creates media item for new files."""
        mock_hash.return_value = "abc123hash"
        ingestion_service.media_repo.get_by_path.return_value = None
        ingestion_service.media_repo.get_by_hash.return_value = []
        mock_validation = Mock(is_valid=True, warnings=[])
        ingestion_service.image_processor.validate_image.return_value = mock_validation

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(b"test image content")
            try:
                ingestion_service._index_file(Path(tmp.name), user_id="user-123")

                # Should create media item
                ingestion_service.media_repo.create.assert_called_once()
                call_kwargs = ingestion_service.media_repo.create.call_args.kwargs
                assert call_kwargs["file_hash"] == "abc123hash"
                assert call_kwargs["indexed_by_user_id"] == "user-123"
            finally:
                os.unlink(tmp.name)

    @patch("src.services.core.media_ingestion.calculate_file_hash")
    def test_index_file_validates_images(self, mock_hash, ingestion_service):
        """Test that _index_file validates image files."""
        mock_hash.return_value = "hash123"
        ingestion_service.media_repo.get_by_path.return_value = None
        ingestion_service.media_repo.get_by_hash.return_value = []

        # Mock invalid validation
        mock_validation = Mock(is_valid=False, errors=["Image too small"])
        ingestion_service.image_processor.validate_image.return_value = mock_validation

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(b"tiny image")
            try:
                with pytest.raises(ValueError, match="validation failed"):
                    ingestion_service._index_file(Path(tmp.name), user_id=None)
            finally:
                os.unlink(tmp.name)

    @patch("src.services.core.media_ingestion.calculate_file_hash")
    def test_index_file_detects_duplicates(self, mock_hash, ingestion_service):
        """Test that _index_file detects duplicate content."""
        mock_hash.return_value = "duplicate_hash"
        ingestion_service.media_repo.get_by_path.return_value = None
        ingestion_service.media_repo.get_by_hash.return_value = [Mock()]  # Has duplicate
        mock_validation = Mock(is_valid=True, warnings=[])
        ingestion_service.image_processor.validate_image.return_value = mock_validation

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(b"duplicate content")
            try:
                # Should still index (with warning logged)
                ingestion_service._index_file(Path(tmp.name), user_id=None)

                # Should still create the record
                ingestion_service.media_repo.create.assert_called_once()
            finally:
                os.unlink(tmp.name)

    def test_supported_extensions(self):
        """Test that SUPPORTED_EXTENSIONS contains expected formats."""
        assert ".jpg" in MediaIngestionService.SUPPORTED_EXTENSIONS
        assert ".jpeg" in MediaIngestionService.SUPPORTED_EXTENSIONS
        assert ".png" in MediaIngestionService.SUPPORTED_EXTENSIONS
        assert ".gif" in MediaIngestionService.SUPPORTED_EXTENSIONS
        assert ".mp4" in MediaIngestionService.SUPPORTED_EXTENSIONS
        assert ".mov" in MediaIngestionService.SUPPORTED_EXTENSIONS
        # Text files should NOT be supported
        assert ".txt" not in MediaIngestionService.SUPPORTED_EXTENSIONS
