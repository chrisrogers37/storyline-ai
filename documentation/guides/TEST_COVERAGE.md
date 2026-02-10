# Test Coverage Report

**Last Updated**: 2026-02-09
**Total Tests**: 494 (351 passing, 143 skipped integration tests)
**Test Files**: 36
**Test Framework**: pytest 7.4.3
**Coverage Target**: Core business logic and critical paths
**Status**: ✅ Current through v1.6.0 + race condition handling

---

## Test Suite Summary

### Coverage by Layer

| Layer | Files | Tests | Coverage Focus |
|-------|-------|-------|----------------|
| **Repositories** | 8 | ~80 | CRUD operations, database interactions |
| **Services** | 17 | ~300 | Business logic, workflow orchestration |
| **Utilities** | 5 | ~50 | File hashing, image processing, validation, encryption |
| **CLI** | 4 | ~45 | Command interface, user interactions |
| **Integration** | 1 | ~13 | End-to-end Instagram posting workflow |
| **TOTAL** | **36** | **494** | **Full Phase 2 + TelegramService refactor + race condition handling** |

### Post-Phase 1.6 Test Additions (~220 new tests)

**Phase 2 - Instagram API (v1.5.0)**:
- **InstagramAPIService** - API posting, rate limiting, error handling
- **CloudStorageService** - Cloudinary upload/delete/cleanup
- **TokenRefreshService** - Token lifecycle, refresh, health checks
- **InstagramAccountService** - Multi-account CRUD, switching, display
- **SettingsService** - Per-chat settings, toggles, validation
- **InteractionService** - Command/callback logging, bot response tracking
- **Integration tests** - End-to-end Instagram posting workflow

**Phase 1.8 - Telegram UX + Refactor**:
- **TelegramCommands** - Extracted command handler tests
- **TelegramCallbacks** - Extracted callback handler tests
- **TelegramSettings** - Settings UI handler tests
- **TelegramAccounts** - Account selection handler tests
- **Encryption utility** - Fernet encryption/decryption tests

### Phase 1.6 Additions (95 new tests, historical)
- **Category Extraction** (7 tests) - Folder structure → category mapping
- **CategoryMixRepository** (18 tests) - Type 2 SCD ratio management
- **Scheduler Category Allocation** (9 tests) - Category-aware slot distribution
- **CLI Category Commands** (27 tests) - list-categories, update-category-mix, category-mix-history
- **Integration Tests** (34 tests) - End-to-end category scheduling

---

## Repository Layer Tests (49 tests)

### UserRepository (9 tests)
- ✅ Create user with Telegram data
- ✅ Get by Telegram ID
- ✅ Get or create (existing/new user)
- ✅ Increment post count
- ✅ Update user role
- ✅ List all users
- ✅ Get by user ID
- ✅ Update last seen timestamp

**File**: `tests/src/repositories/test_user_repository.py`

### MediaRepository (8 tests)
- ✅ Create media item
- ✅ Get by file path
- ✅ Get by file hash (duplicate detection)
- ✅ Get duplicates
- ✅ Increment times posted
- ✅ List with filters (active/inactive)
- ✅ Get never posted items
- ✅ Get least posted items

**File**: `tests/src/repositories/test_media_repository.py`

### QueueRepository (7 tests)
- ✅ Create queue item
- ✅ Get pending items (by scheduled time)
- ✅ Update status
- ✅ Schedule retry with backoff
- ✅ Delete queue item
- ✅ List all queue items
- ✅ Get by media ID

**File**: `tests/src/repositories/test_queue_repository.py`

### HistoryRepository (6 tests)
- ✅ Create history record
- ✅ Get by media ID
- ✅ Get by user ID
- ✅ Get statistics
- ✅ Get recent posts
- ✅ List all with filters

**File**: `tests/src/repositories/test_history_repository.py`

### LockRepository (8 tests)
- ✅ Create lock with TTL
- ✅ Check if locked (active lock)
- ✅ Check if locked (expired lock)
- ✅ Check if locked (no lock)
- ✅ Get active locks
- ✅ Cleanup expired locks
- ✅ Delete specific lock
- ✅ Get locks by media ID

**File**: `tests/src/repositories/test_lock_repository.py`

### ServiceRunRepository (8 tests)
- ✅ Create service run
- ✅ Complete run (success)
- ✅ Complete run (failure)
- ✅ Get recent runs
- ✅ Get failed runs
- ✅ Get runs by service name
- ✅ Get runs by user
- ✅ Execution time calculation

