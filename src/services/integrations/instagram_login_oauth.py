"""Instagram Login OAuth service — handles the newer Instagram Login flow.

This service implements the "Instagram API with Instagram Login" OAuth flow,
which does NOT require users to have a Facebook Page linked to their account.
It uses instagram_business_basic + instagram_business_content_publish scopes.

This is separate from OAuthService (Facebook Login) and coexists alongside it.
"""

import json
import secrets
from datetime import datetime, timedelta
from typing import Optional

import httpx

from src.config.constants import IG_LOGIN_API_BASE, IG_LOGIN_GRAPH_BASE
from telegram import Bot

from src.config.settings import settings
from src.models.instagram_account import AUTH_METHOD_INSTAGRAM_LOGIN
from src.repositories.chat_settings_repository import ChatSettingsRepository
from src.services.base_service import BaseService
from src.services.core.instagram_account_service import InstagramAccountService
from src.utils.encryption import TokenEncryption
from src.utils.logger import logger


class InstagramLoginOAuthService(BaseService):
    """Orchestrate the Instagram Login OAuth redirect flow.

    Handles:
    - Generating signed state tokens (Fernet, same as Google Drive OAuth)
    - Exchanging auth codes for short-lived then long-lived tokens
    - Fetching Instagram user info (user_id returned in token exchange)
    - Creating/updating Instagram accounts with new tokens
    - Notifying Telegram after success/failure
    """

    INSTAGRAM_AUTH_URL = f"{IG_LOGIN_API_BASE}/oauth/authorize"
    INSTAGRAM_TOKEN_URL = f"{IG_LOGIN_API_BASE}/oauth/access_token"
    INSTAGRAM_LONG_LIVED_URL = f"{IG_LOGIN_GRAPH_BASE}/access_token"
    INSTAGRAM_USER_URL = f"{IG_LOGIN_GRAPH_BASE}/me"
    STATE_TTL_SECONDS = 600  # 10 minutes

    REQUIRED_SCOPES = [
        "instagram_business_basic",
        "instagram_business_content_publish",
    ]

    def __init__(self):
        super().__init__()
        self.settings_repo = ChatSettingsRepository()
        self.account_service = InstagramAccountService()
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
        return f"{base}/auth/instagram-login/callback"

    def generate_authorization_url(self, telegram_chat_id: int) -> str:
        """Generate the Instagram Login OAuth authorization URL.

        Args:
            telegram_chat_id: The Telegram chat that initiated the flow

        Returns:
            Full Instagram OAuth authorization URL

        Raises:
            ValueError: If required settings are missing
        """
        self._validate_config()

        state_token = self._create_state_token(telegram_chat_id)

        params = {
            "client_id": settings.INSTAGRAM_APP_ID,
            "redirect_uri": self.redirect_uri,
            "scope": ",".join(self.REQUIRED_SCOPES),
            "response_type": "code",
            "state": state_token,
        }

        from urllib.parse import urlencode

        return f"{self.INSTAGRAM_AUTH_URL}?{urlencode(params)}"

    def _create_state_token(self, telegram_chat_id: int) -> str:
        """Create a signed, time-limited state token."""
        payload = json.dumps(
            {
                "chat_id": telegram_chat_id,
                "provider": "instagram_login",
                "nonce": secrets.token_hex(16),
            }
        )
        return self.encryption.encrypt(payload)

    def validate_state_token(self, state: str) -> int:
        """Validate a state token and extract the Telegram chat ID.

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
        """Exchange the authorization code for tokens and store them.

        Flow:
        1. Exchange auth code → short-lived token + user_id
        2. Exchange short-lived → long-lived token (60 days)
        3. Fetch Instagram username
        4. Create or update InstagramAccount + ApiToken records
        5. Set as active account for the originating chat

        Args:
            auth_code: Authorization code from Instagram callback
            telegram_chat_id: Chat to associate the account with

        Returns:
            dict with username, account_id, expires_in_days

        Raises:
            ValueError: If exchange fails
        """
        with self.track_execution(
            method_name="exchange_and_store",
            triggered_by="user",
            input_params={"chat_id": telegram_chat_id},
        ) as run_id:
            # Strip #_ suffix from Instagram auth codes
            auth_code = auth_code.rstrip("#_")

            # Step 1: Exchange code for short-lived token + user_id
            short_token, ig_user_id = await self._exchange_code_for_token(auth_code)

            # Step 2: Exchange for long-lived token
            long_token, expires_in = await self._exchange_for_long_lived_token(
                short_token
            )

            # Step 3: Fetch username
            username = await self._get_username(long_token, ig_user_id)

            # Step 4: Create or update account
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
            existing = self.account_service.get_account_by_instagram_id(ig_user_id)

            if existing:
                self.account_service.update_account_token(
                    instagram_account_id=ig_user_id,
                    access_token=long_token,
                    instagram_username=username,
                    token_expires_at=expires_at,
                    set_as_active=True,
                    telegram_chat_id=telegram_chat_id,
                    auth_method=AUTH_METHOD_INSTAGRAM_LOGIN,
                )
                logger.info(f"Instagram Login: Updated token for @{username}")
            else:
                display_name = f"@{username}" if username else ig_user_id
                self.account_service.add_account(
                    display_name=display_name,
                    instagram_account_id=ig_user_id,
                    instagram_username=username,
                    access_token=long_token,
                    token_expires_at=expires_at,
                    set_as_active=True,
                    telegram_chat_id=telegram_chat_id,
                    auth_method=AUTH_METHOD_INSTAGRAM_LOGIN,
                )
                logger.info(f"Instagram Login: Created new account @{username}")

            result = {
                "username": username or "unknown",
                "account_id": ig_user_id,
                "expires_in_days": expires_in // 86400,
            }

            self.set_result_summary(run_id, result)
            return result

    async def _exchange_code_for_token(self, auth_code: str) -> tuple[str, str]:
        """Exchange authorization code for short-lived token + user_id.

        Instagram Login returns the token in a data array with user_id.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.INSTAGRAM_TOKEN_URL,
                data={
                    "client_id": settings.INSTAGRAM_APP_ID,
                    "client_secret": settings.INSTAGRAM_APP_SECRET,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri,
                    "code": auth_code,
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                error = response.json()
                error_msg = error.get("error_message", str(error))
                raise ValueError(f"Code exchange failed: {error_msg}")

            data = response.json()

            # Instagram Login wraps response in a data array
            if "data" in data and isinstance(data["data"], list):
                token_data = data["data"][0]
            else:
                token_data = data

            token = token_data.get("access_token")
            user_id = str(token_data.get("user_id", ""))

            if not token:
                raise ValueError("No access_token in code exchange response")
            if not user_id:
                raise ValueError("No user_id in code exchange response")

            return token, user_id

    async def _exchange_for_long_lived_token(self, short_token: str) -> tuple[str, int]:
        """Exchange short-lived token for long-lived token (60 days)."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.INSTAGRAM_LONG_LIVED_URL,
                params={
                    "grant_type": "ig_exchange_token",
                    "client_secret": settings.INSTAGRAM_APP_SECRET,
                    "access_token": short_token,
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                error = response.json()
                error_msg = error.get("error", {}).get("message", str(error))
                raise ValueError(f"Long-lived token exchange failed: {error_msg}")

            data = response.json()
            token = data.get("access_token")
            expires_in = data.get("expires_in", 5184000)  # 60 days default

            if not token:
                raise ValueError("No access_token in long-lived exchange response")

            return token, expires_in

    async def _get_username(self, token: str, user_id: str) -> Optional[str]:
        """Fetch the Instagram username for a user."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.INSTAGRAM_USER_URL}",
                    params={
                        "fields": "username",
                        "access_token": token,
                    },
                    timeout=15.0,
                )
                if response.status_code == 200:
                    return response.json().get("username")
        except httpx.HTTPError as e:
            logger.warning(f"Failed to fetch Instagram username: {e}")
        return None

    async def notify_telegram(
        self, chat_id: int, message: str, success: bool = True
    ) -> None:
        """Send a notification message to the Telegram chat."""
        try:
            bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
            emoji = "\U0001f4f8" if success else "\u26a0\ufe0f"
            full_message = f"{emoji} *Instagram Login*\n\n{message}"
            await bot.send_message(
                chat_id=chat_id,
                text=full_message,
                parse_mode="Markdown",
            )
        except Exception as e:  # noqa: BLE001 — best-effort notification, swallow all errors
            logger.error(
                f"Failed to send Instagram Login notification to chat {chat_id}: {e}"
            )

    def _validate_config(self) -> None:
        """Validate that all required Instagram Login settings are configured."""
        errors = []
        if not settings.INSTAGRAM_APP_ID:
            errors.append("INSTAGRAM_APP_ID not configured")
        if not settings.INSTAGRAM_APP_SECRET:
            errors.append("INSTAGRAM_APP_SECRET not configured")
        if not settings.OAUTH_REDIRECT_BASE_URL:
            errors.append("OAUTH_REDIRECT_BASE_URL not configured")
        if not settings.ENCRYPTION_KEY:
            errors.append("ENCRYPTION_KEY not configured")

        if errors:
            raise ValueError(
                "Instagram Login OAuth not configured: " + "; ".join(errors)
            )
