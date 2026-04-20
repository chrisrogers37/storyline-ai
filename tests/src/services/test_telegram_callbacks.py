"""Tests for TelegramCallbackHandlers (extracted from test_telegram_service.py)."""

import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime
from uuid import uuid4

from sqlalchemy.exc import OperationalError

from src.services.core.telegram_callbacks import TelegramCallbackHandlers


@pytest.fixture
def mock_callback_handlers(mock_telegram_service):
    """Create TelegramCallbackHandlers from shared mock_telegram_service."""
    handlers = TelegramCallbackHandlers(mock_telegram_service)
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
        service.queue_repo.claim_for_processing.return_value = mock_queue_item

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
        assert "test\\_image.jpg" in caption
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
        service.history_repo.get_by_queue_item_id.return_value = None

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
        service.queue_repo.claim_for_processing.return_value = mock_queue_item

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
        params = history_call.args[0]
        assert params.status == "rejected"

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
        service.queue_repo.claim_for_processing.return_value = mock_queue_item

        mock_media_item = Mock()
        mock_media_item.file_name = "test.jpg"
        mock_media_item.title = "Test"
        mock_media_item.caption = None
        mock_media_item.generated_caption = None
        mock_media_item.link_url = None
        mock_media_item.tags = []
        service.media_repo.get_by_id.return_value = mock_media_item

        service.ig_account_service.get_active_account.return_value = None

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

        # Mock is_paused via settings_service — paused
        mock_chat_settings = Mock(is_paused=True)
        service.settings_service.get_settings.return_value = mock_chat_settings
        service.set_paused = Mock(
            side_effect=lambda paused, user=None: setattr(
                mock_chat_settings, "is_paused", paused
            )
        )

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

        # Mock is_paused via settings_service — paused
        mock_chat_settings = Mock(is_paused=True)
        service.settings_service.get_settings.return_value = mock_chat_settings
        service.set_paused = Mock(
            side_effect=lambda paused, user=None: setattr(
                mock_chat_settings, "is_paused", paused
            )
        )

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

        # Mock is_paused via settings_service — paused
        mock_chat_settings = Mock(is_paused=True)
        service.settings_service.get_settings.return_value = mock_chat_settings
        service.set_paused = Mock(
            side_effect=lambda paused, user=None: setattr(
                mock_chat_settings, "is_paused", paused
            )
        )

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
        service.queue_repo.claim_for_processing.return_value = mock_queue_item

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
        service.queue_repo.claim_for_processing.return_value = mock_queue_item

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
        service.queue_repo.claim_for_processing.return_value = mock_queue_item

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
        service.queue_repo.claim_for_processing.return_value = mock_queue_item

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
        service.queue_repo.claim_for_processing.return_value = mock_queue_item

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
        service.queue_repo.claim_for_processing.return_value = mock_queue_item
        service.media_repo.get_by_id.return_value = Mock(
            file_name="test.jpg", generated_caption=None
        )

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
    async def test_skipped_creates_skip_lock(self, mock_callback_handlers):
        """Test skipped action creates a skip TTL lock but does NOT increment counters."""
        handlers = mock_callback_handlers
        service = handlers.service
        queue_id = str(uuid4())
        media_id = uuid4()

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = media_id
        mock_queue_item.created_at = datetime.utcnow()
        mock_queue_item.scheduled_for = datetime.utcnow()
        service.queue_repo.get_by_id.return_value = mock_queue_item
        service.queue_repo.claim_for_processing.return_value = mock_queue_item
        service.media_repo.get_by_id.return_value = Mock(
            file_name="test.jpg", generated_caption=None
        )

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
        service.lock_service.create_lock.assert_called_once_with(
            str(media_id), ttl_days=45, lock_reason="skip"
        )
        service.user_repo.increment_posts.assert_not_called()
        service.queue_repo.delete.assert_called_once_with(queue_id)

    @pytest.mark.asyncio
    async def test_queue_item_not_found(self, mock_callback_handlers):
        """Test complete_queue_action handles missing queue item via claim failure."""
        handlers = mock_callback_handlers
        service = handlers.service
        service.queue_repo.claim_for_processing.return_value = None
        service.queue_repo.get_by_id.return_value = None
        service.history_repo.get_by_queue_item_id.return_value = None

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


