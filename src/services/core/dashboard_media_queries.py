"""Media-related dashboard queries — library, stats, categories, and content health."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.services.core.dashboard_service import DashboardService


class MediaDashboardQueries:
    """Media library stats, category breakdowns, and content health queries."""

    def __init__(self, service: DashboardService):
        self.service = service

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
        with self.service.track_execution(
            "get_media_library",
            input_params={
                "telegram_chat_id": telegram_chat_id,
                "page": page,
                "category": category,
            },
        ) as run_id:
            chat_settings_id = self.service.resolve_chat_settings_id(telegram_chat_id)

            items, total = self.service.media_repo.get_paginated(
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
                        "thumbnail_url": item.thumbnail_url,
                        "created_at": item.created_at.isoformat(),
                    }
                )

            # Only compute expensive pool health stats on page 1
            pool_health = None
            categories: list[str] = []
            if page == 1:
                posting_status_counts = self.service.media_repo.count_by_posting_status(
                    chat_settings_id=chat_settings_id
                )
                category_counts = self.service.media_repo.count_by_category(
                    chat_settings_id=chat_settings_id
                )
                eligible_count = self.service.media_repo.count_eligible(
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

            self.service.set_result_summary(
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
        chat_settings_id = self.service.resolve_chat_settings_id(telegram_chat_id)

        total_active = self.service.media_repo.count_active(
            chat_settings_id=chat_settings_id
        )
        category_counts = self.service.media_repo.count_by_category(
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

    def get_category_analytics(self, telegram_chat_id: int, days: int = 30) -> dict:
        """Return per-category performance with configured vs actual ratios.

        Enriches posting history stats with the configured category mix
        ratios, showing how actual posting patterns compare to the target.
        """
        with self.service.track_execution(
            "get_category_analytics",
            input_params={"telegram_chat_id": telegram_chat_id, "days": days},
        ) as run_id:
            chat_settings_id = self.service.resolve_chat_settings_id(telegram_chat_id)

            # Posting performance by category
            category_stats = self.service.history_repo.get_stats_by_category(
                days=days, chat_settings_id=chat_settings_id
            )

            # Configured ratios from category_post_case_mix
            configured_ratios = self.service.category_mix_repo.get_current_mix_as_dict(
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

            self.service.set_result_summary(
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
        with self.service.track_execution(
            "get_category_mix_drift",
            input_params={"telegram_chat_id": telegram_chat_id, "days": days},
        ) as run_id:
            chat_settings_id = self.service.resolve_chat_settings_id(telegram_chat_id)

            configured = self.service.category_mix_repo.get_current_mix_as_dict(
                chat_settings_id=chat_settings_id
            )
            actual_stats = self.service.history_repo.get_stats_by_category(
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
            self.service.set_result_summary(
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
        with self.service.track_execution(
            "get_dead_content_report",
            input_params={
                "telegram_chat_id": telegram_chat_id,
                "min_age_days": min_age_days,
            },
        ) as run_id:
            chat_settings_id = self.service.resolve_chat_settings_id(telegram_chat_id)

            total_active = self.service.media_repo.count_active(
                chat_settings_id=chat_settings_id
            )
            dead_by_category = self.service.media_repo.count_dead_content_by_category(
                min_age_days=min_age_days, chat_settings_id=chat_settings_id
            )
            total_dead = sum(c["dead_count"] for c in dead_by_category)
            dead_pct = round(total_dead / total_active, 2) if total_active else 0

            self.service.set_result_summary(
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

    def get_content_reuse_insights(self, telegram_chat_id: int) -> dict:
        """Classify media pool into reuse tiers.

        Uses existing count_by_posting_status() which buckets items
        into never_posted / posted_once / posted_multiple.  Includes
        per-category breakdown of never-posted items so users can
        identify which categories have the most stagnant content.
        """
        with self.service.track_execution(
            "get_content_reuse_insights",
            input_params={"telegram_chat_id": telegram_chat_id},
        ) as run_id:
            chat_settings_id = self.service.resolve_chat_settings_id(telegram_chat_id)

            posting_status = self.service.media_repo.count_by_posting_status(
                chat_settings_id=chat_settings_id
            )
            total = sum(posting_status.values())
            never_posted_by_category = (
                self.service.media_repo.count_dead_content_by_category(
                    min_age_days=0, chat_settings_id=chat_settings_id
                )
            )

            self.service.set_result_summary(run_id, {"total": total, **posting_status})
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
