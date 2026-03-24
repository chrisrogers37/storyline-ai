"""Tests for onboarding Mini App API endpoints."""

import pytest
from unittest.mock import Mock, patch

from tests.src.api.conftest import CHAT_ID, mock_validate, service_ctx


def _default_setup_state(**overrides):
    """Build a default setup state dict with optional overrides."""
    state = {
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
        "onboarding_completed": False,
        "onboarding_step": None,
        "is_paused": False,
        "dry_run_mode": True,
        "enable_instagram_api": False,
        "show_verbose_notifications": False,
        "media_sync_enabled": False,
        "in_flight_count": 0,
        "last_post_at": None,
        "posting_active": False,
    }
    state.update(overrides)
    return state


def _mock_setup_state(**overrides):
    """Patch SetupStateService to return a preset setup state dict."""
    state = _default_setup_state(**overrides)
    return patch(
        "src.api.routes.onboarding.helpers.SetupStateService",
        **{
            "return_value.__enter__": Mock(
                return_value=Mock(get_setup_state=Mock(return_value=state))
            ),
            "return_value.__exit__": Mock(return_value=False),
        },
    )


# =============================================================================
# POST /api/onboarding/init
# =============================================================================


@pytest.mark.unit
class TestOnboardingInit:
    """Test POST /api/onboarding/init."""

    def test_init_returns_setup_state(self, client):
        """Valid initData returns chat_id, user, and setup_state."""
        with (
            mock_validate(),
            _mock_setup_state(),
            patch(
                "src.api.routes.onboarding.setup.SettingsService"
            ) as MockSettingsService,
        ):
            service_ctx(MockSettingsService)
            response = client.post(
                "/api/onboarding/init",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["chat_id"] == CHAT_ID
        assert data["user"]["user_id"] == 12345
        assert data["setup_state"]["instagram_connected"] is False
        assert data["setup_state"]["gdrive_connected"] is False
        assert data["setup_state"]["posts_per_day"] == 3

    def test_init_shows_connected_instagram(self, client):
        """When Instagram is connected, setup_state reflects it."""
        with (
            mock_validate(),
            _mock_setup_state(
                instagram_connected=True,
                instagram_username="storyline_ai",
            ),
            patch(
                "src.api.routes.onboarding.setup.SettingsService"
            ) as MockSettingsService,
        ):
            service_ctx(MockSettingsService)
            response = client.post(
                "/api/onboarding/init",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        data = response.json()
        assert data["setup_state"]["instagram_connected"] is True
        assert data["setup_state"]["instagram_username"] == "storyline_ai"

    def test_init_shows_connected_gdrive(self, client):
        """When Google Drive is connected, setup_state reflects it."""
        with (
            mock_validate(),
            _mock_setup_state(
                gdrive_connected=True,
                gdrive_email="user@gmail.com",
                gdrive_needs_reconnect=False,
            ),
            patch(
                "src.api.routes.onboarding.setup.SettingsService"
            ) as MockSettingsService,
        ):
            service_ctx(MockSettingsService)
            response = client.post(
                "/api/onboarding/init",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        data = response.json()
        assert data["setup_state"]["gdrive_connected"] is True
        assert data["setup_state"]["gdrive_email"] == "user@gmail.com"
        assert data["setup_state"]["gdrive_needs_reconnect"] is False

    def test_init_shows_gdrive_needs_reconnect(self, client):
        """When Google Drive token is stale (expired >7 days), flag is set."""
        with (
            mock_validate(),
            _mock_setup_state(
                gdrive_connected=True,
                gdrive_needs_reconnect=True,
            ),
            patch(
                "src.api.routes.onboarding.setup.SettingsService"
            ) as MockSettingsService,
        ):
            service_ctx(MockSettingsService)
            response = client.post(
                "/api/onboarding/init",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        data = response.json()
        assert data["setup_state"]["gdrive_connected"] is True
        assert data["setup_state"]["gdrive_needs_reconnect"] is True

    def test_init_invalid_data_returns_401(self, client):
        """Invalid initData returns 401."""
        with patch(
            "src.api.routes.onboarding.helpers.validate_init_data",
            side_effect=ValueError("Invalid initData signature"),
        ):
            response = client.post(
                "/api/onboarding/init",
                json={"init_data": "bad-data", "chat_id": CHAT_ID},
            )

        assert response.status_code == 401
        assert "Invalid" in response.json()["detail"]

    def test_init_includes_media_folder_fields(self, client):
        """Init response contains media_folder_configured, media_indexed, media_count."""
        with (
            mock_validate(),
            _mock_setup_state(
                media_folder_configured=True,
                media_folder_id="abc123",
                media_indexed=True,
                media_count=3,
                onboarding_step="media_folder",
            ),
            patch(
                "src.api.routes.onboarding.setup.SettingsService"
            ) as MockSettingsService,
        ):
            service_ctx(MockSettingsService)
            response = client.post(
                "/api/onboarding/init",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        data = response.json()
        assert data["setup_state"]["media_folder_configured"] is True
        assert data["setup_state"]["media_folder_id"] == "abc123"
        assert data["setup_state"]["media_indexed"] is True
        assert data["setup_state"]["media_count"] == 3
        assert data["setup_state"]["onboarding_step"] == "media_folder"

    def test_init_sets_welcome_step_on_first_access(self, client):
        """Init sets onboarding_step='welcome' when not yet started."""
        with (
            mock_validate(),
            _mock_setup_state(onboarding_completed=False, onboarding_step=None),
            patch(
                "src.api.routes.onboarding.setup.SettingsService"
            ) as MockSettingsService,
        ):
            svc = service_ctx(MockSettingsService)
            response = client.post(
                "/api/onboarding/init",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["setup_state"]["onboarding_step"] == "welcome"
        svc.set_onboarding_step.assert_called_once_with(CHAT_ID, "welcome")

    def test_init_returns_dashboard_fields(self, client):
        """Init response includes queue_count, last_post_at, is_paused, dry_run_mode."""
        with (
            mock_validate(),
            _mock_setup_state(
                onboarding_completed=True,
                is_paused=False,
                dry_run_mode=True,
                queue_count=5,
                last_post_at="2026-02-18T10:30:00",
            ),
            patch(
                "src.api.routes.onboarding.setup.SettingsService"
            ) as MockSettingsService,
        ):
            service_ctx(MockSettingsService)
            response = client.post(
                "/api/onboarding/init",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["setup_state"]["is_paused"] is False
        assert data["setup_state"]["dry_run_mode"] is True
        assert data["setup_state"]["queue_count"] == 5
        assert data["setup_state"]["last_post_at"] is not None

    def test_init_dashboard_fields_default_on_error(self, client):
        """Queue/history errors don't break the init response (handled in service)."""
        with (
            mock_validate(),
            _mock_setup_state(
                onboarding_completed=True,
                is_paused=False,
                dry_run_mode=False,
                queue_count=0,
                last_post_at=None,
            ),
            patch(
                "src.api.routes.onboarding.setup.SettingsService"
            ) as MockSettingsService,
        ):
            service_ctx(MockSettingsService)
            response = client.post(
                "/api/onboarding/init",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["setup_state"]["queue_count"] == 0
        assert data["setup_state"]["last_post_at"] is None


# =============================================================================
# GET /api/onboarding/oauth-url/{provider}
# =============================================================================


@pytest.mark.unit
class TestOnboardingOAuthUrl:
    """Test GET /api/onboarding/oauth-url/{provider}."""

    def test_instagram_returns_auth_url(self, client):
        """Instagram provider returns OAuth authorization URL."""
        with (
            mock_validate(),
            patch("src.api.routes.onboarding.setup.OAuthService") as MockOAuth,
        ):
            svc = service_ctx(MockOAuth)
            svc.generate_authorization_url.return_value = (
                "https://facebook.com/dialog/oauth?client_id=123"
            )
            response = client.get(
                f"/api/onboarding/oauth-url/instagram?init_data=test&chat_id={CHAT_ID}"
            )

        assert response.status_code == 200
        assert "facebook.com" in response.json()["auth_url"]

    def test_gdrive_returns_auth_url(self, client):
        """Google Drive provider returns OAuth authorization URL."""
        with (
            mock_validate(),
            patch(
                "src.api.routes.onboarding.setup.GoogleDriveOAuthService"
            ) as MockGDrive,
        ):
            svc = service_ctx(MockGDrive)
            svc.generate_authorization_url.return_value = (
                "https://accounts.google.com/o/oauth2/auth?client_id=123"
            )
            response = client.get(
                f"/api/onboarding/oauth-url/google-drive"
                f"?init_data=test&chat_id={CHAT_ID}"
            )

        assert response.status_code == 200
        assert "google.com" in response.json()["auth_url"]

    def test_unknown_provider_returns_400(self, client):
        """Unknown provider returns 400."""
        with mock_validate():
            response = client.get(
                f"/api/onboarding/oauth-url/twitter?init_data=test&chat_id={CHAT_ID}"
            )

        assert response.status_code == 400
        assert "Unknown provider" in response.json()["detail"]

    def test_invalid_init_data_returns_401(self, client):
        """Invalid initData on oauth-url returns 401."""
        with patch(
            "src.api.routes.onboarding.helpers.validate_init_data",
            side_effect=ValueError("Missing hash"),
        ):
            response = client.get(
                f"/api/onboarding/oauth-url/instagram?init_data=bad&chat_id={CHAT_ID}"
            )

        assert response.status_code == 401


# =============================================================================
# POST /api/onboarding/media-folder
# =============================================================================


@pytest.mark.unit
class TestOnboardingMediaFolder:
    """Test POST /api/onboarding/media-folder."""

    def test_valid_folder_url_returns_file_count(self, client):
        """Valid Google Drive folder URL returns file count and categories."""
        mock_files = [
            {"name": "a.jpg", "category": "memes"},
            {"name": "b.jpg", "category": "memes"},
            {"name": "c.jpg", "category": "merch"},
        ]

        with (
            mock_validate(),
            patch("src.api.routes.onboarding.setup.GoogleDriveService") as MockGDrive,
            patch("src.api.routes.onboarding.setup.SettingsService") as MockSettings,
        ):
            gdrive_svc = service_ctx(MockGDrive)
            mock_provider = Mock()
            mock_provider.list_files.return_value = mock_files
            gdrive_svc.get_provider_for_chat.return_value = mock_provider
            settings_svc = service_ctx(MockSettings)

            response = client.post(
                "/api/onboarding/media-folder",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "folder_url": "https://drive.google.com/drive/folders/abc123",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["folder_id"] == "abc123"
        assert data["file_count"] == 3
        assert data["saved"] is True
        assert "memes" in data["categories"]
        assert "merch" in data["categories"]
        settings_svc.update_setting.assert_any_call(
            CHAT_ID, "media_source_type", "google_drive"
        )
        settings_svc.update_setting.assert_any_call(
            CHAT_ID, "media_source_root", "abc123"
        )
        settings_svc.set_onboarding_step.assert_called_once_with(
            CHAT_ID, "media_folder"
        )

    def test_invalid_folder_url_returns_400(self, client):
        """Non-Drive URL returns 400."""
        with mock_validate():
            response = client.post(
                "/api/onboarding/media-folder",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "folder_url": "https://example.com/not-a-folder",
                },
            )

        assert response.status_code == 400
        assert "Invalid Google Drive folder URL" in response.json()["detail"]

    def test_inaccessible_folder_returns_400(self, client):
        """Folder that can't be accessed returns 400."""
        with (
            mock_validate(),
            patch("src.api.routes.onboarding.setup.GoogleDriveService") as MockGDrive,
        ):
            svc = service_ctx(MockGDrive)
            svc.get_provider_for_chat.side_effect = Exception("No credentials")

            response = client.post(
                "/api/onboarding/media-folder",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "folder_url": "https://drive.google.com/drive/folders/xyz",
                },
            )

        assert response.status_code == 400
        assert "Cannot access" in response.json()["detail"]


# =============================================================================
# POST /api/onboarding/start-indexing
# =============================================================================


@pytest.mark.unit
class TestOnboardingStartIndexing:
    """Test POST /api/onboarding/start-indexing."""

    def test_indexing_runs_sync(self, client):
        """Start indexing triggers MediaSyncService.sync() with chat config."""
        mock_sync_result = Mock(
            new=42, updated=0, unchanged=0, deactivated=0, errors=0, total_processed=42
        )

        with (
            mock_validate(),
            patch("src.api.routes.onboarding.setup.SettingsService") as MockSettings,
            patch("src.api.routes.onboarding.setup.MediaSyncService") as MockSync,
        ):
            # First SettingsService context: get_media_source_config
            settings_svc = service_ctx(MockSettings)
            settings_svc.get_media_source_config.return_value = (
                "google_drive",
                "abc123",
            )
            # Second SettingsService context reuses same mock
            sync_svc = service_ctx(MockSync)
            sync_svc.sync.return_value = mock_sync_result

            response = client.post(
                "/api/onboarding/start-indexing",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["indexed"] is True
        assert data["new"] == 42
        assert data["total_processed"] == 42
        settings_svc.set_onboarding_step.assert_called_once_with(CHAT_ID, "indexing")

    def test_indexing_without_folder_returns_400(self, client):
        """Start indexing without a configured folder returns 400."""
        with (
            mock_validate(),
            patch("src.api.routes.onboarding.setup.SettingsService") as MockSettings,
        ):
            svc = service_ctx(MockSettings)
            svc.get_media_source_config.return_value = ("local", None)

            response = client.post(
                "/api/onboarding/start-indexing",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 400
        assert "No media folder" in response.json()["detail"]

    def test_indexing_sync_error_returns_500(self, client):
        """MediaSyncService failure returns 500 with user-friendly message."""
        with (
            mock_validate(),
            patch("src.api.routes.onboarding.setup.SettingsService") as MockSettings,
            patch("src.api.routes.onboarding.setup.MediaSyncService") as MockSync,
        ):
            svc = service_ctx(MockSettings)
            svc.get_media_source_config.return_value = ("google_drive", "abc123")
            sync_svc = service_ctx(MockSync)
            sync_svc.sync.side_effect = Exception("Connection timeout")

            response = client.post(
                "/api/onboarding/start-indexing",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 500
        assert "failed" in response.json()["detail"].lower()

    def test_indexing_value_error_returns_400(self, client):
        """MediaSyncService ValueError (e.g., unconfigured provider) returns 400."""
        with (
            mock_validate(),
            patch("src.api.routes.onboarding.setup.SettingsService") as MockSettings,
            patch("src.api.routes.onboarding.setup.MediaSyncService") as MockSync,
        ):
            svc = service_ctx(MockSettings)
            svc.get_media_source_config.return_value = ("google_drive", "abc123")
            sync_svc = service_ctx(MockSync)
            sync_svc.sync.side_effect = ValueError("Provider not configured")

            response = client.post(
                "/api/onboarding/start-indexing",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 400


# =============================================================================
# POST /api/onboarding/schedule
# =============================================================================


@pytest.mark.unit
class TestOnboardingSchedule:
    """Test POST /api/onboarding/schedule."""

    def test_schedule_saves_config(self, client):
        """Valid schedule config saves to settings."""
        with (
            mock_validate(),
            patch("src.api.routes.onboarding.setup.SettingsService") as MockSettings,
        ):
            svc = service_ctx(MockSettings)

            response = client.post(
                "/api/onboarding/schedule",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "posts_per_day": 5,
                    "posting_hours_start": 9,
                    "posting_hours_end": 21,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["posts_per_day"] == 5
        assert data["posting_hours_start"] == 9
        assert data["posting_hours_end"] == 21
        assert svc.update_setting.call_count == 3
        svc.set_onboarding_step.assert_called_once_with(CHAT_ID, "schedule")

    def test_schedule_service_validation_error_returns_400(self, client):
        """Service-level validation error returns 400."""
        with (
            mock_validate(),
            patch("src.api.routes.onboarding.setup.SettingsService") as MockSettings,
        ):
            svc = service_ctx(MockSettings)
            svc.update_setting.side_effect = ValueError("Invalid setting value")

            response = client.post(
                "/api/onboarding/schedule",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "posts_per_day": 5,
                    "posting_hours_start": 9,
                    "posting_hours_end": 21,
                },
            )

        assert response.status_code == 400


# =============================================================================
# POST /api/onboarding/complete
# =============================================================================


@pytest.mark.unit
class TestOnboardingComplete:
    """Test POST /api/onboarding/complete."""

    def test_complete_marks_onboarding_done(self, client):
        """Complete endpoint marks onboarding as finished."""
        with (
            mock_validate(),
            patch(
                "src.api.routes.onboarding.setup.SettingsService"
            ) as MockSettingsService,
            _mock_setup_state(),
        ):
            svc = service_ctx(MockSettingsService)
            response = client.post(
                "/api/onboarding/complete",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["onboarding_completed"] is True
        svc.complete_onboarding.assert_called_once_with(CHAT_ID)

    def test_complete_enables_instagram_when_connected(self, client):
        """When Instagram is connected, complete enables enable_instagram_api."""
        with (
            mock_validate(),
            patch(
                "src.api.routes.onboarding.setup.SettingsService"
            ) as MockSettingsService,
            _mock_setup_state(instagram_connected=True),
        ):
            svc = service_ctx(MockSettingsService)
            response = client.post(
                "/api/onboarding/complete",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                },
            )

        assert response.status_code == 200
        calls = svc.update_setting.call_args_list
        setting_updates = {c.args[1]: c.args[2] for c in calls}
        assert setting_updates.get("enable_instagram_api") is True

    def test_complete_does_not_disable_dry_run(self, client):
        """Complete NEVER changes dry_run_mode."""
        with (
            mock_validate(),
            patch(
                "src.api.routes.onboarding.setup.SettingsService"
            ) as MockSettingsService,
            _mock_setup_state(
                instagram_connected=True,
                media_folder_configured=True,
            ),
        ):
            svc = service_ctx(MockSettingsService)
            client.post(
                "/api/onboarding/complete",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                },
            )

        calls = svc.update_setting.call_args_list
        setting_names = [c.args[1] for c in calls]
        assert "dry_run_mode" not in setting_names


# =============================================================================
# Security: Chat ID verification
# =============================================================================


@pytest.mark.unit
class TestOnboardingChatIdVerification:
    """Test that chat_id from initData is verified against request chat_id."""

    def test_mismatched_chat_id_returns_403(self, client):
        """If initData has a different chat_id than the request, return 403."""
        user_with_chat = {
            "user_id": 12345,
            "first_name": "Chris",
            "chat_id": 999,
        }
        with mock_validate(return_value=user_with_chat):
            response = client.post(
                "/api/onboarding/init",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 403
        assert "mismatch" in response.json()["detail"].lower()

    def test_matching_chat_id_succeeds(self, client):
        """If initData chat_id matches request chat_id, proceed normally."""
        user_with_chat = {
            "user_id": 12345,
            "first_name": "Chris",
            "chat_id": CHAT_ID,
        }
        with (
            mock_validate(return_value=user_with_chat),
            _mock_setup_state(),
            patch(
                "src.api.routes.onboarding.setup.SettingsService"
            ) as MockSettingsService,
        ):
            service_ctx(MockSettingsService)
            response = client.post(
                "/api/onboarding/init",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 200

    def test_no_chat_id_in_initdata_allows_any(self, client):
        """If initData has no chat_id (DM context), request proceeds."""
        with (
            mock_validate(),
            _mock_setup_state(),
            patch(
                "src.api.routes.onboarding.setup.SettingsService"
            ) as MockSettingsService,
        ):
            service_ctx(MockSettingsService)
            response = client.post(
                "/api/onboarding/init",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 200


# =============================================================================
# Security: Input validation on schedule fields
# =============================================================================


@pytest.mark.unit
class TestOnboardingInputValidation:
    """Test Pydantic field validators reject out-of-range values."""

    def test_posts_per_day_zero_rejected(self, client):
        """posts_per_day=0 is rejected by Pydantic validation."""
        with mock_validate():
            response = client.post(
                "/api/onboarding/schedule",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "posts_per_day": 0,
                    "posting_hours_start": 9,
                    "posting_hours_end": 21,
                },
            )

        assert response.status_code == 422

    def test_posts_per_day_negative_rejected(self, client):
        """Negative posts_per_day is rejected."""
        with mock_validate():
            response = client.post(
                "/api/onboarding/schedule",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "posts_per_day": -1,
                    "posting_hours_start": 9,
                    "posting_hours_end": 21,
                },
            )

        assert response.status_code == 422

    def test_posting_hours_out_of_range_rejected(self, client):
        """posting_hours_start=25 is rejected."""
        with mock_validate():
            response = client.post(
                "/api/onboarding/schedule",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "posts_per_day": 3,
                    "posting_hours_start": 25,
                    "posting_hours_end": 21,
                },
            )

        assert response.status_code == 422
