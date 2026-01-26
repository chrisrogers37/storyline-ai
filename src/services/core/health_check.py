"""Health check service - system health monitoring."""

from datetime import datetime, timedelta
from sqlalchemy import text

from src.services.base_service import BaseService
from src.repositories.queue_repository import QueueRepository
from src.repositories.history_repository import HistoryRepository
from src.config.database import get_db
from src.config.settings import settings
from src.utils.logger import logger


class HealthCheckService(BaseService):
    """System health monitoring."""

    def __init__(self):
        super().__init__()
        self.queue_repo = QueueRepository()
        self.history_repo = HistoryRepository()

        # Lazy-loaded services for Instagram checks
        self._token_service = None
        self._instagram_service = None

    @property
    def token_service(self):
        """Lazy-load token service."""
        if self._token_service is None:
            from src.services.integrations.token_refresh import TokenRefreshService

            self._token_service = TokenRefreshService()
        return self._token_service

    @property
    def instagram_service(self):
        """Lazy-load Instagram API service."""
        if self._instagram_service is None:
            from src.services.integrations.instagram_api import InstagramAPIService

            self._instagram_service = InstagramAPIService()
        return self._instagram_service

    def check_all(self) -> dict:
        """
        Run all health checks.

        Returns:
            Dict with overall status and individual check results
        """
        checks = {
            "database": self._check_database(),
            "telegram": self._check_telegram_config(),
            "instagram_api": self._check_instagram_api(),
            "queue": self._check_queue(),
            "recent_posts": self._check_recent_posts(),
        }

        # Determine overall status
        all_healthy = all(check["healthy"] for check in checks.values())
        overall_status = "healthy" if all_healthy else "unhealthy"

        return {
            "status": overall_status,
            "checks": checks,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _check_database(self) -> dict:
        """Check database connectivity."""
        try:
            db = next(get_db())
            db.execute(text("SELECT 1"))
            return {"healthy": True, "message": "Database connection OK"}
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {"healthy": False, "message": f"Database error: {str(e)}"}

    def _check_telegram_config(self) -> dict:
        """Check Telegram configuration."""
        if not settings.TELEGRAM_BOT_TOKEN:
            return {"healthy": False, "message": "Telegram bot token not configured"}

        if not settings.TELEGRAM_CHANNEL_ID:
            return {"healthy": False, "message": "Telegram channel ID not configured"}

        return {"healthy": True, "message": "Telegram configuration OK"}

    def _check_instagram_api(self) -> dict:
        """Check Instagram API health."""
        # If Instagram API is disabled, report as healthy but disabled
        if not settings.ENABLE_INSTAGRAM_API:
            return {
                "healthy": True,
                "message": "Disabled via config",
                "enabled": False,
            }

        # Check configuration
        if not settings.INSTAGRAM_ACCOUNT_ID:
            return {
                "healthy": False,
                "message": "INSTAGRAM_ACCOUNT_ID not configured",
                "enabled": True,
            }

        if not settings.FACEBOOK_APP_ID:
            return {
                "healthy": False,
                "message": "FACEBOOK_APP_ID not configured",
                "enabled": True,
            }

        # Check token health
        try:
            token_health = self.token_service.check_token_health("instagram")

            if not token_health["valid"]:
                return {
                    "healthy": False,
                    "message": f"Token invalid: {token_health.get('error', 'Unknown')}",
                    "enabled": True,
                    "token_source": token_health.get("source"),
                }

            # Check rate limit
            remaining = self.instagram_service.get_rate_limit_remaining()

            # Build response
            expires_in_hours = token_health.get("expires_in_hours")
            expires_in_days = int(expires_in_hours // 24) if expires_in_hours else None

            response = {
                "healthy": True,
                "enabled": True,
                "rate_limit_remaining": remaining,
                "rate_limit_total": settings.INSTAGRAM_POSTS_PER_HOUR,
            }

            # Add token info
            if expires_in_days is not None:
                response["token_expires_in_days"] = expires_in_days

            if token_health.get("needs_refresh"):
                response["message"] = (
                    f"OK ({remaining}/{settings.INSTAGRAM_POSTS_PER_HOUR} posts), token refresh recommended"
                )
            elif remaining == 0:
                response["healthy"] = False
                response["message"] = "Rate limit exhausted (0 posts remaining)"
            else:
                response["message"] = (
                    f"OK ({remaining}/{settings.INSTAGRAM_POSTS_PER_HOUR} posts remaining)"
                )

            return response

        except Exception as e:
            logger.error(f"Instagram API health check failed: {e}")
            return {
                "healthy": False,
                "message": f"Check failed: {str(e)}",
                "enabled": True,
            }

    def _check_queue(self) -> dict:
        """Check posting queue health."""
        try:
            pending_count = self.queue_repo.count_pending()
            oldest_pending = self.queue_repo.get_oldest_pending()

            # Alert if queue is backing up
            if pending_count > 50:
                return {
                    "healthy": False,
                    "message": f"Queue backlog: {pending_count} items pending",
                    "pending_count": pending_count,
                }

            # Alert if oldest item is very old
            if oldest_pending:
                age = datetime.utcnow() - oldest_pending.created_at
                if age > timedelta(hours=24):
                    return {
                        "healthy": False,
                        "message": f"Oldest item pending for {age.total_seconds() / 3600:.1f} hours",
                        "pending_count": pending_count,
                    }

            return {
                "healthy": True,
                "message": f"Queue healthy ({pending_count} pending)",
                "pending_count": pending_count,
            }

        except Exception as e:
            return {"healthy": False, "message": f"Queue check error: {str(e)}"}

    def _check_recent_posts(self) -> dict:
        """Check if posts have been made recently."""
        try:
            recent_posts = self.history_repo.get_recent_posts(hours=48)

            if not recent_posts:
                return {
                    "healthy": False,
                    "message": "No posts in last 48 hours",
                    "recent_count": 0,
                }

            successful_posts = [p for p in recent_posts if p.success]

            return {
                "healthy": True,
                "message": f"{len(successful_posts)}/{len(recent_posts)} successful in last 48h",
                "recent_count": len(recent_posts),
                "successful_count": len(successful_posts),
            }

        except Exception as e:
            return {"healthy": False, "message": f"Recent posts check error: {str(e)}"}
