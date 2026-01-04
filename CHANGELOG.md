# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.1] - 2026-01-04

### Added
- Comprehensive test suite with 147 tests covering all Phase 1 functionality
- Automatic test database creation and cleanup (pytest fixtures)
- Repository layer tests (6 test files, 49 tests)
- Service layer tests (7 test files, 56 tests)
- Utility layer tests (4 test files, 33 tests)
- CLI command tests (4 test files, 18 tests)
- Test fixtures for database sessions with automatic rollback
- Test documentation (tests/README.md, TESTING_SETUP.md)
- Makefile targets for test execution (test, test-unit, test-quick, test-failed)
- Enhanced logger utility with setup_logger() and get_logger() functions for testability
- Development command: `storyline-cli process-queue --force` for immediate testing
- Lock creation verification in telegram service tests

### Fixed (Code Review - 2026-01-04)
- **Critical**: Service run metadata silently discarded (wrong column name in repository)
- **Critical**: Scheduler date mutation bug causing incorrect scheduling for midnight-crossing windows

### Fixed (Deployment - 2026-01-04)
- **Critical**: 30-day lock creation missing in TelegramService button handlers
- **Database**: Made DB_PASSWORD optional for local PostgreSQL development
- **Database**: Database URL now handles empty password correctly
- **Telegram**: Auto-initialization of bot for CLI commands (one-time use)
- **Validation**: Removed DB_PASSWORD requirement from config validator
- **SQLAlchemy**: Added text() wrapper for raw SQL in health check (SQLAlchemy 2.0+ compatibility)

### Fixed (Testing)
- SQLAlchemy reserved keyword issue (renamed ServiceRun.metadata to context_metadata)
- Test environment configuration loading in conftest.py
- CLI command function names in test imports

### Technical Improvements
- Session-scoped database fixture for one-time setup per test run
- Function-scoped test_db fixture with transaction rollback for test isolation
- Zero-manual-setup testing (database auto-created from .env.test)
- CI/CD ready test infrastructure
- TelegramService now creates locks when "Posted" button is clicked
- PostingService.process_next_immediate() method for development testing

### Next Steps
- **Phase 2 (Optional)**: Instagram API automation integration
  - CloudStorageService (Cloudinary/S3)
  - InstagramAPIService (Graph API)
  - Token refresh service
  - Hybrid workflow (automated simple stories, manual interactive stories)
- **Phase 3**: Shopify product integration (schema ready)
- **Phase 4**: Instagram analytics and metrics (schema ready)
- **Phase 5**: REST API and web frontend

## [1.0.0] - 2026-01-03

### Added

#### Core Infrastructure
- Complete PostgreSQL database schema with 6 core tables
- SQLAlchemy ORM models for all entities
- Pydantic-based configuration management with environment variables
- Comprehensive logging system with file and console outputs
- Service execution tracking for observability and debugging

#### Data Models
- `User` model with auto-discovery from Telegram interactions
- `MediaItem` model as source of truth for media files
- `PostingQueue` model for active work items (ephemeral)
- `PostingHistory` model for permanent audit trail
- `MediaPostingLock` model for TTL-based repost prevention
- `ServiceRun` model for service execution tracking

#### Repository Layer (CRUD Operations)
- `UserRepository` with user management and stats tracking
- `MediaRepository` with duplicate detection and filtering
- `QueueRepository` with retry logic and status management
- `HistoryRepository` with statistics and filtering
- `LockRepository` with TTL lock management
- `ServiceRunRepository` with execution tracking

#### Services Layer
- `BaseService` class with automatic execution tracking and error handling
- `MediaIngestionService` for filesystem scanning and media indexing
- `SchedulerService` with intelligent media selection algorithm
- `MediaLockService` for TTL lock management (30-day default)
- `PostingService` for workflow orchestration
- `TelegramService` with bot polling and callback handlers
- `HealthCheckService` with 4 health checks (database, telegram, queue, recent posts)

#### Utilities
- SHA256 file content hashing (filename-agnostic)
- Image validation against Instagram Story requirements (aspect ratio, resolution, file size)
- Image optimization for Instagram (resize, crop, convert)
- Configuration validation with startup checks
- Structured logging with configurable log levels

#### CLI Commands
- `index-media` - Index media files from directory
- `list-media` - List all indexed media items with filters
- `validate-image` - Validate image against Instagram requirements
- `create-schedule` - Generate intelligent posting schedule
- `process-queue` - Process pending queue items
- `list-queue` - View pending queue items
- `list-users` - List all users with stats
- `promote-user` - Change user role (admin/member)
- `check-health` - System health check with component status

