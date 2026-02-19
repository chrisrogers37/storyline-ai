# Phase 05: `/status` Setup Completion Reporting + `/connect_drive` Cleanup

**Status**: 🔧 IN PROGRESS
**Started**: 2026-02-19

## Header

| Field | Value |
|-------|-------|
| **PR Title** | `feat: enhance /status with setup completion + remove /connect_drive` |
| **Risk Level** | Low |
| **Estimated Effort** | Small (1-2 hours) |
| **Branch Name** | `feature/onboarding-status-reporting` |

### Files Modified

| File | Action |
|------|--------|
| `src/services/core/telegram_commands.py` | Modified (enhance `/status`, add helper, remove `/connect_drive`) |
| `src/services/core/telegram_service.py` | Modified (remove `connect_drive` registration and BotCommand) |
| `tests/src/services/test_telegram_commands.py` | Modified (add `/status` setup tests, update `/connect_drive` tests) |
| `documentation/guides/cloud-deployment.md` | Modified (remove `/connect_drive` references) |
| `CHANGELOG.md` | Modified (new entry) |
| `CLAUDE.md` | Modified (update command reference table) |

### Files NOT Modified

| File | Reason |
|------|--------|
| `src/api/routes/oauth.py` | OAuth routes still used by Mini App wizard |
| `src/api/routes/onboarding.py` | Onboarding API unchanged |
| `src/services/integrations/google_drive_oauth.py` | Still used by Mini App |
| `src/services/core/telegram_settings.py` | Not related to this phase |
| `src/services/core/health_check.py` | We use service/repo calls directly, not HealthCheckService |

---

## Context

### Why enhance `/status`

The current `/status` command (lines 94-145 of `src/services/core/telegram_commands.py`) shows operational metrics -- queue counts, media library size, posting activity, pause state -- but gives the user zero indication of whether their tenant is **fully set up**. A user who just completed onboarding, or who is partially through it, has no quick way to see what is connected and what is missing.

The setup completion section will appear at the TOP of the `/status` response, before the existing operational sections. This gives users a dashboard-style "everything green" view or a clear indication of what still needs configuration.

### Why remove `/connect_drive`

The `/connect_drive` command (lines 1042-1083 of `src/services/core/telegram_commands.py`) was the original way to initiate Google Drive OAuth before the onboarding Mini App wizard was built. Now that Phases 02 and 03 of the onboarding plan provide Google Drive connection through the wizard, having a standalone command creates duplication:

- Two entry points for the same operation is confusing.
- The Mini App provides better UX (step-by-step flow, folder selection, validation).
- Removing the command reduces the command list length and guides users toward the wizard.

The underlying OAuth routes (`/auth/google-drive/start`, `/auth/google-drive/callback`) and `GoogleDriveOAuthService` remain intact -- they are invoked by the Mini App.

---

## Dependencies

| Phase | What it provides | Status |
|-------|-----------------|--------|
| Phase 01 | `media_source_type` and `media_source_root` columns on `chat_settings` | **Required** -- This phase must check whether a media folder is configured. If Phase 01 is not yet merged, the setup status check for "Media Folder" must use a fallback approach (check `MEDIA_SOURCE_ROOT` from env instead of per-chat settings). |
| Phase 02 | Completed onboarding wizard | Required -- The `/start` command already routes to it. `/connect_drive` removal makes sense only after the wizard handles Drive connections. |
| Phase 03 | Mini App home screen | Required -- After removing `/connect_drive`, the home screen is the only place to trigger Google Drive OAuth. |

**Phase 01 is merged**: The `media_source_root` column exists on `chat_settings`. The media folder check uses per-chat `chat_settings.media_source_root` directly — no global env fallback needed.

---

## Detailed Implementation Plan

### Step 1: Add `_get_setup_status` Helper Method to `TelegramCommandHandlers`

**File**: `/Users/chris/Projects/storyline-ai/src/services/core/telegram_commands.py`

**Location**: Insert after the existing status helper methods (after `_get_sync_status_line` which ends at line 210), before `handle_queue` at line 212.

