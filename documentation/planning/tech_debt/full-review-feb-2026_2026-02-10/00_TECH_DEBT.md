# Tech Debt Inventory — Full Review (February 2026)

**Date**: 2026-02-10
**Scope**: Full codebase scan of `storyline-ai`
**Branch**: `docs/documentation-review-2026-02-10`

---

## Executive Summary

This audit identified **12 categories of technical debt** across the Storyline AI codebase. The most impactful issues are:

1. **136 skipped tests** — effectively zero automated safety net for repositories and critical services
2. **2 architecture layer violations** — services bypassing the repository pattern
3. **150+ instances of code duplication** — primarily in Telegram handlers and repositories
4. **26 outdated dependencies** — including major version gaps in core libraries

The remediation is organized into **12 phases**, each representing exactly one PR. Phases are designed to be as independent as possible to allow parallel execution by multiple engineers.

---

## Inventory

### 1. Architecture Layer Violations (CRITICAL)

| ID | File | Lines | Issue |
|----|------|-------|-------|
| ARCH-1 | `src/services/core/health_check.py` | 4, 9, 72-73 | Direct `db.execute(text("SELECT 1"))` in service — imports `sqlalchemy.text` and `get_db`, bypassing repository layer |
| ARCH-2 | `src/services/core/scheduler.py` | 416-458 | `_select_media_from_pool()` accesses `media_repo.db` directly, imports 3 models, builds multi-table SQLAlchemy subqueries |

**Impact**: Breaks the strict separation of concerns, makes services harder to test in isolation, creates hidden coupling between service and data layers.

---

### 2. Complexity Hotspots (HIGH)

| ID | File | Lines | Issue | Metric |
|----|------|-------|-------|--------|
| CPLX-1 | `src/services/core/telegram_service.py` | 468-559 | `_handle_callback()` — if-elif chain dispatching 20+ actions | Nesting depth 8, 90 lines |
| CPLX-2 | `src/repositories/history_repository.py` | 78-97 | `create()` method | 18 parameters |
| CPLX-3 | `src/services/core/scheduler.py` | 28-117 | `create_schedule()` | 90 lines |
| CPLX-4 | `src/services/core/scheduler.py` | 120-221 | `extend_schedule()` | 102 lines |
| CPLX-5 | `src/services/core/instagram_account_service.py` | 146-245 | `add_account()` | 100 lines, 9 params |
| CPLX-6 | `src/services/core/instagram_account_service.py` | 292-383 | `update_account_token()` | 92 lines, 8 params |
| CPLX-7 | `src/services/integrations/cloud_storage.py` | 58-157 | `upload_media()` | 100 lines |
| CPLX-8 | `src/services/integrations/cloud_storage.py` | 290-353 | `get_story_optimized_url()` | 64 lines |
| CPLX-9 | `src/services/core/health_check.py` | 89-164 | `_check_instagram_api()` | 75 lines |
| CPLX-10 | `src/services/core/media_ingestion.py` | 24-98 | `scan_directory()` | 75 lines |
| CPLX-11 | `src/services/core/telegram_settings.py` | 26-98 | `build_settings_message_and_keyboard()` | 73 lines |
| CPLX-12 | `src/utils/image_processing.py` | 35-106 | `validate_image()` | 72 lines |
| CPLX-13 | `src/services/core/settings_service.py` | 103-165 | `update_setting()` | 63 lines |
| CPLX-14 | `src/services/base_service.py` | 80-160 | `track_execution()` | 81 lines, 6 params |

**Additional high-parameter functions** (17 total with 6+ params):
- `src/repositories/media_repository.py:65` — `create()` (14 params)
- `src/repositories/token_repository.py:107` — `create_or_update()` (9 params)
- `src/repositories/service_run_repository.py:20` — `create_run()` (7 params)
- `src/repositories/interaction_repository.py:17` — `create()` (7 params)
- `src/repositories/user_repository.py:37` — `create()` (7 params)
- `src/repositories/media_repository.py:102` — `update_metadata()` (7 params)
- `src/services/core/posting.py:489` — `handle_completion()` (7 params)
- `src/services/core/interaction_service.py:31,66,101` — Multiple methods (6+ params)
- `src/services/core/telegram_service.py:306,369` — Caption builders (6 params)
- `src/repositories/service_run_repository.py:60` — `fail_run()` (6 params)
- `src/repositories/media_repository.py:140` — `update_cloud_info()` (6 params)

