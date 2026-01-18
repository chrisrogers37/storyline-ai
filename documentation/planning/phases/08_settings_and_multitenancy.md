# Phase 8: Settings Management & Multi-Tenancy Foundation

**Status**: 📋 PLANNING
**Created**: 2026-01-18
**Priority**: High (Operational Improvement)
**Dependencies**: Phase 2 (Instagram API) - Complete

---

## Problem Statement

The current system uses environment variables (`.env`) for all configuration:

```bash
# Current: Everything in .env
DRY_RUN_MODE=true
ENABLE_INSTAGRAM_API=true
POSTS_PER_DAY=10
POSTING_HOURS_START=13
POSTING_HOURS_END=1
INSTAGRAM_ACCESS_TOKEN=EAA...
INSTAGRAM_ACCOUNT_ID=17841...
MEDIA_DIR=/path/to/media
# ... 20+ more settings
```

**Problems with this approach:**

1. **No runtime changes** - Requires service restart to change settings
2. **No user visibility** - Users can't see current config without server access
3. **Single-tenant only** - One bot instance = one configuration
4. **Poor onboarding** - New deployments require manual `.env` editing
5. **No audit trail** - No record of who changed what settings

---

## Goals

### Phase 8A: Settings UI (Minimum Viable)
- `/settings` command to view and toggle operational settings
- Database-backed settings with `.env` fallback
- No multi-tenancy yet (single chat mode)

### Phase 8B: Initialization Wizard
- `/init` command for guided first-time setup
- Walk users through all required configuration
- Validate settings before saving

### Phase 8C: Multi-Tenancy Foundation
- Per-chat settings isolation
- Per-chat Instagram account linking
- Per-chat media libraries and queues

---

## Architecture

### Settings Hierarchy

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: Infrastructure (.env - required, never in DB)     │
├─────────────────────────────────────────────────────────────┤
│  TELEGRAM_BOT_TOKEN      - Bot identity                     │
│  DATABASE_URL            - Database connection              │
│  ENCRYPTION_KEY          - Token encryption key             │
│  CLOUDINARY_CLOUD_NAME   - Cloud storage account            │
│  CLOUDINARY_API_KEY      - Cloud storage credentials        │
│  CLOUDINARY_API_SECRET   - Cloud storage credentials        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: Chat Settings (DB - per chat, runtime editable)   │
├─────────────────────────────────────────────────────────────┤
│  dry_run_mode            - Safety toggle                    │
│  enable_instagram_api    - Feature flag                     │
│  posts_per_day           - Posting frequency                │
│  posting_hours_start     - Schedule window start            │
│  posting_hours_end       - Schedule window end              │
│  instagram_account_id    - Linked IG account                │
│  instagram_username      - Display name                     │
│  media_dir               - Media source path                │
│  category_ratios         - Posting mix (JSONB)              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: Defaults (.env - fallback if not in DB)           │
├─────────────────────────────────────────────────────────────┤
│  DEFAULT_DRY_RUN_MODE=true                                  │
│  DEFAULT_POSTS_PER_DAY=3                                    │
│  DEFAULT_POSTING_HOURS_START=13                             │
│  DEFAULT_POSTING_HOURS_END=1                                │
└─────────────────────────────────────────────────────────────┘
```

### Resolution Order

When a service needs a setting:
1. Check `chat_settings` table for chat-specific value
2. If not found, use `DEFAULT_*` from `.env`
3. If no default, use hardcoded application default

---

## Data Model

### New Table: `chat_settings`

```sql
CREATE TABLE IF NOT EXISTS chat_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Chat identification
    telegram_chat_id BIGINT NOT NULL UNIQUE,
    chat_name VARCHAR(255),
    chat_type VARCHAR(20),  -- 'private', 'group', 'supergroup', 'channel'

    -- Operational settings
    dry_run_mode BOOLEAN DEFAULT true,
    enable_instagram_api BOOLEAN DEFAULT false,
    posts_per_day INTEGER DEFAULT 3,
    posting_hours_start INTEGER DEFAULT 13,  -- UTC hour (0-23)
    posting_hours_end INTEGER DEFAULT 1,     -- UTC hour (0-23)

    -- Instagram settings (per-chat)
    instagram_account_id VARCHAR(50),
    instagram_username VARCHAR(50),

    -- Media settings
    media_dir TEXT,

    -- Category ratios (JSONB for flexibility)
    category_ratios JSONB DEFAULT '{}',
    -- Example: {"memes": 0.7, "merch": 0.3}

    -- Initialization status
    initialized BOOLEAN DEFAULT false,
    initialized_at TIMESTAMP,
    initialized_by_user_id UUID REFERENCES users(id),

    -- Pause state (moved from in-memory)
    is_paused BOOLEAN DEFAULT false,
    paused_at TIMESTAMP,
    paused_by_user_id UUID REFERENCES users(id),

    -- Audit
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT valid_posts_per_day CHECK (posts_per_day BETWEEN 1 AND 50),
    CONSTRAINT valid_hours CHECK (posting_hours_start BETWEEN 0 AND 23
                                  AND posting_hours_end BETWEEN 0 AND 23)
);

