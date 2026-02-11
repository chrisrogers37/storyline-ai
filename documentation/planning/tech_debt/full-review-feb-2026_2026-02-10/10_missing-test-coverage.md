# Add Missing Test Files for Uncovered Modules

| Field | Value |
|---|---|
| **Status** | ✅ COMPLETE |
| **Started** | 2026-02-10 |
| **Completed** | 2026-02-10 |
| **PR Title** | `test: add missing test files for uncovered modules` |
| **Risk Level** | Low |
| **Effort** | Large (6-8 hours) |
| **Dependencies** | Phase 08, Phase 09 (test patterns must be established first) |
| **Blocks** | None |
| **Files Modified** | New test files only: `tests/src/services/test_telegram_autopost.py`, `tests/cli/test_instagram_commands.py`, `tests/src/repositories/test_base_repository.py`, `tests/src/repositories/test_chat_settings_repository.py`, `tests/src/repositories/test_instagram_account_repository.py`, `tests/src/repositories/test_token_repository.py` |

---

## Problem Description

Six source modules have zero test coverage -- no test file exists for them at all. These modules represent critical business logic (auto-posting to Instagram), CLI commands (account management), and foundational infrastructure (base repository, settings persistence).

The highest-priority gap is `telegram_autopost.py` (467 lines), which handles the real Instagram posting flow including Cloudinary upload, safety gates, dry-run mode, and error recovery. A bug here could result in posting to the wrong Instagram account or failing silently.

The four repository files (`base_repository.py`, `chat_settings_repository.py`, `instagram_account_repository.py`, `token_repository.py`) lack the unit-test-with-mocked-session coverage that other repositories already have (see `tests/src/repositories/test_category_mix_repository.py` for the established pattern).

---

## Step-by-Step Implementation

### Step 1: Create `tests/src/services/test_telegram_autopost.py`

**Source file**: `src/services/core/telegram_autopost.py` (467 lines)

This is the highest-priority test file. The `TelegramAutopostHandler` class uses a composition pattern -- it receives a reference to the parent `TelegramService` and accesses repositories through `self.service.*`.

The mocking pattern follows the same approach as `tests/src/services/test_telegram_callbacks.py`: patch all repository classes in `TelegramService.__init__`, create the `TelegramService`, then create `TelegramAutopostHandler(service)`.

**Create** `tests/src/services/test_telegram_autopost.py`:

