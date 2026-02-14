# Phase 06: Telegram Onboarding Wizard

**Status:** 📋 PENDING
**Risk:** Low
**Effort:** 4-5 hours
**PR Title:** `feat: guided Telegram onboarding wizard for self-service setup`

---


## Overview

Phase 06 introduces a guided onboarding experience for new users who send `/start` to the Telegram bot. Instead of showing a static command list, the bot walks the user through connecting Instagram, connecting a media source, and configuring their posting schedule -- all via inline buttons and conversation messages, with no CLI or terminal access required.

This phase depends on:
- **Phase 03** (per-tenant scheduler and posting) -- so the schedule created during onboarding applies to this user's tenant
- **Phase 04** (Instagram OAuth redirect flow) -- so the "Connect Instagram" step can generate an OAuth URL
- **Phase 05** (Google Drive OAuth) -- so the "Connect Google Drive" step can generate an OAuth URL

## Architecture Analysis

### Current Pattern: Manual State Tracking via `context.user_data`

The codebase explicitly does **not** use python-telegram-bot's `ConversationHandler`. Instead, it uses a manual pattern:

1. **State is stored** in `context.user_data["{feature}_state"]` (e.g., `add_account_state`, `settings_edit_state`)
2. **Text messages are routed** by the central `_handle_conversation_message()` in `telegram_service.py`, which checks for active conversation keys and dispatches to the appropriate handler
3. **Callback buttons** are routed by the central `_handle_callback()` in `telegram_service.py`, which uses a dispatch table + special-cases method
4. **State cleanup** is handled by dedicated `clear_{feature}_state()` functions in `telegram_utils.py`

This is the pattern to follow for onboarding. We should NOT introduce `ConversationHandler`.

### Current `/start` Handler

Located in `telegram_commands.py` line 32-52. It simply shows a static welcome message with a list of commands. This will be replaced with the onboarding flow for new users, and a dashboard for returning users.

### Composition Pattern

All Telegram handler modules follow the same composition pattern:
- Receive a `TelegramService` reference in `__init__`
- Access shared state via `self.service.{repo|service}`
- Are instantiated inside `TelegramService.initialize()`
- Are imported lazily inside `initialize()` to avoid circular imports

### State Tracking Approach Decision

**Recommendation: Add an `onboarding_step` column to `chat_settings`**, rather than a separate table.

Rationale:
- `chat_settings` is already the per-tenant identity table (AD-3 in the SaaS plan)
- Adding a nullable column is consistent with how other features were added (migrations 009, 010, 012)
- The onboarding state is inherently per-chat, which is exactly what `chat_settings` tracks
- A separate table would be over-engineering for a single column
- `NULL` = onboarding not started or already completed; non-null = in-progress step

