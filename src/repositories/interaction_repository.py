"""Interaction repository - CRUD operations for user interactions."""
from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.config.database import get_db
from src.models.user_interaction import UserInteraction


class InteractionRepository:
    """Repository for UserInteraction CRUD operations."""

    def __init__(self):
        self.db: Session = next(get_db())

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
        return self.db.query(UserInteraction).filter(
            UserInteraction.id == interaction_id
        ).first()

    def get_by_user(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[UserInteraction]:
        """Get interactions for a specific user."""
        return (
            self.db.query(UserInteraction)
            .filter(UserInteraction.user_id == user_id)
            .order_by(UserInteraction.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_by_type(
        self,
        interaction_type: str,
        days: int = 30,
        limit: int = 1000,
    ) -> List[UserInteraction]:
        """Get interactions by type within date range."""
        since = datetime.utcnow() - timedelta(days=days)
        return (
            self.db.query(UserInteraction)
            .filter(
                UserInteraction.interaction_type == interaction_type,
                UserInteraction.created_at >= since,
            )
            .order_by(UserInteraction.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_by_name(
        self,
        interaction_name: str,
        days: int = 30,
        limit: int = 1000,
    ) -> List[UserInteraction]:
        """Get interactions by name within date range."""
        since = datetime.utcnow() - timedelta(days=days)
        return (
            self.db.query(UserInteraction)
            .filter(
                UserInteraction.interaction_name == interaction_name,
                UserInteraction.created_at >= since,
            )
            .order_by(UserInteraction.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_recent(
        self,
        days: int = 30,
        limit: int = 1000,
    ) -> List[UserInteraction]:
        """Get all recent interactions."""
        since = datetime.utcnow() - timedelta(days=days)
        return (
            self.db.query(UserInteraction)
            .filter(UserInteraction.created_at >= since)
            .order_by(UserInteraction.created_at.desc())
            .limit(limit)
            .all()
        )

    def count_by_user(self, user_id: str, days: int = 30) -> int:
        """Count interactions for a user within date range."""
        since = datetime.utcnow() - timedelta(days=days)
        return (
            self.db.query(func.count(UserInteraction.id))
            .filter(
                UserInteraction.user_id == user_id,
                UserInteraction.created_at >= since,
            )
            .scalar()
        )

    def count_by_name(self, interaction_name: str, days: int = 30) -> int:
        """Count interactions by name within date range."""
        since = datetime.utcnow() - timedelta(days=days)
        return (
            self.db.query(func.count(UserInteraction.id))
            .filter(
                UserInteraction.interaction_name == interaction_name,
                UserInteraction.created_at >= since,
            )
            .scalar()
        )

    def get_user_stats(self, user_id: str, days: int = 30) -> dict:
        """Get aggregated stats for a user."""
        since = datetime.utcnow() - timedelta(days=days)

        interactions = (
            self.db.query(UserInteraction)
            .filter(
                UserInteraction.user_id == user_id,
                UserInteraction.created_at >= since,
            )
            .all()
        )

        stats = {
            "total_interactions": len(interactions),
            "posts_marked": 0,
            "posts_skipped": 0,
            "posts_rejected": 0,
            "commands_used": {},
        }

        for interaction in interactions:
            if interaction.interaction_name == "posted":
                stats["posts_marked"] += 1
            elif interaction.interaction_name == "skip":
                stats["posts_skipped"] += 1
            elif interaction.interaction_name == "confirm_reject":
                stats["posts_rejected"] += 1
            elif interaction.interaction_type == "command":
                cmd = interaction.interaction_name
                stats["commands_used"][cmd] = stats["commands_used"].get(cmd, 0) + 1

        return stats

    def get_team_activity(self, days: int = 30) -> dict:
        """Get team-wide activity stats."""
        since = datetime.utcnow() - timedelta(days=days)

        interactions = (
            self.db.query(UserInteraction)
            .filter(UserInteraction.created_at >= since)
            .all()
        )

        user_ids = set()
        by_type = {}
        by_name = {}

        for interaction in interactions:
            user_ids.add(str(interaction.user_id))

            t = interaction.interaction_type
            by_type[t] = by_type.get(t, 0) + 1

            n = interaction.interaction_name
            by_name[n] = by_name.get(n, 0) + 1

        return {
            "total_interactions": len(interactions),
            "active_users": len(user_ids),
            "interactions_by_type": by_type,
            "interactions_by_name": by_name,
        }

    def get_content_decisions(self, days: int = 30) -> dict:
        """Get content decision breakdown (posted vs skipped vs rejected)."""
        since = datetime.utcnow() - timedelta(days=days)

        decisions = (
            self.db.query(UserInteraction)
            .filter(
                UserInteraction.interaction_type == "callback",
                UserInteraction.interaction_name.in_(["posted", "skip", "confirm_reject"]),
                UserInteraction.created_at >= since,
            )
            .all()
        )

        posted = sum(1 for d in decisions if d.interaction_name == "posted")
        skipped = sum(1 for d in decisions if d.interaction_name == "skip")
        rejected = sum(1 for d in decisions if d.interaction_name == "confirm_reject")
        total = len(decisions)

        return {
            "total_decisions": total,
            "posted": posted,
            "skipped": skipped,
            "rejected": rejected,
            "posted_percentage": round(posted / total * 100, 1) if total > 0 else 0,
            "skip_percentage": round(skipped / total * 100, 1) if total > 0 else 0,
            "rejection_rate": round(rejected / total * 100, 1) if total > 0 else 0,
        }
