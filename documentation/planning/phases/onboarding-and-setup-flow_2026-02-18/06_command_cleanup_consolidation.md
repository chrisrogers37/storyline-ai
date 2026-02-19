# Phase 06: Command Audit, Cleanup & Consolidation

**PR Title:** `refactor: audit and consolidate Telegram bot commands into minimal daily-use set`
**Risk Level:** Medium (removing user-facing functionality)
**Estimated Effort:** Medium (4-6 hours)
**Depends On:** Phases 01-05 (all onboarding phases complete)

---

## Files Summary

### Files Modified
| File | Change Type | Summary |
|------|-------------|---------|
| `src/services/core/telegram_commands.py` | Heavy edit | Remove handler methods for removed commands; merge `/stats` data into `/status`; add deprecation replies for removed commands |
| `src/services/core/telegram_service.py` | Medium edit | Remove command registrations from `command_map`; update `BotCommand` list for autocomplete menu; remove callback dispatch entries if needed |
| `src/services/core/telegram_callbacks.py` | Minor edit | Remove `handle_reset_callback` if `/reset` is removed (and its `clear:` callback pattern) |
| `tests/src/services/test_telegram_commands.py` | Heavy edit | Remove test classes for removed commands; add tests for merged `/status` output; add tests for deprecation replies |
| `tests/src/services/test_telegram_callbacks.py` | Minor edit | Remove tests for `handle_reset_callback` if `/reset` removed |
| `tests/src/services/test_telegram_sync_command.py` | No change | `/sync` is kept |
| `CHANGELOG.md` | Minor edit | Add entry under `[Unreleased]` |
| `CLAUDE.md` | Medium edit | Update the Telegram Bot Commands Reference table and Callback Actions table |

### Files NOT Modified
| File | Reason |
|------|--------|
| `src/api/routes/*` | API routes are independent of bot commands |
| `src/services/core/posting_service.py` | Posting logic unchanged |
| `src/services/core/telegram_settings.py` | `/settings` / `/setup` handler stays as-is |
| `src/services/core/telegram_accounts.py` | Account handlers stay as-is |
| `src/services/core/telegram_autopost.py` | Autopost handler stays as-is |
| `src/services/core/telegram_utils.py` | Shared utilities stay (used by kept commands) |
| `src/models/*` | No schema changes |
| `cli/*` | CLI commands are completely separate from bot commands |
| `scripts/migrations/*` | No database changes |

### Files Created
None.

### Files Deleted
None. (Handler methods are removed from existing files, not deleted as whole files.)

---

## 1. Context

### Why This Phase Exists

After Phases 01-05 of the onboarding plan, the bot has accumulated a large command set -- 19 slash commands registered in the Telegram autocomplete menu (see `/Users/chris/Projects/storyline-ai/src/services/core/telegram_service.py` lines 159-179). Many of these commands predate the Mini App (Phase 03) and the `/settings` / `/setup` in-channel settings panel (Phase 04). Their functionality is now duplicated or accessible through better UIs.

The user explicitly stated a preference for keeping "some quick handy slash commands" -- the kind you can fire off in chat for an instant result. This phase trims the command set down to a focused, daily-use core.

### Guiding Principle

A command earns its place as a slash command if it meets ALL of these criteria:
1. It is used frequently (daily or weekly)
2. The result is quick and fits naturally in chat (a short text reply)
3. It is not a dangerous/destructive action
4. It is not already covered by the `/settings` panel or Mini App

---

## 2. Dependencies

This phase depends on ALL previous onboarding phases (01-05) being merged. Specifically:
- **Phase 03** introduced the Mini App, which absorbs setup and configuration flows
- **Phase 04** introduced `/settings` (aliased as `/setup`) with inline toggles for dry run, pause, Instagram API, verbose, media sync, schedule management, and posting hours
- **Phase 05** established the onboarding wizard with Google Drive and Instagram connection

Without these phases being complete, we cannot reason about which commands are redundant.

---

## 3. Command Audit Table

This is the core deliverable. **Before implementing, present this table to the user for approval.** The implementer MUST NOT remove commands until the user confirms the disposition.

