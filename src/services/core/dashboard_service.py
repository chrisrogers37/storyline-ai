"""Dashboard service - read-only aggregation queries for the Mini App."""

from typing import Optional

from src.services.base_service import BaseService
from src.services.core.settings_service import SettingsService
from src.repositories.history_repository import HistoryRepository
from src.repositories.media_repository import MediaRepository
from src.repositories.queue_repository import QueueRepository
from src.repositories.category_mix_repository import CategoryMixRepository


class DashboardService(BaseService):
    """Read-only aggregation queries for dashboard endpoints.

    Encapsulates the cross-repository joins that the onboarding
    dashboard needs, keeping the API layer free of direct
    repository imports.
    """

    MIN_RECOMMENDATION_DATA_POINTS = 10

    def __init__(self):
        super().__init__()
        self.settings_service = SettingsService()
        self.queue_repo = QueueRepository()
        self.history_repo = HistoryRepository()
        self.media_repo = MediaRepository()
        self.category_mix_repo = CategoryMixRepository()

    def _resolve_chat_settings_id(self, telegram_chat_id: int) -> str:
        chat_settings = self.settings_service.get_settings(telegram_chat_id)
        return str(chat_settings.id)

    def get_queue_detail(self, telegram_chat_id: int, limit: int = 10) -> dict:
        """Return in-flight queue items with media info and activity summary.

        JIT semantics: the queue holds only items currently awaiting team
        action (0-5 typical), not a multi-day schedule.
        """
        chat_settings_id = self._resolve_chat_settings_id(telegram_chat_id)

        pending_rows = self.queue_repo.get_all_with_media(
            status="pending", chat_settings_id=chat_settings_id
        )
        processing_rows = self.queue_repo.get_all_with_media(
            status="processing", chat_settings_id=chat_settings_id
        )
        all_in_flight = pending_rows + processing_rows

        # Item list (limited) with media info from JOIN
        items = []
        for item, file_name, category in all_in_flight[:limit]:
            items.append(
                {
                    "scheduled_for": item.scheduled_for.isoformat(),
                    "media_name": file_name if file_name else "Unknown",
                    "category": (category if category else None) or "uncategorized",
                    "status": item.status,
                }
            )

        # Posts today from posting_history
        today_posts = self.history_repo.get_recent_posts(
            hours=24, chat_settings_id=chat_settings_id
        )
        posts_today = len(today_posts)

        # Last post time
        last_post_at = None
        if today_posts:
            last_post_at = today_posts[0].posted_at.isoformat()
        else:
            # Check further back
            recent = self.history_repo.get_recent_posts(
                hours=720, chat_settings_id=chat_settings_id
            )
            if recent:
                last_post_at = recent[0].posted_at.isoformat()

        return {
            "items": items,
            "total_in_flight": len(all_in_flight),
            "posts_today": posts_today,
            "last_post_at": last_post_at,
        }

    def get_history_detail(self, telegram_chat_id: int, limit: int = 10) -> dict:
        """Return recent posting history with media info."""
        chat_settings_id = self._resolve_chat_settings_id(telegram_chat_id)

        history_rows = self.history_repo.get_all_with_media(
            limit=limit, chat_settings_id=chat_settings_id
        )

        items = []
        for item, file_name, category in history_rows:
            items.append(
                {
                    "posted_at": item.posted_at.isoformat(),
                    "media_name": file_name if file_name else "Unknown",
                    "category": (category if category else None) or "uncategorized",
                    "status": item.status,
                    "posting_method": item.posting_method,
                }
            )

        return {"items": items}

    def get_media_stats(self, telegram_chat_id: int) -> dict:
        """Return media library breakdown by category."""
        chat_settings_id = self._resolve_chat_settings_id(telegram_chat_id)

        total_active = self.media_repo.count_active(chat_settings_id=chat_settings_id)
        category_counts = self.media_repo.count_by_category(
            chat_settings_id=chat_settings_id
        )

        categories = [
            {"name": name, "count": count}
            for name, count in sorted(
                category_counts.items(), key=lambda x: x[1], reverse=True
            )
        ]

        return {
            "total_active": total_active,
            "categories": categories,
        }

    def get_analytics(self, telegram_chat_id: int, days: int = 30) -> dict:
        """Return aggregated posting analytics for the dashboard.

        Combines status breakdown, method breakdown, daily counts,
        hourly distribution, and category performance into a single
        response.
        """
        with self.track_execution(
            "get_analytics",
            input_params={"telegram_chat_id": telegram_chat_id, "days": days},
        ) as run_id:
            chat_settings_id = self._resolve_chat_settings_id(telegram_chat_id)

            status_counts = self.history_repo.get_stats_by_status(
                days=days, chat_settings_id=chat_settings_id
            )
            method_counts = self.history_repo.get_stats_by_method(
                days=days, chat_settings_id=chat_settings_id
            )
            daily_counts = self.history_repo.get_daily_counts(
                days=days, chat_settings_id=chat_settings_id
            )
            hourly_dist = self.history_repo.get_hourly_distribution(
                days=days, chat_settings_id=chat_settings_id
            )
            category_stats = self.history_repo.get_stats_by_category(
                days=days, chat_settings_id=chat_settings_id
            )

            total = sum(status_counts.values())
            posted = status_counts.get("posted", 0)

            result = {
                "summary": {
                    "total_posts": total,
                    "posted": posted,
                    "skipped": status_counts.get("skipped", 0),
                    "rejected": status_counts.get("rejected", 0),
                    "failed": status_counts.get("failed", 0),
                    "success_rate": round(posted / total, 2) if total else 0,
                    "avg_per_day": round(total / days, 1),
                },
                "method_breakdown": method_counts,
                "daily_counts": daily_counts,
                "hourly_distribution": hourly_dist,
                "category_breakdown": category_stats,
                "days": days,
            }

            self.set_result_summary(run_id, {"total_posts": total, "days": days})
            return result

    def get_category_analytics(self, telegram_chat_id: int, days: int = 30) -> dict:
        """Return per-category performance with configured vs actual ratios.

        Enriches posting history stats with the configured category mix
        ratios, showing how actual posting patterns compare to the target.
        """
        with self.track_execution(
            "get_category_analytics",
            input_params={"telegram_chat_id": telegram_chat_id, "days": days},
        ) as run_id:
            chat_settings_id = self._resolve_chat_settings_id(telegram_chat_id)

            # Posting performance by category
            category_stats = self.history_repo.get_stats_by_category(
                days=days, chat_settings_id=chat_settings_id
            )

            # Configured ratios from category_post_case_mix
            configured_ratios = self.category_mix_repo.get_current_mix_as_dict(
                chat_settings_id=chat_settings_id
            )

            # Compute actual ratios and enrich with configured targets
            total_all = sum(c.get("total", 0) for c in category_stats)
            categories = []
            for cat_data in category_stats:
                name = cat_data["category"]
                total = cat_data.get("total", 0)
                actual_ratio = round(total / total_all, 2) if total_all else 0
                configured = configured_ratios.get(name)

                entry = {
                    "category": name,
                    "posted": cat_data.get("posted", 0),
                    "skipped": cat_data.get("skipped", 0),
                    "rejected": cat_data.get("rejected", 0),
                    "failed": cat_data.get("failed", 0),
                    "total": total,
                    "success_rate": cat_data.get("success_rate", 0),
                    "actual_ratio": actual_ratio,
                    "configured_ratio": float(configured) if configured else None,
                }
                categories.append(entry)

            self.set_result_summary(
                run_id, {"categories": len(categories), "days": days}
            )
            return {
                "categories": categories,
                "total_posts": total_all,
                "days": days,
            }

    def get_category_mix_drift(self, telegram_chat_id: int, days: int = 7) -> dict:
        """Compare actual posting ratios against configured targets.

        Returns per-category drift (absolute difference between actual
        and configured ratios) with warning/critical thresholds.
        """
        with self.track_execution(
            "get_category_mix_drift",
            input_params={"telegram_chat_id": telegram_chat_id, "days": days},
        ) as run_id:
            chat_settings_id = self._resolve_chat_settings_id(telegram_chat_id)

            configured = self.category_mix_repo.get_current_mix_as_dict(
                chat_settings_id=chat_settings_id
            )
            actual_stats = self.history_repo.get_stats_by_category(
                days=days, chat_settings_id=chat_settings_id
            )

            total_posted = sum(c.get("posted", 0) for c in actual_stats)

            categories = []
            max_drift = 0.0
            for name, target_ratio in configured.items():
                actual_posted = 0
                for c in actual_stats:
                    if c["category"] == name:
                        actual_posted = c.get("posted", 0)
                        break
                actual_ratio = (
                    round(actual_posted / total_posted, 2) if total_posted else 0
                )
                drift = round(abs(actual_ratio - float(target_ratio)), 2)
                max_drift = max(max_drift, drift)

                status = "ok"
                if drift >= 0.25:
                    status = "critical"
                elif drift >= 0.10:
                    status = "warning"

                categories.append(
                    {
                        "category": name,
                        "configured_ratio": float(target_ratio),
                        "actual_ratio": actual_ratio,
                        "drift": drift,
                        "status": status,
                    }
                )

            healthy = max_drift < 0.10
            self.set_result_summary(
                run_id,
                {
                    "healthy": healthy,
                    "max_drift": max_drift,
                    "categories": len(categories),
                },
            )
            return {
                "healthy": healthy,
                "max_drift": max_drift,
                "categories": categories,
                "total_posted": total_posted,
                "days": days,
            }

    def get_dead_content_report(
        self, telegram_chat_id: int, min_age_days: int = 30
    ) -> dict:
        """Surface media items that have never been posted.

        Returns dead content count and per-category breakdown,
        alongside total pool stats for context.
        """
        with self.track_execution(
            "get_dead_content_report",
            input_params={
                "telegram_chat_id": telegram_chat_id,
                "min_age_days": min_age_days,
            },
        ) as run_id:
            chat_settings_id = self._resolve_chat_settings_id(telegram_chat_id)

            total_active = self.media_repo.count_active(
                chat_settings_id=chat_settings_id
            )
            dead_by_category = self.media_repo.count_dead_content_by_category(
                min_age_days=min_age_days, chat_settings_id=chat_settings_id
            )
            total_dead = sum(c["dead_count"] for c in dead_by_category)
            dead_pct = round(total_dead / total_active, 2) if total_active else 0

            self.set_result_summary(
                run_id,
                {"total_dead": total_dead, "dead_pct": dead_pct},
            )
            return {
                "total_active": total_active,
                "total_dead": total_dead,
                "dead_percentage": dead_pct,
                "by_category": dead_by_category,
                "min_age_days": min_age_days,
            }

    def get_schedule_recommendations(
        self, telegram_chat_id: int, days: int = 90
    ) -> dict:
        """Analyze posting history to recommend optimal posting times.

        Returns hourly approval rates, day-of-week patterns, and
        human-readable recommendations based on when posts are most
        frequently approved vs skipped/rejected.
        """
        with self.track_execution(
            "get_schedule_recommendations",
            input_params={"telegram_chat_id": telegram_chat_id, "days": days},
        ) as run_id:
            chat_settings_id = self._resolve_chat_settings_id(telegram_chat_id)

            hourly = self.history_repo.get_hourly_approval_rates(
                days=days, chat_settings_id=chat_settings_id
            )
            dow = self.history_repo.get_dow_approval_rates(
                days=days, chat_settings_id=chat_settings_id
            )

            total_data_points = sum(h.get("total", 0) for h in hourly)

            if total_data_points < self.MIN_RECOMMENDATION_DATA_POINTS:
                self.set_result_summary(
                    run_id,
                    {"status": "insufficient_data", "data_points": total_data_points},
                )
                return {
                    "status": "insufficient_data",
                    "message": (
                        f"Need at least {self.MIN_RECOMMENDATION_DATA_POINTS} posts to generate "
                        f"recommendations (have {total_data_points})"
                    ),
                    "hourly_rates": [],
                    "dow_rates": [],
                    "recommendations": [],
                    "days": days,
                }

            recommendations = self._generate_recommendations(hourly, dow)

            self.set_result_summary(
                run_id,
                {
                    "status": "ok",
                    "data_points": total_data_points,
                    "recommendation_count": len(recommendations),
                },
            )
            return {
                "status": "ok",
                "hourly_rates": hourly,
                "dow_rates": dow,
                "recommendations": recommendations,
                "days": days,
                "data_points": total_data_points,
                "timezone": "UTC",
            }

    @staticmethod
    def _generate_recommendations(hourly: list, dow: list) -> list:
        """Generate human-readable schedule recommendations from patterns."""
        recommendations = []

        # Find best and worst hours (need at least some data per hour)
        hours_with_data = [h for h in hourly if h.get("total", 0) >= 3]
        if hours_with_data:
            best_hour = max(hours_with_data, key=lambda h: h["approval_rate"])
            worst_hour = min(hours_with_data, key=lambda h: h["approval_rate"])

            if best_hour["approval_rate"] > worst_hour["approval_rate"] + 0.1:
                recommendations.append(
                    {
                        "type": "best_hour",
                        "message": (
                            f"Posts at {best_hour['hour']}:00 UTC have the highest "
                            f"approval rate ({best_hour['approval_rate']:.0%})"
                        ),
                        "hour": best_hour["hour"],
                        "approval_rate": best_hour["approval_rate"],
                    }
                )

            if worst_hour["approval_rate"] < 0.7 and worst_hour["total"] >= 5:
                recommendations.append(
                    {
                        "type": "worst_hour",
                        "message": (
                            f"Posts at {worst_hour['hour']}:00 UTC have a low "
                            f"approval rate ({worst_hour['approval_rate']:.0%}) — "
                            f"consider avoiding this time"
                        ),
                        "hour": worst_hour["hour"],
                        "approval_rate": worst_hour["approval_rate"],
                    }
                )

        # Find best and worst days
        days_with_data = [d for d in dow if d.get("total", 0) >= 3]
        if days_with_data:
            best_day = max(days_with_data, key=lambda d: d["approval_rate"])
            worst_day = min(days_with_data, key=lambda d: d["approval_rate"])

            if best_day["approval_rate"] > worst_day["approval_rate"] + 0.1:
                recommendations.append(
                    {
                        "type": "best_day",
                        "message": (
                            f"{best_day['day_name']}s have the highest approval rate "
                            f"({best_day['approval_rate']:.0%})"
                        ),
                        "day_name": best_day["day_name"],
                        "approval_rate": best_day["approval_rate"],
                    }
                )

            if worst_day["approval_rate"] < 0.7 and worst_day["total"] >= 5:
                recommendations.append(
                    {
                        "type": "worst_day",
                        "message": (
                            f"{worst_day['day_name']}s have a low approval rate "
                            f"({worst_day['approval_rate']:.0%}) — "
                            f"consider reducing posts on this day"
                        ),
                        "day_name": worst_day["day_name"],
                        "approval_rate": worst_day["approval_rate"],
                    }
                )

        return recommendations

    def get_approval_latency(self, telegram_chat_id: int, days: int = 30) -> dict:
        """Return approval latency statistics — time from queue to decision.

        Shows overall avg/min/max and breakdowns by hour and category.
        """
        with self.track_execution(
            "get_approval_latency",
            input_params={"telegram_chat_id": telegram_chat_id, "days": days},
        ) as run_id:
            chat_settings_id = self._resolve_chat_settings_id(telegram_chat_id)
            result = self.history_repo.get_approval_latency(
                days=days, chat_settings_id=chat_settings_id
            )
            result["days"] = days
            self.set_result_summary(
                run_id,
                {
                    "count": result["overall"]["count"],
                    "avg_minutes": result["overall"]["avg_minutes"],
                },
            )
            return result

    def get_team_performance(self, telegram_chat_id: int, days: int = 30) -> dict:
        """Return per-user approval rates and response times.

        Shows each team member's posted/skipped/rejected counts,
        approval rate, and average response latency.
        """
        with self.track_execution(
            "get_team_performance",
            input_params={"telegram_chat_id": telegram_chat_id, "days": days},
        ) as run_id:
            chat_settings_id = self._resolve_chat_settings_id(telegram_chat_id)
            users = self.history_repo.get_user_approval_stats(
                days=days, chat_settings_id=chat_settings_id
            )
            self.set_result_summary(run_id, {"user_count": len(users), "days": days})
            return {"users": users, "days": days}

    def get_pending_queue_items(self, chat_settings_id: Optional[str] = None) -> list:
        """Return pending queue items with media details.

        Used by CLI ``list-queue`` command.
        """
        rows = self.queue_repo.get_all_with_media(
            status="pending", chat_settings_id=chat_settings_id
        )

        items = []
        for item, file_name, category in rows:
            items.append(
                {
                    "scheduled_for": item.scheduled_for,
                    "file_name": file_name if file_name else "Unknown",
                    "category": (category if category else None) or "-",
                    "status": item.status,
                }
            )
        return items
