# Extract Magic Numbers into Named Constants

**Status**: 🔧 IN PROGRESS
**Started**: 2026-02-10

| Field | Value |
|---|---|
| **PR Title** | `refactor: extract magic numbers into named constants` |
| **Risk Level** | Low |
| **Effort** | Small (1-2 hours) |
| **Dependencies** | None |
| **Blocks** | None |
| **Files Modified** | `src/config/constants.py` (new), `src/services/core/health_check.py`, `src/services/core/scheduler.py`, `src/services/core/telegram_commands.py`, `src/services/core/telegram_settings.py`, `src/services/core/settings_service.py`, `src/services/integrations/instagram_api.py`, `src/services/core/telegram_accounts.py` |

---

## Problem Description

Multiple files contain "magic numbers" -- literal numeric values used directly in business logic without named constants. This makes it difficult to understand what the numbers mean, creates maintenance risk when the same value appears in multiple files, and makes it easy to introduce bugs when updating a value in one place but not another.

The most critical case is the posts-per-day validation range (`1 <= value <= 50`) and the posting hour range (`0 <= value <= 23`), which appear in both `telegram_settings.py` and `settings_service.py`. If someone updates one file but not the other, the validation becomes inconsistent.

---

## Step-by-Step Implementation

### Step 1: Create `src/config/constants.py`

This is a **new file**. It holds constants shared across multiple modules.

**Create** `src/config/constants.py`:

```python
"""Shared application constants.

Constants used by multiple modules are defined here to ensure consistency.
Module-specific constants should be defined as class-level attributes on
their respective service classes instead.
"""

# Posting schedule limits (used by telegram_settings.py and settings_service.py)
MIN_POSTS_PER_DAY = 1
MAX_POSTS_PER_DAY = 50
MIN_POSTING_HOUR = 0
MAX_POSTING_HOUR = 23
```

---

### Step 2: Update `src/services/core/health_check.py`

Three magic numbers need to become class-level constants on `HealthCheckService`.

**Before** (lines 14-15):

```python
class HealthCheckService(BaseService):
    """System health monitoring."""
```

**After**:

```python
class HealthCheckService(BaseService):
    """System health monitoring."""

    QUEUE_BACKLOG_THRESHOLD = 50
    MAX_PENDING_AGE_HOURS = 24
    RECENT_POSTS_WINDOW_HOURS = 48
```

**Before** (line 173):

```python
            if pending_count > 50:
```

**After**:

```python
            if pending_count > self.QUEUE_BACKLOG_THRESHOLD:
```

**Before** (line 183):

```python
                if age > timedelta(hours=24):
```

**After**:

```python
                if age > timedelta(hours=self.MAX_PENDING_AGE_HOURS):
```

**Before** (line 202):

```python
            recent_posts = self.history_repo.get_recent_posts(hours=48)
```

**After**:

```python
            recent_posts = self.history_repo.get_recent_posts(hours=self.RECENT_POSTS_WINDOW_HOURS)
```

**Before** (lines 204-208):

```python
            if not recent_posts:
                return {
                    "healthy": False,
                    "message": "No posts in last 48 hours",
                    "recent_count": 0,
                }
```

**After**:

```python
            if not recent_posts:
                return {
                    "healthy": False,
                    "message": f"No posts in last {self.RECENT_POSTS_WINDOW_HOURS} hours",
                    "recent_count": 0,
                }
```

**Before** (line 215):

```python
                "message": f"{len(successful_posts)}/{len(recent_posts)} successful in last 48h",
```

**After**:

```python
                "message": f"{len(successful_posts)}/{len(recent_posts)} successful in last {self.RECENT_POSTS_WINDOW_HOURS}h",
```

---

### Step 3: Update `src/services/core/scheduler.py`

One magic number for jitter needs to become a class-level constant.

**Before** (lines 17-18):

```python
class SchedulerService(BaseService):
    """Create and manage posting schedule."""
```

**After**:

```python
class SchedulerService(BaseService):
    """Create and manage posting schedule."""

    SCHEDULE_JITTER_MINUTES = 30
```

**Before** (line 265 inside `_generate_time_slots_from_date`):