**What to add**: A new private method that gathers all setup completeness information for a given chat. This method follows the exact same pattern as `_get_setup_state()` in `/Users/chris/Projects/storyline-ai/src/api/routes/onboarding.py` (lines 77-122), but returns formatted strings instead of raw dicts.

```python
def _get_setup_status(self, chat_id: int) -> str:
    """Build setup completion section for /status output.

    Each _check_* method returns (display_line, is_configured).
    Check failures count as "missing" to nudge users toward /start.
    """
    lines = ["*Setup Status:*"]
    checks = [
        self._check_instagram_setup(chat_id),
        self._check_gdrive_setup(chat_id),
        self._check_media_setup(chat_id),
        self._check_schedule_setup(chat_id),
        self._check_delivery_setup(chat_id),
    ]

    missing = 0
    for line_text, is_configured in checks:
        lines.append(line_text)
        if not is_configured:
            missing += 1

    if missing > 0:
        lines.append(f"\n_Use /start to configure missing items._")

    return "\n".join(lines)
```

**Key design decision**: Break the checks into individual private methods for testability. Each method returns `tuple[str, bool]` — the display line and whether the check passed. Check failures (DB errors) count as "missing" to nudge users toward `/start`.

### Step 2: Add Individual Setup Check Methods

**File**: `/Users/chris/Projects/storyline-ai/src/services/core/telegram_commands.py`

**Location**: Immediately after `_get_setup_status`.

```python
def _check_instagram_setup(self, chat_id: int) -> tuple[str, bool]:
    """Check Instagram account connection for setup status."""
    try:
        active_account = self.service.ig_account_service.get_active_account(chat_id)
        if active_account and active_account.instagram_username:
            return (f"├── 📸 Instagram: ✅ Connected (@{active_account.instagram_username})", True)
        elif active_account:
            return (f"├── 📸 Instagram: ✅ Connected ({active_account.display_name})", True)
        return ("├── 📸 Instagram: ⚠️ Not connected", False)
    except Exception:
        return ("├── 📸 Instagram: ❓ Check failed", False)

def _check_gdrive_setup(self, chat_id: int) -> tuple[str, bool]:
    """Check Google Drive OAuth connection for setup status.

    Reuses settings_service for chat_settings lookup; only creates
    TokenRepository for token check.
    """
    try:
        from src.repositories.token_repository import TokenRepository

        chat_settings = self.service.settings_service.get_settings(chat_id)
        if not chat_settings:
            return ("├── 📁 Google Drive: ⚠️ Not connected", False)

        token_repo = TokenRepository()
        try:
            gdrive_token = token_repo.get_token_for_chat(
                "google_drive", "oauth_access", str(chat_settings.id)
            )
            if gdrive_token:
                email = None
                if gdrive_token.token_metadata:
                    email = gdrive_token.token_metadata.get("email")
                if email:
                    return (f"├── 📁 Google Drive: ✅ Connected ({email})", True)
                return ("├── 📁 Google Drive: ✅ Connected", True)
            return ("├── 📁 Google Drive: ⚠️ Not connected", False)
        finally:
            token_repo.close()
    except Exception:
        return ("├── 📁 Google Drive: ❓ Check failed", False)

def _check_media_setup(self, chat_id: int) -> tuple[str, bool]:
    """Check media folder configuration and library size for setup status.

    Uses per-chat chat_settings.media_source_root (Phase 01 merged).
    """
    try:
        media_count = len(self.service.media_repo.get_all(is_active=True))
        if media_count > 0:
            return (f"├── 📂 Media Library: ✅ {media_count} files", True)

        # No media indexed -- check if source is configured (per-chat)
        chat_settings = self.service.settings_service.get_settings(chat_id)
        if chat_settings and chat_settings.media_source_root:
            return ("├── 📂 Media Library: ⚠️ Configured (0 files — run /sync)", False)
        return ("├── 📂 Media Library: ⚠️ Not configured", False)
    except Exception:
        return ("├── 📂 Media Library: ❓ Check failed", False)

def _check_schedule_setup(self, chat_id: int) -> tuple[str, bool]:
    """Check schedule configuration for setup status."""
    try:
        chat_settings = self.service.settings_service.get_settings(chat_id)
        ppd = chat_settings.posts_per_day
        start = chat_settings.posting_hours_start
        end = chat_settings.posting_hours_end
        return (f"├── 📅 Schedule: ✅ {ppd}/day, {start:02d}:00-{end:02d}:00 UTC", True)
    except Exception:
        return ("├── 📅 Schedule: ❓ Check failed", False)

def _check_delivery_setup(self, chat_id: int) -> tuple[str, bool]:
    """Check delivery mode (dry run / paused) for setup status."""
    try:
        chat_settings = self.service.settings_service.get_settings(chat_id)
        if chat_settings.is_paused:
            return ("└── 📦 Delivery: ⏸️ PAUSED", True)
        if chat_settings.dry_run_mode:
            return ("└── 📦 Delivery: 🧪 Dry Run (not posting)", True)
        return ("└── 📦 Delivery: ✅ Live", True)
    except Exception:
        return ("└── 📦 Delivery: ❓ Check failed", False)
```

