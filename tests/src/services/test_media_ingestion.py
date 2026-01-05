"""Tests for MediaIngestionService."""
import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from src.services.core.media_ingestion import MediaIngestionService


@pytest.mark.unit
class TestMediaIngestionService:
    """Test suite for MediaIngestionService."""

    def test_scan_directory_validates_path_exists(self):
        """Test that scan_directory validates directory exists."""
        service = MediaIngestionService()

        with pytest.raises(ValueError, match="Directory does not exist"):
            service.scan_directory("/nonexistent/path")

    @patch("src.services.core.media_ingestion.Path")
    def test_scan_directory_only_processes_supported_formats(self, mock_path):
        """Test that only supported file formats are indexed."""
        service = MediaIngestionService()

        # Mock file list
        mock_files = [
            Mock(is_file=lambda: True, suffix=".jpg", name="image.jpg"),
            Mock(is_file=lambda: True, suffix=".txt", name="readme.txt"),  # Unsupported
            Mock(is_file=lambda: True, suffix=".png", name="photo.png"),
        ]

        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = True
        mock_path_instance.is_dir.return_value = True
        mock_path_instance.glob.return_value = mock_files
        mock_path.return_value = mock_path_instance

        # Mock repository
        service.media_repo = Mock()
        service.media_repo.get_by_path.return_value = None

        # Mock _index_file to avoid actual file operations
        service._index_file = Mock()

        result = service.scan_directory("/test/path")

        # Should skip .txt file
        assert result["skipped"] >= 1

    def test_index_file_creates_media_item(self, test_db):
        """Test indexing a file creates a media item."""
        from src.repositories.media_repository import MediaRepository
        import tempfile
        from pathlib import Path

        # Create a temporary image file
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_file:
            temp_file.write(b"fake image content")
            temp_path = Path(temp_file.name)

        try:
            service = MediaIngestionService(db=test_db)

            result = service._index_file(temp_path)

            assert result is True

            # Verify media was created in database
            media_repo = MediaRepository(test_db)
            media = media_repo.get_by_path(str(temp_path))

            assert media is not None
            assert media.file_name == temp_path.name
            assert media.file_hash is not None
        finally:
            temp_path.unlink()

    def test_scan_directory_skips_duplicates(self, test_db):
        """Test that scanning skips duplicate files."""
        from src.repositories.media_repository import MediaRepository
        import tempfile
        from pathlib import Path

        # Create temp directory with files
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test file
            test_file = temp_path / "test.jpg"
            test_file.write_text("test content")

            service = MediaIngestionService(db=test_db)

            # First scan should add the file
            result1 = service.scan_directory(str(temp_path))
            assert result1["added"] >= 1

            # Second scan should skip the file (already indexed)
            result2 = service.scan_directory(str(temp_path))
            assert result2["already_exists"] >= 1