**File**: `tests/src/repositories/test_service_run_repository.py`

---

## Service Layer Tests (56 tests)

### BaseService (8 tests)
- ✅ Service initialization
- ✅ Track execution creates run
- ✅ Track execution records success
- ✅ Track execution records failure
- ✅ Track with input parameters
- ✅ Track with user ID
- ✅ Track with result summary
- ✅ Calculate execution timing

**File**: `tests/src/services/test_base_service.py`

### MediaIngestionService (4 tests)
- ✅ Scan directory validates path
- ✅ Only processes supported formats
- ✅ Index file creates media item
- ✅ Skips duplicate files

**File**: `tests/src/services/test_media_ingestion.py`

### SchedulerService (11 tests)
- ✅ Create schedule for N days
- ✅ Calculate time slots
- ✅ Select never-posted media first
- ✅ Select least-posted media
- ✅ Exclude locked media
- ✅ Exclude already-queued media
- ✅ Handle insufficient media
- ✅ Distribute posts evenly
- ✅ Apply jitter to scheduled times
- ✅ Handle wrap-around posting hours
- ✅ Validate posts per day configuration

**File**: `tests/src/services/test_scheduler.py`

### MediaLockService (3 tests)
- ✅ Create lock with 30-day default
- ✅ Check if media is locked
- ✅ Cleanup expired locks

**File**: `tests/src/services/test_media_lock.py`

### PostingService (9 tests)
- ✅ Process pending posts
- ✅ Process immediate (force mode) - **Added 2026-01-04**
- ✅ Route to Telegram service
- ✅ Handle completion (success)
- ✅ Handle completion (failure)
- ✅ Create history record
- ✅ Increment media counter
- ✅ Create 30-day lock
- ✅ Delete from queue

**File**: `tests/src/services/test_posting.py`

### TelegramService (42 tests)

**Core Tests (11 tests)**:
- ✅ Service initialization
- ✅ Get or create user (new)
- ✅ Get or create user (existing)
- ✅ Format queue notification
- ✅ Send queue notification
- ✅ Create inline keyboard
- ✅ Handle posted callback
- ✅ **Handle posted callback creates lock** - **Updated 2026-01-04**
- ✅ Handle skip callback
- ✅ Update message caption
- ✅ User stats incremented

**Reject Confirmation Tests (5 tests)**:
- ✅ Reject confirmation shows warning
- ✅ Reject confirmation not found
- ✅ Confirm reject creates permanent lock
- ✅ Cancel reject restores buttons
- ✅ Callback routes correctly

**Queue Command Tests (3 tests)** - **Added 2026-01-07**:
- ✅ Queue shows all pending (not just due)
- ✅ Queue empty message
- ✅ Queue limits to 10 items

**Next Command Tests (5 tests)** - **Added 2026-01-07**:
- ✅ Next sends earliest scheduled post
- ✅ Next empty queue
- ✅ Next media not found
- ✅ Next notification failure
- ✅ Next logs interaction

**Pause Command Tests (2 tests)** - **Added 2026-01-08**:
- ✅ Pause when not paused
- ✅ Pause when already paused

**Resume Command Tests (3 tests)** - **Added 2026-01-08**:
- ✅ Resume when not paused
- ✅ Resume with overdue posts (shows options)
- ✅ Resume with no overdue (immediate)

**Schedule Command Tests (2 tests)** - **Added 2026-01-08**:
- ✅ Schedule creates schedule
- ✅ Schedule invalid days

**Stats Command Tests (1 test)** - **Added 2026-01-08**:
- ✅ Stats shows media statistics

**History Command Tests (2 tests)** - **Added 2026-01-08**:
- ✅ History shows recent posts
- ✅ History empty message

**Locks Command Tests (2 tests)** - **Added 2026-01-08**:
- ✅ Locks shows permanent locks
- ✅ Locks empty message

**Reset Command Tests (2 tests)** - **Added 2026-01-08**:
- ✅ Reset shows confirmation
- ✅ Reset empty queue

**Resume Callback Tests (3 tests)** - **Added 2026-01-08**:
- ✅ Resume reschedule
- ✅ Resume clear
- ✅ Resume force

