"""Health check service - system health monitoring."""

from datetime import datetime, timedelta

from src.services.base_service import BaseService
from src.repositories.queue_repository import QueueRepository
from src.repositories.history_repository import HistoryRepository
from src.repositories.base_repository import BaseRepository
from src.config.settings import settings
from src.utils.logger import logger


class HealthCheckService(BaseService):
    """System health monitoring."""

    QUEUE_BACKLOG_THRESHOLD = 50
    MAX_PENDING_AGE_HOURS = 24
    RECENT_POSTS_WINDOW_HOURS = 48

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
            "media_sync": self._check_media_sync(),
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
            BaseRepository.check_connection()
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
            if pending_count > self.QUEUE_BACKLOG_THRESHOLD:
                return {
                    "healthy": False,
                    "message": f"Queue backlog: {pending_count} items pending",
                    "pending_count": pending_count,
                }

            # Alert if oldest item is very old
            if oldest_pending:
                age = datetime.utcnow() - oldest_pending.created_at
                if age > timedelta(hours=self.MAX_PENDING_AGE_HOURS):
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
            recent_posts = self.history_repo.get_recent_posts(
                hours=self.RECENT_POSTS_WINDOW_HOURS
            )

            if not recent_posts:
                return {
                    "healthy": False,
                    "message": f"No posts in last {self.RECENT_POSTS_WINDOW_HOURS} hours",
                    "recent_count": 0,
                }

            successful_posts = [p for p in recent_posts if p.success]

            return {
                "healthy": True,
                "message": f"{len(successful_posts)}/{len(recent_posts)} successful in last {self.RECENT_POSTS_WINDOW_HOURS}h",
                "recent_count": len(recent_posts),
                "successful_count": len(successful_posts),
            }

        except Exception as e:
            return {"healthy": False, "message": f"Recent posts check error: {str(e)}"}

    def _check_media_sync(self) -> dict:
        """Check media sync health including provider connectivity."""
        if not settings.MEDIA_SYNC_ENABLED:
            return {
                "healthy": True,
                "message": "Disabled via config",
                "enabled": False,
            }

        try:
            from src.services.core.media_sync import MediaSyncService
            from src.services.media_sources.factory import MediaSourceFactory

            # Check provider connectivity
            source_type = settings.MEDIA_SOURCE_TYPE
            source_root = settings.MEDIA_SOURCE_ROOT
            if source_type == "local" and not source_root:
                source_root = settings.MEDIA_DIR

            provider_healthy = False
            provider_message = ""
            try:
                if source_type == "local":
                    provider = MediaSourceFactory.create(
                        source_type, base_path=source_root
                    )
                elif source_type == "google_drive":
                    provider = MediaSourceFactory.create(
                        source_type, root_folder_id=source_root
                    )
                else:
                    provider = MediaSourceFactory.create(source_type)

                provider_healthy = provider.is_configured()
                if not provider_healthy:
                    provider_message = f"Provider '{source_type}' not accessible"
            except Exception as e:
                provider_message = f"Provider error: {str(e)[:100]}"

            if not provider_healthy:
                return {
                    "healthy": False,
                    "message": provider_message
                    or f"Provider '{source_type}' not configured",
                    "enabled": True,
                    "source_type": source_type,
                }

            # Check last sync run
            sync_service = MediaSyncService()
            last_sync = sync_service.get_last_sync_info()

            if not last_sync:
                return {
                    "healthy": False,
                    "message": f"No sync runs recorded yet (source: {source_type})",
                    "enabled": True,
                    "source_type": source_type,
                }

            if not last_sync["success"]:
                return {
                    "healthy": False,
                    "message": f"Last sync failed: {last_sync.get('status', 'unknown')}",
                    "enabled": True,
                    "source_type": source_type,
                    "last_run": last_sync["started_at"],
                }

            # Check if last sync is stale (more than 3x interval)
            if last_sync["completed_at"]:
                completed = datetime.fromisoformat(last_sync["completed_at"])
                stale_threshold = timedelta(
                    seconds=settings.MEDIA_SYNC_INTERVAL_SECONDS * 3
                )
                if datetime.utcnow() - completed > stale_threshold:
                    return {
                        "healthy": False,
                        "message": (
                            f"Last sync was {last_sync['completed_at']} "
                            f"(stale, expected every {settings.MEDIA_SYNC_INTERVAL_SECONDS}s)"
                        ),
                        "enabled": True,
                        "source_type": source_type,
                        "last_run": last_sync["started_at"],
                    }

            result_summary = last_sync.get("result", {}) or {}
            errors = result_summary.get("errors", 0)

            if errors > 0:
                return {
                    "healthy": True,
                    "message": (
                        f"Last sync OK with {errors} error(s) (source: {source_type})"
                    ),
                    "enabled": True,
                    "source_type": source_type,
                    "last_run": last_sync["started_at"],
                    "last_result": result_summary,
                }

            return {
                "healthy": True,
                "message": f"OK (source: {source_type}, last: {last_sync['started_at'][:16]})",
                "enabled": True,
                "source_type": source_type,
                "last_run": last_sync["started_at"],
                "last_result": result_summary,
            }

        except Exception as e:
            return {
                "healthy": False,
                "message": f"Sync check error: {str(e)}",
                "enabled": True,
            }
