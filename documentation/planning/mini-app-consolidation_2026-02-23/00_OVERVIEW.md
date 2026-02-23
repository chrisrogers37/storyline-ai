# Mini App Consolidation — Command Cleanup & Feature Unification

**Status**: 🔧 IN PROGRESS (Phase 5)
**Started**: 2026-02-23
**Created**: 2026-02-23
**Priority**: High

## Problem Statement

The bot has grown organically into two parallel interfaces:

1. **Telegram Commands** (11 active) — text-heavy, multi-step conversation flows, settings menus with 10+ inline buttons
2. **Mini App** (webapp) — visual dashboard with collapsible cards, toggles, lazy-loaded data

These overlap significantly. Users must context-switch between typing `/settings` for account management, opening the Mini App for schedule actions, and using `/status` for health checks. The experience is fragmented.

### Current Command Inventory

| Command | What It Does | Mini App Overlap |
|---------|-------------|------------------|
| `/start` | Opens Mini App (or shows fallback) | **Full** — IS the Mini App |
| `/status` | 25-line health report + setup status tree | **Partial** — dashboard shows counts but not health/setup checks |
| `/queue` | Lists next 10 queue items | **Full** — Queue card does this |
| `/next` | Force-send next post immediately | **None** — action command, not info |
| `/pause` | Pause delivery | **Full** — Quick Controls toggle |
| `/resume` | Resume + handle overdue items | **Partial** — toggle exists, but overdue flow is Telegram-only |
| `/history N` | Recent post list (scrollable) | **Full** — Recent Activity card |
| `/settings` | 10-button settings menu + multi-step conversations | **Partial** — only 2 toggles in Mini App |
| `/help` | Command reference | **None** — reference material |
| `/sync` | Trigger media sync | **None** — action command |
| `/cleanup` | Delete bot messages | **None** — utility |

### What the Mini App Already Has

The Enhanced Dashboard (shipped Feb 2026) already provides:

- **8 collapsible cards**: Instagram, Google Drive, Quick Controls, Schedule, Queue, Recent Activity, Media Library
- **Quick Controls card**: Delivery ON/OFF and Dry Run ON/OFF toggles
- **Schedule card**: Day summary, +7 Days extend, Regenerate (with confirmation), Edit Settings link
- **Queue card**: Lazy-loaded next 10 pending posts with scheduled times
- **Recent Activity card**: Lazy-loaded last 10 posts with status and posting method
- **Media Library card**: Category breakdown with percentage bars
- **Edit mode**: Jump to any wizard step from home, "Save & Return" navigation
- **API endpoints**: `/toggle-setting`, `/queue-detail`, `/history-detail`, `/media-stats`, `/extend-schedule`, `/regenerate-schedule`

### Remaining Gaps in Mini App

1. **Incomplete settings** — Quick Controls only has 2 of 5 toggles; missing Instagram API, Verbose, Media Sync. No Posts/Day or Posting Hours editing from dashboard.
2. **No account management** — can't add/switch/remove Instagram accounts
3. **No /next equivalent** — can't force-send from dashboard
4. **No /sync equivalent** — can't trigger sync from dashboard
5. **No overdue handling** — /resume's reschedule/clear/force flow has no Mini App equivalent
6. **No status/health view** — no system health or setup completion reporting

---

## Design Philosophy

### Keep In Telegram (Quick Actions)
Commands that are **fast, contextual, action-oriented** and benefit from being typed in-chat:

- **`/next`** — Force-send. One word, immediate result. This is a power-user shortcut.
- **`/cleanup`** — Channel housekeeping. Must operate on Telegram messages.
- **`/help`** — Reference card. Quick text dump, no UI needed.

### Slim Down In Telegram (Deferred to Phase 5)
Commands that currently display **rich UI** in Telegram will become **thin redirects** with one-line status + a "Open Dashboard" button — but only after the Mini App has full feature parity:

- **`/status`** → One-line summary + button to Mini App status view
- **`/settings`** → One-line current config + button to Mini App settings

### Move to Mini App (Full Experience)
Everything that involves **browsing data, editing settings, or multi-step workflows**:

- Account management (add/switch/remove)
- Full settings panel (all toggles + numeric inputs)
- Queue browsing + schedule management (already done)
- History browsing (already done)
- Media library browsing (already done)
- System health / setup status
- Media sync trigger
- Overdue post handling

### Post Notifications (Unchanged)
The in-channel post notification with action buttons stays exactly as-is:
- Auto Post / Posted / Skip / Reject buttons
- Inline account selector (switch account per-post)
- These are contextual actions on a specific post and belong in the channel

---

## Phased Implementation Plan

### Phase 1: Complete Settings in Quick Controls Card — ✅ COMPLETE (PR #73)
**Expand the existing Quick Controls card to include all settings**

The Quick Controls card already has Delivery and Dry Run toggles. This phase adds the remaining 3 toggles and numeric settings editing inline.

Frontend changes (`index.html` + `app.js` + `style.css`):
- Add 3 toggle rows to Quick Controls card body: Instagram API, Verbose Notifications, Media Sync
- Add Posts/Day display with edit control (number input or stepper)
- Add Posting Hours display with edit controls (start/end hour selectors)
- Reuse existing `toggleSetting()` method (already handles POST to `/toggle-setting`)
- Add `updateSetting(name, value)` method for numeric settings (POST to existing `/schedule` endpoint pattern)

Backend changes (`onboarding.py`):
- Expand `/toggle-setting` endpoint's `allowed_settings` from `{"is_paused", "dry_run_mode"}` to include `"enable_instagram_api"`, `"show_verbose_notifications"`, `"media_sync_enabled"` — the `SettingsService.toggle_setting()` already supports all 5
- Add `POST /api/onboarding/update-setting` for numeric settings — calls existing `SettingsService.update_setting()` which already validates `posts_per_day` (1-50), `posting_hours_start` (0-23), `posting_hours_end` (0-23)

No changes to `/settings` command in this phase.

### Phase 2: Account Management in Mini App — ✅ COMPLETE (PR #74)
**Move add/switch/remove accounts to Mini App**

Expand the existing Instagram card to be collapsible with account management:
- List of all connected accounts globally (active for this chat marked with checkmark)
- "Switch" button per inactive account (calls switch-account endpoint)
- "Add Account" button → opens OAuth flow (reuse existing `connectOAuth('instagram')` pattern — OAuth only, no manual token input)
- "Remove" button per account (with inline confirmation dialog, calls deactivate)
- Active account badge on card header (e.g., "@username")
- If no accounts exist, show "Connect Instagram" button (same OAuth flow)

Frontend changes (`index.html` + `app.js` + `style.css`):
- Make Instagram card expandable (add `home-card-expandable` class, chevron, `onclick`)
- Card body: account list with switch/remove buttons, add button at bottom
- Lazy-load account list on first expand (follow `toggleCard()` + `_loadCardData()` pattern)
- `_loadAccounts()` — fetch and render account list
- `switchAccount(accountId)` — POST switch, update UI
- `removeAccount(accountId)` — show inline confirm, POST deactivate, re-render list
- Reuse `connectOAuth('instagram')` for adding accounts (already polls for completion)
- Update card summary text after any account change

Backend changes (`onboarding.py`):
- `GET /api/onboarding/accounts` — list all active accounts + mark which is active for this chat (uses `InstagramAccountService.list_accounts()` + `ChatSettingsRepository` for active_instagram_account_id)
- `POST /api/onboarding/switch-account` — switch active account for this chat (uses `InstagramAccountService.switch_account()`)
- `POST /api/onboarding/remove-account` — deactivate account (uses `InstagramAccountService.deactivate_account()`)
- Reuse existing OAuth flow for adding accounts (existing `/oauth-url/instagram` endpoint)

Note: **In-channel post account selector stays unchanged** — switching account on a specific post notification is a contextual action that belongs in the channel.

### Phase 3: Status & Health in Mini App ✅ COMPLETE (PR #75)
**Move /status reporting to Mini App**

Add a new collapsible **System Status card** to the dashboard (positioned after Quick Controls) showing:
- Delivery mode (active/paused/dry-run)
- Instagram API status (enabled/disabled, token health)
- Media sync status (last sync time, source type)
- Setup completion checklist (5 items with checkmarks)
- Queue health (pending count, next post time)

