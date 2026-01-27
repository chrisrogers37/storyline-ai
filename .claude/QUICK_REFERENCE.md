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
| Check linting | `ruff check src/` |
| Check bot status | `/telegram-status` command |
| Quick commit | `/quick-commit` command |
| Full PR workflow | `/commit-push-pr` command |

---

## Database (Raspberry Pi)

```bash
# Connect via SSH
ssh crogberrypi "psql -U storyline_user -d storyline_ai -c 'YOUR_QUERY'"

# Safe queries
SELECT * FROM posting_queue WHERE status = 'pending';
SELECT * FROM posting_history ORDER BY posted_at DESC LIMIT 10;
SELECT * FROM instagram_accounts WHERE is_active = true;
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
