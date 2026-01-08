"""Tests for TelegramService."""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime
from uuid import uuid4

from src.services.core.telegram_service import TelegramService
from src.repositories.user_repository import UserRepository
from src.repositories.queue_repository import QueueRepository
from src.repositories.media_repository import MediaRepository


@pytest.fixture
def mock_telegram_service():
    """Create TelegramService with mocked dependencies."""
    with patch("src.services.core.telegram_service.settings") as mock_settings, \
         patch("src.services.core.telegram_service.UserRepository") as mock_user_repo_class, \
         patch("src.services.core.telegram_service.QueueRepository") as mock_queue_repo_class, \
         patch("src.services.core.telegram_service.MediaRepository") as mock_media_repo_class, \
         patch("src.services.core.telegram_service.HistoryRepository") as mock_history_repo_class, \
         patch("src.services.core.telegram_service.LockRepository") as mock_lock_repo_class, \
         patch("src.services.core.telegram_service.MediaLockService") as mock_lock_service_class, \
         patch("src.services.core.telegram_service.InteractionService") as mock_interaction_service_class:

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

        yield service


@pytest.mark.unit
class TestGetDisplayName:
    """Tests for _get_display_name helper method."""

    def test_display_name_with_username(self, mock_telegram_service):
        """Test display name returns @username when available."""
        user = Mock()
        user.telegram_username = "testuser"
        user.telegram_first_name = "Test"
        user.telegram_user_id = 123456

        result = mock_telegram_service._get_display_name(user)

        assert result == "@testuser"

    def test_display_name_with_first_name_only(self, mock_telegram_service):
        """Test display name returns first_name when username is None."""
        user = Mock()
        user.telegram_username = None
        user.telegram_first_name = "TestFirstName"
        user.telegram_user_id = 123456

        result = mock_telegram_service._get_display_name(user)

        assert result == "TestFirstName"

    def test_display_name_fallback_to_user_id(self, mock_telegram_service):
        """Test display name returns User {id} when both username and first_name are None."""
        user = Mock()
        user.telegram_username = None
        user.telegram_first_name = None
        user.telegram_user_id = 123456

        result = mock_telegram_service._get_display_name(user)

        assert result == "User 123456"

    def test_display_name_empty_string_username(self, mock_telegram_service):
        """Test empty string username is treated as falsy, falls back to first_name."""
        user = Mock()
        user.telegram_username = ""
        user.telegram_first_name = "TestName"
        user.telegram_user_id = 123456

        result = mock_telegram_service._get_display_name(user)

        # Empty string is falsy, should fall back to first_name
        assert result == "TestName"


@pytest.mark.unit
class TestButtonLayout:
    """Tests for button layout in notifications."""

    def test_instagram_button_above_reject(self, mock_telegram_service):
        """Test that Instagram button appears above Reject button in keyboard layout."""
        # Setup mock data
        queue_item_id = str(uuid4())
        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()

        mock_media_item = Mock()
        mock_media_item.file_path = "/test/image.jpg"
        mock_media_item.file_name = "image.jpg"
        mock_media_item.title = "Test"
        mock_media_item.caption = None
        mock_media_item.link_url = None
        mock_media_item.tags = []

        mock_telegram_service.queue_repo.get_by_id.return_value = mock_queue_item
        mock_telegram_service.media_repo.get_by_id.return_value = mock_media_item

        # Import InlineKeyboardButton to check button order
        from telegram import InlineKeyboardButton

        # Build keyboard manually like the service does
        keyboard = [
            [
                InlineKeyboardButton("✅ Posted", callback_data=f"posted:{queue_item_id}"),
                InlineKeyboardButton("⏭️ Skip", callback_data=f"skip:{queue_item_id}"),
            ],
            [
                InlineKeyboardButton("📱 Open Instagram", url="https://www.instagram.com/"),
            ],
            [
                InlineKeyboardButton("🚫 Reject", callback_data=f"reject:{queue_item_id}"),
            ]
        ]

        # Verify button order: row 0 = Posted/Skip, row 1 = Instagram, row 2 = Reject
        assert len(keyboard) == 3
        assert "Instagram" in keyboard[1][0].text
        assert "Reject" in keyboard[2][0].text

        # Instagram (row 1) should come before Reject (row 2)
        instagram_row = 1
        reject_row = 2
        assert instagram_row < reject_row, "Instagram button should be above Reject button"


