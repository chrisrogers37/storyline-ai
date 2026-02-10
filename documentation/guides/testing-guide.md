# Testing Guide

This document explains how testing works in the Storyline AI project.

**Current test count**: 494 tests (351 passing, 143 skipped integration tests) as of v1.6.0

## Quick Start

```bash
# Run all tests (database auto-created/cleaned up)
make test

# Run unit tests only
make test-unit

# Run tests without coverage (faster)
make test-quick

# Run a specific test file
pytest tests/src/services/test_telegram_callbacks.py

# Run a specific test method
pytest tests/src/services/test_scheduler.py::TestSchedulerService::test_create_schedule
```

## Automatic Test Database Setup

The test suite **automatically creates and manages its own PostgreSQL test database**. No manual database setup is required.

### What Happens When You Run Tests

1. **Setup Phase** (once per test run):
   - Connects to PostgreSQL using credentials from `.env.test`
   - Creates `storyline_ai_test` database if it doesn't exist
   - Creates all tables using SQLAlchemy models

2. **Test Execution** (for each test):
   - Each test gets a fresh database session
   - Tests run inside a transaction
   - Transaction is rolled back after each test (clean slate)

3. **Teardown Phase** (after all tests):
   - Drops all tables
   - Terminates all connections
   - Drops the test database

### Configuration (`.env.test`)

```bash
# Database connection (test DB auto-created from this)
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres              # Must have CREATE DATABASE permission
DB_PASSWORD=postgres
TEST_DB_NAME=storyline_ai_test  # The database to auto-create

# Test values for required settings
TELEGRAM_BOT_TOKEN=test_bot_token
TELEGRAM_CHANNEL_ID=-100123456789
ADMIN_TELEGRAM_CHAT_ID=123456789
DRY_RUN_MODE=true
LOG_LEVEL=DEBUG
```

**Important**: The `DB_USER` must have permission to create databases. Using `postgres` superuser works out of the box.

### Fixture Architecture (`tests/conftest.py`)

```python
@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """
    Session-scoped fixture - runs once per test session.

    1. Connects to 'postgres' database
    2. Creates 'storyline_ai_test' database
    3. Creates all tables via SQLAlchemy
    4. Yields engine to tests
    5. Drops everything after tests complete
    """
    create_test_database()  # CREATE DATABASE storyline_ai_test

    engine = create_engine(settings.test_database_url)
    Base.metadata.create_all(engine)  # CREATE TABLE users, media_items, etc.

    yield engine

    Base.metadata.drop_all(engine)  # DROP TABLE ...
    drop_test_database()            # DROP DATABASE storyline_ai_test


@pytest.fixture(scope="function")
def test_db(setup_test_database):
    """
    Function-scoped fixture - runs for each test.

    Provides clean database session with automatic rollback.
    """
    session = TestSessionLocal()
    session.begin_nested()  # Start transaction

    yield session

    session.rollback()  # Rollback transaction (clean slate)
    session.close()
```

Key design decisions:
- **Session-scoped setup**: Database created once per test run, not per test
- **Transaction rollback**: Each test rolled back for fast isolation
- **Automatic cleanup**: Database dropped after all tests complete
- **Error handling**: Terminates connections before dropping database
- **Idempotent**: Safe to run multiple times

## Test Structure

```
tests/
├── conftest.py              # Pytest configuration & fixtures
├── cli/                     # CLI command tests (4 files)
│   ├── test_media_commands.py
│   ├── test_queue_commands.py
│   ├── test_user_commands.py
│   └── test_health_commands.py
├── src/
│   ├── repositories/        # Repository layer tests (8 files)
│   │   ├── test_user_repository.py
│   │   ├── test_media_repository.py
│   │   ├── test_queue_repository.py
│   │   ├── test_history_repository.py
│   │   ├── test_lock_repository.py
│   │   ├── test_service_run_repository.py
│   │   ├── test_category_mix_repository.py
│   │   └── test_interaction_repository.py
│   ├── services/            # Service layer tests (17 files)
│   │   ├── test_base_service.py
│   │   ├── test_media_ingestion.py
│   │   ├── test_scheduler.py
│   │   ├── test_media_lock.py
│   │   ├── test_posting.py
│   │   ├── test_telegram_service.py       # Core service tests
│   │   ├── test_telegram_commands.py      # Command handler tests
│   │   ├── test_telegram_callbacks.py     # Callback handler tests
│   │   ├── test_telegram_settings.py      # Settings UI tests
│   │   ├── test_telegram_accounts.py      # Account handler tests
│   │   ├── test_health_check.py
│   │   ├── test_settings_service.py       # Per-chat settings
│   │   ├── test_instagram_account_service.py  # Multi-account
│   │   ├── test_interaction_service.py    # Bot interaction tracking
│   │   ├── test_instagram_api.py          # Instagram Graph API
│   │   ├── test_cloud_storage.py          # Cloudinary integration
│   │   └── test_token_refresh.py          # Token lifecycle
│   └── utils/               # Utility tests (5 files)
│       ├── test_file_hash.py
│       ├── test_logger.py
│       ├── test_validators.py
│       ├── test_image_processing.py
│       └── test_encryption.py             # Fernet encryption
└── integration/             # Integration tests
    └── test_instagram_posting.py          # End-to-end posting
```

