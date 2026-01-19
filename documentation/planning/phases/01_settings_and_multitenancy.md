# Settings Management & Multi-Tenancy

**Status**: 📋 PLANNING
**Created**: 2026-01-18
**Priority**: Next Up
**Dependencies**: Phase 2 (Instagram API) - Complete

---

## Problem Statement

The current system uses environment variables (`.env`) for all configuration, requiring service restarts to change settings and limiting the system to single-tenant operation.

**Current Pain Points:**
- No runtime changes without restart
- Users can't see/edit config without server access
- Single-tenant only (one bot = one config)
- No audit trail of setting changes

---

## Implementation Sequence

| Phase | Name | Scope |
|-------|------|-------|
| **1** | Settings Menu | Runtime config via `/settings` for existing features |
| **2** | Cloud Media Storage | Google Drive / S3 integration, per-chat media source |
| **3** | Multi-Tenancy | Full `/init` flow, per-chat isolation, audit logs |

---

## Phase 1: Settings Menu

**Goal**: Expose current `.env` settings via a `/settings` command with simple toggle buttons.

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
- `[Change]` - Opens input prompt
- Immediate update on click, refresh message

### Settings to Expose

| Setting | Type | Current Source |
|---------|------|----------------|
| `dry_run_mode` | Toggle | `DRY_RUN_MODE` env |
| `enable_instagram_api` | Toggle | `ENABLE_INSTAGRAM_API` env |
| `is_paused` | Toggle | In-memory (TelegramService) |
| `posts_per_day` | Number | `POSTS_PER_DAY` env |
| `posting_hours_start` | Number | `POSTING_HOURS_START` env |
| `posting_hours_end` | Number | `POSTING_HOURS_END` env |

### Database Schema

```sql
-- Migration: 005_chat_settings.sql

CREATE TABLE IF NOT EXISTS chat_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Chat identification
    telegram_chat_id BIGINT NOT NULL UNIQUE,
    chat_name VARCHAR(255),

    -- Operational settings
    dry_run_mode BOOLEAN DEFAULT true,
    enable_instagram_api BOOLEAN DEFAULT false,
    is_paused BOOLEAN DEFAULT false,
    posts_per_day INTEGER DEFAULT 3,
    posting_hours_start INTEGER DEFAULT 13,
    posting_hours_end INTEGER DEFAULT 1,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_posts_per_day CHECK (posts_per_day BETWEEN 1 AND 50),
    CONSTRAINT valid_hours CHECK (
        posting_hours_start BETWEEN 0 AND 23
        AND posting_hours_end BETWEEN 0 AND 23
    )
);

CREATE INDEX idx_chat_settings_telegram_id ON chat_settings(telegram_chat_id);
```

### Service Layer

```python
# src/services/core/settings_service.py

class SettingsService(BaseService):
    """
    Per-chat settings with .env fallback.

    Resolution order:
    1. DB value for chat
    2. .env default
    3. Hardcoded default
    """

    def get_settings(self, telegram_chat_id: int) -> ChatSettings:
        """Get or create settings for chat."""

    def toggle_setting(self, chat_id: int, setting: str, user: User) -> bool:
        """Toggle boolean setting, return new value."""

    def update_setting(self, chat_id: int, setting: str, value: Any, user: User):
        """Update setting value."""
```

### Permissions

**Phase 1**: Anyone in the channel can change settings.

### Files to Create/Modify

| Action | File |
|--------|------|
| Create | `src/models/chat_settings.py` |
| Create | `src/repositories/chat_settings_repository.py` |
| Create | `src/services/core/settings_service.py` |
| Create | `scripts/migrations/005_chat_settings.sql` |
| Modify | `src/services/core/telegram_service.py` - Add /settings |
| Modify | `src/services/core/posting.py` - Use SettingsService |
| Modify | `src/services/core/scheduler.py` - Use SettingsService |

### Migration Path

1. Deploy with new `chat_settings` table
2. On first `/settings` call, auto-create record from current `.env` values
3. Services check DB first, fall back to `.env`
4. No breaking changes to existing deployments

---

## Phase 2: Cloud Media Storage

**Goal**: Replace local `MEDIA_DIR` with cloud storage (Google Drive or S3), configurable per-chat.

### Supported Providers

| Provider | Auth Method | Use Case |
|----------|-------------|----------|
| Google Drive | OAuth2 | Self-hosted users with existing Drive |
| AWS S3 | API Keys | Production deployments |
| Local Path | None | Development / legacy |

### Database Schema Additions

