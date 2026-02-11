# Phase 05: Extract Telegram Handler Common Utilities

**Status**: ✅ COMPLETE
**Started**: 2026-02-10
**Completed**: 2026-02-10

| Field | Value |
|-------|-------|
| **PR Title** | Extract Telegram handler common utilities |
| **Risk Level** | Medium |
| **Effort** | Large (4-6 hours) |
| **Dependencies** | None |
| **Blocks** | Phase 06 |
| **Files Modified** | `src/services/core/telegram_utils.py` (new), `src/services/core/telegram_callbacks.py`, `src/services/core/telegram_autopost.py`, `src/services/core/telegram_accounts.py`, `src/services/core/telegram_settings.py` |

---

## Problem Description

Four code patterns are duplicated across the Telegram handler modules. Each pattern is copied 4-15+ times with minor variations. This creates maintenance burden (changes must be made in multiple places), increases bug surface area (one copy might get fixed while others do not), and makes the handler files unnecessarily long.

The four patterns are:

### Pattern 1: Queue Item Validation (15+ occurrences)

The pattern of fetching a queue item by ID and returning early with an error caption if not found appears in nearly every callback handler. Examples:

- `telegram_callbacks.py` line 69-73 (`_do_complete_queue_action`)
- `telegram_callbacks.py` line 177-180 (`handle_back`)
- `telegram_callbacks.py` line 232-235 (`handle_reject_confirmation`)
- `telegram_callbacks.py` line 283-287 (`handle_cancel_reject`)
- `telegram_callbacks.py` line 382-385 (`handle_rejected`)
- `telegram_autopost.py` line 57-60 (`_locked_autopost`)
- `telegram_accounts.py` line 614-616 (`handle_post_account_selector`)
- `telegram_accounts.py` line 700-703 (`handle_post_account_switch`)
- `telegram_accounts.py` line 768-770 (`handle_back_to_post`)
- `telegram_accounts.py` line 780-783 (`rebuild_posting_workflow`)

### Pattern 2: Standard Action Keyboard (5+ occurrences)

The inline keyboard with "Auto Post / Posted / Skip / Reject / Account Selector / Open Instagram" buttons is rebuilt from scratch in multiple places with slight variations. Examples:

- `telegram_service.py` lines 216-268 (`send_notification`)
- `telegram_callbacks.py` lines 193-222 (`handle_back`)
- `telegram_callbacks.py` lines 309-356 (`handle_cancel_reject`)
- `telegram_autopost.py` lines 412-445 (error recovery keyboard)
- `telegram_accounts.py` lines 800-849 (`rebuild_posting_workflow`)

### Pattern 3: Cancel Button Keyboard (6+ occurrences in settings)

The single-button "Cancel" keyboard is rebuilt identically in multiple settings edit flows:

- `telegram_settings.py` lines 175-181 (`handle_settings_edit_start`, posts_per_day branch)
- `telegram_settings.py` lines 196-202 (`handle_settings_edit_start`, hours branch)
- `telegram_settings.py` lines 252-258 (`handle_settings_edit_message`, error in posts_per_day)
- `telegram_settings.py` lines 282-288 (`handle_settings_edit_message`, success in hours_start)
- `telegram_settings.py` lines 302-308 (`handle_settings_edit_message`, error in hours_start)
- `telegram_settings.py` lines 352-358 (`handle_settings_edit_message`, error in hours_end)

### Pattern 4: Settings Edit State Cleanup (4 occurrences)

The same set of `context.user_data.pop()` calls to clear settings editing state:

- `telegram_settings.py` lines 240-241 (`handle_settings_edit_message`, posts_per_day success)
- `telegram_settings.py` lines 339-342 (`handle_settings_edit_message`, hours_end success)
- `telegram_settings.py` lines 378-381 (`handle_settings_edit_cancel`)
- And partially in `telegram_accounts.py` lines 492-495 (`handle_add_account_cancel`, similar pattern for add_account state)

---

## Step-by-Step Implementation

### Step 1: Create `src/services/core/telegram_utils.py`

Create a new file at `src/services/core/telegram_utils.py` with the following content:

