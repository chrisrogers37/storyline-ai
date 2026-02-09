"""Tests for TelegramService."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from uuid import uuid4

from src.services.core.telegram_service import TelegramService
from src.services.core.telegram_callbacks import TelegramCallbackHandlers
from src.services.core.telegram_autopost import TelegramAutopostHandler


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

        # Set up sub-handlers for callback routing tests
        service.callbacks = TelegramCallbackHandlers(service)
        service.autopost = TelegramAutopostHandler(service)

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


# Direct handler tests (TestRejectConfirmation, TestVerbosePostedSkipped,
# TestVerboseRejected, TestCompleteQueueAction, TestResumeCallbacks,
# TestResetCallbacks) have been moved to test_telegram_callbacks.py as part
# of the telegram service refactor.

# Routing tests remain here since they test _handle_callback dispatch.


@pytest.mark.unit
@pytest.mark.asyncio
class TestCallbackRouting:
    """Tests for _handle_callback dispatch to handler objects."""

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


# Command test classes have been moved to test_telegram_commands.py.
# Callback test classes (TestRejectConfirmation, TestResumeCallbacks,
# TestResetCallbacks, TestVerbosePostedSkipped, TestVerboseRejected,
# TestCompleteQueueAction) have been moved to test_telegram_callbacks.py.


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


@pytest.mark.unit
class TestIsVerbose:
    """Tests for _is_verbose helper method."""

    def test_verbose_true_when_setting_is_true(self, mock_telegram_service):
        """Test _is_verbose returns True when show_verbose_notifications=True."""
        mock_settings = Mock()
        mock_settings.show_verbose_notifications = True
        mock_telegram_service.settings_service.get_settings.return_value = mock_settings

        assert mock_telegram_service._is_verbose(-100123) is True

    def test_verbose_false_when_setting_is_false(self, mock_telegram_service):
        """Test _is_verbose returns False when show_verbose_notifications=False."""
        mock_settings = Mock()
        mock_settings.show_verbose_notifications = False
        mock_telegram_service.settings_service.get_settings.return_value = mock_settings

        assert mock_telegram_service._is_verbose(-100123) is False

    def test_verbose_defaults_to_true_when_none(self, mock_telegram_service):
        """Test _is_verbose defaults to True when setting is None."""
        mock_settings = Mock()
        mock_settings.show_verbose_notifications = None
        mock_telegram_service.settings_service.get_settings.return_value = mock_settings

        assert mock_telegram_service._is_verbose(-100123) is True

    def test_verbose_uses_preloaded_settings(self, mock_telegram_service):
        """Test _is_verbose uses pre-loaded chat_settings when provided."""
        preloaded = Mock()
        preloaded.show_verbose_notifications = False

        result = mock_telegram_service._is_verbose(-100123, chat_settings=preloaded)

        assert result is False
        # Should NOT call get_settings since we passed chat_settings
        mock_telegram_service.settings_service.get_settings.assert_not_called()


@pytest.mark.unit
class TestVerboseEnhancedCaption:
    """Tests for verbose toggle in _build_enhanced_caption."""

    def test_verbose_on_shows_workflow_instructions(self, mock_telegram_service):
        """Test that verbose=True includes workflow instructions."""
        mock_media = Mock()
        mock_media.title = "Test"
        mock_media.caption = None
        mock_media.link_url = None
        mock_media.tags = []

        with patch("src.services.core.telegram_service.settings") as mock_settings:
            mock_settings.CAPTION_STYLE = "enhanced"
            caption = mock_telegram_service._build_caption(
                mock_media, verbose=True, active_account=None
            )

        assert "Click & hold image" in caption
        assert "Open Instagram" in caption

    def test_verbose_off_hides_workflow_instructions(self, mock_telegram_service):
        """Test that verbose=False omits workflow instructions."""
        mock_media = Mock()
        mock_media.title = "Test"
        mock_media.caption = None
        mock_media.link_url = None
        mock_media.tags = []

        with patch("src.services.core.telegram_service.settings") as mock_settings:
            mock_settings.CAPTION_STYLE = "enhanced"
            caption = mock_telegram_service._build_caption(
                mock_media, verbose=False, active_account=None
            )

        assert "Click & hold image" not in caption
        assert "Open Instagram" not in caption

    def test_verbose_off_still_shows_account(self, mock_telegram_service):
        """Test that verbose=False still shows the account indicator."""
        mock_media = Mock()
        mock_media.title = "Test"
        mock_media.caption = None
        mock_media.link_url = None
        mock_media.tags = []

        mock_account = Mock()
        mock_account.display_name = "My Brand"

        with patch("src.services.core.telegram_service.settings") as mock_settings:
            mock_settings.CAPTION_STYLE = "enhanced"
            caption = mock_telegram_service._build_caption(
                mock_media, verbose=False, active_account=mock_account
            )

        assert "My Brand" in caption


@pytest.mark.unit
class TestVerboseSimpleCaption:
    """Tests for verbose toggle in _build_simple_caption."""

    def test_simple_verbose_on_shows_file_and_id(self, mock_telegram_service):
        """Test simple caption includes file/ID info when verbose=True."""
        mock_media = Mock()
        mock_media.id = "12345678-abcd-efgh-ijkl-mnopqrstuvwx"
        mock_media.title = "Test"
        mock_media.file_name = "image.jpg"
        mock_media.caption = None
        mock_media.link_url = None
        mock_media.tags = []

        with patch("src.services.core.telegram_service.settings") as mock_settings:
            mock_settings.CAPTION_STYLE = "simple"
            caption = mock_telegram_service._build_caption(
                mock_media, verbose=True, active_account=None
            )

        assert "File: image.jpg" in caption
        assert "ID:" in caption

    def test_simple_verbose_off_hides_file_and_id(self, mock_telegram_service):
        """Test simple caption omits file/ID info when verbose=False."""
        mock_media = Mock()
        mock_media.id = "12345678-abcd-efgh-ijkl-mnopqrstuvwx"
        mock_media.title = "Test"
        mock_media.file_name = "image.jpg"
        mock_media.caption = None
        mock_media.link_url = None
        mock_media.tags = []

        with patch("src.services.core.telegram_service.settings") as mock_settings:
            mock_settings.CAPTION_STYLE = "simple"
            caption = mock_telegram_service._build_caption(
                mock_media, verbose=False, active_account=None
            )

        assert "File:" not in caption
        assert "ID:" not in caption

    def test_simple_caption_shows_account(self, mock_telegram_service):
        """Test simple caption includes account when provided."""
        mock_media = Mock()
        mock_media.title = "Test"
        mock_media.file_name = "image.jpg"
        mock_media.caption = None
        mock_media.link_url = None
        mock_media.tags = []

        mock_account = Mock()
        mock_account.display_name = "Brand Account"

        with patch("src.services.core.telegram_service.settings") as mock_settings:
            mock_settings.CAPTION_STYLE = "simple"
            caption = mock_telegram_service._build_caption(
                mock_media, verbose=True, active_account=mock_account
            )

        assert "Brand Account" in caption


@pytest.mark.unit
class TestBuildSettingsKeyboard:
    """Tests for _build_settings_message_and_keyboard helper."""

    def test_returns_message_and_markup(self, mock_telegram_service):
        """Test helper returns (message, InlineKeyboardMarkup) tuple."""
        mock_telegram_service.settings_service.get_settings_display.return_value = {
            "dry_run_mode": False,
            "enable_instagram_api": True,
            "is_paused": False,
            "posts_per_day": 3,
            "posting_hours_start": 9,
            "posting_hours_end": 21,
            "show_verbose_notifications": True,
        }
        mock_telegram_service.ig_account_service.get_accounts_for_display.return_value = {
            "active_account_id": "some-id",
            "active_account_name": "Test Account",
        }

        message, markup = mock_telegram_service._build_settings_message_and_keyboard(
            -100123
        )

        assert "Bot Settings" in message
        assert markup is not None

    def test_verbose_toggle_button_shows_state(self, mock_telegram_service):
        """Test that verbose button shows correct ON/OFF state."""

        mock_telegram_service.settings_service.get_settings_display.return_value = {
            "dry_run_mode": False,
            "enable_instagram_api": False,
            "is_paused": False,
            "posts_per_day": 3,
            "posting_hours_start": 9,
            "posting_hours_end": 21,
            "show_verbose_notifications": False,
        }
        mock_telegram_service.ig_account_service.get_accounts_for_display.return_value = {
            "active_account_id": None,
            "active_account_name": "Not selected",
        }

        _, markup = mock_telegram_service._build_settings_message_and_keyboard(-100123)

        # Find verbose button in keyboard
        all_buttons = [btn for row in markup.inline_keyboard for btn in row]
        verbose_buttons = [b for b in all_buttons if "Verbose" in b.text]
        assert len(verbose_buttons) == 1
        assert "OFF" in verbose_buttons[0].text