| # | Command | Current Handler | Current Purpose | Disposition | Reasoning |
|---|---------|----------------|-----------------|-------------|-----------|
| 1 | `/start` | `telegram_commands.py:handle_start` (line 32) | Opens Mini App for new users; shows dashboard summary for returning users | **KEEP** | Essential entry point. Every Telegram bot needs `/start`. |
| 2 | `/status` | `telegram_commands.py:handle_status` (line 94) | Shows system health, queue count, media count, lock count, IG API status, sync status | **KEEP + ENHANCE** | Quick health check. Merge `/stats` media library data into this output. |
| 3 | `/help` | `telegram_commands.py:handle_help` (line 321) | Lists all available commands | **KEEP** | Standard bot convention. Update to show only the kept commands. |
| 4 | `/queue` | `telegram_commands.py:handle_queue` (line 212) | View pending scheduled posts (up to 10) | **KEEP** | Daily-use command. Shows what is coming up. Quick, useful, fits in chat. |
| 5 | `/next` | `telegram_commands.py:handle_next` (line 260) | Force-send next scheduled post immediately | **KEEP** | Power-user shortcut. Very handy for immediate posting. |
| 6 | `/pause` | `telegram_commands.py:handle_pause` (line 435) | Pause automatic posting | **KEEP** | Quick toggle. Also available in `/settings`, but slash command is faster when you need to stop posting urgently. |
| 7 | `/resume` | `telegram_commands.py:handle_resume` (line 465) | Resume automatic posting (with overdue detection) | **KEEP** | Companion to `/pause`. The overdue-post detection with inline buttons (reschedule/clear/force) is genuinely useful and cannot be replicated in `/settings`. |
| 8 | `/schedule N` | `telegram_commands.py:handle_schedule` (line 526) | Create N days of posting schedule | **REMOVE** | Redundant with `/settings` panel which has "Regenerate" and "+7 Days" buttons (see `telegram_settings.py` lines 102-108). Schedule creation is a setup action, not a daily action. |
| 9 | `/stats` | `telegram_commands.py:handle_stats` (line 577) | Media library statistics (total, never-posted, posted-once, posted-multiple, locks, queue) | **REMOVE (merge into /status)** | Overlaps heavily with `/status`. The unique data (never-posted, posted-once, posted-2+) can be added to `/status` under a "Library" section. |
| 10 | `/history N` | `telegram_commands.py:handle_history` (line 620) | Show recent post history | **REMOVE** | Low daily-use value. Better suited for Mini App dashboard or API. |
| 11 | `/locks` | `telegram_commands.py:handle_locks` (line 669) | View permanently rejected items | **REMOVE** | Very niche. Lock count is already shown in `/status`. Full lock list belongs in Mini App or admin dashboard. |
| 12 | `/reset` | `telegram_commands.py:handle_reset` (line 701) | Clear posting queue (with confirmation dialog) | **REMOVE** | Dangerous action. Already available in `/settings` as "Regenerate" (which clears + rebuilds). Removing as a casual slash command reduces accidental queue clears. |
| 13 | `/cleanup` | `telegram_commands.py:handle_cleanup` (line 739) | Delete recent bot messages from channel | **KEEP** | Unique utility with no equivalent in `/settings` or Mini App. Channel hygiene is a daily concern. |
| 14 | `/settings` | `telegram_settings.py:handle_settings` (line 114) | Show settings panel with toggle buttons | **KEEP (as alias for /setup)** | After Phase 04, `/settings` and `/setup` should point to the same handler. Keep both registered so users can use either name. |
| 15 | `/dryrun` | `telegram_commands.py:handle_dryrun` (line 363) | Toggle or check dry-run mode | **REMOVE** | Fully redundant with `/settings` toggle (see `telegram_settings.py` line 51: dry_run_mode toggle button). |
| 16 | `/sync` | `telegram_commands.py:handle_sync` (line 809) | Trigger manual media sync | **KEEP** | Handy shortcut. Shows live progress with message editing. Cannot be replicated in `/settings` because it requires async progress reporting. |
| 17 | `/backfill` | `telegram_commands.py:handle_backfill` (line 912) | Backfill media from Instagram | **REMOVE** | One-time migration utility. Should remain available via CLI (`storyline-cli backfill-instagram`) but not clutter the bot command menu. |
| 18 | `/connect` | `telegram_commands.py:handle_connect` (line 999) | Generate Instagram OAuth link | **REMOVE** | Handled by Mini App onboarding wizard (Phase 03/05). OAuth connection should go through the wizard, not a standalone command. |
| 19 | `/connect_drive` | `telegram_commands.py:handle_connect_drive` (line 1042) | Generate Google Drive OAuth link | **REMOVE** | Same reasoning as `/connect`. Mini App handles this. |

