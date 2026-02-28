"""Media downloading, storage, and Instagram API calls for backfill."""

import hashlib
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

from src.config.settings import settings
from src.exceptions import (
    BackfillError,
    BackfillMediaExpiredError,
    BackfillMediaNotFoundError,
    InstagramAPIError,
)
from src.utils.logger import logger

if False:  # TYPE_CHECKING without import overhead
    from src.services.integrations.instagram_backfill import (
        BackfillContext,
        InstagramBackfillService,
    )


class BackfillDownloader:
    """Handles media downloading, storage, and Instagram API calls for backfill.

    Extracted from InstagramBackfillService to keep the parent focused on
    orchestration (pagination, deduplication, result tracking) while this
    class handles the lower-level I/O: API calls, file downloads, hashing,
    and database indexing.

    Uses composition: receives a reference to the parent service for access
    to httpx client helpers, repositories, and configuration constants.
    """

    def __init__(self, backfill_service: "InstagramBackfillService"):
        self.service = backfill_service

    # ==================== Processing ====================

    async def process_carousel(
        self,
        ctx: "BackfillContext",
        item: dict,
    ) -> None:
        """Expand a carousel album and process each child media item."""
        carousel_id = item.get("id")
        logger.info(f"[InstagramBackfillService] Expanding carousel: {carousel_id}")

        try:
            children_data = await self.fetch_carousel_children(
                token=ctx.token,
                carousel_id=carousel_id,
            )
        except InstagramAPIError as e:
            ctx.result.failed += 1
            ctx.result.error_details.append(
                f"Failed to expand carousel {carousel_id}: {e}"
            )
            return

        children = children_data.get("data", [])
        for child in children:
            ctx.result.total_api_items += 1

            child.setdefault("caption", item.get("caption"))
            child.setdefault("permalink", item.get("permalink"))
            child.setdefault("username", item.get("username"))

            await self.service._process_media_item(
                ctx, item=child, source_label="carousel"
            )

    async def download_and_index(
        self,
        ctx: "BackfillContext",
        ig_media_id: str,
        media_url: str,
        media_type: str,
        item: dict,
        source_label: str,
    ) -> None:
        """Download media from Instagram and index in the database."""
        file_bytes = await self.download_media(media_url, ig_media_id)

        extension = self.get_extension_for_type(media_type, media_url)
        timestamp = item.get("timestamp", "")
        date_prefix = ""
        if timestamp:
            try:
                normalized = timestamp.replace("Z", "+00:00")
                # Python 3.10 fromisoformat doesn't support +0000 (no colon)
                if normalized.endswith("+0000"):
                    normalized = normalized[:-5] + "+00:00"
                dt = datetime.fromisoformat(normalized)
                date_prefix = dt.strftime("%Y%m%d_%H%M%S_")
            except (ValueError, TypeError):
                pass

        filename = f"{date_prefix}{ig_media_id}{extension}"
        file_path = ctx.storage_dir / filename

        file_path.write_bytes(file_bytes)

        file_hash = hashlib.sha256(file_bytes).hexdigest()

        mime_type, _ = mimetypes.guess_type(str(file_path))
        if not mime_type:
            mime_type = "image/jpeg" if media_type == "IMAGE" else "video/mp4"

        media_item = self.service.media_repo.create(
            file_path=str(file_path),
            file_name=filename,
            file_hash=file_hash,
            file_size_bytes=len(file_bytes),
            mime_type=mime_type,
            category=self.service.BACKFILL_CATEGORY,
            source_type="instagram_backfill",
            source_identifier=ig_media_id,
        )

        # Set backfill tracking fields directly on the returned object
        media_item.instagram_media_id = ig_media_id
        media_item.backfilled_at = datetime.utcnow()
        self.service.media_repo.db.commit()

        logger.info(
            f"[InstagramBackfillService] Downloaded and indexed: "
            f"{filename} ({media_type}, {source_label})"
        )

    # ==================== API Calls ====================

    async def fetch_media_page(
        self,
        token: str,
        ig_account_id: str,
        after_cursor: Optional[str] = None,
        page_size: int = 25,
    ) -> dict:
        """Fetch a page of media from GET /{user-id}/media."""
        params = {
            "fields": self.service.MEDIA_FIELDS,
            "limit": page_size,
            "access_token": token,
        }
        if after_cursor:
            params["after"] = after_cursor

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.service.META_GRAPH_BASE}/{ig_account_id}/media",
                params=params,
                timeout=self.service.API_TIMEOUT,
            )

            self.service.instagram_service._check_response_errors(response)
            return response.json()

    async def fetch_stories(
        self,
        token: str,
        ig_account_id: str,
    ) -> dict:
        """Fetch live stories from GET /{user-id}/stories."""
        params = {
            "fields": self.service.MEDIA_FIELDS,
            "access_token": token,
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.service.META_GRAPH_BASE}/{ig_account_id}/stories",
                params=params,
                timeout=self.service.API_TIMEOUT,
            )

            self.service.instagram_service._check_response_errors(response)
            return response.json()

    async def fetch_carousel_children(
        self,
        token: str,
        carousel_id: str,
    ) -> dict:
        """Fetch children of a carousel album."""
        params = {
            "fields": self.service.CAROUSEL_CHILDREN_FIELDS,
            "access_token": token,
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.service.META_GRAPH_BASE}/{carousel_id}/children",
                params=params,
                timeout=self.service.API_TIMEOUT,
            )

            self.service.instagram_service._check_response_errors(response)
            return response.json()

    async def download_media(self, url: str, ig_media_id: str) -> bytes:
        """Download media bytes from an Instagram media URL.

        Raises:
            BackfillMediaExpiredError: If URL has expired (HTTP 403/410)
            BackfillError: If download fails for other reasons
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    timeout=self.service.DOWNLOAD_TIMEOUT,
                    follow_redirects=True,
                )

                if response.status_code in (403, 410):
                    raise BackfillMediaExpiredError(
                        f"Media URL expired for {ig_media_id} "
                        f"(HTTP {response.status_code})",
                        instagram_media_id=ig_media_id,
                    )

                if response.status_code == 404:
                    raise BackfillMediaNotFoundError(
                        f"Media not found for {ig_media_id}",
                        instagram_media_id=ig_media_id,
                    )

                if response.status_code != 200:
                    raise BackfillError(
                        f"Download failed for {ig_media_id}: "
                        f"HTTP {response.status_code}",
                        instagram_media_id=ig_media_id,
                    )

                content = response.content
                if not content:
                    raise BackfillError(
                        f"Empty response for {ig_media_id}",
                        instagram_media_id=ig_media_id,
                    )

                return content

        except httpx.RequestError as e:
            raise BackfillError(
                f"Network error downloading {ig_media_id}: {e}",
                instagram_media_id=ig_media_id,
            )

    # ==================== Helpers ====================

    def get_storage_dir(self) -> Path:
        """Get the local directory to store backfilled media."""
        return Path(settings.MEDIA_DIR) / self.service.BACKFILL_CATEGORY

    def get_extension_for_type(self, media_type: str, url: str) -> str:
        """Determine file extension from media type and URL."""
        try:
            url_path = url.split("?")[0]
            suffix = Path(url_path).suffix.lower()
            if suffix in {".jpg", ".jpeg", ".png", ".gif", ".mp4", ".mov", ".webp"}:
                return suffix
        except (ValueError, IndexError):
            pass

        if media_type == "VIDEO":
            return ".mp4"
        return ".jpg"

    def is_after_date(self, item: dict, since: datetime) -> bool:
        """Check if an Instagram item's timestamp is after the 'since' date."""
        timestamp_str = item.get("timestamp", "")
        if not timestamp_str:
            return True

        try:
            normalized = timestamp_str.replace("Z", "+00:00")
            # Python 3.10 fromisoformat doesn't support +0000 (no colon)
            if normalized.endswith("+0000"):
                normalized = normalized[:-5] + "+00:00"
            item_dt = datetime.fromisoformat(normalized).replace(tzinfo=None)
            return item_dt >= since
        except (ValueError, TypeError):
            return True
