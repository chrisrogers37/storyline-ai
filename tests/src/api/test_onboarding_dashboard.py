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

    def test_toggle_setting_disallowed(self, client):
        """Cannot toggle settings not in the allowed list."""
        with _mock_validate():
            response = client.post(
                "/api/onboarding/toggle-setting",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "setting_name": "enable_instagram_api",
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
