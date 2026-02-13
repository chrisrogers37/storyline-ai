# Phase 05: Convert Skipped CLI Tests to Unit Tests

**Status:** ✅ COMPLETE
**Started:** 2026-02-12
**Completed:** 2026-02-12
**PR Title:** `test: convert 17 skipped CLI tests to unit tests with mocked services`
**Risk Level:** Low (test-only changes)
**Estimated Effort:** 2-3 hours
**Files Modified:**
- `tests/cli/test_user_commands.py` (rewrite)
- `tests/cli/test_queue_commands.py` (rewrite)
- `tests/cli/test_media_commands.py` (rewrite)

## Dependencies
- None (independent)

## Blocks
- None

## Context

17 CLI tests across 3 files are all skipped with `@pytest.mark.skip(reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/")`. These tests were written as integration tests requiring a real database, but the CLI commands are thin wrappers around service classes — they should be tested with mocked services using Click's `CliRunner`.

The pattern to follow already exists in `tests/cli/test_instagram_commands.py`, which has 11 passing unit tests that mock service classes with `@patch` decorators and use `CliRunner` to invoke commands.

### Mocking Pattern Reference

```python
# PATTERN: Patch the class at the module where it's used (not where defined)
#
# If cli/commands/users.py has:
#     from src.repositories.user_repository import UserRepository
# Then patch at: "cli.commands.users.UserRepository"
#
# EXCEPTION: If the import is INSIDE the function body (lazy import):
#     def list_queue():
#         from src.repositories.media_repository import MediaRepository
# Then patch at source: "src.repositories.media_repository.MediaRepository"

@patch("cli.commands.users.UserRepository")
def test_example(self, mock_repo_class):
    mock_repo = mock_repo_class.return_value
    mock_repo.get_all.return_value = [...]

    runner = CliRunner()
    result = runner.invoke(command_function, [args])

    assert result.exit_code == 0
    assert "expected text" in result.output
```

## Implementation Steps

### Step 1: Convert test_user_commands.py (5 tests → 6 tests)

The `cli/commands/users.py` module uses `UserRepository` imported at module level.

**Replace the entire file with:**

```python
"""Tests for user CLI commands."""

import pytest
from unittest.mock import Mock, patch
from click.testing import CliRunner

from cli.commands.users import list_users, promote_user


@pytest.mark.unit
class TestListUsersCommand:
    """Tests for the list-users CLI command."""

    @patch("cli.commands.users.UserRepository")
    def test_list_users_shows_users(self, mock_repo_class):
        """Test list-users displays users in a table."""
        mock_repo = mock_repo_class.return_value

        mock_user = Mock()
        mock_user.telegram_username = "testuser"
        mock_user.telegram_user_id = 1000001
        mock_user.role = "admin"
        mock_user.total_posts = 42

        mock_repo.get_all.return_value = [mock_user]

        runner = CliRunner()
        result = runner.invoke(list_users, [])

        assert result.exit_code == 0
        assert "testuser" in result.output
        assert "admin" in result.output
        mock_repo.get_all.assert_called_once()

    @patch("cli.commands.users.UserRepository")
    def test_list_users_empty_database(self, mock_repo_class):
        """Test list-users shows message when no users found."""
        mock_repo = mock_repo_class.return_value
        mock_repo.get_all.return_value = []

        runner = CliRunner()
        result = runner.invoke(list_users, [])

        assert result.exit_code == 0
        assert "No users found" in result.output

    @patch("cli.commands.users.UserRepository")
    def test_list_users_without_username(self, mock_repo_class):
        """Test list-users shows telegram ID when username is None."""
        mock_repo = mock_repo_class.return_value

        mock_user = Mock()
        mock_user.telegram_username = None
        mock_user.telegram_user_id = 2000002
        mock_user.role = "member"
        mock_user.total_posts = 0

        mock_repo.get_all.return_value = [mock_user]

        runner = CliRunner()
        result = runner.invoke(list_users, [])

        assert result.exit_code == 0
        assert "2000002" in result.output


@pytest.mark.unit
class TestPromoteUserCommand:
    """Tests for the promote-user CLI command."""

    @patch("cli.commands.users.UserRepository")
    def test_promote_user_to_admin(self, mock_repo_class):
        """Test promote-user successfully promotes a user."""
        mock_repo = mock_repo_class.return_value

        mock_user = Mock()
        mock_user.id = "uuid-123"
        mock_user.telegram_username = "testuser"
        mock_user.role = "member"
        mock_repo.get_by_telegram_id.return_value = mock_user

        runner = CliRunner()
        result = runner.invoke(promote_user, ["3000003", "--role", "admin"])

        assert result.exit_code == 0
        mock_repo.get_by_telegram_id.assert_called_once_with(3000003)
        mock_repo.update_role.assert_called_once_with("uuid-123", "admin")

    @patch("cli.commands.users.UserRepository")
    def test_promote_user_nonexistent(self, mock_repo_class):
        """Test promote-user with non-existent user shows error."""
        mock_repo = mock_repo_class.return_value
        mock_repo.get_by_telegram_id.return_value = None

        runner = CliRunner()
        result = runner.invoke(promote_user, ["9999999", "--role", "admin"])

        assert result.exit_code != 0
        assert "User not found" in result.output
        mock_repo.update_role.assert_not_called()

    def test_promote_user_invalid_role(self):
        """Test promote-user with invalid role is rejected by Click."""
        runner = CliRunner()
        result = runner.invoke(promote_user, ["3000004", "--role", "superadmin"])

        assert result.exit_code == 2
        assert "Invalid value" in result.output or "invalid" in result.output.lower()
```

