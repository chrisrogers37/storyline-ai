# Design: Meta App + Instagram Login OAuth + Go-Live

**Date:** 2026-03-31
**Status:** APPROVED
**Goal:** Take Storydump from single-user dry-run to a system where testers can self-onboard and post to their own Instagram accounts via the Mini App.

## Context

The Instagram posting infrastructure (Graph API, Cloudinary upload, token storage, multi-account support) is complete and working for a single user with manually-obtained tokens. To onboard additional users, the system needs:

1. A registered Meta Developer App so users can authenticate via OAuth
2. The newer Instagram Login flow (no Facebook Page required)
3. Graph API version bump from v18.0 to v21.0
4. Documentation of bootstrap-only env vars

The current user's operational setup must not be disrupted at any point.

## Architecture: Parallel Paths

```
UNCHANGED (current user's account):
├── Legacy token flow (.env INSTAGRAM_ACCESS_TOKEN → api_tokens table)
├── InstagramAPIService.post_story() posting logic
├── Telegram bot, scheduler, media sync
└── All existing tests

NEW (parallel path for new users):
├── InstagramLoginOAuthService (new service alongside existing OAuthService)
│   ├── instagram_business_basic + instagram_business_content_publish scopes
│   ├── Direct Instagram OAuth (no Facebook Page required)
│   └── Stores tokens in existing api_tokens + instagram_accounts tables
├── GET /auth/instagram-login/callback (new route, coexists with existing)
├── Onboarding Mini App wired to new OAuth endpoint
└── New env vars: INSTAGRAM_APP_ID, INSTAGRAM_APP_SECRET
```

Both paths produce the same data model (tokens in `api_tokens`, accounts in `instagram_accounts`). `InstagramAPIService.post_story()` doesn't care how the token was obtained.

## Milestone 1: Graph API Version Bump + Env Var Cleanup

**Type:** Code changes
**Risk:** Low

### Graph API Version
- Extract `META_GRAPH_BASE` into `src/config/settings.py` as a single constant
- Bump from v18.0 to v21.0 (required for Instagram Login scopes)
- Update all references in: `oauth_service.py`, `instagram_api.py`, `settings.py` (onboarding routes)

### Env Var Documentation
- Add docstring comments to `src/config/settings.py` marking bootstrap-only env vars:
  - `DRY_RUN_MODE` — bootstrap only, runtime in `chat_settings.dry_run_mode`
  - `ENABLE_INSTAGRAM_API` — bootstrap only, runtime in `chat_settings.enable_instagram_api`
  - `POSTS_PER_DAY`, `POSTING_HOURS_START`, `POSTING_HOURS_END` — bootstrap only
  - `MEDIA_SYNC_ENABLED`, `MEDIA_SOURCE_TYPE`, `MEDIA_SOURCE_ROOT` — bootstrap only
- Do NOT remove these (still needed for new chat bootstrapping)

### Verification
- Deploy to Railway
- `storydump-cli check-health`
- Confirm next scheduled post completes successfully

## Milestone 2: Meta App Registration + Instagram Login OAuth

### PAUSE — User Action Required
Before this milestone's code can be tested, the user must:
1. Register a Meta Developer App at developers.facebook.com
2. Add "Instagram" product to the app
3. Configure redirect URI: `{OAUTH_REDIRECT_BASE_URL}/auth/instagram-login/callback`
4. Set `INSTAGRAM_APP_ID` and `INSTAGRAM_APP_SECRET` as Railway env vars (both services)
5. Add testers as app roles (Admin/Developer/Tester — up to 4)

### New Env Vars
- `INSTAGRAM_APP_ID` — Meta App ID for Instagram Login flow
- `INSTAGRAM_APP_SECRET` — Meta App Secret for Instagram Login flow
- Separate from existing `FACEBOOK_APP_ID`/`FACEBOOK_APP_SECRET` to avoid confusion

### New Service: `InstagramLoginOAuthService`

**File:** `src/services/integrations/instagram_login_oauth.py`

Pattern: Same as `GoogleDriveOAuthService` (BaseService, track_execution, Fernet state tokens)

| Method | Purpose |
|--------|---------|
| `generate_authorization_url(chat_id)` | Build Instagram OAuth URL with encrypted state |
| `validate_state_token(state)` | Decrypt + validate TTL + extract chat_id |
| `exchange_and_store(auth_code, chat_id)` | Code → short-lived → long-lived → encrypt → store |