CREATE INDEX idx_chat_settings_telegram_id ON chat_settings(telegram_chat_id);
```

### New Table: `chat_settings_history` (Audit Trail)

```sql
CREATE TABLE IF NOT EXISTS chat_settings_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chat_settings_id UUID NOT NULL REFERENCES chat_settings(id),

    -- What changed
    setting_name VARCHAR(50) NOT NULL,
    old_value TEXT,
    new_value TEXT,

    -- Who changed it
    changed_by_user_id UUID REFERENCES users(id),
    changed_by_username VARCHAR(100),

    -- When
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_settings_history_chat ON chat_settings_history(chat_settings_id);
CREATE INDEX idx_settings_history_time ON chat_settings_history(changed_at);
```

### Migration: Link Existing Tables to Chat

For multi-tenancy, existing tables need `chat_id` foreign keys:

```sql
-- Phase 8C only (multi-tenancy)
ALTER TABLE posting_queue ADD COLUMN chat_settings_id UUID REFERENCES chat_settings(id);
ALTER TABLE posting_history ADD COLUMN chat_settings_id UUID REFERENCES chat_settings(id);
ALTER TABLE media_items ADD COLUMN chat_settings_id UUID REFERENCES chat_settings(id);
ALTER TABLE api_tokens ADD COLUMN chat_settings_id UUID REFERENCES chat_settings(id);
```

---

## Service Layer

### SettingsService

```python
# src/services/core/settings_service.py

class SettingsService(BaseService):
    """
    Manage per-chat settings with .env fallback.

    Settings Resolution:
    1. Chat-specific value in DB
    2. DEFAULT_* value from .env
    3. Hardcoded application default
    """

    def __init__(self):
        super().__init__()
        self.settings_repo = ChatSettingsRepository()
        self._cache: Dict[int, ChatSettings] = {}  # telegram_chat_id -> settings
        self._cache_ttl = 60  # seconds

    # ─────────────────────────────────────────────────────────────
    # Core Methods
    # ─────────────────────────────────────────────────────────────

    def get_settings(self, telegram_chat_id: int) -> ChatSettings:
        """
        Get settings for a chat, creating defaults if not exists.

        Returns ChatSettings object with all resolved values.
        """
        # Check cache first
        if self._is_cached(telegram_chat_id):
            return self._cache[telegram_chat_id]

        # Get from DB or create with defaults
        settings = self.settings_repo.get_by_chat_id(telegram_chat_id)

        if not settings:
            settings = self._create_default_settings(telegram_chat_id)

        # Cache and return
        self._cache[telegram_chat_id] = settings
        return settings

    def update_setting(
        self,
        telegram_chat_id: int,
        setting_name: str,
        new_value: Any,
        changed_by_user_id: str,
        changed_by_username: str,
    ) -> ChatSettings:
        """
        Update a single setting for a chat.

        Records change in audit history.
        """
        settings = self.get_settings(telegram_chat_id)
        old_value = getattr(settings, setting_name)

        # Validate
        self._validate_setting(setting_name, new_value)

        # Update
        setattr(settings, setting_name, new_value)
        settings.updated_at = datetime.utcnow()
        self.settings_repo.update(settings)

        # Record history
        self.settings_repo.record_change(
            chat_settings_id=settings.id,
            setting_name=setting_name,
            old_value=str(old_value),
            new_value=str(new_value),
            changed_by_user_id=changed_by_user_id,
            changed_by_username=changed_by_username,
        )

        # Invalidate cache
        self._invalidate_cache(telegram_chat_id)

        return settings

    def toggle_setting(
        self,
        telegram_chat_id: int,
        setting_name: str,
        user_id: str,
        username: str,
    ) -> tuple[bool, str]:
        """
        Toggle a boolean setting.

        Returns (new_value, message).
        """
        settings = self.get_settings(telegram_chat_id)
        current = getattr(settings, setting_name)

        if not isinstance(current, bool):
            raise ValueError(f"{setting_name} is not a boolean setting")

        new_value = not current
        self.update_setting(
            telegram_chat_id, setting_name, new_value, user_id, username
        )

        return new_value, f"{setting_name} is now {'ON' if new_value else 'OFF'}"

    # ─────────────────────────────────────────────────────────────
    # Initialization
    # ─────────────────────────────────────────────────────────────

    def initialize_chat(
        self,
        telegram_chat_id: int,
        chat_name: str,
        chat_type: str,
        initialized_by_user_id: str,
        **initial_settings,
    ) -> ChatSettings:
        """
        Initialize settings for a new chat.

        Called by /init command after wizard completion.
        """
        settings = self.get_settings(telegram_chat_id)

        settings.chat_name = chat_name
        settings.chat_type = chat_type
        settings.initialized = True
        settings.initialized_at = datetime.utcnow()
        settings.initialized_by_user_id = initialized_by_user_id

        # Apply initial settings
        for key, value in initial_settings.items():
            if hasattr(settings, key):
                setattr(settings, key, value)

        self.settings_repo.update(settings)
        self._invalidate_cache(telegram_chat_id)

        return settings

    def is_initialized(self, telegram_chat_id: int) -> bool:
        """Check if chat has been initialized."""
        settings = self.get_settings(telegram_chat_id)
        return settings.initialized

    # ─────────────────────────────────────────────────────────────
    # Migration Helper
    # ─────────────────────────────────────────────────────────────

    def bootstrap_from_env(self, telegram_chat_id: int) -> ChatSettings:
        """
        Bootstrap chat settings from current .env values.

        Used for migrating existing single-chat deployments.
        """
        from src.config.settings import settings as env_settings

        return self.initialize_chat(
            telegram_chat_id=telegram_chat_id,
            chat_name="Migrated from .env",
            chat_type="unknown",
            initialized_by_user_id=None,
            dry_run_mode=env_settings.DRY_RUN_MODE,
            enable_instagram_api=env_settings.ENABLE_INSTAGRAM_API,
            posts_per_day=env_settings.POSTS_PER_DAY,
            posting_hours_start=env_settings.POSTING_HOURS_START,
            posting_hours_end=env_settings.POSTING_HOURS_END,
            instagram_account_id=env_settings.INSTAGRAM_ACCOUNT_ID,
            media_dir=env_settings.MEDIA_DIR,
        )