**Test mapping from old to new:**

| Old Test | New Test | Key Change |
|----------|----------|------------|
| `test_list_users_command` | `test_list_users_shows_users` | Mocks `UserRepository`, asserts output content |
| `test_list_users_empty_database` | `test_list_users_empty_database` | Mocks empty return, checks "No users found" |
| `test_promote_user_command` | `test_promote_user_to_admin` | Mocks repo, verifies `update_role` called |
| `test_promote_user_nonexistent` | `test_promote_user_nonexistent` | Mocks `get_by_telegram_id` returning None |
| `test_promote_user_invalid_role` | `test_promote_user_invalid_role` | No mock needed — Click validates choices |

**Added test:** `test_list_users_without_username` — tests the `ID:{telegram_user_id}` fallback branch (line 34 of `users.py`).

### Step 2: Convert test_queue_commands.py (5 tests → 7 tests)

The `cli/commands/queue.py` module uses:
- `SchedulerService` — module-level import, patch at `cli.commands.queue.SchedulerService`
- `PostingService` — module-level import, patch at `cli.commands.queue.PostingService`
- `QueueRepository` — module-level import, patch at `cli.commands.queue.QueueRepository`
- `MediaRepository` — **lazy import inside `list_queue()` function body**, patch at `src.repositories.media_repository.MediaRepository`

**Replace the entire file with:**