### Summary

| Disposition | Count | Commands |
|-------------|-------|----------|
| **KEEP** | 10 | `/start`, `/status`, `/help`, `/queue`, `/next`, `/pause`, `/resume`, `/cleanup`, `/settings`, `/sync` |
| **REMOVE** | 9 | `/schedule`, `/stats`, `/history`, `/locks`, `/reset`, `/dryrun`, `/backfill`, `/connect`, `/connect_drive` |

---

## 4. Detailed Implementation Plan

### Step 1: Get User Approval on the Audit Table (CRITICAL)

Before writing any code, present the audit table from Section 3 to the user. The user said they want "some quick handy slash commands." They may disagree with specific removals. Do NOT proceed until the user confirms the disposition of each command.

### Step 2: Merge `/stats` Data into `/status`

**File:** `/Users/chris/Projects/storyline-ai/src/services/core/telegram_commands.py`

The current `/status` handler (line 94) already shows:
- Queue count, media count, lock count
- Next post time, last posted time, 24h post count
- Dry run status, pause status, IG API status, sync status

The `/stats` handler (line 577) adds these unique data points:
- Never posted count
- Posted once count
- Posted 2+ count
- Temporary lock count (distinct from permanent)

**What to do:** Add a "Library Breakdown" subsection to the `/status` output. The implementation should:

1. In `handle_status`, after the existing `media_count = len(self.service.media_repo.get_all(is_active=True))` on line 102, compute the additional stats:

```python
# Compute library breakdown (merged from former /stats command)
all_media = self.service.media_repo.get_all(is_active=True)
media_count = len(all_media)
never_posted = len([m for m in all_media if m.times_posted == 0])
posted_once = len([m for m in all_media if m.times_posted == 1])
posted_multiple = len([m for m in all_media if m.times_posted > 1])
```

Note: this replaces the current `media_count = len(self.service.media_repo.get_all(is_active=True))` on line 102 since we need to iterate the list anyway.

2. Update the status message string to include the breakdown. Add after the "Queue & Media" section:

```python
f"*Library:*\n"
f"📁 Total: {media_count} active\n"
f"🆕 Never posted: {never_posted}\n"
f"1️⃣ Posted once: {posted_once}\n"
f"🔁 Posted 2+: {posted_multiple}\n\n"
```

This replaces the single `f"📁 Library: {media_count} active\n"` line currently at line 126.

### Step 3: Remove Handler Methods for Removed Commands

**File:** `/Users/chris/Projects/storyline-ai/src/services/core/telegram_commands.py`

Delete the following methods entirely:
- `handle_schedule` (lines 526-575) -- schedule creation is in `/settings` panel
- `handle_stats` (lines 577-618) -- merged into `/status`
- `handle_history` (lines 620-667) -- moved to Mini App / API
- `handle_locks` (lines 669-698) -- moved to Mini App / API
- `handle_reset` (lines 701-737) -- available in `/settings` as "Regenerate"
- `handle_dryrun` (lines 363-433) -- available in `/settings` toggle
- `handle_backfill` (lines 912-997) -- CLI-only utility
- `handle_connect` (lines 999-1040) -- Mini App handles OAuth
- `handle_connect_drive` (lines 1042-1083) -- Mini App handles OAuth

Also remove the `MAX_LOCKS_DISPLAY = 10` class constant (line 27) since it was only used by `handle_locks`.

### Step 4: Add Deprecation Replies for Removed Commands

Rather than silently ignoring removed commands (which would confuse users with muscle memory), add a small `handle_removed_command` method that responds with a helpful redirect message:

```python
async def handle_removed_command(self, update, context):
    """Handle removed commands with a helpful redirect message."""
    command = update.message.text.split()[0].split("@")[0]  # Extract /command

    redirects = {
        "/schedule": "Use /settings to manage your posting schedule (Regenerate / +7 Days).",
        "/stats": "Media stats are now included in /status.",
        "/history": "Post history is available in the Storyline dashboard.",
        "/locks": "Lock count is shown in /status. Full list in the dashboard.",
        "/reset": "Use /settings → Regenerate to rebuild your queue.",
        "/dryrun": "Use /settings to toggle dry-run mode.",
        "/backfill": "Use the CLI: storyline-cli backfill-instagram",
        "/connect": "Use /start to open the setup wizard and connect Instagram.",
        "/connect_drive": "Use /start to open the setup wizard and connect Google Drive.",
    }

    message = redirects.get(command, "This command has been removed.")
    await update.message.reply_text(
        f"ℹ️ `{command}` has been retired.\n\n{message}",
        parse_mode="Markdown",
    )
```

This is a single method that handles ALL removed commands by looking up the command name in a dictionary. Users get a clear redirect instead of silence.

### Step 5: Update Command Registration in `telegram_service.py`

**File:** `/Users/chris/Projects/storyline-ai/src/services/core/telegram_service.py`

#### 5a. Update `command_map` (lines 125-145)

Change the `command_map` dictionary in the `initialize()` method. The new map should look like:

```python
command_map = {
    # Active commands
    "start": self.commands.handle_start,
    "status": self.commands.handle_status,
    "queue": self.commands.handle_queue,
    "next": self.commands.handle_next,
    "pause": self.commands.handle_pause,
    "resume": self.commands.handle_resume,
    "cleanup": self.commands.handle_cleanup,
    "help": self.commands.handle_help,
    "sync": self.commands.handle_sync,
    "settings": self.settings_handler.handle_settings,
    "setup": self.settings_handler.handle_settings,  # Alias
    # Retired commands (show helpful redirect)
    "schedule": self.commands.handle_removed_command,
    "stats": self.commands.handle_removed_command,
    "history": self.commands.handle_removed_command,
    "locks": self.commands.handle_removed_command,
    "reset": self.commands.handle_removed_command,
    "dryrun": self.commands.handle_removed_command,
    "backfill": self.commands.handle_removed_command,
    "connect": self.commands.handle_removed_command,
    "connect_drive": self.commands.handle_removed_command,
}
```

Key points:
- `/setup` is added as an alias for `/settings` (both point to `self.settings_handler.handle_settings`)
- All removed commands still have a handler registration -- they point to `handle_removed_command` so users get a helpful message instead of Telegram ignoring the command
- This means Telegram will still autocomplete these commands unless we remove them from the `BotCommand` list (next step)

#### 5b. Update `BotCommand` list (lines 159-179)

Replace the current 19-item BotCommand list with only the 10 kept commands:

```python
commands = [
    BotCommand("start", "Open Storyline (setup & config)"),
    BotCommand("status", "System health & media overview"),
    BotCommand("setup", "Quick settings & toggles"),
    BotCommand("queue", "View upcoming posts"),
    BotCommand("next", "Send next post now"),
    BotCommand("pause", "Pause delivery"),
    BotCommand("resume", "Resume delivery"),
    BotCommand("sync", "Sync media from Drive"),
    BotCommand("cleanup", "Delete recent bot messages"),
    BotCommand("help", "Show available commands"),
]
```

Note: `/settings` is NOT listed as a BotCommand because `/setup` is the user-facing name (per Phase 04). But `/settings` still works because it is registered in `command_map`. Users who type `/settings` will get the settings panel; it just will not appear in autocomplete.

#### 5c. Remove `clear` callback dispatch entry

In the `_build_callback_dispatch_table` method (line 184), the entry `"clear": self.callbacks.handle_reset_callback` should be kept IF we keep the `/reset` command, or removed if we remove `/reset`.

**Decision:** Even after removing `/reset` as a slash command, existing queue item messages in chat history may have "Clear" callback buttons from the `/resume` overdue handling. The `resume` callbacks emit `resume:reschedule`, `resume:clear`, `resume:force` -- these route through `handle_resume_callback`, NOT `handle_reset_callback`. The `clear:confirm` / `clear:cancel` pattern is ONLY created by `/reset`. Since we are removing `/reset`, there is a brief window where old `/reset` confirmation messages still in chat could have stale buttons. We should keep the `"clear"` callback dispatch entry for backward compatibility and remove it in a future cleanup.

### Step 6: Update `/help` Output