**Why this structure**: Each check is isolated, catches its own exceptions, and returns a formatted string. This means one failing check does not crash the entire `/status` command. The pattern mirrors how `_get_sync_status_line` (lines 174-210) wraps everything in a `try/except` that returns a safe fallback string.

**Important**: The `_check_gdrive_setup` method reuses `self.service.settings_service.get_settings(chat_id)` for the chat_settings lookup (avoiding a second repo instantiation). It only creates a `TokenRepository` for the token check, with `try/finally` + `.close()` to ensure cleanup.

### Step 3: Modify `handle_status` to Include Setup Section

**File**: `/Users/chris/Projects/storyline-ai/src/services/core/telegram_commands.py`

**Current code** (lines 94-133):

The current `handle_status` builds a `status_msg` string with sections for System, Instagram API, Media Source, Queue & Media, and Activity.

**Change**: Insert the setup status section at the TOP of the message, before the existing "System" section.

Replace lines 113-131 (the `status_msg` string construction) with:

```python
        # Build setup status section (appears at top)
        setup_section = self._get_setup_status(chat_id)

        status_msg = (
            f"📊 *Storyline AI Status*\n\n"
            f"{setup_section}\n\n"
            f"*System:*\n"
            f"🤖 Bot: Online\n"
            f"⏯️ Posting: {pause_status}\n"
            f"🧪 Dry Run: {dry_run_status}\n\n"
            f"*Instagram API:*\n"
            f"📸 {ig_status}\n\n"
            f"*Media Source:*\n"
            f"{sync_status_line}\n\n"
            f"*Queue & Media:*\n"
            f"📋 Queue: {pending_count} pending\n"
            f"📁 Library: {media_count} active\n"
            f"🔒 Locked: {locked_count}\n\n"
            f"*Activity:*\n"
            f"⏰ Next: {next_post_str}\n"
            f"📤 Last: {last_posted}\n"
            f"📈 24h: {len(recent_posts)} posts"
        )
```

The only change is adding `f"{setup_section}\n\n"` between the header line and the "System" section.

### Step 4: Remove `handle_connect_drive` Method

**File**: `/Users/chris/Projects/storyline-ai/src/services/core/telegram_commands.py`

**Action**: Delete lines 1042-1083 (the entire `handle_connect_drive` method).

Specifically, remove:

```python
    async def handle_connect_drive(self, update, context):
        """Handle /connect_drive command - generate Google Drive OAuth link.
        ...
        """
        # ... entire method body ...
```

**Verification**: After deletion, the `handle_connect` method (lines 999-1040) should be the last method in the class. Make sure there is no dangling code or broken indentation.

### Step 5: Remove `connect_drive` from Command Registration

**File**: `/Users/chris/Projects/storyline-ai/src/services/core/telegram_service.py`

**Change 1** -- Remove from the `command_map` dict (lines 125-145):

Delete this line from the dict:
```python
            "connect_drive": self.commands.handle_connect_drive,
```

The `command_map` should go from 17 entries to 16 entries.

**Change 2** -- Remove from the BotCommand list (lines 159-179):

Delete this line:
```python
            BotCommand("connect_drive", "Connect your Google Drive for media"),
```

The commands list should go from 18 `BotCommand` entries to 17.

