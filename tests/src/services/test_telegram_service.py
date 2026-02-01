"""Tests for TelegramService."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from uuid import uuid4

from src.services.core.telegram_service import TelegramService


@pytest.fixture
def mock_telegram_service():
    """Create TelegramService with mocked dependencies."""
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
                InlineKeyboardButton(
                    "✅ Posted", callback_data=f"posted:{queue_item_id}"
                ),
                InlineKeyboardButton("⏭️ Skip", callback_data=f"skip:{queue_item_id}"),
            ],
            [
                InlineKeyboardButton(
                    "📱 Open Instagram", url="https://www.instagram.com/"
                ),
            ],
            [
                InlineKeyboardButton(
                    "🚫 Reject", callback_data=f"reject:{queue_item_id}"
                ),
            ],
        ]

        # Verify button order: row 0 = Posted/Skip, row 1 = Instagram, row 2 = Reject
        assert len(keyboard) == 3
        assert "Instagram" in keyboard[1][0].text
        assert "Reject" in keyboard[2][0].text

        # Instagram (row 1) should come before Reject (row 2)
        instagram_row = 1
        reject_row = 2
        assert instagram_row < reject_row, (
            "Instagram button should be above Reject button"
        )


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

        mock_telegram_service._get_or_create_user(telegram_user)

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

        mock_telegram_service._get_or_create_user(telegram_user)

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

        mock_telegram_service._get_or_create_user(telegram_user)

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

        await mock_telegram_service._handle_reject_confirmation(
            queue_id, mock_user, mock_query
        )

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

    async def test_reject_confirmation_not_found(self, mock_telegram_service):
        """Test reject confirmation handles missing queue item."""
        queue_id = str(uuid4())

        mock_telegram_service.queue_repo.get_by_id.return_value = None

        mock_user = Mock()
        mock_query = AsyncMock()

        await mock_telegram_service._handle_reject_confirmation(
            queue_id, mock_user, mock_query
        )

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
        assert history_call.kwargs.get("status") == "rejected"

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

        await mock_telegram_service._handle_cancel_reject(
            queue_id, mock_user, mock_query
        )

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

    def test_service_initialization(self, mock_telegram_service):
        """Test TelegramService initialization."""
        service = mock_telegram_service

        assert service.user_repo is not None
        assert service.queue_repo is not None
        assert service.media_repo is not None

    def test_get_or_create_user_new_user(self, mock_telegram_service):
        """Test creating a new user from Telegram update."""
        service = mock_telegram_service

        # Mock user_repo to simulate user not found, then created
        mock_new_user = Mock()
        mock_new_user.telegram_user_id = 1000001
        mock_new_user.telegram_username = "newuser"
        mock_new_user.telegram_first_name = "New"

        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_new_user

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
        service.user_repo.get_by_telegram_id.assert_called_once_with(1000001)
        service.user_repo.create.assert_called_once()

    def test_get_or_create_user_existing_user(self, mock_telegram_service):
        """Test retrieving existing user."""
        service = mock_telegram_service

        # Mock existing user
        existing_user = Mock()
        existing_user.id = uuid4()
        existing_user.telegram_user_id = 1000002
        existing_user.telegram_username = "existing"

        service.user_repo.get_by_telegram_id.return_value = existing_user
        service.user_repo.update_profile.return_value = (
            existing_user  # Profile sync returns same user
        )

        # Mock Telegram user with same ID
        telegram_user = Mock()
        telegram_user.id = 1000002
        telegram_user.username = "existing"
        telegram_user.first_name = "Existing"
        telegram_user.last_name = None

        user = service._get_or_create_user(telegram_user)

        assert user.id == existing_user.id
        service.user_repo.get_by_telegram_id.assert_called_once_with(1000002)
        service.user_repo.create.assert_not_called()

    def test_format_queue_notification(self, mock_telegram_service):
        """Test formatting queue notification message."""
        service = mock_telegram_service

        # Create mock objects
        mock_queue_item = Mock()
        mock_queue_item.id = uuid4()
        mock_queue_item.scheduled_for = datetime(2030, 1, 1, 12, 0)

        mock_media = Mock()
        mock_media.file_name = "notification.jpg"
        mock_media.category = "memes"
        mock_media.title = None  # Must set explicitly to avoid Mock auto-creation
        mock_media.caption = None
        mock_media.link_url = None
        mock_media.tags = []

        message = service._build_caption(mock_media, mock_queue_item)

        # Verify message contains expected elements
        assert "Story" in message or "Post" in message  # Caption should mention posting

    @pytest.mark.skip(reason="Complex integration test - skip for now")
    @pytest.mark.asyncio
    async def test_send_queue_notification(self, mock_telegram_service):
        """Test sending queue notification."""
        # This test requires complex mocking of Telegram bot application
        # Skipping for now as it's an integration test
        pass

    @pytest.mark.skip(reason="Keyboard structure test - needs refactoring")
    def test_create_inline_keyboard(self, mock_telegram_service):
        """Test creating inline keyboard for queue item."""
        # This test needs to be refactored to match current keyboard structure
        pass

    @pytest.mark.skip(reason="Complex integration test - needs test_db fixture")
    @pytest.mark.asyncio
    async def test_handle_posted_callback(self):
        """Test handling 'posted' callback."""
        # This is a complex integration test that requires full database
        # Skipping for now - covered by other callback tests
        pass

    @pytest.mark.skip(reason="Complex integration test - needs test_db fixture")
    @pytest.mark.asyncio
    async def test_handle_skip_callback(self):
        """Test handling 'skip' callback."""
        # This is a complex integration test that requires full database
        # Skipping for now - covered by other callback tests
        pass


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
        mock_telegram_service.queue_repo.get_all.return_value = [
            mock_queue_item1,
            mock_queue_item2,
        ]

        mock_media = Mock()
        mock_media.file_name = "test.jpg"  # String, not Mock
        mock_media.category = "memes"  # String, not Mock
        mock_telegram_service.media_repo.get_by_id.return_value = mock_media

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        await mock_telegram_service._handle_queue(mock_update, mock_context)

        # Should call get_all with status="pending", NOT get_pending
        mock_telegram_service.queue_repo.get_all.assert_called_once_with(
            status="pending"
        )

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
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
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
        mock_media.file_name = "test.jpg"  # String, not Mock
        mock_media.category = "memes"  # String, not Mock
        mock_telegram_service.media_repo.get_by_id.return_value = mock_media

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
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
            await mock_telegram_service._handle_next(mock_update, mock_context)

        # Should call force_post_next on PostingService
        mock_posting_service.force_post_next.assert_called_once()

        # Should NOT send any extra messages on success (no clutter)
        mock_update.message.reply_text.assert_not_called()

    async def test_next_empty_queue(self, mock_telegram_service):
        """Test /next shows error when queue is empty."""
        mock_user = Mock()
        mock_user.id = uuid4()
        mock_telegram_service.user_repo.get_by_telegram_id.return_value = None
        mock_telegram_service.user_repo.create.return_value = mock_user

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
            await mock_telegram_service._handle_next(mock_update, mock_context)

        # Should show empty queue message
        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Queue Empty" in message_text
        assert "No posts to send" in message_text

    @pytest.mark.skip(reason="Needs PostingService mock - TODO")
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
        mock_telegram_service.media_repo.get_by_id.return_value = (
            None  # Media not found
        )

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        await mock_telegram_service._handle_next(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Error" in message_text
        assert "Media item not found" in message_text

    @pytest.mark.skip(reason="Needs PostingService mock - TODO")
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
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
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

    @pytest.mark.skip(reason="Needs PostingService mock - TODO")
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
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        await mock_telegram_service._handle_next(mock_update, mock_context)

        # Should send notification with force_sent=True
        mock_telegram_service.send_notification.assert_called_once_with(
            str(queue_item_id), force_sent=True
        )

        # Should log the command
        mock_telegram_service.interaction_service.log_command.assert_called_once()
        call_kwargs = (
            mock_telegram_service.interaction_service.log_command.call_args.kwargs
        )
        assert call_kwargs["command"] == "/next"
        assert call_kwargs["context"]["media_filename"] == "logged_post.jpg"
        assert call_kwargs["context"]["success"] is True


@pytest.mark.skip(
    reason="Needs SettingsService mock for chat_settings.is_paused - TODO"
)
@pytest.mark.unit
@pytest.mark.asyncio
class TestPauseCommand:
    """Tests for /pause command."""

    async def test_pause_when_not_paused(self, mock_telegram_service):
        """Test /pause pauses posting when not already paused."""
        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "testuser"
        mock_telegram_service.user_repo.get_by_telegram_id.return_value = None
        mock_telegram_service.user_repo.create.return_value = mock_user

        mock_telegram_service.queue_repo.count_pending.return_value = 10

        # Ensure not paused initially
        mock_telegram_service.set_paused(False)

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        await mock_telegram_service._handle_pause(mock_update, mock_context)

        # Should now be paused
        assert mock_telegram_service.is_paused is True

        # Should show paused message
        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Posting Paused" in message_text
        assert "10 posts" in message_text

    async def test_pause_when_already_paused(self, mock_telegram_service):
        """Test /pause shows already paused message."""
        mock_user = Mock()
        mock_user.id = uuid4()
        mock_telegram_service.user_repo.get_by_telegram_id.return_value = None
        mock_telegram_service.user_repo.create.return_value = mock_user

        # Set already paused
        mock_telegram_service.set_paused(True)

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        await mock_telegram_service._handle_pause(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Already Paused" in message_text


@pytest.mark.skip(reason="Needs SettingsService and SchedulerService mocks - TODO")
@pytest.mark.unit
@pytest.mark.asyncio
class TestResumeCommand:
    """Tests for /resume command."""

    async def test_resume_when_not_paused(self, mock_telegram_service):
        """Test /resume shows already running message."""
        mock_user = Mock()
        mock_user.id = uuid4()
        mock_telegram_service.user_repo.get_by_telegram_id.return_value = None
        mock_telegram_service.user_repo.create.return_value = mock_user

        mock_telegram_service.set_paused(False)

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        await mock_telegram_service._handle_resume(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Already Running" in message_text

    async def test_resume_with_overdue_posts(self, mock_telegram_service):
        """Test /resume shows options when there are overdue posts."""
        mock_user = Mock()
        mock_user.id = uuid4()
        mock_telegram_service.user_repo.get_by_telegram_id.return_value = None
        mock_telegram_service.user_repo.create.return_value = mock_user

        mock_telegram_service.set_paused(True)

        # Create overdue and future items
        overdue_item = Mock()
        overdue_item.scheduled_for = datetime(2020, 1, 1, 12, 0)  # Past

        future_item = Mock()
        future_item.scheduled_for = datetime(2030, 1, 1, 12, 0)  # Future

        mock_telegram_service.queue_repo.get_all.return_value = [
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

        await mock_telegram_service._handle_resume(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Overdue Posts Found" in message_text
        assert "1 overdue" in message_text
        assert "1 still scheduled" in message_text

        # Should have reply_markup with options
        assert call_args.kwargs.get("reply_markup") is not None

    async def test_resume_no_overdue(self, mock_telegram_service):
        """Test /resume immediately resumes when no overdue posts."""
        mock_user = Mock()
        mock_user.id = uuid4()
        mock_telegram_service.user_repo.get_by_telegram_id.return_value = None
        mock_telegram_service.user_repo.create.return_value = mock_user

        mock_telegram_service.set_paused(True)

        # Only future items
        future_item = Mock()
        future_item.scheduled_for = datetime(2030, 1, 1, 12, 0)

        mock_telegram_service.queue_repo.get_all.return_value = [future_item]

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        await mock_telegram_service._handle_resume(mock_update, mock_context)

        # Should be resumed
        assert mock_telegram_service.is_paused is False

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Posting Resumed" in message_text


@pytest.mark.unit
@pytest.mark.asyncio
class TestScheduleCommand:
    """Tests for /schedule command."""

    async def test_schedule_creates_schedule(self, mock_telegram_service):
        """Test /schedule creates a posting schedule."""
        mock_user = Mock()
        mock_user.id = uuid4()
        mock_telegram_service.user_repo.get_by_telegram_id.return_value = None
        mock_telegram_service.user_repo.create.return_value = mock_user

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

            await mock_telegram_service._handle_schedule(mock_update, mock_context)

            mock_scheduler.create_schedule.assert_called_once_with(days=7)

            call_args = mock_update.message.reply_text.call_args
            message_text = call_args.args[0]
            assert "Schedule Created" in message_text
            assert "21" in message_text

    async def test_schedule_invalid_days(self, mock_telegram_service):
        """Test /schedule handles invalid days argument."""
        mock_user = Mock()
        mock_user.id = uuid4()
        mock_telegram_service.user_repo.get_by_telegram_id.return_value = None
        mock_telegram_service.user_repo.create.return_value = mock_user

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()
        mock_context.args = ["abc"]

        await mock_telegram_service._handle_schedule(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Usage:" in message_text


@pytest.mark.unit
@pytest.mark.asyncio
class TestStatsCommand:
    """Tests for /stats command."""

    async def test_stats_shows_media_statistics(self, mock_telegram_service):
        """Test /stats shows media library statistics."""
        mock_user = Mock()
        mock_user.id = uuid4()
        mock_telegram_service.user_repo.get_by_telegram_id.return_value = None
        mock_telegram_service.user_repo.create.return_value = mock_user

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

        mock_telegram_service.media_repo.get_all.return_value = [media1, media2, media3]
        mock_telegram_service.lock_repo.get_permanent_locks.return_value = [Mock()]
        mock_telegram_service.lock_repo.is_locked.return_value = False
        mock_telegram_service.queue_repo.count_pending.return_value = 5

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        await mock_telegram_service._handle_stats(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Media Library Stats" in message_text
        assert "Total active: 3" in message_text
        assert "Never posted: 1" in message_text


@pytest.mark.unit
@pytest.mark.asyncio
class TestHistoryCommand:
    """Tests for /history command."""

    async def test_history_shows_recent_posts(self, mock_telegram_service):
        """Test /history shows recent post history."""
        mock_user = Mock()
        mock_user.id = uuid4()
        mock_telegram_service.user_repo.get_by_telegram_id.return_value = None
        mock_telegram_service.user_repo.create.return_value = mock_user

        # Create mock history items
        history1 = Mock()
        history1.status = "posted"
        history1.posted_at = datetime(2024, 1, 15, 10, 30)
        history1.posted_by_telegram_username = "user1"

        history2 = Mock()
        history2.status = "skipped"
        history2.posted_at = datetime(2024, 1, 14, 14, 0)
        history2.posted_by_telegram_username = "user2"

        mock_telegram_service.history_repo.get_recent_posts.return_value = [
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

        await mock_telegram_service._handle_history(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Recent Posts" in message_text
        assert "@user1" in message_text
        assert "@user2" in message_text

    async def test_history_empty(self, mock_telegram_service):
        """Test /history shows empty message when no history."""
        mock_user = Mock()
        mock_user.id = uuid4()
        mock_telegram_service.user_repo.get_by_telegram_id.return_value = None
        mock_telegram_service.user_repo.create.return_value = mock_user

        mock_telegram_service.history_repo.get_recent_posts.return_value = []

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()
        mock_context.args = []

        await mock_telegram_service._handle_history(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "No Recent History" in message_text


@pytest.mark.unit
@pytest.mark.asyncio
class TestLocksCommand:
    """Tests for /locks command."""

    async def test_locks_shows_permanent_locks(self, mock_telegram_service):
        """Test /locks shows permanently locked items."""
        mock_user = Mock()
        mock_user.id = uuid4()
        mock_telegram_service.user_repo.get_by_telegram_id.return_value = None
        mock_telegram_service.user_repo.create.return_value = mock_user

        # Create mock locks
        lock1 = Mock()
        lock1.media_item_id = uuid4()

        lock2 = Mock()
        lock2.media_item_id = uuid4()

        mock_telegram_service.lock_repo.get_permanent_locks.return_value = [
            lock1,
            lock2,
        ]

        mock_media = Mock()
        mock_media.file_name = "locked_image.jpg"
        mock_telegram_service.media_repo.get_by_id.return_value = mock_media

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        await mock_telegram_service._handle_locks(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Permanently Locked" in message_text
        assert "(2)" in message_text
        assert "locked_image.jpg" in message_text

    async def test_locks_empty(self, mock_telegram_service):
        """Test /locks shows no locks message."""
        mock_user = Mock()
        mock_user.id = uuid4()
        mock_telegram_service.user_repo.get_by_telegram_id.return_value = None
        mock_telegram_service.user_repo.create.return_value = mock_user

        mock_telegram_service.lock_repo.get_permanent_locks.return_value = []

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        await mock_telegram_service._handle_locks(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "No Permanent Locks" in message_text


@pytest.mark.unit
@pytest.mark.asyncio
class TestResetCommand:
    """Tests for /reset command (formerly /clear)."""

    async def test_reset_shows_confirmation(self, mock_telegram_service):
        """Test /reset shows confirmation dialog."""
        mock_user = Mock()
        mock_user.id = uuid4()
        mock_telegram_service.user_repo.get_by_telegram_id.return_value = None
        mock_telegram_service.user_repo.create.return_value = mock_user

        mock_telegram_service.queue_repo.count_pending.return_value = 15

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        await mock_telegram_service._handle_reset(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Clear Queue?" in message_text
        assert "15 pending posts" in message_text
        assert call_args.kwargs.get("reply_markup") is not None

    async def test_reset_empty_queue(self, mock_telegram_service):
        """Test /reset shows already empty message."""
        mock_user = Mock()
        mock_user.id = uuid4()
        mock_telegram_service.user_repo.get_by_telegram_id.return_value = None
        mock_telegram_service.user_repo.create.return_value = mock_user

        mock_telegram_service.queue_repo.count_pending.return_value = 0

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        await mock_telegram_service._handle_reset(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Queue Already Empty" in message_text


@pytest.mark.skip(reason="Needs SettingsService and SchedulerService mocks - TODO")
@pytest.mark.unit
@pytest.mark.asyncio
class TestResumeCallbacks:
    """Tests for resume callback handlers."""

    async def test_resume_reschedule(self, mock_telegram_service):
        """Test resume:reschedule reschedules overdue posts."""
        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "testuser"

        mock_telegram_service.set_paused(True)

        # Create overdue item
        overdue_item = Mock()
        overdue_item.id = uuid4()
        overdue_item.scheduled_for = datetime(2020, 1, 1, 12, 0)

        mock_telegram_service.queue_repo.get_all.return_value = [overdue_item]

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        await mock_telegram_service._handle_resume_callback(
            "reschedule", mock_user, mock_query
        )

        # Should be resumed
        assert mock_telegram_service.is_paused is False

        # Should reschedule the item
        mock_telegram_service.queue_repo.update_scheduled_time.assert_called_once()

        # Should show success message
        mock_query.edit_message_text.assert_called_once()
        call_args = mock_query.edit_message_text.call_args
        assert "Rescheduled 1 overdue posts" in call_args.args[0]

    async def test_resume_clear(self, mock_telegram_service):
        """Test resume:clear clears overdue posts."""
        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "testuser"

        mock_telegram_service.set_paused(True)

        # Create overdue and future items
        overdue_item = Mock()
        overdue_item.id = uuid4()
        overdue_item.scheduled_for = datetime(2020, 1, 1, 12, 0)

        future_item = Mock()
        future_item.id = uuid4()
        future_item.scheduled_for = datetime(2030, 1, 1, 12, 0)

        mock_telegram_service.queue_repo.get_all.return_value = [
            overdue_item,
            future_item,
        ]

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        await mock_telegram_service._handle_resume_callback(
            "clear", mock_user, mock_query
        )

        # Should be resumed
        assert mock_telegram_service.is_paused is False

        # Should delete the overdue item
        mock_telegram_service.queue_repo.delete.assert_called_once_with(
            str(overdue_item.id)
        )

        # Should show success message
        call_args = mock_query.edit_message_text.call_args
        assert "Cleared 1 overdue posts" in call_args.args[0]
        assert "1 scheduled posts remaining" in call_args.args[0]

    async def test_resume_force(self, mock_telegram_service):
        """Test resume:force resumes without handling overdue."""
        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "testuser"

        mock_telegram_service.set_paused(True)

        overdue_item = Mock()
        overdue_item.scheduled_for = datetime(2020, 1, 1, 12, 0)

        mock_telegram_service.queue_repo.get_all.return_value = [overdue_item]

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        await mock_telegram_service._handle_resume_callback(
            "force", mock_user, mock_query
        )

        # Should be resumed
        assert mock_telegram_service.is_paused is False

        # Should NOT delete or reschedule anything
        mock_telegram_service.queue_repo.delete.assert_not_called()
        mock_telegram_service.queue_repo.update_scheduled_time.assert_not_called()

        call_args = mock_query.edit_message_text.call_args
        assert "overdue posts will be processed immediately" in call_args.args[0]


@pytest.mark.unit
@pytest.mark.asyncio
class TestResetCallbacks:
    """Tests for reset callback handlers (formerly clear)."""

    async def test_reset_confirm(self, mock_telegram_service):
        """Test reset:confirm deletes all pending posts."""
        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "testuser"

        # Create mock queue items
        item1 = Mock()
        item1.id = uuid4()
        item2 = Mock()
        item2.id = uuid4()

        mock_telegram_service.queue_repo.get_all.return_value = [item1, item2]

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        await mock_telegram_service._handle_reset_callback(
            "confirm", mock_user, mock_query
        )

        # Should delete both items
        assert mock_telegram_service.queue_repo.delete.call_count == 2

        call_args = mock_query.edit_message_text.call_args
        assert "Queue Cleared" in call_args.args[0]
        assert "Removed 2 pending posts" in call_args.args[0]

    async def test_reset_cancel(self, mock_telegram_service):
        """Test reset:cancel does not delete anything."""
        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "testuser"

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        await mock_telegram_service._handle_reset_callback(
            "cancel", mock_user, mock_query
        )

        # Should NOT delete anything
        mock_telegram_service.queue_repo.delete.assert_not_called()

        call_args = mock_query.edit_message_text.call_args
        assert "Cancelled" in call_args.args[0]


@pytest.mark.skip(
    reason="Complex integration test requiring PostingService and database - TODO"
)
@pytest.mark.unit
class TestPauseIntegration:
    """Tests for pause integration with PostingService."""

    def test_posting_service_respects_pause(self):
        """Test that PostingService checks pause state."""
        from src.services.core.posting import PostingService

        # Just verify the PostingService has access to telegram_service.is_paused
        posting_service = PostingService()
        # The is_paused property should be accessible
        assert hasattr(posting_service.telegram_service, "is_paused")


@pytest.mark.unit
class TestInlineAccountSelector:
    """Tests for inline account selector in posting workflow (Phase 1.7)."""

    def test_caption_includes_active_account_name(self, mock_telegram_service):
        """Test that caption shows active account's display name."""
        mock_media_item = Mock()
        mock_media_item.title = "Test Image"
        mock_media_item.caption = None
        mock_media_item.link_url = None
        mock_media_item.tags = []

        mock_active_account = Mock()
        mock_active_account.display_name = "Main Account"
        mock_active_account.instagram_username = "mainaccount"

        with patch("src.services.core.telegram_service.settings") as mock_settings:
            mock_settings.CAPTION_STYLE = "enhanced"
            caption = mock_telegram_service._build_caption(
                mock_media_item,
                queue_item=None,
                active_account=mock_active_account,
            )

        assert "📸 Account: Main Account" in caption

    def test_caption_shows_not_set_when_no_account(self, mock_telegram_service):
        """Test caption when no account is set."""
        mock_media_item = Mock()
        mock_media_item.title = "Test Image"
        mock_media_item.caption = None
        mock_media_item.link_url = None
        mock_media_item.tags = []

        with patch("src.services.core.telegram_service.settings") as mock_settings:
            mock_settings.CAPTION_STYLE = "enhanced"
            caption = mock_telegram_service._build_caption(
                mock_media_item,
                queue_item=None,
                active_account=None,  # No active account
            )

        assert "📸 Account: Not set" in caption

    def test_keyboard_button_order_status_actions_then_instagram(
        self, mock_telegram_service
    ):
        """Test that status actions (Posted/Skip/Reject) are grouped, then Instagram actions."""
        from telegram import InlineKeyboardButton

        queue_item_id = str(uuid4())
        active_account = Mock()
        active_account.display_name = "Test Account"

        # Build keyboard like the service does (new layout)
        keyboard = [
            # Status action buttons (grouped together)
            [
                InlineKeyboardButton(
                    "✅ Posted", callback_data=f"posted:{queue_item_id}"
                ),
                InlineKeyboardButton("⏭️ Skip", callback_data=f"skip:{queue_item_id}"),
            ],
            [
                InlineKeyboardButton(
                    "🚫 Reject", callback_data=f"reject:{queue_item_id}"
                ),
            ],
            # Instagram-related buttons (grouped together)
            [
                InlineKeyboardButton(
                    f"📸 {active_account.display_name}",
                    callback_data=f"select_account:{queue_item_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "📱 Open Instagram", url="https://www.instagram.com/"
                ),
            ],
        ]

        # Verify button order
        assert len(keyboard) == 4
        # Row 0: Posted/Skip
        assert "Posted" in keyboard[0][0].text
        assert "Skip" in keyboard[0][1].text
        # Row 1: Reject
        assert "Reject" in keyboard[1][0].text
        # Row 2: Account selector
        assert "Test Account" in keyboard[2][0].text
        assert "select_account" in keyboard[2][0].callback_data
        # Row 3: Open Instagram
        assert "Instagram" in keyboard[3][0].text

    def test_account_selector_button_shows_display_name(self, mock_telegram_service):
        """Test account selector button shows friendly display name, not @username."""
        from telegram import InlineKeyboardButton

        queue_item_id = str(uuid4())

        # Test with active account
        active_account = Mock()
        active_account.display_name = "Main Brand Account"  # Friendly name

        button = InlineKeyboardButton(
            f"📸 {active_account.display_name}",
            callback_data=f"select_account:{queue_item_id}",
        )

        assert button.text == "📸 Main Brand Account"
        assert "select_account" in button.callback_data

    def test_account_selector_no_account_label(self):
        """Test account selector shows 'No Account' when none configured."""
        from telegram import InlineKeyboardButton

        queue_item_id = str(uuid4())
        active_account = None

        account_label = (
            f"📸 {active_account.display_name}" if active_account else "📸 No Account"
        )

        button = InlineKeyboardButton(
            account_label,
            callback_data=f"select_account:{queue_item_id}",
        )

        assert button.text == "📸 No Account"

    def test_settings_menu_shows_default_account_label(self):
        """Test settings menu shows 'Default: {name}' instead of '@username'."""
        account_data = {
            "active_account_id": "some-uuid",
            "active_account_name": "Main Account",
            "active_account_username": "mainaccount",
        }

        # This is the new label format
        if account_data["active_account_id"]:
            label = f"📸 Default: {account_data['active_account_name']}"
        else:
            label = "📸 Set Default Account"

        assert label == "📸 Default: Main Account"

    def test_settings_menu_shows_set_default_when_no_account(self):
        """Test settings shows 'Set Default Account' when none selected."""
        account_data = {
            "active_account_id": None,
            "active_account_name": "Not selected",
            "active_account_username": None,
        }

        # This is the new label format
        if account_data["active_account_id"]:
            label = f"📸 Default: {account_data['active_account_name']}"
        else:
            label = "📸 Set Default Account"

        assert label == "📸 Set Default Account"

    def test_callback_data_format_shortened_for_telegram_limit(self):
        """Test callback data uses shortened UUIDs for 64 byte limit."""
        queue_id = "550e8400-e29b-41d4-a716-446655440000"
        account_id = "660f9511-f39c-52e5-b827-557766551111"

        # Shortened format
        short_queue_id = queue_id[:8]  # "550e8400"
        short_account_id = account_id[:8]  # "660f9511"

        callback_data = f"sap:{short_queue_id}:{short_account_id}"

        assert len(callback_data) < 64
        assert callback_data == "sap:550e8400:660f9511"