```python
                jitter_minutes = random.randint(-30, 30)
```

**After**:

```python
                jitter_minutes = random.randint(-self.SCHEDULE_JITTER_MINUTES, self.SCHEDULE_JITTER_MINUTES)
```

**Before** (line 364 inside `_generate_time_slots`):

```python
                jitter_minutes = random.randint(-30, 30)
```

**After**:

```python
                jitter_minutes = random.randint(-self.SCHEDULE_JITTER_MINUTES, self.SCHEDULE_JITTER_MINUTES)
```

Note: The comment on line 363 (`# Add +/-30min jitter for unpredictability`) should also be updated:

**Before** (line 363):

```python
                # Add ±30min jitter for unpredictability
```

**After**:

```python
                # Add jitter for unpredictability (configurable via SCHEDULE_JITTER_MINUTES)
```

---

### Step 4: Update `src/services/core/telegram_commands.py`

One magic number for the locks display limit.

**Before** (line 591):

```python
        for i, lock in enumerate(permanent[:10], 1):  # Show max 10
```

**After**: First add a class-level constant:

```python
class TelegramCommandHandlers:
    """Handles all /command interactions for the Telegram bot.

    Uses composition pattern: receives a TelegramService reference
    and accesses shared state via self.service.
    """

    MAX_LOCKS_DISPLAY = 10
```

Then update the usage on line 591:

```python
        for i, lock in enumerate(permanent[:self.MAX_LOCKS_DISPLAY], 1):  # Show max
```

**Before** (line 596):

```python
        if len(permanent) > 10:
            lines.append(f"\n... and {len(permanent) - 10} more")
```

**After**:

```python
        if len(permanent) > self.MAX_LOCKS_DISPLAY:
            lines.append(f"\n... and {len(permanent) - self.MAX_LOCKS_DISPLAY} more")
```

---

### Step 5: Update `src/services/core/telegram_settings.py`

Replace hardcoded validation ranges with shared constants. Two locations use `1 <= value <= 50` and `0 <= value <= 23`.

**Before** (lines 1-9, imports section):

```python
"""Telegram settings handlers - /settings command, toggles, edits, and schedule management."""

from __future__ import annotations

from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.utils.logger import logger
```

**After**:

```python
"""Telegram settings handlers - /settings command, toggles, edits, and schedule management."""

from __future__ import annotations

from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.config.constants import MAX_POSTS_PER_DAY, MIN_POSTS_PER_DAY, MAX_POSTING_HOUR, MIN_POSTING_HOUR
from src.utils.logger import logger
```

**Before** (line 186, inside `handle_settings_edit_start`):

```python
                f"Enter a number between 1 and 50:",
```

**After**:

```python
                f"Enter a number between {MIN_POSTS_PER_DAY} and {MAX_POSTS_PER_DAY}:",
```

**Before** (line 207, inside `handle_settings_edit_start`):

```python
                f"Enter the *start hour* (0-23 UTC):",
```

**After**:

```python
                f"Enter the *start hour* ({MIN_POSTING_HOUR}-{MAX_POSTING_HOUR} UTC):",
```

**Before** (line 231, inside `handle_settings_edit_message`):

```python
                if not 1 <= value <= 50:
```

**After**:

```python
                if not MIN_POSTS_PER_DAY <= value <= MAX_POSTS_PER_DAY:
```

**Before** (line 264, error message for posts_per_day):

```python
                        "❌ Invalid input. Please enter a number between 1 and 50:"
```

**After**:

```python
                        f"❌ Invalid input. Please enter a number between {MIN_POSTS_PER_DAY} and {MAX_POSTS_PER_DAY}:"
```

**Before** (line 275, inside `handle_settings_edit_message` for hours_start):

```python
                if not 0 <= value <= 23:
```

**After**:

```python
                if not MIN_POSTING_HOUR <= value <= MAX_POSTING_HOUR:
```

**Before** (line 295, prompt text for end hour):

```python
                        f"Enter the *end hour* (0-23 UTC):"
```

**After**:

```python
                        f"Enter the *end hour* ({MIN_POSTING_HOUR}-{MAX_POSTING_HOUR} UTC):"
```

