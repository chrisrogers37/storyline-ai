"""Dashboard service - read-only aggregation queries for the Mini App."""

from typing import Optional

from src.services.base_service import BaseService
from src.services.core.settings_service import SettingsService
from src.repositories.history_repository import HistoryRepository
from src.repositories.media_repository import MediaRepository
from src.repositories.queue_repository import QueueRepository
from src.repositories.category_mix_repository import CategoryMixRepository
from src.repositories.membership_repository import MembershipRepository
from src.repositories.user_repository import UserRepository


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
        self.membership_repo = MembershipRepository()
        self.user_repo = UserRepository()

    def _resolve_chat_settings_id(self, telegram_chat_id: int) -> str:
        chat_settings = self.settings_service.get_settings(telegram_chat_id)
        return str(chat_settings.id)

    def get_user_instances(self, telegram_user_id: int) -> dict:
        """Return all instances a user belongs to, with stats per instance.

        Used by the instance picker (web dashboard and DM Mini App).
        """
        user = self.user_repo.get_by_telegram_id(telegram_user_id)
        if not user:
            return {"instances": []}

        memberships = self.membership_repo.get_for_user(str(user.id))
        instances = []
        for membership in memberships:
            cs = membership.chat_settings
            cs_id = str(cs.id)

            media_count = self.media_repo.count_active(chat_settings_id=cs_id)

            last_post_at = None
            recent = self.history_repo.get_recent_posts(
                hours=720, chat_settings_id=cs_id, limit=1
            )
            if recent:
                last_post_at = recent[0].posted_at.isoformat()

            instances.append(
                {
                    "chat_settings_id": cs_id,
                    "telegram_chat_id": cs.telegram_chat_id,
                    "display_name": cs.display_name,
                    "media_count": media_count,
                    "posts_per_day": cs.posts_per_day,
                    "is_paused": cs.is_paused,
                    "last_post_at": last_post_at,
                    "instance_role": membership.instance_role,
                }
            )

        return {"instances": instances}

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

    def get_media_library(
        self,
        telegram_chat_id: int,
        page: int = 1,
        page_size: int = 20,
        category: Optional[str] = None,
        posting_status: Optional[str] = None,
    ) -> dict:
        """Return paginated media items with pool health stats.

        Combines item listing with aggregate stats for the media library view.
        """
        with self.track_execution(
            "get_media_library",
            input_params={
                "telegram_chat_id": telegram_chat_id,
                "page": page,
                "category": category,
            },
        ) as run_id:
            chat_settings_id = self._resolve_chat_settings_id(telegram_chat_id)

            items, total = self.media_repo.get_paginated(
                page=page,
                page_size=page_size,
                category=category,
                posting_status=posting_status,
                chat_settings_id=chat_settings_id,
            )

            serialized = []
            for item in items:
                serialized.append(
                    {
                        "id": str(item.id),
                        "file_name": item.file_name,
                        "category": item.category or "uncategorized",
                        "mime_type": item.mime_type,
                        "file_size": item.file_size,
                        "times_posted": item.times_posted,
                        "last_posted_at": (
                            item.last_posted_at.isoformat()
                            if item.last_posted_at
                            else None
                        ),
                        "source_type": item.source_type,
                        "created_at": item.created_at.isoformat(),
                    }
                )

            # Only compute expensive pool health stats on page 1
            pool_health = None
            categories: list[str] = []
            if page == 1:
                posting_status_counts = self.media_repo.count_by_posting_status(
                    chat_settings_id=chat_settings_id
                )
                category_counts = self.media_repo.count_by_category(
                    chat_settings_id=chat_settings_id
                )
                eligible_count = self.media_repo.count_eligible(
                    chat_settings_id=chat_settings_id
                )
                categories = sorted(category_counts.keys())
                pool_health = {
                    "total_active": sum(posting_status_counts.values()),
                    "never_posted": posting_status_counts.get("never_posted", 0),
                    "posted_once": posting_status_counts.get("posted_once", 0),
                    "posted_multiple": posting_status_counts.get("posted_multiple", 0),
                    "eligible_for_posting": eligible_count,
                    "by_category": [
                        {"name": name, "count": count}
                        for name, count in sorted(
                            category_counts.items(),
                            key=lambda x: x[1],
                            reverse=True,
                        )
                    ],
                }

            self.set_result_summary(
                run_id, {"total": total, "page": page, "returned": len(serialized)}
            )

            return {
                "items": serialized,
                "total": total,
                "page": page,
                "page_size": page_size,
                "categories": categories,
                "pool_health": pool_health,
            }

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

    def get_schedule_preview(self, telegram_chat_id: int, slots: int = 10) -> dict:
        """Show upcoming scheduled slots with predicted categories.

        Computes future slot times from the posting interval and
        assigns categories using weighted random (same logic as the
        scheduler).  Does NOT select specific media items.  Slot times
        are clamped to the configured posting window — if a computed
        slot falls outside the window, it advances to the next open.
        """
        import random
        from datetime import datetime, timedelta

        with self.track_execution(
            "get_schedule_preview",
            input_params={"telegram_chat_id": telegram_chat_id, "slots": slots},
        ) as run_id:
            chat_settings = self.settings_service.get_settings(telegram_chat_id)

            if chat_settings.is_paused:
                self.set_result_summary(run_id, {"status": "paused"})
                return {"status": "paused", "slots": []}

            ppd = chat_settings.posts_per_day
            start_h = chat_settings.posting_hours_start
            end_h = chat_settings.posting_hours_end
            window_hours = (
                (24 - start_h + end_h) if end_h < start_h else (end_h - start_h)
            )
            interval_seconds = (window_hours * 3600) / ppd if ppd else 3600

            now = datetime.utcnow()
            last = chat_settings.last_post_sent_at
            if last and last.tzinfo:
                last = last.replace(tzinfo=None)
            next_time = last + timedelta(seconds=interval_seconds) if last else now

            configured = self.category_mix_repo.get_current_mix_as_dict(
                chat_settings_id=str(chat_settings.id)
            )
            categories = list(configured.keys()) if configured else []
            weights = [float(r) for r in configured.values()] if configured else []

            def _clamp_to_window(dt: datetime) -> datetime:
                """Advance dt to the next posting window open if outside."""
                hour = dt.hour + dt.minute / 60.0
                if end_h < start_h:
                    in_window = hour >= start_h or hour < end_h
                else:
                    in_window = start_h <= hour < end_h
                if in_window:
                    return dt
                # Advance to start_h today or tomorrow
                candidate = dt.replace(hour=start_h, minute=0, second=0, microsecond=0)
                if candidate <= dt:
                    candidate += timedelta(days=1)
                return candidate

            result_slots = []
            for _ in range(slots):
                if next_time < now:
                    next_time = now
                next_time = _clamp_to_window(next_time)

                predicted_cat = (
                    random.choices(categories, weights=weights, k=1)[0]
                    if categories
                    else None
                )
                result_slots.append(
                    {
                        "slot_time": next_time.isoformat() + "Z",
                        "predicted_category": predicted_cat,
                    }
                )
                next_time += timedelta(seconds=interval_seconds)

            self.set_result_summary(
                run_id, {"slots": len(result_slots), "status": "ok"}
            )
            return {
                "status": "ok",
                "slots": result_slots,
                "interval_minutes": round(interval_seconds / 60, 1),
                "posts_per_day": ppd,
                "timezone": "UTC",
            }

    def get_content_reuse_insights(self, telegram_chat_id: int) -> dict:
        """Classify media pool into reuse tiers.

        Uses existing count_by_posting_status() which buckets items
        into never_posted / posted_once / posted_multiple.  Includes
        per-category breakdown of never-posted items so users can
        identify which categories have the most stagnant content.
        """
        with self.track_execution(
            "get_content_reuse_insights",
            input_params={"telegram_chat_id": telegram_chat_id},
        ) as run_id:
            chat_settings_id = self._resolve_chat_settings_id(telegram_chat_id)

            posting_status = self.media_repo.count_by_posting_status(
                chat_settings_id=chat_settings_id
            )
            total = sum(posting_status.values())
            never_posted_by_category = self.media_repo.count_dead_content_by_category(
                min_age_days=0, chat_settings_id=chat_settings_id
            )

            self.set_result_summary(run_id, {"total": total, **posting_status})
            return {
                "total_active": total,
                "never_posted": posting_status["never_posted"],
                "posted_once": posting_status["posted_once"],
                "posted_multiple": posting_status["posted_multiple"],
                "reuse_rate": round(posting_status["posted_multiple"] / total, 2)
                if total
                else 0,
                "never_posted_by_category": never_posted_by_category,
            }

    def get_service_health_stats(self, hours: int = 24) -> dict:
        """Aggregate service_runs telemetry for an ops dashboard.

        Returns per-service call counts, error rates, and avg duration.

        NOTE: This is intentionally a global (system-level) view.
        service_runs are not tenant-scoped — they track internal service
        executions that span tenants. The API endpoint requires valid
        auth but does not filter by chat_id.
        """
        stats = self.service_run_repo.get_health_stats(hours=hours)
        total_calls = sum(s["call_count"] for s in stats)
        total_failures = sum(s["failure_count"] for s in stats)

        return {
            "services": stats,
            "total_calls": total_calls,
            "total_failures": total_failures,
            "overall_error_rate": round(total_failures / total_calls, 2)
            if total_calls
            else 0,
            "hours": hours,
        }

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
