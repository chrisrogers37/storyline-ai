"""Tests for InstagramBackfillService."""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import httpx

from src.exceptions import (
    BackfillError,
    BackfillMediaExpiredError,
    BackfillMediaNotFoundError,
    InstagramAPIError,
    TokenExpiredError,
)
from src.services.integrations.instagram_backfill import (
    BackfillResult,
    InstagramBackfillService,
)


# ==================== BackfillResult Tests ====================


@pytest.mark.unit
class TestBackfillResult:
    """Tests for the BackfillResult dataclass."""

    def test_defaults(self):
        """All counters start at 0, error_details is empty, dry_run is False."""
        result = BackfillResult()
        assert result.downloaded == 0
        assert result.skipped_duplicate == 0
        assert result.skipped_unsupported == 0
        assert result.failed == 0
        assert result.total_api_items == 0
        assert result.error_details == []
        assert result.dry_run is False

    def test_to_dict(self):
        """Converts correctly and caps error_details at 20."""
        result = BackfillResult(
            downloaded=5,
            skipped_duplicate=3,
            failed=1,
            total_api_items=9,
            error_details=[f"error_{i}" for i in range(25)],
        )
        d = result.to_dict()
        assert d["downloaded"] == 5
        assert d["skipped_duplicate"] == 3
        assert d["failed"] == 1
        assert d["total_api_items"] == 9
        assert len(d["error_details"]) == 20

    def test_to_dict_no_errors(self):
        """Omits error_details key when empty."""
        result = BackfillResult(downloaded=1)
        d = result.to_dict()
        assert "error_details" not in d

    def test_total_processed(self):
        """Sums downloaded + skipped_duplicate + skipped_unsupported + failed."""
        result = BackfillResult(
            downloaded=10,
            skipped_duplicate=5,
            skipped_unsupported=2,
            failed=3,
        )
        assert result.total_processed == 20

    def test_dry_run_flag(self):
        """Correctly stores dry_run=True."""
        result = BackfillResult(dry_run=True)
        assert result.dry_run is True
        assert result.to_dict()["dry_run"] is True


# ==================== Fixtures ====================


@pytest.fixture
def mock_backfill_service():
    """Create InstagramBackfillService with mocked dependencies."""
    with (
        patch.object(InstagramBackfillService, "__init__", lambda self: None),
    ):
        service = InstagramBackfillService()
        service.instagram_service = MagicMock()
        service.media_repo = MagicMock()
        service.service_run_repo = MagicMock()

        # Set up track_execution context manager
        service.track_execution = MagicMock()
        run_id = "test-run-id"
        service.track_execution.return_value.__enter__ = Mock(return_value=run_id)
        service.track_execution.return_value.__exit__ = Mock(return_value=False)
        service.set_result_summary = MagicMock()

        yield service


# ==================== Credential Tests ====================


