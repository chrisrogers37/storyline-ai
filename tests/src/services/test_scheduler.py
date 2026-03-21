"""Tests for SchedulerService (JIT model)."""

import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from src.exceptions.google_drive import GoogleDriveAuthError
from src.services.core.scheduler import SchedulerService
from tests.src.services.conftest import mock_track_execution


@pytest.fixture
def scheduler_service_mocked():
    """Create SchedulerService with all dependencies mocked."""
    with patch.object(SchedulerService, "__init__", lambda self: None):
        service = SchedulerService()
        service.media_repo = Mock()
        service.queue_repo = Mock()
        service.lock_repo = Mock()
        service.category_mix_repo = Mock()
        service.settings_service = Mock()
        service.telegram_service = AsyncMock()
        service.service_run_repo = Mock()
        service.service_name = "SchedulerService"
        service.SCHEDULE_JITTER_MINUTES = 30
        service.track_execution = mock_track_execution
        service.set_result_summary = Mock()
        return service


def _make_chat_settings(
    *,
    posts_per_day=3,
    posting_hours_start=9,
    posting_hours_end=21,
    last_post_sent_at=None,
    is_paused=False,
    telegram_chat_id=-100123,
    settings_id=None,
):
    """Helper to build a mock chat_settings object."""
    cs = Mock()
    cs.posts_per_day = posts_per_day
    cs.posting_hours_start = posting_hours_start
    cs.posting_hours_end = posting_hours_end
    cs.last_post_sent_at = last_post_sent_at
    cs.is_paused = is_paused
    cs.telegram_chat_id = telegram_chat_id
    cs.id = settings_id or uuid4()
    return cs


# ------------------------------------------------------------------
# is_slot_due
# ------------------------------------------------------------------