---

### 3. Skipped Tests (HIGH) — 136 Total

All carry the reason: `"TODO: Integration test - needs test_db, convert to unit test or move to integration/"`.

| Test File | Skipped Count |
|-----------|---------------|
| `tests/src/repositories/test_user_repository.py` | 14 |
| `tests/src/repositories/test_interaction_repository.py` | 14 |
| `tests/src/services/test_instagram_api.py` | 12 |
| `tests/src/repositories/test_queue_repository.py` | 12 |
| `tests/src/services/test_base_service.py` | 9 |
| `tests/src/repositories/test_media_repository.py` | 8 |
| `tests/src/repositories/test_lock_repository.py` | 8 |
| `tests/src/repositories/test_service_run_repository.py` | 8 |
| `tests/cli/test_media_commands.py` | 7 |
| `tests/src/repositories/test_history_repository.py` | 6 |
| `tests/src/services/test_media_lock.py` | 6 |
| `tests/src/services/test_scheduler.py` | 6 |
| `tests/cli/test_user_commands.py` | 5 |
| `tests/cli/test_queue_commands.py` | 5 |
| `tests/src/services/test_posting.py` | 5 |
| `tests/src/services/test_telegram_commands.py` | 5 |
| `tests/src/services/test_telegram_callbacks.py` | 1 |
| **TOTAL** | **136** |

---

### 4. Missing Test Coverage (MEDIUM)

Six source files have **no test file at all**:

| Source File | Lines | Risk |
|-------------|-------|------|
| `src/services/core/telegram_autopost.py` | 467 | HIGH — auto-posting is critical path |
| `cli/commands/instagram.py` | 638 | MEDIUM — Instagram CLI untested |
| `src/repositories/base_repository.py` | 108 | MEDIUM — foundation for all repos |
| `src/repositories/chat_settings_repository.py` | unknown | MEDIUM — settings persistence |
| `src/repositories/instagram_account_repository.py` | unknown | MEDIUM — multi-account persistence |
| `src/repositories/token_repository.py` | unknown | MEDIUM — OAuth token handling |

---

### 5. Code Duplication (MEDIUM)

| Pattern | Count | Location |
|---------|-------|----------|
| User/settings lookup + interaction logging | 30+ | All 5 Telegram handler files |
| Queue item not-found guard clause | 15+ | `telegram_callbacks.py`, `telegram_autopost.py`, `telegram_accounts.py` |
| Keyboard building (Posted/Skip/Reject buttons) | 5+ | `telegram_callbacks.py`, `telegram_autopost.py`, `telegram_accounts.py` |
| Repository `db.add() / db.commit() / db.refresh()` boilerplate | 40+ | All repository files |
| Repository update pattern (get → mutate → commit → refresh) | 25+ | All repository files |
| Settings edit state management (init/cleanup/validate) | 18+ | `telegram_settings.py` |
| CLI error handling `try/except → console.print(red)` | 8+ | All CLI command files |
| Verbose caption formatting conditional | 6+ | `telegram_autopost.py`, `telegram_callbacks.py`, `telegram_accounts.py` |

---

### 6. Silent Error Swallowing (MEDIUM)

Bare `except Exception: pass` blocks that mask real errors:

| File | Lines | Context |
|------|-------|---------|
| `src/repositories/base_repository.py` | 32-33 | Session state check — silently ignores rollback failures |
| `src/repositories/base_repository.py` | 66-67 | Read transaction end — silently ignores rollback |
| `src/repositories/base_repository.py` | 82, 90, 98 | Session close and GC — silently ignores cleanup failures |
| `src/services/core/telegram_settings.py` | 225-226 | Message deletion — silently ignores API errors |
| `src/services/core/telegram_accounts.py` | 312-315, 324-325, 435, 490 | Message deletion and UI updates — silently ignores API errors |

