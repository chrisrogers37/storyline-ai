"""Tests for TelegramCallbackAdminHandlers — batch approve, resume, reset."""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from src.services.core.telegram_callbacks_admin import TelegramCallbackAdminHandlers
from src.services.core.telegram_callbacks_core import TelegramCallbackCore
from tests.src.services.conftest import make_query as _make_query
from tests.src.services.conftest import make_user as _make_user


@pytest.fixture
def mock_service():
    """Minimal TelegramService mock for admin handler tests."""
    service = Mock()
    service.queue_repo = Mock()
    service.interaction_service = Mock()
    service._get_display_name.return_value = "AdminUser"
    service.set_paused = Mock()
    return service


@pytest.fixture
def mock_core(mock_service):
    """TelegramCallbackCore mock."""
    core = Mock(spec=TelegramCallbackCore)
    core.service = mock_service
    core._execute_complete_db_ops = Mock()
    return core


@pytest.fixture
def handlers(mock_service, mock_core):
    """TelegramCallbackAdminHandlers with mocked dependencies."""
    return TelegramCallbackAdminHandlers(mock_service, mock_core)


# ──────────────────────────────────────────────────────────────
# handle_batch_approve
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
class TestHandleBatchApprove:
    @patch("src.services.core.telegram_callbacks_admin.telegram_edit_with_retry")
    async def test_approves_all_items(self, mock_retry, handlers):
        """Approves all pending+processing items and reports count."""
        qi1, qi2 = Mock(id="q-1"), Mock(id="q-2")
        handlers.service.queue_repo.get_all_with_media.side_effect = [
            [(qi1, "f1.jpg", "memes")],  # pending
            [(qi2, "f2.jpg", "memes")],  # processing
        ]
        handlers.service.queue_repo.claim_for_processing.return_value = Mock()

        user = _make_user()
        query = _make_query()

        await handlers.handle_batch_approve("cs-1", user, query)

        assert handlers.core._execute_complete_db_ops.call_count == 2
        handlers.service.interaction_service.log_callback.assert_called_once()

    @patch("src.services.core.telegram_callbacks_admin.telegram_edit_with_retry")
    async def test_no_items_to_approve(self, mock_retry, handlers):
        """Shows 'no pending items' when both lists are empty."""
        handlers.service.queue_repo.get_all_with_media.return_value = []

        user = _make_user()
        query = _make_query()

        await handlers.handle_batch_approve("cs-1", user, query)

        mock_retry.assert_called()
        # First real call after the progress message
        first_call_text = mock_retry.call_args_list[0][0][1]
        assert "No pending items" in first_call_text

    @patch("src.services.core.telegram_callbacks_admin.telegram_edit_with_retry")
    async def test_mixed_success_and_failure(self, mock_retry, handlers):
        """Reports both approved and failed counts."""
        qi1, qi2 = Mock(id="q-1"), Mock(id="q-2")
        handlers.service.queue_repo.get_all_with_media.side_effect = [
            [(qi1, "f1.jpg", "m"), (qi2, "f2.jpg", "m")],
            [],
        ]
        # First succeeds, second fails
        handlers.service.queue_repo.claim_for_processing.side_effect = [Mock(), Mock()]
        handlers.core._execute_complete_db_ops.side_effect = [
            None,
            Exception("db error"),
        ]

        user = _make_user()
        query = _make_query()

        await handlers.handle_batch_approve("cs-1", user, query)

        # Last call should contain both approved and failed counts
        last_call_text = mock_retry.call_args_list[-1][0][1]
        assert "1 item marked as posted" in last_call_text
        assert "1 item failed" in last_call_text

    @patch("src.services.core.telegram_callbacks_admin.telegram_edit_with_retry")
    async def test_claim_failure_counts_as_failed(self, mock_retry, handlers):
        """If claim_for_processing returns None, it counts as failed."""
        qi1 = Mock(id="q-1")
        handlers.service.queue_repo.get_all_with_media.side_effect = [
            [(qi1, "f1.jpg", "m")],
            [],
        ]
        handlers.service.queue_repo.claim_for_processing.return_value = None

        user = _make_user()
        query = _make_query()

        await handlers.handle_batch_approve("cs-1", user, query)

        handlers.core._execute_complete_db_ops.assert_not_called()


# ──────────────────────────────────────────────────────────────
# handle_batch_approve_cancel
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
class TestHandleBatchApproveCancel:
    @patch("src.services.core.telegram_callbacks_admin.telegram_edit_with_retry")
    async def test_shows_cancelled_message(self, mock_retry, handlers):
        """Shows cancellation message."""
        user = _make_user()
        query = _make_query()

        await handlers.handle_batch_approve_cancel("cs-1", user, query)

        mock_retry.assert_called_once()
        assert "cancelled" in mock_retry.call_args[0][1].lower()