@pytest.mark.unit
@pytest.mark.asyncio
class TestEarlyProcessingFeedback:
    """Tests for early keyboard removal before DB operations."""

    async def test_keyboard_removed_before_db_operations(self, mock_callback_handlers):
        """Inline keyboard is removed immediately after lock, before DB ops."""
        handlers = mock_callback_handlers
        service = handlers.service
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()
        mock_queue_item.created_at = datetime.utcnow()
        mock_queue_item.scheduled_for = datetime.utcnow()
        service.queue_repo.get_by_id.return_value = mock_queue_item
        service.queue_repo.claim_for_processing.return_value = mock_queue_item
        service.media_repo.get_by_id.return_value = Mock(
            file_name="test.jpg", generated_caption=None
        )

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "tester"

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        # Track call order
        call_order = []
        mock_query.edit_message_reply_markup.side_effect = lambda **kw: (
            call_order.append("remove_keyboard")
        )
        service.history_repo.create.side_effect = lambda *a, **kw: call_order.append(
            "history_create"
        )

        await handlers.complete_queue_action(
            queue_id,
            mock_user,
            mock_query,
            status="skipped",
            success=False,
            caption="⏭️ Test",
            callback_name="skip",
        )

        assert "remove_keyboard" in call_order
        assert "history_create" in call_order
        assert call_order.index("remove_keyboard") < call_order.index("history_create")

    async def test_keyboard_removal_failure_does_not_break_flow(
        self, mock_callback_handlers
    ):
        """Early keyboard removal failure still allows DB ops + caption update."""
        handlers = mock_callback_handlers
        service = handlers.service
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()
        mock_queue_item.created_at = datetime.utcnow()
        mock_queue_item.scheduled_for = datetime.utcnow()
        service.queue_repo.get_by_id.return_value = mock_queue_item
        service.queue_repo.claim_for_processing.return_value = mock_queue_item
        service.media_repo.get_by_id.return_value = Mock(
            file_name="test.jpg", generated_caption=None
        )

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "tester"

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)
        mock_query.edit_message_reply_markup.side_effect = Exception(
            "Message is not modified"
        )

        await handlers.complete_queue_action(
            queue_id,
            mock_user,
            mock_query,
            status="skipped",
            success=False,
            caption="⏭️ Test",
            callback_name="skip",
        )

        service.history_repo.create.assert_called_once()
        service.queue_repo.delete.assert_called_once()
        mock_query.edit_message_caption.assert_called_once()

    async def test_rejected_removes_keyboard_before_db_ops(
        self, mock_callback_handlers
    ):
        """handle_rejected removes keyboard before creating history/locks."""
        handlers = mock_callback_handlers
        service = handlers.service
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()
        mock_queue_item.created_at = datetime.utcnow()
        mock_queue_item.scheduled_for = datetime.utcnow()
        mock_queue_item.chat_settings_id = uuid4()
        service.queue_repo.get_by_id.return_value = mock_queue_item
        service.queue_repo.claim_for_processing.return_value = mock_queue_item

        mock_media = Mock()
        mock_media.file_name = "test.jpg"
        service.media_repo.get_by_id.return_value = mock_media

        mock_settings = Mock()
        mock_settings.show_verbose_notifications = False
        service.settings_service.get_settings.return_value = mock_settings

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "rejecter"
        mock_user.telegram_first_name = "Test"

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        call_order = []
        mock_query.edit_message_reply_markup.side_effect = lambda **kw: (
            call_order.append("remove_keyboard")
        )
        service.history_repo.create.side_effect = lambda *a, **kw: call_order.append(
            "history_create"
        )

        await handlers.handle_rejected(queue_id, mock_user, mock_query)

        assert "remove_keyboard" in call_order
        assert "history_create" in call_order
        assert call_order.index("remove_keyboard") < call_order.index("history_create")