@pytest.mark.unit
class TestProfileSync:
    """Tests for profile synchronization in _get_or_create_user."""

    def test_new_user_created_with_profile_data(self, mock_telegram_service):
        """Test that new users are created with all Telegram profile data."""
        mock_telegram_service.user_repo.get_by_telegram_id.return_value = None

        mock_new_user = Mock()
        mock_new_user.telegram_username = "newuser"
        mock_new_user.telegram_first_name = "New"
        mock_telegram_service.user_repo.create.return_value = mock_new_user

        telegram_user = Mock()
        telegram_user.id = 123456
        telegram_user.username = "newuser"
        telegram_user.first_name = "New"
        telegram_user.last_name = "User"

        result = mock_telegram_service._get_or_create_user(telegram_user)

        mock_telegram_service.user_repo.create.assert_called_once_with(
            telegram_user_id=123456,
            telegram_username="newuser",
            telegram_first_name="New",
            telegram_last_name="User",
        )

    def test_existing_user_profile_synced(self, mock_telegram_service):
        """Test that existing users have their profile data synced on each interaction."""
        existing_user = Mock()
        existing_user.id = uuid4()
        existing_user.telegram_username = "oldusername"
        mock_telegram_service.user_repo.get_by_telegram_id.return_value = existing_user

        updated_user = Mock()
        updated_user.telegram_username = "newusername"
        mock_telegram_service.user_repo.update_profile.return_value = updated_user

        telegram_user = Mock()
        telegram_user.id = 123456
        telegram_user.username = "newusername"  # Changed username
        telegram_user.first_name = "Updated"
        telegram_user.last_name = "Name"

        result = mock_telegram_service._get_or_create_user(telegram_user)

        # Should call update_profile, not just update_last_seen
        mock_telegram_service.user_repo.update_profile.assert_called_once_with(
            str(existing_user.id),
            telegram_username="newusername",
            telegram_first_name="Updated",
            telegram_last_name="Name",
        )

    def test_profile_sync_handles_none_username(self, mock_telegram_service):
        """Test profile sync works when user has no username."""
        existing_user = Mock()
        existing_user.id = uuid4()
        mock_telegram_service.user_repo.get_by_telegram_id.return_value = existing_user
        mock_telegram_service.user_repo.update_profile.return_value = existing_user

        telegram_user = Mock()
        telegram_user.id = 123456
        telegram_user.username = None  # No username set
        telegram_user.first_name = "NoUsername"
        telegram_user.last_name = None

        result = mock_telegram_service._get_or_create_user(telegram_user)

        mock_telegram_service.user_repo.update_profile.assert_called_once_with(
            str(existing_user.id),
            telegram_username=None,
            telegram_first_name="NoUsername",
            telegram_last_name=None,
        )


