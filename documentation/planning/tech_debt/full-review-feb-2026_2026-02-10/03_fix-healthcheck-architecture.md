# Fix Architecture Violation in HealthCheckService

**Status**: ✅ COMPLETE
**Started**: 2026-02-10
**Completed**: 2026-02-10

| Field | Value |
|---|---|
| **PR Title** | `refactor: route health check database query through repository layer` |
| **Risk Level** | Low |
| **Effort** | Small (30 minutes) |
| **Dependencies** | None |
| **Blocks** | Phase 08 |
| **Files Modified** | `src/services/core/health_check.py`, `src/repositories/base_repository.py` |

---

## Problem Description

The project's architecture enforces strict separation of concerns:

```
Services --> Repositories --> Database
```

Services must **never** access the database directly. They must always go through a repository. This is documented in `CLAUDE.md` under "Key Design Principle: STRICT SEPARATION OF CONCERNS":

> - **Services** --> orchestrate business logic, call Repositories
> - **Repositories** --> CRUD operations, return Models
> - **NEVER violate layer boundaries**

`HealthCheckService._check_database()` violates this rule. It imports `sqlalchemy.text` and `get_db` directly, then executes raw SQL:

```python
from sqlalchemy import text
from src.config.database import get_db

# ...

def _check_database(self) -> dict:
    try:
        db = next(get_db())
        db.execute(text("SELECT 1"))
```

This is the **only** service in the entire codebase that directly accesses the database. It bypasses the repository layer completely.

The fix is to add a `check_connection()` static method to `BaseRepository` and call it from the service.

---

## Step-by-Step Implementation

### Step 1: Add `check_connection()` to `src/repositories/base_repository.py`

Add a new static method after the `__exit__` method (after line 107). This method creates its own short-lived session, executes `SELECT 1`, and cleans up.

**Before** (lines 100-107):

```python
    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures session is closed."""
        self.close()
        return False  # Don't suppress exceptions
```

**After** (lines 100-121):

```python
    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures session is closed."""
        self.close()
        return False  # Don't suppress exceptions

    @staticmethod
    def check_connection():
        """
        Verify database connectivity by executing a simple query.

        Used by HealthCheckService to test the database connection
        without violating the service/repository layer boundary.

        Raises:
            Exception: If database is unreachable or query fails
        """
        from sqlalchemy import text

        db = next(get_db())
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()
```

**Why `@staticmethod`?** This method does not need an instance of any repository. It creates and destroys its own session. Making it static means the health check service does not need to instantiate a `BaseRepository` just to check connectivity.

