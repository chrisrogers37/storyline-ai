"""Interaction repository - CRUD operations for user interactions."""

from typing import Optional, List
from datetime import datetime, timedelta
from src.repositories.base_repository import BaseRepository
from src.models.user_interaction import UserInteraction


class InteractionRepository(BaseRepository):
    """Repository for UserInteraction CRUD operations."""

    def __init__(self):
        super().__init__()

    def create(
        self,
        user_id: str,
        interaction_type: str,
        interaction_name: str,
        context: Optional[dict] = None,
        telegram_chat_id: Optional[int] = None,
        telegram_message_id: Optional[int] = None,
    ) -> UserInteraction:
        """Create a new interaction record."""
        interaction = UserInteraction(
            user_id=user_id,
            interaction_type=interaction_type,
            interaction_name=interaction_name,
            context=context or {},
            telegram_chat_id=telegram_chat_id,
            telegram_message_id=telegram_message_id,
        )
        self.db.add(interaction)
        self.db.commit()
        self.db.refresh(interaction)
        return interaction

    def get_by_id(self, interaction_id: str) -> Optional[UserInteraction]:
        """Get interaction by ID."""
        result = (
            self.db.query(UserInteraction)
            .filter(UserInteraction.id == interaction_id)
            .first()
        )
        self.end_read_transaction()
        return result

    def get_recent(
        self,
        days: int = 30,
        limit: int = 1000,
    ) -> List[UserInteraction]:
        """Get all recent interactions."""
        since = datetime.utcnow() - timedelta(days=days)
        result = (
            self.db.query(UserInteraction)
            .filter(UserInteraction.created_at >= since)
            .order_by(UserInteraction.created_at.desc())
            .limit(limit)
            .all()
        )
        self.end_read_transaction()
        return result

    def get_user_stats(self, user_id: str, days: int = 30) -> dict:
        """Get aggregated stats for a user using SQL."""
        from sqlalchemy import func, case

        since = datetime.utcnow() - timedelta(days=days)

        row = (
            self.db.query(
                func.count(UserInteraction.id).label("total"),
                func.count(
                    case((UserInteraction.interaction_name == "posted", 1))
                ).label("posted"),
                func.count(case((UserInteraction.interaction_name == "skip", 1))).label(
                    "skipped"
                ),
                func.count(
                    case((UserInteraction.interaction_name == "confirm_reject", 1))
                ).label("rejected"),
            )
            .filter(
                UserInteraction.user_id == user_id,
                UserInteraction.created_at >= since,
            )
            .first()
        )
        self.end_read_transaction()

        cmd_rows = (
            self.db.query(
                UserInteraction.interaction_name,
                func.count(UserInteraction.id),
            )
            .filter(
                UserInteraction.user_id == user_id,
                UserInteraction.interaction_type == "command",
                UserInteraction.created_at >= since,
            )
            .group_by(UserInteraction.interaction_name)
            .all()
        )
        self.end_read_transaction()

        return {
            "total_interactions": row.total or 0,
            "posts_marked": row.posted or 0,
            "posts_skipped": row.skipped or 0,
            "posts_rejected": row.rejected or 0,
            "commands_used": {name: count for name, count in cmd_rows},
        }

    def get_team_activity(self, days: int = 30) -> dict:
        """Get team-wide activity stats using SQL."""
        from sqlalchemy import func

        since = datetime.utcnow() - timedelta(days=days)
        base_filter = UserInteraction.created_at >= since

        total = (
            self.db.query(func.count(UserInteraction.id)).filter(base_filter).scalar()
            or 0
        )

        active_users = (
            self.db.query(func.count(func.distinct(UserInteraction.user_id)))
            .filter(base_filter)
            .scalar()
            or 0
        )

        by_type = dict(
            self.db.query(
                UserInteraction.interaction_type, func.count(UserInteraction.id)
            )
            .filter(base_filter)
            .group_by(UserInteraction.interaction_type)
            .all()
        )

        by_name = dict(
            self.db.query(
                UserInteraction.interaction_name, func.count(UserInteraction.id)
            )
            .filter(base_filter)
            .group_by(UserInteraction.interaction_name)
            .all()
        )
        self.end_read_transaction()

        return {
            "total_interactions": total,
            "active_users": active_users,
            "interactions_by_type": by_type,
            "interactions_by_name": by_name,
        }

    def get_content_decisions(self, days: int = 30) -> dict:
        """Get content decision breakdown using SQL."""
        from sqlalchemy import func, case

        since = datetime.utcnow() - timedelta(days=days)

        row = (
            self.db.query(
                func.count(UserInteraction.id).label("total"),
                func.count(
                    case((UserInteraction.interaction_name == "posted", 1))
                ).label("posted"),
                func.count(case((UserInteraction.interaction_name == "skip", 1))).label(
                    "skipped"
                ),
                func.count(
                    case((UserInteraction.interaction_name == "confirm_reject", 1))
                ).label("rejected"),
            )
            .filter(
                UserInteraction.interaction_type == "callback",
                UserInteraction.interaction_name.in_(
                    ["posted", "skip", "confirm_reject"]
                ),
                UserInteraction.created_at >= since,
            )
            .first()
        )
        self.end_read_transaction()

        total = row.total or 0
        posted = row.posted or 0
        skipped = row.skipped or 0
        rejected = row.rejected or 0

        return {
            "total_decisions": total,
            "posted": posted,
            "skipped": skipped,
            "rejected": rejected,
            "posted_percentage": round(posted / total * 100, 1) if total > 0 else 0,
            "skip_percentage": round(skipped / total * 100, 1) if total > 0 else 0,
            "rejection_rate": round(rejected / total * 100, 1) if total > 0 else 0,
        }

    def get_bot_responses_by_chat(
        self,
        chat_id: int,
        hours: int = 48,
    ) -> List[UserInteraction]:
        """
        Get bot response messages for a specific chat within time window.

        Used by /cleanup command to find deletable bot messages.
        Telegram API only allows deleting messages < 48 hours old.

        Args:
            chat_id: Telegram chat ID to filter by
            hours: Lookback window in hours (default 48 for Telegram limit)

        Returns:
            List of bot_response interactions with telegram_message_id
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        result = (
            self.db.query(UserInteraction)
            .filter(
                UserInteraction.interaction_type == "bot_response",
                UserInteraction.telegram_chat_id == chat_id,
                UserInteraction.telegram_message_id.isnot(None),
                UserInteraction.created_at >= since,
            )
            .order_by(UserInteraction.created_at.desc())
            .all()
        )
        self.end_read_transaction()
        return result