@pytest.mark.unit
class TestIsSlotDue:
    """Tests for SchedulerService.is_slot_due()."""

    def test_in_window_and_first_post_ever(self, scheduler_service_mocked):
        """Slot is due when last_post_sent_at is None (first post)."""
        service = scheduler_service_mocked
        service.category_mix_repo.get_current_mix_as_dict.return_value = {}

        cs = _make_chat_settings(
            posting_hours_start=9,
            posting_hours_end=21,
            posts_per_day=3,
            last_post_sent_at=None,
        )

        with patch("src.services.core.scheduler.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2026, 3, 21, 12, 0)
            result = service.is_slot_due(cs)

        # Should be due (None = no category preference)
        assert result is None

    def test_outside_posting_window_returns_false(self, scheduler_service_mocked):
        """Returns False when current time is outside posting window."""
        service = scheduler_service_mocked
        cs = _make_chat_settings(
            posting_hours_start=9,
            posting_hours_end=17,
        )

        with patch("src.services.core.scheduler.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2026, 3, 21, 20, 0)
            result = service.is_slot_due(cs)

        assert result is False

    def test_too_soon_since_last_post(self, scheduler_service_mocked):
        """Returns False when last post was too recent."""
        service = scheduler_service_mocked
        # Window 9-21 = 12 hours, 3 posts/day => interval = 4 hours
        cs = _make_chat_settings(
            posting_hours_start=9,
            posting_hours_end=21,
            posts_per_day=3,
            last_post_sent_at=datetime(2026, 3, 21, 11, 0),
        )

        with patch("src.services.core.scheduler.datetime") as mock_dt:
            # Only 1 hour since last post, interval is 4 hours
            mock_dt.utcnow.return_value = datetime(2026, 3, 21, 12, 0)
            result = service.is_slot_due(cs)

        assert result is False

    def test_due_after_sufficient_interval(self, scheduler_service_mocked):
        """Returns category (or None) when enough time has elapsed."""
        service = scheduler_service_mocked
        service.category_mix_repo.get_current_mix_as_dict.return_value = {}

        # Window 9-21 = 12 hours, 3 posts/day => interval = 4 hours
        cs = _make_chat_settings(
            posting_hours_start=9,
            posting_hours_end=21,
            posts_per_day=3,
            last_post_sent_at=datetime(2026, 3, 21, 8, 0),
        )

        with patch("src.services.core.scheduler.datetime") as mock_dt:
            # 5 hours since last post, interval is 4 hours -> due
            mock_dt.utcnow.return_value = datetime(2026, 3, 21, 13, 0)
            result = service.is_slot_due(cs)

        # No category ratios -> None (due, no preference)
        assert result is None

    def test_midnight_rollover_window(self, scheduler_service_mocked):
        """Slot is due when posting window crosses midnight (e.g. 22-2)."""
        service = scheduler_service_mocked
        service.category_mix_repo.get_current_mix_as_dict.return_value = {}

        cs = _make_chat_settings(
            posting_hours_start=22,
            posting_hours_end=2,
            posts_per_day=2,
            last_post_sent_at=None,
        )

        with patch("src.services.core.scheduler.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2026, 3, 21, 23, 0)
            result = service.is_slot_due(cs)

        assert result is not False

    def test_single_post_per_day(self, scheduler_service_mocked):
        """Single post per day with 12-hour window => interval = 12 hours."""
        service = scheduler_service_mocked
        service.category_mix_repo.get_current_mix_as_dict.return_value = {}

        cs = _make_chat_settings(
            posting_hours_start=9,
            posting_hours_end=21,
            posts_per_day=1,
            last_post_sent_at=datetime(2026, 3, 21, 9, 0),
        )

        with patch("src.services.core.scheduler.datetime") as mock_dt:
            # Only 2 hours since last post, interval is 12 hours
            mock_dt.utcnow.return_value = datetime(2026, 3, 21, 11, 0)
            result = service.is_slot_due(cs)

        assert result is False

    def test_returns_category_when_ratios_configured(self, scheduler_service_mocked):
        """Returns a category string when category ratios are configured."""
        service = scheduler_service_mocked
        service.category_mix_repo.get_current_mix_as_dict.return_value = {
            "memes": Decimal("0.7"),
            "merch": Decimal("0.3"),
        }

        cs = _make_chat_settings(
            posting_hours_start=9,
            posting_hours_end=21,
            posts_per_day=3,
            last_post_sent_at=None,
        )

        with patch("src.services.core.scheduler.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2026, 3, 21, 12, 0)
            result = service.is_slot_due(cs)

        assert isinstance(result, str)
        assert result in ("memes", "merch")


# ------------------------------------------------------------------
# process_slot
# ------------------------------------------------------------------


@pytest.mark.unit
class TestProcessSlot:
    """Tests for SchedulerService.process_slot()."""

    @pytest.mark.asyncio
    async def test_paused_returns_paused(self, scheduler_service_mocked):
        """Returns paused result when chat is paused."""
        service = scheduler_service_mocked
        cs = _make_chat_settings(is_paused=True)
        service.settings_service.get_settings.return_value = cs

        result = await service.process_slot(telegram_chat_id=-100123)

        assert result["posted"] is False
        assert result["reason"] == "paused"

    @pytest.mark.asyncio
    async def test_not_due_returns_not_due(self, scheduler_service_mocked):
        """Returns not_due when is_slot_due returns False."""
        service = scheduler_service_mocked
        cs = _make_chat_settings(is_paused=False)
        service.settings_service.get_settings.return_value = cs
        service.is_slot_due = Mock(return_value=False)

        result = await service.process_slot(telegram_chat_id=-100123)

        assert result["posted"] is False
        assert result["reason"] == "not_due"

    @pytest.mark.asyncio
    async def test_posts_successfully(self, scheduler_service_mocked):
        """Delegates to _select_and_send when slot is due."""
        service = scheduler_service_mocked
        cs = _make_chat_settings(is_paused=False)
        service.settings_service.get_settings.return_value = cs
        service.is_slot_due = Mock(return_value=None)

        expected_result = {
            "posted": True,
            "queue_item_id": "q-1",
            "media_file": "test.jpg",
        }
        service._select_and_send = AsyncMock(return_value=expected_result)

        result = await service.process_slot(telegram_chat_id=-100123)

        assert result["posted"] is True
        service._select_and_send.assert_called_once()
        call_kwargs = service._select_and_send.call_args.kwargs
        assert call_kwargs["category"] is None
        assert call_kwargs["triggered_by"] == "scheduler"

    @pytest.mark.asyncio
    async def test_passes_category_from_is_slot_due(self, scheduler_service_mocked):
        """Passes category string from is_slot_due to _select_and_send."""
        service = scheduler_service_mocked
        cs = _make_chat_settings(is_paused=False)
        service.settings_service.get_settings.return_value = cs
        service.is_slot_due = Mock(return_value="memes")
        service._select_and_send = AsyncMock(return_value={"posted": True})

        await service.process_slot(telegram_chat_id=-100123)

        call_kwargs = service._select_and_send.call_args.kwargs
        assert call_kwargs["category"] == "memes"

    @pytest.mark.asyncio
    async def test_no_eligible_media(self, scheduler_service_mocked):
        """Returns no_eligible_media when _select_media returns None."""
        service = scheduler_service_mocked
        cs = _make_chat_settings(is_paused=False)
        service.settings_service.get_settings.return_value = cs
        service.is_slot_due = Mock(return_value=None)

        # Let _select_and_send flow through to real implementation
        service.media_repo.get_next_eligible_for_posting.return_value = None

        result = await service.process_slot(telegram_chat_id=-100123)

        assert result["posted"] is False
        assert result["reason"] == "no_eligible_media"


# ------------------------------------------------------------------
# force_send_next
# ------------------------------------------------------------------


@pytest.mark.unit
class TestForceSendNext:
    """Tests for SchedulerService.force_send_next()."""

    @pytest.mark.asyncio
    async def test_success(self, scheduler_service_mocked):
        """Sends immediately regardless of is_slot_due."""
        service = scheduler_service_mocked
        cs = _make_chat_settings()
        service.settings_service.get_settings.return_value = cs

        mock_media = Mock(id=uuid4(), file_name="force.jpg", category="memes")
        service.media_repo.get_next_eligible_for_posting.return_value = mock_media

        mock_queue_item = Mock(id=uuid4())
        service.queue_repo.create.return_value = mock_queue_item
        service.telegram_service.send_notification = AsyncMock(return_value=True)

        result = await service.force_send_next(
            telegram_chat_id=-100123, user_id="user-1"
        )

        assert result["posted"] is True
        assert result["media_file"] == "force.jpg"
        service.settings_service.update_last_post_sent_at.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_media_available(self, scheduler_service_mocked):
        """Returns error when no eligible media exists."""
        service = scheduler_service_mocked
        cs = _make_chat_settings()
        service.settings_service.get_settings.return_value = cs
        service.media_repo.get_next_eligible_for_posting.return_value = None

        result = await service.force_send_next(telegram_chat_id=-100123)

        assert result["posted"] is False
        assert result["error"] == "No eligible media available"

    @pytest.mark.asyncio
    async def test_force_sent_indicator_passed_through(self, scheduler_service_mocked):
        """force_sent_indicator is threaded to _send_to_telegram."""
        service = scheduler_service_mocked
        cs = _make_chat_settings()
        service.settings_service.get_settings.return_value = cs

        mock_media = Mock(id=uuid4(), file_name="f.jpg", category=None)
        service.media_repo.get_next_eligible_for_posting.return_value = mock_media

        mock_queue_item = Mock(id=uuid4())
        service.queue_repo.create.return_value = mock_queue_item
        service.telegram_service.send_notification = AsyncMock(return_value=True)

        await service.force_send_next(
            telegram_chat_id=-100123, force_sent_indicator=True
        )

        service.telegram_service.send_notification.assert_called_once_with(
            str(mock_queue_item.id), force_sent=True
        )


# ------------------------------------------------------------------
# _send_to_telegram
# ------------------------------------------------------------------


@pytest.mark.unit
class TestSendToTelegram:
    """Tests for SchedulerService._send_to_telegram()."""

    @pytest.mark.asyncio
    async def test_success(self, scheduler_service_mocked):
        """Marks item as processing, sends, returns True."""
        service = scheduler_service_mocked
        queue_item = Mock(id=uuid4())
        service.telegram_service.send_notification = AsyncMock(return_value=True)

        result = await service._send_to_telegram(queue_item)

        assert result is True
        service.queue_repo.update_status.assert_called_once_with(
            str(queue_item.id), "processing"
        )

    @pytest.mark.asyncio
    async def test_failure_rolls_back_to_pending(self, scheduler_service_mocked):
        """Rolls back to pending when send_notification returns False."""
        service = scheduler_service_mocked
        queue_item = Mock(id=uuid4())
        service.telegram_service.send_notification = AsyncMock(return_value=False)

        result = await service._send_to_telegram(queue_item)

        assert result is False
        # First call: processing, second call: rollback to pending
        calls = service.queue_repo.update_status.call_args_list
        assert calls[0][0] == (str(queue_item.id), "processing")
        assert calls[1][0] == (str(queue_item.id), "pending")

    @pytest.mark.asyncio
    async def test_google_drive_auth_error_reraises(self, scheduler_service_mocked):
        """GoogleDriveAuthError rolls back and re-raises."""
        service = scheduler_service_mocked
        queue_item = Mock(id=uuid4())
        service.telegram_service.send_notification = AsyncMock(
            side_effect=GoogleDriveAuthError("Token expired")
        )

        with pytest.raises(GoogleDriveAuthError, match="Token expired"):
            await service._send_to_telegram(queue_item)

        # Should have rolled back to pending
        service.queue_repo.update_status.assert_any_call(str(queue_item.id), "pending")

    @pytest.mark.asyncio
    async def test_generic_exception_returns_false(self, scheduler_service_mocked):
        """Generic exceptions are caught, rolled back, returns False."""
        service = scheduler_service_mocked
        queue_item = Mock(id=uuid4())
        service.telegram_service.send_notification = AsyncMock(
            side_effect=RuntimeError("Network error")
        )

        result = await service._send_to_telegram(queue_item)

        assert result is False
        service.queue_repo.update_status.assert_any_call(str(queue_item.id), "pending")

    @pytest.mark.asyncio
    async def test_rollback_failure_suppressed(self, scheduler_service_mocked):
        """If rollback itself fails, the original exception still propagates."""
        service = scheduler_service_mocked
        queue_item = Mock(id=uuid4())
        service.telegram_service.send_notification = AsyncMock(
            side_effect=GoogleDriveAuthError("Auth fail")
        )
        # Make the rollback raise too
        service.queue_repo.update_status.side_effect = [
            None,  # processing
            Exception("DB down"),  # rollback fails
        ]

        with pytest.raises(GoogleDriveAuthError, match="Auth fail"):
            await service._send_to_telegram(queue_item)


# ------------------------------------------------------------------
# Posting window helpers
# ------------------------------------------------------------------


@pytest.mark.unit
class TestPostingWindowHelpers:
    """Tests for _in_posting_window and _posting_window_hours."""

    def test_in_window_normal_hours(self):
        """Time within normal posting window returns True."""
        cs = _make_chat_settings(posting_hours_start=9, posting_hours_end=21)
        now = datetime(2026, 3, 21, 12, 0)

        assert SchedulerService._in_posting_window(now, cs) is True

    def test_outside_window_normal_hours(self):
        """Time outside normal posting window returns False."""
        cs = _make_chat_settings(posting_hours_start=9, posting_hours_end=17)
        now = datetime(2026, 3, 21, 20, 0)

        assert SchedulerService._in_posting_window(now, cs) is False

    def test_at_start_boundary(self):
        """Time exactly at window start is inside."""
        cs = _make_chat_settings(posting_hours_start=9, posting_hours_end=17)
        now = datetime(2026, 3, 21, 9, 0)

        assert SchedulerService._in_posting_window(now, cs) is True

    def test_at_end_boundary(self):
        """Time exactly at window end is outside (half-open interval)."""
        cs = _make_chat_settings(posting_hours_start=9, posting_hours_end=17)
        now = datetime(2026, 3, 21, 17, 0)

        assert SchedulerService._in_posting_window(now, cs) is False

    def test_midnight_crossing_before_midnight(self):
        """Window 22-2: time at 23 is inside."""
        cs = _make_chat_settings(posting_hours_start=22, posting_hours_end=2)
        now = datetime(2026, 3, 21, 23, 0)

        assert SchedulerService._in_posting_window(now, cs) is True

    def test_midnight_crossing_after_midnight(self):
        """Window 22-2: time at 1 is inside."""
        cs = _make_chat_settings(posting_hours_start=22, posting_hours_end=2)
        now = datetime(2026, 3, 22, 1, 0)

        assert SchedulerService._in_posting_window(now, cs) is True

    def test_midnight_crossing_outside(self):
        """Window 22-2: time at 15 is outside."""
        cs = _make_chat_settings(posting_hours_start=22, posting_hours_end=2)
        now = datetime(2026, 3, 21, 15, 0)

        assert SchedulerService._in_posting_window(now, cs) is False

    def test_posting_window_hours_normal(self):
        """Normal window: 21 - 9 = 12 hours."""
        cs = _make_chat_settings(posting_hours_start=9, posting_hours_end=21)

        assert SchedulerService._posting_window_hours(cs) == 12.0

    def test_posting_window_hours_midnight_crossing(self):
        """Midnight crossing: (24 - 22) + 2 = 4 hours."""
        cs = _make_chat_settings(posting_hours_start=22, posting_hours_end=2)

        assert SchedulerService._posting_window_hours(cs) == 4.0

    def test_posting_window_hours_full_day(self):
        """Full day window: 24 - 0 = 24 hours."""
        cs = _make_chat_settings(posting_hours_start=0, posting_hours_end=24)

        assert SchedulerService._posting_window_hours(cs) == 24.0


# ------------------------------------------------------------------
# _pick_category_for_slot
# ------------------------------------------------------------------


@pytest.mark.unit
class TestPickCategoryForSlot:
    """Tests for SchedulerService._pick_category_for_slot()."""

    def test_returns_none_when_no_ratios(self, scheduler_service_mocked):
        """Returns None when no category mix is configured."""
        service = scheduler_service_mocked
        service.category_mix_repo.get_current_mix_as_dict.return_value = {}

        assert service._pick_category_for_slot() is None

    def test_returns_category_with_ratios(self, scheduler_service_mocked):
        """Returns a valid category when ratios are configured."""
        service = scheduler_service_mocked
        service.category_mix_repo.get_current_mix_as_dict.return_value = {
            "memes": Decimal("0.7"),
            "merch": Decimal("0.3"),
        }

        result = service._pick_category_for_slot()

        assert result in ("memes", "merch")

    def test_single_category_always_returned(self, scheduler_service_mocked):
        """Single category at 100% is always returned."""
        service = scheduler_service_mocked
        service.category_mix_repo.get_current_mix_as_dict.return_value = {
            "memes": Decimal("1.0"),
        }

        for _ in range(10):
            assert service._pick_category_for_slot() == "memes"


# ------------------------------------------------------------------
# Category allocation (unchanged methods - kept from original tests)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestSchedulerCategoryAllocation:
    """Test suite for category-based slot allocation."""

    @pytest.fixture
    def scheduler_service(self):
        """Create SchedulerService with mocked dependencies."""
        with patch.object(SchedulerService, "__init__", lambda self: None):
            service = SchedulerService()
            service.media_repo = Mock()
            service.queue_repo = Mock()
            service.lock_repo = Mock()
            service.category_mix_repo = Mock()
            service.settings_service = Mock()
            service.service_run_repo = Mock()
            service.service_name = "SchedulerService"
            service.SCHEDULE_JITTER_MINUTES = 30
            service.track_execution = mock_track_execution
            service.set_result_summary = Mock()
            return service

    def test_allocate_slots_with_ratios(self, scheduler_service):
        """Test that slots are allocated according to category ratios."""
        scheduler_service.category_mix_repo.get_current_mix_as_dict.return_value = {
            "memes": Decimal("0.7"),
            "merch": Decimal("0.3"),
        }

        allocation = scheduler_service._allocate_slots_to_categories(10)

        assert len(allocation) == 10

        memes_count = allocation.count("memes")
        merch_count = allocation.count("merch")

        assert memes_count == 7
        assert merch_count == 3

    def test_allocate_slots_with_rounding(self, scheduler_service):
        """Test that slot allocation handles rounding correctly."""
        scheduler_service.category_mix_repo.get_current_mix_as_dict.return_value = {
            "memes": Decimal("0.7"),
            "merch": Decimal("0.3"),
        }

        allocation = scheduler_service._allocate_slots_to_categories(21)

        assert len(allocation) == 21

        memes_count = allocation.count("memes")
        merch_count = allocation.count("merch")

        assert memes_count + merch_count == 21
        assert memes_count >= 14 and memes_count <= 15
        assert merch_count >= 6 and merch_count <= 7

    def test_allocate_slots_no_ratios_configured(self, scheduler_service):
        """Test that empty list is returned when no ratios configured."""
        scheduler_service.category_mix_repo.get_current_mix_as_dict.return_value = {}

        allocation = scheduler_service._allocate_slots_to_categories(10)

        assert allocation == []

    def test_allocate_slots_single_category(self, scheduler_service):
        """Test allocation with single category at 100%."""
        scheduler_service.category_mix_repo.get_current_mix_as_dict.return_value = {
            "memes": Decimal("1.0"),
        }

        allocation = scheduler_service._allocate_slots_to_categories(10)

        assert len(allocation) == 10
        assert all(cat == "memes" for cat in allocation)

    def test_allocate_slots_three_categories(self, scheduler_service):
        """Test allocation with three categories."""
        scheduler_service.category_mix_repo.get_current_mix_as_dict.return_value = {
            "memes": Decimal("0.5"),
            "merch": Decimal("0.3"),
            "misc": Decimal("0.2"),
        }

        allocation = scheduler_service._allocate_slots_to_categories(10)

        assert len(allocation) == 10

        memes = allocation.count("memes")
        merch = allocation.count("merch")
        misc = allocation.count("misc")

        assert memes == 5
        assert merch == 3
        assert misc == 2

    def test_summarize_allocation(self, scheduler_service):
        """Test allocation summary string."""
        allocation = ["memes", "memes", "merch", "memes", "merch"]

        summary = scheduler_service._summarize_allocation(allocation)

        assert "memes: 3" in summary
        assert "merch: 2" in summary

    def test_select_media_with_category(self, scheduler_service):
        """Test that _select_media passes category to pool selection."""
        mock_media = Mock(category="memes", file_name="test.jpg")
        scheduler_service._select_media_from_pool = Mock(return_value=mock_media)

        result = scheduler_service._select_media(category="memes")

        scheduler_service._select_media_from_pool.assert_called_with(category="memes")
        assert result == mock_media

    def test_select_media_fallback_when_category_exhausted(self, scheduler_service):
        """Test fallback to any category when target is exhausted."""
        mock_media = Mock(category="merch", file_name="fallback.jpg")

        scheduler_service._select_media_from_pool = Mock(side_effect=[None, mock_media])

        result = scheduler_service._select_media(category="memes")

        assert scheduler_service._select_media_from_pool.call_count == 2
        calls = scheduler_service._select_media_from_pool.call_args_list
        assert calls[0][1]["category"] == "memes"
        assert calls[1][1]["category"] is None
        assert result == mock_media

    def test_select_media_no_fallback_when_no_category(self, scheduler_service):
        """Test that no fallback occurs when no category specified."""
        scheduler_service._select_media_from_pool = Mock(return_value=None)

        result = scheduler_service._select_media(category=None)

        scheduler_service._select_media_from_pool.assert_called_once_with(category=None)
        assert result is None


# ------------------------------------------------------------------
# Media pool (unchanged methods - kept from original tests)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestSchedulerMediaPool:
    """Tests for _select_media_from_pool method."""

    @pytest.fixture
    def scheduler_service(self):
        """Create SchedulerService with mocked dependencies."""
        with patch.object(SchedulerService, "__init__", lambda self: None):
            service = SchedulerService()
            service.media_repo = Mock()
            service.queue_repo = Mock()
            service.lock_repo = Mock()
            service.category_mix_repo = Mock()
            service.settings_service = Mock()
            service.service_run_repo = Mock()
            service.service_name = "SchedulerService"
            service.SCHEDULE_JITTER_MINUTES = 30
            return service

    def test_select_media_from_pool_delegates_to_repository(self, scheduler_service):
        """Test that _select_media_from_pool delegates to media_repo."""
        mock_media = Mock(category="memes", file_name="test.jpg")
        scheduler_service.media_repo.get_next_eligible_for_posting.return_value = (
            mock_media
        )

        result = scheduler_service._select_media_from_pool(category="memes")

        scheduler_service.media_repo.get_next_eligible_for_posting.assert_called_once_with(
            category="memes"
        )
        assert result == mock_media

    def test_select_media_from_pool_passes_none_category(self, scheduler_service):
        """Test that _select_media_from_pool passes None category correctly."""
        scheduler_service.media_repo.get_next_eligible_for_posting.return_value = None

        result = scheduler_service._select_media_from_pool(category=None)

        scheduler_service.media_repo.get_next_eligible_for_posting.assert_called_once_with(
            category=None
        )
        assert result is None