```python
"""Tests for TelegramAutopostHandler."""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime
from uuid import uuid4

from src.services.core.telegram_service import TelegramService
from src.services.core.telegram_autopost import TelegramAutopostHandler


@pytest.fixture
def mock_autopost_handler():
    """Create TelegramAutopostHandler with mocked service dependencies."""
    with (
        patch("src.services.core.telegram_service.settings") as mock_settings,
        patch(
            "src.services.core.telegram_service.UserRepository"
        ) as mock_user_repo_class,
        patch(
            "src.services.core.telegram_service.QueueRepository"
        ) as mock_queue_repo_class,
        patch(
            "src.services.core.telegram_service.MediaRepository"
        ) as mock_media_repo_class,
        patch(
            "src.services.core.telegram_service.HistoryRepository"
        ) as mock_history_repo_class,
        patch(
            "src.services.core.telegram_service.LockRepository"
        ) as mock_lock_repo_class,
        patch(
            "src.services.core.telegram_service.MediaLockService"
        ) as mock_lock_service_class,
        patch(
            "src.services.core.telegram_service.InteractionService"
        ) as mock_interaction_service_class,
        patch(
            "src.services.core.telegram_service.SettingsService"
        ) as mock_settings_service_class,
        patch(
            "src.services.core.telegram_service.InstagramAccountService"
        ) as mock_ig_account_service_class,
    ):
        mock_settings.TELEGRAM_BOT_TOKEN = "123456:ABC-DEF1234ghIkl"
        mock_settings.TELEGRAM_CHANNEL_ID = -1001234567890
        mock_settings.CAPTION_STYLE = "enhanced"
        mock_settings.SEND_LIFECYCLE_NOTIFICATIONS = False
        mock_settings.ENABLE_INSTAGRAM_API = True

        service = TelegramService()

        service.user_repo = mock_user_repo_class.return_value
        service.queue_repo = mock_queue_repo_class.return_value
        service.media_repo = mock_media_repo_class.return_value
        service.history_repo = mock_history_repo_class.return_value
        service.lock_repo = mock_lock_repo_class.return_value
        service.lock_service = mock_lock_service_class.return_value
        service.interaction_service = mock_interaction_service_class.return_value
        service.settings_service = mock_settings_service_class.return_value
        service.ig_account_service = mock_ig_account_service_class.return_value

        handler = TelegramAutopostHandler(service)
        yield handler


@pytest.mark.unit
@pytest.mark.asyncio
class TestAutopostQueueItemNotFound:
    """Tests for autopost when queue/media items are missing."""

    async def test_autopost_queue_item_not_found(self, mock_autopost_handler):
        """Test that autopost handles missing queue item gracefully."""
        handler = mock_autopost_handler
        service = handler.service
        queue_id = str(uuid4())

        service.queue_repo.get_by_id.return_value = None

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_query = AsyncMock()

        await handler.handle_autopost(queue_id, mock_user, mock_query)

        mock_query.edit_message_caption.assert_called_once()
        call_args = mock_query.edit_message_caption.call_args
        assert "not found" in str(call_args).lower()

    async def test_autopost_media_item_not_found(self, mock_autopost_handler):
        """Test that autopost handles missing media item gracefully."""
        handler = mock_autopost_handler
        service = handler.service
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()
        service.queue_repo.get_by_id.return_value = mock_queue_item
        service.media_repo.get_by_id.return_value = None

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_query = AsyncMock()

        await handler.handle_autopost(queue_id, mock_user, mock_query)

        mock_query.edit_message_caption.assert_called_once()
        call_args = mock_query.edit_message_caption.call_args
        assert "not found" in str(call_args).lower()


@pytest.mark.unit
@pytest.mark.asyncio
class TestAutopostSafetyGates:
    """Tests for safety check enforcement."""

    async def test_autopost_safety_check_failure_blocks_posting(
        self, mock_autopost_handler
    ):
        """Test that a failed safety check prevents posting."""
        handler = mock_autopost_handler
        service = handler.service
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()
        service.queue_repo.get_by_id.return_value = mock_queue_item

        mock_media = Mock()
        mock_media.file_path = "/test/story.jpg"
        mock_media.file_name = "story.jpg"
        service.media_repo.get_by_id.return_value = mock_media

        mock_chat_settings = Mock()
        mock_chat_settings.dry_run_mode = False
        service.settings_service.get_settings.return_value = mock_chat_settings

        mock_user = Mock()
        mock_user.id = uuid4()

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        # Patch the Instagram service's safety check to return failure
        with patch(
            "src.services.core.telegram_autopost.InstagramAPIService"
        ) as mock_ig_class, patch(
            "src.services.core.telegram_autopost.CloudStorageService"
        ) as mock_cloud_class:
            mock_ig_instance = mock_ig_class.return_value
            mock_ig_instance.safety_check_before_post.return_value = {
                "safe_to_post": False,
                "errors": ["Token expired", "Rate limit exceeded"],
            }
            mock_ig_instance.close = Mock()
            mock_cloud_instance = mock_cloud_class.return_value
            mock_cloud_instance.close = Mock()

            await handler.handle_autopost(queue_id, mock_user, mock_query)

        # Should show safety check failure message
        caption_call = mock_query.edit_message_caption.call_args
        caption = str(caption_call)
        assert "SAFETY CHECK FAILED" in caption

        # Should NOT create history or delete from queue
        service.history_repo.create.assert_not_called()
        service.queue_repo.delete.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
class TestAutopostDryRun:
    """Tests for dry-run mode behavior."""

    async def test_dry_run_uploads_to_cloudinary_but_skips_instagram(
        self, mock_autopost_handler
    ):
        """Test that dry-run mode uploads to Cloudinary but stops before Instagram API."""
        handler = mock_autopost_handler
        service = handler.service
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()
        service.queue_repo.get_by_id.return_value = mock_queue_item

        mock_media = Mock()
        mock_media.file_path = "/test/story.jpg"
        mock_media.file_name = "story.jpg"
        service.media_repo.get_by_id.return_value = mock_media

        mock_chat_settings = Mock()
        mock_chat_settings.dry_run_mode = True
        service.settings_service.get_settings.return_value = mock_chat_settings

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "tester"
        mock_user.telegram_first_name = "Test"

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        with patch(
            "src.services.core.telegram_autopost.InstagramAPIService"
        ) as mock_ig_class, patch(
            "src.services.core.telegram_autopost.CloudStorageService"
        ) as mock_cloud_class:
            mock_ig_instance = mock_ig_class.return_value
            mock_ig_instance.safety_check_before_post.return_value = {
                "safe_to_post": True,
                "errors": [],
            }
            mock_ig_instance.get_account_info = AsyncMock(
                return_value={"username": "testaccount"}
            )
            mock_ig_instance.close = Mock()

            mock_cloud_instance = mock_cloud_class.return_value
            mock_cloud_instance.upload_media.return_value = {
                "url": "https://res.cloudinary.com/test/image.jpg",
                "public_id": "instagram_stories/test123",
            }
            mock_cloud_instance.get_story_optimized_url.return_value = (
                "https://res.cloudinary.com/test/image_optimized.jpg"
            )
            mock_cloud_instance.close = Mock()

            await handler.handle_autopost(queue_id, mock_user, mock_query)

        # Cloudinary upload SHOULD have been called
        mock_cloud_instance.upload_media.assert_called_once()

        # Instagram API post SHOULD NOT have been called
        mock_ig_instance.post_story.assert_not_called()

        # Queue item should NOT be deleted (preserved for re-testing)
        service.queue_repo.delete.assert_not_called()

        # History should NOT be created
        service.history_repo.create.assert_not_called()

        # Dry run interaction should be logged
        service.interaction_service.log_callback.assert_called_once()
        log_call = service.interaction_service.log_callback.call_args
        assert log_call.kwargs["context"]["dry_run"] is True

        # Caption should mention DRY RUN
        final_caption_call = mock_query.edit_message_caption.call_args_list[-1]
        caption = str(final_caption_call)
        assert "DRY RUN" in caption


@pytest.mark.unit
@pytest.mark.asyncio
class TestAutopostErrorRecovery:
    """Tests for error handling during auto-post."""

    async def test_cloudinary_upload_failure_shows_error(self, mock_autopost_handler):
        """Test that Cloudinary upload failure shows error with retry button."""
        handler = mock_autopost_handler
        service = handler.service
        queue_id = str(uuid4())

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = uuid4()
        service.queue_repo.get_by_id.return_value = mock_queue_item

        mock_media = Mock()
        mock_media.file_path = "/test/story.jpg"
        mock_media.file_name = "story.jpg"
        service.media_repo.get_by_id.return_value = mock_media

        mock_chat_settings = Mock()
        mock_chat_settings.dry_run_mode = False
        service.settings_service.get_settings.return_value = mock_chat_settings

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.telegram_username = "poster"

        mock_query = AsyncMock()
        mock_query.message = Mock(chat_id=-100123, message_id=1)

        with patch(
            "src.services.core.telegram_autopost.InstagramAPIService"
        ) as mock_ig_class, patch(
            "src.services.core.telegram_autopost.CloudStorageService"
        ) as mock_cloud_class:
            mock_ig_instance = mock_ig_class.return_value
            mock_ig_instance.safety_check_before_post.return_value = {
                "safe_to_post": True,
                "errors": [],
            }
            mock_ig_instance.close = Mock()

            mock_cloud_instance = mock_cloud_class.return_value
            mock_cloud_instance.upload_media.side_effect = Exception(
                "Cloudinary timeout"
            )
            mock_cloud_instance.close = Mock()

            await handler.handle_autopost(queue_id, mock_user, mock_query)

        # Should show error message
        final_caption_call = mock_query.edit_message_caption.call_args_list[-1]
        caption = str(final_caption_call)
        assert "Auto Post Failed" in caption
        assert "Cloudinary timeout" in caption

        # Should log failure interaction
        service.interaction_service.log_callback.assert_called_once()
        log_call = service.interaction_service.log_callback.call_args
        assert log_call.kwargs["context"]["success"] is False


@pytest.mark.unit
@pytest.mark.asyncio
class TestAutopostOperationLock:
    """Tests for the operation lock that prevents duplicate auto-posts."""

    async def test_double_click_returns_already_processing(
        self, mock_autopost_handler
    ):
        """Test that clicking autopost while already processing shows feedback."""
        handler = mock_autopost_handler
        service = handler.service
        queue_id = str(uuid4())

        # Pre-acquire the lock to simulate an in-progress operation
        lock = service.get_operation_lock(queue_id)
        await lock.acquire()

        mock_user = Mock()
        mock_user.id = uuid4()
        mock_query = AsyncMock()

        await handler.handle_autopost(queue_id, mock_user, mock_query)

        # Should show "Already processing" feedback
        mock_query.answer.assert_called_once()
        answer_call = mock_query.answer.call_args
        assert "Already processing" in str(answer_call)

        # Clean up
        lock.release()
```