Key differences from existing `OAuthService` (Facebook Login):

| Aspect | Facebook Login (existing) | Instagram Login (new) |
|--------|--------------------------|----------------------|
| Auth URL | `facebook.com/v21.0/dialog/oauth` | `api.instagram.com/oauth/authorize` |
| Token exchange | `GET graph.facebook.com/v21.0/oauth/access_token` | `POST api.instagram.com/oauth/access_token` |
| Token response | Flat JSON `{access_token, ...}` | Wrapped: `{data: [{access_token, user_id, permissions}]}` |
| Scopes | `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement` | `instagram_business_basic`, `instagram_business_content_publish` |
| Account discovery | Token → Facebook Pages → IG Business Account (multi-hop) | `user_id` returned directly in token exchange |
| Long-lived exchange | `GET graph.facebook.com/v21.0/oauth/access_token` (`fb_exchange_token`) | `GET graph.instagram.com/access_token` (`ig_exchange_token`) |
| Token refresh | `GET graph.facebook.com/v21.0/oauth/access_token` (`ig_refresh_token`) | `GET graph.instagram.com/refresh_access_token` (`ig_refresh_token`) |
| Facebook Page required | Yes | No |

**Important:** Auth code from Instagram Login has a `#_` suffix that must be stripped before use. Codes are single-use and expire in 1 hour.

Account storage: Same `instagram_accounts` + `api_tokens` tables, with `auth_method="instagram_login"`.

### New Callback Route

**File:** `src/api/routes/oauth.py`

- `GET /auth/instagram-login/callback?code=...&state=...`
- Validates state token → exchanges code → stores tokens → notifies Telegram
- Returns HTML success/error page (same pattern as existing callbacks)
- Coexists with `/auth/instagram/callback` (Facebook Login path)

### Onboarding Mini App Update

- `GET /api/onboarding/oauth-url/instagram` currently calls `OAuthService`
- Add routing: if `INSTAGRAM_APP_ID` is configured, use `InstagramLoginOAuthService`; else fall back to `OAuthService` (Facebook Login); else return error
- Polling logic unchanged (polls `/init` for `instagram_connected`)

### Token Refresh Update

**File:** `src/services/integrations/token_refresh.py`

- Add refresh path for Instagram Login tokens
- Endpoint: `GET graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token={token}`
- Detect token type by `auth_method` on the associated `instagram_accounts` record
- Existing Facebook Login refresh path stays unchanged

### Tests
- Unit tests for `InstagramLoginOAuthService` (state tokens, exchange, store)
- Route tests for `/auth/instagram-login/callback` (success, denial, invalid state)
- Token refresh tests for Instagram Login path

## Milestone 3: Verify Go-Live State

### PAUSE — User Action Required
- Check `chat_settings.dry_run_mode` for your chat via production DB query or Mini App dashboard
- If `true`, toggle to `false` via dashboard
- Monitor first live post via Telegram notification
- Confirm Story appears on Instagram

## Milestone 4: Tester Onboarding Dry Run

### PAUSE — User Action Required
- Add tester email addresses as roles in Meta Developer Console
- Have testers: open bot → `/start` → Mini App wizard → Connect Instagram → set up folder → schedule → verify first post
- Collect feedback on onboarding friction

## Key Files

| File | Milestone | Change |
|------|-----------|--------|
| `src/config/settings.py` | 1 | `META_GRAPH_BASE` constant, bootstrap-only docs, new env vars |
| `src/services/core/oauth_service.py` | 1 | Use `META_GRAPH_BASE` from settings |
| `src/services/integrations/instagram_api.py` | 1 | Use `META_GRAPH_BASE` from settings |
| `src/api/routes/onboarding/settings.py` | 1 | Use `META_GRAPH_BASE` from settings |
| `src/services/integrations/instagram_login_oauth.py` | 2 | **New** — Instagram Login OAuth service |
| `src/api/routes/oauth.py` | 2 | New callback route |
| `src/api/routes/onboarding/setup.py` | 2 | Route OAuth URL to new service |
| `src/services/integrations/token_refresh.py` | 2 | Instagram Login refresh path |

## Non-Goals

- Meta App Review (not needed for Testing mode with < 5 users)
- Removing `FACEBOOK_APP_ID`/`FACEBOOK_APP_SECRET` (existing Facebook Login path preserved)
- Per-tenant Cloudinary namespaces
- Per-tenant rate limiting
- Public launch / open onboarding
