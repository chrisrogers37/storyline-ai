"""Tests for BackfillDownloader — media downloading, storage, and Instagram API calls."""

import hashlib
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
import httpx

from src.exceptions import (
    BackfillError,
    BackfillMediaExpiredError,
    BackfillMediaNotFoundError,
    InstagramAPIError,
)
from src.services.integrations.backfill_downloader import BackfillDownloader


class MockHttpxClient:
    """Async context manager that replaces httpx.AsyncClient in tests."""

    def __init__(self, response=None, get_side_effect=None):
        self._response = response
        self._get_side_effect = get_side_effect

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def get(self, *args, **kwargs):
        if self._get_side_effect:
            raise self._get_side_effect
        return self._response


@pytest.fixture
def mock_backfill_service():
    """Minimal InstagramBackfillService mock."""
    service = Mock()
    service.MEDIA_FIELDS = (
        "id,media_type,media_url,timestamp,caption,permalink,username"
    )
    service.CAROUSEL_CHILDREN_FIELDS = "id,media_type,media_url,timestamp"
    service.BACKFILL_CATEGORY = "instagram_backfill"
    service.API_TIMEOUT = 30
    service.DOWNLOAD_TIMEOUT = 60
    service.instagram_service = Mock()
    service.media_repo = Mock()
    service.media_repo.db = Mock()
    service._process_media_item = AsyncMock()
    return service


@pytest.fixture
def downloader(mock_backfill_service):
    """BackfillDownloader with mocked parent service."""
    return BackfillDownloader(mock_backfill_service)


def _make_ctx(token="test-token", storage_dir="/tmp/test"):
    """Build a minimal BackfillContext mock."""
    ctx = Mock()
    ctx.token = token
    ctx.storage_dir = Path(storage_dir)
    ctx.result = Mock(
        total_api_items=0,
        failed=0,
        error_details=[],
    )
    return ctx


# ──────────────────────────────────────────────────────────────
# process_carousel
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
class TestProcessCarousel:
    async def test_expands_and_processes_children(self, downloader):
        """Fetches carousel children and processes each one."""
        ctx = _make_ctx()
        item = {
            "id": "carousel-1",
            "caption": "Group post",
            "permalink": "https://ig/p/123",
            "username": "testuser",
        }
        downloader.fetch_carousel_children = AsyncMock(
            return_value={
                "data": [
                    {"id": "child-1", "media_type": "IMAGE"},
                    {"id": "child-2", "media_type": "IMAGE"},
                ]
            }
        )

        await downloader.process_carousel(ctx, item)

        assert ctx.result.total_api_items == 2
        assert downloader.service._process_media_item.call_count == 2

    async def test_children_inherit_parent_fields(self, downloader):
        """Children get caption, permalink, username from parent when missing."""
        ctx = _make_ctx()
        item = {
            "id": "carousel-1",
            "caption": "Parent caption",
            "permalink": "https://ig/p/123",
            "username": "testuser",
        }
        child = {"id": "child-1", "media_type": "IMAGE"}
        downloader.fetch_carousel_children = AsyncMock(return_value={"data": [child]})

        await downloader.process_carousel(ctx, item)

        call_kwargs = downloader.service._process_media_item.call_args[1]
        assert call_kwargs["item"]["caption"] == "Parent caption"

    async def test_api_error_increments_failed(self, downloader):
        """If fetching children fails, increments failed count."""
        ctx = _make_ctx()
        item = {"id": "carousel-1"}
        downloader.fetch_carousel_children = AsyncMock(
            side_effect=InstagramAPIError("API error")
        )

        await downloader.process_carousel(ctx, item)

        assert ctx.result.failed == 1
        assert len(ctx.result.error_details) == 1