**Key test methods and what they cover:**

| Test | Source Lines Covered | What It Validates |
|---|---|---|
| `test_autopost_queue_item_not_found` | Lines 57-61 | Early exit when queue item missing |
| `test_autopost_media_item_not_found` | Lines 64-67 | Early exit when media item missing |
| `test_autopost_safety_check_failure_blocks_posting` | Lines 112-125 | Safety gate enforcement |
| `test_dry_run_uploads_to_cloudinary_but_skips_instagram` | Lines 168-259 | Dry-run stops before Instagram API |
| `test_cloudinary_upload_failure_shows_error` | Lines 401-467 | Error recovery with retry keyboard |
| `test_double_click_returns_already_processing` | Lines 41-44 | Operation lock prevents duplicates |

---

### Step 2: Create `tests/cli/test_instagram_commands.py`

**Source file**: `cli/commands/instagram.py` (638 lines)

This file contains 5 Click commands: `instagram_auth`, `instagram_status`, `add_instagram_account`, `list_instagram_accounts`, `deactivate_instagram_account`, and `reactivate_instagram_account`.

Use Click's `CliRunner` for testing. Mock all service and repository dependencies at their import paths.

**Create** `tests/cli/test_instagram_commands.py`:

```python
"""Tests for Instagram CLI commands."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from click.testing import CliRunner
from datetime import datetime, timedelta

from cli.commands.instagram import (
    instagram_status,
    add_instagram_account,
    list_instagram_accounts,
    deactivate_instagram_account,
    reactivate_instagram_account,
)


@pytest.mark.unit
class TestInstagramStatusCommand:
    """Tests for the instagram-status CLI command."""

    @patch("cli.commands.instagram.TokenRefreshService")
    @patch("cli.commands.instagram.settings")
    def test_instagram_status_authenticated(self, mock_settings, mock_service_class):
        """Test instagram-status shows authenticated status."""
        mock_service = mock_service_class.return_value
        mock_service.check_token_health.return_value = {
            "valid": True,
            "exists": True,
            "source": "database",
            "expires_at": datetime.utcnow() + timedelta(days=30),
            "expires_in_hours": 720,
            "needs_refresh": False,
            "needs_bootstrap": False,
            "last_refreshed": datetime.utcnow(),
        }
        mock_settings.ENABLE_INSTAGRAM_API = True
        mock_settings.INSTAGRAM_ACCOUNT_ID = "12345"
        mock_settings.FACEBOOK_APP_ID = "app123"
        mock_settings.CLOUDINARY_CLOUD_NAME = "mycloud"

        runner = CliRunner()
        result = runner.invoke(instagram_status)

        assert result.exit_code == 0
        assert "Authenticated" in result.output

    @patch("cli.commands.instagram.TokenRefreshService")
    @patch("cli.commands.instagram.settings")
    def test_instagram_status_not_authenticated(
        self, mock_settings, mock_service_class
    ):
        """Test instagram-status shows not authenticated when no token."""
        mock_service = mock_service_class.return_value
        mock_service.check_token_health.return_value = {
            "valid": False,
            "exists": False,
            "source": None,
            "expires_at": None,
            "error": "No token found",
        }
        mock_settings.ENABLE_INSTAGRAM_API = False
        mock_settings.INSTAGRAM_ACCOUNT_ID = None
        mock_settings.FACEBOOK_APP_ID = None
        mock_settings.CLOUDINARY_CLOUD_NAME = None

        runner = CliRunner()
        result = runner.invoke(instagram_status)

        assert result.exit_code == 0
        assert "Not Authenticated" in result.output


@pytest.mark.unit
class TestAddInstagramAccountCommand:
    """Tests for the add-instagram-account CLI command."""

    @patch("cli.commands.instagram.settings")
    @patch("cli.commands.instagram.TokenEncryption")
    @patch("cli.commands.instagram.InstagramAccountService")
    def test_add_account_success(
        self, mock_service_class, mock_encryption_class, mock_settings
    ):
        """Test successfully adding a new Instagram account."""
        mock_service = mock_service_class.return_value
        mock_account = Mock()
        mock_account.id = "acc-uuid-123"
        mock_account.display_name = "Main Brand"
        mock_account.instagram_account_id = "17841234567890"
        mock_account.instagram_username = "brand_main"
        mock_service.add_account.return_value = mock_account

        mock_encryption = mock_encryption_class.return_value
        mock_encryption.encrypt.return_value = "encrypted_token_value"

        mock_settings.ADMIN_TELEGRAM_CHAT_ID = -100123

        runner = CliRunner()
        result = runner.invoke(
            add_instagram_account,
            [
                "--display-name", "Main Brand",
                "--account-id", "17841234567890",
                "--username", "brand_main",
                "--access-token", "A" * 60,  # Valid token length
                "--set-active",
            ],
        )

        assert result.exit_code == 0
        assert "successfully" in result.output
        mock_service.add_account.assert_called_once()

    @patch("cli.commands.instagram.settings")
    @patch("cli.commands.instagram.TokenEncryption")
    @patch("cli.commands.instagram.InstagramAccountService")
    def test_add_account_invalid_token(
        self, mock_service_class, mock_encryption_class, mock_settings
    ):
        """Test adding account with invalid token shows error."""
        runner = CliRunner()
        result = runner.invoke(
            add_instagram_account,
            [
                "--display-name", "Test",
                "--account-id", "123",
                "--username", "test",
                "--access-token", "short",  # Too short
            ],
        )

        assert "Invalid access token" in result.output

    @patch("cli.commands.instagram.settings")
    @patch("cli.commands.instagram.TokenEncryption")
    @patch("cli.commands.instagram.InstagramAccountService")
    def test_add_account_service_error(
        self, mock_service_class, mock_encryption_class, mock_settings
    ):
        """Test adding account when service raises ValueError."""
        mock_service = mock_service_class.return_value
        mock_service.add_account.side_effect = ValueError(
            "Account with this Instagram ID already exists"
        )

        mock_encryption = mock_encryption_class.return_value
        mock_encryption.encrypt.return_value = "encrypted"

        runner = CliRunner()
        result = runner.invoke(
            add_instagram_account,
            [
                "--display-name", "Duplicate",
                "--account-id", "17841234567890",
                "--username", "duplicate",
                "--access-token", "A" * 60,
            ],
        )

        assert "already exists" in result.output


@pytest.mark.unit
class TestListInstagramAccountsCommand:
    """Tests for the list-instagram-accounts CLI command."""

    @patch("cli.commands.instagram.settings")
    @patch("cli.commands.instagram.TokenRepository")
    @patch("cli.commands.instagram.InstagramAccountService")
    def test_list_accounts_shows_table(
        self, mock_service_class, mock_token_repo_class, mock_settings
    ):
        """Test listing accounts displays table with account info."""
        mock_service = mock_service_class.return_value

        mock_account = Mock()
        mock_account.id = "acc-1"
        mock_account.display_name = "Main Brand"
        mock_account.instagram_username = "brand_main"
        mock_account.instagram_account_id = "17841234567890"
        mock_account.is_active = True

        mock_service.list_accounts.return_value = [mock_account]
        mock_service.get_active_account.return_value = mock_account
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = -100123

        mock_token_repo = mock_token_repo_class.return_value
        mock_token = Mock()
        mock_token.is_expired = False
        mock_token.hours_until_expiry.return_value = 720
        mock_token_repo.get_token_for_account.return_value = mock_token

        runner = CliRunner()
        result = runner.invoke(list_instagram_accounts)

        assert result.exit_code == 0
        assert "Main Brand" in result.output

    @patch("cli.commands.instagram.settings")
    @patch("cli.commands.instagram.TokenRepository")
    @patch("cli.commands.instagram.InstagramAccountService")
    def test_list_accounts_empty(
        self, mock_service_class, mock_token_repo_class, mock_settings
    ):
        """Test listing accounts when no accounts configured."""
        mock_service = mock_service_class.return_value
        mock_service.list_accounts.return_value = []
        mock_service.get_active_account.return_value = None
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = -100123

        runner = CliRunner()
        result = runner.invoke(list_instagram_accounts)

        assert result.exit_code == 0
        assert "No Instagram accounts configured" in result.output


@pytest.mark.unit
class TestDeactivateReactivateCommands:
    """Tests for deactivate/reactivate Instagram account commands."""

    @patch("cli.commands.instagram.InstagramAccountService")
    def test_deactivate_account_success(self, mock_service_class):
        """Test deactivating an existing account."""
        mock_service = mock_service_class.return_value
        mock_account = Mock()
        mock_account.display_name = "Old Account"
        mock_account.instagram_username = "old_brand"
        mock_account.is_active = True
        mock_service.get_account_by_username.return_value = mock_account

        runner = CliRunner()
        result = runner.invoke(
            deactivate_instagram_account, ["old_brand"], input="y\n"
        )

        assert result.exit_code == 0
        assert "deactivated" in result.output
        mock_service.deactivate_account.assert_called_once()

    @patch("cli.commands.instagram.InstagramAccountService")
    def test_deactivate_account_not_found(self, mock_service_class):
        """Test deactivating a non-existent account."""
        mock_service = mock_service_class.return_value
        mock_service.get_account_by_username.return_value = None
        mock_service.get_account_by_id.return_value = None

        runner = CliRunner()
        result = runner.invoke(deactivate_instagram_account, ["nonexistent"])

        assert "not found" in result.output

    @patch("cli.commands.instagram.InstagramAccountService")
    def test_reactivate_account_success(self, mock_service_class):
        """Test reactivating a deactivated account."""
        mock_service = mock_service_class.return_value
        mock_account = Mock()
        mock_account.id = "acc-1"
        mock_account.display_name = "Restored Account"
        mock_account.instagram_username = "restored"
        mock_account.is_active = False
        mock_service.get_account_by_username.return_value = mock_account

        runner = CliRunner()
        result = runner.invoke(reactivate_instagram_account, ["restored"])

        assert result.exit_code == 0
        assert "reactivated" in result.output
        mock_service.reactivate_account.assert_called_once()

    @patch("cli.commands.instagram.InstagramAccountService")
    def test_reactivate_already_active(self, mock_service_class):
        """Test reactivating an account that is already active."""
        mock_service = mock_service_class.return_value
        mock_account = Mock()
        mock_account.display_name = "Active Account"
        mock_account.is_active = True
        mock_service.get_account_by_username.return_value = mock_account

        runner = CliRunner()
        result = runner.invoke(reactivate_instagram_account, ["active_account"])

        assert "already active" in result.output
```

