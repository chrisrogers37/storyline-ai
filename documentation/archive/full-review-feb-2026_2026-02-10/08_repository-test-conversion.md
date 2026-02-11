# Phase 08: Convert Skipped Repository Tests to Unit Tests

✅ COMPLETE | Completed: 2026-02-10 | PR: #37

| Field | Value |
|---|---|
| **PR Title** | `test: convert skipped repository tests to unit tests with mocks` |
| **Risk Level** | Low |
| **Effort** | Large (6-8 hours) |
| **Dependencies** | Phase 03 (so `BaseRepository.check_connection` exists to test) |
| **Blocks** | Phase 10, Phase 12 |
| **Files Modified** | All 7 files in `tests/src/repositories/` |

---

## Problem Description

There are **70 skipped tests** across 7 repository test files. Every single one is skipped with:

```python
@pytest.mark.skip(
    reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/"
)
```

These tests were written to run against a real database (`test_db` fixture), but that fixture was never implemented. The tests need to be converted to unit tests that mock the SQLAlchemy session.

**Test counts by file:**

| File | Skipped Tests |
|---|---|
| `test_media_repository.py` | 8 |
| `test_queue_repository.py` | 12 |
| `test_user_repository.py` | 14 |
| `test_interaction_repository.py` | 14 |
| `test_lock_repository.py` | 8 |
| `test_history_repository.py` | 6 |
| `test_service_run_repository.py` | 8 |
| **Total** | **70** |

---

## Mocking Strategy

### The Key Thing to Mock

Every repository inherits from `BaseRepository` (`src/repositories/base_repository.py`). The `__init__` method calls `get_db()` to get a real database session:

```python
class BaseRepository:
    def __init__(self):
        self._db_generator = get_db()
        self._db: Session = next(self._db_generator)
```

We must prevent this real database connection by patching `__init__`. The `db` property on `BaseRepository` returns `self._db`, so we set `_db` to our mock session.

### Standard Fixture Pattern

Use this pattern for every repository. It prevents the real `__init__` from running, injects a mock session, and makes the repository usable for unit tests:

```python
from unittest.mock import Mock, patch, MagicMock, PropertyMock
from sqlalchemy.orm import Session


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    session = MagicMock(spec=Session)
    # Make query().filter().first() chainable
    session.query.return_value.filter.return_value.first.return_value = None
    session.query.return_value.filter.return_value.all.return_value = []
    session.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    return session


@pytest.fixture
def media_repo(mock_db):
    """Create MediaRepository with mocked DB session."""
    with patch.object(MediaRepository, '__init__', lambda self: None):
        repo = MediaRepository()
        repo._db = mock_db
        return repo
```

### How Mock-Based Tests Differ from Integration Tests

The original tests created real database objects and asserted on the return values. Unit tests instead:

1. Configure mock return values to simulate what the database would return
2. Call the repository method
3. Assert that the correct SQLAlchemy operations were called (`.add()`, `.commit()`, `.query()`, etc.)
4. Assert that the return value is correct given the mock configuration

---

## File-by-File Conversion Instructions

### 1. `test_media_repository.py` -- 8 Tests

**Special considerations:** The `create()` method calls `self.db.add(item)`, `self.db.commit()`, and `self.db.refresh(item)`. For `refresh`, we need a side effect that sets the `id` attribute.

**Add these fixtures at the top of the file (replace the existing imports):**

```python
"""Tests for MediaRepository."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4, UUID
from sqlalchemy.orm import Session

from src.repositories.media_repository import MediaRepository
from src.models.media_item import MediaItem


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    session = MagicMock(spec=Session)
    return session


@pytest.fixture
def media_repo(mock_db):
    """Create MediaRepository with mocked DB session."""
    with patch.object(MediaRepository, '__init__', lambda self: None):
        repo = MediaRepository()
        repo._db = mock_db
        return repo
```

**Example conversion -- `test_create_media_item`:**