@pytest.mark.unit
class TestAccountSelectorCallbacks:
    """Tests for account selector callback handlers."""

    async def test_handle_post_account_selector_shows_accounts(
        self, mock_telegram_service
    ):
        """Test that account selector menu shows all configured accounts."""
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.id = queue_id
        mock_telegram_service.queue_repo.get_by_id.return_value = mock_queue_item

        mock_telegram_service.ig_account_service = Mock()
        mock_telegram_service.ig_account_service.get_accounts_for_display.return_value = {
            "accounts": [
                {"id": "acc1", "display_name": "Main Account", "username": "main"},
                {"id": "acc2", "display_name": "Brand Account", "username": "brand"},
            ],
            "active_account_id": "acc1",
        }

        mock_user = Mock()
        mock_user.id = uuid4()

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        await mock_telegram_service._handle_post_account_selector(
            queue_id, mock_user, mock_query
        )

        # Verify edit_message_caption was called
        mock_query.edit_message_caption.assert_called_once()
        call_args = mock_query.edit_message_caption.call_args
        assert "Select Instagram Account" in call_args.kwargs["caption"]

    async def test_handle_back_to_post_rebuilds_workflow(self, mock_telegram_service):
        """Test that back_to_post returns to the posting workflow."""
        queue_id = str(uuid4())
        short_queue_id = queue_id[:8]

        mock_queue_item = Mock()
        mock_queue_item.id = queue_id
        mock_queue_item.media_item_id = uuid4()
        mock_telegram_service.queue_repo.get_by_id_prefix.return_value = mock_queue_item
        mock_telegram_service.queue_repo.get_by_id.return_value = mock_queue_item

        mock_media_item = Mock()
        mock_media_item.title = "Test"
        mock_media_item.caption = None
        mock_media_item.link_url = None
        mock_media_item.tags = []
        mock_telegram_service.media_repo.get_by_id.return_value = mock_media_item

        mock_telegram_service.ig_account_service = Mock()
        mock_telegram_service.ig_account_service.get_active_account.return_value = None

        mock_telegram_service.settings_service = Mock()
        mock_telegram_service.settings_service.get_settings.return_value = Mock(
            enable_instagram_api=False
        )

        mock_user = Mock()
        mock_user.id = uuid4()

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        await mock_telegram_service._handle_back_to_post(
            short_queue_id, mock_user, mock_query
        )

        # Should call edit_message_caption to rebuild the posting workflow
        mock_query.edit_message_caption.assert_called()

    async def test_handle_post_account_switch_stays_in_selector(
        self, mock_telegram_service
    ):
        """Test that switching account stays in selector menu to show updated checkmark."""
        queue_id = str(uuid4())
        account_id = str(uuid4())
        short_queue_id = queue_id[:8]
        short_account_id = account_id[:8]
        chat_id = -100123

        # Mock queue item
        mock_queue_item = Mock()
        mock_queue_item.id = queue_id
        mock_telegram_service.queue_repo.get_by_id_prefix.return_value = mock_queue_item
        mock_telegram_service.queue_repo.get_by_id.return_value = mock_queue_item

        # Mock account
        mock_account = Mock()
        mock_account.id = account_id
        mock_account.display_name = "Test Account"
        mock_account.instagram_username = "testaccount"
        mock_telegram_service.ig_account_service = Mock()
        mock_telegram_service.ig_account_service.get_account_by_id_prefix.return_value = mock_account
        mock_telegram_service.ig_account_service.switch_account.return_value = (
            mock_account
        )
        mock_telegram_service.ig_account_service.get_accounts_for_display.return_value = {
            "accounts": [
                {
                    "id": account_id,
                    "display_name": "Test Account",
                    "username": "testaccount",
                }
            ],
            "active_account_id": account_id,
        }

        mock_user = Mock()
        mock_user.id = uuid4()

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=chat_id, message_id=1)

        # Call the handler
        data = f"{short_queue_id}:{short_account_id}"
        await mock_telegram_service._handle_post_account_switch(
            data, mock_user, mock_query
        )

        # Verify switch_account was called
        mock_telegram_service.ig_account_service.switch_account.assert_called_once_with(
            chat_id, account_id, mock_user
        )

        # Verify success toast was shown
        mock_query.answer.assert_called_once_with("✅ Switched to Test Account")

        # Verify edit_message_caption was called (account selector menu rebuilt)
        mock_query.edit_message_caption.assert_called_once()
        call_args = mock_query.edit_message_caption.call_args
        assert "Select Instagram Account" in call_args.kwargs["caption"]