---

### Step 3: Create `tests/src/repositories/test_base_repository.py`

**Source file**: `src/repositories/base_repository.py` (108 lines)

This file defines `BaseRepository`, the parent class for all repositories. It manages database session lifecycle through a generator pattern (`get_db()`).

**Create** `tests/src/repositories/test_base_repository.py`:

```python
"""Tests for BaseRepository."""

import pytest
from unittest.mock import Mock, MagicMock, patch

from src.repositories.base_repository import BaseRepository


@pytest.mark.unit
class TestBaseRepository:
    """Test suite for BaseRepository."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()

    @pytest.fixture
    def repo(self, mock_db):
        """Create BaseRepository with mocked database."""
        with patch("src.repositories.base_repository.get_db") as mock_get_db:
            mock_get_db.return_value = iter([mock_db])
            repo = BaseRepository()
            repo._db = mock_db
            return repo

    def test_init_creates_session(self):
        """Test that __init__ creates a database session from get_db()."""
        mock_session = MagicMock()
        with patch("src.repositories.base_repository.get_db") as mock_get_db:
            mock_get_db.return_value = iter([mock_session])
            repo = BaseRepository()

        assert repo._db is mock_session

    def test_db_property_returns_session(self, repo, mock_db):
        """Test that db property returns the session."""
        mock_db.is_active = True
        result = repo.db
        assert result is mock_db

    def test_db_property_rollback_on_inactive(self, repo, mock_db):
        """Test that db property rolls back when session is not active."""
        mock_db.is_active = False
        _ = repo.db
        mock_db.rollback.assert_called_once()

    def test_commit_calls_session_commit(self, repo, mock_db):
        """Test that commit() delegates to session.commit()."""
        repo.commit()
        mock_db.commit.assert_called_once()

    def test_commit_rollback_on_error(self, repo, mock_db):
        """Test that commit() rolls back and re-raises on error."""
        mock_db.commit.side_effect = Exception("Commit failed")

        with pytest.raises(Exception, match="Commit failed"):
            repo.commit()

        mock_db.rollback.assert_called_once()

    def test_rollback_calls_session_rollback(self, repo, mock_db):
        """Test that rollback() delegates to session.rollback()."""
        repo.rollback()
        mock_db.rollback.assert_called_once()

    def test_rollback_suppresses_error(self, repo, mock_db):
        """Test that rollback() does not raise if session.rollback fails."""
        mock_db.rollback.side_effect = Exception("Rollback failed")
        # Should NOT raise
        repo.rollback()

    def test_end_read_transaction_commits(self, repo, mock_db):
        """Test that end_read_transaction() commits to release locks."""
        repo.end_read_transaction()
        mock_db.commit.assert_called_once()

    def test_end_read_transaction_rollback_on_error(self, repo, mock_db):
        """Test that end_read_transaction() falls back to rollback."""
        mock_db.commit.side_effect = Exception("Read commit failed")
        # Should NOT raise
        repo.end_read_transaction()
        mock_db.rollback.assert_called_once()

    def test_close_exhausts_generator(self, repo, mock_db):
        """Test that close() attempts to exhaust the generator."""
        # close() calls next() on the generator and then session.close()
        repo.close()
        mock_db.close.assert_called_once()

    def test_context_manager_enter_returns_self(self, repo):
        """Test that __enter__ returns the repository instance."""
        result = repo.__enter__()
        assert result is repo

    def test_context_manager_exit_calls_close(self, repo, mock_db):
        """Test that __exit__ calls close()."""
        repo.__exit__(None, None, None)
        mock_db.close.assert_called_once()

    def test_context_manager_does_not_suppress_exceptions(self, repo):
        """Test that __exit__ returns False (does not suppress exceptions)."""
        result = repo.__exit__(ValueError, ValueError("test"), None)
        assert result is False
```

