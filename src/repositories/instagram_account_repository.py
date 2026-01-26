"""Instagram account repository - CRUD for connected accounts."""
from typing import Optional, List
from datetime import datetime

from src.repositories.base_repository import BaseRepository
from src.models.instagram_account import InstagramAccount


class InstagramAccountRepository(BaseRepository):
    """Repository for InstagramAccount CRUD operations."""

    def get_all_active(self) -> List[InstagramAccount]:
        """Get all active Instagram accounts."""
        result = self.db.query(InstagramAccount).filter(
            InstagramAccount.is_active
        ).order_by(InstagramAccount.display_name).all()
        self.end_read_transaction()
        return result

    def get_all(self) -> List[InstagramAccount]:
        """Get all Instagram accounts (including inactive)."""
        result = self.db.query(InstagramAccount).order_by(
            InstagramAccount.display_name
        ).all()
        self.end_read_transaction()
        return result

    def get_by_id(self, account_id: str) -> Optional[InstagramAccount]:
        """Get account by UUID."""
        result = self.db.query(InstagramAccount).filter(
            InstagramAccount.id == account_id
        ).first()
        self.end_read_transaction()
        return result

    def get_by_instagram_id(self, instagram_account_id: str) -> Optional[InstagramAccount]:
        """Get account by Instagram's account ID."""
        result = self.db.query(InstagramAccount).filter(
            InstagramAccount.instagram_account_id == instagram_account_id
        ).first()
        self.end_read_transaction()
        return result

    def get_by_username(self, username: str) -> Optional[InstagramAccount]:
        """Get account by Instagram username."""
        # Strip @ if present
        username = username.lstrip("@")
        result = self.db.query(InstagramAccount).filter(
            InstagramAccount.instagram_username == username
        ).first()
        self.end_read_transaction()
        return result

    def create(
        self,
        display_name: str,
        instagram_account_id: str,
        instagram_username: Optional[str] = None
    ) -> InstagramAccount:
        """Create a new Instagram account record."""
        # Strip @ if present in username
        if instagram_username:
            instagram_username = instagram_username.lstrip("@")

        account = InstagramAccount(
            display_name=display_name,
            instagram_account_id=instagram_account_id,
            instagram_username=instagram_username,
        )
        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)
        return account

    def update(self, account_id: str, **kwargs) -> InstagramAccount:
        """Update an Instagram account."""
        account = self.db.query(InstagramAccount).filter(
            InstagramAccount.id == account_id
        ).first()

        if not account:
            raise ValueError(f"Account {account_id} not found")

        for key, value in kwargs.items():
            if hasattr(account, key):
                # Strip @ from username if updating
                if key == "instagram_username" and value:
                    value = value.lstrip("@")
                setattr(account, key, value)

        account.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(account)
        return account

    def deactivate(self, account_id: str) -> InstagramAccount:
        """Soft-delete an account by marking inactive."""
        return self.update(account_id, is_active=False)

    def activate(self, account_id: str) -> InstagramAccount:
        """Re-activate a previously deactivated account."""
        return self.update(account_id, is_active=True)

    def count_active(self) -> int:
        """Count active Instagram accounts."""
        result = self.db.query(InstagramAccount).filter(
            InstagramAccount.is_active
        ).count()
        self.end_read_transaction()
        return result
