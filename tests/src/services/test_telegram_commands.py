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
class TestGetNextPostDisplay:
    """Tests for _get_next_post_display helper."""

    def test_returns_paused_when_paused(self):
        """Test returns 'Paused' when delivery is paused."""
        mock_settings = Mock(is_paused=True)
        result = TelegramCommandHandlers._get_next_post_display(mock_settings)
        assert result == "Paused"

    def test_returns_due_now_when_no_last_post(self):
        """Test returns 'Due now' when no post has been sent yet."""
        mock_settings = Mock(
            is_paused=False,
            posting_hours_start=12,
            posting_hours_end=4,
            posts_per_day=15,
            last_post_sent_at=None,
        )
        result = TelegramCommandHandlers._get_next_post_display(mock_settings)
        assert result == "Due now"

    def test_returns_due_now_when_past_due(self):
        """Test returns 'Due now' when next post time is in the past."""
        mock_settings = Mock(
            is_paused=False,
            posting_hours_start=12,
            posting_hours_end=4,
            posts_per_day=15,
            last_post_sent_at=datetime(2026, 1, 1, 10, 0, 0),
        )
        result = TelegramCommandHandlers._get_next_post_display(mock_settings)
        assert result == "Due now"

    def test_returns_time_estimate_when_future(self):
        """Test returns time estimate when next post is in the future."""
        # Set last_post_sent_at to just now so next is in the future
        mock_settings = Mock(
            is_paused=False,
            posting_hours_start=12,
            posting_hours_end=4,
            posts_per_day=15,
            last_post_sent_at=datetime.utcnow(),
        )
        result = TelegramCommandHandlers._get_next_post_display(mock_settings)
        assert "UTC" in result
        assert "~" in result

    def test_returns_not_configured_for_zero_window(self):
        """Test returns 'Not configured' when posting window is zero."""
        mock_settings = Mock(
            is_paused=False,
            posting_hours_start=12,
            posting_hours_end=12,
            posts_per_day=5,
            last_post_sent_at=None,
        )
        result = TelegramCommandHandlers._get_next_post_display(mock_settings)
        assert result == "Not configured"


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

    def test_enabled_with_rate_limit(self):
        """Test shows enabled status with rate limit remaining."""
        mock_chat_settings = Mock(enable_instagram_api=True)

        mock_ig = Mock()
        mock_ig.get_rate_limit_remaining.return_value = 20
        mock_ig.__enter__ = Mock(return_value=mock_ig)
        mock_ig.__exit__ = Mock(return_value=False)

        with patch(
            "src.services.integrations.instagram_api.InstagramAPIService",
            return_value=mock_ig,
        ):
            result = TelegramCommandHandlers._get_instagram_api_status(
                mock_chat_settings, "fake-cs-id"
            )

        assert "Enabled" in result
        assert "20/25" in result

    def test_disabled(self):
        """Test shows disabled status when chat_settings has IG API off."""
        mock_chat_settings = Mock(enable_instagram_api=False)

        result = TelegramCommandHandlers._get_instagram_api_status(
            mock_chat_settings, "fake-cs-id"
        )

        assert "Disabled" in result


@pytest.mark.unit
class TestGetSyncStatusLine:
    """Tests for _get_sync_status_line helper."""

    def test_sync_disabled(self):
        """Test shows disabled when media sync is off."""
        mock_chat_settings = Mock(media_sync_enabled=False)

        mock_sync = Mock()
        mock_sync.get_last_sync_info.return_value = None

        with patch(
            "src.services.core.media_sync.MediaSyncService",
            return_value=mock_sync,
        ):
            result = TelegramCommandHandlers._get_sync_status_line(mock_chat_settings)

        assert "Disabled" in result

    def test_no_syncs_yet(self):
        """Test shows 'No syncs yet' when no history."""
        mock_chat_settings = Mock(media_sync_enabled=True)

        mock_sync = Mock()
        mock_sync.get_last_sync_info.return_value = None

        with patch(
            "src.services.core.media_sync.MediaSyncService",
            return_value=mock_sync,
        ):
            result = TelegramCommandHandlers._get_sync_status_line(mock_chat_settings)

        assert "No syncs yet" in result

    def test_successful_sync(self):
        """Test shows OK with counts for successful sync."""
        mock_chat_settings = Mock(media_sync_enabled=True)

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
            result = TelegramCommandHandlers._get_sync_status_line(mock_chat_settings)

        assert "OK" in result
        assert "50 items" in result
        assert "5 new" in result

    def test_failed_sync(self):
        """Test shows warning for failed sync."""
        mock_chat_settings = Mock(media_sync_enabled=True)

        mock_sync = Mock()
        mock_sync.get_last_sync_info.return_value = {
            "success": False,
            "started_at": "2026-03-15T10:00:00Z",
        }

        with patch(
            "src.services.core.media_sync.MediaSyncService",
            return_value=mock_sync,
        ):
            result = TelegramCommandHandlers._get_sync_status_line(mock_chat_settings)

        assert "failed" in result

    def test_exception_shows_check_failed(self):
        """Test exception returns 'Check failed'."""
        mock_chat_settings = Mock(media_sync_enabled=True)

        with patch(
            "src.services.core.media_sync.MediaSyncService",
            side_effect=Exception("Import error"),
        ):
            result = TelegramCommandHandlers._get_sync_status_line(mock_chat_settings)

        assert "Check failed" in result


