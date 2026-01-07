"""Tests for image_processing utility."""
import pytest
from pathlib import Path
from PIL import Image
import tempfile
import os

from src.utils.image_processing import ImageProcessor, ValidationResult


@pytest.mark.unit
class TestImageProcessor:
    """Test suite for ImageProcessor."""

    @pytest.fixture
    def processor(self):
        """Create ImageProcessor instance."""
        return ImageProcessor()

    def create_test_image(self, width, height, format="JPEG", mode="RGB"):
        """Helper to create a test image."""
        temp_file = tempfile.NamedTemporaryFile(
            delete=False, suffix=f".{format.lower()}"
        )
        temp_file.close()

        img = Image.new(mode, (width, height), color="red")
        img.save(temp_file.name, format=format)

        return Path(temp_file.name)

    def test_validate_image_valid(self, processor):
        """Test validating a valid Instagram Story image."""
        # Create 9:16 aspect ratio image (1080x1920)
        image_path = self.create_test_image(1080, 1920)

        try:
            result = processor.validate_image(image_path)

            assert isinstance(result, ValidationResult)
            assert result.is_valid is True
            assert len(result.errors) == 0
            assert result.width == 1080
            assert result.height == 1920
            assert result.format == "JPEG"
        finally:
            os.unlink(image_path)

    def test_validate_image_wrong_aspect_ratio(self, processor):
        """Test validation warns with aspect ratio outside acceptable range."""
        # Create 2:1 image (wider than acceptable 1.91:1 max)
        image_path = self.create_test_image(2000, 1000)

        try:
            result = processor.validate_image(image_path)

            # Wrong aspect ratio is a warning, not an error
            assert result.is_valid is True  # Still valid, just not ideal
            assert any("aspect ratio" in w.lower() for w in result.warnings)
        finally:
            os.unlink(image_path)

    def test_validate_image_low_resolution(self, processor):
        """Test validation warns with low resolution."""
        # Create small 9:16 image
        image_path = self.create_test_image(540, 960)

        try:
            result = processor.validate_image(image_path)

            # Low resolution is a warning, not an error
            assert result.is_valid is True  # Still valid, just not ideal
            assert any("resolution" in w.lower() for w in result.warnings)
        finally:
            os.unlink(image_path)

    def test_validate_image_file_not_found(self, processor):
        """Test validation fails with non-existent file."""
        result = processor.validate_image(Path("/nonexistent/image.jpg"))

        assert result.is_valid is False
        assert any("failed to open" in e.lower() for e in result.errors)

    def test_validate_image_returns_dimensions(self, processor):
        """Test validation result includes dimensions."""
        image_path = self.create_test_image(800, 1200)

        try:
            result = processor.validate_image(image_path)

            assert result.width == 800
            assert result.height == 1200
            assert abs(result.aspect_ratio - (800 / 1200)) < 0.01
        finally:
            os.unlink(image_path)

    def test_validate_image_returns_file_size(self, processor):
        """Test validation result includes file size."""
        image_path = self.create_test_image(1080, 1920)

        try:
            result = processor.validate_image(image_path)

            assert result.file_size_mb > 0
        finally:
            os.unlink(image_path)

    def test_optimize_for_instagram_resizes(self, processor):
        """Test optimizing an oversized image."""
        # Create oversized image
        image_path = self.create_test_image(2160, 3840)

        try:
            output_path = image_path.parent / "optimized.jpg"
            result_path = processor.optimize_for_instagram(image_path, output_path)

            assert result_path.exists()

            # Check optimized image properties
            with Image.open(result_path) as img:
                assert img.width == 1080
                assert img.height == 1920

            os.unlink(output_path)
        finally:
            os.unlink(image_path)

    def test_optimize_for_instagram_crops_wide_image(self, processor):
        """Test optimization crops wide images to correct aspect ratio."""
        # Create wide 16:9 image
        image_path = self.create_test_image(1920, 1080)

        try:
            output_path = image_path.parent / "optimized_crop.jpg"
            result_path = processor.optimize_for_instagram(image_path, output_path)

            assert result_path.exists()

            # Should be cropped to 9:16
            with Image.open(result_path) as img:
                aspect_ratio = img.width / img.height
                expected_ratio = 9 / 16
                assert abs(aspect_ratio - expected_ratio) < 0.01

            os.unlink(output_path)
        finally:
            os.unlink(image_path)

    def test_optimize_for_instagram_png_to_jpg(self, processor):
        """Test converting PNG to JPG."""
        # Create PNG image
        image_path = self.create_test_image(1080, 1920, format="PNG")

        try:
            output_path = image_path.parent / "converted.jpg"
            result_path = processor.optimize_for_instagram(image_path, output_path)

            assert result_path.exists()
            assert result_path.suffix.lower() == ".jpg"

            os.unlink(output_path)
        finally:
            os.unlink(image_path)

    def test_optimize_for_instagram_rgba_to_rgb(self, processor):
        """Test converting RGBA to RGB."""
        # Create RGBA image (with transparency)
        image_path = self.create_test_image(1080, 1920, format="PNG", mode="RGBA")

        try:
            output_path = image_path.parent / "rgb_converted.jpg"
            result_path = processor.optimize_for_instagram(image_path, output_path)

            assert result_path.exists()

            # JPG should be RGB
            with Image.open(result_path) as img:
                assert img.mode == "RGB"

            os.unlink(output_path)
        finally:
            os.unlink(image_path)

    def test_optimize_in_place(self, processor):
        """Test optimization can overwrite source file."""
        image_path = self.create_test_image(2160, 3840)

        try:
            # Optimize in place (no output_path)
            result_path = processor.optimize_for_instagram(image_path)

            assert result_path == image_path
            assert result_path.exists()

            with Image.open(result_path) as img:
                assert img.width == 1080
                assert img.height == 1920
        finally:
            if image_path.exists():
                os.unlink(image_path)

    def test_validation_result_dataclass(self):
        """Test ValidationResult dataclass properties."""
        result = ValidationResult(
            is_valid=True,
            warnings=["warning1"],
            errors=[],
            width=1080,
            height=1920,
            aspect_ratio=0.5625,
            file_size_mb=1.5,
            format="JPEG",
        )

        assert result.is_valid is True
        assert len(result.warnings) == 1
        assert result.width == 1080
        assert result.height == 1920

    def test_processor_constants(self):
        """Test ImageProcessor has expected constants."""
        assert ImageProcessor.IDEAL_WIDTH == 1080
        assert ImageProcessor.IDEAL_HEIGHT == 1920
        assert ImageProcessor.MAX_FILE_SIZE_MB == 100
        assert "JPEG" in ImageProcessor.SUPPORTED_FORMATS
        assert "PNG" in ImageProcessor.SUPPORTED_FORMATS
