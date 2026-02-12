# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## CRITICAL SAFETY RULES

**THIS SYSTEM POSTS TO INSTAGRAM. DO NOT TRIGGER POSTING WITHOUT EXPLICIT USER APPROVAL.**

### NEVER run these commands:
```bash
# DANGEROUS - Actually posts to Instagram/Telegram
storyline-cli process-queue
storyline-cli process-queue --force
python -m src.main

# DANGEROUS - Modifies production schedule
storyline-cli create-schedule
storyline-cli reset-queue

# DANGEROUS - Modifies authentication
storyline-cli instagram-auth
```

### SAFE commands you CAN run:
```bash
# Reading/inspection only - always safe
storyline-cli list-queue
storyline-cli list-media
storyline-cli list-categories
storyline-cli list-users
storyline-cli check-health
storyline-cli instagram-status
storyline-cli validate-image <path>
storyline-cli category-mix-history
storyline-cli sync-media
storyline-cli sync-status

# Tests - always safe
pytest
```

### Before ANY posting-related action:
1. **STOP** and ask the user for explicit confirmation
2. Explain exactly what will happen (e.g., "This will post to Instagram immediately")
3. Wait for user to type "yes" or approve

### Telegram Web (web.telegram.org) Rules:
- **NEVER type or click** in Telegram Web - view/screenshot only
- Use Telegram Web purely for visual verification of message formatting
- All bot interactions must go through the database or user's phone

---

## Remote Development (Raspberry Pi)

The production system runs on a Raspberry Pi. SSH access is configured via alias (see `~/.ssh/config`).

### Connecting to the Pi
```bash
# SSH using configured alias (IP/hostname in ~/.ssh/config, not in repo)
ssh crogberrypi

# Database access via SSH tunnel
ssh -L 5433:localhost:5432 crogberrypi

# Then connect locally through the tunnel:
psql -h localhost -p 5433 -U storyline_user -d storyline_ai

# Or run psql directly on the Pi:
ssh crogberrypi "psql -U storyline_user -d storyline_ai -c 'SELECT 1;'"
```

> **Note for contributors**: Set up your own SSH alias `crogberrypi` pointing to the Pi's IP.

### Safe Database Queries
```sql
-- Check queue status
SELECT * FROM posting_queue WHERE status = 'pending' ORDER BY scheduled_for;

-- View recent posts
SELECT * FROM posting_history ORDER BY posted_at DESC LIMIT 20;

-- Check media items
SELECT id, file_name, category, times_posted, last_posted_at
FROM media_items WHERE is_active = true LIMIT 50;

-- Service run history
SELECT * FROM service_runs ORDER BY started_at DESC LIMIT 20;
```

### NEVER run on production Pi:
- `storyline-cli process-queue` (posts to Instagram)
- `python -m src.main` (starts the posting scheduler)
- Any INSERT/UPDATE/DELETE on `posting_history` without explicit approval

---

## Project Overview

**Storyline AI** is a self-hosted Instagram Story scheduling and automation system with Telegram-based team collaboration.

**Core Philosophy**: Phased deployment - Start with 100% manual posting (Phase 1), optionally enable Instagram API automation (Phase 2), then add web UI (Phase 3).

**Tech Stack**:
- **Backend**: Python 3.10+, FastAPI (for API layer)
- **Database**: PostgreSQL (with migration path from Raspberry Pi → Neon)
- **Primary UI**: Telegram Bot (team workflow)
- **Future UI**: Next.js web frontend
- **Deployment**: Raspberry Pi (local) → Railway/Render (cloud)

## Architecture at a Glance

### Three-Layer Architecture

```
┌─────────────────────────────────────────┐
│  Interface Layer (Multiple UIs)          │
│  • cli/       - Command-line interface  │
│  • Telegram   - Bot workflow (Phase 1)  │
│  • ui/        - Next.js frontend (Future)│
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│  API Layer (Phase 2.5)                  │
│  • src/api/   - FastAPI REST endpoints  │
│  • Exposes all services via HTTP        │
│  • JWT authentication                   │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│  Service Layer (Business Logic)         │
│  • src/services/core/       - Phase 1   │
│  • src/services/integrations/ - Phase 2+│
│  • src/services/domain/     - Future    │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│  Data Layer                             │
│  • src/repositories/ - Database access  │
│  • src/models/      - SQLAlchemy models │
│  • PostgreSQL       - Single source of truth│
└─────────────────────────────────────────┘
```

### Key Design Principle: STRICT SEPARATION OF CONCERNS