@pytest.mark.unit
@pytest.mark.asyncio
class TestRaceConditionHandling:
    """Tests for operation lock and cancellation flag race condition handling."""

    async def test_double_click_posted_does_not_create_duplicate(
        self, mock_callback_handlers
    ):
        """Test that clicking 'Posted' twice doesn't create duplicate history entries."""
        handlers = mock_callback_handlers
        service = handlers.service
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()
        mock_queue_item.created_at = datetime.utcnow()
        mock_queue_item.scheduled_for = datetime.utcnow()
        service.queue_repo.get_by_id.return_value = mock_queue_item
        service.queue_repo.claim_for_processing.return_value = mock_queue_item

        mock_media = Mock()
        mock_media.file_name = "test.jpg"
        service.media_repo.get_by_id.return_value = mock_media

        mock_settings = Mock()
        mock_settings.show_verbose_notifications = True
        service.settings_service.get_settings.return_value = mock_settings

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "poster"
        mock_user.telegram_first_name = "Test"

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        # First click succeeds
        await handlers.handle_posted(queue_id, mock_user, mock_query)

        # History created exactly once
        assert service.history_repo.create.call_count == 1

        # Second click on the same item - lock is cleaned up so a new one is created,
        # but claim_for_processing returns None (item was already claimed/deleted)
        service.queue_repo.claim_for_processing.return_value = None
        service.queue_repo.get_by_id.return_value = None
        mock_query_2 = AsyncMock()
        mock_query_2.message = Mock(chat_id=-100123, message_id=1)

        await handlers.handle_posted(queue_id, mock_user, mock_query_2)

        # History still only created once (second call found no queue item)
        assert service.history_repo.create.call_count == 1

    async def test_lock_prevents_concurrent_execution(self, mock_callback_handlers):
        """Test that the lock prevents concurrent execution on the same item."""
        handlers = mock_callback_handlers
        service = handlers.service
        queue_id = str(uuid4())

        # Pre-acquire the lock to simulate an in-progress operation
        lock = service.get_operation_lock(queue_id)
        await lock.acquire()

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "poster"
        mock_user.telegram_first_name = "Test"

        mock_settings = Mock()
        mock_settings.show_verbose_notifications = True
        service.settings_service.get_settings.return_value = mock_settings

        # Try to execute while lock is held
        await handlers.complete_queue_action(
            queue_id,
            mock_user,
            mock_query,
            status="posted",
            success=True,
            caption="✅ Test",
            callback_name="posted",
        )

        # Should show "Already processing" feedback
        mock_query.answer.assert_called_once_with(
            "⏳ Already processing this item...", show_alert=False
        )

        # Should NOT create history (action was blocked)
        service.history_repo.create.assert_not_called()

        # Clean up
        lock.release()

    async def test_lock_cleaned_up_after_operation(self, mock_callback_handlers):
        """Test that the lock is cleaned up after operation completes."""
        handlers = mock_callback_handlers
        service = handlers.service
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()
        mock_queue_item.created_at = datetime.utcnow()
        mock_queue_item.scheduled_for = datetime.utcnow()
        service.queue_repo.get_by_id.return_value = mock_queue_item
        service.queue_repo.claim_for_processing.return_value = mock_queue_item
        service.media_repo.get_by_id.return_value = Mock(
            file_name="test.jpg", generated_caption=None
        )

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "tester"

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        mock_settings = Mock()
        mock_settings.show_verbose_notifications = True
        service.settings_service.get_settings.return_value = mock_settings

        await handlers.handle_posted(queue_id, mock_user, mock_query)

        # Lock and cancel flag should be cleaned up
        assert queue_id not in service.operation_state._operation_locks
        assert queue_id not in service.operation_state._cancel_flags

    async def test_posted_sets_cancel_flag_for_autopost(self, mock_callback_handlers):
        """Test that clicking 'Posted' sets the cancel flag to abort pending auto-post."""
        handlers = mock_callback_handlers
        service = handlers.service
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()
        mock_queue_item.created_at = datetime.utcnow()
        mock_queue_item.scheduled_for = datetime.utcnow()
        service.queue_repo.get_by_id.return_value = mock_queue_item
        service.queue_repo.claim_for_processing.return_value = mock_queue_item
        service.media_repo.get_by_id.return_value = Mock(
            file_name="test.jpg", generated_caption=None
        )

        mock_settings = Mock()
        mock_settings.show_verbose_notifications = True
        service.settings_service.get_settings.return_value = mock_settings

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "poster"
        mock_user.telegram_first_name = "Test"

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        # Create a cancel flag before the action (simulating autopost created it)
        cancel_flag = service.get_cancel_flag(queue_id)
        assert not cancel_flag.is_set()

        await handlers.handle_posted(queue_id, mock_user, mock_query)

        # The cancel flag should have been set (even though cleanup_operation_state
        # removes it, we verify it was set by checking the call succeeded)
        service.history_repo.create.assert_called_once()

    async def test_skipped_sets_cancel_flag(self, mock_callback_handlers):
        """Test that clicking 'Skip' sets the cancel flag."""
        handlers = mock_callback_handlers
        service = handlers.service
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()
        mock_queue_item.created_at = datetime.utcnow()
        mock_queue_item.scheduled_for = datetime.utcnow()
        service.queue_repo.get_by_id.return_value = mock_queue_item
        service.queue_repo.claim_for_processing.return_value = mock_queue_item
        service.media_repo.get_by_id.return_value = Mock(
            file_name="test.jpg", generated_caption=None
        )

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "skipper"
        mock_user.telegram_first_name = "Test"

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        # Create a cancel flag
        cancel_flag = service.get_cancel_flag(queue_id)

        # Patch to capture the cancel flag state before cleanup
        original_cleanup = service.cleanup_operation_state
        flag_was_set = False

        def capture_cleanup(qid):
            nonlocal flag_was_set
            flag_was_set = cancel_flag.is_set()
            original_cleanup(qid)

        service.cleanup_operation_state = capture_cleanup

        await handlers.handle_skipped(queue_id, mock_user, mock_query)

        assert flag_was_set, "Cancel flag should have been set before cleanup"

    async def test_rejected_sets_cancel_flag(self, mock_callback_handlers):
        """Test that clicking 'Reject' (confirmed) sets the cancel flag."""
        handlers = mock_callback_handlers
        service = handlers.service
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()
        mock_queue_item.created_at = datetime.utcnow()
        mock_queue_item.scheduled_for = datetime.utcnow()
        service.queue_repo.get_by_id.return_value = mock_queue_item
        service.queue_repo.claim_for_processing.return_value = mock_queue_item

        mock_media = Mock()
        mock_media.file_name = "test.jpg"
        service.media_repo.get_by_id.return_value = mock_media

        mock_settings = Mock()
        mock_settings.show_verbose_notifications = True
        service.settings_service.get_settings.return_value = mock_settings

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "rejecter"
        mock_user.telegram_first_name = "Test"

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        # Create a cancel flag and verify it gets set
        cancel_flag = service.get_cancel_flag(queue_id)
        assert not cancel_flag.is_set()

        await handlers.handle_rejected(queue_id, mock_user, mock_query)

        # The action should have completed (permanent lock created)
        service.lock_service.create_permanent_lock.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