**Why the lazy import of `text`?** The `sqlalchemy` import is inside the method to be consistent with the existing pattern in the file (the file's top-level imports only include `Session` and `get_db`). This is a minor style choice; moving it to the top of the file would also be acceptable.

**Why `db.close()` in `finally`?** The method creates a short-lived session specifically for the health check. It must be closed to return the connection to the pool, even if the query fails.

---

### Step 2: Update imports in `src/services/core/health_check.py`

Remove the two imports that are only used for the direct database access, and add the `BaseRepository` import.

**Before** (lines 1-11):

```python
"""Health check service - system health monitoring."""

from datetime import datetime, timedelta
from sqlalchemy import text

from src.services.base_service import BaseService
from src.repositories.queue_repository import QueueRepository
from src.repositories.history_repository import HistoryRepository
from src.config.database import get_db
from src.config.settings import settings
from src.utils.logger import logger
```

**After** (lines 1-11):

```python
"""Health check service - system health monitoring."""

from datetime import datetime, timedelta

from src.services.base_service import BaseService
from src.repositories.queue_repository import QueueRepository
from src.repositories.history_repository import HistoryRepository
from src.repositories.base_repository import BaseRepository
from src.config.settings import settings
from src.utils.logger import logger
```

Changes made:
- **Removed**: `from sqlalchemy import text` (no longer needed in this file)
- **Removed**: `from src.config.database import get_db` (no longer needed in this file)
- **Added**: `from src.repositories.base_repository import BaseRepository`

---

### Step 3: Update `_check_database()` in `src/services/core/health_check.py`

Replace the direct database access with a call to the repository method.

**Before** (lines 69-77):

```python
    def _check_database(self) -> dict:
        """Check database connectivity."""
        try:
            db = next(get_db())
            db.execute(text("SELECT 1"))
            return {"healthy": True, "message": "Database connection OK"}
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {"healthy": False, "message": f"Database error: {str(e)}"}
```

**After** (lines 69-77):

```python
    def _check_database(self) -> dict:
        """Check database connectivity."""
        try:
            BaseRepository.check_connection()
            return {"healthy": True, "message": "Database connection OK"}
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {"healthy": False, "message": f"Database error: {str(e)}"}
```

The change is exactly two lines:
1. `db = next(get_db())` and `db.execute(text("SELECT 1"))` are replaced by `BaseRepository.check_connection()`

The error handling and return values remain identical.

---

## Complete File Diffs

### `src/repositories/base_repository.py` -- final state of changed region

```python
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures session is closed."""
        self.close()
        return False  # Don't suppress exceptions

    @staticmethod
    def check_connection():
        """
        Verify database connectivity by executing a simple query.

        Used by HealthCheckService to test the database connection
        without violating the service/repository layer boundary.

        Raises:
            Exception: If database is unreachable or query fails
        """
        from sqlalchemy import text

        db = next(get_db())
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()
```

### `src/services/core/health_check.py` -- final state of imports

```python
"""Health check service - system health monitoring."""

from datetime import datetime, timedelta

from src.services.base_service import BaseService
from src.repositories.queue_repository import QueueRepository
from src.repositories.history_repository import HistoryRepository
from src.repositories.base_repository import BaseRepository
from src.config.settings import settings
from src.utils.logger import logger
```

### `src/services/core/health_check.py` -- final state of `_check_database`

```python
    def _check_database(self) -> dict:
        """Check database connectivity."""
        try:
            BaseRepository.check_connection()
            return {"healthy": True, "message": "Database connection OK"}
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {"healthy": False, "message": f"Database error: {str(e)}"}
```

---

## Verification Checklist

```bash
# 1. Activate virtual environment
source venv/bin/activate

# 2. Lint check on both modified files
ruff check src/repositories/base_repository.py src/services/core/health_check.py

# 3. Format check
ruff format --check src/repositories/base_repository.py src/services/core/health_check.py

# 4. Run full test suite
pytest

# 5. Run health check service tests specifically
pytest tests/src/services/test_health_check.py -v

# 6. Verify the health check still works end-to-end (safe read-only command)
storyline-cli check-health

# 7. Verify health_check.py no longer imports sqlalchemy or get_db
grep -n "sqlalchemy" src/services/core/health_check.py   # Should return nothing
grep -n "get_db" src/services/core/health_check.py        # Should return nothing

# 8. Verify no other services import get_db directly (should only be in repositories and config)
grep -rn "from src.config.database import get_db" src/services/
# Expected: zero results (after this fix)
```

Step 6 (`storyline-cli check-health`) is the most important verification. It exercises the exact code path being changed and is a safe, read-only command.

---

## What NOT To Do

1. **Do NOT create a `HealthCheckRepository` class.** A full repository class is overkill for a single `SELECT 1` query. The `@staticmethod` on `BaseRepository` is the right level of abstraction -- it keeps the database access in the repository layer without creating unnecessary classes.

2. **Do NOT make `check_connection()` an instance method.** The health check service does not (and should not) instantiate a `BaseRepository`. The method needs no instance state -- it creates and destroys its own session. A static method is correct.

3. **Do NOT use an existing repository instance** (like `self.queue_repo`) to run the connectivity check. The purpose of `_check_database()` is to verify that a **new** database connection can be established. Reusing an existing session would test whether that specific session is alive, not whether the database is reachable. These are different failure modes.

4. **Do NOT remove the `try/finally` in `check_connection()`.** The session created inside the method must be closed even if the query fails. Without the `finally` block, a failed health check would leak a database connection from the pool every time it runs.

5. **Do NOT add this method to a different repository.** `BaseRepository` is the correct location because (a) connectivity checking is not specific to any domain entity, and (b) `BaseRepository` already owns the `get_db` import and session lifecycle logic.