```

---

## Command Interfaces

### /settings Command

```
User: /settings

Bot: ⚙️ *Settings for GatorTails Chat*

*Operational*
├ 🔄 Dry Run Mode: *ON* [Toggle]
├ 📱 Instagram API: *ON* [Toggle]
└ ⏸️ Posting: *Active* [Pause]

*Schedule*
├ 📊 Posts/Day: *10* [Change]
└ 🕐 Hours: *1PM-1AM UTC* [Change]

*Instagram*
├ 📸 Account: *@your_account* [Change]
└ 🔑 Token: *Valid (58 days)* [Refresh]

*Media*
└ 📁 Directory: */media/stories* [View Stats]

━━━━━━━━━━━━━━━━━━━━
Last updated: 2 hours ago by @crogcrogcrog

[View History] [Export] [Reset Defaults]
```

**Button Actions:**

| Button | Action |
|--------|--------|
| `[Toggle]` | Immediate toggle, update message |
| `[Change]` | Show input prompt or picker |
| `[Pause]` | Pause/resume posting |
| `[Refresh]` | Trigger Instagram token refresh |
| `[View Stats]` | Show media library stats |
| `[View History]` | Show recent setting changes |
| `[Export]` | Export settings as JSON |
| `[Reset Defaults]` | Confirmation then reset |

### /init Command (Wizard Flow)

```
User: /init

Bot: 👋 *Welcome to Storyline AI Setup!*

I'll help you configure the bot for this chat.
This takes about 2 minutes.

[Start Setup] [Cancel]
```

**Step 1: Mode Selection**
```
Bot: *Step 1/5: Operating Mode*

How would you like to run the bot?

[🧪 Dry Run Mode]
Start in test mode - no actual posts to Instagram.
Recommended for first-time setup.

[🚀 Live Mode]
Posts will go to Instagram immediately.
Only select if you've tested before.
```

**Step 2: Instagram Connection**
```
Bot: *Step 2/5: Instagram Account*

Do you want to connect an Instagram account?

[📱 Connect Instagram]
Required for Auto Post feature.

