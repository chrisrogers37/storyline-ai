"""Tests for SettingsService."""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from src.services.core.settings_service import SettingsService, TOGGLEABLE_SETTINGS, NUMERIC_SETTINGS
from src.repositories.chat_settings_repository import ChatSettingsRepository
from src.models.chat_settings import ChatSettings
from src.models.user import User


@pytest.mark.unit
class TestSettingsService:
    """Test suite for SettingsService."""

    def test_get_settings_creates_from_env_on_first_access(self, test_db):
        """First access should bootstrap settings from .env values."""
        # Create service with test db
        service = SettingsService()
        service.settings_repo = ChatSettingsRepository()
        service.settings_repo._db = test_db

        chat_id = -1001234567890

        # Get settings (should create from .env)
        settings = service.get_settings(chat_id)

        assert settings is not None
        assert settings.telegram_chat_id == chat_id
        # Should have default values from .env
        assert isinstance(settings.dry_run_mode, bool)
        assert isinstance(settings.posts_per_day, int)

    def test_get_settings_returns_existing(self, test_db):
        """Subsequent access should return existing record."""
        service = SettingsService()
        service.settings_repo = ChatSettingsRepository()
        service.settings_repo._db = test_db

        chat_id = -1001234567891

        # First access creates
        settings1 = service.get_settings(chat_id)
        # Second access returns same
        settings2 = service.get_settings(chat_id)

        assert settings1.id == settings2.id

    def test_toggle_setting_flips_boolean(self, test_db):
        """Toggle should flip dry_run_mode from True to False."""
        service = SettingsService()
        service.settings_repo = ChatSettingsRepository()
        service.settings_repo._db = test_db
        service.service_run_repo._db = test_db

        chat_id = -1001234567892

        # Get initial settings
        settings = service.get_settings(chat_id)
        initial_value = settings.dry_run_mode

        # Toggle
        mock_user = Mock(spec=User)
        mock_user.id = "test-user-id"
        mock_user.telegram_username = "testuser"

        new_value = service.toggle_setting(chat_id, "dry_run_mode", mock_user)

        assert new_value != initial_value
        assert new_value == (not initial_value)

    def test_toggle_invalid_setting_raises_error(self, test_db):
        """Toggling non-toggleable setting should raise ValueError."""
        service = SettingsService()
        service.settings_repo = ChatSettingsRepository()
        service.settings_repo._db = test_db

        chat_id = -1001234567893

        with pytest.raises(ValueError, match="not toggleable"):
            service.toggle_setting(chat_id, "posts_per_day", None)

    def test_update_posts_per_day_validates_range(self, test_db):
        """posts_per_day outside 1-50 should raise ValueError."""
        service = SettingsService()
        service.settings_repo = ChatSettingsRepository()
        service.settings_repo._db = test_db
        service.service_run_repo._db = test_db

        chat_id = -1001234567894

        # Too low
        with pytest.raises(ValueError, match="must be between 1 and 50"):
            service.update_setting(chat_id, "posts_per_day", 0, None)

        # Too high
        with pytest.raises(ValueError, match="must be between 1 and 50"):
            service.update_setting(chat_id, "posts_per_day", 100, None)

        # Valid
        result = service.update_setting(chat_id, "posts_per_day", 10, None)
        assert result.posts_per_day == 10

    def test_update_posting_hours_validates_range(self, test_db):
        """Hour must be between 0 and 23."""
        service = SettingsService()
        service.settings_repo = ChatSettingsRepository()
        service.settings_repo._db = test_db
        service.service_run_repo._db = test_db

        chat_id = -1001234567895

        # Invalid hour
        with pytest.raises(ValueError, match="Hour must be between 0 and 23"):
            service.update_setting(chat_id, "posting_hours_start", 25, None)

        # Valid hour
        result = service.update_setting(chat_id, "posting_hours_start", 14, None)
        assert result.posting_hours_start == 14

    def test_pause_tracks_user_and_timestamp(self, test_db):
        """Pausing should record who paused and when."""
        service = SettingsService()
        service.settings_repo = ChatSettingsRepository()
        service.settings_repo._db = test_db
        service.service_run_repo._db = test_db

        chat_id = -1001234567896

        # Create user in database first
        from src.repositories.user_repository import UserRepository
        user_repo = UserRepository()
        user_repo._db = test_db

        user = user_repo.create(
            telegram_user_id=123456789,
            telegram_username="pauseuser",
            telegram_first_name="Pause",
        )

        # Ensure not paused initially
        settings = service.get_settings(chat_id)
        if settings.is_paused:
            service.toggle_setting(chat_id, "is_paused", user)

        # Now pause
        before_pause = datetime.utcnow()
        service.toggle_setting(chat_id, "is_paused", user)

        # Check pause state was recorded
        updated_settings = service.get_settings(chat_id)
        assert updated_settings.is_paused is True
        assert updated_settings.paused_at is not None
        assert updated_settings.paused_at >= before_pause
        assert str(updated_settings.paused_by_user_id) == str(user.id)

    def test_unpause_clears_tracking(self, test_db):
        """Unpausing should clear paused_at and paused_by_user_id."""
        service = SettingsService()
        service.settings_repo = ChatSettingsRepository()
        service.settings_repo._db = test_db
        service.service_run_repo._db = test_db

        chat_id = -1001234567897

        # Create user
        from src.repositories.user_repository import UserRepository
        user_repo = UserRepository()
        user_repo._db = test_db

        user = user_repo.create(
            telegram_user_id=987654321,
            telegram_username="unpauseuser",
            telegram_first_name="Unpause",
        )

        # Ensure paused
        settings = service.get_settings(chat_id)
        if not settings.is_paused:
            service.toggle_setting(chat_id, "is_paused", user)

        # Now unpause
        service.toggle_setting(chat_id, "is_paused", user)

        # Check pause state was cleared
        updated_settings = service.get_settings(chat_id)
        assert updated_settings.is_paused is False
        assert updated_settings.paused_at is None
        assert updated_settings.paused_by_user_id is None

    def test_get_settings_display(self, test_db):
        """get_settings_display should return dict with all settings."""
        service = SettingsService()
        service.settings_repo = ChatSettingsRepository()
        service.settings_repo._db = test_db

        chat_id = -1001234567898

        display = service.get_settings_display(chat_id)

        # Should have all expected keys
        assert "dry_run_mode" in display
        assert "enable_instagram_api" in display
        assert "is_paused" in display
        assert "posts_per_day" in display
        assert "posting_hours_start" in display
        assert "posting_hours_end" in display
        assert "updated_at" in display

    def test_update_unknown_setting_raises_error(self, test_db):
        """Updating unknown setting should raise ValueError."""
        service = SettingsService()
        service.settings_repo = ChatSettingsRepository()
        service.settings_repo._db = test_db

        chat_id = -1001234567899

        with pytest.raises(ValueError, match="Unknown setting"):
            service.update_setting(chat_id, "nonexistent_setting", "value", None)