Before (skipped):
```python
@pytest.mark.skip(
    reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/"
)
def test_create_media_item(self, test_db):
    """Test creating a new media item."""
    repo = MediaRepository(test_db)

    media = repo.create(
        file_path="/test/image.jpg",
        file_name="image.jpg",
        file_hash="abc123",
        file_size_bytes=102400,
        mime_type="image/jpeg",
    )

    assert media.id is not None
    assert isinstance(media.id, UUID)
    assert media.file_path == "/test/image.jpg"
    assert media.file_hash == "abc123"
    assert media.times_posted == 0
```

After (unit test):
```python
def test_create_media_item(self, media_repo, mock_db):
    """Test creating a new media item."""
    test_id = uuid4()

    def set_id_on_refresh(item):
        item.id = test_id

    mock_db.refresh.side_effect = set_id_on_refresh

    media = media_repo.create(
        file_path="/test/image.jpg",
        file_name="image.jpg",
        file_hash="abc123",
        file_size_bytes=102400,
        mime_type="image/jpeg",
    )

    # Verify database operations
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once()

    # Verify the created object
    assert media.file_path == "/test/image.jpg"
    assert media.file_hash == "abc123"
```

**Example conversion -- `test_get_by_path`:**

Before (skipped):
```python
@pytest.mark.skip(
    reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/"
)
def test_get_by_path(self, test_db):
    """Test retrieving media by file path."""
    repo = MediaRepository(test_db)

    created_media = repo.create(...)
    found_media = repo.get_by_path("/test/unique.jpg")
    assert found_media is not None
    assert found_media.id == created_media.id
```

After (unit test):
```python
def test_get_by_path(self, media_repo, mock_db):
    """Test retrieving media by file path."""
    mock_media = Mock(spec=MediaItem)
    mock_media.id = uuid4()
    mock_media.file_path = "/test/unique.jpg"

    mock_db.query.return_value.filter.return_value.first.return_value = mock_media

    found = media_repo.get_by_path("/test/unique.jpg")

    assert found is not None
    assert found.file_path == "/test/unique.jpg"
    mock_db.query.assert_called_once_with(MediaItem)
```

**Remaining tests to convert with the same pattern:**
- `test_get_by_hash` -- mock `filter().first()` return
- `test_get_duplicates` -- mock `filter().all()` return with multiple items
- `test_increment_times_posted` -- mock `get_by_id` return, verify `.commit()` called
- `test_list_all_with_filters` -- mock query chain, verify filter arguments
- `test_get_never_posted` -- mock query chain with `filter(times_posted == 0)`
- `test_get_least_posted` -- mock `order_by().limit().all()` return

---

### 2. `test_queue_repository.py` -- 12 Tests

**Special considerations:** The `QueueRepository` tests previously created `MediaItem` and `User` objects as dependencies. In unit tests, we pass UUIDs directly (since the repository just stores them as foreign keys). The `shift_slots_forward` tests (5 of 12) are more complex because they test cascading updates.

**Fixture:**
```python
@pytest.fixture
def queue_repo(mock_db):
    """Create QueueRepository with mocked DB session."""
    with patch.object(QueueRepository, '__init__', lambda self: None):
        repo = QueueRepository()
        repo._db = mock_db
        return repo
```

**Example conversion -- `test_create_queue_item`:**

After (unit test):
```python
def test_create_queue_item(self, queue_repo, mock_db):
    """Test creating a new queue item."""
    test_id = uuid4()
    media_id = uuid4()
    scheduled_time = datetime.utcnow() + timedelta(hours=1)

    def set_id_on_refresh(item):
        item.id = test_id

    mock_db.refresh.side_effect = set_id_on_refresh

    queue_item = queue_repo.create(
        media_item_id=str(media_id),
        scheduled_for=scheduled_time,
    )

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    assert queue_item.media_item_id == str(media_id)
```

