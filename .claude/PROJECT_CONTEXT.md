# Storyline AI - Project Context

**Copy this into Claude web/phone sessions for context.**

---

## What This Project Does

Storyline AI is a self-hosted Instagram Story scheduling system with Telegram-based workflow:
1. Media files are indexed from a directory
2. A scheduler creates a posting queue with time slots
3. At each slot, the bot either:
   - Posts directly via Instagram Graph API (Phase 2), or
   - Sends the image to Telegram for manual posting (Phase 1)
4. Users interact via Telegram bot commands (/settings, /queue, /status)

---

## Architecture (3-Layer)

```
┌─────────────────────────────────────┐
│  Interface Layer                    │
│  • cli/commands/  - CLI interface   │
│  • TelegramService - Bot handlers   │
└───────────────┬─────────────────────┘
                │
┌───────────────▼─────────────────────┐
│  Service Layer (Business Logic)     │
│  • src/services/core/               │
│    - TelegramService                │
│    - PostingService                 │
│    - SchedulerService               │
│    - MediaIngestionService          │
│    - InstagramAccountService        │
│  • src/services/integrations/       │
│    - InstagramAPIService            │
│    - TokenRefreshService            │
└───────────────┬─────────────────────┘
                │
┌───────────────▼─────────────────────┐
│  Data Layer                         │
│  • src/repositories/ - CRUD only    │
│  • src/models/ - SQLAlchemy models  │
│  • PostgreSQL on Raspberry Pi       │
└─────────────────────────────────────┘
```

**STRICT RULE**: Never violate layer boundaries. Services call Repositories, never Models directly.

---

## Key Database Tables

| Table | Purpose |
|-------|---------|
| `media_items` | All indexed media (source of truth) |
| `posting_queue` | Scheduled posts (ephemeral work items) |
| `posting_history` | Permanent audit log of all posts |
| `instagram_accounts` | Multi-account support (Phase 1.5) |
| `chat_settings` | Per-Telegram-chat configuration |
| `api_tokens` | Encrypted OAuth tokens |

---

## Settings Resolution

**Database overrides .env for per-chat settings:**
- `chat_settings.dry_run_mode` overrides `DRY_RUN_MODE`
- `chat_settings.enable_instagram_api` overrides `ENABLE_INSTAGRAM_API`
- `chat_settings.active_instagram_account_id` selects which account to post from

---

## Key Files

| File | Purpose |
|------|---------|
| `src/services/core/telegram_service.py` | Telegram bot command/callback handlers |
| `src/services/core/posting_service.py` | Orchestrates posting workflow |
| `src/services/core/scheduler.py` | Creates posting schedules |
| `src/services/integrations/instagram_api.py` | Instagram Graph API wrapper |
| `src/services/core/instagram_account_service.py` | Multi-account management |
| `src/models/chat_settings.py` | Per-chat settings model |

---

## Safety Rules

**NEVER suggest running:**
- `storyline-cli process-queue` (posts to Instagram)
- `storyline-cli create-schedule` (modifies queue)
- `python -m src.main` (starts the bot)

**SAFE to suggest:**
- `storyline-cli list-queue` / `list-media` / `check-health`
- `pytest tests/`
- Database SELECT queries

---

## Current Phase: 1.6

- ✅ Phase 1: Telegram manual posting
- ✅ Phase 1.5: Multi-account support
- ✅ Phase 1.6: Settings improvements
- 🔲 Phase 2: Full Instagram API automation
- 🔲 Phase 3: Web UI

---

## Common Patterns

**Adding a new setting:**
1. Add column to `chat_settings` model
2. Create migration in `scripts/migrations/`
3. Add to `SettingsService.TOGGLEABLE_SETTINGS` if it's a toggle
4. Update Telegram /settings handler

**Adding a new command:**
1. Create handler in `TelegramService`
2. Register in `_register_handlers()`
3. Update help text

**Testing:**
- All services should have unit tests in `tests/src/services/`
- Mock repositories, never hit real database
- Run with `pytest tests/ -v`
