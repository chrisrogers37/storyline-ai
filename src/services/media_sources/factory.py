"""Factory for creating media source provider instances."""

from src.config.settings import settings
from src.services.media_sources.base_provider import MediaSourceProvider
from src.services.media_sources.local_provider import LocalMediaProvider
from src.utils.logger import logger


class MediaSourceFactory:
    """Factory for creating MediaSourceProvider instances.

    Supports:
        - 'local': LocalMediaProvider (filesystem-based)
        - 'google_drive': GoogleDriveProvider (Google Drive API)
    """

    _providers: dict[str, type[MediaSourceProvider]] = {
        "local": LocalMediaProvider,
    }

    _google_drive_registered: bool = False

    @classmethod
    def _ensure_google_drive_registered(cls) -> None:
        """Lazily register GoogleDriveProvider to avoid import errors
        when google-api-python-client is not installed."""
        if cls._google_drive_registered:
            return
        try:
            from src.services.media_sources.google_drive_provider import (
                GoogleDriveProvider,
            )

            cls._providers["google_drive"] = GoogleDriveProvider
            cls._google_drive_registered = True
        except ImportError:
            logger.debug(
                "google-api-python-client not installed, "
                "Google Drive provider unavailable"
            )

    @classmethod
    def create(cls, source_type: str, **kwargs) -> MediaSourceProvider:
        """Create a provider instance for the given source type.

        Args:
            source_type: 'local' or 'google_drive'
            **kwargs: Provider-specific config.
                local: 'base_path' (defaults to settings.MEDIA_DIR)
                google_drive: 'root_folder_id', plus 'service_account_info'
                    or 'oauth_credentials'. If no auth provided, loads from DB.

        Raises:
            ValueError: If source_type is not supported.
        """
        cls._ensure_google_drive_registered()

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

        if source_type == "google_drive":
            root_folder_id = kwargs.get("root_folder_id")
            service_account_info = kwargs.get("service_account_info")
            oauth_credentials = kwargs.get("oauth_credentials")
            telegram_chat_id = kwargs.get("telegram_chat_id")

            if not service_account_info and not oauth_credentials:
                from src.services.integrations.google_drive import (
                    GoogleDriveService,
                )

                gdrive_service = GoogleDriveService()

                # Try per-tenant user OAuth first, then service account fallback
                if telegram_chat_id:
                    try:
                        return gdrive_service.get_provider_for_chat(
                            telegram_chat_id, root_folder_id
                        )
                    except Exception:
                        logger.debug(
                            "No user OAuth for chat %s, falling back to service account",
                            telegram_chat_id,
                        )

                return gdrive_service.get_provider(root_folder_id)

            return provider_class(
                root_folder_id=root_folder_id,
                service_account_info=service_account_info,
                oauth_credentials=oauth_credentials,
            )

        return provider_class(**kwargs)

    @classmethod
    def get_provider_for_media_item(cls, media_item) -> MediaSourceProvider:
        """Get the appropriate provider for an existing media item.
        Falls back to 'local' if source_type is not set."""
        source_type = media_item.source_type or "local"
        return cls.create(source_type)

    @classmethod
    def register_provider(
        cls, source_type: str, provider_class: type[MediaSourceProvider]
    ) -> None:
        """Register a new provider type."""
        cls._providers[source_type] = provider_class
        logger.info(f"Registered media source provider: {source_type}")
