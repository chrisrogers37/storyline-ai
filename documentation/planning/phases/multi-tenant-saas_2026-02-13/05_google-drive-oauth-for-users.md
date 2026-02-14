# Phase 05: Google Drive OAuth for Users

**Status:** 📋 PENDING
**Risk:** Medium
**Effort:** 4-5 hours
**PR Title:** `feat: Google Drive user OAuth flow with folder selection via Telegram`

## 1. Summary

This phase replaces the CLI-based Google Drive service account connection flow with a user-facing OAuth2 flow initiated from Telegram. The user clicks a link, authorizes in their browser, Google redirects back with an auth code, and the server exchanges it for tokens that are stored per-tenant in the database. The existing `GoogleDriveProvider` already supports `oauth_credentials` alongside `service_account_info`, so the provider layer requires minimal changes. The primary work is in adding FastAPI callback endpoints, an OAuth state management utility, a Google token refresh mechanism, and Telegram UX for folder selection.

## 2. Architecture Decisions

### AD-1: Reuse `api_tokens` Table with `chat_settings_id` Scoping

Currently, `api_tokens` has a unique constraint on `(service_name, token_type, instagram_account_id)`. For Google Drive OAuth, we need per-tenant scoping. The approach from the Multi-Tenant SaaS overview (Phase 01) introduces a `chat_settings_id` FK on tenant-scoped tables. However, since Phase 01 may not yet be merged when this phase is implemented, we add a nullable `chat_settings_id` FK column to `api_tokens` now and include it in a NEW unique constraint for `google_drive` tokens. The existing Instagram constraint remains untouched.

### AD-2: FastAPI as Separate Process

The codebase does not currently have an `src/api/` directory or FastAPI app. This phase creates the initial FastAPI application structure. The FastAPI server runs as a separate process (not embedded in the Telegram bot `src/main.py`). It needs to be publicly accessible for Google OAuth callbacks. The bot sends the OAuth link; the FastAPI server handles the redirect.

### AD-3: OAuth State Tokens via Database

State tokens for CSRF protection are stored in a database table `oauth_states`, not in-memory. This allows the FastAPI callback server and the Telegram bot to run as separate processes. Each state record has: `state_token`, `chat_settings_id`, `provider` (e.g., `google_drive`), `created_at`, and `expires_at` (10-minute TTL). This utility is shared with Phase 04 (Instagram OAuth).

### AD-4: Folder Selection via Telegram Message

After OAuth completes, the bot sends a confirmation message and asks the user to paste a Google Drive folder URL. The bot extracts the folder ID from the URL, validates access via the provider, and stores it in `token_metadata`. This is simpler than building a web-based folder picker and keeps the Telegram-first philosophy.

### AD-5: Google Token Refresh via `google-auth` Library

