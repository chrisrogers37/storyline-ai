# Replace Silent Error Swallowing with Proper Handling

**Status**: ✅ COMPLETE
**Started**: 2026-02-10
**Completed**: 2026-02-10
**PR**: #30

| Field | Value |
|---|---|
| **PR Title** | `fix: replace silent error swallowing with debug logging` |
| **Risk Level** | Low |
| **Effort** | Small (1-2 hours) |
| **Dependencies** | None |
| **Blocks** | None |
| **Files Modified** | `src/repositories/base_repository.py`, `src/services/core/telegram_settings.py`, `src/services/core/telegram_accounts.py` |

---

## Problem Description

Several locations in the codebase use bare `except Exception: pass` blocks that silently swallow errors. When something goes wrong in these paths, there is absolutely no diagnostic output -- the error disappears entirely. This makes debugging production issues much harder than necessary.

There are two categories of silent swallowing in this codebase:

1. **Repository lifecycle/cleanup methods** (`base_repository.py`): These are places where swallowing errors is actually correct behavior (you do not want a cleanup failure to crash the application), but the lack of even `DEBUG`-level logging means you cannot see what happened when investigating issues.

2. **Telegram message deletion** (`telegram_settings.py`, `telegram_accounts.py`): These are "nice to have" cleanup operations where deleting a message fails silently. The message may already be deleted, the bot may lack permissions, etc. Crashing would be wrong, but logging at `DEBUG` level would help diagnose issues.

---

## Step-by-Step Implementation

### Step 1: Update `src/repositories/base_repository.py`

This file already imports `logger` (line 6), so no new imports are needed.

#### Change 1a: `db` property (lines 29-33)

**Rationale**: When the session is in a bad state and `rollback()` fails, we want to know what happened during debugging. This can indicate a closed connection, a disposed engine, or a corrupted session.

**Before**:

```python
    @property
    def db(self) -> Session:
        """Get the database session, ensuring it's in a clean state."""
        # Rollback any failed transaction to reset session state
        try:
            if not self._db.is_active:
                self._db.rollback()
        except Exception:
            pass
        return self._db
```

**After**:

```python
    @property
    def db(self) -> Session:
        """Get the database session, ensuring it's in a clean state."""
        # Rollback any failed transaction to reset session state
        try:
            if not self._db.is_active:
                self._db.rollback()
        except Exception as e:
            # Suppressed: rollback during session recovery is best-effort.
            # If this fails, the session may be unusable, but raising here
            # would mask the original error that caused the bad state.
            logger.debug(f"Suppressed error during session recovery rollback: {e}")
        return self._db
```

#### Change 1b: `end_read_transaction` inner except (lines 64-67)

**Rationale**: The inner `except` catches failures during rollback-after-failed-commit. This is a last-resort cleanup. Logging helps identify when the session is truly broken.

**Before**:

```python
    def end_read_transaction(self):
        """
        End a read-only transaction by committing (releases locks).

        Call this after read-only operations to prevent "idle in transaction"
        connections. In SQLAlchemy, even SELECT queries start a transaction
        that must be ended.
        """
        try:
            self._db.commit()
        except Exception:
            # If commit fails on a read-only transaction, rollback
            try:
                self._db.rollback()
            except Exception:
                pass
```

**After**:

```python
    def end_read_transaction(self):
        """
        End a read-only transaction by committing (releases locks).

        Call this after read-only operations to prevent "idle in transaction"
        connections. In SQLAlchemy, even SELECT queries start a transaction
        that must be ended.
        """
        try:
            self._db.commit()
        except Exception:
            # If commit fails on a read-only transaction, rollback
            try:
                self._db.rollback()
            except Exception as e:
                # Suppressed: rollback after failed read-commit is best-effort.
                # The connection may already be closed or invalidated.
                logger.debug(f"Suppressed error during read-transaction rollback: {e}")
```

#### Change 1c: `close()` StopIteration except (lines 81-82)

**Rationale**: The `except StopIteration: pass` on line 81-82 is correct and expected -- `next()` on an exhausted generator raises `StopIteration`. However, the outer `except Exception` on lines 83-84 already logs via `logger.warning`. The inner `except StopIteration` does not need a log because it is the **expected** path (the generator is already exhausted). Add a comment to clarify this.