**Before** (line 314, error message for hours_start):

```python
                        "❌ Invalid input. Please enter a number between 0 and 23:"
```

**After**:

```python
                        f"❌ Invalid input. Please enter a number between {MIN_POSTING_HOUR} and {MAX_POSTING_HOUR}:"
```

**Before** (line 325, inside `handle_settings_edit_message` for hours_end):

```python
                if not 0 <= value <= 23:
```

**After**:

```python
                if not MIN_POSTING_HOUR <= value <= MAX_POSTING_HOUR:
```

**Before** (line 365, error message for hours_end):

```python
                        f"❌ Invalid input. Please enter a number between 0 and 23:"
```

**After**:

```python
                        f"❌ Invalid input. Please enter a number between {MIN_POSTING_HOUR} and {MAX_POSTING_HOUR}:"
```

---

### Step 6: Update `src/services/core/settings_service.py`

Replace hardcoded validation ranges with shared constants.

**Before** (lines 1-9, imports):

```python
"""Settings service - runtime configuration management."""

from typing import Optional, Any, Dict

from src.services.base_service import BaseService
from src.repositories.chat_settings_repository import ChatSettingsRepository
from src.models.chat_settings import ChatSettings
from src.models.user import User
from src.utils.logger import logger
```

**After**:

```python
"""Settings service - runtime configuration management."""

from typing import Optional, Any, Dict

from src.services.base_service import BaseService
from src.repositories.chat_settings_repository import ChatSettingsRepository
from src.config.constants import MAX_POSTS_PER_DAY, MIN_POSTS_PER_DAY, MAX_POSTING_HOUR, MIN_POSTING_HOUR
from src.models.chat_settings import ChatSettings
from src.models.user import User
from src.utils.logger import logger
```

**Before** (lines 138-145, inside `update_setting`):

```python
            # Validate numeric settings
            if setting_name == "posts_per_day":
                value = int(value)
                if not 1 <= value <= 50:
                    raise ValueError("posts_per_day must be between 1 and 50")
            elif setting_name in ("posting_hours_start", "posting_hours_end"):
                value = int(value)
                if not 0 <= value <= 23:
                    raise ValueError("Hour must be between 0 and 23")
```

**After**:

```python
            # Validate numeric settings
            if setting_name == "posts_per_day":
                value = int(value)
                if not MIN_POSTS_PER_DAY <= value <= MAX_POSTS_PER_DAY:
                    raise ValueError(f"posts_per_day must be between {MIN_POSTS_PER_DAY} and {MAX_POSTS_PER_DAY}")
            elif setting_name in ("posting_hours_start", "posting_hours_end"):
                value = int(value)
                if not MIN_POSTING_HOUR <= value <= MAX_POSTING_HOUR:
                    raise ValueError(f"Hour must be between {MIN_POSTING_HOUR} and {MAX_POSTING_HOUR}")
```

---

### Step 7: Update `src/services/integrations/instagram_api.py`

One magic number for the minimum Instagram account ID length.

**Before** (lines 46-50, existing class-level constants):

```python
class InstagramAPIService(BaseService):
    """
    Instagram Graph API integration for Stories.
    ...
    """

    # Meta Graph API configuration
    META_GRAPH_BASE = "https://graph.facebook.com/v18.0"
    CONTAINER_STATUS_POLL_INTERVAL = 2  # seconds
    CONTAINER_STATUS_MAX_POLLS = 30  # max ~60 seconds wait
```

**After**:

```python
class InstagramAPIService(BaseService):
    """
    Instagram Graph API integration for Stories.
    ...
    """

    # Meta Graph API configuration
    META_GRAPH_BASE = "https://graph.facebook.com/v18.0"
    CONTAINER_STATUS_POLL_INTERVAL = 2  # seconds
    CONTAINER_STATUS_MAX_POLLS = 30  # max ~60 seconds wait
    MIN_ACCOUNT_ID_LENGTH = 10  # Instagram account IDs are typically 15-17 digits
```

**Before** (line 519):

```python
        if len(account_id_str) < 10:
```

**After**:

```python
        if len(account_id_str) < self.MIN_ACCOUNT_ID_LENGTH:
```