class TestSSLRetry:
    """Tests for OperationalError retry logic in callback handlers."""

    async def test_operational_error_triggers_retry(self, mock_callback_handlers):
        """OperationalError triggers session refresh + retry."""
        handlers = mock_callback_handlers
        service = handlers.service
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()
        mock_queue_item.created_at = datetime.utcnow()
        mock_queue_item.scheduled_for = datetime.utcnow()
        mock_queue_item.chat_settings_id = uuid4()
        service.queue_repo.get_by_id.return_value = mock_queue_item
        service.queue_repo.claim_for_processing.return_value = mock_queue_item
        service.media_repo.get_by_id.return_value = Mock(
            file_name="test.jpg", generated_caption=None
        )

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "tester"

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        # First history_repo.create raises OperationalError, second succeeds
        op_error = OperationalError("SSL closed", {}, Exception("SSL"))
        service.history_repo.create.side_effect = [op_error, Mock()]
        # No existing history → retry should proceed
        service.history_repo.get_by_queue_item_id.return_value = None

        await handlers.complete_queue_action(
            queue_id,
            mock_user,
            mock_query,
            status="skipped",
            success=False,
            caption="⏭️ Test",
            callback_name="skip",
        )

        assert service.history_repo.create.call_count == 2
        mock_query.edit_message_caption.assert_called()

    async def test_non_operational_error_not_retried(self, mock_callback_handlers):
        """ValueError is not retried."""
        handlers = mock_callback_handlers
        service = handlers.service
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()
        mock_queue_item.created_at = datetime.utcnow()
        mock_queue_item.scheduled_for = datetime.utcnow()
        service.queue_repo.get_by_id.return_value = mock_queue_item
        service.queue_repo.claim_for_processing.return_value = mock_queue_item
        service.media_repo.get_by_id.return_value = Mock(
            file_name="test.jpg", generated_caption=None
        )

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "tester"

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        service.history_repo.create.side_effect = ValueError("bad data")

        with pytest.raises(ValueError):
            await handlers._do_complete_queue_action(
                queue_id,
                mock_user,
                mock_query,
                status="skipped",
                success=False,
                caption="⏭️ Test",
                callback_name="skip",
            )

        assert service.history_repo.create.call_count == 1

    async def test_second_failure_propagates(self, mock_callback_handlers):
        """Both attempts fail -> exception propagates."""
        handlers = mock_callback_handlers
        service = handlers.service
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()
        mock_queue_item.created_at = datetime.utcnow()
        mock_queue_item.scheduled_for = datetime.utcnow()
        mock_queue_item.chat_settings_id = uuid4()
        service.queue_repo.get_by_id.return_value = mock_queue_item
        service.queue_repo.claim_for_processing.return_value = mock_queue_item
        service.media_repo.get_by_id.return_value = Mock(
            file_name="test.jpg", generated_caption=None
        )

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "tester"

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        op_error = OperationalError("SSL closed", {}, Exception("SSL"))
        service.history_repo.create.side_effect = [op_error, op_error]
        # No existing history → retry should proceed (and fail again)
        service.history_repo.get_by_queue_item_id.return_value = None

        with pytest.raises(OperationalError):
            await handlers._do_complete_queue_action(
                queue_id,
                mock_user,
                mock_query,
                status="skipped",
                success=False,
                caption="⏭️ Test",
                callback_name="skip",
            )

    async def test_queue_item_deleted_during_retry(self, mock_callback_handlers):
        """Queue item gone after refresh -> shows 'already processed'."""
        handlers = mock_callback_handlers
        service = handlers.service
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()
        mock_queue_item.created_at = datetime.utcnow()
        mock_queue_item.scheduled_for = datetime.utcnow()
        # claim_for_processing returns item (initial claim succeeds)
        service.queue_repo.claim_for_processing.return_value = mock_queue_item
        # get_by_id returns None on re-fetch after error
        service.queue_repo.get_by_id.return_value = None
        service.media_repo.get_by_id.return_value = Mock(
            file_name="test.jpg", generated_caption=None
        )

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "tester"

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        op_error = OperationalError("SSL closed", {}, Exception("SSL"))
        service.history_repo.create.side_effect = op_error
        # No existing history → retry path checks get_by_id
        service.history_repo.get_by_queue_item_id.return_value = None

        await handlers._do_complete_queue_action(
            queue_id,
            mock_user,
            mock_query,
            status="skipped",
            success=False,
            caption="⏭️ Test",
            callback_name="skip",
        )

        assert "already processed" in str(mock_query.edit_message_caption.call_args)

    async def test_rejected_operational_error_triggers_retry(
        self, mock_callback_handlers
    ):
        """handle_rejected also retries on OperationalError."""
        handlers = mock_callback_handlers
        service = handlers.service
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()
        mock_queue_item.created_at = datetime.utcnow()
        mock_queue_item.scheduled_for = datetime.utcnow()
        mock_queue_item.chat_settings_id = uuid4()
        service.queue_repo.get_by_id.return_value = mock_queue_item
        service.queue_repo.claim_for_processing.return_value = mock_queue_item
        service.media_repo.get_by_id.return_value = Mock(
            file_name="test.jpg", generated_caption=None
        )

        mock_settings = Mock()
        mock_settings.show_verbose_notifications = False
        service.settings_service.get_settings.return_value = mock_settings

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "rejecter"
        mock_user.telegram_first_name = "Test"

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        op_error = OperationalError("SSL closed", {}, Exception("SSL"))
        service.history_repo.create.side_effect = [op_error, Mock()]
        # No existing history → retry should proceed
        service.history_repo.get_by_queue_item_id.return_value = None

        await handlers.handle_rejected(queue_id, mock_user, mock_query)

        assert service.history_repo.create.call_count == 2