@pytest.mark.unit
class TestGetCredentials:
    """Tests for credential resolution."""

    def test_active_account_credentials(self, mock_backfill_service):
        """Uses _get_active_account_credentials when no account_id."""
        mock_backfill_service.instagram_service._get_active_account_credentials.return_value = (
            "token123",
            "ig_id_456",
            "testuser",
        )

        token, ig_id, username = mock_backfill_service._get_credentials(
            telegram_chat_id=-100123
        )

        assert token == "token123"
        assert ig_id == "ig_id_456"
        assert username == "testuser"
        mock_backfill_service.instagram_service._get_active_account_credentials.assert_called_once_with(
            -100123
        )

    def test_specific_account_credentials(self, mock_backfill_service):
        """Looks up account by ID when account_id provided."""
        mock_account = Mock()
        mock_account.instagram_account_id = "ig_specific"
        mock_account.instagram_username = "specific_user"
        mock_backfill_service.instagram_service.account_service.get_account_by_id.return_value = mock_account

        mock_token_record = Mock()
        mock_token_record.is_expired = False
        mock_token_record.token_value = "encrypted_token"
        mock_backfill_service.instagram_service.token_repo.get_token_for_account.return_value = mock_token_record

        mock_backfill_service.instagram_service.encryption.decrypt.return_value = (
            "decrypted_token"
        )

        token, ig_id, username = mock_backfill_service._get_credentials(
            telegram_chat_id=-100123, account_id="uuid-123"
        )

        assert token == "decrypted_token"
        assert ig_id == "ig_specific"
        assert username == "specific_user"

    def test_no_token_raises(self, mock_backfill_service):
        """Raises BackfillError when no token available."""
        mock_backfill_service.instagram_service._get_active_account_credentials.return_value = (
            None,
            "ig_id",
            "user",
        )

        with pytest.raises(BackfillError, match="No valid Instagram token"):
            mock_backfill_service._get_credentials(telegram_chat_id=-100123)

    def test_no_account_raises(self, mock_backfill_service):
        """Raises BackfillError when no account configured."""
        mock_backfill_service.instagram_service._get_active_account_credentials.return_value = (
            "token",
            None,
            None,
        )

        with pytest.raises(BackfillError, match="No Instagram account configured"):
            mock_backfill_service._get_credentials(telegram_chat_id=-100123)

    def test_specific_account_not_found_raises(self, mock_backfill_service):
        """Raises BackfillError when specific account_id not found."""
        mock_backfill_service.instagram_service.account_service.get_account_by_id.return_value = None

        with pytest.raises(BackfillError, match="account not found"):
            mock_backfill_service._get_credentials(
                telegram_chat_id=-100123, account_id="nonexistent"
            )

    def test_specific_account_expired_token_raises(self, mock_backfill_service):
        """Raises TokenExpiredError when specific account token is expired."""
        mock_account = Mock()
        mock_account.display_name = "Test"
        mock_backfill_service.instagram_service.account_service.get_account_by_id.return_value = mock_account

        mock_token_record = Mock()
        mock_token_record.is_expired = True
        mock_backfill_service.instagram_service.token_repo.get_token_for_account.return_value = mock_token_record

        with pytest.raises(TokenExpiredError, match="No valid token"):
            mock_backfill_service._get_credentials(
                telegram_chat_id=-100123, account_id="uuid-expired"
            )


# ==================== Feed Backfill Tests ====================