**File:** `/Users/chris/Projects/storyline-ai/src/services/core/telegram_commands.py`

Replace the `handle_help` method's `help_text` string (lines 325-351) with:

```python
help_text = (
    "📖 *Storyline AI Help*\n\n"
    "*Daily Commands:*\n"
    "/queue - View upcoming posts\n"
    "/next - Send next post now\n"
    "/status - System health & overview\n\n"
    "*Control Commands:*\n"
    "/pause - Pause delivery\n"
    "/resume - Resume delivery\n"
    "/setup - Quick settings & toggles\n"
    "/sync - Sync media from source\n"
    "/cleanup - Delete recent bot messages\n\n"
    "*Getting Started:*\n"
    "/start - Open setup wizard\n"
    "/help - Show this help\n\n"
    "*Button Actions:*\n"
    "🤖 Auto Post - Post via Instagram API\n"
    "✅ Posted - Mark as posted (manual)\n"
    "⏭️ Skip - Skip (requeue later)\n"
    "🚫 Reject - Permanently remove"
)
```

### Step 7: Clean Up Unused Imports

**File:** `/Users/chris/Projects/storyline-ai/src/services/core/telegram_commands.py`

After removing handler methods, check for unused imports. Current imports at the top of the file (lines 1-17):

```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from src.config.settings import settings
from src.services.core.telegram_service import _escape_markdown
from src.utils.logger import logger
from datetime import datetime
import asyncio
```

After removals:
- `InlineKeyboardButton` -- still needed by `handle_resume` (for overdue options)
- `InlineKeyboardMarkup` -- still needed by `handle_resume` and `handle_start`
- `WebAppInfo` -- still needed by `handle_start`
- `_escape_markdown` -- still needed by `handle_queue`
- `settings` -- still needed by `handle_status`, `handle_sync`
- `logger` -- still needed by multiple handlers
- `datetime` -- still needed by `handle_resume`, `handle_status`
- `asyncio` -- was only needed by `handle_cleanup` (the `asyncio.sleep(5)` on line 802). If `/cleanup` is kept, `asyncio` stays.

All current imports remain needed. No cleanup required.

### Step 8: Remove Dead Callback Handlers (conditional)

**File:** `/Users/chris/Projects/storyline-ai/src/services/core/telegram_callbacks.py`

If `/reset` is removed:
- The `handle_reset_callback` method (lines 445-478) becomes reachable ONLY through old stale messages. Keep it for backward compatibility (see Step 5c reasoning).
- Do NOT remove it in this phase. Mark it with a comment: `# Legacy: kept for backward compat with old /reset confirmation messages`

No other callback handlers are affected by command removals. All callback patterns (`posted:`, `skip:`, `reject:`, `confirm_reject:`, `cancel_reject:`, `autopost:`, `resume:`, `settings_toggle:`, `schedule_action:`, `schedule_confirm:`, `switch_account:`, `account_remove:`, `select_account:`, `sap:`, `btp:`) are used by KEPT commands or by the inline notification buttons, not by removed commands.

---

## 5. Test Plan

### Tests to Remove

**File:** `/Users/chris/Projects/storyline-ai/tests/src/services/test_telegram_commands.py`

Remove these entire test classes:
- `TestScheduleCommand` (lines 638-716) -- `/schedule` removed
- `TestStatsCommand` (lines 718-767) -- `/stats` removed
- `TestHistoryCommand` (lines 770-847) -- `/history` removed
- `TestLocksCommand` (lines 850-925) -- `/locks` removed
- `TestResetCommand` (lines 928-989) -- `/reset` removed
- `TestConnectCommand` (lines 1273-1368) -- `/connect` removed
- `TestConnectDriveCommand` (lines 1374-1474) -- `/connect_drive` removed

These test classes at lines 718-989 total roughly 270 lines. The connect tests at lines 1273-1474 total roughly 200 lines. Total lines removed from this file: approximately 470 lines.

### Tests to Update

**File:** `/Users/chris/Projects/storyline-ai/tests/src/services/test_telegram_commands.py`

1. **Update `TestStatusCommand`** (line 1197): Add assertions for the merged `/stats` data. The existing test at line 1202 (`test_sends_formatted_status_message`) should verify that the new "Library" section is present in the output. Add a new test:

