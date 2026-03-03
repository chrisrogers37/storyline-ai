---
description: "Check Telegram bot activity and queue status"
---

Query the Neon production database to show current Telegram bot status with full bidirectional visibility. The user must provide the DATABASE_URL or it should be available as an environment variable.

## 1. Recent Bot Activity (bidirectional - last 15 interactions)

This shows BOTH incoming (user actions) AND outgoing (bot responses):

```bash
psql "$DATABASE_URL" -c "
SELECT
    created_at,
    interaction_type,
    interaction_name,
    CASE
        WHEN interaction_type = 'bot_response' THEN '→ BOT'
        ELSE '← USER'
    END as direction,
    COALESCE(context->>'media_filename', context->>'action', '') as detail,
    LEFT(COALESCE(context->>'caption', ''), 50) as caption_preview
FROM user_interactions
ORDER BY created_at DESC
LIMIT 15;
"
```

## 2. Current Queue (next 5 scheduled)

```bash
psql "$DATABASE_URL" -c "
SELECT
    q.scheduled_for,
    m.file_name,
    m.category
FROM posting_queue q
JOIN media_items m ON q.media_item_id = m.id
WHERE q.status = 'pending'
ORDER BY q.scheduled_for
LIMIT 5;
"
```

## 3. Recent Posts (last 5)

```bash
psql "$DATABASE_URL" -c "
SELECT
    posted_at,
    posting_method,
    m.file_name
FROM posting_history h
JOIN media_items m ON h.media_item_id = m.id
ORDER BY h.posted_at DESC
LIMIT 5;
"
```

## 4. Service Health

```bash
psql "$DATABASE_URL" -c "
SELECT
    method_name,
    status,
    started_at,
    result_summary
FROM service_runs
ORDER BY started_at DESC
LIMIT 10;
"
```

## Presenting Results

Format the output as a clear activity timeline:

```
## Telegram Bot Status

**Deployment:** Railway (worker + API)

### Recent Activity (newest first)
| Time | Direction | Action | Detail |
|------|-----------|--------|--------|
| 16:05 | → BOT | photo_notification | IMG_1234.jpg |
| 16:05 | ← USER | autopost | IMG_1234.jpg |
| 16:06 | → BOT | caption_update | "Posted to Instagram..." |

### Queue (Next 5)
| Scheduled | File | Category |
|-----------|------|----------|
| ...       | ...  | ...      |

### Recent Posts
| Posted | Method | File |
|--------|--------|------|
| ...    | ...    | ...  |
```

**REMINDER**: Do NOT run any posting commands. This is read-only status checking.
