"""Scheduler service - create and manage posting schedule."""
from datetime import datetime, timedelta
from typing import Optional
import random

from src.services.base_service import BaseService
from src.repositories.media_repository import MediaRepository
from src.repositories.queue_repository import QueueRepository
from src.repositories.lock_repository import LockRepository
from src.config.settings import settings
from src.utils.logger import logger


class SchedulerService(BaseService):
    """Create and manage posting schedule."""

    def __init__(self):
        super().__init__()
        self.media_repo = MediaRepository()
        self.queue_repo = QueueRepository()
        self.lock_repo = LockRepository()

    def create_schedule(self, days: int = 7, user_id: Optional[str] = None) -> dict:
        """
        Generate posting schedule for the next N days.

        Args:
            days: Number of days to schedule
            user_id: User who triggered scheduling

        Returns:
            Dict with results: {scheduled: 21, skipped: 5, error: "..."}
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

            try:
                # Calculate total posts needed
                total_posts = days * settings.POSTS_PER_DAY

                # Generate time slots
                time_slots = self._generate_time_slots(days)

                logger.info(f"Generating schedule for {days} days ({total_posts} posts)")

                for scheduled_time in time_slots:
                    # Select media for this slot
                    media_item = self._select_media()

                    if not media_item:
                        logger.warning(f"No eligible media found for slot {scheduled_time}")
                        skipped_count += 1
                        continue

                    # Add to queue
                    self.queue_repo.create(media_item_id=str(media_item.id), scheduled_for=scheduled_time)

                    logger.info(f"Scheduled {media_item.file_name} for {scheduled_time}")
                    scheduled_count += 1

            except Exception as e:
                error_message = str(e)
                logger.error(f"Error during scheduling: {e}")

            result = {"scheduled": scheduled_count, "skipped": skipped_count, "total_slots": len(time_slots)}

            if error_message:
                result["error"] = error_message

            self.set_result_summary(run_id, result)

            return result

    def _generate_time_slots(self, days: int) -> list[datetime]:
        """
        Generate evenly distributed time slots within posting windows.

        Returns:
            List of datetime objects for posting
        """
        time_slots = []
        posts_per_day = settings.POSTS_PER_DAY
        start_hour = settings.POSTING_HOURS_START
        end_hour = settings.POSTING_HOURS_END

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

                # Add ±30min jitter for unpredictability
                jitter_minutes = random.randint(-30, 30)

                scheduled_time = datetime.combine(post_date, datetime.min.time()) + timedelta(
                    hours=hour_offset, minutes=jitter_minutes
                )

                # Ensure we don't schedule in the past
                if scheduled_time > datetime.utcnow():
                    time_slots.append(scheduled_time)

        return sorted(time_slots)

    def _select_media(self):
        """
        Select next media item to post using intelligent selection logic.

        Selection priority:
        1. Never posted items first (last_posted_at IS NULL)
        2. Least posted items (times_posted ASC)
        3. Random from eligible items (variety)

        Returns:
            MediaItem or None if no eligible media
        """
        # Get all active media not currently queued or locked
        from sqlalchemy import and_, exists, select
        from src.models.media_item import MediaItem
        from src.models.posting_queue import PostingQueue
        from src.models.media_lock import MediaPostingLock

        query = self.media_repo.db.query(MediaItem).filter(MediaItem.is_active == True)

        # Exclude already queued items
        queued_subquery = exists(select(PostingQueue.id).where(PostingQueue.media_item_id == MediaItem.id))
        query = query.filter(~queued_subquery)

        # Exclude locked items (both permanent and TTL locks)
        now = datetime.utcnow()
        locked_subquery = exists(
            select(MediaPostingLock.id).where(
                and_(
                    MediaPostingLock.media_item_id == MediaItem.id,
                    # Lock is active if: locked_until is NULL (permanent) OR locked_until > now (TTL not expired)
                    (MediaPostingLock.locked_until.is_(None)) | (MediaPostingLock.locked_until > now)
                )
            )
        )
        query = query.filter(~locked_subquery)

        # Sort by priority:
        # 1. Never posted first (NULLS FIRST)
        # 2. Then least posted
        # 3. Then random
        query = query.order_by(MediaItem.last_posted_at.asc().nullsfirst(), MediaItem.times_posted.asc())

        # Get top candidates
        candidates = query.limit(10).all()

        if not candidates:
            return None

        # Random selection from top candidates for variety
        return random.choice(candidates)

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