```python
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
    mock_update.effective_user = Mock(id=123, username="test", first_name="Test", last_name=None)
    mock_update.effective_chat = Mock(id=-100123)
    mock_update.message = AsyncMock()
    mock_update.message.message_id = 1

    with (
        patch("src.services.core.telegram_commands.settings") as mock_settings,
        patch("src.services.core.media_sync.MediaSyncService", side_effect=Exception("n/a")),
    ):
        mock_settings.DRY_RUN_MODE = False
        mock_settings.ENABLE_INSTAGRAM_API = False
        await handlers.handle_status(mock_update, Mock())

    msg = mock_update.message.reply_text.call_args.args[0]
    assert "Never posted: 1" in msg
    assert "Posted once: 1" in msg
    assert "Posted 2+: 1" in msg
```

### Tests to Add

**File:** `/Users/chris/Projects/storyline-ai/tests/src/services/test_telegram_commands.py`

Add a new test class for the deprecation handler:

```python
@pytest.mark.unit
@pytest.mark.asyncio
class TestRemovedCommandRedirects:
    """Tests for removed command deprecation messages."""

    @pytest.mark.parametrize("command,expected_text", [
        ("/schedule", "/settings"),
        ("/stats", "/status"),
        ("/history", "dashboard"),
        ("/locks", "/status"),
        ("/reset", "/settings"),
        ("/dryrun", "/settings"),
        ("/backfill", "CLI"),
        ("/connect", "/start"),
        ("/connect_drive", "/start"),
    ])
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
```

### Tests NOT to Modify

- `/Users/chris/Projects/storyline-ai/tests/src/services/test_telegram_service.py` -- Tests for `_get_display_name`, `_build_caption`, callback routing, profile sync, verbose mode, and inline account selector are all unaffected.
- `/Users/chris/Projects/storyline-ai/tests/src/services/test_telegram_callbacks.py` -- All callback tests remain valid. The `handle_reset_callback` tests should be kept since we are keeping the callback handler for backward compatibility.
- `/Users/chris/Projects/storyline-ai/tests/src/services/test_telegram_sync_command.py` -- `/sync` is kept, no changes.
- `/Users/chris/Projects/storyline-ai/tests/src/services/test_telegram_settings.py` -- `/settings` is kept, no changes.
- `/Users/chris/Projects/storyline-ai/tests/src/services/test_telegram_accounts.py` -- Account handlers are kept, no changes.
- `/Users/chris/Projects/storyline-ai/tests/src/services/test_telegram_autopost.py` -- Autopost handler is kept, no changes.
- `/Users/chris/Projects/storyline-ai/tests/src/services/test_telegram_utils.py` -- Shared utilities are kept, no changes.

---

## 6. Documentation Updates

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Changed

- **Telegram command cleanup** - Consolidated bot commands from 19 to 10 for a cleaner daily experience
  - **Kept:** `/start`, `/status`, `/help`, `/queue`, `/next`, `/pause`, `/resume`, `/cleanup`, `/settings` (alias: `/setup`), `/sync`
  - **Removed:** `/schedule`, `/stats`, `/history`, `/locks`, `/reset`, `/dryrun`, `/backfill`, `/connect`, `/connect_drive`
  - Removed commands show a helpful redirect message (e.g., "Use /settings to toggle dry-run mode")
  - `/stats` media breakdown (never-posted, posted-once, posted-2+) merged into `/status` output
  - Schedule management remains available via `/settings` panel (Regenerate / +7 Days buttons)
  - OAuth connections remain available via `/start` setup wizard
  - `/backfill` remains available via CLI (`storyline-cli backfill-instagram`)