Values for `onboarding_step`:
- `NULL` -- Not in onboarding (new user who hasn't started, or completed setup)
- `"welcome"` -- At welcome screen
- `"instagram"` -- Waiting for Instagram OAuth callback
- `"media_source"` -- Choosing media source
- `"gdrive_folder"` -- Waiting for Google Drive folder URL input
- `"schedule"` -- Configuring schedule
- `"complete"` -- Just finished (transient, used to show completion message)

We also need an `onboarding_completed` boolean column to distinguish "never started" from "already completed" for the returning-user check.

## Detailed Conversation Flow

### Step 1: Welcome (New User)

**Trigger**: User sends `/start` and has no `chat_settings` record, or has one where `onboarding_completed = False`.

```
Welcome to Storyline AI!

I'll help you automate your Instagram Stories.
Let's get you set up in a few steps.

[Connect Instagram]  [Skip for Now]
```

**Button callbacks**:
- `onboard:instagram` -- Start Instagram OAuth flow
- `onboard:skip_instagram` -- Skip to media source step

**State transition**: Sets `onboarding_step = "welcome"` when message is shown.

### Step 2: Connect Instagram

**Trigger**: User clicks `[Connect Instagram]`.

```
To connect your Instagram account, click the link below.
You'll be redirected to Instagram to authorize access.

[Authorize Instagram ->]  (URL button to OAuth endpoint)

Once you've authorized, I'll continue automatically.

[Skip this step]
```

**Button structure**:
- `InlineKeyboardButton("Authorize Instagram", url=oauth_url)` -- URL button (opens browser), NOT a callback
- `onboard:skip_instagram` -- Skip to media source

**State transition**: Sets `onboarding_step = "instagram"`. The OAuth callback (Phase 04) will notify the bot when authorization completes.

**OAuth callback notification**: When the FastAPI OAuth callback endpoint receives a successful authorization:
1. It stores the token (Phase 04 handles this)
2. It checks if the `chat_settings` for this user has `onboarding_step = "instagram"`
3. If so, it sends a proactive Telegram message to the chat:

```
Connected to @username!

Now let's set up your media source.

[Google Drive]  [Skip - I'll add media later]
```

**State transition**: Sets `onboarding_step = "media_source"`.

### Step 2b: Instagram Skipped

```
No problem! You can connect Instagram later via /settings.

Where are your story images stored?

[Google Drive]  [Skip - I'll add media later]
```

**State transition**: Sets `onboarding_step = "media_source"`.

### Step 3: Connect Media Source

**Trigger**: User clicks `[Google Drive]`.

```
Click below to connect your Google Drive:

[Authorize Google Drive ->]  (URL button to OAuth endpoint)

Once you've authorized, I'll ask for your media folder.

[Skip this step]
```

**Button structure**:
- `InlineKeyboardButton("Authorize Google Drive", url=gdrive_oauth_url)` -- URL button
- `onboard:skip_media` -- Skip to schedule

**State transition**: Sets `onboarding_step = "media_source"`.

**Google Drive OAuth callback notification**: When successful:

```
Google Drive connected!

Now paste the link to your media folder in Google Drive:
(e.g., https://drive.google.com/drive/folders/abc123)

[Skip this step]
```

**State transition**: Sets `onboarding_step = "gdrive_folder"`.

### Step 3a: Folder URL Input

**Trigger**: User pastes a Google Drive folder URL as a text message.

This is handled by `_handle_conversation_message` routing to the onboarding handler when `onboard_state` is active in `context.user_data`.

**Processing**:
1. Extract folder ID from the URL (regex: `folders/([a-zA-Z0-9_-]+)`)
2. Validate folder exists and is accessible with the user's OAuth token
3. Store folder ID in `chat_settings.media_source_root` (or equivalent)
4. Trigger a media sync to count files
5. Show result:

```
Found 47 media files in 3 categories!

Now let's configure your posting schedule.

How many stories per day?

[3 (Recommended)]  [5]  [7]  [Custom]
```

**State transition**: Sets `onboarding_step = "schedule"`.

### Step 3b: Media Skipped

```
No problem! You can connect media later via /sync.

Let's configure your posting schedule.

How many stories per day?

[3 (Recommended)]  [5]  [7]  [Custom]
```

### Step 4: Configure Schedule

**Trigger**: User clicks a posts-per-day button or enters a custom number.

**Button callbacks**:
- `onboard:ppd:3` / `onboard:ppd:5` / `onboard:ppd:7` -- Set posts per day
- `onboard:ppd:custom` -- Ask for custom number (text input)

After posts per day is set:

```
What hours should stories be posted? (UTC)

[9am - 9pm (Recommended)]  [12pm - 12am]  [Custom]
```

**Button callbacks**:
- `onboard:hours:9:21` -- Set 9am-9pm
- `onboard:hours:12:0` -- Set 12pm-12am (0 = midnight next day)
- `onboard:hours:custom` -- Ask for custom hours (text input)

### Step 5: Setup Complete

```
You're all set! Here's your setup:

Instagram: @username (or "Not connected")
Media: Google Drive - 47 files (or "Not connected")
Schedule: 3 stories/day, 9am-9pm UTC

Your first story will be scheduled when you run /schedule 7.
Use /settings to adjust anytime.

[Create 7-Day Schedule]  [Settings]  [Help]
```

**Button callbacks**:
- `onboard:create_schedule` -- Run `SchedulerService.create_schedule(days=7)`
- `settings` -- Redirect to settings (reuse existing)
- (Help is just `/help` command)

**State transition**: Sets `onboarding_step = NULL`, `onboarding_completed = True`.

### Returning User Dashboard

**Trigger**: User sends `/start` and has `onboarding_completed = True`.

```
Welcome back!

Instagram: @username
Media: Google Drive (47 files)
Schedule: 3 stories/day, 9am-9pm UTC
Queue: 12 pending posts

[View Queue]  [Settings]  [Reconfigure]
```

**Button callbacks**:
- `onboard:view_queue` -- Show queue (same as `/queue`)
- `settings` -- Open settings
- `onboard:reconfigure` -- Reset `onboarding_completed = False` and restart onboarding

## Implementation Details

### New File: `src/services/core/telegram_onboarding.py`

```python
"""Telegram onboarding handlers - guided /start setup wizard."""

from __future__ import annotations
from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from src.utils.logger import logger

if TYPE_CHECKING:
    from src.services.core.telegram_service import TelegramService


class TelegramOnboardingHandlers:
    """Handles the onboarding wizard flow for new users.

    Manages the step-by-step setup: Instagram connection, media source
    connection, and schedule configuration.
    Uses composition: receives a TelegramService reference for shared state.
    """

    def __init__(self, service: TelegramService):
        self.service = service

    # =========================================================================
    # Entry point (replaces old /start handler)
    # =========================================================================

    async def handle_start(self, update, context):
        """Handle /start command - route to onboarding or dashboard."""
        ...

    # =========================================================================
    # Step 1: Welcome
    # =========================================================================

    async def _show_welcome(self, update, user, chat_id):
        """Show welcome message with onboarding options."""
        ...

    # =========================================================================
    # Step 2: Instagram Connection
    # =========================================================================

    async def handle_connect_instagram(self, data, user, query):
        """Handle 'Connect Instagram' button click."""
        ...

    async def handle_skip_instagram(self, data, user, query):
        """Handle 'Skip Instagram' button click."""
        ...

    async def notify_instagram_connected(self, chat_id, username):
        """Called by OAuth callback when Instagram is authorized.

        Sends a proactive message to the chat to continue onboarding.
        """
        ...

    # =========================================================================
    # Step 3: Media Source Connection
    # =========================================================================

    async def _show_media_source_step(self, chat_id, message_or_query):
        """Show media source selection."""
        ...

    async def handle_connect_gdrive(self, data, user, query):
        """Handle 'Google Drive' button click."""
        ...

    async def handle_skip_media(self, data, user, query):
        """Handle 'Skip media' button click."""
        ...

    async def notify_gdrive_connected(self, chat_id):
        """Called by OAuth callback when Google Drive is authorized."""
        ...

    async def handle_gdrive_folder_input(self, update, context):
        """Handle text input for Google Drive folder URL."""
        ...

    # =========================================================================
    # Step 4: Schedule Configuration
    # =========================================================================

    async def _show_schedule_step(self, chat_id, message_or_query):
        """Show schedule configuration options."""
        ...

    async def handle_posts_per_day(self, data, user, query):
        """Handle posts-per-day selection."""
        ...

    async def handle_custom_ppd_input(self, update, context):
        """Handle custom posts-per-day text input."""
        ...

    async def handle_posting_hours(self, data, user, query):
        """Handle posting hours selection."""
        ...

    async def handle_custom_hours_input(self, update, context):
        """Handle custom posting hours text input."""
        ...

    # =========================================================================
    # Step 5: Completion
    # =========================================================================

    async def _show_setup_complete(self, chat_id):
        """Show setup completion summary."""
        ...

    async def handle_create_schedule(self, data, user, query):
        """Handle 'Create 7-Day Schedule' button click."""
        ...

    # =========================================================================
    # Returning User Dashboard
    # =========================================================================

    async def _show_dashboard(self, update, user, chat_id):
        """Show returning-user dashboard."""
        ...

    async def handle_reconfigure(self, data, user, query):
        """Handle 'Reconfigure' button click - restart onboarding."""
        ...

    # =========================================================================
    # Helpers
    # =========================================================================

    def _build_setup_summary(self, chat_id) -> str:
        """Build a summary of the current setup for display."""
        ...

    def _generate_instagram_oauth_url(self, chat_id) -> str:
        """Generate the Instagram OAuth URL with state parameter."""
        ...

    def _generate_gdrive_oauth_url(self, chat_id) -> str:
        """Generate the Google Drive OAuth URL with state parameter."""
        ...
```

### Modifications to `telegram_service.py`

1. **Import and instantiate** `TelegramOnboardingHandlers` in `initialize()`:

```python
# Inside initialize(), after existing handler imports:
from src.services.core.telegram_onboarding import TelegramOnboardingHandlers

self.onboarding = TelegramOnboardingHandlers(self)
```

2. **Replace /start handler registration** to use the onboarding handler:

```python
# Change from:
"start": self.commands.handle_start,
# To:
"start": self.onboarding.handle_start,
```

3. **Add onboarding callbacks to dispatch table** in `_build_callback_dispatch_table()`:

```python
# Onboarding (telegram_onboarding.py)
"onboard": self.onboarding.handle_onboard_callback,
```

Note: A single `"onboard"` action prefix is used. The data portion after the colon routes to specific sub-handlers (e.g., `onboard:instagram`, `onboard:skip_instagram`, `onboard:ppd:3`). This follows the pattern used by `settings_accounts` and `accounts_config` in `_handle_callback_special_cases`.

4. **Add onboarding conversation routing** in `_handle_conversation_message()`:

```python
# Check for onboarding conversation (gdrive folder URL or custom schedule input)
if "onboard_state" in context.user_data:
    handled = await self.onboarding.handle_onboard_message(update, context)
    if handled:
        return
```

### Modifications to `telegram_commands.py`

The `handle_start` method in `TelegramCommandHandlers` should be kept but renamed to `handle_start_legacy` (or removed), since `/start` now routes to `TelegramOnboardingHandlers.handle_start`. The old method body becomes the "returning user with completed setup" dashboard fallback.

### Database Migration: `014_chat_settings_onboarding.sql`

```sql
-- Migration 014: Add onboarding tracking columns to chat_settings
-- Phase 06 of multi-tenant SaaS transition

BEGIN;

ALTER TABLE chat_settings
    ADD COLUMN onboarding_step VARCHAR(50) DEFAULT NULL,
    ADD COLUMN onboarding_completed BOOLEAN DEFAULT FALSE;

-- Backfill: mark existing records as completed
-- (existing deployments have already been configured via CLI)
UPDATE chat_settings SET onboarding_completed = TRUE
WHERE onboarding_completed IS NULL OR onboarding_completed = FALSE;

-- Record migration
INSERT INTO schema_version (version, description, applied_at)
VALUES (14, 'Add onboarding tracking to chat_settings', NOW());

COMMIT;
```

### Model Update: `chat_settings.py`

Add two columns:

```python
# Onboarding wizard state
onboarding_step = Column(String(50), nullable=True)  # NULL = not in onboarding
onboarding_completed = Column(Boolean, default=False)
```

### Settings Service Updates

Add to `SettingsService`:

```python
def set_onboarding_step(self, telegram_chat_id: int, step: Optional[str]) -> ChatSettings:
    """Update the onboarding step for a chat."""
    return self.settings_repo.update(telegram_chat_id, onboarding_step=step)

def complete_onboarding(self, telegram_chat_id: int) -> ChatSettings:
    """Mark onboarding as completed."""
    return self.settings_repo.update(
        telegram_chat_id, onboarding_step=None, onboarding_completed=True
    )
```

### OAuth Callback Integration

Phase 04 (Instagram OAuth) and Phase 05 (Google Drive OAuth) provide FastAPI callback endpoints. These endpoints need to be modified to send a proactive Telegram message when authorization succeeds and the user is in the middle of onboarding.

The callback endpoint needs to:

1. After storing the token, look up the `chat_settings` record using the `state` parameter (which should encode the `telegram_chat_id`)
2. Check if `onboarding_step` matches the current OAuth type (`"instagram"` or `"media_source"`)
3. If so, send a proactive Telegram message via the Bot API to continue the flow

This requires the callback endpoint to have access to the Telegram Bot instance. Two approaches:

**Approach A (Recommended): Store the chat_id in the OAuth state parameter and use a standalone Bot instance in the callback**

```python
# In the FastAPI OAuth callback:
from telegram import Bot
from src.config.settings import settings

bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
# After successful token storage:
if chat_settings.onboarding_step == "instagram":
    await bot.send_message(
        chat_id=chat_settings.telegram_chat_id,
        text="...",
        reply_markup=...,
    )
```

**Approach B: Use a shared event/queue**

More complex, not needed for this use case.

### State Tracking in `context.user_data`

For text input steps (Google Drive folder URL, custom posts-per-day, custom hours), use the existing `context.user_data` pattern:

```python
ONBOARD_KEYS = [
    "onboard_state",
    "onboard_chat_id",
    "onboard_messages",  # Track message IDs for cleanup
    "onboard_data",      # Collected data during flow
]
```

States for `context.user_data["onboard_state"]`:
- `"awaiting_gdrive_folder"` -- Waiting for Google Drive folder URL
- `"awaiting_custom_ppd"` -- Waiting for custom posts-per-day number
- `"awaiting_custom_hours_start"` -- Waiting for custom start hour
- `"awaiting_custom_hours_end"` -- Waiting for custom end hour

Add corresponding `clear_onboard_state()` to `telegram_utils.py`.

### Callback Action Routing

The onboarding handler should be added to `_handle_callback_special_cases()` rather than the standard dispatch table, because it needs sub-routing based on the data portion:

```python
elif action == "onboard":
    await self.onboarding.handle_onboard_callback(data, user, query, context)
    return True
```

Inside `TelegramOnboardingHandlers.handle_onboard_callback`:

```python
async def handle_onboard_callback(self, data, user, query, context):
    """Route onboarding callback sub-actions."""
    if data == "instagram":
        await self.handle_connect_instagram(data, user, query)
    elif data == "skip_instagram":
        await self.handle_skip_instagram(data, user, query)
    elif data == "gdrive":
        await self.handle_connect_gdrive(data, user, query)
    elif data == "skip_media":
        await self.handle_skip_media(data, user, query)
    elif data and data.startswith("ppd:"):
        await self.handle_posts_per_day(data, user, query)
    elif data and data.startswith("hours:"):
        await self.handle_posting_hours(data, user, query)
    elif data == "create_schedule":
        await self.handle_create_schedule(data, user, query)
    elif data == "reconfigure":
        await self.handle_reconfigure(data, user, query)
    elif data == "view_queue":
        # Delegate to existing queue display
        await self.service.commands.handle_queue(query, context)
    else:
        logger.warning(f"Unknown onboarding action: {data}")
```

### Inline Keyboard Structures

**Welcome (Step 1)**:
```python
keyboard = [
    [
        InlineKeyboardButton("📸 Connect Instagram", callback_data="onboard:instagram"),
    ],
    [
        InlineKeyboardButton("⏭️ Skip for Now", callback_data="onboard:skip_instagram"),
    ],
]
```

**Connect Instagram (Step 2)**:
```python
oauth_url = self._generate_instagram_oauth_url(chat_id)
keyboard = [
    [
        InlineKeyboardButton("🔗 Authorize Instagram", url=oauth_url),
    ],
    [
        InlineKeyboardButton("⏭️ Skip this step", callback_data="onboard:skip_instagram"),
    ],
]
```

**Media Source (Step 3)**:
```python
keyboard = [
    [
        InlineKeyboardButton("📁 Google Drive", callback_data="onboard:gdrive"),
    ],
    [
        InlineKeyboardButton("⏭️ Skip - I'll add media later", callback_data="onboard:skip_media"),
    ],
]
```

**Connect Google Drive (Step 3a)**:
```python
gdrive_url = self._generate_gdrive_oauth_url(chat_id)
keyboard = [
    [
        InlineKeyboardButton("🔗 Authorize Google Drive", url=gdrive_url),
    ],
    [
        InlineKeyboardButton("⏭️ Skip this step", callback_data="onboard:skip_media"),
    ],
]
```

**Schedule - Posts Per Day (Step 4a)**:
```python
keyboard = [
    [
        InlineKeyboardButton("3 (Recommended)", callback_data="onboard:ppd:3"),
        InlineKeyboardButton("5", callback_data="onboard:ppd:5"),
        InlineKeyboardButton("7", callback_data="onboard:ppd:7"),
    ],
    [
        InlineKeyboardButton("Custom", callback_data="onboard:ppd:custom"),
    ],
]
```

**Schedule - Posting Hours (Step 4b)**:
```python
keyboard = [
    [
        InlineKeyboardButton("9am-9pm UTC", callback_data="onboard:hours:9:21"),
    ],
    [
        InlineKeyboardButton("12pm-12am UTC", callback_data="onboard:hours:12:0"),
    ],
    [
        InlineKeyboardButton("Custom", callback_data="onboard:hours:custom"),
    ],
]
```

**Completion (Step 5)**:
```python
keyboard = [
    [
        InlineKeyboardButton("📅 Create 7-Day Schedule", callback_data="onboard:create_schedule"),
    ],
    [
        InlineKeyboardButton("⚙️ Settings", callback_data="settings_refresh"),
        InlineKeyboardButton("❓ Help", callback_data="onboard:help"),
    ],
]
```

**Returning User Dashboard**:
```python
keyboard = [
    [
        InlineKeyboardButton("📋 View Queue", callback_data="onboard:view_queue"),
        InlineKeyboardButton("⚙️ Settings", callback_data="settings_refresh"),
    ],
    [
        InlineKeyboardButton("🔄 Reconfigure", callback_data="onboard:reconfigure"),
    ],
]
```

## State Transition Diagram

```
/start (new user)
    │
    ▼
[welcome] ──── onboard:instagram ────► [instagram] ──── OAuth callback ────► [media_source]
    │                                       │
    │                                   onboard:skip_instagram
    │                                       │
    └── onboard:skip_instagram ─────────────┘
                                            │
                                            ▼
                                    [media_source] ── onboard:gdrive ──► [media_source] ── OAuth callback ──► [gdrive_folder]
                                            │                                                                        │
                                            │                                                                   text input
                                        onboard:skip_media                                                           │
                                            │                                                                        ▼
                                            └────────────────────────────────────────────────────────────────► [schedule]
                                                                                                                     │
                                                                                                              onboard:ppd:N
                                                                                                              onboard:hours:S:E
                                                                                                                     │
                                                                                                                     ▼
                                                                                                             [complete] ──► NULL
                                                                                                             (onboarding_completed=True)

/start (returning user, onboarding_completed=True)
    │
    ▼
[dashboard] ── onboard:reconfigure ──► [welcome] (restarts flow)
```

## Files to Create

| File | Description |
|------|-------------|
| `src/services/core/telegram_onboarding.py` | New handler module with all onboarding logic |
| `scripts/migrations/014_chat_settings_onboarding.sql` | Add `onboarding_step` and `onboarding_completed` columns |
| `tests/src/services/test_telegram_onboarding.py` | Tests for onboarding handlers |

## Files to Modify

| File | Change |
|------|--------|
| `src/models/chat_settings.py` | Add `onboarding_step` and `onboarding_completed` columns |
| `src/services/core/settings_service.py` | Add `set_onboarding_step()` and `complete_onboarding()` methods |
| `src/services/core/telegram_service.py` | Import and instantiate `TelegramOnboardingHandlers`, update callback dispatch, update `_handle_conversation_message()` |
| `src/services/core/telegram_commands.py` | Remove or rename old `handle_start` (replaced by onboarding) |
| `src/services/core/telegram_utils.py` | Add `ONBOARD_KEYS` and `clear_onboard_state()` |
| `src/repositories/chat_settings_repository.py` | No changes needed (generic `update()` already handles new columns) |
| OAuth callback endpoints (Phase 04/05) | Add proactive Telegram notification when onboarding is in progress |

## Test Plan

### Unit Tests (`tests/src/services/test_telegram_onboarding.py`)

Follow the existing pattern from `test_telegram_accounts.py`:

1. **Fixture**: `mock_onboarding_handlers` -- Same pattern as other test files, creating `TelegramOnboardingHandlers` with fully mocked `TelegramService`

2. **Test Classes**:

```python
class TestHandleStart:
    """Tests for /start command routing."""

    async def test_start_new_user_shows_welcome(self, mock_onboarding_handlers):
        """New user (no chat_settings) sees welcome with onboarding options."""

    async def test_start_returning_user_shows_dashboard(self, mock_onboarding_handlers):
        """User with onboarding_completed=True sees dashboard."""

    async def test_start_user_mid_onboarding_resumes(self, mock_onboarding_handlers):
        """User with onboarding_step set resumes from that step."""


class TestInstagramConnection:
    """Tests for Instagram connection step."""

    async def test_connect_instagram_shows_oauth_url(self, mock_onboarding_handlers):
        """Connect Instagram button shows OAuth URL button."""

    async def test_skip_instagram_advances_to_media(self, mock_onboarding_handlers):
        """Skip advances to media source step."""

    async def test_notify_instagram_connected_continues_flow(self, mock_onboarding_handlers):
        """OAuth callback notification updates UI and advances step."""


class TestMediaSourceConnection:
    """Tests for media source step."""

    async def test_gdrive_shows_oauth_url(self, mock_onboarding_handlers):
        """Google Drive button shows OAuth URL button."""

    async def test_skip_media_advances_to_schedule(self, mock_onboarding_handlers):
        """Skip advances to schedule step."""

    async def test_gdrive_folder_input_valid_url(self, mock_onboarding_handlers):
        """Valid Drive folder URL extracts ID and triggers sync."""

    async def test_gdrive_folder_input_invalid_url(self, mock_onboarding_handlers):
        """Invalid URL shows error and asks again."""


class TestScheduleConfiguration:
    """Tests for schedule step."""

    async def test_preset_ppd_updates_settings(self, mock_onboarding_handlers):
        """Selecting preset posts-per-day updates chat_settings."""

    async def test_custom_ppd_prompts_for_input(self, mock_onboarding_handlers):
        """Custom button sets conversation state for text input."""

    async def test_posting_hours_preset_updates_settings(self, mock_onboarding_handlers):
        """Selecting preset hours updates chat_settings."""

    async def test_schedule_complete_shows_summary(self, mock_onboarding_handlers):
        """After schedule is set, shows completion summary."""


class TestCompletion:
    """Tests for completion step."""

    async def test_complete_sets_onboarding_completed(self, mock_onboarding_handlers):
        """Completion sets onboarding_completed=True, step=None."""

    async def test_create_schedule_calls_scheduler(self, mock_onboarding_handlers):
        """Create Schedule button invokes SchedulerService."""


class TestReturningUserDashboard:
    """Tests for returning user experience."""

    async def test_dashboard_shows_setup_summary(self, mock_onboarding_handlers):
        """Dashboard shows Instagram, media, schedule summary."""

    async def test_reconfigure_resets_onboarding(self, mock_onboarding_handlers):
        """Reconfigure sets onboarding_completed=False and restarts."""
```

### State Transition Tests

```python
class TestStateTransitions:
    """Verify correct state transitions between onboarding steps."""

    async def test_welcome_to_instagram(self, mock_onboarding_handlers):
        """onboarding_step transitions from welcome to instagram."""

    async def test_instagram_to_media_source(self, mock_onboarding_handlers):
        """onboarding_step transitions from instagram to media_source."""

    async def test_skip_all_to_schedule(self, mock_onboarding_handlers):
        """Skipping all optional steps reaches schedule."""

    async def test_schedule_to_complete(self, mock_onboarding_handlers):
        """Setting schedule marks onboarding as complete."""
```

## Implementation Sequence

1. **Database migration** -- Add columns to `chat_settings`
2. **Model update** -- Add columns to `ChatSettings` model
3. **Settings service update** -- Add `set_onboarding_step()` and `complete_onboarding()`
4. **telegram_utils.py update** -- Add `ONBOARD_KEYS` and `clear_onboard_state()`
5. **Create telegram_onboarding.py** -- The main handler module
6. **Update telegram_service.py** -- Wire up the new handler
7. **Update telegram_commands.py** -- Remove/rename old `/start` handler
8. **Write tests** -- Full test coverage for all steps
9. **Update CHANGELOG.md** -- Document the new feature

## What NOT To Do

1. **Do NOT use `ConversationHandler`** from python-telegram-bot. The codebase uses manual `context.user_data` state tracking. Introducing `ConversationHandler` would create two conflicting patterns and require restructuring the central `_handle_callback` dispatcher.

2. **Do NOT create a separate onboarding table**. The `chat_settings` table is the right place for per-chat onboarding state. A separate table adds complexity for no benefit.

3. **Do NOT block returning users from using commands during onboarding**. If a user is mid-onboarding and types `/help` or `/settings`, those commands should still work normally. The onboarding state only affects `/start` and onboarding-specific callback buttons.

4. **Do NOT auto-create a schedule during onboarding**. The "Create 7-Day Schedule" button at the end is explicit user action. Do not create schedules automatically just because setup completed.

5. **Do NOT store OAuth tokens or credentials in `context.user_data`**. Tokens must be stored in the database via the existing `api_tokens` table (Phase 04/05 handle this).

6. **Do NOT modify the existing `/settings` command behavior**. The onboarding wizard is a first-time setup flow. Settings remains the ongoing configuration tool. They complement each other.

7. **Do NOT hardcode OAuth URLs**. The OAuth endpoints will be defined by Phases 04 and 05. Use helper methods that generate URLs based on configuration (FastAPI base URL + chat ID state parameter).

8. **Do NOT add onboarding state to the `get_settings_display()` dict**. Onboarding state is internal workflow tracking, not a user-visible setting.

## Potential Challenges

1. **OAuth callback timing**: The user may close the browser before completing OAuth. The bot should handle this gracefully -- if the user clicks "Connect Instagram" again, regenerate the OAuth URL. If they type `/start` again, resume from the current step.

2. **Proactive messaging from FastAPI to Telegram**: The OAuth callback endpoint runs in a FastAPI context, not in the python-telegram-bot event loop. It needs to create a standalone `Bot` instance to send the proactive message. This is already done elsewhere in the codebase (see `send_notification` which initializes the bot for CLI usage at line 281-283 of `telegram_service.py`).

3. **Race conditions**: A user might click multiple buttons rapidly. Use the existing `get_operation_lock()` pattern if needed, though onboarding actions are idempotent so this is low risk.

4. **Bot private chat vs group chat**: The onboarding flow should work in both private chats (user DMs the bot) and group chats. The `telegram_chat_id` in `chat_settings` handles this naturally.

5. **Phases 04/05 not yet implemented**: The OAuth URL generation and callback notification code depends on those phases. The onboarding module should be structured to work without them (graceful degradation -- show "Coming soon" or skip the step if OAuth endpoints are not configured).

## Verification Checklist

- [ ] New user sends `/start` and sees welcome message with onboarding options
- [ ] "Connect Instagram" shows OAuth URL button
- [ ] "Skip" buttons correctly advance to the next step
- [ ] OAuth callback sends proactive message to continue onboarding
- [ ] Google Drive folder URL is parsed and validated
- [ ] Schedule configuration saves to `chat_settings`
- [ ] Completion summary shows accurate setup details
- [ ] Returning user sees dashboard with summary
- [ ] "Reconfigure" restarts onboarding from the beginning
- [ ] All onboarding callbacks are properly logged via `interaction_service`
- [ ] State transitions are tracked in `chat_settings.onboarding_step`
- [ ] Other commands (e.g. `/help`, `/settings`) still work during onboarding
- [ ] Test coverage for all steps and transitions
- [ ] Ruff lint and format pass
- [ ] CHANGELOG.md updated

### Critical Files for Implementation

- `/Users/chris/Projects/storyline-ai/src/services/core/telegram_onboarding.py` - New file: all onboarding wizard logic (entry point, step handlers, state transitions, OAuth notification receivers)
- `/Users/chris/Projects/storyline-ai/src/services/core/telegram_service.py` - Wire up onboarding handler: import, instantiate, add to callback dispatch, add to conversation message router
- `/Users/chris/Projects/storyline-ai/src/models/chat_settings.py` - Add `onboarding_step` and `onboarding_completed` columns to the model
- `/Users/chris/Projects/storyline-ai/src/services/core/telegram_accounts.py` - Pattern to follow: multi-step conversation flow with `context.user_data` state tracking, message cleanup, cancel handling
- `/Users/chris/Projects/storyline-ai/src/services/core/telegram_utils.py` - Add `ONBOARD_KEYS` list and `clear_onboard_state()` cleanup function (following existing Pattern 4)