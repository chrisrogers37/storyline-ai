# Feed & Queue Feature Research

**Date**: 2026-03-08
**Branch**: `claude/research-feed-queue-features-4lJnj`
**Status**: Research & Planning

---

## Workstreams

This research session covers three related but independent workstreams for improving the posting workflow:

| # | Workstream | Focus | Doc |
|---|-----------|-------|-----|
| 1 | [Live Story Visibility](./01_live_story_visibility.md) | Fetch & display currently-live Instagram stories | Read-only API integration |
| 2 | [Feed Reset](./02_feed_reset.md) | Clear live stories from Instagram before a fresh posting day | Blocked — DELETE not available |
| 3 | [Queue Enhancements](./03_queue_enhancements.md) | Improve queue management, visibility, and control | Telegram + CLI improvements |

## Context

These features were identified to improve the daily posting workflow:
- **Visibility gap**: No way to see what's currently live on Instagram without opening the app
- **Fresh start**: Desire to clear old stories before starting a new posting cycle
- **Queue control**: Better tools for managing and previewing the posting queue

## API Research Summary

Research into the Meta Graph API (v22.0) confirmed:
- `GET /{ig-user-id}/stories` — returns currently-live stories (within 24h window) ✅
- `DELETE /{ig-media-id}` — **does NOT exist** for stories ❌
- Rate limits: ~200 reads/hour (generous), 100 publishes/24h rolling window
- Required permissions: `instagram_basic`, `pages_show_list`, `pages_read_engagement`
