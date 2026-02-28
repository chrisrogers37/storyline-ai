# Phase 05: Telegram Service Split

**Status**: ✅ COMPLETE
**Started**: 2026-02-28
**Completed**: 2026-02-28
**PR**: #91
**PR Title**: Extract notification sending and caption building into TelegramNotificationService
**Risk Level**: Low
**Estimated Effort**: Medium (1-2 hours)
**Files Modified**: 3 existing + 2 new
**Dependencies**: None
**Blocks**: None

---

## Context

`telegram_service.py` (795 lines) combines 6 distinct responsibilities. The highest-value extraction is the notification/caption system (~280 lines) which is self-contained and has clear boundaries. This reduces the main file to ~515 lines and isolates the most frequently-modified code (caption formatting changes with every UI tweak).

---

## Implementation Plan

### 1. Create TelegramNotificationService

**New file**: `src/services/core/telegram_notification.py`

Extract these methods from `telegram_service.py`:

| Method | Lines in telegram_service.py | Purpose |
|--------|------------------------------|---------|
| `send_notification()` | ~276-420 | Orchestrate photo + caption + keyboard dispatch |
| `_build_caption()` | ~421-445 | Route to style builder |
| `_build_simple_caption()` | ~447-482 | Basic caption format |
| `_build_enhanced_caption()` | ~484-532 | Emoji/workflow caption format |
| `_get_header_emoji()` | ~534-553 | Tag-based emoji selection |

Also extract the keyboard construction logic currently embedded inside `send_notification()` (~lines 322-373) into a dedicated `_build_keyboard()` method.

**Structure**:
```python
# src/services/core/telegram_notification.py

from src.utils.logger import logger


class TelegramNotificationService:
    """Handles notification sending, caption building, and keyboard construction."""

    def __init__(self, telegram_service):
        """
        Args:
            telegram_service: Parent TelegramService for access to
                bot, repos, and settings.
        """
        self.service = telegram_service

    async def send_notification(self, queue_item_id, force_sent=False):
        """Send a notification for a queue item. Returns True on success."""
        # ... moved from telegram_service.py ...

    def _build_keyboard(self, queue_item, media_item, settings):
        """Build inline keyboard buttons for the notification."""
        # ... extracted from within send_notification() ...

    def _build_caption(self, media_item, queue_item, settings):
        """Route to the appropriate caption style.

        Note: Inlines the verbose check (settings.show_verbose_notifications)
        directly instead of calling self.service._is_verbose(settings).
        """
        # ... moved from telegram_service.py ...

    def _build_simple_caption(self, media_item, queue_item):
        """Build basic notification caption."""
        # ... moved from telegram_service.py ...

    def _build_enhanced_caption(self, media_item, queue_item, settings):
        """Build enhanced notification caption with emojis and instructions."""
        # ... moved from telegram_service.py ...

    def _get_header_emoji(self, category):
        """Get emoji for category tag."""
        # ... moved from telegram_service.py ...
```

**Key detail**: The constructor takes the parent `TelegramService` as a dependency, following the existing composition pattern used by all handler modules (telegram_commands, telegram_callbacks, etc.).

### 2. Wire up in TelegramService

**File**: `src/services/core/telegram_service.py`

**In `__init__()`**, add:
```python
from src.services.core.telegram_notification import TelegramNotificationService

# After existing handler initialization:
self.notification_service = TelegramNotificationService(self)
```

**Add delegation method** (preserves backward compatibility for all handler modules):
```python
async def send_notification(self, queue_item_id, force_sent=False):
    """Delegate to notification service."""
    return await self.notification_service.send_notification(
        queue_item_id, force_sent=force_sent
    )
```

**Remove** the extracted methods from `telegram_service.py`:
- `send_notification()` (replaced by delegation)
- `_build_caption()`
- `_build_simple_caption()`
- `_build_enhanced_caption()`
- `_get_header_emoji()`
- Inline keyboard construction code (now in `_build_keyboard()`)

### 3. Resolve internal dependencies