```python
"""Telegram handler utilities - shared patterns extracted from handler modules.

This module contains common patterns used across multiple Telegram handler files:
- Queue item validation
- Standard action keyboard builders
- Settings edit state management
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

if TYPE_CHECKING:
    from src.services.core.telegram_service import TelegramService


# =========================================================================
# Pattern 1: Queue Item Validation
# =========================================================================


async def validate_queue_item(service: TelegramService, queue_id: str, query):
    """Fetch a queue item by ID, showing an error if not found.

    This is the standard validation pattern used by nearly every callback handler.
    On success, returns the queue item. On failure, edits the message caption
    with an error and returns None.

    Args:
        service: The parent TelegramService instance (provides queue_repo)
        queue_id: The queue item UUID string
        query: The Telegram CallbackQuery to edit on failure

    Returns:
        The queue item if found, or None if not found (message already updated)
    """
    queue_item = service.queue_repo.get_by_id(queue_id)
    if not queue_item:
        await query.edit_message_caption(caption="\u26a0\ufe0f Queue item not found")
        return None
    return queue_item


async def validate_queue_and_media(service: TelegramService, queue_id: str, query):
    """Fetch both queue item and its associated media item.

    Convenience wrapper that validates the queue item and then fetches the
    associated media item. Returns (None, None) on any failure, with the
    message already updated with an error.

    Args:
        service: The parent TelegramService instance
        queue_id: The queue item UUID string
        query: The Telegram CallbackQuery to edit on failure

    Returns:
        Tuple of (queue_item, media_item), or (None, None) on failure
    """
    queue_item = await validate_queue_item(service, queue_id, query)
    if not queue_item:
        return None, None

    media_item = service.media_repo.get_by_id(str(queue_item.media_item_id))
    if not media_item:
        await query.edit_message_caption(caption="\u26a0\ufe0f Media item not found")
        return None, None

    return queue_item, media_item


# =========================================================================
# Pattern 2: Standard Action Keyboard
# =========================================================================


def build_queue_action_keyboard(
    queue_id: str,
    enable_instagram_api: bool = False,
    active_account=None,
) -> InlineKeyboardMarkup:
    """Build the standard action keyboard for a queue item notification.

    This is the keyboard shown on every posting notification message. It includes:
    - Auto Post button (if Instagram API is enabled)
    - Posted / Skip buttons
    - Reject button
    - Account selector button
    - Open Instagram link

    Args:
        queue_id: The queue item UUID string (used in callback_data)
        enable_instagram_api: Whether to show the Auto Post button
        active_account: The active InstagramAccount object (for account label),
                        or None to show "No Account"

    Returns:
        InlineKeyboardMarkup with the complete action keyboard
    """
    keyboard = []

    # Auto Post button (if Instagram API is enabled)
    if enable_instagram_api:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "\U0001f916 Auto Post to Instagram",
                    callback_data=f"autopost:{queue_id}",
                ),
            ]
        )

    # Status action buttons
    keyboard.extend(
        [
            [
                InlineKeyboardButton(
                    "\u2705 Posted", callback_data=f"posted:{queue_id}"
                ),
                InlineKeyboardButton(
                    "\u23ed\ufe0f Skip", callback_data=f"skip:{queue_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    "\U0001f6ab Reject", callback_data=f"reject:{queue_id}"
                ),
            ],
        ]
    )

    # Instagram-related buttons
    account_label = (
        f"\U0001f4f8 {active_account.display_name}"
        if active_account
        else "\U0001f4f8 No Account"
    )
    keyboard.extend(
        [
            [
                InlineKeyboardButton(
                    account_label,
                    callback_data=f"select_account:{queue_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "\U0001f4f1 Open Instagram", url="https://www.instagram.com/"
                ),
            ],
        ]
    )

    return InlineKeyboardMarkup(keyboard)


def build_error_recovery_keyboard(
    queue_id: str,
    enable_instagram_api: bool = False,
) -> InlineKeyboardMarkup:
    """Build the keyboard shown after an auto-post failure.

    Similar to the standard keyboard but with a "Retry" button instead of
    Auto Post, and no account selector.

    Args:
        queue_id: The queue item UUID string
        enable_instagram_api: Whether to show the Retry Auto Post button

    Returns:
        InlineKeyboardMarkup with retry and fallback options
    """
    keyboard = []

    if enable_instagram_api:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "\U0001f504 Retry Auto Post",
                    callback_data=f"autopost:{queue_id}",
                ),
            ]
        )

    keyboard.extend(
        [
            [
                InlineKeyboardButton(
                    "\u2705 Posted", callback_data=f"posted:{queue_id}"
                ),
                InlineKeyboardButton(
                    "\u23ed\ufe0f Skip", callback_data=f"skip:{queue_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    "\U0001f4f1 Open Instagram",
                    url="https://www.instagram.com/",
                ),
            ],
            [
                InlineKeyboardButton(
                    "\U0001f6ab Reject", callback_data=f"reject:{queue_id}"
                ),
            ],
        ]
    )

    return InlineKeyboardMarkup(keyboard)


# =========================================================================
# Pattern 3: Cancel Button Keyboard (for settings edit flows)
# =========================================================================


CANCEL_KEYBOARD = InlineKeyboardMarkup(
    [[InlineKeyboardButton("\u274c Cancel", callback_data="settings_edit_cancel")]]
)
"""Pre-built keyboard with a single Cancel button for settings edit flows.

Used in all settings edit prompts (posts_per_day, hours_start, hours_end)
and their error states. This is a module-level constant because the keyboard
never changes.
"""


# =========================================================================
# Pattern 4: Settings Edit State Cleanup
# =========================================================================


SETTINGS_EDIT_KEYS = [
    "settings_edit_state",
    "settings_edit_chat_id",
    "settings_edit_message_id",
    "settings_edit_hours_start",
]
"""All context.user_data keys used during a settings edit conversation."""


def clear_settings_edit_state(context) -> None:
    """Clear all settings edit conversation state from context.user_data.

    Call this when a settings edit conversation ends (success, cancel, or error).
    Safely pops all keys without raising if they don't exist.

    Args:
        context: The Telegram CallbackContext or equivalent with user_data dict
    """
    for key in SETTINGS_EDIT_KEYS:
        context.user_data.pop(key, None)


ADD_ACCOUNT_KEYS = [
    "add_account_state",
    "add_account_data",
    "add_account_chat_id",
    "add_account_messages",
]
"""All context.user_data keys used during an add-account conversation."""


def clear_add_account_state(context) -> None:
    """Clear all add-account conversation state from context.user_data.

    Call this when the add-account conversation ends (success, cancel, or error).

    Args:
        context: The Telegram CallbackContext or equivalent with user_data dict
    """
    for key in ADD_ACCOUNT_KEYS:
        context.user_data.pop(key, None)
```