```

### CLAUDE.md Updates

**Section: Telegram Bot Commands Reference** (the large table)

Replace the current command table with:

| Command | Description | Handler Module |
|---------|-------------|----------------|
| `/start` | Open setup wizard or show dashboard | `telegram_commands.py` |
| `/status` | System health, media stats, queue status | `telegram_commands.py` |
| `/help` | Show available commands | `telegram_commands.py` |
| `/queue` | View pending scheduled posts | `telegram_commands.py` |
| `/next` | Force-send next scheduled post | `telegram_commands.py` |
| `/pause` | Pause automatic posting | `telegram_commands.py` |
| `/resume` | Resume posting | `telegram_commands.py` |
| `/cleanup` | Delete recent bot messages | `telegram_commands.py` |
| `/settings` | Configure bot settings (alias: `/setup`) | `telegram_settings.py` |
| `/sync` | Trigger manual media sync | `telegram_commands.py` |

Add a note below the table:

> **Retired commands:** `/schedule`, `/stats`, `/history`, `/locks`, `/reset`, `/dryrun`, `/backfill`, `/connect`, `/connect_drive` still respond with a helpful redirect message but are not listed in the bot menu. Their functionality is available through `/settings`, `/status`, `/start` (setup wizard), or the CLI.

**Section: Telegram Callback Actions**

Remove the row for `clear:confirm` / `clear:cancel` or mark it as legacy. The `/resume` callbacks (`resume:reschedule`, `resume:clear`, `resume:force`) remain active and should be documented.

---

## 7. Stress Testing & Edge Cases

### 7a. Muscle Memory for Removed Commands

Users who have typed `/schedule 7` for months will try it again. The `handle_removed_command` method handles this gracefully by replying with a redirect message. This is significantly better than:
- Silence (Telegram ignores unregistered commands)
- An error message with no guidance

The redirect messages are specific per command (see the `redirects` dict in Step 4), so the user immediately knows where to go.

### 7b. Bot Menu Autocomplete

After the `BotCommand` list is updated (Step 5b), Telegram's command menu will only show 10 commands. However, the old menu may be cached on user devices for up to 24 hours. This is normal Telegram behavior and requires no workaround.

### 7c. Stale Inline Buttons from `/reset`

If a user previously typed `/reset` and got a confirmation dialog ("Yes, Clear All" / "Cancel"), those buttons will still exist in the chat history. The callback data is `clear:confirm` and `clear:cancel`. Since we keep `handle_reset_callback` in the callback dispatch table (Step 5c), these stale buttons will still work. This is correct behavior.

### 7d. Stale Inline Buttons from `/resume`

The `/resume` command creates inline buttons (`resume:reschedule`, `resume:clear`, `resume:force`). Since `/resume` is KEPT, this is not an issue. These buttons continue to work.

### 7e. `/setup` Alias

After this phase, both `/settings` and `/setup` work. Only `/setup` appears in the autocomplete menu. This is intentional -- `/setup` is the user-facing name going forward, but `/settings` is kept for backward compatibility.

### 7f. Race Condition: Commands Sent During Deployment

If a user sends a removed command exactly during deployment (between the old version shutting down and the new version starting), Telegram queues the update. On restart, the new bot processes it. Since the removed commands are still registered (pointing to `handle_removed_command`), the user gets a redirect message. No race condition.

---

## 8. Verification Checklist

After implementation, manually verify each of these:

### Kept Commands (must work)
- [ ] `/start` -- New user sees Mini App button; returning user sees dashboard
- [ ] `/status` -- Shows all sections including new "Library" breakdown (never-posted, posted-once, posted-2+ counts)
- [ ] `/help` -- Shows only the 10 kept commands
- [ ] `/queue` -- Shows upcoming posts (up to 10)
- [ ] `/next` -- Force-sends next post
- [ ] `/pause` -- Pauses posting; shows "already paused" if re-run
- [ ] `/resume` -- Resumes posting; shows overdue options if applicable
- [ ] `/cleanup` -- Deletes recent bot messages; self-deletes confirmation
- [ ] `/settings` -- Shows settings panel with toggle buttons
- [ ] `/setup` -- Same as `/settings` (alias)
- [ ] `/sync` -- Triggers media sync; shows progress

### Removed Commands (must show redirect)
- [ ] `/schedule 7` -- Shows redirect to `/settings`
- [ ] `/stats` -- Shows redirect to `/status`
- [ ] `/history 5` -- Shows redirect to dashboard
- [ ] `/locks` -- Shows redirect to `/status`
- [ ] `/reset` -- Shows redirect to `/settings`
- [ ] `/dryrun` -- Shows redirect to `/settings`
- [ ] `/dryrun on` -- Shows redirect to `/settings` (not crash on args)
- [ ] `/backfill` -- Shows redirect to CLI
- [ ] `/connect` -- Shows redirect to `/start`
- [ ] `/connect_drive` -- Shows redirect to `/start`

### Bot Menu
- [ ] Telegram autocomplete shows exactly 10 commands (start, status, setup, queue, next, pause, resume, sync, cleanup, help)
- [ ] No removed commands appear in autocomplete

### Callback Buttons (must still work)
- [ ] "Posted" / "Skip" / "Reject" buttons on queue notifications work
- [ ] "Auto Post" button works (if Instagram API enabled)
- [ ] Account selector button works
- [ ] Settings toggle buttons work (from `/settings`)
- [ ] Regenerate / +7 Days buttons work (from `/settings`)
- [ ] Old `/reset` "Clear All" / "Cancel" buttons still work (if any exist in chat)

### Tests
- [ ] `pytest tests/src/services/test_telegram_commands.py` passes
- [ ] `pytest tests/src/services/test_telegram_callbacks.py` passes
- [ ] `pytest tests/src/services/test_telegram_service.py` passes
- [ ] Full suite: `pytest` passes
- [ ] Lint: `ruff check src/ tests/ cli/` passes
- [ ] Format: `ruff format --check src/ tests/` passes

---

## 9. "What NOT To Do"

These are common mistakes to avoid during this phase. Read all of them before starting.

### DO NOT remove commands without user approval
The audit table in Section 3 is a RECOMMENDATION. The user may want to keep `/history` or `/locks`. Present the table, get explicit approval, then implement. If the user changes even one disposition, re-evaluate the `/help` text and tests accordingly.

### DO NOT remove CLI commands
Bot commands and CLI commands are completely separate. `storyline-cli backfill-instagram`, `storyline-cli create-schedule`, `storyline-cli reset-queue`, etc., are all CLI commands defined in `/Users/chris/Projects/storyline-ai/cli/` and must NOT be touched. This phase ONLY affects Telegram bot commands.

### DO NOT remove API routes
API routes in `/Users/chris/Projects/storyline-ai/src/api/routes/` are independent of bot commands and must not be modified.

### DO NOT remove callback handlers for existing queue items
The callback handlers in `telegram_callbacks.py` and `telegram_autopost.py` handle button presses on messages that may already be in the chat. If you remove `handle_reset_callback`, old "Clear All" buttons will silently fail. Always keep callback handlers or add a "this action is no longer available" response.

### DO NOT silently ignore removed commands
Always register removed commands in `command_map` pointing to `handle_removed_command`. If you skip registration, Telegram will show the command as "unknown" or ignore it entirely. Users need a clear redirect message.

### DO NOT remove the `/settings` registration
Even though `/setup` is the "new" name, many users and the existing CLAUDE.md documentation reference `/settings`. Both must remain registered.

### DO NOT modify the `_build_callback_dispatch_table` destructively
The callback dispatch table maps action strings to handlers. Removing entries can break stale inline buttons in chat history. When in doubt, keep the entry.

### DO NOT forget to run the full pre-commit check
```bash
source venv/bin/activate && ruff check src/ tests/ cli/ && ruff format --check src/ tests/ && pytest
```
The `cli/` directory is included in the ruff check per the MEMORY.md note: "CI lint checks src/ AND cli/ but local pre-commit only checks src/ tests/ -- include cli/ in local checks."

### DO NOT update the `MAX_LOCKS_DISPLAY` constant without checking references
The constant at line 27 of `telegram_commands.py` is only used by `handle_locks`. If `handle_locks` is removed, also remove `MAX_LOCKS_DISPLAY`. But grep the codebase first to confirm no other file references it.

---

### Critical Files for Implementation
- `/Users/chris/Projects/storyline-ai/src/services/core/telegram_commands.py` - Core file: remove 9 handler methods, add `handle_removed_command`, merge stats into status, update help text
- `/Users/chris/Projects/storyline-ai/src/services/core/telegram_service.py` - Update command_map registrations and BotCommand autocomplete list
- `/Users/chris/Projects/storyline-ai/tests/src/services/test_telegram_commands.py` - Remove ~470 lines of tests for removed commands, add tests for merged status and deprecation redirects
- `/Users/chris/Projects/storyline-ai/CLAUDE.md` - Update the Telegram Bot Commands Reference table (the large table listing all commands)
- `/Users/chris/Projects/storyline-ai/src/services/core/telegram_callbacks.py` - Mark `handle_reset_callback` as legacy (keep for backward compat)