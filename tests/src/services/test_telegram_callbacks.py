"""Tests for TelegramCallbackHandlers (extracted from test_telegram_service.py)."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from uuid import uuid4

from src.services.core.telegram_service import TelegramService
from src.services.core.telegram_callbacks import TelegramCallbackHandlers


@pytest.fixture
def mock_callback_handlers():
    """Create TelegramCallbackHandlers with mocked service dependencies."""
    with (
        patch("src.services.core.telegram_service.settings") as mock_settings,
        patch(
            "src.services.core.telegram_service.UserRepository"
        ) as mock_user_repo_class,
        patch(
            "src.services.core.telegram_service.QueueRepository"
        ) as mock_queue_repo_class,
        patch(
            "src.services.core.telegram_service.MediaRepository"
        ) as mock_media_repo_class,
        patch(
            "src.services.core.telegram_service.HistoryRepository"
        ) as mock_history_repo_class,
        patch(
            "src.services.core.telegram_service.LockRepository"
        ) as mock_lock_repo_class,
        patch(
            "src.services.core.telegram_service.MediaLockService"
        ) as mock_lock_service_class,
        patch(
            "src.services.core.telegram_service.InteractionService"
        ) as mock_interaction_service_class,
        patch(
            "src.services.core.telegram_service.SettingsService"
        ) as mock_settings_service_class,
        patch(
            "src.services.core.telegram_service.InstagramAccountService"
        ) as mock_ig_account_service_class,
    ):
        mock_settings.TELEGRAM_BOT_TOKEN = "123456:ABC-DEF1234ghIkl"
        mock_settings.TELEGRAM_CHANNEL_ID = -1001234567890
        mock_settings.CAPTION_STYLE = "enhanced"
        mock_settings.SEND_LIFECYCLE_NOTIFICATIONS = False

        service = TelegramService()

        # Make repos accessible for test assertions
        service.user_repo = mock_user_repo_class.return_value
        service.queue_repo = mock_queue_repo_class.return_value
        service.media_repo = mock_media_repo_class.return_value
        service.history_repo = mock_history_repo_class.return_value
        service.lock_repo = mock_lock_repo_class.return_value
        service.lock_service = mock_lock_service_class.return_value
        service.interaction_service = mock_interaction_service_class.return_value
        service.settings_service = mock_settings_service_class.return_value
        service.ig_account_service = mock_ig_account_service_class.return_value

        handlers = TelegramCallbackHandlers(service)
        yield handlers


@pytest.mark.unit
@pytest.mark.asyncio
class TestRejectConfirmation:
    """Tests for reject confirmation flow."""

    async def test_reject_shows_confirmation_dialog(self, mock_callback_handlers):
        """Test that clicking Reject shows confirmation dialog instead of immediate rejection."""
        handlers = mock_callback_handlers
        service = handlers.service
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()
        service.queue_repo.get_by_id.return_value = mock_queue_item

        mock_media_item = Mock()
        mock_media_item.file_name = "test_image.jpg"
        service.media_repo.get_by_id.return_value = mock_media_item

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "testuser"

        mock_query = AsyncMock()

        await handlers.handle_reject_confirmation(queue_id, mock_user, mock_query)

        # Should edit message with confirmation
        mock_query.edit_message_caption.assert_called_once()
        call_kwargs = mock_query.edit_message_caption.call_args

        # Check caption contains warning text
        caption = call_kwargs.kwargs.get("caption") or call_kwargs.args[0]
        assert "Are you sure?" in caption
        assert "test_image.jpg" in caption
        assert "cannot be undone" in caption

        # Check keyboard has confirm/cancel buttons
        reply_markup = call_kwargs.kwargs.get("reply_markup")
        assert reply_markup is not None

    async def test_reject_confirmation_not_found(self, mock_callback_handlers):
        """Test reject confirmation handles missing queue item."""
        handlers = mock_callback_handlers
        service = handlers.service
        queue_id = str(uuid4())

        service.queue_repo.get_by_id.return_value = None

        mock_user = Mock()
        mock_query = AsyncMock()

        await handlers.handle_reject_confirmation(queue_id, mock_user, mock_query)

        mock_query.edit_message_caption.assert_called_once()
        call_args = mock_query.edit_message_caption.call_args
        assert "not found" in str(call_args)

    async def test_confirm_reject_creates_permanent_lock(self, mock_callback_handlers):
        """Test that confirming rejection creates a permanent lock."""
        handlers = mock_callback_handlers
        service = handlers.service
        queue_id = str(uuid4())
        media_id = uuid4()

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = media_id
        mock_queue_item.created_at = datetime.utcnow()
        mock_queue_item.scheduled_for = datetime.utcnow()
        service.queue_repo.get_by_id.return_value = mock_queue_item

        mock_media_item = Mock()
        mock_media_item.file_name = "rejected_image.jpg"
        service.media_repo.get_by_id.return_value = mock_media_item

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "rejecter"
        mock_user.telegram_first_name = "Test"

        mock_query = AsyncMock()

        await handlers.handle_rejected(queue_id, mock_user, mock_query)

        # Should create permanent lock
        service.lock_service.create_permanent_lock.assert_called_once()
        call_args = service.lock_service.create_permanent_lock.call_args
        assert str(media_id) in str(call_args)

        # Should delete from queue
        service.queue_repo.delete.assert_called_once_with(queue_id)

        # Should create history record with status='rejected'
        service.history_repo.create.assert_called_once()
        history_call = service.history_repo.create.call_args
        assert history_call.kwargs.get("status") == "rejected"

    async def test_cancel_reject_restores_original_buttons(
        self, mock_callback_handlers
    ):
        """Test that canceling rejection restores the original message."""
        handlers = mock_callback_handlers
        service = handlers.service
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()
        service.queue_repo.get_by_id.return_value = mock_queue_item

        mock_media_item = Mock()
        mock_media_item.file_name = "test.jpg"
        mock_media_item.title = "Test"
        mock_media_item.caption = None
        mock_media_item.link_url = None
        mock_media_item.tags = []
        service.media_repo.get_by_id.return_value = mock_media_item

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "canceler"
        mock_user.telegram_first_name = "Test"

        mock_query = AsyncMock()

        await handlers.handle_cancel_reject(queue_id, mock_user, mock_query)

        # Should restore original message
        mock_query.edit_message_caption.assert_called_once()

        # Queue item should NOT be deleted
        service.queue_repo.delete.assert_not_called()

        # No lock should be created
        service.lock_service.create_permanent_lock.assert_not_called()


@pytest.mark.skip(reason="Needs SettingsService and SchedulerService mocks - TODO")
@pytest.mark.unit
@pytest.mark.asyncio
class TestResumeCallbacks:
    """Tests for resume callback handlers."""

    async def test_resume_reschedule(self, mock_callback_handlers):
        """Test resume:reschedule reschedules overdue posts."""
        handlers = mock_callback_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "testuser"

        service.set_paused(True)

        # Create overdue item
        overdue_item = Mock()
        overdue_item.id = uuid4()
        overdue_item.scheduled_for = datetime(2020, 1, 1, 12, 0)

        service.queue_repo.get_all.return_value = [overdue_item]

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        await handlers.handle_resume_callback("reschedule", mock_user, mock_query)

        # Should be resumed
        assert service.is_paused is False

        # Should reschedule the item
        service.queue_repo.update_scheduled_time.assert_called_once()

        # Should show success message
        mock_query.edit_message_text.assert_called_once()
        call_args = mock_query.edit_message_text.call_args
        assert "Rescheduled 1 overdue posts" in call_args.args[0]

    async def test_resume_clear(self, mock_callback_handlers):
        """Test resume:clear clears overdue posts."""
        handlers = mock_callback_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "testuser"

        service.set_paused(True)

        # Create overdue and future items
        overdue_item = Mock()
        overdue_item.id = uuid4()
        overdue_item.scheduled_for = datetime(2020, 1, 1, 12, 0)

        future_item = Mock()
        future_item.id = uuid4()
        future_item.scheduled_for = datetime(2030, 1, 1, 12, 0)

        service.queue_repo.get_all.return_value = [overdue_item, future_item]

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        await handlers.handle_resume_callback("clear", mock_user, mock_query)

        # Should be resumed
        assert service.is_paused is False

        # Should delete the overdue item
        service.queue_repo.delete.assert_called_once_with(str(overdue_item.id))

        # Should show success message
        call_args = mock_query.edit_message_text.call_args
        assert "Cleared 1 overdue posts" in call_args.args[0]
        assert "1 scheduled posts remaining" in call_args.args[0]

    async def test_resume_force(self, mock_callback_handlers):
        """Test resume:force resumes without handling overdue."""
        handlers = mock_callback_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "testuser"

        service.set_paused(True)

        overdue_item = Mock()
        overdue_item.scheduled_for = datetime(2020, 1, 1, 12, 0)

        service.queue_repo.get_all.return_value = [overdue_item]

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        await handlers.handle_resume_callback("force", mock_user, mock_query)

        # Should be resumed
        assert service.is_paused is False

        # Should NOT delete or reschedule anything
        service.queue_repo.delete.assert_not_called()
        service.queue_repo.update_scheduled_time.assert_not_called()

        call_args = mock_query.edit_message_text.call_args
        assert "overdue posts will be processed immediately" in call_args.args[0]


@pytest.mark.unit
@pytest.mark.asyncio
class TestResetCallbacks:
    """Tests for reset callback handlers (formerly clear)."""

    async def test_reset_confirm(self, mock_callback_handlers):
        """Test reset:confirm deletes all pending posts."""
        handlers = mock_callback_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "testuser"

        # Create mock queue items
        item1 = Mock()
        item1.id = uuid4()
        item2 = Mock()
        item2.id = uuid4()

        service.queue_repo.get_all.return_value = [item1, item2]

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        await handlers.handle_reset_callback("confirm", mock_user, mock_query)

        # Should delete both items
        assert service.queue_repo.delete.call_count == 2

        call_args = mock_query.edit_message_text.call_args
        assert "Queue Cleared" in call_args.args[0]
        assert "Removed 2 pending posts" in call_args.args[0]

    async def test_reset_cancel(self, mock_callback_handlers):
        """Test reset:cancel does not delete anything."""
        handlers = mock_callback_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "testuser"

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        await handlers.handle_reset_callback("cancel", mock_user, mock_query)

        # Should NOT delete anything
        service.queue_repo.delete.assert_not_called()

        call_args = mock_query.edit_message_text.call_args
        assert "Cancelled" in call_args.args[0]


@pytest.mark.unit
@pytest.mark.asyncio
class TestVerbosePostedSkipped:
    """Tests for verbose toggle in posted/skipped confirmations."""

    async def test_posted_verbose_on_shows_marked_as_posted(
        self, mock_callback_handlers
    ):
        """Test verbose=True shows 'Marked as posted by' message."""
        handlers = mock_callback_handlers
        service = handlers.service
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()
        mock_queue_item.created_at = datetime.utcnow()
        mock_queue_item.scheduled_for = datetime.utcnow()
        service.queue_repo.get_by_id.return_value = mock_queue_item

        mock_media = Mock()
        mock_media.file_name = "test.jpg"
        service.media_repo.get_by_id.return_value = mock_media

        # Verbose ON
        mock_settings = Mock()
        mock_settings.show_verbose_notifications = True
        service.settings_service.get_settings.return_value = mock_settings

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "poster"
        mock_user.telegram_first_name = "Test"

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        await handlers.handle_posted(queue_id, mock_user, mock_query)

        caption = (
            mock_query.edit_message_caption.call_args.kwargs.get("caption")
            or mock_query.edit_message_caption.call_args.args[0]
        )
        assert "Marked as posted" in caption
        assert "@poster" in caption

    async def test_posted_verbose_off_shows_posted_by(self, mock_callback_handlers):
        """Test verbose=False shows shorter 'Posted by' message."""
        handlers = mock_callback_handlers
        service = handlers.service
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()
        mock_queue_item.created_at = datetime.utcnow()
        mock_queue_item.scheduled_for = datetime.utcnow()
        service.queue_repo.get_by_id.return_value = mock_queue_item

        mock_media = Mock()
        mock_media.file_name = "test.jpg"
        service.media_repo.get_by_id.return_value = mock_media

        # Verbose OFF
        mock_settings = Mock()
        mock_settings.show_verbose_notifications = False
        service.settings_service.get_settings.return_value = mock_settings

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "poster"
        mock_user.telegram_first_name = "Test"

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        await handlers.handle_posted(queue_id, mock_user, mock_query)

        caption = (
            mock_query.edit_message_caption.call_args.kwargs.get("caption")
            or mock_query.edit_message_caption.call_args.args[0]
        )
        assert "Marked as posted" not in caption
        assert "Posted by @poster" in caption

    async def test_skipped_always_shows_user(self, mock_callback_handlers):
        """Test skipped always shows user regardless of verbose."""
        handlers = mock_callback_handlers
        service = handlers.service
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()
        mock_queue_item.created_at = datetime.utcnow()
        mock_queue_item.scheduled_for = datetime.utcnow()
        service.queue_repo.get_by_id.return_value = mock_queue_item

        mock_media = Mock()
        mock_media.file_name = "test.jpg"
        service.media_repo.get_by_id.return_value = mock_media

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "skipper"
        mock_user.telegram_first_name = "Test"

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        await handlers.handle_skipped(queue_id, mock_user, mock_query)

        caption = (
            mock_query.edit_message_caption.call_args.kwargs.get("caption")
            or mock_query.edit_message_caption.call_args.args[0]
        )
        assert "Skipped by @skipper" in caption


@pytest.mark.unit
@pytest.mark.asyncio
class TestVerboseRejected:
    """Tests for verbose toggle in rejected confirmation."""

    async def test_rejected_verbose_on_shows_full_detail(self, mock_callback_handlers):
        """Test verbose=True shows full rejection message with file info."""
        handlers = mock_callback_handlers
        service = handlers.service
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()
        mock_queue_item.created_at = datetime.utcnow()
        mock_queue_item.scheduled_for = datetime.utcnow()
        service.queue_repo.get_by_id.return_value = mock_queue_item

        mock_media = Mock()
        mock_media.file_name = "rejected.jpg"
        service.media_repo.get_by_id.return_value = mock_media

        # Verbose ON
        mock_settings = Mock()
        mock_settings.show_verbose_notifications = True
        service.settings_service.get_settings.return_value = mock_settings

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "rejecter"
        mock_user.telegram_first_name = "Test"

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        await handlers.handle_rejected(queue_id, mock_user, mock_query)

        caption = (
            mock_query.edit_message_caption.call_args.kwargs.get("caption")
            or mock_query.edit_message_caption.call_args.args[0]
        )
        assert "Permanently Rejected" in caption
        assert "rejected.jpg" in caption
        assert "never be queued again" in caption

    async def test_rejected_verbose_off_shows_minimal(self, mock_callback_handlers):
        """Test verbose=False shows minimal rejection message."""
        handlers = mock_callback_handlers
        service = handlers.service
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()
        mock_queue_item.created_at = datetime.utcnow()
        mock_queue_item.scheduled_for = datetime.utcnow()
        service.queue_repo.get_by_id.return_value = mock_queue_item

        mock_media = Mock()
        mock_media.file_name = "rejected.jpg"
        service.media_repo.get_by_id.return_value = mock_media

        # Verbose OFF
        mock_settings = Mock()
        mock_settings.show_verbose_notifications = False
        service.settings_service.get_settings.return_value = mock_settings

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "rejecter"
        mock_user.telegram_first_name = "Test"

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        await handlers.handle_rejected(queue_id, mock_user, mock_query)

        caption = (
            mock_query.edit_message_caption.call_args.kwargs.get("caption")
            or mock_query.edit_message_caption.call_args.args[0]
        )
        assert "Rejected by @rejecter" in caption
        assert "never be queued again" not in caption


@pytest.mark.unit
class TestCompleteQueueAction:
    """Tests for complete_queue_action shared helper."""

    @pytest.mark.asyncio
    async def test_posted_creates_lock_and_increments(self, mock_callback_handlers):
        """Test posted action creates lock and increments counters."""
        handlers = mock_callback_handlers
        service = handlers.service
        queue_id = str(uuid4())
        media_id = uuid4()

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = media_id
        mock_queue_item.created_at = datetime.utcnow()
        mock_queue_item.scheduled_for = datetime.utcnow()
        service.queue_repo.get_by_id.return_value = mock_queue_item
        service.media_repo.get_by_id.return_value = Mock(file_name="test.jpg")

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "tester"

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        await handlers.complete_queue_action(
            queue_id,
            mock_user,
            mock_query,
            status="posted",
            success=True,
            caption="✅ Test",
            callback_name="posted",
        )

        service.media_repo.increment_times_posted.assert_called_once()
        service.lock_service.create_lock.assert_called_once()
        service.user_repo.increment_posts.assert_called_once()
        service.queue_repo.delete.assert_called_once_with(queue_id)

    @pytest.mark.asyncio
    async def test_skipped_does_not_create_lock(self, mock_callback_handlers):
        """Test skipped action does NOT create lock or increment counters."""
        handlers = mock_callback_handlers
        service = handlers.service
        queue_id = str(uuid4())
        media_id = uuid4()

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = media_id
        mock_queue_item.created_at = datetime.utcnow()
        mock_queue_item.scheduled_for = datetime.utcnow()
        service.queue_repo.get_by_id.return_value = mock_queue_item
        service.media_repo.get_by_id.return_value = Mock(file_name="test.jpg")

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "tester"

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        await handlers.complete_queue_action(
            queue_id,
            mock_user,
            mock_query,
            status="skipped",
            success=False,
            caption="⏭️ Test",
            callback_name="skip",
        )

        service.media_repo.increment_times_posted.assert_not_called()
        service.lock_service.create_lock.assert_not_called()
        service.user_repo.increment_posts.assert_not_called()
        service.queue_repo.delete.assert_called_once_with(queue_id)

    @pytest.mark.asyncio
    async def test_queue_item_not_found(self, mock_callback_handlers):
        """Test complete_queue_action handles missing queue item."""
        handlers = mock_callback_handlers
        service = handlers.service
        service.queue_repo.get_by_id.return_value = None

        mock_query = AsyncMock()

        await handlers.complete_queue_action(
            "nonexistent",
            Mock(),
            mock_query,
            status="posted",
            success=True,
            caption="test",
            callback_name="posted",
        )

        mock_query.edit_message_caption.assert_called_once()
        assert "not found" in str(mock_query.edit_message_caption.call_args)
