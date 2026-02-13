"""Tests for media CLI commands."""

import pytest
from unittest.mock import Mock, patch
from click.testing import CliRunner

from cli.commands.media import index, list_media, validate


@pytest.mark.unit
class TestIndexMediaCommand:
    """Tests for the index-media CLI command."""

    @patch("cli.commands.media.CategoryMixRepository")
    @patch("cli.commands.media.MediaRepository")
    @patch("cli.commands.media.MediaIngestionService")
    def test_index_media_success(
        self, mock_service_class, mock_media_repo_class, mock_mix_repo_class
    ):
        """Test index-media indexes files from a directory."""
        import tempfile

        mock_service = mock_service_class.return_value
        mock_service.scan_directory.return_value = {
            "indexed": 3,
            "skipped": 1,
            "errors": 0,
            "categories": ["memes"],
        }

        mock_media_repo = mock_media_repo_class.return_value
        mock_media_repo.get_categories.return_value = ["memes"]

        mock_mix_repo = mock_mix_repo_class.return_value
        mock_mix_repo.has_current_mix.return_value = True
        mock_mix_repo.get_current_mix_as_dict.return_value = {"memes": 1.0}
        mock_mix_repo.get_categories_without_ratio.return_value = []

        mock_mix_entry = Mock()
        mock_mix_entry.category = "memes"
        mock_mix_entry.ratio = 1.0
        mock_mix_repo.get_current_mix.return_value = [mock_mix_entry]

        mock_media_repo.get_all.return_value = [Mock(), Mock(), Mock()]

        with tempfile.TemporaryDirectory() as temp_dir:
            runner = CliRunner()
            result = runner.invoke(index, [temp_dir], input="y\n")

        assert result.exit_code == 0
        assert "Indexing complete" in result.output
        assert "Indexed: 3" in result.output
        mock_service.scan_directory.assert_called_once()

    def test_index_media_nonexistent_directory(self):
        """Test index-media with non-existent directory is rejected by Click."""
        runner = CliRunner()
        result = runner.invoke(index, ["/nonexistent/path/that/does/not/exist"])

        assert result.exit_code == 2
        assert "does not exist" in result.output.lower() or "Error" in result.output

    @patch("cli.commands.media.CategoryMixRepository")
    @patch("cli.commands.media.MediaRepository")
    @patch("cli.commands.media.MediaIngestionService")
    def test_index_media_service_error(
        self, mock_service_class, mock_media_repo_class, mock_mix_repo_class
    ):
        """Test index-media handles service errors gracefully."""
        import tempfile

        mock_service = mock_service_class.return_value
        mock_service.scan_directory.side_effect = RuntimeError("Disk full")

        with tempfile.TemporaryDirectory() as temp_dir:
            runner = CliRunner()
            result = runner.invoke(index, [temp_dir])

        assert result.exit_code != 0
        assert "Error" in result.output


@pytest.mark.unit
class TestListMediaCommand:
    """Tests for the list-media CLI command."""

    @patch("cli.commands.media.MediaRepository")
    def test_list_media_shows_items(self, mock_repo_class):
        """Test list-media displays media items in a table."""
        from datetime import datetime

        mock_repo = mock_repo_class.return_value

        mock_item = Mock()
        mock_item.file_name = "list1.jpg"
        mock_item.category = "memes"
        mock_item.times_posted = 3
        mock_item.last_posted_at = datetime(2026, 2, 10)
        mock_item.is_active = True

        mock_repo.get_all.return_value = [mock_item]

        runner = CliRunner()
        result = runner.invoke(list_media, ["--limit", "10"])

        assert result.exit_code == 0
        assert "list1.jpg" in result.output
        assert "memes" in result.output
        mock_repo.get_all.assert_called_once_with(
            is_active=None, category=None, limit=10
        )

    @patch("cli.commands.media.MediaRepository")
    def test_list_media_empty(self, mock_repo_class):
        """Test list-media with no media shows empty message."""
        mock_repo = mock_repo_class.return_value
        mock_repo.get_all.return_value = []

        runner = CliRunner()
        result = runner.invoke(list_media, [])

        assert result.exit_code == 0
        assert "No media items found" in result.output

    @patch("cli.commands.media.MediaRepository")
    def test_list_media_with_category_filter(self, mock_repo_class):
        """Test list-media filters by category."""
        mock_repo = mock_repo_class.return_value

        mock_item = Mock()
        mock_item.file_name = "merch_item.jpg"
        mock_item.category = "merch"
        mock_item.times_posted = 0
        mock_item.last_posted_at = None
        mock_item.is_active = True

        mock_repo.get_all.return_value = [mock_item]

        runner = CliRunner()
        result = runner.invoke(list_media, ["--category", "merch"])

        assert result.exit_code == 0
        assert "merch" in result.output
        mock_repo.get_all.assert_called_once_with(
            is_active=None, category="merch", limit=20
        )

    @patch("cli.commands.media.MediaRepository")
    def test_list_media_active_only(self, mock_repo_class):
        """Test list-media with --active-only flag."""
        mock_repo = mock_repo_class.return_value
        mock_repo.get_all.return_value = []

        runner = CliRunner()
        result = runner.invoke(list_media, ["--active-only"])

        assert result.exit_code == 0
        mock_repo.get_all.assert_called_once_with(
            is_active=True, category=None, limit=20
        )