[⏭️ Skip for Now]
You can still use manual posting via Telegram.
```

**Step 3: Posting Schedule**
```
Bot: *Step 3/5: Posting Schedule*

How many posts per day?

[3 posts] [5 posts] [10 posts] [Custom...]

What hours should posts be scheduled? (UTC)

[9AM-9PM] [1PM-1AM] [Custom...]
```

**Step 4: Media Directory**
```
Bot: *Step 4/5: Media Source*

Where are your media files stored?

Current server path: `/home/user/media/stories`

[✅ Use This Path]
[📝 Enter Different Path]
[☁️ Configure Cloud Sync] (coming soon)
```

**Step 5: Review & Confirm**
```
Bot: *Step 5/5: Review Settings*

📋 *Configuration Summary*

├ Mode: Dry Run (safe)
├ Instagram: @your_account (connected)
├ Schedule: 10 posts/day, 1PM-1AM UTC
└ Media: /home/user/media/stories (142 files)

Everything look good?

[✅ Confirm & Start] [← Back] [❌ Cancel]
```

**Completion**
```
Bot: 🎉 *Setup Complete!*

Storyline AI is now configured for this chat.

*Quick Commands:*
├ /settings - View/edit settings
├ /schedule 7 - Create 7-day schedule
├ /queue - View pending posts
└ /next - Force-send next post

Ready to create your first schedule?

[📅 Create Schedule] [📖 View Help]
```

---

## Implementation Plan

### Phase 8A: Settings UI (1-2 weeks)

**Files to Create:**
- `src/models/chat_settings.py` - SQLAlchemy model
- `src/repositories/chat_settings_repository.py` - DB operations
- `src/services/core/settings_service.py` - Business logic
- `scripts/migrations/005_chat_settings.sql` - DB migration
- `tests/src/services/test_settings_service.py` - Unit tests

**Files to Modify:**
- `src/services/core/telegram_service.py` - Add /settings command
- `src/services/core/posting.py` - Get settings from SettingsService
- `src/services/core/scheduler.py` - Get settings from SettingsService
- `src/config/settings.py` - Add DEFAULT_* fallbacks

**Deliverables:**
- [ ] `/settings` command shows current config
- [ ] Toggle buttons for boolean settings (dry_run, enable_instagram_api)
- [ ] Settings changes persisted to DB
- [ ] Audit trail for all changes
- [ ] Fallback to .env if no DB settings

### Phase 8B: Initialization Wizard (1 week)

**Files to Create:**
- `src/services/core/init_wizard.py` - Wizard state machine

**Files to Modify:**
- `src/services/core/telegram_service.py` - Add /init command, wizard handlers

**Deliverables:**
- [ ] `/init` command starts wizard
- [ ] 5-step guided setup flow
- [ ] Validation at each step
- [ ] Settings saved on completion
- [ ] Skip individual steps
- [ ] Cancel and resume support

### Phase 8C: Multi-Tenancy Foundation (2-3 weeks)

**Database Changes:**
- Add `chat_settings_id` FK to: `posting_queue`, `posting_history`, `media_items`, `api_tokens`
- Backfill existing data with default chat

**Service Changes:**
- All services accept `chat_id` parameter
- Repository queries filter by `chat_settings_id`
- Separate queues/history per chat

**Deliverables:**
- [ ] Per-chat data isolation
- [ ] Per-chat Instagram account linking
- [ ] Migration script for existing data
- [ ] Admin view of all chats

---

## Migration Strategy

### For Existing Deployments

1. **Run migration** - Creates `chat_settings` table
2. **Auto-bootstrap** - On first bot interaction:
   - Detect if settings exist for chat
   - If not, call `bootstrap_from_env()`
   - Copy all .env values to DB
   - Mark as initialized
3. **Continue operation** - Services now read from DB
4. **Optional cleanup** - Remove operational settings from .env

### Backwards Compatibility

The `SettingsService` always falls back to .env:

```python
def get_setting(self, chat_id: int, setting_name: str) -> Any:
    # Try DB first
    db_value = self._get_from_db(chat_id, setting_name)
    if db_value is not None:
        return db_value

    # Fall back to .env
    env_value = getattr(env_settings, setting_name, None)
    if env_value is not None:
        return env_value

    # Use hardcoded default
    return DEFAULTS.get(setting_name)