# ──────────────────────────────────────────────────────────────
# download_and_index
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
class TestDownloadAndIndex:
    async def test_downloads_and_creates_media_item(self, downloader, tmp_path):
        """Downloads media, saves to disk, and indexes in database."""
        ctx = _make_ctx(storage_dir=str(tmp_path))
        file_bytes = b"fake-image-data"
        downloader.download_media = AsyncMock(return_value=file_bytes)
        mock_media_item = Mock()
        downloader.service.media_repo.create.return_value = mock_media_item

        item = {"timestamp": "2026-03-15T10:30:00+0000"}

        await downloader.download_and_index(
            ctx, "ig-1", "https://cdn.ig/photo.jpg", "IMAGE", item, "feed"
        )

        downloader.service.media_repo.create.assert_called_once()
        call_kwargs = downloader.service.media_repo.create.call_args[1]
        assert call_kwargs["source_type"] == "instagram_backfill"
        assert call_kwargs["source_identifier"] == "ig-1"
        assert call_kwargs["file_hash"] == hashlib.sha256(file_bytes).hexdigest()
        assert mock_media_item.instagram_media_id == "ig-1"

    async def test_timestamp_in_filename(self, downloader, tmp_path):
        """Timestamp is included as prefix in the filename."""
        ctx = _make_ctx(storage_dir=str(tmp_path))
        downloader.download_media = AsyncMock(return_value=b"data")
        downloader.service.media_repo.create.return_value = Mock()

        item = {"timestamp": "2026-03-15T10:30:00+0000"}

        await downloader.download_and_index(
            ctx, "ig-1", "https://cdn.ig/photo.jpg", "IMAGE", item, "feed"
        )

        call_kwargs = downloader.service.media_repo.create.call_args[1]
        assert call_kwargs["file_name"].startswith("20260315_")

    async def test_no_timestamp(self, downloader, tmp_path):
        """Missing timestamp → filename starts with media ID directly."""
        ctx = _make_ctx(storage_dir=str(tmp_path))
        downloader.download_media = AsyncMock(return_value=b"data")
        downloader.service.media_repo.create.return_value = Mock()

        item = {}

        await downloader.download_and_index(
            ctx, "ig-1", "https://cdn.ig/photo.jpg", "IMAGE", item, "feed"
        )

        call_kwargs = downloader.service.media_repo.create.call_args[1]
        assert call_kwargs["file_name"].startswith("ig-1")


# ──────────────────────────────────────────────────────────────
# download_media
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
class TestDownloadMedia:
    async def test_success(self, downloader):
        """Returns content bytes on 200."""
        client = MockHttpxClient(response=Mock(status_code=200, content=b"image-bytes"))

        with patch("httpx.AsyncClient", return_value=client):
            result = await downloader.download_media("https://cdn.ig/photo.jpg", "ig-1")

        assert result == b"image-bytes"

    async def test_403_raises_expired(self, downloader):
        """HTTP 403 → BackfillMediaExpiredError."""
        client = MockHttpxClient(response=Mock(status_code=403))

        with patch("httpx.AsyncClient", return_value=client):
            with pytest.raises(BackfillMediaExpiredError):
                await downloader.download_media("https://cdn.ig/photo.jpg", "ig-1")

    async def test_410_raises_expired(self, downloader):
        """HTTP 410 → BackfillMediaExpiredError."""
        client = MockHttpxClient(response=Mock(status_code=410))

        with patch("httpx.AsyncClient", return_value=client):
            with pytest.raises(BackfillMediaExpiredError):
                await downloader.download_media("https://cdn.ig/photo.jpg", "ig-1")

    async def test_404_raises_not_found(self, downloader):
        """HTTP 404 → BackfillMediaNotFoundError."""
        client = MockHttpxClient(response=Mock(status_code=404))

        with patch("httpx.AsyncClient", return_value=client):
            with pytest.raises(BackfillMediaNotFoundError):
                await downloader.download_media("https://cdn.ig/photo.jpg", "ig-1")

    async def test_other_status_raises_backfill_error(self, downloader):
        """Non-200/403/404/410 → BackfillError."""
        client = MockHttpxClient(response=Mock(status_code=500))

        with patch("httpx.AsyncClient", return_value=client):
            with pytest.raises(BackfillError):
                await downloader.download_media("https://cdn.ig/photo.jpg", "ig-1")

    async def test_empty_response_raises_backfill_error(self, downloader):
        """Empty content body → BackfillError."""
        client = MockHttpxClient(response=Mock(status_code=200, content=b""))

        with patch("httpx.AsyncClient", return_value=client):
            with pytest.raises(BackfillError, match="Empty response"):
                await downloader.download_media("https://cdn.ig/photo.jpg", "ig-1")

    async def test_network_error_raises_backfill_error(self, downloader):
        """httpx.RequestError → BackfillError."""
        client = MockHttpxClient(
            get_side_effect=httpx.RequestError("Connection failed")
        )

        with patch("httpx.AsyncClient", return_value=client):
            with pytest.raises(BackfillError, match="Network error"):
                await downloader.download_media("https://cdn.ig/photo.jpg", "ig-1")


