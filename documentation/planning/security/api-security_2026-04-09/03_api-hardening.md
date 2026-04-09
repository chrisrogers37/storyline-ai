# Phase 03: Harden API with Docs Gating, Security Headers, and Rate Limiting

| Field | Value |
|-------|-------|
| **PR Title** | `fix: harden API with docs gating, security headers, and rate limiting` |
| **Severity** | MEDIUM (Finding #8), MEDIUM (Finding #9), LOW (Finding #10) |
| **Effort** | Medium (3-4 hours) |
| **Risk** | Low |
| **Files Modified** | 3 (`src/api/app.py`, `src/config/settings.py`, `requirements.txt`) |
| **Files Created** | 2 (`src/api/middleware.py`, `tests/src/api/test_middleware.py`) |
| **Files Deleted** | 0 |

---

## Context

The security audit identified three API hardening gaps. First, FastAPI's auto-generated documentation endpoints (`/docs`, `/redoc`, `/openapi.json`) are publicly accessible in the production Railway deployment, providing attackers with a complete map of every endpoint, parameter name, type, and description. Second, the API returns no security headers -- no HSTS, no X-Frame-Options, no X-Content-Type-Options -- leaving the OAuth callback HTML pages vulnerable to clickjacking and MIME confusion. Third, there is zero rate limiting on any endpoint, enabling brute-force attacks on authentication, rapid-fire OAuth state token generation, and denial-of-service against state-mutating endpoints.

All three issues are independent of each other and of the higher-severity tenant isolation fixes in Phases 01-02, so this phase can be implemented in parallel with those.

---

## Findings Addressed

| # | Finding | Severity | Research Ref |
|---|---------|----------|--------------|
| F4 | FastAPI docs/redoc/openapi exposed in production | MEDIUM | `auth-transport-endpoints.md` F4 |
| F5 | Missing security headers (HSTS, X-Frame-Options, X-Content-Type-Options) | MEDIUM | `auth-transport-endpoints.md` F5 |
| F6 | No rate limiting on any API endpoint | LOW | `auth-transport-endpoints.md` F6 |

---

## Dependencies

**Requires:** None -- this phase is fully independent.

**Unlocks:** None -- no other phases depend on this work.

**Parallel safety:** This phase modifies `src/api/app.py`, `src/config/settings.py`, and `requirements.txt`. Verify no other in-flight phases modify these same files. Phases 01 and 02 modify `src/api/routes/` files and `src/utils/webapp_auth.py` respectively, which do not overlap.

---

## Detailed Implementation Plan

### Step 1: Add the `ENVIRONMENT` setting to `src/config/settings.py`

The project currently has no environment discriminator. Add one to the `Settings` class so the app can distinguish production from development.

**File:** `src/config/settings.py`

**Current code (lines 84-86):**

```python
    # Development Settings (bootstrap only — runtime value in chat_settings)
    DRY_RUN_MODE: bool = False
    LOG_LEVEL: str = "INFO"
```

**Replace with:**

```python
    # Development Settings (bootstrap only — runtime value in chat_settings)
    DRY_RUN_MODE: bool = False
    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = "development"  # "development" | "production" — controls docs visibility
```

**Why `ENVIRONMENT` instead of checking `RAILWAY_ENVIRONMENT`:** The research file suggested checking `os.getenv("RAILWAY_ENVIRONMENT")`, but that couples the app logic to the deployment platform. A first-class `ENVIRONMENT` setting is portable across platforms, testable without mocking env vars, and follows the existing pattern where all config flows through the Pydantic `Settings` class. On Railway, set `ENVIRONMENT=production` as an env var on both the worker and API services.

---

### Step 2: Add `slowapi` to `requirements.txt`

**File:** `requirements.txt`

**Current code (lines 33-35):**

```
# API Server (Phase 04 OAuth)
fastapi>=0.109.0
uvicorn>=0.27.0
```

**Replace with:**

```
# API Server (Phase 04 OAuth)
fastapi>=0.109.0
uvicorn>=0.27.0
slowapi>=0.1.9
```

**Why `slowapi`:** It is the de facto rate limiting library for FastAPI/Starlette. It wraps `limits` (a mature Python rate limiting library), integrates natively with Starlette middleware, and supports per-route decorator-based limits. It requires no external state store (uses in-memory by default), which is appropriate for a single-instance Railway deployment.

---

### Step 3: Create `src/api/middleware.py`

Create a new file containing the security headers middleware. Keeping middleware separate from `app.py` follows separation of concerns and makes each middleware independently testable.

**File:** `src/api/middleware.py` (NEW)

**Full content:**

```python
"""Security middleware for the Storyline AI API."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all API responses.

    Headers added:
    - Strict-Transport-Security: Instructs browsers to only use HTTPS.
      Railway terminates TLS at the load balancer, but HSTS ensures
      browsers never attempt an HTTP downgrade.
    - X-Frame-Options: DENY prevents the page from being embedded in
      iframes, protecting OAuth callback HTML pages from clickjacking.
    - X-Content-Type-Options: nosniff prevents browsers from MIME-sniffing
      responses away from the declared Content-Type.
    - Referrer-Policy: strict-origin-when-cross-origin limits referrer
      leakage on cross-origin navigations (e.g., OAuth redirects).
    - Permissions-Policy: Disables browser features (camera, microphone,
      geolocation) that the API never needs.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        return response
```

**Why no Content-Security-Policy header:** The OAuth callback endpoints (`_success_html_page`, `_error_html_page` in `src/api/routes/oauth.py`) serve inline HTML with inline `<style>` blocks. Adding a strict CSP with `style-src 'self'` would break those pages. A CSP that allows `'unsafe-inline'` for styles provides marginal security value. If the inline styles are later moved to static CSS files, CSP can be added at that point. This is documented as a future improvement, not a gap.

---

### Step 4: Rewrite `src/api/app.py` with all three fixes

This is the main change. The file is rewritten to:
1. Conditionally disable docs endpoints based on `ENVIRONMENT`
2. Register the security headers middleware
3. Configure slowapi rate limiting with per-route limits

**File:** `src/api/app.py`

**Current content (entire file, lines 1-52):**

```python
"""FastAPI application for Storyline AI OAuth flows and Mini App."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.api.routes.oauth import router as oauth_router
from src.api.routes.onboarding import router as onboarding_router
from src.config.settings import settings

app = FastAPI(
    title="Storyline AI API",
    description="OAuth and API endpoints for Storyline AI",
    version="0.1.0",
)

# CORS middleware — restrict to our own domain in production
_cors_origins = (
    [settings.OAUTH_REDIRECT_BASE_URL]
    if settings.OAUTH_REDIRECT_BASE_URL
    else ["http://localhost:8000"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# Static files for Mini App
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Register routes
app.include_router(oauth_router, prefix="/auth")
app.include_router(onboarding_router, prefix="/api/onboarding")


@app.get("/webapp/onboarding")
async def serve_onboarding_webapp():
    """Serve the onboarding Mini App HTML."""
    html_path = STATIC_DIR / "onboarding" / "index.html"
    if not html_path.exists():
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Onboarding app not found")
    return FileResponse(str(html_path), media_type="text/html")
```

**Replace entire file with:**

```python
"""FastAPI application for Storyline AI OAuth flows and Mini App."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from src.api.middleware import SecurityHeadersMiddleware
from src.api.routes.oauth import router as oauth_router
from src.api.routes.onboarding import router as onboarding_router
from src.config.settings import settings

# ---------------------------------------------------------------------------
# Rate limiter (in-memory, per-IP)
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address)

# ---------------------------------------------------------------------------
# App construction — disable docs in production
# ---------------------------------------------------------------------------
_is_production = settings.ENVIRONMENT == "production"

app = FastAPI(
    title="Storyline AI API",
    description="OAuth and API endpoints for Storyline AI",
    version="0.1.0",
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
    openapi_url=None if _is_production else "/openapi.json",
)

# Attach limiter state to the app (required by slowapi)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---------------------------------------------------------------------------
# Middleware (order matters — last added runs first)
# ---------------------------------------------------------------------------

# Security headers — runs on every response
app.add_middleware(SecurityHeadersMiddleware)

# CORS — restrict to our own domain in production
_cors_origins = (
    [settings.OAUTH_REDIRECT_BASE_URL]
    if settings.OAUTH_REDIRECT_BASE_URL
    else ["http://localhost:8000"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# ---------------------------------------------------------------------------
# Static files for Mini App
# ---------------------------------------------------------------------------
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ---------------------------------------------------------------------------
# Register routes
# ---------------------------------------------------------------------------
app.include_router(oauth_router, prefix="/auth")
app.include_router(onboarding_router, prefix="/api/onboarding")


# ---------------------------------------------------------------------------
# Top-level routes
# ---------------------------------------------------------------------------
@app.get("/webapp/onboarding")
@limiter.limit("30/minute")
async def serve_onboarding_webapp(request: Request):
    """Serve the onboarding Mini App HTML."""
    html_path = STATIC_DIR / "onboarding" / "index.html"
    if not html_path.exists():
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Onboarding app not found")
    return FileResponse(str(html_path), media_type="text/html")
```

**Key changes explained:**

1. **Docs gating (lines with `docs_url`, `redoc_url`, `openapi_url`):** When `ENVIRONMENT=production`, all three are set to `None`, which tells FastAPI to not register those routes at all. In development (the default), they remain at their standard paths for local testing.

2. **Security headers middleware:** `app.add_middleware(SecurityHeadersMiddleware)` -- added BEFORE CORS middleware so that security headers are applied to every response, including CORS preflight responses. Starlette processes middleware in reverse order of addition, so the last `add_middleware` call runs first. CORS must run first (outermost), so it is added last.

3. **Rate limiter setup:** The `limiter` instance is created at module level with `get_remote_address` as the key function (extracts client IP from the request). The `app.state.limiter` assignment and exception handler are required by slowapi's architecture. The `_rate_limit_exceeded_handler` returns a `429 Too Many Requests` JSON response automatically.

4. **`request: Request` parameter added to `serve_onboarding_webapp`:** slowapi requires the `Request` object to be available as a function parameter to extract the client IP. This is a FastAPI/Starlette convention -- the framework injects it automatically.

---

### Step 5: Add rate limits to OAuth routes

The OAuth start endpoints are the highest-priority targets for rate limiting because they generate state tokens and initiate redirect flows without authentication.

**File:** `src/api/routes/oauth.py`

**Current imports (lines 1-12):**

```python
"""OAuth redirect flow endpoints for Instagram and Google Drive."""

import html

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from src.api.routes.onboarding.helpers import service_error_handler
from src.services.core.oauth_service import OAuthService
from src.services.integrations.google_drive_oauth import GoogleDriveOAuthService
from src.services.integrations.instagram_login_oauth import InstagramLoginOAuthService
from src.utils.logger import logger
```

**Replace with:**

```python
"""OAuth redirect flow endpoints for Instagram and Google Drive."""

import html

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.api.app import limiter
from src.api.routes.onboarding.helpers import service_error_handler
from src.services.core.oauth_service import OAuthService
from src.services.integrations.google_drive_oauth import GoogleDriveOAuthService
from src.services.integrations.instagram_login_oauth import InstagramLoginOAuthService
from src.utils.logger import logger
```

**IMPORTANT -- circular import prevention:** The `oauth.py` module is imported by `app.py` (via `from src.api.routes.oauth import router as oauth_router`). Importing `limiter` from `app.py` in `oauth.py` creates a circular import. To fix this, the `limiter` must be defined in a separate module that both `app.py` and route files can import from.

**Revised approach -- extract limiter to a shared module:**

**File:** `src/api/middleware.py` -- add the limiter instance here alongside the security headers middleware.

**Updated full content of `src/api/middleware.py`:**

```python
"""Security middleware and shared API utilities for Storyline AI."""

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# ---------------------------------------------------------------------------
# Rate limiter (in-memory, per-IP)
# ---------------------------------------------------------------------------
# Shared instance — imported by app.py (for setup) and route files (for decorators).
limiter = Limiter(key_func=get_remote_address)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all API responses.

    Headers added:
    - Strict-Transport-Security: Instructs browsers to only use HTTPS.
      Railway terminates TLS at the load balancer, but HSTS ensures
      browsers never attempt an HTTP downgrade.
    - X-Frame-Options: DENY prevents the page from being embedded in
      iframes, protecting OAuth callback HTML pages from clickjacking.
    - X-Content-Type-Options: nosniff prevents browsers from MIME-sniffing
      responses away from the declared Content-Type.
    - Referrer-Policy: strict-origin-when-cross-origin limits referrer
      leakage on cross-origin navigations (e.g., OAuth redirects).
    - Permissions-Policy: Disables browser features (camera, microphone,
      geolocation) that the API never needs.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        return response
```

**Updated `src/api/app.py` import (change the limiter import line):**

In the final `app.py` above, change:

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from src.api.middleware import SecurityHeadersMiddleware
```

to:

```python
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.api.middleware import SecurityHeadersMiddleware, limiter
```

And remove these lines from `app.py`:

```python
limiter = Limiter(key_func=get_remote_address)
```

The `limiter` is now created once in `middleware.py` and imported by both `app.py` and route files, avoiding circular imports entirely.

---

**Now, back to the OAuth route changes.**

**File:** `src/api/routes/oauth.py`

**Updated imports:**

```python
"""OAuth redirect flow endpoints for Instagram and Google Drive."""

import html

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.api.middleware import limiter
from src.api.routes.onboarding.helpers import service_error_handler
from src.services.core.oauth_service import OAuthService
from src.services.integrations.google_drive_oauth import GoogleDriveOAuthService
from src.services.integrations.instagram_login_oauth import InstagramLoginOAuthService
from src.utils.logger import logger
```

**Add rate limit decorators and `request: Request` parameter to the four endpoints that need them:**

**`instagram_oauth_start` (line 17-29) -- current:**

```python
@router.get("/instagram/start")
async def instagram_oauth_start(
    chat_id: int = Query(..., description="Telegram chat ID initiating the flow"),
):
```

**Replace with:**

```python
@router.get("/instagram/start")
@limiter.limit("10/minute")
async def instagram_oauth_start(
    request: Request,
    chat_id: int = Query(..., description="Telegram chat ID initiating the flow"),
):
```

**`instagram_oauth_callback` (line 32-38) -- current:**

```python
@router.get("/instagram/callback")
async def instagram_oauth_callback(
    code: str = Query(None, description="Authorization code from Meta"),
```

**Replace with:**

```python
@router.get("/instagram/callback")
@limiter.limit("10/minute")
async def instagram_oauth_callback(
    request: Request,
    code: str = Query(None, description="Authorization code from Meta"),
```

**`instagram_login_oauth_callback` (line 111-117) -- current:**

```python
@router.get("/instagram-login/callback")
async def instagram_login_oauth_callback(
    code: str = Query(None, description="Authorization code from Instagram"),
```

**Replace with:**

```python
@router.get("/instagram-login/callback")
@limiter.limit("10/minute")
async def instagram_login_oauth_callback(
    request: Request,
    code: str = Query(None, description="Authorization code from Instagram"),
```

**`google_drive_oauth_start` (line 185-188) -- current:**

```python
@router.get("/google-drive/start")
async def google_drive_oauth_start(
    chat_id: int = Query(..., description="Telegram chat ID initiating the flow"),
):
```

**Replace with:**

```python
@router.get("/google-drive/start")
@limiter.limit("10/minute")
async def google_drive_oauth_start(
    request: Request,
    chat_id: int = Query(..., description="Telegram chat ID initiating the flow"),
):
```

**`google_drive_oauth_callback` (line 200-205) -- current:**

```python
@router.get("/google-drive/callback")
async def google_drive_oauth_callback(
    code: str = Query(None, description="Authorization code from Google"),
```

**Replace with:**

```python
@router.get("/google-drive/callback")
@limiter.limit("10/minute")
async def google_drive_oauth_callback(
    request: Request,
    code: str = Query(None, description="Authorization code from Google"),
```

**Rate limit rationale for OAuth routes:** `10/minute` is strict because these endpoints either generate encrypted state tokens (start) or exchange authorization codes (callback). A legitimate user will hit these at most once or twice per OAuth flow. 10/minute allows for retries and edge cases without enabling abuse.

---

### Step 6: Add rate limits to onboarding routes

**File:** `src/api/routes/onboarding/setup.py`

**Current imports (lines 1-27):**

```python
"""Setup wizard endpoints for onboarding Mini App."""

from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import OperationalError

from src.config.settings import settings
from src.services.core.media_sync import MediaSyncService
from src.services.core.oauth_service import OAuthService
from src.services.core.settings_service import SettingsService
from src.services.integrations.google_drive import GoogleDriveService
from src.services.integrations.google_drive_oauth import GoogleDriveOAuthService
from src.services.integrations.instagram_login_oauth import InstagramLoginOAuthService
from src.utils.logger import logger

from .helpers import (
    GDRIVE_FOLDER_RE,
    _get_setup_state,
    _validate_request,
    service_error_handler,
)
from .models import (
    CompleteRequest,
    InitRequest,
    MediaFolderRequest,
    ScheduleRequest,
    StartIndexingRequest,
)
```

**Replace with:**

```python
"""Setup wizard endpoints for onboarding Mini App."""

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.exc import OperationalError

from src.api.middleware import limiter
from src.config.settings import settings
from src.services.core.media_sync import MediaSyncService
from src.services.core.oauth_service import OAuthService
from src.services.core.settings_service import SettingsService
from src.services.integrations.google_drive import GoogleDriveService
from src.services.integrations.google_drive_oauth import GoogleDriveOAuthService
from src.services.integrations.instagram_login_oauth import InstagramLoginOAuthService
from src.utils.logger import logger

from .helpers import (
    GDRIVE_FOLDER_RE,
    _get_setup_state,
    _validate_request,
    service_error_handler,
)
from .models import (
    CompleteRequest,
    InitRequest,
    MediaFolderRequest,
    ScheduleRequest,
    StartIndexingRequest,
)
```

**Add decorators and `request: Request` to each endpoint:**

**`onboarding_init` (line 32-33) -- current:**

```python
@router.post("/init")
async def onboarding_init(request: InitRequest):
```

**Replace with:**

```python
@router.post("/init")
@limiter.limit("20/minute")
async def onboarding_init(request: Request, body: InitRequest):
```

**IMPORTANT:** The `request` parameter name is now taken by the Starlette `Request` object (required by slowapi). The Pydantic model parameter must be renamed to `body` (or any other name). FastAPI resolves parameters by type annotation, not by name, so `body: InitRequest` is correctly parsed from the request body.

Then update ALL references to `request.init_data`, `request.chat_id` inside `onboarding_init` to `body.init_data`, `body.chat_id`:

**Current body of `onboarding_init`:**

```python
    user_info = _validate_request(request.init_data, request.chat_id)

    setup_state = _get_setup_state(request.chat_id)

    # Set initial onboarding step if not yet started
    if not setup_state.get("onboarding_completed") and not setup_state.get(
        "onboarding_step"
    ):
        with SettingsService() as settings_service:
            settings_service.set_onboarding_step(request.chat_id, "welcome")
        setup_state["onboarding_step"] = "welcome"

    return {
        "chat_id": request.chat_id,
        "user": user_info,
        "setup_state": setup_state,
    }
```

**Replace with:**

```python
    user_info = _validate_request(body.init_data, body.chat_id)

    setup_state = _get_setup_state(body.chat_id)

    # Set initial onboarding step if not yet started
    if not setup_state.get("onboarding_completed") and not setup_state.get(
        "onboarding_step"
    ):
        with SettingsService() as settings_service:
            settings_service.set_onboarding_step(body.chat_id, "welcome")
        setup_state["onboarding_step"] = "welcome"

    return {
        "chat_id": body.chat_id,
        "user": user_info,
        "setup_state": setup_state,
    }
```

**Apply the same pattern to every endpoint in `setup.py`:**

| Endpoint | Rate Limit | Rename `request` to `body` |
|----------|------------|---------------------------|
| `onboarding_init` | `20/minute` | Yes -- all `request.` -> `body.` |
| `onboarding_oauth_url` | `10/minute` | No -- uses query params, add `request: Request` as first param |
| `onboarding_media_folder` | `10/minute` | Yes -- all `request.` -> `body.` |
| `onboarding_start_indexing` | `5/minute` | Yes -- all `request.` -> `body.` |
| `onboarding_schedule` | `10/minute` | Yes -- all `request.` -> `body.` |
| `onboarding_complete` | `10/minute` | Yes -- all `request.` -> `body.` |

**Example for `onboarding_oauth_url` (GET endpoint with query params):**

**Current:**

```python
@router.get("/oauth-url/{provider}")
async def onboarding_oauth_url(
    provider: str,
    init_data: str,
    chat_id: int,
):
```

**Replace with:**

```python
@router.get("/oauth-url/{provider}")
@limiter.limit("10/minute")
async def onboarding_oauth_url(
    request: Request,
    provider: str,
    init_data: str,
    chat_id: int,
):
```

(No body rename needed -- this endpoint uses query params, not a Pydantic model.)

**Example for `onboarding_start_indexing` (POST, resource-intensive):**

**Current:**

```python
@router.post("/start-indexing")
async def onboarding_start_indexing(request: StartIndexingRequest):
```

**Replace with:**

```python
@router.post("/start-indexing")
@limiter.limit("5/minute")
async def onboarding_start_indexing(request: Request, body: StartIndexingRequest):
```

Then change every `request.init_data` to `body.init_data` and `request.chat_id` to `body.chat_id` in the function body.

---

**File:** `src/api/routes/onboarding/dashboard.py`

**Current imports (lines 1-10):**

```python
"""Dashboard detail endpoints for onboarding Mini App."""

from fastapi import APIRouter, Query

from src.services.core.dashboard_service import DashboardService
from src.services.core.health_check import HealthCheckService
from src.services.core.instagram_account_service import InstagramAccountService
from src.services.core.settings_service import SettingsService

from .helpers import _validate_request
```

**Replace with:**

```python
"""Dashboard detail endpoints for onboarding Mini App."""

from fastapi import APIRouter, Query, Request

from src.api.middleware import limiter
from src.services.core.dashboard_service import DashboardService
from src.services.core.health_check import HealthCheckService
from src.services.core.instagram_account_service import InstagramAccountService
from src.services.core.settings_service import SettingsService

from .helpers import _validate_request
```

**Add rate limit decorators to each endpoint (all GET with query params, so just add `request: Request` as first param):**

| Endpoint | Rate Limit | Change |
|----------|------------|--------|
| `onboarding_queue_detail` | `30/minute` | Add `request: Request` as first param |
| `onboarding_history_detail` | `30/minute` | Add `request: Request` as first param |
| `onboarding_media_stats` | `30/minute` | Add `request: Request` as first param |
| `onboarding_accounts` | `30/minute` | Add `request: Request` as first param |
| `onboarding_system_status` | `30/minute` | Add `request: Request` as first param |

**Example for `onboarding_queue_detail`:**

**Current:**

```python
@router.get("/queue-detail")
async def onboarding_queue_detail(
    init_data: str,
    chat_id: int,
    limit: int = Query(default=10, ge=1, le=50),
):
```

**Replace with:**

```python
@router.get("/queue-detail")
@limiter.limit("30/minute")
async def onboarding_queue_detail(
    request: Request,
    init_data: str,
    chat_id: int,
    limit: int = Query(default=10, ge=1, le=50),
):
```

Apply the same pattern to `onboarding_history_detail`, `onboarding_media_stats`, `onboarding_accounts`, and `onboarding_system_status`.

---

**File:** `src/api/routes/onboarding/settings.py`

**Current imports (lines 1-25):**

```python
"""Settings and schedule action endpoints for onboarding Mini App."""

import httpx
from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import OperationalError

from src.config.settings import settings
```

**Replace first 4 lines with:**

```python
"""Settings and schedule action endpoints for onboarding Mini App."""

import httpx
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.exc import OperationalError

from src.api.middleware import limiter
from src.config.settings import settings
```

**Add decorators and rename `request` to `body` for each POST endpoint:**

| Endpoint | Rate Limit | Rename |
|----------|------------|--------|
| `onboarding_toggle_setting` | `10/minute` | `request` -> `body` |
| `onboarding_update_setting` | `10/minute` | `request` -> `body` |
| `onboarding_switch_account` | `10/minute` | `request` -> `body` |
| `onboarding_remove_account` | `10/minute` | `request` -> `body` |
| `onboarding_disconnect_gdrive` | `5/minute` | `request` -> `body` |
| `onboarding_sync_media` | `5/minute` | `request` -> `body` |
| `onboarding_queue_preview` | `20/minute` | `request` -> `body` |
| `onboarding_add_account` | `5/minute` | `request` -> `body` |

**Example for `onboarding_toggle_setting`:**

**Current:**

```python
@router.post("/toggle-setting")
async def onboarding_toggle_setting(request: ToggleSettingRequest):
    """Toggle a boolean setting (is_paused, dry_run_mode) from dashboard."""
    _validate_request(request.init_data, request.chat_id)
```

**Replace with:**

```python
@router.post("/toggle-setting")
@limiter.limit("10/minute")
async def onboarding_toggle_setting(request: Request, body: ToggleSettingRequest):
    """Toggle a boolean setting (is_paused, dry_run_mode) from dashboard."""
    _validate_request(body.init_data, body.chat_id)
```

Then update ALL `request.` references in the function body to `body.`:
- `request.setting_name` -> `body.setting_name`
- `request.chat_id` -> `body.chat_id`
- `request.init_data` -> `body.init_data`

Apply the same rename-and-decorate pattern to every POST endpoint in `settings.py`.

---

### Step 7: Update `src/api/app.py` -- final version

After extracting `limiter` to `middleware.py`, here is the **complete final content** of `app.py`:

```python
"""FastAPI application for Storyline AI OAuth flows and Mini App."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.api.middleware import SecurityHeadersMiddleware, limiter
from src.api.routes.oauth import router as oauth_router
from src.api.routes.onboarding import router as onboarding_router
from src.config.settings import settings

# ---------------------------------------------------------------------------
# App construction — disable docs in production
# ---------------------------------------------------------------------------
_is_production = settings.ENVIRONMENT == "production"

app = FastAPI(
    title="Storyline AI API",
    description="OAuth and API endpoints for Storyline AI",
    version="0.1.0",
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
    openapi_url=None if _is_production else "/openapi.json",
)

# Attach limiter state to the app (required by slowapi)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---------------------------------------------------------------------------
# Middleware (order matters — last added runs first in Starlette)
# ---------------------------------------------------------------------------

# Security headers — runs on every response
app.add_middleware(SecurityHeadersMiddleware)

# CORS — restrict to our own domain in production
_cors_origins = (
    [settings.OAUTH_REDIRECT_BASE_URL]
    if settings.OAUTH_REDIRECT_BASE_URL
    else ["http://localhost:8000"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# ---------------------------------------------------------------------------
# Static files for Mini App
# ---------------------------------------------------------------------------
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ---------------------------------------------------------------------------
# Register routes
# ---------------------------------------------------------------------------
app.include_router(oauth_router, prefix="/auth")
app.include_router(onboarding_router, prefix="/api/onboarding")


# ---------------------------------------------------------------------------
# Top-level routes
# ---------------------------------------------------------------------------
@app.get("/webapp/onboarding")
@limiter.limit("30/minute")
async def serve_onboarding_webapp(request: Request):
    """Serve the onboarding Mini App HTML."""
    html_path = STATIC_DIR / "onboarding" / "index.html"
    if not html_path.exists():
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Onboarding app not found")
    return FileResponse(str(html_path), media_type="text/html")
```

---

### Rate Limit Summary

| Endpoint Category | Rate Limit | Rationale |
|-------------------|------------|-----------|
| OAuth start (`/auth/*/start`) | 10/minute | Token generation, no auth, high abuse risk |
| OAuth callback (`/auth/*/callback`) | 10/minute | Token exchange, triggered by redirect |
| Auth init (`/api/onboarding/init`) | 20/minute | Authentication endpoint, moderate abuse risk |
| OAuth URL generation (`/api/onboarding/oauth-url/*`) | 10/minute | Generates state tokens |
| Resource-intensive mutations (`start-indexing`, `sync-media`, `disconnect-gdrive`, `add-account`) | 5/minute | Triggers external API calls or heavy DB operations |
| Settings mutations (`toggle-setting`, `update-setting`, `switch-account`, `remove-account`, `schedule`, `complete`) | 10/minute | State-changing but lightweight |
| Dashboard reads (`queue-detail`, `history-detail`, `media-stats`, `accounts`, `system-status`) | 30/minute | Read-only, low risk, but prevent scraping |
| Static page (`/webapp/onboarding`) | 30/minute | HTML serving, low risk |

---

## Test Plan

### New test file: `tests/src/api/test_middleware.py`

Create this file with the following tests:

```python
"""Tests for API security middleware and rate limiting configuration."""

import pytest
from unittest.mock import patch
from starlette.testclient import TestClient


class TestSecurityHeadersMiddleware:
    """Verify security headers are present on all responses."""

    @pytest.fixture
    def client(self):
        """Create a test client with mocked settings."""
        with patch("src.config.settings.Settings") as MockSettings:
            mock_settings = MockSettings.return_value
            mock_settings.ENVIRONMENT = "development"
            mock_settings.OAUTH_REDIRECT_BASE_URL = None
            mock_settings.TELEGRAM_BOT_TOKEN = "test"
            mock_settings.TELEGRAM_CHANNEL_ID = 123
            mock_settings.ADMIN_TELEGRAM_CHAT_ID = 123

            # Re-import to pick up mocked settings
            from src.api.app import app

            return TestClient(app)

    def test_hsts_header_present(self, client):
        """HSTS header is set on every response."""
        response = client.get("/webapp/onboarding")
        # Even 404 should have security headers
        assert "strict-transport-security" in response.headers
        assert "max-age=31536000" in response.headers["strict-transport-security"]

    def test_x_frame_options_deny(self, client):
        """X-Frame-Options is DENY on every response."""
        response = client.get("/webapp/onboarding")
        assert response.headers.get("x-frame-options") == "DENY"

    def test_x_content_type_options_nosniff(self, client):
        """X-Content-Type-Options is nosniff on every response."""
        response = client.get("/webapp/onboarding")
        assert response.headers.get("x-content-type-options") == "nosniff"

    def test_referrer_policy_present(self, client):
        """Referrer-Policy header is set."""
        response = client.get("/webapp/onboarding")
        assert (
            response.headers.get("referrer-policy")
            == "strict-origin-when-cross-origin"
        )

    def test_permissions_policy_present(self, client):
        """Permissions-Policy header disables camera, microphone, geolocation."""
        response = client.get("/webapp/onboarding")
        assert "camera=()" in response.headers.get("permissions-policy", "")


class TestDocsGating:
    """Verify /docs, /redoc, /openapi.json are disabled in production."""

    def test_docs_disabled_in_production(self):
        """Docs endpoints return 404 when ENVIRONMENT=production."""
        with patch.dict("os.environ", {"ENVIRONMENT": "production"}):
            # Must reload the module to pick up the env change
            import importlib
            import src.config.settings
            importlib.reload(src.config.settings)
            import src.api.app
            importlib.reload(src.api.app)

            client = TestClient(src.api.app.app)
            assert client.get("/docs").status_code == 404
            assert client.get("/redoc").status_code == 404
            assert client.get("/openapi.json").status_code == 404

    def test_docs_enabled_in_development(self):
        """Docs endpoints are accessible when ENVIRONMENT=development."""
        with patch.dict("os.environ", {"ENVIRONMENT": "development"}):
            import importlib
            import src.config.settings
            importlib.reload(src.config.settings)
            import src.api.app
            importlib.reload(src.api.app)

            client = TestClient(src.api.app.app)
            assert client.get("/docs").status_code == 200
            assert client.get("/openapi.json").status_code == 200


class TestRateLimiting:
    """Verify rate limiting is configured and enforced."""

    def test_rate_limit_exceeded_returns_429(self):
        """Exceeding rate limit returns HTTP 429."""
        from src.api.app import app

        client = TestClient(app)
        # Hit the onboarding webapp endpoint rapidly
        # 30/minute limit -- send 31 requests
        responses = []
        for _ in range(35):
            resp = client.get("/webapp/onboarding")
            responses.append(resp.status_code)

        assert 429 in responses, "Expected at least one 429 after exceeding rate limit"

    def test_rate_limit_header_present(self):
        """Rate-limited responses include retry-after or rate limit headers."""
        from src.api.app import app

        client = TestClient(app)
        response = client.get("/webapp/onboarding")
        # slowapi adds X-RateLimit headers to responses
        # Check for at least one rate-limit-related header
        rate_headers = [
            h for h in response.headers if "ratelimit" in h.lower()
        ]
        assert len(rate_headers) > 0, "Expected rate limit headers in response"
```

**Note:** The docs gating tests use `importlib.reload()` because the `_is_production` flag and the `FastAPI(docs_url=...)` call happen at module import time. The reload approach is the standard pattern for testing module-level configuration. An alternative approach is to extract the app factory into a `create_app()` function, but that is a larger refactor beyond this phase's scope.

### Existing tests to verify

No existing tests directly test `app.py` (no `test_app.py` file exists). All existing tests are for models and services, which are unaffected by this change. Run the full test suite to verify no regressions:

```bash
pytest
```

### Coverage expectations

- `src/api/middleware.py` -- 100% coverage from the `SecurityHeadersMiddleware` tests
- `src/api/app.py` -- module-level configuration code covered by docs gating tests; route-level covered by rate limit tests
- All modified route files -- existing tests (if any) continue to pass; new rate limit behavior is covered by the integration test

---

## Documentation Updates

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Security
- Disabled `/docs`, `/redoc`, `/openapi.json` in production (`ENVIRONMENT=production`)
- Added security headers middleware (HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy)
- Added rate limiting via slowapi — stricter on OAuth/auth endpoints (5-10/min), lenient on reads (30/min)
```

### Railway env var setup

After deploying, set the following env var on **both** the worker and API services in Railway:

```
ENVIRONMENT=production
```

This is a one-time manual step. Document in `documentation/operations/` or the deployment runbook.

---

## Stress Testing & Edge Cases

1. **Rate limit state is in-memory:** If the API service restarts (Railway redeploy, crash recovery), all rate limit counters reset. This is acceptable for a single-instance deployment. If the API scales to multiple instances, switch to a Redis-backed store (`slowapi` supports `limits.storage.RedisStorage`).

2. **Reverse proxy IP forwarding:** Railway's load balancer sets `X-Forwarded-For`. The `get_remote_address` function from slowapi reads from this header when present. Verify in production logs that rate limiting is not being applied to Railway's internal IP instead of the client IP. If it is, switch to a custom key function:
   ```python
   def get_real_ip(request: Request) -> str:
       forwarded = request.headers.get("x-forwarded-for")
       if forwarded:
           return forwarded.split(",")[0].strip()
       return request.client.host
   ```

3. **HSTS preload consideration:** The current HSTS header includes `includeSubDomains` but NOT `preload`. Adding `preload` would submit the domain to browser preload lists, which is irreversible without a multi-month removal process. Do NOT add `preload` unless the team explicitly decides to.

4. **OAuth callback rate limit and Meta redirects:** Meta's OAuth flow redirects the user's browser to the callback endpoint. If Meta's servers are slow and the user refreshes, they may hit the rate limit. 10/minute is generous enough for this scenario (a user would need to complete 10 full OAuth flows in one minute to be blocked).

5. **Empty `ENVIRONMENT` env var:** If `ENVIRONMENT` is set to an empty string, the condition `settings.ENVIRONMENT == "production"` evaluates to `False`, so docs remain enabled. This is safe -- erring on the side of accessibility when config is missing.

---

## Verification Checklist

After implementation, verify each item:

- [ ] `ENVIRONMENT` setting added to `Settings` class with default `"development"`
- [ ] `slowapi>=0.1.9` added to `requirements.txt`
- [ ] `pip install -r requirements.txt` succeeds without errors
- [ ] `src/api/middleware.py` created with `SecurityHeadersMiddleware` and `limiter`
- [ ] `src/api/app.py` uses `docs_url=None` / `redoc_url=None` / `openapi_url=None` when `ENVIRONMENT=production`
- [ ] `src/api/app.py` registers `SecurityHeadersMiddleware`
- [ ] `src/api/app.py` attaches `limiter` to `app.state` and registers the 429 exception handler
- [ ] Every route function in `oauth.py`, `setup.py`, `dashboard.py`, `settings.py` has a `@limiter.limit()` decorator
- [ ] Every route function has `request: Request` as its first parameter
- [ ] POST endpoints that previously used `request: PydanticModel` now use `request: Request, body: PydanticModel` with all internal references updated to `body.`
- [ ] No circular imports (run `python -c "from src.api.app import app"` to verify)
- [ ] `ruff check src/ tests/` passes
- [ ] `ruff format --check src/ tests/` passes
- [ ] `pytest` passes with no failures
- [ ] **Manual: local dev** -- `uvicorn src.api.app:app --reload` starts, `/docs` loads, security headers visible in browser devtools Network tab
- [ ] **Manual: simulated production** -- `ENVIRONMENT=production uvicorn src.api.app:app` starts, `/docs` returns 404, `/openapi.json` returns 404

---

## What NOT To Do

1. **Do NOT import `limiter` from `app.py` in route files.** This creates a circular import because `app.py` imports the route modules. The limiter MUST live in `middleware.py` (or another module that doesn't import routes).

2. **Do NOT use `os.getenv("RAILWAY_ENVIRONMENT")` to gate docs.** This couples the application to Railway. Use the first-class `ENVIRONMENT` setting in `Settings` which works on any platform.

3. **Do NOT add Content-Security-Policy yet.** The OAuth callback pages use inline `<style>` blocks. A CSP that blocks inline styles would break those pages. A CSP that allows `'unsafe-inline'` provides minimal value. Fix the inline styles first (move to static CSS), then add CSP.

4. **Do NOT add `preload` to the HSTS header.** HSTS preload list inclusion is effectively permanent. Only add it after deliberate team discussion.

5. **Do NOT use Redis for rate limiting storage.** The current deployment is single-instance. In-memory storage is simpler, has zero dependencies, and resets on deploy (which is acceptable). Revisit if/when the API scales to multiple instances.

6. **Do NOT rename the `request` parameter on GET endpoints.** GET endpoints that use query parameters (like `dashboard.py` endpoints) don't have a Pydantic model parameter named `request`. Just add `request: Request` as the first parameter alongside the existing query params. The rename-to-`body` pattern is ONLY needed for POST endpoints where the existing parameter is named `request` and typed as a Pydantic model.

7. **Do NOT forget to set `ENVIRONMENT=production` on Railway.** The docs gating is inert without this env var. After the PR is merged and deployed, set it on BOTH the worker and API services. The default is `"development"`, so forgetting this step means docs remain exposed.

8. **Do NOT apply rate limits inside route function bodies.** Always use the `@limiter.limit()` decorator. Programmatic limiting inside the function would bypass slowapi's middleware integration and header injection.

9. **Do NOT set the rate limit exception handler globally via middleware.** Use `app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)` as shown. Adding it as middleware would double-process responses.