@pytest.mark.unit
@pytest.mark.asyncio
class TestBackfillFeed:
    """Tests for feed media backfill."""

    async def test_downloads_images(self, mock_backfill_service):
        """IMAGE items are downloaded and indexed."""
        result = BackfillResult()
        known_ig_ids = set()
        storage_dir = Path("/tmp/test_backfill")

        mock_backfill_service._fetch_media_page = AsyncMock(
            return_value={
                "data": [
                    {
                        "id": "img_1",
                        "media_type": "IMAGE",
                        "media_url": "https://example.com/img.jpg",
                        "timestamp": "2025-06-01T12:00:00+0000",
                    }
                ],
                "paging": {},
            }
        )
        mock_backfill_service._download_and_index = AsyncMock()

        await mock_backfill_service._backfill_feed(
            token="tok",
            ig_account_id="ig_123",
            username="user",
            limit=None,
            since=None,
            dry_run=False,
            known_ig_ids=known_ig_ids,
            storage_dir=storage_dir,
            result=result,
        )

        assert result.downloaded == 1
        assert result.total_api_items == 1
        assert "img_1" in known_ig_ids
        mock_backfill_service._download_and_index.assert_called_once()

    async def test_skips_duplicates(self, mock_backfill_service):
        """Items already in known_ig_ids are skipped."""
        result = BackfillResult()
        known_ig_ids = {"existing_id"}

        mock_backfill_service._fetch_media_page = AsyncMock(
            return_value={
                "data": [
                    {
                        "id": "existing_id",
                        "media_type": "IMAGE",
                        "media_url": "https://example.com/img.jpg",
                    }
                ],
                "paging": {},
            }
        )

        await mock_backfill_service._backfill_feed(
            token="tok",
            ig_account_id="ig_123",
            username="user",
            limit=None,
            since=None,
            dry_run=False,
            known_ig_ids=known_ig_ids,
            storage_dir=Path("/tmp"),
            result=result,
        )

        assert result.skipped_duplicate == 1
        assert result.downloaded == 0

    async def test_handles_pagination(self, mock_backfill_service):
        """Multiple pages fetched via cursor."""
        result = BackfillResult()
        known_ig_ids = set()

        page1 = {
            "data": [
                {"id": "p1", "media_type": "IMAGE", "media_url": "https://a.com/1.jpg"}
            ],
            "paging": {"cursors": {"after": "cursor_abc"}, "next": "https://next"},
        }
        page2 = {
            "data": [
                {"id": "p2", "media_type": "IMAGE", "media_url": "https://a.com/2.jpg"}
            ],
            "paging": {},
        }

        mock_backfill_service._fetch_media_page = AsyncMock(side_effect=[page1, page2])
        mock_backfill_service._download_and_index = AsyncMock()

        await mock_backfill_service._backfill_feed(
            token="tok",
            ig_account_id="ig_123",
            username="user",
            limit=None,
            since=None,
            dry_run=False,
            known_ig_ids=known_ig_ids,
            storage_dir=Path("/tmp"),
            result=result,
        )

        assert result.downloaded == 2
        assert result.total_api_items == 2
        assert mock_backfill_service._fetch_media_page.call_count == 2

    async def test_respects_limit(self, mock_backfill_service):
        """Stops after limit items."""
        result = BackfillResult()
        known_ig_ids = set()

        mock_backfill_service._fetch_media_page = AsyncMock(
            return_value={
                "data": [
                    {
                        "id": "a",
                        "media_type": "IMAGE",
                        "media_url": "https://a.com/1.jpg",
                    },
                    {
                        "id": "b",
                        "media_type": "IMAGE",
                        "media_url": "https://a.com/2.jpg",
                    },
                    {
                        "id": "c",
                        "media_type": "IMAGE",
                        "media_url": "https://a.com/3.jpg",
                    },
                ],
                "paging": {"cursors": {"after": "x"}, "next": "https://next"},
            }
        )
        mock_backfill_service._download_and_index = AsyncMock()

        await mock_backfill_service._backfill_feed(
            token="tok",
            ig_account_id="ig_123",
            username="user",
            limit=2,
            since=None,
            dry_run=False,
            known_ig_ids=known_ig_ids,
            storage_dir=Path("/tmp"),
            result=result,
        )

        assert result.downloaded == 2

    async def test_respects_since_filter(self, mock_backfill_service):
        """Stops at items older than since."""
        result = BackfillResult()
        known_ig_ids = set()

        mock_backfill_service._fetch_media_page = AsyncMock(
            return_value={
                "data": [
                    {
                        "id": "new",
                        "media_type": "IMAGE",
                        "media_url": "https://a.com/1.jpg",
                        "timestamp": "2025-06-01T12:00:00+0000",
                    },
                    {
                        "id": "old",
                        "media_type": "IMAGE",
                        "media_url": "https://a.com/2.jpg",
                        "timestamp": "2024-01-01T12:00:00+0000",
                    },
                ],
                "paging": {},
            }
        )
        mock_backfill_service._download_and_index = AsyncMock()

        since = datetime(2025, 1, 1)
        await mock_backfill_service._backfill_feed(
            token="tok",
            ig_account_id="ig_123",
            username="user",
            limit=None,
            since=since,
            dry_run=False,
            known_ig_ids=known_ig_ids,
            storage_dir=Path("/tmp"),
            result=result,
        )

        # Should download the new one but stop at the old one
        assert result.downloaded == 1

    async def test_dry_run_no_download(self, mock_backfill_service):
        """dry_run=True counts but doesn't download."""
        result = BackfillResult(dry_run=True)
        known_ig_ids = set()

        mock_backfill_service._fetch_media_page = AsyncMock(
            return_value={
                "data": [
                    {
                        "id": "dry_1",
                        "media_type": "IMAGE",
                        "media_url": "https://a.com/1.jpg",
                    }
                ],
                "paging": {},
            }
        )
        mock_backfill_service._download_and_index = AsyncMock()

        await mock_backfill_service._backfill_feed(
            token="tok",
            ig_account_id="ig_123",
            username="user",
            limit=None,
            since=None,
            dry_run=True,
            known_ig_ids=known_ig_ids,
            storage_dir=Path("/tmp"),
            result=result,
        )

        assert result.downloaded == 1
        assert "dry_1" in known_ig_ids
        mock_backfill_service._download_and_index.assert_not_called()

    async def test_handles_videos(self, mock_backfill_service):
        """VIDEO items are processed."""
        result = BackfillResult()
        known_ig_ids = set()

        mock_backfill_service._fetch_media_page = AsyncMock(
            return_value={
                "data": [
                    {
                        "id": "vid_1",
                        "media_type": "VIDEO",
                        "media_url": "https://a.com/v.mp4",
                    }
                ],
                "paging": {},
            }
        )
        mock_backfill_service._download_and_index = AsyncMock()

        await mock_backfill_service._backfill_feed(
            token="tok",
            ig_account_id="ig_123",
            username="user",
            limit=None,
            since=None,
            dry_run=False,
            known_ig_ids=known_ig_ids,
            storage_dir=Path("/tmp"),
            result=result,
        )

        assert result.downloaded == 1

    async def test_empty_response(self, mock_backfill_service):
        """Empty data array produces no items."""
        result = BackfillResult()

        mock_backfill_service._fetch_media_page = AsyncMock(
            return_value={"data": [], "paging": {}}
        )

        await mock_backfill_service._backfill_feed(
            token="tok",
            ig_account_id="ig_123",
            username="user",
            limit=None,
            since=None,
            dry_run=False,
            known_ig_ids=set(),
            storage_dir=Path("/tmp"),
            result=result,
        )

        assert result.total_api_items == 0
        assert result.downloaded == 0