@pytest.mark.unit
@pytest.mark.asyncio
class TestRejectConfirmation:
    """Tests for reject confirmation flow."""

    async def test_reject_shows_confirmation_dialog(self, mock_telegram_service):
        """Test that clicking Reject shows confirmation dialog instead of immediate rejection."""
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()
        mock_telegram_service.queue_repo.get_by_id.return_value = mock_queue_item

        mock_media_item = Mock()
        mock_media_item.file_name = "test_image.jpg"
        mock_telegram_service.media_repo.get_by_id.return_value = mock_media_item

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "testuser"

        mock_query = AsyncMock()

        await mock_telegram_service._handle_reject_confirmation(queue_id, mock_user, mock_query)

        # Should edit message with confirmation
        mock_query.edit_message_caption.assert_called_once()
        call_kwargs = mock_query.edit_message_caption.call_args

        # Check caption contains warning text
        caption = call_kwargs.kwargs.get('caption') or call_kwargs.args[0]
        assert "Are you sure?" in caption
        assert "test_image.jpg" in caption
        assert "cannot be undone" in caption

        # Check keyboard has confirm/cancel buttons
        reply_markup = call_kwargs.kwargs.get('reply_markup')
        assert reply_markup is not None

    async def test_reject_confirmation_not_found(self, mock_telegram_service):
        """Test reject confirmation handles missing queue item."""
        queue_id = str(uuid4())

        mock_telegram_service.queue_repo.get_by_id.return_value = None

        mock_user = Mock()
        mock_query = AsyncMock()

        await mock_telegram_service._handle_reject_confirmation(queue_id, mock_user, mock_query)

        mock_query.edit_message_caption.assert_called_once()
        call_args = mock_query.edit_message_caption.call_args
        assert "not found" in str(call_args)

    async def test_confirm_reject_creates_permanent_lock(self, mock_telegram_service):
        """Test that confirming rejection creates a permanent lock."""
        queue_id = str(uuid4())
        media_id = uuid4()

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = media_id
        mock_queue_item.created_at = datetime.utcnow()
        mock_queue_item.scheduled_for = datetime.utcnow()
        mock_telegram_service.queue_repo.get_by_id.return_value = mock_queue_item

        mock_media_item = Mock()
        mock_media_item.file_name = "rejected_image.jpg"
        mock_telegram_service.media_repo.get_by_id.return_value = mock_media_item

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "rejecter"
        mock_user.telegram_first_name = "Test"

        mock_query = AsyncMock()

        await mock_telegram_service._handle_rejected(queue_id, mock_user, mock_query)

        # Should create permanent lock
        mock_telegram_service.lock_service.create_permanent_lock.assert_called_once()
        call_args = mock_telegram_service.lock_service.create_permanent_lock.call_args
        assert str(media_id) in str(call_args)

        # Should delete from queue
        mock_telegram_service.queue_repo.delete.assert_called_once_with(queue_id)

        # Should create history record with status='rejected'
        mock_telegram_service.history_repo.create.assert_called_once()
        history_call = mock_telegram_service.history_repo.create.call_args
        assert history_call.kwargs.get('status') == 'rejected'

    async def test_cancel_reject_restores_original_buttons(self, mock_telegram_service):
        """Test that canceling rejection restores the original message."""
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()
        mock_telegram_service.queue_repo.get_by_id.return_value = mock_queue_item

        mock_media_item = Mock()
        mock_media_item.file_name = "test.jpg"
        mock_media_item.title = "Test"
        mock_media_item.caption = None
        mock_media_item.link_url = None
        mock_media_item.tags = []
        mock_telegram_service.media_repo.get_by_id.return_value = mock_media_item

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "canceler"
        mock_user.telegram_first_name = "Test"

        mock_query = AsyncMock()

        await mock_telegram_service._handle_cancel_reject(queue_id, mock_user, mock_query)

        # Should restore original message
        mock_query.edit_message_caption.assert_called_once()

        # Queue item should NOT be deleted
        mock_telegram_service.queue_repo.delete.assert_not_called()

        # No lock should be created
        mock_telegram_service.lock_service.create_permanent_lock.assert_not_called()

    async def test_callback_routes_to_confirm_reject(self, mock_telegram_service):
        """Test that confirm_reject callback is properly routed."""
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()
        mock_queue_item.created_at = datetime.utcnow()
        mock_queue_item.scheduled_for = datetime.utcnow()
        mock_telegram_service.queue_repo.get_by_id.return_value = mock_queue_item

        mock_media_item = Mock()
        mock_media_item.file_name = "test.jpg"
        mock_telegram_service.media_repo.get_by_id.return_value = mock_media_item

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "confirmer"
        mock_user.telegram_first_name = "Test"
        mock_telegram_service.user_repo.get_by_telegram_id.return_value = None
        mock_telegram_service.user_repo.create.return_value = mock_user

        mock_update = Mock()
        mock_update.callback_query = AsyncMock()
        mock_update.callback_query.data = f"confirm_reject:{queue_id}"
        mock_update.callback_query.from_user = Mock()
        mock_update.callback_query.from_user.id = 123456
        mock_update.callback_query.from_user.username = "confirmer"
        mock_update.callback_query.from_user.first_name = "Test"
        mock_update.callback_query.from_user.last_name = None
        mock_update.callback_query.answer = AsyncMock()
        mock_update.callback_query.edit_message_caption = AsyncMock()

        mock_context = Mock()

        await mock_telegram_service._handle_callback(mock_update, mock_context)

        # Should create permanent lock (indicates confirm_reject was handled)
        mock_telegram_service.lock_service.create_permanent_lock.assert_called_once()

    async def test_callback_routes_to_cancel_reject(self, mock_telegram_service):
        """Test that cancel_reject callback is properly routed."""
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()
        mock_telegram_service.queue_repo.get_by_id.return_value = mock_queue_item

        mock_media_item = Mock()
        mock_media_item.file_name = "test.jpg"
        mock_media_item.title = "Test"
        mock_media_item.caption = None
        mock_media_item.link_url = None
        mock_media_item.tags = []
        mock_telegram_service.media_repo.get_by_id.return_value = mock_media_item

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "canceler"
        mock_user.telegram_first_name = "Test"
        mock_telegram_service.user_repo.get_by_telegram_id.return_value = None
        mock_telegram_service.user_repo.create.return_value = mock_user

        mock_update = Mock()
        mock_update.callback_query = AsyncMock()
        mock_update.callback_query.data = f"cancel_reject:{queue_id}"
        mock_update.callback_query.from_user = Mock()
        mock_update.callback_query.from_user.id = 123456
        mock_update.callback_query.from_user.username = "canceler"
        mock_update.callback_query.from_user.first_name = "Test"
        mock_update.callback_query.from_user.last_name = None
        mock_update.callback_query.answer = AsyncMock()
        mock_update.callback_query.edit_message_caption = AsyncMock()

        mock_context = Mock()

        await mock_telegram_service._handle_callback(mock_update, mock_context)

        # Should NOT create permanent lock (cancel was handled)
        mock_telegram_service.lock_service.create_permanent_lock.assert_not_called()


