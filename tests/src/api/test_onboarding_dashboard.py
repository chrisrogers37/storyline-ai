"""Tests for onboarding dashboard detail API endpoints."""

from datetime import datetime, timezone
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from tests.src.api.conftest import CHAT_ID, mock_validate, service_ctx


def _mock_settings_obj(**overrides):
    defaults = dict(
        id=uuid4(),
        posts_per_day=3,
        posting_hours_start=14,
        posting_hours_end=2,
        onboarding_completed=True,
        onboarding_step=None,
        media_source_root="folder123",
        media_source_type="google_drive",
        is_paused=False,
        dry_run_mode=True,
        enable_instagram_api=True,
        show_verbose_notifications=False,
        media_sync_enabled=True,
        active_instagram_account_id=None,
    )
    defaults.update(overrides)
    return Mock(**defaults)


# =============================================================================
# GET /api/onboarding/queue-detail
# =============================================================================


@pytest.mark.unit
class TestQueueDetail:
    """Test GET /api/onboarding/queue-detail."""

    def test_queue_detail_returns_items(self, client):
        """Queue detail returns items with media info and day summary."""
        with (
            mock_validate(),
            patch(
                "src.api.routes.onboarding.dashboard.DashboardService"
            ) as MockDashboard,
        ):
            mock_svc = service_ctx(MockDashboard)
            mock_svc.get_queue_detail.return_value = {
                "items": [
                    {
                        "scheduled_for": "2026-02-22T14:00:00",
                        "media_name": "meme_01.jpg",
                        "category": "memes",
                    },
                    {
                        "scheduled_for": "2026-02-22T18:00:00",
                        "media_name": "merch_01.jpg",
                        "category": "merch",
                    },
                    {
                        "scheduled_for": "2026-02-23T10:00:00",
                        "media_name": "meme_02.jpg",
                        "category": "memes",
                    },
                ],
                "total_pending": 3,
                "schedule_end": "2026-02-23T10:00:00",
                "days_remaining": 1,
                "day_summary": [
                    {"date": "2026-02-22", "count": 2},
                    {"date": "2026-02-23", "count": 1},
                ],
            }

            response = client.get(
                "/api/onboarding/queue-detail",
                params={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "limit": 10,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total_pending"] == 3
        assert len(data["items"]) == 3
        assert data["items"][0]["media_name"] == "meme_01.jpg"
        assert data["items"][0]["category"] == "memes"
        assert data["items"][1]["media_name"] == "merch_01.jpg"

        # Day summary
        assert len(data["day_summary"]) == 2
        assert data["day_summary"][0]["date"] == "2026-02-22"
        assert data["day_summary"][0]["count"] == 2
        assert data["day_summary"][1]["date"] == "2026-02-23"
        assert data["day_summary"][1]["count"] == 1

        assert data["schedule_end"] is not None
        assert data["days_remaining"] is not None

        mock_svc.get_queue_detail.assert_called_once_with(CHAT_ID, limit=10)

    def test_queue_detail_empty(self, client):
        """Queue detail with no pending items."""
        with (
            mock_validate(),
            patch(
                "src.api.routes.onboarding.dashboard.DashboardService"
            ) as MockDashboard,
        ):
            mock_svc = service_ctx(MockDashboard)
            mock_svc.get_queue_detail.return_value = {
                "items": [],
                "total_pending": 0,
                "schedule_end": None,
                "days_remaining": None,
                "day_summary": [],
            }

            response = client.get(
                "/api/onboarding/queue-detail",
                params={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total_pending"] == 0
        assert data["items"] == []
        assert data["day_summary"] == []
        assert data["schedule_end"] is None

    def test_queue_detail_unauthorized(self, client):
        """Queue detail rejects invalid auth."""
        with (
            patch(
                "src.api.routes.onboarding.helpers.validate_init_data",
                side_effect=ValueError("bad"),
            ),
            patch(
                "src.api.routes.onboarding.helpers.validate_url_token",
                side_effect=ValueError("bad"),
            ),
        ):
            response = client.get(
                "/api/onboarding/queue-detail",
                params={"init_data": "invalid", "chat_id": CHAT_ID},
            )

        assert response.status_code == 401


# =============================================================================
# GET /api/onboarding/history-detail
# =============================================================================


@pytest.mark.unit
class TestHistoryDetail:
    """Test GET /api/onboarding/history-detail."""

    def test_history_detail_returns_items(self, client):
        """History detail returns items with media info and status."""
        with (
            mock_validate(),
            patch(
                "src.api.routes.onboarding.dashboard.DashboardService"
            ) as MockDashboard,
        ):
            mock_svc = service_ctx(MockDashboard)
            mock_svc.get_history_detail.return_value = {
                "items": [
                    {
                        "posted_at": "2026-02-22T14:00:00",
                        "media_name": "story_01.jpg",
                        "category": "memes",
                        "status": "posted",
                        "posting_method": "instagram_api",
                    },
                    {
                        "posted_at": "2026-02-22T14:00:00",
                        "media_name": "story_02.jpg",
                        "category": "merch",
                        "status": "skipped",
                        "posting_method": "telegram_manual",
                    },
                ],
            }

            response = client.get(
                "/api/onboarding/history-detail",
                params={"init_data": "test", "chat_id": CHAT_ID, "limit": 10},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["items"][0]["media_name"] == "story_01.jpg"
        assert data["items"][0]["status"] == "posted"
        assert data["items"][0]["posting_method"] == "instagram_api"
        assert data["items"][1]["status"] == "skipped"

        mock_svc.get_history_detail.assert_called_once_with(CHAT_ID, limit=10)

    def test_history_detail_empty(self, client):
        """History detail with no posts."""
        with (
            mock_validate(),
            patch(
                "src.api.routes.onboarding.dashboard.DashboardService"
            ) as MockDashboard,
        ):
            mock_svc = service_ctx(MockDashboard)
            mock_svc.get_history_detail.return_value = {"items": []}

            response = client.get(
                "/api/onboarding/history-detail",
                params={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 200
        assert response.json()["items"] == []


# =============================================================================
# GET /api/onboarding/media-stats
# =============================================================================


@pytest.mark.unit
class TestMediaStats:
    """Test GET /api/onboarding/media-stats."""

    def test_media_stats_returns_categories(self, client):
        """Media stats returns category breakdown sorted by count."""
        with (
            mock_validate(),
            patch(
                "src.api.routes.onboarding.dashboard.DashboardService"
            ) as MockDashboard,
        ):
            mock_svc = service_ctx(MockDashboard)
            mock_svc.get_media_stats.return_value = {
                "total_active": 6,
                "categories": [
                    {"name": "memes", "count": 3},
                    {"name": "merch", "count": 2},
                    {"name": "lifestyle", "count": 1},
                ],
            }

            response = client.get(
                "/api/onboarding/media-stats",
                params={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total_active"] == 6
        assert len(data["categories"]) == 3
        # Sorted by count descending
        assert data["categories"][0]["name"] == "memes"
        assert data["categories"][0]["count"] == 3
        assert data["categories"][1]["name"] == "merch"
        assert data["categories"][1]["count"] == 2
        assert data["categories"][2]["name"] == "lifestyle"
        assert data["categories"][2]["count"] == 1

        mock_svc.get_media_stats.assert_called_once_with(CHAT_ID)

    def test_media_stats_empty(self, client):
        """Media stats with no active media."""
        with (
            mock_validate(),
            patch(
                "src.api.routes.onboarding.dashboard.DashboardService"
            ) as MockDashboard,
        ):
            mock_svc = service_ctx(MockDashboard)
            mock_svc.get_media_stats.return_value = {
                "total_active": 0,
                "categories": [],
            }

            response = client.get(
                "/api/onboarding/media-stats",
                params={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total_active"] == 0
        assert data["categories"] == []


# =============================================================================
# POST /api/onboarding/toggle-setting
# =============================================================================


@pytest.mark.unit
class TestToggleSetting:
    """Test POST /api/onboarding/toggle-setting."""

    def test_toggle_setting_paused(self, client):
        """Toggle is_paused returns new value."""
        with (
            mock_validate(),
            patch("src.api.routes.onboarding.settings.SettingsService") as MockService,
        ):
            mock_svc = service_ctx(MockService)
            mock_svc.toggle_setting.return_value = True

            response = client.post(
                "/api/onboarding/toggle-setting",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "setting_name": "is_paused",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["setting_name"] == "is_paused"
        assert data["new_value"] is True

    def test_toggle_setting_dry_run(self, client):
        """Toggle dry_run_mode returns new value."""
        with (
            mock_validate(),
            patch("src.api.routes.onboarding.settings.SettingsService") as MockService,
        ):
            mock_svc = service_ctx(MockService)
            mock_svc.toggle_setting.return_value = False

            response = client.post(
                "/api/onboarding/toggle-setting",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "setting_name": "dry_run_mode",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["setting_name"] == "dry_run_mode"
        assert data["new_value"] is False

    def test_toggle_setting_instagram_api(self, client):
        """Toggle enable_instagram_api returns new value."""
        with (
            mock_validate(),
            patch("src.api.routes.onboarding.settings.SettingsService") as MockService,
        ):
            mock_svc = service_ctx(MockService)
            mock_svc.toggle_setting.return_value = True

            response = client.post(
                "/api/onboarding/toggle-setting",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "setting_name": "enable_instagram_api",
                },
            )

        assert response.status_code == 200
        assert response.json()["new_value"] is True

    def test_toggle_setting_verbose(self, client):
        """Toggle show_verbose_notifications returns new value."""
        with (
            mock_validate(),
            patch("src.api.routes.onboarding.settings.SettingsService") as MockService,
        ):
            mock_svc = service_ctx(MockService)
            mock_svc.toggle_setting.return_value = False

            response = client.post(
                "/api/onboarding/toggle-setting",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "setting_name": "show_verbose_notifications",
                },
            )

        assert response.status_code == 200
        assert response.json()["new_value"] is False

    def test_toggle_setting_media_sync(self, client):
        """Toggle media_sync_enabled returns new value."""
        with (
            mock_validate(),
            patch("src.api.routes.onboarding.settings.SettingsService") as MockService,
        ):
            mock_svc = service_ctx(MockService)
            mock_svc.toggle_setting.return_value = True

            response = client.post(
                "/api/onboarding/toggle-setting",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "setting_name": "media_sync_enabled",
                },
            )

        assert response.status_code == 200
        assert response.json()["new_value"] is True

    def test_toggle_setting_disallowed(self, client):
        """Cannot toggle settings not in the allowed list."""
        with mock_validate():
            response = client.post(
                "/api/onboarding/toggle-setting",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "setting_name": "posts_per_day",
                },
            )

        assert response.status_code == 400
        assert "cannot be toggled" in response.json()["detail"]

    def test_toggle_setting_unauthorized(self, client):
        """Toggle rejects invalid auth."""
        with (
            patch(
                "src.api.routes.onboarding.helpers.validate_init_data",
                side_effect=ValueError("bad"),
            ),
            patch(
                "src.api.routes.onboarding.helpers.validate_url_token",
                side_effect=ValueError("bad"),
            ),
        ):
            response = client.post(
                "/api/onboarding/toggle-setting",
                json={
                    "init_data": "invalid",
                    "chat_id": CHAT_ID,
                    "setting_name": "is_paused",
                },
            )

        assert response.status_code == 401


# =============================================================================
# POST /api/onboarding/update-setting
# =============================================================================


@pytest.mark.unit
class TestUpdateSetting:
    """Test POST /api/onboarding/update-setting."""

    def test_update_posts_per_day(self, client):
        """Update posts_per_day returns new value."""
        with (
            mock_validate(),
            patch("src.api.routes.onboarding.settings.SettingsService") as MockService,
        ):
            mock_svc = service_ctx(MockService)

            response = client.post(
                "/api/onboarding/update-setting",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "setting_name": "posts_per_day",
                    "value": 10,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["setting_name"] == "posts_per_day"
        assert data["new_value"] == 10
        mock_svc.update_setting.assert_called_once_with(CHAT_ID, "posts_per_day", 10)

    def test_update_posting_hours_start(self, client):
        """Update posting_hours_start returns new value."""
        with (
            mock_validate(),
            patch("src.api.routes.onboarding.settings.SettingsService") as MockService,
        ):
            service_ctx(MockService)

            response = client.post(
                "/api/onboarding/update-setting",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "setting_name": "posting_hours_start",
                    "value": 9,
                },
            )

        assert response.status_code == 200
        assert response.json()["new_value"] == 9

    def test_update_posting_hours_end(self, client):
        """Update posting_hours_end returns new value."""
        with (
            mock_validate(),
            patch("src.api.routes.onboarding.settings.SettingsService") as MockService,
        ):
            service_ctx(MockService)

            response = client.post(
                "/api/onboarding/update-setting",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "setting_name": "posting_hours_end",
                    "value": 21,
                },
            )

        assert response.status_code == 200
        assert response.json()["new_value"] == 21

    def test_update_setting_disallowed(self, client):
        """Cannot update settings not in the allowed list."""
        with mock_validate():
            response = client.post(
                "/api/onboarding/update-setting",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "setting_name": "is_paused",
                    "value": 1,
                },
            )

        assert response.status_code == 400
        assert "cannot be updated" in response.json()["detail"]

    def test_update_setting_validation_error(self, client):
        """Update rejects invalid values via Pydantic validation."""
        with mock_validate():
            response = client.post(
                "/api/onboarding/update-setting",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "setting_name": "posts_per_day",
                    "value": -1,
                },
            )

        assert response.status_code == 422

    def test_update_setting_unauthorized(self, client):
        """Update rejects invalid auth."""
        with (
            patch(
                "src.api.routes.onboarding.helpers.validate_init_data",
                side_effect=ValueError("bad"),
            ),
            patch(
                "src.api.routes.onboarding.helpers.validate_url_token",
                side_effect=ValueError("bad"),
            ),
        ):
            response = client.post(
                "/api/onboarding/update-setting",
                json={
                    "init_data": "invalid",
                    "chat_id": CHAT_ID,
                    "setting_name": "posts_per_day",
                    "value": 5,
                },
            )

        assert response.status_code == 401


# =============================================================================
# POST /api/onboarding/extend-schedule
# =============================================================================


@pytest.mark.unit
class TestExtendSchedule:
    """Test POST /api/onboarding/extend-schedule."""

    def test_extend_schedule(self, client):
        """Extend schedule calls scheduler and returns result."""
        with (
            mock_validate(),
            patch(
                "src.api.routes.onboarding.settings.SchedulerService"
            ) as MockScheduler,
        ):
            mock_svc = service_ctx(MockScheduler)
            mock_svc.extend_schedule.return_value = {
                "scheduled": 21,
                "skipped": 0,
                "total_slots": 21,
                "extended_from": "2026-02-28T00:00:00",
            }

            response = client.post(
                "/api/onboarding/extend-schedule",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "days": 7,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["scheduled"] == 21
        assert data["total_slots"] == 21
        assert data["extended_from"] == "2026-02-28T00:00:00"

    def test_extend_schedule_default_days(self, client):
        """Extend schedule defaults to 7 days."""
        with (
            mock_validate(),
            patch(
                "src.api.routes.onboarding.settings.SchedulerService"
            ) as MockScheduler,
        ):
            mock_svc = service_ctx(MockScheduler)
            mock_svc.extend_schedule.return_value = {
                "scheduled": 21,
                "skipped": 0,
                "total_slots": 21,
            }

            response = client.post(
                "/api/onboarding/extend-schedule",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 200
        mock_svc.extend_schedule.assert_called_once_with(
            days=7, telegram_chat_id=CHAT_ID
        )


# =============================================================================
# POST /api/onboarding/regenerate-schedule
# =============================================================================


@pytest.mark.unit
class TestRegenerateSchedule:
    """Test POST /api/onboarding/regenerate-schedule."""

    def test_regenerate_schedule(self, client):
        """Regenerate clears pending items and creates new schedule."""
        with (
            mock_validate(),
            patch(
                "src.api.routes.onboarding.settings.SchedulerService"
            ) as MockScheduler,
        ):
            mock_svc = service_ctx(MockScheduler)
            mock_svc.clear_pending_queue.return_value = 42
            mock_svc.create_schedule.return_value = {
                "scheduled": 21,
                "skipped": 0,
                "total_slots": 21,
            }

            response = client.post(
                "/api/onboarding/regenerate-schedule",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "days": 7,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["scheduled"] == 21
        assert data["cleared"] == 42
        assert data["total_slots"] == 21

        # Verify queue was cleared before schedule was created
        mock_svc.clear_pending_queue.assert_called_once_with(CHAT_ID)
        mock_svc.create_schedule.assert_called_once_with(
            days=7, telegram_chat_id=CHAT_ID
        )

    def test_regenerate_schedule_unauthorized(self, client):
        """Regenerate rejects invalid auth."""
        with (
            patch(
                "src.api.routes.onboarding.helpers.validate_init_data",
                side_effect=ValueError("bad"),
            ),
            patch(
                "src.api.routes.onboarding.helpers.validate_url_token",
                side_effect=ValueError("bad"),
            ),
        ):
            response = client.post(
                "/api/onboarding/regenerate-schedule",
                json={
                    "init_data": "invalid",
                    "chat_id": CHAT_ID,
                    "days": 7,
                },
            )

        assert response.status_code == 401


# =============================================================================
# Enhanced _get_setup_state (next_post_at, schedule_end_date)
# =============================================================================


@pytest.mark.unit
class TestEnhancedSetupState:
    """Test that _get_setup_state includes schedule timing fields."""

    def test_setup_state_includes_schedule_dates(self, client):
        """Init response includes next_post_at and schedule_end_date."""
        now = datetime(2026, 2, 22, 14, 0, 0, tzinfo=timezone.utc)
        later = datetime(2026, 2, 28, 18, 0, 0, tzinfo=timezone.utc)

        setup_state = {
            "instagram_connected": False,
            "instagram_username": None,
            "gdrive_connected": False,
            "gdrive_email": None,
            "gdrive_needs_reconnect": False,
            "media_folder_configured": False,
            "media_folder_id": None,
            "media_indexed": False,
            "media_count": 0,
            "posts_per_day": 3,
            "posting_hours_start": 14,
            "posting_hours_end": 2,
            "onboarding_completed": True,
            "onboarding_step": None,
            "is_paused": False,
            "dry_run_mode": True,
            "enable_instagram_api": True,
            "show_verbose_notifications": False,
            "media_sync_enabled": True,
            "queue_count": 2,
            "last_post_at": None,
            "next_post_at": now.isoformat(),
            "schedule_end_date": later.isoformat(),
        }

        with (
            mock_validate(),
            patch(
                "src.api.routes.onboarding.helpers.SetupStateService"
            ) as MockSetupState,
        ):
            mock_svc = service_ctx(MockSetupState)
            mock_svc.get_setup_state.return_value = setup_state

            response = client.post(
                "/api/onboarding/init",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 200
        state = response.json()["setup_state"]
        assert state["next_post_at"] == now.isoformat()
        assert state["schedule_end_date"] == later.isoformat()
        assert state["queue_count"] == 2

    def test_setup_state_includes_all_settings(self, client):
        """Init response includes all boolean settings for Quick Controls."""
        setup_state = {
            "instagram_connected": False,
            "instagram_username": None,
            "gdrive_connected": False,
            "gdrive_email": None,
            "gdrive_needs_reconnect": False,
            "media_folder_configured": False,
            "media_folder_id": None,
            "media_indexed": False,
            "media_count": 0,
            "posts_per_day": 3,
            "posting_hours_start": 14,
            "posting_hours_end": 2,
            "onboarding_completed": True,
            "onboarding_step": None,
            "is_paused": False,
            "dry_run_mode": True,
            "enable_instagram_api": True,
            "show_verbose_notifications": False,
            "media_sync_enabled": True,
            "queue_count": 0,
            "last_post_at": None,
            "next_post_at": None,
            "schedule_end_date": None,
        }

        with (
            mock_validate(),
            patch(
                "src.api.routes.onboarding.helpers.SetupStateService"
            ) as MockSetupState,
        ):
            mock_svc = service_ctx(MockSetupState)
            mock_svc.get_setup_state.return_value = setup_state

            response = client.post(
                "/api/onboarding/init",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 200
        state = response.json()["setup_state"]
        assert state["enable_instagram_api"] is True
        assert state["show_verbose_notifications"] is False
        assert state["media_sync_enabled"] is True
        assert state["is_paused"] is False
        assert state["dry_run_mode"] is True

    def test_setup_state_empty_queue_no_dates(self, client):
        """Init response with empty queue has null schedule dates."""
        setup_state = {
            "instagram_connected": False,
            "instagram_username": None,
            "gdrive_connected": False,
            "gdrive_email": None,
            "gdrive_needs_reconnect": False,
            "media_folder_configured": False,
            "media_folder_id": None,
            "media_indexed": False,
            "media_count": 0,
            "posts_per_day": 3,
            "posting_hours_start": 14,
            "posting_hours_end": 2,
            "onboarding_completed": True,
            "onboarding_step": None,
            "is_paused": False,
            "dry_run_mode": True,
            "enable_instagram_api": True,
            "show_verbose_notifications": False,
            "media_sync_enabled": True,
            "queue_count": 0,
            "last_post_at": None,
            "next_post_at": None,
            "schedule_end_date": None,
        }

        with (
            mock_validate(),
            patch(
                "src.api.routes.onboarding.helpers.SetupStateService"
            ) as MockSetupState,
        ):
            mock_svc = service_ctx(MockSetupState)
            mock_svc.get_setup_state.return_value = setup_state

            response = client.post(
                "/api/onboarding/init",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 200
        state = response.json()["setup_state"]
        assert state["next_post_at"] is None
        assert state["schedule_end_date"] is None
        assert state["queue_count"] == 0


# =============================================================================
# GET /api/onboarding/system-status
# =============================================================================


def _mock_health_checks(overrides=None):
    """Build a mock HealthCheckService.check_all() result."""
    checks = {
        "database": {"healthy": True, "message": "Database connection OK"},
        "telegram": {"healthy": True, "message": "Telegram configuration OK"},
        "instagram_api": {
            "healthy": True,
            "message": "OK (23/25 posts remaining)",
            "enabled": True,
            "rate_limit_remaining": 23,
        },
        "queue": {
            "healthy": True,
            "message": "Queue healthy (12 pending)",
            "pending_count": 12,
        },
        "recent_posts": {
            "healthy": True,
            "message": "5/5 successful in last 48h",
            "recent_count": 5,
            "successful_count": 5,
        },
        "media_sync": {
            "healthy": True,
            "message": "OK (source: google_drive)",
            "enabled": True,
            "source_type": "google_drive",
        },
    }
    if overrides:
        checks.update(overrides)
    return {
        "status": "healthy"
        if all(c["healthy"] for c in checks.values())
        else "unhealthy",
        "checks": checks,
        "timestamp": "2026-02-22T14:00:00",
    }


@pytest.mark.unit
class TestSystemStatus:
    """Test GET /api/onboarding/system-status."""

    def test_system_status_healthy(self, client):
        """System status returns health checks when all healthy."""
        with (
            mock_validate(),
            patch(
                "src.api.routes.onboarding.dashboard.HealthCheckService"
            ) as MockHealthService,
        ):
            mock_svc = service_ctx(MockHealthService)
            mock_svc.check_all.return_value = _mock_health_checks()

            response = client.get(
                "/api/onboarding/system-status",
                params={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["checks"]["database"]["healthy"] is True
        assert data["checks"]["queue"]["pending_count"] == 12
        assert data["checks"]["instagram_api"]["rate_limit_remaining"] == 23

    def test_system_status_unhealthy(self, client):
        """System status returns unhealthy when checks fail."""
        health_data = _mock_health_checks(
            overrides={
                "database": {"healthy": False, "message": "Connection refused"},
            }
        )

        with (
            mock_validate(),
            patch(
                "src.api.routes.onboarding.dashboard.HealthCheckService"
            ) as MockHealthService,
        ):
            mock_svc = service_ctx(MockHealthService)
            mock_svc.check_all.return_value = health_data

            response = client.get(
                "/api/onboarding/system-status",
                params={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["checks"]["database"]["healthy"] is False
        assert "Connection refused" in data["checks"]["database"]["message"]

    def test_system_status_unauthorized(self, client):
        """System status rejects invalid auth."""
        with (
            patch(
                "src.api.routes.onboarding.helpers.validate_init_data",
                side_effect=ValueError("bad"),
            ),
            patch(
                "src.api.routes.onboarding.helpers.validate_url_token",
                side_effect=ValueError("bad"),
            ),
        ):
            response = client.get(
                "/api/onboarding/system-status",
                params={"init_data": "invalid", "chat_id": CHAT_ID},
            )

        assert response.status_code == 401


# =============================================================================
# POST /api/onboarding/sync-media
# =============================================================================


@pytest.mark.unit
class TestSyncMedia:
    """Test POST /api/onboarding/sync-media."""

    def test_sync_media_success(self, client):
        """Sync media calls service and returns result counts."""
        mock_result = Mock()
        mock_result.new = 5
        mock_result.updated = 2
        mock_result.deactivated = 1
        mock_result.unchanged = 100
        mock_result.errors = 0
        mock_result.total_processed = 108

        with (
            mock_validate(),
            patch(
                "src.api.routes.onboarding.settings.SettingsService"
            ) as MockSettingsService,
            patch(
                "src.api.routes.onboarding.settings.MediaSyncService"
            ) as MockSyncService,
        ):
            mock_settings_svc = service_ctx(MockSettingsService)
            mock_settings_svc.get_media_source_config.return_value = (
                "google_drive",
                "folder123",
            )
            mock_sync_svc = service_ctx(MockSyncService)
            mock_sync_svc.sync.return_value = mock_result

            response = client.post(
                "/api/onboarding/sync-media",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["new"] == 5
        assert data["updated"] == 2
        assert data["deactivated"] == 1
        assert data["unchanged"] == 100
        assert data["errors"] == 0
        assert data["total_processed"] == 108
        mock_sync_svc.sync.assert_called_once_with(
            source_type="google_drive",
            source_root="folder123",
            triggered_by="dashboard",
            telegram_chat_id=CHAT_ID,
        )

    def test_sync_media_no_folder_configured(self, client):
        """Sync media returns 400 when no media folder is configured."""
        with (
            mock_validate(),
            patch(
                "src.api.routes.onboarding.settings.SettingsService"
            ) as MockSettingsService,
        ):
            mock_settings_svc = service_ctx(MockSettingsService)
            mock_settings_svc.get_media_source_config.return_value = (None, None)

            response = client.post(
                "/api/onboarding/sync-media",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 400
        assert "No media folder" in response.json()["detail"]

    def test_sync_media_service_error(self, client):
        """Sync media returns 500 when sync service fails."""
        with (
            mock_validate(),
            patch(
                "src.api.routes.onboarding.settings.SettingsService"
            ) as MockSettingsService,
            patch(
                "src.api.routes.onboarding.settings.MediaSyncService"
            ) as MockSyncService,
        ):
            mock_settings_svc = service_ctx(MockSettingsService)
            mock_settings_svc.get_media_source_config.return_value = (
                "google_drive",
                "folder123",
            )
            mock_sync_svc = service_ctx(MockSyncService)
            mock_sync_svc.sync.side_effect = RuntimeError("Drive error")

            response = client.post(
                "/api/onboarding/sync-media",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 500
        assert "sync failed" in response.json()["detail"].lower()

    def test_sync_media_unauthorized(self, client):
        """Sync media rejects invalid auth."""
        with (
            patch(
                "src.api.routes.onboarding.helpers.validate_init_data",
                side_effect=ValueError("bad"),
            ),
            patch(
                "src.api.routes.onboarding.helpers.validate_url_token",
                side_effect=ValueError("bad"),
            ),
        ):
            response = client.post(
                "/api/onboarding/sync-media",
                json={"init_data": "invalid", "chat_id": CHAT_ID},
            )

        assert response.status_code == 401


# =============================================================================
# GET /api/onboarding/accounts
# =============================================================================


def _mock_account(
    display_name="Thursday Lines", username="thursday.lines", acct_id=None
):
    acct = Mock()
    acct.id = acct_id or uuid4()
    acct.display_name = display_name
    acct.instagram_username = username
    acct.is_active = True
    return acct


@pytest.mark.unit
class TestAccounts:
    """Test GET /api/onboarding/accounts."""

    def test_accounts_returns_list(self, client):
        """Accounts endpoint returns all active accounts with active marker."""
        acct_1 = _mock_account("Thursday Lines", "thursday.lines")
        acct_2 = _mock_account("Side Project", "sideproject")
        mock_settings = _mock_settings_obj(
            active_instagram_account_id=acct_1.id,
        )

        with (
            mock_validate(),
            patch(
                "src.api.routes.onboarding.dashboard.InstagramAccountService"
            ) as MockIGService,
            patch(
                "src.api.routes.onboarding.dashboard.SettingsService"
            ) as MockSettingsService,
        ):
            mock_ig_svc = service_ctx(MockIGService)
            mock_ig_svc.list_accounts.return_value = [acct_1, acct_2]
            mock_settings_svc = service_ctx(MockSettingsService)
            mock_settings_svc.get_settings.return_value = mock_settings

            response = client.get(
                "/api/onboarding/accounts",
                params={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["accounts"]) == 2
        assert data["accounts"][0]["display_name"] == "Thursday Lines"
        assert data["accounts"][0]["is_active"] is True
        assert data["accounts"][1]["display_name"] == "Side Project"
        assert data["accounts"][1]["is_active"] is False
        assert data["active_account_id"] == str(acct_1.id)

    def test_accounts_empty(self, client):
        """Accounts endpoint returns empty list when no accounts."""
        mock_settings = _mock_settings_obj(active_instagram_account_id=None)

        with (
            mock_validate(),
            patch(
                "src.api.routes.onboarding.dashboard.InstagramAccountService"
            ) as MockIGService,
            patch(
                "src.api.routes.onboarding.dashboard.SettingsService"
            ) as MockSettingsService,
        ):
            mock_ig_svc = service_ctx(MockIGService)
            mock_ig_svc.list_accounts.return_value = []
            mock_settings_svc = service_ctx(MockSettingsService)
            mock_settings_svc.get_settings.return_value = mock_settings

            response = client.get(
                "/api/onboarding/accounts",
                params={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["accounts"] == []
        assert data["active_account_id"] is None

    def test_accounts_unauthorized(self, client):
        """Accounts rejects invalid auth."""
        with (
            patch(
                "src.api.routes.onboarding.helpers.validate_init_data",
                side_effect=ValueError("bad"),
            ),
            patch(
                "src.api.routes.onboarding.helpers.validate_url_token",
                side_effect=ValueError("bad"),
            ),
        ):
            response = client.get(
                "/api/onboarding/accounts",
                params={"init_data": "invalid", "chat_id": CHAT_ID},
            )

        assert response.status_code == 401


# =============================================================================
# POST /api/onboarding/switch-account
# =============================================================================


@pytest.mark.unit
class TestSwitchAccount:
    """Test POST /api/onboarding/switch-account."""

    def test_switch_account_success(self, client):
        """Switch account returns new active account info."""
        acct = _mock_account("Side Project", "sideproject")

        with (
            mock_validate(),
            patch(
                "src.api.routes.onboarding.settings.InstagramAccountService"
            ) as MockIGService,
        ):
            mock_svc = service_ctx(MockIGService)
            mock_svc.switch_account.return_value = acct

            response = client.post(
                "/api/onboarding/switch-account",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "account_id": str(acct.id),
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "Side Project"
        assert data["instagram_username"] == "sideproject"
        mock_svc.switch_account.assert_called_once_with(
            telegram_chat_id=CHAT_ID,
            account_id=str(acct.id),
        )

    def test_switch_account_not_found(self, client):
        """Switch account returns 400 for unknown account."""
        with (
            mock_validate(),
            patch(
                "src.api.routes.onboarding.settings.InstagramAccountService"
            ) as MockIGService,
        ):
            mock_svc = service_ctx(MockIGService)
            mock_svc.switch_account.side_effect = ValueError("Account not found")

            response = client.post(
                "/api/onboarding/switch-account",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "account_id": "nonexistent",
                },
            )

        assert response.status_code == 400
        assert "not found" in response.json()["detail"]

    def test_switch_account_unauthorized(self, client):
        """Switch account rejects invalid auth."""
        with (
            patch(
                "src.api.routes.onboarding.helpers.validate_init_data",
                side_effect=ValueError("bad"),
            ),
            patch(
                "src.api.routes.onboarding.helpers.validate_url_token",
                side_effect=ValueError("bad"),
            ),
        ):
            response = client.post(
                "/api/onboarding/switch-account",
                json={
                    "init_data": "invalid",
                    "chat_id": CHAT_ID,
                    "account_id": str(uuid4()),
                },
            )

        assert response.status_code == 401


# =============================================================================
# POST /api/onboarding/remove-account
# =============================================================================


@pytest.mark.unit
class TestRemoveAccount:
    """Test POST /api/onboarding/remove-account."""

    def test_remove_account_success(self, client):
        """Remove account deactivates and returns confirmation."""
        acct = _mock_account("Old Account", "oldaccount")

        with (
            mock_validate(),
            patch(
                "src.api.routes.onboarding.settings.InstagramAccountService"
            ) as MockIGService,
        ):
            mock_svc = service_ctx(MockIGService)
            mock_svc.deactivate_account.return_value = acct

            response = client.post(
                "/api/onboarding/remove-account",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "account_id": str(acct.id),
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "Old Account"
        assert data["removed"] is True
        mock_svc.deactivate_account.assert_called_once_with(
            account_id=str(acct.id),
        )

    def test_remove_account_not_found(self, client):
        """Remove account returns 400 for unknown account."""
        with (
            mock_validate(),
            patch(
                "src.api.routes.onboarding.settings.InstagramAccountService"
            ) as MockIGService,
        ):
            mock_svc = service_ctx(MockIGService)
            mock_svc.deactivate_account.side_effect = ValueError("Account not found")

            response = client.post(
                "/api/onboarding/remove-account",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "account_id": "nonexistent",
                },
            )

        assert response.status_code == 400
        assert "not found" in response.json()["detail"]

    def test_remove_account_unauthorized(self, client):
        """Remove account rejects invalid auth."""
        with (
            patch(
                "src.api.routes.onboarding.helpers.validate_init_data",
                side_effect=ValueError("bad"),
            ),
            patch(
                "src.api.routes.onboarding.helpers.validate_url_token",
                side_effect=ValueError("bad"),
            ),
        ):
            response = client.post(
                "/api/onboarding/remove-account",
                json={
                    "init_data": "invalid",
                    "chat_id": CHAT_ID,
                    "account_id": str(uuid4()),
                },
            )

        assert response.status_code == 401
