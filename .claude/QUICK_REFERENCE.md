# Storyline AI - Quick Reference for Claude

## ⚠️ CRITICAL SAFETY RULES

**NEVER run these commands** (they post to Instagram or modify production):
- `storyline-cli process-queue`
- `storyline-cli create-schedule`
- `storyline-cli reset-queue`
- `python -m src.main`

**SAFE commands** (read-only):
- `storyline-cli list-queue` / `list-media` / `list-categories` / `list-users`
- `storyline-cli check-health` / `instagram-status`
- `pytest` (all tests)

---

## Architecture (3-Layer)

```
CLI/Telegram → Services → Repositories → Models/DB
```

**NEVER violate layer boundaries:**
- CLI/API calls Services only
- Services call Repositories only
- Repositories return Models

---

## Key Directories

| Path | Purpose |
|------|---------|
| `src/services/core/` | Business logic (Phase 1) |
| `src/services/integrations/` | Instagram API, external services |
| `src/repositories/` | Database access (CRUD only) |
| `src/models/` | SQLAlchemy models |
| `cli/commands/` | CLI command definitions |
| `tests/` | Mirrors src/ structure |

---

## Common Tasks

| Task | Command/Action |
|------|----------------|
| Run tests | `pytest tests/ -v` |
| Check linting | `ruff check src/ tests/` |
| Format code | `ruff format src/ tests/` |
| Check bot status | `/telegram-status` skill |
| Check DB status | `/db-status` skill |
| Pre-commit check | `ruff check src/ tests/ && ruff format --check src/ tests/ && pytest` |

---

## Database (Neon PostgreSQL)

```bash
# Connect to production database
psql "$DATABASE_URL"

# Safe queries
psql "$DATABASE_URL" -c "SELECT * FROM posting_queue WHERE status = 'pending';"
psql "$DATABASE_URL" -c "SELECT * FROM posting_history ORDER BY posted_at DESC LIMIT 10;"
psql "$DATABASE_URL" -c "SELECT * FROM instagram_accounts WHERE is_active = true;"
```

---

## Key Files to Know

| File | Contains |
|------|----------|
| `src/services/core/telegram_service.py` | Telegram bot handlers |
| `src/services/core/posting_service.py` | Posting orchestration |
| `src/services/core/scheduler.py` | Schedule creation |
| `src/services/integrations/instagram_api.py` | Instagram Graph API |
| `src/models/chat_settings.py` | Per-chat settings |

---

## Settings Flow

**Database overrides .env for these:**
- `dry_run_mode` → `chat_settings.dry_run_mode`
- `enable_instagram_api` → `chat_settings.enable_instagram_api`
- `active_instagram_account_id` → per-chat account selection

---

## CHANGELOG Reminder

Every PR must update `CHANGELOG.md` under `## [Unreleased]`