**CRITICAL**: Each layer is strictly isolated:
- **CLI** → calls Services (never touches Repositories or Models directly)
- **API** → calls Services (never touches Repositories or Models directly)
- **UI** → calls API (never calls Services directly)
- **Services** → orchestrate business logic, call Repositories
- **Repositories** → CRUD operations, return Models
- **Models** → database schema definitions only (no business logic)

**NEVER violate layer boundaries**. If you find yourself importing across layers incorrectly, refactor.

## Essential Commands

### Development Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install CLI tool (editable mode)
pip install -e .

# Set up database
psql -U postgres -c "CREATE DATABASE storyline_ai;"
psql -U storyline_ai -d storyline_ai -f scripts/setup_database.sql

# Configure environment
cp .env.example .env
# Edit .env with your credentials
```

### Common Development Tasks

```bash
# Index media files
storyline-cli index-media /path/to/media/stories

# Create posting schedule
storyline-cli create-schedule --days 7 --posts-per-day 3

# Process queue (manual trigger)
storyline-cli process-queue

# Check system health
storyline-cli check-health

# Manage users
storyline-cli list-users
storyline-cli promote-user <telegram_user_id> --role admin

# Category management
storyline-cli list-categories
storyline-cli update-category-mix
storyline-cli category-mix-history --limit 10

# Instagram API (Phase 2)
storyline-cli instagram-auth         # Authenticate with Instagram
storyline-cli instagram-status       # Check token status

# Multi-Account Management
storyline-cli add-instagram-account  # Register new Instagram account
storyline-cli list-instagram-accounts # Show all registered accounts
storyline-cli deactivate-instagram-account <id>  # Soft-delete an account
storyline-cli reactivate-instagram-account <id>  # Restore a deactivated account

# Run main application (scheduler + Telegram bot)
python -m src.main

# Run tests
pytest                          # All tests
pytest tests/src/services/      # Service tests only
pytest -m unit                  # Unit tests only
pytest -m integration           # Integration tests only
pytest --cov=src --cov-report=html  # With coverage

