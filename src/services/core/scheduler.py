"""Scheduler service - JIT posting schedule with per-slot media selection."""

from datetime import datetime
from typing import Optional, List, Union
import random

from src.exceptions.google_drive import GoogleDriveAuthError
from src.services.base_service import BaseService
from src.services.core.settings_service import SettingsService
from src.repositories.media_repository import MediaRepository
from src.repositories.queue_repository import QueueRepository
from src.repositories.lock_repository import LockRepository
from src.repositories.category_mix_repository import CategoryMixRepository
from src.config.settings import settings
from src.utils.logger import logger


class SchedulerService(BaseService):
    """Just-in-time posting scheduler.

    Instead of pre-populating the queue days in advance, computes whether
    a posting slot is due on each scheduler tick and selects media at that
    moment.  The posting_queue narrows to an "in-flight tracker" — items
    enter when selected and leave when the team acts (Posted/Skip/Reject).
    """

    SCHEDULE_JITTER_MINUTES = 30

    def __init__(self):
        super().__init__()
        self.media_repo = MediaRepository()
        self.queue_repo = QueueRepository()
        self.lock_repo = LockRepository()
        self.category_mix_repo = CategoryMixRepository()
        self.settings_service = SettingsService()
        # Injected by main.py after construction
        self.telegram_service = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_slot_due(self, chat_settings) -> Union[str, None, bool]:
        """Check whether a posting slot should fire now.

        Uses posts_per_day and the posting window to compute an even
        interval, then compares against last_post_sent_at.

        Returns:
            str  — target category name (slot is due, use this category)
            None — slot is due, no category preference
            False — slot is not due
        """
        now = datetime.utcnow()

        if not self._in_posting_window(now, chat_settings):
            return False

        window_hours = self._posting_window_hours(chat_settings)
        interval_seconds = (window_hours * 3600) / chat_settings.posts_per_day

        last_sent = chat_settings.last_post_sent_at
        if last_sent:
            # ORM now declares timezone=True; strip tzinfo for naive UTC comparison
            last_sent = (
                last_sent.replace(tzinfo=None) if last_sent.tzinfo else last_sent
            )
        if last_sent and (now - last_sent).total_seconds() < interval_seconds:
            return False  # Too soon

        # Pick category for this slot
        return self._pick_category_for_slot()

    async def process_slot(self, telegram_chat_id: int) -> dict:
        """Process a single scheduler tick for a tenant.

        This is the main entry point called by the scheduler loop every
        60 seconds.  No service_run is created for no-op ticks.

        Args:
            telegram_chat_id: Tenant to check

        Returns:
            Dict with keys: posted (bool), reason (str), and optionally
            queue_item_id, media_file, category.
        """
        chat_settings = self.settings_service.get_settings(telegram_chat_id)

        if chat_settings.is_paused:
            return {"posted": False, "reason": "paused"}

        slot_result = self.is_slot_due(chat_settings)
        if slot_result is False:
            return {"posted": False, "reason": "not_due"}

        category = slot_result if isinstance(slot_result, str) else None
        return await self._select_and_send(
            chat_settings,
            category=category,
            triggered_by="scheduler",
        )

    async def force_send_next(
        self,
        telegram_chat_id: int,
        user_id: Optional[str] = None,
        force_sent_indicator: bool = False,
    ) -> dict:
        """JIT select and send immediately.  Used by /next command.

        Differs from process_slot():
        - Ignores is_slot_due() — always fires
        - Updates last_post_sent_at to prevent immediate follow-up slot

        Args:
            telegram_chat_id: Tenant chat
            user_id: User who triggered (for observability)
            force_sent_indicator: If True, caption shows ⚡ indicator

        Returns:
            Dict with posted, queue_item_id, media_item, error keys
        """
        chat_settings = self.settings_service.get_settings(telegram_chat_id)
        return await self._select_and_send(
            chat_settings,
            category=None,
            triggered_by="telegram",
            user_id=user_id,
            force_sent_indicator=force_sent_indicator,
        )

    def get_queue_preview(
        self,
        telegram_chat_id: int,
        count: int = 5,
    ) -> list:
        """Compute the next N selections without persisting.

        Runs _select_media() with a simulated exclusion set so the caller
        can see what would be posted next.

        Returns:
            List of dicts with media_id, file_name, category.
        """
        previews = []
        seen_ids = set()

        for _ in range(count):
            media_item = self._select_media(category=None)
            if not media_item or str(media_item.id) in seen_ids:
                break
            seen_ids.add(str(media_item.id))
            previews.append(
                {
                    "media_id": str(media_item.id),
                    "file_name": media_item.file_name,
                    "category": media_item.category,
                }
            )

        return previews

    # ------------------------------------------------------------------
    # Queue management (kept from old scheduler)
    # ------------------------------------------------------------------

    def _resolve_chat_settings_id(
        self, telegram_chat_id: Optional[int] = None
    ) -> Optional[str]:
        """Derive chat_settings_id from telegram_chat_id."""
        if telegram_chat_id is None:
            telegram_chat_id = settings.ADMIN_TELEGRAM_CHAT_ID
        chat_settings = self.settings_service.get_settings(telegram_chat_id)
        return str(chat_settings.id) if chat_settings else None

    def clear_pending_queue(self, telegram_chat_id: Optional[int] = None) -> int:
        """Delete all pending queue items for a chat."""
        chat_settings_id = self._resolve_chat_settings_id(telegram_chat_id)
        return self.queue_repo.delete_all_pending(chat_settings_id=chat_settings_id)

    def count_pending(self, telegram_chat_id: Optional[int] = None) -> int:
        """Count pending queue items for a chat."""
        chat_settings_id = self._resolve_chat_settings_id(telegram_chat_id)
        return self.queue_repo.count_pending(chat_settings_id=chat_settings_id)

    def check_availability(self, media_id: str) -> bool:
        """Check if media item is available for scheduling."""
        if self.lock_repo.is_locked(media_id):
            return False
        if self.queue_repo.get_by_media_id(media_id):
            return False
        return True

    # ------------------------------------------------------------------
    # Internal: JIT core
    # ------------------------------------------------------------------

    async def _select_and_send(
        self,
        chat_settings,
        *,
        category: Optional[str],
        triggered_by: str,
        user_id: Optional[str] = None,
        force_sent_indicator: bool = False,
    ) -> dict:
        """Core JIT flow: select media → create queue item → send.

        Only creates a service_run when there is actual work to do.
        """
        with self.track_execution(
            method_name="select_and_send",
            user_id=user_id,
            triggered_by=triggered_by,
        ) as run_id:
            media_item = self._select_media(category=category)
            if not media_item:
                result = {
                    "posted": False,
                    "reason": "no_eligible_media",
                    "queue_item_id": None,
                    "media_item": None,
                    "error": "No eligible media available",
                }
                self.set_result_summary(
                    run_id, {k: v for k, v in result.items() if k != "media_item"}
                )
                return result

            # Create in-flight queue item
            queue_item = self.queue_repo.create(
                media_item_id=str(media_item.id),
                scheduled_for=datetime.utcnow(),
                chat_settings_id=str(chat_settings.id),
            )

            # Send to Telegram
            success = await self._send_to_telegram(
                queue_item, force_sent=force_sent_indicator
            )

            if success:
                self.settings_service.update_last_post_sent_at(
                    chat_settings.telegram_chat_id, datetime.utcnow()
                )

            result = {
                "posted": success,
                "queue_item_id": str(queue_item.id),
                "media_item": media_item,
                "media_file": media_item.file_name,
                "category": media_item.category,
                "error": None if success else "Failed to send Telegram notification",
            }
            self.set_result_summary(
                run_id,
                {
                    "posted": success,
                    "queue_item_id": str(queue_item.id),
                    "media_file": media_item.file_name,
                    "category": media_item.category,
                },
            )
            return result

    async def _send_to_telegram(self, queue_item, force_sent: bool = False) -> bool:
        """Claim queue item and send to Telegram.

        Claims (status → processing) BEFORE sending to prevent duplicate
        sends if the scheduler fires again before Telegram responds.
        Rolls back to pending on failure.
        """
        queue_item_id = str(queue_item.id)
        try:
            self.queue_repo.update_status(queue_item_id, "processing")
            success = await self.telegram_service.send_notification(
                queue_item_id, force_sent=force_sent
            )
            if not success:
                logger.error(
                    f"Failed to send Telegram notification for {queue_item_id}"
                )
                self.queue_repo.update_status(queue_item_id, "pending")
            else:
                logger.info(f"Sent Telegram notification for {queue_item_id}")
            return success

        except GoogleDriveAuthError:
            logger.error(
                f"Google Drive auth error for {queue_item_id} — rolling back to pending"
            )
            try:
                self.queue_repo.update_status(queue_item_id, "pending")
            except Exception:
                pass
            raise

        except Exception as e:
            logger.error(f"Error sending to Telegram: {e}")
            try:
                self.queue_repo.update_status(queue_item_id, "pending")
            except Exception:
                pass
            return False

    # ------------------------------------------------------------------
    # Internal: slot timing
    # ------------------------------------------------------------------

    @staticmethod
    def _in_posting_window(now: datetime, chat_settings) -> bool:
        """Check if current time is within the posting window."""
        current_hour = now.hour + now.minute / 60.0
        start = chat_settings.posting_hours_start
        end = chat_settings.posting_hours_end

        if end < start:
            # Window crosses midnight (e.g., 22-2)
            return current_hour >= start or current_hour < end
        else:
            return start <= current_hour < end

    @staticmethod
    def _posting_window_hours(chat_settings) -> float:
        """Compute the length of the posting window in hours."""
        start = chat_settings.posting_hours_start
        end = chat_settings.posting_hours_end
        if end < start:
            return (24 - start) + end
        return end - start

    # ------------------------------------------------------------------
    # Internal: category selection
    # ------------------------------------------------------------------

    def _pick_category_for_slot(self) -> Optional[str]:
        """Pick a single category for this slot using configured ratios.

        Uses weighted random selection so that over many slots the
        distribution matches the configured mix.

        Returns:
            Category name, or None if no ratios configured.
        """
        current_mix = self.category_mix_repo.get_current_mix_as_dict()
        if not current_mix:
            return None

        categories = list(current_mix.keys())
        weights = [float(r) for r in current_mix.values()]
        return random.choices(categories, weights=weights, k=1)[0]

    def _allocate_slots_to_categories(self, total_slots: int) -> List[Optional[str]]:
        """Allocate slots to categories based on configured ratios.

        Kept for queue_preview and backwards compatibility.
        """
        current_mix = self.category_mix_repo.get_current_mix_as_dict()

        if not current_mix:
            return []

        slot_allocation = []
        remaining_slots = total_slots

        sorted_categories = sorted(
            current_mix.items(), key=lambda x: x[1], reverse=True
        )

        for i, (category, ratio) in enumerate(sorted_categories):
            if i == len(sorted_categories) - 1:
                slots_for_category = remaining_slots
            else:
                slots_for_category = round(float(ratio) * total_slots)
                remaining_slots -= slots_for_category

            slot_allocation.extend([category] * slots_for_category)

        random.shuffle(slot_allocation)
        return slot_allocation

    def _summarize_allocation(self, slot_categories: List[str]) -> str:
        """Summarize slot allocation for logging."""
        summary = {}
        for cat in slot_categories:
            summary[cat] = summary.get(cat, 0) + 1
        return ", ".join(f"{cat}: {count}" for cat, count in sorted(summary.items()))

    # ------------------------------------------------------------------
    # Internal: media selection (unchanged)
    # ------------------------------------------------------------------

    def _select_media(self, category: Optional[str] = None):
        """Select next media item to post.

        Selection priority:
        1. Filter by category (if specified)
        2. Never posted items first (last_posted_at IS NULL)
        3. Least posted items (times_posted ASC)
        4. Random from eligible items (variety)

        Falls back to any category if target category is exhausted.
        """
        media_item = self._select_media_from_pool(category=category)

        if not media_item and category:
            logger.warning(
                f"Category '{category}' exhausted, falling back to any available media"
            )
            media_item = self._select_media_from_pool(category=None)

        return media_item

    def _select_media_from_pool(self, category: Optional[str] = None):
        """Select media from a specific pool (category or all).

        Delegates to MediaRepository.get_next_eligible_for_posting().
        """
        return self.media_repo.get_next_eligible_for_posting(category=category)