---

### Step 4: Create `tests/src/repositories/test_chat_settings_repository.py`

**Source file**: `src/repositories/chat_settings_repository.py` (100 lines)

**Create** `tests/src/repositories/test_chat_settings_repository.py`:

```python
"""Tests for ChatSettingsRepository."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from src.repositories.chat_settings_repository import ChatSettingsRepository
from src.models.chat_settings import ChatSettings


@pytest.mark.unit
class TestChatSettingsRepository:
    """Test suite for ChatSettingsRepository."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()

    @pytest.fixture
    def settings_repo(self, mock_db):
        """Create ChatSettingsRepository with mocked database."""
        with patch("src.repositories.base_repository.get_db") as mock_get_db:
            mock_get_db.return_value = iter([mock_db])
            repo = ChatSettingsRepository()
            repo._db = mock_db
            return repo

    def test_get_by_chat_id_found(self, settings_repo, mock_db):
        """Test getting settings for an existing chat."""
        mock_settings = Mock(spec=ChatSettings)
        mock_settings.telegram_chat_id = -100123
        mock_db.query.return_value.filter.return_value.first.return_value = (
            mock_settings
        )

        result = settings_repo.get_by_chat_id(-100123)

        assert result is mock_settings
        mock_db.commit.assert_called_once()  # end_read_transaction

    def test_get_by_chat_id_not_found(self, settings_repo, mock_db):
        """Test getting settings for non-existent chat returns None."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = settings_repo.get_by_chat_id(-999999)

        assert result is None

    @patch("src.repositories.chat_settings_repository.env_settings")
    def test_get_or_create_returns_existing(self, mock_env, settings_repo, mock_db):
        """Test get_or_create returns existing record without creating."""
        mock_settings = Mock(spec=ChatSettings)
        mock_db.query.return_value.filter.return_value.first.return_value = (
            mock_settings
        )

        result = settings_repo.get_or_create(-100123)

        assert result is mock_settings
        mock_db.add.assert_not_called()

    @patch("src.repositories.chat_settings_repository.env_settings")
    def test_get_or_create_bootstraps_from_env(self, mock_env, settings_repo, mock_db):
        """Test get_or_create creates new record from .env defaults."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        mock_env.DRY_RUN_MODE = True
        mock_env.ENABLE_INSTAGRAM_API = False
        mock_env.POSTS_PER_DAY = 3
        mock_env.POSTING_HOURS_START = 9
        mock_env.POSTING_HOURS_END = 22

        settings_repo.get_or_create(-100123)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

        added_obj = mock_db.add.call_args[0][0]
        assert isinstance(added_obj, ChatSettings)
        assert added_obj.telegram_chat_id == -100123
        assert added_obj.dry_run_mode is True
        assert added_obj.posts_per_day == 3

    def test_update_modifies_fields(self, settings_repo, mock_db):
        """Test update modifies specified fields on existing record."""
        mock_settings = Mock(spec=ChatSettings)
        mock_settings.dry_run_mode = False
        mock_settings.is_paused = False
        # get_or_create returns existing
        mock_db.query.return_value.filter.return_value.first.return_value = (
            mock_settings
        )

        settings_repo.update(-100123, dry_run_mode=True, is_paused=True)

        assert mock_settings.dry_run_mode is True
        assert mock_settings.is_paused is True
        mock_db.commit.assert_called()

    def test_set_paused_tracks_user(self, settings_repo, mock_db):
        """Test set_paused records who paused and when."""
        mock_settings = Mock(spec=ChatSettings)
        mock_db.query.return_value.filter.return_value.first.return_value = (
            mock_settings
        )

        settings_repo.set_paused(-100123, is_paused=True, user_id="user-uuid-1")

        assert mock_settings.is_paused is True
        assert mock_settings.paused_by_user_id == "user-uuid-1"
        assert mock_settings.paused_at is not None

    def test_set_unpaused_clears_tracking(self, settings_repo, mock_db):
        """Test set_paused(False) clears pause tracking fields."""
        mock_settings = Mock(spec=ChatSettings)
        mock_settings.is_paused = True
        mock_settings.paused_by_user_id = "user-uuid-1"
        mock_db.query.return_value.filter.return_value.first.return_value = (
            mock_settings
        )

        settings_repo.set_paused(-100123, is_paused=False)

        assert mock_settings.is_paused is False
        assert mock_settings.paused_by_user_id is None
        assert mock_settings.paused_at is None
```

