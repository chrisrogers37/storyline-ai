"""FastAPI application for Storyline AI OAuth flows."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes.oauth import router as oauth_router

app = FastAPI(
    title="Storyline AI API",
    description="OAuth and API endpoints for Storyline AI",
    version="0.1.0",
)

# CORS middleware (needed for browser redirects)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Register routes
app.include_router(oauth_router, prefix="/auth")
