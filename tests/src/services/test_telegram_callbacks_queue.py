"""Tests for TelegramCallbackQueueHandlers — posted/skipped/rejected flows."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.exc import OperationalError

from src.services.core.telegram_callbacks_core import TelegramCallbackCore
from src.services.core.telegram_callbacks_queue import TelegramCallbackQueueHandlers
from tests.src.services.conftest import make_query as _make_query
from tests.src.services.conftest import make_user as _make_user


async def _consume_coro_args(*args, **kwargs):
    """Close any coroutine arguments to prevent 'never awaited' warnings."""
    for arg in args:
        if asyncio.iscoroutine(arg):
            arg.close()


@pytest.fixture
def mock_service():
    """Minimal TelegramService mock for queue handler tests."""
    service = Mock()
    service.queue_repo = Mock()
    service.media_repo = Mock()
    service.history_repo = Mock()
    service.interaction_service = Mock()
    service.settings_service = Mock()
    service.ig_account_service = Mock()
    service.ig_account_service.get_active_account.return_value = None
    service.ig_account_service.count_active_accounts.return_value = 1
    service._get_display_name.return_value = "TestUser"
    service._is_verbose.return_value = False
    service.get_cancel_flag.return_value = Mock()
    service._build_caption.return_value = "original caption"

    return service


@pytest.fixture
def mock_core(mock_service):
    """TelegramCallbackCore with mocked internals."""
    core = Mock(spec=TelegramCallbackCore)
    core.service = mock_service
    core._safe_locked_callback = AsyncMock(side_effect=_consume_coro_args)
    core._execute_complete_db_ops = Mock()
    core._execute_reject_db_ops = Mock()
    core._refresh_repo_sessions = Mock()
    return core


@pytest.fixture
def handlers(mock_service, mock_core):
    """TelegramCallbackQueueHandlers with mocked dependencies."""
    return TelegramCallbackQueueHandlers(mock_service, mock_core)


# ──────────────────────────────────────────────────────────────
# handle_posted
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
class TestHandlePosted:
    async def test_sets_cancel_flag_and_delegates(self, handlers):
        """Sets the cancel flag for autopost, then calls complete_queue_action."""
        user = _make_user()
        query = _make_query()

        await handlers.handle_posted("q-1", user, query)

        handlers.service.get_cancel_flag.assert_called_once_with("q-1")
        handlers.service.get_cancel_flag.return_value.set.assert_called_once()
        handlers.core._safe_locked_callback.assert_called_once()

    async def test_verbose_caption_includes_marked_as(self, handlers):
        """Verbose mode passes 'Marked as posted by' caption."""
        handlers.service._is_verbose.return_value = True
        user = _make_user()
        query = _make_query()

        # Call the internal method directly to verify caption content
        with patch.object(
            handlers, "complete_queue_action", new_callable=AsyncMock
        ) as mock_cqa:
            await handlers.handle_posted("q-1", user, query)

        caption = mock_cqa.call_args[1]["caption"]
        assert "Marked as posted" in caption
        assert "TestUser" in caption

    async def test_non_verbose_caption(self, handlers):
        """Non-verbose mode passes shorter caption without 'Marked as'."""
        handlers.service._is_verbose.return_value = False
        user = _make_user()
        query = _make_query()

        with patch.object(
            handlers, "complete_queue_action", new_callable=AsyncMock
        ) as mock_cqa:
            await handlers.handle_posted("q-1", user, query)

        caption = mock_cqa.call_args[1]["caption"]
        assert "Marked as posted" not in caption
        assert "TestUser" in caption


# ──────────────────────────────────────────────────────────────
# handle_skipped
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
class TestHandleSkipped:
    async def test_sets_cancel_flag_and_delegates(self, handlers):
        """Sets cancel flag and delegates to complete_queue_action with 'skipped'."""
        user = _make_user()
        query = _make_query()

        await handlers.handle_skipped("q-1", user, query)

        handlers.service.get_cancel_flag.assert_called_once_with("q-1")
        handlers.service.get_cancel_flag.return_value.set.assert_called_once()
        handlers.core._safe_locked_callback.assert_called_once()


# ──────────────────────────────────────────────────────────────
# _do_complete_queue_action
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
class TestDoCompleteQueueAction:
    @patch("src.services.core.telegram_callbacks_queue.telegram_edit_with_retry")
    async def test_happy_path(self, mock_retry, handlers):
        """Claim, execute DB ops, update caption, log interaction."""
        queue_item = Mock(media_item_id="m-1")
        handlers.service.queue_repo.claim_for_processing.return_value = queue_item
        media_item = Mock(file_name="photo.jpg")
        handlers.core._execute_complete_db_ops.return_value = media_item

        user = _make_user()
        query = _make_query()

        await handlers._do_complete_queue_action(
            "q-1", user, query, "posted", True, "Done!", "posted"
        )

        handlers.service.queue_repo.claim_for_processing.assert_called_once_with("q-1")
        handlers.core._execute_complete_db_ops.assert_called_once_with(
            "q-1", queue_item, user, "posted", True
        )
        mock_retry.assert_called_once()
        handlers.service.interaction_service.log_callback.assert_called_once()
        handlers.service.interaction_service.log_bot_response.assert_called_once()

    @patch("src.services.core.telegram_callbacks_queue.validate_queue_item")
    async def test_already_claimed_validates(self, mock_validate, handlers):
        """If claim returns None, call validate_queue_item for user feedback."""
        mock_validate.return_value = AsyncMock()
        handlers.service.queue_repo.claim_for_processing.return_value = None

        user = _make_user()
        query = _make_query()

        await handlers._do_complete_queue_action(
            "q-1", user, query, "posted", True, "Done!", "posted"
        )

        mock_validate.assert_called_once()
        handlers.core._execute_complete_db_ops.assert_not_called()

    @patch("src.services.core.telegram_callbacks_queue.telegram_edit_with_retry")
    async def test_operational_error_retries(self, mock_retry, handlers):
        """On OperationalError, refresh sessions and retry once."""
        queue_item = Mock(media_item_id="m-1")
        handlers.service.queue_repo.claim_for_processing.return_value = queue_item
        handlers.service.history_repo.get_by_queue_item_id.return_value = None
        handlers.service.queue_repo.get_by_id.return_value = queue_item

        media_item = Mock(file_name="photo.jpg")
        handlers.core._execute_complete_db_ops.side_effect = [
            OperationalError("ssl", {}, Exception()),
            media_item,
        ]

        user = _make_user()
        query = _make_query()

        await handlers._do_complete_queue_action(
            "q-1", user, query, "posted", True, "Done!", "posted"
        )

        assert handlers.core._execute_complete_db_ops.call_count == 2
        handlers.core._refresh_repo_sessions.assert_called_once()

    @patch("src.services.core.telegram_callbacks_queue.telegram_edit_with_retry")
    async def test_operational_error_with_existing_history(self, mock_retry, handlers):
        """If history already exists after OperationalError, just clean up."""
        queue_item = Mock(media_item_id="m-1")
        handlers.service.queue_repo.claim_for_processing.return_value = queue_item
        media_item = Mock(file_name="photo.jpg")
        handlers.service.media_repo.get_by_id.return_value = media_item

        existing_history = Mock()
        handlers.service.history_repo.get_by_queue_item_id.return_value = (
            existing_history
        )

        handlers.core._execute_complete_db_ops.side_effect = OperationalError(
            "ssl", {}, Exception()
        )

        user = _make_user()
        query = _make_query()

        await handlers._do_complete_queue_action(
            "q-1", user, query, "posted", True, "Done!", "posted"
        )

        handlers.service.queue_repo.delete.assert_called_once_with("q-1")
        assert handlers.core._execute_complete_db_ops.call_count == 1

    @patch("src.services.core.telegram_callbacks_queue.telegram_edit_with_retry")
    async def test_operational_error_queue_item_gone(self, mock_retry, handlers):
        """If queue item gone after session refresh, show 'already processed'."""
        queue_item = Mock(media_item_id="m-1")
        handlers.service.queue_repo.claim_for_processing.return_value = queue_item
        handlers.service.history_repo.get_by_queue_item_id.return_value = None
        handlers.service.queue_repo.get_by_id.return_value = None

        handlers.core._execute_complete_db_ops.side_effect = OperationalError(
            "ssl", {}, Exception()
        )

        user = _make_user()
        query = _make_query()

        await handlers._do_complete_queue_action(
            "q-1", user, query, "posted", True, "Done!", "posted"
        )

        mock_retry.assert_called_once()
        assert "already processed" in mock_retry.call_args[1]["caption"]


# ──────────────────────────────────────────────────────────────
# handle_back
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
class TestHandleBack:
    @patch("src.services.core.telegram_callbacks_queue.build_queue_action_keyboard")
    @patch("src.services.core.telegram_callbacks_queue.validate_queue_and_media")
    @patch("src.services.core.telegram_callbacks_queue.telegram_edit_with_retry")
    async def test_restores_original_message(
        self, mock_retry, mock_validate, mock_keyboard, handlers
    ):
        """Restores original caption and keyboard."""
        queue_item = Mock()
        media_item = Mock()
        mock_validate.return_value = (queue_item, media_item)
        mock_keyboard.return_value = Mock()
        handlers.service.settings_service.get_settings.return_value = Mock(
            enable_instagram_api=False
        )

        user = _make_user()
        query = _make_query()

        await handlers.handle_back("q-1", user, query)

        mock_validate.assert_called_once()
        handlers.service._build_caption.assert_called_once()
        mock_retry.assert_called_once()

    @patch("src.services.core.telegram_callbacks_queue.validate_queue_and_media")
    async def test_returns_early_if_queue_item_missing(self, mock_validate, handlers):
        """Returns early if queue item no longer exists."""
        mock_validate.return_value = (None, None)

        user = _make_user()
        query = _make_query()

        await handlers.handle_back("q-1", user, query)

        handlers.service._build_caption.assert_not_called()

    @patch("src.services.core.telegram_callbacks_queue.telegram_edit_with_retry")
    @patch("src.services.core.telegram_callbacks_queue.validate_queue_and_media")
    async def test_returns_early_if_no_chat_settings(
        self, mock_validate, mock_retry, handlers
    ):
        """Returns early if chat_settings not found — message not updated."""
        mock_validate.return_value = (Mock(), Mock())
        handlers.service.settings_service.get_settings.return_value = None

        user = _make_user()
        query = _make_query()

        await handlers.handle_back("q-1", user, query)

        mock_retry.assert_not_called()


# ──────────────────────────────────────────────────────────────
# handle_regenerate_caption
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
class TestHandleRegenerateCaption:
    @patch("src.services.core.telegram_callbacks_queue.build_queue_action_keyboard")
    @patch("src.services.core.telegram_callbacks_queue.validate_queue_and_media")
    @patch("src.utils.resilience.telegram_edit_with_retry")
    async def test_success_regenerates_and_updates(
        self, mock_retry, mock_validate, mock_keyboard, handlers
    ):
        """Generates new caption, rebuilds message, updates UI."""
        chat_settings = Mock(enable_ai_captions=True, enable_instagram_api=False)
        handlers.service.settings_service.get_settings.return_value = chat_settings

        queue_item = Mock(media_item_id="m-1")
        media_item = Mock(generated_caption="new caption", caption=None)
        mock_validate.return_value = (queue_item, media_item)
        handlers.service.media_repo.get_by_id.return_value = media_item

        mock_caption_svc = Mock()
        mock_caption_svc.generate_caption = AsyncMock(return_value="AI generated")
        mock_caption_svc.__enter__ = Mock(return_value=mock_caption_svc)
        mock_caption_svc.__exit__ = Mock(return_value=False)

        user = _make_user()
        query = _make_query()

        with patch(
            "src.services.core.caption_service.CaptionService",
            return_value=mock_caption_svc,
        ):
            await handlers.handle_regenerate_caption("q-1", user, query)

        mock_retry.assert_called_once()

    async def test_disabled_ai_captions_answers_alert(self, handlers):
        """If AI captions are disabled, show alert and return."""
        chat_settings = Mock(enable_ai_captions=False)
        handlers.service.settings_service.get_settings.return_value = chat_settings

        user = _make_user()
        query = _make_query()

        await handlers.handle_regenerate_caption("q-1", user, query)

        query.answer.assert_called_once()
        assert "disabled" in query.answer.call_args[0][0]

    @patch("src.services.core.telegram_callbacks_queue.validate_queue_and_media")
    async def test_generation_failure_answers_alert(self, mock_validate, handlers):
        """If caption generation returns None, show alert."""
        chat_settings = Mock(enable_ai_captions=True)
        handlers.service.settings_service.get_settings.return_value = chat_settings
        mock_validate.return_value = (Mock(media_item_id="m-1"), Mock())

        mock_caption_svc = Mock()
        mock_caption_svc.generate_caption = AsyncMock(return_value=None)
        mock_caption_svc.__enter__ = Mock(return_value=mock_caption_svc)
        mock_caption_svc.__exit__ = Mock(return_value=False)

        user = _make_user()
        query = _make_query()

        with patch(
            "src.services.core.caption_service.CaptionService",
            return_value=mock_caption_svc,
        ):
            await handlers.handle_regenerate_caption("q-1", user, query)

        query.answer.assert_called_once()
        assert "failed" in query.answer.call_args[0][0]

    async def test_no_chat_settings_answers_alert(self, handlers):
        """If chat_settings is None, show alert."""
        handlers.service.settings_service.get_settings.return_value = None

        user = _make_user()
        query = _make_query()

        await handlers.handle_regenerate_caption("q-1", user, query)

        query.answer.assert_called_once()


# ──────────────────────────────────────────────────────────────
# handle_reject_confirmation
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
class TestHandleRejectConfirmation:
    @patch("src.services.core.telegram_callbacks_queue.validate_queue_item")
    @patch("src.services.core.telegram_callbacks_queue.telegram_edit_with_retry")
    async def test_shows_confirmation_dialog(self, mock_retry, mock_validate, handlers):
        """Shows Yes/No keyboard with file name and warning."""
        queue_item = Mock(media_item_id="m-1")
        mock_validate.return_value = queue_item
        media_item = Mock(file_name="photo.jpg")
        handlers.service.media_repo.get_by_id.return_value = media_item

        user = _make_user()
        query = _make_query()

        await handlers.handle_reject_confirmation("q-1", user, query)

        mock_retry.assert_called_once()
        call_kwargs = mock_retry.call_args[1]
        assert "Are you sure" in call_kwargs["caption"]
        assert call_kwargs["reply_markup"] is not None
        handlers.service.interaction_service.log_callback.assert_called_once()

    @patch("src.services.core.telegram_callbacks_queue.validate_queue_item")
    async def test_returns_early_if_queue_item_missing(self, mock_validate, handlers):
        """Returns early if queue item not found."""
        mock_validate.return_value = None

        user = _make_user()
        query = _make_query()

        await handlers.handle_reject_confirmation("q-1", user, query)

        handlers.service.media_repo.get_by_id.assert_not_called()


# ──────────────────────────────────────────────────────────────
# handle_cancel_reject
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
class TestHandleCancelReject:
    @patch("src.services.core.telegram_callbacks_queue.build_queue_action_keyboard")
    @patch("src.services.core.telegram_callbacks_queue.validate_queue_and_media")
    @patch("src.services.core.telegram_callbacks_queue.telegram_edit_with_retry")
    async def test_restores_original_buttons(
        self, mock_retry, mock_validate, mock_keyboard, handlers
    ):
        """Cancelling reject restores original caption and keyboard."""
        queue_item = Mock()
        media_item = Mock()
        mock_validate.return_value = (queue_item, media_item)
        mock_keyboard.return_value = Mock()
        handlers.service.settings_service.get_settings.return_value = Mock(
            enable_instagram_api=True
        )

        user = _make_user()
        query = _make_query()

        await handlers.handle_cancel_reject("q-1", user, query)

        mock_validate.assert_called_once()
        handlers.service._build_caption.assert_called_once()
        mock_retry.assert_called_once()
        handlers.service.interaction_service.log_callback.assert_called_once()


# ──────────────────────────────────────────────────────────────
# handle_rejected + _do_handle_rejected
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
class TestHandleRejected:
    async def test_sets_cancel_flag_and_uses_lock(self, handlers):
        """Sets cancel flag and delegates via _safe_locked_callback."""
        user = _make_user()
        query = _make_query()

        await handlers.handle_rejected("q-1", user, query)

        handlers.service.get_cancel_flag.assert_called_once_with("q-1")
        handlers.service.get_cancel_flag.return_value.set.assert_called_once()
        handlers.core._safe_locked_callback.assert_called_once()

    @patch("src.services.core.telegram_callbacks_queue.telegram_edit_with_retry")
    async def test_do_handle_rejected_happy_path(self, mock_retry, handlers):
        """Successful rejection: claim, DB ops, update caption, log."""
        queue_item = Mock(media_item_id="m-1")
        handlers.service.queue_repo.claim_for_processing.return_value = queue_item
        media_item = Mock(file_name="photo.jpg")
        handlers.core._execute_reject_db_ops.return_value = media_item

        user = _make_user()
        query = _make_query()

        await handlers._do_handle_rejected("q-1", user, query)

        handlers.core._execute_reject_db_ops.assert_called_once_with(
            "q-1", queue_item, user
        )
        mock_retry.assert_called_once()
        handlers.service.interaction_service.log_callback.assert_called_once()
        handlers.service.interaction_service.log_bot_response.assert_called_once()

    @patch("src.services.core.telegram_callbacks_queue.validate_queue_item")
    async def test_do_handle_rejected_already_claimed(self, mock_validate, handlers):
        """If claim returns None, calls validate_queue_item."""
        mock_validate.return_value = AsyncMock()
        handlers.service.queue_repo.claim_for_processing.return_value = None

        user = _make_user()
        query = _make_query()

        await handlers._do_handle_rejected("q-1", user, query)

        mock_validate.assert_called_once()
        handlers.core._execute_reject_db_ops.assert_not_called()

    @patch("src.services.core.telegram_callbacks_queue.telegram_edit_with_retry")
    async def test_do_handle_rejected_verbose_caption(self, mock_retry, handlers):
        """Verbose mode includes file name and permanent rejection notice."""
        handlers.service._is_verbose.return_value = True
        queue_item = Mock(media_item_id="m-1")
        handlers.service.queue_repo.claim_for_processing.return_value = queue_item
        media_item = Mock(file_name="photo.jpg")
        handlers.core._execute_reject_db_ops.return_value = media_item

        user = _make_user()
        query = _make_query()

        await handlers._do_handle_rejected("q-1", user, query)

        caption = mock_retry.call_args[1]["caption"]
        assert "Permanently Rejected" in caption

    @patch("src.services.core.telegram_callbacks_queue.telegram_edit_with_retry")
    async def test_do_handle_rejected_operational_error_retry(
        self, mock_retry, handlers
    ):
        """On OperationalError, refresh and retry once."""
        queue_item = Mock(media_item_id="m-1")
        handlers.service.queue_repo.claim_for_processing.return_value = queue_item
        handlers.service.history_repo.get_by_queue_item_id.return_value = None
        handlers.service.queue_repo.get_by_id.return_value = queue_item

        media_item = Mock(file_name="photo.jpg")
        handlers.core._execute_reject_db_ops.side_effect = [
            OperationalError("ssl", {}, Exception()),
            media_item,
        ]

        user = _make_user()
        query = _make_query()

        await handlers._do_handle_rejected("q-1", user, query)

        assert handlers.core._execute_reject_db_ops.call_count == 2
        handlers.core._refresh_repo_sessions.assert_called_once()