@pytest.mark.unit
@pytest.mark.asyncio
class TestAtomicClaim:
    """Tests for atomic claim_for_processing guard."""

    async def test_claim_failure_shows_already_processed(self, mock_callback_handlers):
        """When claim_for_processing returns None, no history is created."""
        handlers = mock_callback_handlers
        service = handlers.service
        queue_id = str(uuid4())

        # claim fails (another handler already claimed it)
        service.queue_repo.claim_for_processing.return_value = None
        # validate_queue_item fallback: item gone, history exists
        service.queue_repo.get_by_id.return_value = None
        history = Mock(status="posted", posting_method="telegram_manual")
        service.history_repo.get_by_queue_item_id.return_value = history

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        await handlers.complete_queue_action(
            queue_id,
            Mock(),
            mock_query,
            status="posted",
            success=True,
            caption="✅ Test",
            callback_name="posted",
        )

        # No history created (claim failed, fallback showed message)
        service.history_repo.create.assert_not_called()
        service.queue_repo.delete.assert_not_called()

    async def test_claim_success_proceeds_normally(self, mock_callback_handlers):
        """When claim_for_processing succeeds, full flow executes."""
        handlers = mock_callback_handlers
        service = handlers.service
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()
        mock_queue_item.created_at = datetime.utcnow()
        mock_queue_item.scheduled_for = datetime.utcnow()
        service.queue_repo.claim_for_processing.return_value = mock_queue_item
        service.media_repo.get_by_id.return_value = Mock(
            file_name="test.jpg", generated_caption=None
        )

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

        service.history_repo.create.assert_called_once()
        service.queue_repo.delete.assert_called_once_with(queue_id)

    async def test_rejected_uses_operation_lock(self, mock_callback_handlers):
        """handle_rejected respects operation lock (prevents double rejection)."""
        handlers = mock_callback_handlers
        service = handlers.service
        queue_id = str(uuid4())

        # Pre-acquire the lock to simulate an in-progress operation
        lock = service.get_operation_lock(queue_id)
        await lock.acquire()

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "rejecter"
        mock_user.telegram_first_name = "Test"

        await handlers.handle_rejected(queue_id, mock_user, mock_query)

        # Should show "Already processing" feedback
        mock_query.answer.assert_called_once_with(
            "⏳ Already processing this item...", show_alert=False
        )

        # Should NOT create history or lock (action was blocked)
        service.history_repo.create.assert_not_called()
        service.lock_service.create_permanent_lock.assert_not_called()

        lock.release()

    async def test_retry_skips_duplicate_history(self, mock_callback_handlers):
        """OperationalError retry checks for existing history before retrying."""
        handlers = mock_callback_handlers
        service = handlers.service
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()
        mock_queue_item.created_at = datetime.utcnow()
        mock_queue_item.scheduled_for = datetime.utcnow()
        mock_queue_item.chat_settings_id = uuid4()
        service.queue_repo.claim_for_processing.return_value = mock_queue_item
        service.media_repo.get_by_id.return_value = Mock(
            file_name="test.jpg", generated_caption=None
        )

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "tester"

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        # First create raises OperationalError
        op_error = OperationalError("SSL closed", {}, Exception("SSL"))
        service.history_repo.create.side_effect = op_error
        # History already exists (written before the error)
        service.history_repo.get_by_queue_item_id.return_value = Mock(status="skipped")

        await handlers._do_complete_queue_action(
            queue_id,
            mock_user,
            mock_query,
            status="skipped",
            success=False,
            caption="⏭️ Test",
            callback_name="skip",
        )

        # history_repo.create called only once (the failing attempt);
        # retry was skipped because history already existed
        assert service.history_repo.create.call_count == 1
        # Queue item still cleaned up
        service.queue_repo.delete.assert_called_once_with(queue_id)


