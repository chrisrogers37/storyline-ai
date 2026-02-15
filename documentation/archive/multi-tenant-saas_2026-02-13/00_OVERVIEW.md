# Multi-Tenant SaaS Transition

**Status:** 📋 PLANNING
**Created:** 2026-02-13
**Session:** `multi-tenant-saas`
**Goal:** Transform Storyline AI from a single-tenant, developer-operated system into a multi-tenant SaaS where any Instagram creator can onboard themselves via Telegram.

## Vision

**Current state:** One Raspberry Pi, one team, one media library. All setup via CLI + SSH.

**Target state:** One central application serving many Instagram creators. Each user onboards through Telegram, connects their own Instagram account and media source, configures their schedule, and the system handles the rest. Zero CLI access needed for end users.

## Phased Remediation Plan

### Dependency Matrix

```
Phase 01  ──► Phase 02  ──► Phase 03
                              │
Phase 04  (independent)  ─────┤
Phase 05  (independent)  ─────┤
                              │
                              ▼
                          Phase 06 (depends on 03 + 04 + 05)
                              │
                              ▼
                          Phase 07 (infrastructure guide, independent but last)
```

### Phase Summary

| Phase | Title | Scope | Risk | Effort | PR |
|-------|-------|-------|------|--------|----|
| 01 | Multi-Tenant Data Model | Add tenant FK to 6 tables, update models | Medium | 3-4h | - |
| 02 | Per-Tenant Repository Queries | Update 12+ repos with tenant filtering | Low | 4-6h | - |
| 03 | Per-Tenant Scheduler & Posting | Replace hardcoded chat IDs, per-tenant loops | Medium | 4-5h | - |
| 04 | Instagram OAuth Redirect Flow | FastAPI callback endpoint, browser-based auth | Medium | 4-5h | - |
| 05 | Google Drive OAuth for Users | User-facing Google OAuth, folder picker | Medium | 4-5h | - |
| 06 | Telegram Onboarding Wizard | Guided /start flow with inline buttons | Low | 4-5h | - |
| 07 | Central Deployment & Infrastructure Guide | Cloud deploy docs, Neon DB, domain setup | Low | 2-3h | - |

### Parallel Execution Guide

**Can run in parallel** (touch disjoint files):
- Phase 04 and Phase 05 are fully independent of each other
- Phase 04 and Phase 05 can start after Phase 03 is merged
- Phase 07 can be written at any time (documentation only)

**Must be sequential:**
- Phase 01 → Phase 02 → Phase 03 (data model → queries → scheduler)
- Phase 06 depends on 03 + 04 + 05 (onboarding uses OAuth flows + per-tenant scheduling)

### Recommended Execution Order

1. **Phase 01** — Multi-tenant data model (foundation)
2. **Phase 02** — Per-tenant repository queries (uses new FKs)
3. **Phase 03** — Per-tenant scheduler & posting (uses new queries)
4. **Phase 04** — Instagram OAuth (independent, can overlap with 05)
5. **Phase 05** — Google Drive OAuth (independent, can overlap with 04)
6. **Phase 06** — Telegram onboarding wizard (ties everything together)
7. **Phase 07** — Central deployment guide (operational docs)

## Architecture Decisions

### AD-1: Shared Bot, Single Database
One Telegram bot token serves all users. One PostgreSQL database with `chat_settings_id` FK on all tenant-scoped tables. Simpler deployment, easier backup/restore, lower operational overhead.

### AD-2: Backward-Compatible Tenant Scoping
All tenant FK columns are nullable. `NULL` = legacy single-tenant behavior (existing queries unchanged). Per-tenant queries use `WHERE chat_settings_id = :id`. This allows gradual migration without breaking the existing Pi deployment.

### AD-3: chat_settings as Tenant Identity
`chat_settings` table is the tenant boundary. Each Telegram chat (group or DM) is one tenant. A user's DM with the bot = their personal tenant. Each tenant has its own media library, queue, schedule, credentials, and settings.

### AD-4: OAuth via FastAPI Callbacks
Instagram and Google Drive OAuth flows use FastAPI endpoints for redirect callbacks. The bot sends the user a link, they authorize in-browser, the callback captures the token and notifies the bot. This requires a publicly accessible URL (covered in Phase 07).

## What's NOT in Scope

- **Billing / usage limits** — Future concern, not needed for MVP
- **Web dashboard UI** — Telegram-first; web UI is a later phase
- **Multi-bot deployment** — One bot, many users
- **Data migration tooling** — Existing Pi data stays as-is (single-tenant)
- **Admin panel** — CLI remains for system administration