# Queue operations
storyline-cli reset-queue        # Reset queue (clear all pending posts)
```

## Core Services Reference

### Phase 1 Services (Always Available)

| Service | Responsibility | Key Methods |
|---------|---------------|-------------|
| **MediaIngestionService** | Scan filesystem, index media | `scan_directory()`, `index_file()`, `detect_duplicates()` |
| **SchedulerService** | Create posting schedule | `create_schedule()`, `select_media()`, `add_to_queue()` |
| **PostingService** | Orchestrate posting workflow | `process_pending_posts()`, `post_automated()`, `post_via_telegram()` |
| **TelegramService** | Telegram bot coordination | `send_notification()`, `initialize()`, `start_polling()` |
| **TelegramCommandHandlers** | `/command` handlers | `handle_status()`, `handle_queue()`, `handle_next()` |
| **TelegramCallbackHandlers** | Button callback handlers | `handle_posted()`, `handle_skipped()`, `handle_rejected()` |
| **TelegramAutopostHandler** | Auto-posting via API | `handle_autopost()` |
| **TelegramSettingsHandlers** | Settings UI | `handle_settings()`, `handle_settings_toggle()` |
| **TelegramAccountHandlers** | Account selection | `handle_account_selection_menu()`, `handle_account_switch()` |
| **MediaLockService** | TTL lock management | `create_lock()`, `is_locked()`, `cleanup_expired_locks()` |
| **HealthCheckService** | System health monitoring | `check_all()`, `check_database()`, `check_instagram_api()` |
| **SettingsService** | Per-chat runtime configuration | `get_settings()`, `toggle_setting()`, `update_schedule_settings()` |
| **InstagramAccountService** | Multi-account management | `add_account()`, `switch_account()`, `get_active_account()` |
| **InteractionService** | Bot interaction tracking | `log_command()`, `log_callback()`, `log_bot_response()` |

> **Note**: `InteractionService` intentionally does NOT extend `BaseService` to avoid recursive tracking.
> The Telegram handler modules (commands, callbacks, etc.) use a composition pattern — they receive
> a reference to the parent `TelegramService` and are NOT standalone services.

### Phase 2 Services (When ENABLE_INSTAGRAM_API=true)

| Service | Responsibility | Key Methods |
|---------|---------------|-------------|
| **CloudStorageService** | Upload to Cloudinary | `upload_media()`, `delete_media()`, `cleanup_expired()` |
| **InstagramAPIService** | Post to Instagram Graph API | `post_story()`, `get_rate_limit_remaining()`, `validate_media_url()` |
| **TokenRefreshService** | Manage OAuth token lifecycle | `get_token()`, `refresh_instagram_token()`, `check_token_health()` |

**Token Flow**: Initial token from `.env` → bootstrapped to DB → auto-refreshed before expiry (60 days).

**Rate Limiting**: Derived from `posting_history` (count API posts in trailing 60 min). Default: 25 posts/hour.

### Future Services (Phase 3+)

| Service | Responsibility |
|---------|---------------|
| **ShopifyService** | Sync products from Shopify |
| **ProductLinkService** | Link media to products |
| **InstagramMetricsService** | Fetch performance data |
| **AnalyticsService** | Generate insights |

## Database Architecture

### Key Tables

**Core Tables** (Phase 1):
- `media_items` - All indexed media (source of truth, includes `category` column)
- `posting_queue` - Active work items (ephemeral)
- `posting_history` - Permanent audit log (never deleted)
- `media_posting_locks` - TTL-based repost prevention
- `users` - Auto-populated from Telegram interactions
- `service_runs` - Service execution tracking (observability)
- `category_post_case_mix` - Type 2 SCD for posting ratio configuration
- `user_interactions` - Bot interaction tracking for analytics

**Settings & Account Tables** (Phase 2):
- `chat_settings` - Per-chat runtime configuration (DB-backed, `.env` fallback)
- `instagram_accounts` - Multi-Instagram account identity management

**Integration Tables** (Phase 2+):
- `api_tokens` - Encrypted OAuth tokens (linked to `instagram_accounts` via FK)
- `shopify_products` - Type 2 SCD for product history (Future)
- `media_product_links` - Many-to-many media ↔ products (Future)
- `instagram_post_metrics` - Performance data from Meta API (Future)

**Phase 2 Columns Added**:
- `media_items`: `cloud_url`, `cloud_public_id`, `cloud_uploaded_at`, `cloud_expires_at`
- `posting_history`: `instagram_story_id`, `posting_method` ('instagram_api' | 'telegram_manual')

### Settings Architecture (Database + .env Hybrid)

Settings are stored in the `chat_settings` table with `.env` as fallback:
- **First access**: `SettingsService.get_settings()` bootstraps from `.env` values into the database
- **Runtime changes**: Made via Telegram `/settings` command, persisted to DB
- **Survives restarts**: All settings (pause state, dry-run, Instagram API toggle) persist
- **Per-chat**: Each Telegram chat can have independent settings
- **Configurable via Telegram**: `dry_run_mode`, `enable_instagram_api`, `is_paused`, `posts_per_day`, `posting_hours_start/end`, `show_verbose_notifications`, `active_instagram_account_id`

### Multi-Account Instagram Architecture

Three tables work together for multi-account support:
- `instagram_accounts` = **Identity** (what accounts exist? display name, Instagram ID, username)
- `api_tokens` = **Credentials** (OAuth tokens per account, encrypted via Fernet)
- `chat_settings.active_instagram_account_id` = **Selection** (which account is active per chat)

### Critical Design Patterns

1. **Queue vs History Pattern**:
   - Queue is ephemeral (work to do)
   - History is permanent (audit log)
   - Enables reposting same media multiple times

2. **TTL Locks** (`media_posting_locks`):
   - Prevents premature reposts
   - Automatic expiration (no manual cleanup)
   - Lock types: `recent_post`, `manual_hold`, `seasonal`, `permanent_reject`
   - Permanent locks: `locked_until = NULL` (infinite TTL)

3. **User Auto-Discovery**:
   - Users created automatically from Telegram interactions
   - No separate registration system
   - Telegram is single source of truth

4. **Type 2 SCD for Shopify Products**:
   - Tracks historical changes (price, title, description)
   - Enables queries like "What was the price when we posted this story?"
   - Critical for accurate performance analysis

5. **Type 2 SCD for Category Ratios** (`category_post_case_mix`):
   - Tracks posting ratio changes per category
   - Enables auditing: "Who changed the ratios and when?"
   - All active ratios must sum to 1.0 (100%)

## Scheduler Algorithm

**Selection Logic** (in order of priority):

1. Filter eligible media:
   ```sql
   WHERE is_active = TRUE
     AND NOT locked (no active locks in media_posting_locks)
     AND NOT queued (not already in posting_queue)
     AND category = target_category (if category ratios configured)
   ```

2. Sort by:
   - **Primary**: `last_posted_at ASC NULLS FIRST` (never-posted first)
   - **Secondary**: `times_posted ASC` (least-posted preferred)
   - **Tertiary**: `RANDOM()` (tie-breaker for variety)

3. Time slot allocation:
   ```python
   # Evenly distributed slots within posting window
   interval_hours = (POSTING_HOURS_END - POSTING_HOURS_START) / POSTS_PER_DAY

   # Add ±30min jitter for unpredictability
   scheduled_time = base_time + random_jitter(-30min, +30min)
   ```

4. Category-based slot allocation (if ratios configured):
   ```python
   # Allocate slots proportionally to category ratios
   # Example: 70% memes, 30% merch with 21 slots → 15 memes, 6 merch
   slot_allocation = allocate_by_ratio(total_slots, category_ratios)
   random.shuffle(slot_allocation)  # Variety in scheduling

   # Fallback: If category exhausted, select from any category
   ```

5. After posting:
   - Create 30-day TTL lock automatically
   - Increment `times_posted` counter
   - Update `last_posted_at` timestamp

## Telegram Bot Commands Reference

| Command | Description | Handler Module |
|---------|-------------|----------------|
| `/start` | Initialize bot, show welcome | `telegram_commands.py` |
| `/status` | System health and queue status | `telegram_commands.py` |
| `/help` | Show available commands | `telegram_commands.py` |
| `/queue` | View pending scheduled posts | `telegram_commands.py` |
| `/next` | Force-send next scheduled post | `telegram_commands.py` |
| `/pause` | Pause automatic posting | `telegram_commands.py` |
| `/resume` | Resume posting | `telegram_commands.py` |
| `/schedule N` | Create N days of posting schedule | `telegram_commands.py` |
| `/stats` | Media library statistics | `telegram_commands.py` |
| `/history N` | Recent post history | `telegram_commands.py` |
| `/locks` | View permanently rejected items | `telegram_commands.py` |
| `/reset` | Reset posting queue | `telegram_commands.py` |
| `/cleanup` | Delete recent bot messages | `telegram_commands.py` |
| `/settings` | Configure bot settings | `telegram_settings.py` |
| `/dryrun` | Toggle dry-run mode | `telegram_commands.py` |

### Telegram Callback Actions

| Action | Description | Handler Module |
|--------|-------------|----------------|
| `posted:{queue_id}` | Mark as posted to Instagram | `telegram_callbacks.py` |
| `skip:{queue_id}` | Skip for later | `telegram_callbacks.py` |
| `reject:{queue_id}` | Initiate permanent rejection | `telegram_callbacks.py` |
| `confirm_reject:{queue_id}` | Confirm rejection | `telegram_callbacks.py` |
| `autopost:{queue_id}` | Auto-post via Instagram API | `telegram_autopost.py` |
| `settings_toggle:{setting}` | Toggle a boolean setting | `telegram_settings.py` |
| `sa:{queue_id}` | Open account selector | `telegram_accounts.py` |
| `sap:{queue_id}:{account_id}` | Switch account for post | `telegram_accounts.py` |

## Feature Flags

### Phase Control

```bash
# Phase 1: Telegram-only (default)
ENABLE_INSTAGRAM_API=false