---

### Step 5: Create `tests/src/repositories/test_instagram_account_repository.py`

**Source file**: `src/repositories/instagram_account_repository.py` (149 lines)

**Create** `tests/src/repositories/test_instagram_account_repository.py`:

```python
"""Tests for InstagramAccountRepository."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from src.repositories.instagram_account_repository import InstagramAccountRepository
from src.models.instagram_account import InstagramAccount


@pytest.mark.unit
class TestInstagramAccountRepository:
    """Test suite for InstagramAccountRepository."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()

    @pytest.fixture
    def account_repo(self, mock_db):
        """Create InstagramAccountRepository with mocked database."""
        with patch("src.repositories.base_repository.get_db") as mock_get_db:
            mock_get_db.return_value = iter([mock_db])
            repo = InstagramAccountRepository()
            repo._db = mock_db
            return repo

    def test_get_all_active(self, account_repo, mock_db):
        """Test getting all active accounts."""
        mock_accounts = [
            Mock(display_name="Account A", is_active=True),
            Mock(display_name="Account B", is_active=True),
        ]
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_accounts

        result = account_repo.get_all_active()

        assert len(result) == 2
        mock_db.commit.assert_called_once()  # end_read_transaction

    def test_get_all_includes_inactive(self, account_repo, mock_db):
        """Test getting all accounts including inactive."""
        mock_accounts = [
            Mock(display_name="Active", is_active=True),
            Mock(display_name="Disabled", is_active=False),
        ]
        mock_db.query.return_value.order_by.return_value.all.return_value = (
            mock_accounts
        )

        result = account_repo.get_all()

        assert len(result) == 2

    def test_get_by_id(self, account_repo, mock_db):
        """Test getting account by UUID."""
        mock_account = Mock(id="acc-uuid-1")
        mock_db.query.return_value.filter.return_value.first.return_value = (
            mock_account
        )

        result = account_repo.get_by_id("acc-uuid-1")

        assert result is mock_account

    def test_get_by_username_strips_at(self, account_repo, mock_db):
        """Test that get_by_username strips leading @ from username."""
        mock_account = Mock(instagram_username="brand_main")
        mock_db.query.return_value.filter.return_value.first.return_value = (
            mock_account
        )

        result = account_repo.get_by_username("@brand_main")

        assert result is mock_account

    def test_get_by_instagram_id(self, account_repo, mock_db):
        """Test getting account by Instagram's external ID."""
        mock_account = Mock(instagram_account_id="17841234567890")
        mock_db.query.return_value.filter.return_value.first.return_value = (
            mock_account
        )

        result = account_repo.get_by_instagram_id("17841234567890")

        assert result is mock_account

    def test_create_strips_at_from_username(self, account_repo, mock_db):
        """Test that create strips @ from username."""
        account_repo.create(
            display_name="Test Account",
            instagram_account_id="123456",
            instagram_username="@test_user",
        )

        mock_db.add.assert_called_once()
        added_obj = mock_db.add.call_args[0][0]
        assert isinstance(added_obj, InstagramAccount)
        assert added_obj.instagram_username == "test_user"

    def test_update_account(self, account_repo, mock_db):
        """Test updating account fields."""
        mock_account = Mock(spec=InstagramAccount)
        mock_account.display_name = "Old Name"
        mock_db.query.return_value.filter.return_value.first.return_value = (
            mock_account
        )

        account_repo.update("acc-uuid-1", display_name="New Name")

        assert mock_account.display_name == "New Name"
        mock_db.commit.assert_called()

    def test_update_not_found_raises(self, account_repo, mock_db):
        """Test updating non-existent account raises ValueError."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError, match="not found"):
            account_repo.update("nonexistent", display_name="Test")

    def test_deactivate(self, account_repo, mock_db):
        """Test deactivating an account sets is_active=False."""
        mock_account = Mock(spec=InstagramAccount)
        mock_account.is_active = True
        mock_db.query.return_value.filter.return_value.first.return_value = (
            mock_account
        )

        account_repo.deactivate("acc-uuid-1")

        assert mock_account.is_active is False

    def test_activate(self, account_repo, mock_db):
        """Test activating a deactivated account."""
        mock_account = Mock(spec=InstagramAccount)
        mock_account.is_active = False
        mock_db.query.return_value.filter.return_value.first.return_value = (
            mock_account
        )

        account_repo.activate("acc-uuid-1")

        assert mock_account.is_active is True

    def test_count_active(self, account_repo, mock_db):
        """Test counting active accounts."""
        mock_db.query.return_value.filter.return_value.count.return_value = 3

        result = account_repo.count_active()

        assert result == 3

    def test_get_by_id_prefix(self, account_repo, mock_db):
        """Test getting account by ID prefix (shortened UUID)."""
        mock_account = Mock(id="abcdef12-3456-7890-abcd-ef1234567890")
        mock_db.query.return_value.filter.return_value.first.return_value = (
            mock_account
        )

        result = account_repo.get_by_id_prefix("abcdef12")

        assert result is mock_account
```

