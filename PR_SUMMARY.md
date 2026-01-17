# PR: Fix Database Connection Pool Exhaustion

## Summary

Fixes the `QueuePool limit of size 5 overflow 10 reached` error that occurred when using Auto Post and other Telegram bot commands. The root cause was database sessions being created but never properly released back to the connection pool.

## Changes

### New Files
- `src/repositories/base_repository.py` - Base class for all repositories with proper session lifecycle management

### Modified Files

**Connection Pool Configuration**
- `src/config/database.py` - Increased pool size (5→10), overflow (10→20), added connection recycling

**Repository Layer** (all updated to extend BaseRepository)
- `src/repositories/__init__.py` - Export BaseRepository and TokenRepository
- `src/repositories/media_repository.py`
- `src/repositories/queue_repository.py`
- `src/repositories/history_repository.py`
- `src/repositories/user_repository.py`
- `src/repositories/lock_repository.py`
- `src/repositories/service_run_repository.py`
- `src/repositories/interaction_repository.py`
- `src/repositories/category_mix_repository.py`
- `src/repositories/token_repository.py`

**Service Layer**
- `src/services/base_service.py` - Added `close()` method, `__del__` cleanup, context manager support
- `src/services/core/telegram_service.py` - Updated handlers to use context managers for proper cleanup

**Documentation**
- `documentation/planning/phases/00_MASTER_ROADMAP.md` - Added backlog item for future race condition handling

## Technical Details

### Root Cause
Repositories were creating database sessions in `__init__` via `next(get_db())` but never closing them. Each Telegram callback created new service instances → new repositories → new connections that leaked.

### Solution

1. **BaseRepository** - All repositories now extend this base class which:
   - Manages session lifecycle
   - Provides `close()` method to release connections
   - Implements `__del__` for garbage collection cleanup
   - Supports context manager usage (`with repo:`)

2. **BaseService** - Updated to:
   - Auto-close all repository instances on cleanup
   - Support context manager usage (`with service:`)
   - Clean up on garbage collection

3. **Connection Pool** - Increased capacity and added safeguards:
   ```python
   pool_size=10,        # was 5
   max_overflow=20,     # was 10
   pool_recycle=300,    # new - recycle stale connections
   pool_timeout=30,     # new - wait timeout
   ```

4. **Handler Updates** - Key Telegram handlers now use context managers:
   ```python
   with PostingService() as service:
       result = await service.force_post_next(...)
   ```

## Testing

- All imports verified working
- Context managers properly return connections to pool
- Auto Post tested successfully after changes

## Database Changes

**None** - All changes are Python-side connection management. No migrations required.

## Deployment Notes

1. Pull latest code to Raspberry Pi
2. Restart the bot service
3. No database migrations needed