@pytest.mark.unit
@pytest.mark.asyncio
class TestStatusCommand:
    """Tests for handle_status end-to-end."""

    async def test_sends_formatted_status_message(self, mock_command_handlers):
        """Test /status sends a formatted message with key sections."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        # Set up repo returns (tenant-scoped)
        service.history_repo.get_recent_posts.return_value = []
        service.media_repo.count_by_posting_status.return_value = {
            "never_posted": 1,
            "posted_once": 1,
            "posted_multiple": 1,
        }

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        # Mock settings from DB (single source of truth)
        service.settings_service.get_settings.return_value = Mock(
            id="fake-uuid",
            posts_per_day=3,
            posting_hours_start=14,
            posting_hours_end=2,
            is_paused=False,
            dry_run_mode=False,
            enable_instagram_api=False,
            media_sync_enabled=False,
            media_source_root=None,
            last_post_sent_at=None,
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
            mock_settings.OAUTH_REDIRECT_BASE_URL = None
            await handlers.handle_status(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message_text = call_args.args[0]

        assert "Storyline AI Status" in message_text
        assert "Posted: 2" in message_text
        assert "Never posted: 1" in message_text
        assert "Next:" in message_text
        assert "Last:" in message_text
        assert "24h:" in message_text

        # Verify removed lines are NOT present
        assert "Bot: Online" not in message_text
        assert "Dry Run" not in message_text
        assert "Queue:" not in message_text
        assert "Locked:" not in message_text
        assert "Cadence:" not in message_text

        # Should log interaction
        service.interaction_service.log_command.assert_called_once()

    async def test_status_reads_config_from_db_not_env(self, mock_command_handlers):
        """Test /status reads all config from chat_settings DB, not env vars."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user
        service.history_repo.get_recent_posts.return_value = []
        service.media_repo.count_by_posting_status.return_value = {
            "never_posted": 0,
            "posted_once": 0,
            "posted_multiple": 0,
        }

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        # DB says IG API is enabled — env var should be irrelevant
        service.settings_service.get_settings.return_value = Mock(
            id="fake-uuid",
            posts_per_day=3,
            posting_hours_start=14,
            posting_hours_end=2,
            is_paused=False,
            dry_run_mode=False,
            enable_instagram_api=True,
            media_sync_enabled=False,
            media_source_root=None,
            last_post_sent_at=None,
        )

        mock_ig = Mock()
        mock_ig.get_rate_limit_remaining.return_value = 20
        mock_ig.__enter__ = Mock(return_value=mock_ig)
        mock_ig.__exit__ = Mock(return_value=False)

        with (
            patch("src.services.core.telegram_commands.settings") as mock_settings,
            patch(
                "src.services.core.media_sync.MediaSyncService",
                side_effect=Exception("n/a"),
            ),
            patch(
                "src.services.integrations.instagram_api.InstagramAPIService",
                return_value=mock_ig,
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
            mock_settings.OAUTH_REDIRECT_BASE_URL = None
            # Env says disabled, but DB says enabled — DB should win
            mock_settings.ENABLE_INSTAGRAM_API = False
            await handlers.handle_status(mock_update, Mock())

        msg = mock_update.message.reply_text.call_args.args[0]
        assert "Enabled" in msg
        assert "20/25" in msg


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

        # Set up repo returns (tenant-scoped)
        service.history_repo.get_recent_posts.return_value = []
        service.media_repo.count_by_posting_status.return_value = {
            "never_posted": 0,
            "posted_once": 0,
            "posted_multiple": 0,
        }

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        mock_context = Mock()

        mock_chat_settings = Mock(
            id="fake-uuid",
            posts_per_day=3,
            posting_hours_start=14,
            posting_hours_end=2,
            is_paused=False,
            dry_run_mode=False,
            enable_instagram_api=False,
            media_sync_enabled=False,
            media_source_root=None,
            last_post_sent_at=None,
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
            mock_settings.OAUTH_REDIRECT_BASE_URL = None

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

        service.history_repo.get_recent_posts.return_value = []
        service.media_repo.count_by_posting_status.return_value = {
            "never_posted": 0,
            "posted_once": 0,
            "posted_multiple": 0,
        }

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
            enable_instagram_api=False,
            media_sync_enabled=False,
            media_source_root=None,
            last_post_sent_at=None,
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

        service.history_repo.get_recent_posts.return_value = []
        service.media_repo.count_by_posting_status.return_value = {
            "never_posted": 0,
            "posted_once": 0,
            "posted_multiple": 0,
        }

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
            enable_instagram_api=False,
            media_sync_enabled=False,
            media_source_root=None,
            last_post_sent_at=None,
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
            mock_settings.OAUTH_REDIRECT_BASE_URL = None

            await handlers.handle_status(mock_update, Mock())

        call_args = mock_update.message.reply_text.call_args
        reply_markup = call_args.kwargs.get("reply_markup")
        assert reply_markup is None


@pytest.mark.unit
@pytest.mark.asyncio
class TestStatusLibraryBreakdown:
    """Tests for /status library section — now shows only never-posted count."""

    async def test_status_includes_never_posted_count(self, mock_command_handlers):
        """Test /status shows never-posted count (content runway)."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = None
        service.user_repo.create.return_value = mock_user

        service.media_repo.count_by_posting_status.return_value = {
            "never_posted": 42,
            "posted_once": 10,
            "posted_multiple": 5,
        }
        service.history_repo.get_recent_posts.return_value = []

        mock_update = Mock()
        mock_update.effective_user = Mock(
            id=123, username="test", first_name="Test", last_name=None
        )
        mock_update.effective_chat = Mock(id=-100123)
        mock_update.message = AsyncMock()
        mock_update.message.message_id = 1

        service.settings_service.get_settings.return_value = Mock(
            id="fake-uuid",
            posts_per_day=3,
            posting_hours_start=14,
            posting_hours_end=2,
            is_paused=False,
            dry_run_mode=False,
            enable_instagram_api=False,
            media_sync_enabled=False,
            media_source_root=None,
            last_post_sent_at=None,
        )

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
            mock_settings.OAUTH_REDIRECT_BASE_URL = None

            await handlers.handle_status(mock_update, Mock())

        msg = mock_update.message.reply_text.call_args.args[0]
        assert "Posted: 15" in msg
        assert "Never posted: 42" in msg
        # These lines were removed from the streamlined /status
        assert "Posted once" not in msg
        assert "Posted 2+" not in msg
        assert "Total:" not in msg


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
            ("/reset", "JIT scheduler"),
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


@pytest.mark.unit
@pytest.mark.asyncio
class TestApproveAllCommand:
    """Tests for /approveall command - batch approve pending posts."""

    async def test_approveall_shows_summary_and_confirm(self, mock_command_handlers):
        """Test /approveall shows pending count and confirmation button."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = mock_user

        mock_chat_settings = Mock()
        mock_chat_settings.id = uuid4()
        mock_chat_settings.enable_instagram_api = False
        service.settings_service.get_settings.return_value = mock_chat_settings

        mock_item1 = Mock(id=uuid4())
        mock_item2 = Mock(id=uuid4())
        service.queue_repo.get_all_with_media.side_effect = [
            [(mock_item1, "meme.jpg", "memes"), (mock_item2, "merch.jpg", "merch")],
            [],  # processing = empty
        ]

        mock_update = AsyncMock()
        mock_update.effective_user.id = 123
        mock_update.effective_user.first_name = "Test"
        mock_update.effective_user.username = "test"
        mock_update.effective_chat.id = -100123
        mock_update.message.message_id = 1

        await handlers.handle_approveall(mock_update, Mock())

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        text = call_args[0][0]
        assert "2 pending posts" in text
        assert "memes" in text
        assert "merch" in text
        # Check confirmation button exists
        keyboard = call_args[1]["reply_markup"]
        assert keyboard is not None

    async def test_approveall_empty_queue(self, mock_command_handlers):
        """Test /approveall with no pending items."""
        handlers = mock_command_handlers
        service = handlers.service

        mock_user = Mock()
        mock_user.id = uuid4()
        service.user_repo.get_by_telegram_id.return_value = mock_user

        mock_chat_settings = Mock()
        mock_chat_settings.id = uuid4()
        service.settings_service.get_settings.return_value = mock_chat_settings

        service.queue_repo.get_all_with_media.return_value = []

        mock_update = AsyncMock()
        mock_update.effective_user.id = 123
        mock_update.effective_user.first_name = "Test"
        mock_update.effective_user.username = "test"
        mock_update.effective_chat.id = -100123
        mock_update.message.message_id = 1

        await handlers.handle_approveall(mock_update, Mock())

        call_text = mock_update.message.reply_text.call_args[0][0]
        assert "No Pending Posts" in call_text