---

### Step 6: Create `tests/src/repositories/test_token_repository.py`

**Source file**: `src/repositories/token_repository.py` (235 lines)

**Create** `tests/src/repositories/test_token_repository.py`:

```python
"""Tests for TokenRepository."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta

from src.repositories.token_repository import TokenRepository
from src.models.api_token import ApiToken


@pytest.mark.unit
class TestTokenRepository:
    """Test suite for TokenRepository."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()

    @pytest.fixture
    def token_repo(self, mock_db):
        """Create TokenRepository with mocked database."""
        with patch("src.repositories.base_repository.get_db") as mock_get_db:
            mock_get_db.return_value = iter([mock_db])
            repo = TokenRepository()
            repo._db = mock_db
            return repo

    def test_get_token_found(self, token_repo, mock_db):
        """Test getting a token by service name and type."""
        mock_token = Mock(spec=ApiToken)
        mock_token.service_name = "instagram"
        mock_token.token_type = "access_token"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_token

        result = token_repo.get_token("instagram", "access_token")

        assert result is mock_token

    def test_get_token_not_found(self, token_repo, mock_db):
        """Test getting a non-existent token returns None."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = token_repo.get_token("instagram", "access_token")

        assert result is None

    def test_get_token_with_account_id(self, token_repo, mock_db):
        """Test getting a token filtered by account ID."""
        mock_token = Mock(spec=ApiToken)
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_token
        )

        result = token_repo.get_token(
            "instagram", "access_token", instagram_account_id="acc-uuid-1"
        )

        assert result is mock_token

    def test_get_token_for_account(self, token_repo, mock_db):
        """Test convenience method for getting Instagram token by account."""
        mock_token = Mock(spec=ApiToken)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_token

        result = token_repo.get_token_for_account("acc-uuid-1")

        assert result is mock_token

    def test_get_all_instagram_tokens(self, token_repo, mock_db):
        """Test getting all Instagram tokens for refresh iteration."""
        mock_tokens = [Mock(spec=ApiToken), Mock(spec=ApiToken)]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_tokens

        result = token_repo.get_all_instagram_tokens()

        assert len(result) == 2

    def test_create_or_update_creates_new_token(self, token_repo, mock_db):
        """Test create_or_update creates a new token when none exists."""
        # get_token returns None (no existing token)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        token_repo.create_or_update(
            service_name="instagram",
            token_type="access_token",
            token_value="encrypted_value",
            issued_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=60),
            scopes=["instagram_basic", "instagram_content_publish"],
            metadata={"method": "cli_wizard"},
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called()
        added_obj = mock_db.add.call_args[0][0]
        assert isinstance(added_obj, ApiToken)
        assert added_obj.service_name == "instagram"
        assert added_obj.token_value == "encrypted_value"

    def test_create_or_update_updates_existing_token(self, token_repo, mock_db):
        """Test create_or_update updates when token already exists."""
        existing_token = Mock(spec=ApiToken)
        existing_token.token_value = "old_encrypted"
        # First call to get_token finds existing
        mock_db.query.return_value.filter.return_value.first.return_value = (
            existing_token
        )

        token_repo.create_or_update(
            service_name="instagram",
            token_type="access_token",
            token_value="new_encrypted",
            expires_at=datetime.utcnow() + timedelta(days=60),
            scopes=["instagram_basic"],
        )

        # Should update existing, not add new
        mock_db.add.assert_not_called()
        assert existing_token.token_value == "new_encrypted"
        mock_db.commit.assert_called()

    def test_update_last_refreshed(self, token_repo, mock_db):
        """Test updating last_refreshed_at timestamp."""
        mock_token = Mock(spec=ApiToken)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_token

        result = token_repo.update_last_refreshed("instagram", "access_token")

        assert result is True
        assert mock_token.last_refreshed_at is not None
        mock_db.commit.assert_called()

    def test_update_last_refreshed_not_found(self, token_repo, mock_db):
        """Test update_last_refreshed returns False when token not found."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = token_repo.update_last_refreshed("instagram", "access_token")

        assert result is False

    def test_get_expiring_tokens(self, token_repo, mock_db):
        """Test getting tokens expiring within threshold."""
        mock_tokens = [Mock(spec=ApiToken)]
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
            mock_tokens
        )

        result = token_repo.get_expiring_tokens(hours_until_expiry=168)

        assert len(result) == 1

    def test_delete_token_found(self, token_repo, mock_db):
        """Test deleting an existing token."""
        mock_token = Mock(spec=ApiToken)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_token

        result = token_repo.delete_token("instagram", "access_token")

        assert result is True
        mock_db.delete.assert_called_once_with(mock_token)

    def test_delete_token_not_found(self, token_repo, mock_db):
        """Test deleting non-existent token returns False."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = token_repo.delete_token("instagram", "access_token")

        assert result is False

    def test_delete_all_for_service(self, token_repo, mock_db):
        """Test deleting all tokens for a service."""
        mock_db.query.return_value.filter.return_value.delete.return_value = 3

        result = token_repo.delete_all_for_service("instagram")

        assert result == 3
        mock_db.commit.assert_called()

    def test_get_expired_tokens(self, token_repo, mock_db):
        """Test getting all expired tokens."""
        mock_tokens = [Mock(spec=ApiToken)]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_tokens

        result = token_repo.get_expired_tokens()

        assert len(result) == 1
```

