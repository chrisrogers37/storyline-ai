# Tech Debt Inventory — Maintainability Cleanup

**Date**: 2026-02-25
**Scope**: Full codebase scan of Storyline AI
**Session**: `maintainability-cleanup_2026-02-25`

---

## Executive Summary

The codebase is in strong health overall — zero TODO/FIXME comments, 95%+ test coverage, all dependencies current, and clean architecture. The remaining tech debt is concentrated in **file size / complexity** and **repetitive patterns** that reduce maintainability.

6 remediation phases identified, each mapping to exactly 1 PR.

---

## Inventory

### HIGH Priority

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| H1 | `posting.py` — 645 lines, 7 nesting levels, ~200 lines dead code, BaseService violation | `src/services/core/posting.py` | Maintainability, correctness |
| H2 | `telegram_service.py` — 795 lines, 6 responsibilities, 30+ methods | `src/services/core/telegram_service.py` | Maintainability |
| H3 | API error handling duplication — 9 identical ValueError→HTTPException patterns | `src/api/routes/onboarding/{settings,setup}.py`, `src/api/routes/oauth.py` | DRY violation |

### MEDIUM Priority

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| M1 | Repository tenant filter boilerplate — 33 repeated `_apply_tenant_filter()` calls | 6 repository files | DRY violation |
| M2 | `telegram_accounts.py` (720 lines), `instagram_backfill.py` (698 lines), `instagram_api.py` (686 lines) | `src/services/core/`, `src/services/integrations/` | Maintainability |

### LOW Priority (Quick Wins)

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| L1 | `setup.py` missing 12 runtime dependencies | `setup.py` | Install reliability |
| L2 | Dead `process_next_immediate()` method | `src/services/core/posting.py:198-229` | Dead code |
| L3 | Stale `.claude/worktrees/` directory | `.claude/worktrees/` | Repo cleanliness |

---

## Severity Scoring

| Phase | Blast Radius | Complexity | Risk | Overall |
|-------|-------------|-----------|------|---------|
| 01 Quick Wins | Low (config + dead code) | Low | Low | LOW |
| 02 API Error Handling | Low (3 route files) | Low | Low | LOW |
| 03 Repository Query Builder | Medium (6 repos) | Low | Low | MEDIUM |
| 04 Posting Complexity | Medium (core service) | Medium | Low | MEDIUM |
| 05 Telegram Service Split | High (core + 5 handlers) | Medium | Low | HIGH |
| 06 Remaining Large Files | High (3 services) | Medium | Low | HIGH |

---

## Dependency Matrix

```
Phase 01 (Quick Wins)
  └── Phase 04 (Posting Complexity) — depends on dead code removal from Phase 01
       └── (independent after Phase 01)

Phase 02 (API Error Handling) — independent
Phase 03 (Repository Query Builder) — independent
Phase 05 (Telegram Service Split) — independent
Phase 06 (Remaining Large File Splits) — independent
```

**Recommended execution order**: 01 → 02 → 03 → 04 → 05 → 06

Phases 02, 03, 05, and 06 are independent of each other and can be parallelized after Phase 01.

---

## Remediation Phases

| Phase | PR Title | Effort | Risk | Files | Depends On |
|-------|----------|--------|------|-------|-----------|
| [01](01_quick-wins.md) | Sync setup.py deps, remove dead posting code, prune stale worktrees | Low | Low | 7 | None |
| [02](02_api-error-handling.md) | Extract service_error_handler to eliminate duplicated ValueError→HTTPException patterns | Low | Low | 4 | None |
| [03](03_repository-query-builder.md) | Add `_tenant_query()` helper to BaseRepository and refactor 29 methods | Low | Low | 7 | None |
| [04](04_posting-complexity.md) | Flatten nesting and extract helpers in PostingService | Low | Low | 3 | Phase 01 |
| [05](05_telegram-service-split.md) | Extract notification sending and caption building into TelegramNotificationService | Medium | Low | 5 | None |
| [06](06_remaining-large-file-splits.md) | Extract wizard, downloader, and credential manager from large files | Medium | Low | 9 | None |

---

## Clean Areas (No Action Needed)

- **TODO/FIXME comments**: Zero found across entire codebase
- **Test coverage**: 95%+ with comprehensive mocking patterns
- **Dependencies**: All up-to-date per `pip list --outdated`
- **Architecture**: Clean 3-layer separation (CLI/API → Services → Repositories)
- **Dead code**: Minimal outside of `posting.py`