Google OAuth refresh tokens are long-lived (never expire unless revoked). Access tokens expire in 1 hour. Rather than building custom HTTP refresh logic (as was done for Instagram's Meta API), we use the `google-auth` library's built-in `Credentials.refresh()` mechanism. The `GoogleDriveProvider` already holds a `Credentials` object that `googleapiclient` auto-refreshes on API calls. We store the refresh token, and reconstruct `Credentials` with it on each provider instantiation.

## 3. New Files

### 3.1 `src/api/__init__.py` (empty)

Package init for the API layer.

### 3.2 `src/api/app.py` -- FastAPI Application

Creates the FastAPI app with CORS middleware and includes the auth router. Entry point: `uvicorn src.api.app:app`.

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes.auth import router as auth_router

app = FastAPI(title="Storyline AI API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth")
```

### 3.3 `src/api/routes/__init__.py` (empty)

### 3.4 `src/api/routes/auth.py` -- OAuth Callback Endpoints

Two endpoints for Google Drive OAuth:

- `GET /auth/google-drive/start?chat_id={telegram_chat_id}` -- Generates a state token, stores it in `oauth_states`, and returns a redirect URL to Google's consent screen.
- `GET /auth/google-drive/callback?code={code}&state={state}` -- Validates the state token, exchanges the code for tokens via `https://oauth2.googleapis.com/token`, encrypts and stores tokens in `api_tokens`, then returns an HTML page saying "Success! Return to Telegram."

The endpoint also sends a Telegram message to the user's chat notifying them that Google Drive is connected and prompting for folder selection.

### 3.5 `src/models/oauth_state.py` -- OAuth State Model

```python
class OAuthState(Base):
    __tablename__ = "oauth_states"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    state_token = Column(String(64), nullable=False, unique=True, index=True)
    provider = Column(String(50), nullable=False)  # 'google_drive', 'instagram'
    telegram_chat_id = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
```

### 3.6 `src/repositories/oauth_state_repository.py` -- OAuth State CRUD

Methods: `create_state(provider, telegram_chat_id, ttl_seconds=600)`, `consume_state(state_token)` (returns and deletes), `cleanup_expired()`.

### 3.7 `src/services/integrations/google_drive_oauth.py` -- Google Drive OAuth Service

New service that handles:
- `generate_auth_url(telegram_chat_id)` -- creates state, builds Google OAuth URL
- `exchange_code(code, state_token)` -- validates state, exchanges code for tokens, stores encrypted tokens
- `store_folder_selection(telegram_chat_id, folder_id)` -- validates folder access, stores folder ID in token metadata
- `get_user_provider(telegram_chat_id)` -- creates a `GoogleDriveProvider` from stored user OAuth tokens
- `disconnect(telegram_chat_id)` -- removes stored tokens

### 3.8 `scripts/migrations/014_oauth_states.sql` -- OAuth States Table

```sql
BEGIN;

CREATE TABLE oauth_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    state_token VARCHAR(64) NOT NULL UNIQUE,
    provider VARCHAR(50) NOT NULL,
    telegram_chat_id BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL
);

CREATE INDEX idx_oauth_states_token ON oauth_states (state_token);
CREATE INDEX idx_oauth_states_expires ON oauth_states (expires_at);

INSERT INTO schema_version (version, description, applied_at)
VALUES (14, 'OAuth state tokens for Google Drive and Instagram OAuth flows', NOW());

COMMIT;
```

### 3.9 `scripts/migrations/015_api_tokens_chat_settings_fk.sql` -- Add `chat_settings_id` to `api_tokens`

```sql
BEGIN;

ALTER TABLE api_tokens
    ADD COLUMN chat_settings_id UUID REFERENCES chat_settings(id);

CREATE INDEX idx_api_tokens_chat_settings ON api_tokens (chat_settings_id);

-- Partial unique constraint for google_drive tokens (one per tenant per token type)
CREATE UNIQUE INDEX unique_google_drive_token_per_chat
    ON api_tokens (service_name, token_type, chat_settings_id)
    WHERE service_name = 'google_drive' AND chat_settings_id IS NOT NULL;

INSERT INTO schema_version (version, description, applied_at)
VALUES (15, 'Add chat_settings_id FK to api_tokens for per-tenant Google Drive tokens', NOW());

COMMIT;
```

### 3.10 Test Files

- `tests/src/api/__init__.py`
- `tests/src/api/routes/__init__.py`
- `tests/src/api/routes/test_auth.py` -- FastAPI endpoint tests using `TestClient`
- `tests/src/services/test_google_drive_oauth.py` -- GoogleDriveOAuthService tests
- `tests/src/repositories/test_oauth_state_repository.py` -- OAuth state CRUD tests
- `tests/src/models/test_oauth_state.py` -- Model tests

## 4. Modified Files

### 4.1 `src/config/settings.py` -- Add Google OAuth Settings

Add three new fields:

```python
# Google Drive OAuth (Phase 05 Multi-Tenant SaaS)
GOOGLE_CLIENT_ID: Optional[str] = None
GOOGLE_CLIENT_SECRET: Optional[str] = None
OAUTH_REDIRECT_BASE_URL: Optional[str] = None  # e.g., "https://api.storyline.ai"
```

`OAUTH_REDIRECT_BASE_URL` is shared with Phase 04 (Instagram OAuth). The redirect URI for Google Drive will be `{OAUTH_REDIRECT_BASE_URL}/auth/google-drive/callback`.

### 4.2 `src/models/api_token.py` -- Add `chat_settings_id` Column

Add a nullable FK column:

```python
chat_settings_id = Column(
    UUID(as_uuid=True),
    ForeignKey("chat_settings.id"),
    nullable=True,
    index=True,
)
```

The existing unique constraint `unique_service_token_type_account` remains unchanged (it governs Instagram tokens). Google Drive tokens are governed by the partial unique index created in the migration.

### 4.3 `src/repositories/token_repository.py` -- Add Tenant-Scoped Methods

Add new methods:

```python
def get_token_for_chat(
    self,
    service_name: str,
    token_type: str,
    chat_settings_id: str,
) -> Optional[ApiToken]:
    """Get token scoped to a specific tenant (chat)."""

def create_or_update_for_chat(
    self,
    service_name: str,
    token_type: str,
    token_value: str,
    chat_settings_id: str,
    **kwargs,
) -> ApiToken:
    """Create or update a token scoped to a specific tenant."""

def delete_token_for_chat(
    self,
    service_name: str,
    token_type: str,
    chat_settings_id: str,
) -> bool:
    """Delete a tenant-scoped token."""
```

### 4.4 `src/services/integrations/google_drive.py` -- Support User OAuth Credentials

The existing `GoogleDriveService` only supports service account credentials. Add a new method:

```python
def get_provider_for_chat(
    self,
    telegram_chat_id: int,
    root_folder_id: Optional[str] = None,
) -> GoogleDriveProvider:
    """Create a GoogleDriveProvider from per-tenant OAuth credentials.

    First checks for user OAuth tokens (google_drive/oauth_user).
    Falls back to global service account credentials.
    """
```

This method:
1. Looks up the `chat_settings.id` for the given `telegram_chat_id`
2. Queries `api_tokens` for `service_name='google_drive'`, `token_type='oauth_access'`, `chat_settings_id=...`
3. If found, decrypts the access token and refresh token
4. Constructs a `google.oauth2.credentials.Credentials` object with `token`, `refresh_token`, `client_id`, `client_secret`, `token_uri`
5. Returns `GoogleDriveProvider(root_folder_id=..., oauth_credentials=credentials)`
6. If not found, falls back to existing `get_provider()` (service account)

### 4.5 `src/services/media_sources/factory.py` -- Tenant-Aware Provider Creation

Update the `google_drive` branch in `MediaSourceFactory.create()` to accept an optional `telegram_chat_id` parameter. When present, use `GoogleDriveService.get_provider_for_chat()` instead of `get_provider()`.

### 4.6 `src/services/core/telegram_commands.py` (or new `telegram_onboarding.py`)

Add a handler for the "Connect Google Drive" button flow. This could be part of `/settings` or a dedicated `/connect` command. The handler:
1. Generates the OAuth URL via `GoogleDriveOAuthService.generate_auth_url(chat_id)`
2. Sends an inline button with the URL
3. After OAuth callback, the service sends a message: "Google Drive connected! Paste the link to your media folder."
4. A message handler intercepts the folder URL, extracts the folder ID, validates access, and stores it

### 4.7 `src/services/core/telegram_settings.py` -- Add Google Drive Status Button

Add a new button row to the settings keyboard showing Google Drive connection status:

```python
[
    InlineKeyboardButton(
        "📁 Google Drive: Connected" if gdrive_connected else "📁 Connect Google Drive",
        callback_data="gdrive_connect" if not gdrive_connected else "gdrive_status",
    ),
],
```

### 4.8 `src/exceptions/__init__.py` -- Export New Exception (if needed)

If we add `GoogleDriveOAuthError`, export it.

### 4.9 `requirements.txt` -- Add `fastapi` and `uvicorn`

```
# API Layer (Phase 05+)
fastapi>=0.115.0
uvicorn>=0.34.0
```

Note: `google-auth-oauthlib>=1.1.0` is already in requirements.

## 5. Detailed Flow

### 5.1 OAuth Initiation

```
User clicks "Connect Google Drive" in Telegram
  -> TelegramSettingsHandlers (or TelegramCommandHandlers)
     -> GoogleDriveOAuthService.generate_auth_url(chat_id)
        -> Creates OAuthState record (state_token, chat_id, expires_at=now+10min)
        -> Builds URL:
           https://accounts.google.com/o/oauth2/v2/auth
             ?client_id={GOOGLE_CLIENT_ID}
             &redirect_uri={OAUTH_REDIRECT_BASE_URL}/auth/google-drive/callback
             &scope=https://www.googleapis.com/auth/drive.readonly
             &response_type=code
             &state={state_token}
             &access_type=offline
             &prompt=consent
  -> Bot sends InlineKeyboardButton with url= parameter (opens browser)
```

### 5.2 OAuth Callback

```
Google redirects to: /auth/google-drive/callback?code={code}&state={state}
  -> FastAPI auth router
     -> Validate state_token (exists, not expired, consume it)
     -> Exchange code for tokens:
        POST https://oauth2.googleapis.com/token
          grant_type=authorization_code
          code={code}
          client_id={GOOGLE_CLIENT_ID}
          client_secret={GOOGLE_CLIENT_SECRET}
          redirect_uri={OAUTH_REDIRECT_BASE_URL}/auth/google-drive/callback
     -> Response: { access_token, refresh_token, expires_in, scope, token_type }
     -> Get/create chat_settings for the telegram_chat_id
     -> Encrypt both tokens
     -> Store access_token: api_tokens(service='google_drive', type='oauth_access', chat_settings_id=...)
     -> Store refresh_token: api_tokens(service='google_drive', type='oauth_refresh', chat_settings_id=...)
     -> Store user email in metadata (from token info endpoint)
     -> Send Telegram message to chat_id:
        "Google Drive connected! Now paste the link to your media folder."
     -> Return HTML page: "Success! You can close this tab and return to Telegram."
```

### 5.3 Folder Selection

```
User pastes folder URL in Telegram chat
  e.g., "https://drive.google.com/drive/folders/1ABC123xyz"
  -> MessageHandler detects Drive folder URL pattern
     -> Extract folder ID: "1ABC123xyz"
     -> Create GoogleDriveProvider with user's OAuth credentials
     -> provider.is_configured() to validate folder access
     -> provider.get_folders() to list subfolders (categories)
     -> Store folder_id in token_metadata
     -> Update chat_settings.media_sync_enabled = True (optionally)
     -> Bot replies: "Connected to folder '1ABC123xyz'
        Found 42 media files across 3 categories: memes, merch, promo"
```

### 5.4 Token Refresh

```
On each GoogleDriveProvider instantiation:
  -> Credentials(
       token=access_token,
       refresh_token=refresh_token,
       token_uri="https://oauth2.googleapis.com/token",
       client_id=GOOGLE_CLIENT_ID,
       client_secret=GOOGLE_CLIENT_SECRET,
     )
  -> The google-auth library auto-refreshes expired access tokens
     when the googleapiclient makes an API call
  -> After refresh, the new access_token can be persisted back
     (optional optimization -- the refresh_token never changes)
```

The `google.oauth2.credentials.Credentials` object handles refresh automatically when passed to `googleapiclient.discovery.build()`. When the access token expires, the library calls the token endpoint with the refresh token and gets a new access token. We do NOT need a custom refresh loop like Instagram's `TokenRefreshService`. However, we should store the updated access token back to the database for efficiency (avoids refreshing on every request).

Strategy: After creating the `Credentials` object, check if the token is expired. If so, call `credentials.refresh(google.auth.transport.requests.Request())` explicitly, then store the new `credentials.token` and `credentials.expiry` back to the database.

### 5.5 Provider Selection Flow

```
MediaSyncService.sync() or PostingService needs a GoogleDriveProvider
  -> MediaSourceFactory.create("google_drive", telegram_chat_id=chat_id)
     -> GoogleDriveService.get_provider_for_chat(chat_id)
        -> Look up user OAuth tokens for this chat
        -> If found: construct Credentials, return GoogleDriveProvider(oauth_credentials=...)
        -> If not found: fall back to global service account (existing behavior)
```

## 6. GoogleDriveProvider Authentication Switching -- Detailed

The `GoogleDriveProvider` already supports both auth modes (lines 56-75 of `/Users/chris/Projects/storyline-ai/src/services/media_sources/google_drive_provider.py`):

```python
def __init__(
    self,
    root_folder_id: str,
    service_account_info: Optional[dict] = None,
    oauth_credentials: Optional[UserCredentials] = None,
):
    if service_account_info:
        credentials = ServiceAccountCredentials.from_service_account_info(...)
    elif oauth_credentials:
        credentials = oauth_credentials
    else:
        raise GoogleDriveAuthError(...)
```

No changes needed to `GoogleDriveProvider` itself. The switching happens in `GoogleDriveService.get_provider_for_chat()`, which constructs the appropriate `Credentials` object and passes it as `oauth_credentials`.

The `google.oauth2.credentials.Credentials` constructor for user OAuth:

```python
from google.oauth2.credentials import Credentials

credentials = Credentials(
    token=decrypted_access_token,
    refresh_token=decrypted_refresh_token,
    token_uri="https://oauth2.googleapis.com/token",
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    scopes=["https://www.googleapis.com/auth/drive.readonly"],
)
```

## 7. Token Storage Schema

For a single tenant's Google Drive connection, we store two rows in `api_tokens`:

| service_name | token_type | chat_settings_id | token_value (encrypted) | token_metadata |
|---|---|---|---|---|
| google_drive | oauth_access | {uuid} | {encrypted access_token} | `{"email": "user@gmail.com", "root_folder_id": "1ABC...", "scope": "drive.readonly"}` |
| google_drive | oauth_refresh | {uuid} | {encrypted refresh_token} | `{"email": "user@gmail.com"}` |

Alternatively, we can store both tokens in a single row (as a JSON blob). But the two-row approach aligns with the existing Instagram pattern and makes refresh logic cleaner (update only the access token row).

## 8. Telegram UX Flow

### Connect Flow
```
/settings
  -> [📁 Connect Google Drive]  (url button -> opens browser)
     -> Google consent screen -> authorize
     -> Redirect to callback
     -> Bot message: "✅ Google Drive connected for user@gmail.com!
        Now paste the link to your media folder."
  -> User pastes: https://drive.google.com/drive/folders/1ABC...
  -> Bot: "📁 Connected to folder!
           Found 42 files in 3 categories: memes, merch, promo
           Media sync will start automatically."
```

### Status/Disconnect
```
/settings
  -> [📁 Google Drive: Connected ✅]
     -> Submenu:
        [📊 42 files, 3 categories]
        [🔄 Sync Now]
        [🔌 Disconnect]
        [↩️ Back to Settings]
```

### Folder URL Pattern Match
```python
GDRIVE_FOLDER_PATTERN = re.compile(
    r"(?:https?://)?drive\.google\.com/drive/(?:u/\d+/)?folders/([a-zA-Z0-9_-]+)"
)
```

## 9. Test Plan

### Unit Tests

**`tests/src/services/test_google_drive_oauth.py`**:
- `test_generate_auth_url_creates_state` -- Verify state token is created and URL is well-formed
- `test_generate_auth_url_missing_client_id` -- Raises when `GOOGLE_CLIENT_ID` not configured
- `test_exchange_code_success` -- Mock HTTP exchange, verify tokens stored encrypted
- `test_exchange_code_invalid_state` -- Consumed/expired state raises error
- `test_exchange_code_google_error` -- Google returns error response
- `test_store_folder_selection_valid` -- Folder accessible, metadata updated
- `test_store_folder_selection_invalid` -- Folder not accessible, raises error
- `test_get_user_provider_success` -- Returns provider with user OAuth credentials
- `test_get_user_provider_falls_back_to_service_account` -- No user tokens, uses SA
- `test_disconnect_removes_tokens` -- Both access and refresh tokens deleted
- `test_token_refresh_on_expired_access` -- Credentials refresh called when access token expired

**`tests/src/api/routes/test_auth.py`**:
- `test_start_returns_redirect_url` -- GET /start returns 200 with URL
- `test_start_invalid_chat_id` -- Missing/invalid chat_id returns 400
- `test_callback_success` -- Valid code+state exchanges and stores tokens
- `test_callback_invalid_state` -- Unknown state returns 400
- `test_callback_expired_state` -- Expired state returns 400
- `test_callback_google_exchange_failure` -- Google returns error, returns 502

**`tests/src/repositories/test_oauth_state_repository.py`**:
- `test_create_state` -- Creates with TTL
- `test_consume_state_valid` -- Returns and deletes
- `test_consume_state_expired` -- Returns None for expired
- `test_consume_state_missing` -- Returns None for nonexistent
- `test_cleanup_expired` -- Removes old records

**`tests/src/models/test_oauth_state.py`**:
- `test_model_fields` -- Columns exist with correct types
- `test_state_token_unique` -- Unique constraint enforced

### Integration Tests (optional)

- `test_full_oauth_flow` -- Start -> Callback -> Folder selection -> Provider creation
- Uses `TestClient` for FastAPI and mocked Google OAuth responses

## 10. Verification Checklist

- [ ] `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env.example`
- [ ] Migration 014 creates `oauth_states` table
- [ ] Migration 015 adds `chat_settings_id` FK to `api_tokens`
- [ ] `GET /auth/google-drive/start?chat_id=123` returns a valid Google OAuth URL
- [ ] State token is stored in `oauth_states` with 10-minute TTL
- [ ] `GET /auth/google-drive/callback` with valid code+state stores encrypted tokens
- [ ] State token is consumed (one-time use)
- [ ] Expired state tokens are rejected
- [ ] Tokens are encrypted with `TokenEncryption` before storage
- [ ] User email is stored in `token_metadata`
- [ ] Telegram bot sends "Connected!" message after successful callback
- [ ] Folder URL pasted in Telegram is parsed and validated
- [ ] `GoogleDriveProvider` works with user OAuth credentials
- [ ] Auto-refresh works when access token expires (google-auth handles it)
- [ ] Disconnect flow removes both token rows
- [ ] Settings menu shows Google Drive status
- [ ] Service account fallback still works when no user OAuth tokens exist
- [ ] All existing Google Drive tests pass unchanged
- [ ] `ruff check` and `ruff format` pass
- [ ] `pytest` passes with new tests
- [ ] CHANGELOG.md updated

## 11. What NOT To Do

1. **Do NOT modify `GoogleDriveProvider`** -- It already supports both auth modes via its constructor. All switching logic belongs in `GoogleDriveService` / `GoogleDriveOAuthService`.

2. **Do NOT build a web-based folder picker** -- The Telegram-first philosophy means folder selection happens via pasting a URL in chat. A web picker adds unnecessary frontend complexity.

3. **Do NOT store tokens in plaintext** -- All tokens must go through `TokenEncryption.encrypt()` before database storage.

4. **Do NOT implement custom token refresh HTTP calls** -- The `google-auth` library handles refresh automatically via `Credentials.refresh()`. Do not replicate the `TokenRefreshService` pattern used for Instagram.

5. **Do NOT break the existing service account flow** -- The new user OAuth path is additive. `get_provider()` (service account) must continue working. `get_provider_for_chat()` is the new tenant-aware method.

6. **Do NOT store the Google client secret in the database** -- It stays in `.env` only. The `Credentials` object needs it at construction time, but it comes from `settings.GOOGLE_CLIENT_SECRET`.

7. **Do NOT embed the FastAPI server inside `src/main.py`** -- Run it as a separate process via `uvicorn src.api.app:app`. The main process is the Telegram bot; the API server is auxiliary.

8. **Do NOT send Telegram messages from the FastAPI endpoint directly** -- Use `httpx` to call the Telegram Bot API from the callback endpoint (one-off message), or use a shared notification service. Do not import `TelegramService` into the API layer (violates layer separation).

9. **Do NOT use `google_auth_oauthlib.flow.Flow` for the server-side exchange** -- That library is designed for local/CLI flows. For a web server callback, use direct `httpx` POST to Google's token endpoint. The `google-auth-oauthlib` dependency is already installed but we only need `google.oauth2.credentials.Credentials` from `google-auth`.

10. **Do NOT add the FastAPI server to `src/main.py`'s asyncio loop** -- Keep them separate to avoid coupling the bot's lifecycle with the API server.

## 12. Dependency Sequencing

This phase has no hard dependencies on Phases 01-03 of the Multi-Tenant SaaS plan, because:
- We add `chat_settings_id` to `api_tokens` ourselves (migration 015)
- We look up `chat_settings` by `telegram_chat_id` (already exists)
- The `oauth_states` table is self-contained

However, if Phase 01 is merged first and adds a broader `chat_settings_id` FK pattern, migration 015 should be adjusted to avoid duplicate columns.

**Internal ordering within this phase:**
1. Migrations (014, 015) -- foundation
2. `OAuthState` model + repository -- shared utility
3. Settings additions (`GOOGLE_CLIENT_ID`, etc.)
4. `api_token.py` model update (`chat_settings_id`)
5. `token_repository.py` new methods
6. `GoogleDriveOAuthService` -- core OAuth logic
7. FastAPI app + auth routes -- HTTP layer
8. `GoogleDriveService.get_provider_for_chat()` -- provider wiring
9. `MediaSourceFactory` update -- tenant-aware creation
10. Telegram UX (settings button, folder URL handler)
11. Tests throughout
12. `.env.example` and CHANGELOG updates

### Critical Files for Implementation
- `/Users/chris/Projects/storyline-ai/src/services/integrations/google_drive.py` - Core service to extend with `get_provider_for_chat()` for user OAuth credentials
- `/Users/chris/Projects/storyline-ai/src/repositories/token_repository.py` - Must add tenant-scoped methods (`get_token_for_chat`, `create_or_update_for_chat`)
- `/Users/chris/Projects/storyline-ai/src/models/api_token.py` - Add `chat_settings_id` FK column for per-tenant token storage
- `/Users/chris/Projects/storyline-ai/src/services/media_sources/google_drive_provider.py` - Reference file: already supports `oauth_credentials`, no changes needed but essential to understand
- `/Users/chris/Projects/storyline-ai/src/services/core/telegram_settings.py` - Add Google Drive connect/status button to settings keyboard
