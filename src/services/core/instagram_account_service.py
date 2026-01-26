"""Instagram account service - manage connected accounts."""
from typing import Optional, List, Dict, Any
from datetime import datetime

from src.services.base_service import BaseService
from src.repositories.instagram_account_repository import InstagramAccountRepository
from src.repositories.chat_settings_repository import ChatSettingsRepository
from src.repositories.token_repository import TokenRepository
from src.models.instagram_account import InstagramAccount
from src.models.user import User
from src.utils.logger import logger
from src.utils.encryption import TokenEncryption


class InstagramAccountService(BaseService):
    """
    Manage Instagram accounts within a deployment.

    Handles:
    - Listing available accounts
    - Adding new accounts (with token storage)
    - Switching active account
    - Account status management

    Separation of concerns:
    - InstagramAccount = Identity (what accounts exist)
    - ApiToken = Credentials (how do we authenticate)
    - ChatSettings = Selection (which account is active)
    """

    def __init__(self):
        super().__init__()
        self.account_repo = InstagramAccountRepository()
        self.settings_repo = ChatSettingsRepository()
        self.token_repo = TokenRepository()
        self.encryption = TokenEncryption()

    def list_accounts(self, include_inactive: bool = False) -> List[InstagramAccount]:
        """
        Get Instagram accounts.

        Args:
            include_inactive: If True, include deactivated accounts

        Returns:
            List of InstagramAccount objects
        """
        if include_inactive:
            return self.account_repo.get_all()
        return self.account_repo.get_all_active()

    def get_account_by_id(self, account_id: str) -> Optional[InstagramAccount]:
        """Get account by UUID."""
        return self.account_repo.get_by_id(account_id)

    def get_account_by_username(self, username: str) -> Optional[InstagramAccount]:
        """Get account by Instagram username."""
        return self.account_repo.get_by_username(username)

    def get_active_account(self, telegram_chat_id: int) -> Optional[InstagramAccount]:
        """
        Get the currently active account for a chat.

        Args:
            telegram_chat_id: Telegram chat/channel ID

        Returns:
            Active InstagramAccount or None if not set
        """
        settings = self.settings_repo.get_or_create(telegram_chat_id)
        if settings.active_instagram_account_id:
            return self.account_repo.get_by_id(str(settings.active_instagram_account_id))
        return None

    def switch_account(
        self,
        telegram_chat_id: int,
        account_id: str,
        user: Optional[User] = None
    ) -> InstagramAccount:
        """
        Switch the active Instagram account.

        Args:
            telegram_chat_id: Chat to update
            account_id: UUID of account to switch to
            user: User performing the switch

        Returns:
            The newly active InstagramAccount

        Raises:
            ValueError: If account not found or disabled
        """
        with self.track_execution(
            "switch_account",
            user_id=user.id if user else None,
            triggered_by="user",
            input_params={"account_id": account_id}
        ) as run_id:
            account = self.account_repo.get_by_id(account_id)
            if not account:
                raise ValueError(f"Account {account_id} not found")

            if not account.is_active:
                raise ValueError(f"Account '{account.display_name}' is disabled")

            # Get old account for logging
            old_account = self.get_active_account(telegram_chat_id)

            # Update settings
            self.settings_repo.update(
                telegram_chat_id,
                active_instagram_account_id=account_id
            )

            self.set_result_summary(run_id, {
                "old_account": old_account.display_name if old_account else None,
                "new_account": account.display_name,
                "changed_by": user.telegram_username if user else "system"
            })

            logger.info(
                f"Switched Instagram account: "
                f"{old_account.display_name if old_account else 'None'} -> {account.display_name}"
            )

            return account

    def add_account(
        self,
        display_name: str,
        instagram_account_id: str,
        instagram_username: str,
        access_token: str,
        token_expires_at: Optional[datetime] = None,
        user: Optional[User] = None,
        set_as_active: bool = False,
        telegram_chat_id: Optional[int] = None
    ) -> InstagramAccount:
        """
        Add a new Instagram account with its token.

        Args:
            display_name: User-friendly name
            instagram_account_id: Meta's account ID (numeric string)
            instagram_username: @username
            access_token: OAuth access token
            token_expires_at: When token expires
            user: User adding the account
            set_as_active: If True, set this as the active account
            telegram_chat_id: Required if set_as_active is True

        Returns:
            Created InstagramAccount

        Raises:
            ValueError: If account already exists or invalid params
        """
        with self.track_execution(
            "add_account",
            user_id=user.id if user else None,
            triggered_by="user",
            input_params={
                "display_name": display_name,
                "instagram_username": instagram_username
            }
        ) as run_id:
            # Check if account already exists
            existing = self.account_repo.get_by_instagram_id(instagram_account_id)
            if existing:
                raise ValueError(
                    f"Account with ID {instagram_account_id} already exists "
                    f"as '{existing.display_name}'"
                )

            # Also check by username
            existing_by_username = self.account_repo.get_by_username(instagram_username)
            if existing_by_username:
                raise ValueError(
                    f"Account @{instagram_username} already exists "
                    f"as '{existing_by_username.display_name}'"
                )

            # Create account record
            account = self.account_repo.create(
                display_name=display_name,
                instagram_account_id=instagram_account_id,
                instagram_username=instagram_username,
            )

            # Encrypt and store token linked to this account
            encrypted_token = self.encryption.encrypt(access_token)
            self.token_repo.create_or_update(
                service_name="instagram",
                token_type="access_token",
                token_value=encrypted_token,
                expires_at=token_expires_at,
                instagram_account_id=str(account.id),
                metadata={
                    "account_id": instagram_account_id,
                    "username": instagram_username
                }
            )

            # Optionally set as active
            if set_as_active:
                if not telegram_chat_id:
                    raise ValueError("telegram_chat_id required when set_as_active=True")
                self.settings_repo.update(
                    telegram_chat_id,
                    active_instagram_account_id=str(account.id)
                )

            self.set_result_summary(run_id, {
                "account_id": str(account.id),
                "display_name": display_name,
                "username": instagram_username,
                "set_as_active": set_as_active
            })

            logger.info(f"Added Instagram account: {display_name} (@{instagram_username})")

            return account

    def update_account(
        self,
        account_id: str,
        display_name: Optional[str] = None,
        instagram_username: Optional[str] = None,
        user: Optional[User] = None
    ) -> InstagramAccount:
        """
        Update an Instagram account's display info.

        Args:
            account_id: UUID of account to update
            display_name: New display name (optional)
            instagram_username: New username (optional)
            user: User performing the update

        Returns:
            Updated InstagramAccount
        """
        with self.track_execution(
            "update_account",
            user_id=user.id if user else None,
            triggered_by="user",
            input_params={"account_id": account_id}
        ) as run_id:
            updates = {}
            if display_name is not None:
                updates["display_name"] = display_name
            if instagram_username is not None:
                updates["instagram_username"] = instagram_username

            if not updates:
                raise ValueError("No updates provided")

            account = self.account_repo.update(account_id, **updates)

            self.set_result_summary(run_id, {
                "account_id": str(account.id),
                "updates": updates
            })

            logger.info(f"Updated Instagram account: {account.display_name}")

            return account

    def update_account_token(
        self,
        instagram_account_id: str,
        access_token: str,
        instagram_username: Optional[str] = None,
        token_expires_at: Optional[datetime] = None,
        user: Optional[User] = None,
        set_as_active: bool = False,
        telegram_chat_id: Optional[int] = None
    ) -> InstagramAccount:
        """
        Update the token for an existing Instagram account.

        Use this when re-adding an account that already exists
        (e.g., token expired and user is re-authenticating).

        Args:
            instagram_account_id: Meta's account ID (numeric string)
            access_token: New OAuth access token
            instagram_username: Update username if changed (optional)
            token_expires_at: When new token expires
            user: User performing the update
            set_as_active: If True, set this as the active account
            telegram_chat_id: Required if set_as_active is True

        Returns:
            Updated InstagramAccount

        Raises:
            ValueError: If account not found
        """
        with self.track_execution(
            "update_account_token",
            user_id=user.id if user else None,
            triggered_by="user",
            input_params={"instagram_account_id": instagram_account_id}
        ) as run_id:
            # Find existing account
            account = self.account_repo.get_by_instagram_id(instagram_account_id)
            if not account:
                raise ValueError(f"Account with ID {instagram_account_id} not found")

            # Update username if provided
            if instagram_username and instagram_username != account.instagram_username:
                account = self.account_repo.update(
                    str(account.id),
                    instagram_username=instagram_username
                )

            # Encrypt and update/create token
            encrypted_token = self.encryption.encrypt(access_token)
            self.token_repo.create_or_update(
                service_name="instagram",
                token_type="access_token",
                token_value=encrypted_token,
                expires_at=token_expires_at,
                instagram_account_id=str(account.id),
                metadata={
                    "account_id": instagram_account_id,
                    "username": account.instagram_username
                }
            )

            # Reactivate if was deactivated
            if not account.is_active:
                account = self.account_repo.activate(str(account.id))
                logger.info(f"Reactivated Instagram account: {account.display_name}")

            # Optionally set as active
            if set_as_active:
                if not telegram_chat_id:
                    raise ValueError("telegram_chat_id required when set_as_active=True")
                self.settings_repo.update(
                    telegram_chat_id,
                    active_instagram_account_id=str(account.id)
                )

            self.set_result_summary(run_id, {
                "account_id": str(account.id),
                "display_name": account.display_name,
                "username": account.instagram_username,
                "token_updated": True
            })

            logger.info(
                f"Updated token for Instagram account: "
                f"{account.display_name} (@{account.instagram_username})"
            )

            return account

    def get_account_by_instagram_id(self, instagram_account_id: str) -> Optional[InstagramAccount]:
        """Get account by Instagram's numeric ID."""
        return self.account_repo.get_by_instagram_id(instagram_account_id)

    def deactivate_account(
        self,
        account_id: str,
        user: Optional[User] = None
    ) -> InstagramAccount:
        """
        Soft-delete an account by marking it inactive.

        The account and its tokens are preserved for audit purposes.

        Args:
            account_id: UUID of account to deactivate
            user: User performing the action

        Returns:
            Deactivated InstagramAccount
        """
        with self.track_execution(
            "deactivate_account",
            user_id=user.id if user else None,
            triggered_by="user",
            input_params={"account_id": account_id}
        ) as run_id:
            account = self.account_repo.deactivate(account_id)

            self.set_result_summary(run_id, {
                "account_id": str(account.id),
                "display_name": account.display_name
            })

            logger.info(f"Deactivated Instagram account: {account.display_name}")

            return account

    def reactivate_account(
        self,
        account_id: str,
        user: Optional[User] = None
    ) -> InstagramAccount:
        """
        Reactivate a previously deactivated account.

        Args:
            account_id: UUID of account to reactivate
            user: User performing the action

        Returns:
            Reactivated InstagramAccount
        """
        with self.track_execution(
            "reactivate_account",
            user_id=user.id if user else None,
            triggered_by="user",
            input_params={"account_id": account_id}
        ) as run_id:
            account = self.account_repo.activate(account_id)

            self.set_result_summary(run_id, {
                "account_id": str(account.id),
                "display_name": account.display_name
            })

            logger.info(f"Reactivated Instagram account: {account.display_name}")

            return account

    def get_accounts_for_display(self, telegram_chat_id: int) -> Dict[str, Any]:
        """
        Get account info formatted for /settings display.

        Args:
            telegram_chat_id: Chat to get settings for

        Returns:
            Dict with accounts list and active account info
        """
        accounts = self.list_accounts()
        active = self.get_active_account(telegram_chat_id)

        return {
            "accounts": [
                {
                    "id": str(a.id),
                    "display_name": a.display_name,
                    "username": a.instagram_username
                }
                for a in accounts
            ],
            "active_account_id": str(active.id) if active else None,
            "active_account_name": active.display_name if active else "Not selected",
            "active_account_username": active.instagram_username if active else None
        }

    def get_token_for_active_account(
        self,
        telegram_chat_id: int
    ) -> Optional[str]:
        """
        Get the access token for the currently active account.

        Convenience method for posting services.

        Args:
            telegram_chat_id: Chat to get active account for

        Returns:
            Access token string or None if no active account/token
        """
        active = self.get_active_account(telegram_chat_id)
        if not active:
            return None

        token = self.token_repo.get_token_for_account(
            str(active.id),
            token_type="access_token"
        )
        return token.token_value if token else None

    def auto_select_account_if_single(self, telegram_chat_id: int) -> Optional[InstagramAccount]:
        """
        Auto-select an account if exactly one exists and none is selected.

        Convenience for new deployments.

        Args:
            telegram_chat_id: Chat to check/update

        Returns:
            Auto-selected account, or None if not applicable
        """
        current = self.get_active_account(telegram_chat_id)
        if current:
            return None  # Already has an account selected

        accounts = self.list_accounts()
        if len(accounts) == 1:
            # Auto-select the only account
            self.settings_repo.update(
                telegram_chat_id,
                active_instagram_account_id=str(accounts[0].id)
            )
            logger.info(f"Auto-selected Instagram account: {accounts[0].display_name}")
            return accounts[0]

        return None