### Step 2: Update `telegram_callbacks.py` -- Use `validate_queue_item` and `build_queue_action_keyboard`

**File**: `src/services/core/telegram_callbacks.py`

**2a. Add import at top of file (after existing imports, around line 11):**

**BEFORE** (lines 1-14):

```python
"""Telegram callback handlers - queue action callbacks (posted, skipped, rejected, resume, reset)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.config.settings import settings
from src.utils.logger import logger
from datetime import datetime, timedelta

if TYPE_CHECKING:
    from src.services.core.telegram_service import TelegramService
```

**AFTER**:

```python
"""Telegram callback handlers - queue action callbacks (posted, skipped, rejected, resume, reset)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.config.settings import settings
from src.services.core.telegram_utils import (
    validate_queue_item,
    validate_queue_and_media,
    build_queue_action_keyboard,
)
from src.utils.logger import logger
from datetime import datetime, timedelta

if TYPE_CHECKING:
    from src.services.core.telegram_service import TelegramService
```

**2b. Replace queue item validation in `_do_complete_queue_action` (lines 68-73):**

**BEFORE**:

```python
    async def _do_complete_queue_action(
        self,
        queue_id: str,
        user,
        query,
        status: str,
        success: bool,
        caption: str,
        callback_name: str,
    ):
        """Internal implementation of queue action completion (runs under lock)."""
        queue_item = self.service.queue_repo.get_by_id(queue_id)

        if not queue_item:
            await query.edit_message_caption(caption="\u26a0\ufe0f Queue item not found")
            return
```

**AFTER**:

```python
    async def _do_complete_queue_action(
        self,
        queue_id: str,
        user,
        query,
        status: str,
        success: bool,
        caption: str,
        callback_name: str,
    ):
        """Internal implementation of queue action completion (runs under lock)."""
        queue_item = await validate_queue_item(self.service, queue_id, query)
        if not queue_item:
            return
```

**2c. Replace `handle_back` validation and keyboard building (lines 175-226):**

**BEFORE**:

```python
    async def handle_back(self, queue_id: str, user, query):
        """Handle 'Back' button - restore original queue item message."""
        queue_item = self.service.queue_repo.get_by_id(queue_id)

        if not queue_item:
            await query.edit_message_caption(caption="\u26a0\ufe0f Queue item not found")
            return

        media_item = self.service.media_repo.get_by_id(str(queue_item.media_item_id))

        if not media_item:
            await query.edit_message_caption(caption="\u26a0\ufe0f Media item not found")
            return

        # Rebuild original caption
        caption = self.service._build_caption(media_item, queue_item)

        # Rebuild original keyboard (including Auto Post if enabled)
        keyboard = []
        if settings.ENABLE_INSTAGRAM_API:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "\U0001f916 Auto Post to Instagram",
                        callback_data=f"autopost:{queue_id}",
                    ),
                ]
            )
        keyboard.extend(
            [
                [
                    InlineKeyboardButton(
                        "\u2705 Posted", callback_data=f"posted:{queue_id}"
                    ),
                    InlineKeyboardButton("\u23ed\ufe0f Skip", callback_data=f"skip:{queue_id}"),
                ],
                [
                    InlineKeyboardButton(
                        "\U0001f4f1 Open Instagram", url="https://www.instagram.com/"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "\U0001f6ab Reject", callback_data=f"reject:{queue_id}"
                    ),
                ],
            ]
        )

        await query.edit_message_caption(
            caption=caption, reply_markup=InlineKeyboardMarkup(keyboard)
        )
```

**AFTER**:

```python
    async def handle_back(self, queue_id: str, user, query):
        """Handle 'Back' button - restore original queue item message."""
        queue_item, media_item = await validate_queue_and_media(
            self.service, queue_id, query
        )
        if not queue_item:
            return

        # Rebuild original caption
        caption = self.service._build_caption(media_item, queue_item)

        # Rebuild original keyboard
        # NOTE: handle_back uses settings.ENABLE_INSTAGRAM_API (env var) rather than
        # chat_settings.enable_instagram_api (DB). This is a pre-existing inconsistency
        # that should be addressed separately. Do not change this behavior here.
        reply_markup = build_queue_action_keyboard(
            queue_id=queue_id,
            enable_instagram_api=settings.ENABLE_INSTAGRAM_API,
        )

        await query.edit_message_caption(caption=caption, reply_markup=reply_markup)
```

> **Important note**: The `handle_back` method's existing keyboard does NOT include the account selector button, while `send_notification`, `handle_cancel_reject`, and `rebuild_posting_workflow` do include it. The `build_queue_action_keyboard` utility always includes the account selector. This means `handle_back` will now show the account selector button, which is actually the correct behavior (it was previously missing). If you need to preserve the exact old behavior for `handle_back`, you would need to add an `include_account_selector` parameter. However, adding the button is an improvement, not a regression.

**2d. Replace `handle_reject_confirmation` validation (lines 230-235):**

**BEFORE**:

```python
    async def handle_reject_confirmation(self, queue_id: str, user, query):
        """Show confirmation dialog before permanently rejecting media."""
        queue_item = self.service.queue_repo.get_by_id(queue_id)

        if not queue_item:
            await query.edit_message_caption(caption="\u26a0\ufe0f Queue item not found")
            return
```

**AFTER**:

```python
    async def handle_reject_confirmation(self, queue_id: str, user, query):
        """Show confirmation dialog before permanently rejecting media."""
        queue_item = await validate_queue_item(self.service, queue_id, query)
        if not queue_item:
            return
```

**2e. Replace `handle_cancel_reject` validation and keyboard (lines 281-360):**

**BEFORE**:

```python
    async def handle_cancel_reject(self, queue_id: str, user, query):
        """Cancel rejection and restore original buttons."""
        queue_item = self.service.queue_repo.get_by_id(queue_id)

        if not queue_item:
            await query.edit_message_caption(caption="\u26a0\ufe0f Queue item not found")
            return

        # Get media item for caption rebuild
        media_item = self.service.media_repo.get_by_id(str(queue_item.media_item_id))

        if not media_item:
            await query.edit_message_caption(caption="\u26a0\ufe0f Media item not found")
            return

        chat_id = query.message.chat_id

        # Get active account for caption and button
        active_account = self.service.ig_account_service.get_active_account(chat_id)

        # Rebuild original caption
        caption = self.service._build_caption(
            media_item, queue_item, active_account=active_account
        )

        # Get chat settings for enable_instagram_api check (use DB, not env var)
        chat_settings = self.service.settings_service.get_settings(chat_id)

        # Rebuild original keyboard (including Auto Post if enabled)
        keyboard = []
        if chat_settings.enable_instagram_api:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "\U0001f916 Auto Post to Instagram",
                        callback_data=f"autopost:{queue_id}",
                    ),
                ]
            )

        # Status action buttons (grouped together)
        keyboard.extend(
            [
                [
                    InlineKeyboardButton(
                        "\u2705 Posted", callback_data=f"posted:{queue_id}"
                    ),
                    InlineKeyboardButton("\u23ed\ufe0f Skip", callback_data=f"skip:{queue_id}"),
                ],
                [
                    InlineKeyboardButton(
                        "\U0001f6ab Reject", callback_data=f"reject:{queue_id}"
                    ),
                ],
            ]
        )

        # Instagram-related buttons (grouped together)
        account_label = (
            f"\U0001f4f8 {active_account.display_name}" if active_account else "\U0001f4f8 No Account"
        )
        keyboard.extend(
            [
                [
                    InlineKeyboardButton(
                        account_label,
                        callback_data=f"select_account:{queue_id}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "\U0001f4f1 Open Instagram", url="https://www.instagram.com/"
                    ),
                ],
            ]
        )

        await query.edit_message_caption(
            caption=caption, reply_markup=InlineKeyboardMarkup(keyboard)
        )
```

**AFTER**:

```python
    async def handle_cancel_reject(self, queue_id: str, user, query):
        """Cancel rejection and restore original buttons."""
        queue_item, media_item = await validate_queue_and_media(
            self.service, queue_id, query
        )
        if not queue_item:
            return

        chat_id = query.message.chat_id

        # Get active account for caption and button
        active_account = self.service.ig_account_service.get_active_account(chat_id)

        # Rebuild original caption
        caption = self.service._build_caption(
            media_item, queue_item, active_account=active_account
        )

        # Get chat settings for enable_instagram_api check (use DB, not env var)
        chat_settings = self.service.settings_service.get_settings(chat_id)

        reply_markup = build_queue_action_keyboard(
            queue_id=queue_id,
            enable_instagram_api=chat_settings.enable_instagram_api,
            active_account=active_account,
        )

        await query.edit_message_caption(caption=caption, reply_markup=reply_markup)
```

**2f. Replace `handle_rejected` validation (lines 382-385):**

**BEFORE**:

```python
        queue_item = self.service.queue_repo.get_by_id(queue_id)

        if not queue_item:
            await query.edit_message_caption(caption="\u26a0\ufe0f Queue item not found")
            return
```

**AFTER**:

```python
        queue_item = await validate_queue_item(self.service, queue_id, query)
        if not queue_item:
            return
```

### Step 3: Update `telegram_autopost.py` -- Use `validate_queue_item` and `build_error_recovery_keyboard`

**File**: `src/services/core/telegram_autopost.py`

**3a. Add import (after existing imports, around line 9):**

**BEFORE** (lines 7-12):

```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.services.core.telegram_service import _escape_markdown
from src.config.settings import settings
from src.utils.logger import logger
from datetime import datetime
```

**AFTER**:

```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.services.core.telegram_service import _escape_markdown
from src.services.core.telegram_utils import validate_queue_item, build_error_recovery_keyboard
from src.config.settings import settings
from src.utils.logger import logger
from datetime import datetime
```

**3b. Replace `_locked_autopost` validation (lines 57-60):**

**BEFORE**:

```python
    async def _locked_autopost(self, queue_id, user, query, cancel_flag):
        """Autopost implementation that runs under the operation lock."""
        queue_item = self.service.queue_repo.get_by_id(queue_id)

        if not queue_item:
            await query.edit_message_caption(caption="\u26a0\ufe0f Queue item not found")
            return
```

**AFTER**:

```python
    async def _locked_autopost(self, queue_id, user, query, cancel_flag):
        """Autopost implementation that runs under the operation lock."""
        queue_item = await validate_queue_item(self.service, queue_id, query)
        if not queue_item:
            return
```

**3c. Replace error recovery keyboard (lines 412-445):**

**BEFORE**:

```python
            # Rebuild keyboard with all buttons
            keyboard = []
            if settings.ENABLE_INSTAGRAM_API:
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            "\U0001f504 Retry Auto Post",
                            callback_data=f"autopost:{queue_id}",
                        ),
                    ]
                )
            keyboard.extend(
                [
                    [
                        InlineKeyboardButton(
                            "\u2705 Posted", callback_data=f"posted:{queue_id}"
                        ),
                        InlineKeyboardButton(
                            "\u23ed\ufe0f Skip", callback_data=f"skip:{queue_id}"
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "\U0001f4f1 Open Instagram",
                            url="https://www.instagram.com/",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "\U0001f6ab Reject", callback_data=f"reject:{queue_id}"
                        ),
                    ],
                ]
            )
```