# Phase 2: Hybrid mode (auto + manual)
ENABLE_INSTAGRAM_API=true
```

### Routing Logic

```
If ENABLE_INSTAGRAM_API = false:
  → ALL posts go to Telegram (manual)

If ENABLE_INSTAGRAM_API = true:
  If media.requires_interaction = true:
    → Telegram (manual)
  If rate_limit_remaining = 0:
    → Telegram (fallback, with warning log)
  Try Instagram API:
    If success → Done
    If error (RateLimitError, TokenExpiredError, InstagramAPIError):
      → Telegram (fallback)
```

**Fallback Behavior**: The system gracefully falls back to Telegram when Instagram API is unavailable, rate-limited, or erroring. This ensures posts are never lost.

## Image Processing Requirements

Instagram Story specifications:
- **Aspect Ratio**: 9:16 (ideal), 1.91:1 to 9:16 (acceptable)
- **Resolution**: 1080x1920 (ideal), min 720x1280
- **File Size**: Max 100MB (images)
- **Formats**: JPG, PNG, GIF

**Validation**: `ImageProcessor.validate_image()` checks all requirements
**Optimization**: `ImageProcessor.optimize_for_instagram()` resizes/converts automatically

## Testing Guidelines

### CRITICAL: Write Tests for ALL New Functionality

Every new feature must include:

1. **Unit Tests** (`tests/src/`)
   - Test each service method in isolation
   - Mock all dependencies (repositories, external APIs)
   - Focus on business logic correctness
   - Fast execution (< 1 second per test)

2. **Integration Tests** (`tests/integration/`)
   - Test service interactions
   - Use real database (test environment)
   - Test end-to-end workflows
   - Acceptable to be slower

3. **Test Structure** (mirrors `src/`):
   ```
   tests/
   ├── src/
   │   ├── services/
   │   │   ├── test_media_ingestion.py
   │   │   ├── test_scheduler.py
   │   │   ├── test_posting.py
   │   │   └── test_telegram_service.py
   │   ├── repositories/
   │   │   ├── test_media_repository.py
   │   │   └── test_queue_repository.py
   │   └── utils/
   │       ├── test_file_hash.py
   │       └── test_image_processing.py
   └── integration/
       ├── test_end_to_end.py
       └── test_telegram_workflow.py
   ```

### Test Template

```python
# tests/src/services/test_example_service.py
import pytest
from unittest.mock import Mock, patch
from src.services.core.example_service import ExampleService

