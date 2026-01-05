"""Tests for image_processing utility."""
import pytest
from pathlib import Path
from PIL import Image
import tempfile
import os

from src.utils.image_processing import ImageProcessor


@pytest.mark.unit
class TestImageProcessor:
    """Test suite for ImageProcessor."""

    def create_test_image(self, width, height, format="JPEG", mode="RGB"):
        """Helper to create a test image."""
        temp_file = tempfile.NamedTemporaryFile(
            delete=False, suffix=f".{format.lower()}"
        )
        temp_file.close()

        img = Image.new(mode, (width, height), color="red")
        img.save(temp_file.name, format=format)

        return Path(temp_file.name)

    def test_validate_instagram_story_valid_image(self):
        """Test validating a valid Instagram Story image."""
        # Create 9:16 aspect ratio image (1080x1920)
        image_path = self.create_test_image(1080, 1920)

        try:
            is_valid, errors = ImageProcessor.validate_instagram_story(image_path)

            assert is_valid is True
            assert len(errors) == 0
        finally:
            os.unlink(image_path)

    def test_validate_instagram_story_wrong_aspect_ratio(self):
        """Test validation fails with wrong aspect ratio."""
        # Create 16:9 image (wrong orientation)
        image_path = self.create_test_image(1920, 1080)

        try:
            is_valid, errors = ImageProcessor.validate_instagram_story(image_path)

            assert is_valid is False
            assert any("aspect ratio" in error.lower() for error in errors)
        finally:
            os.unlink(image_path)

    def test_validate_instagram_story_low_resolution(self):
        """Test validation fails with low resolution."""
        # Create small 9:16 image
        image_path = self.create_test_image(540, 960)

        try:
            is_valid, errors = ImageProcessor.validate_instagram_story(image_path)

            assert is_valid is False
            assert any("resolution" in error.lower() for error in errors)
        finally:
            os.unlink(image_path)

    def test_validate_instagram_story_file_not_found(self):
        """Test validation fails with non-existent file."""
        is_valid, errors = ImageProcessor.validate_instagram_story(
            Path("/nonexistent/image.jpg")
        )

        assert is_valid is False
        assert any("not found" in error.lower() for error in errors)

    def test_optimize_for_instagram_valid_image(self):
        """Test optimizing an image for Instagram."""
        # Create oversized image
        image_path = self.create_test_image(2160, 3840)

        try:
            output_path = image_path.parent / "optimized.jpg"
            result_path = ImageProcessor.optimize_for_instagram(
                image_path, output_path
            )

            assert result_path.exists()

            # Check optimized image properties
            with Image.open(result_path) as img:
                assert img.width == 1080
                assert img.height == 1920

            os.unlink(output_path)
        finally:
            os.unlink(image_path)

    def test_optimize_for_instagram_wrong_aspect_ratio(self):
        """Test optimization crops to correct aspect ratio."""
        # Create square image
        image_path = self.create_test_image(1080, 1080)

        try:
            output_path = image_path.parent / "optimized_crop.jpg"
            result_path = ImageProcessor.optimize_for_instagram(
                image_path, output_path
            )

            assert result_path.exists()

            # Should be cropped to 9:16
            with Image.open(result_path) as img:
                aspect_ratio = img.width / img.height
                expected_ratio = 9 / 16
                assert abs(aspect_ratio - expected_ratio) < 0.01

            os.unlink(output_path)
        finally:
            os.unlink(image_path)

    def test_optimize_for_instagram_png_to_jpg(self):
        """Test converting PNG to JPG."""
        # Create PNG image
        image_path = self.create_test_image(1080, 1920, format="PNG")

        try:
            output_path = image_path.parent / "converted.jpg"
            result_path = ImageProcessor.optimize_for_instagram(
                image_path, output_path
            )

            assert result_path.exists()
            assert result_path.suffix.lower() == ".jpg"

            os.unlink(output_path)
        finally:
            os.unlink(image_path)

    def test_optimize_for_instagram_rgba_to_rgb(self):
        """Test converting RGBA to RGB."""
        # Create RGBA image (with transparency)
        image_path = self.create_test_image(1080, 1920, format="PNG", mode="RGBA")

        try:
            output_path = image_path.parent / "rgb_converted.jpg"
            result_path = ImageProcessor.optimize_for_instagram(
                image_path, output_path
            )

            assert result_path.exists()

            # JPG should be RGB
            with Image.open(result_path) as img:
                assert img.mode == "RGB"

            os.unlink(output_path)
        finally:
            os.unlink(image_path)

    def test_get_image_info(self):
        """Test getting image information."""
        image_path = self.create_test_image(1080, 1920)

        try:
            info = ImageProcessor.get_image_info(image_path)

            assert info["width"] == 1080
            assert info["height"] == 1920
            assert info["format"] == "JPEG"
            assert info["mode"] == "RGB"
            assert "file_size_bytes" in info
        finally:
            os.unlink(image_path)

    def test_get_image_info_file_not_found(self):
        """Test get_image_info with non-existent file."""
        info = ImageProcessor.get_image_info(Path("/nonexistent/image.jpg"))

        assert info is None

    def test_calculate_aspect_ratio(self):
        """Test aspect ratio calculation."""
        ratio = ImageProcessor.calculate_aspect_ratio(1080, 1920)

        expected_ratio = 9 / 16
        assert abs(ratio - expected_ratio) < 0.01

    def test_calculate_aspect_ratio_zero_height(self):
        """Test aspect ratio calculation with zero height."""
        ratio = ImageProcessor.calculate_aspect_ratio(1080, 0)

        assert ratio == 0
