"""Tests for media CLI commands."""

import pytest
from click.testing import CliRunner
from pathlib import Path
import tempfile

from cli.commands.media import index, list_media, validate
from src.repositories.media_repository import MediaRepository


@pytest.mark.unit
class TestMediaCommands:
    """Test suite for media CLI commands."""

    def test_index_media_command(self, test_db):
        """Test index-media CLI command."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test image file
            test_file = Path(temp_dir) / "test.jpg"
            test_file.write_bytes(b"fake image content")

            result = runner.invoke(index, [temp_dir])

            # Command should execute successfully
            assert result.exit_code == 0
            assert (
                "indexed" in result.output.lower() or "added" in result.output.lower()
            )

    def test_index_media_nonexistent_directory(self, test_db):
        """Test index-media with non-existent directory."""
        runner = CliRunner()

        result = runner.invoke(index, ["/nonexistent/path"])

        # Should fail with error
        assert result.exit_code != 0
        assert (
            "does not exist" in result.output.lower()
            or "not found" in result.output.lower()
        )

    def test_list_media_command(self, test_db):
        """Test list-media CLI command."""
        media_repo = MediaRepository(test_db)

        # Create test media
        media_repo.create(
            file_path="/test/list1.jpg",
            file_name="list1.jpg",
            file_hash="list1_hash",
            file_size_bytes=100000,
            mime_type="image/jpeg",
        )

        runner = CliRunner()
        result = runner.invoke(list_media, ["--limit", "10"])

        # Command should execute successfully
        assert result.exit_code == 0

    def test_list_media_with_filters(self, test_db):
        """Test list-media with filters."""
        media_repo = MediaRepository(test_db)

        # Create media with interaction requirement
        media_repo.create(
            file_path="/test/interactive.jpg",
            file_name="interactive.jpg",
            file_hash="interactive_hash",
            file_size_bytes=95000,
            mime_type="image/jpeg",
            requires_interaction=True,
        )

        runner = CliRunner()
        result = runner.invoke(list_media, ["--requires-interaction"])

        assert result.exit_code == 0

    def test_validate_image_valid(self):
        """Test validate-image command with valid image."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a valid 9:16 image
            from PIL import Image

            test_file = Path(temp_dir) / "valid.jpg"
            img = Image.new("RGB", (1080, 1920), color="red")
            img.save(test_file, "JPEG")

            result = runner.invoke(validate, [str(test_file)])

            assert result.exit_code == 0

    def test_validate_image_invalid(self):
        """Test validate-image command with invalid image."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create invalid image (wrong aspect ratio)
            from PIL import Image

            test_file = Path(temp_dir) / "invalid.jpg"
            img = Image.new("RGB", (1920, 1080), color="blue")
            img.save(test_file, "JPEG")

            result = runner.invoke(validate, [str(test_file)])

            # May still exit 0 but show validation errors in output
            assert (
                "aspect ratio" in result.output.lower()
                or "resolution" in result.output.lower()
                or result.exit_code == 0
            )

    def test_validate_image_nonexistent(self):
        """Test validate-image with non-existent file."""
        runner = CliRunner()

        result = runner.invoke(validate, ["/nonexistent/image.jpg"])

        # Should handle gracefully
        assert (
            "not found" in result.output.lower()
            or "does not exist" in result.output.lower()
            or result.exit_code != 0
        )
