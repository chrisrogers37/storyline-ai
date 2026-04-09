# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.
Domain-specific rules are in `.claude/rules/` and load automatically when working in matching files.

---

## CRITICAL SAFETY RULES

**THIS SYSTEM POSTS TO INSTAGRAM. DO NOT TRIGGER POSTING WITHOUT EXPLICIT USER APPROVAL.**

### NEVER run these commands:
```bash
storyline-cli process-queue          # Posts to Instagram/Telegram
storyline-cli process-queue --force  # Posts to Instagram/Telegram
python -m src.main                   # Starts posting scheduler
storyline-cli create-schedule        # Modifies production schedule
storyline-cli reset-queue            # Modifies production queue
storyline-cli instagram-auth         # Modifies authentication
```

### SAFE commands you CAN run:
```bash
storyline-cli list-queue             # Reading/inspection only
storyline-cli list-media
storyline-cli list-categories
storyline-cli list-users
storyline-cli check-health
storyline-cli instagram-status
storyline-cli validate-image <path>
storyline-cli category-mix-history
storyline-cli sync-media
storyline-cli sync-status
storyline-cli backfill-instagram --dry-run
storyline-cli backfill-status
storyline-cli pool-health
storyline-cli dedup-media            # Dry-run by default (--apply mutates)
pytest                               # Tests - always safe
```

### Before ANY posting-related action:
1. **STOP** and ask the user for explicit confirmation
2. Explain exactly what will happen
3. Wait for user to type "yes" or approve

### Telegram Web (web.telegram.org):
- **NEVER type or click** — view/screenshot only
- All bot interactions must go through the database or user's phone

---

## Cloud Deployment (Railway + Neon)

- **Worker**: `python -m src.main` (scheduler + Telegram bot)
- **API**: `uvicorn src.api.app:app` (REST API + Mini App)
- **Database**: Neon PostgreSQL — connect via `psql "$DATABASE_URL"`
- Env vars are per-service — must set on both worker AND API
- **NEVER run on production**: `process-queue`, `python -m src.main`, or mutating SQL on `posting_history`

---

## Project Overview

**Storyline AI** is a self-hosted Instagram Story scheduling and automation system with Telegram-based team collaboration.

**Core Philosophy**: Phased deployment — 100% manual posting (Phase 1), optional Instagram API automation (Phase 2), web UI (Phase 3).

**Tech Stack**: Python 3.10+, FastAPI, Neon PostgreSQL, Telegram Bot, Railway deployment, Next.js landing site.

## Architecture: STRICT SEPARATION OF CONCERNS

**CRITICAL** — each layer is strictly isolated. NEVER violate layer boundaries:

- **CLI/API** → calls Services (never touches Repositories or Models directly)
- **UI** → calls API (never calls Services directly)
- **Services** → orchestrate business logic, call Repositories
- **Repositories** → CRUD operations, return Models
- **Models** → database schema definitions only (no business logic)

## Essential Commands

```bash
# Development setup
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt && pip install -e .

# Common tasks
storyline-cli check-health
storyline-cli queue-preview
storyline-cli list-categories
storyline-cli update-category-mix

# Testing
pytest                          # All tests
pytest tests/src/services/      # Service tests only
pytest -m unit                  # Unit tests only
pytest --cov=src                # With coverage
```

## Feature Flags

```bash
ENABLE_INSTAGRAM_API=false  # Phase 1: Telegram-only (default)
ENABLE_INSTAGRAM_API=true   # Phase 2: Hybrid mode
```

When enabled, Instagram API is tried first. On failure or rate-limit, falls back to Telegram automatically. Posts are never lost.

## Pre-Commit & CI Requirements

**Run before every commit:**
```bash
source venv/bin/activate && ruff check src/ tests/ && ruff format --check src/ tests/ && pytest
```

**ALWAYS update CHANGELOG.md** when creating PRs — CI will fail without it. Use [Keep a Changelog](https://keepachangelog.com/) format, entries under `## [Unreleased]`.

## Documentation

- **Full docs**: `documentation/README.md`
- **All new docs** go in `documentation/` subdirectories (planning/, guides/, updates/, operations/, api/)
- **Bug fixes/patches**: Use dated filenames in `documentation/updates/` (e.g., `2026-01-04-bugfixes.md`)
- **Never** create markdown files scattered in source directories