```python
"""Tests for queue CLI commands."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from click.testing import CliRunner

from cli.commands.queue import create_schedule, list_queue, process_queue


@pytest.mark.unit
class TestCreateScheduleCommand:
    """Tests for the create-schedule CLI command."""

    @patch("cli.commands.queue.SchedulerService")
    def test_create_schedule_success(self, mock_service_class):
        """Test create-schedule successfully creates a schedule."""
        mock_service = mock_service_class.return_value
        mock_service.create_schedule.return_value = {
            "scheduled": 6,
            "skipped": 0,
            "total_slots": 6,
            "category_breakdown": {"memes": 4, "merch": 2},
        }

        runner = CliRunner()
        result = runner.invoke(create_schedule, ["--days", "1"])

        assert result.exit_code == 0
        assert "Schedule created" in result.output
        assert "Scheduled: 6" in result.output
        mock_service.create_schedule.assert_called_once_with(days=1)

    @patch("cli.commands.queue.SchedulerService")
    def test_create_schedule_no_media(self, mock_service_class):
        """Test create-schedule when service raises exception due to no media."""
        mock_service = mock_service_class.return_value
        mock_service.create_schedule.side_effect = ValueError(
            "No eligible media items available"
        )

        runner = CliRunner()
        result = runner.invoke(create_schedule, ["--days", "1"])

        assert result.exit_code != 0
        assert "No eligible media" in result.output or "Error" in result.output

    @patch("cli.commands.queue.SchedulerService")
    def test_create_schedule_default_days(self, mock_service_class):
        """Test create-schedule uses default of 7 days."""
        mock_service = mock_service_class.return_value
        mock_service.create_schedule.return_value = {
            "scheduled": 21,
            "skipped": 0,
            "total_slots": 21,
        }

        runner = CliRunner()
        result = runner.invoke(create_schedule, [])

        assert result.exit_code == 0
        mock_service.create_schedule.assert_called_once_with(days=7)


@pytest.mark.unit
class TestListQueueCommand:
    """Tests for the list-queue CLI command."""

    @patch("src.repositories.media_repository.MediaRepository")
    @patch("cli.commands.queue.QueueRepository")
    def test_list_queue_shows_items(self, mock_queue_class, mock_media_class):
        """Test list-queue displays pending items in a table."""
        from datetime import datetime

        mock_queue_repo = mock_queue_class.return_value
        mock_media_repo = mock_media_class.return_value

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = "media-uuid-1"
        mock_queue_item.scheduled_for = datetime(2026, 2, 15, 10, 0)
        mock_queue_item.status = "pending"

        mock_queue_repo.get_all.return_value = [mock_queue_item]

        mock_media = Mock()
        mock_media.file_name = "queue_list.jpg"
        mock_media.category = "memes"
        mock_media_repo.get_by_id.return_value = mock_media

        runner = CliRunner()
        result = runner.invoke(list_queue, [])

        assert result.exit_code == 0
        assert "queue_list.jpg" in result.output
        assert "memes" in result.output
        assert "pending" in result.output
        mock_queue_repo.get_all.assert_called_once_with(status="pending")

    @patch("src.repositories.media_repository.MediaRepository")
    @patch("cli.commands.queue.QueueRepository")
    def test_list_queue_empty(self, mock_queue_class, mock_media_class):
        """Test list-queue shows message when queue is empty."""
        mock_queue_repo = mock_queue_class.return_value
        mock_queue_repo.get_all.return_value = []

        runner = CliRunner()
        result = runner.invoke(list_queue, [])

        assert result.exit_code == 0
        assert "Queue is empty" in result.output


@pytest.mark.unit
class TestProcessQueueCommand:
    """Tests for the process-queue CLI command."""

    @patch("cli.commands.queue.PostingService")
    def test_process_queue_success(self, mock_service_class):
        """Test process-queue processes pending items."""
        mock_service = mock_service_class.return_value
        mock_service.process_pending_posts = AsyncMock(
            return_value={
                "processed": 3,
                "telegram": 3,
                "failed": 0,
            }
        )

        runner = CliRunner()
        result = runner.invoke(process_queue, [])

        assert result.exit_code == 0
        assert "Processing complete" in result.output
        assert "Processed: 3" in result.output

    @patch("cli.commands.queue.PostingService")
    def test_process_queue_force(self, mock_service_class):
        """Test process-queue --force posts next item immediately."""
        mock_service = mock_service_class.return_value

        mock_media = Mock()
        mock_media.file_name = "force_post.jpg"

        mock_service.force_post_next = AsyncMock(
            return_value={
                "success": True,
                "media_item": mock_media,
                "queue_item_id": "queue-uuid-1",
                "shifted_count": 2,
            }
        )

        runner = CliRunner()
        result = runner.invoke(process_queue, ["--force"])

        assert result.exit_code == 0
        assert "Force-posted successfully" in result.output
        assert "force_post.jpg" in result.output
        assert "Shifted 2 items forward" in result.output
```

**Test mapping from old to new:**

| Old Test | New Test | Key Change |
|----------|----------|------------|
| `test_create_schedule_command` | `test_create_schedule_success` | Mocks `SchedulerService` |
| `test_create_schedule_no_media` | `test_create_schedule_no_media` | Service raises ValueError |
| `test_list_queue_command` | `test_list_queue_shows_items` | Mocks both repos |
| `test_list_queue_with_status_filter` | **Removed** — `list_queue` has no `--status` option. Replaced with `test_list_queue_empty` |
| `test_process_queue_command` | `test_process_queue_success` | Uses `AsyncMock` for async service |