# ==================== Carousel Tests ====================


@pytest.mark.unit
@pytest.mark.asyncio
class TestBackfillCarousel:
    """Tests for carousel album expansion."""

    async def test_expands_children(self, mock_backfill_service):
        """CAROUSEL_ALBUM fetches children and processes each."""
        result = BackfillResult()
        known_ig_ids = set()

        carousel_item = {
            "id": "carousel_1",
            "media_type": "CAROUSEL_ALBUM",
            "caption": "My carousel",
            "permalink": "https://instagram.com/p/abc",
            "username": "testuser",
        }

        mock_backfill_service._fetch_carousel_children = AsyncMock(
            return_value={
                "data": [
                    {
                        "id": "child_1",
                        "media_type": "IMAGE",
                        "media_url": "https://a.com/c1.jpg",
                    },
                    {
                        "id": "child_2",
                        "media_type": "IMAGE",
                        "media_url": "https://a.com/c2.jpg",
                    },
                ]
            }
        )
        mock_backfill_service._download_and_index = AsyncMock()

        await mock_backfill_service._process_carousel(
            item=carousel_item,
            token="tok",
            username="testuser",
            dry_run=False,
            known_ig_ids=known_ig_ids,
            storage_dir=Path("/tmp"),
            result=result,
        )

        assert result.downloaded == 2
        assert result.total_api_items == 2

    async def test_inherits_caption(self, mock_backfill_service):
        """Children inherit parent caption/permalink/username."""
        result = BackfillResult()
        known_ig_ids = set()

        carousel_item = {
            "id": "carousel_2",
            "media_type": "CAROUSEL_ALBUM",
            "caption": "Parent caption",
            "permalink": "https://instagram.com/p/xyz",
            "username": "parent_user",
        }

        mock_backfill_service._fetch_carousel_children = AsyncMock(
            return_value={
                "data": [
                    {
                        "id": "child_a",
                        "media_type": "IMAGE",
                        "media_url": "https://a.com/a.jpg",
                    },
                ]
            }
        )
        mock_backfill_service._download_and_index = AsyncMock()

        await mock_backfill_service._process_carousel(
            item=carousel_item,
            token="tok",
            username="parent_user",
            dry_run=False,
            known_ig_ids=known_ig_ids,
            storage_dir=Path("/tmp"),
            result=result,
        )

        assert result.downloaded == 1

    async def test_child_failure_continues(self, mock_backfill_service):
        """One child fails, others still process."""
        result = BackfillResult()
        known_ig_ids = set()

        carousel_item = {
            "id": "carousel_3",
            "media_type": "CAROUSEL_ALBUM",
        }

        mock_backfill_service._fetch_carousel_children = AsyncMock(
            return_value={
                "data": [
                    {
                        "id": "good",
                        "media_type": "IMAGE",
                        "media_url": "https://a.com/g.jpg",
                    },
                    {
                        "id": "bad",
                        "media_type": "IMAGE",
                        "media_url": "https://a.com/b.jpg",
                    },
                ]
            }
        )
        mock_backfill_service._download_and_index = AsyncMock(
            side_effect=[None, Exception("Download error")]
        )

        await mock_backfill_service._process_carousel(
            item=carousel_item,
            token="tok",
            username="user",
            dry_run=False,
            known_ig_ids=known_ig_ids,
            storage_dir=Path("/tmp"),
            result=result,
        )

        assert result.downloaded == 1
        assert result.failed == 1

    async def test_carousel_api_error(self, mock_backfill_service):
        """API error fetching children counts as failed."""
        result = BackfillResult()

        mock_backfill_service._fetch_carousel_children = AsyncMock(
            side_effect=InstagramAPIError("API error")
        )

        await mock_backfill_service._process_carousel(
            item={"id": "carousel_err"},
            token="tok",
            username="user",
            dry_run=False,
            known_ig_ids=set(),
            storage_dir=Path("/tmp"),
            result=result,
        )

        assert result.failed == 1
        assert len(result.error_details) == 1


