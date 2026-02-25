"""Tests for TelegramAutopostHandler."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from uuid import uuid4
import threading

from src.services.core.telegram_service import TelegramService
from src.services.core.telegram_autopost import (
    AutopostContext,
    TelegramAutopostHandler,
)


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
        service.history_repo.get_by_queue_item_id.return_value = None

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
        mock_media.source_type = "local"
        mock_media.source_identifier = "/test/story.jpg"
        mock_media.mime_type = "image/jpeg"
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

        mock_provider = Mock()
        mock_provider.download_file.return_value = b"fake image bytes"

        with (
            patch(
                "src.services.integrations.instagram_api.InstagramAPIService"
            ) as mock_ig_class,
            patch(
                "src.services.integrations.cloud_storage.CloudStorageService"
            ) as mock_cloud_class,
            patch(
                "src.services.media_sources.factory.MediaSourceFactory.get_provider_for_media_item",
                return_value=mock_provider,
            ),
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
class TestAutopostEarlyFeedback:
    """Tests for early keyboard removal in autopost handler."""

    async def test_autopost_removes_keyboard_before_processing(
        self, mock_autopost_handler
    ):
        """handle_autopost removes keyboard immediately after lock acquisition."""
        handler = mock_autopost_handler
        queue_id = str(uuid4())

        mock_user = Mock()
        mock_query = AsyncMock()

        # Make _locked_autopost return immediately (we only care about keyboard removal)
        handler._locked_autopost = AsyncMock()

        await handler.handle_autopost(queue_id, mock_user, mock_query)

        # Keyboard should be removed before _locked_autopost is called
        mock_query.edit_message_reply_markup.assert_called_once()


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


# ==================== Extracted Helper Tests ====================


@pytest.fixture
def make_autopost_ctx():
    """Factory fixture to create AutopostContext with sensible defaults."""

    def _make(
        queue_id=None,
        queue_item=None,
        media_item=None,
        user=None,
        query=None,
        chat_id=-100123,
        chat_settings=None,
        cloud_service=None,
        instagram_service=None,
        cancel_flag=None,
        cloud_url=None,
        cloud_public_id=None,
    ):
        if queue_id is None:
            queue_id = str(uuid4())
        if queue_item is None:
            queue_item = Mock(
                media_item_id=uuid4(),
                created_at="2026-01-01T00:00:00",
                scheduled_for="2026-01-01T12:00:00",
            )
        if media_item is None:
            media_item = Mock(
                id=uuid4(),
                file_path="/test/story.jpg",
                file_name="story.jpg",
                source_identifier="/test/story.jpg",
                mime_type="image/jpeg",
            )
        if user is None:
            user = Mock(
                id=uuid4(),
                telegram_username="tester",
                telegram_first_name="Test",
            )
        if query is None:
            query = AsyncMock()
            query.message = Mock(chat_id=chat_id, message_id=1)
        if chat_settings is None:
            chat_settings = Mock(dry_run_mode=False)
        if cloud_service is None:
            cloud_service = Mock()
        if instagram_service is None:
            instagram_service = AsyncMock()

        return AutopostContext(
            queue_id=queue_id,
            queue_item=queue_item,
            media_item=media_item,
            user=user,
            query=query,
            chat_id=chat_id,
            chat_settings=chat_settings,
            cloud_service=cloud_service,
            instagram_service=instagram_service,
            cancel_flag=cancel_flag,
            cloud_url=cloud_url,
            cloud_public_id=cloud_public_id,
        )

    return _make


@pytest.mark.unit
class TestAutopostContext:
    """Tests for the AutopostContext dataclass."""

    def test_creation(self):
        """Test AutopostContext can be created with all fields."""
        ctx = AutopostContext(
            queue_id="q1",
            queue_item=Mock(),
            media_item=Mock(),
            user=Mock(),
            query=Mock(),
            chat_id=-100,
            chat_settings=Mock(),
            cloud_service=Mock(),
            instagram_service=Mock(),
        )
        assert ctx.queue_id == "q1"
        assert ctx.chat_id == -100
        assert ctx.cancel_flag is None
        assert ctx.cloud_url is None
        assert ctx.cloud_public_id is None

    def test_mutable_fields(self):
        """Test that cloud_url and cloud_public_id can be set after creation."""
        ctx = AutopostContext(
            queue_id="q1",
            queue_item=Mock(),
            media_item=Mock(),
            user=Mock(),
            query=Mock(),
            chat_id=-100,
            chat_settings=Mock(),
            cloud_service=Mock(),
            instagram_service=Mock(),
        )
        ctx.cloud_url = "https://example.com/img.jpg"
        ctx.cloud_public_id = "stories/abc123"
        assert ctx.cloud_url == "https://example.com/img.jpg"
        assert ctx.cloud_public_id == "stories/abc123"


@pytest.mark.unit
@pytest.mark.asyncio
class TestGetAccountDisplay:
    """Tests for _get_account_display helper."""

    async def test_returns_username(self, mock_autopost_handler, make_autopost_ctx):
        """Test successful account info lookup returns @username."""
        handler = mock_autopost_handler
        ctx = make_autopost_ctx(
            instagram_service=AsyncMock(
                get_account_info=AsyncMock(return_value={"username": "mybrand"})
            )
        )

        result = await handler._get_account_display(ctx)
        assert result == "@mybrand"

    async def test_fallback_on_exception(
        self, mock_autopost_handler, make_autopost_ctx
    ):
        """Test that exception returns 'Unknown account'."""
        handler = mock_autopost_handler
        ctx = make_autopost_ctx(
            instagram_service=AsyncMock(
                get_account_info=AsyncMock(side_effect=Exception("API error"))
            )
        )

        result = await handler._get_account_display(ctx)
        assert result == "Unknown account"


@pytest.mark.unit
@pytest.mark.asyncio
class TestUploadToCloudinary:
    """Tests for _upload_to_cloudinary helper."""

    async def test_success_sets_ctx_fields(
        self, mock_autopost_handler, make_autopost_ctx
    ):
        """Test successful upload sets cloud_url and cloud_public_id on ctx."""
        handler = mock_autopost_handler
        mock_cloud = Mock()
        mock_cloud.upload_media.return_value = {
            "url": "https://res.cloudinary.com/test/img.jpg",
            "public_id": "instagram_stories/abc",
        }

        ctx = make_autopost_ctx(cloud_service=mock_cloud)

        mock_provider = Mock()
        mock_provider.download_file.return_value = b"fake bytes"

        with patch(
            "src.services.media_sources.factory.MediaSourceFactory.get_provider_for_media_item",
            return_value=mock_provider,
        ):
            result = await handler._upload_to_cloudinary(ctx)

        assert result is True
        assert ctx.cloud_url == "https://res.cloudinary.com/test/img.jpg"
        assert ctx.cloud_public_id == "instagram_stories/abc"
        handler.service.media_repo.update_cloud_info.assert_called_once()

    async def test_cancelled_returns_false(
        self, mock_autopost_handler, make_autopost_ctx
    ):
        """Test that a set cancel flag after upload returns False."""
        handler = mock_autopost_handler
        mock_cloud = Mock()
        mock_cloud.upload_media.return_value = {
            "url": "https://res.cloudinary.com/test/img.jpg",
            "public_id": "instagram_stories/abc",
        }

        cancel_flag = threading.Event()
        cancel_flag.set()  # Already cancelled

        ctx = make_autopost_ctx(cloud_service=mock_cloud, cancel_flag=cancel_flag)

        mock_provider = Mock()
        mock_provider.download_file.return_value = b"fake bytes"

        with patch(
            "src.services.media_sources.factory.MediaSourceFactory.get_provider_for_media_item",
            return_value=mock_provider,
        ):
            result = await handler._upload_to_cloudinary(ctx)

        assert result is False
        # Should show cancelled message
        found_cancelled = False
        for call in ctx.query.edit_message_caption.call_args_list:
            if "cancelled" in str(call).lower():
                found_cancelled = True
                break
        assert found_cancelled


@pytest.mark.unit
@pytest.mark.asyncio
class TestHandleDryRun:
    """Tests for _handle_dry_run helper."""

    async def test_edits_message_with_dry_run_caption(
        self, mock_autopost_handler, make_autopost_ctx
    ):
        """Test dry run edits message with DRY RUN caption."""
        handler = mock_autopost_handler
        handler.service._is_verbose = Mock(return_value=False)
        handler.service._get_display_name = Mock(return_value="@tester")

        ctx = make_autopost_ctx(
            cloud_url="https://example.com/img.jpg",
            cloud_public_id="stories/abc",
            instagram_service=AsyncMock(
                get_account_info=AsyncMock(return_value={"username": "testaccount"})
            ),
        )

        await handler._handle_dry_run(ctx)

        # Should edit message with dry run caption
        ctx.query.edit_message_caption.assert_called_once()
        call_kwargs = ctx.query.edit_message_caption.call_args.kwargs
        assert "DRY RUN" in call_kwargs["caption"]
        assert call_kwargs["reply_markup"] is not None

    async def test_logs_dry_run_interaction(
        self, mock_autopost_handler, make_autopost_ctx
    ):
        """Test dry run logs interaction with dry_run=True."""
        handler = mock_autopost_handler
        handler.service._is_verbose = Mock(return_value=False)
        handler.service._get_display_name = Mock(return_value="@tester")

        ctx = make_autopost_ctx(
            cloud_url="https://example.com/img.jpg",
            cloud_public_id="stories/abc",
            instagram_service=AsyncMock(
                get_account_info=AsyncMock(return_value={"username": "testaccount"})
            ),
        )

        await handler._handle_dry_run(ctx)

        handler.service.interaction_service.log_callback.assert_called_once()
        log_ctx = handler.service.interaction_service.log_callback.call_args.kwargs[
            "context"
        ]
        assert log_ctx["dry_run"] is True


@pytest.mark.unit
@pytest.mark.asyncio
class TestExecuteInstagramPost:
    """Tests for _execute_instagram_post helper."""

    async def test_success_returns_story_id(
        self, mock_autopost_handler, make_autopost_ctx
    ):
        """Test successful post returns story_id."""
        handler = mock_autopost_handler
        mock_cloud = Mock()
        mock_cloud.get_story_optimized_url.return_value = (
            "https://res.cloudinary.com/optimized.jpg"
        )

        mock_ig = AsyncMock()
        mock_ig.post_story = AsyncMock(return_value={"story_id": "17890012345678"})

        ctx = make_autopost_ctx(
            cloud_service=mock_cloud,
            instagram_service=mock_ig,
            cloud_url="https://res.cloudinary.com/test/img.jpg",
        )

        result = await handler._execute_instagram_post(ctx)

        assert result == "17890012345678"
        mock_ig.post_story.assert_called_once()

    async def test_cancelled_returns_none(
        self, mock_autopost_handler, make_autopost_ctx
    ):
        """Test that a set cancel flag returns None without posting."""
        handler = mock_autopost_handler
        cancel_flag = threading.Event()
        cancel_flag.set()

        ctx = make_autopost_ctx(cancel_flag=cancel_flag)

        result = await handler._execute_instagram_post(ctx)

        assert result is None

    async def test_video_uses_cloud_url_directly(
        self, mock_autopost_handler, make_autopost_ctx
    ):
        """Test VIDEO media type uses cloud_url directly (no optimization)."""
        handler = mock_autopost_handler
        mock_cloud = Mock()
        mock_ig = AsyncMock()
        mock_ig.post_story = AsyncMock(return_value={"story_id": "vid123"})

        video_media = Mock(
            id=uuid4(),
            file_path="/test/story.mp4",
            file_name="story.mp4",
            source_identifier="/test/story.mp4",
            mime_type="video/mp4",
        )

        ctx = make_autopost_ctx(
            media_item=video_media,
            cloud_service=mock_cloud,
            instagram_service=mock_ig,
            cloud_url="https://res.cloudinary.com/test/video.mp4",
        )

        await handler._execute_instagram_post(ctx)

        # Should NOT call get_story_optimized_url for video
        mock_cloud.get_story_optimized_url.assert_not_called()
        # Should post with original cloud_url
        call_kwargs = mock_ig.post_story.call_args.kwargs
        assert call_kwargs["media_url"] == "https://res.cloudinary.com/test/video.mp4"
        assert call_kwargs["media_type"] == "VIDEO"


@pytest.mark.unit
class TestRecordSuccessfulPost:
    """Tests for _record_successful_post helper."""

    def test_calls_all_repo_operations(self, mock_autopost_handler, make_autopost_ctx):
        """Test that all 5 repo operations are called."""
        handler = mock_autopost_handler
        ctx = make_autopost_ctx()

        handler._record_successful_post(ctx, story_id="story_abc")

        # 1. Create history
        handler.service.history_repo.create.assert_called_once()
        # 2. Increment times posted
        handler.service.media_repo.increment_times_posted.assert_called_once_with(
            str(ctx.queue_item.media_item_id)
        )
        # 3. Create lock
        handler.service.lock_service.create_lock.assert_called_once_with(
            str(ctx.queue_item.media_item_id)
        )
        # 4. Delete queue item
        handler.service.queue_repo.delete.assert_called_once_with(ctx.queue_id)
        # 5. Increment user posts
        handler.service.user_repo.increment_posts.assert_called_once_with(
            str(ctx.user.id)
        )


@pytest.mark.unit
@pytest.mark.asyncio
class TestHandleAutopostError:
    """Tests for _handle_autopost_error helper."""

    async def test_generic_exception_shows_fallback_message(
        self, mock_autopost_handler, make_autopost_ctx
    ):
        """Test generic exceptions show user-friendly fallback."""
        handler = mock_autopost_handler
        ctx = make_autopost_ctx()

        await handler._handle_autopost_error(ctx, Exception("Connection timeout"))

        ctx.query.edit_message_caption.assert_called_once()
        call_kwargs = ctx.query.edit_message_caption.call_args.kwargs
        assert "Auto Post Failed" in call_kwargs["caption"]
        assert "unexpected error" in call_kwargs["caption"]
        assert "Connection timeout" in call_kwargs["caption"]
        assert call_kwargs["reply_markup"] is not None

    async def test_media_upload_error_hides_internals(
        self, mock_autopost_handler, make_autopost_ctx
    ):
        """Test MediaUploadError shows user-friendly message without provider details."""
        from src.exceptions.instagram import MediaUploadError

        handler = mock_autopost_handler
        ctx = make_autopost_ctx()

        await handler._handle_autopost_error(
            ctx, MediaUploadError("Cloudinary upload failed: Unknown API key 123")
        )

        call_kwargs = ctx.query.edit_message_caption.call_args.kwargs
        assert "Cloudinary" not in call_kwargs["caption"]
        assert "server issue" in call_kwargs["caption"]

    async def test_rate_limit_error_message(
        self, mock_autopost_handler, make_autopost_ctx
    ):
        """Test RateLimitError shows rate limit message."""
        from src.exceptions.instagram import RateLimitError

        handler = mock_autopost_handler
        ctx = make_autopost_ctx()

        await handler._handle_autopost_error(ctx, RateLimitError())

        call_kwargs = ctx.query.edit_message_caption.call_args.kwargs
        assert "rate limit" in call_kwargs["caption"].lower()

    async def test_token_expired_error_message(
        self, mock_autopost_handler, make_autopost_ctx
    ):
        """Test TokenExpiredError shows reconnect message."""
        from src.exceptions.instagram import TokenExpiredError

        handler = mock_autopost_handler
        ctx = make_autopost_ctx()

        await handler._handle_autopost_error(ctx, TokenExpiredError())

        call_kwargs = ctx.query.edit_message_caption.call_args.kwargs
        assert "expired" in call_kwargs["caption"].lower()
        assert "reconnect" in call_kwargs["caption"].lower()

    async def test_instagram_api_error_shows_instagram_message(
        self, mock_autopost_handler, make_autopost_ctx
    ):
        """Test InstagramAPIError passes through Instagram's message."""
        from src.exceptions.instagram import InstagramAPIError

        handler = mock_autopost_handler
        ctx = make_autopost_ctx()

        await handler._handle_autopost_error(
            ctx, InstagramAPIError("Media too large for story")
        )

        call_kwargs = ctx.query.edit_message_caption.call_args.kwargs
        assert "Instagram rejected" in call_kwargs["caption"]
        assert "Media too large" in call_kwargs["caption"]

    async def test_logs_failure_interaction(
        self, mock_autopost_handler, make_autopost_ctx
    ):
        """Test error handler logs interaction with success=False."""
        handler = mock_autopost_handler
        ctx = make_autopost_ctx()

        await handler._handle_autopost_error(ctx, Exception("API error"))

        handler.service.interaction_service.log_callback.assert_called_once()
        log_ctx = handler.service.interaction_service.log_callback.call_args.kwargs[
            "context"
        ]
        assert log_ctx["success"] is False
        assert "API error" in log_ctx["error"]
