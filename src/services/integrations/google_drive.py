"""Google Drive integration service for media source management."""

import json
from typing import Optional

from src.exceptions import GoogleDriveAuthError, GoogleDriveError
from src.repositories.token_repository import TokenRepository
from src.services.base_service import BaseService
from src.services.media_sources.google_drive_provider import GoogleDriveProvider
from src.utils.encryption import TokenEncryption
from src.utils.logger import logger


class GoogleDriveService(BaseService):
    """Orchestration service for Google Drive media source.

    Handles credential retrieval from encrypted storage, provider creation,
    connection validation, and credential management.
    """

    SERVICE_NAME = "google_drive"
    TOKEN_TYPE_SERVICE_ACCOUNT = "service_account_json"

    def __init__(self):
        super().__init__()
        self.token_repo = TokenRepository()
        self._encryption: Optional[TokenEncryption] = None

    @property
    def encryption(self) -> TokenEncryption:
        """Lazy-load encryption to avoid errors when ENCRYPTION_KEY not set."""
        if self._encryption is None:
            self._encryption = TokenEncryption()
        return self._encryption

    def connect(
        self,
        credentials_json: str,
        root_folder_id: str,
    ) -> bool:
        """Set up Google Drive by storing credentials and validating access.

        Args:
            credentials_json: Service account JSON key file content (string)
            root_folder_id: Google Drive folder ID to use as media root

        Returns:
            True if connection successful

        Raises:
            GoogleDriveAuthError: If credentials are invalid
            GoogleDriveError: If folder is not accessible
            ValueError: If credentials_json is not valid JSON
        """
        with self.track_execution(
            method_name="connect",
            triggered_by="cli",
            input_params={"root_folder_id": root_folder_id},
        ) as run_id:
            try:
                creds_dict = json.loads(credentials_json)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid credentials JSON: {e}")

            cred_type = creds_dict.get("type", "")
            if cred_type != "service_account":
                raise ValueError(
                    f"Unsupported credential type: '{cred_type}'. "
                    f"Expected 'service_account'."
                )

            # Test connection before storing
            provider = GoogleDriveProvider(
                root_folder_id=root_folder_id,
                service_account_info=creds_dict,
            )

            if not provider.is_configured():
                raise GoogleDriveError(
                    f"Cannot access Google Drive folder: {root_folder_id}. "
                    f"Ensure the folder is shared with the service account email."
                )

            # Encrypt and store
            encrypted = self.encryption.encrypt(credentials_json)

            self.token_repo.create_or_update(
                service_name=self.SERVICE_NAME,
                token_type=self.TOKEN_TYPE_SERVICE_ACCOUNT,
                token_value=encrypted,
                metadata={
                    "root_folder_id": root_folder_id,
                    "credential_type": cred_type,
                    "service_account_email": creds_dict.get("client_email", "unknown"),
                },
            )

            logger.info(
                f"Google Drive connected. Root folder: {root_folder_id}, "
                f"Account: {creds_dict.get('client_email', 'N/A')}"
            )

            self.set_result_summary(
                run_id,
                {
                    "success": True,
                    "root_folder_id": root_folder_id,
                    "credential_type": cred_type,
                },
            )

            return True

    def validate_access(self, root_folder_id: Optional[str] = None) -> dict:
        """Validate that stored credentials can access the target folder.

        Returns:
            dict with: valid, folder_id, file_count, categories, error
        """
        with self.track_execution(
            method_name="validate_access",
            input_params={"root_folder_id": root_folder_id},
        ) as run_id:
            try:
                provider = self.get_provider(root_folder_id)

                if not provider.is_configured():
                    result = {"valid": False, "error": "Cannot access folder"}
                    self.set_result_summary(run_id, result)
                    return result

                folders = provider.get_folders()
                files = provider.list_files()

                result = {
                    "valid": True,
                    "folder_id": provider.root_folder_id,
                    "file_count": len(files),
                    "categories": folders,
                }

                self.set_result_summary(run_id, result)
                return result

            except (GoogleDriveAuthError, GoogleDriveError) as e:
                result = {"valid": False, "error": str(e)}
                self.set_result_summary(run_id, result)
                return result

    def get_provider(self, root_folder_id: Optional[str] = None) -> GoogleDriveProvider:
        """Create a configured GoogleDriveProvider from stored credentials.

        Args:
            root_folder_id: Override the stored folder ID (optional).

        Raises:
            GoogleDriveAuthError: If no credentials stored or decryption fails.
        """
        db_token = self.token_repo.get_token(
            self.SERVICE_NAME, self.TOKEN_TYPE_SERVICE_ACCOUNT
        )

        if not db_token:
            raise GoogleDriveAuthError(
                "No Google Drive credentials found. "
                "Run 'storyline-cli connect-google-drive' first."
            )

        try:
            credentials_json = self.encryption.decrypt(db_token.token_value)
            creds_dict = json.loads(credentials_json)
        except (ValueError, json.JSONDecodeError) as e:
            raise GoogleDriveAuthError(
                f"Failed to decrypt Google Drive credentials: {e}"
            )

        if not root_folder_id:
            metadata = db_token.token_metadata or {}
            root_folder_id = metadata.get("root_folder_id")

        if not root_folder_id:
            raise GoogleDriveAuthError("No root_folder_id configured.")

        return GoogleDriveProvider(
            root_folder_id=root_folder_id,
            service_account_info=creds_dict,
        )

    def get_provider_for_chat(
        self,
        telegram_chat_id: int,
        root_folder_id: Optional[str] = None,
    ) -> GoogleDriveProvider:
        """Create a GoogleDriveProvider using user OAuth credentials for a tenant.

        Args:
            telegram_chat_id: Telegram chat ID to look up OAuth tokens for.
            root_folder_id: Google Drive folder ID to use as media root.

        Raises:
            GoogleDriveAuthError: If no user OAuth tokens found for this chat.
        """
        from src.services.integrations.google_drive_oauth import GoogleDriveOAuthService

        oauth_service = GoogleDriveOAuthService()
        try:
            credentials = oauth_service.get_user_credentials(telegram_chat_id)
        finally:
            oauth_service.close()

        if not credentials:
            raise GoogleDriveAuthError(
                "No Google Drive OAuth credentials found for this chat. "
                "Use /connect_drive to connect your Google Drive."
            )

        if not root_folder_id:
            raise GoogleDriveAuthError(
                "No root_folder_id configured for Google Drive media source."
            )

        return GoogleDriveProvider(
            root_folder_id=root_folder_id,
            oauth_credentials=credentials,
        )

    def disconnect(self) -> bool:
        """Remove stored Google Drive credentials."""
        with self.track_execution(method_name="disconnect") as run_id:
            deleted = self.token_repo.delete_token(
                self.SERVICE_NAME, self.TOKEN_TYPE_SERVICE_ACCOUNT
            )

            if not deleted:
                logger.info("No Google Drive credentials to remove")
                self.set_result_summary(
                    run_id, {"success": False, "reason": "no_credentials"}
                )
                return False

            logger.info("Google Drive credentials removed")
            self.set_result_summary(run_id, {"success": True})
            return True

    def get_connection_status(self) -> dict:
        """Check current Google Drive connection status."""
        db_token = self.token_repo.get_token(
            self.SERVICE_NAME, self.TOKEN_TYPE_SERVICE_ACCOUNT
        )

        if not db_token:
            return {"connected": False, "error": "No credentials configured"}

        metadata = db_token.token_metadata or {}

        return {
            "connected": True,
            "credential_type": metadata.get("credential_type", "unknown"),
            "service_account_email": metadata.get("service_account_email", "unknown"),
            "root_folder_id": metadata.get("root_folder_id", "unknown"),
        }
