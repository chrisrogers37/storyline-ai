# Project Mission — Storyline AI

## What this project is
A social media automation platform that manages the full content lifecycle — from sourcing and scheduling to posting and performance analysis. Currently a Telegram bot for Instagram Stories with Google Drive as the content hub. Supports multi-account management for small teams.

## What it's becoming
The single control center for social media content. Upload or pull content from anywhere (Drive, Instagram history, product catalogs, UGC), schedule and post across platforms, track what performs, and optimize automatically. Telegram stays as the fast approval layer. A web dashboard handles everything else — analytics, content management, onboarding, and sharing. Simple enough for a meme page, powerful enough for a dropshipping store.

## North star
Zero-friction content automation — from source to posted to optimized, with as few manual steps as possible.

## Core Mental Model

The entire product — data model, UI, and bot behavior — is anchored to this hierarchy:

```
User (Telegram identity)
  → manages multiple Instances (group chats)
    → each Instance has: social media accounts, media sources, queue, schedule, settings
    → media sources contain: multiple files
```

**Surfaces map directly to this model:**

- **DM** = management console (user-level view of all instances)
- **Group chat** = where the instance lives (team review + posting)
- **Web dashboard** = instance picker → instance management

A user sees their instance list first. Tapping an instance drills into its config, media, and posting state. Every command, screen, and API endpoint should know whether it operates at the user level or the instance level — and behave accordingly.

## Guiding principles
- **Simple over powerful.** If a feature needs explanation, simplify it.
- **Web-first for management, Telegram-first for actions.** Approval flows and quick decisions live in Telegram. Everything else belongs on the web dashboard.
- **Closed loop.** Every post generates data that improves the next post.
- **Onboarding should take minutes, not hours.** No API keys, no 10 systems.
- **Build for 2 teams today, design for 200.**

## In bounds for autonomous work
- Bug fixes and UX polish
- Instagram API integration improvements
- Content pipeline enhancements (new sources, better scheduling)
- Analytics and performance tracking
- Test coverage and code quality
- Telegram formatting and flow improvements

## Requires approval
- New platform integrations (TikTok, Twitter, Reels)
- Shopify/product catalog integration
- Web dashboard architecture decisions
- Auth/login flow changes
- Database schema changes
- Anything that changes the multi-account model

## Success metrics
- Time from content creation to posted: decreasing
- Manual steps per post: decreasing
- Repeat usage (daily active posting): increasing
- Onboarding time for new account: under 5 minutes