### Step 6: Update `/help` Text

**File**: `/Users/chris/Projects/storyline-ai/src/services/core/telegram_commands.py`

**Current `/help` text** (lines 325-350):

The current help text does not explicitly list `/connect_drive` (it was not added to `/help` in the first place). However, verify this is the case. Based on my reading of lines 325-350, `/connect_drive` is NOT in the help text already, so no change is needed for `/help`.

But verify: `/connect` (Instagram OAuth) IS also not listed in the help text. This is expected -- OAuth commands are triggered through the wizard, not manually. No changes needed to help text.

### Step 7: Update Tests

**File**: `/Users/chris/Projects/storyline-ai/tests/src/services/test_telegram_commands.py`

**7a. Update `TestConnectDriveCommand` class (lines 1374-1474)**

The existing `TestConnectDriveCommand` class has three tests. These tests need to be **replaced** with a new test class that verifies the command no longer exists.

Delete the entire `TestConnectDriveCommand` class (lines 1371-1474) and replace with:

```python
# ==================== /connect_drive Removal Tests ====================


@pytest.mark.unit
class TestConnectDriveRemoved:
    """Verify /connect_drive has been removed (replaced by onboarding wizard)."""

    def test_connect_drive_handler_not_present(self, mock_command_handlers):
        """Verify handle_connect_drive method no longer exists."""
        handlers = mock_command_handlers
        assert not hasattr(handlers, "handle_connect_drive")
```

**7b. Add setup status tests**

Add a new test class after the existing `TestStatusCommand` class (which is at line 1197). The new class tests the setup status helper and the individual check methods.