# ==================== Stories Tests ====================


@pytest.mark.unit
@pytest.mark.asyncio
class TestBackfillStories:
    """Tests for stories backfill."""

    async def test_fetches_live_stories(self, mock_backfill_service):
        """Calls stories endpoint and processes items."""
        result = BackfillResult()
        known_ig_ids = set()

        mock_backfill_service._fetch_stories = AsyncMock(
            return_value={
                "data": [
                    {
                        "id": "story_1",
                        "media_type": "IMAGE",
                        "media_url": "https://a.com/s.jpg",
                    }
                ]
            }
        )
        mock_backfill_service._download_and_index = AsyncMock()

        await mock_backfill_service._backfill_stories(
            token="tok",
            ig_account_id="ig_123",
            username="user",
            limit=None,
            dry_run=False,
            known_ig_ids=known_ig_ids,
            storage_dir=Path("/tmp"),
            result=result,
        )

        assert result.downloaded == 1
        assert result.total_api_items == 1

    async def test_empty_stories(self, mock_backfill_service):
        """No live stories returns gracefully."""
        result = BackfillResult()

        mock_backfill_service._fetch_stories = AsyncMock(return_value={"data": []})

        await mock_backfill_service._backfill_stories(
            token="tok",
            ig_account_id="ig_123",
            username="user",
            limit=None,
            dry_run=False,
            known_ig_ids=set(),
            storage_dir=Path("/tmp"),
            result=result,
        )

        assert result.total_api_items == 0

    async def test_api_error_handled(self, mock_backfill_service):
        """API error caught and logged, no crash."""
        result = BackfillResult()

        mock_backfill_service._fetch_stories = AsyncMock(
            side_effect=InstagramAPIError("Stories not available")
        )

        await mock_backfill_service._backfill_stories(
            token="tok",
            ig_account_id="ig_123",
            username="user",
            limit=None,
            dry_run=False,
            known_ig_ids=set(),
            storage_dir=Path("/tmp"),
            result=result,
        )

        assert result.total_api_items == 0
        assert result.failed == 0


# ==================== Download Tests ====================


@pytest.mark.unit
@pytest.mark.asyncio
class TestDownloadMedia:
    """Tests for _download_media."""

    async def test_success(self, mock_backfill_service):
        """Returns bytes on HTTP 200."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"image_bytes"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            content = await mock_backfill_service._download_media(
                "https://example.com/img.jpg", "media_123"
            )

        assert content == b"image_bytes"

    async def test_expired_url_403(self, mock_backfill_service):
        """HTTP 403 raises BackfillMediaExpiredError."""
        mock_response = Mock()
        mock_response.status_code = 403

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(BackfillMediaExpiredError):
                await mock_backfill_service._download_media(
                    "https://example.com/img.jpg", "media_expired"
                )

    async def test_expired_url_410(self, mock_backfill_service):
        """HTTP 410 raises BackfillMediaExpiredError."""
        mock_response = Mock()
        mock_response.status_code = 410

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(BackfillMediaExpiredError):
                await mock_backfill_service._download_media(
                    "https://example.com/img.jpg", "media_gone"
                )

    async def test_not_found_404(self, mock_backfill_service):
        """HTTP 404 raises BackfillMediaNotFoundError."""
        mock_response = Mock()
        mock_response.status_code = 404

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(BackfillMediaNotFoundError):
                await mock_backfill_service._download_media(
                    "https://example.com/img.jpg", "media_missing"
                )

    async def test_network_error(self, mock_backfill_service):
        """httpx.RequestError raises BackfillError."""
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.RequestError("Connection reset")
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(BackfillError, match="Network error"):
                await mock_backfill_service._download_media(
                    "https://example.com/img.jpg", "media_net_err"
                )

    async def test_empty_response(self, mock_backfill_service):
        """Empty body raises BackfillError."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b""

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(BackfillError, match="Empty response"):
                await mock_backfill_service._download_media(
                    "https://example.com/img.jpg", "media_empty"
                )


