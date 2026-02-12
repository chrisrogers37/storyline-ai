"""Factory for creating media source provider instances."""

from src.config.settings import settings
from src.services.media_sources.base_provider import MediaSourceProvider
from src.services.media_sources.local_provider import LocalMediaProvider
from src.utils.logger import logger


class MediaSourceFactory:
    """Factory for creating MediaSourceProvider instances.

    Currently supports:
        - 'local': LocalMediaProvider (filesystem-based)

    Future phases will add:
        - 'google_drive': GoogleDriveProvider
        - 's3': S3Provider
    """

    _providers: dict[str, type[MediaSourceProvider]] = {
        "local": LocalMediaProvider,
    }

    @classmethod
    def create(cls, source_type: str, **kwargs) -> MediaSourceProvider:
        """Create a provider instance for the given source type.

        Args:
            source_type: Provider type string (e.g., 'local', 'google_drive').
            **kwargs: Provider-specific configuration. For 'local', accepts
                'base_path' (defaults to settings.MEDIA_DIR).

        Returns:
            Configured MediaSourceProvider instance.

        Raises:
            ValueError: If source_type is not supported.
        """
        if source_type not in cls._providers:
            supported = ", ".join(sorted(cls._providers.keys()))
            raise ValueError(
                f"Unsupported media source type: '{source_type}'. "
                f"Supported types: {supported}"
            )

        provider_class = cls._providers[source_type]

        if source_type == "local":
            base_path = kwargs.get("base_path", settings.MEDIA_DIR)
            return provider_class(base_path=base_path)

        return provider_class(**kwargs)

    @classmethod
    def get_provider_for_media_item(cls, media_item) -> MediaSourceProvider:
        """Get the appropriate provider for an existing media item.

        Uses the media_item's source_type to create the correct provider.
        Falls back to 'local' if source_type is not set.

        Args:
            media_item: A MediaItem model instance.

        Returns:
            Configured MediaSourceProvider instance.
        """
        return cls.create(media_item.source_type or "local")

    @classmethod
    def register_provider(
        cls, source_type: str, provider_class: type[MediaSourceProvider]
    ) -> None:
        """Register a new provider type (used by future phases)."""
        cls._providers[source_type] = provider_class
        logger.info(f"Registered media source provider: {source_type}")