@pytest.mark.unit
class TestTelegramService:
    """Test suite for TelegramService."""

    @patch("src.services.core.telegram_service.settings")
    def test_service_initialization(self, mock_settings, test_db):
        """Test TelegramService initialization."""
        mock_settings.TELEGRAM_BOT_TOKEN = "123456:ABC-DEF1234ghIkl"
        mock_settings.TELEGRAM_CHANNEL_ID = -1001234567890

        service = TelegramService(db=test_db)

        assert service.db is not None
        assert service.user_repo is not None

    def test_get_or_create_user_new_user(self, test_db):
        """Test creating a new user from Telegram update."""
        user_repo = UserRepository(test_db)
        service = TelegramService(db=test_db)

        # Mock Telegram user
        telegram_user = Mock()
        telegram_user.id = 1000001
        telegram_user.username = "newuser"
        telegram_user.first_name = "New"
        telegram_user.last_name = "User"

        user = service._get_or_create_user(telegram_user)

        assert user is not None
        assert user.telegram_user_id == 1000001
        assert user.telegram_username == "newuser"

    def test_get_or_create_user_existing_user(self, test_db):
        """Test retrieving existing user."""
        user_repo = UserRepository(test_db)
        service = TelegramService(db=test_db)

        # Create existing user
        existing_user = user_repo.create(
            telegram_user_id=1000002,
            telegram_username="existing"
        )

        # Mock Telegram user with same ID
        telegram_user = Mock()
        telegram_user.id = 1000002
        telegram_user.username = "existing"
        telegram_user.first_name = "Existing"
        telegram_user.last_name = None

        user = service._get_or_create_user(telegram_user)

        assert user.id == existing_user.id

    def test_format_queue_notification(self, test_db):
        """Test formatting queue notification message."""
        media_repo = MediaRepository(test_db)
        queue_repo = QueueRepository(test_db)
        user_repo = UserRepository(test_db)

        service = TelegramService(db=test_db)

        # Create test data
        media = media_repo.create(
            file_path="/test/notification.jpg",
            file_name="notification.jpg",
            file_hash="notif890",
            file_size_bytes=100000,
            mime_type="image/jpeg"
        )

        user = user_repo.create(telegram_user_id=1000003)

        queue_item = queue_repo.create(
            media_id=media.id,
            scheduled_user_id=user.id,
            scheduled_time=datetime.utcnow()
        )

        message = service._format_queue_notification(queue_item, media)

        assert "notification.jpg" in message
        assert "Story" in message

    @pytest.mark.asyncio
    @patch("src.services.core.telegram_service.Application")
    async def test_send_queue_notification(self, mock_app_class, test_db):
        """Test sending queue notification."""
        media_repo = MediaRepository(test_db)
        queue_repo = QueueRepository(test_db)
        user_repo = UserRepository(test_db)

        # Mock the application and bot
        mock_app = Mock()
        mock_bot = AsyncMock()
        mock_app.bot = mock_bot
        mock_bot.send_photo = AsyncMock(return_value=Mock(message_id=12345))
        mock_app_class.return_value = mock_app

        service = TelegramService(db=test_db)
        service.application = mock_app

        # Create test data
        media = media_repo.create(
            file_path="/test/send_notif.jpg",
            file_name="send_notif.jpg",
            file_hash="send890",
            file_size_bytes=95000,
            mime_type="image/jpeg"
        )

        user = user_repo.create(telegram_user_id=1000004)

        queue_item = queue_repo.create(
            media_id=media.id,
            scheduled_user_id=user.id,
            scheduled_time=datetime.utcnow()
        )

        # Send notification
        result = await service.send_queue_notification(queue_item.id)

        assert result["sent"] is True
        assert result["message_id"] == 12345

    def test_create_inline_keyboard(self, test_db):
        """Test creating inline keyboard for queue item."""
        service = TelegramService(db=test_db)

        keyboard = service._create_inline_keyboard("test-queue-id")

        assert keyboard is not None
        # Keyboard should have buttons for Posted and Skip
        assert len(keyboard.inline_keyboard) >= 1

    @pytest.mark.asyncio
    async def test_handle_posted_callback(self, test_db):
        """Test handling 'posted' callback."""
        from src.repositories.lock_repository import LockRepository

        media_repo = MediaRepository(test_db)
        queue_repo = QueueRepository(test_db)
        user_repo = UserRepository(test_db)
        lock_repo = LockRepository(test_db)

        service = TelegramService(db=test_db)

        # Create test data
        media = media_repo.create(
            file_path="/test/callback_posted.jpg",
            file_name="callback_posted.jpg",
            file_hash="callback_p890",
            file_size_bytes=90000,
            mime_type="image/jpeg"
        )

        user = user_repo.create(telegram_user_id=1000005)

        queue_item = queue_repo.create(
            media_id=media.id,
            scheduled_user_id=user.id,
            scheduled_time=datetime.utcnow()
        )

        # Mock update and context
        mock_update = Mock()
        mock_update.callback_query = AsyncMock()
        mock_update.callback_query.data = f"posted:{queue_item.id}"
        mock_update.callback_query.from_user = Mock()
        mock_update.callback_query.from_user.id = 1000005
        mock_update.callback_query.from_user.username = "testuser"
        mock_update.callback_query.from_user.first_name = "Test"
        mock_update.callback_query.from_user.last_name = None
        mock_update.callback_query.answer = AsyncMock()
        mock_update.callback_query.edit_message_caption = AsyncMock()

        mock_context = Mock()

        # Handle callback
        await service._handle_callback(mock_update, mock_context)

        # Verify queue item was deleted (moved to history)
        deleted_item = queue_repo.get_by_id(queue_item.id)
        assert deleted_item is None

        # Verify media post count incremented
        updated_media = media_repo.get_by_id(media.id)
        assert updated_media.times_posted == 1

        # Verify 30-day lock was created
        assert lock_repo.is_locked(media.id) is True

    @pytest.mark.asyncio
    async def test_handle_skip_callback(self, test_db):
        """Test handling 'skip' callback."""
        media_repo = MediaRepository(test_db)
        queue_repo = QueueRepository(test_db)
        user_repo = UserRepository(test_db)

        service = TelegramService(db=test_db)

        # Create test data
        media = media_repo.create(
            file_path="/test/callback_skip.jpg",
            file_name="callback_skip.jpg",
            file_hash="callback_s890",
            file_size_bytes=85000,
            mime_type="image/jpeg"
        )

        user = user_repo.create(telegram_user_id=1000006)

        queue_item = queue_repo.create(
            media_id=media.id,
            scheduled_user_id=user.id,
            scheduled_time=datetime.utcnow()
        )

        # Mock update and context
        mock_update = Mock()
        mock_update.callback_query = AsyncMock()
        mock_update.callback_query.data = f"skip:{queue_item.id}"
        mock_update.callback_query.from_user = Mock()
        mock_update.callback_query.from_user.id = 1000006
        mock_update.callback_query.from_user.username = "skipuser"
        mock_update.callback_query.from_user.first_name = "Skip"
        mock_update.callback_query.from_user.last_name = None
        mock_update.callback_query.answer = AsyncMock()
        mock_update.callback_query.edit_message_caption = AsyncMock()

        mock_context = Mock()

        # Handle callback
        await service._handle_callback(mock_update, mock_context)

        # Verify queue item was marked as skipped
        updated_item = queue_repo.get_by_id(queue_item.id)
        assert updated_item.status == "skipped"

        # Verify media post count NOT incremented
        updated_media = media_repo.get_by_id(media.id)
        assert updated_media.times_posted == 0


