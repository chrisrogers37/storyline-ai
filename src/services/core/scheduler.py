"""Scheduler service - create and manage posting schedule."""

from datetime import datetime, timedelta
from typing import Optional, List
import random

from src.services.base_service import BaseService
from src.services.core.settings_service import SettingsService
from src.repositories.media_repository import MediaRepository
from src.repositories.queue_repository import QueueRepository
from src.repositories.lock_repository import LockRepository
from src.repositories.category_mix_repository import CategoryMixRepository
from src.config.settings import settings
from src.utils.logger import logger


class SchedulerService(BaseService):
    """Create and manage posting schedule."""

    SCHEDULE_JITTER_MINUTES = 30

    def __init__(self):
        super().__init__()
        self.media_repo = MediaRepository()
        self.queue_repo = QueueRepository()
        self.lock_repo = LockRepository()
        self.category_mix_repo = CategoryMixRepository()
        self.settings_service = SettingsService()

    def create_schedule(
        self,
        days: int = 7,
        user_id: Optional[str] = None,
        telegram_chat_id: Optional[int] = None,
    ) -> dict:
        """
        Generate posting schedule for the next N days.

        Uses category ratios to allocate slots across categories.
        For example, with 70% memes / 30% merch and 21 total slots:
        - ~15 slots allocated to memes
        - ~6 slots allocated to merch

        Args:
            days: Number of days to schedule
            user_id: User who triggered scheduling

        Returns:
            Dict with results: {scheduled: 21, skipped: 5, category_breakdown: {...}}
        """
        with self.track_execution(
            method_name="create_schedule",
            user_id=user_id,
            triggered_by="cli" if user_id else "system",
            input_params={"days": days},
        ) as run_id:
            scheduled_count = 0
            skipped_count = 0
            error_message = None
            category_breakdown = {}

            try:
                # Generate time slots
                time_slots = self._generate_time_slots(
                    days, telegram_chat_id=telegram_chat_id
                )
                total_slots = len(time_slots)

                logger.info(
                    f"Generating schedule for {days} days ({total_slots} slots)"
                )

                # Allocate slots to categories based on ratios
                slot_categories = self._allocate_slots_to_categories(total_slots)

                if slot_categories:
                    logger.info(
                        f"Category allocation: {self._summarize_allocation(slot_categories)}"
                    )

                scheduled_count, skipped_count, category_breakdown = (
                    self._fill_schedule_slots(time_slots, slot_categories)
                )

            except Exception as e:
                error_message = str(e)
                logger.error(f"Error during scheduling: {e}")

            result = {
                "scheduled": scheduled_count,
                "skipped": skipped_count,
                "total_slots": len(time_slots),
                "category_breakdown": category_breakdown,
            }

            if error_message:
                result["error"] = error_message

            self.set_result_summary(run_id, result)

            return result

    def extend_schedule(
        self,
        days: int = 7,
        user_id: Optional[str] = None,
        telegram_chat_id: Optional[int] = None,
    ) -> dict:
        """
        Extend existing schedule by adding more days.

        Unlike create_schedule(), this preserves existing queue items
        and appends new slots starting after the last scheduled time.

        Args:
            days: Number of days to add
            user_id: User who triggered extension

        Returns:
            Dict with results: {scheduled: N, skipped: M, extended_from: datetime, ...}
        """
        with self.track_execution(
            method_name="extend_schedule",
            user_id=user_id,
            triggered_by="telegram" if user_id else "system",
            input_params={"days": days},
        ) as run_id:
            scheduled_count = 0
            skipped_count = 0
            error_message = None
            category_breakdown = {}

            try:
                # Find the last scheduled time in the queue
                all_pending = self.queue_repo.get_all(status="pending")

                if all_pending:
                    # Find the latest scheduled_for time
                    last_scheduled = max(item.scheduled_for for item in all_pending)
                    # Start from the day after the last scheduled item
                    start_date = last_scheduled.date() + timedelta(days=1)
                else:
                    # No existing queue - start from today
                    start_date = datetime.utcnow().date()
                    last_scheduled = None

                logger.info(f"Extending schedule from {start_date} for {days} days")

                # Generate time slots starting from start_date
                time_slots = self._generate_time_slots_from_date(
                    start_date, days, telegram_chat_id=telegram_chat_id
                )
                total_slots = len(time_slots)

                logger.info(f"Generated {total_slots} new time slots")

                # Allocate slots to categories based on ratios
                slot_categories = self._allocate_slots_to_categories(total_slots)

                if slot_categories:
                    logger.info(
                        f"Category allocation: {self._summarize_allocation(slot_categories)}"
                    )

                scheduled_count, skipped_count, category_breakdown = (
                    self._fill_schedule_slots(time_slots, slot_categories)
                )

            except Exception as e:
                error_message = str(e)
                logger.error(f"Error during schedule extension: {e}")

            result = {
                "scheduled": scheduled_count,
                "skipped": skipped_count,
                "total_slots": total_slots if "total_slots" in dir() else 0,
                "extended_from": last_scheduled.isoformat() if last_scheduled else None,
                "category_breakdown": category_breakdown,
            }

            if error_message:
                result["error"] = error_message

            self.set_result_summary(run_id, result)

            return result

    def _fill_schedule_slots(
        self,
        time_slots: list[datetime],
        slot_categories: List[Optional[str]],
    ) -> tuple[int, int, dict]:
        """
        Fill time slots with media items and add to queue.

        Args:
            time_slots: List of scheduled times to fill
            slot_categories: Category assignment per slot (empty list = no category filtering)

        Returns:
            Tuple of (scheduled_count, skipped_count, category_breakdown)
        """
        scheduled_count = 0
        skipped_count = 0
        category_breakdown = {}

        for i, scheduled_time in enumerate(time_slots):
            target_category = slot_categories[i] if slot_categories else None

            media_item = self._select_media(category=target_category)

            if not media_item:
                logger.warning(f"No eligible media found for slot {scheduled_time}")
                skipped_count += 1
                continue

            self.queue_repo.create(
                media_item_id=str(media_item.id), scheduled_for=scheduled_time
            )

            item_category = media_item.category or "uncategorized"
            category_breakdown[item_category] = (
                category_breakdown.get(item_category, 0) + 1
            )

            logger.info(
                f"Scheduled {media_item.file_name} [{item_category}] for {scheduled_time}"
            )
            scheduled_count += 1

        return scheduled_count, skipped_count, category_breakdown

    def _generate_time_slots_from_date(
        self, start_date, days: int, telegram_chat_id: Optional[int] = None
    ) -> list[datetime]:
        """
        Generate time slots starting from a specific date.

        Args:
            start_date: Date to start generating slots from
            days: Number of days to generate
            telegram_chat_id: Chat to get schedule settings for.
                Falls back to ADMIN_TELEGRAM_CHAT_ID if not specified.

        Returns:
            List of datetime objects for posting
        """
        # Get schedule settings from database
        if telegram_chat_id is None:
            telegram_chat_id = settings.ADMIN_TELEGRAM_CHAT_ID
        chat_settings = self.settings_service.get_settings(telegram_chat_id)

        time_slots = []
        posts_per_day = chat_settings.posts_per_day
        start_hour = chat_settings.posting_hours_start
        end_hour = chat_settings.posting_hours_end

        for day_offset in range(days):
            base_date = start_date + timedelta(days=day_offset)

            # Handle wrap-around posting hours (e.g., 22-2 means 22:00 to 02:00 next day)
            if end_hour < start_hour:
                posting_window_hours = (24 - start_hour) + end_hour
            else:
                posting_window_hours = end_hour - start_hour

            interval_hours = posting_window_hours / posts_per_day

            for post_num in range(posts_per_day):
                hour_offset = start_hour + (post_num * interval_hours)

                post_date = base_date
                if hour_offset >= 24:
                    hour_offset -= 24
                    post_date = base_date + timedelta(days=1)

                # Add jitter
                jitter_minutes = random.randint(
                    -self.SCHEDULE_JITTER_MINUTES, self.SCHEDULE_JITTER_MINUTES
                )

                scheduled_time = datetime.combine(
                    post_date, datetime.min.time()
                ) + timedelta(hours=hour_offset, minutes=jitter_minutes)

                # Only add future times
                if scheduled_time > datetime.utcnow():
                    time_slots.append(scheduled_time)

        return sorted(time_slots)

    def _allocate_slots_to_categories(self, total_slots: int) -> List[Optional[str]]:
        """
        Allocate slots to categories based on configured ratios.

        Args:
            total_slots: Total number of slots to allocate

        Returns:
            List of category names (shuffled), or empty list if no ratios configured
        """
        current_mix = self.category_mix_repo.get_current_mix_as_dict()

        if not current_mix:
            logger.info("No category mix configured, using default selection")
            return []

        # Calculate slots per category
        slot_allocation = []
        remaining_slots = total_slots

        # Sort categories by ratio descending to handle rounding better
        sorted_categories = sorted(
            current_mix.items(), key=lambda x: x[1], reverse=True
        )

        for i, (category, ratio) in enumerate(sorted_categories):
            if i == len(sorted_categories) - 1:
                # Last category gets all remaining slots (handles rounding)
                slots_for_category = remaining_slots
            else:
                slots_for_category = round(float(ratio) * total_slots)
                remaining_slots -= slots_for_category

            slot_allocation.extend([category] * slots_for_category)

        # Shuffle for variety (so it's not all memes first, then all merch)
        random.shuffle(slot_allocation)

        return slot_allocation

    def _summarize_allocation(self, slot_categories: List[str]) -> str:
        """Summarize slot allocation for logging."""
        summary = {}
        for cat in slot_categories:
            summary[cat] = summary.get(cat, 0) + 1
        return ", ".join(f"{cat}: {count}" for cat, count in sorted(summary.items()))

    def _generate_time_slots(
        self, days: int, telegram_chat_id: Optional[int] = None
    ) -> list[datetime]:
        """
        Generate evenly distributed time slots within posting windows.

        Args:
            days: Number of days to generate slots for
            telegram_chat_id: Chat to get schedule settings for.
                Falls back to ADMIN_TELEGRAM_CHAT_ID if not specified.

        Returns:
            List of datetime objects for posting
        """
        # Get schedule settings from database (falls back to .env if not in DB)
        if telegram_chat_id is None:
            telegram_chat_id = settings.ADMIN_TELEGRAM_CHAT_ID
        chat_settings = self.settings_service.get_settings(telegram_chat_id)

        time_slots = []
        posts_per_day = chat_settings.posts_per_day
        start_hour = chat_settings.posting_hours_start
        end_hour = chat_settings.posting_hours_end

        for day_offset in range(days):
            base_date = datetime.utcnow().date() + timedelta(days=day_offset)

            # Handle wrap-around posting hours (e.g., 22-2 means 22:00 to 02:00 next day)
            if end_hour < start_hour:
                # Posting window crosses midnight
                posting_window_hours = (24 - start_hour) + end_hour
            else:
                posting_window_hours = end_hour - start_hour

            interval_hours = posting_window_hours / posts_per_day

            for post_num in range(posts_per_day):
                # Calculate base time
                hour_offset = start_hour + (post_num * interval_hours)

                # Handle wrap-around (use local variable to avoid mutation)
                post_date = base_date
                if hour_offset >= 24:
                    hour_offset -= 24
                    post_date = base_date + timedelta(days=1)

                # Add jitter for unpredictability (configurable via SCHEDULE_JITTER_MINUTES)
                jitter_minutes = random.randint(
                    -self.SCHEDULE_JITTER_MINUTES, self.SCHEDULE_JITTER_MINUTES
                )

                scheduled_time = datetime.combine(
                    post_date, datetime.min.time()
                ) + timedelta(hours=hour_offset, minutes=jitter_minutes)

                # Ensure we don't schedule in the past
                if scheduled_time > datetime.utcnow():
                    time_slots.append(scheduled_time)

        return sorted(time_slots)

    def _select_media(self, category: Optional[str] = None):
        """
        Select next media item to post using intelligent selection logic.

        Selection priority:
        1. Filter by category (if specified)
        2. Never posted items first (last_posted_at IS NULL)
        3. Least posted items (times_posted ASC)
        4. Random from eligible items (variety)

        If category is specified but exhausted, falls back to any available media.

        Args:
            category: Target category to select from (optional)

        Returns:
            MediaItem or None if no eligible media
        """
        # Try to select from target category first
        media_item = self._select_media_from_pool(category=category)

        # Fallback to any category if target category is exhausted
        if not media_item and category:
            logger.warning(
                f"Category '{category}' exhausted, falling back to any available media"
            )
            media_item = self._select_media_from_pool(category=None)

        return media_item

    def _select_media_from_pool(self, category: Optional[str] = None):
        """
        Select media from a specific pool (category or all).

        Delegates to MediaRepository.get_next_eligible_for_posting() which handles
        filtering out locked, queued, and inactive items with proper priority sorting.

        Args:
            category: Filter by category, or None for all

        Returns:
            MediaItem or None
        """
        return self.media_repo.get_next_eligible_for_posting(category=category)

    def check_availability(self, media_id: str) -> bool:
        """
        Check if media item is available for scheduling.

        Args:
            media_id: Media item ID

        Returns:
            True if available for scheduling
        """
        # Check if locked
        if self.lock_repo.is_locked(media_id):
            return False

        # Check if already queued
        if self.queue_repo.get_by_media_id(media_id):
            return False

        return True