```sql
-- Add to chat_settings
ALTER TABLE chat_settings ADD COLUMN media_source_type VARCHAR(20) DEFAULT 'local';
-- Values: 'local', 'google_drive', 's3'

ALTER TABLE chat_settings ADD COLUMN media_source_config JSONB DEFAULT '{}';
-- For google_drive: {"folder_id": "xxx", "refresh_token": "encrypted"}
-- For s3: {"bucket": "xxx", "prefix": "stories/", "region": "us-east-1"}
-- For local: {"path": "/media/stories"}
```

### Google Drive Integration

**OAuth Flow:**
1. User runs `/connect-drive`
2. Bot sends OAuth URL
3. User authorizes, gets code
4. User pastes code back to bot
5. Bot exchanges for tokens, stores encrypted
6. User selects folder from Drive

**Sync Behavior:**
- On-demand fetch (not full sync)
- Cache file list with TTL
- Download to temp for processing
- Upload to Cloudinary for Instagram

### S3 Integration

**Setup Flow:**
1. User runs `/connect-s3`
2. Bot prompts for: bucket, region, access key, secret key
3. Bot validates credentials
4. Bot lists folders, user selects prefix
5. Credentials stored encrypted

### Service Interface

```python
# src/services/integrations/media_source.py

class MediaSourceService(BaseService):
    """Abstract media source - local, Drive, or S3."""

    def list_files(self, chat_id: int) -> List[MediaFile]:
        """List available media files."""

    def download_file(self, chat_id: int, file_id: str) -> Path:
        """Download file to temp location."""

    def get_provider(self, chat_id: int) -> MediaProvider:
        """Get configured provider for chat."""
```

### Files to Create

| File | Purpose |
|------|---------|
| `src/services/integrations/media_source.py` | Abstract interface |
| `src/services/integrations/google_drive.py` | Drive provider |
| `src/services/integrations/s3_media.py` | S3 provider |
| `src/services/integrations/local_media.py` | Local provider |

---

## Phase 3: Multi-Tenancy

**Goal**: Full per-chat isolation with `/init` wizard, audit logs, and Type 2 SCD for settings history.

### /init Wizard Flow

```
User: /init

Bot: 👋 *Welcome to Storyline AI!*

Let's set up the bot for this chat. This takes ~2 minutes.

[Start Setup]
```

**Step 1: Operating Mode**
```
Dry Run Mode: [ON] [off]

Recommended: Start with Dry Run ON to test safely.

[Next →]
```

**Step 2: Instagram Connection**
```
Connect your Instagram Business account:

[🔗 Connect Instagram] [Skip for now]
```

**Step 3: Media Source**
```
Where are your media files?

[📁 Local Path] [📂 Google Drive] [☁️ AWS S3]
```

**Step 4: Schedule**
```
Posts per day: [3] [5] [10] [Custom]
Posting hours (UTC): [9AM-9PM] [1PM-1AM] [Custom]

[Next →]
```

**Step 5: Confirm**
```
*Setup Summary*

Mode: Dry Run
Instagram: @your_account
Media: Google Drive (My Stories folder)
Schedule: 10 posts/day, 1PM-1AM

[✅ Complete Setup] [← Back]
```

### Database Schema - Full Multi-Tenancy

```sql
-- Settings audit log (Type 2 SCD)
CREATE TABLE IF NOT EXISTS chat_settings_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chat_settings_id UUID NOT NULL REFERENCES chat_settings(id),

    -- Snapshot of all settings at this point
    settings_snapshot JSONB NOT NULL,

    -- Change metadata
    changed_by_user_id UUID REFERENCES users(id),
    changed_by_username VARCHAR(100),
    change_reason VARCHAR(255),

    -- SCD fields
    valid_from TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    valid_to TIMESTAMP,  -- NULL = current
    is_current BOOLEAN DEFAULT true,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_settings_history_chat ON chat_settings_history(chat_settings_id);
CREATE INDEX idx_settings_history_current ON chat_settings_history(chat_settings_id, is_current)
    WHERE is_current = true;

-- Per-chat Instagram tokens
ALTER TABLE api_tokens ADD COLUMN chat_settings_id UUID REFERENCES chat_settings(id);
CREATE INDEX idx_api_tokens_chat ON api_tokens(chat_settings_id);

-- Per-chat media items
ALTER TABLE media_items ADD COLUMN chat_settings_id UUID REFERENCES chat_settings(id);
CREATE INDEX idx_media_items_chat ON media_items(chat_settings_id);

-- Per-chat queues
ALTER TABLE posting_queue ADD COLUMN chat_settings_id UUID REFERENCES chat_settings(id);
CREATE INDEX idx_posting_queue_chat ON posting_queue(chat_settings_id);

-- Per-chat history
ALTER TABLE posting_history ADD COLUMN chat_settings_id UUID REFERENCES chat_settings(id);
CREATE INDEX idx_posting_history_chat ON posting_history(chat_settings_id);
```

