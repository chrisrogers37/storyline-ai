"""Tests for onboarding dashboard detail API endpoints."""

from datetime import datetime, timezone
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.api.app import app


@pytest.fixture
def client():
    return TestClient(app)


VALID_USER = {"user_id": 12345, "first_name": "Chris"}
CHAT_ID = -1001234567890


def _mock_validate(return_value=None):
    return patch(
        "src.api.routes.onboarding.validate_init_data",
        return_value=return_value or VALID_USER,
    )


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
    )
    defaults.update(overrides)
    return Mock(**defaults)


def _mock_queue_item(scheduled_for, media_item_id=None):
    return Mock(
        id=uuid4(),
        media_item_id=media_item_id or uuid4(),
        scheduled_for=scheduled_for,
        status="pending",
    )


def _mock_history_item(posted_at, status="posted", posting_method="telegram_manual"):
    return Mock(
        id=uuid4(),
        media_item_id=uuid4(),
        posted_at=posted_at,
        status=status,
        posting_method=posting_method,
    )


def _mock_media_item(file_name="story_001.jpg", category="memes"):
    return Mock(
        id=uuid4(),
        file_name=file_name,
        category=category,
        is_active=True,
    )


# =============================================================================
# GET /api/onboarding/queue-detail
# =============================================================================