**For `shift_slots_forward` tests (5 tests):** These test a method that queries pending items, sorts them, and updates `scheduled_for` on multiple rows. Mock the query to return a list of mock queue items, then verify that the correct `scheduled_for` values are assigned.

```python
def test_shift_slots_forward_basic(self, queue_repo, mock_db):
    """Test basic slot shifting."""
    base_time = datetime(2026, 1, 15, 10, 0, 0)

    items = []
    for i, offset_hours in enumerate([0, 4, 8, 12]):
        item = Mock()
        item.id = uuid4()
        item.scheduled_for = base_time + timedelta(hours=offset_hours)
        item.status = "pending"
        items.append(item)

    # Mock: get_by_id returns first item
    queue_repo.get_by_id = Mock(return_value=items[0])

    # Mock: query for all pending items returns all 4
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = items

    shifted = queue_repo.shift_slots_forward(str(items[0].id))

    assert shifted == 3
    mock_db.commit.assert_called()
```

---

### 3. `test_user_repository.py` -- 14 Tests

**Special considerations:** The `get_or_create` method returns a tuple `(user, created_bool)`. `update_profile` and `update_role` modify the existing object.

**Fixture:**
```python
@pytest.fixture
def user_repo(mock_db):
    """Create UserRepository with mocked DB session."""
    with patch.object(UserRepository, '__init__', lambda self: None):
        repo = UserRepository()
        repo._db = mock_db
        return repo
```

**Example conversion -- `test_get_by_telegram_id_not_found`:**

After:
```python
def test_get_by_telegram_id_not_found(self, user_repo, mock_db):
    """Test retrieving non-existent user."""
    mock_db.query.return_value.filter.return_value.first.return_value = None

    user = user_repo.get_by_telegram_id(999999999)

    assert user is None
```

**Example conversion -- `test_update_profile`:**

After:
```python
def test_update_profile(self, user_repo, mock_db):
    """Test updating user profile data."""
    mock_user = Mock()
    mock_user.id = uuid4()
    mock_user.telegram_username = "oldname"
    mock_user.telegram_first_name = "Old"

    mock_db.query.return_value.filter.return_value.first.return_value = mock_user

    updated_user = user_repo.update_profile(
        str(mock_user.id),
        telegram_username="newname",
        telegram_first_name="New",
        telegram_last_name="Person",
    )

    assert updated_user.telegram_username == "newname"
    assert updated_user.telegram_first_name == "New"
    mock_db.commit.assert_called()
```

---

### 4. `test_interaction_repository.py` -- 14 Tests

**Special considerations:** Several tests (`get_user_stats`, `get_team_activity`, `get_content_decisions`) call aggregation methods that return computed dicts. Mock the query results to return raw data, then verify the aggregation logic produces the correct dict.

The `get_bot_responses_by_chat` tests filter by `interaction_type == "bot_response"` and `telegram_chat_id`. These are important to get right.

**Fixture:**
```python
@pytest.fixture
def interaction_repo(mock_db):
    """Create InteractionRepository with mocked DB session."""
    with patch.object(InteractionRepository, '__init__', lambda self: None):
        repo = InteractionRepository()
        repo._db = mock_db
        return repo
```

**Example conversion -- `test_create_command_interaction`:**

After:
```python
def test_create_command_interaction(self, interaction_repo, mock_db):
    """Test creating a command interaction."""
    test_id = uuid4()
    user_id = str(uuid4())

    def set_id_on_refresh(item):
        item.id = test_id

    mock_db.refresh.side_effect = set_id_on_refresh

    interaction = interaction_repo.create(
        user_id=user_id,
        interaction_type="command",
        interaction_name="/status",
        context={"queue_size": 5},
        telegram_chat_id=123456,
        telegram_message_id=789,
    )

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    assert interaction.interaction_type == "command"
    assert interaction.interaction_name == "/status"
    assert interaction.context == {"queue_size": 5}
    assert interaction.telegram_chat_id == 123456
```

