# Landing Site — Overview

**Session**: landing-site
**Date**: 2026-03-04
**Theme**: Marketing landing page + waitlist + onboarding guide for public launch

## Context

Storyline AI currently has no public-facing discovery path. The only way to use the product is through the Telegram bot, which requires knowing it exists. This plan creates a marketing website that sells the product, captures waitlist signups, and provides detailed setup documentation for accepted users.

**Positioning**: "You already have hundreds of pieces of content. Storyline keeps them rotating through your Instagram Stories automatically — powered by Telegram."

**Target user**: Established creators and small brand owners with large content libraries who want to keep their Stories active without daily effort.

## Phases

| # | Title | Effort | Description |
|---|-------|--------|-------------|
| 01 | Project Scaffold | Small | Next.js 16 project, Tailwind, shadcn/ui, Vercel deployment |
| 02 | Landing Page | Medium | Hero, How It Works, Features, Telegram Preview, Pricing, FAQ |
| 03 | Waitlist System | Small | Neon migration, API route, form component, Telegram notification |
| 04 | Onboarding Guide | Medium | Unlisted /setup/* pages covering all prerequisites |

## Dependency Graph

```
01 Project Scaffold
 ├──▶ 02 Landing Page
 ├──▶ 03 Waitlist System
 └──▶ 04 Onboarding Guide
```

- Phase 01 must complete first (project foundation)
- Phases 02, 03, 04 can run in parallel after 01
- Phase 03 has a minor dependency on 02 (waitlist form lives on the landing page), but the API/DB work is independent

## Tech Stack

Based on the user's existing projects (tl-co, really-personal-finance, paige-success-hub):

- **Framework**: Next.js 16, App Router, TypeScript
- **Styling**: Tailwind CSS 4 + shadcn/ui (Radix + class-variance-authority)
- **Database**: Drizzle ORM → Neon PostgreSQL (same Neon instance as storyline-ai backend)
- **Deployment**: Vercel (free tier)
- **Domain**: storyline.ai (or fallback TBD)
- **Path aliases**: `@/*` → `src/*`

## Architecture Decision: Same DB, Separate App

The landing site connects to the **same Neon database** as the Python backend for the waitlist table. This avoids spinning up a second database. The landing site only needs write access to one table (`waitlist_signups`) and read access to nothing — minimal surface area.

The waitlist API route also sends a Telegram notification to the admin via the existing bot token (passed as an env var to Vercel).

## Estimated Total Effort

~3-5 days of focused work across all 4 phases.

## Implementation

Run `/implement-plan documentation/planning/phases/landing-site_2026-03-04/` to begin. Each phase doc contains file-level specifications, acceptance criteria, and testing requirements.