**AFTER**:

```python
            # Rebuild keyboard with retry and fallback options
            reply_markup = build_error_recovery_keyboard(
                queue_id=queue_id,
                enable_instagram_api=settings.ENABLE_INSTAGRAM_API,
            )
```

Then update the `edit_message_caption` call that follows to use `reply_markup=reply_markup` instead of `reply_markup=InlineKeyboardMarkup(keyboard)`:

**BEFORE**:

```python
            await query.edit_message_caption(
                caption=caption,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )
```

**AFTER**:

```python
            await query.edit_message_caption(
                caption=caption,
                reply_markup=reply_markup,
                parse_mode="Markdown",
            )
```

### Step 4: Update `telegram_accounts.py` -- Use `validate_queue_item`, `validate_queue_and_media`, `build_queue_action_keyboard`, and `clear_add_account_state`

**File**: `src/services/core/telegram_accounts.py`

**4a. Add import (after line 9):**

**BEFORE** (lines 7-9):

```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.utils.logger import logger
```

**AFTER**:

```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.services.core.telegram_utils import (
    validate_queue_item,
    validate_queue_and_media,
    build_queue_action_keyboard,
    clear_add_account_state,
)
from src.utils.logger import logger
```

**4b. Replace `handle_post_account_selector` validation (lines 613-616):**

**BEFORE**:

```python
        # Get queue item to preserve context
        queue_item = self.service.queue_repo.get_by_id(queue_id)
        if not queue_item:
            await query.edit_message_caption(caption="\u26a0\ufe0f Queue item not found")
            return
```

**AFTER**:

```python
        # Get queue item to preserve context
        queue_item = await validate_queue_item(self.service, queue_id, query)
        if not queue_item:
            return
```

**4c. Replace `rebuild_posting_workflow` validation and keyboard (lines 775-853):**

**BEFORE**:

```python
    async def rebuild_posting_workflow(self, queue_id: str, query):
        """Rebuild the original posting workflow message."""
        queue_item = self.service.queue_repo.get_by_id(queue_id)
        if not queue_item:
            await query.edit_message_caption(caption="\u26a0\ufe0f Queue item not found")
            return

        media_item = self.service.media_repo.get_by_id(str(queue_item.media_item_id))
        if not media_item:
            await query.edit_message_caption(caption="\u26a0\ufe0f Media item not found")
            return

        chat_id = query.message.chat_id

        # Get active account for caption and button
        active_account = self.service.ig_account_service.get_active_account(chat_id)

        # Rebuild caption with current account
        caption = self.service._build_caption(
            media_item, queue_item, active_account=active_account
        )

        # Rebuild keyboard with account selector
        chat_settings = self.service.settings_service.get_settings(chat_id)
        keyboard = []

        if chat_settings.enable_instagram_api:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "\U0001f916 Auto Post to Instagram",
                        callback_data=f"autopost:{queue_id}",
                    ),
                ]
            )

        # Status action buttons (grouped together)
        keyboard.extend(
            [
                [
                    InlineKeyboardButton(
                        "\u2705 Posted", callback_data=f"posted:{queue_id}"
                    ),
                    InlineKeyboardButton("\u23ed\ufe0f Skip", callback_data=f"skip:{queue_id}"),
                ],
                [
                    InlineKeyboardButton(
                        "\U0001f6ab Reject", callback_data=f"reject:{queue_id}"
                    ),
                ],
            ]
        )

        # Instagram-related buttons (grouped together)
        account_label = (
            f"\U0001f4f8 {active_account.display_name}" if active_account else "\U0001f4f8 No Account"
        )
        keyboard.extend(
            [
                [
                    InlineKeyboardButton(
                        account_label,
                        callback_data=f"select_account:{queue_id}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "\U0001f4f1 Open Instagram", url="https://www.instagram.com/"
                    ),
                ],
            ]
        )

        await query.edit_message_caption(
            caption=caption, reply_markup=InlineKeyboardMarkup(keyboard)
        )
```

**AFTER**:

```python
    async def rebuild_posting_workflow(self, queue_id: str, query):
        """Rebuild the original posting workflow message."""
        queue_item, media_item = await validate_queue_and_media(
            self.service, queue_id, query
        )
        if not queue_item:
            return

        chat_id = query.message.chat_id

        # Get active account for caption and button
        active_account = self.service.ig_account_service.get_active_account(chat_id)

        # Rebuild caption with current account
        caption = self.service._build_caption(
            media_item, queue_item, active_account=active_account
        )

        # Rebuild keyboard with account selector
        chat_settings = self.service.settings_service.get_settings(chat_id)
        reply_markup = build_queue_action_keyboard(
            queue_id=queue_id,
            enable_instagram_api=chat_settings.enable_instagram_api,
            active_account=active_account,
        )

        await query.edit_message_caption(caption=caption, reply_markup=reply_markup)
```

**4d. Replace add account state cleanup (4 locations):**

In `handle_add_account_message` success path (around lines 328-331), replace:

```python
                context.user_data.pop("add_account_state", None)
                context.user_data.pop("add_account_data", None)
                context.user_data.pop("add_account_chat_id", None)
                context.user_data.pop("add_account_messages", None)
```

with:

```python
                clear_add_account_state(context)
```

In `handle_add_account_message` error path (around lines 438-441), replace:

```python
                context.user_data.pop("add_account_state", None)
                context.user_data.pop("add_account_data", None)
                context.user_data.pop("add_account_chat_id", None)
                context.user_data.pop("add_account_messages", None)
```

with:

```python
                clear_add_account_state(context)
```

In `handle_add_account_cancel` (around lines 492-495), replace:

```python
        context.user_data.pop("add_account_state", None)
        context.user_data.pop("add_account_data", None)
        context.user_data.pop("add_account_chat_id", None)
        context.user_data.pop("add_account_messages", None)
```

with:

```python
        clear_add_account_state(context)
```

### Step 5: Update `telegram_settings.py` -- Use `CANCEL_KEYBOARD` and `clear_settings_edit_state`

**File**: `src/services/core/telegram_settings.py`

**5a. Add import (after line 9):**

**BEFORE** (lines 7-9):

```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.utils.logger import logger
```

**AFTER**:

```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.services.core.telegram_utils import CANCEL_KEYBOARD, clear_settings_edit_state
from src.utils.logger import logger
```

**5b. Replace all cancel keyboard constructions (6 locations).**

In every place where this pattern appears:

```python
            keyboard = [
                [
                    InlineKeyboardButton(
                        "\u274c Cancel", callback_data="settings_edit_cancel"
                    )
                ]
            ]
```

followed by `reply_markup=InlineKeyboardMarkup(keyboard)`, replace `InlineKeyboardMarkup(keyboard)` with `CANCEL_KEYBOARD`.

Specifically, in `handle_settings_edit_start` (2 occurrences, around lines 175-188 and 196-209):

**BEFORE** (first occurrence):

```python
            keyboard = [
                [
                    InlineKeyboardButton(
                        "\u274c Cancel", callback_data="settings_edit_cancel"
                    )
                ]
            ]

            await query.edit_message_text(
                f"...",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
```

**AFTER**:

```python
            await query.edit_message_text(
                f"...",
                parse_mode="Markdown",
                reply_markup=CANCEL_KEYBOARD,
            )
```

Repeat for all 6 occurrences. Remove the `keyboard = [...]` variable assignment each time and pass `CANCEL_KEYBOARD` directly.

**5c. Replace all settings edit state cleanup (3 locations).**

In `handle_settings_edit_message` posts_per_day success (around lines 240-241):

**BEFORE**:

```python
                context.user_data.pop("settings_edit_state", None)
                context.user_data.pop("settings_edit_chat_id", None)
```

**AFTER**:

```python
                clear_settings_edit_state(context)
```

In `handle_settings_edit_message` hours_end success (around lines 339-342):

**BEFORE**:

```python
                context.user_data.pop("settings_edit_state", None)
                context.user_data.pop("settings_edit_chat_id", None)
                context.user_data.pop("settings_edit_hours_start", None)
                context.user_data.pop("settings_edit_message_id", None)
```

**AFTER**:

```python
                clear_settings_edit_state(context)
```

In `handle_settings_edit_cancel` (around lines 378-381):

**BEFORE**:

```python
        context.user_data.pop("settings_edit_state", None)
        context.user_data.pop("settings_edit_chat_id", None)
        context.user_data.pop("settings_edit_hours_start", None)
        context.user_data.pop("settings_edit_message_id", None)
```

