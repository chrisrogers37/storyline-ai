"""Tests for onboarding Mini App API endpoints."""

import pytest
from datetime import datetime
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


def _mock_settings_obj(**overrides):
    """Create a mock ChatSettings object with sensible defaults."""
    defaults = dict(
        id=uuid4(),
        posts_per_day=3,
        posting_hours_start=14,
        posting_hours_end=2,
        onboarding_completed=False,
        onboarding_step=None,
        media_source_root=None,
        media_source_type=None,
        is_paused=False,
        dry_run_mode=True,
        enable_instagram_api=False,
        show_verbose_notifications=False,
        media_sync_enabled=False,
    )
    defaults.update(overrides)
    return Mock(**defaults)


def _mock_init_repos(mock_settings=None, instagram_account=None, gdrive_token=None):
    """Return context managers for the three repos used by _get_setup_state + init."""
    if mock_settings is None:
        mock_settings = _mock_settings_obj()

    settings_repo = patch("src.api.routes.onboarding.ChatSettingsRepository")
    token_repo = patch("src.api.routes.onboarding.TokenRepository")
    ig_service = patch("src.api.routes.onboarding.InstagramAccountService")
    settings_service = patch("src.api.routes.onboarding.SettingsService")

    return (
        settings_repo,
        token_repo,
        ig_service,
        settings_service,
        mock_settings,
        instagram_account,
        gdrive_token,
    )


# =============================================================================
# POST /api/onboarding/init
# =============================================================================


