# Phase 04: Instagram OAuth Redirect Flow

**Status:** 🔧 IN PROGRESS
**Started:** 2026-02-15
**Risk:** Medium
**Effort:** 4-5 hours
**PR Title:** `feat: Instagram OAuth redirect flow for self-service account connection`

## 1. Overview

This phase replaces the manual CLI-based Instagram authentication (copy-paste token from Graph API Explorer) with a browser-based OAuth redirect flow. The user initiates the flow from Telegram, completes Meta authorization in a browser, and the system automatically exchanges the code for a long-lived token, stores it, and confirms back via Telegram.

## 2. Current State Analysis

### What exists today

**Manual CLI flow** (`/Users/chris/Projects/storyline-ai/cli/commands/instagram.py`):
- `instagram-auth` command opens Graph API Explorer in the browser
- User manually copies a short-lived token, pastes it into the terminal
- CLI calls `_exchange_for_long_lived_token()` to convert short-lived to long-lived token via `https://graph.facebook.com/v18.0/oauth/access_token?grant_type=fb_exchange_token`
- CLI calls `_get_instagram_account_id()` to fetch the IG Business Account ID from pages
- CLI calls `_store_token()` which encrypts and stores via `TokenRepository.create_or_update()`

**Token infrastructure** (`/Users/chris/Projects/storyline-ai/src/services/integrations/token_refresh.py`):
- `TokenRefreshService` handles token retrieval, refresh, bootstrap from .env
- Uses `ig_refresh_token` grant type for refreshing existing long-lived tokens
- Multi-account support via `instagram_account_id` FK on `api_tokens`

**Account management** (`/Users/chris/Projects/storyline-ai/src/services/core/instagram_account_service.py`):
- `InstagramAccountService.add_account()` creates an `InstagramAccount` record and stores an encrypted token
- `InstagramAccountService.update_account_token()` re-authenticates an existing account with a new token
- Three-table pattern: `instagram_accounts` (identity), `api_tokens` (credentials), `chat_settings` (selection)

**No API layer exists** -- there is no `src/api/` directory. The CLAUDE.md architecture diagram references `src/api/` as part of "Phase 2.5" but it has not been implemented yet.

### Key settings already in `/Users/chris/Projects/storyline-ai/src/config/settings.py`
- `FACEBOOK_APP_ID` -- already defined (Optional[str], default None)
- `FACEBOOK_APP_SECRET` -- already defined (Optional[str], default None)
- `ENCRYPTION_KEY` -- already defined (Optional[str], default None)
- Missing: `OAUTH_REDIRECT_BASE_URL` -- needs to be added

### Dependencies already available
- `httpx` -- already in requirements.txt (0.28.1)
- `cryptography` -- already in requirements.txt (Fernet encryption)
- Missing: `fastapi` and `uvicorn` -- **not** in requirements.txt. Need to add these.

## 3. Architecture Decisions

### 3.1 Minimal FastAPI Server for OAuth Only

Rather than building the full Phase 2.5 API layer, this phase introduces a minimal FastAPI app with only two endpoints (`/auth/instagram/start` and `/auth/instagram/callback`). This keeps scope tight and avoids premature architecture.

The FastAPI app will live at `src/api/app.py` and use the same database and service patterns as the rest of the system. It can be run standalone via `uvicorn` alongside the main Telegram bot process, or composed into `src/main.py` later.

### 3.2 State Token Design

The OAuth `state` parameter must:
1. Encode `telegram_chat_id` so the callback knows which tenant to associate
2. Be cryptographically signed to prevent CSRF
3. Have a 10-minute TTL

Approach: Use the existing `ENCRYPTION_KEY` (Fernet) to create a time-limited encrypted payload. Fernet already includes timestamp-based TTL validation via `decrypt(token, ttl=600)`. The payload is `{"chat_id": <int>, "nonce": <random_hex>}`.

### 3.3 Token Exchange Strategy

