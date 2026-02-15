"""OAuth service - handles Instagram OAuth redirect flow."""

import json
import secrets
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

import httpx
from telegram import Bot

from src.services.base_service import BaseService
from src.services.core.instagram_account_service import InstagramAccountService
from src.config.settings import settings
from src.utils.encryption import TokenEncryption
from src.utils.logger import logger


class OAuthService(BaseService):
    """
    Orchestrate the Instagram OAuth redirect flow.

    Handles:
    - Generating signed state tokens (CSRF protection)
    - Exchanging auth codes for long-lived tokens
    - Creating/updating Instagram accounts with new tokens
    - Notifying Telegram after success/failure
    """

    META_GRAPH_BASE = "https://graph.facebook.com/v18.0"
    META_OAUTH_DIALOG = "https://www.facebook.com/dialog/oauth"
    STATE_TTL_SECONDS = 600  # 10 minutes

    REQUIRED_SCOPES = [
        "instagram_basic",
        "instagram_content_publish",
        "pages_show_list",
        "pages_read_engagement",
    ]

    def __init__(self):
        super().__init__()
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
        return f"{base}/auth/instagram/callback"

    def generate_authorization_url(self, telegram_chat_id: int) -> str:
        """
        Generate the Meta OAuth authorization URL with a signed state token.

        Args:
            telegram_chat_id: The Telegram chat that initiated the flow

        Returns:
            Full Meta OAuth authorization URL

        Raises:
            ValueError: If required settings are missing
        """
        self._validate_oauth_config()

        state_token = self._create_state_token(telegram_chat_id)

        params = {
            "client_id": settings.FACEBOOK_APP_ID,
            "redirect_uri": self.redirect_uri,
            "scope": ",".join(self.REQUIRED_SCOPES),
            "response_type": "code",
            "state": state_token,
        }

        return f"{self.META_OAUTH_DIALOG}?{urlencode(params)}"

    def _create_state_token(self, telegram_chat_id: int) -> str:
        """
        Create a signed, time-limited state token.

        The token is a Fernet-encrypted JSON payload containing:
        - chat_id: The Telegram chat ID to associate the token with
        - nonce: Random value for uniqueness

        Fernet includes a timestamp, so TTL is enforced on decrypt.

        Returns:
            URL-safe base64-encoded encrypted state string
        """
        payload = json.dumps(
            {
                "chat_id": telegram_chat_id,
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
            # Use Fernet's TTL-based decrypt directly for time validation
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
        Exchange the authorization code for a long-lived token and store it.

        Flow:
        1. Exchange auth code -> short-lived token
        2. Exchange short-lived -> long-lived token (60 days)
        3. Fetch Instagram Business Account ID and username
        4. Create or update the InstagramAccount + ApiToken records
        5. Set as active account for the originating chat

        Args:
            auth_code: Authorization code from Meta callback
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
            # Step 1: Exchange code for short-lived token
            short_token = await self._exchange_code_for_token(auth_code)

            # Step 2: Exchange for long-lived token
            long_token, expires_in = await self._exchange_for_long_lived_token(
                short_token
            )

            # Step 3: Fetch Instagram account info
            account_info = await self._get_instagram_account_info(long_token)

            if not account_info:
                raise ValueError(
                    "Could not find an Instagram Business Account "
                    "linked to your Facebook Page. "
                    "Make sure your Instagram account is a Business "
                    "or Creator account linked to a Facebook Page."
                )

            # Step 4: Create or update account
            ig_account_id = account_info["id"]
            ig_username = account_info["username"]
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

            existing = self.account_service.get_account_by_instagram_id(ig_account_id)

            if existing:
                self.account_service.update_account_token(
                    instagram_account_id=ig_account_id,
                    access_token=long_token,
                    instagram_username=ig_username,
                    token_expires_at=expires_at,
                    set_as_active=True,
                    telegram_chat_id=telegram_chat_id,
                )
                logger.info(f"OAuth: Updated token for existing account @{ig_username}")
            else:
                display_name = f"@{ig_username}" if ig_username else ig_account_id
                self.account_service.add_account(
                    display_name=display_name,
                    instagram_account_id=ig_account_id,
                    instagram_username=ig_username,
                    access_token=long_token,
                    token_expires_at=expires_at,
                    set_as_active=True,
                    telegram_chat_id=telegram_chat_id,
                )
                logger.info(f"OAuth: Created new account @{ig_username}")

            result = {
                "username": ig_username or "unknown",
                "account_id": ig_account_id,
                "expires_in_days": expires_in // 86400,
            }

            self.set_result_summary(run_id, result)
            return result

    async def _exchange_code_for_token(self, auth_code: str) -> str:
        """
        Exchange authorization code for a short-lived access token.

        This is step 3 of the OAuth flow (code -> short-lived token).
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.META_GRAPH_BASE}/oauth/access_token",
                params={
                    "client_id": settings.FACEBOOK_APP_ID,
                    "client_secret": settings.FACEBOOK_APP_SECRET,
                    "redirect_uri": self.redirect_uri,
                    "code": auth_code,
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                error = response.json()
                error_msg = error.get("error", {}).get("message", "Unknown error")
                raise ValueError(f"Code exchange failed: {error_msg}")

            data = response.json()
            token = data.get("access_token")

            if not token:
                raise ValueError("No access_token in code exchange response")

            return token

    async def _exchange_for_long_lived_token(self, short_token: str) -> tuple[str, int]:
        """
        Exchange short-lived token for long-lived token (60 days).

        Returns:
            Tuple of (long_lived_token, expires_in_seconds)
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.META_GRAPH_BASE}/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": settings.FACEBOOK_APP_ID,
                    "client_secret": settings.FACEBOOK_APP_SECRET,
                    "fb_exchange_token": short_token,
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                error = response.json()
                error_msg = error.get("error", {}).get("message", "Unknown error")
                raise ValueError(f"Long-lived token exchange failed: {error_msg}")

            data = response.json()
            return (
                data.get("access_token"),
                data.get("expires_in", 5184000),  # Default 60 days
            )

    async def _get_instagram_account_info(self, token: str) -> Optional[dict]:
        """
        Fetch the Instagram Business Account ID and username.

        Traverses: token -> Facebook Pages -> Instagram Business Account.

        Returns:
            dict with 'id' and 'username', or None if not found
        """
        async with httpx.AsyncClient() as client:
            # Get Facebook Pages
            pages_resp = await client.get(
                f"{self.META_GRAPH_BASE}/me/accounts",
                params={"access_token": token},
                timeout=30.0,
            )

            if pages_resp.status_code != 200:
                logger.error(f"Failed to fetch Facebook Pages: {pages_resp.text}")
                return None

            pages = pages_resp.json().get("data", [])
            if not pages:
                logger.warning("No Facebook Pages found for this token")
                return None

            # Get Instagram account linked to the first page
            page_id = pages[0]["id"]
            ig_resp = await client.get(
                f"{self.META_GRAPH_BASE}/{page_id}",
                params={
                    "fields": "instagram_business_account",
                    "access_token": token,
                },
                timeout=30.0,
            )

            if ig_resp.status_code != 200:
                return None

            ig_account = ig_resp.json().get("instagram_business_account")
            if not ig_account:
                return None

            ig_account_id = ig_account["id"]

            # Get username
            username_resp = await client.get(
                f"{self.META_GRAPH_BASE}/{ig_account_id}",
                params={
                    "fields": "username",
                    "access_token": token,
                },
                timeout=30.0,
            )

            username = "unknown"
            if username_resp.status_code == 200:
                username = username_resp.json().get("username", "unknown")

            return {"id": ig_account_id, "username": username}

    async def notify_telegram(
        self, chat_id: int, message: str, success: bool = True
    ) -> None:
        """
        Send a notification message to the Telegram chat.

        Args:
            chat_id: Telegram chat to notify
            message: Message text
            success: Whether this is a success or error notification
        """
        try:
            bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
            emoji = "\U0001f4f8" if success else "\u26a0\ufe0f"
            full_message = f"{emoji} *Instagram OAuth*\n\n{message}"
            await bot.send_message(
                chat_id=chat_id,
                text=full_message,
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Failed to send OAuth notification to chat {chat_id}: {e}")

    def _validate_oauth_config(self) -> None:
        """Validate that all required OAuth settings are configured."""
        errors = []
        if not settings.FACEBOOK_APP_ID:
            errors.append("FACEBOOK_APP_ID not configured")
        if not settings.FACEBOOK_APP_SECRET:
            errors.append("FACEBOOK_APP_SECRET not configured")
        if not settings.OAUTH_REDIRECT_BASE_URL:
            errors.append("OAUTH_REDIRECT_BASE_URL not configured")
        if not settings.ENCRYPTION_KEY:
            errors.append("ENCRYPTION_KEY not configured")

        if errors:
            raise ValueError("OAuth not configured: " + "; ".join(errors))