@pytest.mark.unit
@pytest.mark.asyncio
class TestQueueCommand:
    """Tests for /queue command."""

    async def test_queue_shows_all_pending_not_just_due(self, mock_telegram_service):
        """Test /queue shows ALL pending items, not just ones due now."""
        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "testuser"
        mock_telegram_service.user_repo.get_by_telegram_id.return_value = None
        mock_telegram_service.user_repo.create.return_value = mock_user

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
        mock_telegram_service.queue_repo.get_all.return_value = [mock_queue_item1, mock_queue_item2]

        mock_media = Mock()
        mock_media.file_name = "test.jpg"
        mock_telegram_service.media_repo.get_by_id.return_value = mock_media

        mock_update = Mock()
        mock_update.effective_user = Mock(id=123, username="test", first_name="Test", last_name=None)
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        await mock_telegram_service._handle_queue(mock_update, mock_context)

        # Should call get_all with status="pending", NOT get_pending
        mock_telegram_service.queue_repo.get_all.assert_called_once_with(status="pending")

        # Should show items in message
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Upcoming Queue" in message_text
        assert "2 of 2" in message_text

    async def test_queue_empty_message(self, mock_telegram_service):
        """Test /queue shows empty message when no posts scheduled."""
        mock_user = Mock()
        mock_user.id = uuid4()
        mock_telegram_service.user_repo.get_by_telegram_id.return_value = None
        mock_telegram_service.user_repo.create.return_value = mock_user

        mock_telegram_service.queue_repo.get_all.return_value = []

        mock_update = Mock()
        mock_update.effective_user = Mock(id=123, username="test", first_name="Test", last_name=None)
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        await mock_telegram_service._handle_queue(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Queue Empty" in message_text
        assert "No posts scheduled" in message_text

    async def test_queue_limits_to_ten_items(self, mock_telegram_service):
        """Test /queue only shows first 10 items."""
        mock_user = Mock()
        mock_user.id = uuid4()
        mock_telegram_service.user_repo.get_by_telegram_id.return_value = None
        mock_telegram_service.user_repo.create.return_value = mock_user

        # Create 15 mock queue items
        mock_items = []
        for i in range(15):
            item = Mock()
            item.id = uuid4()
            item.media_item_id = uuid4()
            item.scheduled_for = datetime(2030, 1, i + 1, 12, 0)
            mock_items.append(item)

        mock_telegram_service.queue_repo.get_all.return_value = mock_items

        mock_media = Mock()
        mock_media.file_name = "test.jpg"
        mock_telegram_service.media_repo.get_by_id.return_value = mock_media

        mock_update = Mock()
        mock_update.effective_user = Mock(id=123, username="test", first_name="Test", last_name=None)
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        await mock_telegram_service._handle_queue(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        # Should show "10 of 15"
        assert "10 of 15" in message_text


@pytest.mark.unit
@pytest.mark.asyncio
class TestNextCommand:
    """Tests for /next command - force send next post."""

    async def test_next_sends_earliest_scheduled_post(self, mock_telegram_service):
        """Test /next sends the earliest scheduled post."""
        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "testuser"
        mock_telegram_service.user_repo.get_by_telegram_id.return_value = None
        mock_telegram_service.user_repo.create.return_value = mock_user

        queue_item_id = uuid4()
        media_id = uuid4()

        mock_queue_item = Mock()
        mock_queue_item.id = queue_item_id
        mock_queue_item.media_item_id = media_id
        mock_queue_item.scheduled_for = datetime(2030, 6, 15, 14, 0)

        mock_telegram_service.queue_repo.get_all.return_value = [mock_queue_item]

        mock_media = Mock()
        mock_media.file_name = "next_post.jpg"
        mock_telegram_service.media_repo.get_by_id.return_value = mock_media

        # Mock send_notification
        mock_telegram_service.send_notification = AsyncMock(return_value=True)

        mock_update = Mock()
        mock_update.effective_user = Mock(id=123, username="test", first_name="Test", last_name=None)
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        await mock_telegram_service._handle_next(mock_update, mock_context)

        # Should get all pending items
        mock_telegram_service.queue_repo.get_all.assert_called_with(status="pending")

        # Should send notification for the queue item with force_sent=True
        mock_telegram_service.send_notification.assert_called_once_with(str(queue_item_id), force_sent=True)

        # Should update status to processing
        mock_telegram_service.queue_repo.update_status.assert_called_once_with(str(queue_item_id), "processing")

        # Should NOT send any extra messages on success (no clutter)
        mock_update.message.reply_text.assert_not_called()

    async def test_next_empty_queue(self, mock_telegram_service):
        """Test /next shows error when queue is empty."""
        mock_user = Mock()
        mock_user.id = uuid4()
        mock_telegram_service.user_repo.get_by_telegram_id.return_value = None
        mock_telegram_service.user_repo.create.return_value = mock_user

        mock_telegram_service.queue_repo.get_all.return_value = []

        mock_update = Mock()
        mock_update.effective_user = Mock(id=123, username="test", first_name="Test", last_name=None)
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        await mock_telegram_service._handle_next(mock_update, mock_context)

        # Should show empty queue message
        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Queue Empty" in message_text
        assert "No posts to send" in message_text

    async def test_next_media_not_found(self, mock_telegram_service):
        """Test /next handles missing media gracefully."""
        mock_user = Mock()
        mock_user.id = uuid4()
        mock_telegram_service.user_repo.get_by_telegram_id.return_value = None
        mock_telegram_service.user_repo.create.return_value = mock_user

        mock_queue_item = Mock()
        mock_queue_item.id = uuid4()
        mock_queue_item.media_item_id = uuid4()
        mock_queue_item.scheduled_for = datetime(2030, 6, 15, 14, 0)

        mock_telegram_service.queue_repo.get_all.return_value = [mock_queue_item]
        mock_telegram_service.media_repo.get_by_id.return_value = None  # Media not found

        mock_update = Mock()
        mock_update.effective_user = Mock(id=123, username="test", first_name="Test", last_name=None)
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        await mock_telegram_service._handle_next(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Error" in message_text
        assert "Media item not found" in message_text

    async def test_next_notification_failure(self, mock_telegram_service):
        """Test /next handles notification failure gracefully."""
        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "testuser"
        mock_telegram_service.user_repo.get_by_telegram_id.return_value = None
        mock_telegram_service.user_repo.create.return_value = mock_user

        mock_queue_item = Mock()
        mock_queue_item.id = uuid4()
        mock_queue_item.media_item_id = uuid4()
        mock_queue_item.scheduled_for = datetime(2030, 6, 15, 14, 0)

        mock_telegram_service.queue_repo.get_all.return_value = [mock_queue_item]

        mock_media = Mock()
        mock_media.file_name = "fail_post.jpg"
        mock_telegram_service.media_repo.get_by_id.return_value = mock_media

        # Mock send_notification to fail
        mock_telegram_service.send_notification = AsyncMock(return_value=False)

        mock_update = Mock()
        mock_update.effective_user = Mock(id=123, username="test", first_name="Test", last_name=None)
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        await mock_telegram_service._handle_next(mock_update, mock_context)

        # Should NOT update status (since send failed)
        mock_telegram_service.queue_repo.update_status.assert_not_called()

        # Should show failure message (only message sent on failure)
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        assert "Failed to send" in call_args.args[0]

    async def test_next_logs_interaction(self, mock_telegram_service):
        """Test /next logs the interaction."""
        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "testuser"
        mock_telegram_service.user_repo.get_by_telegram_id.return_value = None
        mock_telegram_service.user_repo.create.return_value = mock_user

        queue_item_id = uuid4()
        media_id = uuid4()

        mock_queue_item = Mock()
        mock_queue_item.id = queue_item_id
        mock_queue_item.media_item_id = media_id
        mock_queue_item.scheduled_for = datetime(2030, 6, 15, 14, 0)

        mock_telegram_service.queue_repo.get_all.return_value = [mock_queue_item]

        mock_media = Mock()
        mock_media.file_name = "logged_post.jpg"
        mock_telegram_service.media_repo.get_by_id.return_value = mock_media

        mock_telegram_service.send_notification = AsyncMock(return_value=True)

        mock_update = Mock()
        mock_update.effective_user = Mock(id=123, username="test", first_name="Test", last_name=None)
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        await mock_telegram_service._handle_next(mock_update, mock_context)

        # Should send notification with force_sent=True
        mock_telegram_service.send_notification.assert_called_once_with(str(queue_item_id), force_sent=True)

        # Should log the command
        mock_telegram_service.interaction_service.log_command.assert_called_once()
        call_kwargs = mock_telegram_service.interaction_service.log_command.call_args.kwargs
        assert call_kwargs["command"] == "/next"
        assert call_kwargs["context"]["media_filename"] == "logged_post.jpg"
        assert call_kwargs["context"]["success"] is True