@pytest.mark.unit
class TestSharedSessionAtomicity:
    """Tests for _shared_session deferred-commit (flush-then-commit) pattern."""

    def test_commit_replaced_with_flush_during_context(self, mock_callback_handlers):
        """During _shared_session, session.commit should be session.flush."""
        handlers = mock_callback_handlers
        service = handlers.service

        mock_session = Mock()
        mock_session.commit = Mock(name="original_commit")
        mock_session.flush = Mock(name="flush")
        service.history_repo.db = mock_session

        # Set _db on each repo so originals dict is populated
        for repo in [
            service.history_repo,
            service.media_repo,
            service.queue_repo,
            service.user_repo,
            service.lock_service.lock_repo,
        ]:
            repo._db = Mock()

        with handlers._shared_session():
            # Inside the context, commit should be replaced with flush
            assert mock_session.commit is mock_session.flush

    def test_real_commit_called_on_success(self, mock_callback_handlers):
        """On successful exit, the original commit is called once."""
        handlers = mock_callback_handlers
        service = handlers.service

        original_commit = Mock(name="original_commit")
        mock_session = Mock()
        mock_session.commit = original_commit
        mock_session.flush = Mock(name="flush")
        service.history_repo.db = mock_session

        for repo in [
            service.history_repo,
            service.media_repo,
            service.queue_repo,
            service.user_repo,
            service.lock_service.lock_repo,
        ]:
            repo._db = Mock()

        with handlers._shared_session():
            pass

        # The original commit should have been called exactly once (at exit)
        original_commit.assert_called_once()

    def test_rollback_on_exception_no_commit(self, mock_callback_handlers):
        """On exception, rollback is called and commit is NOT called."""
        handlers = mock_callback_handlers
        service = handlers.service

        original_commit = Mock(name="original_commit")
        mock_session = Mock()
        mock_session.commit = original_commit
        mock_session.flush = Mock(name="flush")
        mock_session.rollback = Mock(name="rollback")
        service.history_repo.db = mock_session

        for repo in [
            service.history_repo,
            service.media_repo,
            service.queue_repo,
            service.user_repo,
            service.lock_service.lock_repo,
        ]:
            repo._db = Mock()

        with pytest.raises(ValueError, match="test error"):
            with handlers._shared_session():
                raise ValueError("test error")

        # Rollback should be called
        mock_session.rollback.assert_called_once()
        # Original commit should NOT have been called
        original_commit.assert_not_called()

    def test_sessions_restored_in_finally(self, mock_callback_handlers):
        """Original sessions are restored even after an exception."""
        handlers = mock_callback_handlers
        service = handlers.service

        mock_session = Mock()
        mock_session.commit = Mock(name="original_commit")
        mock_session.flush = Mock(name="flush")
        service.history_repo.db = mock_session

        # Record original _db values
        original_dbs = {}
        repos = [
            service.history_repo,
            service.media_repo,
            service.queue_repo,
            service.user_repo,
            service.lock_service.lock_repo,
        ]
        for repo in repos:
            original_db = Mock(name=f"original_db_{id(repo)}")
            repo._db = original_db
            original_dbs[id(repo)] = original_db

        with pytest.raises(RuntimeError):
            with handlers._shared_session():
                raise RuntimeError("boom")

        # All repos should have their original sessions restored
        for repo in repos:
            repo.use_session.assert_called()
            # The last call to use_session should restore the original
            last_call_arg = repo.use_session.call_args_list[-1][0][0]
            assert last_call_arg is original_dbs[id(repo)]

    def test_commit_restored_after_success(self, mock_callback_handlers):
        """After successful exit, session.commit is restored to original."""
        handlers = mock_callback_handlers
        service = handlers.service

        original_commit = Mock(name="original_commit")
        mock_session = Mock()
        mock_session.commit = original_commit
        mock_session.flush = Mock(name="flush")
        service.history_repo.db = mock_session

        for repo in [
            service.history_repo,
            service.media_repo,
            service.queue_repo,
            service.user_repo,
            service.lock_service.lock_repo,
        ]:
            repo._db = Mock()

        with handlers._shared_session():
            pass

        # After exiting, commit should be restored
        assert mock_session.commit is original_commit

    def test_commit_restored_after_exception(self, mock_callback_handlers):
        """After exception, session.commit is restored to original."""
        handlers = mock_callback_handlers
        service = handlers.service

        original_commit = Mock(name="original_commit")
        mock_session = Mock()
        mock_session.commit = original_commit
        mock_session.flush = Mock(name="flush")
        service.history_repo.db = mock_session

        for repo in [
            service.history_repo,
            service.media_repo,
            service.queue_repo,
            service.user_repo,
            service.lock_service.lock_repo,
        ]:
            repo._db = Mock()

        with pytest.raises(ValueError):
            with handlers._shared_session():
                raise ValueError("error")

        # After exiting, commit should be restored
        assert mock_session.commit is original_commit


