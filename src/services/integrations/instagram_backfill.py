"""Instagram media backfill service - pull existing media from Instagram into the system."""

import hashlib
import mimetypes
from dataclasses import dataclass, field
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
    TokenExpiredError,
)
from src.repositories.media_repository import MediaRepository
from src.services.base_service import BaseService
from src.services.integrations.instagram_api import InstagramAPIService
from src.utils.logger import logger


@dataclass
class BackfillResult:
    """Tracks the outcome of an Instagram backfill operation."""

    downloaded: int = 0
    skipped_duplicate: int = 0
    skipped_unsupported: int = 0
    failed: int = 0
    total_api_items: int = 0
    error_details: list[str] = field(default_factory=list)
    dry_run: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for result summary storage."""
        result = {
            "downloaded": self.downloaded,
            "skipped_duplicate": self.skipped_duplicate,
            "skipped_unsupported": self.skipped_unsupported,
            "failed": self.failed,
            "total_api_items": self.total_api_items,
            "dry_run": self.dry_run,
        }
        if self.error_details:
            result["error_details"] = self.error_details[:20]
        return result

    @property
    def total_processed(self) -> int:
        """Total items that were evaluated."""
        return (
            self.downloaded
            + self.skipped_duplicate
            + self.skipped_unsupported
            + self.failed
        )


class InstagramBackfillService(BaseService):
    """Pull existing media from Instagram back into the media library.

    Uses the Instagram Graph API to fetch a user's media history (feed posts),
    downloads the media files, stores them to the configured media directory,
    and indexes them in the database.

    Important API constraints:
    - GET /{user-id}/media returns feed posts only (photos, videos, carousels, reels)
    - GET /{user-id}/stories returns only LIVE stories (last 24 hours)
    - media_url values expire after a few hours -- download promptly
    - Rate limit: ~200 API calls/user/hour
    - Pagination: cursor-based with 'after' token
    """

    META_GRAPH_BASE = "https://graph.facebook.com/v18.0"

    MEDIA_FIELDS = (
        "id,media_type,media_url,thumbnail_url,timestamp,"
        "caption,permalink,username"
    )

    SUPPORTED_MEDIA_TYPES = {"IMAGE", "VIDEO"}
    CAROUSEL_TYPE = "CAROUSEL_ALBUM"
    CAROUSEL_CHILDREN_FIELDS = "id,media_type,media_url,timestamp"

    DOWNLOAD_TIMEOUT = 120.0
    API_TIMEOUT = 30.0
    MAX_PAGES = 100
    DEFAULT_PAGE_SIZE = 25

    BACKFILL_CATEGORY = "instagram_backfill"

    def __init__(self):
        super().__init__()
        self.instagram_service = InstagramAPIService()
        self.media_repo = MediaRepository()

    async def backfill(
        self,
        telegram_chat_id: Optional[int] = None,
        limit: Optional[int] = None,
        media_type: str = "feed",
        since: Optional[datetime] = None,
        dry_run: bool = False,
        account_id: Optional[str] = None,
        triggered_by: str = "cli",
    ) -> BackfillResult:
        """Run Instagram media backfill.

        Fetches the user's media from Instagram Graph API, downloads each
        item, stores it to the local media directory, and indexes it in
        the database.

        Args:
            telegram_chat_id: Chat to get active account for.
                Defaults to ADMIN_TELEGRAM_CHAT_ID.
            limit: Maximum number of items to backfill (None = all available).
            media_type: Type of media to backfill:
                'feed' = feed posts only (default, most useful)
                'stories' = live stories only (last 24 hours)
                'both' = feed + live stories
            since: Only backfill media newer than this date (None = all).
            dry_run: If True, fetch and count but don't download.
            account_id: Specific Instagram account UUID to use.
            triggered_by: Who triggered the backfill ('cli', 'telegram', 'system').

        Returns:
            BackfillResult with counts for each outcome.

        Raises:
            BackfillError: If backfill cannot proceed (no credentials, etc.)
            TokenExpiredError: If Instagram token is invalid.
        """
        if telegram_chat_id is None:
            telegram_chat_id = settings.ADMIN_TELEGRAM_CHAT_ID

        with self.track_execution(
            method_name="backfill",
            triggered_by=triggered_by,
            input_params={
                "limit": limit,
                "media_type": media_type,
                "since": since.isoformat() if since else None,
                "dry_run": dry_run,
                "account_id": account_id,
            },
        ) as run_id:
            result = BackfillResult(dry_run=dry_run)

            token, ig_account_id, username = self._get_credentials(
                telegram_chat_id, account_id
            )

            logger.info(
                f"[InstagramBackfillService] Starting backfill for @{username or ig_account_id} "
                f"(type={media_type}, limit={limit}, dry_run={dry_run})"
            )

            known_ig_ids = self.media_repo.get_backfilled_instagram_media_ids()
            logger.info(
                f"[InstagramBackfillService] {len(known_ig_ids)} existing backfilled items in DB"
            )

            storage_dir = self._get_storage_dir()
            if not dry_run:
                storage_dir.mkdir(parents=True, exist_ok=True)

            if media_type in ("feed", "both"):
                await self._backfill_feed(
                    token=token,
                    ig_account_id=ig_account_id,
                    username=username,
                    limit=limit,
                    since=since,
                    dry_run=dry_run,
                    known_ig_ids=known_ig_ids,
                    storage_dir=storage_dir,
                    result=result,
                )

            if media_type in ("stories", "both"):
                await self._backfill_stories(
                    token=token,
                    ig_account_id=ig_account_id,
                    username=username,
                    limit=limit if media_type == "stories" else None,
                    dry_run=dry_run,
                    known_ig_ids=known_ig_ids,
                    storage_dir=storage_dir,
                    result=result,
                )

            logger.info(
                f"[InstagramBackfillService] Backfill complete: "
                f"{result.downloaded} downloaded, "
                f"{result.skipped_duplicate} duplicates, "
                f"{result.skipped_unsupported} unsupported, "
                f"{result.failed} failed "
                f"(total API items: {result.total_api_items})"
            )

            self.set_result_summary(run_id, result.to_dict())
            return result

    def _get_credentials(
        self,
        telegram_chat_id: int,
        account_id: Optional[str] = None,
    ) -> tuple[str, str, Optional[str]]:
        """Get Instagram API credentials for backfill.

        Returns:
            Tuple of (token, instagram_account_id, username).

        Raises:
            BackfillError: If no credentials available.
            TokenExpiredError: If token is expired.
        """
        if account_id:
            account = self.instagram_service.account_service.get_account_by_id(
                account_id
            )
            if not account:
                raise BackfillError(f"Instagram account not found: {account_id}")

            token_record = self.instagram_service.token_repo.get_token_for_account(
                account_id, token_type="access_token"
            )
            if not token_record or token_record.is_expired:
                raise TokenExpiredError(
                    f"No valid token for account {account.display_name}"
                )

            decrypted_token = self.instagram_service.encryption.decrypt(
                token_record.token_value
            )
            return (
                decrypted_token,
                account.instagram_account_id,
                account.instagram_username,
            )

        token, ig_id, username = (
            self.instagram_service._get_active_account_credentials(telegram_chat_id)
        )

        if not token:
            raise BackfillError(
                "No valid Instagram token available. "
                "Configure an account via CLI or /settings."
            )

        if not ig_id:
            raise BackfillError(
                "No Instagram account configured. "
                "Use /settings to select one or add via CLI."
            )

        return (token, ig_id, username)

    async def _backfill_feed(
        self,
        token: str,
        ig_account_id: str,
        username: Optional[str],
        limit: Optional[int],
        since: Optional[datetime],
        dry_run: bool,
        known_ig_ids: set,
        storage_dir: Path,
        result: BackfillResult,
    ) -> None:
        """Fetch and process feed media from Instagram API.

        Handles cursor-based pagination through GET /{user-id}/media.
        """
        items_remaining = limit
        after_cursor = None

        for page_num in range(self.MAX_PAGES):
            page_size = self.DEFAULT_PAGE_SIZE
            if items_remaining is not None:
                page_size = min(page_size, items_remaining)
                if page_size <= 0:
                    break

            media_page = await self._fetch_media_page(
                token=token,
                ig_account_id=ig_account_id,
                after_cursor=after_cursor,
                page_size=page_size,
            )

            items = media_page.get("data", [])
            if not items:
                break

            result.total_api_items += len(items)
            logger.info(
                f"[InstagramBackfillService] Feed page {page_num + 1}: "
                f"{len(items)} items"
            )

            for item in items:
                if since and not self._is_after_date(item, since):
                    logger.info(
                        f"[InstagramBackfillService] Reached items older than "
                        f"{since.isoformat()}, stopping."
                    )
                    return

                await self._process_media_item(
                    item=item,
                    token=token,
                    username=username,
                    dry_run=dry_run,
                    known_ig_ids=known_ig_ids,
                    storage_dir=storage_dir,
                    result=result,
                    source_label="feed",
                )

                if items_remaining is not None:
                    items_remaining -= 1
                    if items_remaining <= 0:
                        return

            paging = media_page.get("paging", {})
            after_cursor = paging.get("cursors", {}).get("after")
            if not after_cursor or "next" not in paging:
                break

    async def _backfill_stories(
        self,
        token: str,
        ig_account_id: str,
        username: Optional[str],
        limit: Optional[int],
        dry_run: bool,
        known_ig_ids: set,
        storage_dir: Path,
        result: BackfillResult,
    ) -> None:
        """Fetch and process live stories (last 24 hours only)."""
        try:
            stories_data = await self._fetch_stories(
                token=token,
                ig_account_id=ig_account_id,
            )
        except InstagramAPIError as e:
            logger.warning(
                f"[InstagramBackfillService] Stories fetch failed: {e}. "
                f"This is expected if the account has no live stories."
            )
            return

        items = stories_data.get("data", [])
        if not items:
            logger.info(
                "[InstagramBackfillService] No live stories found (stories "
                "are only available for 24 hours via API)"
            )
            return

        result.total_api_items += len(items)
        logger.info(
            f"[InstagramBackfillService] Found {len(items)} live stories"
        )

        items_remaining = limit
        for item in items:
            if items_remaining is not None and items_remaining <= 0:
                break

            await self._process_media_item(
                item=item,
                token=token,
                username=username,
                dry_run=dry_run,
                known_ig_ids=known_ig_ids,
                storage_dir=storage_dir,
                result=result,
                source_label="story",
            )

            if items_remaining is not None:
                items_remaining -= 1

    async def _process_media_item(
        self,
        item: dict,
        token: str,
        username: Optional[str],
        dry_run: bool,
        known_ig_ids: set,
        storage_dir: Path,
        result: BackfillResult,
        source_label: str,
    ) -> None:
        """Process a single Instagram media item."""
        ig_media_id = item.get("id")
        media_type = item.get("media_type", "")

        if ig_media_id in known_ig_ids:
            result.skipped_duplicate += 1
            return

        if media_type == self.CAROUSEL_TYPE:
            await self._process_carousel(
                item=item,
                token=token,
                username=username,
                dry_run=dry_run,
                known_ig_ids=known_ig_ids,
                storage_dir=storage_dir,
                result=result,
            )
            return

        if media_type not in self.SUPPORTED_MEDIA_TYPES:
            result.skipped_unsupported += 1
            return

        media_url = item.get("media_url")
        if not media_url and media_type == "VIDEO":
            media_url = item.get("thumbnail_url")

        if not media_url:
            result.failed += 1
            result.error_details.append(
                f"No media_url for {ig_media_id} ({media_type})"
            )
            return

        if dry_run:
            result.downloaded += 1
            known_ig_ids.add(ig_media_id)
            logger.info(
                f"[InstagramBackfillService] [DRY RUN] Would download: "
                f"{ig_media_id} ({media_type}, {source_label})"
            )
            return

        try:
            await self._download_and_index(
                ig_media_id=ig_media_id,
                media_url=media_url,
                media_type=media_type,
                item=item,
                username=username,
                storage_dir=storage_dir,
                source_label=source_label,
            )
            result.downloaded += 1
            known_ig_ids.add(ig_media_id)
        except Exception as e:
            result.failed += 1
            error_msg = f"Failed to download {ig_media_id}: {e}"
            result.error_details.append(error_msg)
            logger.error(f"[InstagramBackfillService] {error_msg}")

    async def _process_carousel(
        self,
        item: dict,
        token: str,
        username: Optional[str],
        dry_run: bool,
        known_ig_ids: set,
        storage_dir: Path,
        result: BackfillResult,
    ) -> None:
        """Expand a carousel album and process each child media item."""
        carousel_id = item.get("id")
        logger.info(
            f"[InstagramBackfillService] Expanding carousel: {carousel_id}"
        )

        try:
            children_data = await self._fetch_carousel_children(
                token=token,
                carousel_id=carousel_id,
            )
        except InstagramAPIError as e:
            result.failed += 1
            result.error_details.append(
                f"Failed to expand carousel {carousel_id}: {e}"
            )
            return

        children = children_data.get("data", [])
        for child in children:
            result.total_api_items += 1

            child.setdefault("caption", item.get("caption"))
            child.setdefault("permalink", item.get("permalink"))
            child.setdefault("username", item.get("username"))

            await self._process_media_item(
                item=child,
                token=token,
                username=username,
                dry_run=dry_run,
                known_ig_ids=known_ig_ids,
                storage_dir=storage_dir,
                result=result,
                source_label="carousel",
            )

    async def _download_and_index(
        self,
        ig_media_id: str,
        media_url: str,
        media_type: str,
        item: dict,
        username: Optional[str],
        storage_dir: Path,
        source_label: str,
    ) -> None:
        """Download media from Instagram and index in the database."""
        file_bytes = await self._download_media(media_url, ig_media_id)

        extension = self._get_extension_for_type(media_type, media_url)
        timestamp = item.get("timestamp", "")
        date_prefix = ""
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                date_prefix = dt.strftime("%Y%m%d_%H%M%S_")
            except (ValueError, TypeError):
                pass

        filename = f"{date_prefix}{ig_media_id}{extension}"
        file_path = storage_dir / filename

        file_path.write_bytes(file_bytes)

        file_hash = hashlib.sha256(file_bytes).hexdigest()

        mime_type, _ = mimetypes.guess_type(str(file_path))
        if not mime_type:
            mime_type = "image/jpeg" if media_type == "IMAGE" else "video/mp4"

        media_item = self.media_repo.create(
            file_path=str(file_path),
            file_name=filename,
            file_hash=file_hash,
            file_size_bytes=len(file_bytes),
            mime_type=mime_type,
            category=self.BACKFILL_CATEGORY,
            source_type="instagram_backfill",
            source_identifier=ig_media_id,
        )

        # Set backfill tracking fields directly on the returned object
        media_item.instagram_media_id = ig_media_id
        media_item.backfilled_at = datetime.utcnow()
        self.media_repo.db.commit()

        logger.info(
            f"[InstagramBackfillService] Downloaded and indexed: "
            f"{filename} ({media_type}, {source_label})"
        )

    # ==================== API Calls ====================

    async def _fetch_media_page(
        self,
        token: str,
        ig_account_id: str,
        after_cursor: Optional[str] = None,
        page_size: int = 25,
    ) -> dict:
        """Fetch a page of media from GET /{user-id}/media."""
        params = {
            "fields": self.MEDIA_FIELDS,
            "limit": page_size,
            "access_token": token,
        }
        if after_cursor:
            params["after"] = after_cursor

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.META_GRAPH_BASE}/{ig_account_id}/media",
                params=params,
                timeout=self.API_TIMEOUT,
            )

            self.instagram_service._check_response_errors(response)
            return response.json()

    async def _fetch_stories(
        self,
        token: str,
        ig_account_id: str,
    ) -> dict:
        """Fetch live stories from GET /{user-id}/stories."""
        params = {
            "fields": self.MEDIA_FIELDS,
            "access_token": token,
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.META_GRAPH_BASE}/{ig_account_id}/stories",
                params=params,
                timeout=self.API_TIMEOUT,
            )

            self.instagram_service._check_response_errors(response)
            return response.json()

    async def _fetch_carousel_children(
        self,
        token: str,
        carousel_id: str,
    ) -> dict:
        """Fetch children of a carousel album."""
        params = {
            "fields": self.CAROUSEL_CHILDREN_FIELDS,
            "access_token": token,
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.META_GRAPH_BASE}/{carousel_id}/children",
                params=params,
                timeout=self.API_TIMEOUT,
            )

            self.instagram_service._check_response_errors(response)
            return response.json()

    async def _download_media(self, url: str, ig_media_id: str) -> bytes:
        """Download media bytes from an Instagram media URL.

        Raises:
            BackfillMediaExpiredError: If URL has expired (HTTP 403/410)
            BackfillError: If download fails for other reasons
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    timeout=self.DOWNLOAD_TIMEOUT,
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

    def _get_storage_dir(self) -> Path:
        """Get the local directory to store backfilled media."""
        return Path(settings.MEDIA_DIR) / self.BACKFILL_CATEGORY

    def _get_extension_for_type(self, media_type: str, url: str) -> str:
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

    def _is_after_date(self, item: dict, since: datetime) -> bool:
        """Check if an Instagram item's timestamp is after the 'since' date."""
        timestamp_str = item.get("timestamp", "")
        if not timestamp_str:
            return True

        try:
            item_dt = datetime.fromisoformat(
                timestamp_str.replace("Z", "+00:00")
            ).replace(tzinfo=None)
            return item_dt >= since
        except (ValueError, TypeError):
            return True

    def get_backfill_status(self) -> dict:
        """Get information about backfill history."""
        runs = self.service_run_repo.get_recent_runs(
            service_name="InstagramBackfillService", limit=5
        )

        backfilled_count = len(
            self.media_repo.get_backfilled_instagram_media_ids()
        )

        last_run = None
        if runs:
            run = runs[0]
            last_run = {
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "completed_at": (
                    run.completed_at.isoformat() if run.completed_at else None
                ),
                "success": run.success,
                "result": run.result_summary,
                "triggered_by": run.triggered_by,
            }

        return {
            "total_backfilled": backfilled_count,
            "last_run": last_run,
        }
