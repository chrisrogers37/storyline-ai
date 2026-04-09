"""Media lifecycle service — orchestrates cross-concern media operations."""

from src.repositories.media_repository import MediaRepository
from src.services.base_service import BaseService
from src.services.integrations.cloud_storage import CloudStorageService
from src.utils.logger import logger


class MediaLifecycleService(BaseService):
    """Orchestrates media item lifecycle operations that span storage + DB.

    Use this service (instead of MediaRepository.delete directly) when
    deleting media items that may have Cloudinary resources attached.
    """

    def __init__(self):
        super().__init__()
        self.media_repo = MediaRepository()
        self.cloud_service = CloudStorageService()

    def delete_media_item(self, media_id: str) -> bool:
        """Delete a media item and its Cloudinary resource if present.

        Cloudinary deletion is best-effort — if it fails, the DB record
        is still deleted. The safety-net cleanup loop handles orphans.

        Args:
            media_id: UUID of the media item to delete.

        Returns:
            True if the DB record was deleted, False if not found.
        """
        with self.track_execution(
            "delete_media_item", input_params={"media_id": media_id}
        ) as run_id:
            media_item = self.media_repo.get_by_id(media_id)
            if not media_item:
                self.set_result_summary(run_id, {"found": False})
                return False

            # Best-effort Cloudinary cleanup
            if media_item.cloud_public_id and self.cloud_service.is_configured():
                try:
                    deleted_cloud = self.cloud_service.delete_media(
                        media_item.cloud_public_id
                    )
                    if not deleted_cloud:
                        logger.warning(
                            f"Cloudinary delete returned false for "
                            f"{media_item.cloud_public_id}"
                        )
                except Exception as e:
                    logger.warning(
                        f"Failed to delete Cloudinary resource "
                        f"{media_item.cloud_public_id}: {e}"
                    )

            deleted = self.media_repo.delete(media_id)
            self.set_result_summary(run_id, {"found": True, "deleted": deleted})
            return deleted