#### Features
- **Smart Scheduling Algorithm**
  - Prioritizes never-posted media items
  - Prefers least-posted items
  - Random selection for variety
  - Excludes locked and queued media
  - Evenly distributed time slots with ±30min jitter
- **Telegram Bot Integration**
  - Inline keyboard buttons (Posted/Skip)
  - Auto-discovery of users from interactions
  - User attribution for all actions
  - /start and /status commands
  - Callback handling for workflow tracking
- **TTL Lock System**
  - Automatic 30-day repost prevention
  - Self-expiring locks (no manual cleanup)
  - Configurable lock duration
  - Multiple lock reasons (recent_post, manual_hold, seasonal)
- **User Management**
  - Auto-creation from Telegram interactions
  - Role-based access (admin/member)
  - Statistics tracking (total posts, last seen)
  - Team name support
- **Complete Audit Trail**
  - Permanent posting history (never deleted)
  - Media metadata snapshots
  - User attribution for all posts
  - Error tracking with retry counts
  - Queue lifecycle timestamps preserved
- **Service Execution Tracking**
  - Automatic logging of all service calls
  - Performance metrics (execution time)
  - Error tracking with stack traces
  - Input parameters and result summaries
  - User attribution for manual triggers
- **Image Processing**
  - Validation against Instagram Story specs (9:16 aspect ratio, 1080x1920 resolution)
  - Automatic optimization (resize, crop, format conversion)
  - HEIC to JPG conversion support
  - PNG transparency handling (RGBA to RGB)
- **Health Monitoring**
  - Database connectivity check
  - Telegram configuration validation
  - Queue backlog detection
  - Recent posts verification
- **Development Features**
  - Dry-run mode for testing without posting
  - Configuration validation on startup (fail-fast)
  - Comprehensive error messages
  - Rich CLI output with tables and colors

#### Application
- Main application entry point with async event loop
- Scheduler loop (checks every minute for pending posts)
- Cleanup loop (hourly expired lock cleanup)
- Telegram bot polling in same process
- Graceful shutdown handling (SIGTERM/SIGINT)
- Configuration validation before startup

#### Database
- Complete schema with indexes for performance
- Foreign key constraints and cascading deletes
- Check constraints for data integrity
- GIN indexes for array columns (tags)
- Schema version tracking table

#### Documentation
- Comprehensive README with quick start guide
- QUICKSTART.md for 10-minute setup
- CLAUDE.md developer guide for AI assistants
- IMPLEMENTATION_COMPLETE.md with full component list
- Complete implementation plan in documentation/
- Inline code documentation and docstrings

#### Testing
- Pytest configuration with coverage reporting
- Test fixtures for database and sample data
- Unit tests for file hashing
- Unit tests for media ingestion service
- Test structure mirroring src/ directory
- Markers for unit/integration/slow tests

#### DevOps
- SQL schema setup script
- Python database initialization script
- requirements.txt with pinned versions
- setup.py for CLI installation
- .env.example with complete configuration template
- .env.test for test environment
- .gitignore for Python projects

### Technical Details

#### Architecture
- Three-layer architecture: CLI → Services → Repositories → Models
- Strict separation of concerns enforced
- Repository pattern for data access
- Service layer for business logic
- Base service class for cross-cutting concerns

#### Configuration
- Environment-based configuration (12-factor app)
- Pydantic settings with validation
- Support for .env files
- Separate test environment configuration
- Feature flags (ENABLE_INSTAGRAM_API, DRY_RUN_MODE)

#### Database
- PostgreSQL with SQLAlchemy ORM
- UUID primary keys
- Timestamp tracking (created_at, updated_at)
- JSONB columns for flexible metadata
- Array columns for tags

#### Performance
- Database indexes on foreign keys and frequently queried columns
- GIN indexes for array searches
- Connection pooling (5 connections, 10 overflow)
- Chunked file reading for hash calculation
- Pre-ping for connection validation

#### Security
- No sensitive data in code (environment variables only)
- Database password required
- User roles for access control
- Input validation at all layers

### Phase Information
- **Current Phase**: Phase 1 (Telegram-Only Mode)
- **Deployment Target**: Raspberry Pi (16GB RAM)
- **Python Version**: 3.10+
- **Database**: PostgreSQL
- **Posting Mode**: 100% manual via Telegram
- **Instagram API**: Not required for Phase 1

[Unreleased]: https://github.com/yourusername/storyline-ai/compare/v1.0.1...HEAD
[1.0.1]: https://github.com/yourusername/storyline-ai/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/yourusername/storyline-ai/releases/tag/v1.0.0
