"""Tests for TelegramService."""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime

from src.services.core.telegram_service import TelegramService
from src.repositories.user_repository import UserRepository
from src.repositories.queue_repository import QueueRepository
from src.repositories.media_repository import MediaRepository


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
