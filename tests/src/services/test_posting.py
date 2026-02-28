"""Tests for PostingService."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from contextlib import contextmanager
from uuid import uuid4

from src.services.core.posting import PostingService


@contextmanager
def mock_track_execution(*args, **kwargs):
    """Mock context manager for track_execution."""
    yield "mock_run_id"


@pytest.fixture
def posting_service():
    """Create PostingService with mocked dependencies."""
    with patch.object(PostingService, "__init__", lambda self: None):
        service = PostingService()
        service.queue_repo = Mock()
        service.media_repo = Mock()
        service.history_repo = Mock()
        service.telegram_service = Mock()
        service.lock_service = Mock()
        service.settings_service = Mock()
        service.service_run_repo = Mock()
        service.service_name = "PostingService"
        service.track_execution = mock_track_execution
        service.set_result_summary = Mock()
        return service


@pytest.mark.unit
class TestPostingService:
    """Test suite for PostingService."""

    @pytest.mark.asyncio
    async def test_process_pending_queue_no_items(self, posting_service):
        """Test processing queue when no items are pending."""
        posting_service.telegram_service.is_paused = False
        posting_service.queue_repo.get_pending.return_value = []

        result = await posting_service.process_pending_posts()

        assert result["processed"] == 0

    @pytest.mark.asyncio
    async def test_retry_failed_post(self, posting_service):
        """Test retrying a failed post."""
        posting_service.queue_repo.get_all.return_value = []

        result = await posting_service.force_post_next()

        assert result["success"] is False
        assert result["error"] == "No pending items in queue"


@pytest.mark.unit
class TestBuildForcePostResult:
    """Tests for _build_force_post_result helper."""

    def test_status_only(self, posting_service):
        """Build result with status only — defaults filled in."""
        result = posting_service._build_force_post_result("empty")

        assert result["success"] is False
        assert result["queue_item_id"] is None
        assert result["media_item"] is None
        assert result["shifted_count"] == 0
        assert result["error"] is None

    def test_success_status(self, posting_service):
        """Build result with success status — success is True."""
        result = posting_service._build_force_post_result("success")

        assert result["success"] is True

    def test_with_kwargs(self, posting_service):
        """Build result with extra kwargs — merged into result."""
        result = posting_service._build_force_post_result(
            "success",
            queue_item_id="abc-123",
            shifted_count=3,
        )

        assert result["success"] is True
        assert result["queue_item_id"] == "abc-123"
        assert result["shifted_count"] == 3

    def test_with_run_id_sets_summary(self, posting_service):
        """Build result with run_id — calls set_result_summary."""
        mock_media = Mock(file_name="test.jpg")
        result = posting_service._build_force_post_result(
            "success",
            run_id="run-xyz",
            queue_item_id="abc-123",
            media_item=mock_media,
            shifted_count=2,
        )

        assert result["success"] is True
        posting_service.set_result_summary.assert_called_once()
        summary = posting_service.set_result_summary.call_args[0][1]
        assert summary["media_file_name"] == "test.jpg"
        assert summary["shifted_count"] == 2

    def test_without_run_id_skips_summary(self, posting_service):
        """Build result without run_id — does not call set_result_summary."""
        posting_service._build_force_post_result("empty")

        posting_service.set_result_summary.assert_not_called()

    def test_error_kwarg_overrides_default(self, posting_service):
        """Error kwarg overrides default None."""
        result = posting_service._build_force_post_result(
            "error", error="Something broke"
        )

        assert result["error"] == "Something broke"
        assert result["success"] is False


@pytest.mark.unit
class TestProcessSinglePending:
    """Tests for _process_single_pending helper."""

    @pytest.mark.asyncio
    async def test_media_not_found_returns_none(self, posting_service):
        """Returns None when media item is not found."""
        queue_item = Mock(media_item_id=uuid4())
        posting_service.media_repo.get_by_id.return_value = None

        result = await posting_service._process_single_pending(queue_item)

        assert result is None

    @pytest.mark.asyncio
    async def test_routes_post_when_media_found(self, posting_service):
        """Delegates to _route_post when media is found."""
        queue_item = Mock(media_item_id=uuid4())
        media_item = Mock(file_name="test.jpg")
        posting_service.media_repo.get_by_id.return_value = media_item
        posting_service._route_post = AsyncMock(
            return_value={"method": "telegram_manual", "success": True}
        )

        result = await posting_service._process_single_pending(queue_item)

        assert result == {"method": "telegram_manual", "success": True}
        posting_service._route_post.assert_called_once_with(queue_item, media_item)


@pytest.mark.unit
class TestPostingServiceTenantSupport:
    """Tests for per-tenant posting behavior."""

    @pytest.mark.asyncio
    async def test_process_pending_posts_with_tenant_chat_id(self, posting_service):
        """process_pending_posts with telegram_chat_id uses per-tenant pause state."""
        mock_chat_settings = Mock()
        mock_chat_settings.is_paused = False
        mock_chat_settings.id = uuid4()
        posting_service.settings_service.get_settings.return_value = mock_chat_settings
        posting_service.queue_repo.get_pending.return_value = []

        result = await posting_service.process_pending_posts(telegram_chat_id=-200456)

        posting_service.settings_service.get_settings.assert_called_with(-200456)
        assert result["processed"] == 0

    @pytest.mark.asyncio
    async def test_process_pending_posts_tenant_paused(self, posting_service):
        """process_pending_posts returns paused result when tenant is paused."""
        mock_chat_settings = Mock()
        mock_chat_settings.is_paused = True
        posting_service.settings_service.get_settings.return_value = mock_chat_settings

        result = await posting_service.process_pending_posts(telegram_chat_id=-200456)

        assert result["paused"] is True
        assert result["processed"] == 0
        posting_service.queue_repo.get_pending.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_pending_posts_falls_back_to_global(self, posting_service):
        """process_pending_posts without telegram_chat_id uses global is_paused."""
        posting_service.telegram_service.is_paused = False
        posting_service.queue_repo.get_pending.return_value = []

        result = await posting_service.process_pending_posts()

        posting_service.settings_service.get_settings.assert_not_called()
        assert result["processed"] == 0

    @pytest.mark.asyncio
    async def test_process_pending_posts_passes_chat_settings_id_to_queue(
        self, posting_service
    ):
        """process_pending_posts threads chat_settings_id to queue_repo.get_pending."""
        mock_chat_settings = Mock()
        mock_chat_settings.is_paused = False
        mock_chat_settings.id = uuid4()
        posting_service.settings_service.get_settings.return_value = mock_chat_settings
        posting_service.queue_repo.get_pending.return_value = []

        await posting_service.process_pending_posts(telegram_chat_id=-200456)

        posting_service.queue_repo.get_pending.assert_called_once_with(
            limit=1, chat_settings_id=str(mock_chat_settings.id)
        )

    @patch("src.services.core.posting.settings")
    def test_get_chat_settings_with_explicit_chat_id(
        self, mock_settings, posting_service
    ):
        """_get_chat_settings with explicit chat_id uses that id."""
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = -100123
        posting_service._get_chat_settings(-200456)

        posting_service.settings_service.get_settings.assert_called_with(-200456)

    @patch("src.services.core.posting.settings")
    def test_get_chat_settings_falls_back_to_admin(
        self, mock_settings, posting_service
    ):
        """_get_chat_settings without chat_id falls back to ADMIN_TELEGRAM_CHAT_ID."""
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = -100123
        posting_service._get_chat_settings()

        posting_service.settings_service.get_settings.assert_called_with(-100123)