---

### 7. Magic Numbers / Duplicated Constants (LOW)

| Value | Used In | Should Be |
|-------|---------|-----------|
| `50` (queue backlog threshold) | `health_check.py:173` | `QUEUE_BACKLOG_THRESHOLD` |
| `24` hours (max pending age) | `health_check.py:183` | `MAX_PENDING_AGE_HOURS` |
| `1-50` (posts_per_day range) | `telegram_settings.py:231`, `settings_service.py:140` | `MIN_POSTS_PER_DAY`, `MAX_POSTS_PER_DAY` |
| `0-23` (posting hours range) | `telegram_settings.py:275,325`, `settings_service.py:144` | `MIN_POSTING_HOUR`, `MAX_POSTING_HOUR` |
| `10` (min Instagram account ID length) | `instagram_api.py:519` | `MIN_ACCOUNT_ID_LENGTH` |
| `10` (locks display limit) | `telegram_commands.py:596` | `MAX_LOCKS_DISPLAY` |
| `[:8]` (ID truncation for display) | `telegram_accounts.py:632-633` | `ID_DISPLAY_LENGTH` |
| `-30, 30` (schedule jitter minutes) | `scheduler.py:265` | `SCHEDULE_JITTER_MINUTES` |
| `48` hours (recent posts window) | `health_check.py:202` | `RECENT_POSTS_WINDOW_HOURS` |

---

### 8. Outdated Dependencies (LOW)

26 outdated packages. Notable gaps:

| Package | Current | Latest | Gap |
|---------|---------|--------|-----|
| `Pillow` | 10.1.0 | 12.1.0 | 2 major versions |
| `httpx` | 0.25.2 | 0.28.1 | 3 minor versions |
| `python-telegram-bot` | 20.7 | 22.6 | 2 major versions |
| `pytest` | 7.4.3 | 9.0.2 | 2 major versions |
| `pydantic` | 2.5.0 | 2.12.5 | 7 minor versions |
| `SQLAlchemy` | 2.0.23 | 2.0.46 | 23 patch versions |
| `psycopg2-binary` | 2.9.9 | 2.9.11 | 2 patch versions |
| `cryptography` | 46.0.3 | 46.0.5 | 2 patch versions |
| `ruff` | 0.14.14 | 0.15.0 | 1 minor version |

---

### 9. Potentially Dead Code (LOW)

~30 repository methods that are not called from anywhere in `src/` or `cli/`:

- `category_mix_repository.py`: `get_categories_without_ratio()`, `get_category_ratio()`, `get_history()`, `get_mix_at_date()`, `has_current_mix()`, `set_mix()`
- `interaction_repository.py`: `count_by_name()`, `count_by_user()`, `get_by_name()`, `get_by_type()`, `get_by_user()`
- `history_repository.py`: `get_by_user_id()`, `get_stats()`
- `service_run_repository.py`: `get_failed_runs()`, `get_recent_runs()`
- `queue_repository.py`: `delete_all_pending()`, `schedule_retry()`
- `token_repository.py`: `delete_all_for_service()`, `delete_token()`, `get_all_for_service()`, `get_expired_tokens()`
- `media_repository.py`: `get_categories()`, `update_metadata()`

**Note**: Some may be used by CLI commands or planned for future features. Requires manual verification before removal.

---

## Severity Scoring

Each item is scored on three dimensions (1-5 scale):

| Dimension | Description |
|-----------|-------------|
| **Blast Radius** | How many files/features does this affect? |
| **Complexity** | How hard is this to fix? |
| **Risk** | What's the probability of a bug caused by this debt? |

| Category | Blast Radius | Complexity | Risk | Score |
|----------|-------------|------------|------|-------|
| Architecture violations | 3 | 2 | 4 | **9** |
| Skipped tests | 5 | 4 | 5 | **14** |
| Missing test coverage | 3 | 3 | 4 | **10** |
| Callback dispatcher complexity | 2 | 2 | 3 | **7** |
| Long functions / many params | 4 | 3 | 3 | **10** |
| Code duplication | 5 | 4 | 3 | **12** |
| Silent error swallowing | 3 | 1 | 4 | **8** |
| Magic numbers | 3 | 1 | 2 | **6** |
| Outdated dependencies | 5 | 3 | 3 | **11** |
| Dead code | 2 | 1 | 1 | **4** |

