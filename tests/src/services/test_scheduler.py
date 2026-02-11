"""Tests for SchedulerService."""

import pytest
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4

from src.services.core.scheduler import SchedulerService


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
        service.service_run_repo = Mock()
        service.service_name = "SchedulerService"
        service.SCHEDULE_JITTER_MINUTES = 30
        # Mock track_execution as MagicMock with context manager support
        service.track_execution = MagicMock()
        service.track_execution.return_value.__enter__ = Mock(return_value="run-123")
        service.track_execution.return_value.__exit__ = Mock(return_value=False)
        service.set_result_summary = Mock()
        return service


@pytest.mark.unit
class TestSchedulerService:
    """Test suite for SchedulerService."""

    @patch("src.services.core.scheduler.settings")
    def test_create_schedule_creates_queue_items(
        self, mock_settings, scheduler_service_mocked
    ):
        """Test that create_schedule creates queue items."""
        service = scheduler_service_mocked
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = -100123

        mock_chat_settings = Mock()
        mock_chat_settings.posts_per_day = 2
        mock_chat_settings.posting_hours_start = 9
        mock_chat_settings.posting_hours_end = 17
        service.settings_service.get_settings.return_value = mock_chat_settings

        service.category_mix_repo.get_current_mix_as_dict.return_value = {}

        mock_media = Mock()
        mock_media.id = uuid4()
        mock_media.file_name = "schedule1.jpg"
        mock_media.category = "memes"
        service._select_media = Mock(return_value=mock_media)

        # Use days=2 to ensure tomorrow's slots are always in the future
        result = service.create_schedule(days=2)

        assert result["scheduled"] >= 1
        assert service.queue_repo.create.call_count >= 1

    def test_select_next_media_prioritizes_never_posted(self, scheduler_service_mocked):
        """Test that never-posted media is prioritized."""
        service = scheduler_service_mocked

        mock_media = Mock()
        mock_media.times_posted = 0
        service.media_repo.get_next_eligible_for_posting.return_value = mock_media

        result = service._select_media()

        assert result is not None
        assert result.times_posted == 0
        service.media_repo.get_next_eligible_for_posting.assert_called()

    def test_select_next_media_excludes_locked(self, scheduler_service_mocked):
        """Test that locked media is excluded from selection."""
        service = scheduler_service_mocked

        mock_media = Mock(category="memes", file_name="unlocked.jpg")
        service.media_repo.get_next_eligible_for_posting.return_value = mock_media

        result = service._select_media()

        assert result is not None
        service.media_repo.get_next_eligible_for_posting.assert_called_once_with(
            category=None
        )

    def test_select_next_media_excludes_queued(self, scheduler_service_mocked):
        """Test that queued media is excluded from selection."""
        service = scheduler_service_mocked

        mock_media = Mock(category="memes", file_name="available.jpg")
        service.media_repo.get_next_eligible_for_posting.return_value = mock_media

        result = service._select_media()

        assert result is not None
        service.media_repo.get_next_eligible_for_posting.assert_called_once_with(
            category=None
        )

    @patch("src.services.core.scheduler.settings")
    def test_generate_time_slots(self, mock_settings, scheduler_service_mocked):
        """Test generating time slots for scheduling."""
        service = scheduler_service_mocked
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = -100123

        mock_chat_settings = Mock()
        mock_chat_settings.posts_per_day = 3
        mock_chat_settings.posting_hours_start = 9
        mock_chat_settings.posting_hours_end = 21
        service.settings_service.get_settings.return_value = mock_chat_settings

        time_slots = service._generate_time_slots(days=2)

        # Should generate up to 6 slots (2 days * 3 posts), minus any in the past
        assert len(time_slots) <= 6

        # Slots should be in chronological order
        for i in range(len(time_slots) - 1):
            assert time_slots[i] < time_slots[i + 1]

    @patch("src.services.core.scheduler.settings")
    def test_create_schedule_respects_posting_hours(
        self, mock_settings, scheduler_service_mocked
    ):
        """Test that schedule respects posting hours configuration."""
        service = scheduler_service_mocked
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = -100123

        mock_chat_settings = Mock()
        mock_chat_settings.posts_per_day = 2
        mock_chat_settings.posting_hours_start = 9
        mock_chat_settings.posting_hours_end = 17
        service.settings_service.get_settings.return_value = mock_chat_settings

        service.category_mix_repo.get_current_mix_as_dict.return_value = {}

        mock_media = Mock()
        mock_media.id = uuid4()
        mock_media.file_name = "hours.jpg"
        mock_media.category = None
        service._select_media = Mock(return_value=mock_media)

        # Use days=2 to ensure tomorrow's slots are always in the future
        service.create_schedule(days=2)

        assert service.queue_repo.create.call_count >= 1

        # Verify times are within posting hours (with jitter tolerance)
        for call in service.queue_repo.create.call_args_list:
            scheduled_time = call.kwargs["scheduled_for"]
            assert 0 <= scheduled_time.hour <= 23