Design decisions:
- Setup checks are replicated inline in the endpoint (not extracted to a shared helper) — the 5 checks are simple queries and only 2 consumers exist
- Lock count omitted — niche info not needed in dashboard
- Card positioned after Quick Controls for logical grouping with operational controls

Frontend changes (`index.html` + `app.js` + `style.css`):
- New collapsible card with `home-card-expandable` pattern
- Badge shows "Healthy" (green) or "N Issues" (warning/error)
- Card body: setup checklist rows + system health rows
- Lazy-load via `_loadCardData('status')` pattern

Backend changes (`onboarding.py`):
- `GET /api/onboarding/system-status` — aggregated health data
- Calls `HealthCheckService.check_all()` for system checks
- Replicates setup check logic from `TelegramCommandHandlers._get_setup_status()` inline (account, drive, media, schedule, delivery)

No changes to `/status` command in this phase.

### Phase 4: Sync Media Action in Mini App — 🔧 IN PROGRESS
**Add media sync trigger to Quick Controls card**
Started: 2026-02-22

Simplified scope after challenge round:
- **Dropped**: "Send Next Now" — stays as `/next` in Telegram (one word, instant, power-user shortcut)
- **Dropped**: Overdue handling — rare scenario, keep in Telegram via `/resume`
- **Kept**: "Sync Media" trigger button — natural fit alongside the Media Sync toggle

Add to Quick Controls card body:
- "Sync Media" trigger button below the existing settings
- Visual divider separating settings from actions
- Inline result display (e.g., "3 new, 1 updated" or "No changes")
- Loading state while sync runs
- Error handling for sync failures

Backend:
- `POST /api/onboarding/sync-media` — calls existing `MediaSyncService.sync(telegram_chat_id=chat_id)`

Tests:
- `test_sync_media_success` — verify endpoint calls service and returns result
- `test_sync_media_unauthorized` — verify auth check
- `test_sync_media_error` — verify error handling

### Phase 5: Command Cleanup — 🔧 IN PROGRESS
**Retire redundant commands, keep /status and /settings as full handlers**
Started: 2026-02-23

After Phases 1-4, the Mini App has full feature parity. Now retire redundant commands.

**Challenge round decision**: Keep `/status` and `/settings` as full handlers (not one-line summaries).
- `/status` is genuinely useful for in-chat troubleshooting (setup checklist, system health)
- `/settings` is the quick BotFather-style control panel users rely on
- The 11→6 reduction comes entirely from retiring 5 commands, not slimming these
- Add "Open Dashboard" button to `/status` (already exists on `/settings`)

**Retire** (add redirect messages to existing `handle_removed_command` dict):
- `/queue` → "View your queue in the dashboard" + redirect
- `/pause` → "Use Quick Controls in the dashboard" + redirect
- `/resume` → "Use Quick Controls in the dashboard" + redirect
- `/history` → "View recent activity in the dashboard" + redirect
- `/sync` → "Sync from the dashboard" + redirect

**Enhance** `/status`:
- Add "Open Dashboard" inline button (WebAppInfo for private, signed URL for groups)

**Update** `/help`:
- Show only 6 active commands (remove queue, pause, resume, history, sync references)

**Update** `/start` fallback:
- Remove references to retired commands in the fallback text (no OAUTH_REDIRECT_BASE_URL)

**Update** command registration:
- Move 5 commands from active to `handle_removed_command` in `command_map`
- Trim `BotCommand` list from 11 to 6

**Update** tests:
- Remove test classes for retired commands (TestQueueCommand, TestPauseCommand, TestResumeCommand, TestHistoryCommand)
- Add tests for new redirect messages
- Add test for "Open Dashboard" button on `/status`
- Keep TestSyncCommand tests in separate file (test_telegram_sync_command.py) — those test the sync service, not the Telegram handler

The command structure becomes:

| Command | Behavior | Purpose |
|---------|----------|---------|
| `/start` | Opens Mini App (unchanged) | **Primary entry point** |
| `/status` | Full health report + "Open Dashboard" button | **Diagnostics** |
| `/settings` | Toggle panel + "Open Full Settings" button (unchanged) | **Quick controls** |
| `/next` | Force-send (unchanged) | **Power-user shortcut** |
| `/help` | Slim command reference (updated) | **Reference** |
| `/cleanup` | Delete bot messages (unchanged) | **Utility** |