@pytest.mark.unit
class TestQueueDetail:
    """Test GET /api/onboarding/queue-detail."""

    def test_queue_detail_returns_items(self, client):
        """Queue detail returns items with media info and day summary."""
        mock_settings = _mock_settings_obj()
        now = datetime(2026, 2, 22, 14, 0, 0, tzinfo=timezone.utc)
        later = datetime(2026, 2, 22, 18, 0, 0, tzinfo=timezone.utc)
        tomorrow = datetime(2026, 2, 23, 10, 0, 0, tzinfo=timezone.utc)

        media_id_1 = uuid4()
        media_id_2 = uuid4()
        media_id_3 = uuid4()

        queue_items = [
            _mock_queue_item(now, media_id_1),
            _mock_queue_item(later, media_id_2),
            _mock_queue_item(tomorrow, media_id_3),
        ]

        media_map = {
            str(media_id_1): _mock_media_item("meme_01.jpg", "memes"),
            str(media_id_2): _mock_media_item("merch_01.jpg", "merch"),
            str(media_id_3): _mock_media_item("meme_02.jpg", "memes"),
        }

        with (
            _mock_validate(),
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch("src.api.routes.onboarding.QueueRepository") as MockQueueRepo,
            patch("src.api.routes.onboarding.MediaRepository") as MockMediaRepo,
        ):
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.close = Mock()
            MockQueueRepo.return_value.get_all.return_value = queue_items
            MockQueueRepo.return_value.close = Mock()
            MockMediaRepo.return_value.get_by_id.side_effect = (
                lambda mid: media_map.get(mid)
            )
            MockMediaRepo.return_value.close = Mock()

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

    def test_queue_detail_empty(self, client):
        """Queue detail with no pending items."""
        mock_settings = _mock_settings_obj()

        with (
            _mock_validate(),
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch("src.api.routes.onboarding.QueueRepository") as MockQueueRepo,
            patch("src.api.routes.onboarding.MediaRepository") as MockMediaRepo,
        ):
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.close = Mock()
            MockQueueRepo.return_value.get_all.return_value = []
            MockQueueRepo.return_value.close = Mock()
            MockMediaRepo.return_value.close = Mock()

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
                "src.api.routes.onboarding.validate_init_data",
                side_effect=ValueError("bad"),
            ),
            patch(
                "src.api.routes.onboarding.validate_url_token",
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
        mock_settings = _mock_settings_obj()
        now = datetime(2026, 2, 22, 14, 0, 0, tzinfo=timezone.utc)

        media_id_1 = uuid4()
        media_id_2 = uuid4()

        history_items = [
            _mock_history_item(now, "posted", "instagram_api"),
            _mock_history_item(now, "skipped", "telegram_manual"),
        ]
        history_items[0].media_item_id = media_id_1
        history_items[1].media_item_id = media_id_2

        media_map = {
            str(media_id_1): _mock_media_item("story_01.jpg", "memes"),
            str(media_id_2): _mock_media_item("story_02.jpg", "merch"),
        }

        with (
            _mock_validate(),
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch("src.api.routes.onboarding.HistoryRepository") as MockHistoryRepo,
            patch("src.api.routes.onboarding.MediaRepository") as MockMediaRepo,
        ):
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.close = Mock()
            MockHistoryRepo.return_value.get_all.return_value = history_items
            MockHistoryRepo.return_value.close = Mock()
            MockMediaRepo.return_value.get_by_id.side_effect = (
                lambda mid: media_map.get(mid)
            )
            MockMediaRepo.return_value.close = Mock()

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

    def test_history_detail_empty(self, client):
        """History detail with no posts."""
        mock_settings = _mock_settings_obj()

        with (
            _mock_validate(),
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch("src.api.routes.onboarding.HistoryRepository") as MockHistoryRepo,
            patch("src.api.routes.onboarding.MediaRepository") as MockMediaRepo,
        ):
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.close = Mock()
            MockHistoryRepo.return_value.get_all.return_value = []
            MockHistoryRepo.return_value.close = Mock()
            MockMediaRepo.return_value.close = Mock()

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
        mock_settings = _mock_settings_obj()

        media_items = [
            _mock_media_item("m1.jpg", "memes"),
            _mock_media_item("m2.jpg", "memes"),
            _mock_media_item("m3.jpg", "memes"),
            _mock_media_item("m4.jpg", "merch"),
            _mock_media_item("m5.jpg", "merch"),
            _mock_media_item("m6.jpg", "lifestyle"),
        ]

        with (
            _mock_validate(),
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch("src.api.routes.onboarding.MediaRepository") as MockMediaRepo,
        ):
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.close = Mock()
            MockMediaRepo.return_value.get_all.return_value = media_items
            MockMediaRepo.return_value.close = Mock()

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

    def test_media_stats_empty(self, client):
        """Media stats with no active media."""
        mock_settings = _mock_settings_obj()

        with (
            _mock_validate(),
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch("src.api.routes.onboarding.MediaRepository") as MockMediaRepo,
        ):
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.close = Mock()
            MockMediaRepo.return_value.get_all.return_value = []
            MockMediaRepo.return_value.close = Mock()

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
            _mock_validate(),
            patch("src.api.routes.onboarding.SettingsService") as MockService,
        ):
            MockService.return_value.toggle_setting.return_value = True
            MockService.return_value.close = Mock()

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
            _mock_validate(),
            patch("src.api.routes.onboarding.SettingsService") as MockService,
        ):
            MockService.return_value.toggle_setting.return_value = False
            MockService.return_value.close = Mock()

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
            _mock_validate(),
            patch("src.api.routes.onboarding.SettingsService") as MockService,
        ):
            MockService.return_value.toggle_setting.return_value = True
            MockService.return_value.close = Mock()

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
            _mock_validate(),
            patch("src.api.routes.onboarding.SettingsService") as MockService,
        ):
            MockService.return_value.toggle_setting.return_value = False
            MockService.return_value.close = Mock()

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
            _mock_validate(),
            patch("src.api.routes.onboarding.SettingsService") as MockService,
        ):
            MockService.return_value.toggle_setting.return_value = True
            MockService.return_value.close = Mock()

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
        with _mock_validate():
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
                "src.api.routes.onboarding.validate_init_data",
                side_effect=ValueError("bad"),
            ),
            patch(
                "src.api.routes.onboarding.validate_url_token",
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
            _mock_validate(),
            patch("src.api.routes.onboarding.SettingsService") as MockService,
        ):
            MockService.return_value.close = Mock()

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
        MockService.return_value.update_setting.assert_called_once_with(
            CHAT_ID, "posts_per_day", 10
        )

    def test_update_posting_hours_start(self, client):
        """Update posting_hours_start returns new value."""
        with (
            _mock_validate(),
            patch("src.api.routes.onboarding.SettingsService") as MockService,
        ):
            MockService.return_value.close = Mock()

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
            _mock_validate(),
            patch("src.api.routes.onboarding.SettingsService") as MockService,
        ):
            MockService.return_value.close = Mock()

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
        with _mock_validate():
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
        with _mock_validate():
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
                "src.api.routes.onboarding.validate_init_data",
                side_effect=ValueError("bad"),
            ),
            patch(
                "src.api.routes.onboarding.validate_url_token",
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
            _mock_validate(),
            patch("src.services.core.scheduler.SchedulerService") as MockScheduler,
        ):
            MockScheduler.return_value.extend_schedule.return_value = {
                "scheduled": 21,
                "skipped": 0,
                "total_slots": 21,
                "extended_from": "2026-02-28T00:00:00",
            }
            MockScheduler.return_value.close = Mock()

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
            _mock_validate(),
            patch("src.services.core.scheduler.SchedulerService") as MockScheduler,
        ):
            MockScheduler.return_value.extend_schedule.return_value = {
                "scheduled": 21,
                "skipped": 0,
                "total_slots": 21,
            }
            MockScheduler.return_value.close = Mock()

            response = client.post(
                "/api/onboarding/extend-schedule",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 200
        MockScheduler.return_value.extend_schedule.assert_called_once_with(
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
        mock_settings = _mock_settings_obj()

        with (
            _mock_validate(),
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch("src.api.routes.onboarding.QueueRepository") as MockQueueRepo,
            patch("src.services.core.scheduler.SchedulerService") as MockScheduler,
        ):
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.close = Mock()
            MockQueueRepo.return_value.delete_all_pending.return_value = 42
            MockQueueRepo.return_value.close = Mock()
            MockScheduler.return_value.create_schedule.return_value = {
                "scheduled": 21,
                "skipped": 0,
                "total_slots": 21,
            }
            MockScheduler.return_value.close = Mock()

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
        MockQueueRepo.return_value.delete_all_pending.assert_called_once()
        MockScheduler.return_value.create_schedule.assert_called_once_with(
            days=7, telegram_chat_id=CHAT_ID
        )

    def test_regenerate_schedule_unauthorized(self, client):
        """Regenerate rejects invalid auth."""
        with (
            patch(
                "src.api.routes.onboarding.validate_init_data",
                side_effect=ValueError("bad"),
            ),
            patch(
                "src.api.routes.onboarding.validate_url_token",
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
        mock_settings = _mock_settings_obj(
            onboarding_completed=True, media_source_root=None
        )
        now = datetime(2026, 2, 22, 14, 0, 0, tzinfo=timezone.utc)
        later = datetime(2026, 2, 28, 18, 0, 0, tzinfo=timezone.utc)

        queue_items = [
            _mock_queue_item(now),
            _mock_queue_item(later),
        ]

        with (
            _mock_validate(),
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch("src.api.routes.onboarding.TokenRepository") as MockTokenRepo,
            patch("src.api.routes.onboarding.InstagramAccountService") as MockIGService,
            patch("src.api.routes.onboarding.QueueRepository") as MockQueueRepo,
            patch("src.api.routes.onboarding.HistoryRepository") as MockHistoryRepo,
        ):
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.close = Mock()
            MockTokenRepo.return_value.get_token_for_chat.return_value = None
            MockTokenRepo.return_value.close = Mock()
            MockIGService.return_value.get_active_account.return_value = None
            MockIGService.return_value.close = Mock()
            MockQueueRepo.return_value.get_all.return_value = queue_items
            MockQueueRepo.return_value.close = Mock()
            MockHistoryRepo.return_value.get_recent_posts.return_value = []
            MockHistoryRepo.return_value.close = Mock()

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
        mock_settings = _mock_settings_obj(
            onboarding_completed=True,
            media_source_root=None,
            enable_instagram_api=True,
            show_verbose_notifications=False,
            media_sync_enabled=True,
        )

        with (
            _mock_validate(),
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch("src.api.routes.onboarding.TokenRepository") as MockTokenRepo,
            patch("src.api.routes.onboarding.InstagramAccountService") as MockIGService,
            patch("src.api.routes.onboarding.QueueRepository") as MockQueueRepo,
            patch("src.api.routes.onboarding.HistoryRepository") as MockHistoryRepo,
        ):
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.close = Mock()
            MockTokenRepo.return_value.get_token_for_chat.return_value = None
            MockTokenRepo.return_value.close = Mock()
            MockIGService.return_value.get_active_account.return_value = None
            MockIGService.return_value.close = Mock()
            MockQueueRepo.return_value.get_all.return_value = []
            MockQueueRepo.return_value.close = Mock()
            MockHistoryRepo.return_value.get_recent_posts.return_value = []
            MockHistoryRepo.return_value.close = Mock()

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
        mock_settings = _mock_settings_obj(
            onboarding_completed=True, media_source_root=None
        )

        with (
            _mock_validate(),
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch("src.api.routes.onboarding.TokenRepository") as MockTokenRepo,
            patch("src.api.routes.onboarding.InstagramAccountService") as MockIGService,
            patch("src.api.routes.onboarding.QueueRepository") as MockQueueRepo,
            patch("src.api.routes.onboarding.HistoryRepository") as MockHistoryRepo,
        ):
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.close = Mock()
            MockTokenRepo.return_value.get_token_for_chat.return_value = None
            MockTokenRepo.return_value.close = Mock()
            MockIGService.return_value.get_active_account.return_value = None
            MockIGService.return_value.close = Mock()
            MockQueueRepo.return_value.get_all.return_value = []
            MockQueueRepo.return_value.close = Mock()
            MockHistoryRepo.return_value.get_recent_posts.return_value = []
            MockHistoryRepo.return_value.close = Mock()

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
            _mock_validate(),
            patch("src.services.core.health_check.HealthCheckService") as MockHealthService,
        ):
            MockHealthService.return_value.check_all.return_value = (
                _mock_health_checks()
            )
            MockHealthService.return_value.queue_repo = Mock()
            MockHealthService.return_value.history_repo = Mock()

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
            _mock_validate(),
            patch("src.services.core.health_check.HealthCheckService") as MockHealthService,
        ):
            MockHealthService.return_value.check_all.return_value = health_data
            MockHealthService.return_value.queue_repo = Mock()
            MockHealthService.return_value.history_repo = Mock()

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
                "src.api.routes.onboarding.validate_init_data",
                side_effect=ValueError("bad"),
            ),
            patch(
                "src.api.routes.onboarding.validate_url_token",
                side_effect=ValueError("bad"),
            ),
        ):
            response = client.get(
                "/api/onboarding/system-status",
                params={"init_data": "invalid", "chat_id": CHAT_ID},
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
            _mock_validate(),
            patch("src.api.routes.onboarding.InstagramAccountService") as MockIGService,
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
        ):
            MockIGService.return_value.list_accounts.return_value = [acct_1, acct_2]
            MockIGService.return_value.close = Mock()
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.close = Mock()

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
            _mock_validate(),
            patch("src.api.routes.onboarding.InstagramAccountService") as MockIGService,
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
        ):
            MockIGService.return_value.list_accounts.return_value = []
            MockIGService.return_value.close = Mock()
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.close = Mock()

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
                "src.api.routes.onboarding.validate_init_data",
                side_effect=ValueError("bad"),
            ),
            patch(
                "src.api.routes.onboarding.validate_url_token",
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
            _mock_validate(),
            patch("src.api.routes.onboarding.InstagramAccountService") as MockIGService,
        ):
            MockIGService.return_value.switch_account.return_value = acct
            MockIGService.return_value.close = Mock()

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
        MockIGService.return_value.switch_account.assert_called_once_with(
            telegram_chat_id=CHAT_ID,
            account_id=str(acct.id),
        )

    def test_switch_account_not_found(self, client):
        """Switch account returns 400 for unknown account."""
        with (
            _mock_validate(),
            patch("src.api.routes.onboarding.InstagramAccountService") as MockIGService,
        ):
            MockIGService.return_value.switch_account.side_effect = ValueError(
                "Account not found"
            )
            MockIGService.return_value.close = Mock()

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
                "src.api.routes.onboarding.validate_init_data",
                side_effect=ValueError("bad"),
            ),
            patch(
                "src.api.routes.onboarding.validate_url_token",
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
            _mock_validate(),
            patch("src.api.routes.onboarding.InstagramAccountService") as MockIGService,
        ):
            MockIGService.return_value.deactivate_account.return_value = acct
            MockIGService.return_value.close = Mock()

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
        MockIGService.return_value.deactivate_account.assert_called_once_with(
            account_id=str(acct.id),
        )

    def test_remove_account_not_found(self, client):
        """Remove account returns 400 for unknown account."""
        with (
            _mock_validate(),
            patch("src.api.routes.onboarding.InstagramAccountService") as MockIGService,
        ):
            MockIGService.return_value.deactivate_account.side_effect = ValueError(
                "Account not found"
            )
            MockIGService.return_value.close = Mock()

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
                "src.api.routes.onboarding.validate_init_data",
                side_effect=ValueError("bad"),
            ),
            patch(
                "src.api.routes.onboarding.validate_url_token",
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