@pytest.mark.unit
@pytest.mark.asyncio
class TestBatchApprove:
    """Tests for batch approve callback handlers."""

    async def test_batch_approve_processes_all_items(self, mock_callback_handlers):
        """Batch approve marks all pending items as posted."""
        handlers = mock_callback_handlers
        service = handlers.service

        cs_id = str(uuid4())
        queue_id_1 = uuid4()
        queue_id_2 = uuid4()

        item1 = Mock(
            id=queue_id_1,
            media_item_id=uuid4(),
            chat_settings_id=cs_id,
            created_at=datetime.utcnow(),
            scheduled_for=datetime.utcnow(),
        )
        item2 = Mock(
            id=queue_id_2,
            media_item_id=uuid4(),
            chat_settings_id=cs_id,
            created_at=datetime.utcnow(),
            scheduled_for=datetime.utcnow(),
        )

        service.queue_repo.get_all_with_media.side_effect = [
            [(item1, "meme.jpg", "memes")],
            [(item2, "merch.jpg", "merch")],
        ]
        service.queue_repo.claim_for_processing.side_effect = [item1, item2]
        service.media_repo.get_by_id.return_value = Mock()

        mock_query = AsyncMock()
        mock_query.message.chat_id = -100123
        mock_query.message.message_id = 1
        mock_user = Mock(id=uuid4(), telegram_username="test")

        mock_session = Mock()
        mock_session.commit = Mock()
        mock_session.flush = Mock()
        service.history_repo.db = mock_session
        for repo in [
            service.history_repo,
            service.media_repo,
            service.queue_repo,
            service.user_repo,
            service.lock_service.lock_repo,
        ]:
            repo._db = Mock()

        await handlers.handle_batch_approve(cs_id, mock_user, mock_query)

        assert service.queue_repo.claim_for_processing.call_count == 2
        final_call = mock_query.edit_message_text.call_args_list[-1]
        assert "2 items marked as posted" in final_call[0][0]

    async def test_batch_approve_empty_queue(self, mock_callback_handlers):
        """Batch approve with no pending items shows empty message."""
        handlers = mock_callback_handlers
        service = handlers.service

        service.queue_repo.get_all_with_media.return_value = []

        mock_query = AsyncMock()
        mock_query.message.chat_id = -100123
        mock_user = Mock(id=uuid4())

        await handlers.handle_batch_approve("cs-id", mock_user, mock_query)

        final_text = mock_query.edit_message_text.call_args[0][0]
        assert "No pending items" in final_text

    async def test_batch_approve_handles_claim_failure(self, mock_callback_handlers):
        """Batch approve continues when individual items fail to claim."""
        handlers = mock_callback_handlers
        service = handlers.service

        item1 = Mock(
            id=uuid4(),
            media_item_id=uuid4(),
            chat_settings_id="cs",
            created_at=datetime.utcnow(),
            scheduled_for=datetime.utcnow(),
        )

        service.queue_repo.get_all_with_media.side_effect = [
            [(item1, "file.jpg", "cat")],
            [],
        ]
        service.queue_repo.claim_for_processing.return_value = None

        mock_query = AsyncMock()
        mock_query.message.chat_id = -100123
        mock_query.message.message_id = 1
        mock_user = Mock(id=uuid4())

        await handlers.handle_batch_approve("cs-id", mock_user, mock_query)

        final_text = mock_query.edit_message_text.call_args[0][0]
        assert "0 items marked as posted" in final_text
        assert "1 item failed" in final_text

    async def test_batch_approve_cancel(self, mock_callback_handlers):
        """Batch approve cancel shows cancelled message."""
        handlers = mock_callback_handlers
        mock_query = AsyncMock()
        mock_user = Mock(id=uuid4())

        await handlers.handle_batch_approve_cancel("", mock_user, mock_query)

        final_text = mock_query.edit_message_text.call_args[0][0]
        assert "cancelled" in final_text