@pytest.mark.unit
class TestValidateImageCommand:
    """Tests for the validate-image CLI command."""

    @patch("src.utils.image_processing.ImageProcessor")
    def test_validate_image_valid(self, mock_processor_class):
        """Test validate-image with a valid image."""
        import tempfile
        from pathlib import Path

        mock_processor = mock_processor_class.return_value

        mock_result = Mock()
        mock_result.is_valid = True
        mock_result.errors = []
        mock_result.warnings = []
        mock_result.width = 1080
        mock_result.height = 1920
        mock_result.aspect_ratio = 0.5625
        mock_result.file_size_mb = 2.5
        mock_result.format = "JPEG"
        mock_processor.validate_image.return_value = mock_result

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "valid.jpg"
            test_file.write_bytes(b"fake image content")

            runner = CliRunner()
            result = runner.invoke(validate, [str(test_file)])

        assert result.exit_code == 0
        assert "Image is valid" in result.output
        assert "1080x1920" in result.output
        assert "JPEG" in result.output

    @patch("src.utils.image_processing.ImageProcessor")
    def test_validate_image_with_warnings(self, mock_processor_class):
        """Test validate-image with warnings (non-ideal aspect ratio)."""
        import tempfile
        from pathlib import Path

        mock_processor = mock_processor_class.return_value

        mock_result = Mock()
        mock_result.is_valid = True
        mock_result.errors = []
        mock_result.warnings = [
            "Non-ideal aspect ratio: 1.78. Instagram prefers 9:16 (0.56)"
        ]
        mock_result.width = 1920
        mock_result.height = 1080
        mock_result.aspect_ratio = 1.78
        mock_result.file_size_mb = 3.1
        mock_result.format = "JPEG"
        mock_processor.validate_image.return_value = mock_result

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "wide.jpg"
            test_file.write_bytes(b"fake image content")

            runner = CliRunner()
            result = runner.invoke(validate, [str(test_file)])

        assert result.exit_code == 0
        assert "Image is valid" in result.output
        assert "Warnings" in result.output
        assert "aspect ratio" in result.output.lower()

    @patch("src.utils.image_processing.ImageProcessor")
    def test_validate_image_with_errors(self, mock_processor_class):
        """Test validate-image with validation errors."""
        import tempfile
        from pathlib import Path

        mock_processor = mock_processor_class.return_value

        mock_result = Mock()
        mock_result.is_valid = False
        mock_result.errors = ["Unsupported format: BMP. Must be JPG, PNG, or GIF"]
        mock_result.warnings = []
        mock_result.width = 800
        mock_result.height = 600
        mock_result.aspect_ratio = 1.33
        mock_result.file_size_mb = 1.0
        mock_result.format = "BMP"
        mock_processor.validate_image.return_value = mock_result

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "invalid.bmp"
            test_file.write_bytes(b"fake image content")

            runner = CliRunner()
            result = runner.invoke(validate, [str(test_file)])

        assert result.exit_code == 0
        assert "has errors" in result.output
        assert "Unsupported format" in result.output

    def test_validate_image_nonexistent_file(self):
        """Test validate-image with non-existent file is rejected by Click."""
        runner = CliRunner()
        result = runner.invoke(validate, ["/nonexistent/image.jpg"])

        assert result.exit_code == 2
        assert "does not exist" in result.output.lower() or "Error" in result.output