**For aggregation tests (`get_user_stats`, `get_team_activity`, `get_content_decisions`):** These methods build dicts from raw query results. If the method internally runs multiple queries, mock each query chain separately. Check the source code of each method to understand the exact query pattern.

---

### 5. `test_lock_repository.py` -- 8 Tests

**Special considerations:** The `is_locked` method checks for active locks (not expired). The `cleanup_expired` method deletes rows and returns a count. Mock the query to return expired lock objects, then verify `delete()` was called.

**Fixture:**
```python
@pytest.fixture
def lock_repo(mock_db):
    """Create LockRepository with mocked DB session."""
    with patch.object(LockRepository, '__init__', lambda self: None):
        repo = LockRepository()
        repo._db = mock_db
        return repo
```

**Example conversion -- `test_is_locked_active_lock`:**

After:
```python
def test_is_locked_active_lock(self, lock_repo, mock_db):
    """Test checking if media is locked with active lock."""
    media_id = uuid4()

    # Simulate an active lock exists
    mock_db.query.return_value.filter.return_value.first.return_value = Mock()

    is_locked = lock_repo.is_locked(str(media_id))

    assert is_locked is True
```

**Example conversion -- `test_is_locked_no_lock`:**

After:
```python
def test_is_locked_no_lock(self, lock_repo, mock_db):
    """Test checking if media is locked with no lock."""
    media_id = uuid4()

    mock_db.query.return_value.filter.return_value.first.return_value = None

    is_locked = lock_repo.is_locked(str(media_id))

    assert is_locked is False
```

---

### 6. `test_history_repository.py` -- 6 Tests

**Special considerations:** After Phase 07 (if completed first), the `create()` method accepts a `HistoryCreateParams` dataclass instead of individual kwargs. If Phase 07 is not yet merged, convert tests using the current kwargs signature. Either way, the mocking pattern is the same.

**Fixture:**
```python
@pytest.fixture
def history_repo(mock_db):
    """Create HistoryRepository with mocked DB session."""
    with patch.object(HistoryRepository, '__init__', lambda self: None):
        repo = HistoryRepository()
        repo._db = mock_db
        return repo
```

**Example conversion -- `test_get_stats`:**

The `get_stats()` method (lines 123-150 of `history_repository.py`) runs three separate count queries. Each must be mocked:

After:
```python
def test_get_stats(self, history_repo, mock_db):
    """Test getting posting statistics."""
    # Mock the three scalar queries
    mock_db.query.return_value.filter.return_value.scalar.side_effect = [
        10,  # total
        8,   # successful
        2,   # failed
    ]

    stats = history_repo.get_stats(days=30)

    assert stats["total"] == 10
    assert stats["successful"] == 8
    assert stats["failed"] == 2
    assert stats["success_rate"] == 80.0
```

---

### 7. `test_service_run_repository.py` -- 8 Tests

**Special considerations:** The `create_run()` method sets `status = "running"` and `started_at = datetime.utcnow()`. The `complete_run()` method computes `execution_time_seconds`. The timing test (`test_execution_time_calculation`) uses `time.sleep(0.1)` which is inappropriate for a unit test -- convert it to verify the calculation logic instead.

**Fixture:**
```python
@pytest.fixture
def run_repo(mock_db):
    """Create ServiceRunRepository with mocked DB session."""
    with patch.object(ServiceRunRepository, '__init__', lambda self: None):
        repo = ServiceRunRepository()
        repo._db = mock_db
        return repo
```

**Example conversion -- `test_create_run`:**

After:
```python
def test_create_run(self, run_repo, mock_db):
    """Test creating a service run record."""
    test_id = uuid4()

    def set_id_on_refresh(item):
        item.id = test_id

    mock_db.refresh.side_effect = set_id_on_refresh

    run = run_repo.create_run(
        service_name="TestService",
        method_name="test_method",
        parameters={"param1": "value1"},
    )

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    assert run.service_name == "TestService"
    assert run.method_name == "test_method"
    assert run.status == "running"
```

