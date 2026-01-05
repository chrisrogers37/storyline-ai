"""Image validation and optimization for Instagram Stories."""
from PIL import Image
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of image validation."""

    is_valid: bool
    warnings: list[str]
    errors: list[str]
    width: int
    height: int
    aspect_ratio: float
    file_size_mb: float
    format: str


class ImageProcessor:
    """Validate and optimize images for Instagram Stories."""

    # Instagram Story specs
    IDEAL_WIDTH = 1080
    IDEAL_HEIGHT = 1920
    IDEAL_ASPECT_RATIO = 9 / 16
    MIN_ASPECT_RATIO = 1.91 / 1  # More horizontal
    MAX_ASPECT_RATIO = 9 / 16  # More vertical
    MAX_FILE_SIZE_MB = 100
    SUPPORTED_FORMATS = {"JPEG", "PNG", "GIF"}

    def validate_image(self, file_path: Path) -> ValidationResult:
        """
        Validate image meets Instagram requirements.

        Returns:
            ValidationResult with validation details
        """
        errors = []
        warnings = []

        try:
            img = Image.open(file_path)
            width, height = img.size
            aspect_ratio = width / height
            file_size_mb = file_path.stat().st_size / (1024 * 1024)

            # Check format
            if img.format not in self.SUPPORTED_FORMATS:
                errors.append(f"Unsupported format: {img.format}. Must be JPG, PNG, or GIF")

            # Check file size
            if file_size_mb > self.MAX_FILE_SIZE_MB:
                errors.append(f"File too large: {file_size_mb:.1f}MB (max {self.MAX_FILE_SIZE_MB}MB)")

            # Check aspect ratio
            if aspect_ratio < self.MAX_ASPECT_RATIO or aspect_ratio > self.MIN_ASPECT_RATIO:
                warnings.append(
                    f"Non-ideal aspect ratio: {aspect_ratio:.2f}. "
                    f"Instagram prefers 9:16 ({self.IDEAL_ASPECT_RATIO:.2f})"
                )

            # Check resolution
            if width < 720 or height < 1280:
                warnings.append(f"Low resolution: {width}x{height}. Minimum recommended: 720x1280")
            elif width != self.IDEAL_WIDTH or height != self.IDEAL_HEIGHT:
                warnings.append(
                    f"Non-optimal resolution: {width}x{height}. Instagram ideal: {self.IDEAL_WIDTH}x{self.IDEAL_HEIGHT}"
                )

            is_valid = len(errors) == 0

            return ValidationResult(
                is_valid=is_valid,
                warnings=warnings,
                errors=errors,
                width=width,
                height=height,
                aspect_ratio=aspect_ratio,
                file_size_mb=file_size_mb,
                format=img.format,
            )

        except Exception as e:
            return ValidationResult(
                is_valid=False,
                warnings=[],
                errors=[f"Failed to open image: {str(e)}"],
                width=0,
                height=0,
                aspect_ratio=0,
                file_size_mb=0,
                format="unknown",
            )

    def optimize_for_instagram(self, file_path: Path, output_path: Optional[Path] = None) -> Path:
        """
        Resize/convert image to Instagram specs.

        Args:
            file_path: Source image path
            output_path: Destination path (default: overwrite source)

        Returns:
            Path to optimized image
        """
        img = Image.open(file_path)
        width, height = img.size
        aspect_ratio = width / height

        # Calculate target dimensions maintaining aspect ratio
        if aspect_ratio > self.IDEAL_ASPECT_RATIO:
            # Image is too wide, crop to 9:16
            target_width = int(height * self.IDEAL_ASPECT_RATIO)
            target_height = height
            left = (width - target_width) // 2
            img = img.crop((left, 0, left + target_width, height))
        else:
            # Image is correct or too tall, resize to 1080x1920
            target_width = self.IDEAL_WIDTH
            target_height = self.IDEAL_HEIGHT
            img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)

        # Convert RGBA to RGB if needed (PNG with transparency)
        if img.mode == "RGBA":
            rgb_img = Image.new("RGB", img.size, (255, 255, 255))
            rgb_img.paste(img, mask=img.split()[3])
            img = rgb_img

        # Save optimized image
        if output_path is None:
            output_path = file_path

        img.save(output_path, "JPEG", quality=95, optimize=True)

        return output_path
