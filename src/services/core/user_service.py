"""User service - user management operations."""

from typing import Optional

from src.services.base_service import BaseService
from src.repositories.user_repository import UserRepository
from src.models.user import User


class UserService(BaseService):
    """User management operations for CLI and API layers."""

    def __init__(self):
        super().__init__()
        self.user_repo = UserRepository()

    def list_users(self, is_active: Optional[bool] = None) -> list[User]:
        """List all users, optionally filtered by active status."""
        return self.user_repo.get_all(is_active=is_active)

    def get_by_telegram_id(self, telegram_user_id: int) -> Optional[User]:
        """Get a user by their Telegram user ID."""
        return self.user_repo.get_by_telegram_id(telegram_user_id)

    def promote_user(self, telegram_user_id: int, role: str) -> User:
        """Change a user's role.

        Args:
            telegram_user_id: Telegram user ID to look up
            role: New role ('admin' or 'member')

        Returns:
            Updated User

        Raises:
            ValueError: If user not found
        """
        user = self.user_repo.get_by_telegram_id(telegram_user_id)
        if not user:
            raise ValueError(f"User not found: {telegram_user_id}")
        self.user_repo.update_role(str(user.id), role)
        return user
