# Phase 01: Quick Wins

**PR Title**: Sync setup.py deps, remove dead posting code, prune stale worktrees
**Risk Level**: Low
**Estimated Effort**: Low (30 min)
**Files Modified**: 7
**Dependencies**: None
**Blocks**: Phase 04 (posting complexity)

---

## Context

Three low-risk cleanups that can ship as a single PR:
1. `setup.py` is missing 12 runtime dependencies that are in `requirements.txt`
2. `posting.py` contains ~200 lines of dead code (deprecated + Phase 2 leftovers)
3. `.claude/worktrees/` is an untracked empty directory

---

## Implementation Plan

### 1. Sync setup.py with requirements.txt

**File**: `setup.py`

Read `requirements.txt` and compare against `install_requires` in `setup.py`. Add the 12 missing dependencies:

Missing packages (from research):
- `cryptography`
- `google-api-python-client`
- `google-auth-httplib2`
- `google-auth-oauthlib`
- `Jinja2`
- `pydantic-settings`
- `python-telegram-bot`
- `rclone-python`
- `sqlalchemy`
- `alembic`
- `uvicorn`
- `gunicorn`

**Steps**:
1. Read `requirements.txt` to get exact version specs
2. Read `setup.py` to see current `install_requires`
3. Add missing packages with matching version constraints from requirements.txt
4. Keep alphabetical order in install_requires

### 2. Remove dead code from posting.py

**File**: `src/services/core/posting.py`

Remove these dead methods and their supporting code:

| Method | Lines | Reason |
|--------|-------|--------|
| `process_next_immediate()` | 198-229 | Deprecated wrapper, zero callers |
| `_post_via_instagram()` | 444-552 | Phase 2 leftover, `_route_post()` always routes to Telegram |
| `_cleanup_cloud_media()` | 554-584 | Only called from `_post_via_instagram` |
| `handle_completion()` | 586-644 | Orphaned, zero callers in codebase |

Also remove:
- Lazy imports of `InstagramAPIService` and `CloudStorageService` (only used by dead methods)
- Any comments referencing the removed methods

**Steps**:
1. Read `posting.py` in full
2. Verify zero callers with grep for each method name across the codebase
3. Remove methods bottom-up (handle_completion → _cleanup_cloud_media → _post_via_instagram → process_next_immediate)
4. Remove unused lazy imports
5. File should shrink from ~645 to ~445 lines

### 3. Clean up stale worktrees directory

**File**: `.claude/worktrees/`

Add `.claude/worktrees/` to `.gitignore` if not already present, and remove the untracked directory.

**Steps**:
1. Check if `.claude/worktrees/` is in `.gitignore`
2. If not, add it
3. Verify the directory is empty, then remove it or leave it (gitignore handles it)

---

## Test Plan

```bash
# 1. Verify setup.py is valid
python setup.py check

# 2. Verify no import errors after dead code removal
python -c "from src.services.core.posting import PostingService"

# 3. Run full test suite
pytest

# 4. Verify removed methods have no callers
grep -rn "process_next_immediate\|_post_via_instagram\|_cleanup_cloud_media\|handle_completion" src/ --include="*.py"

# 5. Lint
ruff check src/ tests/ && ruff format --check src/ tests/
```

---

## Verification Checklist

- [ ] `setup.py` install_requires matches all packages in `requirements.txt`
- [ ] `posting.py` reduced by ~200 lines
- [ ] No grep hits for removed method names (except in tests, which should also be removed)
- [ ] `pytest` passes with no failures
- [ ] `ruff check` and `ruff format` pass
- [ ] CHANGELOG.md updated

---

## What NOT To Do

- **Don't remove `_route_post()`** — it's still called by `process_pending_posts()`
- **Don't remove `_post_via_telegram()`** — it's the active posting path
- **Don't pin exact versions in setup.py** — use `>=` constraints matching requirements.txt style
- **Don't remove test files for dead methods yet** — verify tests exist first, remove if they do
- **Don't touch `reschedule_overdue_for_paused_chat()`** — it has a BaseService violation but that's Phase 04