```python
@pytest.mark.unit
class TestSetupStatus:
    """Tests for the setup completion section in /status."""

    def test_instagram_connected(self, mock_command_handlers):
        """Test Instagram shows connected when active account exists."""
        handlers = mock_command_handlers
        mock_account = Mock()
        mock_account.instagram_username = "testshop"
        mock_account.display_name = "Test Shop"
        handlers.service.ig_account_service.get_active_account.return_value = (
            mock_account
        )

        line, ok = handlers._check_instagram_setup(-100123)
        assert "Connected" in line
        assert "@testshop" in line
        assert ok is True

    def test_instagram_not_connected(self, mock_command_handlers):
        """Test Instagram shows not connected when no active account."""
        handlers = mock_command_handlers
        handlers.service.ig_account_service.get_active_account.return_value = None

        line, ok = handlers._check_instagram_setup(-100123)
        assert "Not connected" in line
        assert ok is False

    def test_instagram_check_failure(self, mock_command_handlers):
        """Test Instagram check handles exceptions gracefully."""
        handlers = mock_command_handlers
        handlers.service.ig_account_service.get_active_account.side_effect = (
            Exception("DB error")
        )

        line, ok = handlers._check_instagram_setup(-100123)
        assert "Check failed" in line
        assert ok is False

    def test_media_library_with_files(self, mock_command_handlers):
        """Test media library shows file count when media is indexed."""
        handlers = mock_command_handlers
        handlers.service.media_repo.get_all.return_value = [Mock()] * 847

        line, ok = handlers._check_media_setup(-100123)
        assert "847 files" in line
        assert ok is True

    def test_media_library_no_files_source_configured(self, mock_command_handlers):
        """Test media library when source configured but no files synced."""
        handlers = mock_command_handlers
        handlers.service.media_repo.get_all.return_value = []
        handlers.service.settings_service.get_settings.return_value = Mock(
            media_source_root="some_folder_id"
        )

        line, ok = handlers._check_media_setup(-100123)
        assert "Configured" in line
        assert "0 files" in line
        assert ok is False

    def test_media_library_not_configured(self, mock_command_handlers):
        """Test media library when nothing is configured."""
        handlers = mock_command_handlers
        handlers.service.media_repo.get_all.return_value = []
        handlers.service.settings_service.get_settings.return_value = Mock(
            media_source_root=None
        )

        line, ok = handlers._check_media_setup(-100123)
        assert "Not configured" in line
        assert ok is False

    def test_schedule_configured(self, mock_command_handlers):
        """Test schedule shows configuration."""
        handlers = mock_command_handlers
        mock_settings = Mock(
            posts_per_day=3, posting_hours_start=14, posting_hours_end=2
        )
        handlers.service.settings_service.get_settings.return_value = mock_settings

        line, ok = handlers._check_schedule_setup(-100123)
        assert "3/day" in line
        assert "14:00-02:00 UTC" in line
        assert ok is True

    def test_delivery_live(self, mock_command_handlers):
        """Test delivery shows live when not paused and not dry run."""
        handlers = mock_command_handlers
        mock_settings = Mock(is_paused=False, dry_run_mode=False)
        handlers.service.settings_service.get_settings.return_value = mock_settings

        line, ok = handlers._check_delivery_setup(-100123)
        assert "Live" in line
        assert ok is True

    def test_delivery_dry_run(self, mock_command_handlers):
        """Test delivery shows dry run when enabled."""
        handlers = mock_command_handlers
        mock_settings = Mock(is_paused=False, dry_run_mode=True)
        handlers.service.settings_service.get_settings.return_value = mock_settings

        line, ok = handlers._check_delivery_setup(-100123)
        assert "Dry Run" in line
        assert ok is True

    def test_delivery_paused(self, mock_command_handlers):
        """Test delivery shows paused state."""
        handlers = mock_command_handlers
        mock_settings = Mock(is_paused=True, dry_run_mode=False)
        handlers.service.settings_service.get_settings.return_value = mock_settings

        line, ok = handlers._check_delivery_setup(-100123)
        assert "PAUSED" in line
        assert ok is True


@pytest.mark.unit
class TestSetupStatusGoogleDrive:
    """Tests for Google Drive check in setup status (needs repo mocking)."""

    def test_gdrive_connected_with_email(self, mock_command_handlers):
        """Test Google Drive shows connected with email."""
        handlers = mock_command_handlers

        mock_token = Mock()
        mock_token.token_metadata = {"email": "user@gmail.com"}

        mock_settings_obj = Mock()
        mock_settings_obj.id = "fake-uuid"
        handlers.service.settings_service.get_settings.return_value = mock_settings_obj

        with patch(
            "src.services.core.telegram_commands.TokenRepository"
        ) as MockTokenRepo:
            MockTokenRepo.return_value.get_token_for_chat.return_value = mock_token
            MockTokenRepo.return_value.close = Mock()

            line, ok = handlers._check_gdrive_setup(-100123)

        assert "Connected" in line
        assert "user@gmail.com" in line
        assert ok is True

    def test_gdrive_not_connected(self, mock_command_handlers):
        """Test Google Drive shows not connected when no token."""
        handlers = mock_command_handlers

        mock_settings_obj = Mock()
        mock_settings_obj.id = "fake-uuid"
        handlers.service.settings_service.get_settings.return_value = mock_settings_obj

        with patch(
            "src.services.core.telegram_commands.TokenRepository"
        ) as MockTokenRepo:
            MockTokenRepo.return_value.get_token_for_chat.return_value = None
            MockTokenRepo.return_value.close = Mock()

            line, ok = handlers._check_gdrive_setup(-100123)

        assert "Not connected" in line
        assert ok is False


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

        # Mock settings_service for setup checks (schedule, delivery, media, gdrive)
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
                side_effect=Exception("not configured"),
            ),
            patch(
                "src.services.core.telegram_commands.TokenRepository"
            ) as MockTokenRepo,
        ):
            mock_settings.DRY_RUN_MODE = False
            mock_settings.ENABLE_INSTAGRAM_API = False

            MockTokenRepo.return_value.get_token_for_chat.return_value = None
            MockTokenRepo.return_value.close = Mock()

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
```

### Step 8: Update Documentation

**8a. CHANGELOG.md**

Add under `## [Unreleased]`:

```markdown
### Changed
- **`/status` enhanced with setup completion reporting** - Now shows setup status at the top: Instagram connection, Google Drive connection, media library, schedule config, and delivery mode. Users with missing configuration see a hint to run `/start`.

### Removed
- **`/connect_drive` command removed** - Google Drive connection is now handled exclusively through the onboarding Mini App wizard (accessible via `/start`). The underlying OAuth routes remain unchanged.
```