**Clear Callback Tests (2 tests)** - **Added 2026-01-08**:
- ✅ Clear confirm
- ✅ Clear cancel

**Pause Integration Tests (1 test)** - **Added 2026-01-08**:
- ✅ PostingService respects pause state

**File**: `tests/src/services/test_telegram_service.py`

### HealthCheckService (10 tests)
- ✅ Check database connection (healthy)
- ✅ Check database connection (unhealthy)
- ✅ Check Telegram config (valid)
- ✅ Check Telegram config (invalid)
- ✅ Check queue status (healthy)
- ✅ Check queue status (backlog)
- ✅ Check recent posts (healthy)
- ✅ Check recent posts (no activity)
- ✅ Run all checks
- ✅ Get system info

**File**: `tests/src/services/test_health_check.py`

---

## Utility Layer Tests (33 tests)

### FileHash (4 tests)
- ✅ Calculate SHA256 hash
- ✅ Handle missing files
- ✅ Detect file changes
- ✅ Chunked reading for large files

**File**: `tests/src/utils/test_file_hash.py`

### ImageProcessing (17 tests)
- ✅ Validate aspect ratio (9:16)
- ✅ Validate resolution (1080x1920)
- ✅ Validate file size
- ✅ Validate format (JPEG, PNG)
- ✅ Reject invalid aspect ratios
- ✅ Reject low resolution
- ✅ Reject oversized files
- ✅ Resize image to target
- ✅ Crop to 9:16 ratio
- ✅ Convert HEIC to JPEG
- ✅ Convert PNG to JPEG
- ✅ Handle transparency (RGBA)
- ✅ Optimize quality
- ✅ Full validation pipeline
- ✅ Handle corrupt images
- ✅ Handle missing files
- ✅ Preserve EXIF metadata

**File**: `tests/src/utils/test_image_processing.py`

### Logger (8 tests)
- ✅ Setup logger with defaults
- ✅ Configure log level
- ✅ Configure output directory
- ✅ Get logger by name
- ✅ Singleton behavior
- ✅ File output
- ✅ Console output
- ✅ Format configuration

**File**: `tests/src/utils/test_logger.py`

### Validators (4 tests)
- ✅ Validate configuration (all valid)
- ✅ Validate posting schedule
- ✅ Validate Telegram config
- ✅ Validate paths exist

**File**: `tests/src/utils/test_validators.py`

---

## CLI Layer Tests (18 tests)

### MediaCommands (9 tests)
- ✅ index-media command
- ✅ index-media nonexistent directory
- ✅ list-media command
- ✅ list-media with filters
- ✅ validate-image valid
- ✅ validate-image invalid
- ✅ validate-image nonexistent

**File**: `tests/cli/test_media_commands.py`

### QueueCommands (5 tests)
- ✅ create-schedule command
- ✅ create-schedule with no media
- ✅ list-queue command
- ✅ list-queue with status filter
- ✅ process-queue command
- ✅ **process-queue --force** - **Added 2026-01-04**

**File**: `tests/cli/test_queue_commands.py`

### UserCommands (5 tests)
- ✅ list-users command
- ✅ list-users empty database
- ✅ promote-user command
- ✅ promote-user nonexistent
- ✅ promote-user invalid role

**File**: `tests/cli/test_user_commands.py`

### HealthCommands (2 tests)
- ✅ check-health command
- ✅ check-health shows all checks

**File**: `tests/cli/test_health_commands.py`

---

## Test Infrastructure

### Test Database Management
- **Automatic creation**: Test database created from `.env.test`
- **Session-scoped fixture**: One-time setup per test run
- **Function-scoped fixture**: Rollback after each test
- **Zero manual setup**: No SQL scripts to run manually
- **Isolation**: Each test runs in a transaction

### Test Configuration
```ini
# pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
markers =
    unit: Unit tests (no external dependencies)
    integration: Integration tests (database, external services)
    slow: Slow-running tests
asyncio_mode = auto
```

### Coverage Reporting
```bash
# HTML report generated in htmlcov/
make test

# Terminal output with line numbers
pytest --cov=src --cov-report=term-missing

# Specific coverage threshold
pytest --cov=src --cov-fail-under=80
```

### Makefile Targets
```makefile
test          # All tests with coverage
test-unit     # Unit tests only
test-integration  # Integration tests only
test-quick    # Without coverage (faster)
test-failed   # Rerun only failed tests
```

---

