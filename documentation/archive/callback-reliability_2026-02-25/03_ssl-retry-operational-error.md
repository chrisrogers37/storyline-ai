# Fix 03: SSL Retry on OperationalError in Callback Handlers

**Status**: ✅ COMPLETE
**Started**: 2026-02-25

**Investigation**: callback-reliability_2026-02-25
**Root Cause**: #3 — SSL Staleness (Neon drops idle SSL connections)
**Impact**: Medium | **Effort**: Low | **Risk**: Low

---

## Problem

Neon PostgreSQL drops idle SSL connections. When the callback handler's core DB operations (`history_repo.create()`, `queue_repo.delete()`) hit a stale connection, `psycopg2.OperationalError: SSL connection has been closed unexpectedly` is raised. Unlike `InteractionService` (which has try/except guards), these core operations have NO error handling — the exception propagates up, preventing the caption edit, and the user sees no reaction.

`pool_pre_ping=True` in `database.py` checks connections at checkout, but there's a window where a connection passes pre_ping then the SSL drops before the query executes.

**Evidence**: 2 SSL errors observed at 12:02 and 12:15 UTC (on InteractionService paths, but same mechanism affects core repos).

---

## Solution

Add a retry-once pattern around core DB operations. On `OperationalError`:
1. Force session refresh on all affected repos via `end_read_transaction()`
2. Re-fetch the queue item (may have been deleted by concurrent operation)
3. Retry the DB operations ONCE
4. If retry fails, let exception propagate

---

## Implementation Steps

### Step 1: Add import

**File**: `src/services/core/telegram_callbacks.py`

```python
from sqlalchemy.exc import OperationalError
```

### Step 2: Extract DB operations into helper

**File**: `src/services/core/telegram_callbacks.py`

New method `_execute_complete_db_ops()` encapsulating lines 79-109:
```python
def _execute_complete_db_ops(self, queue_id, queue_item, user, status, success):
    """Execute core DB operations for completing a queue action.

    Separated to enable retry on OperationalError.
    Returns the media_item.
    """
    media_item = self.service.media_repo.get_by_id(str(queue_item.media_item_id))

    self.service.history_repo.create(
        HistoryCreateParams(
            media_item_id=str(queue_item.media_item_id),
            queue_item_id=queue_id,
            queue_created_at=queue_item.created_at,
            queue_deleted_at=datetime.utcnow(),
            scheduled_for=queue_item.scheduled_for,
            posted_at=datetime.utcnow(),
            status=status,
            success=success,
            posted_by_user_id=str(user.id),
            posted_by_telegram_username=user.telegram_username,
            chat_settings_id=str(queue_item.chat_settings_id)
            if queue_item.chat_settings_id else None,
        )
    )

    if status == "posted":
        self.service.media_repo.increment_times_posted(str(queue_item.media_item_id))
        self.service.lock_service.create_lock(str(queue_item.media_item_id))
        self.service.user_repo.increment_posts(str(user.id))

    self.service.queue_repo.delete(queue_id)
    return media_item
```

### Step 3: Add session refresh helper

```python
def _refresh_repo_sessions(self):
    """Force session refresh on all repos used by callback DB operations."""
    for repo in [
        self.service.history_repo,
        self.service.media_repo,
        self.service.queue_repo,
        self.service.user_repo,
    ]:
        repo.end_read_transaction()
    self.service.lock_service.lock_repo.end_read_transaction()
```

### Step 4: Rewrite `_do_complete_queue_action` with retry

```python
async def _do_complete_queue_action(self, queue_id, user, query, status, success, caption, callback_name):
    """Internal implementation of queue action completion (runs under lock)."""
    queue_item = await validate_queue_item(self.service, queue_id, query)
    if not queue_item:
        return

    # Execute DB operations with retry-once on SSL/connection errors
    try:
        media_item = self._execute_complete_db_ops(queue_id, queue_item, user, status, success)
    except OperationalError as e:
        logger.warning(
            f"OperationalError during {callback_name} for queue {queue_id}, "
            f"refreshing sessions and retrying: {e}"
        )
        self._refresh_repo_sessions()

        # Re-fetch — may have been deleted by concurrent operation
        queue_item = self.service.queue_repo.get_by_id(queue_id)
        if not queue_item:
            logger.info(f"Queue item {queue_id} gone after session refresh")
            await query.edit_message_caption(caption="⚠️ This item was already processed.")
            return

        # Retry once — if this fails, let it propagate
        media_item = self._execute_complete_db_ops(queue_id, queue_item, user, status, success)
        logger.info(f"Retry succeeded for {callback_name} on queue {queue_id}")

    await query.edit_message_caption(caption=caption)

    # Interaction logging (unchanged, already fire-and-forget)
    self.service.interaction_service.log_callback(...)
    self.service.interaction_service.log_bot_response(...)
    logger.info(f"Post {status} by {self.service._get_display_name(user)}")
```

### Step 5: Same pattern for `handle_rejected()`

Extract `_execute_reject_db_ops()` and wrap with the same retry pattern.

---

## Tests

**File**: `tests/src/services/test_telegram_callbacks.py`

Add `TestSSLRetry` class:

```python
class TestSSLRetry:
    async def test_operational_error_triggers_retry(self):
        """OperationalError triggers session refresh + retry."""
        # First history_repo.create raises, second succeeds
        service.history_repo.create.side_effect = [OperationalError(...), Mock()]
        await handlers.complete_queue_action(...)
        assert service.history_repo.create.call_count == 2

    async def test_non_operational_error_not_retried(self):
        """ValueError is not retried."""
        service.history_repo.create.side_effect = ValueError("bad")
        with pytest.raises(ValueError):
            await handlers._do_complete_queue_action(...)
        assert service.history_repo.create.call_count == 1

    async def test_second_failure_propagates(self):
        """Both attempts fail -> exception propagates."""
        service.history_repo.create.side_effect = [OperationalError(...), OperationalError(...)]
        with pytest.raises(OperationalError):
            await handlers._do_complete_queue_action(...)

    async def test_queue_item_deleted_during_retry(self):
        """Queue item gone after refresh -> shows 'already processed'."""
        service.history_repo.create.side_effect = OperationalError(...)
        service.queue_repo.get_by_id.side_effect = [mock_item, None]  # gone on retry
        await handlers._do_complete_queue_action(...)
        assert "already processed" in mock_query.edit_message_caption.call_args[...]

    async def test_rejected_operational_error_triggers_retry(self):
        """handle_rejected also retries on OperationalError."""
```

---

## Idempotency Note

If `history_repo.create()` succeeds but `queue_repo.delete()` fails with OperationalError, the retry will create a duplicate history record. This is acceptable:
- Duplicates are identifiable by `queue_item_id`
- The probability is very low (SSL drop between two successive commits)
- Proper transaction wrapping would require significant repository refactoring

---

## Files Changed

| File | Change |
|------|--------|
| `src/services/core/telegram_callbacks.py` | Add `OperationalError` import, extract helpers, add retry logic |
| `tests/src/services/test_telegram_callbacks.py` | Add `TestSSLRetry` class (5 tests) |
