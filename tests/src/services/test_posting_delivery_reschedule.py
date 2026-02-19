"""Tests for smart delivery reschedule logic in PostingService."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from contextlib import contextmanager
from uuid import uuid4

from src.services.core.posting import PostingService


@contextmanager
def mock_track_execution(*args, **kwargs):
    """Mock context manager for track_execution."""
    yield "mock_run_id"


@pytest.fixture
def posting_service():
    """Create PostingService with mocked dependencies."""
    with patch.object(PostingService, "__init__", lambda self: None):
        service = PostingService()
        service.queue_repo = Mock()
        service.media_repo = Mock()
        service.history_repo = Mock()
        service.telegram_service = Mock()
        service.lock_service = Mock()
        service.settings_service = Mock()
        service.service_run_repo = Mock()
        service.service_name = "PostingService"
        service._instagram_service = None
        service._cloud_service = None
        service.track_execution = mock_track_execution
        service.set_result_summary = Mock()
        return service


@pytest.mark.unit
class TestRescheduleOverdueForPausedChat:
    """Tests for PostingService.reschedule_overdue_for_paused_chat()."""

    def test_reschedule_bumps_overdue_items(self, posting_service):
        """reschedule_overdue_for_paused_chat bumps overdue items +24hr."""
        mock_settings = Mock()
        mock_settings.id = uuid4()
        posting_service.settings_service.get_settings.return_value = mock_settings

        now = datetime.utcnow()
        item_1 = MagicMock()
        item_1.scheduled_for = now - timedelta(hours=2)
        item_2 = MagicMock()
        item_2.scheduled_for = now - timedelta(hours=50)
        posting_service.queue_repo.get_overdue_pending.return_value = [item_1, item_2]
        posting_service.queue_repo.db = Mock()

        result = posting_service.reschedule_overdue_for_paused_chat(
            telegram_chat_id=-100123
        )

        assert result["rescheduled"] == 2
        assert result["chat_id"] == -100123
        assert item_1.scheduled_for > now
        assert item_2.scheduled_for > now
        posting_service.queue_repo.db.commit.assert_called_once()

    def test_reschedule_with_no_overdue_items(self, posting_service):
        """Returns 0 rescheduled when no items are overdue."""
        mock_settings = Mock()
        mock_settings.id = uuid4()
        posting_service.settings_service.get_settings.return_value = mock_settings
        posting_service.queue_repo.get_overdue_pending.return_value = []

        result = posting_service.reschedule_overdue_for_paused_chat(
            telegram_chat_id=-100123
        )

        assert result["rescheduled"] == 0

    def test_reschedule_passes_correct_tenant_id(self, posting_service):
        """Verifies tenant ID is correctly threaded through."""
        mock_settings = Mock()
        mock_settings.id = uuid4()
        posting_service.settings_service.get_settings.return_value = mock_settings
        posting_service.queue_repo.get_overdue_pending.return_value = []

        posting_service.reschedule_overdue_for_paused_chat(telegram_chat_id=-200456)

        posting_service.settings_service.get_settings.assert_called_with(-200456)

    def test_reschedule_item_far_in_past_needs_multiple_bumps(self, posting_service):
        """An item scheduled 5 days ago needs 6 bumps of +24hr."""
        mock_settings = Mock()
        mock_settings.id = uuid4()
        posting_service.settings_service.get_settings.return_value = mock_settings

        now = datetime.utcnow()
        item = MagicMock()
        item.scheduled_for = now - timedelta(days=5, hours=1)
        posting_service.queue_repo.get_overdue_pending.return_value = [item]
        posting_service.queue_repo.db = Mock()

        posting_service.reschedule_overdue_for_paused_chat(telegram_chat_id=-100123)

        assert item.scheduled_for > now
        assert item.scheduled_for < now + timedelta(hours=24)

    def test_reschedule_no_chat_settings(self, posting_service):
        """When _get_chat_settings returns None, passes None as chat_settings_id."""
        posting_service.settings_service.get_settings.return_value = None
        posting_service.queue_repo.get_overdue_pending.return_value = []

        result = posting_service.reschedule_overdue_for_paused_chat(
            telegram_chat_id=-100123
        )

        posting_service.queue_repo.get_overdue_pending.assert_called_once_with(
            chat_settings_id=None
        )
        assert result["rescheduled"] == 0
