"""User repository - CRUD operations for users."""

from typing import Optional
from datetime import datetime

from src.repositories.base_repository import BaseRepository
from src.models.user import User


class UserRepository(BaseRepository):
    """Repository for User CRUD operations."""

    def __init__(self):
        super().__init__()

    def get_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_telegram_id(self, telegram_user_id: int) -> Optional[User]:
        """Get user by Telegram user ID."""
        return (
            self.db.query(User)
            .filter(User.telegram_user_id == telegram_user_id)
            .first()
        )

    def get_all(self, is_active: Optional[bool] = None) -> list[User]:
        """Get all users, optionally filtered by active status."""
        query = self.db.query(User)

        if is_active is not None:
            query = query.filter(User.is_active == is_active)

        return query.order_by(User.created_at.desc()).all()

    def create(
        self,
        telegram_user_id: int,
        telegram_username: Optional[str] = None,
        telegram_first_name: Optional[str] = None,
        telegram_last_name: Optional[str] = None,
        team_name: Optional[str] = None,
        role: str = "member",
    ) -> User:
        """Create a new user."""
        user = User(
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username,
            telegram_first_name=telegram_first_name,
            telegram_last_name=telegram_last_name,
            team_name=team_name,
            role=role,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_last_seen(self, user_id: str) -> User:
        """Update user's last seen timestamp."""
        user = self.get_by_id(user_id)
        if user:
            user.last_seen_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(user)
        return user

    def update_profile(
        self,
        user_id: str,
        telegram_username: Optional[str] = None,
        telegram_first_name: Optional[str] = None,
        telegram_last_name: Optional[str] = None,
    ) -> User:
        """Update user's Telegram profile data and last seen timestamp.

        Syncs profile data on each interaction in case user changed their
        Telegram username or added one after initial account creation.
        """
        user = self.get_by_id(user_id)
        if user:
            user.telegram_username = telegram_username
            user.telegram_first_name = telegram_first_name
            user.telegram_last_name = telegram_last_name
            user.last_seen_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(user)
        return user

    def increment_posts(self, user_id: str) -> User:
        """Increment user's total posts count."""
        user = self.get_by_id(user_id)
        if user:
            user.total_posts += 1
            user.last_seen_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(user)
        return user

    def update_role(self, user_id: str, role: str) -> User:
        """Update user's role."""
        user = self.get_by_id(user_id)
        if user:
            user.role = role
            self.db.commit()
            self.db.refresh(user)
        return user

    def deactivate(self, user_id: str) -> User:
        """Deactivate a user."""
        user = self.get_by_id(user_id)
        if user:
            user.is_active = False
            self.db.commit()
            self.db.refresh(user)
        return user
