"""Onboarding API routes — setup wizard, dashboard, and settings."""

from fastapi import APIRouter

from src.api.routes.onboarding.dashboard import router as dashboard_router
from src.api.routes.onboarding.settings import router as settings_router
from src.api.routes.onboarding.setup import router as setup_router

router = APIRouter()
router.include_router(setup_router)
router.include_router(dashboard_router)
router.include_router(settings_router)
