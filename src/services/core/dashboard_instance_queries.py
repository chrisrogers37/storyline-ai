"""Instance-related dashboard queries — user instances and membership lookups."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.services.core.dashboard_service import DashboardService


class InstanceDashboardQueries:
    """User instance listing and membership queries for the dashboard."""

    def __init__(self, service: DashboardService):
        self.service = service

    def get_user_instances(self, telegram_user_id: int) -> dict:
        """Return all instances a user belongs to, with stats per instance.

        Used by the instance picker (web dashboard and DM Mini App).
        """
        user = self.service.user_repo.get_by_telegram_id(telegram_user_id)
        if not user:
            return {"instances": []}

        memberships = self.service.membership_repo.get_for_user(str(user.id))
        instances = []
        for membership in memberships:
            cs = membership.chat_settings
            cs_id = str(cs.id)

            media_count = self.service.media_repo.count_active(chat_settings_id=cs_id)

            last_post_at = None
            recent = self.service.history_repo.get_recent_posts(
                hours=720, chat_settings_id=cs_id, limit=1
            )
            if recent:
                last_post_at = recent[0].posted_at.isoformat()

            instances.append(
                {
                    "chat_settings_id": cs_id,
                    "telegram_chat_id": cs.telegram_chat_id,
                    "display_name": cs.display_name,
                    "media_count": media_count,
                    "posts_per_day": cs.posts_per_day,
                    "is_paused": cs.is_paused,
                    "last_post_at": last_post_at,
                    "instance_role": membership.instance_role,
                }
            )

        return {"instances": instances}
