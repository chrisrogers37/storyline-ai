"""Cloud storage service for temporary media uploads (Cloudinary)."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import cloudinary
import cloudinary.uploader
import cloudinary.api

from src.services.base_service import BaseService
from src.config.settings import settings
from src.exceptions import MediaUploadError
from src.utils.logger import logger


class CloudStorageService(BaseService):
    """
    Abstraction for cloud storage operations (currently Cloudinary).

    Instagram API requires publicly accessible URLs for media. This service
    handles uploading local media to cloud storage and managing the lifecycle.

    Usage:
        service = CloudStorageService()

        # Upload media
        result = service.upload_media("/path/to/image.jpg")
        print(result["url"])  # Public URL for Instagram API

        # Delete after posting
        service.delete_media(result["public_id"])
    """

    def __init__(self):
        super().__init__()
        self._configure_cloudinary()

    def _configure_cloudinary(self) -> None:
        """Configure Cloudinary SDK with credentials from settings."""
        if not all(
            [
                settings.CLOUDINARY_CLOUD_NAME,
                settings.CLOUDINARY_API_KEY,
                settings.CLOUDINARY_API_SECRET,
            ]
        ):
            logger.warning("Cloudinary credentials not configured")
            return

        cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
            secure=True,
        )

    def upload_media(
        self,
        file_path: str,
        folder: str = "storyline",
        public_id: Optional[str] = None,
    ) -> dict:
        """
        Upload media file to Cloudinary.

        Args:
            file_path: Local path to media file
            folder: Cloudinary folder/prefix for organization
            public_id: Optional custom identifier (auto-generated if not provided)

        Returns:
            dict with:
                - url: Public URL for the uploaded media
                - public_id: Cloudinary identifier for deletion
                - uploaded_at: When the upload occurred
                - expires_at: When the URL should be considered expired
                - size_bytes: File size in bytes
                - format: File format (jpg, png, etc.)

        Raises:
            MediaUploadError: If upload fails
        """
        with self.track_execution(
            method_name="upload_media",
            input_params={"file_path": file_path, "folder": folder},
        ) as run_id:
            path = self._validate_file_path(file_path)

            try:
                upload_options = self._build_upload_options(path, folder, public_id)

                logger.info(f"Uploading {path.name} to Cloudinary ({folder}/)")

                result = cloudinary.uploader.upload(str(path), **upload_options)

                uploaded_at = datetime.utcnow()
                expires_at = uploaded_at + timedelta(
                    hours=settings.CLOUD_UPLOAD_RETENTION_HOURS
                )

                upload_result = {
                    "url": result["secure_url"],
                    "public_id": result["public_id"],
                    "uploaded_at": uploaded_at,
                    "expires_at": expires_at,
                    "size_bytes": result.get("bytes", 0),
                    "format": result.get("format", ""),
                    "width": result.get("width"),
                    "height": result.get("height"),
                }

                logger.info(
                    f"Successfully uploaded {path.name} to Cloudinary: {result['public_id']}"
                )

                self.set_result_summary(
                    run_id,
                    {
                        "success": True,
                        "public_id": result["public_id"],
                        "size_bytes": result.get("bytes", 0),
                    },
                )

                return upload_result

            except cloudinary.exceptions.Error as e:
                logger.error(f"Cloudinary upload failed: {e}")
                raise MediaUploadError(
                    f"Cloudinary upload failed: {e}",
                    file_path=file_path,
                    provider="cloudinary",
                )

    def _validate_file_path(self, file_path: str) -> Path:
        """Validate file path exists and is a file.

        Returns:
            Path object for the validated file

        Raises:
            MediaUploadError: If path doesn't exist or isn't a file
        """
        path = Path(file_path)

        if not path.exists():
            raise MediaUploadError(
                f"File not found: {file_path}",
                file_path=file_path,
                provider="cloudinary",
            )

        if not path.is_file():
            raise MediaUploadError(
                f"Path is not a file: {file_path}",
                file_path=file_path,
                provider="cloudinary",
            )

        return path

    def _build_upload_options(
        self, path: Path, folder: str, public_id: Optional[str] = None
    ) -> dict:
        """Build Cloudinary upload options dict.

        Returns:
            Dict of upload options for cloudinary.uploader.upload()
        """
        resource_type = self._get_resource_type(path)

        options = {
            "folder": folder,
            "resource_type": resource_type,
            "overwrite": True,
        }

        if public_id:
            options["public_id"] = public_id

        return options

    def delete_media(self, public_id: str) -> bool:
        """
        Delete uploaded media from Cloudinary.

        Args:
            public_id: Cloudinary public_id from upload result

        Returns:
            True if deleted successfully, False otherwise
        """
        with self.track_execution(
            method_name="delete_media",
            input_params={"public_id": public_id},
        ) as run_id:
            try:
                result = cloudinary.uploader.destroy(public_id)
                success = result.get("result") == "ok"

                if success:
                    logger.info(f"Deleted media from Cloudinary: {public_id}")
                else:
                    logger.warning(
                        f"Cloudinary delete returned unexpected result for {public_id}: {result}"
                    )

                self.set_result_summary(run_id, {"success": success, "result": result})
                return success

            except cloudinary.exceptions.Error as e:
                logger.error(f"Failed to delete from Cloudinary: {e}")
                self.set_result_summary(run_id, {"success": False, "error": str(e)})
                return False

    def get_url(self, public_id: str) -> Optional[str]:
        """
        Get the URL for an existing Cloudinary upload.

        Args:
            public_id: Cloudinary public_id

        Returns:
            Public URL or None if not found
        """
        try:
            result = cloudinary.api.resource(public_id)
            return result.get("secure_url")
        except cloudinary.exceptions.NotFound:
            logger.warning(f"Cloudinary resource not found: {public_id}")
            return None
        except cloudinary.exceptions.Error as e:
            logger.error(f"Error fetching Cloudinary resource: {e}")
            return None

    def cleanup_expired(self, folder: str = "storyline") -> int:
        """
        Remove uploads older than retention period.

        This is a batch cleanup operation that should be run periodically
        to remove any orphaned uploads that weren't deleted after posting.

        Args:
            folder: Cloudinary folder to clean up

        Returns:
            Number of items deleted
        """
        with self.track_execution(
            method_name="cleanup_expired",
            input_params={"folder": folder},
        ) as run_id:
            deleted_count = 0
            retention_hours = settings.CLOUD_UPLOAD_RETENTION_HOURS
            cutoff = datetime.utcnow() - timedelta(hours=retention_hours)

            try:
                # List all resources in the folder
                result = cloudinary.api.resources(
                    type="upload",
                    prefix=folder,
                    max_results=500,
                )

                for resource in result.get("resources", []):
                    # Parse Cloudinary's created_at timestamp
                    created_at_str = resource.get("created_at", "")
                    if created_at_str:
                        try:
                            # Cloudinary format: "2024-01-11T12:00:00Z"
                            created_at = datetime.fromisoformat(
                                created_at_str.replace("Z", "+00:00")
                            ).replace(tzinfo=None)

                            if created_at < cutoff:
                                if self.delete_media(resource["public_id"]):
                                    deleted_count += 1
                        except ValueError:
                            logger.warning(
                                f"Could not parse date for {resource['public_id']}: {created_at_str}"
                            )

                logger.info(
                    f"Cleaned up {deleted_count} expired uploads from Cloudinary"
                )
                self.set_result_summary(run_id, {"deleted_count": deleted_count})
                return deleted_count

            except cloudinary.exceptions.Error as e:
                logger.error(f"Cloudinary cleanup failed: {e}")
                self.set_result_summary(
                    run_id, {"deleted_count": deleted_count, "error": str(e)}
                )
                return deleted_count

    def is_configured(self) -> bool:
        """Check if Cloudinary is properly configured."""
        return all(
            [
                settings.CLOUDINARY_CLOUD_NAME,
                settings.CLOUDINARY_API_KEY,
                settings.CLOUDINARY_API_SECRET,
            ]
        )

    def _get_resource_type(self, path: Path) -> str:
        """Determine Cloudinary resource type from file extension."""
        video_extensions = {".mp4", ".mov", ".avi", ".webm", ".mkv"}
        if path.suffix.lower() in video_extensions:
            return "video"
        return "image"

    def get_story_optimized_url(self, url: str, blur_intensity: int = 2000) -> str:
        """
        Transform a Cloudinary URL for Instagram Story format (9:16).

        Uses underlay technique: creates a blurred, filled version of the image
        as the background, then places the original image centered on top with
        padding. This preserves the original image while filling the 9:16 frame.

        Note: b_blurred only works for videos in Cloudinary. For images, we use
        an underlay of the same image with e_blur effect applied.

        Args:
            url: Original Cloudinary URL
            blur_intensity: Blur strength for background (100-2000, default 400)

        Returns:
            Transformed URL optimized for Instagram Stories

        Example:
            Input:  https://res.cloudinary.com/xxx/image/upload/v123/folder/img.jpg
            Output: Complex underlay transformation URL
        """
        import re

        if "/upload/" not in url:
            logger.warning(
                f"Could not apply transformation - unexpected URL format: {url[:50]}..."
            )
            return url

        # Extract the public_id from the URL
        # URL format: https://res.cloudinary.com/cloud/image/upload/v123/folder/file.ext
        match = re.search(r"/upload/(?:v\d+/)?(.+?)(?:\.[^.]+)?$", url)
        if not match:
            logger.warning(f"Could not extract public_id from URL: {url[:50]}...")
            return url

        public_id = match.group(1)
        # Replace slashes with colons for underlay reference
        underlay_id = public_id.replace("/", ":")

        # Build the transformation chain:
        # 1. Define underlay (same image)
        # 2. Transform underlay: fill to 9:16 frame, apply blur
        # 3. fl_layer_apply to close underlay section
        # 4. Transform base image: scale to fill WIDTH (1080), then pad HEIGHT only
        #
        # This ensures the main image fills edge-to-edge horizontally,
        # with blurred padding only on top/bottom.
        #
        # URL structure: /u_<id>/underlay_transforms/fl_layer_apply/base_transforms/
        transformation = (
            f"u_{underlay_id}/"
            f"c_fill,w_1080,h_1920,e_blur:{blur_intensity}/"
            f"fl_layer_apply/"
            f"c_limit,w_1080/"  # Scale to fit width, maintain aspect ratio
            f"c_pad,w_1080,h_1920,g_center"  # Pad vertically to 9:16
        )

        transformed_url = url.replace("/upload/", f"/upload/{transformation}/")
        logger.info(
            f"Applied Story transformation with blurred underlay (public_id: {public_id})"
        )

        return transformed_url