The OAuth code-to-token flow has two steps (per Meta's docs):
1. Exchange auth code for a **short-lived** token via `POST https://graph.facebook.com/v18.0/oauth/access_token`
2. Exchange short-lived token for a **long-lived** token (60 days) via `GET https://graph.facebook.com/v18.0/oauth/access_token?grant_type=fb_exchange_token`

This is exactly what the existing CLI `_exchange_for_long_lived_token()` does for step 2, and the existing `_get_instagram_account_id()` does for fetching account info. The new OAuth service will reuse this logic.

### 3.4 Integration with Existing Account System

After getting the long-lived token and account info, the OAuth callback should:
- If the Instagram account already exists in `instagram_accounts`: call `InstagramAccountService.update_account_token()` to refresh its token
- If the Instagram account is new: call `InstagramAccountService.add_account()` to create it
- In both cases, set the account as active for the chat that initiated the flow

## 4. Files to Create

### 4.1 `src/api/__init__.py` -- Empty init

### 4.2 `src/api/app.py` -- FastAPI Application

Minimal FastAPI app with CORS and two OAuth routes.

```python
"""FastAPI application for Storyline AI OAuth flows."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes.oauth import router as oauth_router

app = FastAPI(
    title="Storyline AI API",
    description="OAuth and API endpoints for Storyline AI",
    version="0.1.0",
)

# CORS middleware (needed for Telegram WebApp or browser redirects)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Register routes
app.include_router(oauth_router, prefix="/auth")
```

### 4.3 `src/api/routes/__init__.py` -- Empty init

### 4.4 `src/api/routes/oauth.py` -- OAuth Route Handlers

```python
"""Instagram OAuth redirect flow endpoints."""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from src.services.core.oauth_service import OAuthService
from src.utils.logger import logger

router = APIRouter(tags=["oauth"])


@router.get("/instagram/start")
async def instagram_oauth_start(
    chat_id: int = Query(..., description="Telegram chat ID initiating the flow"),
):
    """
    Generate Instagram OAuth authorization URL.

    Called when user clicks "Connect Instagram" in Telegram.
    Returns a redirect to Meta's authorization page.
    """
    oauth_service = OAuthService()
    try:
        auth_url = oauth_service.generate_authorization_url(chat_id)
        return RedirectResponse(url=auth_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        oauth_service.close()


@router.get("/instagram/callback")
async def instagram_oauth_callback(
    code: str = Query(None, description="Authorization code from Meta"),
    state: str = Query(..., description="Signed state token"),
    error: str = Query(None, description="Error code if user denied"),
    error_reason: str = Query(None, description="Error reason"),
    error_description: str = Query(None, description="Human-readable error"),
):
    """
    Handle Instagram OAuth callback.

    Meta redirects here after user authorizes (or denies).
    Exchanges the code for a long-lived token, stores it,
    and notifies the user in Telegram.
    """
    oauth_service = OAuthService()
    try:
        # Handle user denial
        if error:
            logger.warning(
                f"OAuth denied: {error} - {error_reason} - {error_description}"
            )
            # Validate state to get chat_id for notification
            try:
                chat_id = oauth_service.validate_state_token(state)
                await oauth_service.notify_telegram(
                    chat_id,
                    f"Instagram connection cancelled.\n"
                    f"Reason: {error_description or error_reason or error}",
                    success=False,
                )
            except ValueError:
                pass  # Can't notify if state is invalid
            return _error_html_page(
                "Connection Cancelled",
                "You cancelled the Instagram connection. "
                "You can try again from Telegram.",
            )

        if not code:
            raise HTTPException(status_code=400, detail="Missing authorization code")

        # Validate state token (CSRF protection + extract chat_id)
        try:
            chat_id = oauth_service.validate_state_token(state)
        except ValueError as e:
            logger.error(f"Invalid OAuth state: {e}")
            return _error_html_page(
                "Link Expired",
                "This authorization link has expired or is invalid. "
                "Please request a new one from Telegram.",
            )

        # Exchange code for tokens and store
        result = await oauth_service.exchange_and_store(code, chat_id)

        # Notify Telegram
        await oauth_service.notify_telegram(
            chat_id,
            f"Instagram connected! Account: @{result['username']}\n"
            f"Token valid for {result['expires_in_days']} days.",
            success=True,
        )

        return _success_html_page(result["username"])

    except Exception as e:
        logger.error(f"OAuth callback error: {e}", exc_info=True)
        return _error_html_page(
            "Connection Failed",
            "Something went wrong connecting your Instagram account. "
            "Please try again from Telegram.",
        )
    finally:
        oauth_service.close()


def _success_html_page(username: str) -> HTMLResponse:
    """Return a simple HTML success page."""
    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
        <head><title>Storyline AI - Connected!</title>
        <style>
            body {{ font-family: -apple-system, sans-serif; text-align: center;
                   padding: 60px 20px; background: #f5f5f5; }}
            .card {{ background: white; border-radius: 12px; padding: 40px;
                    max-width: 400px; margin: 0 auto; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
            h1 {{ color: #22c55e; }}
            p {{ color: #666; }}
        </style></head>
        <body>
        <div class="card">
            <h1>Connected!</h1>
            <p>Instagram account <strong>@{username}</strong> has been
            connected to Storyline AI.</p>
            <p>You can close this window and return to Telegram.</p>
        </div>
        </body></html>
        """,
        status_code=200,
    )


def _error_html_page(title: str, message: str) -> HTMLResponse:
    """Return a simple HTML error page."""
    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
        <head><title>Storyline AI - {title}</title>
        <style>
            body {{ font-family: -apple-system, sans-serif; text-align: center;
                   padding: 60px 20px; background: #f5f5f5; }}
            .card {{ background: white; border-radius: 12px; padding: 40px;
                    max-width: 400px; margin: 0 auto; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
            h1 {{ color: #ef4444; }}
            p {{ color: #666; }}
        </style></head>
        <body>
        <div class="card">
            <h1>{title}</h1>
            <p>{message}</p>
        </div>
        </body></html>
        """,
        status_code=200,
    )
```

### 4.5 `src/services/core/oauth_service.py` -- OAuth Business Logic

This is the core service that handles state generation, token exchange, account storage, and Telegram notification.

```python
"""OAuth service - handles Instagram OAuth redirect flow."""

import json
import secrets
from datetime import datetime, timedelta
from typing import Optional

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

    This service reuses the same token exchange logic
    as the CLI instagram-auth command but automates
    the browser redirect flow.
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

        # Build URL with query parameters (urlencode handles redirect_uri safely)
        from urllib.parse import urlencode
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
        payload = json.dumps({
            "chat_id": telegram_chat_id,
            "nonce": secrets.token_hex(16),
        })
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
            # Fernet decrypt with TTL validation
            # TokenEncryption wraps Fernet, but we need TTL support
            # so we access the cipher directly
            decrypted_bytes = self.encryption._cipher.decrypt(
                state.encode(),
                ttl=self.STATE_TTL_SECONDS,
            )
            payload = json.loads(decrypted_bytes.decode())
            chat_id = payload.get("chat_id")

            if not chat_id or not isinstance(chat_id, int):
                raise ValueError("Invalid payload: missing chat_id")

            return chat_id

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

            # Check if account already exists
            existing = self.account_service.get_account_by_instagram_id(ig_account_id)

            if existing:
                # Update token for existing account
                self.account_service.update_account_token(
                    instagram_account_id=ig_account_id,
                    access_token=long_token,
                    instagram_username=ig_username,
                    token_expires_at=expires_at,
                    set_as_active=True,
                    telegram_chat_id=telegram_chat_id,
                )
                logger.info(
                    f"OAuth: Updated token for existing account @{ig_username}"
                )
            else:
                # Create new account
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

    async def _exchange_for_long_lived_token(
        self, short_token: str
    ) -> tuple[str, int]:
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
            emoji = "connected!" if success else "connection issue"
            full_message = (
                f"{'📸' if success else '⚠️'} *Instagram OAuth*\n\n{message}"
            )
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
            raise ValueError(
                "OAuth not configured: " + "; ".join(errors)
            )
```

### 4.6 `src/api/routes/__init__.py` -- Empty init

### 4.7 `tests/src/services/test_oauth_service.py` -- Unit Tests

### 4.8 `tests/src/api/__init__.py` -- Empty init

### 4.9 `tests/src/api/test_oauth_routes.py` -- Route Tests

## 5. Files to Modify

### 5.1 `src/config/settings.py`

Add one new setting:

```python
# OAuth Configuration (Phase 04)
OAUTH_REDIRECT_BASE_URL: Optional[str] = None  # e.g., "https://api.storyline.ai"
```

This is placed after the existing `FACEBOOK_APP_SECRET` line (line 48). The `Optional[str] = None` pattern matches the existing Instagram settings.

### 5.2 `requirements.txt`

Add FastAPI and uvicorn:

```
# API Server (Phase 04 OAuth)
fastapi>=0.109.0
uvicorn>=0.27.0
```

### 5.3 `src/services/core/telegram_commands.py`

Add a `/connect` command handler that generates the OAuth link and sends it to the user.

Inside the `TelegramCommandHandlers` class, add:

```python
async def handle_connect(self, update, context):
    """Handle /connect command - generate Instagram OAuth link."""
    user = self.service._get_or_create_user(update.effective_user)
    chat_id = update.effective_chat.id

    from src.services.core.oauth_service import OAuthService

    oauth_service = OAuthService()
    try:
        auth_url = oauth_service.generate_authorization_url(chat_id)

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Connect Instagram", url=auth_url)]
        ])

        await update.message.reply_text(
            "📸 *Connect Instagram Account*\n\n"
            "Click the button below to authorize Storyline AI "
            "to post Stories on your behalf.\n\n"
            "_This link expires in 10 minutes._",
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
    except ValueError as e:
        await update.message.reply_text(
            f"⚠️ OAuth not configured: {e}\n\n"
            "Contact your admin to set up FACEBOOK_APP_ID, "
            "FACEBOOK_APP_SECRET, and OAUTH_REDIRECT_BASE_URL.",
        )
    finally:
        oauth_service.close()

    self.service.interaction_service.log_command(
        user_id=str(user.id),
        command="/connect",
        telegram_chat_id=chat_id,
        telegram_message_id=update.message.message_id,
    )
```

### 5.4 `src/services/core/telegram_service.py`

Register the new `/connect` command in `initialize()`:

In the `command_map` dict (around line 124), add:
```python
"connect": self.commands.handle_connect,
```

In the `commands` list for Telegram autocomplete (around line 156), add:
```python
BotCommand("connect", "Connect an Instagram account via OAuth"),
```

### 5.5 `src/services/core/instagram_account_service.py`

The `add_account()` method currently expects an **already encrypted** `access_token`. The OAuth service will pass a **plaintext** token (the service handles encryption internally). Looking at the code more carefully:

In `_create_account_with_token()` (line 243), the method calls `self.encryption.encrypt(access_token)`. But in the CLI `add_instagram_account` command (line 452), the token is encrypted **before** calling `service.add_account()`. This means `add_account()` receives a pre-encrypted token and then encrypts it again -- this is a latent bug.

Looking at the CLI code on line 452: `encrypted_token = encryption.encrypt(access_token)` and then on line 465: `access_token=encrypted_token`. Then inside `_create_account_with_token()` on line 262: `encrypted_token = self.encryption.encrypt(access_token)` -- so it double-encrypts.

**This is an existing bug** that needs to be documented and handled. For the OAuth flow, the `OAuthService` should pass the **plaintext** token directly to `add_account()` / `update_account_token()`, which is the correct behavior since the service layer handles encryption.

For `update_account_token()` (line 370), the method also calls `self.encryption.encrypt(access_token)`, which is correct for plaintext input.

**Action for this phase**: The OAuth service passes plaintext tokens to `InstagramAccountService`. No changes needed to `InstagramAccountService` itself for the OAuth flow. The CLI double-encryption bug should be documented as a separate fix item.

### 5.6 `CHANGELOG.md`

Add entries under `## [Unreleased]` for the new OAuth flow.

## 6. State Token Implementation Detail

The state token leverages Fernet's built-in timestamp. Here is how the flow works:

```
State creation:
  payload = {"chat_id": -1001234567890, "nonce": "a7b3c9d2e1f0..."}
  state = Fernet.encrypt(json.dumps(payload).encode())
  # Fernet prepends: version (1 byte) + timestamp (8 bytes) + IV (16 bytes)
  # Result is URL-safe base64 string

State validation (in callback):
  decrypted = Fernet.decrypt(state.encode(), ttl=600)
  # Fernet checks: timestamp + 600s > now? If not, raises InvalidToken
  # If valid: parse JSON, extract chat_id
```

The `nonce` field prevents replay attacks -- even if two users from the same chat both start OAuth flows, each state token is unique.

**Important**: The `TokenEncryption.decrypt()` method does not support TTL. The `validate_state_token()` method accesses `self.encryption._cipher` directly to use Fernet's `decrypt(token, ttl=...)`. This is acceptable because `_cipher` is the Fernet instance and the TTL feature is a core Fernet capability.

## 7. Token Exchange Sequence

```
User in Telegram                     FastAPI Server                    Meta/Facebook
       |                                   |                                |
       | /connect                          |                                |
       |---------------------------------->|                                |
       | "Click here to connect"           |                                |
       |<-- InlineButton(url=auth_url) ----|                                |
       |                                   |                                |
       | [clicks button, browser opens]    |                                |
       |--------------------------------------------------------->          |
       |                               Meta OAuth dialog                    |
       |                               [User authorizes app]               |
       |                                   |                                |
       |         302 redirect to /auth/instagram/callback?code=XXX&state=YYY|
       |                                   |<-------------------------------|
       |                                   |                                |
       |                                   | validate_state_token(state)    |
       |                                   | extract chat_id                |
       |                                   |                                |
       |                                   | POST /oauth/access_token       |
       |                                   | (code -> short-lived token)    |
       |                                   |------------------------------->|
       |                                   |<------- short_lived_token -----|
       |                                   |                                |
       |                                   | GET /oauth/access_token        |
       |                                   | (short -> long-lived token)    |
       |                                   |------------------------------->|
       |                                   |<------- long_lived_token ------|
       |                                   |                                |
       |                                   | GET /me/accounts               |
       |                                   | (get Facebook Pages)           |
       |                                   |------------------------------->|
       |                                   |<------- page_id --------------|
       |                                   |                                |
       |                                   | GET /{page_id}?fields=ig_biz  |
       |                                   |------------------------------->|
       |                                   |<------- ig_account_id --------|
       |                                   |                                |
       |                                   | GET /{ig_id}?fields=username   |
       |                                   |------------------------------->|
       |                                   |<------- username -------------|
       |                                   |                                |
       |                                   | store token in DB              |
       |                                   | create/update account          |
       |                                   | set as active for chat         |
       |                                   |                                |
       | Bot.send_message("Connected!")    |                                |
       |<----------------------------------|                                |
       |                                   |                                |
       | Browser shows success page        |                                |
       |<----------------------------------|                                |
```

## 8. Test Plan

### 8.1 Unit Tests for `OAuthService` (`tests/src/services/test_oauth_service.py`)

```python
"""Unit tests for OAuthService."""

import pytest
import json
import time
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from contextlib import contextmanager
import uuid

from src.services.core.oauth_service import OAuthService


@contextmanager
def mock_track_execution(*args, **kwargs):
    yield str(uuid.uuid4())


class TestStateTokenGeneration:
    """Test state token creation and validation."""

    @patch.object(OAuthService, "__init__", lambda self: None)
    def setup_method(self):
        """Set up test fixtures."""
        self.service = OAuthService()
        self.service.service_run_repo = Mock()
        self.service.service_name = "OAuthService"
        self.service.account_service = Mock()
        self.service._encryption = None

    @patch("src.services.core.oauth_service.TokenEncryption")
    def test_create_state_token_encrypts_chat_id(self, MockEncryption):
        """State token contains chat_id in encrypted payload."""
        mock_cipher = MagicMock()
        mock_cipher.encrypt.return_value = b"encrypted_state_bytes"
        mock_encryption = MockEncryption.return_value
        mock_encryption._cipher = mock_cipher
        mock_encryption.encrypt.return_value = "encrypted_state"
        self.service._encryption = mock_encryption

        result = self.service._create_state_token(chat_id=-1001234567890)

        assert result == "encrypted_state"
        # Verify encrypt was called with JSON containing chat_id
        call_args = mock_encryption.encrypt.call_args[0][0]
        payload = json.loads(call_args)
        assert payload["chat_id"] == -1001234567890
        assert "nonce" in payload

    @patch("src.services.core.oauth_service.TokenEncryption")
    def test_validate_state_token_returns_chat_id(self, MockEncryption):
        """Valid state token returns the embedded chat_id."""
        mock_cipher = MagicMock()
        payload = json.dumps({"chat_id": -1001234567890, "nonce": "abc123"})
        mock_cipher.decrypt.return_value = payload.encode()

        mock_encryption = MockEncryption.return_value
        mock_encryption._cipher = mock_cipher
        self.service._encryption = mock_encryption

        result = self.service.validate_state_token("some_state")

        assert result == -1001234567890
        mock_cipher.decrypt.assert_called_once()
        # Verify TTL was passed
        _, kwargs = mock_cipher.decrypt.call_args
        assert kwargs["ttl"] == 600

    @patch("src.services.core.oauth_service.TokenEncryption")
    def test_validate_state_token_expired_raises(self, MockEncryption):
        """Expired state token raises ValueError."""
        from cryptography.fernet import InvalidToken

        mock_cipher = MagicMock()
        mock_cipher.decrypt.side_effect = InvalidToken()

        mock_encryption = MockEncryption.return_value
        mock_encryption._cipher = mock_cipher
        self.service._encryption = mock_encryption

        with pytest.raises(ValueError, match="Invalid or expired"):
            self.service.validate_state_token("expired_state")

    @patch("src.services.core.oauth_service.TokenEncryption")
    def test_validate_state_token_invalid_payload_raises(self, MockEncryption):
        """State token with missing chat_id raises ValueError."""
        mock_cipher = MagicMock()
        mock_cipher.decrypt.return_value = json.dumps({"nonce": "abc"}).encode()

        mock_encryption = MockEncryption.return_value
        mock_encryption._cipher = mock_cipher
        self.service._encryption = mock_encryption

        with pytest.raises(ValueError, match="Invalid payload"):
            self.service.validate_state_token("bad_state")


class TestGenerateAuthorizationUrl:
    """Test authorization URL generation."""

    @patch.object(OAuthService, "__init__", lambda self: None)
    def setup_method(self):
        self.service = OAuthService()
        self.service.service_run_repo = Mock()
        self.service.service_name = "OAuthService"
        self.service.account_service = Mock()
        self.service._encryption = None

    @patch("src.services.core.oauth_service.settings")
    @patch("src.services.core.oauth_service.TokenEncryption")
    def test_generate_url_includes_required_params(self, MockEncryption, mock_settings):
        mock_settings.FACEBOOK_APP_ID = "test_app_id"
        mock_settings.FACEBOOK_APP_SECRET = "test_secret"
        mock_settings.OAUTH_REDIRECT_BASE_URL = "https://api.example.com"
        mock_settings.ENCRYPTION_KEY = "test_key"

        mock_encryption = MockEncryption.return_value
        mock_encryption.encrypt.return_value = "encrypted_state"
        mock_encryption._cipher = MagicMock()
        self.service._encryption = mock_encryption

        url = self.service.generate_authorization_url(-1001234567890)

        assert "client_id=test_app_id" in url
        assert "redirect_uri=" in url
        assert "instagram_basic" in url
        assert "state=encrypted_state" in url
        assert "response_type=code" in url

    @patch("src.services.core.oauth_service.settings")
    def test_generate_url_missing_config_raises(self, mock_settings):
        mock_settings.FACEBOOK_APP_ID = None
        mock_settings.FACEBOOK_APP_SECRET = None
        mock_settings.OAUTH_REDIRECT_BASE_URL = None
        mock_settings.ENCRYPTION_KEY = None

        with pytest.raises(ValueError, match="OAuth not configured"):
            self.service.generate_authorization_url(-1001234567890)


class TestExchangeAndStore:
    """Test the full exchange + store flow."""

    @pytest.fixture
    def service(self):
        with patch.object(OAuthService, "__init__", lambda self: None):
            svc = OAuthService()
            svc.service_run_repo = Mock()
            svc.service_name = "OAuthService"
            svc.account_service = Mock()
            svc._encryption = Mock()
            svc.track_execution = mock_track_execution
            svc.set_result_summary = Mock()
            return svc

    @pytest.mark.asyncio
    async def test_exchange_new_account_creates_it(self, service):
        """When Instagram account is new, add_account is called."""
        service.account_service.get_account_by_instagram_id.return_value = None
        service.account_service.add_account.return_value = Mock()

        with patch.object(
            service, "_exchange_code_for_token", new_callable=AsyncMock
        ) as mock_code:
            mock_code.return_value = "short_token"

            with patch.object(
                service, "_exchange_for_long_lived_token", new_callable=AsyncMock
            ) as mock_long:
                mock_long.return_value = ("long_token", 5184000)

                with patch.object(
                    service, "_get_instagram_account_info", new_callable=AsyncMock
                ) as mock_info:
                    mock_info.return_value = {
                        "id": "17841234567890",
                        "username": "testuser",
                    }

                    result = await service.exchange_and_store("auth_code", -100123)

        assert result["username"] == "testuser"
        assert result["expires_in_days"] == 60
        service.account_service.add_account.assert_called_once()

    @pytest.mark.asyncio
    async def test_exchange_existing_account_updates_token(self, service):
        """When Instagram account exists, update_account_token is called."""
        existing = Mock()
        service.account_service.get_account_by_instagram_id.return_value = existing
        service.account_service.update_account_token.return_value = existing

        with patch.object(
            service, "_exchange_code_for_token", new_callable=AsyncMock
        ) as mock_code:
            mock_code.return_value = "short_token"

            with patch.object(
                service, "_exchange_for_long_lived_token", new_callable=AsyncMock
            ) as mock_long:
                mock_long.return_value = ("long_token", 5184000)

                with patch.object(
                    service, "_get_instagram_account_info", new_callable=AsyncMock
                ) as mock_info:
                    mock_info.return_value = {
                        "id": "17841234567890",
                        "username": "testuser",
                    }

                    result = await service.exchange_and_store("auth_code", -100123)

        service.account_service.update_account_token.assert_called_once()
        service.account_service.add_account.assert_not_called()

    @pytest.mark.asyncio
    async def test_exchange_no_ig_account_raises(self, service):
        """When no IG business account found, raises ValueError."""
        with patch.object(
            service, "_exchange_code_for_token", new_callable=AsyncMock
        ) as mock_code:
            mock_code.return_value = "short_token"

            with patch.object(
                service, "_exchange_for_long_lived_token", new_callable=AsyncMock
            ) as mock_long:
                mock_long.return_value = ("long_token", 5184000)

                with patch.object(
                    service, "_get_instagram_account_info", new_callable=AsyncMock
                ) as mock_info:
                    mock_info.return_value = None

                    with pytest.raises(ValueError, match="Could not find"):
                        await service.exchange_and_store("auth_code", -100123)
```

### 8.2 Route Tests (`tests/src/api/test_oauth_routes.py`)

Use FastAPI's `TestClient` to test the endpoints.

```python
"""Unit tests for OAuth API routes."""

import pytest
from unittest.mock import patch, AsyncMock, Mock, MagicMock

from fastapi.testclient import TestClient

from src.api.app import app


@pytest.fixture
def client():
    return TestClient(app)


class TestOAuthStartEndpoint:

    def test_start_redirects_to_meta(self, client):
        """GET /auth/instagram/start redirects to Meta OAuth."""
        with patch(
            "src.api.routes.oauth.OAuthService"
        ) as MockService:
            mock_svc = MockService.return_value
            mock_svc.generate_authorization_url.return_value = (
                "https://www.facebook.com/dialog/oauth?client_id=123"
            )
            mock_svc.close = Mock()

            response = client.get(
                "/auth/instagram/start?chat_id=-1001234567890",
                follow_redirects=False,
            )

        assert response.status_code == 307  # RedirectResponse
        assert "facebook.com" in response.headers["location"]

    def test_start_missing_chat_id_returns_422(self, client):
        """GET /auth/instagram/start without chat_id returns validation error."""
        response = client.get("/auth/instagram/start")
        assert response.status_code == 422

    def test_start_invalid_config_returns_400(self, client):
        """GET /auth/instagram/start with bad config returns 400."""
        with patch(
            "src.api.routes.oauth.OAuthService"
        ) as MockService:
            mock_svc = MockService.return_value
            mock_svc.generate_authorization_url.side_effect = ValueError(
                "FACEBOOK_APP_ID not configured"
            )
            mock_svc.close = Mock()

            response = client.get(
                "/auth/instagram/start?chat_id=-1001234567890"
            )

        assert response.status_code == 400


class TestOAuthCallbackEndpoint:

    def test_callback_success_returns_html(self, client):
        """Successful callback returns HTML success page."""
        with patch(
            "src.api.routes.oauth.OAuthService"
        ) as MockService:
            mock_svc = MockService.return_value
            mock_svc.validate_state_token.return_value = -1001234567890
            mock_svc.exchange_and_store = AsyncMock(return_value={
                "username": "testuser",
                "account_id": "17841234567890",
                "expires_in_days": 60,
            })
            mock_svc.notify_telegram = AsyncMock()
            mock_svc.close = Mock()

            response = client.get(
                "/auth/instagram/callback?code=AUTH_CODE&state=VALID_STATE"
            )

        assert response.status_code == 200
        assert "testuser" in response.text
        assert "Connected" in response.text

    def test_callback_user_denied_returns_cancelled_page(self, client):
        """User denial returns cancellation HTML page."""
        with patch(
            "src.api.routes.oauth.OAuthService"
        ) as MockService:
            mock_svc = MockService.return_value
            mock_svc.validate_state_token.return_value = -1001234567890
            mock_svc.notify_telegram = AsyncMock()
            mock_svc.close = Mock()

            response = client.get(
                "/auth/instagram/callback?"
                "error=access_denied&error_reason=user_denied"
                "&error_description=User+denied&state=VALID_STATE"
            )

        assert response.status_code == 200
        assert "Cancelled" in response.text

    def test_callback_expired_state_returns_expired_page(self, client):
        """Expired state token returns link-expired HTML page."""
        with patch(
            "src.api.routes.oauth.OAuthService"
        ) as MockService:
            mock_svc = MockService.return_value
            mock_svc.validate_state_token.side_effect = ValueError("expired")
            mock_svc.close = Mock()

            response = client.get(
                "/auth/instagram/callback?code=AUTH_CODE&state=EXPIRED_STATE"
            )

        assert response.status_code == 200
        assert "Expired" in response.text
```

### 8.3 Additional Dependency for Tests

Add to `requirements.txt`:
```
# Testing (API)
httpx>=0.28.0  # Already present, also needed for TestClient
```

FastAPI's `TestClient` uses `httpx` under the hood, which is already in requirements.txt.

## 9. Deployment Notes

### Running the OAuth Server

The FastAPI server runs separately from the main Telegram bot:

```bash
# Start the OAuth API server (production)
uvicorn src.api.app:app --host 0.0.0.0 --port 8000

# Development
uvicorn src.api.app:app --reload --port 8000
```

### Future Integration with `src/main.py`

In a future phase, the FastAPI server could be co-located with the Telegram bot in `main_async()` by running uvicorn programmatically. This is **not** part of this phase.

### Meta App Configuration

In the Meta Developer Console:
1. Add `{OAUTH_REDIRECT_BASE_URL}/auth/instagram/callback` as a valid OAuth redirect URI
2. Ensure the app has `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement` permissions approved

## 10. Verification Checklist

- [x] `OAUTH_REDIRECT_BASE_URL` setting added to `Settings` class
- [x] `fastapi` and `uvicorn` added to `requirements.txt`
- [x] `src/api/app.py` creates FastAPI app with OAuth router
- [x] `GET /auth/instagram/start?chat_id=X` generates state, redirects to Meta
- [x] `GET /auth/instagram/callback?code=X&state=Y` exchanges code, stores token, notifies Telegram
- [x] State token expires after 10 minutes (Fernet TTL)
- [x] State token includes CSRF nonce
- [x] User denial at Meta is handled gracefully (error page + Telegram notification)
- [x] Expired/invalid state shows user-friendly error page
- [x] New account: `InstagramAccountService.add_account()` called, set as active
- [x] Existing account: `InstagramAccountService.update_account_token()` called, set as active
- [x] Telegram `/connect` command sends InlineKeyboardButton with OAuth link
- [x] `/connect` registered in TelegramService.initialize() command map
- [x] Success page shown in browser after callback
- [x] Telegram bot notifies chat: "Instagram connected! Account: @username"
- [x] All unit tests pass for OAuthService (state validation, token exchange, store logic)
- [x] All route tests pass for `/auth/instagram/start` and `/auth/instagram/callback`
- [x] `ruff check` and `ruff format` pass on all new/modified files
- [x] CHANGELOG.md updated

## 11. What NOT To Do

1. **Do NOT build the full Phase 2.5 API layer.** This phase adds only the OAuth endpoints. No JWT auth, no general REST API.

2. **Do NOT integrate the FastAPI server into `src/main.py`.** Keep it as a separate `uvicorn` process for now. Combining them is a future concern.

3. **Do NOT store the state token in the database.** Fernet's built-in timestamp + TTL is sufficient for CSRF protection. Database-backed state adds unnecessary complexity for a 10-minute TTL.

4. **Do NOT modify `TokenRefreshService` or `TokenRepository`.** The OAuth flow creates tokens through `InstagramAccountService`, which already delegates to `TokenRepository`. No changes needed to the token infrastructure.

5. **Do NOT change the `InstagramAccountService.add_account()` signature.** Pass plaintext tokens from OAuthService. The service handles encryption internally via `_create_account_with_token()`.

6. **Do NOT add middleware/authentication to the OAuth endpoints.** The `/start` endpoint is protected by the state token (only Telegram users with the link can use it). The `/callback` endpoint validates the cryptographic state. Adding API keys or JWT here would break the browser redirect flow.

7. **Do NOT URL-encode the Fernet state token manually.** Fernet outputs URL-safe base64, which is safe for query parameters without additional encoding.

8. **Do NOT handle multiple Facebook Pages.** The current implementation (matching the CLI) uses the first page returned by `/me/accounts`. Multi-page support is a future enhancement.

9. **Do NOT post to Instagram or modify the posting queue.** This phase only handles authentication. It is purely about connecting accounts.

## 12. Implementation Sequence

1. Add `OAUTH_REDIRECT_BASE_URL` to `src/config/settings.py`
2. Add `fastapi` and `uvicorn` to `requirements.txt`
3. Create `src/api/__init__.py`, `src/api/routes/__init__.py` (empty inits)
4. Create `src/services/core/oauth_service.py` (state management + token exchange + store)
5. Create `src/api/app.py` (FastAPI app)
6. Create `src/api/routes/oauth.py` (route handlers)
7. Add `/connect` command to `src/services/core/telegram_commands.py`
8. Register `/connect` in `src/services/core/telegram_service.py`
9. Write tests: `tests/src/services/test_oauth_service.py`
10. Write tests: `tests/src/api/__init__.py`, `tests/src/api/test_oauth_routes.py`
11. Run `ruff check` + `ruff format` + `pytest`
12. Update `CHANGELOG.md`

## 13. Existing Bug Note

The CLI `add-instagram-account` command (line 452 of `cli/commands/instagram.py`) encrypts the token **before** passing it to `InstagramAccountService.add_account()`, which then encrypts it **again** inside `_create_account_with_token()`. This is a double-encryption bug. The OAuth flow avoids this by passing plaintext tokens. The CLI bug should be tracked as a separate fix.

---

### Critical Files for Implementation
- `/Users/chris/Projects/storyline-ai/src/services/core/oauth_service.py` - New file: core OAuth business logic (state tokens, token exchange, account storage)
- `/Users/chris/Projects/storyline-ai/src/api/routes/oauth.py` - New file: FastAPI route handlers for /start and /callback endpoints
- `/Users/chris/Projects/storyline-ai/src/services/core/instagram_account_service.py` - Existing: add_account() and update_account_token() are the integration point for storing OAuth results
- `/Users/chris/Projects/storyline-ai/src/services/core/telegram_commands.py` - Existing: add /connect command handler
- `/Users/chris/Projects/storyline-ai/src/config/settings.py` - Existing: add OAUTH_REDIRECT_BASE_URL setting