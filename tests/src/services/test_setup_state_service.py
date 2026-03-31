"""Tests for SetupStateService."""

from datetime import datetime, timedelta

import pytest
from unittest.mock import Mock, patch

from src.services.core.setup_state_service import (
    SetupStateService,
    TOKEN_STALE_DAYS,
    is_token_stale,
)
from tests.src.services.conftest import mock_track_execution


@pytest.mark.unit
class TestGetSetupState:
    """Tests for SetupStateService.get_setup_state()."""

    @pytest.fixture(autouse=True)
    def setup_service(self):
        with patch.object(SetupStateService, "__init__", lambda self: None):
            self.service = SetupStateService()
            self.service.service_run_repo = Mock()
            self.service.service_name = "SetupStateService"
            self.service.track_execution = mock_track_execution
            self.service.settings_service = Mock()
            self.service.ig_account_service = Mock()
            self.service.token_repo = Mock()
            self.service.media_repo = Mock()
            self.service.queue_repo = Mock()
            self.service.history_repo = Mock()

    def _make_chat_settings(self, **overrides):
        defaults = {
            "id": "uuid-123",
            "posts_per_day": 3,
            "posting_hours_start": 14,
            "posting_hours_end": 2,
            "onboarding_completed": False,
            "onboarding_step": None,
            "is_paused": False,
            "dry_run_mode": True,
            "enable_instagram_api": False,
            "show_verbose_notifications": True,
            "media_sync_enabled": False,
            "media_source_root": None,
        }
        defaults.update(overrides)
        return Mock(**defaults)

    @pytest.fixture(autouse=True)
    def setup_default_mocks(self, setup_service):
        """Set all-disconnected baseline. Tests override what they vary."""
        self.service.settings_service.get_settings.return_value = (
            self._make_chat_settings()
        )
        self.service.ig_account_service.get_active_account.return_value = None
        self.service.token_repo.get_token_for_chat.return_value = None
        self.service.media_repo.get_active_by_source_type.return_value = []
        self.service.queue_repo.get_all.return_value = []
        self.service.history_repo.get_recent_posts.return_value = []

    def test_all_disconnected(self):
        """All services disconnected returns default False/None/0 state."""
        state = self.service.get_setup_state(-1001234567890)

        assert state["instagram_connected"] is False
        assert state["instagram_username"] is None
        assert state["gdrive_connected"] is False
        assert state["gdrive_email"] is None
        assert state["gdrive_needs_reconnect"] is False
        assert state["media_folder_configured"] is False
        assert state["media_indexed"] is False
        assert state["media_count"] == 0
        assert state["in_flight_count"] == 0
        assert state["posting_active"] is False

    def test_instagram_connected(self):
        """Active Instagram account is reflected in state."""
        self.service.ig_account_service.get_active_account.return_value = Mock(
            instagram_username="testuser",
            display_name="Test User",
        )

        state = self.service.get_setup_state(-1001234567890)

        assert state["instagram_connected"] is True
        assert state["instagram_username"] == "testuser"

    def test_gdrive_connected_fresh(self):
        """Fresh Google Drive token shows connected, not needing reconnect."""
        self.service.token_repo.get_token_for_chat.return_value = Mock(
            token_metadata={"email": "user@gmail.com"},
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )

        state = self.service.get_setup_state(-1001234567890)

        assert state["gdrive_connected"] is True
        assert state["gdrive_email"] == "user@gmail.com"
        assert state["gdrive_needs_reconnect"] is False

    def test_gdrive_needs_reconnect(self):
        """Token expired > 7 days ago triggers needs_reconnect."""
        self.service.token_repo.get_token_for_chat.return_value = Mock(
            token_metadata={"email": "old@gmail.com"},
            expires_at=datetime.utcnow() - timedelta(days=TOKEN_STALE_DAYS + 1),
        )

        state = self.service.get_setup_state(-1001234567890)

        assert state["gdrive_connected"] is True
        assert state["gdrive_needs_reconnect"] is True

    def test_media_indexed(self):
        """Configured folder with media items shows indexed."""
        self.service.settings_service.get_settings.return_value = (
            self._make_chat_settings(media_source_root="folder123")
        )
        self.service.media_repo.get_active_by_source_type.return_value = [
            Mock(),
            Mock(),
            Mock(),
        ]

        state = self.service.get_setup_state(-1001234567890)

        assert state["media_folder_configured"] is True
        assert state["media_folder_id"] == "folder123"
        assert state["media_indexed"] is True
        assert state["media_count"] == 3

    def test_posting_active(self):
        """Recent post within 48h makes posting_active True."""
        self.service.history_repo.get_recent_posts.return_value = [
            Mock(posted_at=datetime.utcnow() - timedelta(hours=1)),
        ]

        state = self.service.get_setup_state(-1001234567890)

        assert state["posting_active"] is True
        assert state["last_post_at"] is not None

    def test_instagram_check_exception_returns_disconnected(self):
        """Exception in Instagram check returns disconnected gracefully."""
        self.service.ig_account_service.get_active_account.side_effect = Exception(
            "DB error"
        )

        state = self.service.get_setup_state(-1001234567890)

        assert state["instagram_connected"] is False


@pytest.mark.unit
class TestIsTokenStale:
    """Tests for is_token_stale() utility function."""

    def test_fresh_token_not_stale(self):
        """Token expiring in the future is not stale."""
        token = Mock(expires_at=datetime.utcnow() + timedelta(hours=1))
        assert is_token_stale(token) is False

    def test_recently_expired_not_stale(self):
        """Token expired within 7 days is not stale."""
        token = Mock(
            expires_at=datetime.utcnow() - timedelta(days=TOKEN_STALE_DAYS - 1)
        )
        assert is_token_stale(token) is False

    def test_expired_over_threshold_is_stale(self):
        """Token expired > 7 days ago is stale."""
        token = Mock(
            expires_at=datetime.utcnow() - timedelta(days=TOKEN_STALE_DAYS + 1)
        )
        assert is_token_stale(token) is True

    def test_no_expiry_not_stale(self):
        """Token with no expires_at is not stale."""
        token = Mock(expires_at=None)
        assert is_token_stale(token) is False


@pytest.mark.unit
class TestFormatSetupStatus:
    """Tests for SetupStateService static formatters."""

    def test_gdrive_needs_reconnect_format(self):
        """Stale GDrive token formats as warning."""
        line, is_configured = SetupStateService._fmt_gdrive(
            {
                "gdrive_connected": True,
                "gdrive_needs_reconnect": True,
                "gdrive_email": "user@gmail.com",
            }
        )
        assert "Needs Reconnection" in line
        assert is_configured is False

    def test_gdrive_connected_format(self):
        """Connected GDrive formats with email."""
        line, is_configured = SetupStateService._fmt_gdrive(
            {
                "gdrive_connected": True,
                "gdrive_needs_reconnect": False,
                "gdrive_email": "user@gmail.com",
            }
        )
        assert "user@gmail.com" in line
        assert is_configured is True

    def test_gdrive_disconnected_format(self):
        """Disconnected GDrive formats as warning."""
        line, is_configured = SetupStateService._fmt_gdrive(
            {
                "gdrive_connected": False,
                "gdrive_needs_reconnect": False,
                "gdrive_email": None,
            }
        )
        assert "Not connected" in line
        assert is_configured is False