@pytest.fixture
def example_service():
    """Fixture for ExampleService with mocked dependencies."""
    service = ExampleService()
    service.repo = Mock()  # Mock repository
    return service

class TestExampleService:
    """Test suite for ExampleService."""

    def test_method_name_success_case(self, example_service):
        """Test description of what this test validates."""
        # Arrange
        example_service.repo.get_by_id.return_value = Mock(id=1, name="test")

        # Act
        result = example_service.some_method(1)

        # Assert
        assert result.name == "test"
        example_service.repo.get_by_id.assert_called_once_with(1)

    def test_method_name_error_case(self, example_service):
        """Test error handling when repository raises exception."""
        # Arrange
        example_service.repo.get_by_id.side_effect = ValueError("Not found")

        # Act & Assert
        with pytest.raises(ValueError, match="Not found"):
            example_service.some_method(1)
```

### Test Markers

```python
@pytest.mark.unit  # Fast, isolated
@pytest.mark.integration  # Slower, multiple components
@pytest.mark.slow  # Very slow tests (skip in CI with -m "not slow")
```

### Running Tests

```bash
# All tests with coverage
pytest --cov=src --cov-report=term-missing

# Only fast unit tests
pytest -m unit

# Exclude slow tests
pytest -m "not slow"

# Specific test file
pytest tests/src/services/test_scheduler.py

# Specific test method
pytest tests/src/services/test_scheduler.py::TestSchedulerService::test_create_schedule
```

## Development Guidelines

### 1. Separation of Concerns (CRITICAL)

**Service Layer** (`src/services/`):
```python
class MediaIngestionService(BaseService):
    """
    CORRECT: Service orchestrates business logic
    ✅ Calls repositories
    ✅ Contains workflow logic
    ✅ Handles errors and retries
    ❌ Does NOT contain SQL queries
    ❌ Does NOT import models directly (except for type hints)
    """

    def __init__(self):
        super().__init__()
        self.media_repo = MediaRepository()  # ✅ Dependency injection

    def scan_directory(self, path: str):
        """Business logic for scanning media."""
        for file_path in Path(path).glob("**/*.jpg"):
            # ✅ Use repository for database operations
            existing = self.media_repo.get_by_path(str(file_path))

            if not existing:
                # ✅ Business logic here
                file_hash = calculate_file_hash(file_path)
                self.media_repo.create(
                    file_path=str(file_path),
                    file_hash=file_hash
                )
```

**Repository Layer** (`src/repositories/`):
```python
class MediaRepository:
    """
    CORRECT: Repository handles database access only
    ✅ CRUD operations
    ✅ Query builders
    ❌ Does NOT contain business logic
    ❌ Does NOT make external API calls
    """

    def get_by_path(self, file_path: str) -> Optional[MediaItem]:
        """Simple database query."""
        return self.db.query(MediaItem).filter(
            MediaItem.file_path == file_path
        ).first()

    def create(self, **kwargs) -> MediaItem:
        """Create database record."""
        item = MediaItem(**kwargs)
        self.db.add(item)
        self.db.commit()
        return item
```

### 2. Error Handling Pattern

```python
# ✅ CORRECT: Let BaseService handle logging, just raise exceptions
class ExampleService(BaseService):
    def process_item(self, item_id: str):
        with self.track_execution("process_item", input_params={"item_id": item_id}):
            item = self.repo.get_by_id(item_id)

            if not item:
                raise ValueError(f"Item {item_id} not found")

            # Process...
            result = self._do_work(item)

            # Set result summary for observability
            self.set_result_summary(run_id, {"processed": 1, "status": "success"})

            return result
```

### 3. Configuration Validation

**Always validate config on startup**:
```python
# src/main.py
def main():
    # ✅ Validate before doing anything else
    is_valid, errors = ConfigValidator.validate_all()

    if not is_valid:
        for error in errors:
            logger.error(f"Config error: {error}")
        sys.exit(1)

    # Continue with application...
```

### 4. Database Migrations

When changing schema:

```bash
# Create migration file in scripts/migrations/
scripts/migrations/002_add_column.sql

# Apply migration
psql -U storyline_user -d storyline_ai -f scripts/migrations/002_add_column.sql

