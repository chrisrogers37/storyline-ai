"""Tests for onboarding Mini App API endpoints."""

import pytest
from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from src.api.app import app


@pytest.fixture
def client():
    return TestClient(app)


VALID_USER = {"user_id": 12345, "first_name": "Chris"}
CHAT_ID = -1001234567890


def _mock_validate(return_value=None):
    """Patch validate_init_data to skip HMAC validation in tests.

    The default return has no chat_id, simulating DM-opened Mini Apps.
    Pass chat_id in return_value to test group-chat initData.
    """
    return patch(
        "src.api.routes.onboarding.validate_init_data",
        return_value=return_value or VALID_USER,
    )


# =============================================================================
# POST /api/onboarding/init
# =============================================================================


@pytest.mark.unit
class TestOnboardingInit:
    """Test POST /api/onboarding/init."""

    def test_init_returns_setup_state(self, client):
        """Valid initData returns chat_id, user, and setup_state."""
        mock_settings = Mock(
            id=uuid4(),
            posts_per_day=3,
            posting_hours_start=14,
            posting_hours_end=2,
            onboarding_completed=False,
        )

        with (
            _mock_validate(),
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch("src.api.routes.onboarding.TokenRepository") as MockTokenRepo,
            patch("src.api.routes.onboarding.InstagramAccountService") as MockIGService,
        ):
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.close = Mock()
            MockTokenRepo.return_value.get_token_for_chat.return_value = None
            MockTokenRepo.return_value.close = Mock()
            MockIGService.return_value.get_active_account.return_value = None
            MockIGService.return_value.close = Mock()

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
        mock_settings = Mock(
            id=uuid4(),
            posts_per_day=3,
            posting_hours_start=14,
            posting_hours_end=2,
            onboarding_completed=False,
        )
        mock_account = Mock(instagram_username="storyline_ai")

        with (
            _mock_validate(),
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch("src.api.routes.onboarding.TokenRepository") as MockTokenRepo,
            patch("src.api.routes.onboarding.InstagramAccountService") as MockIGService,
        ):
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.close = Mock()
            MockTokenRepo.return_value.get_token_for_chat.return_value = None
            MockTokenRepo.return_value.close = Mock()
            MockIGService.return_value.get_active_account.return_value = mock_account
            MockIGService.return_value.close = Mock()

            response = client.post(
                "/api/onboarding/init",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        data = response.json()
        assert data["setup_state"]["instagram_connected"] is True
        assert data["setup_state"]["instagram_username"] == "storyline_ai"

    def test_init_shows_connected_gdrive(self, client):
        """When Google Drive is connected, setup_state reflects it."""
        mock_settings = Mock(
            id=uuid4(),
            posts_per_day=3,
            posting_hours_start=14,
            posting_hours_end=2,
            onboarding_completed=False,
        )
        mock_token = Mock(token_metadata={"email": "user@gmail.com"})

        with (
            _mock_validate(),
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch("src.api.routes.onboarding.TokenRepository") as MockTokenRepo,
            patch("src.api.routes.onboarding.InstagramAccountService") as MockIGService,
        ):
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.close = Mock()
            MockTokenRepo.return_value.get_token_for_chat.return_value = mock_token
            MockTokenRepo.return_value.close = Mock()
            MockIGService.return_value.get_active_account.return_value = None
            MockIGService.return_value.close = Mock()

            response = client.post(
                "/api/onboarding/init",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        data = response.json()
        assert data["setup_state"]["gdrive_connected"] is True
        assert data["setup_state"]["gdrive_email"] == "user@gmail.com"

    def test_init_invalid_data_returns_401(self, client):
        """Invalid initData returns 401."""
        with patch(
            "src.api.routes.onboarding.validate_init_data",
            side_effect=ValueError("Invalid initData signature"),
        ):
            response = client.post(
                "/api/onboarding/init",
                json={"init_data": "bad-data", "chat_id": CHAT_ID},
            )

        assert response.status_code == 401
        assert "Invalid" in response.json()["detail"]


# =============================================================================
# GET /api/onboarding/oauth-url/{provider}
# =============================================================================


@pytest.mark.unit
class TestOnboardingOAuthUrl:
    """Test GET /api/onboarding/oauth-url/{provider}."""

    def test_instagram_returns_auth_url(self, client):
        """Instagram provider returns OAuth authorization URL."""
        with (
            _mock_validate(),
            patch("src.services.core.oauth_service.OAuthService") as MockOAuth,
        ):
            MockOAuth.return_value.generate_authorization_url.return_value = (
                "https://facebook.com/dialog/oauth?client_id=123"
            )
            MockOAuth.return_value.close = Mock()

            response = client.get(
                f"/api/onboarding/oauth-url/instagram?init_data=test&chat_id={CHAT_ID}"
            )

        assert response.status_code == 200
        assert "facebook.com" in response.json()["auth_url"]

    def test_gdrive_returns_auth_url(self, client):
        """Google Drive provider returns OAuth authorization URL."""
        with (
            _mock_validate(),
            patch(
                "src.services.integrations.google_drive_oauth.GoogleDriveOAuthService"
            ) as MockGDrive,
        ):
            MockGDrive.return_value.generate_authorization_url.return_value = (
                "https://accounts.google.com/o/oauth2/auth?client_id=123"
            )
            MockGDrive.return_value.close = Mock()

            response = client.get(
                f"/api/onboarding/oauth-url/google-drive"
                f"?init_data=test&chat_id={CHAT_ID}"
            )

        assert response.status_code == 200
        assert "google.com" in response.json()["auth_url"]

    def test_unknown_provider_returns_400(self, client):
        """Unknown provider returns 400."""
        with _mock_validate():
            response = client.get(
                f"/api/onboarding/oauth-url/twitter?init_data=test&chat_id={CHAT_ID}"
            )

        assert response.status_code == 400
        assert "Unknown provider" in response.json()["detail"]

    def test_invalid_init_data_returns_401(self, client):
        """Invalid initData on oauth-url returns 401."""
        with patch(
            "src.api.routes.onboarding.validate_init_data",
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
            _mock_validate(),
            patch(
                "src.services.integrations.google_drive.GoogleDriveService"
            ) as MockGDrive,
            patch("src.api.routes.onboarding.SettingsService") as MockSettings,
        ):
            mock_provider = Mock()
            mock_provider.list_files.return_value = mock_files
            MockGDrive.return_value.get_provider_for_chat.return_value = mock_provider
            MockGDrive.return_value.close = Mock()
            MockSettings.return_value.close = Mock()

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
        assert "memes" in data["categories"]
        assert "merch" in data["categories"]
        # Verify folder config was saved to per-chat settings
        MockSettings.return_value.update_setting.assert_any_call(
            CHAT_ID, "media_source_type", "google_drive"
        )
        MockSettings.return_value.update_setting.assert_any_call(
            CHAT_ID, "media_source_root", "abc123"
        )

    def test_invalid_folder_url_returns_400(self, client):
        """Non-Drive URL returns 400."""
        with _mock_validate():
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
            _mock_validate(),
            patch(
                "src.services.integrations.google_drive.GoogleDriveService"
            ) as MockGDrive,
        ):
            MockGDrive.return_value.get_provider_for_chat.side_effect = Exception(
                "No credentials"
            )
            MockGDrive.return_value.close = Mock()

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
# POST /api/onboarding/schedule
# =============================================================================


@pytest.mark.unit
class TestOnboardingSchedule:
    """Test POST /api/onboarding/schedule."""

    def test_schedule_saves_config(self, client):
        """Valid schedule config saves to settings."""
        with (
            _mock_validate(),
            patch("src.api.routes.onboarding.SettingsService") as MockSettings,
        ):
            MockSettings.return_value.close = Mock()

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

        # Verify service was called 3 times (one per setting)
        mock_svc = MockSettings.return_value
        assert mock_svc.update_setting.call_count == 3

    def test_schedule_service_validation_error_returns_400(self, client):
        """Service-level validation error returns 400."""
        with (
            _mock_validate(),
            patch("src.api.routes.onboarding.SettingsService") as MockSettings,
        ):
            MockSettings.return_value.update_setting.side_effect = ValueError(
                "Invalid setting value"
            )
            MockSettings.return_value.close = Mock()

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
            _mock_validate(),
            patch("src.api.routes.onboarding.SettingsService") as MockSettings,
        ):
            MockSettings.return_value.close = Mock()

            response = client.post(
                "/api/onboarding/complete",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "create_schedule": False,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["onboarding_completed"] is True
        assert data["schedule_created"] is False

        MockSettings.return_value.complete_onboarding.assert_called_once_with(CHAT_ID)

    def test_complete_creates_schedule(self, client):
        """Complete with create_schedule=true calls SchedulerService."""
        with (
            _mock_validate(),
            patch("src.api.routes.onboarding.SettingsService") as MockSettings,
            patch("src.services.core.scheduler.SchedulerService") as MockScheduler,
        ):
            MockSettings.return_value.close = Mock()
            MockScheduler.return_value.create_schedule.return_value = {
                "scheduled": 21,
                "total_slots": 21,
            }
            MockScheduler.return_value.close = Mock()

            response = client.post(
                "/api/onboarding/complete",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "create_schedule": True,
                    "schedule_days": 7,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["onboarding_completed"] is True
        assert data["schedule_created"] is True
        assert data["schedule_summary"]["scheduled"] == 21

        MockScheduler.return_value.create_schedule.assert_called_once_with(
            days=7, telegram_chat_id=CHAT_ID
        )

    def test_complete_handles_schedule_error(self, client):
        """Schedule creation error doesn't fail the whole request."""
        with (
            _mock_validate(),
            patch("src.api.routes.onboarding.SettingsService") as MockSettings,
            patch("src.services.core.scheduler.SchedulerService") as MockScheduler,
        ):
            MockSettings.return_value.close = Mock()
            MockScheduler.return_value.create_schedule.side_effect = Exception(
                "No media items"
            )
            MockScheduler.return_value.close = Mock()

            response = client.post(
                "/api/onboarding/complete",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "create_schedule": True,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["onboarding_completed"] is True
        assert data["schedule_created"] is False
        assert "schedule_error" in data


# =============================================================================
# Security: Chat ID verification
# =============================================================================


@pytest.mark.unit
class TestOnboardingChatIdVerification:
    """Test that chat_id from initData is verified against request chat_id."""

    def test_mismatched_chat_id_returns_403(self, client):
        """If initData has a different chat_id than the request, return 403."""
        # initData says chat_id=999, but request says CHAT_ID
        user_with_chat = {
            "user_id": 12345,
            "first_name": "Chris",
            "chat_id": 999,
        }
        with _mock_validate(return_value=user_with_chat):
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
        mock_settings = Mock(
            id=uuid4(),
            posts_per_day=3,
            posting_hours_start=14,
            posting_hours_end=2,
            onboarding_completed=False,
        )

        with (
            _mock_validate(return_value=user_with_chat),
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch("src.api.routes.onboarding.TokenRepository") as MockTokenRepo,
            patch("src.api.routes.onboarding.InstagramAccountService") as MockIGService,
        ):
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.close = Mock()
            MockTokenRepo.return_value.get_token_for_chat.return_value = None
            MockTokenRepo.return_value.close = Mock()
            MockIGService.return_value.get_active_account.return_value = None
            MockIGService.return_value.close = Mock()

            response = client.post(
                "/api/onboarding/init",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 200

    def test_no_chat_id_in_initdata_allows_any(self, client):
        """If initData has no chat_id (DM context), request proceeds."""
        mock_settings = Mock(
            id=uuid4(),
            posts_per_day=3,
            posting_hours_start=14,
            posting_hours_end=2,
            onboarding_completed=False,
        )

        with (
            _mock_validate(),  # default: no chat_id in return
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch("src.api.routes.onboarding.TokenRepository") as MockTokenRepo,
            patch("src.api.routes.onboarding.InstagramAccountService") as MockIGService,
        ):
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.close = Mock()
            MockTokenRepo.return_value.get_token_for_chat.return_value = None
            MockTokenRepo.return_value.close = Mock()
            MockIGService.return_value.get_active_account.return_value = None
            MockIGService.return_value.close = Mock()

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
        with _mock_validate():
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
        with _mock_validate():
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
        with _mock_validate():
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

    def test_schedule_days_over_max_rejected(self, client):
        """schedule_days=100 is rejected on complete endpoint."""
        with _mock_validate():
            response = client.post(
                "/api/onboarding/complete",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "create_schedule": True,
                    "schedule_days": 100,
                },
            )

        assert response.status_code == 422
