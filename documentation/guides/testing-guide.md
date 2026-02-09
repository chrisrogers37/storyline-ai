# Testing Guide

This document explains how testing works in the Storyline AI project.

## Quick Start

```bash
# Run all tests (database auto-created/cleaned up)
make test

# Run unit tests only
make test-unit

# Run tests without coverage (faster)
make test-quick
```

## How Test Database Works

The test suite **automatically creates and manages its own test database**. You don't need to manually create or configure it!

### What Happens When You Run Tests:

1. **Setup Phase** (once per test run):
   - Connects to PostgreSQL using credentials from `.env.test`
   - Creates `storyline_ai_test` database if it doesn't exist
   - Creates all tables using SQLAlchemy models
   - Prints confirmation: `✓ Created test database: storyline_ai_test`

2. **Test Execution** (for each test):
   - Each test gets a fresh database session
   - Tests run inside a transaction
   - Transaction is rolled back after each test (clean slate)

3. **Teardown Phase** (after all tests):
   - Drops all tables
   - Terminates all connections
   - Drops the test database
   - Prints confirmation: `✓ Dropped test database: storyline_ai_test`

### Benefits:

✅ **Zero manual setup** - Just run `make test`
✅ **CI/CD friendly** - Works in automated environments
✅ **Fast test isolation** - Rollback transactions, not recreating tables
✅ **Safe** - Never touches production data
✅ **New developer friendly** - No setup instructions needed

## Test Structure

```
tests/
├── conftest.py              # Pytest configuration & fixtures
├── cli/                     # CLI command tests
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

### Run Specific Test Types:

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

### Repository Tests Example:

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

### Service Tests Example:

```python
@pytest.mark.unit
class TestMediaIngestionService:
    def test_scan_directory(self, test_db):
        """Test scanning a directory for media."""
        service = MediaIngestionService(db=test_db)

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test file
            test_file = Path(temp_dir) / "test.jpg"
            test_file.write_bytes(b"fake image")

            result = service.scan_directory(temp_dir)

            assert result["added"] >= 1
```

### CLI Tests Example:

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

## Configuration

Test configuration is in `.env.test`:

```bash
# Test Database (auto-created)
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres          # Must have CREATE DATABASE permission
DB_PASSWORD=postgres
TEST_DB_NAME=storyline_ai_test

# Test Telegram (dummy values)
TELEGRAM_BOT_TOKEN=test_bot_token
TELEGRAM_CHANNEL_ID=-100123456789
ADMIN_TELEGRAM_CHAT_ID=123456789

# Always dry run in tests
DRY_RUN_MODE=true
LOG_LEVEL=DEBUG
```

**Important**: The `DB_USER` must have permission to create databases. Using `postgres` superuser works out of the box.

## Coverage

Test coverage is tracked with pytest-cov:

```bash
# Run with coverage report
make test

# Generate HTML coverage report
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

## Troubleshooting

### "FATAL: database 'storyline_ai_test' does not exist"

This shouldn't happen - the test suite creates it automatically! If you see this:
- Check PostgreSQL is running: `pg_ctl status`
- Check credentials in `.env.test`
- Verify `DB_USER` has CREATE DATABASE permission

### "Could not connect to server"

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
# Edit .env.test:
DB_USER=postgres
DB_PASSWORD=postgres

# Option 2: Grant permissions to your user
psql -U postgres -c "ALTER USER storyline_user CREATEDB;"
```

### Tests are slow

Use faster options:
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

## Best Practices

1. **Test Isolation**: Each test should be independent
   - Don't rely on test execution order
   - Don't share state between tests
   - The `test_db` fixture handles cleanup automatically

2. **Descriptive Names**: Use clear test names
   ```python
   ✅ def test_create_user_with_valid_data(self):
   ❌ def test_user1(self):
   ```

3. **One Assertion Per Concept**: Keep tests focused
   ```python
   ✅ def test_user_creation_sets_default_role(self):
       user = repo.create(telegram_user_id=123)
       assert user.role == "member"

   ❌ def test_user_everything(self):
       # Tests creation, updates, deletion all at once
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

## Continuous Integration

In CI environments (GitHub Actions, etc.), tests run automatically:

```yaml
# .github/workflows/test.yml example
- name: Run tests
  run: |
    make install
    make test
  env:
    # CI will use .env.test automatically
    POSTGRES_HOST: localhost
    POSTGRES_PORT: 5432
```

No special setup needed - the test database is created automatically!

## Test Coverage Goals

- **Repositories**: 100% (all CRUD operations)
- **Services**: 80%+ (core business logic)
- **Utilities**: 90%+ (pure functions)
- **CLI**: 70%+ (happy paths + error cases)

Check current coverage:
```bash
make test
# Look for coverage report at end
```

---

**Questions?** See `CLAUDE.md` for development guidelines or open an issue.
