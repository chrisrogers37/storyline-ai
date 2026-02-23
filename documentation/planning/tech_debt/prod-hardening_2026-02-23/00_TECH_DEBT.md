# Production Hardening — Tech Debt Remediation

**Status:** 🔧 IN PROGRESS (3/4 phases complete)
**Created:** 2026-02-23
**Session:** prod-hardening

## Summary

Tech debt scan of the Storyline AI codebase focused on production reliability, observability, and maintainability. Findings grouped into 4 remediation phases ordered by impact and effort.

## Inventory

### High Severity

| # | Finding | Location | Impact |
|---|---------|----------|--------|
| H1 | Debug `print()` in production services | `cloud_storage.py:29`, `instagram_api.py:41` | Leaks URLs/IDs to unstructured stdout |
| H2 | 7 silent `except Exception:` in status checks | `telegram_commands.py:258-378` | Zero observability when checks fail |
| H3 | Inconsistent resource management | Multiple handler files | Connection pool exhaustion risk |

### Medium Severity

| # | Finding | Location | Impact |
|---|---------|----------|--------|
| M1 | WebApp button builder duplicated 3x | `telegram_commands.py:70-82,167-177`, `telegram_settings.py:128-138` | Bug surface if logic changes |
| M2 | `onboarding.py` is 937 lines (20 endpoints + 10 models) | `src/api/routes/onboarding.py` | Hard to navigate, review, test |
| M3 | 5 test files exceed 800 lines | `tests/src/api/`, `tests/src/services/` | Maintenance burden, slow iteration |
| M4 | Integration test coverage gap | `tests/integration/` (1 file) | Session recovery, lock TTL untested |

### Low Severity

| # | Finding | Location | Impact |
|---|---------|----------|--------|
| L1 | No `pyproject.toml` (uses `requirements.txt` + `setup.py`) | Project root | Modern tooling harder to adopt |
| L2 | `MEDIA_SOURCE_ROOT` in `.env` instead of DB | `settings.py:75` | Not per-tenant |
| L3 | 14 outdated dependencies (minor/patch) | `requirements.txt` | Drift risk |

## Remediation Phases

| Phase | Title | Addresses | Effort | Risk | Dependencies |
|-------|-------|-----------|--------|------|-------------|
| 01 | Observability & logging fixes | H1, H2 | Low | Low | None | ✅ PR #78 |
| 02 | Extract WebApp button builder | M1 | Low | Low | None | ✅ PR #79 |
| 03 | Consistent resource management | H3 | Medium | Low | None | ✅ PR #80 |
| 04 | Split onboarding routes | M2 | Medium | Medium | None | 📋 PENDING |

Phases 01-03 are independent and can run in parallel. Phase 04 is independent but higher effort.

**Out of scope for this session** (tracked but not planned):
- M3 (test file splitting) — mechanical, low risk, do when touching those files
- M4 (integration tests) — requires test infrastructure decisions
- L1-L3 — nice-to-have, do opportunistically

## Verification

All phases must pass:
```bash
ruff check src/ tests/ && ruff format --check src/ tests/ && pytest
```
