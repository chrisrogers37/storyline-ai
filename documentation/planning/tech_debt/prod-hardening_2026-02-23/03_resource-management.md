# Phase 03: Resource Management — Context Manager Conversion

**Status:** 🔧 IN PROGRESS
**Started:** 2026-02-23

## Overview

Convert all `try/finally/close()` patterns to context manager `with` statements
in `telegram_commands.py` and `onboarding.py`.

## Files

- `src/services/core/telegram_commands.py` — 2 patterns
- `src/api/routes/onboarding.py` — ~29 patterns

## Rules

1. `BaseRepository` and `BaseService` already implement `__enter__`/`__exit__`
2. Single resource: `with SomeRepo() as repo:`
3. Multiple resources at same scope: `with RepoA() as a, RepoB() as b:`
4. Nested try/finally inside outer try/finally → flatten with separate `with` blocks
5. No behavioral changes — purely lifecycle management refactor