**Added tests:** `test_create_schedule_default_days`, `test_process_queue_force`

### Step 3: Convert test_media_commands.py (7 tests → 11 tests)

The `cli/commands/media.py` module uses:
- `MediaIngestionService`, `MediaRepository`, `CategoryMixRepository` — module-level imports
- `ImageProcessor` — **lazy import inside `validate()` function body**, patch at `src.utils.image_processing.ImageProcessor`

Commands with `type=click.Path(exists=True)` reject non-existent paths with exit code 2 before any Python code runs — no mocking needed for those negative cases.

**Replace the entire file with:**

```python
"""Tests for media CLI commands."""

import pytest
from unittest.mock import Mock, patch
from click.testing import CliRunner

from cli.commands.media import index, list_media, validate


@pytest.mark.unit
class TestIndexMediaCommand:
    """Tests for the index-media CLI command."""

    @patch("cli.commands.media.CategoryMixRepository")
    @patch("cli.commands.media.MediaRepository")
    @patch("cli.commands.media.MediaIngestionService")
    def test_index_media_success(
        self, mock_service_class, mock_media_repo_class, mock_mix_repo_class
    ):
        """Test index-media indexes files from a directory."""
        import tempfile

        mock_service = mock_service_class.return_value
        mock_service.scan_directory.return_value = {
            "indexed": 3,
            "skipped": 1,
            "errors": 0,
            "categories": ["memes"],
        }

        mock_media_repo = mock_media_repo_class.return_value
        mock_media_repo.get_categories.return_value = ["memes"]

        mock_mix_repo = mock_mix_repo_class.return_value
        mock_mix_repo.has_current_mix.return_value = True
        mock_mix_repo.get_current_mix_as_dict.return_value = {"memes": 1.0}
        mock_mix_repo.get_categories_without_ratio.return_value = []

        mock_mix_entry = Mock()
        mock_mix_entry.category = "memes"
        mock_mix_entry.ratio = 1.0
        mock_mix_repo.get_current_mix.return_value = [mock_mix_entry]

        mock_media_repo.get_all.return_value = [Mock(), Mock(), Mock()]

        with tempfile.TemporaryDirectory() as temp_dir:
            runner = CliRunner()
            result = runner.invoke(index, [temp_dir], input="y\n")

        assert result.exit_code == 0
        assert "Indexing complete" in result.output
        assert "Indexed: 3" in result.output
        mock_service.scan_directory.assert_called_once()

    def test_index_media_nonexistent_directory(self):
        """Test index-media with non-existent directory is rejected by Click."""
        runner = CliRunner()
        result = runner.invoke(index, ["/nonexistent/path/that/does/not/exist"])

        assert result.exit_code == 2
        assert "does not exist" in result.output.lower() or "Error" in result.output

    @patch("cli.commands.media.CategoryMixRepository")
    @patch("cli.commands.media.MediaRepository")
    @patch("cli.commands.media.MediaIngestionService")
    def test_index_media_service_error(
        self, mock_service_class, mock_media_repo_class, mock_mix_repo_class
    ):
        """Test index-media handles service errors gracefully."""
        import tempfile

        mock_service = mock_service_class.return_value
        mock_service.scan_directory.side_effect = RuntimeError("Disk full")

        with tempfile.TemporaryDirectory() as temp_dir:
            runner = CliRunner()
            result = runner.invoke(index, [temp_dir])

        assert result.exit_code != 0
        assert "Error" in result.output


@pytest.mark.unit
class TestListMediaCommand:
    """Tests for the list-media CLI command."""

    @patch("cli.commands.media.MediaRepository")
    def test_list_media_shows_items(self, mock_repo_class):
        """Test list-media displays media items in a table."""
        from datetime import datetime

        mock_repo = mock_repo_class.return_value

        mock_item = Mock()
        mock_item.file_name = "list1.jpg"
        mock_item.category = "memes"
        mock_item.times_posted = 3
        mock_item.last_posted_at = datetime(2026, 2, 10)
        mock_item.is_active = True

        mock_repo.get_all.return_value = [mock_item]

        runner = CliRunner()
        result = runner.invoke(list_media, ["--limit", "10"])

        assert result.exit_code == 0
        assert "list1.jpg" in result.output
        assert "memes" in result.output
        mock_repo.get_all.assert_called_once_with(
            is_active=None, category=None, limit=10
        )

    @patch("cli.commands.media.MediaRepository")
    def test_list_media_empty(self, mock_repo_class):
        """Test list-media with no media shows empty message."""
        mock_repo = mock_repo_class.return_value
        mock_repo.get_all.return_value = []

        runner = CliRunner()
        result = runner.invoke(list_media, [])

        assert result.exit_code == 0
        assert "No media items found" in result.output

    @patch("cli.commands.media.MediaRepository")
    def test_list_media_with_category_filter(self, mock_repo_class):
        """Test list-media filters by category."""
        mock_repo = mock_repo_class.return_value

        mock_item = Mock()
        mock_item.file_name = "merch_item.jpg"
        mock_item.category = "merch"
        mock_item.times_posted = 0
        mock_item.last_posted_at = None
        mock_item.is_active = True

        mock_repo.get_all.return_value = [mock_item]

        runner = CliRunner()
        result = runner.invoke(list_media, ["--category", "merch"])

        assert result.exit_code == 0
        assert "merch" in result.output
        mock_repo.get_all.assert_called_once_with(
            is_active=None, category="merch", limit=20
        )

    @patch("cli.commands.media.MediaRepository")
    def test_list_media_active_only(self, mock_repo_class):
        """Test list-media with --active-only flag."""
        mock_repo = mock_repo_class.return_value
        mock_repo.get_all.return_value = []

        runner = CliRunner()
        result = runner.invoke(list_media, ["--active-only"])

        assert result.exit_code == 0
        mock_repo.get_all.assert_called_once_with(
            is_active=True, category=None, limit=20
        )


@pytest.mark.unit
class TestValidateImageCommand:
    """Tests for the validate-image CLI command."""

    @patch("src.utils.image_processing.ImageProcessor")
    def test_validate_image_valid(self, mock_processor_class):
        """Test validate-image with a valid image."""
        import tempfile
        from pathlib import Path

        mock_processor = mock_processor_class.return_value

        mock_result = Mock()
        mock_result.is_valid = True
        mock_result.errors = []
        mock_result.warnings = []
        mock_result.width = 1080
        mock_result.height = 1920
        mock_result.aspect_ratio = 0.5625
        mock_result.file_size_mb = 2.5
        mock_result.format = "JPEG"
        mock_processor.validate_image.return_value = mock_result

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "valid.jpg"
            test_file.write_bytes(b"fake image content")

            runner = CliRunner()
            result = runner.invoke(validate, [str(test_file)])

        assert result.exit_code == 0
        assert "Image is valid" in result.output
        assert "1080x1920" in result.output
        assert "JPEG" in result.output

    @patch("src.utils.image_processing.ImageProcessor")
    def test_validate_image_with_warnings(self, mock_processor_class):
        """Test validate-image with warnings (non-ideal aspect ratio)."""
        import tempfile
        from pathlib import Path

        mock_processor = mock_processor_class.return_value

        mock_result = Mock()
        mock_result.is_valid = True
        mock_result.errors = []
        mock_result.warnings = [
            "Non-ideal aspect ratio: 1.78. Instagram prefers 9:16 (0.56)"
        ]
        mock_result.width = 1920
        mock_result.height = 1080
        mock_result.aspect_ratio = 1.78
        mock_result.file_size_mb = 3.1
        mock_result.format = "JPEG"
        mock_processor.validate_image.return_value = mock_result

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "wide.jpg"
            test_file.write_bytes(b"fake image content")

            runner = CliRunner()
            result = runner.invoke(validate, [str(test_file)])

        assert result.exit_code == 0
        assert "Image is valid" in result.output
        assert "Warnings" in result.output
        assert "aspect ratio" in result.output.lower()

    @patch("src.utils.image_processing.ImageProcessor")
    def test_validate_image_with_errors(self, mock_processor_class):
        """Test validate-image with validation errors."""
        import tempfile
        from pathlib import Path

        mock_processor = mock_processor_class.return_value

        mock_result = Mock()
        mock_result.is_valid = False
        mock_result.errors = ["Unsupported format: BMP. Must be JPG, PNG, or GIF"]
        mock_result.warnings = []
        mock_result.width = 800
        mock_result.height = 600
        mock_result.aspect_ratio = 1.33
        mock_result.file_size_mb = 1.0
        mock_result.format = "BMP"
        mock_processor.validate_image.return_value = mock_result

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "invalid.bmp"
            test_file.write_bytes(b"fake image content")

            runner = CliRunner()
            result = runner.invoke(validate, [str(test_file)])

        assert result.exit_code == 0
        assert "has errors" in result.output
        assert "Unsupported format" in result.output

    def test_validate_image_nonexistent_file(self):
        """Test validate-image with non-existent file is rejected by Click."""
        runner = CliRunner()
        result = runner.invoke(validate, ["/nonexistent/image.jpg"])

        assert result.exit_code == 2
        assert (
            "does not exist" in result.output.lower()
            or "Error" in result.output
        )
```

