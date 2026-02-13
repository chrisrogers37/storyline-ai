# Tech Debt: Post-Cloud-Media Quality Review

**Status:** 📋 PENDING
**Created:** 2026-02-12
**Session:** `quality-review-feb-2026`
**Trigger:** Codebase scan after completing Cloud Media Enhancements (5 phases, PRs #41-#45)

## Executive Summary

Scan of the 32,680-line codebase revealed **12 findings** across 3 severity levels. The codebase is structurally sound (no dead code, no unused imports, clean architecture), but the rapid 5-phase feature addition introduced complexity hotspots and test coverage gaps that should be addressed before the next feature cycle.

**Key numbers:**
- 708 tests passing, 13 skipped
- 0% test coverage on models (12 files) and config (3 files)
- 17 CLI tests all skipped (TODO placeholders)
- 1 function at 315 lines with 6+ nesting levels
- 4 functions with 7-8 parameters each
- ~150 lines of duplicated code across Telegram handlers

## Findings Inventory

### HIGH Priority

| ID | Finding | Location | Severity |
|----|---------|----------|----------|
| H1 | Monster method: 315 lines, 6+ nesting, duplicated cleanup 3x | `telegram_accounts.py:handle_add_account_message()` L167-482 | High |
| H2 | Parameter bloat: 4 functions with 7-8 params each | `instagram_backfill.py` | High |
| H3 | 0% test coverage on models (12) and config (3) | `src/models/`, `src/config/` | High |
| H4 | 17 CLI tests all skipped with TODO placeholders | `tests/cli/test_user_commands.py`, `test_queue_commands.py`, `test_media_commands.py` | High |

### MEDIUM Priority

| ID | Finding | Location | Severity |
|----|---------|----------|----------|
| M1 | Long method: 152+ lines, 8 params | `telegram_autopost.py:_do_autopost()` L97 | Medium |
| M2 | Long method: 115 lines, 5 nesting levels | `telegram_commands.py:handle_status()` L54-168 | Medium |
| M3 | ~150 duplicated lines: keyboard building (4x), cleanup loops (3x), API error extraction (3x) | Telegram handler files | Medium |
| M4 | 3 of 5 exception modules untested | `base.py`, `google_drive.py`, `instagram.py` | Medium |
| M5 | 3 new CLI command modules with 0 tests | `backfill.py`, `google_drive.py`, `sync.py` | Medium |

### LOW Priority

| ID | Finding | Location | Severity |
|----|---------|----------|----------|
| L1 | Missing `__init__.py` exports for 2 repositories | `src/repositories/__init__.py` | Low |
| L2 | Stale comment (says "unused" but is used by tests) | `service_run_repository.py` L87 | Low |
| L3 | 9 packages with minor version bumps | `pip list --outdated` | Low |

## Phased Remediation Plan

### Dependency Matrix

```
Phase 01  ──┐
             ├──► Phase 04
Phase 03  ──┘

Phase 02  (independent)
Phase 05  (independent)
Phase 06  (independent)
Phase 07  (independent, naturally last)
```

### Phase Summary

| Phase | Title | Findings | Risk | Effort | PR |
|-------|-------|----------|------|--------|-----|
| 01 | Refactor Account Add State Machine | H1 | Medium | 2-3h | #46 |
| 02 | BackfillContext Dataclass | H2 | Low | 1-2h | #47 |
| 03 | Extract Long Method Sub-Methods | M1, M2 | Medium | 2-3h | #48 |
| 04 | Extract Shared Telegram Utilities | M3 | Low | 1-2h | #49 |
| 05 | Convert Skipped CLI Tests | H4 | Low | 2-3h | - |
| 06 | Model, Config, and Exception Tests | H3, M4 | Low | 3-4h | - |
| 07 | CLI Command Tests + Cleanup | M5, L1-L3 | Low | 2-3h | - |

### Parallel Execution Guide

**Can run in parallel** (touch disjoint files):
- Phase 01, 02, 05, 06 are fully independent
- Phase 03 is independent of 01 and 02

**Must be sequential:**
- Phase 04 depends on Phase 01 + Phase 03 (extracts patterns they create)
- Phase 07 is naturally last (cleanup)

### Recommended Execution Order

1. **Phase 01** — Refactor the worst complexity hotspot
2. **Phase 02** — Quick win, independent
3. **Phase 03** — Extract long methods (unblocks Phase 04)
4. **Phase 04** — Deduplicate shared patterns (depends on 01 + 03)
5. **Phase 05** — Convert skipped CLI tests (independent)
6. **Phase 06** — Add model/config/exception tests (independent)
7. **Phase 07** — CLI command tests + final cleanup

## What's NOT in Scope

- **Dead code removal** — Already clean from prior tech debt session (PRs #28-#40)
- **Architecture changes** — The 3-layer architecture is solid
- **Dependency upgrades** — Only minor bumps, no security issues
- **Performance optimization** — No performance issues identified
- **New features** — This is strictly quality improvement