---

### Step 8: Update `src/services/core/telegram_accounts.py`

One magic number for the UUID display truncation length.

**Before** (lines 15-23):

```python
class TelegramAccountHandlers:
    """Handles Instagram account management in Telegram.

    Manages account selection menus, add/remove flows, inline account
    switching from posting workflow, and the back-to-post rebuild.
    Uses composition: receives a TelegramService reference for shared state.
    """

    def __init__(self, service: TelegramService):
        self.service = service
```

**After**:

```python
class TelegramAccountHandlers:
    """Handles Instagram account management in Telegram.

    Manages account selection menus, add/remove flows, inline account
    switching from posting workflow, and the back-to-post rebuild.
    Uses composition: receives a TelegramService reference for shared state.
    """

    ID_DISPLAY_LENGTH = 8  # Truncate UUIDs for Telegram's 64-byte callback limit

    def __init__(self, service: TelegramService):
        self.service = service
```

**Before** (lines 632-633, inside `handle_post_account_selector`):

```python
            short_queue_id = queue_id[:8] if len(queue_id) > 8 else queue_id
            short_account_id = acc["id"][:8] if len(acc["id"]) > 8 else acc["id"]
```

**After**:

```python
            short_queue_id = queue_id[:self.ID_DISPLAY_LENGTH] if len(queue_id) > self.ID_DISPLAY_LENGTH else queue_id
            short_account_id = acc["id"][:self.ID_DISPLAY_LENGTH] if len(acc["id"]) > self.ID_DISPLAY_LENGTH else acc["id"]
```

**Before** (line 654, inside `handle_post_account_selector`):

```python
        short_queue_id = queue_id[:8] if len(queue_id) > 8 else queue_id
```

**After**:

```python
        short_queue_id = queue_id[:self.ID_DISPLAY_LENGTH] if len(queue_id) > self.ID_DISPLAY_LENGTH else queue_id
```

---

## Verification Checklist

Run these commands after making all changes:

```bash
# 1. Activate virtual environment
source venv/bin/activate

# 2. Lint check (should pass with zero errors)
ruff check src/config/constants.py src/services/core/health_check.py src/services/core/scheduler.py src/services/core/telegram_commands.py src/services/core/telegram_settings.py src/services/core/settings_service.py src/services/integrations/instagram_api.py src/services/core/telegram_accounts.py

# 3. Format check (should pass)
ruff format --check src/config/constants.py src/services/core/health_check.py src/services/core/scheduler.py src/services/core/telegram_commands.py src/services/core/telegram_settings.py src/services/core/settings_service.py src/services/integrations/instagram_api.py src/services/core/telegram_accounts.py

# 4. Run full test suite (all tests should still pass)
pytest

# 5. Verify the new constants file is importable
python -c "from src.config.constants import MIN_POSTS_PER_DAY, MAX_POSTS_PER_DAY, MIN_POSTING_HOUR, MAX_POSTING_HOUR; print('OK')"
```

---

## What NOT To Do

1. **Do NOT put all constants in `constants.py`.** Only constants shared between multiple modules belong there. Class-specific constants (like `QUEUE_BACKLOG_THRESHOLD`) should remain as class-level attributes on their service class. This keeps constants close to where they are used and avoids creating a "god file."

2. **Do NOT change the actual numeric values.** This PR is purely a refactor. The threshold for queue backlog is still 50. The jitter is still +/-30 minutes. Do not "improve" any values in this PR.

3. **Do NOT add constants for numbers that appear only once AND are self-explanatory.** For example, `limit=1` in `get_pending(limit=1)` or `days > 30` in the schedule command validation. Those are clear from context.

4. **Do NOT change any business logic.** The behavior of every code path must be identical before and after this change. If a test fails, you introduced a regression -- do not "fix" the test by changing its expectations.

5. **Do NOT forget the f-string conversion.** When replacing hardcoded numbers in string literals (like error messages and UI text), you must convert plain strings to f-strings so the constant value is interpolated. For example, `"between 1 and 50"` must become `f"between {MIN_POSTS_PER_DAY} and {MAX_POSTS_PER_DAY}"`.