## Deployment-Critical Tests (Added 2026-01-04)

### Lock Creation Verification
**Test**: `test_handle_posted_callback` (updated)
**File**: `tests/src/services/test_telegram_service.py:149-203`
**Purpose**: Verify 30-day lock is created when "Posted" button is clicked

```python
# Verify 30-day lock was created
assert lock_repo.is_locked(media.id) is True
```

**Why Critical**: Without this test, the lock creation bug could regress, allowing immediate reposts.

### Force-Process Testing
**Test**: `test_process_next_immediate`
**File**: `tests/src/services/test_posting.py`
**Purpose**: Verify development command processes posts ignoring schedule

**Why Critical**: Essential for development and testing workflows.

---

## Coverage Gaps & Future Work

### Not Currently Tested
1. **Telegram bot polling** - Integration test would require live Telegram API
2. **Main application loop** - Would require long-running test environment
3. **Signal handling** - SIGTERM/SIGINT handling for graceful shutdown
4. **Concurrent access** - Multiple users clicking buttons simultaneously
5. **Network failures** - Telegram API timeout/retry scenarios

### Acceptable Gaps
- ~~Instagram API integration (Phase 2)~~ ✅ Now tested
- ~~Cloudinary integration (Phase 2)~~ ✅ Now tested
- Web frontend (Phase 5+)
- Real-time metrics (Phase 4+)
- Shopify/Printify integration (Phase 3-4)

---

## Test Execution Results

### Latest Run (2026-01-08)
```
Platform: darwin (macOS Intel)
Python: 3.11.12
PostgreSQL: 14.18

Test Summary:
- Total: 173 tests
- Passed: 121
- Skipped: 113 (integration tests requiring live services)
- Failed: 0
- Coverage: 56% overall, 62% (telegram_service)
```

**Note**: Coverage percentage is lower for repositories/services because they include database interaction code paths that are covered by integration tests but not counted by coverage tools in some execution modes. Skipped tests are integration tests that require live Telegram/database connections.

---

## Running Tests

### Quick Start
```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
make test

# Run specific test file
pytest tests/src/services/test_telegram_service.py -v

# Run specific test
pytest tests/src/services/test_telegram_service.py::TestTelegramService::test_handle_posted_callback -v
```

### CI/CD Integration
```bash
# Run in CI environment
pytest --cov=src --cov-report=xml --junitxml=test-results.xml

# Check for test failures
pytest --maxfail=1

# Run with parallel execution (if pytest-xdist installed)
pytest -n auto
```

---

## Test Quality Metrics

### Test Characteristics
- ✅ **Fast**: 147 tests run in ~5 seconds
- ✅ **Isolated**: Each test uses transaction rollback
- ✅ **Deterministic**: No flaky tests observed
- ✅ **Clear**: Descriptive test names and assertions
- ✅ **Maintainable**: Test structure mirrors src/ directory

### Test Coverage Philosophy
**Phase 1 Approach**: Focus on critical business logic and user-facing workflows
- **High priority**: Lock creation, schedule algorithm, user attribution
- **Medium priority**: CRUD operations, validation
- **Lower priority**: Logging, formatting, utility functions

**Why**: Phase 1 is about proving the workflow works end-to-end. 30% coverage of critical paths is more valuable than 90% coverage of all code paths.

---

## Conclusion

✅ **Test Suite Status**: **CURRENT** (488 tests)

- All critical workflows tested
- Category-based scheduling fully tested
- Type 2 SCD ratio management validated
- Instagram API automation tested (Phase 2)
- Cloudinary integration tested
- Token management and encryption tested
- Multi-account management tested
- TelegramService refactored into 5 handler modules, all tested
- Per-chat settings management tested
- Interaction tracking tested
- 15+ Telegram bot commands tested

**Version History**:
- v1.0.0: 147 tests (Phase 1)
- v1.2.0: 155 tests (Phase 1.5 Week 1)
- v1.3.0: 173 tests (Phase 1.5 Week 2)
- v1.4.0: 268 tests (Phase 1.6)
- v1.5.0: 345 tests (Phase 2 - Instagram API)
- Current: 488 tests (Phase 1.8 + TelegramService refactor)

**Next Steps**:
- Maintain test coverage as new features added
- Consider adding performance tests for large media libraries (1000+ items)
- Add tests for future Shopify/Printify integrations (Phase 3-4)
