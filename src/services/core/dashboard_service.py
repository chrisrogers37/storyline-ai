"""Dashboard service - thin facade delegating to focused query classes."""

from typing import Optional

from src.services.base_service import BaseService
from src.services.core.settings_service import SettingsService
from src.repositories.history_repository import HistoryRepository
from src.repositories.media_repository import MediaRepository
from src.repositories.queue_repository import QueueRepository
from src.repositories.category_mix_repository import CategoryMixRepository
from src.repositories.membership_repository import MembershipRepository
from src.repositories.user_repository import UserRepository
from src.services.core.dashboard_queue_queries import QueueDashboardQueries
from src.services.core.dashboard_media_queries import MediaDashboardQueries
from src.services.core.dashboard_history_queries import HistoryDashboardQueries
from src.services.core.dashboard_instance_queries import InstanceDashboardQueries


class DashboardService(BaseService):
    """Read-only aggregation queries for dashboard endpoints.

    Thin facade that delegates to focused query classes while keeping
    the API layer free of direct repository imports.  Each query class
    groups methods by dashboard section (queue, media, history, instance).
    """

    MIN_RECOMMENDATION_DATA_POINTS = 10

    def __init__(self):
        super().__init__()
        self.settings_service = SettingsService()
        self.queue_repo = QueueRepository()
        self.history_repo = HistoryRepository()
        self.media_repo = MediaRepository()
        self.category_mix_repo = CategoryMixRepository()
        self.membership_repo = MembershipRepository()
        self.user_repo = UserRepository()

        # Extracted query classes
        self.queue_queries = QueueDashboardQueries(self)
        self.media_queries = MediaDashboardQueries(self)
        self.history_queries = HistoryDashboardQueries(self)
        self.instance_queries = InstanceDashboardQueries(self)

    def resolve_chat_settings_id(self, telegram_chat_id: int) -> str:
        chat_settings = self.settings_service.get_settings(telegram_chat_id)
        return str(chat_settings.id)

    # -- Queue delegates --

    def get_queue_detail(self, telegram_chat_id: int, limit: int = 10) -> dict:

        return self.queue_queries.get_queue_detail(telegram_chat_id, limit)

    def get_pending_queue_items(self, chat_settings_id: Optional[str] = None) -> list:

        return self.queue_queries.get_pending_queue_items(chat_settings_id)

    # -- Media delegates --

    def get_media_library(
        self,
        telegram_chat_id: int,
        page: int = 1,
        page_size: int = 20,
        category: Optional[str] = None,
        posting_status: Optional[str] = None,
    ) -> dict:

        return self.media_queries.get_media_library(
            telegram_chat_id, page, page_size, category, posting_status
        )

    def get_media_stats(self, telegram_chat_id: int) -> dict:

        return self.media_queries.get_media_stats(telegram_chat_id)

    def get_category_analytics(self, telegram_chat_id: int, days: int = 30) -> dict:

        return self.media_queries.get_category_analytics(telegram_chat_id, days)

    def get_category_mix_drift(self, telegram_chat_id: int, days: int = 7) -> dict:

        return self.media_queries.get_category_mix_drift(telegram_chat_id, days)

    def get_dead_content_report(
        self, telegram_chat_id: int, min_age_days: int = 30
    ) -> dict:

        return self.media_queries.get_dead_content_report(
            telegram_chat_id, min_age_days
        )

    def get_content_reuse_insights(self, telegram_chat_id: int) -> dict:

        return self.media_queries.get_content_reuse_insights(telegram_chat_id)

    # -- History delegates --

    def get_history_detail(self, telegram_chat_id: int, limit: int = 10) -> dict:

        return self.history_queries.get_history_detail(telegram_chat_id, limit)

    def get_analytics(self, telegram_chat_id: int, days: int = 30) -> dict:

        return self.history_queries.get_analytics(telegram_chat_id, days)

    def get_schedule_recommendations(
        self, telegram_chat_id: int, days: int = 90
    ) -> dict:

        return self.history_queries.get_schedule_recommendations(telegram_chat_id, days)

    @staticmethod
    def _generate_recommendations(hourly: list, dow: list) -> list:

        return HistoryDashboardQueries._generate_recommendations(hourly, dow)

    def get_schedule_preview(self, telegram_chat_id: int, slots: int = 10) -> dict:

        return self.history_queries.get_schedule_preview(telegram_chat_id, slots)

    def get_approval_latency(self, telegram_chat_id: int, days: int = 30) -> dict:

        return self.history_queries.get_approval_latency(telegram_chat_id, days)

    def get_team_performance(self, telegram_chat_id: int, days: int = 30) -> dict:

        return self.history_queries.get_team_performance(telegram_chat_id, days)

    # -- Instance delegates --

    def get_user_instances(self, telegram_user_id: int) -> dict:

        return self.instance_queries.get_user_instances(telegram_user_id)

    # -- Operations (stays on facade — system-level, not tenant-scoped) --

    def get_service_health_stats(self, hours: int = 24) -> dict:
        """Aggregate service_runs telemetry for an ops dashboard.

        Returns per-service call counts, error rates, and avg duration.

        NOTE: This is intentionally a global (system-level) view.
        service_runs are not tenant-scoped — they track internal service
        executions that span tenants. The API endpoint requires valid
        auth but does not filter by chat_id.
        """
        stats = self.service_run_repo.get_health_stats(hours=hours)
        total_calls = sum(s["call_count"] for s in stats)
        total_failures = sum(s["failure_count"] for s in stats)

        return {
            "services": stats,
            "total_calls": total_calls,
            "total_failures": total_failures,
            "overall_error_rate": round(total_failures / total_calls, 2)
            if total_calls
            else 0,
            "hours": hours,
        }