# ──────────────────────────────────────────────────────────────
# get_storage_dir
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestGetStorageDir:
    @patch("src.services.integrations.backfill_downloader.settings")
    def test_returns_category_subdir(self, mock_settings, downloader):
        """Returns MEDIA_DIR / BACKFILL_CATEGORY."""
        mock_settings.MEDIA_DIR = "/data/media"
        result = downloader.get_storage_dir()
        assert result == Path("/data/media/instagram_backfill")


# ──────────────────────────────────────────────────────────────
# get_extension_for_type
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestGetExtensionForType:
    def test_extracts_from_url(self, downloader):
        """Extracts extension from URL path."""
        assert (
            downloader.get_extension_for_type(
                "IMAGE", "https://cdn.ig/photo.png?token=abc"
            )
            == ".png"
        )
        assert (
            downloader.get_extension_for_type(
                "VIDEO", "https://cdn.ig/video.mp4?token=abc"
            )
            == ".mp4"
        )

    def test_fallback_for_image(self, downloader):
        """Falls back to .jpg for IMAGE type when URL has no recognizable extension."""
        assert (
            downloader.get_extension_for_type("IMAGE", "https://cdn.ig/media") == ".jpg"
        )

    def test_fallback_for_video(self, downloader):
        """Falls back to .mp4 for VIDEO type when URL has no recognizable extension."""
        assert (
            downloader.get_extension_for_type("VIDEO", "https://cdn.ig/media") == ".mp4"
        )


# ──────────────────────────────────────────────────────────────
# is_after_date
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestIsAfterDate:
    def test_item_after_since(self, downloader):
        """Returns True when item timestamp is after 'since'."""
        item = {"timestamp": "2026-04-15T12:00:00+0000"}
        since = datetime(2026, 4, 1)
        assert downloader.is_after_date(item, since) is True

    def test_item_before_since(self, downloader):
        """Returns False when item timestamp is before 'since'."""
        item = {"timestamp": "2026-03-01T12:00:00+0000"}
        since = datetime(2026, 4, 1)
        assert downloader.is_after_date(item, since) is False

    def test_no_timestamp_returns_true(self, downloader):
        """Returns True when item has no timestamp (include by default)."""
        assert downloader.is_after_date({}, datetime(2026, 1, 1)) is True
        assert downloader.is_after_date({"timestamp": ""}, datetime(2026, 1, 1)) is True

    def test_invalid_timestamp_returns_true(self, downloader):
        """Returns True for unparseable timestamps (include by default)."""
        item = {"timestamp": "not-a-date"}
        assert downloader.is_after_date(item, datetime(2026, 1, 1)) is True

    def test_z_suffix_handled(self, downloader):
        """Handles 'Z' suffix timestamps."""
        item = {"timestamp": "2026-04-15T12:00:00Z"}
        since = datetime(2026, 4, 1)
        assert downloader.is_after_date(item, since) is True