# Update schema_version table
INSERT INTO schema_version (version, description)
VALUES (2, 'Add new column to media_items');
```

**Current migration history** (as of 2026-02-09):

| Version | File | Description |
|---------|------|-------------|
| - | `setup_database.sql` | Initial schema (all Phase 1 tables) |
| 001 | `001_add_category_column.sql` | Category column on media_items |
| 002 | `002_add_category_post_case_mix.sql` | Category ratio configuration (Type 2 SCD) |
| 003 | `003_add_user_interactions.sql` | Bot interaction tracking |
| 004 | `004_instagram_api_phase2.sql` | Instagram API columns on media/history |
| 005 | `005_bot_response_logging.sql` | Bot response logging columns |
| 006 | `006_chat_settings.sql` | Per-chat runtime settings |
| 007 | `007_instagram_accounts.sql` | Multi-account identity table |
| 008 | `008_api_tokens_account_fk.sql` | Token-account linking |
| 009 | `009_chat_settings_active_account.sql` | Per-chat account selection |
| 010 | `010_add_verbose_notifications.sql` | Verbose notifications toggle |

### 5. Pre-Commit Checklist (CRITICAL)

**ALWAYS complete these steps before committing or creating PRs:**

```bash
# 1. Run ruff linting on changed files
source venv/bin/activate
ruff check src/ tests/

# 2. Run ruff formatting on changed files
ruff format src/ tests/

# 3. Run tests to ensure nothing is broken
pytest

# 4. Update CHANGELOG.md (see section 6 below)
```

**Quick single-command check:**
```bash
source venv/bin/activate && ruff check src/ tests/ && ruff format --check src/ tests/ && pytest
```

**CI will fail if:**
- Ruff linting errors exist (`ruff check`)
- Ruff formatting is incorrect (`ruff format --check`)
- CHANGELOG.md is not updated for PRs
- Tests fail

### 6. Changelog Maintenance (CRITICAL)

**ALWAYS update CHANGELOG.md when creating PRs.** The changelog is the user-facing record of all changes.

**Format**: This project uses [Keep a Changelog](https://keepachangelog.com/) with [Semantic Versioning](https://semver.org/).

**When to update**:
- **Every PR** must include a CHANGELOG.md entry
- Add entries under `## [Unreleased]` section
- Move entries to a versioned section when releasing

**Version bump rules** (Semantic Versioning):
- **MAJOR** (X.0.0): Breaking changes, incompatible API changes
- **MINOR** (x.Y.0): New features, backward-compatible additions
- **PATCH** (x.y.Z): Bug fixes, minor improvements

**Entry categories** (use as applicable):
- `### Added` - New features or capabilities
- `### Changed` - Changes to existing functionality
- `### Deprecated` - Features that will be removed
- `### Removed` - Features that were removed
- `### Fixed` - Bug fixes
- `### Security` - Security-related changes

**Entry format**:
```markdown
## [Unreleased]

### Added
- **Feature Name** - Brief description of what was added
  - Sub-bullet with implementation detail
  - Another detail if needed

### Fixed
- **Bug Name** - What was broken and how it was fixed
```

**Best practices**:
- Write entries from the user's perspective (what changed for them)
- Include enough detail to understand the change without reading code
- Reference issue/PR numbers when relevant: `(#123)`
- Group related changes under descriptive subheadings
- Include technical details section for significant changes
- List affected files for complex changes

**Example entry**:
```markdown
## [Unreleased]

### Added - Instagram Account Management (Phase 1.5)

#### Multi-Account Support
- **Instagram Accounts Table** - Store multiple Instagram account identities
  - Display name, Instagram ID, username per account
  - Active/inactive status for soft deletion
  - Created via CLI: `storyline-cli add-instagram-account`

- **Account Switching** - Switch between accounts via Telegram /settings
  - Per-chat active account selection
  - Auto-select when only one account exists

#### New CLI Commands
- `add-instagram-account` - Register new Instagram account with token
- `list-instagram-accounts` - Show all registered accounts
- `deactivate-instagram-account` - Soft-delete an account
- `reactivate-instagram-account` - Restore a deactivated account

### Technical Details

#### Database Migrations
- `007_instagram_accounts.sql` - Creates instagram_accounts table
- `008_api_tokens_account_fk.sql` - Links tokens to accounts
- `009_chat_settings_active_account.sql` - Per-chat account selection

#### Files Changed
- `src/models/instagram_account.py` - New model
- `src/services/core/instagram_account_service.py` - Business logic
- `src/services/core/telegram_service.py` - Account switching UI
```

### 7. Logging Standards

