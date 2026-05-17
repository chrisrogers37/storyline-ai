"""FastAPI application for Storydump OAuth flows and Mini App."""

import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from src.api.rate_limit import limiter
from src.api.routes.oauth import router as oauth_router
from src.api.routes.onboarding import router as onboarding_router
from src.config.settings import settings

_START_TIME = time.time()

app = FastAPI(
    title="Storydump API",
    description="OAuth and API endpoints for Storydump",
    version="0.1.0",
)

# Proxy headers — trust X-Forwarded-For/Proto from Railway's load balancer
# so request.client.host returns the real client IP, not the proxy IP.
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])

# Rate limiting — 30 req/min per IP global default (see src/api/rate_limit.py)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

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


@app.get("/health")
async def health_check():
    """Health check endpoint for Railway. No auth required."""
    return {
        "status": "ok",
        "version": app.version,
        "uptime_seconds": int(time.time() - _START_TIME),
    }


@app.get("/webapp/onboarding")
async def serve_onboarding_webapp():
    """Serve the onboarding Mini App HTML."""
    html_path = STATIC_DIR / "onboarding" / "index.html"
    if not html_path.exists():
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Onboarding app not found")
    return FileResponse(str(html_path), media_type="text/html")