**AFTER**:

```python
        clear_settings_edit_state(context)
```

> **Note**: The posts_per_day success path (step 5c, first occurrence) currently only pops 2 of the 4 keys. Using `clear_settings_edit_state` will now also pop `settings_edit_hours_start` and `settings_edit_message_id`, which is harmless (they won't exist in that flow, and `.pop(key, None)` handles that gracefully). This is actually a minor bug fix -- if a user started editing hours, cancelled, then edited posts_per_day, the stale `settings_edit_hours_start` key would have lingered.

---

## Verification Checklist

- [ ] `src/services/core/telegram_utils.py` exists and contains all 4 patterns
- [ ] `ruff check src/services/core/telegram_utils.py` passes
- [ ] `ruff check src/services/core/telegram_callbacks.py` passes
- [ ] `ruff check src/services/core/telegram_autopost.py` passes
- [ ] `ruff check src/services/core/telegram_accounts.py` passes
- [ ] `ruff check src/services/core/telegram_settings.py` passes
- [ ] `ruff format --check src/services/core/` passes
- [ ] `pytest tests/src/services/test_telegram_callbacks.py` passes (all 19 existing tests)
- [ ] `pytest tests/src/services/test_telegram_accounts.py` passes
- [ ] `pytest tests/src/services/test_telegram_settings.py` passes
- [ ] `pytest` full test suite passes
- [ ] No remaining `"\u26a0\ufe0f Queue item not found"` patterns in handler files (search to verify all were replaced)
- [ ] `telegram_callbacks.py` imports `validate_queue_item` and/or `validate_queue_and_media` from `telegram_utils`
- [ ] `telegram_autopost.py` imports `validate_queue_item` and `build_error_recovery_keyboard` from `telegram_utils`
- [ ] `telegram_accounts.py` imports `validate_queue_item`, `validate_queue_and_media`, `build_queue_action_keyboard`, and `clear_add_account_state` from `telegram_utils`
- [ ] `telegram_settings.py` imports `CANCEL_KEYBOARD` and `clear_settings_edit_state` from `telegram_utils`
- [ ] Keyboard button text, callback_data values, and button ordering are identical to the originals

---

## What NOT To Do

1. **Do NOT change `send_notification()` in `telegram_service.py` in this phase.** That method builds the keyboard slightly differently (it reads `chat_settings.enable_instagram_api` from the database and has specific verbose/caption logic). It is a candidate for using `build_queue_action_keyboard` in a future phase, but changing it now increases the scope and risk of this PR.

2. **Do NOT make `telegram_utils.py` a class.** It is a module of standalone functions and constants. There is no shared state to manage. Using a class would add unnecessary complexity and go against the composition pattern used by the handler modules.

3. **Do NOT change callback_data strings.** The callback data format (e.g., `"posted:{queue_id}"`, `"autopost:{queue_id}"`) must remain identical. The dispatcher in `telegram_service.py` parses these strings to route callbacks. Changing them would break the routing.

4. **Do NOT change the `InlineKeyboardButton` import in handler files that still build custom keyboards.** For example, `telegram_callbacks.py` still needs `InlineKeyboardButton` for the reject confirmation dialog (which has unique "Yes/No" buttons). Only remove the import if the file no longer uses it directly.

5. **Do NOT add business logic to `telegram_utils.py`.** This module should contain only UI-level utilities (keyboard builders, validation helpers, state cleanup). No database queries, no posting logic, no interaction logging. If you find yourself adding service calls, you are putting logic in the wrong place.

6. **Do NOT extract the `handle_back` method's keyboard as a separate function from `build_queue_action_keyboard`.** The old `handle_back` keyboard was missing the account selector button -- this was a bug, not an intentional design choice. The unified `build_queue_action_keyboard` corrects this inconsistency.

7. **Do NOT change the error message text.** The string `"\u26a0\ufe0f Queue item not found"` and `"\u26a0\ufe0f Media item not found"` must remain identical to their current values. Tests assert on these strings (e.g., `test_telegram_callbacks.py` line 123: `assert "not found" in str(call_args)`).

8. **Do NOT remove the `InlineKeyboardMarkup` import from `telegram_settings.py`.** Even after extracting `CANCEL_KEYBOARD`, the settings handlers still build other keyboards (e.g., the schedule confirmation dialog, the settings menu itself) that use `InlineKeyboardMarkup` directly.