**Before**:

```python
    def close(self):
        """
        Close the database session and return connection to pool.

        Call this when you're done with the repository to prevent
        connection pool exhaustion.
        """
        try:
            # Exhaust the generator to trigger the finally block
            # which closes the session
            try:
                next(self._db_generator)
            except StopIteration:
                pass
        except Exception as e:
            logger.warning(f"Error closing database session: {e}")
        finally:
            # Also explicitly close just in case
            try:
                self._db.close()
            except Exception:
                pass
```

**After**:

```python
    def close(self):
        """
        Close the database session and return connection to pool.

        Call this when you're done with the repository to prevent
        connection pool exhaustion.
        """
        try:
            # Exhaust the generator to trigger the finally block
            # which closes the session
            try:
                next(self._db_generator)
            except StopIteration:
                pass  # Expected: generator already exhausted from __init__
        except Exception as e:
            logger.warning(f"Error closing database session: {e}")
        finally:
            # Also explicitly close just in case
            try:
                self._db.close()
            except Exception as e:
                # Suppressed: session.close() during cleanup is best-effort.
                # The session may already be closed or the pool invalidated.
                logger.debug(f"Suppressed error during session close: {e}")
```

#### Change 1d: `__del__` method (lines 92-98)

**Rationale**: The `__del__` method runs during garbage collection. At this point, the Python runtime may be shutting down, and logging infrastructure may not be available. Adding a `logger.debug()` call here could itself raise an error during interpreter shutdown. The suppression is correct. Add a comment explaining why.

**Before**:

```python
    def __del__(self):
        """Cleanup when repository is garbage collected."""
        try:
            self.close()
        except Exception:
            # Suppress errors during garbage collection
            pass
```

**After**:

```python
    def __del__(self):
        """Cleanup when repository is garbage collected."""
        try:
            self.close()
        except Exception:
            # Suppressed intentionally: during garbage collection / interpreter shutdown,
            # logging infrastructure may already be torn down. Attempting to log here
            # could itself raise errors. The close() method already has its own logging.
            pass
```

---

### Step 2: Update `src/services/core/telegram_settings.py`

One location deletes a user's message as a "nice to have" cleanup.

#### Change 2a: Lines 223-226 in `handle_settings_edit_message`

**Rationale**: This deletes the user's input message to keep the chat clean during the settings edit flow. If deletion fails (e.g., the bot lacks `delete_messages` permission in a group chat, or the message was already deleted), the settings edit should still proceed. Catching the broad `Exception` is acceptable here since `telegram.error.TelegramError` is the expected failure mode, but there could also be network errors. We log at `DEBUG` because this is a cosmetic operation.

**Before**:

```python
        # Delete user's message to keep chat clean
        try:
            await update.message.delete()
        except Exception:
            pass
```

**After**:

```python
        # Delete user's message to keep chat clean (best-effort)
        try:
            await update.message.delete()
        except Exception as e:
            logger.debug(f"Could not delete user settings input message: {e}")
```

---

### Step 3: Update `src/services/core/telegram_accounts.py`

Multiple locations delete messages as "nice to have" cleanup during the add-account conversation flow.

#### Change 3a: Lines 312-315 in `handle_add_account_message` (verifying message deletion in success path)

**Before**:

```python
                # Delete verifying message
                try:
                    await verifying_msg.delete()
                except Exception:
                    pass
```

**After**:

```python
                # Delete verifying message (best-effort)
                try:
                    await verifying_msg.delete()
                except Exception as e:
                    logger.debug(f"Could not delete verifying message: {e}")
```

#### Change 3b: Lines 322-325 in `handle_add_account_message` (conversation message cleanup in success path)

**Before**:

```python
                for msg_id in messages_to_delete:
                    try:
                        await context.bot.delete_message(
                            chat_id=chat_id, message_id=msg_id
                        )
                    except Exception:
                        pass  # Message may already be deleted
```

**After**:

```python
                for msg_id in messages_to_delete:
                    try:
                        await context.bot.delete_message(
                            chat_id=chat_id, message_id=msg_id
                        )
                    except Exception as e:
                        logger.debug(f"Could not delete conversation message {msg_id}: {e}")
```

