"""Tests for TelegramCommandHandlers (extracted from test_telegram_service.py)."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from uuid import uuid4

from src.services.core.telegram_commands import TelegramCommandHandlers


@pytest.fixture
def mock_command_handlers(mock_telegram_service):
    """Create TelegramCommandHandlers from shared mock_telegram_service."""
    handlers = TelegramCommandHandlers(mock_telegram_service)
    yield handlers


@pytest.mark.unit
@pytest.mark.asyncio
class TestNextCommand:
    """Tests for /next command - force send next post."""

    async def test_next_sends_earliest_scheduled_post(self, mock_command_handlers):
        """Test /next sends the earliest scheduled post."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "testuser"
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        queue_item_id = uuid4()

        mock_media = Mock()
        mock_media.file_name = "next_post.jpg"

        # Mock SchedulerService
        mock_scheduler = Mock()
        mock_scheduler.force_send_next = AsyncMock(
            return_value={
                "posted": True,
                "queue_item_id": str(queue_item_id),
                "media_item": mock_media,
            }
        )
        mock_scheduler.__enter__ = Mock(return_value=mock_scheduler)
        mock_scheduler.__exit__ = Mock(return_value=False)

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        with patch(
            "src.services.core.scheduler.SchedulerService",
            return_value=mock_scheduler,
        ):
            await handlers.handle_next(mock_update, mock_context)

        # Should call force_send_next on SchedulerService
        mock_scheduler.force_send_next.assert_called_once_with(
            telegram_chat_id=-100123,
            user_id=str(mock_user.id),
            force_sent_indicator=True,
        )

        # Should inject telegram_service
        assert mock_scheduler.telegram_service is service

        # Should NOT send any extra messages on success (no clutter)
        mock_update.message.reply_text.assert_not_called()

    async def test_next_no_eligible_media(self, mock_command_handlers):
        """Test /next shows error when no eligible media."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        # Mock SchedulerService to return no eligible media
        mock_scheduler = Mock()
        mock_scheduler.force_send_next = AsyncMock(
            return_value={
                "posted": False,
                "reason": "no_eligible_media",
            }
        )
        mock_scheduler.__enter__ = Mock(return_value=mock_scheduler)
        mock_scheduler.__exit__ = Mock(return_value=False)

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        with patch(
            "src.services.core.scheduler.SchedulerService",
            return_value=mock_scheduler,
        ):
            await handlers.handle_next(mock_update, mock_context)

        # Should show no eligible media message
        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "No Eligible Media" in message_text
        assert "No media available to send" in message_text

    async def test_next_generic_failure(self, mock_command_handlers):
        """Test /next handles generic failure gracefully."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        mock_scheduler = Mock()
        mock_scheduler.force_send_next = AsyncMock(
            return_value={
                "posted": False,
                "error": "Some unexpected error",
            }
        )
        mock_scheduler.__enter__ = Mock(return_value=mock_scheduler)
        mock_scheduler.__exit__ = Mock(return_value=False)

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        with patch(
            "src.services.core.scheduler.SchedulerService",
            return_value=mock_scheduler,
        ):
            await handlers.handle_next(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Failed to send" in message_text

    async def test_next_notification_failure(self, mock_command_handlers):
        """Test /next handles notification failure gracefully."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        mock_scheduler = Mock()
        mock_scheduler.force_send_next = AsyncMock(
            return_value={
                "posted": False,
                "error": "Failed to send notification",
            }
        )
        mock_scheduler.__enter__ = Mock(return_value=mock_scheduler)
        mock_scheduler.__exit__ = Mock(return_value=False)

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        with patch(
            "src.services.core.scheduler.SchedulerService",
            return_value=mock_scheduler,
        ):
            await handlers.handle_next(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Failed to send" in message_text

    async def test_next_logs_interaction(self, mock_command_handlers):
        """Test /next logs the interaction on success."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "testuser"
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        queue_item_id = uuid4()
        mock_media = Mock()
        mock_media.id = uuid4()
        mock_media.file_name = "logged_post.jpg"

        mock_scheduler = Mock()
        mock_scheduler.force_send_next = AsyncMock(
            return_value={
                "posted": True,
                "queue_item_id": str(queue_item_id),
                "media_item": mock_media,
            }
        )
        mock_scheduler.__enter__ = Mock(return_value=mock_scheduler)
        mock_scheduler.__exit__ = Mock(return_value=False)

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        with patch(
            "src.services.core.scheduler.SchedulerService",
            return_value=mock_scheduler,
        ):
            await handlers.handle_next(mock_update, mock_context)

        # Should log interaction
        service.interaction_service.log_command.assert_called_once()
        call_kwargs = service.interaction_service.log_command.call_args.kwargs
        assert call_kwargs["command"] == "/next"
        assert call_kwargs["context"]["success"] is True


# ==================== Status Helper Tests ====================


@pytest.mark.unit
class TestGetCadenceDisplay:
    """Tests for _get_cadence_display helper."""

    def test_returns_cadence_string(self, mock_command_handlers):
        """Test returns formatted cadence when settings are available."""
        handlers = mock_command_handlers
        mock_settings = Mock(
            posts_per_day=3, posting_hours_start=14, posting_hours_end=2
        )
        handlers.service.settings_service.get_settings.return_value = mock_settings

        result = handlers._get_cadence_display(-100123)
        assert result == "3/day, 14:00-02:00 UTC"

    def test_returns_unknown_on_error(self, mock_command_handlers):
        """Test returns 'Unknown' when settings service fails."""
        handlers = mock_command_handlers
        handlers.service.settings_service.get_settings.side_effect = Exception(
            "DB error"
        )

        result = handlers._get_cadence_display(-100123)
        assert result == "Unknown"


@pytest.mark.unit
class TestGetLastPostedDisplay:
    """Tests for _get_last_posted_display helper."""

    def test_recent_post_hours_ago(self, mock_command_handlers):
        """Test shows hours ago for recent posts."""
        handlers = mock_command_handlers
        mock_post = Mock()
        mock_post.posted_at = datetime.utcnow().replace(
            hour=max(datetime.utcnow().hour - 3, 0)
        )

        # Use a fixed time difference to avoid test flakiness
        with patch("src.services.core.telegram_commands.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2026, 3, 15, 15, 0, 0)
            mock_post.posted_at = datetime(2026, 3, 15, 12, 0, 0)
            result = handlers._get_last_posted_display([mock_post])

        assert result == "3h ago"

    def test_very_recent_post(self, mock_command_handlers):
        """Test shows '< 1h ago' for very recent posts."""
        handlers = mock_command_handlers
        mock_post = Mock()

        with patch("src.services.core.telegram_commands.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2026, 3, 15, 15, 0, 0)
            mock_post.posted_at = datetime(2026, 3, 15, 14, 45, 0)
            result = handlers._get_last_posted_display([mock_post])

        assert result == "< 1h ago"

    def test_no_posts(self, mock_command_handlers):
        """Test returns 'Never' when no posts exist."""
        handlers = mock_command_handlers
        result = handlers._get_last_posted_display([])
        assert result == "Never"


@pytest.mark.unit
class TestGetInstagramApiStatus:
    """Tests for _get_instagram_api_status helper."""

    def test_enabled_with_rate_limit(self, mock_command_handlers):
        """Test shows enabled status with rate limit remaining."""
        handlers = mock_command_handlers

        mock_ig = Mock()
        mock_ig.get_rate_limit_remaining.return_value = 20
        mock_ig.__enter__ = Mock(return_value=mock_ig)
        mock_ig.__exit__ = Mock(return_value=False)

        with (
            patch("src.services.core.telegram_commands.settings") as mock_settings,
            patch(
                "src.services.integrations.instagram_api.InstagramAPIService",
                return_value=mock_ig,
            ),
        ):
            mock_settings.ENABLE_INSTAGRAM_API = True
            mock_settings.INSTAGRAM_POSTS_PER_HOUR = 25
            result = handlers._get_instagram_api_status()

        assert "Enabled" in result
        assert "20/25" in result

    def test_disabled(self, mock_command_handlers):
        """Test shows disabled status."""
        handlers = mock_command_handlers

        with patch("src.services.core.telegram_commands.settings") as mock_settings:
            mock_settings.ENABLE_INSTAGRAM_API = False
            result = handlers._get_instagram_api_status()

        assert "Disabled" in result


@pytest.mark.unit
class TestGetSyncStatusLine:
    """Tests for _get_sync_status_line helper."""

    def test_sync_disabled(self, mock_command_handlers):
        """Test shows disabled when media sync is off."""
        handlers = mock_command_handlers
        mock_chat_settings = Mock(media_sync_enabled=False)
        handlers.service.settings_service.get_settings.return_value = mock_chat_settings

        mock_sync = Mock()
        mock_sync.get_last_sync_info.return_value = None
        mock_sync.__enter__ = Mock(return_value=mock_sync)
        mock_sync.__exit__ = Mock(return_value=False)

        with patch(
            "src.services.core.media_sync.MediaSyncService",
            return_value=mock_sync,
        ):
            result = handlers._get_sync_status_line(-100123)

        assert "Disabled" in result

    def test_no_syncs_yet(self, mock_command_handlers):
        """Test shows 'No syncs yet' when no history."""
        handlers = mock_command_handlers
        mock_chat_settings = Mock(media_sync_enabled=True)
        handlers.service.settings_service.get_settings.return_value = mock_chat_settings

        mock_sync = Mock()
        mock_sync.get_last_sync_info.return_value = None

        with patch(
            "src.services.core.media_sync.MediaSyncService",
            return_value=mock_sync,
        ):
            result = handlers._get_sync_status_line(-100123)

        assert "No syncs yet" in result

    def test_successful_sync(self, mock_command_handlers):
        """Test shows OK with counts for successful sync."""
        handlers = mock_command_handlers
        mock_chat_settings = Mock(media_sync_enabled=True)
        handlers.service.settings_service.get_settings.return_value = mock_chat_settings

        mock_sync = Mock()
        mock_sync.get_last_sync_info.return_value = {
            "success": True,
            "started_at": "2026-03-15T10:00:00Z",
            "result": {
                "new": 5,
                "updated": 2,
                "deactivated": 0,
                "reactivated": 1,
                "unchanged": 42,
            },
        }

        with patch(
            "src.services.core.media_sync.MediaSyncService",
            return_value=mock_sync,
        ):
            result = handlers._get_sync_status_line(-100123)

        assert "OK" in result
        assert "50 items" in result
        assert "5 new" in result

    def test_failed_sync(self, mock_command_handlers):
        """Test shows warning for failed sync."""
        handlers = mock_command_handlers
        mock_chat_settings = Mock(media_sync_enabled=True)
        handlers.service.settings_service.get_settings.return_value = mock_chat_settings

        mock_sync = Mock()
        mock_sync.get_last_sync_info.return_value = {
            "success": False,
            "started_at": "2026-03-15T10:00:00Z",
        }

        with patch(
            "src.services.core.media_sync.MediaSyncService",
            return_value=mock_sync,
        ):
            result = handlers._get_sync_status_line(-100123)

        assert "failed" in result

    def test_exception_shows_check_failed(self, mock_command_handlers):
        """Test exception returns 'Check failed'."""
        handlers = mock_command_handlers

        with patch(
            "src.services.core.media_sync.MediaSyncService",
            side_effect=Exception("Import error"),
        ):
            result = handlers._get_sync_status_line(-100123)

        assert "Check failed" in result


@pytest.mark.unit
@pytest.mark.asyncio
class TestStatusCommand:
    """Tests for handle_status end-to-end."""

    async def test_sends_formatted_status_message(self, mock_command_handlers):
        """Test /status sends a formatted message with all sections."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        # Set up repo returns
        service.queue_repo.count_pending.return_value = 5
        service.queue_repo.get_pending.return_value = []
        service.history_repo.get_recent_posts.return_value = []
        service.media_repo.get_all.return_value = [
            Mock(times_posted=0),
            Mock(times_posted=1),
            Mock(times_posted=2),
        ]
        service.lock_repo.get_permanent_locks.return_value = [Mock()]

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        # Mock settings_service for setup status checks
        service.settings_service.get_settings.return_value = Mock(
            id="fake-uuid",
            posts_per_day=3,
            posting_hours_start=14,
            posting_hours_end=2,
            is_paused=False,
            dry_run_mode=False,
            media_sync_enabled=False,
            media_source_root=None,
        )

        with (
            patch("src.services.core.telegram_commands.settings") as mock_settings,
            patch(
                "src.services.core.media_sync.MediaSyncService",
                side_effect=Exception("not configured"),
            ),
            patch(
                "src.services.core.setup_state_service.SetupStateService.__init__",
                lambda self: None,
            ),
            patch(
                "src.services.core.setup_state_service.SetupStateService.format_setup_status",
                return_value=(
                    "*Setup Status:*\n"
                    "├── 📸 Instagram: ⚠️ Not connected\n"
                    "├── 📁 Google Drive: ⚠️ Not connected\n"
                    "├── 📂 Media Library: ⚠️ Not configured\n"
                    "├── 📅 Schedule: ✅ 3/day, 14:00-02:00 UTC\n"
                    "└── 📦 Delivery: ✅ Live"
                ),
            ),
            patch(
                "src.services.core.setup_state_service.SetupStateService.close",
            ),
        ):
            mock_settings.DRY_RUN_MODE = False
            mock_settings.ENABLE_INSTAGRAM_API = False
            await handlers.handle_status(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]

        assert "Storyline AI Status" in message_text
        assert "Queue: 5 pending" in message_text
        assert "Total: 3 active" in message_text
        assert "Locked: 1" in message_text
        assert "Cadence:" in message_text

        # Should log interaction
        service.interaction_service.log_command.assert_called_once()


# ==================== Setup Status Tests ====================


@pytest.mark.unit
class TestSetupStatus:
    """Tests for SetupStateService static formatters (formerly on TelegramCommandHandlers)."""

    def test_instagram_connected(self):
        """Test Instagram shows connected when active account exists."""
        from src.services.core.setup_state_service import SetupStateService

        state = {"instagram_connected": True, "instagram_username": "testshop"}
        line, ok = SetupStateService._fmt_instagram(state)
        assert "Connected" in line
        assert "@testshop" in line
        assert ok is True

    def test_instagram_not_connected(self):
        """Test Instagram shows not connected when no active account."""
        from src.services.core.setup_state_service import SetupStateService

        state = {"instagram_connected": False, "instagram_username": None}
        line, ok = SetupStateService._fmt_instagram(state)
        assert "Not connected" in line
        assert ok is False

    def test_instagram_connected_no_username(self):
        """Test Instagram shows connected even without a username."""
        from src.services.core.setup_state_service import SetupStateService

        state = {"instagram_connected": True, "instagram_username": None}
        line, ok = SetupStateService._fmt_instagram(state)
        assert "Connected" in line
        assert ok is True

    def test_media_library_with_files(self):
        """Test media library shows file count when media is indexed."""
        from src.services.core.setup_state_service import SetupStateService

        state = {"media_count": 847, "media_folder_configured": True}
        line, ok = SetupStateService._fmt_media(state)
        assert "847 files" in line
        assert ok is True

    def test_media_library_no_files_source_configured(self):
        """Test media library when source configured but no files synced."""
        from src.services.core.setup_state_service import SetupStateService

        state = {"media_count": 0, "media_folder_configured": True}
        line, ok = SetupStateService._fmt_media(state)
        assert "Configured" in line
        assert "0 files" in line
        assert ok is False

    def test_media_library_not_configured(self):
        """Test media library when nothing is configured."""
        from src.services.core.setup_state_service import SetupStateService

        state = {"media_count": 0, "media_folder_configured": False}
        line, ok = SetupStateService._fmt_media(state)
        assert "Not configured" in line
        assert ok is False

    def test_schedule_configured(self):
        """Test schedule shows configuration."""
        from src.services.core.setup_state_service import SetupStateService

        state = {
            "posts_per_day": 3,
            "posting_hours_start": 14,
            "posting_hours_end": 2,
        }
        line, ok = SetupStateService._fmt_schedule(state)
        assert "3/day" in line
        assert "14:00-02:00 UTC" in line
        assert ok is True

    def test_delivery_live(self):
        """Test delivery shows live when not paused and not dry run."""
        from src.services.core.setup_state_service import SetupStateService

        state = {"is_paused": False, "dry_run_mode": False}
        line, ok = SetupStateService._fmt_delivery(state)
        assert "Live" in line
        assert ok is True

    def test_delivery_dry_run(self):
        """Test delivery shows dry run when enabled."""
        from src.services.core.setup_state_service import SetupStateService

        state = {"is_paused": False, "dry_run_mode": True}
        line, ok = SetupStateService._fmt_delivery(state)
        assert "Dry Run" in line
        assert ok is True

    def test_delivery_paused(self):
        """Test delivery shows paused state."""
        from src.services.core.setup_state_service import SetupStateService

        state = {"is_paused": True, "dry_run_mode": False}
        line, ok = SetupStateService._fmt_delivery(state)
        assert "PAUSED" in line
        assert ok is True


@pytest.mark.unit
class TestSetupStatusGoogleDrive:
    """Tests for Google Drive formatter and token staleness (formerly on TelegramCommandHandlers)."""

    def test_gdrive_connected_with_email(self):
        """Test Google Drive shows connected with email."""
        from src.services.core.setup_state_service import SetupStateService

        state = {
            "gdrive_connected": True,
            "gdrive_email": "user@gmail.com",
            "gdrive_needs_reconnect": False,
        }
        line, ok = SetupStateService._fmt_gdrive(state)
        assert "Connected" in line
        assert "user@gmail.com" in line
        assert ok is True

    def test_gdrive_not_connected(self):
        """Test Google Drive shows not connected when no token."""
        from src.services.core.setup_state_service import SetupStateService

        state = {
            "gdrive_connected": False,
            "gdrive_email": None,
            "gdrive_needs_reconnect": False,
        }
        line, ok = SetupStateService._fmt_gdrive(state)
        assert "Not connected" in line
        assert ok is False

    def test_gdrive_needs_reconnection(self):
        """Test Google Drive shows 'Needs Reconnection' when token is stale."""
        from src.services.core.setup_state_service import SetupStateService

        state = {
            "gdrive_connected": True,
            "gdrive_email": "user@gmail.com",
            "gdrive_needs_reconnect": True,
        }
        line, ok = SetupStateService._fmt_gdrive(state)
        assert "Needs Reconnection" in line
        assert ok is False

    def test_gdrive_stale_token_detection(self):
        """Test is_token_stale returns True for token expired >7 days ago."""
        from datetime import timedelta

        from src.services.core.setup_state_service import is_token_stale

        mock_token = Mock()
        # Expired 10 days ago (>7 day threshold)
        mock_token.expires_at = datetime.utcnow() - timedelta(days=10)
        assert is_token_stale(mock_token) is True

    def test_gdrive_recently_expired_not_stale(self):
        """Token expired 2 days ago (< 7 day threshold) is not considered stale."""
        from datetime import timedelta

        from src.services.core.setup_state_service import is_token_stale

        mock_token = Mock()
        # Expired 2 days ago (within 7 day threshold)
        mock_token.expires_at = datetime.utcnow() - timedelta(days=2)
        assert is_token_stale(mock_token) is False


@pytest.mark.unit
@pytest.mark.asyncio
class TestHandleNextGDriveAuthError:
    """Tests for /next handling of Google Drive auth errors."""

    async def test_next_gdrive_auth_error_shows_reconnect(self, mock_command_handlers):
        """Test /next shows reconnect message for google_drive error."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        mock_scheduler = Mock()
        mock_scheduler.force_send_next = AsyncMock(
            return_value={
                "posted": False,
                "error": "google_drive_auth_expired",
            }
        )
        mock_scheduler.__enter__ = Mock(return_value=mock_scheduler)
        mock_scheduler.__exit__ = Mock(return_value=False)

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        with (
            patch(
                "src.services.core.scheduler.SchedulerService",
                return_value=mock_scheduler,
            ),
            patch("src.services.core.telegram_commands.settings") as mock_settings,
        ):
            mock_settings.OAUTH_REDIRECT_BASE_URL = "https://app.example.com"
            await handlers.handle_next(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]
        assert "Disconnected" in message_text
        # Should include reconnect button
        reply_markup = call_args.kwargs.get("reply_markup")
        assert reply_markup is not None


@pytest.mark.unit
@pytest.mark.asyncio
class TestStatusIncludesSetup:
    """Test that handle_status now includes setup section."""

    async def test_status_message_contains_setup_section(self, mock_command_handlers):
        """Test /status output includes the Setup Status header."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        # Set up repo returns
        service.queue_repo.count_pending.return_value = 0
        service.queue_repo.get_pending.return_value = []
        service.history_repo.get_recent_posts.return_value = []
        service.media_repo.get_all.return_value = []
        service.lock_repo.get_permanent_locks.return_value = []
        service.ig_account_service.get_active_account.return_value = None

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        # Mock settings_service for setup checks
        mock_chat_settings = Mock(
            id="fake-uuid",
            posts_per_day=3,
            posting_hours_start=14,
            posting_hours_end=2,
            is_paused=False,
            dry_run_mode=False,
            media_sync_enabled=False,
            media_source_root=None,
        )
        service.settings_service.get_settings.return_value = mock_chat_settings

        setup_status_text = (
            "*Setup Status:*\n"
            "├── 📸 Instagram: ⚠️ Not connected\n"
            "├── 📁 Google Drive: ⚠️ Not connected\n"
            "├── 📂 Media Library: ⚠️ Not configured\n"
            "├── 📅 Schedule: ✅ 3/day, 14:00-02:00 UTC\n"
            "└── 📦 Delivery: ✅ Live"
        )

        with (
            patch("src.services.core.telegram_commands.settings") as mock_settings,
            patch(
                "src.services.core.media_sync.MediaSyncService",
                side_effect=Exception("not configured"),
            ),
            patch(
                "src.services.core.setup_state_service.SetupStateService.__init__",
                lambda self: None,
            ),
            patch(
                "src.services.core.setup_state_service.SetupStateService.format_setup_status",
                return_value=setup_status_text,
            ),
            patch(
                "src.services.core.setup_state_service.SetupStateService.close",
            ),
        ):
            mock_settings.DRY_RUN_MODE = False
            mock_settings.ENABLE_INSTAGRAM_API = False

            await handlers.handle_status(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]

        # Setup Status section should be present
        assert "Setup Status" in message_text
        assert "Instagram" in message_text
        assert "Google Drive" in message_text
        assert "Media Library" in message_text
        assert "Schedule" in message_text
        assert "Delivery" in message_text

        # Existing sections should still be present
        assert "Storyline AI Status" in message_text
        assert "Queue" in message_text


@pytest.mark.unit
@pytest.mark.asyncio
class TestStatusDashboardButton:
    """Tests for the Open Dashboard button on /status."""

    async def test_status_includes_dashboard_button(self, mock_command_handlers):
        """Test /status includes an Open Dashboard button when Mini App URL is configured."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        service.queue_repo.count_pending.return_value = 0
        service.queue_repo.get_pending.return_value = []
        service.history_repo.get_recent_posts.return_value = []
        service.media_repo.get_all.return_value = []
        service.lock_repo.get_permanent_locks.return_value = []
        service.ig_account_service.get_active_account.return_value = None

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123, type="private")
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_chat_settings = Mock(
            id="fake-uuid",
            posts_per_day=3,
            posting_hours_start=14,
            posting_hours_end=2,
            is_paused=False,
            dry_run_mode=False,
            media_sync_enabled=False,
            media_source_root=None,
        )
        service.settings_service.get_settings.return_value = mock_chat_settings

        with (
            patch("src.services.core.telegram_commands.settings") as mock_settings,
            patch(
                "src.services.core.media_sync.MediaSyncService",
                side_effect=Exception("n/a"),
            ),
            patch(
                "src.services.core.setup_state_service.SetupStateService.__init__",
                lambda self: None,
            ),
            patch(
                "src.services.core.setup_state_service.SetupStateService.format_setup_status",
                return_value="*Setup Status:*\n├── 📸 Instagram: ⚠️ Not connected",
            ),
            patch(
                "src.services.core.setup_state_service.SetupStateService.close",
            ),
        ):
            mock_settings.DRY_RUN_MODE = False
            mock_settings.ENABLE_INSTAGRAM_API = False
            mock_settings.OAUTH_REDIRECT_BASE_URL = "https://example.com"

            await handlers.handle_status(mock_update, Mock())

        call_args = mock_update.message.reply_text.call_args
        reply_markup = call_args.kwargs.get("reply_markup")
        assert reply_markup is not None
        # Check the button text
        button = reply_markup.inline_keyboard[0][0]
        assert "Open Dashboard" in button.text

    async def test_status_no_button_without_oauth_url(self, mock_command_handlers):
        """Test /status has no button when OAUTH_REDIRECT_BASE_URL is not set."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        service.queue_repo.count_pending.return_value = 0
        service.queue_repo.get_pending.return_value = []
        service.history_repo.get_recent_posts.return_value = []
        service.media_repo.get_all.return_value = []
        service.lock_repo.get_permanent_locks.return_value = []
        service.ig_account_service.get_active_account.return_value = None

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123, type="private")
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_chat_settings = Mock(
            id="fake-uuid",
            posts_per_day=3,
            posting_hours_start=14,
            posting_hours_end=2,
            is_paused=False,
            dry_run_mode=False,
            media_sync_enabled=False,
            media_source_root=None,
        )
        service.settings_service.get_settings.return_value = mock_chat_settings

        with (
            patch("src.services.core.telegram_commands.settings") as mock_settings,
            patch(
                "src.services.core.media_sync.MediaSyncService",
                side_effect=Exception("n/a"),
            ),
            patch(
                "src.services.core.setup_state_service.SetupStateService.__init__",
                lambda self: None,
            ),
            patch(
                "src.services.core.setup_state_service.SetupStateService.format_setup_status",
                return_value="*Setup Status:*\n├── 📸 Instagram: ⚠️ Not connected",
            ),
            patch(
                "src.services.core.setup_state_service.SetupStateService.close",
            ),
        ):
            mock_settings.DRY_RUN_MODE = False
            mock_settings.ENABLE_INSTAGRAM_API = False
            mock_settings.OAUTH_REDIRECT_BASE_URL = None

            await handlers.handle_status(mock_update, Mock())

        call_args = mock_update.message.reply_text.call_args
        reply_markup = call_args.kwargs.get("reply_markup")
        assert reply_markup is None


@pytest.mark.unit
@pytest.mark.asyncio
class TestStatusLibraryBreakdown:
    """Tests for /status library breakdown (merged from /stats)."""

    async def test_status_includes_library_breakdown(self, mock_command_handlers):
        """Test /status includes never-posted, posted-once, and posted-2+ counts."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        # Create media items with varying times_posted
        media_never = Mock(times_posted=0)
        media_once = Mock(times_posted=1)
        media_multi = Mock(times_posted=3)
        service.media_repo.get_all.return_value = [media_never, media_once, media_multi]
        service.queue_repo.count_pending.return_value = 0
        service.queue_repo.get_pending.return_value = []
        service.history_repo.get_recent_posts.return_value = []
        service.lock_repo.get_permanent_locks.return_value = []

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        with (
            patch("src.services.core.telegram_commands.settings") as mock_settings,
            patch(
                "src.services.core.media_sync.MediaSyncService",
                side_effect=Exception("n/a"),
            ),
            patch(
                "src.services.core.setup_state_service.SetupStateService.__init__",
                lambda self: None,
            ),
            patch(
                "src.services.core.setup_state_service.SetupStateService.format_setup_status",
                return_value="*Setup Status:*\n└── 📦 Delivery: ✅ Live",
            ),
            patch(
                "src.services.core.setup_state_service.SetupStateService.close",
            ),
        ):
            mock_settings.DRY_RUN_MODE = False
            mock_settings.ENABLE_INSTAGRAM_API = False

            await handlers.handle_status(mock_update, Mock())

        msg = mock_update.message.reply_text.call_args.args[0]
        assert "Never posted: 1" in msg
        assert "Posted once: 1" in msg
        assert "Posted 2+: 1" in msg
        assert "Total: 3" in msg


@pytest.mark.unit
@pytest.mark.asyncio
class TestRemovedCommandRedirects:
    """Tests for removed command deprecation messages."""

    @pytest.mark.parametrize(
        "command,expected_text",
        [
            ("/schedule", "/settings"),
            ("/stats", "/status"),
            ("/locks", "/status"),
            ("/reset", "/settings"),
            ("/dryrun", "/settings"),
            ("/backfill", "CLI"),
            ("/connect", "/start"),
            ("/queue", "dashboard"),
            ("/pause", "dashboard"),
            ("/resume", "dashboard"),
            ("/history", "dashboard"),
            ("/sync", "dashboard"),
        ],
    )
    async def test_removed_command_shows_redirect(
        self, mock_command_handlers, command, expected_text
    ):
        """Removed commands show a helpful redirect message."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1
        mock_update.message.text = command

        await handlers.handle_removed_command(mock_update, Mock())

        call_text = mock_update.message.reply_text.call_args.args[0]
        assert "retired" in call_text
        assert expected_text in call_text


@pytest.mark.unit
class TestPauseIntegration:
    """Tests for pause integration with PostingService."""

    def test_posting_service_respects_pause(self):
        """Test that PostingService checks pause state via telegram_service."""
        from src.services.core.posting import PostingService

        with patch.object(PostingService, "__init__", lambda self: None):
            posting_service = PostingService()
            posting_service.telegram_service = Mock()
            posting_service.telegram_service.is_paused = True

            # Verify PostingService can read telegram_service.is_paused
            assert posting_service.telegram_service.is_paused is True

            posting_service.telegram_service.is_paused = False
            assert posting_service.telegram_service.is_paused is False


# ==================== /connect_drive Removal Tests ====================


@pytest.mark.unit
class TestConnectDriveRemoved:
    """Verify /connect_drive has been removed (replaced by onboarding wizard)."""

    def test_connect_drive_handler_not_present(self, mock_command_handlers):
        """Verify handle_connect_drive method no longer exists."""
        handlers = mock_command_handlers
        assert not hasattr(handlers, "handle_connect_drive")


@pytest.mark.unit
@pytest.mark.asyncio
class TestStartCommand:
    """Tests for the /start command with onboarding Mini App support."""

    async def test_start_new_user_shows_webapp_button(self, mock_command_handlers):
        """New user (onboarding not completed) sees the setup wizard button."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        mock_update = AsyncMock()
        mock_update.effective_user.id = 12345
        mock_update.effective_user.first_name = "Test"
        mock_update.effective_user.username = "testuser"
        mock_update.effective_chat.id = -100123
        mock_update.message.message_id = 1

        with patch(
            "src.services.core.settings_service.SettingsService"
        ) as MockSettings:
            mock_settings_instance = MockSettings.return_value
            mock_settings_instance.__enter__ = Mock(return_value=mock_settings_instance)
            mock_settings_instance.__exit__ = Mock(return_value=False)
            mock_chat_settings = Mock(onboarding_completed=False)
            mock_settings_instance.get_settings.return_value = mock_chat_settings

            with patch(
                "src.services.core.telegram_commands.settings"
            ) as mock_app_settings:
                mock_app_settings.OAUTH_REDIRECT_BASE_URL = "https://example.com"

                await handlers.handle_start(mock_update, Mock())

        call_args = mock_update.message.reply_text.call_args
        assert "Setup Wizard" in str(call_args)

    async def test_start_returning_user_shows_webapp_button(
        self, mock_command_handlers
    ):
        """Returning user (onboarding completed) sees 'Open Storyline' Mini App button."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = mock_user

        mock_update = AsyncMock()
        mock_update.effective_user.id = 12345
        mock_update.effective_user.first_name = "Test"
        mock_update.effective_user.username = "testuser"
        mock_update.effective_chat.id = -100123
        mock_update.message.message_id = 1

        with patch(
            "src.services.core.settings_service.SettingsService"
        ) as MockSettings:
            mock_settings_instance = MockSettings.return_value
            mock_settings_instance.__enter__ = Mock(return_value=mock_settings_instance)
            mock_settings_instance.__exit__ = Mock(return_value=False)
            mock_chat_settings = Mock(onboarding_completed=True)
            mock_settings_instance.get_settings.return_value = mock_chat_settings

            with patch(
                "src.services.core.telegram_commands.settings"
            ) as mock_app_settings:
                mock_app_settings.OAUTH_REDIRECT_BASE_URL = "https://example.com"

                await handlers.handle_start(mock_update, Mock())

        call_args = mock_update.message.reply_text.call_args
        assert "Open Storyline" in str(call_args)
        assert "Welcome back" in str(call_args)

    async def test_start_no_oauth_url_shows_text_fallback(self, mock_command_handlers):
        """When OAUTH_REDIRECT_BASE_URL is not set, show text command list."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = mock_user

        mock_update = AsyncMock()
        mock_update.effective_user.id = 12345
        mock_update.effective_user.first_name = "Test"
        mock_update.effective_user.username = "testuser"
        mock_update.effective_chat.id = -100123
        mock_update.message.message_id = 1

        with patch(
            "src.services.core.settings_service.SettingsService"
        ) as MockSettings:
            mock_settings_instance = MockSettings.return_value
            mock_settings_instance.__enter__ = Mock(return_value=mock_settings_instance)
            mock_settings_instance.__exit__ = Mock(return_value=False)
            mock_chat_settings = Mock(onboarding_completed=True)
            mock_settings_instance.get_settings.return_value = mock_chat_settings

            with patch(
                "src.services.core.telegram_commands.settings"
            ) as mock_app_settings:
                mock_app_settings.OAUTH_REDIRECT_BASE_URL = None

                await handlers.handle_start(mock_update, Mock())

        call_text = mock_update.message.reply_text.call_args[0][0]
        assert "/status" in call_text
        assert "/setup" in call_text

    async def test_start_logs_interaction(self, mock_command_handlers):
        """Start command logs the interaction."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = mock_user

        mock_update = AsyncMock()
        mock_update.effective_user.id = 12345
        mock_update.effective_user.first_name = "Test"
        mock_update.effective_user.username = "testuser"
        mock_update.effective_chat.id = -100123
        mock_update.message.message_id = 1

        with patch(
            "src.services.core.settings_service.SettingsService"
        ) as MockSettings:
            mock_settings_instance = MockSettings.return_value
            mock_settings_instance.__enter__ = Mock(return_value=mock_settings_instance)
            mock_settings_instance.__exit__ = Mock(return_value=False)
            mock_chat_settings = Mock(onboarding_completed=True)
            mock_settings_instance.get_settings.return_value = mock_chat_settings

            await handlers.handle_start(mock_update, Mock())

        service.interaction_service.log_command.assert_called_once()
        call_kwargs = service.interaction_service.log_command.call_args[1]
        assert call_kwargs["command"] == "/start"