**For `test_execution_time_calculation`:** Instead of sleeping, mock `started_at` to a known time and verify `complete_run` computes the delta correctly:

```python
def test_execution_time_calculation(self, run_repo, mock_db):
    """Test that execution time is calculated correctly."""
    from datetime import datetime, timedelta

    mock_run = Mock()
    mock_run.id = uuid4()
    mock_run.started_at = datetime(2026, 1, 15, 10, 0, 0)

    mock_db.query.return_value.filter.return_value.first.return_value = mock_run

    with patch("src.repositories.service_run_repository.datetime") as mock_dt:
        mock_dt.utcnow.return_value = datetime(2026, 1, 15, 10, 0, 5)  # 5 seconds later
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        completed = run_repo.complete_run(mock_run.id, status="success")

    assert completed.execution_time_seconds is not None
    mock_db.commit.assert_called()
```

---

## General Process for Each Test

For every skipped test, follow this checklist:

1. **Remove** the `@pytest.mark.skip(reason="TODO: ...")` decorator
2. **Change** the method signature from `def test_xxx(self, test_db)` to `def test_xxx(self, <repo_fixture>, mock_db)`
3. **Remove** any inline repository construction (e.g., `repo = MediaRepository(test_db)`)
4. **Remove** any dependency creation (e.g., creating media items or users just to satisfy foreign keys)
5. **Add** mock return values for any query the method will execute
6. **Call** the method under test
7. **Assert** on:
   - The return value (using mock return values you configured)
   - That the correct database operations were called (`.add()`, `.commit()`, `.query()`, etc.)

---

## Verification Checklist

After converting all tests:

- [ ] Run `pytest tests/src/repositories/ -v` -- all 70 tests should pass (0 skipped)
- [ ] Run `pytest tests/src/repositories/ -v --tb=short` -- verify no test uses `test_db` fixture
- [ ] Run `ruff check tests/src/repositories/`
- [ ] Run `ruff format tests/src/repositories/`
- [ ] Verify there are no remaining `@pytest.mark.skip` decorators: `grep -r "pytest.mark.skip" tests/src/repositories/` should return nothing
- [ ] Run `pytest --co tests/src/repositories/` to list all collected tests and verify the count matches expectations
- [ ] Run `pytest tests/src/repositories/ -x` to fail fast on first error during conversion
- [ ] Verify all fixture names are consistent: `mock_db`, `media_repo`, `queue_repo`, `user_repo`, `interaction_repo`, `lock_repo`, `history_repo`, `run_repo`

---

## What NOT To Do

1. **Do NOT create a `conftest.py` with shared fixtures.** Each test file should be self-contained with its own fixtures. Shared fixtures create hidden coupling between test files.
2. **Do NOT use `autospec=True` on the Session mock.** SQLAlchemy's `Session` has complex metaclass behavior that breaks with `autospec`. Use `MagicMock(spec=Session)` instead.
3. **Do NOT test the actual SQL queries.** Unit tests verify that the repository calls the right SQLAlchemy methods. The actual SQL is tested by integration tests (which belong in `tests/integration/`).
4. **Do NOT delete the skipped tests and write new ones from scratch.** Convert them in place -- the test names, docstrings, and logical assertions are already correct. Only the setup and execution need to change.
5. **Do NOT add `time.sleep()` to any converted test.** The original `test_execution_time_calculation` used sleep because it ran against a real database. Unit tests should mock time instead.
6. **Do NOT mock `BaseRepository.__init__` in a parent class or shared helper.** Use `patch.object(SpecificRepo, '__init__', lambda self: None)` in each fixture. This is explicit and clear.
7. **Do NOT change the `@pytest.mark.unit` class-level marker.** These are unit tests and should keep that marker.
8. **Do NOT create integration test versions of these tests at this time.** That is a separate task. This PR only converts skipped tests to unit tests.
