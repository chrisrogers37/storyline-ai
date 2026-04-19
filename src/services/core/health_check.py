"""Health check service - system health monitoring."""

from datetime import datetime, timedelta, timezone

from src.services.base_service import BaseService
from src.repositories.queue_repository import QueueRepository
from src.repositories.history_repository import HistoryRepository
from src.repositories.base_repository import BaseRepository
from src.config.settings import settings
from src.utils.logger import logger


class HealthCheckService(BaseService):
    """System health monitoring."""

    QUEUE_BACKLOG_THRESHOLD = 10  # JIT queue is 0-5 items; 10+ indicates a problem
    MAX_PENDING_AGE_HOURS = 4  # JIT items should be acted on within hours, not days
    RECENT_POSTS_WINDOW_HOURS = 48
    POOL_WARNING_DAYS = 7  # Warn when category has < 7 days of runway
    POOL_CRITICAL_DAYS = 2  # Critical when < 2 days of runway
    TOKEN_WARNING_DAYS = 7  # Warn when token expires in < 7 days
    TOKEN_CRITICAL_DAYS = 1  # Critical when < 1 day

    def __init__(self):
        super().__init__()
        self.queue_repo = QueueRepository()
        self.history_repo = HistoryRepository()

        # Lazy-loaded services for Instagram checks
        self._token_service = None
        self._instagram_service = None

        self._media_repo = None
        self._settings_service = None

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

    @property
    def media_repo(self):
        """Lazy-load media repository."""
        if self._media_repo is None:
            from src.repositories.media_repository import MediaRepository

            self._media_repo = MediaRepository()
        return self._media_repo

    @property
    def settings_service(self):
        """Lazy-load settings service."""
        if self._settings_service is None:
            from src.services.core.settings_service import SettingsService

            self._settings_service = SettingsService()
        return self._settings_service

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
            "media_pool": self._check_media_pool(),
            "loop_liveness": self._check_loop_liveness(),
        }

        # Determine overall status
        all_healthy = all(check["healthy"] for check in checks.values())
        overall_status = "healthy" if all_healthy else "unhealthy"

        return {
            "status": overall_status,
            "checks": checks,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _check_database(self) -> dict:
        """Check database connectivity."""
        try:
            BaseRepository.check_connection()
            return {"healthy": True, "message": "Database connection OK"}
        except Exception as e:  # noqa: BLE001 — health check must not crash
            logger.error(f"Database health check failed: {e}", exc_info=True)
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

        except Exception as e:  # noqa: BLE001 — health check must not crash
            logger.error(f"Instagram API health check failed: {e}", exc_info=True)
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
                age = datetime.now(timezone.utc) - oldest_pending.created_at
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

        except Exception as e:  # noqa: BLE001 — health check must not crash
            logger.error(f"Queue health check failed: {e}", exc_info=True)
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

        except Exception as e:  # noqa: BLE001 — health check must not crash
            logger.error(f"Recent posts health check failed: {e}", exc_info=True)
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
            except Exception as e:  # noqa: BLE001 — health check must not crash
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
                if datetime.now(timezone.utc) - completed > stale_threshold:
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

        except Exception as e:  # noqa: BLE001 — health check must not crash
            logger.error(f"Media sync health check failed: {e}", exc_info=True)
            return {
                "healthy": False,
                "message": f"Sync check error: {str(e)}",
                "enabled": True,
            }

    def _check_loop_liveness(self) -> dict:
        """Check if background loops are still ticking.

        Uses in-memory heartbeat timestamps from src.main. Each loop
        records a heartbeat on every iteration; a loop is stale if its
        last heartbeat exceeds 2x its expected interval.
        """
        # Inline import: src.main imports services, so a top-level import would be circular
        from src.main import get_loop_liveness

        liveness = get_loop_liveness()
        stale = [name for name, info in liveness.items() if not info["alive"]]

        if stale:
            return {
                "healthy": False,
                "message": f"Stale loops: {', '.join(stale)}",
                "loops": liveness,
            }

        return {
            "healthy": True,
            "message": f"All {len(liveness)} loops alive",
            "loops": liveness,
        }

    def _check_media_pool(self) -> dict:
        """Check media pool health across all active tenants.

        Reports the lowest-runway category across all tenants.
        For per-tenant detail, use check_media_pool_for_chat().
        """
        try:
            active_chats = self.settings_service.get_all_active_chats()
            if not active_chats:
                return {"healthy": True, "message": "No active chats configured"}

            worst_runway = float("inf")
            worst_detail = None

            for chat in active_chats:
                pool_info = self.check_media_pool_for_chat(
                    chat.telegram_chat_id, chat_settings=chat
                )
                for cat_info in pool_info.get("categories", []):
                    if cat_info["runway_days"] < worst_runway:
                        worst_runway = cat_info["runway_days"]
                        worst_detail = cat_info

            if worst_detail is None:
                return {"healthy": True, "message": "No categories configured"}

            if worst_runway <= self.POOL_CRITICAL_DAYS:
                return {
                    "healthy": False,
                    "message": (
                        f"Critical: '{worst_detail['category']}' has "
                        f"{worst_detail['eligible']} items "
                        f"({worst_detail['runway_days']:.0f} days remaining)"
                    ),
                    "worst_category": worst_detail,
                }

            if worst_runway <= self.POOL_WARNING_DAYS:
                return {
                    "healthy": False,
                    "message": (
                        f"Low pool: '{worst_detail['category']}' has "
                        f"{worst_detail['eligible']} items "
                        f"({worst_detail['runway_days']:.0f} days remaining)"
                    ),
                    "worst_category": worst_detail,
                }

            return {
                "healthy": True,
                "message": f"All categories have >{self.POOL_WARNING_DAYS} days of runway",
            }

        except Exception as e:  # noqa: BLE001 — health check must not crash
            logger.error(f"Media pool check failed: {e}", exc_info=True)
            return {"healthy": False, "message": f"Pool check error: {str(e)}"}

    def check_media_pool_for_chat(
        self, telegram_chat_id: int, *, chat_settings=None
    ) -> dict:
        """Check media pool health for a specific chat.

        Returns per-category breakdown with eligible counts and runway estimates.

        Args:
            telegram_chat_id: The tenant's Telegram chat ID.
            chat_settings: Pre-loaded ChatSettings (avoids extra DB lookup).

        Returns:
            Dict with categories list, each containing: category, eligible,
            posts_per_day_share, runway_days.
        """
        if chat_settings is None:
            chat_settings = self.settings_service.get_settings(telegram_chat_id)

        chat_settings_id = str(chat_settings.id)
        posts_per_day = chat_settings.posts_per_day or 1

        eligible_by_category = self.media_repo.count_eligible_by_category(
            chat_settings_id
        )

        if not eligible_by_category:
            return {
                "total_eligible": 0,
                "posts_per_day": posts_per_day,
                "categories": [],
                "warnings": ["No eligible media in any category"],
            }

        num_categories = len(eligible_by_category)
        categories = []
        warnings = []

        for category, eligible in sorted(eligible_by_category.items()):
            posts_per_day_share = posts_per_day / num_categories
            runway_days = (
                eligible / posts_per_day_share if posts_per_day_share else float("inf")
            )

            cat_info = {
                "category": category,
                "eligible": eligible,
                "posts_per_day_share": round(posts_per_day_share, 2),
                "runway_days": round(runway_days, 1),
            }
            categories.append(cat_info)

            if runway_days <= self.POOL_CRITICAL_DAYS:
                warnings.append(
                    f"CRITICAL: '{category}' has {eligible} items "
                    f"(< {self.POOL_CRITICAL_DAYS} days remaining)"
                )
            elif runway_days <= self.POOL_WARNING_DAYS:
                warnings.append(
                    f"LOW: '{category}' has {eligible} items "
                    f"({runway_days:.0f} days remaining)"
                )

        total_eligible = sum(eligible_by_category.values())
        return {
            "total_eligible": total_eligible,
            "posts_per_day": posts_per_day,
            "categories": categories,
            "warnings": warnings,
        }

    def format_pool_alert(self, pool_info: dict) -> str | None:
        """Format a Telegram alert message from pool check results.

        Returns None if no categories are below the warning threshold.
        """
        low_categories = [
            c
            for c in pool_info.get("categories", [])
            if c["runway_days"] <= self.POOL_WARNING_DAYS
        ]
        if not low_categories:
            return None

        lines = ["\u26a0\ufe0f Content pool alert:"]
        for cat in low_categories:
            lines.append(
                f"  \u2022 {cat['category']}: "
                f"{cat['eligible']} items left "
                f"({cat['runway_days']:.0f} days remaining)"
            )
        lines.append("\nAdd more content to Google Drive to keep posting.")
        return "\n".join(lines)

    def check_gdrive_token_for_chat(
        self, telegram_chat_id: int, *, chat_settings=None
    ) -> dict:
        """Check Google Drive token health for a specific chat.

        Returns:
            Dict with healthy, expires_in_days, needs_refresh, message.
        """
        if chat_settings is None:
            chat_settings = self.settings_service.get_settings(telegram_chat_id)

        chat_settings_id = str(chat_settings.id)

        if not getattr(chat_settings, "media_sync_enabled", False):
            return {"healthy": True, "message": "Media sync disabled", "enabled": False}

        source_type = getattr(chat_settings, "media_source_type", None)
        if source_type != "google_drive":
            return {
                "healthy": True,
                "message": f"Source is '{source_type}', not Google Drive",
                "enabled": False,
            }

        try:
            token_health = self.token_service.check_token_health_for_chat(
                "google_drive", chat_settings_id
            )
        except Exception as e:  # noqa: BLE001 — health check must not crash
            logger.error(f"GDrive token health check failed: {e}", exc_info=True)
            return {"healthy": False, "message": f"Token check error: {str(e)}"}

        if not token_health["exists"]:
            return {
                "healthy": False,
                "message": "No Google Drive token found",
                "expires_in_days": None,
            }

        auto_refreshable = token_health.get("auto_refreshable", False)

        if not token_health["valid"]:
            return {
                "healthy": False,
                "message": "Google Drive token expired — reconnect required",
                "expires_in_days": 0,
            }

        expires_in_hours = token_health.get("expires_in_hours")
        expires_in_days = (
            round(expires_in_hours / 24, 1) if expires_in_hours is not None else None
        )

        # Access token expiry warnings don't apply when auto-refresh is available
        if not auto_refreshable:
            if (
                expires_in_days is not None
                and expires_in_days <= self.TOKEN_CRITICAL_DAYS
            ):
                return {
                    "healthy": False,
                    "message": f"Google Drive token expires in {expires_in_days:.0f} day(s)",
                    "expires_in_days": expires_in_days,
                    "needs_refresh": token_health.get("needs_refresh", False),
                }

            if (
                expires_in_days is not None
                and expires_in_days <= self.TOKEN_WARNING_DAYS
            ):
                return {
                    "healthy": False,
                    "message": f"Google Drive token expires in {expires_in_days:.0f} days",
                    "expires_in_days": expires_in_days,
                    "needs_refresh": token_health.get("needs_refresh", False),
                }

        return {
            "healthy": True,
            "message": (
                "Google Drive token OK"
                + (" (auto-refresh active)" if auto_refreshable else "")
                + (
                    f" ({expires_in_days:.0f} days remaining)"
                    if expires_in_days and not auto_refreshable
                    else ""
                )
            ),
            "expires_in_days": expires_in_days,
        }

    def format_token_alert(self, token_info: dict, telegram_chat_id: int) -> str | None:
        """Format a Telegram alert for expiring/expired Google Drive token.

        Returns None if no alert needed (healthy token).
        """
        if token_info.get("healthy", True):
            return None

        expires_in_days = token_info.get("expires_in_days")

        if expires_in_days is not None and expires_in_days > 0:
            text = f"\u26a0\ufe0f Google Drive token expiring in {expires_in_days:.0f} day(s)."
        else:
            text = "\u26a0\ufe0f Google Drive token has expired — reconnect required."

        reconnect_url = None
        if settings.OAUTH_REDIRECT_BASE_URL:
            reconnect_url = (
                f"{settings.OAUTH_REDIRECT_BASE_URL}"
                f"/auth/google-drive/start?chat_id={telegram_chat_id}"
            )
            text += f"\n\nRe-authenticate: {reconnect_url}"

        if expires_in_days is not None and expires_in_days > 0:
            expiry_date = (
                datetime.now(timezone.utc) + timedelta(days=expires_in_days)
            ).strftime("%b %d")
            text += f"\n\nIf ignored, media sync will stop on {expiry_date}."
        else:
            text += "\n\nMedia sync is paused until you reconnect."

        return text
