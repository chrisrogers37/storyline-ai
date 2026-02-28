"""Instagram media backfill service - pull existing media from Instagram into the system."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.config.settings import settings
from src.exceptions import (
    BackfillError,
    InstagramAPIError,
    TokenExpiredError,
)
from src.repositories.media_repository import MediaRepository
from src.services.base_service import BaseService
from src.services.integrations.backfill_downloader import BackfillDownloader
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


@dataclass
class BackfillContext:
    """Shared state passed through the backfill call chain.

    Bundles parameters that are constant for a single backfill() invocation
    and shared across _backfill_feed, _process_media_item, _process_carousel,
    and _download_and_index.
    """

    token: str
    ig_account_id: str
    username: Optional[str]
    dry_run: bool
    known_ig_ids: set
    storage_dir: Path
    result: BackfillResult


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
        "id,media_type,media_url,thumbnail_url,timestamp,caption,permalink,username"
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
        self.downloader = BackfillDownloader(self)

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

            ctx = BackfillContext(
                token=token,
                ig_account_id=ig_account_id,
                username=username,
                dry_run=dry_run,
                known_ig_ids=known_ig_ids,
                storage_dir=storage_dir,
                result=result,
            )

            if media_type in ("feed", "both"):
                await self._backfill_feed(ctx, limit=limit, since=since)

            if media_type in ("stories", "both"):
                stories_limit = limit if media_type == "stories" else None
                await self._backfill_stories(ctx, limit=stories_limit)

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

        token, ig_id, username = self.instagram_service._get_active_account_credentials(
            telegram_chat_id
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
        ctx: BackfillContext,
        limit: Optional[int],
        since: Optional[datetime],
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
                token=ctx.token,
                ig_account_id=ctx.ig_account_id,
                after_cursor=after_cursor,
                page_size=page_size,
            )

            items = media_page.get("data", [])
            if not items:
                break

            ctx.result.total_api_items += len(items)
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

                await self._process_media_item(ctx, item=item, source_label="feed")

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
        ctx: BackfillContext,
        limit: Optional[int],
    ) -> None:
        """Fetch and process live stories (last 24 hours only)."""
        try:
            stories_data = await self._fetch_stories(
                token=ctx.token,
                ig_account_id=ctx.ig_account_id,
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

        ctx.result.total_api_items += len(items)
        logger.info(f"[InstagramBackfillService] Found {len(items)} live stories")

        items_remaining = limit
        for item in items:
            if items_remaining is not None and items_remaining <= 0:
                break

            await self._process_media_item(ctx, item=item, source_label="story")

            if items_remaining is not None:
                items_remaining -= 1

    async def _process_media_item(
        self,
        ctx: BackfillContext,
        item: dict,
        source_label: str,
    ) -> None:
        """Process a single Instagram media item."""
        ig_media_id = item.get("id")
        media_type = item.get("media_type", "")

        if ig_media_id in ctx.known_ig_ids:
            ctx.result.skipped_duplicate += 1
            return

        if media_type == self.CAROUSEL_TYPE:
            await self._process_carousel(ctx, item=item)
            return

        if media_type not in self.SUPPORTED_MEDIA_TYPES:
            ctx.result.skipped_unsupported += 1
            return

        media_url = item.get("media_url")
        if not media_url and media_type == "VIDEO":
            media_url = item.get("thumbnail_url")

        if not media_url:
            ctx.result.failed += 1
            ctx.result.error_details.append(
                f"No media_url for {ig_media_id} ({media_type})"
            )
            return

        if ctx.dry_run:
            ctx.result.downloaded += 1
            ctx.known_ig_ids.add(ig_media_id)
            logger.info(
                f"[InstagramBackfillService] [DRY RUN] Would download: "
                f"{ig_media_id} ({media_type}, {source_label})"
            )
            return

        try:
            await self._download_and_index(
                ctx,
                ig_media_id=ig_media_id,
                media_url=media_url,
                media_type=media_type,
                item=item,
                source_label=source_label,
            )
            ctx.result.downloaded += 1
            ctx.known_ig_ids.add(ig_media_id)
        except Exception as e:
            ctx.result.failed += 1
            error_msg = f"Failed to download {ig_media_id}: {e}"
            ctx.result.error_details.append(error_msg)
            logger.error(f"[InstagramBackfillService] {error_msg}")

    # =========================================================================
    # Delegation to BackfillDownloader
    # =========================================================================

    async def _process_carousel(self, ctx, item):
        """Delegate to downloader.process_carousel."""
        return await self.downloader.process_carousel(ctx, item=item)

    async def _download_and_index(self, ctx, **kwargs):
        """Delegate to downloader.download_and_index."""
        return await self.downloader.download_and_index(ctx, **kwargs)

    async def _fetch_media_page(self, **kwargs):
        """Delegate to downloader.fetch_media_page."""
        return await self.downloader.fetch_media_page(**kwargs)

    async def _fetch_stories(self, **kwargs):
        """Delegate to downloader.fetch_stories."""
        return await self.downloader.fetch_stories(**kwargs)

    async def _fetch_carousel_children(self, **kwargs):
        """Delegate to downloader.fetch_carousel_children."""
        return await self.downloader.fetch_carousel_children(**kwargs)

    async def _download_media(self, url, ig_media_id):
        """Delegate to downloader.download_media."""
        return await self.downloader.download_media(url, ig_media_id)

    def _get_storage_dir(self):
        """Delegate to downloader.get_storage_dir."""
        return self.downloader.get_storage_dir()

    def _get_extension_for_type(self, media_type, url):
        """Delegate to downloader.get_extension_for_type."""
        return self.downloader.get_extension_for_type(media_type, url)

    def _is_after_date(self, item, since):
        """Delegate to downloader.is_after_date."""
        return self.downloader.is_after_date(item, since)

    # =========================================================================
    # Status
    # =========================================================================

    def get_backfill_status(self) -> dict:
        """Get information about backfill history."""
        runs = self.service_run_repo.get_recent_runs(
            service_name="InstagramBackfillService", limit=5
        )

        backfilled_count = len(self.media_repo.get_backfilled_instagram_media_ids())

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
