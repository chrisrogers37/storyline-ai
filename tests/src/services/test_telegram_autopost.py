"""Tests for TelegramAutopostHandler."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from uuid import uuid4

from src.services.core.telegram_service import TelegramService
from src.services.core.telegram_autopost import TelegramAutopostHandler


@pytest.fixture
def mock_autopost_handler():
    """Create TelegramAutopostHandler with mocked service dependencies."""
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
        mock_settings.ENABLE_INSTAGRAM_API = True

        service = TelegramService()

        service.user_repo = mock_user_repo_class.return_value
        service.queue_repo = mock_queue_repo_class.return_value
        service.media_repo = mock_media_repo_class.return_value
        service.history_repo = mock_history_repo_class.return_value
        service.lock_repo = mock_lock_repo_class.return_value
        service.lock_service = mock_lock_service_class.return_value
        service.interaction_service = mock_interaction_service_class.return_value
        service.settings_service = mock_settings_service_class.return_value
        service.ig_account_service = mock_ig_account_service_class.return_value

        handler = TelegramAutopostHandler(service)
        yield handler


@pytest.mark.unit
@pytest.mark.asyncio
class TestAutopostQueueItemNotFound:
    """Tests for autopost when queue/media items are missing."""

    async def test_autopost_queue_item_not_found(self, mock_autopost_handler):
        """Test that autopost handles missing queue item gracefully."""
        handler = mock_autopost_handler
        service = handler.service
        queue_id = str(uuid4())

        service.queue_repo.get_by_id.return_value = None

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_query = AsyncMock()

        await handler.handle_autopost(queue_id, mock_user, mock_query)

        mock_query.edit_message_caption.assert_called_once()
        call_args = mock_query.edit_message_caption.call_args
        assert "not found" in str(call_args).lower()

    async def test_autopost_media_item_not_found(self, mock_autopost_handler):
        """Test that autopost handles missing media item gracefully."""
        handler = mock_autopost_handler
        service = handler.service
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()
        service.queue_repo.get_by_id.return_value = mock_queue_item
        service.media_repo.get_by_id.return_value = None

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_query = AsyncMock()

        await handler.handle_autopost(queue_id, mock_user, mock_query)

        # Should have been called at least once with "not found"
        found_not_found = False
        for call in mock_query.edit_message_caption.call_args_list:
            if "not found" in str(call).lower():
                found_not_found = True
                break
        assert found_not_found


@pytest.mark.unit
@pytest.mark.asyncio
class TestAutopostSafetyGates:
    """Tests for safety check enforcement."""

    async def test_autopost_safety_check_failure_blocks_posting(
        self, mock_autopost_handler
    ):
        """Test that a failed safety check prevents posting."""
        handler = mock_autopost_handler
        service = handler.service
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()
        service.queue_repo.get_by_id.return_value = mock_queue_item

        mock_media = Mock()
        mock_media.file_path = "/test/story.jpg"
        mock_media.file_name = "story.jpg"
        service.media_repo.get_by_id.return_value = mock_media

        mock_user = Mock()
        mock_user.id = uuid4()

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        mock_chat_settings = Mock()
        mock_chat_settings.dry_run_mode = False
        service.settings_service.get_settings.return_value = mock_chat_settings

        with (
            patch(
                "src.services.integrations.instagram_api.InstagramAPIService"
            ) as mock_ig_class,
            patch(
                "src.services.integrations.cloud_storage.CloudStorageService"
            ) as mock_cloud_class,
        ):
            mock_ig_instance = mock_ig_class.return_value
            mock_ig_instance.safety_check_before_post.return_value = {
                "safe_to_post": False,
                "errors": ["Token expired", "Rate limit exceeded"],
            }
            mock_ig_instance.close = Mock()
            mock_cloud_instance = mock_cloud_class.return_value
            mock_cloud_instance.close = Mock()

            await handler.handle_autopost(queue_id, mock_user, mock_query)

        # Should show safety check failure message
        found_safety_fail = False
        for call in mock_query.edit_message_caption.call_args_list:
            if "SAFETY CHECK FAILED" in str(call):
                found_safety_fail = True
                break
        assert found_safety_fail

        # Should NOT create history or delete from queue
        service.history_repo.create.assert_not_called()
        service.queue_repo.delete.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
class TestAutopostDryRun:
    """Tests for dry-run mode behavior."""

    async def test_dry_run_uploads_to_cloudinary_but_skips_instagram(
        self, mock_autopost_handler
    ):
        """Test that dry-run mode uploads to Cloudinary but stops before Instagram API."""
        handler = mock_autopost_handler
        service = handler.service
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()
        service.queue_repo.get_by_id.return_value = mock_queue_item

        mock_media = Mock()
        mock_media.id = uuid4()
        mock_media.file_path = "/test/story.jpg"
        mock_media.file_name = "story.jpg"
        service.media_repo.get_by_id.return_value = mock_media

        mock_chat_settings = Mock()
        mock_chat_settings.dry_run_mode = True
        service.settings_service.get_settings.return_value = mock_chat_settings

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "tester"
        mock_user.telegram_first_name = "Test"

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        with (
            patch(
                "src.services.integrations.instagram_api.InstagramAPIService"
            ) as mock_ig_class,
            patch(
                "src.services.integrations.cloud_storage.CloudStorageService"
            ) as mock_cloud_class,
        ):
            mock_ig_instance = mock_ig_class.return_value
            mock_ig_instance.safety_check_before_post.return_value = {
                "safe_to_post": True,
                "errors": [],
            }
            mock_ig_instance.get_account_info = AsyncMock(
                return_value={"username": "testaccount"}
            )
            mock_ig_instance.close = Mock()

            mock_cloud_instance = mock_cloud_class.return_value
            mock_cloud_instance.upload_media.return_value = {
                "url": "https://res.cloudinary.com/test/image.jpg",
                "public_id": "instagram_stories/test123",
            }
            mock_cloud_instance.get_story_optimized_url.return_value = (
                "https://res.cloudinary.com/test/image_optimized.jpg"
            )
            mock_cloud_instance.close = Mock()

            await handler.handle_autopost(queue_id, mock_user, mock_query)

        # Cloudinary upload SHOULD have been called
        mock_cloud_instance.upload_media.assert_called_once()

        # Instagram API post SHOULD NOT have been called
        mock_ig_instance.post_story.assert_not_called()

        # Queue item should NOT be deleted (preserved for re-testing)
        service.queue_repo.delete.assert_not_called()

        # History should NOT be created
        service.history_repo.create.assert_not_called()

        # Dry run interaction should be logged
        service.interaction_service.log_callback.assert_called_once()
        log_call = service.interaction_service.log_callback.call_args
        assert log_call.kwargs["context"]["dry_run"] is True

        # Caption should mention DRY RUN
        found_dry_run = False
        for call in mock_query.edit_message_caption.call_args_list:
            if "DRY RUN" in str(call):
                found_dry_run = True
                break
        assert found_dry_run


@pytest.mark.unit
@pytest.mark.asyncio
class TestAutopostErrorRecovery:
    """Tests for error handling during auto-post."""

    async def test_cloudinary_upload_failure_shows_error(self, mock_autopost_handler):
        """Test that Cloudinary upload failure shows error with retry button."""
        handler = mock_autopost_handler
        service = handler.service
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()
        service.queue_repo.get_by_id.return_value = mock_queue_item

        mock_media = Mock()
        mock_media.id = uuid4()
        mock_media.file_path = "/test/story.jpg"
        mock_media.file_name = "story.jpg"
        service.media_repo.get_by_id.return_value = mock_media

        mock_chat_settings = Mock()
        mock_chat_settings.dry_run_mode = False
        service.settings_service.get_settings.return_value = mock_chat_settings

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "poster"

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        with (
            patch(
                "src.services.integrations.instagram_api.InstagramAPIService"
            ) as mock_ig_class,
            patch(
                "src.services.integrations.cloud_storage.CloudStorageService"
            ) as mock_cloud_class,
        ):
            mock_ig_instance = mock_ig_class.return_value
            mock_ig_instance.safety_check_before_post.return_value = {
                "safe_to_post": True,
                "errors": [],
            }
            mock_ig_instance.close = Mock()

            mock_cloud_instance = mock_cloud_class.return_value
            mock_cloud_instance.upload_media.side_effect = Exception(
                "Cloudinary timeout"
            )
            mock_cloud_instance.close = Mock()

            await handler.handle_autopost(queue_id, mock_user, mock_query)

        # Should show error message
        found_error = False
        for call in mock_query.edit_message_caption.call_args_list:
            if "Auto Post Failed" in str(call):
                found_error = True
                break
        assert found_error

        # Should log failure interaction
        service.interaction_service.log_callback.assert_called_once()
        log_call = service.interaction_service.log_callback.call_args
        assert log_call.kwargs["context"]["success"] is False


@pytest.mark.unit
@pytest.mark.asyncio
class TestAutopostOperationLock:
    """Tests for the operation lock that prevents duplicate auto-posts."""

    async def test_double_click_returns_already_processing(self, mock_autopost_handler):
        """Test that clicking autopost while already processing shows feedback."""
        handler = mock_autopost_handler
        service = handler.service
        queue_id = str(uuid4())

        # Pre-acquire the lock to simulate an in-progress operation
        lock = service.get_operation_lock(queue_id)
        await lock.acquire()

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_query = AsyncMock()

        await handler.handle_autopost(queue_id, mock_user, mock_query)

        # Should show "Already processing" feedback
        mock_query.answer.assert_called_once()
        answer_call = mock_query.answer.call_args
        assert "Already processing" in str(answer_call)

        # Clean up
        lock.release()