```python
from src.utils.logger import logger

# ✅ Structured logging with context
logger.info(f"Indexing media file: {file_path}")
logger.warning(f"Image {file_path} has validation warnings: {warnings}")
logger.error(f"Failed to upload to Cloudinary: {error}", exc_info=True)

# ✅ Use appropriate levels
# DEBUG: Detailed diagnostic info
# INFO: General informational messages
# WARNING: Something unexpected but handled
# ERROR: Error occurred but app continues
# CRITICAL: Severe error, app might crash
```

### 8. Async/Await Usage

```python
# Telegram and HTTP operations are async
async def send_notification(self, media_item):
    await self.telegram_service.send_photo(
        chat_id=settings.TELEGRAM_CHANNEL_ID,
        photo=open(media_item.file_path, 'rb'),
        caption=self._build_caption(media_item)
    )

# Database operations are synchronous (SQLAlchemy)
def get_media_by_id(self, media_id: str):
    return self.db.query(MediaItem).filter(MediaItem.id == media_id).first()
```

## Common Patterns

### Service Execution Tracking

```python
class MyService(BaseService):
    def my_method(self, param: str):
        # ✅ All service methods should use track_execution
        with self.track_execution(
            method_name="my_method",
            user_id=user_id,  # Optional
            triggered_by="system",  # or "user", "cli", "scheduler"
            input_params={"param": param}
        ) as run_id:

            # Your logic here
            result = self._do_work(param)

            # Record results for observability
            self.set_result_summary(run_id, {
                "items_processed": result.count,
                "success": True
            })

            return result
```

### User Auto-Discovery (Telegram)

```python
def get_or_create_user(telegram_user_data: dict) -> User:
    """Auto-create users from Telegram interactions."""
    user = user_repo.get_by_telegram_id(telegram_user_data['id'])

    if not user:
        user = user_repo.create(
            telegram_user_id=telegram_user_data['id'],
            telegram_username=telegram_user_data.get('username'),
            telegram_first_name=telegram_user_data.get('first_name'),
            role='member'
        )
        logger.info(f"New user discovered: @{telegram_user_data.get('username')}")

    return user
```

## File Organization

### Module Naming Conventions

```
src/
├── services/
│   ├── core/
│   │   ├── telegram_service.py        # Core bot lifecycle + coordination
│   │   ├── telegram_commands.py       # /command handlers (composition)
│   │   ├── telegram_callbacks.py      # Button callback handlers
│   │   ├── telegram_autopost.py       # Auto-posting logic
│   │   ├── telegram_settings.py       # Settings UI handlers
│   │   ├── telegram_accounts.py       # Account selection handlers
│   │   ├── settings_service.py        # Per-chat runtime settings
│   │   ├── instagram_account_service.py  # Multi-account management
│   │   ├── interaction_service.py     # Bot interaction tracking
│   │   └── ...                        # Other core services
│   ├── integrations/
│   │   ├── instagram_api.py           # Class: InstagramAPIService
│   │   ├── cloud_storage.py           # Class: CloudStorageService
│   │   └── token_refresh.py           # Class: TokenRefreshService
│   └── domain/
│       └── (empty - future analytics/AI services)
├── repositories/
│   └── example_repository.py      # Class: ExampleRepository
├── models/
│   └── example_model.py           # Class: ExampleModel (SQLAlchemy)
├── api/
│   └── routes/
│       └── example.py             # router = APIRouter()
└── utils/
    └── example_utility.py         # Stateless utility functions
```

### Import Order

```python
# Standard library
import os
from datetime import datetime
from typing import Optional, List

# Third-party
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends
import httpx

# Local application
from src.config.settings import settings
from src.models.media_item import MediaItem
from src.repositories.media_repository import MediaRepository
from src.utils.logger import logger
```

### Documentation Organization

**IMPORTANT**: All helpful markdown documentation should be placed in the `documentation/` directory.

```
documentation/
├── README.md                           # Index of all documentation
├── planning/                           # Planning and design docs
│   ├── instagram_automation_plan.md   # Master implementation plan
│   ├── IMPLEMENTATION_COMPLETE.md     # Phase completion status
│   ├── TEST_COVERAGE.md               # Test coverage report
│   └── architecture_decisions.md      # ADRs (Architecture Decision Records)
├── guides/                             # How-to guides and tutorials
│   ├── quickstart.md                  # 10-minute setup guide
│   ├── deployment.md                  # Production deployment
│   ├── testing-guide.md               # How to run and write tests
│   └── contributing.md
├── updates/                            # Project updates, patches, bugfixes
│   ├── YYYY-MM-DD-bugfixes.md         # Dated bug fix reports
│   ├── YYYY-MM-DD-patch.md            # Dated patch notes
│   └── YYYY-MM-DD-hotfix.md           # Dated hotfix documentation
├── operations/                         # Operational runbooks
│   ├── monitoring.md
│   ├── backups.md
│   └── troubleshooting.md
└── api/                                # API documentation (Phase 5)
    ├── endpoints.md
    └── authentication.md
```