**8b. CLAUDE.md**

In the "Telegram Bot Commands Reference" table, remove the `/connect_drive` row. The current CLAUDE.md does NOT list `/connect_drive` in its command reference table (I searched and found no match), so no change is needed there.

However, in the "Essential Commands" section near `storyline-cli connect_drive` or similar references, verify nothing needs removing. Based on my search, CLAUDE.md does not reference `connect_drive` at all, so no changes are needed.

**8c. `documentation/guides/cloud-deployment.md`**

Three references need updating:
1. Line 237: `connect_drive - Connect Google Drive` -- Remove this line from the command list.
2. Line 289: `1. User sends /connect_drive in Telegram (or uses the onboarding wizard)` -- Change to: `1. User connects Google Drive via the onboarding wizard (/start)`
3. Line 398: `13. [ ] Test Google Drive OAuth flow (via /connect_drive or wizard)` -- Change to: `13. [ ] Test Google Drive OAuth flow (via onboarding wizard)`

---

## Stress Testing and Edge Cases

### Edge Case 1: Partially Configured User (Instagram Only)

A user who connected Instagram but not Google Drive and has no media:

```
*Setup Status:*
├── 📸 Instagram: ✅ Connected (@shopname)
├── 📁 Google Drive: ⚠️ Not connected
├── 📂 Media Library: ⚠️ Not configured
├── 📅 Schedule: ✅ 3/day, 14:00-02:00 UTC
└── 📦 Delivery: 🧪 Dry Run (not posting)

_Use /start to configure missing items._
```

The hint line only appears when there is at least one unconfigured item.

### Edge Case 2: Brand New User (Nothing Configured)

```
*Setup Status:*
├── 📸 Instagram: ⚠️ Not connected
├── 📁 Google Drive: ⚠️ Not connected
├── 📂 Media Library: ⚠️ Not configured
├── 📅 Schedule: ✅ 3/day, 14:00-02:00 UTC
└── 📦 Delivery: 🧪 Dry Run (not posting)

_Use /start to configure missing items._
```

Note: Schedule always shows as "configured" because `chat_settings` has default values from `.env` bootstrap.

### Edge Case 3: Fully Configured User

```
*Setup Status:*
├── 📸 Instagram: ✅ Connected (@shopname)
├── 📁 Google Drive: ✅ Connected (user@gmail.com)
├── 📂 Media Library: ✅ 847 files
├── 📅 Schedule: ✅ 3/day, 14:00-02:00 UTC
└── 📦 Delivery: ✅ Live
```

No hint line appears when everything is green.

### Edge Case 4: Database Connection Failure During Setup Check

If any individual check fails (database down, token repo error), it shows the safe fallback:

```
├── 📸 Instagram: ❓ Check failed
```

This does NOT crash the `/status` command. The remaining checks continue.

### Edge Case 5: Instagram Account Without Username

Some accounts may have a `display_name` but no `instagram_username`:

```
├── 📸 Instagram: ✅ Connected (My Shop Account)
```

### Edge Case 6: Google Drive Token Without Email Metadata

OAuth tokens stored before the email field was added:

```
├── 📁 Google Drive: ✅ Connected
```

(No email shown, but still shows as connected.)

### Edge Case 7: Media Source Configured But Zero Files

User connected Google Drive and set folder, but has not run `/sync` yet:

```
├── 📂 Media Library: ⚠️ Configured (0 files — run /sync)
```

### Edge Case 8: User Sends `/connect_drive` After Removal

Telegram will not autocomplete it (removed from BotCommand list). If the user types it manually, Telegram bot framework simply ignores unregistered commands -- no handler is invoked, no error is shown.

---

## Missing Count Detection Logic

Each `_check_*` method returns `tuple[str, bool]` — the display line and whether the check passed. The parent `_get_setup_status` counts `False` values to decide whether to show the hint line.

**Design decisions (agreed in challenge round):**
- Check failures (DB errors returning "Check failed") count as "missing" → `False`
- "Dry Run" and "PAUSED" are valid delivery states → `True`
- Python 3.10 compatibility: use `from __future__ import annotations` (already present in file) for `tuple[str, bool]` type hints

