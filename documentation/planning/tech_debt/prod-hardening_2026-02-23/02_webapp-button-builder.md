# Phase 02: Extract Shared WebApp Button Builder

**Status:** 🔧 IN PROGRESS
**Started:** 2026-02-23
**Estimated effort:** 30 minutes
**Risk:** Low — pure refactor, no behavior change

## Problem

The private-vs-group WebApp button logic is duplicated in 3 places:
- `telegram_commands.py` `handle_start` (lines 70-82)
- `telegram_commands.py` `handle_status` (lines 167-177)
- `telegram_settings.py` `handle_settings` (lines 128-138)

Each copy has the same pattern:
1. Check if chat is private
2. If private, use `WebAppInfo` button
3. If group, generate signed URL token and use regular URL button

## Solution

Extract a shared `build_webapp_button()` utility in `telegram_utils.py` (Pattern 7) and replace all 3 call sites.

## Files Changed

- `src/services/core/telegram_utils.py` — Add `build_webapp_button()` function
- `src/services/core/telegram_commands.py` — Use shared utility, remove unused imports
- `src/services/core/telegram_settings.py` — Use shared utility, remove unused imports
- `tests/src/services/test_telegram_utils.py` — Add 3 test cases
