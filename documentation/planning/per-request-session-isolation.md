# Per-Request Session Isolation + Concurrent Updates

> **Status:** Planning only. Not yet scheduled for implementation.
> **Created:** 2026-04-09
> **Depends on:** Background auto-post tasks (implemented in same PR)

## Problem

The Telegram bot processes all callbacks sequentially (`concurrent_updates=False` in python-telegram-bot). While Enhancement #2 (background auto-post tasks) solves the main UX issue by unblocking the pipeline during auto-posts, enabling true concurrent callback processing requires per-request database session isolation.

### Current Architecture Issues

1. **Shared sessions**: Each repository holds ONE SQLAlchemy session for its entire lifetime. All concurrent handlers would share these sessions.
2. **`_shared_session()` pattern** (`telegram_callbacks.py:121-161`): Monkey-patches `commit->flush` and swaps sessions across repos for atomicity. Would corrupt under concurrent access.
3. **`context.user_data` races**: Settings edit flows store conversation state that could race between concurrent callbacks for the same user.

## Design: RequestContext Pattern

A lightweight per-request container holding its own repository instances sharing a single fresh session:

```python
# src/services/core/request_context.py (new file)

from contextlib import contextmanager
from src.config.database import SessionLocal

class RequestContext:
    """Per-request database context for concurrent-safe callback handling.

    Each callback invocation creates its own RequestContext with an
    isolated SQLAlchemy session. All repository operations within that
    callback use this session, preventing cross-request contamination.
    """

    def __init__(self):
        self._session = SessionLocal()
        self.queue_repo = QueueRepository(session=self._session)
        self.history_repo = HistoryRepository(session=self._session)
        self.media_repo = MediaRepository(session=self._session)
        self.user_repo = UserRepository(session=self._session)
        self.lock_repo = MediaPostingLockRepository(session=self._session)

    def commit(self):
        self._session.commit()

    def rollback(self):
        self._session.rollback()

    def close(self):
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        self.close()
        return False


@contextmanager
def atomic_scope(ctx: RequestContext):
    """Replace _shared_session() — atomic multi-repo operations.

    Uses the context's single session (already shared across repos)
    and wraps in a savepoint for atomicity without monkey-patching.
    """
    savepoint = ctx._session.begin_nested()
    try:
        yield ctx
        savepoint.commit()
    except Exception:
        savepoint.rollback()
        raise
```

## Phased Implementation

### Phase 1: Create RequestContext (Low Risk)

**Scope:** Purely additive — create `request_context.py` with `RequestContext` and `atomic_scope()`. No behavior changes.

**Changes:**
- New file: `src/services/core/request_context.py`
- Modify `src/repositories/base_repository.py`: Add `__init__` variant accepting an external session
- Tests for RequestContext lifecycle

**Estimated effort:** 1 day

### Phase 2: Replace `_shared_session()` (Medium Risk)

**Scope:** Replace the monkey-patching `_shared_session()` in `telegram_callbacks.py` with `atomic_scope()`. Same external behavior but uses fresh sessions.

**Changes:**
- Modify `src/services/core/telegram_callbacks.py`: Replace `_shared_session()` calls with `atomic_scope()`
- The retry-once pattern in `_do_complete_queue_action` (lines 271-308) must create a NEW `RequestContext` on SSL errors
- Update tests in `tests/src/services/test_telegram_callbacks.py`

**Risk area:** The retry logic is the highest-risk change. A broken session can't be reused — must create fresh context.

**Estimated effort:** 1 day

### Phase 3: Per-Request Context in Handlers (Medium-High Risk)

**Scope:** `_handle_callback()` creates a `RequestContext` per invocation. Handler method signatures gain a `ctx` parameter. References change from `self.service.queue_repo` to `ctx.queue_repo`.

**Changes:**
- `src/services/core/telegram_service.py`: `_handle_callback()` wraps dispatch in `with RequestContext() as ctx:`
- `src/services/core/telegram_callbacks.py`: All handler methods accept `ctx` parameter
- `src/services/core/telegram_autopost.py`: `handle_autopost()` accepts `ctx` parameter
- `src/services/core/telegram_accounts.py`: Handler methods accept `ctx` parameter
- `src/services/core/telegram_settings.py`: Handler methods accept `ctx` parameter
- Add per-user `asyncio.Lock` for `context.user_data` mutations in settings flows
- Extensive test updates

**Feature flag:** `TELEGRAM_PER_REQUEST_SESSIONS=true/false` for instant rollback.

**Estimated effort:** 3-5 days

### Phase 4: Enable Concurrent Updates (Low Risk)

**Scope:** One line change + one new setting.

**Changes:**
- `src/services/core/telegram_service.py:130`:
  ```python
  self.application = (
      Application.builder()
      .token(self.bot_token)
      .concurrent_updates(settings.TELEGRAM_MAX_CONCURRENT_UPDATES)
      .build()
  )
  ```
- `src/config/settings.py`: Add `TELEGRAM_MAX_CONCURRENT_UPDATES: int = 8`
- Rollback: Set env var to `1` (equivalent to `False`)

**Estimated effort:** 1 hour

## Connection Pool Considerations

With `concurrent_updates=8`:
- Peak concurrent connections: 8 (handlers) + 6 (background loops) = 14
- Current pool: `pool_size=10`, `max_overflow=20`, max=30
- **No pool size increase needed** for current concurrency level
- Monitor with `storydump-cli check-health` after enabling

## Key Design Decisions

1. **RequestContext vs per-handler service instances**: RequestContext is lighter — shares one session across repos rather than creating N sessions
2. **Savepoints vs monkey-patching**: `atomic_scope()` uses SQL savepoints instead of `_shared_session()`'s commit-to-flush swap. Cleaner, standard SQL, concurrent-safe
3. **BaseRepository session injection**: Add `session` param to `__init__` — if provided, use it; if not, create own (backward compatible)
4. **Feature flag for Phase 3**: The handler signature change is the riskiest refactor. A flag allows instant rollback without redeploy

## Existing Pattern to Follow

The FastAPI API layer already uses per-request session scoping:
- `src/api/routes/onboarding/settings.py`: Services created fresh per request with context managers
- `src/api/routes/oauth.py`: Same pattern

## Critical Files

| File | Phase | Change Type |
|------|-------|-------------|
| `src/services/core/request_context.py` | 1 | New |
| `src/repositories/base_repository.py` | 1 | Session injection |
| `src/services/core/telegram_callbacks.py` | 2, 3 | Replace `_shared_session`, add `ctx` param |
| `src/services/core/telegram_service.py` | 3, 4 | Handler dispatch, concurrent_updates |
| `src/services/core/telegram_autopost.py` | 3 | Add `ctx` param |
| `src/services/core/telegram_accounts.py` | 3 | Add `ctx` param |
| `src/services/core/telegram_settings.py` | 3 | Add `ctx` param + user locks |
| `src/config/settings.py` | 4 | New setting |