**Rules**:
- ✅ **DO** create subdirectories in `documentation/` based on document purpose
- ✅ **DO** keep root-level docs for critical project info only (README.md, CHANGELOG.md, etc.)
- ✅ **DO** update `documentation/README.md` when adding new docs
- ✅ **DO** use dated filenames for updates: `YYYY-MM-DD-description.md`
- ✅ **DO** place bug fix reports, patches, and hotfixes in `documentation/updates/`
- ❌ **DON'T** create markdown files scattered throughout the codebase
- ❌ **DON'T** put documentation in source directories (`src/`, `cli/`, etc.)
- ❌ **DON'T** create temporary documentation files in the project root

**Root-level documentation exceptions** (only these should be in project root):
- `README.md` - Project overview and quick start
- `CHANGELOG.md` - Version history
- `CLAUDE.md` - This file (developer guide for AI assistants)
- `LICENSE` - Project license
- `CONTRIBUTING.md` - Contribution guidelines (if public)

**Subdirectory Purpose Guide**:

| Folder | Purpose | Examples |
|--------|---------|----------|
| `planning/` | Design docs, specs, completion reports | `instagram_automation_plan.md`, `TEST_COVERAGE.md` |
| `guides/` | How-to guides, tutorials | `quickstart.md`, `deployment.md`, `testing-guide.md` |
| `updates/` | **Dated bug fixes, patches, hotfixes** | `2026-01-04-bugfixes.md`, `2026-02-15-security-patch.md` |
| `operations/` | Production runbooks, procedures | `monitoring.md`, `incident-response.md` |
| `api/` | API reference documentation | `endpoints.md`, `authentication.md` |

**Examples**:
```bash
# ✅ CORRECT
documentation/guides/telegram_setup.md
documentation/operations/backup_restore.md
documentation/updates/2026-01-04-bugfixes.md        # Dated bugfix report
documentation/updates/2026-01-15-hotfix-locks.md    # Dated hotfix
documentation/api/rate_limiting.md

# ❌ INCORRECT
src/services/README.md                              # Don't put docs in src/
cli/commands/GUIDE.md                               # Don't put docs in cli/
TelegramSetup.md                                    # Don't put guides in root
BUGFIXES.md                                         # Don't put updates in root (use dated file in updates/)
HotfixDec2025.md                                    # Use ISO date format: YYYY-MM-DD
```

## Troubleshooting Guide

### Common Issues

**Import errors**:
- Ensure virtual environment is activated
- Run `pip install -e .` to install CLI in editable mode

**Database connection errors**:
- Check PostgreSQL is running: `sudo systemctl status postgresql`
- Verify credentials in `.env`
- Test connection: `psql -U storyline_user -d storyline_ai -c "SELECT 1;"`

**Telegram bot not responding**:
- Check bot token is valid: `curl https://api.telegram.org/bot<TOKEN>/getMe`
- Verify channel ID is correct (negative for channels)
- Check bot has admin permissions in channel

**Image validation failing**:
- Check image meets Instagram specs (9:16 aspect ratio, max 100MB)
- Try `storyline-cli validate-image /path/to/image.jpg`

**Tests failing**:
- Ensure test database exists: `createdb storyline_ai_test`
- Check `.env.test` has correct test database credentials
- Run `pytest -v` for verbose output

## Summary

**Key Principles**:
1. ✅ Strict separation of concerns (CLI → API → Services → Repositories → Models)
2. ✅ Write tests for ALL new functionality
3. ✅ Use BaseService for automatic logging and error tracking
4. ✅ Validate configuration on startup
5. ✅ Keep services focused (single responsibility)
6. ✅ Use repositories for all database access (no raw SQL in services)
7. ✅ Handle errors gracefully with informative messages
8. ✅ Log important events with appropriate severity levels

**Quick Reference**:
- Main application: `python -m src.main`
- API server: `uvicorn src.api.app:app --reload`
- Run tests: `pytest --cov=src`
- Check health: `storyline-cli check-health`
- **All documentation**: See `documentation/README.md` for complete index
- Full technical spec: `documentation/planning/instagram_automation_plan.md`
- Instagram API setup: `documentation/guides/instagram-api-setup.md`
- Deployment guide: `documentation/guides/deployment.md`
- Testing guide: `documentation/guides/testing-guide.md`