# ==================== Index & Storage Tests ====================


@pytest.mark.unit
@pytest.mark.asyncio
class TestDownloadAndIndex:
    """Tests for _download_and_index."""

    async def test_creates_record(self, mock_backfill_service, tmp_path):
        """media_repo.create() called with correct args."""
        mock_backfill_service._download_media = AsyncMock(return_value=b"test_bytes")
        mock_media_item = MagicMock()
        mock_backfill_service.media_repo.create.return_value = mock_media_item

        await mock_backfill_service._download_and_index(
            ig_media_id="ig_12345",
            media_url="https://example.com/photo.jpg",
            media_type="IMAGE",
            item={"timestamp": "2025-06-15T10:30:00+0000"},
            username="testuser",
            storage_dir=tmp_path,
            source_label="feed",
        )

        mock_backfill_service.media_repo.create.assert_called_once()
        call_kwargs = mock_backfill_service.media_repo.create.call_args[1]
        assert call_kwargs["source_type"] == "instagram_backfill"
        assert call_kwargs["source_identifier"] == "ig_12345"
        assert call_kwargs["category"] == "instagram_backfill"
        assert "ig_12345" in call_kwargs["file_name"]

        # Verify backfill tracking fields set on returned object
        assert mock_media_item.instagram_media_id == "ig_12345"
        assert mock_media_item.backfilled_at is not None

    async def test_filename_format(self, mock_backfill_service, tmp_path):
        """Filename follows YYYYMMDD_HHMMSS_{id}.{ext} format."""
        mock_backfill_service._download_media = AsyncMock(return_value=b"bytes")
        mock_backfill_service.media_repo.create.return_value = MagicMock()

        await mock_backfill_service._download_and_index(
            ig_media_id="ig_99999",
            media_url="https://example.com/photo.jpg",
            media_type="IMAGE",
            item={"timestamp": "2025-03-15T14:30:45+0000"},
            username="user",
            storage_dir=tmp_path,
            source_label="feed",
        )

        call_kwargs = mock_backfill_service.media_repo.create.call_args[1]
        filename = call_kwargs["file_name"]
        assert filename == "20250315_143045_ig_99999.jpg"


# ==================== Helper Tests ====================


@pytest.mark.unit
class TestHelpers:
    """Tests for helper methods."""

    def test_get_extension_for_type_image(self, mock_backfill_service):
        """Returns .jpg for IMAGE."""
        ext = mock_backfill_service._get_extension_for_type(
            "IMAGE", "https://example.com/photo?query=1"
        )
        assert ext == ".jpg"

    def test_get_extension_for_type_video(self, mock_backfill_service):
        """Returns .mp4 for VIDEO."""
        ext = mock_backfill_service._get_extension_for_type(
            "VIDEO", "https://example.com/video?query=1"
        )
        assert ext == ".mp4"

    def test_get_extension_from_url(self, mock_backfill_service):
        """Extracts extension from URL when available."""
        ext = mock_backfill_service._get_extension_for_type(
            "IMAGE", "https://example.com/photo.png?token=abc"
        )
        assert ext == ".png"

    def test_is_after_date_newer(self, mock_backfill_service):
        """Returns True for items newer than since."""
        item = {"timestamp": "2025-06-01T12:00:00+0000"}
        since = datetime(2025, 1, 1)
        assert mock_backfill_service._is_after_date(item, since) is True

    def test_is_after_date_older(self, mock_backfill_service):
        """Returns False for items older than since."""
        item = {"timestamp": "2024-01-01T12:00:00+0000"}
        since = datetime(2025, 1, 1)
        assert mock_backfill_service._is_after_date(item, since) is False

    def test_is_after_date_no_timestamp(self, mock_backfill_service):
        """Returns True when item has no timestamp."""
        item = {}
        since = datetime(2025, 1, 1)
        assert mock_backfill_service._is_after_date(item, since) is True

    @patch("src.services.integrations.instagram_backfill.settings")
    def test_get_storage_dir(self, mock_settings, mock_backfill_service):
        """Returns MEDIA_DIR/instagram_backfill."""
        mock_settings.MEDIA_DIR = "/home/pi/media"
        result = mock_backfill_service._get_storage_dir()
        assert result == Path("/home/pi/media/instagram_backfill")


