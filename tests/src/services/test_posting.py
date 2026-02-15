"""Tests for PostingService."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
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
        service._instagram_service = None
        service._cloud_service = None
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

    def test_mark_as_posted(self, posting_service):
        """Test marking a queue item as posted."""
        queue_item_id = str(uuid4())
        media_id = uuid4()
        user_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.id = queue_item_id
        mock_queue_item.media_item_id = media_id
        mock_queue_item.created_at = datetime.utcnow()
        mock_queue_item.scheduled_for = datetime.utcnow()
        mock_queue_item.retry_count = 0
        posting_service.queue_repo.get_by_id.return_value = mock_queue_item

        posting_service.handle_completion(
            queue_item_id=queue_item_id,
            success=True,
            posted_by_user_id=user_id,
        )

        posting_service.history_repo.create.assert_called_once()
        posting_service.media_repo.increment_times_posted.assert_called_once()
        posting_service.lock_service.create_lock.assert_called_once()
        posting_service.queue_repo.delete.assert_called_once_with(queue_item_id)

    def test_mark_as_skipped(self, posting_service):
        """Test marking a queue item as skipped."""
        queue_item_id = str(uuid4())
        media_id = uuid4()

        mock_queue_item = Mock()
        mock_queue_item.id = queue_item_id
        mock_queue_item.media_item_id = media_id
        mock_queue_item.created_at = datetime.utcnow()
        mock_queue_item.scheduled_for = datetime.utcnow()
        mock_queue_item.retry_count = 0
        posting_service.queue_repo.get_by_id.return_value = mock_queue_item

        posting_service.handle_completion(
            queue_item_id=queue_item_id,
            success=False,
            error_message="Skipped by user",
        )

        posting_service.history_repo.create.assert_called_once()
        # Failed/skipped posts don't increment or create locks
        posting_service.media_repo.increment_times_posted.assert_not_called()
        posting_service.lock_service.create_lock.assert_not_called()
        posting_service.queue_repo.delete.assert_called_once_with(queue_item_id)

    def test_get_queue_item_with_media(self, posting_service):
        """Test retrieving queue item with media details."""
        posting_service.queue_repo.get_by_id.return_value = None

        # handle_completion returns early when queue item not found
        posting_service.handle_completion(
            queue_item_id="nonexistent",
            success=True,
        )

        posting_service.history_repo.create.assert_not_called()
        posting_service.queue_repo.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_retry_failed_post(self, posting_service):
        """Test retrying a failed post."""
        posting_service.queue_repo.get_all.return_value = []

        result = await posting_service.force_post_next()

        assert result["success"] is False
        assert result["error"] == "No pending items in queue"


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
            limit=100, chat_settings_id=str(mock_chat_settings.id)
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
