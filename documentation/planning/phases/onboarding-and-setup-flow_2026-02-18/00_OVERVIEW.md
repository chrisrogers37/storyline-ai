# Onboarding and Setup Flow

**Session Date:** 2026-02-18
**Scope:** End-to-end onboarding UX, `/start` Mini App wizard, `/setup` quick settings, delivery toggle, command cleanup
**Branch Base:** `main`

## User's Vision

> `/start` should be the single entry point that handles ALL setup via the Mini App wizard. After connecting Google Drive, the wizard tells you how many files are there and asks if you want to index. Everything that needs to be configured and saved in the database for app usage should be reachable from `/start`. A later `/setup` call provides in-channel quick toggles and buttons for already-configured settings. There should be a delivery ON/OFF toggle separate from dry_run that smartly reschedules queue items +24hr when paused.

## Phase Summary

| # | Phase | Impact | Effort | Risk | PR |
|---|-------|--------|--------|------|----|
| 01 | [Per-Chat Media Source Columns](01_per_chat_media_source_columns.md) | High | Low | Low | #62 |
| 02 | [Complete Mini App Onboarding Wizard](02_complete_mini_app_wizard.md) | High | Medium | Low | #63 |
| 03 | [Mini App Home Screen for Returning Users](03_mini_app_home_screen.md) | High | Medium | Low | 🔧 IN PROGRESS |
| 04 | [`/setup` Command + Smart Delivery Toggle](04_setup_command_delivery_toggle.md) | High | Medium | Medium | |
| 05 | [`/status` Setup Reporting + `/connect_drive` Cleanup](05_status_reporting_connect_drive_cleanup.md) | Medium | Low | Low | |
| 06 | [Command Audit, Cleanup & Consolidation](06_command_cleanup_consolidation.md) | Medium | Medium | Medium | |

## Dependency Graph

```
Phase 01 (DB columns)
  └──> Phase 02 (wizard completion)
         └──> Phase 03 (home screen)
                └──> Phase 04 (/setup + delivery toggle)
                       └──> Phase 05 (/status + cleanup)
                              └──> Phase 06 (command cleanup)
```

**All phases are sequential.** Each phase builds on the previous one's changes. No phases can safely run in parallel due to overlapping files (`telegram_commands.py`, `onboarding.py`, `app.js`, `index.html`).

## Phase Details

### Phase 01: Per-Chat Media Source Columns
- **What:** Add `media_source_type` and `media_source_root` columns to `chat_settings` table
- **Why:** Currently `MEDIA_SOURCE_ROOT` (Google Drive folder ID) is a global env var. Each tenant needs its own folder config.
- **Key files:** `chat_settings.py`, `settings_service.py`, `media_sync.py`, `onboarding.py`, new migration `017_add_media_source_to_chat_settings.sql`

### Phase 02: Complete Mini App Onboarding Wizard
- **What:** Fix folder ID persistence (save to `chat_settings`), add indexing step, make all steps skippable, enrich init response
- **Why:** The wizard currently has a TODO at line 221 where folder_id is never saved. Users complete setup but nothing is configured.
- **Key files:** `onboarding.py`, `index.html`, `app.js`, `style.css`

### Phase 03: Mini App Home Screen for Returning Users
- **What:** `/start` always opens Mini App. New users see wizard, returning users see dashboard with status cards and edit buttons
- **Why:** Returning users currently get a plain text command list. The Mini App should be the single entry point for everything.
- **Key files:** `telegram_commands.py`, `index.html`, `app.js`, `style.css`, `onboarding.py`

### Phase 04: `/setup` Command + Smart Delivery Toggle
- **What:** Rename `/settings` to `/setup`, add Mini App link button, replace `is_paused` with "Delivery ON/OFF" framing, smart +24hr reschedule of overdue items
- **Why:** `/setup` should be the quick in-channel settings panel. Delivery toggle gives clear control over whether media gets posted. Smart reschedule prevents queue items from being wasted when delivery is paused.
- **Key files:** `telegram_settings.py`, `telegram_commands.py`, `telegram_service.py`, `queue_repository.py`, `posting_service.py`

### Phase 05: `/status` Setup Reporting + `/connect_drive` Cleanup
- **What:** Add setup completion section to `/status` output showing what's configured. Remove `/connect_drive` command (OAuth routes stay, flow happens through Mini App wizard).
- **Why:** Users need visibility into their setup state from the channel. `/connect_drive` is orphaned now that the wizard handles it.
- **Key files:** `telegram_commands.py`, `telegram_service.py`

### Phase 06: Command Audit, Cleanup & Consolidation
- **What:** Audit all 19 commands, keep ~10 essential daily-use commands, remove vestigial ones with friendly redirect messages. Merge `/stats` data into `/status`.
- **Why:** Too many commands create confusion. Keep it lean with the commands people actually use daily.
- **Key files:** `telegram_commands.py`, `telegram_service.py`

## Estimated Total Effort

~20-30 hours across all 6 phases.
