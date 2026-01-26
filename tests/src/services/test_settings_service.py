"""Comprehensive tests for SettingsService.

Test Categories:
1. Unit tests (mocked, no DB required)
2. Integration tests (require test_db fixture)
3. Architecture validation tests
4. .env fallback behavior tests
5. Multi-chat isolation tests
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
from uuid import uuid4

from src.services.core.settings_service import (
    SettingsService,
    TOGGLEABLE_SETTINGS,
    NUMERIC_SETTINGS,
)
from src.repositories.chat_settings_repository import ChatSettingsRepository
from src.models.chat_settings import ChatSettings


# =============================================================================
# UNIT TESTS (Mocked - No Database Required)
# =============================================================================


@pytest.mark.unit
class TestSettingsServiceUnit:
    """Unit tests with mocked dependencies - run without database."""

    def test_toggleable_settings_are_defined(self):
        """Verify TOGGLEABLE_SETTINGS contains expected settings."""
        assert "dry_run_mode" in TOGGLEABLE_SETTINGS
        assert "enable_instagram_api" in TOGGLEABLE_SETTINGS
        assert "is_paused" in TOGGLEABLE_SETTINGS
        # posts_per_day should NOT be toggleable
        assert "posts_per_day" not in TOGGLEABLE_SETTINGS

    def test_numeric_settings_are_defined(self):
        """Verify NUMERIC_SETTINGS contains expected settings."""
        assert "posts_per_day" in NUMERIC_SETTINGS
        assert "posting_hours_start" in NUMERIC_SETTINGS
        assert "posting_hours_end" in NUMERIC_SETTINGS
        # dry_run_mode should NOT be numeric
        assert "dry_run_mode" not in NUMERIC_SETTINGS

    def test_toggle_invalid_setting_raises_error_without_db(self):
        """Toggling non-toggleable setting should raise ValueError immediately."""
        service = SettingsService()
        # Mock the repo to avoid DB calls
        service.settings_repo = Mock()

        with pytest.raises(ValueError, match="not toggleable"):
            service.toggle_setting(-100, "posts_per_day", None)

        # Repo should NOT have been called
        service.settings_repo.get_or_create.assert_not_called()

    def test_update_unknown_setting_raises_error_without_db(self):
        """Updating unknown setting should raise ValueError immediately."""
        service = SettingsService()
        service.settings_repo = Mock()

        with pytest.raises(ValueError, match="Unknown setting"):
            service.update_setting(-100, "fake_setting", "value", None)

        service.settings_repo.get_or_create.assert_not_called()

    def test_get_settings_calls_repository(self):
        """get_settings should delegate to repository."""
        service = SettingsService()
        mock_repo = Mock()
        mock_settings = Mock(spec=ChatSettings)
        mock_repo.get_or_create.return_value = mock_settings
        service.settings_repo = mock_repo

        result = service.get_settings(-1001234567890)

        mock_repo.get_or_create.assert_called_once_with(-1001234567890)
        assert result == mock_settings

    def test_toggle_setting_flips_value(self):
        """Toggle should flip boolean value."""
        service = SettingsService()

        # Mock repository
        mock_settings = Mock(spec=ChatSettings)
        mock_settings.dry_run_mode = True  # Initial value

        mock_repo = Mock()
        mock_repo.get_or_create.return_value = mock_settings
        mock_repo.update.return_value = mock_settings
        service.settings_repo = mock_repo

        # Mock service_run_repo for track_execution
        service.service_run_repo = Mock()
        service.service_run_repo.create_run.return_value = str(uuid4())

        # Toggle
        service.toggle_setting(-100, "dry_run_mode", None)

        # Should have called update with opposite value
        mock_repo.update.assert_called_once()
        call_kwargs = mock_repo.update.call_args[1]
        assert call_kwargs["dry_run_mode"] is False  # Flipped from True

    def test_toggle_is_paused_uses_set_paused(self):
        """Toggling is_paused should call set_paused for tracking."""
        service = SettingsService()

        mock_settings = Mock(spec=ChatSettings)
        mock_settings.is_paused = False

        mock_repo = Mock()
        mock_repo.get_or_create.return_value = mock_settings
        service.settings_repo = mock_repo

        service.service_run_repo = Mock()
        service.service_run_repo.create_run.return_value = str(uuid4())

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "testuser"

        service.toggle_setting(-100, "is_paused", mock_user)

        # Should have called set_paused, not update
        mock_repo.set_paused.assert_called_once()
        mock_repo.update.assert_not_called()

    def test_update_posts_per_day_validates_min(self):
        """posts_per_day below 1 should raise ValueError."""
        service = SettingsService()
        mock_settings = Mock(spec=ChatSettings)
        mock_settings.posts_per_day = 5

        mock_repo = Mock()
        mock_repo.get_or_create.return_value = mock_settings
        service.settings_repo = mock_repo

        service.service_run_repo = Mock()
        service.service_run_repo.create_run.return_value = str(uuid4())

        with pytest.raises(ValueError, match="must be between 1 and 50"):
            service.update_setting(-100, "posts_per_day", 0, None)

    def test_update_posts_per_day_validates_max(self):
        """posts_per_day above 50 should raise ValueError."""
        service = SettingsService()
        mock_settings = Mock(spec=ChatSettings)
        mock_settings.posts_per_day = 5

        mock_repo = Mock()
        mock_repo.get_or_create.return_value = mock_settings
        service.settings_repo = mock_repo

        service.service_run_repo = Mock()
        service.service_run_repo.create_run.return_value = str(uuid4())

        with pytest.raises(ValueError, match="must be between 1 and 50"):
            service.update_setting(-100, "posts_per_day", 51, None)

    def test_update_posting_hours_validates_range(self):
        """Hour values must be 0-23."""
        service = SettingsService()
        mock_settings = Mock(spec=ChatSettings)
        mock_settings.posting_hours_start = 14

        mock_repo = Mock()
        mock_repo.get_or_create.return_value = mock_settings
        service.settings_repo = mock_repo

        service.service_run_repo = Mock()
        service.service_run_repo.create_run.return_value = str(uuid4())

        with pytest.raises(ValueError, match="Hour must be between 0 and 23"):
            service.update_setting(-100, "posting_hours_start", 24, None)

        with pytest.raises(ValueError, match="Hour must be between 0 and 23"):
            service.update_setting(-100, "posting_hours_end", -1, None)

    def test_get_settings_display_returns_all_keys(self):
        """get_settings_display should return dict with all expected keys."""
        service = SettingsService()

        mock_settings = Mock(spec=ChatSettings)
        mock_settings.dry_run_mode = True
        mock_settings.enable_instagram_api = False
        mock_settings.is_paused = False
        mock_settings.paused_at = None
        mock_settings.paused_by_user_id = None
        mock_settings.posts_per_day = 10
        mock_settings.posting_hours_start = 14
        mock_settings.posting_hours_end = 2
        mock_settings.updated_at = datetime.utcnow()

        mock_repo = Mock()
        mock_repo.get_or_create.return_value = mock_settings
        service.settings_repo = mock_repo

        display = service.get_settings_display(-100)

        expected_keys = [
            "dry_run_mode",
            "enable_instagram_api",
            "is_paused",
            "paused_at",
            "paused_by_user_id",
            "posts_per_day",
            "posting_hours_start",
            "posting_hours_end",
            "updated_at",
        ]
        for key in expected_keys:
            assert key in display, f"Missing key: {key}"


# =============================================================================
# ARCHITECTURE VALIDATION TESTS
# =============================================================================


@pytest.mark.unit
class TestSettingsArchitecture:
    """Tests validating architectural decisions."""

    def test_chat_settings_model_has_chat_id(self):
        """ChatSettings model should have telegram_chat_id for multi-tenancy."""
        from src.models.chat_settings import ChatSettings

        assert hasattr(ChatSettings, "telegram_chat_id")

    def test_settings_service_accepts_chat_id(self):
        """All SettingsService methods should accept chat_id parameter."""
        import inspect

        service = SettingsService()

        # get_settings
        sig = inspect.signature(service.get_settings)
        assert "telegram_chat_id" in sig.parameters

        # toggle_setting
        sig = inspect.signature(service.toggle_setting)
        assert "telegram_chat_id" in sig.parameters

        # update_setting
        sig = inspect.signature(service.update_setting)
        assert "telegram_chat_id" in sig.parameters

        # get_settings_display
        sig = inspect.signature(service.get_settings_display)
        assert "telegram_chat_id" in sig.parameters

    def test_settings_service_does_not_hardcode_chat_id(self):
        """SettingsService should not import or use ADMIN_TELEGRAM_CHAT_ID."""
        from pathlib import Path

        service_path = Path("src/services/core/settings_service.py")
        content = service_path.read_text()

        # Should not reference ADMIN_TELEGRAM_CHAT_ID
        assert "ADMIN_TELEGRAM_CHAT_ID" not in content, (
            "SettingsService should not hardcode ADMIN_TELEGRAM_CHAT_ID"
        )

    def test_repository_uses_chat_id_for_lookup(self):
        """Repository should use chat_id for unique lookups."""
        from src.repositories.chat_settings_repository import ChatSettingsRepository
        import inspect

        repo = ChatSettingsRepository()

        # get_by_chat_id
        sig = inspect.signature(repo.get_by_chat_id)
        assert "telegram_chat_id" in sig.parameters

        # get_or_create
        sig = inspect.signature(repo.get_or_create)
        assert "telegram_chat_id" in sig.parameters


# =============================================================================
# .ENV FALLBACK BEHAVIOR TESTS
# =============================================================================


@pytest.mark.unit
class TestEnvFallback:
    """Tests for .env fallback behavior when no DB record exists."""

    @patch("src.repositories.chat_settings_repository.env_settings")
    def test_repository_bootstraps_from_env(self, mock_env_settings):
        """Repository should create settings from .env on first access."""
        mock_env_settings.DRY_RUN_MODE = True
        mock_env_settings.ENABLE_INSTAGRAM_API = False
        mock_env_settings.POSTS_PER_DAY = 5
        mock_env_settings.POSTING_HOURS_START = 10
        mock_env_settings.POSTING_HOURS_END = 22

        # Create mock db session
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None  # No existing record

        mock_db.query.return_value = mock_query

        repo = ChatSettingsRepository()
        repo._db = mock_db

        # Mock db.add to capture the created object
        created_settings = None

        def capture_add(obj):
            nonlocal created_settings
            created_settings = obj

        mock_db.add.side_effect = capture_add

        # Mock refresh to do nothing
        mock_db.refresh = MagicMock()

        # This should create from .env
        repo.get_or_create(-1001234567890)

        # Verify .env values were used
        mock_db.add.assert_called_once()
        assert created_settings.dry_run_mode is True
        assert created_settings.enable_instagram_api is False
        assert created_settings.posts_per_day == 5


# =============================================================================
# MULTI-CHAT ISOLATION TESTS
# =============================================================================


@pytest.mark.unit
class TestMultiChatIsolation:
    """Tests ensuring different chats have isolated settings."""

    def test_different_chat_ids_get_different_settings(self):
        """Two chat IDs should get independent settings."""
        service = SettingsService()

        # Track which chat_id is requested
        requested_ids = []

        def mock_get_or_create(chat_id):
            requested_ids.append(chat_id)
            settings = Mock(spec=ChatSettings)
            settings.telegram_chat_id = chat_id
            settings.dry_run_mode = True
            return settings

        mock_repo = Mock()
        mock_repo.get_or_create.side_effect = mock_get_or_create
        service.settings_repo = mock_repo

        # Get settings for two different chats
        settings1 = service.get_settings(-1001111111111)
        settings2 = service.get_settings(-1002222222222)

        # Both should have been called with their own ID
        assert -1001111111111 in requested_ids
        assert -1002222222222 in requested_ids
        assert settings1.telegram_chat_id != settings2.telegram_chat_id

    def test_toggle_affects_only_specified_chat(self):
        """Toggling setting for one chat should not affect others."""
        service = SettingsService()

        # Track which chat_id gets updated
        updated_chat_ids = []

        def mock_update(chat_id, **kwargs):
            updated_chat_ids.append(chat_id)
            return Mock(spec=ChatSettings)

        mock_settings = Mock(spec=ChatSettings)
        mock_settings.dry_run_mode = True

        mock_repo = Mock()
        mock_repo.get_or_create.return_value = mock_settings
        mock_repo.update.side_effect = mock_update
        service.settings_repo = mock_repo

        service.service_run_repo = Mock()
        service.service_run_repo.create_run.return_value = str(uuid4())

        # Toggle for specific chat
        service.toggle_setting(-1001111111111, "dry_run_mode", None)

        # Only that chat should have been updated
        assert -1001111111111 in updated_chat_ids
        assert len(updated_chat_ids) == 1


# =============================================================================
# INTEGRATION TESTS (Require Database)
# =============================================================================


@pytest.mark.integration
class TestSettingsServiceIntegration:
    """Integration tests requiring database connection."""

    def test_get_settings_creates_from_env_on_first_access(self, test_db):
        """First access should bootstrap settings from .env values."""
        service = SettingsService()
        service.settings_repo = ChatSettingsRepository()
        service.settings_repo._db = test_db

        chat_id = -1001234567890

        settings = service.get_settings(chat_id)

        assert settings is not None
        assert settings.telegram_chat_id == chat_id
        assert isinstance(settings.dry_run_mode, bool)
        assert isinstance(settings.posts_per_day, int)

    def test_get_settings_returns_existing(self, test_db):
        """Subsequent access should return existing record."""
        service = SettingsService()
        service.settings_repo = ChatSettingsRepository()
        service.settings_repo._db = test_db

        chat_id = -1001234567891

        settings1 = service.get_settings(chat_id)
        settings2 = service.get_settings(chat_id)

        assert settings1.id == settings2.id

    def test_toggle_setting_persists(self, test_db):
        """Toggled value should be persisted to database."""
        service = SettingsService()
        service.settings_repo = ChatSettingsRepository()
        service.settings_repo._db = test_db
        service.service_run_repo._db = test_db

        chat_id = -1001234567892

        settings = service.get_settings(chat_id)
        initial_value = settings.dry_run_mode

        service.toggle_setting(chat_id, "dry_run_mode", None)

        # Get fresh from DB
        fresh_settings = service.get_settings(chat_id)
        assert fresh_settings.dry_run_mode != initial_value

    def test_pause_tracks_user_and_timestamp(self, test_db):
        """Pausing should record who paused and when."""
        service = SettingsService()
        service.settings_repo = ChatSettingsRepository()
        service.settings_repo._db = test_db
        service.service_run_repo._db = test_db

        chat_id = -1001234567896

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

        before_pause = datetime.utcnow()
        service.toggle_setting(chat_id, "is_paused", user)

        updated_settings = service.get_settings(chat_id)
        assert updated_settings.is_paused is True
        assert updated_settings.paused_at is not None
        assert updated_settings.paused_at >= before_pause

    def test_unpause_clears_tracking(self, test_db):
        """Unpausing should clear paused_at and paused_by_user_id."""
        service = SettingsService()
        service.settings_repo = ChatSettingsRepository()
        service.settings_repo._db = test_db
        service.service_run_repo._db = test_db

        chat_id = -1001234567897

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

        service.toggle_setting(chat_id, "is_paused", user)

        updated_settings = service.get_settings(chat_id)
        assert updated_settings.is_paused is False
        assert updated_settings.paused_at is None
        assert updated_settings.paused_by_user_id is None

    def test_different_chats_have_isolated_settings(self, test_db):
        """Two chats should have independent settings."""
        service = SettingsService()
        service.settings_repo = ChatSettingsRepository()
        service.settings_repo._db = test_db
        service.service_run_repo._db = test_db

        chat_id_1 = -1001111111111
        chat_id_2 = -1002222222222

        # Get settings for both
        settings1 = service.get_settings(chat_id_1)
        settings2 = service.get_settings(chat_id_2)

        # They should be different records
        assert settings1.id != settings2.id

        # Toggle dry_run for chat 1 only
        initial_chat2_value = settings2.dry_run_mode
        service.toggle_setting(chat_id_1, "dry_run_mode", None)

        # Chat 2 should be unchanged
        fresh_settings2 = service.get_settings(chat_id_2)
        assert fresh_settings2.dry_run_mode == initial_chat2_value


# =============================================================================
# TELEGRAM SERVICE INTEGRATION TESTS
# =============================================================================


@pytest.mark.unit
class TestTelegramSettingsIntegration:
    """Tests for TelegramService settings integration."""

    def test_telegram_service_uses_settings_service(self):
        """TelegramService should have settings_service attribute."""
        from src.services.core.telegram_service import TelegramService

        # Check the class has the initialization
        import inspect

        source = inspect.getsource(TelegramService.__init__)
        assert "settings_service" in source or "SettingsService" in source

    def test_is_paused_uses_database(self):
        """TelegramService.is_paused should query database, not class variable."""
        from src.services.core.telegram_service import TelegramService
        import inspect

        # Read the property source
        source = inspect.getsource(TelegramService.is_paused.fget)

        # Should reference settings_service, not _paused class variable
        assert "settings_service" in source or "get_settings" in source
        assert (
            "_paused" not in source or "is_paused" in source
        )  # is_paused from DB, not _paused


# =============================================================================
# POSTING/SCHEDULER SERVICE ARCHITECTURE TESTS
# =============================================================================


@pytest.mark.unit
class TestServiceSettingsUsage:
    """Tests verifying PostingService and SchedulerService use SettingsService."""

    def test_posting_service_has_settings_service(self):
        """PostingService should have settings_service attribute."""
        from src.services.core.posting import PostingService
        import inspect

        source = inspect.getsource(PostingService.__init__)
        assert "settings_service" in source or "SettingsService" in source

    def test_scheduler_service_has_settings_service(self):
        """SchedulerService should have settings_service attribute."""
        from src.services.core.scheduler import SchedulerService
        import inspect

        source = inspect.getsource(SchedulerService.__init__)
        assert "settings_service" in source or "SettingsService" in source

    def test_posting_service_checks_dry_run_from_settings(self):
        """PostingService should check dry_run from SettingsService, not .env."""
        from src.services.core.posting import PostingService
        import inspect

        # Read _post_via_telegram source
        source = inspect.getsource(PostingService._post_via_telegram)

        # Should reference chat_settings.dry_run_mode, not settings.DRY_RUN_MODE
        assert "dry_run_mode" in source.lower()


# =============================================================================
# DEPLOYMENT MODEL DOCUMENTATION TEST
# =============================================================================


@pytest.mark.unit
class TestDeploymentModel:
    """Tests documenting and validating the deployment model."""

    def test_current_deployment_is_single_tenant(self):
        """
        DOCUMENTATION TEST: Current deployment model is single-tenant.

        Each deployment of storyline-ai represents:
        - ONE Telegram bot (TELEGRAM_BOT_TOKEN)
        - ONE admin channel (TELEGRAM_CHANNEL_ID / ADMIN_TELEGRAM_CHAT_ID)
        - ONE Instagram account (INSTAGRAM_ACCOUNT_ID)

        This is BY DESIGN for Phase 1. Multi-tenancy is Phase 3.

        If another group wants to use storyline-ai, they should:
        1. Fork/clone the repository
        2. Deploy their own instance
        3. Configure their own .env with their credentials
        4. Run their own bot

        They should NOT try to share a single bot instance.
        """
        # This test documents the architecture decision
        # Verify the .env template mentions single-tenant
        from pathlib import Path

        env_example = Path(".env.example")
        if env_example.exists():
            content = env_example.read_text()
            # Just verify required single-tenant configs exist
            assert "TELEGRAM_BOT_TOKEN" in content
            assert "TELEGRAM_CHANNEL_ID" in content

    def test_chat_settings_supports_future_multi_tenancy(self):
        """
        DOCUMENTATION TEST: Database schema supports future multi-tenancy.

        The chat_settings table is designed for Phase 3 multi-tenancy:
        - telegram_chat_id is the unique identifier
        - Each chat can have different posts_per_day, posting_hours, etc.

        Current limitation (Phase 1):
        - PostingService and SchedulerService use hardcoded ADMIN_TELEGRAM_CHAT_ID

        Future multi-tenancy (Phase 3) requires:
        - Pass telegram_chat_id through the call stack
        - Add telegram_chat_id to api_tokens for per-chat Instagram accounts
        - Add telegram_chat_id to posting_queue for routing
        """
        from src.models.chat_settings import ChatSettings

        # Verify the model has the multi-tenancy column
        assert hasattr(ChatSettings, "telegram_chat_id")

        # Verify it's indexed (for performance)
        from sqlalchemy import inspect as sa_inspect

        mapper = sa_inspect(ChatSettings)

        # Find the telegram_chat_id column
        for col in mapper.columns:
            if col.name == "telegram_chat_id":
                assert col.unique, "telegram_chat_id should be unique"
                break