**Test mapping from old to new:**

| Old Test | New Test | Key Change |
|----------|----------|------------|
| `test_index_media_command` | `test_index_media_success` | Mocks 3 classes, provides Confirm prompt input |
| `test_index_media_nonexistent_directory` | `test_index_media_nonexistent_directory` | No mock needed — Click rejects path |
| `test_list_media_command` | `test_list_media_shows_items` | Mocks `MediaRepository` |
| `test_list_media_with_filters` | `test_list_media_with_category_filter` | Changed from non-existent `--requires-interaction` to real `--category` |
| `test_validate_image_valid` | `test_validate_image_valid` | Mocks `ImageProcessor`, creates dummy file |
| `test_validate_image_invalid` | `test_validate_image_with_errors` | Mocks processor returning errors |
| `test_validate_image_nonexistent` | `test_validate_image_nonexistent_file` | No mock needed — Click rejects path |

**Added tests:** `test_index_media_service_error`, `test_list_media_empty`, `test_list_media_active_only`, `test_validate_image_with_warnings`

## Verification Checklist

- [x] All `@pytest.mark.skip` decorators removed
- [x] No test accepts a `test_db` fixture parameter
- [x] All tests use `@pytest.mark.unit` on their class
- [x] All mocks patch at the correct module path (where class is imported, not where defined)
- [x] CLI options match actual command signatures (no `--posts-per-day`, `--status`, `--requires-interaction`)
- [x] Tests for `process_queue` use `AsyncMock` for async service methods
- [x] Tests for `validate` and `index` create real temp files for `click.Path(exists=True)`
- [x] `ruff check tests/cli/` passes
- [x] `ruff format --check tests/cli/` passes
- [x] `pytest tests/cli/ -v` shows 0 skipped for the 3 modified files (24 passed)
- [x] `pytest` (full suite) passes (786 passed, 21 skipped)
- [x] No imports changed in any `cli/commands/` source files
- [x] CHANGELOG.md updated

## What NOT To Do

- **Do NOT modify any CLI source files** (`cli/commands/*.py`). This is a test-only change.
- **Do NOT create a shared conftest.py** for CLI tests. Each test file is self-contained with `@patch` decorators, matching the established pattern in `test_instagram_commands.py`.
- **Do NOT use `test_db` fixture** in any of the converted tests. The whole point is to eliminate the database dependency.
- **Do NOT test internal service logic** (e.g., whether the scheduler algorithm selects the right media). These are CLI tests — they test that the CLI correctly calls the service and formats the output.
- **Do NOT mock `click.CliRunner`**. Use it directly — it's a test utility, not a production dependency.
- **Do NOT use `monkeypatch`** when `@patch` decorators work fine. Stay consistent with the instagram test pattern.
- **Do NOT add new integration tests** in this phase. The goal is converting skipped tests to unit tests, not expanding test scope.
- **Do NOT keep any `@pytest.mark.skip` decorators**. Every test must either run or be deleted.