This takes us from **11 active commands** down to **6** (with 5 joining the 7 already-retired commands as redirects).

### Phase 6: Menu Button
**Configure BotFather menu button to always open Mini App**

Instead of the hamburger menu showing a command list, the main menu button opens the Mini App directly. This makes the Mini App the default interface.

---

## Command Consolidation Summary

### Before (11 commands)
```
/start    /status    /queue     /next      /pause
/resume   /history   /settings  /help      /sync
/cleanup
```

### After (6 commands)
```
/start     → Opens Mini App (primary interface)
/status    → Full health report + [Open Dashboard] button
/settings  → Toggle panel + [Open Full Settings] button
/next      → Force-send next post (power-user action)
/help      → Slim reference card
/cleanup   → Delete bot messages (utility)
```

### Retired → Redirect (12 total, 5 new + 7 existing)
```
/queue /pause /resume /history /sync          ← NEW redirects
/schedule /stats /locks /reset /dryrun        ← Existing redirects
/backfill /connect                            ← Existing redirects
```

---

## What Stays in Telegram (Unchanged)

**Post notifications** with full button set:
- Auto Post to Instagram
- Posted / Skip / Reject
- Account selector (switch per-post)
- Open Instagram link

These are contextual actions on specific posts and MUST stay in the channel. The Mini App cannot interact with individual Telegram messages.

---

## Files Affected (Estimated)

| Phase | Files | Scope |
|-------|-------|-------|
| 1 | `onboarding.py`, `index.html`, `app.js`, `style.css`, tests | Expand Quick Controls |
| 2 | `onboarding.py`, `index.html`, `app.js`, `style.css`, tests | Account management |
| 3 | `onboarding.py`, `index.html`, `app.js`, `style.css`, tests | Status/health card |
| 4 | `onboarding.py`, `index.html`, `app.js`, `style.css`, tests | Sync Media trigger button |
| 5 | `telegram_commands.py`, `telegram_settings.py`, tests | Command slimming + retirements |
| 6 | BotFather config (manual) | Menu button |

## Existing Code to Reuse (NOT Duplicate)

| What | Where It Already Lives | Reuse Pattern |
|------|----------------------|---------------|
| Toggle 5 boolean settings | `SettingsService.toggle_setting()` | Widen `allowed_settings` in endpoint |
| Update numeric settings | `SettingsService.update_setting()` | New thin endpoint, same service call |
| Schedule extend/regenerate | `/extend-schedule`, `/regenerate-schedule` endpoints | Already in Mini App |
| Queue detail + day summary | `/queue-detail` endpoint | Already in Mini App |
| History detail | `/history-detail` endpoint | Already in Mini App |
| Media stats | `/media-stats` endpoint | Already in Mini App |
| Account CRUD | `InstagramAccountService` | New endpoints call existing service |
| Health checks | `HealthCheckService.check_all()` | New endpoint wraps existing service |
| Setup status checks | `TelegramCommandHandlers._get_setup_status()` | Extract logic to shared helper |
| Force post next | `PostingService.force_post_next()` | New endpoint calls existing service |
| Media sync | `MediaSyncService.sync()` | New endpoint calls existing service |
| Overdue handling | `TelegramCommandHandlers.handle_resume()` | Extract logic to shared helper |
| OAuth flow | `connectOAuth()` in app.js | Reuse for account additions |
| Collapsible card pattern | Existing cards in index.html/app.js | Follow established pattern |
| Lazy-load on expand | `toggleCard()` + `_loadCardData()` | Follow established pattern |

## Dependencies

- Phase 1 is independent (no blockers)
- Phase 2 is independent (no blockers)
- Phase 3 is independent (no blockers)
- Phase 4 is independent (no blockers)
- Phase 5 depends on Phases 1-4 (can't retire until Mini App has the features)
- Phase 6 depends on Phase 5 (menu button change is the final step)
- Phases 1-4 can be done in any order, but suggested order maximizes user value

## Risk & Rollback

- All retired commands get redirect messages (never a dead end)
- Mini App features are additive (don't remove Telegram functionality until Mini App equivalent is verified)
- Phase 5 (retirements) is the only destructive phase and should be the last step
