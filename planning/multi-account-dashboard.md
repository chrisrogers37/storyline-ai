# Multi-Account Dashboard Migration

**Status:** Planning (consolidated 2026-04-17)
**Created:** 2026-04-17
**Reviewed by:** Rajan (architecture), Greg (implementation)

## Problem

When a user logs in via the web dashboard or opens the Mini App from their DM, they only see the DM-scoped instance (empty). Their real instances live in group chats (e.g., TL group with 4554 media items). There's no way to see or switch between instances.

## Current Architecture

The system already has multi-tenancy via `chat_settings` — each `telegram_chat_id` is an independent tenant with its own media, queue, history, schedule, and settings. This works great for group chats.

**The gap:** There's no `user ↔ chat_settings` relationship table. When a user logs in (web or Mini App DM), the system creates/resolves a `chat_settings` for their DM chat_id, which is a separate empty instance. It can't discover which group chat instances the user belongs to.

## Design Decisions

These decisions resolve contradictions identified during review. They are final.

1. **DM = management console + opt-in solo instances.** The DM is primarily the management console (instance picker, onboarding). But users CAN create a 1:1 DM instance via `/new` → "solo" option. This is opt-in, never auto-created. The key distinction: phantom DM `chat_settings` rows (created silently by `get_or_create`) are eliminated. Only explicitly created DM instances exist. Web login always lands on the instance picker ("System Management"), showing both group and solo instances.

2. **`display_name` lives only on `chat_settings`.** One canonical name per instance, set via `/name` in the group, visible to all members. No per-user labeling on the membership table.

3. **JWT stores `userId` and `activeChatId` only.** No instance list in the token. Instances are fetched dynamically via `GET /api/instances`. Selected instance stored as `activeChatId` in the JWT, reissued on switch.

4. **DM onboarding state lives in `onboarding_sessions` table** (separate from `chat_settings.onboarding_step` which tracks per-instance setup). Two state machines, two tables. The DM machine is short-lived (create instance, link to group, done).

5. **`my_chat_member` event is the primary group-linking mechanism**, not `startgroup` deep links. The `my_chat_member` event fires regardless of how the bot was added (deep link, manual add, invite link). `startgroup` is a convenience, `/link` is the manual fallback.

6. **`get_settings()` must be split** into `get_settings()` (returns None) and `get_or_create_settings()` (current behavior). This is a prerequisite for Phase 2, not part of it. ~15 call sites to audit. Greg recommends `create_if_missing: bool = True` parameter for backward compat, flipping callers one by one.

## Target Architecture

```
User (Telegram identity)
  └── user_chat_memberships (new join table)
       ├── Instance A: "TL Enterprises" (group chat, 4554 media, 10/day)
       ├── Instance B: "Personal Brand" (group chat, 200 media, 3/day)
       └── Instance C: "My Solo Account" (1:1 DM, opt-in, 100 media, 5/day)
```

### New Table: `user_chat_memberships`

```sql
CREATE TABLE user_chat_memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    chat_settings_id UUID NOT NULL REFERENCES chat_settings(id),
    instance_role VARCHAR(20) NOT NULL DEFAULT 'member',  -- 'owner', 'admin', 'member'
    joined_at TIMESTAMP NOT NULL DEFAULT NOW(),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE(user_id, chat_settings_id)
);
```

Note: field is `instance_role` (not `role`) to avoid collision with `users.role` which is a system-level concept.

### New Table: `onboarding_sessions`

```sql
CREATE TABLE onboarding_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    step VARCHAR(50) NOT NULL DEFAULT 'naming',  -- naming → awaiting_group → complete
    pending_instance_name VARCHAR(100),
    pending_chat_settings_id UUID REFERENCES chat_settings(id),
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(user_id)  -- one active onboarding per user
);
```

### `chat_settings` Enhancement

```sql
ALTER TABLE chat_settings ADD COLUMN display_name VARCHAR(100);
```

### Auto-Population Strategy

Memberships are created automatically:
1. **On bot interaction in a group chat:** Hook into `TelegramService._get_or_create_user()` — after user resolution, check if membership exists for `(user.id, chat_settings_id)`, create if not. Already runs on every interaction.
2. **On `my_chat_member` event:** When bot is added to a group, create membership for the user who added it (with `instance_role = 'owner'`).
3. **Backfill migration:** Scan `user_interactions` for historical group chat memberships.