### Multi-Channel Request Routing

```python
# src/services/core/telegram_service.py

class TelegramService:
    """
    Routes all requests through chat_id context.

    Every handler extracts chat_id and passes to services.
    Services query data filtered by chat_settings_id.
    """

    async def _handle_command(self, update, context):
        chat_id = update.effective_chat.id
        settings = self.settings_service.get_settings(chat_id)

        # All subsequent calls use chat_id context
        await self._process_with_context(chat_id, settings, ...)
```

### Remove Bootstrap

Phase 3 removes the `.env` bootstrap approach:
- `/init` is required for new chats
- No automatic creation from `.env`
- Clean separation between infrastructure (.env) and operational (DB) config

### Audit Log Features

```
User: /settings history

Bot: *Settings Change History*

📅 Jan 18, 2:30 PM - @chris
├ dry_run_mode: true → false
└ Reason: "Ready for production"

📅 Jan 17, 4:15 PM - @sarah
├ posts_per_day: 3 → 10
└ Reason: "Increasing frequency"

📅 Jan 15, 10:00 AM - @chris
└ Initial setup

[Load More]
```

---

## Settings Hierarchy (Final)

```
┌─────────────────────────────────────────────────────────────┐
│  .env (Infrastructure Only)                                  │
├─────────────────────────────────────────────────────────────┤
│  TELEGRAM_BOT_TOKEN       - Bot identity                    │
│  DATABASE_URL             - Database connection             │
│  ENCRYPTION_KEY           - Token encryption                │
│  CLOUDINARY_*             - Cloud storage (shared)          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  chat_settings (Per-Chat, Runtime Editable)                 │
├─────────────────────────────────────────────────────────────┤
│  dry_run_mode             - Safety toggle                   │
│  enable_instagram_api     - Feature flag                    │
│  is_paused                - Posting state                   │
│  posts_per_day            - Schedule config                 │
│  posting_hours_*          - Schedule window                 │
│  media_source_type        - local/drive/s3                  │
│  media_source_config      - Provider-specific config        │
│  instagram_account_id     - Linked IG account               │
│  category_ratios          - Posting mix                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  chat_settings_history (Type 2 SCD Audit Trail)             │
├─────────────────────────────────────────────────────────────┤
│  Full snapshot at each change point                         │
│  Who changed, when, why                                     │
│  Query historical settings at any point in time             │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation Checklist

### Phase 1: Settings Menu
- [ ] Create `chat_settings` table (migration 005)
- [ ] Create ChatSettings model
- [ ] Create ChatSettingsRepository
- [ ] Create SettingsService
- [ ] Add `/settings` command to TelegramService
- [ ] Implement toggle button handlers
- [ ] Implement "Change" input handlers
- [ ] Update PostingService to use SettingsService
- [ ] Update SchedulerService to use SettingsService
- [ ] Write unit tests
- [ ] Write integration tests

### Phase 2: Cloud Media Storage
- [ ] Design MediaSourceService interface
- [ ] Implement LocalMediaProvider (wrap existing)
- [ ] Implement GoogleDriveProvider
- [ ] Implement S3MediaProvider
- [ ] Add `/connect-drive` command
- [ ] Add `/connect-s3` command
- [ ] Add media source fields to chat_settings
- [ ] Update MediaIngestionService to use providers
- [ ] Write unit tests

### Phase 3: Multi-Tenancy
- [ ] Add chat_settings_id FK to all relevant tables
- [ ] Create chat_settings_history table (Type 2 SCD)
- [ ] Implement `/init` wizard flow
- [ ] Update all services for chat_id context
- [ ] Implement settings history tracking
- [ ] Add `/settings history` command
- [ ] Remove bootstrap_from_env
- [ ] Migration script for existing data
- [ ] Write unit tests
- [ ] Write integration tests

---

## Open Questions

1. **Google Drive folder structure**: Should we mirror Drive folder structure as categories?

2. **S3 credentials per-chat**: Store in `media_source_config` encrypted, or separate table?

3. **Settings export**: JSON export for backup/migration?

4. **Rate limiting**: Per-chat rate limits for commands?

---

**Document Version**: 2.0
**Last Updated**: 2026-01-18
**Author**: Claude + Chris