# ──────────────────────────────────────────────────────────────
# handle_resume_callback
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
class TestHandleResumeCallback:
    @patch("src.services.core.telegram_callbacks_admin.telegram_edit_with_retry")
    async def test_reschedule_action(self, mock_retry, handlers):
        """Reschedules overdue posts and resumes delivery."""
        now = datetime.utcnow()
        overdue = [Mock(id="q-1", scheduled_for=now - timedelta(hours=2))]
        future = [Mock(id="q-2", scheduled_for=now + timedelta(hours=1))]
        handlers.service.queue_repo.get_all.return_value = overdue + future

        user = _make_user()
        query = _make_query()

        await handlers.handle_resume_callback("reschedule", user, query)

        handlers.service.queue_repo.update_scheduled_time.assert_called_once()
        handlers.service.set_paused.assert_called_once_with(False, user)
        handlers.service.interaction_service.log_callback.assert_called_once()

    @patch("src.services.core.telegram_callbacks_admin.telegram_edit_with_retry")
    async def test_clear_action(self, mock_retry, handlers):
        """Clears overdue posts and resumes delivery."""
        now = datetime.utcnow()
        overdue = [Mock(id="q-1", scheduled_for=now - timedelta(hours=2))]
        handlers.service.queue_repo.get_all.return_value = overdue

        user = _make_user()
        query = _make_query()

        await handlers.handle_resume_callback("clear", user, query)

        handlers.service.queue_repo.delete.assert_called_once()
        handlers.service.set_paused.assert_called_once_with(False, user)

    @patch("src.services.core.telegram_callbacks_admin.telegram_edit_with_retry")
    async def test_force_action(self, mock_retry, handlers):
        """Force resumes without handling overdue posts."""
        now = datetime.utcnow()
        overdue = [Mock(id="q-1", scheduled_for=now - timedelta(hours=2))]
        handlers.service.queue_repo.get_all.return_value = overdue

        user = _make_user()
        query = _make_query()

        await handlers.handle_resume_callback("force", user, query)

        handlers.service.set_paused.assert_called_once_with(False, user)
        handlers.service.queue_repo.delete.assert_not_called()
        handlers.service.queue_repo.update_scheduled_time.assert_not_called()

    @patch("src.services.core.telegram_callbacks_admin.telegram_edit_with_retry")
    async def test_error_shows_fallback_message(self, mock_retry, handlers):
        """On exception, shows error message."""
        handlers.service.queue_repo.get_all.side_effect = RuntimeError("db down")

        user = _make_user()
        query = _make_query()

        await handlers.handle_resume_callback("reschedule", user, query)

        mock_retry.assert_called_once()
        assert "Error" in mock_retry.call_args[0][1]


# ──────────────────────────────────────────────────────────────
# handle_reset_callback
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
class TestHandleResetCallback:
    @patch("src.services.core.telegram_callbacks_admin.telegram_edit_with_retry")
    async def test_confirm_clears_queue(self, mock_retry, handlers):
        """Confirm action deletes all pending posts."""
        pending = [Mock(id="q-1"), Mock(id="q-2")]
        handlers.service.queue_repo.get_all.return_value = pending

        user = _make_user()
        query = _make_query()

        await handlers.handle_reset_callback("confirm", user, query)

        assert handlers.service.queue_repo.delete.call_count == 2
        handlers.service.interaction_service.log_callback.assert_called_once()

    @patch("src.services.core.telegram_callbacks_admin.telegram_edit_with_retry")
    async def test_cancel_does_not_clear(self, mock_retry, handlers):
        """Cancel action shows message but doesn't delete anything."""
        user = _make_user()
        query = _make_query()

        await handlers.handle_reset_callback("cancel", user, query)

        handlers.service.queue_repo.delete.assert_not_called()
        mock_retry.assert_called_once()
        assert "Cancelled" in mock_retry.call_args[0][1]

    @patch("src.services.core.telegram_callbacks_admin.telegram_edit_with_retry")
    async def test_error_during_confirm(self, mock_retry, handlers):
        """On exception during confirm, shows error message."""
        handlers.service.queue_repo.get_all.side_effect = RuntimeError("db down")

        user = _make_user()
        query = _make_query()

        await handlers.handle_reset_callback("confirm", user, query)

        mock_retry.assert_called_once()
        assert "Error" in mock_retry.call_args[0][1]
