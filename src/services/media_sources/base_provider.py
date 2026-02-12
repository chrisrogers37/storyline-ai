"""Abstract base class for media source providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class MediaFileInfo:
    """Metadata for a media file from any provider.

    Attributes:
        identifier: Provider-specific unique ID (file_path for local, file_id for Drive)
        name: Display filename (e.g., "image.jpg")
        size_bytes: File size in bytes
        mime_type: MIME type string (e.g., "image/jpeg")
        folder: Category/folder name (e.g., "memes"), or None if at root
        modified_at: Last modification timestamp, or None if unavailable
        hash: Provider-side content hash if available, or None
    """

    identifier: str
    name: str
    size_bytes: int
    mime_type: str
    folder: Optional[str] = None
    modified_at: Optional[datetime] = None
    hash: Optional[str] = None


class MediaSourceProvider(ABC):
    """Abstract interface for media source providers.

    All media access in the system should go through a provider instance.
    This enables swapping local filesystem for Google Drive, S3, etc.

    Providers are lightweight objects -- they do NOT extend BaseService and
    are not tracked in service_runs. They are used by services that do have
    tracking (e.g., MediaIngestionService, PostingService).
    """

    @abstractmethod
    def list_files(self, folder: Optional[str] = None) -> list[MediaFileInfo]:
        """List available media files.

        Args:
            folder: Optional folder/category name to filter by.
                    If None, lists all files across all folders.

        Returns:
            List of MediaFileInfo objects for all matching files.
        """

    @abstractmethod
    def download_file(self, file_identifier: str) -> bytes:
        """Download file content as bytes.

        Args:
            file_identifier: Provider-specific unique ID for the file.

        Returns:
            Raw file bytes.

        Raises:
            FileNotFoundError: If file_identifier does not exist.
        """

    @abstractmethod
    def get_file_info(self, file_identifier: str) -> Optional[MediaFileInfo]:
        """Get file metadata without downloading content.

        Args:
            file_identifier: Provider-specific unique ID for the file.

        Returns:
            MediaFileInfo if file exists, None otherwise.
        """

    @abstractmethod
    def file_exists(self, file_identifier: str) -> bool:
        """Check whether a file exists.

        Args:
            file_identifier: Provider-specific unique ID for the file.

        Returns:
            True if the file exists and is accessible.
        """

    @abstractmethod
    def get_folders(self) -> list[str]:
        """List top-level folders (categories).

        Returns:
            List of folder/category names.
        """

    @abstractmethod
    def is_configured(self) -> bool:
        """Check whether this provider has valid configuration.

        Returns:
            True if the provider can operate (paths exist, credentials valid, etc.).
        """

    @abstractmethod
    def calculate_file_hash(self, file_identifier: str) -> str:
        """Calculate content hash for deduplication.

        Args:
            file_identifier: Provider-specific unique ID for the file.

        Returns:
            Hex string of SHA256 hash.

        Raises:
            FileNotFoundError: If file_identifier does not exist.
        """