---

## Verification Checklist

After creating all test files, verify the following:

```bash
# 1. Check all test files exist
ls -la tests/src/services/test_telegram_autopost.py
ls -la tests/cli/test_instagram_commands.py
ls -la tests/src/repositories/test_base_repository.py
ls -la tests/src/repositories/test_chat_settings_repository.py
ls -la tests/src/repositories/test_instagram_account_repository.py
ls -la tests/src/repositories/test_token_repository.py

# 2. Run linting
ruff check tests/src/services/test_telegram_autopost.py
ruff check tests/cli/test_instagram_commands.py
ruff check tests/src/repositories/test_base_repository.py
ruff check tests/src/repositories/test_chat_settings_repository.py
ruff check tests/src/repositories/test_instagram_account_repository.py
ruff check tests/src/repositories/test_token_repository.py

# 3. Run formatting
ruff format tests/src/services/test_telegram_autopost.py
ruff format tests/cli/test_instagram_commands.py
ruff format tests/src/repositories/test_base_repository.py
ruff format tests/src/repositories/test_chat_settings_repository.py
ruff format tests/src/repositories/test_instagram_account_repository.py
ruff format tests/src/repositories/test_token_repository.py

# 4. Run all new tests
pytest tests/src/services/test_telegram_autopost.py -v
pytest tests/cli/test_instagram_commands.py -v
pytest tests/src/repositories/test_base_repository.py -v
pytest tests/src/repositories/test_chat_settings_repository.py -v
pytest tests/src/repositories/test_instagram_account_repository.py -v
pytest tests/src/repositories/test_token_repository.py -v

# 5. Run the full test suite to confirm no regressions
pytest

# 6. Check coverage improvement
pytest --cov=src --cov-report=term-missing
```

Each test file should have **all tests passing** (0 failures) and should add coverage for previously uncovered lines.

---

## What NOT To Do

1. **Do NOT create integration tests** in this phase. All tests here are unit tests with mocked dependencies. Integration tests (using a real database) are a separate effort.

2. **Do NOT modify any source code**. This phase only adds new test files. If a test reveals a bug, document it and file a separate issue.

3. **Do NOT test private methods** (methods starting with `_`) directly unless they contain critical business logic (like `_validate_ratios`). Test them indirectly through public methods.

4. **Do NOT use `test_db` fixture** for these tests. That fixture requires a running PostgreSQL instance. All tests here use `MagicMock` sessions injected via the `patch("src.repositories.base_repository.get_db")` pattern established in `test_category_mix_repository.py`.

5. **Do NOT test `instagram_auth` command** -- it requires interactive input (`click.prompt(hide_input=True)`) and browser interaction (`webbrowser.open`). That command needs a different testing approach (integration test or manual verification).

6. **Do NOT import directly from `src.services.core.telegram_autopost` at module level** in the test file. The `TelegramAutopostHandler` class imports `InstagramAPIService` and `CloudStorageService` lazily (inside methods), which is why we patch them inside the test methods using `with patch(...)` blocks.