# ==================== Status Tests ====================


@pytest.mark.unit
class TestBackfillStatus:
    """Tests for get_backfill_status."""

    def test_no_runs(self, mock_backfill_service):
        """Returns total_backfilled=0 and last_run=None when no history."""
        mock_backfill_service.service_run_repo.get_recent_runs.return_value = []
        mock_backfill_service.media_repo.get_backfilled_instagram_media_ids.return_value = set()

        status = mock_backfill_service.get_backfill_status()

        assert status["total_backfilled"] == 0
        assert status["last_run"] is None

    def test_with_history(self, mock_backfill_service):
        """Returns correct counts and last run details."""
        mock_run = MagicMock()
        mock_run.started_at = datetime(2025, 6, 1, 12, 0)
        mock_run.completed_at = datetime(2025, 6, 1, 12, 5)
        mock_run.success = True
        mock_run.result_summary = {"downloaded": 10}
        mock_run.triggered_by = "cli"

        mock_backfill_service.service_run_repo.get_recent_runs.return_value = [mock_run]
        mock_backfill_service.media_repo.get_backfilled_instagram_media_ids.return_value = {
            "a",
            "b",
            "c",
        }

        status = mock_backfill_service.get_backfill_status()

        assert status["total_backfilled"] == 3
        assert status["last_run"]["success"] is True
        assert status["last_run"]["triggered_by"] == "cli"


# ==================== Process Item Error Handling ====================


@pytest.mark.unit
@pytest.mark.asyncio
class TestProcessMediaItemErrors:
    """Tests for error handling in _process_media_item."""

    async def test_unsupported_media_type(self, mock_backfill_service):
        """Unsupported media types are counted."""
        result = BackfillResult()
        item = {"id": "unsup", "media_type": "UNKNOWN_TYPE"}

        await mock_backfill_service._process_media_item(
            item=item,
            token="tok",
            username="user",
            dry_run=False,
            known_ig_ids=set(),
            storage_dir=Path("/tmp"),
            result=result,
            source_label="feed",
        )

        assert result.skipped_unsupported == 1

    async def test_no_media_url(self, mock_backfill_service):
        """Items without media_url count as failed."""
        result = BackfillResult()
        item = {"id": "no_url", "media_type": "IMAGE"}

        await mock_backfill_service._process_media_item(
            item=item,
            token="tok",
            username="user",
            dry_run=False,
            known_ig_ids=set(),
            storage_dir=Path("/tmp"),
            result=result,
            source_label="feed",
        )

        assert result.failed == 1
        assert len(result.error_details) == 1

    async def test_download_error_continues(self, mock_backfill_service):
        """Download error for one item doesn't stop processing."""
        result = BackfillResult()
        mock_backfill_service._download_and_index = AsyncMock(
            side_effect=BackfillMediaExpiredError("Expired")
        )

        item = {"id": "exp", "media_type": "IMAGE", "media_url": "https://a.com/x.jpg"}

        await mock_backfill_service._process_media_item(
            item=item,
            token="tok",
            username="user",
            dry_run=False,
            known_ig_ids=set(),
            storage_dir=Path("/tmp"),
            result=result,
            source_label="feed",
        )

        assert result.failed == 1
        assert result.downloaded == 0