## Auth Flow

```
Current:
  Telegram Login → JWT{userId, chatId=userId} → Dashboard(chatId=userId) → Empty instance

New:
  Telegram Login → JWT{userId, activeChatId=null} → GET /api/instances → [{chatId, name, stats}...]
    → User picks instance → POST /api/instances/:id/select → JWT reissued with activeChatId
    → Dashboard(chatId=activeChatId) → Real instance with data
```

### BFF Proxy Guard

If `activeChatId` is null when the BFF proxy tries to forward a dashboard request, redirect to the instance picker instead of proxying. This prevents `generateUrlToken(null, userId)` from crashing `validate_url_token()` on the Python side.

### URL Token Auth Gap

URL tokens bake in `chat_id` and are valid for 1 hour. If a user is removed from a group mid-session, their token remains valid. The BFF proxy should validate `activeChatId` against active memberships on each request. Low severity but worth implementing.

## Dashboard Changes

**Web Dashboard (Next.js):**
1. After Telegram login, fetch `GET /api/instances` for the logged-in user
2. If 1 instance → go directly to that instance's dashboard
3. If multiple → show instance picker: name, media count, last post, status
4. Instance picker persists selection via JWT reissue, allows switching via header dropdown

**Mini App (Telegram):**
1. When opened from group chat → show that group's instance directly (unchanged, use presence/absence of `chat_id` in validated initData as routing signal)
2. When opened from DM → show instance picker

## Onboarding Flow (New User via DM)

### First-Time Flow

```
User sends /start in DM
  ↓
Bot: "Welcome to Storydump! Let's set up your first posting instance."
  ↓
Step 1: "What do you want to call this instance?" → user types "TL Enterprises"
  ↓
Step 2: "Add me to the group chat where your team will review posts."
        [Button: "Add to Group Chat" → t.me/storydump_bot?startgroup=setup_{session_id}]
        "Bot already in your group? Run /link in that group."
  ↓
Bot is added to group → my_chat_member event fires → auto-links pending session
  (OR: startgroup deep link fires if bot freshly added)
  (OR: user runs /link {session_id} in the group as manual fallback)
  ↓
Step 3: Bot creates chat_settings for group, sets display_name
        Creates user_chat_membership (instance_role=owner)
  ↓
Instance-level onboarding begins in the group chat (existing wizard:
  connect Instagram, connect media source, set schedule)
  ↓
Bot in DM: "You're all set! Open your dashboard:"
           [Open Dashboard → Mini App with instance pre-selected]
```

