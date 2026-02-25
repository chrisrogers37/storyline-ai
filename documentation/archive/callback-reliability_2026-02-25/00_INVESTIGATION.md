# Investigation: Callback Reliability — 2026-02-25

## Problem Statement

Clicking "Skip" in the Telegram bot intermittently doesn't react — no pulse animation, no status update. The post eventually appears as skipped. The issue is intermittent and has happened on multiple occasions.

## Platform

- **Deployment**: Railway (worker + API services)
- **Database**: Neon PostgreSQL (us-east-1)
- **Worker Service**: `9af6a3ec-640e-4fec-8ae6-22b43b83c466`
- **API Service**: `ceab816e-ac42-4521-9e97-800d06ef17b6` (idle, no traffic)

## Evidence Gathered

### Railway Logs

1. **SSL Connection Drops** — Two `psycopg2.OperationalError: SSL connection has been closed unexpectedly` errors at 12:02 and 12:15 UTC, both on InteractionService logging paths (`log_bot_response` and `log_callback`).

2. **Connection Pool Exhaustion** — `QueuePool limit of size 10 overflow 10 reached, connection timed out, timeout 30.00` at 04:42-04:50 UTC during rapid-fire autopost callbacks.

3. **Silent Skip Failure** — Skip callback at 04:39:50 for item already auto-posted at 04:39:32. No "Post skipped" log line, no user feedback — queue item was already deleted.

4. **Duplicate Scheduler Runs** — `process_pending_posts` fires twice per minute (two active chat_settings rows, one production + one dev/test).

### Database State

- **Queue**: 165 pending items, no orphans, pipeline healthy
- **Connections**: 13 total (10 idle, 2 idle-in-transaction, 1 active)
- **Leaked Transactions**: 2 sessions idle-in-transaction for 1-2 minutes on `user_interactions` SELECT queries
- **Chat Settings**: 2 rows — production (dry_run=false, active) + test (dry_run=true, no account)
- **Last Successful Post**: 13:17 UTC via Instagram API

### Code Trace

- `_handle_callback()` calls `query.answer()` (line 580) which provides NO visual feedback
- `complete_queue_action()` acquires an async lock, then runs synchronous DB ops (history create, queue delete) BEFORE editing the message caption (line 112)
- `InteractionService` does NOT extend `BaseService` — invisible to `cleanup_transactions()`
- `InteractionService.interaction_repo` sessions are never committed/rolled back after callbacks
- `pool_pre_ping=True` protects managed pool connections, but leaked InteractionService sessions bypass this

## Root Cause Analysis

| # | Category | Finding | Confidence | Evidence |
|---|----------|---------|------------|----------|
| 1 | Connection Leak | InteractionService sessions leak "idle in transaction" — NOT cleaned by cleanup_transactions() because it doesn't extend BaseService | High | 2 idle-in-transaction sessions on user_interactions; code confirms InteractionService skipped by cleanup |
| 2 | Connection Pool | Pool exhaustion during concurrent operations (autopost batch, DB writes, interaction logging) | High | Logs: "QueuePool limit...reached, timeout 30.00" |
| 3 | SSL Staleness | Neon drops idle SSL connections; InteractionService's leaked sessions hit stale connections | Medium | 2 SSL errors on InteractionService paths; pool_pre_ping can't help leaked sessions |
| 4 | Race Condition | Autopost deletes queue item before skip callback runs — skip silently fails | Medium | Log gap: item auto-posted at 04:39:32, skip at 04:39:50, no completion log |
| 5 | UX Timing | Visual feedback (caption edit) happens only AFTER all sync DB ops | Medium | Code: edit_message_caption at line 112, after history_repo.create + queue_repo.delete |

## Fix Proposals

| # | Fix | Impact | Effort | Risk |
|---|-----|--------|--------|------|
| 1 | Include InteractionService in cleanup_transactions() | High | Low | Low |
| 2 | Add early "processing" feedback before DB operations | Medium | Low | Low |
| 3 | Add try/except with retry-once on OperationalError in core callback DB ops | Medium | Low | Low |
| 4 | Handle "already completed" race gracefully with clear user feedback | Low | Low | Low |
| 5 | Fix duplicate scheduler runs for dry_run_mode chats | Low | Low | Low |

## Timeline of Events (2026-02-25)

| Time (UTC) | Event |
|------------|-------|
| 04:32:56 | Worker deployed (latest deployment) |
| 04:34-04:39 | Queue items sent to Telegram |
| 04:39:17 | Autopost callback received for item 05015eb1 |
| 04:39:32 | Auto-posted to Instagram (story_id: 18237795982307044) |
| 04:39:50 | Skip callback for same item — silently fails (already deleted) |
| 04:42-04:50 | Connection pool exhaustion during batch autopost |
| 12:02:20 | SSL drop on bot_response logging |
| 12:15:49 | SSL drop on skip callback logging (skip itself succeeded) |
| 13:17:12 | Last successful Instagram API post |