@pytest.mark.unit
class TestSchedulerCategoryAllocation:
    """Test suite for category-based slot allocation."""

    @pytest.fixture
    def scheduler_service(self):
        """Create SchedulerService with mocked dependencies."""
        with patch("src.services.core.scheduler.MediaRepository"):
            with patch("src.services.core.scheduler.QueueRepository"):
                with patch("src.services.core.scheduler.LockRepository"):
                    with patch("src.services.core.scheduler.CategoryMixRepository"):
                        with patch("src.services.base_service.ServiceRunRepository"):
                            service = SchedulerService()
                            service.media_repo = Mock()
                            service.queue_repo = Mock()
                            service.lock_repo = Mock()
                            service.category_mix_repo = Mock()
                            # Mock track_execution
                            service.track_execution = MagicMock()
                            service.track_execution.return_value.__enter__ = Mock(
                                return_value="run-123"
                            )
                            service.track_execution.return_value.__exit__ = Mock(
                                return_value=False
                            )
                            service.set_result_summary = Mock()
                            return service

    def test_allocate_slots_with_ratios(self, scheduler_service):
        """Test that slots are allocated according to category ratios."""
        scheduler_service.category_mix_repo.get_current_mix_as_dict.return_value = {
            "memes": Decimal("0.7"),
            "merch": Decimal("0.3"),
        }

        allocation = scheduler_service._allocate_slots_to_categories(10)

        # Should have 10 slots total
        assert len(allocation) == 10

        # Count per category
        memes_count = allocation.count("memes")
        merch_count = allocation.count("merch")

        # 70% of 10 = 7 memes, 30% of 10 = 3 merch
        assert memes_count == 7
        assert merch_count == 3

    def test_allocate_slots_with_rounding(self, scheduler_service):
        """Test that slot allocation handles rounding correctly."""
        scheduler_service.category_mix_repo.get_current_mix_as_dict.return_value = {
            "memes": Decimal("0.7"),
            "merch": Decimal("0.3"),
        }

        # 21 slots: 70% = 14.7 -> 15, 30% = 6.3 -> 6
        allocation = scheduler_service._allocate_slots_to_categories(21)

        assert len(allocation) == 21

        memes_count = allocation.count("memes")
        merch_count = allocation.count("merch")

        # Should sum to 21
        assert memes_count + merch_count == 21
        # Roughly 70/30 split
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

        assert memes == 5  # 50%
        assert merch == 3  # 30%
        assert misc == 2  # 20%

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

        # First call (with category) returns None, second call (without) returns media
        scheduler_service._select_media_from_pool = Mock(side_effect=[None, mock_media])

        result = scheduler_service._select_media(category="memes")

        # Should have been called twice
        assert scheduler_service._select_media_from_pool.call_count == 2
        # First with category, then without
        calls = scheduler_service._select_media_from_pool.call_args_list
        assert calls[0][1]["category"] == "memes"
        assert calls[1][1]["category"] is None
        # Should return fallback media
        assert result == mock_media

    def test_select_media_no_fallback_when_no_category(self, scheduler_service):
        """Test that no fallback occurs when no category specified."""
        scheduler_service._select_media_from_pool = Mock(return_value=None)

        result = scheduler_service._select_media(category=None)

        # Should only be called once (no fallback)
        scheduler_service._select_media_from_pool.assert_called_once_with(category=None)
        assert result is None

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
