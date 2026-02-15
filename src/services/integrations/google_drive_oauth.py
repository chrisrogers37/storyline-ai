"""Google Drive OAuth service - handles user OAuth flow for Google Drive."""

import json
import secrets
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

import httpx
from telegram import Bot

from src.config.settings import settings
from src.repositories.chat_settings_repository import ChatSettingsRepository
from src.repositories.token_repository import TokenRepository
from src.services.base_service import BaseService
from src.utils.encryption import TokenEncryption
from src.utils.logger import logger


class GoogleDriveOAuthService(BaseService):
    """
    Orchestrate the Google Drive OAuth redirect flow.

    Handles:
    - Generating signed state tokens (Fernet, reuses Phase 04 pattern)
    - Exchanging auth codes for access + refresh tokens
    - Storing encrypted tokens per-tenant in api_tokens
    - Creating GoogleDriveProvider from user OAuth credentials
    - Notifying Telegram after success/failure
    """

    GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
    GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
    STATE_TTL_SECONDS = 600  # 10 minutes

    SERVICE_NAME = "google_drive"
    TOKEN_TYPE_ACCESS = "oauth_access"
    TOKEN_TYPE_REFRESH = "oauth_refresh"

    REQUIRED_SCOPES = [
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/userinfo.email",
    ]

    def __init__(self):
        super().__init__()
        self.token_repo = TokenRepository()
        self.settings_repo = ChatSettingsRepository()
        self._encryption: Optional[TokenEncryption] = None

    @property
    def encryption(self) -> TokenEncryption:
        """Lazy-load encryption to avoid errors when ENCRYPTION_KEY not set."""
        if self._encryption is None:
            self._encryption = TokenEncryption()
        return self._encryption

    @property
    def redirect_uri(self) -> str:
        """Build the full OAuth callback URL."""
        base = settings.OAUTH_REDIRECT_BASE_URL.rstrip("/")
        return f"{base}/auth/google-drive/callback"

    def generate_authorization_url(self, telegram_chat_id: int) -> str:
        """
        Generate the Google OAuth authorization URL with a signed state token.

        Args:
            telegram_chat_id: The Telegram chat that initiated the flow

        Returns:
            Full Google OAuth authorization URL

        Raises:
            ValueError: If required settings are missing
        """
        self._validate_config()

        state_token = self._create_state_token(telegram_chat_id)

        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.REQUIRED_SCOPES),
            "response_type": "code",
            "state": state_token,
            "access_type": "offline",
            "prompt": "consent",
        }

        return f"{self.GOOGLE_AUTH_URL}?{urlencode(params)}"

    def _create_state_token(self, telegram_chat_id: int) -> str:
        """Create a signed, time-limited state token (Fernet, same as Phase 04)."""
        payload = json.dumps(
            {
                "chat_id": telegram_chat_id,
                "provider": "google_drive",
                "nonce": secrets.token_hex(16),
            }
        )
        return self.encryption.encrypt(payload)

    def validate_state_token(self, state: str) -> int:
        """
        Validate a state token and extract the Telegram chat ID.

        Args:
            state: The encrypted state token from the OAuth callback

        Returns:
            telegram_chat_id extracted from the token

        Raises:
            ValueError: If token is invalid, expired, or tampered with
        """
        try:
            decrypted_bytes = self.encryption._cipher.decrypt(
                state.encode(),
                ttl=self.STATE_TTL_SECONDS,
            )
            payload = json.loads(decrypted_bytes.decode())
            chat_id = payload.get("chat_id")

            if not chat_id or not isinstance(chat_id, int):
                raise ValueError("Invalid payload: missing chat_id")

            return chat_id

        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Invalid or expired state token: {e}")

    async def exchange_and_store(self, auth_code: str, telegram_chat_id: int) -> dict:
        """
        Exchange the authorization code for tokens and store them.

        Flow:
        1. Exchange auth code for access_token + refresh_token
        2. Fetch user email from Google
        3. Encrypt and store both tokens per-tenant
        4. Return result dict

        Args:
            auth_code: Authorization code from Google callback
            telegram_chat_id: Chat to associate the tokens with

        Returns:
            dict with email, expires_in_hours

        Raises:
            ValueError: If exchange fails or chat not found
        """
        with self.track_execution(
            method_name="exchange_and_store",
            triggered_by="user",
            input_params={"chat_id": telegram_chat_id},
        ) as run_id:
            # Step 1: Exchange code for tokens
            token_data = await self._exchange_code_for_tokens(auth_code)

            access_token = token_data["access_token"]
            refresh_token = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in", 3600)

            # Step 2: Fetch user email
            email = await self._get_user_email(access_token)

            # Step 3: Resolve chat_settings_id
            chat_settings = self.settings_repo.get_or_create(telegram_chat_id)
            chat_settings_id = str(chat_settings.id)

            # Step 4: Encrypt and store tokens
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

            self.token_repo.create_or_update_for_chat(
                service_name=self.SERVICE_NAME,
                token_type=self.TOKEN_TYPE_ACCESS,
                token_value=self.encryption.encrypt(access_token),
                chat_settings_id=chat_settings_id,
                expires_at=expires_at,
                scopes=self.REQUIRED_SCOPES,
                metadata={"email": email},
            )

            if refresh_token:
                self.token_repo.create_or_update_for_chat(
                    service_name=self.SERVICE_NAME,
                    token_type=self.TOKEN_TYPE_REFRESH,
                    token_value=self.encryption.encrypt(refresh_token),
                    chat_settings_id=chat_settings_id,
                    metadata={"email": email},
                )

            logger.info(
                f"Google Drive OAuth: stored tokens for {email} "
                f"(chat {telegram_chat_id})"
            )

            result = {
                "email": email or "unknown",
                "expires_in_hours": expires_in // 3600,
            }

            self.set_result_summary(run_id, result)
            return result

    async def _exchange_code_for_tokens(self, auth_code: str) -> dict:
        """Exchange authorization code for access and refresh tokens."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.GOOGLE_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": auth_code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": self.redirect_uri,
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                error = response.json()
                error_msg = error.get(
                    "error_description", error.get("error", "Unknown")
                )
                raise ValueError(f"Google token exchange failed: {error_msg}")

            return response.json()

    async def _get_user_email(self, access_token: str) -> Optional[str]:
        """Fetch the user's email from Google userinfo endpoint."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.GOOGLE_USERINFO_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=15.0,
                )
                if response.status_code == 200:
                    return response.json().get("email")
        except Exception as e:
            logger.warning(f"Failed to fetch Google user email: {e}")
        return None

    async def notify_telegram(
        self, chat_id: int, message: str, success: bool = True
    ) -> None:
        """Send a notification message to the Telegram chat."""
        try:
            bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
            emoji = "\U0001f4c1" if success else "\u26a0\ufe0f"
            full_message = f"{emoji} *Google Drive OAuth*\n\n{message}"
            await bot.send_message(
                chat_id=chat_id,
                text=full_message,
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(
                f"Failed to send GDrive OAuth notification to chat {chat_id}: {e}"
            )

    def get_user_credentials(self, telegram_chat_id: int):
        """
        Get Google OAuth credentials for a tenant, suitable for GoogleDriveProvider.

        Returns a google.oauth2.credentials.Credentials object, or None if
        no user OAuth tokens are stored for this tenant.
        """
        chat_settings = self.settings_repo.get_by_chat_id(telegram_chat_id)
        if not chat_settings:
            return None

        chat_settings_id = str(chat_settings.id)

        access_row = self.token_repo.get_token_for_chat(
            self.SERVICE_NAME, self.TOKEN_TYPE_ACCESS, chat_settings_id
        )
        refresh_row = self.token_repo.get_token_for_chat(
            self.SERVICE_NAME, self.TOKEN_TYPE_REFRESH, chat_settings_id
        )

        if not access_row:
            return None

        try:
            from google.oauth2.credentials import Credentials

            access_token = self.encryption.decrypt(access_row.token_value)
            refresh_token = (
                self.encryption.decrypt(refresh_row.token_value)
                if refresh_row
                else None
            )

            return Credentials(
                token=access_token,
                refresh_token=refresh_token,
                token_uri=self.GOOGLE_TOKEN_URL,
                client_id=settings.GOOGLE_CLIENT_ID,
                client_secret=settings.GOOGLE_CLIENT_SECRET,
                scopes=self.REQUIRED_SCOPES,
            )
        except Exception as e:
            logger.error(f"Failed to construct Google credentials: {e}")
            return None

    def _validate_config(self) -> None:
        """Validate that all required Google OAuth settings are configured."""
        errors = []
        if not settings.GOOGLE_CLIENT_ID:
            errors.append("GOOGLE_CLIENT_ID not configured")
        if not settings.GOOGLE_CLIENT_SECRET:
            errors.append("GOOGLE_CLIENT_SECRET not configured")
        if not settings.OAUTH_REDIRECT_BASE_URL:
            errors.append("OAUTH_REDIRECT_BASE_URL not configured")
        if not settings.ENCRYPTION_KEY:
            errors.append("ENCRYPTION_KEY not configured")

        if errors:
            raise ValueError("Google Drive OAuth not configured: " + "; ".join(errors))
