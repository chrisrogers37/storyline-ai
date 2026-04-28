# Web App Migration Plan: Landing Site to Full Application

**Status:** Draft — Pending Review
**Created:** 2026-04-15
**Goal:** Evolve the existing Next.js landing/teaser site into a full web application with auth, dashboard, settings, and media management — replacing most Telegram Mini App functionality while keeping Telegram as the action layer (approvals, quick decisions).

**Guiding Principle:** Web-first for management, Telegram-first for actions.

---

## Table of Contents

1. [Current State](#current-state)
2. [Architecture Decisions](#architecture-decisions)
3. [Phase 1: Auth + Basic Dashboard](#phase-1-auth--basic-dashboard)
4. [Phase 2: Onboarding & Settings Migration](#phase-2-onboarding--settings-migration)
5. [Phase 3: Media Management](#phase-3-media-management)
6. [File Structure](#file-structure)
7. [Database & Schema Changes](#database--schema-changes)
8. [Mini App Migration Matrix](#mini-app-migration-matrix)
9. [Environment & Deployment](#environment--deployment)
10. [Risks & Dependencies](#risks--dependencies)
11. [Open Questions](#open-questions)

---

## Current State

### Landing Site (`landing/`)
- **Framework:** Next.js 16.1.6, React 19, App Router
- **UI:** Tailwind v4, shadcn (new-york style), Lucide icons
- **Database:** Drizzle ORM → Neon PostgreSQL (only `waitlist_signups` table)
- **Routes:** `/` (landing), `/setup/*` (6-page setup guide), `POST /api/waitlist`
- **Auth:** None. Fully public.
- **Deployment:** Vercel

### Backend API (`src/api/`)
- **Framework:** FastAPI (Python)
- **Auth:** Telegram WebApp `initData` (HMAC-SHA256) + signed URL tokens
- **Endpoints:** 30+ across OAuth, onboarding, settings, dashboard, analytics
- **Database:** SQLAlchemy + Alembic → same Neon PostgreSQL instance
- **Deployment:** Railway

### Telegram Mini App (`src/api/static/onboarding/`)
- **Tech:** Vanilla HTML/CSS/JS SPA (no framework)
- **Modes:** `wizard` (7-step onboarding) and `home` (returning user dashboard)
- **Served by:** FastAPI static files

### User Model
- `users` table: `telegram_user_id` (BigInteger, unique) is the identity key
- `chat_settings` table: per-chat tenant boundary (config, onboarding state, active account)
- Users are auto-discovered from Telegram interactions — no registration flow exists

---

## Architecture Decisions

### AD-1: Auth Provider — Telegram Login Widget

**Decision:** Use Telegram Login Widget as the sole auth method.

**Why:**
- Users already have Telegram accounts (onboarded via Mini App)
- `telegram_user_id` maps directly to existing `users.telegram_user_id`
- No new identity system needed — zero friction for existing users
- Widget provides: `id`, `first_name`, `last_name`, `username`, `photo_url`, `auth_date`, `hash`
- Hash validated server-side using bot token (same HMAC pattern as existing auth)

**Session management:**
- Next.js API route validates Telegram Login hash
- Creates a signed JWT stored in an `httpOnly` cookie
- JWT payload: `{ telegram_user_id, first_name, username, photo_url, iat, exp }`
- 7-day expiry with sliding window refresh
- `middleware.ts` checks cookie on `/dashboard/*`, `/settings/*`, `/media/*` routes

**Alternative considered:** NextAuth.js with Telegram provider. Rejected — adds dependency for a single provider, and NextAuth's session model is heavier than needed.

### AD-2: API Communication — BFF (Backend for Frontend) Pattern

**Decision:** Next.js API routes proxy calls to FastAPI. The browser never talks to FastAPI directly.

```
Browser → Next.js API Route (BFF) → FastAPI Backend
                ↓
         Session cookie          Signed URL token
         (httpOnly JWT)          (generated server-side)
```

**Why:**
- Session management stays in Next.js (single auth boundary)
- No CORS configuration needed between frontend and FastAPI
- BFF generates signed URL tokens server-side (bot token never exposed to client)
- Can add response caching, rate limiting, and error normalization at the BFF layer
- FastAPI auth model (`init_data` / URL token) stays unchanged

**Implementation:**
- BFF routes under `src/app/api/v1/` mirror FastAPI endpoints
- Each BFF route: extract `telegram_user_id` from session → generate URL token → call FastAPI → return response
- Use a shared `api-client.ts` server-side utility with `fetch()` to call FastAPI
- FastAPI base URL from `STORYDUMP_API_URL` env var

**Alternative considered:** Direct client-side calls to FastAPI with CORS. Rejected — exposes auth token generation to client, complicates session management, requires CORS changes on FastAPI.

### AD-3: State Management — TanStack Query + React Hooks

**Decision:** TanStack Query (React Query) for server state, React hooks for UI state.

**Why:**
- Dashboard is read-heavy with periodic refreshes (analytics, queue, health)
- TanStack Query provides: caching, background refetch, stale-while-revalidate, loading/error states
- No global client state needed (no Redux/Zustand)
- Fits Next.js App Router patterns well (can combine with Server Components for initial data)

**Patterns:**
- Custom hooks per data domain: `useApprovalLatency(days)`, `useQueueDetail()`, `useMediaStats()`, etc.
- Mutations for settings changes: `useToggleSetting()`, `useUpdateSchedule()`, etc.
- Queries call Next.js BFF routes (not FastAPI directly)
- `QueryClientProvider` in app layout (client boundary)

### AD-4: Route Groups — Marketing vs App

**Decision:** Use Next.js route groups to separate public marketing pages from authenticated app pages.

```
src/app/
├── (marketing)/     ← Public: landing, setup guide, login
│   ├── layout.tsx   ← Header with logo + "Login" button + Footer
│   └── ...
├── (app)/           ← Authenticated: dashboard, settings, media
│   ├── layout.tsx   ← App shell with sidebar nav + user menu
│   └── ...
```

**Why:**
- Different layouts (marketing header/footer vs app sidebar)
- Middleware can protect `(app)` routes with a single pattern match
- Clean separation of concerns
- Landing page performance unaffected by app bundle

### AD-5: Chat/Workspace Selection

**Decision:** Add a chat selector for multi-chat users. Default to the user's most recent chat.

**Problem:** The current system is per-chat (`chat_settings`), but web auth is per-user (`telegram_user_id`). A user may manage multiple chats.

**Solution:**
- New FastAPI endpoint: `GET /api/onboarding/user-chats?init_data=...` returns all chats where the user has been active (query `posting_history` + `user_interactions` for distinct `chat_settings_id` values)
- BFF stores selected `chat_id` in session (or as a cookie)
- Dashboard header shows workspace picker when user has multiple chats
- Single-chat users never see the picker

**Schema impact:** No new tables needed for Phase 1. Use existing interaction data to derive membership. Phase 2 may add a `chat_members` table for explicit access control.

### AD-6: Component Architecture

**Decision:** Server Components for layout/data fetching, Client Components for interactivity.

**Patterns:**
- Dashboard pages: Server Component fetches initial data → passes to Client Component for display + refresh
- Settings forms: Client Components with TanStack Query mutations
- Charts/visualizations: Client Components (likely Recharts or similar)
- Use `Suspense` boundaries for loading states

---

## Phase 1: Auth + Basic Dashboard

**Scope:** Login flow, session management, route protection, dashboard with analytics.
**Estimated PRs:** 3-4
**Dependencies:** None (builds on existing landing site + API)

### PR 1.1: Auth Infrastructure

**Files to create:**
- `src/lib/auth.ts` — JWT creation/validation, session helpers
- `src/lib/telegram-auth.ts` — Telegram Login Widget hash validation
- `src/lib/api-client.ts` — Server-side FastAPI client with URL token generation
- `src/app/api/auth/telegram/route.ts` — POST: validate Telegram Login data, create session
- `src/app/api/auth/session/route.ts` — GET: return current session (for client-side checks)
- `src/app/api/auth/logout/route.ts` — POST: clear session cookie
- `src/middleware.ts` — Protect `/dashboard/*`, `/settings/*`, `/media/*`
- `src/components/auth/telegram-login-button.tsx` — Telegram Login Widget wrapper
- `src/components/auth/user-menu.tsx` — Avatar + dropdown (logout, settings)

**Changes to existing files:**
- `src/app/(marketing)/layout.tsx` (rename from `layout.tsx`) — Add login button to header
- `src/components/layout/header.tsx` — Add conditional login/user menu
- `package.json` — Add `jose` (JWT), `@tanstack/react-query`

**Login UX (per requirements):**
- Small "Log in" link at the bottom of the landing page (footer area)
- Clicking opens `/login` page with Telegram Login Widget centered
- Widget redirects to `/api/auth/telegram` callback
- On success: redirect to `/dashboard`
- Hidden signup: no public registration. Login only works for users already in `users` table. If `telegram_user_id` not found, show "Invite-only" message. (Toggle later via env var `ALLOW_SIGNUP=true`)

**Environment variables:**
- `TELEGRAM_BOT_TOKEN` — already exists, needed for hash validation
- `TELEGRAM_BOT_USERNAME` — for Login Widget configuration
- `JWT_SECRET` — signing key for session JWTs
- `STORYDUMP_API_URL` — FastAPI base URL (e.g., `https://storyline-ai-production.up.railway.app`)

### PR 1.2: App Shell + Dashboard Layout

**Files to create:**
- `src/app/(app)/layout.tsx` — App shell: sidebar + top bar + workspace picker
- `src/app/(app)/dashboard/page.tsx` — Dashboard overview
- `src/components/app/sidebar.tsx` — Navigation sidebar
- `src/components/app/workspace-picker.tsx` — Chat/workspace selector
- `src/components/app/page-header.tsx` — Page title + breadcrumbs
- `src/hooks/use-session.ts` — Client-side session hook
- `src/hooks/use-workspace.ts` — Active workspace context
- `src/providers/query-provider.tsx` — TanStack Query client provider
- `src/providers/workspace-provider.tsx` — Workspace context provider

**Dashboard overview page shows:**
- System status summary (healthy/unhealthy)
- Today's posting stats (posts today, queue depth, success rate)
- Quick actions: pause/resume, force next post
- Recent activity feed (last 5 posts)

**New FastAPI endpoint needed:**
- `GET /api/onboarding/user-chats` — returns chats where user has been active

### PR 1.3: Analytics Dashboard Pages

**Files to create:**
- `src/app/(app)/dashboard/analytics/page.tsx` — Analytics overview
- `src/app/(app)/dashboard/queue/page.tsx` — Queue detail view
- `src/app/(app)/dashboard/history/page.tsx` — Posting history
- `src/app/(app)/dashboard/health/page.tsx` — Service health & system status
- `src/components/dashboard/approval-latency-chart.tsx` — Latency visualization
- `src/components/dashboard/team-performance-table.tsx` — Per-user stats table
- `src/components/dashboard/content-reuse-chart.tsx` — Reuse classification
- `src/components/dashboard/category-drift-chart.tsx` — Config vs actual ratios
- `src/components/dashboard/schedule-preview.tsx` — Upcoming slots timeline
- `src/components/dashboard/service-health-grid.tsx` — Health check cards
- `src/components/dashboard/dead-content-table.tsx` — Never-posted items
- `src/components/dashboard/posting-history-table.tsx` — History with filters
- `src/components/dashboard/queue-table.tsx` — Current queue items
- `src/hooks/use-analytics.ts` — TanStack Query hooks for all analytics endpoints

**BFF routes:**
- `src/app/api/v1/analytics/[endpoint]/route.ts` — Dynamic route proxying to FastAPI analytics endpoints
- `src/app/api/v1/dashboard/route.ts` — Aggregated dashboard data
- `src/app/api/v1/queue/route.ts` — Queue detail proxy
- `src/app/api/v1/history/route.ts` — History detail proxy
- `src/app/api/v1/health/route.ts` — System status proxy

**Chart library:** Recharts (lightweight, React-native, good shadcn compatibility). Add to `package.json`.

### PR 1.4: Polish + Mobile Responsiveness

- Responsive sidebar (hamburger menu on mobile)
- Loading skeletons for dashboard cards
- Error boundaries per dashboard section
- Empty states for new users with no data
- Auto-refresh intervals (analytics: 5min, queue: 30s, health: 1min)

---

## Phase 2: Onboarding & Settings Migration

**Scope:** Move Mini App onboarding wizard and settings to web.
**Estimated PRs:** 3-4
**Dependencies:** Phase 1 complete (auth + dashboard)

### PR 2.1: Settings Pages

**Files to create:**
- `src/app/(app)/settings/page.tsx` — Settings overview
- `src/app/(app)/settings/schedule/page.tsx` — Schedule config (posts/day, hours)
- `src/app/(app)/settings/categories/page.tsx` — Category mix configuration
- `src/app/(app)/settings/general/page.tsx` — Toggles: pause, dry run, verbose notifications
- `src/components/settings/schedule-form.tsx` — Schedule editor with validation
- `src/components/settings/category-mix-editor.tsx` — Ratio sliders/inputs
- `src/components/settings/toggle-card.tsx` — Setting toggle with description
- `src/hooks/use-settings.ts` — TanStack Query hooks for settings mutations

**BFF routes:**
- `src/app/api/v1/settings/route.ts` — GET current settings
- `src/app/api/v1/settings/toggle/route.ts` — POST toggle setting
- `src/app/api/v1/settings/update/route.ts` — POST update numeric setting
- `src/app/api/v1/settings/schedule/route.ts` — POST update schedule

### PR 2.2: Instagram Account Management

**Files to create:**
- `src/app/(app)/settings/instagram/page.tsx` — Account list + management
- `src/components/settings/instagram-account-card.tsx` — Account with switch/remove actions
- `src/components/settings/add-account-form.tsx` — Manual account entry
- `src/components/settings/connect-instagram-button.tsx` — OAuth flow trigger
- `src/hooks/use-accounts.ts` — Account management hooks

**OAuth flow on web:**
- "Connect Instagram" button calls BFF → BFF gets OAuth URL from FastAPI → redirect user to Meta OAuth
- OAuth callback returns to `/api/auth/instagram/callback` (new Next.js route)
- Callback verifies, stores token via FastAPI, redirects to `/settings/instagram` with success message
- Need to update FastAPI OAuth routes to accept a `redirect_uri` parameter for web callbacks (currently hardcoded to Railway)

**BFF routes:**
- `src/app/api/v1/accounts/route.ts` — GET list, POST add manual
- `src/app/api/v1/accounts/switch/route.ts` — POST switch active
- `src/app/api/v1/accounts/[id]/route.ts` — DELETE remove
- `src/app/api/auth/instagram/callback/route.ts` — OAuth callback handler

**FastAPI changes needed:**
- Modify `/auth/instagram/start` to accept optional `redirect_uri` query param (for web OAuth flow)
- Modify `/auth/instagram/callback` and `/auth/instagram-login/callback` to support redirecting back to web app on completion

### PR 2.3: Google Drive Connection

**Files to create:**
- `src/app/(app)/settings/google-drive/page.tsx` — Drive connection status + management
- `src/components/settings/drive-connection-card.tsx` — Connection status, disconnect, reconnect
- `src/components/settings/media-folder-input.tsx` — Folder URL input with validation

**OAuth flow:**
- Similar to Instagram: BFF gets OAuth URL → redirect → callback → redirect back to settings
- Need FastAPI Google Drive OAuth to also support web `redirect_uri`

**BFF routes:**
- `src/app/api/v1/drive/route.ts` — GET status, POST set folder, DELETE disconnect
- `src/app/api/auth/google-drive/callback/route.ts` — OAuth callback

**FastAPI changes needed:**
- Modify `/auth/google-drive/start` to accept optional `redirect_uri`
- Modify `/auth/google-drive/callback` to support redirecting back to web app

### PR 2.4: Web Onboarding Wizard

**Files to create:**
- `src/app/(app)/onboarding/page.tsx` — Onboarding entry point (redirects to first incomplete step)
- `src/app/(app)/onboarding/layout.tsx` — Wizard layout with step progress
- `src/app/(app)/onboarding/instagram/page.tsx` — Step 1: Connect Instagram
- `src/app/(app)/onboarding/google-drive/page.tsx` — Step 2: Connect Google Drive
- `src/app/(app)/onboarding/media-folder/page.tsx` — Step 3: Configure media folder
- `src/app/(app)/onboarding/schedule/page.tsx` — Step 4: Set posting schedule
- `src/app/(app)/onboarding/complete/page.tsx` — Summary + activate
- `src/components/onboarding/step-progress.tsx` — Progress indicator
- `src/components/onboarding/step-layout.tsx` — Consistent step wrapper

**Logic:**
- After Telegram Login, if `onboarding_completed = false`, redirect to `/onboarding`
- Wizard reads `setup_state` from `/api/onboarding/init` to determine which steps are done
- Each step is a standalone page (can be revisited)
- Steps share UI with settings pages where possible (e.g., schedule form)
- On completion, calls `/api/onboarding/complete` and redirects to `/dashboard`

**Relationship to Mini App:**
- Web wizard replaces Mini App wizard for new web users
- Mini App wizard remains available for users who start from Telegram
- Both call the same FastAPI endpoints — no divergence

---

## Phase 3: Media Management

**Scope:** Media library browsing, pool health visibility, content management.
**Estimated PRs:** 2-3
**Dependencies:** Phase 2 complete (Google Drive connection must work from web)

### PR 3.1: Media Library

**Files to create:**
- `src/app/(app)/media/page.tsx` — Media library grid view
- `src/app/(app)/media/[id]/page.tsx` — Single media item detail
- `src/components/media/media-grid.tsx` — Filterable grid of media items
- `src/components/media/media-card.tsx` — Thumbnail + metadata card
- `src/components/media/media-filters.tsx` — Category, status, date filters
- `src/components/media/media-detail.tsx` — Full detail view with posting history
- `src/hooks/use-media.ts` — Media query hooks

**New FastAPI endpoints needed:**
- `GET /api/onboarding/media-library?chat_id=...&category=...&status=...&page=...&per_page=...` — Paginated media list with filters
- `GET /api/onboarding/media/{id}?chat_id=...` — Single media item with posting history

**BFF routes:**
- `src/app/api/v1/media/route.ts` — GET paginated list
- `src/app/api/v1/media/[id]/route.ts` — GET single item
- `src/app/api/v1/media/sync/route.ts` — POST trigger sync

### PR 3.2: Pool Health & Content Insights

**Files to create:**
- `src/app/(app)/media/health/page.tsx` — Pool health overview
- `src/components/media/pool-health-card.tsx` — Runway per category
- `src/components/media/category-breakdown.tsx` — Visual breakdown
- `src/components/media/dead-content-list.tsx` — Actionable dead content view
- `src/components/media/reuse-distribution.tsx` — Content reuse visualization

**Combines existing endpoints:**
- `GET /api/onboarding/media-stats` — Category breakdown
- `GET /api/onboarding/analytics/content-reuse` — Reuse classification
- `GET /api/onboarding/analytics/dead-content` — Never-posted items

### PR 3.3: Media Actions

**Files to create:**
- `src/components/media/sync-trigger.tsx` — Manual sync button with progress
- `src/components/media/media-actions.tsx` — Lock/unlock, categorize actions

**New FastAPI endpoints needed:**
- `POST /api/onboarding/media/{id}/lock` — Add manual hold lock
- `POST /api/onboarding/media/{id}/unlock` — Remove manual hold lock
- `POST /api/onboarding/media/{id}/recategorize` — Change category

---

## File Structure

### Final directory structure after all phases:

```
landing/src/
├── app/
│   ├── (marketing)/                    # PUBLIC - landing & setup guide
│   │   ├── layout.tsx                  # Marketing layout (header + footer)
│   │   ├── page.tsx                    # Landing page (existing)
│   │   ├── login/page.tsx              # Login page (Telegram widget)
│   │   └── setup/                      # Setup guide (existing, unchanged)
│   │       ├── layout.tsx
│   │       ├── page.tsx
│   │       ├── instagram/page.tsx
│   │       ├── meta-developer/page.tsx
│   │       ├── google-drive/page.tsx
│   │       ├── media-organize/page.tsx
│   │       └── connect/page.tsx
│   │
│   ├── (app)/                          # AUTHENTICATED - web app
│   │   ├── layout.tsx                  # App shell (sidebar + top bar)
│   │   ├── dashboard/
│   │   │   ├── page.tsx                # Dashboard overview
│   │   │   ├── analytics/page.tsx      # Analytics deep dive
│   │   │   ├── queue/page.tsx          # Queue detail
│   │   │   ├── history/page.tsx        # Posting history
│   │   │   └── health/page.tsx         # System health
│   │   ├── settings/
│   │   │   ├── page.tsx                # Settings overview
│   │   │   ├── instagram/page.tsx      # Account management
│   │   │   ├── google-drive/page.tsx   # Drive connection
│   │   │   ├── schedule/page.tsx       # Posting schedule
│   │   │   ├── categories/page.tsx     # Category mix
│   │   │   └── general/page.tsx        # Toggles & preferences
│   │   ├── media/
│   │   │   ├── page.tsx                # Media library
│   │   │   ├── health/page.tsx         # Pool health
│   │   │   └── [id]/page.tsx           # Media detail
│   │   └── onboarding/
│   │       ├── layout.tsx              # Wizard layout
│   │       ├── page.tsx                # Entry point / router
│   │       ├── instagram/page.tsx
│   │       ├── google-drive/page.tsx
│   │       ├── media-folder/page.tsx
│   │       ├── schedule/page.tsx
│   │       └── complete/page.tsx
│   │
│   ├── api/
│   │   ├── auth/
│   │   │   ├── telegram/route.ts       # Telegram Login callback
│   │   │   ├── session/route.ts        # Session check
│   │   │   ├── logout/route.ts         # Clear session
│   │   │   ├── instagram/
│   │   │   │   └── callback/route.ts   # Instagram OAuth callback
│   │   │   └── google-drive/
│   │   │       └── callback/route.ts   # Google Drive OAuth callback
│   │   ├── v1/                         # BFF proxy routes
│   │   │   ├── analytics/
│   │   │   │   └── [...endpoint]/route.ts
│   │   │   ├── dashboard/route.ts
│   │   │   ├── queue/route.ts
│   │   │   ├── history/route.ts
│   │   │   ├── health/route.ts
│   │   │   ├── settings/
│   │   │   │   ├── route.ts
│   │   │   │   ├── toggle/route.ts
│   │   │   │   ├── update/route.ts
│   │   │   │   └── schedule/route.ts
│   │   │   ├── accounts/
│   │   │   │   ├── route.ts
│   │   │   │   ├── switch/route.ts
│   │   │   │   └── [id]/route.ts
│   │   │   ├── drive/route.ts
│   │   │   └── media/
│   │   │       ├── route.ts
│   │   │       ├── sync/route.ts
│   │   │       └── [id]/route.ts
│   │   └── waitlist/route.ts           # Existing (unchanged)
│   │
│   ├── layout.tsx                      # Root layout (fonts, providers)
│   └── globals.css                     # Existing (unchanged)
│
├── components/
│   ├── ui/                             # shadcn components (existing)
│   ├── layout/                         # Existing (header, footer)
│   ├── landing/                        # Existing (hero, features, etc.)
│   ├── setup/                          # Existing (setup guide components)
│   ├── auth/                           # NEW
│   │   ├── telegram-login-button.tsx
│   │   └── user-menu.tsx
│   ├── app/                            # NEW
│   │   ├── sidebar.tsx
│   │   ├── workspace-picker.tsx
│   │   └── page-header.tsx
│   ├── dashboard/                      # NEW
│   │   ├── approval-latency-chart.tsx
│   │   ├── team-performance-table.tsx
│   │   ├── content-reuse-chart.tsx
│   │   ├── category-drift-chart.tsx
│   │   ├── schedule-preview.tsx
│   │   ├── service-health-grid.tsx
│   │   ├── dead-content-table.tsx
│   │   ├── posting-history-table.tsx
│   │   └── queue-table.tsx
│   ├── settings/                       # NEW
│   │   ├── schedule-form.tsx
│   │   ├── category-mix-editor.tsx
│   │   ├── toggle-card.tsx
│   │   ├── instagram-account-card.tsx
│   │   ├── add-account-form.tsx
│   │   ├── connect-instagram-button.tsx
│   │   ├── drive-connection-card.tsx
│   │   └── media-folder-input.tsx
│   ├── media/                          # NEW
│   │   ├── media-grid.tsx
│   │   ├── media-card.tsx
│   │   ├── media-filters.tsx
│   │   ├── media-detail.tsx
│   │   ├── pool-health-card.tsx
│   │   ├── category-breakdown.tsx
│   │   ├── dead-content-list.tsx
│   │   ├── reuse-distribution.tsx
│   │   ├── sync-trigger.tsx
│   │   └── media-actions.tsx
│   └── onboarding/                     # NEW
│       ├── step-progress.tsx
│       └── step-layout.tsx
│
├── hooks/                              # NEW
│   ├── use-session.ts
│   ├── use-workspace.ts
│   ├── use-analytics.ts
│   ├── use-settings.ts
│   ├── use-accounts.ts
│   └── use-media.ts
│
├── providers/                          # NEW
│   ├── query-provider.tsx
│   └── workspace-provider.tsx
│
├── lib/
│   ├── db.ts                           # Existing
│   ├── schema.ts                       # Existing
│   ├── telegram.ts                     # Existing
│   ├── utils.ts                        # Existing
│   ├── auth.ts                         # NEW — JWT session management
│   ├── telegram-auth.ts                # NEW — Login Widget hash validation
│   └── api-client.ts                   # NEW — Server-side FastAPI client
│
├── config/
│   └── site.ts                         # Existing (update nav items)
│
└── middleware.ts                        # NEW — Route protection
```

---

## Database & Schema Changes

### Landing Site Database (Drizzle)

**No schema changes to `waitlist_signups`.** The landing site database (Drizzle/Neon) is separate from the backend database (SQLAlchemy/Neon). They may share the same Neon project but use different databases or schemas.

**Option A (Recommended):** Landing site does NOT read/write the backend database directly. All data flows through the BFF → FastAPI path. This keeps the two ORMs isolated and avoids dual-write issues.

**Option B (Considered, rejected):** Add Drizzle schema definitions mirroring SQLAlchemy models. Rejected — creates schema drift risk between two ORMs managing the same tables.

### Backend Database (SQLAlchemy) — New Endpoints Required

**Phase 1:**
- New endpoint: `GET /api/onboarding/user-chats` — query `posting_history` and `user_interactions` for distinct `chat_settings_id` where `user_id` matches, join to `chat_settings` for display info
- No schema changes. Existing tables have all needed data.

**Phase 2:**
- No schema changes. OAuth flows reuse existing `instagram_accounts` and `api_tokens` tables.
- FastAPI OAuth routes need `redirect_uri` parameter support (code change, not schema change).

**Phase 3:**
- New endpoints for media item detail and actions (lock/unlock/recategorize)
- No schema changes. `media_items`, `media_posting_locks` tables already support these operations.

### Future Consideration: `chat_members` Table

If explicit access control is needed (vs. inferring from interaction history):

```sql
CREATE TABLE chat_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_settings_id UUID REFERENCES chat_settings(id),
    user_id UUID REFERENCES users(id),
    role VARCHAR(50) DEFAULT 'member',  -- 'admin', 'member', 'viewer'
    added_at TIMESTAMP DEFAULT now(),
    UNIQUE(chat_settings_id, user_id)
);
```

This is **not needed for Phase 1-3** but would be required for team management features.

---

## Mini App Migration Matrix

| Feature | Current Location | Phase | Web Location | Stays in Telegram? |
|---------|-----------------|-------|--------------|-------------------|
| **Onboarding wizard** | Mini App (`wizard` mode) | Phase 2 | `/onboarding/*` | Yes — both paths work |
| **Dashboard home** | Mini App (`home` mode) | Phase 1 | `/dashboard` | Deprecated after Phase 1 |
| **Instagram OAuth** | Mini App + FastAPI | Phase 2 | `/settings/instagram` | No — web only |
| **Google Drive OAuth** | Mini App + FastAPI | Phase 2 | `/settings/google-drive` | No — web only |
| **Media folder config** | Mini App | Phase 2 | `/settings/google-drive` | No — web only |
| **Schedule config** | Mini App | Phase 2 | `/settings/schedule` | No — web only |
| **Account switching** | Mini App + Telegram buttons | Phase 2 | `/settings/instagram` | Yes — quick switch via Telegram |
| **Toggle settings** | Mini App + Telegram `/setup` | Phase 2 | `/settings/general` | Yes — quick toggles via Telegram |
| **Queue preview** | Mini App | Phase 1 | `/dashboard/queue` | No — web has richer view |
| **History view** | Mini App | Phase 1 | `/dashboard/history` | No — web has richer view |
| **Media stats** | Mini App | Phase 1 | `/dashboard/analytics` | No — web has richer view |
| **Post approval** | Telegram buttons | Never | N/A | **Yes — Telegram only** |
| **Skip/reject** | Telegram buttons | Never | N/A | **Yes — Telegram only** |
| **Auto-post trigger** | Telegram buttons | Never | N/A | **Yes — Telegram only** |
| **Quick status check** | Telegram `/status` | Never | N/A | **Yes — Telegram only** |
| **Force next post** | Telegram `/next` | Never | N/A | **Yes — Telegram only** |

### Mini App Deprecation Path

1. **Phase 1 complete:** Mini App dashboard mode becomes secondary. Users directed to web for analytics.
2. **Phase 2 complete:** Mini App wizard becomes secondary. New users directed to web for onboarding. Mini App still works but stops receiving feature updates.
3. **Phase 3 complete:** Mini App can be simplified to just an "Open Dashboard" link. Telegram `/start` command updated to include web dashboard URL.
4. **Long-term:** Mini App serves as a redirect to the web app, or is removed entirely. Telegram retains only action commands (approve, skip, reject, next).

---

## Environment & Deployment

### New Environment Variables (Vercel)

| Variable | Phase | Purpose |
|----------|-------|---------|
| `TELEGRAM_BOT_USERNAME` | 1 | Login Widget configuration |
| `JWT_SECRET` | 1 | Session JWT signing key |
| `STORYDUMP_API_URL` | 1 | FastAPI backend URL (Railway) |
| `ALLOW_SIGNUP` | 1 | `false` for invite-only, `true` for open registration |

### Existing Variables (already on Vercel)

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Neon PostgreSQL (waitlist) |
| `TELEGRAM_BOT_TOKEN` | Already used for admin notifications; also needed for Login Widget hash validation |
| `ADMIN_TELEGRAM_CHAT_ID` | Admin notifications |

### Deployment Architecture

```
                    ┌─────────────┐
                    │   Vercel     │
                    │  (Next.js)   │
                    │              │
                    │ Landing Page │
                    │ + Web App    │
                    │ + BFF API    │
                    └──────┬───────┘
                           │ HTTPS (server-side)
                           │ Signed URL tokens
                           ▼
                    ┌─────────────┐
                    │   Railway   │
                    │  (FastAPI)  │
                    │              │
                    │  API Server  │
                    │  + Worker    │
                    │  + Bot       │
                    └──────┬───────┘
                           │
                           ▼
                    ┌─────────────┐
                    │    Neon      │
                    │ PostgreSQL   │
                    └─────────────┘
```

### CORS Updates

FastAPI CORS needs to add the Vercel deployment URL:

```python
allow_origins=[
    settings.OAUTH_REDIRECT_BASE_URL,
    "https://storydump.vercel.app",  # or custom domain
    "http://localhost:3000",             # local dev
]
```

However, since we're using the BFF pattern, CORS is only needed if we later decide to make direct client-side calls. For Phase 1-3, the BFF handles all communication server-side.

---

## Risks & Dependencies

### High Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Telegram Login Widget deprecation** | Auth breaks entirely | Widget has been stable since 2018. Fallback plan: add email/password auth as secondary method. Monitor Telegram Bot API changelog. |
| **FastAPI auth model mismatch** | BFF can't authenticate to FastAPI | The signed URL token mechanism already exists and is tested. BFF generates tokens using the same bot token. Low actual risk. |
| **OAuth redirect URI complexity** | Instagram/Google OAuth callbacks break | Phase 2 requires FastAPI to support dynamic `redirect_uri`. Careful implementation needed — validate against allowlist of known origins. |

### Medium Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| **User-to-chat mapping gaps** | Users can't find their workspace | `user-chats` endpoint derives membership from interaction history. Users who were added to a chat but never interacted won't appear. Can supplement with `chat_members` table later. |
| **Two ORM / two deployment drift** | Schema changes in one place not reflected in other | Strict rule: landing site never touches backend DB directly. All data flows through FastAPI. Schema is SQLAlchemy's concern only. |
| **Bundle size growth** | Landing page performance regression | Route groups ensure landing page bundle is separate from app bundle. Verify with `next build` output. TanStack Query + Recharts add ~50KB gzipped. |
| **Session token in Vercel serverless** | JWT validation adds latency | JWT validation is CPU-only (no DB call). <1ms overhead. No concern for serverless cold starts. |

### Low Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Mini App and web app diverge** | Inconsistent user experience | Both call same FastAPI endpoints. UI may differ but data/behavior stays consistent. |
| **Invite-only enforcement** | Users try to log in without being in `users` table | Clear "Invite-only" message on login failure. `ALLOW_SIGNUP` env var for later public launch. |

### Dependencies

| Dependency | Blocks | Notes |
|------------|--------|-------|
| Telegram Bot Token on Vercel | Phase 1 | Already used for waitlist notifications — just needs verification that the same token works for Login Widget |
| FastAPI `user-chats` endpoint | Phase 1 PR 1.2 | New endpoint needed on backend. Can be a simple query — fast to implement. |
| FastAPI OAuth `redirect_uri` support | Phase 2 | Requires careful changes to OAuth routes. Security-sensitive — must validate redirect URIs against allowlist. |
| FastAPI media list/detail endpoints | Phase 3 | New endpoints for paginated media browsing. Straightforward CRUD. |

---

## Open Questions

1. **Custom domain?** Should the web app be at `app.storydump.app` or stay on the Vercel default domain? Affects OAuth redirect URIs and Login Widget configuration.

2. **Chart library preference?** Plan assumes Recharts. Alternatives: Chart.js (lighter), Nivo (more beautiful), Tremor (shadcn-native). Worth a quick spike.

3. **Real-time updates?** Phase 1 uses polling (TanStack Query refetch intervals). Should Phase 2+ add WebSocket or SSE for live queue updates? Would require FastAPI WebSocket support.

4. **Team management?** Current plan defers explicit team management (adding/removing users from a workspace). When does this become a priority?

5. **Mini App sunset timeline?** After Phase 2, the Mini App is functionally redundant for management. Should we actively remove it or let it exist indefinitely as a fallback?

6. **Mobile app?** The web app will be responsive, but is a native Telegram Mini App replacement (or PWA) on the roadmap?