#### Change 3c: Lines 422-425 in `handle_add_account_message` (verifying message deletion in error path)

**Before**:

```python
                # Delete verifying message if it exists
                try:
                    await verifying_msg.delete()
                except Exception:
                    pass
```

**After**:

```python
                # Delete verifying message if it exists (best-effort)
                try:
                    await verifying_msg.delete()
                except Exception as e:
                    logger.debug(f"Could not delete verifying message on error: {e}")
```

#### Change 3d: Lines 431-435 in `handle_add_account_message` (conversation message cleanup in error path)

**Before**:

```python
                for msg_id in messages_to_delete:
                    try:
                        await context.bot.delete_message(
                            chat_id=chat_id, message_id=msg_id
                        )
                    except Exception:
                        pass
```

**After**:

```python
                for msg_id in messages_to_delete:
                    try:
                        await context.bot.delete_message(
                            chat_id=chat_id, message_id=msg_id
                        )
                    except Exception as e:
                        logger.debug(f"Could not delete conversation message {msg_id} during error cleanup: {e}")
```

#### Change 3e: Lines 487-490 in `handle_add_account_cancel` (conversation message cleanup on cancel)

**Before**:

```python
        for msg_id in messages_to_delete:
            if msg_id != current_msg_id:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                except Exception:
                    pass
```

**After**:

```python
        for msg_id in messages_to_delete:
            if msg_id != current_msg_id:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                except Exception as e:
                    logger.debug(f"Could not delete conversation message {msg_id} during cancel: {e}")
```

---

## Verification Checklist

Run these commands after making all changes:

```bash
# 1. Activate virtual environment
source venv/bin/activate

# 2. Lint check (should pass with zero errors)
ruff check src/repositories/base_repository.py src/services/core/telegram_settings.py src/services/core/telegram_accounts.py

# 3. Format check (should pass -- some long logger.debug lines may need wrapping)
ruff format --check src/repositories/base_repository.py src/services/core/telegram_settings.py src/services/core/telegram_accounts.py

# 4. If ruff format reports issues, auto-fix:
ruff format src/repositories/base_repository.py src/services/core/telegram_settings.py src/services/core/telegram_accounts.py

# 5. Run full test suite (all tests should still pass)
pytest

# 6. Run repository-specific tests
pytest tests/src/repositories/

# 7. Grep to verify no bare 'except Exception: pass' remains in modified files
# (This should return zero results for the modified files)
grep -n "except Exception:" src/repositories/base_repository.py src/services/core/telegram_settings.py src/services/core/telegram_accounts.py | grep "pass$"
```

The grep in step 7 should return only the `__del__` method in `base_repository.py` (which we intentionally left as `pass` with a comment). All other `except Exception` blocks should now have `logger.debug()` calls.

---

## What NOT To Do

1. **Do NOT change `except Exception` to a narrower exception type.** For the Telegram message deletion cases, you might think `except telegram.error.TelegramError` is better. It is not, for two reasons: (a) network errors (`httpx.RequestError`, `asyncio.TimeoutError`) would then be uncaught and crash the cleanup, and (b) we genuinely want all errors suppressed here -- these are cosmetic operations. The improvement is adding logging, not narrowing the catch.

2. **Do NOT change the log level to `WARNING` or higher.** These are all best-effort cleanup operations. Failing to delete a Telegram message is not a warning-level event -- it happens routinely when the bot lacks permissions in group chats or when messages are already deleted. `DEBUG` is the correct level. Using `WARNING` would create noise in production logs.

3. **Do NOT add `logger.debug()` to the `__del__` method.** During Python interpreter shutdown, the logging module may already be torn down. A `logger.debug()` call in `__del__` can itself raise `AttributeError` or `ImportError`, which would mask the original error. The comment explaining why `pass` is intentional is sufficient.

4. **Do NOT remove any of the `try/except` blocks entirely.** Every one of these blocks exists for a reason -- to prevent cleanup failures from crashing the application or propagating to the user. The fix is adding visibility (logging), not removing error handling.

5. **Do NOT add `exc_info=True` to the `logger.debug()` calls.** These are expected, routine failures. Including full stack traces for "could not delete message" would bloat debug logs without adding value. The exception message string (`{e}`) is sufficient.
