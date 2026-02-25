# Fix 01: InteractionService Session Leak in cleanup_transactions()

**Status**: ✅ COMPLETE
**Started**: 2026-02-25

**Investigation**: callback-reliability_2026-02-25
**Root Cause**: #1 — Connection Leak (InteractionService invisible to cleanup)
**Impact**: High | **Effort**: Low | **Risk**: Low

---

## Problem

`InteractionService` does **not** extend `BaseService`. It is a plain Python class with `self.interaction_repo = InteractionRepository()` (a `BaseRepository` subclass holding an open SQLAlchemy session).

`TelegramService` stores it at `self.interaction_service` (line 66 of `telegram_service.py`).

When `TelegramService.cleanup_transactions()` runs (inherited from `BaseService`, lines 32-51 of `base_service.py`), it iterates `dir(self)` and looks for:
1. **`BaseRepository` instances** — calls `end_read_transaction()` on them
2. **`BaseService` instances** — recursively calls `cleanup_transactions()` on them

Since `InteractionService` is neither, the traversal **skips it entirely**. The `InteractionRepository` session inside it is never cleaned up.

### Where cleanup is triggered

1. **`_handle_callback` finally block** — `telegram_service.py` line 608-610. Runs after every inline button callback. High-frequency path.
2. **`transaction_cleanup_loop` in main.py** — lines 128-141. Runs every 30 seconds across `[posting_service, telegram_service, lock_service, settings_service]`. Same blind spot.

### Impact

Every callback that calls `interaction_service.log_callback()` or `log_bot_response()` opens a transaction on `InteractionRepository`'s session that is never committed or rolled back. Over time, these "idle in transaction" sessions accumulate and exhaust the connection pool, causing callback hangs.

**Evidence**: 2 "idle in transaction" sessions on `user_interactions` SELECT queries observed in production.

---

## Solution: Override `cleanup_transactions()` on TelegramService

Add an explicit override that:
1. Calls `super().cleanup_transactions()` (handles all `BaseRepository` and `BaseService` attributes normally)
2. Explicitly calls `self.interaction_service.interaction_repo.end_read_transaction()`

### Why not make InteractionService extend BaseService?

- `BaseService.__init__()` creates a `ServiceRunRepository` (line 29 of `base_service.py`), adding an unnecessary DB connection
- The original design comment (lines 19-22 of `interaction_service.py`) explains the intent: fire-and-forget logging shouldn't add overhead
- Option A (override) is a 5-line change in one file; Option B (change inheritance) has broader impact

---

## Implementation Steps

### Step 1: Add `cleanup_transactions()` override to TelegramService

**File**: `src/services/core/telegram_service.py`
**Location**: After `cleanup_operation_state()` (after line 90)

```python
def cleanup_transactions(self):
    """Override to also clean up InteractionService's repository session.

    InteractionService does not extend BaseService (by design - it's
    fire-and-forget logging that doesn't need execution tracking).
    The base cleanup_transactions() traversal skips it because it only
    looks for BaseRepository and BaseService attributes. We explicitly
    clean up its repo here to prevent "idle in transaction" leaks.
    """
    super().cleanup_transactions()
    try:
        self.interaction_service.interaction_repo.end_read_transaction()
    except Exception:
        pass  # Suppress errors during cleanup (matches base class pattern)
```

### Step 2: No changes needed elsewhere

- `src/main.py` `transaction_cleanup_loop`: Automatically benefits from the override (calls `telegram_service.cleanup_transactions()`)
- `src/services/core/interaction_service.py`: Remains unchanged
- `src/services/base_service.py`: No changes to base traversal logic

---

## Tests

**File**: `tests/src/services/test_telegram_service.py`

Add a new test class:

```python
@pytest.mark.unit
class TestCleanupTransactions:
    """Tests for TelegramService.cleanup_transactions() override."""

    def test_cleanup_transactions_cleans_interaction_repo(self, mock_telegram_service):
        """cleanup_transactions() must clean up InteractionService's repo.

        This is the critical fix: InteractionService does not extend BaseService,
        so its interaction_repo is invisible to the base cleanup traversal.
        """
        service = mock_telegram_service
        mock_interaction_repo = Mock()
        service.interaction_service.interaction_repo = mock_interaction_repo

        service.cleanup_transactions()

        mock_interaction_repo.end_read_transaction.assert_called_once()

    def test_cleanup_transactions_suppresses_interaction_repo_errors(self, mock_telegram_service):
        """Errors in interaction_repo cleanup are suppressed."""
        service = mock_telegram_service
        mock_interaction_repo = Mock()
        mock_interaction_repo.end_read_transaction.side_effect = Exception("DB error")
        service.interaction_service.interaction_repo = mock_interaction_repo

        # Should not raise
        service.cleanup_transactions()

    def test_cleanup_transactions_handles_missing_interaction_service(self, mock_telegram_service):
        """Graceful handling if interaction_service is None."""
        service = mock_telegram_service
        service.interaction_service = None

        # Should not raise
        service.cleanup_transactions()
```

---

## Verification

After deploying:

```sql
-- Should show NO long-lived "idle in transaction" on user_interactions
SELECT pid, state, query, now() - state_change AS idle_duration
FROM pg_stat_activity
WHERE datname = current_database()
  AND state = 'idle in transaction'
ORDER BY state_change;
```

## Files Changed

| File | Change |
|------|--------|
| `src/services/core/telegram_service.py` | Add `cleanup_transactions()` override (~8 lines) |
| `tests/src/services/test_telegram_service.py` | Add `TestCleanupTransactions` class (3 tests) |
