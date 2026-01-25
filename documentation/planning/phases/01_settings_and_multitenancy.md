# Settings Management & Multi-Tenancy

**Status**: 📋 PLANNING
**Created**: 2026-01-18
**Updated**: 2026-01-24
**Priority**: Next Up
**Dependencies**: Phase 2 (Instagram API) - Complete
**Document Version**: 3.0

---

## Executive Summary

This document outlines the implementation of runtime-configurable settings and eventual multi-tenancy support. The work is split into three phases to minimize risk and allow incremental deployment.

**Current State Analysis (as of 2026-01-24):**
- All settings loaded from `.env` via Pydantic `BaseSettings`
- `DRY_RUN_MODE` can be toggled at runtime but not persisted (lost on restart)
- Pause state is in-memory only (`TelegramService._paused` class variable)
- No database-backed settings exist
- Current migration version: **005** (next: **006**)
- Type 2 SCD pattern successfully used in `category_post_case_mix` table

---

## Problem Statement

The current system uses environment variables (`.env`) for all configuration, requiring service restarts to change settings and limiting the system to single-tenant operation.

**Current Pain Points:**
- No runtime changes without restart (except DRY_RUN_MODE which isn't persisted)
- Users can't see/edit config without server access
- Single-tenant only (one bot = one config)
- No audit trail of setting changes
- Pause state lost on service restart

---

## Implementation Sequence

| Phase | Name | Scope | Estimated Effort |
|-------|------|-------|------------------|
| **1** | Settings Menu | Runtime config via `/settings` for existing features | 2-3 days |
| **2** | Cloud Media Storage | Google Drive / S3 integration, per-chat media source | 4-5 days |
| **3** | Multi-Tenancy | Full `/init` flow, per-chat isolation, audit logs | 5-7 days |

---

## Phase 1: Settings Menu

**Goal**: Expose current `.env` settings via a `/settings` command with simple toggle buttons and persist them to database.

### Current State vs Target State

| Setting | Current Source | Current Persistence | Target |
|---------|---------------|---------------------|--------|
| `dry_run_mode` | `settings.DRY_RUN_MODE` | In-memory only (can toggle via `/dryrun`) | DB with fallback to .env |
| `enable_instagram_api` | `settings.ENABLE_INSTAGRAM_API` | .env only | DB with fallback to .env |
| `is_paused` | `TelegramService._paused` class var | In-memory only (lost on restart) | DB persisted |
| `posts_per_day` | `settings.POSTS_PER_DAY` | .env only | DB with fallback to .env |
| `posting_hours_start` | `settings.POSTING_HOURS_START` | .env only | DB with fallback to .env |
| `posting_hours_end` | `settings.POSTING_HOURS_END` | .env only | DB with fallback to .env |

### UI Design

Simple inline button format:

```
User: /settings

Bot: ⚙️ *Bot Settings*

Dry Run Mode: [ON] [off]
Instagram API: [on] [OFF]
Posting: [Active] [paused]

Posts Per Day: *10* [Change]
Posting Hours: *1PM-1AM UTC* [Change]

Instagram Account: *@your_account*
Token Status: *Valid (58 days)*

[View Queue] [Create Schedule]
```

**Button Behavior:**
- `[ON]` / `[off]` - Uppercase = current state, clickable toggles
- `[Change]` - Opens input prompt (awaits next message as value)
- Immediate update on click, refresh message

### Database Schema

```sql
-- Migration: 006_chat_settings.sql
-- NOTE: Previous doc said 005, but that's taken by bot_response_logging

-- Enable UUID extension if not exists
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS chat_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Chat identification (for future multi-tenancy)
    -- For Phase 1: Use ADMIN_TELEGRAM_CHAT_ID as the single chat
    telegram_chat_id BIGINT NOT NULL UNIQUE,
    chat_name VARCHAR(255),

    -- Operational settings (mirrors .env defaults)
    dry_run_mode BOOLEAN DEFAULT true,
    enable_instagram_api BOOLEAN DEFAULT false,
    is_paused BOOLEAN DEFAULT false,
    paused_at TIMESTAMP,           -- When paused (NULL if not paused)
    paused_by_user_id UUID REFERENCES users(id),  -- Who paused

    -- Schedule settings
    posts_per_day INTEGER DEFAULT 3,
    posting_hours_start INTEGER DEFAULT 14,  -- UTC hour (0-23)
    posting_hours_end INTEGER DEFAULT 2,     -- UTC hour (0-23)

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT valid_posts_per_day CHECK (posts_per_day BETWEEN 1 AND 50),
    CONSTRAINT valid_hours_start CHECK (posting_hours_start BETWEEN 0 AND 23),
    CONSTRAINT valid_hours_end CHECK (posting_hours_end BETWEEN 0 AND 23)
);

CREATE INDEX idx_chat_settings_telegram_id ON chat_settings(telegram_chat_id);

-- Record migration
INSERT INTO schema_version (version, description, applied_at)
VALUES (6, 'Add chat_settings table for runtime configuration', NOW())
ON CONFLICT DO NOTHING;
```

### Model Implementation

**File**: `src/models/chat_settings.py`

```python
"""Chat settings model - per-chat runtime configuration."""
from sqlalchemy import Column, String, Integer, Boolean, BigInteger, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from src.config.database import Base


class ChatSettings(Base):
    """
    Per-chat runtime settings with .env fallback support.

    For Phase 1, there will be one record per deployment.
    Phase 3 introduces true multi-tenancy with one record per chat.
    """

    __tablename__ = "chat_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Chat identification
    telegram_chat_id = Column(BigInteger, nullable=False, unique=True, index=True)
    chat_name = Column(String(255))

    # Operational settings
    dry_run_mode = Column(Boolean, default=True)
    enable_instagram_api = Column(Boolean, default=False)
    is_paused = Column(Boolean, default=False)
    paused_at = Column(DateTime)
    paused_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    # Schedule settings
    posts_per_day = Column(Integer, default=3)
    posting_hours_start = Column(Integer, default=14)
    posting_hours_end = Column(Integer, default=2)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ChatSettings chat_id={self.telegram_chat_id} paused={self.is_paused}>"
```

**Update `src/models/__init__.py`:**
```python
from src.models.chat_settings import ChatSettings  # Add this line
```

### Repository Implementation

**File**: `src/repositories/chat_settings_repository.py`

```python
"""Chat settings repository - CRUD operations for runtime settings."""
from typing import Optional
from datetime import datetime

from src.repositories.base_repository import BaseRepository
from src.models.chat_settings import ChatSettings
from src.config.settings import settings as env_settings


class ChatSettingsRepository(BaseRepository):
    """
    Repository for ChatSettings CRUD operations.

    Implements .env fallback: If no DB record exists, creates one
    from current .env values on first access.
    """

    def get_by_chat_id(self, telegram_chat_id: int) -> Optional[ChatSettings]:
        """Get settings for a specific chat."""
        result = self.db.query(ChatSettings).filter(
            ChatSettings.telegram_chat_id == telegram_chat_id
        ).first()
        self.end_read_transaction()
        return result

    def get_or_create(self, telegram_chat_id: int) -> ChatSettings:
        """
        Get settings for chat, creating from .env defaults if not exists.

        This is the primary access method - ensures a record always exists.
        """
        existing = self.get_by_chat_id(telegram_chat_id)
        if existing:
            return existing

        # Bootstrap from .env values
        chat_settings = ChatSettings(
            telegram_chat_id=telegram_chat_id,
            dry_run_mode=env_settings.DRY_RUN_MODE,
            enable_instagram_api=env_settings.ENABLE_INSTAGRAM_API,
            is_paused=False,
            posts_per_day=env_settings.POSTS_PER_DAY,
            posting_hours_start=env_settings.POSTING_HOURS_START,
            posting_hours_end=env_settings.POSTING_HOURS_END,
        )
        self.db.add(chat_settings)
        self.db.commit()
        self.db.refresh(chat_settings)
        return chat_settings

    def update(
        self,
        telegram_chat_id: int,
        **kwargs
    ) -> ChatSettings:
        """
        Update settings for a chat.

        Args:
            telegram_chat_id: Chat to update
            **kwargs: Fields to update (dry_run_mode, is_paused, etc.)

        Returns:
            Updated ChatSettings record
        """
        chat_settings = self.get_or_create(telegram_chat_id)

        for key, value in kwargs.items():
            if hasattr(chat_settings, key):
                setattr(chat_settings, key, value)

        chat_settings.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(chat_settings)
        return chat_settings

    def set_paused(
        self,
        telegram_chat_id: int,
        is_paused: bool,
        user_id: Optional[str] = None
    ) -> ChatSettings:
        """
        Set pause state with tracking.

        Args:
            telegram_chat_id: Chat to update
            is_paused: New pause state
            user_id: UUID of user who changed state
        """
        update_data = {
            "is_paused": is_paused,
            "paused_at": datetime.utcnow() if is_paused else None,
            "paused_by_user_id": user_id if is_paused else None,
        }
        return self.update(telegram_chat_id, **update_data)
```

### Service Implementation

**File**: `src/services/core/settings_service.py`

```python
"""Settings service - runtime configuration management."""
from typing import Optional, Any, Dict
from datetime import datetime

from src.services.base_service import BaseService
from src.repositories.chat_settings_repository import ChatSettingsRepository
from src.models.chat_settings import ChatSettings
from src.models.user import User
from src.utils.logger import logger


# Allowed settings that can be toggled/changed
TOGGLEABLE_SETTINGS = {"dry_run_mode", "enable_instagram_api", "is_paused"}
NUMERIC_SETTINGS = {"posts_per_day", "posting_hours_start", "posting_hours_end"}


class SettingsService(BaseService):
    """
    Per-chat settings with .env fallback.

    Resolution order:
    1. DB value for chat (if exists)
    2. .env default (on first access, bootstrapped to DB)

    All setting changes are tracked via ServiceRun for audit.
    """

    def __init__(self):
        super().__init__()
        self.settings_repo = ChatSettingsRepository()

    def get_settings(self, telegram_chat_id: int) -> ChatSettings:
        """
        Get or create settings for a chat.

        Args:
            telegram_chat_id: Telegram chat/channel ID

        Returns:
            ChatSettings record (created from .env if first access)
        """
        with self.track_execution(
            "get_settings",
            triggered_by="system",
            input_params={"telegram_chat_id": telegram_chat_id}
        ):
            return self.settings_repo.get_or_create(telegram_chat_id)

    def toggle_setting(
        self,
        telegram_chat_id: int,
        setting_name: str,
        user: User
    ) -> bool:
        """
        Toggle a boolean setting.

        Args:
            telegram_chat_id: Chat to update
            setting_name: One of TOGGLEABLE_SETTINGS
            user: User performing the change

        Returns:
            New value after toggle

        Raises:
            ValueError: If setting_name not in TOGGLEABLE_SETTINGS
        """
        if setting_name not in TOGGLEABLE_SETTINGS:
            raise ValueError(f"Setting '{setting_name}' is not toggleable")

        with self.track_execution(
            "toggle_setting",
            user_id=user.id if user else None,
            triggered_by="user",
            input_params={"setting_name": setting_name}
        ) as run_id:
            settings = self.settings_repo.get_or_create(telegram_chat_id)
            old_value = getattr(settings, setting_name)
            new_value = not old_value

            if setting_name == "is_paused":
                self.settings_repo.set_paused(
                    telegram_chat_id,
                    new_value,
                    str(user.id) if user else None
                )
            else:
                self.settings_repo.update(telegram_chat_id, **{setting_name: new_value})

            self.set_result_summary(run_id, {
                "setting": setting_name,
                "old_value": old_value,
                "new_value": new_value,
                "changed_by": user.telegram_username if user else "system"
            })

            logger.info(
                f"Setting '{setting_name}' toggled: {old_value} -> {new_value} "
                f"by @{user.telegram_username if user else 'system'}"
            )

            return new_value

    def update_setting(
        self,
        telegram_chat_id: int,
        setting_name: str,
        value: Any,
        user: User
    ) -> ChatSettings:
        """
        Update a setting value.

        Args:
            telegram_chat_id: Chat to update
            setting_name: Setting to change
            value: New value
            user: User performing the change

        Returns:
            Updated ChatSettings

        Raises:
            ValueError: If setting_name not valid or value out of range
        """
        if setting_name not in TOGGLEABLE_SETTINGS | NUMERIC_SETTINGS:
            raise ValueError(f"Unknown setting: {setting_name}")

        with self.track_execution(
            "update_setting",
            user_id=user.id if user else None,
            triggered_by="user",
            input_params={"setting_name": setting_name, "value": value}
        ) as run_id:
            settings = self.settings_repo.get_or_create(telegram_chat_id)
            old_value = getattr(settings, setting_name)

            # Validate numeric settings
            if setting_name == "posts_per_day":
                value = int(value)
                if not 1 <= value <= 50:
                    raise ValueError("posts_per_day must be between 1 and 50")
            elif setting_name in ("posting_hours_start", "posting_hours_end"):
                value = int(value)
                if not 0 <= value <= 23:
                    raise ValueError("Hour must be between 0 and 23")

            updated = self.settings_repo.update(telegram_chat_id, **{setting_name: value})

            self.set_result_summary(run_id, {
                "setting": setting_name,
                "old_value": old_value,
                "new_value": value,
                "changed_by": user.telegram_username if user else "system"
            })

            return updated

    def get_settings_display(self, telegram_chat_id: int) -> Dict[str, Any]:
        """
        Get settings formatted for display in Telegram.

        Returns dict with all settings and their display values.
        """
        settings = self.get_settings(telegram_chat_id)

        return {
            "dry_run_mode": settings.dry_run_mode,
            "enable_instagram_api": settings.enable_instagram_api,
            "is_paused": settings.is_paused,
            "paused_at": settings.paused_at,
            "paused_by_user_id": settings.paused_by_user_id,
            "posts_per_day": settings.posts_per_day,
            "posting_hours_start": settings.posting_hours_start,
            "posting_hours_end": settings.posting_hours_end,
            "updated_at": settings.updated_at,
        }
```

### TelegramService Integration

**Add to `src/services/core/telegram_service.py`:**

1. **Import and initialize SettingsService:**

```python
# At top of file, add import:
from src.services.core.settings_service import SettingsService

# In __init__, add:
self.settings_service = SettingsService()
```

2. **Register /settings command handler:**

```python
# In initialize(), add:
self.application.add_handler(CommandHandler("settings", self._handle_settings))
```

3. **Add callback handlers for settings buttons:**

```python
# In _handle_callback(), add cases:
elif action == "settings_toggle":
    await self._handle_settings_toggle(data, user, query)
elif action == "settings_change":
    await self._handle_settings_change_prompt(data, user, query)
```

4. **Implement handler methods:**

```python
async def _handle_settings(self, update, context):
    """Handle /settings command - show settings menu."""
    user = self._get_or_create_user(update.effective_user)
    chat_id = update.effective_chat.id

    # Log interaction
    self.interaction_service.log_command(
        user_id=str(user.id),
        command="/settings",
        telegram_chat_id=chat_id,
    )

    settings = self.settings_service.get_settings_display(chat_id)

    # Build message
    message = "⚙️ *Bot Settings*\n\n"

    # Build inline keyboard
    keyboard = [
        # Row 1: Dry Run toggle
        [
            InlineKeyboardButton(
                "✅ Dry Run" if settings["dry_run_mode"] else "Dry Run",
                callback_data="settings_toggle:dry_run_mode"
            ),
        ],
        # Row 2: Instagram API toggle
        [
            InlineKeyboardButton(
                "✅ Instagram API" if settings["enable_instagram_api"] else "Instagram API",
                callback_data="settings_toggle:enable_instagram_api"
            ),
        ],
        # Row 3: Pause toggle
        [
            InlineKeyboardButton(
                "⏸️ Paused" if settings["is_paused"] else "▶️ Active",
                callback_data="settings_toggle:is_paused"
            ),
        ],
        # Row 4: Posts per day
        [
            InlineKeyboardButton(
                f"Posts/Day: {settings['posts_per_day']} [Change]",
                callback_data="settings_change:posts_per_day"
            ),
        ],
        # Row 5: Posting hours
        [
            InlineKeyboardButton(
                f"Hours: {settings['posting_hours_start']}:00-{settings['posting_hours_end']}:00 UTC",
                callback_data="settings_change:posting_hours"
            ),
        ],
        # Row 6: Quick actions
        [
            InlineKeyboardButton("📋 Queue", callback_data="quick:queue"),
            InlineKeyboardButton("📅 Schedule", callback_data="quick:schedule"),
        ],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        message,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


async def _handle_settings_toggle(self, setting_name: str, user, query):
    """Handle settings toggle button click."""
    chat_id = query.message.chat_id

    try:
        new_value = self.settings_service.toggle_setting(chat_id, setting_name, user)

        # Log the interaction
        self.interaction_service.log_callback(
            user_id=str(user.id),
            callback_name=f"settings_toggle:{setting_name}",
            context={"new_value": new_value},
            telegram_chat_id=chat_id,
        )

        # Refresh the settings display
        await self._refresh_settings_message(query)

    except ValueError as e:
        await query.answer(f"Error: {e}", show_alert=True)


async def _refresh_settings_message(self, query):
    """Refresh the settings message with current values."""
    chat_id = query.message.chat_id
    settings = self.settings_service.get_settings_display(chat_id)

    # Rebuild keyboard with updated values
    keyboard = [
        [InlineKeyboardButton(
            "✅ Dry Run" if settings["dry_run_mode"] else "Dry Run",
            callback_data="settings_toggle:dry_run_mode"
        )],
        [InlineKeyboardButton(
            "✅ Instagram API" if settings["enable_instagram_api"] else "Instagram API",
            callback_data="settings_toggle:enable_instagram_api"
        )],
        [InlineKeyboardButton(
            "⏸️ Paused" if settings["is_paused"] else "▶️ Active",
            callback_data="settings_toggle:is_paused"
        )],
        [InlineKeyboardButton(
            f"Posts/Day: {settings['posts_per_day']} [Change]",
            callback_data="settings_change:posts_per_day"
        )],
        [InlineKeyboardButton(
            f"Hours: {settings['posting_hours_start']}:00-{settings['posting_hours_end']}:00 UTC",
            callback_data="settings_change:posting_hours"
        )],
        [
            InlineKeyboardButton("📋 Queue", callback_data="quick:queue"),
            InlineKeyboardButton("📅 Schedule", callback_data="quick:schedule"),
        ],
    ]

    await query.edit_message_reply_markup(
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    await query.answer("Setting updated!")
```

### Update PostingService to Use SettingsService

**Modify `src/services/core/posting.py`:**

```python
# Add import
from src.services.core.settings_service import SettingsService

# In __init__
self.settings_service = SettingsService()

# Replace direct settings access with:
def _get_chat_settings(self, chat_id: int):
    """Get settings for the current chat."""
    return self.settings_service.get_settings(chat_id)

# In process_pending_posts(), replace:
#   if self.telegram_service.is_paused:
# With:
#   settings = self._get_chat_settings(settings.ADMIN_TELEGRAM_CHAT_ID)
#   if settings.is_paused:
```

### Update SchedulerService to Use SettingsService

**Modify `src/services/core/scheduler.py`:**

```python
# Add import
from src.services.core.settings_service import SettingsService

# In __init__
self.settings_service = SettingsService()

# In create_schedule(), replace:
#   posts_per_day = settings.POSTS_PER_DAY
#   start_hour = settings.POSTING_HOURS_START
# With:
#   chat_settings = self.settings_service.get_settings(settings.ADMIN_TELEGRAM_CHAT_ID)
#   posts_per_day = chat_settings.posts_per_day
#   start_hour = chat_settings.posting_hours_start
```

### Remove/Deprecate TelegramService._paused

**Current code to replace:**

```python
# Current (in-memory):
class TelegramService(BaseService):
    _paused = False  # Class-level variable

    @property
    def is_paused(self) -> bool:
        return TelegramService._paused
```

**Replace with:**

```python
# New (database-backed):
@property
def is_paused(self) -> bool:
    """Check if posting is paused (from database)."""
    settings = self.settings_service.get_settings(self.channel_id)
    return settings.is_paused
```

### Migration Path

1. **Deploy migration 006** - Creates empty `chat_settings` table
2. **Deploy code changes** - Services start using SettingsService
3. **First access** - `get_or_create()` bootstraps from current `.env` values
4. **Runtime changes** - Now persisted to DB, survive restarts
5. **No breaking changes** - Falls back to .env if no record exists

### Test Plan

**Unit Tests** (`tests/src/services/test_settings_service.py`):

```python
import pytest
from unittest.mock import Mock, patch

class TestSettingsService:

    def test_get_settings_creates_from_env_on_first_access(self):
        """First access should bootstrap from .env values."""
        pass

    def test_toggle_setting_flips_boolean(self):
        """Toggle should flip dry_run_mode from True to False."""
        pass

    def test_toggle_invalid_setting_raises_error(self):
        """Toggling non-toggleable setting should raise ValueError."""
        pass

    def test_update_posts_per_day_validates_range(self):
        """posts_per_day outside 1-50 should raise ValueError."""
        pass

    def test_pause_tracks_user_and_timestamp(self):
        """Pausing should record who paused and when."""
        pass
```

**Integration Tests** (`tests/integration/test_settings_flow.py`):

```python
class TestSettingsIntegration:

    def test_settings_persist_across_restart(self):
        """Changed settings should survive service restart."""
        pass

    def test_pause_state_persists(self):
        """Pause state should be maintained after restart."""
        pass
```

---

## Phase 2: Cloud Media Storage

*(Content unchanged from original document - see lines 157-234)*

**Key Implementation Notes:**

1. Add `media_source_type` and `media_source_config` to `chat_settings` table
2. Create abstract `MediaSourceService` interface
3. Implement providers: `LocalMediaProvider`, `GoogleDriveProvider`, `S3MediaProvider`
4. OAuth flow for Google Drive requires state management (consider using `user_interactions` table)
5. S3 credentials must be encrypted using existing `ENCRYPTION_KEY` pattern from `api_tokens`

---

## Phase 3: Multi-Tenancy

*(Content unchanged from original document - see lines 237-427)*

**Key Implementation Notes:**

1. All existing tables need `chat_settings_id` FK added
2. All queries must filter by `chat_settings_id`
3. Type 2 SCD pattern for `chat_settings_history` mirrors existing `category_post_case_mix`
4. `/init` wizard flow should reuse existing inline keyboard patterns
5. Remove `.env` bootstrap in favor of explicit `/init`

---

## Files Summary

### Phase 1 Files to Create

| File | Purpose |
|------|---------|
| `src/models/chat_settings.py` | ChatSettings SQLAlchemy model |
| `src/repositories/chat_settings_repository.py` | CRUD operations |
| `src/services/core/settings_service.py` | Business logic with audit |
| `scripts/migrations/006_chat_settings.sql` | Database migration |
| `tests/src/services/test_settings_service.py` | Unit tests |
| `tests/src/repositories/test_chat_settings_repository.py` | Repository tests |

### Phase 1 Files to Modify

| File | Changes |
|------|---------|
| `src/models/__init__.py` | Import ChatSettings |
| `src/services/core/telegram_service.py` | Add /settings command, toggle handlers |
| `src/services/core/posting.py` | Use SettingsService for is_paused, dry_run |
| `src/services/core/scheduler.py` | Use SettingsService for posts_per_day, hours |

---

## Open Questions

1. **Google Drive folder structure**: Should we mirror Drive folder structure as categories?
   - *Recommendation*: Yes, treat top-level folders as categories

2. **S3 credentials per-chat**: Store in `media_source_config` encrypted, or separate table?
   - *Recommendation*: Use `media_source_config` JSONB with encrypted values, like existing `api_tokens` pattern

3. **Settings export**: JSON export for backup/migration?
   - *Recommendation*: Add `/settings export` command in Phase 3

4. **Rate limiting**: Per-chat rate limits for commands?
   - *Recommendation*: Not needed for Phase 1; consider for Phase 3 multi-tenancy

5. **Conversation state for /settings change**: How to handle "Change posts per day" flow?
   - *Recommendation*: Use `ConversationHandler` from python-telegram-bot or store pending input in `user_interactions.context`

---

## Appendix: Existing Patterns Reference

### BaseService Pattern (MUST follow)

```python
class MyService(BaseService):
    def __init__(self):
        super().__init__()
        self.my_repo = MyRepository()

    def my_method(self, param: str):
        with self.track_execution(
            "my_method",
            user_id=user.id,
            triggered_by="user",
            input_params={"param": param}
        ) as run_id:
            # Business logic here
            result = self.my_repo.do_something(param)
            self.set_result_summary(run_id, {"processed": 1})
            return result
```

### BaseRepository Pattern (MUST follow)

```python
class MyRepository(BaseRepository):
    def get_by_id(self, id: str) -> Optional[MyModel]:
        result = self.db.query(MyModel).filter(MyModel.id == id).first()
        self.end_read_transaction()  # IMPORTANT: End read transaction
        return result

    def create(self, **kwargs) -> MyModel:
        item = MyModel(**kwargs)
        self.db.add(item)
        self.db.commit()  # IMPORTANT: Commit writes
        self.db.refresh(item)
        return item
```

### Telegram Command Handler Pattern

```python
async def _handle_mycommand(self, update, context):
    """Handle /mycommand - description."""
    user = self._get_or_create_user(update.effective_user)
    chat_id = update.effective_chat.id

    # Log the command
    self.interaction_service.log_command(
        user_id=str(user.id),
        command="/mycommand",
        telegram_chat_id=chat_id,
    )

    # Do work...

    # Reply
    await update.message.reply_text("Response", parse_mode="Markdown")
```

---

**Document Version**: 3.0
**Last Updated**: 2026-01-24
**Author**: Claude + Chris
**Reviewed By**: (pending)