@pytest.mark.unit
class TestOnboardingInit:
    """Test POST /api/onboarding/init."""

    def test_init_returns_setup_state(self, client):
        """Valid initData returns chat_id, user, and setup_state."""
        mock_settings = _mock_settings_obj()

        with (
            _mock_validate(),
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch("src.api.routes.onboarding.TokenRepository") as MockTokenRepo,
            patch("src.api.routes.onboarding.InstagramAccountService") as MockIGService,
            patch("src.api.routes.onboarding.SettingsService") as MockSettingsService,
        ):
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.__enter__ = Mock(
                return_value=MockSettingsRepo.return_value
            )
            MockSettingsRepo.return_value.__exit__ = Mock(return_value=False)
            MockTokenRepo.return_value.get_token_for_chat.return_value = None
            MockTokenRepo.return_value.__enter__ = Mock(
                return_value=MockTokenRepo.return_value
            )
            MockTokenRepo.return_value.__exit__ = Mock(return_value=False)
            MockIGService.return_value.get_active_account.return_value = None
            MockIGService.return_value.__enter__ = Mock(
                return_value=MockIGService.return_value
            )
            MockIGService.return_value.__exit__ = Mock(return_value=False)
            MockSettingsService.return_value.__enter__ = Mock(
                return_value=MockSettingsService.return_value
            )
            MockSettingsService.return_value.__exit__ = Mock(return_value=False)

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
        mock_settings = _mock_settings_obj()
        mock_account = Mock(instagram_username="storyline_ai")

        with (
            _mock_validate(),
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch("src.api.routes.onboarding.TokenRepository") as MockTokenRepo,
            patch("src.api.routes.onboarding.InstagramAccountService") as MockIGService,
            patch("src.api.routes.onboarding.SettingsService") as MockSettingsService,
        ):
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.__enter__ = Mock(
                return_value=MockSettingsRepo.return_value
            )
            MockSettingsRepo.return_value.__exit__ = Mock(return_value=False)
            MockTokenRepo.return_value.get_token_for_chat.return_value = None
            MockTokenRepo.return_value.__enter__ = Mock(
                return_value=MockTokenRepo.return_value
            )
            MockTokenRepo.return_value.__exit__ = Mock(return_value=False)
            MockIGService.return_value.get_active_account.return_value = mock_account
            MockIGService.return_value.__enter__ = Mock(
                return_value=MockIGService.return_value
            )
            MockIGService.return_value.__exit__ = Mock(return_value=False)
            MockSettingsService.return_value.__enter__ = Mock(
                return_value=MockSettingsService.return_value
            )
            MockSettingsService.return_value.__exit__ = Mock(return_value=False)

            response = client.post(
                "/api/onboarding/init",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        data = response.json()
        assert data["setup_state"]["instagram_connected"] is True
        assert data["setup_state"]["instagram_username"] == "storyline_ai"

    def test_init_shows_connected_gdrive(self, client):
        """When Google Drive is connected, setup_state reflects it."""
        mock_settings = _mock_settings_obj()
        mock_token = Mock(token_metadata={"email": "user@gmail.com"})

        with (
            _mock_validate(),
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch("src.api.routes.onboarding.TokenRepository") as MockTokenRepo,
            patch("src.api.routes.onboarding.InstagramAccountService") as MockIGService,
            patch("src.api.routes.onboarding.SettingsService") as MockSettingsService,
        ):
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.__enter__ = Mock(
                return_value=MockSettingsRepo.return_value
            )
            MockSettingsRepo.return_value.__exit__ = Mock(return_value=False)
            MockTokenRepo.return_value.get_token_for_chat.return_value = mock_token
            MockTokenRepo.return_value.__enter__ = Mock(
                return_value=MockTokenRepo.return_value
            )
            MockTokenRepo.return_value.__exit__ = Mock(return_value=False)
            MockIGService.return_value.get_active_account.return_value = None
            MockIGService.return_value.__enter__ = Mock(
                return_value=MockIGService.return_value
            )
            MockIGService.return_value.__exit__ = Mock(return_value=False)
            MockSettingsService.return_value.__enter__ = Mock(
                return_value=MockSettingsService.return_value
            )
            MockSettingsService.return_value.__exit__ = Mock(return_value=False)

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

    def test_init_includes_media_folder_fields(self, client):
        """Init response contains media_folder_configured, media_indexed, media_count."""
        mock_settings = _mock_settings_obj(
            media_source_root="abc123",
            media_source_type="google_drive",
            onboarding_step="media_folder",
        )

        with (
            _mock_validate(),
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch("src.api.routes.onboarding.TokenRepository") as MockTokenRepo,
            patch("src.api.routes.onboarding.InstagramAccountService") as MockIGService,
            patch("src.api.routes.onboarding.SettingsService") as MockSettingsService,
            patch("src.repositories.media_repository.MediaRepository") as MockMediaRepo,
        ):
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.__enter__ = Mock(
                return_value=MockSettingsRepo.return_value
            )
            MockSettingsRepo.return_value.__exit__ = Mock(return_value=False)
            MockTokenRepo.return_value.get_token_for_chat.return_value = None
            MockTokenRepo.return_value.__enter__ = Mock(
                return_value=MockTokenRepo.return_value
            )
            MockTokenRepo.return_value.__exit__ = Mock(return_value=False)
            MockIGService.return_value.get_active_account.return_value = None
            MockIGService.return_value.__enter__ = Mock(
                return_value=MockIGService.return_value
            )
            MockIGService.return_value.__exit__ = Mock(return_value=False)
            MockSettingsService.return_value.__enter__ = Mock(
                return_value=MockSettingsService.return_value
            )
            MockSettingsService.return_value.__exit__ = Mock(return_value=False)
            MockMediaRepo.return_value.get_active_by_source_type.return_value = [
                Mock(),
                Mock(),
                Mock(),
            ]
            MockMediaRepo.return_value.__enter__ = Mock(
                return_value=MockMediaRepo.return_value
            )
            MockMediaRepo.return_value.__exit__ = Mock(return_value=False)

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
        mock_settings = _mock_settings_obj(
            onboarding_completed=False, onboarding_step=None
        )

        with (
            _mock_validate(),
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch("src.api.routes.onboarding.TokenRepository") as MockTokenRepo,
            patch("src.api.routes.onboarding.InstagramAccountService") as MockIGService,
            patch("src.api.routes.onboarding.SettingsService") as MockSettingsService,
        ):
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.__enter__ = Mock(
                return_value=MockSettingsRepo.return_value
            )
            MockSettingsRepo.return_value.__exit__ = Mock(return_value=False)
            MockTokenRepo.return_value.get_token_for_chat.return_value = None
            MockTokenRepo.return_value.__enter__ = Mock(
                return_value=MockTokenRepo.return_value
            )
            MockTokenRepo.return_value.__exit__ = Mock(return_value=False)
            MockIGService.return_value.get_active_account.return_value = None
            MockIGService.return_value.__enter__ = Mock(
                return_value=MockIGService.return_value
            )
            MockIGService.return_value.__exit__ = Mock(return_value=False)
            MockSettingsService.return_value.__enter__ = Mock(
                return_value=MockSettingsService.return_value
            )
            MockSettingsService.return_value.__exit__ = Mock(return_value=False)

            response = client.post(
                "/api/onboarding/init",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["setup_state"]["onboarding_step"] == "welcome"
        MockSettingsService.return_value.set_onboarding_step.assert_called_once_with(
            CHAT_ID, "welcome"
        )

    def test_init_returns_dashboard_fields(self, client):
        """Init response includes queue_count, last_post_at, is_paused, dry_run_mode."""
        mock_settings = _mock_settings_obj(
            onboarding_completed=True,
            is_paused=False,
            dry_run_mode=True,
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
            MockSettingsRepo.return_value.__enter__ = Mock(
                return_value=MockSettingsRepo.return_value
            )
            MockSettingsRepo.return_value.__exit__ = Mock(return_value=False)
            MockTokenRepo.return_value.get_token_for_chat.return_value = None
            MockTokenRepo.return_value.__enter__ = Mock(
                return_value=MockTokenRepo.return_value
            )
            MockTokenRepo.return_value.__exit__ = Mock(return_value=False)
            MockIGService.return_value.get_active_account.return_value = None
            MockIGService.return_value.__enter__ = Mock(
                return_value=MockIGService.return_value
            )
            MockIGService.return_value.__exit__ = Mock(return_value=False)
            mock_queue_items = [
                Mock(scheduled_for=datetime(2026, 2, 20, 10, 0, 0)) for _ in range(5)
            ]
            MockQueueRepo.return_value.get_all.return_value = mock_queue_items
            MockQueueRepo.return_value.__enter__ = Mock(
                return_value=MockQueueRepo.return_value
            )
            MockQueueRepo.return_value.__exit__ = Mock(return_value=False)

            mock_post = Mock()
            mock_post.posted_at = datetime(2026, 2, 18, 10, 30, 0)
            MockHistoryRepo.return_value.get_recent_posts.return_value = [mock_post]
            MockHistoryRepo.return_value.__enter__ = Mock(
                return_value=MockHistoryRepo.return_value
            )
            MockHistoryRepo.return_value.__exit__ = Mock(return_value=False)

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
        """Queue/history errors don't break the init response."""
        mock_settings = _mock_settings_obj(
            onboarding_completed=True,
            is_paused=False,
            dry_run_mode=False,
        )

        with (
            _mock_validate(),
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch("src.api.routes.onboarding.TokenRepository") as MockTokenRepo,
            patch("src.api.routes.onboarding.InstagramAccountService") as MockIGService,
            patch(
                "src.api.routes.onboarding.QueueRepository",
                side_effect=Exception("DB connection failed"),
            ),
        ):
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.__enter__ = Mock(
                return_value=MockSettingsRepo.return_value
            )
            MockSettingsRepo.return_value.__exit__ = Mock(return_value=False)
            MockTokenRepo.return_value.get_token_for_chat.return_value = None
            MockTokenRepo.return_value.__enter__ = Mock(
                return_value=MockTokenRepo.return_value
            )
            MockTokenRepo.return_value.__exit__ = Mock(return_value=False)
            MockIGService.return_value.get_active_account.return_value = None
            MockIGService.return_value.__enter__ = Mock(
                return_value=MockIGService.return_value
            )
            MockIGService.return_value.__exit__ = Mock(return_value=False)

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
            _mock_validate(),
            patch("src.services.core.oauth_service.OAuthService") as MockOAuth,
        ):
            MockOAuth.return_value.generate_authorization_url.return_value = (
                "https://facebook.com/dialog/oauth?client_id=123"
            )
            MockOAuth.return_value.__enter__ = Mock(return_value=MockOAuth.return_value)
            MockOAuth.return_value.__exit__ = Mock(return_value=False)

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
            MockGDrive.return_value.__enter__ = Mock(
                return_value=MockGDrive.return_value
            )
            MockGDrive.return_value.__exit__ = Mock(return_value=False)

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
            MockGDrive.return_value.__enter__ = Mock(
                return_value=MockGDrive.return_value
            )
            MockGDrive.return_value.__exit__ = Mock(return_value=False)
            MockSettings.return_value.__enter__ = Mock(
                return_value=MockSettings.return_value
            )
            MockSettings.return_value.__exit__ = Mock(return_value=False)

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
        # Verify folder config was saved to per-chat settings
        MockSettings.return_value.update_setting.assert_any_call(
            CHAT_ID, "media_source_type", "google_drive"
        )
        MockSettings.return_value.update_setting.assert_any_call(
            CHAT_ID, "media_source_root", "abc123"
        )
        MockSettings.return_value.update_setting.assert_any_call(
            CHAT_ID, "media_sync_enabled", True
        )
        MockSettings.return_value.set_onboarding_step.assert_called_once_with(
            CHAT_ID, "media_folder"
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
            MockGDrive.return_value.__enter__ = Mock(
                return_value=MockGDrive.return_value
            )
            MockGDrive.return_value.__exit__ = Mock(return_value=False)

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
        mock_settings = _mock_settings_obj(
            media_source_type="google_drive",
            media_source_root="abc123",
        )
        mock_sync_result = Mock(
            new=42,
            updated=0,
            unchanged=0,
            deactivated=0,
            errors=0,
            total_processed=42,
        )

        with (
            _mock_validate(),
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch("src.services.core.media_sync.MediaSyncService") as MockSync,
            patch("src.api.routes.onboarding.SettingsService") as MockStepService,
        ):
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.__enter__ = Mock(
                return_value=MockSettingsRepo.return_value
            )
            MockSettingsRepo.return_value.__exit__ = Mock(return_value=False)
            MockSync.return_value.sync.return_value = mock_sync_result
            MockSync.return_value.__enter__ = Mock(return_value=MockSync.return_value)
            MockSync.return_value.__exit__ = Mock(return_value=False)
            MockStepService.return_value.__enter__ = Mock(
                return_value=MockStepService.return_value
            )
            MockStepService.return_value.__exit__ = Mock(return_value=False)

            response = client.post(
                "/api/onboarding/start-indexing",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["indexed"] is True
        assert data["new"] == 42
        assert data["total_processed"] == 42
        MockStepService.return_value.set_onboarding_step.assert_called_once_with(
            CHAT_ID, "indexing"
        )

    def test_indexing_without_folder_returns_400(self, client):
        """Start indexing without a configured folder returns 400."""
        mock_settings = _mock_settings_obj(
            media_source_type="local",
            media_source_root=None,
        )

        with (
            _mock_validate(),
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
        ):
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.__enter__ = Mock(
                return_value=MockSettingsRepo.return_value
            )
            MockSettingsRepo.return_value.__exit__ = Mock(return_value=False)

            response = client.post(
                "/api/onboarding/start-indexing",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 400
        assert "No media folder" in response.json()["detail"]

    def test_indexing_sync_error_returns_500(self, client):
        """MediaSyncService failure returns 500 with user-friendly message."""
        mock_settings = _mock_settings_obj(
            media_source_type="google_drive",
            media_source_root="abc123",
        )

        with (
            _mock_validate(),
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch("src.services.core.media_sync.MediaSyncService") as MockSync,
        ):
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.__enter__ = Mock(
                return_value=MockSettingsRepo.return_value
            )
            MockSettingsRepo.return_value.__exit__ = Mock(return_value=False)
            MockSync.return_value.sync.side_effect = Exception("Connection timeout")
            MockSync.return_value.__enter__ = Mock(return_value=MockSync.return_value)
            MockSync.return_value.__exit__ = Mock(return_value=False)

            response = client.post(
                "/api/onboarding/start-indexing",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 500
        assert "failed" in response.json()["detail"].lower()

    def test_indexing_value_error_returns_400(self, client):
        """MediaSyncService ValueError (e.g., unconfigured provider) returns 400."""
        mock_settings = _mock_settings_obj(
            media_source_type="google_drive",
            media_source_root="abc123",
        )

        with (
            _mock_validate(),
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch("src.services.core.media_sync.MediaSyncService") as MockSync,
        ):
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.__enter__ = Mock(
                return_value=MockSettingsRepo.return_value
            )
            MockSettingsRepo.return_value.__exit__ = Mock(return_value=False)
            MockSync.return_value.sync.side_effect = ValueError(
                "Provider not configured"
            )
            MockSync.return_value.__enter__ = Mock(return_value=MockSync.return_value)
            MockSync.return_value.__exit__ = Mock(return_value=False)

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
            _mock_validate(),
            patch("src.api.routes.onboarding.SettingsService") as MockSettings,
        ):
            MockSettings.return_value.__enter__ = Mock(
                return_value=MockSettings.return_value
            )
            MockSettings.return_value.__exit__ = Mock(return_value=False)

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

        # Verify service was called 3 times for settings + 1 for step tracking
        mock_svc = MockSettings.return_value
        assert mock_svc.update_setting.call_count == 3
        mock_svc.set_onboarding_step.assert_called_once_with(CHAT_ID, "schedule")

    def test_schedule_service_validation_error_returns_400(self, client):
        """Service-level validation error returns 400."""
        with (
            _mock_validate(),
            patch("src.api.routes.onboarding.SettingsService") as MockSettings,
        ):
            MockSettings.return_value.update_setting.side_effect = ValueError(
                "Invalid setting value"
            )
            MockSettings.return_value.__enter__ = Mock(
                return_value=MockSettings.return_value
            )
            MockSettings.return_value.__exit__ = Mock(return_value=False)

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
        mock_settings = _mock_settings_obj()

        with (
            _mock_validate(),
            patch("src.api.routes.onboarding.SettingsService") as MockSettingsService,
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch("src.api.routes.onboarding.TokenRepository") as MockTokenRepo,
            patch("src.api.routes.onboarding.InstagramAccountService") as MockIGService,
        ):
            MockSettingsService.return_value.__enter__ = Mock(
                return_value=MockSettingsService.return_value
            )
            MockSettingsService.return_value.__exit__ = Mock(return_value=False)
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.__enter__ = Mock(
                return_value=MockSettingsRepo.return_value
            )
            MockSettingsRepo.return_value.__exit__ = Mock(return_value=False)
            MockTokenRepo.return_value.get_token_for_chat.return_value = None
            MockTokenRepo.return_value.__enter__ = Mock(
                return_value=MockTokenRepo.return_value
            )
            MockTokenRepo.return_value.__exit__ = Mock(return_value=False)
            MockIGService.return_value.get_active_account.return_value = None
            MockIGService.return_value.__enter__ = Mock(
                return_value=MockIGService.return_value
            )
            MockIGService.return_value.__exit__ = Mock(return_value=False)

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

        MockSettingsService.return_value.complete_onboarding.assert_called_once_with(
            CHAT_ID
        )

    def test_complete_creates_schedule(self, client):
        """Complete with create_schedule=true calls SchedulerService."""
        mock_settings = _mock_settings_obj()

        with (
            _mock_validate(),
            patch("src.api.routes.onboarding.SettingsService") as MockSettingsService,
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch("src.api.routes.onboarding.TokenRepository") as MockTokenRepo,
            patch("src.api.routes.onboarding.InstagramAccountService") as MockIGService,
            patch("src.services.core.scheduler.SchedulerService") as MockScheduler,
        ):
            MockSettingsService.return_value.__enter__ = Mock(
                return_value=MockSettingsService.return_value
            )
            MockSettingsService.return_value.__exit__ = Mock(return_value=False)
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.__enter__ = Mock(
                return_value=MockSettingsRepo.return_value
            )
            MockSettingsRepo.return_value.__exit__ = Mock(return_value=False)
            MockTokenRepo.return_value.get_token_for_chat.return_value = None
            MockTokenRepo.return_value.__enter__ = Mock(
                return_value=MockTokenRepo.return_value
            )
            MockTokenRepo.return_value.__exit__ = Mock(return_value=False)
            MockIGService.return_value.get_active_account.return_value = None
            MockIGService.return_value.__enter__ = Mock(
                return_value=MockIGService.return_value
            )
            MockIGService.return_value.__exit__ = Mock(return_value=False)
            MockScheduler.return_value.create_schedule.return_value = {
                "scheduled": 21,
                "total_slots": 21,
            }
            MockScheduler.return_value.__enter__ = Mock(
                return_value=MockScheduler.return_value
            )
            MockScheduler.return_value.__exit__ = Mock(return_value=False)

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
        mock_settings = _mock_settings_obj()

        with (
            _mock_validate(),
            patch("src.api.routes.onboarding.SettingsService") as MockSettingsService,
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch("src.api.routes.onboarding.TokenRepository") as MockTokenRepo,
            patch("src.api.routes.onboarding.InstagramAccountService") as MockIGService,
            patch("src.services.core.scheduler.SchedulerService") as MockScheduler,
        ):
            MockSettingsService.return_value.__enter__ = Mock(
                return_value=MockSettingsService.return_value
            )
            MockSettingsService.return_value.__exit__ = Mock(return_value=False)
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.__enter__ = Mock(
                return_value=MockSettingsRepo.return_value
            )
            MockSettingsRepo.return_value.__exit__ = Mock(return_value=False)
            MockTokenRepo.return_value.get_token_for_chat.return_value = None
            MockTokenRepo.return_value.__enter__ = Mock(
                return_value=MockTokenRepo.return_value
            )
            MockTokenRepo.return_value.__exit__ = Mock(return_value=False)
            MockIGService.return_value.get_active_account.return_value = None
            MockIGService.return_value.__enter__ = Mock(
                return_value=MockIGService.return_value
            )
            MockIGService.return_value.__exit__ = Mock(return_value=False)
            MockScheduler.return_value.create_schedule.side_effect = Exception(
                "No media items"
            )
            MockScheduler.return_value.__enter__ = Mock(
                return_value=MockScheduler.return_value
            )
            MockScheduler.return_value.__exit__ = Mock(return_value=False)

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

    def test_complete_enables_instagram_when_connected(self, client):
        """When Instagram is connected, complete enables enable_instagram_api."""
        mock_settings = _mock_settings_obj()
        mock_account = Mock(instagram_username="test_ig")

        with (
            _mock_validate(),
            patch("src.api.routes.onboarding.SettingsService") as MockSettingsService,
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch("src.api.routes.onboarding.TokenRepository") as MockTokenRepo,
            patch("src.api.routes.onboarding.InstagramAccountService") as MockIGService,
        ):
            MockSettingsService.return_value.__enter__ = Mock(
                return_value=MockSettingsService.return_value
            )
            MockSettingsService.return_value.__exit__ = Mock(return_value=False)
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.__enter__ = Mock(
                return_value=MockSettingsRepo.return_value
            )
            MockSettingsRepo.return_value.__exit__ = Mock(return_value=False)
            MockTokenRepo.return_value.get_token_for_chat.return_value = None
            MockTokenRepo.return_value.__enter__ = Mock(
                return_value=MockTokenRepo.return_value
            )
            MockTokenRepo.return_value.__exit__ = Mock(return_value=False)
            MockIGService.return_value.get_active_account.return_value = mock_account
            MockIGService.return_value.__enter__ = Mock(
                return_value=MockIGService.return_value
            )
            MockIGService.return_value.__exit__ = Mock(return_value=False)

            response = client.post(
                "/api/onboarding/complete",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "create_schedule": False,
                },
            )

        assert response.status_code == 200

        calls = MockSettingsService.return_value.update_setting.call_args_list
        setting_updates = {c.args[1]: c.args[2] for c in calls}
        assert setting_updates.get("enable_instagram_api") is True

    def test_complete_does_not_disable_dry_run(self, client):
        """Complete NEVER changes dry_run_mode."""
        mock_settings = _mock_settings_obj(media_source_root="abc123")

        with (
            _mock_validate(),
            patch("src.api.routes.onboarding.SettingsService") as MockSettingsService,
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch("src.api.routes.onboarding.TokenRepository") as MockTokenRepo,
            patch("src.api.routes.onboarding.InstagramAccountService") as MockIGService,
            patch("src.repositories.media_repository.MediaRepository") as MockMediaRepo,
        ):
            MockSettingsService.return_value.__enter__ = Mock(
                return_value=MockSettingsService.return_value
            )
            MockSettingsService.return_value.__exit__ = Mock(return_value=False)
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.__enter__ = Mock(
                return_value=MockSettingsRepo.return_value
            )
            MockSettingsRepo.return_value.__exit__ = Mock(return_value=False)
            MockTokenRepo.return_value.get_token_for_chat.return_value = None
            MockTokenRepo.return_value.__enter__ = Mock(
                return_value=MockTokenRepo.return_value
            )
            MockTokenRepo.return_value.__exit__ = Mock(return_value=False)
            MockIGService.return_value.get_active_account.return_value = Mock(
                instagram_username="test"
            )
            MockIGService.return_value.__enter__ = Mock(
                return_value=MockIGService.return_value
            )
            MockIGService.return_value.__exit__ = Mock(return_value=False)
            MockMediaRepo.return_value.get_active_by_source_type.return_value = [Mock()]
            MockMediaRepo.return_value.__enter__ = Mock(
                return_value=MockMediaRepo.return_value
            )
            MockMediaRepo.return_value.__exit__ = Mock(return_value=False)

            client.post(
                "/api/onboarding/complete",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "create_schedule": False,
                },
            )

        calls = MockSettingsService.return_value.update_setting.call_args_list
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
        mock_settings = _mock_settings_obj()

        with (
            _mock_validate(return_value=user_with_chat),
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch("src.api.routes.onboarding.TokenRepository") as MockTokenRepo,
            patch("src.api.routes.onboarding.InstagramAccountService") as MockIGService,
            patch("src.api.routes.onboarding.SettingsService") as MockSettingsService,
        ):
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.__enter__ = Mock(
                return_value=MockSettingsRepo.return_value
            )
            MockSettingsRepo.return_value.__exit__ = Mock(return_value=False)
            MockTokenRepo.return_value.get_token_for_chat.return_value = None
            MockTokenRepo.return_value.__enter__ = Mock(
                return_value=MockTokenRepo.return_value
            )
            MockTokenRepo.return_value.__exit__ = Mock(return_value=False)
            MockIGService.return_value.get_active_account.return_value = None
            MockIGService.return_value.__enter__ = Mock(
                return_value=MockIGService.return_value
            )
            MockIGService.return_value.__exit__ = Mock(return_value=False)
            MockSettingsService.return_value.__enter__ = Mock(
                return_value=MockSettingsService.return_value
            )
            MockSettingsService.return_value.__exit__ = Mock(return_value=False)

            response = client.post(
                "/api/onboarding/init",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 200

    def test_no_chat_id_in_initdata_allows_any(self, client):
        """If initData has no chat_id (DM context), request proceeds."""
        mock_settings = _mock_settings_obj()

        with (
            _mock_validate(),  # default: no chat_id in return
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch("src.api.routes.onboarding.TokenRepository") as MockTokenRepo,
            patch("src.api.routes.onboarding.InstagramAccountService") as MockIGService,
            patch("src.api.routes.onboarding.SettingsService") as MockSettingsService,
        ):
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.__enter__ = Mock(
                return_value=MockSettingsRepo.return_value
            )
            MockSettingsRepo.return_value.__exit__ = Mock(return_value=False)
            MockTokenRepo.return_value.get_token_for_chat.return_value = None
            MockTokenRepo.return_value.__enter__ = Mock(
                return_value=MockTokenRepo.return_value
            )
            MockTokenRepo.return_value.__exit__ = Mock(return_value=False)
            MockIGService.return_value.get_active_account.return_value = None
            MockIGService.return_value.__enter__ = Mock(
                return_value=MockIGService.return_value
            )
            MockIGService.return_value.__exit__ = Mock(return_value=False)
            MockSettingsService.return_value.__enter__ = Mock(
                return_value=MockSettingsService.return_value
            )
            MockSettingsService.return_value.__exit__ = Mock(return_value=False)

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