---

## Prioritized Remediation Order

| Phase | PR Title | Risk | Effort | Depends On | Blocks |
|-------|----------|------|--------|------------|--------|
| 01 | Extract magic numbers into named constants | Low | Small | — | — |
| 02 | Replace silent error swallowing with proper handling | Low | Small | — | — |
| 03 | Fix architecture violation in HealthCheckService | Low | Small | — | 08 |
| 04 | Fix architecture violation in SchedulerService | Medium | Medium | — | 08, 09 |
| 05 | Extract Telegram handler common utilities | Medium | Large | — | 06 |
| 06 | Refactor callback dispatcher to dictionary dispatch | Low | Medium | 05 | — |
| 07 | Decompose long functions and reduce parameter counts | Medium | Large | 03, 04 | — |
| 08 | Convert skipped repository tests to unit tests | Low | Large | 03 | 10 |
| 09 | Convert skipped service tests to unit tests | Low | Large | 04 | 10 |
| 10 | Add missing test files for uncovered modules | Low | Large | 08, 09 | — |
| 11 | Update outdated dependencies | Medium | Medium | — | — |
| 12 | Audit and remove dead code | Low | Small | 08, 09 | — |

### Parallelization Guide

```
Can run in parallel (disjoint files):
  ├── Phase 01 (constants)
  ├── Phase 02 (error handling)
  ├── Phase 03 (health_check.py)
  └── Phase 11 (dependencies)

Sequential chains:
  Phase 03 → Phase 08 → Phase 10
  Phase 04 → Phase 09 → Phase 10
  Phase 05 → Phase 06
  Phase 03 + 04 → Phase 07
  Phase 08 + 09 → Phase 12
```

---

## Dependency Matrix

```
Phase:  01  02  03  04  05  06  07  08  09  10  11  12
  01     -   -   -   -   -   -   -   -   -   -   -   -
  02     -   -   -   -   -   -   -   -   -   -   -   -
  03     -   -   -   -   -   -   -   -   -   -   -   -
  04     -   -   -   -   -   -   -   -   -   -   -   -
  05     -   -   -   -   -   B   -   -   -   -   -   -
  06     -   -   -   -   D   -   -   -   -   -   -   -
  07     -   -   D   D   -   -   -   -   -   -   -   -
  08     -   -   D   -   -   -   -   -   -   B   -   -
  09     -   -   -   D   -   -   -   -   -   B   -   -
  10     -   -   -   -   -   -   -   D   D   -   -   -
  11     -   -   -   -   -   -   -   -   -   -   -   -
  12     -   -   -   -   -   -   -   D   D   -   -   -

Legend: D = depends on (row depends on column)
        B = blocks (row blocks column)
```

---

## Files Index

| Document | Contents |
|----------|----------|
| `00_TECH_DEBT.md` | This file — master inventory |
| `01_extract-constants.md` | Phase 1: Magic numbers → named constants |
| `02_fix-error-swallowing.md` | Phase 2: Replace bare except blocks |
| `03_fix-healthcheck-architecture.md` | Phase 3: Move raw SQL out of HealthCheckService |
| `04_fix-scheduler-architecture.md` | Phase 4: Move query logic out of SchedulerService |
| `05_telegram-handler-utilities.md` | Phase 5: Extract shared Telegram patterns |
| `06_callback-dispatcher-refactor.md` | Phase 6: Dictionary dispatch for callbacks |
| `07_function-decomposition.md` | Phase 7: Break apart long functions |
| `08_repository-test-conversion.md` | Phase 8: Convert skipped repo tests |
| `09_service-test-conversion.md` | Phase 9: Convert skipped service tests |
| `10_missing-test-coverage.md` | Phase 10: Add new test files |
| `11_dependency-updates.md` | Phase 11: Bump outdated packages |
| `12_dead-code-audit.md` | Phase 12: Remove unused code | ✅ COMPLETE |
