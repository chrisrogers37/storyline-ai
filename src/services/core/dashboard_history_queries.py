"""History-related dashboard queries — posting analytics, scheduling, team performance."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.services.core.dashboard_service import DashboardService


class HistoryDashboardQueries:
    """Posting history analytics, schedule recommendations, and team performance."""

    MIN_RECOMMENDATION_DATA_POINTS = 10

    def __init__(self, service: DashboardService):
        self.service = service

    def get_history_detail(self, telegram_chat_id: int, limit: int = 10) -> dict:
        """Return recent posting history with media info."""
        chat_settings_id = self.service.resolve_chat_settings_id(telegram_chat_id)

        history_rows = self.service.history_repo.get_all_with_media(
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

    def get_analytics(self, telegram_chat_id: int, days: int = 30) -> dict:
        """Return aggregated posting analytics for the dashboard.

        Combines status breakdown, method breakdown, daily counts,
        hourly distribution, and category performance into a single
        response.
        """
        with self.service.track_execution(
            "get_analytics",
            input_params={"telegram_chat_id": telegram_chat_id, "days": days},
        ) as run_id:
            chat_settings_id = self.service.resolve_chat_settings_id(telegram_chat_id)

            status_counts = self.service.history_repo.get_stats_by_status(
                days=days, chat_settings_id=chat_settings_id
            )
            method_counts = self.service.history_repo.get_stats_by_method(
                days=days, chat_settings_id=chat_settings_id
            )
            daily_counts = self.service.history_repo.get_daily_counts(
                days=days, chat_settings_id=chat_settings_id
            )
            hourly_dist = self.service.history_repo.get_hourly_distribution(
                days=days, chat_settings_id=chat_settings_id
            )
            category_stats = self.service.history_repo.get_stats_by_category(
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

            self.service.set_result_summary(
                run_id, {"total_posts": total, "days": days}
            )
            return result

    def get_schedule_recommendations(
        self, telegram_chat_id: int, days: int = 90
    ) -> dict:
        """Analyze posting history to recommend optimal posting times.

        Returns hourly approval rates, day-of-week patterns, and
        human-readable recommendations based on when posts are most
        frequently approved vs skipped/rejected.
        """
        with self.service.track_execution(
            "get_schedule_recommendations",
            input_params={"telegram_chat_id": telegram_chat_id, "days": days},
        ) as run_id:
            chat_settings_id = self.service.resolve_chat_settings_id(telegram_chat_id)

            hourly = self.service.history_repo.get_hourly_approval_rates(
                days=days, chat_settings_id=chat_settings_id
            )
            dow = self.service.history_repo.get_dow_approval_rates(
                days=days, chat_settings_id=chat_settings_id
            )

            total_data_points = sum(h.get("total", 0) for h in hourly)

            if total_data_points < self.MIN_RECOMMENDATION_DATA_POINTS:
                self.service.set_result_summary(
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

            self.service.set_result_summary(
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
        from datetime import datetime, timedelta, timezone

        with self.service.track_execution(
            "get_schedule_preview",
            input_params={"telegram_chat_id": telegram_chat_id, "slots": slots},
        ) as run_id:
            chat_settings = self.service.settings_service.get_settings(telegram_chat_id)

            if chat_settings.is_paused:
                self.service.set_result_summary(run_id, {"status": "paused"})
                return {"status": "paused", "slots": []}

            ppd = chat_settings.posts_per_day
            start_h = chat_settings.posting_hours_start
            end_h = chat_settings.posting_hours_end
            window_hours = (
                (24 - start_h + end_h) if end_h < start_h else (end_h - start_h)
            )
            interval_seconds = (window_hours * 3600) / ppd if ppd else 3600

            now = datetime.now(timezone.utc)
            last = chat_settings.last_post_sent_at
            if last and last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            next_time = last + timedelta(seconds=interval_seconds) if last else now

            configured = self.service.category_mix_repo.get_current_mix_as_dict(
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

            self.service.set_result_summary(
                run_id, {"slots": len(result_slots), "status": "ok"}
            )
            return {
                "status": "ok",
                "slots": result_slots,
                "interval_minutes": round(interval_seconds / 60, 1),
                "posts_per_day": ppd,
                "timezone": "UTC",
            }

    def get_approval_latency(self, telegram_chat_id: int, days: int = 30) -> dict:
        """Return approval latency statistics — time from queue to decision.

        Shows overall avg/min/max and breakdowns by hour and category.
        """
        with self.service.track_execution(
            "get_approval_latency",
            input_params={"telegram_chat_id": telegram_chat_id, "days": days},
        ) as run_id:
            chat_settings_id = self.service.resolve_chat_settings_id(telegram_chat_id)
            result = self.service.history_repo.get_approval_latency(
                days=days, chat_settings_id=chat_settings_id
            )
            result["days"] = days
            self.service.set_result_summary(
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
        with self.service.track_execution(
            "get_team_performance",
            input_params={"telegram_chat_id": telegram_chat_id, "days": days},
        ) as run_id:
            chat_settings_id = self.service.resolve_chat_settings_id(telegram_chat_id)
            users = self.service.history_repo.get_user_approval_stats(
                days=days, chat_settings_id=chat_settings_id
            )
            self.service.set_result_summary(
                run_id, {"user_count": len(users), "days": days}
            )
            return {"users": users, "days": days}
