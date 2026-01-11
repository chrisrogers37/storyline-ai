"""Media ingestion service - scan filesystem and index media files."""
from pathlib import Path
from typing import Optional, Dict
import mimetypes

from src.services.base_service import BaseService
from src.repositories.media_repository import MediaRepository
from src.utils.file_hash import calculate_file_hash
from src.utils.image_processing import ImageProcessor
from src.utils.logger import logger


class MediaIngestionService(BaseService):
    """Scan filesystem and index media files."""

    SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".mp4", ".mov"}

    def __init__(self):
        super().__init__()
        self.media_repo = MediaRepository()
        self.image_processor = ImageProcessor()

    def scan_directory(
        self,
        directory_path: str,
        user_id: Optional[str] = None,
        recursive: bool = True,
        extract_category: bool = True,
    ) -> Dict[str, int]:
        """
        Scan a directory and index all media files.

        Args:
            directory_path: Path to directory to scan (used as base for category extraction)
            user_id: User who triggered the scan
            recursive: Whether to scan subdirectories
            extract_category: Whether to extract category from immediate parent folder

        Returns:
            Dict with counts: {indexed: 10, skipped: 2, errors: 1, categories: ["memes", "merch"]}
        """
        with self.track_execution(
            method_name="scan_directory",
            user_id=user_id,
            triggered_by="cli" if user_id else "system",
            input_params={"directory_path": directory_path, "recursive": recursive},
        ) as run_id:
            indexed_count = 0
            skipped_count = 0
            error_count = 0
            categories_found = set()

            base_path = Path(directory_path)

            if not base_path.exists():
                raise ValueError(f"Directory does not exist: {directory_path}")

            if not base_path.is_dir():
                raise ValueError(f"Path is not a directory: {directory_path}")

            pattern = "**/*" if recursive else "*"

            for file_path in base_path.glob(pattern):
                if not file_path.is_file():
                    continue

                if file_path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
                    skipped_count += 1
                    continue

                try:
                    # Extract category from folder structure
                    category = None
                    if extract_category:
                        category = self._extract_category(file_path, base_path)
                        if category:
                            categories_found.add(category)

                    # Index the file
                    self._index_file(file_path, user_id, category=category)
                    indexed_count += 1

                except Exception as e:
                    logger.error(f"Failed to index {file_path}: {e}")
                    error_count += 1

            # Record results
            result_summary = {
                "indexed": indexed_count,
                "skipped": skipped_count,
                "errors": error_count,
                "total_files": indexed_count + skipped_count + error_count,
                "categories": sorted(categories_found),
            }

            self.set_result_summary(run_id, result_summary)

            return result_summary

    def _extract_category(self, file_path: Path, base_path: Path) -> Optional[str]:
        """
        Extract category from the folder structure.

        The category is the immediate subdirectory of base_path that contains the file.
        E.g., if base_path is /media/stories/ and file is /media/stories/memes/image.jpg,
        the category is "memes".

        Args:
            file_path: Full path to the file
            base_path: Base directory being scanned

        Returns:
            Category name or None if file is directly in base_path
        """
        try:
            relative = file_path.relative_to(base_path)
            parts = relative.parts

            # If file is directly in base_path, no category
            if len(parts) <= 1:
                return None

            # First part of relative path is the category folder
            return parts[0]

        except ValueError:
            # File is not under base_path
            return None

    def _index_file(
        self, file_path: Path, user_id: Optional[str], category: Optional[str] = None
    ):
        """Index a single file.

        Args:
            file_path: Path to the file
            user_id: User who triggered the indexing
            category: Category extracted from folder structure
        """
        # Check if already indexed
        existing = self.media_repo.get_by_path(str(file_path))
        if existing:
            logger.debug(f"Skipping already indexed file: {file_path}")
            return

        # Calculate file hash
        file_hash = calculate_file_hash(file_path)

        # Check for duplicate content
        duplicates = self.media_repo.get_by_hash(file_hash)
        if duplicates:
            logger.warning(f"Duplicate content detected: {file_path.name} (hash: {file_hash[:8]}...)")

        # Validate image (if it's an image)
        if file_path.suffix.lower() in {".jpg", ".jpeg", ".png", ".gif"}:
            validation = self.image_processor.validate_image(file_path)

            if not validation.is_valid:
                logger.error(f"Invalid image {file_path}: {validation.errors}")
                raise ValueError(f"Image validation failed: {validation.errors}")

            if validation.warnings:
                logger.warning(f"Image {file_path} has warnings: {validation.warnings}")

        # Get mime type
        mime_type, _ = mimetypes.guess_type(str(file_path))

        # Create media item
        self.media_repo.create(
            file_path=str(file_path),
            file_name=file_path.name,
            file_hash=file_hash,
            file_size_bytes=file_path.stat().st_size,
            mime_type=mime_type,
            category=category,
            indexed_by_user_id=user_id,
        )

        category_info = f" [{category}]" if category else ""
        logger.info(f"Indexed: {file_path.name}{category_info}")

    def detect_duplicates(self) -> list[tuple]:
        """
        Find all duplicate media items (same content, different paths).

        Returns:
            List of tuples (file_hash, count, paths)
        """
        with self.track_execution("detect_duplicates") as run_id:
            duplicates = self.media_repo.get_duplicates()

            self.set_result_summary(run_id, {"duplicates_found": len(duplicates)})

            return duplicates
