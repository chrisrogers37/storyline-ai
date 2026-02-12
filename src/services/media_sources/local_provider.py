"""Local filesystem media source provider."""

import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.services.media_sources.base_provider import MediaFileInfo, MediaSourceProvider
from src.utils.file_hash import calculate_file_hash
from src.utils.logger import logger


class LocalMediaProvider(MediaSourceProvider):
    """Media source provider for local filesystem.

    Wraps standard filesystem operations behind the MediaSourceProvider
    interface. The base_path is the root directory containing media files,
    and subfolders are treated as categories.

    Args:
        base_path: Root directory for media files (e.g., "/home/pi/media")
        supported_extensions: Set of lowercase file extensions to include.
            Defaults to the standard set used by MediaIngestionService.
    """

    DEFAULT_SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".mp4", ".mov"}

    def __init__(
        self,
        base_path: str,
        supported_extensions: Optional[set[str]] = None,
    ):
        self.base_path = Path(base_path)
        self.supported_extensions = (
            supported_extensions or self.DEFAULT_SUPPORTED_EXTENSIONS
        )

    def list_files(self, folder: Optional[str] = None) -> list[MediaFileInfo]:
        """List media files in the base directory or a specific subfolder."""
        if not self.base_path.exists():
            logger.warning(f"Base path does not exist: {self.base_path}")
            return []

        if folder:
            search_path = self.base_path / folder
            if not search_path.exists():
                logger.warning(f"Folder does not exist: {search_path}")
                return []
        else:
            search_path = self.base_path

        results = []
        for file_path in search_path.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in self.supported_extensions:
                continue

            info = self._build_file_info(file_path)
            if info:
                results.append(info)

        return results

    def download_file(self, file_identifier: str) -> bytes:
        """Read file bytes from local filesystem."""
        path = Path(file_identifier)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_identifier}")
        return path.read_bytes()

    def get_file_info(self, file_identifier: str) -> Optional[MediaFileInfo]:
        """Get metadata for a local file."""
        path = Path(file_identifier)
        if not path.exists() or not path.is_file():
            return None
        return self._build_file_info(path)

    def file_exists(self, file_identifier: str) -> bool:
        """Check if a local file exists."""
        return Path(file_identifier).is_file()

    def get_folders(self) -> list[str]:
        """List immediate subdirectories of base_path (categories)."""
        if not self.base_path.exists():
            return []

        folders = [
            d.name
            for d in sorted(self.base_path.iterdir())
            if d.is_dir() and not d.name.startswith(".")
        ]
        return folders

    def is_configured(self) -> bool:
        """Check if the base path exists and is a directory."""
        return self.base_path.exists() and self.base_path.is_dir()

    def calculate_file_hash(self, file_identifier: str) -> str:
        """Calculate SHA256 hash of local file content."""
        path = Path(file_identifier)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_identifier}")
        return calculate_file_hash(path)

    def _build_file_info(self, file_path: Path) -> Optional[MediaFileInfo]:
        """Build a MediaFileInfo from a local file path."""
        try:
            stat = file_path.stat()
            mime_type, _ = mimetypes.guess_type(str(file_path))

            # Extract folder (category) relative to base_path
            folder = None
            try:
                relative = file_path.relative_to(self.base_path)
                parts = relative.parts
                if len(parts) > 1:
                    folder = parts[0]
            except ValueError:
                pass

            return MediaFileInfo(
                identifier=str(file_path),
                name=file_path.name,
                size_bytes=stat.st_size,
                mime_type=mime_type or "application/octet-stream",
                folder=folder,
                modified_at=datetime.fromtimestamp(stat.st_mtime),
            )
        except OSError as e:
            logger.warning(f"Could not stat file {file_path}: {e}")
            return None