---

## Verification Checklist

Before merging:

- [ ] `ruff check src/ tests/ cli/` passes with no errors
- [ ] `ruff format --check src/ tests/ cli/` passes
- [ ] `pytest` passes (all existing tests + new tests)
- [ ] `/connect_drive` handler method is deleted from `telegram_commands.py`
- [ ] `"connect_drive"` is removed from `command_map` in `telegram_service.py`
- [ ] `BotCommand("connect_drive", ...)` is removed from the commands list in `telegram_service.py`
- [ ] No import of `GoogleDriveOAuthService` remains in `telegram_commands.py`
- [ ] `handle_connect` (Instagram OAuth) is still present and unchanged
- [ ] `/status` output includes "Setup Status" section at the top
- [ ] Each setup check handles exceptions gracefully (returns "Check failed")
- [ ] Hint line ("Use /start...") only appears when something is unconfigured
- [ ] CHANGELOG.md updated under `## [Unreleased]`
- [ ] `documentation/guides/cloud-deployment.md` updated (3 references)
- [ ] OAuth routes in `src/api/routes/oauth.py` are untouched
- [ ] `GoogleDriveOAuthService` in `src/services/integrations/google_drive_oauth.py` is untouched
- [ ] `src/api/routes/onboarding.py` is untouched
- [ ] Test for `handle_connect_drive` not existing passes
- [ ] Tests for all five setup checks pass (connected, not connected, error cases)
- [ ] Test for `/status` including setup section passes

---

## What NOT To Do

1. **Do NOT remove `src/api/routes/oauth.py`** or any OAuth callback routes. The Mini App wizard still calls these routes to initiate and complete OAuth flows.

2. **Do NOT remove `src/services/integrations/google_drive_oauth.py`**. The `GoogleDriveOAuthService` is still used by the onboarding Mini App endpoints in `src/api/routes/onboarding.py` (line 164).

3. **Do NOT remove `src/services/integrations/google_drive.py`**. The Google Drive service/provider is used for media sync operations.

4. **Do NOT remove the `/connect` command** (Instagram OAuth). Only `/connect_drive` is being removed. The `/connect` command (lines 999-1040) remains as a standalone option for users who want to connect Instagram without going through the full wizard.

5. **Do NOT modify `src/api/routes/onboarding.py`**. The `_get_setup_state()` function there serves the Mini App and is separate from the Telegram bot `/status` output. Having two similar-looking functions is acceptable -- they serve different consumers (API JSON vs. Telegram Markdown).

6. **Do NOT add `HealthCheckService` as a dependency** for setup checks. The `HealthCheckService` checks operational health (database connectivity, sync freshness, token validity). Setup status is different -- it checks whether things are **configured**, not whether they are currently healthy. These are separate concerns.

7. **Do NOT use global `settings.MEDIA_SOURCE_ROOT`** for the media check. Phase 01 is merged — use per-chat `chat_settings.media_source_root` via `settings_service.get_settings(chat_id)`.

8. **Do NOT change the existing `handle_status` signature or return value**. The change is purely additive -- one new line in the message template.

9. **Do NOT create a separate `ChatSettingsRepository` in `_check_gdrive_setup`**. Reuse `self.service.settings_service.get_settings(chat_id)` for chat_settings — only create `TokenRepository` for the token lookup.

---

### Critical Files for Implementation
- `/Users/chris/Projects/storyline-ai/src/services/core/telegram_commands.py` - Core file: add setup status helpers, modify handle_status, remove handle_connect_drive
- `/Users/chris/Projects/storyline-ai/src/services/core/telegram_service.py` - Remove connect_drive from command_map and BotCommand registration
- `/Users/chris/Projects/storyline-ai/tests/src/services/test_telegram_commands.py` - Add setup status tests, replace connect_drive tests with removal verification
- `/Users/chris/Projects/storyline-ai/src/api/routes/onboarding.py` - Reference pattern: _get_setup_state() shows how to check Instagram/GDrive status (do NOT modify)
- `/Users/chris/Projects/storyline-ai/documentation/guides/cloud-deployment.md` - Update 3 references to /connect_drive