Notes:
- `startgroup` payload = `setup_{onboarding_sessions.id}` (42 chars, within Telegram's 64-char limit)
- `startgroup` silently fails if bot is already in the group — the `/link` fallback and `my_chat_member` handler cover this case
- DM conversation state persisted in `onboarding_sessions`, times out after 24h (cleaned up via scheduler loop piggyback)
- `/start` handler currently doesn't parse `context.args` — must add arg parsing for deep link payloads

### Returning User Flow (DM)

```
User sends /start in DM (has existing instances)
  ↓
Bot: "Welcome back! Your instances:"
  1. TL Enterprises (4,554 media · 10/day · last post 6h ago)
  2. Personal Brand (200 media · 3/day · paused)
  ↓
  [Manage TL Enterprises] [Manage Personal Brand] [+ New Instance]
```

### `/start` Handler Branching

Goes from 2 branches to 5. Extract to a `StartCommandRouter` class:

1. Group + `startgroup` payload → link pending onboarding session to this group
2. Group + no payload → standard group setup (existing behavior, unchanged)
3. DM + new user (0 memberships) → onboarding conversation
4. DM + returning user (1+ memberships) → instance list
5. DM + active onboarding session → resume in-progress onboarding

### Bot Commands

| Command | Context | Behavior |
|---------|---------|----------|
| `/start` | DM | Instance list (returning) or onboarding (new) |
| `/start setup_*` | Group | Link group to pending onboarding session |
| `/start` | Group | Existing group setup (unchanged) |
| `/new` | DM | Create new instance (shortcut) |
| `/instances` | DM | List + manage all instances |
| `/name <name>` | Group | Set display_name for this instance |
| `/link <session_id>` | Group | Manual fallback to link group to onboarding session |

### Offboarding: Bot Kicked from Group

Register `my_chat_member` handler for `ChatMemberUpdated` events. When bot is removed from a group:
- Mark all `user_chat_memberships` for that `chat_settings` as `is_active = false`
- Instance disappears from users' instance pickers
- `chat_settings` row preserved (data not deleted, can be restored if bot is re-added)

## Backfill Strategy

The backfill is the foundation. Must complete and verify before Phase 2 ships.

### Pre-requisite Index

```sql
CREATE INDEX CONCURRENTLY idx_user_interactions_backfill
ON user_interactions(user_id, telegram_chat_id)
WHERE user_id IS NOT NULL AND telegram_chat_id < 0;
```

### Backfill Query

```sql
INSERT INTO user_chat_memberships (user_id, chat_settings_id, instance_role, joined_at)
SELECT DISTINCT
    ui.user_id,
    cs.id,
    'member',
    MIN(ui.created_at)
FROM user_interactions ui
JOIN chat_settings cs ON cs.telegram_chat_id = ui.telegram_chat_id
WHERE ui.user_id IS NOT NULL
  AND ui.telegram_chat_id < 0  -- groups/supergroups only (no DM phantoms)
  AND ui.interaction_type IN ('command', 'callback')  -- exclude bot_response
GROUP BY ui.user_id, cs.id
ON CONFLICT (user_id, chat_settings_id) DO NOTHING;
```

### Post-Backfill: Role Promotion

Call `getChatAdministrators` for each active group, update matching memberships to `admin` or `owner`. Rate limit: Telegram allows 30 calls/sec, batch with 50ms delays.

### Verification (gate for Phase 2 deploy)

```sql
-- Must return 0 rows before Phase 2 can ship
SELECT u.id, u.telegram_username, COUNT(DISTINCT ui.telegram_chat_id) as groups
FROM users u
JOIN user_interactions ui ON ui.user_id = u.id
WHERE ui.telegram_chat_id < 0
GROUP BY u.id, u.telegram_username
HAVING COUNT(DISTINCT ui.telegram_chat_id) > 0
AND u.id NOT IN (SELECT user_id FROM user_chat_memberships);
```

### Known Gap

Backfill can't recover "who added the bot to the group" — only who interacted. Users who added the bot but never sent a command won't have memberships. The `my_chat_member` handler solves this going forward. Accept this gap.

## The `get_settings()` Split

This is the single hardest refactor and a prerequisite for Phase 2. Currently `get_settings()` calls `get_or_create()` unconditionally — ~15 call sites silently create phantom `chat_settings` rows for DM users.

### Approach

Add `create_if_missing: bool = True` parameter to `get_settings()` for backward compat, then flip callers one by one.

### Call Sites That SHOULD Still Create (group context)

- `handle_start` in group context
- `TelegramService` callback handlers (operating on an existing group)
- Scheduler loop (`get_all_active()` — doesn't call `get_settings`, already safe)

### Call Sites That MUST NOT Create (DM context)

- `handle_start` in DM (check memberships first)
- `SetupStateService.get_setup_state()` when called from DM
- `DashboardService._resolve_chat_settings_id()` — creates phantoms on every BFF proxy page load
- `onboarding/init` endpoint — `onboarding_init()` → `_get_setup_state()` → `get_settings()`
- BFF proxy requests with `activeChatId = null`

### Phantom Cleanup

After the `get_settings()` split ships, existing phantom DM `chat_settings` rows will still exist and appear in `get_all_active()` scheduler queries (no-op but wastes cycles). Add a cleanup migration to delete `chat_settings` rows where `telegram_chat_id > 0` AND no media/queue/history references exist.

## Implementation Plan

### Phase 1a: Migration + Model + Repository (1 PR, ~400 LOC, low risk)

- [ ] Migration 023: `user_chat_memberships` table, `onboarding_sessions` table, `display_name` on `chat_settings`
- [ ] Migration 023: Index on `user_interactions(user_id, telegram_chat_id)` for backfill
- [ ] `UserChatMembership` model + `UserChatMembershipRepository` (~120 LOC)
- [ ] `OnboardingSession` model + `OnboardingSessionRepository`
- [ ] Auto-create membership hook in `TelegramService._get_or_create_user()` for group interactions
- [ ] `DashboardService.get_user_instances(telegram_user_id)` — JOIN memberships → chat_settings, aggregate stats (~40 LOC)

### Phase 1b: Backfill + Verification (script, run on prod)

- [ ] Backfill script with group-only filter (`telegram_chat_id < 0`)
- [ ] Role promotion via `getChatAdministrators`
- [ ] Run verification query — must return 0 rows
- [ ] **GATE: Phase 2 cannot deploy until backfill verified**

### Phase 2a: `get_settings()` Split + `/start` Refactor (1 PR, ~400 LOC, high risk)

- [ ] Add `create_if_missing` parameter to `get_settings()`
- [ ] Audit and flip ~15 call sites (DM paths → `create_if_missing=False`)
- [ ] `StartCommandRouter` class with 5-branch `/start` handler
- [ ] `ConversationService` wrapping `onboarding_sessions` (`advance_step()`, `get_current_step()`, `timeout_check()`)
- [ ] DM onboarding flow (naming → awaiting_group → complete)
- [ ] Returning user instance list in DM

### Phase 2b: Group Linking + Event Handlers (1 PR, ~400 LOC, medium risk)

- [ ] `my_chat_member` handler: auto-link pending onboarding on bot-added, deactivate memberships on bot-kicked
- [ ] `startgroup` deep link arg parsing in `/start` handler
- [ ] `/link <session_id>` fallback command
- [ ] `/name <name>` command for setting instance display_name
- [ ] `/instances` command for DM instance management
- [ ] Onboarding session timeout cleanup in scheduler loop

### Phase 3: API + Auth (1 PR, ~300 LOC, medium risk — can parallel with Phase 2b)

- [ ] `SessionPayload.chatId` → `SessionPayload.activeChatId: number | null`
- [ ] Auth route: set `activeChatId = null` on login (not `chatId = body.id`)
- [ ] `GET /api/instances` endpoint — calls `DashboardService.get_user_instances()`
- [ ] `POST /api/instances/:id/select` — reissues JWT with `activeChatId` set
- [ ] BFF proxy: use `activeChatId`, redirect to picker if null
- [ ] BFF proxy: validate `activeChatId` against active memberships on each request

### Phase 4: Frontend (1 PR, ~500 LOC, low risk — depends on Phase 3)

- [ ] Instance picker page/component (name, media count, posts/day, last post, status badge)
- [ ] Instance switcher dropdown in dashboard header
- [ ] Update dashboard layout to show active instance name
- [ ] 0-instance edge case → "Set up your first instance" CTA linking to DM bot
- [ ] Mini App DM entry point: `/webapp/instances` picker view

### Effort Summary

| Phase | LOC | PRs | Risk | Dependencies |
|-------|-----|-----|------|-------------|
| 1a: Data Layer | ~400 | 1 | Low | None |
| 1b: Backfill | script | — | Low | Phase 1a |
| 2a: get_settings + /start | ~400 | 1 | High | Phase 1b verified |
| 2b: Group Linking | ~400 | 1 | Medium | Phase 2a |
| 3: API + Auth | ~300 | 1 | Medium | Phase 1a (can parallel 2b) |
| 4: Frontend | ~500 | 1 | Low | Phase 3 |
| **Total** | **~2000** | **5-6** | | |

Phase 2a is the critical path. Everything else can be parallelized around it.

## Open Questions

1. **Permission model** — can all group members see the dashboard, or only admins/owners?
   - Decision: `instance_role` field on memberships. Owners/admins get full access, members get read-only. Enforced at BFF proxy level.
2. **Instance creation from web dashboard** — support it?
   - Decision: DM bot only for now. Web dashboard manages existing instances.
3. **Instance limits per user?**
   - Decision: No limit for now, revisit if needed.

---

## Review Appendix

Full architecture review (Rajan) and engineering review (Greg) were conducted 2026-04-17. All 20 findings have been incorporated into the consolidated plan above:

- Rajan: 3 blockers (backfill ordering, get_or_create phantoms, startgroup failure), 7 suggestions (display_name dedup, JWT schema, backfill filter, index, onboarding table, URL token gap, role naming), 5 nits (initData routing, payload length, solo user contradiction, bot-kicked handling, backfill role promotion)
- Greg: 5 additional concerns (scheduler phantom iteration, DashboardService phantom factory, null activeChatId crash, backfill gap for bot-adders, onboarding/init phantom creation), implementation complexity analysis, code reuse inventory, effort estimates, PR sequencing