```

---

## Settings Reference

### Boolean Settings (Toggleable)

| Setting | Default | Description |
|---------|---------|-------------|
| `dry_run_mode` | `true` | Test mode - no actual Instagram posts |
| `enable_instagram_api` | `false` | Enable Auto Post feature |
| `is_paused` | `false` | Pause automatic posting |

### Numeric Settings

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| `posts_per_day` | `3` | 1-50 | Target posts per day |
| `posting_hours_start` | `13` | 0-23 | Schedule window start (UTC) |
| `posting_hours_end` | `1` | 0-23 | Schedule window end (UTC) |

### String Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `instagram_account_id` | `null` | Linked Instagram account |
| `instagram_username` | `null` | Display username |
| `media_dir` | `null` | Local media directory path |

### JSON Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `category_ratios` | `{}` | Category posting mix, e.g., `{"memes": 0.7, "merch": 0.3}` |

---

## Security Considerations

### Who Can Change Settings?

**Option A: Admin Only**
- Only users with `role='admin'` can use /settings
- Simpler, more secure

**Option B: Role-Based**
- Admins: All settings
- Members: View only
- Operators: Toggle dry_run, pause only

**Recommendation**: Start with Option A, add granular permissions later.

### Sensitive Settings

Some settings should have extra protection:
- `instagram_account_id` - Requires re-authentication to change
- `media_dir` - Validation that path exists and is readable
- `enable_instagram_api` - Warning when disabling

---

## Testing Requirements

### Unit Tests

```python
# tests/src/services/test_settings_service.py

class TestSettingsService:
    def test_get_settings_creates_defaults(self)
    def test_get_settings_returns_cached(self)
    def test_update_setting_records_history(self)
    def test_toggle_boolean_setting(self)
    def test_toggle_non_boolean_raises_error(self)
    def test_initialize_chat(self)
    def test_bootstrap_from_env(self)
    def test_fallback_to_env_defaults(self)
    def test_validation_rejects_invalid_values(self)

class TestChatSettingsRepository:
    def test_get_by_chat_id(self)
    def test_create_settings(self)
    def test_update_settings(self)
    def test_record_change(self)
    def test_get_history(self)
```

### Integration Tests

```python
# tests/integration/test_settings_flow.py

class TestSettingsIntegration:
    def test_settings_command_shows_config(self)
    def test_toggle_dry_run_updates_db(self)
    def test_init_wizard_creates_settings(self)
    def test_scheduler_uses_chat_settings(self)
    def test_posting_service_uses_chat_settings(self)
```

---

## Success Metrics

- **Adoption**: % of setting changes via /settings vs manual
- **Error rate**: Failed setting validations
- **Audit usage**: How often is history viewed?
- **Multi-tenancy readiness**: # of isolated chats (Phase 8C)

---

## Open Questions

1. **Cloud media sync**: Should we support cloud storage (Dropbox, Google Drive) as media source?

2. **Settings export/import**: JSON export for backup/migration between instances?

3. **Scheduled setting changes**: "Enable live mode at 9 AM tomorrow"?

4. **Setting presets**: "Production mode", "Testing mode", "Vacation mode"?

5. **Notifications**: Alert when settings change? (useful for teams)

---

## Appendix: Full Settings Command Flow

```
/settings
    │
    ├── [Toggle Dry Run] ──────────► Toggle & update message
    │
    ├── [Toggle Instagram API] ────► Toggle & update message
    │
    ├── [Pause/Resume] ────────────► Toggle is_paused & update
    │
    ├── [Change Posts/Day] ────────► Show picker (3/5/10/Custom)
    │   │
    │   └── [Custom] ──────────────► "Reply with number (1-50)"
    │                                     │
    │                                     └── Validate & save
    │
    ├── [Change Hours] ────────────► Show presets or custom
    │   │
    │   └── [Custom] ──────────────► "Reply with start hour (0-23)"
    │                                     │
    │                                     └── "Reply with end hour"
    │                                           │
    │                                           └── Validate & save
    │
    ├── [Change Instagram] ────────► Show current account
    │   │
    │   ├── [Reconnect] ───────────► OAuth flow (existing)
    │   └── [Disconnect] ──────────► Confirm & remove
    │
    ├── [View History] ────────────► Show last 10 changes
    │
    ├── [Export] ──────────────────► Send JSON file
    │
    └── [Reset Defaults] ──────────► Confirm dialog
        │
        └── [Yes, Reset] ──────────► Reset all to defaults
```

---

## Next Steps

1. Review this plan and provide feedback
2. Clarify multi-tenancy scope (8A only vs 8A+8B+8C)
3. Prioritize which settings to include first
4. Begin Phase 8A implementation

---

**Document Version**: 1.0
**Author**: Claude + Chris
**Review Status**: Draft - Awaiting Feedback