## Test Markers

Tests are marked with pytest markers for selective running:

```python
@pytest.mark.unit           # Unit tests (fast, no external dependencies)
@pytest.mark.integration    # Integration tests (slower, external dependencies)
@pytest.mark.slow           # Slow tests (can be skipped in development)
```

Run specific test types:

```bash
# Only unit tests
make test-unit

# Only integration tests
make test-integration

# Skip slow tests
pytest -v -m "not slow"
```

## Fixtures

### Database Fixtures

**`setup_test_database` (session-scoped, auto-use)**
- Creates test database and tables once per test session
- Automatically runs before any tests
- Cleans up after all tests complete

**`test_db` (function-scoped)**
- Provides a clean database session for each test
- Automatically rolls back changes after each test
- Usage:
  ```python
  def test_create_user(test_db):
      repo = UserRepository(test_db)
      user = repo.create(telegram_user_id=123)
      assert user.id is not None
  ```

### Sample Data Fixtures

**`sample_media_item`**
- Returns a dictionary with sample media item data
- Useful for testing without creating actual files

## Writing Tests

### Repository Tests

```python
@pytest.mark.unit
class TestUserRepository:
    def test_create_user(self, test_db):
        """Test creating a new user."""
        repo = UserRepository(test_db)

        user = repo.create(
            telegram_user_id=123456789,
            telegram_username="testuser"
        )

        assert user.id is not None
        assert user.telegram_user_id == 123456789
```

### Service Tests

```python
@pytest.mark.unit
class TestMediaIngestionService:
    def test_scan_directory(self, test_db):
        """Test scanning a directory for media."""
        service = MediaIngestionService(db=test_db)

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.jpg"
            test_file.write_bytes(b"fake image")

            result = service.scan_directory(temp_dir)

            assert result["added"] >= 1
```

### CLI Tests

```python
from click.testing import CliRunner

@pytest.mark.unit
class TestMediaCommands:
    def test_list_media(self, test_db):
        """Test list-media CLI command."""
        runner = CliRunner()
        result = runner.invoke(list_media, ["--limit", "10"])

        assert result.exit_code == 0
```

## Best Practices

1. **Test Isolation**: Each test should be independent
   - Don't rely on test execution order
   - Don't share state between tests
   - The `test_db` fixture handles cleanup automatically

2. **Descriptive Names**: Use clear test names
   ```python
   def test_create_user_with_valid_data(self):     # Good
   def test_user1(self):                            # Bad
   ```

3. **One Assertion Per Concept**: Keep tests focused
   ```python
   def test_user_creation_sets_default_role(self):
       user = repo.create(telegram_user_id=123)
       assert user.role == "member"
   ```

4. **Use Markers**: Tag your tests appropriately
   ```python
   @pytest.mark.unit          # Fast, isolated
   @pytest.mark.integration   # Uses external services
   @pytest.mark.slow          # Takes > 1 second
   ```

5. **Mock External Services**: Don't make real API calls
   ```python
   @patch("src.services.telegram_service.Application")
   def test_send_message(self, mock_app):
       mock_app.bot.send_message = AsyncMock()
       # Test without hitting Telegram API
   ```

## Coverage

Test coverage is tracked with pytest-cov:

```bash
# Run with coverage report
make test

# Generate HTML coverage report
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

### Coverage Goals

- **Repositories**: 100% (all CRUD operations)
- **Services**: 80%+ (core business logic)
- **Utilities**: 90%+ (pure functions)
- **CLI**: 70%+ (happy paths + error cases)

## Continuous Integration

In CI environments (GitHub Actions, etc.), tests run automatically. The test database is created automatically - no special setup needed.

```yaml
# .github/workflows/test.yml
services:
  postgres:
    image: postgres:15
    env:
      POSTGRES_PASSWORD: postgres
    options: >-
      --health-cmd pg_isready
      --health-interval 10s

- name: Run tests
  run: make test
```

## Troubleshooting

### "Connection refused"

PostgreSQL isn't running:
```bash
# macOS (Homebrew)
brew services start postgresql

# Linux
sudo systemctl start postgresql
```

### "Permission denied to create database"

The `DB_USER` in `.env.test` lacks permissions:
```bash
# Option 1: Use postgres superuser (simplest)
# Edit .env.test: DB_USER=postgres

# Option 2: Grant permissions to your user
psql -U postgres -c "ALTER USER storyline_user CREATEDB;"
```

### "FATAL: database 'storyline_ai_test' does not exist"

This shouldn't happen since the test suite creates it automatically. If you see this:
- Check PostgreSQL is running: `pg_ctl status`
- Check credentials in `.env.test`
- Verify `DB_USER` has CREATE DATABASE permission

### Tests are slow

```bash
# Skip coverage calculation
make test-quick

# Run only unit tests
make test-unit

# Run only failed tests
make test-failed

# Parallel execution (requires pytest-xdist)
pytest -v -n auto
```

### Want to inspect the test database?

Run tests with `--pdb` to pause before cleanup:
```bash
pytest --pdb -x  # Stops at first failure, before cleanup
```

Then connect in another terminal:
```bash
psql -U postgres -d storyline_ai_test
```

---

**Questions?** See `CLAUDE.md` for development guidelines or open an issue.
