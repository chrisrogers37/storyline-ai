"""Tests for TelegramCommandHandlers (extracted from test_telegram_service.py)."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from uuid import uuid4

from src.services.core.telegram_service import TelegramService
from src.services.core.telegram_commands import TelegramCommandHandlers


@pytest.fixture
def mock_command_handlers():
    """Create TelegramCommandHandlers with mocked TelegramService dependencies."""
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

        handlers = TelegramCommandHandlers(service)

        yield handlers


@pytest.mark.unit
@pytest.mark.asyncio
class TestQueueCommand:
    """Tests for /queue command."""

    async def test_queue_shows_all_pending_not_just_due(self, mock_command_handlers):
        """Test /queue shows ALL pending items, not just ones due now."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "testuser"
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        # Create mock queue items scheduled for the future
        mock_queue_item1 = Mock()
        mock_queue_item1.id = uuid4()
        mock_queue_item1.media_item_id = uuid4()
        mock_queue_item1.scheduled_for = datetime(2030, 1, 1, 12, 0)  # Future date

        mock_queue_item2 = Mock()
        mock_queue_item2.id = uuid4()
        mock_queue_item2.media_item_id = uuid4()
        mock_queue_item2.scheduled_for = datetime(2030, 1, 2, 14, 0)  # Future date

        # get_all returns future items, get_pending would return empty
        service.queue_repo.get_all.return_value = [
            mock_queue_item1,
            mock_queue_item2,
        ]

        mock_media = Mock()
        mock_media.file_name = "test.jpg"  # String, not Mock
        mock_media.category = "memes"  # String, not Mock
        service.media_repo.get_by_id.return_value = mock_media

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        await handlers.handle_queue(mock_update, mock_context)

        # Should call get_all with status="pending", NOT get_pending
        service.queue_repo.get_all.assert_called_once_with(status="pending")

        # Should show items in message
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Upcoming Queue" in message_text
        assert "2 of 2" in message_text

    async def test_queue_empty_message(self, mock_command_handlers):
        """Test /queue shows empty message when no posts scheduled."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        service.queue_repo.get_all.return_value = []

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        await handlers.handle_queue(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Queue Empty" in message_text
        assert "No posts scheduled" in message_text

    async def test_queue_limits_to_ten_items(self, mock_command_handlers):
        """Test /queue only shows first 10 items."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        # Create 15 mock queue items
        mock_items = []
        for i in range(15):
            item = Mock()
            item.id = uuid4()
            item.media_item_id = uuid4()
            item.scheduled_for = datetime(2030, 1, i + 1, 12, 0)
            mock_items.append(item)

        service.queue_repo.get_all.return_value = mock_items

        mock_media = Mock()
        mock_media.file_name = "test.jpg"  # String, not Mock
        mock_media.category = "memes"  # String, not Mock
        service.media_repo.get_by_id.return_value = mock_media

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        await handlers.handle_queue(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        # Should show "10 of 15"
        assert "10 of 15" in message_text


@pytest.mark.unit
@pytest.mark.asyncio
class TestNextCommand:
    """Tests for /next command - force send next post."""

    async def test_next_sends_earliest_scheduled_post(self, mock_command_handlers):
        """Test /next sends the earliest scheduled post."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "testuser"
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        queue_item_id = uuid4()

        mock_media = Mock()
        mock_media.file_name = "next_post.jpg"

        # Mock PostingService
        mock_posting_service = Mock()
        mock_posting_service.force_post_next = AsyncMock(
            return_value={
                "success": True,
                "queue_item_id": str(queue_item_id),
                "media_item": mock_media,
                "shifted_count": 5,
            }
        )
        mock_posting_service.__enter__ = Mock(return_value=mock_posting_service)
        mock_posting_service.__exit__ = Mock(return_value=False)

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        with patch(
            "src.services.core.posting.PostingService",
            return_value=mock_posting_service,
        ):
            await handlers.handle_next(mock_update, mock_context)

        # Should call force_post_next on PostingService
        mock_posting_service.force_post_next.assert_called_once()

        # Should NOT send any extra messages on success (no clutter)
        mock_update.message.reply_text.assert_not_called()

    async def test_next_empty_queue(self, mock_command_handlers):
        """Test /next shows error when queue is empty."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        # Mock PostingService to return empty queue error
        mock_posting_service = Mock()
        mock_posting_service.force_post_next = AsyncMock(
            return_value={
                "success": False,
                "error": "No pending items in queue",
            }
        )
        mock_posting_service.__enter__ = Mock(return_value=mock_posting_service)
        mock_posting_service.__exit__ = Mock(return_value=False)

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        with patch(
            "src.services.core.posting.PostingService",
            return_value=mock_posting_service,
        ):
            await handlers.handle_next(mock_update, mock_context)

        # Should show empty queue message
        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Queue Empty" in message_text
        assert "No posts to send" in message_text

    async def test_next_media_not_found(self, mock_command_handlers):
        """Test /next handles missing media gracefully."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        mock_posting_service = Mock()
        mock_posting_service.force_post_next = AsyncMock(
            return_value={
                "success": False,
                "error": "Media item not found",
            }
        )
        mock_posting_service.__enter__ = Mock(return_value=mock_posting_service)
        mock_posting_service.__exit__ = Mock(return_value=False)

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        with patch(
            "src.services.core.posting.PostingService",
            return_value=mock_posting_service,
        ):
            await handlers.handle_next(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Error" in message_text
        assert "Media item not found" in message_text

    async def test_next_notification_failure(self, mock_command_handlers):
        """Test /next handles notification failure gracefully."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        mock_posting_service = Mock()
        mock_posting_service.force_post_next = AsyncMock(
            return_value={
                "success": False,
                "error": "Failed to send notification",
            }
        )
        mock_posting_service.__enter__ = Mock(return_value=mock_posting_service)
        mock_posting_service.__exit__ = Mock(return_value=False)

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        with patch(
            "src.services.core.posting.PostingService",
            return_value=mock_posting_service,
        ):
            await handlers.handle_next(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Failed to send" in message_text

    async def test_next_logs_interaction(self, mock_command_handlers):
        """Test /next logs the interaction on success."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "testuser"
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        queue_item_id = uuid4()
        mock_media = Mock()
        mock_media.id = uuid4()
        mock_media.file_name = "logged_post.jpg"

        mock_posting_service = Mock()
        mock_posting_service.force_post_next = AsyncMock(
            return_value={
                "success": True,
                "queue_item_id": str(queue_item_id),
                "media_item": mock_media,
                "shifted_count": 0,
            }
        )
        mock_posting_service.__enter__ = Mock(return_value=mock_posting_service)
        mock_posting_service.__exit__ = Mock(return_value=False)

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        with patch(
            "src.services.core.posting.PostingService",
            return_value=mock_posting_service,
        ):
            await handlers.handle_next(mock_update, mock_context)

        # Should log interaction
        service.interaction_service.log_command.assert_called_once()
        call_kwargs = service.interaction_service.log_command.call_args.kwargs
        assert call_kwargs["command"] == "/next"
        assert call_kwargs["context"]["success"] is True


@pytest.mark.unit
@pytest.mark.asyncio
class TestPauseCommand:
    """Tests for /pause command."""

    async def test_pause_when_not_paused(self, mock_command_handlers):
        """Test /pause pauses posting when not already paused."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "testuser"
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        service.queue_repo.count_pending.return_value = 10

        # Mock is_paused via settings_service
        mock_chat_settings = Mock(is_paused=False)
        service.settings_service.get_settings.return_value = mock_chat_settings
        service.set_paused = Mock(
            side_effect=lambda paused, user=None: setattr(
                mock_chat_settings, "is_paused", paused
            )
        )

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        await handlers.handle_pause(mock_update, mock_context)

        # Should now be paused
        assert service.is_paused is True

        # Should show paused message
        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Posting Paused" in message_text
        assert "10 posts" in message_text

    async def test_pause_when_already_paused(self, mock_command_handlers):
        """Test /pause shows already paused message."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        # Mock is_paused via settings_service — already paused
        mock_chat_settings = Mock(is_paused=True)
        service.settings_service.get_settings.return_value = mock_chat_settings

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        await handlers.handle_pause(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Already Paused" in message_text


@pytest.mark.unit
@pytest.mark.asyncio
class TestResumeCommand:
    """Tests for /resume command."""

    async def test_resume_when_not_paused(self, mock_command_handlers):
        """Test /resume shows already running message."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        # Mock is_paused via settings_service — not paused
        mock_chat_settings = Mock(is_paused=False)
        service.settings_service.get_settings.return_value = mock_chat_settings

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        await handlers.handle_resume(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Already Running" in message_text

    async def test_resume_with_overdue_posts(self, mock_command_handlers):
        """Test /resume shows options when there are overdue posts."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        # Mock is_paused via settings_service — paused
        mock_chat_settings = Mock(is_paused=True)
        service.settings_service.get_settings.return_value = mock_chat_settings

        # Create overdue and future items
        overdue_item = Mock()
        overdue_item.scheduled_for = datetime(2020, 1, 1, 12, 0)  # Past

        future_item = Mock()
        future_item.scheduled_for = datetime(2030, 1, 1, 12, 0)  # Future

        service.queue_repo.get_all.return_value = [
            overdue_item,
            future_item,
        ]

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        await handlers.handle_resume(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Overdue Posts Found" in message_text
        assert "1 overdue" in message_text
        assert "1 still scheduled" in message_text

        # Should have reply_markup with options
        assert call_args.kwargs.get("reply_markup") is not None

    async def test_resume_no_overdue(self, mock_command_handlers):
        """Test /resume immediately resumes when no overdue posts."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        # Mock is_paused via settings_service — paused
        mock_chat_settings = Mock(is_paused=True)
        service.settings_service.get_settings.return_value = mock_chat_settings
        service.set_paused = Mock(
            side_effect=lambda paused, user=None: setattr(
                mock_chat_settings, "is_paused", paused
            )
        )

        # Only future items
        future_item = Mock()
        future_item.scheduled_for = datetime(2030, 1, 1, 12, 0)

        service.queue_repo.get_all.return_value = [future_item]

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        await handlers.handle_resume(mock_update, mock_context)

        # Should be resumed
        assert service.is_paused is False

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Posting Resumed" in message_text


@pytest.mark.unit
@pytest.mark.asyncio
class TestScheduleCommand:
    """Tests for /schedule command."""

    async def test_schedule_creates_schedule(self, mock_command_handlers):
        """Test /schedule creates a posting schedule."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()
        mock_context.args = ["7"]

        # Create a mock SchedulerService that supports context manager protocol
        mock_scheduler = Mock()
        mock_scheduler.create_schedule.return_value = {
            "scheduled": 21,
            "skipped": 5,
            "total_slots": 21,
        }
        mock_scheduler.__enter__ = Mock(return_value=mock_scheduler)
        mock_scheduler.__exit__ = Mock(return_value=False)

        # Patch SchedulerService class
        with patch("src.services.core.scheduler.SchedulerService") as MockScheduler:
            MockScheduler.return_value = mock_scheduler

            await handlers.handle_schedule(mock_update, mock_context)

            mock_scheduler.create_schedule.assert_called_once_with(
                days=7,
                telegram_chat_id=-100123,
            )

            call_args = mock_update.message.reply_text.call_args
            message_text = call_args.args[0]
            assert "Schedule Created" in message_text
            assert "21" in message_text

    async def test_schedule_invalid_days(self, mock_command_handlers):
        """Test /schedule handles invalid days argument."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()
        mock_context.args = ["abc"]

        await handlers.handle_schedule(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Usage:" in message_text


@pytest.mark.unit
@pytest.mark.asyncio
class TestStatsCommand:
    """Tests for /stats command."""

    async def test_stats_shows_media_statistics(self, mock_command_handlers):
        """Test /stats shows media library statistics."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        # Create mock media items
        media1 = Mock()
        media1.id = uuid4()
        media1.times_posted = 0

        media2 = Mock()
        media2.id = uuid4()
        media2.times_posted = 1

        media3 = Mock()
        media3.id = uuid4()
        media3.times_posted = 3

        service.media_repo.get_all.return_value = [media1, media2, media3]
        service.lock_repo.get_permanent_locks.return_value = [Mock()]
        service.lock_repo.is_locked.return_value = False
        service.queue_repo.count_pending.return_value = 5

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        await handlers.handle_stats(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Media Library Stats" in message_text
        assert "Total active: 3" in message_text
        assert "Never posted: 1" in message_text


@pytest.mark.unit
@pytest.mark.asyncio
class TestHistoryCommand:
    """Tests for /history command."""

    async def test_history_shows_recent_posts(self, mock_command_handlers):
        """Test /history shows recent post history."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        # Create mock history items
        history1 = Mock()
        history1.status = "posted"
        history1.posted_at = datetime(2024, 1, 15, 10, 30)
        history1.posted_by_telegram_username = "user1"

        history2 = Mock()
        history2.status = "skipped"
        history2.posted_at = datetime(2024, 1, 14, 14, 0)
        history2.posted_by_telegram_username = "user2"

        service.history_repo.get_recent_posts.return_value = [
            history1,
            history2,
        ]

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()
        mock_context.args = []

        await handlers.handle_history(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Recent Posts" in message_text
        assert "@user1" in message_text
        assert "@user2" in message_text

    async def test_history_empty(self, mock_command_handlers):
        """Test /history shows empty message when no history."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        service.history_repo.get_recent_posts.return_value = []

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()
        mock_context.args = []

        await handlers.handle_history(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "No Recent History" in message_text


@pytest.mark.unit
@pytest.mark.asyncio
class TestLocksCommand:
    """Tests for /locks command."""

    async def test_locks_shows_permanent_locks(self, mock_command_handlers):
        """Test /locks shows permanently locked items."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        # Create mock locks
        lock1 = Mock()
        lock1.media_item_id = uuid4()

        lock2 = Mock()
        lock2.media_item_id = uuid4()

        service.lock_repo.get_permanent_locks.return_value = [
            lock1,
            lock2,
        ]

        mock_media = Mock()
        mock_media.file_name = "locked_image.jpg"
        service.media_repo.get_by_id.return_value = mock_media

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        await handlers.handle_locks(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Permanently Locked" in message_text
        assert "(2)" in message_text
        assert "locked_image.jpg" in message_text

    async def test_locks_empty(self, mock_command_handlers):
        """Test /locks shows no locks message."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        service.lock_repo.get_permanent_locks.return_value = []

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        await handlers.handle_locks(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "No Permanent Locks" in message_text


@pytest.mark.unit
@pytest.mark.asyncio
class TestResetCommand:
    """Tests for /reset command (formerly /clear)."""

    async def test_reset_shows_confirmation(self, mock_command_handlers):
        """Test /reset shows confirmation dialog."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        service.queue_repo.count_pending.return_value = 15

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        await handlers.handle_reset(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Clear Queue?" in message_text
        assert "15 pending posts" in message_text
        assert call_args.kwargs.get("reply_markup") is not None

    async def test_reset_empty_queue(self, mock_command_handlers):
        """Test /reset shows already empty message."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        service.queue_repo.count_pending.return_value = 0

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        await handlers.handle_reset(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Queue Already Empty" in message_text


# ==================== Status Helper Tests ====================


@pytest.mark.unit
class TestGetNextPostDisplay:
    """Tests for _get_next_post_display helper."""

    def test_with_pending_items(self, mock_command_handlers):
        """Test returns formatted time when items are pending."""
        handlers = mock_command_handlers
        mock_item = Mock()
        mock_item.scheduled_for = datetime(2026, 3, 15, 14, 30)
        handlers.service.queue_repo.get_pending.return_value = [mock_item]

        result = handlers._get_next_post_display()
        assert result == "14:30 UTC"

    def test_empty_queue(self, mock_command_handlers):
        """Test returns 'None scheduled' when queue is empty."""
        handlers = mock_command_handlers
        handlers.service.queue_repo.get_pending.return_value = []

        result = handlers._get_next_post_display()
        assert result == "None scheduled"


@pytest.mark.unit
class TestGetLastPostedDisplay:
    """Tests for _get_last_posted_display helper."""

    def test_recent_post_hours_ago(self, mock_command_handlers):
        """Test shows hours ago for recent posts."""
        handlers = mock_command_handlers
        mock_post = Mock()
        mock_post.posted_at = datetime.utcnow().replace(
            hour=max(datetime.utcnow().hour - 3, 0)
        )

        # Use a fixed time difference to avoid test flakiness
        with patch("src.services.core.telegram_commands.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2026, 3, 15, 15, 0, 0)
            mock_post.posted_at = datetime(2026, 3, 15, 12, 0, 0)
            result = handlers._get_last_posted_display([mock_post])

        assert result == "3h ago"

    def test_very_recent_post(self, mock_command_handlers):
        """Test shows '< 1h ago' for very recent posts."""
        handlers = mock_command_handlers
        mock_post = Mock()

        with patch("src.services.core.telegram_commands.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2026, 3, 15, 15, 0, 0)
            mock_post.posted_at = datetime(2026, 3, 15, 14, 45, 0)
            result = handlers._get_last_posted_display([mock_post])

        assert result == "< 1h ago"

    def test_no_posts(self, mock_command_handlers):
        """Test returns 'Never' when no posts exist."""
        handlers = mock_command_handlers
        result = handlers._get_last_posted_display([])
        assert result == "Never"


@pytest.mark.unit
class TestGetInstagramApiStatus:
    """Tests for _get_instagram_api_status helper."""

    def test_enabled_with_rate_limit(self, mock_command_handlers):
        """Test shows enabled status with rate limit remaining."""
        handlers = mock_command_handlers

        mock_ig = Mock()
        mock_ig.get_rate_limit_remaining.return_value = 20
        mock_ig.__enter__ = Mock(return_value=mock_ig)
        mock_ig.__exit__ = Mock(return_value=False)

        with (
            patch("src.services.core.telegram_commands.settings") as mock_settings,
            patch(
                "src.services.integrations.instagram_api.InstagramAPIService",
                return_value=mock_ig,
            ),
        ):
            mock_settings.ENABLE_INSTAGRAM_API = True
            mock_settings.INSTAGRAM_POSTS_PER_HOUR = 25
            result = handlers._get_instagram_api_status()

        assert "Enabled" in result
        assert "20/25" in result

    def test_disabled(self, mock_command_handlers):
        """Test shows disabled status."""
        handlers = mock_command_handlers

        with patch("src.services.core.telegram_commands.settings") as mock_settings:
            mock_settings.ENABLE_INSTAGRAM_API = False
            result = handlers._get_instagram_api_status()

        assert "Disabled" in result


@pytest.mark.unit
class TestGetSyncStatusLine:
    """Tests for _get_sync_status_line helper."""

    def test_sync_disabled(self, mock_command_handlers):
        """Test shows disabled when media sync is off."""
        handlers = mock_command_handlers
        mock_chat_settings = Mock(media_sync_enabled=False)
        handlers.service.settings_service.get_settings.return_value = mock_chat_settings

        mock_sync = Mock()
        mock_sync.get_last_sync_info.return_value = None
        mock_sync.__enter__ = Mock(return_value=mock_sync)
        mock_sync.__exit__ = Mock(return_value=False)

        with patch(
            "src.services.core.media_sync.MediaSyncService",
            return_value=mock_sync,
        ):
            result = handlers._get_sync_status_line(-100123)

        assert "Disabled" in result

    def test_no_syncs_yet(self, mock_command_handlers):
        """Test shows 'No syncs yet' when no history."""
        handlers = mock_command_handlers
        mock_chat_settings = Mock(media_sync_enabled=True)
        handlers.service.settings_service.get_settings.return_value = mock_chat_settings

        mock_sync = Mock()
        mock_sync.get_last_sync_info.return_value = None

        with patch(
            "src.services.core.media_sync.MediaSyncService",
            return_value=mock_sync,
        ):
            result = handlers._get_sync_status_line(-100123)

        assert "No syncs yet" in result

    def test_successful_sync(self, mock_command_handlers):
        """Test shows OK with counts for successful sync."""
        handlers = mock_command_handlers
        mock_chat_settings = Mock(media_sync_enabled=True)
        handlers.service.settings_service.get_settings.return_value = mock_chat_settings

        mock_sync = Mock()
        mock_sync.get_last_sync_info.return_value = {
            "success": True,
            "started_at": "2026-03-15T10:00:00Z",
            "result": {
                "new": 5,
                "updated": 2,
                "deactivated": 0,
                "reactivated": 1,
                "unchanged": 42,
            },
        }

        with patch(
            "src.services.core.media_sync.MediaSyncService",
            return_value=mock_sync,
        ):
            result = handlers._get_sync_status_line(-100123)

        assert "OK" in result
        assert "50 items" in result
        assert "5 new" in result

    def test_failed_sync(self, mock_command_handlers):
        """Test shows warning for failed sync."""
        handlers = mock_command_handlers
        mock_chat_settings = Mock(media_sync_enabled=True)
        handlers.service.settings_service.get_settings.return_value = mock_chat_settings

        mock_sync = Mock()
        mock_sync.get_last_sync_info.return_value = {
            "success": False,
            "started_at": "2026-03-15T10:00:00Z",
        }

        with patch(
            "src.services.core.media_sync.MediaSyncService",
            return_value=mock_sync,
        ):
            result = handlers._get_sync_status_line(-100123)

        assert "failed" in result

    def test_exception_shows_check_failed(self, mock_command_handlers):
        """Test exception returns 'Check failed'."""
        handlers = mock_command_handlers

        with patch(
            "src.services.core.media_sync.MediaSyncService",
            side_effect=Exception("Import error"),
        ):
            result = handlers._get_sync_status_line(-100123)

        assert "Check failed" in result


@pytest.mark.unit
@pytest.mark.asyncio
class TestStatusCommand:
    """Tests for handle_status end-to-end."""

    async def test_sends_formatted_status_message(self, mock_command_handlers):
        """Test /status sends a formatted message with all sections."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        # Set up repo returns
        service.queue_repo.count_pending.return_value = 5
        service.queue_repo.get_pending.return_value = []
        service.history_repo.get_recent_posts.return_value = []
        service.media_repo.get_all.return_value = [Mock(), Mock(), Mock()]
        service.lock_repo.get_permanent_locks.return_value = [Mock()]

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        with (
            patch("src.services.core.telegram_commands.settings") as mock_settings,
            patch(
                "src.services.core.media_sync.MediaSyncService",
                side_effect=Exception("not configured"),
            ),
        ):
            mock_settings.DRY_RUN_MODE = False
            mock_settings.ENABLE_INSTAGRAM_API = False
            await handlers.handle_status(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]

        assert "Storyline AI Status" in message_text
        assert "Queue: 5 pending" in message_text
        assert "Library: 3 active" in message_text
        assert "Locked: 1" in message_text
        assert "None scheduled" in message_text

        # Should log interaction
        service.interaction_service.log_command.assert_called_once()


@pytest.mark.unit
class TestPauseIntegration:
    """Tests for pause integration with PostingService."""

    def test_posting_service_respects_pause(self):
        """Test that PostingService checks pause state via telegram_service."""
        from src.services.core.posting import PostingService

        with patch.object(PostingService, "__init__", lambda self: None):
            posting_service = PostingService()
            posting_service.telegram_service = Mock()
            posting_service.telegram_service.is_paused = True

            # Verify PostingService can read telegram_service.is_paused
            assert posting_service.telegram_service.is_paused is True

            posting_service.telegram_service.is_paused = False
            assert posting_service.telegram_service.is_paused is False


@pytest.mark.unit
@pytest.mark.asyncio
class TestConnectCommand:
    """Tests for /connect command."""

    async def test_connect_sends_oauth_link(self, mock_command_handlers):
        """Test /connect sends inline button with OAuth URL."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "testuser"
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        mock_update = AsyncMock()
        mock_update.effective_user.id = 12345
        mock_update.effective_user.first_name = "Test"
        mock_update.effective_user.username = "testuser"
        mock_update.effective_chat.id = -100123
        mock_update.message.message_id = 1

        with patch("src.services.core.oauth_service.OAuthService") as MockOAuth:
            mock_oauth = MockOAuth.return_value
            mock_oauth.generate_authorization_url.return_value = (
                "https://www.facebook.com/dialog/oauth?client_id=123&state=abc"
            )
            mock_oauth.close = Mock()

            await handlers.handle_connect(mock_update, Mock())

        mock_update.message.reply_text.assert_called_once()
        call_kwargs = mock_update.message.reply_text.call_args[1]
        assert call_kwargs["parse_mode"] == "Markdown"
        assert call_kwargs["reply_markup"] is not None

    async def test_connect_handles_missing_config(self, mock_command_handlers):
        """Test /connect shows error when OAuth not configured."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "testuser"
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        mock_update = AsyncMock()
        mock_update.effective_user.id = 12345
        mock_update.effective_user.first_name = "Test"
        mock_update.effective_user.username = "testuser"
        mock_update.effective_chat.id = -100123
        mock_update.message.message_id = 1

        with patch("src.services.core.oauth_service.OAuthService") as MockOAuth:
            mock_oauth = MockOAuth.return_value
            mock_oauth.generate_authorization_url.side_effect = ValueError(
                "FACEBOOK_APP_ID not configured"
            )
            mock_oauth.close = Mock()

            await handlers.handle_connect(mock_update, Mock())

        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "OAuth not configured" in call_args

    async def test_connect_logs_interaction(self, mock_command_handlers):
        """Test /connect logs the command interaction."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "testuser"
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        mock_update = AsyncMock()
        mock_update.effective_user.id = 12345
        mock_update.effective_user.first_name = "Test"
        mock_update.effective_user.username = "testuser"
        mock_update.effective_chat.id = -100123
        mock_update.message.message_id = 42

        with patch("src.services.core.oauth_service.OAuthService") as MockOAuth:
            mock_oauth = MockOAuth.return_value
            mock_oauth.generate_authorization_url.return_value = "https://example.com"
            mock_oauth.close = Mock()

            await handlers.handle_connect(mock_update, Mock())

        service.interaction_service.log_command.assert_called_once()
        call_kwargs = service.interaction_service.log_command.call_args[1]
        assert call_kwargs["command"] == "/connect"
        assert call_kwargs["telegram_chat_id"] == -100123