The extracted `send_notification()` method accesses several things from `TelegramService`:
- `self.bot` — for sending messages
- `self.media_repo` — for fetching media items
- `self.queue_repo` — for fetching queue items
- `self.history_repo` — for checking posting history
- `self.settings_service` — for notification preferences
- `self.interaction_service` — for logging bot responses
- `self.instagram_account_service` — for account labels on buttons
- `MediaSourceFactory` — lazy import for media source

All accessed via `self.service.<attribute>` in the new class. No new dependencies are introduced.

### 4. Create tests for TelegramNotificationService

**New file**: `tests/src/services/test_telegram_notification.py`

```python
import pytest
from unittest.mock import Mock, AsyncMock, patch
from src.services.core.telegram_notification import TelegramNotificationService


@pytest.fixture
def mock_telegram_service():
    """Mock parent TelegramService with required attributes."""
    service = Mock()
    service.bot = AsyncMock()
    service.media_repo = Mock()
    service.queue_repo = Mock()
    service.history_repo = Mock()
    service.settings_service = Mock()
    service.interaction_service = Mock()
    service.instagram_account_service = Mock()
    return service


@pytest.fixture
def notification_service(mock_telegram_service):
    return TelegramNotificationService(mock_telegram_service)


class TestBuildCaption:
    def test_routes_to_simple_when_not_verbose(self, notification_service):
        settings = Mock(show_verbose_notifications=False)
        media = Mock(file_name="test.jpg", category="memes")
        queue_item = Mock()
        # ... test that _build_simple_caption is called

    def test_routes_to_enhanced_when_verbose(self, notification_service):
        settings = Mock(show_verbose_notifications=True)
        media = Mock(file_name="test.jpg", category="memes")
        queue_item = Mock()
        # ... test that _build_enhanced_caption is called


class TestGetHeaderEmoji:
    def test_known_category(self, notification_service):
        # Test that known categories return expected emojis
        pass

    def test_unknown_category(self, notification_service):
        # Test fallback emoji for unknown category
        pass


class TestBuildKeyboard:
    def test_includes_autopost_when_api_enabled(self, notification_service):
        # Test keyboard includes auto-post button when Instagram API is on
        pass

    def test_excludes_autopost_when_api_disabled(self, notification_service):
        # Test keyboard excludes auto-post button when API is off
        pass
```

### 5. Update existing TelegramService tests

**File**: `tests/src/services/test_telegram_service.py`

- Tests that call `service.send_notification()` still work (delegation method)
- Move caption/keyboard unit tests to `test_telegram_notification.py`
- Keep integration-level tests in the original file

---

## Test Plan

```bash
# 1. Run new notification service tests
pytest tests/src/services/test_telegram_notification.py -v

# 2. Run existing telegram tests (should pass with delegation)
pytest tests/src/services/test_telegram_service.py -v

# 3. Run all handler tests (they call service.send_notification)
pytest tests/src/services/test_telegram_callbacks.py -v
pytest tests/src/services/test_telegram_autopost.py -v

# 4. Full suite
pytest

# 5. Lint
ruff check src/ tests/ && ruff format --check src/ tests/
```

---

## Verification Checklist

- [ ] `telegram_notification.py` created with all extracted methods
- [ ] `telegram_service.py` reduced from ~795 to ~515 lines
- [ ] Delegation method `send_notification()` works in TelegramService
- [ ] All handler modules (commands, callbacks, autopost, settings, accounts) still work
- [ ] No circular imports between telegram_service and telegram_notification
- [ ] New tests pass for TelegramNotificationService
- [ ] Existing tests pass unchanged or with minimal mocking updates
- [ ] `pytest` passes
- [ ] `ruff check` and `ruff format` pass
- [ ] CHANGELOG.md updated

---

## What NOT To Do

- **Don't extract callback dispatching yet** — that's a potential future phase, keep scope tight
- **Don't change handler module patterns** — they still receive `self.service` (TelegramService), and calling `self.service.send_notification()` still works via delegation
- **Don't make TelegramNotificationService extend BaseService** — it's a composition component, not a standalone service
- **Don't move `_get_or_create_user()` or lifecycle methods** — those stay in TelegramService
- **Don't create a separate keyboard service** — keyboard building is tightly coupled to notification sending
