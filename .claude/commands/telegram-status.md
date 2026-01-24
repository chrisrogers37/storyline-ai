---
description: "Check Telegram bot activity and queue status on the Pi"
---

Query the Raspberry Pi to show current Telegram bot status with full bidirectional visibility. Run these commands via SSH and present a unified activity feed.

## 1. Recent Bot Activity (bidirectional - last 15 interactions)

This shows BOTH incoming (user actions) AND outgoing (bot responses):

```bash
ssh crogberrypi "psql -h localhost -U storyline_user -d storyline_ai -c \"
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
\""
```

## 2. Current Queue (next 5 scheduled)

```bash
ssh crogberrypi "psql -h localhost -U storyline_user -d storyline_ai -c \"
SELECT
    q.scheduled_for,
    m.file_name,
    m.category
FROM posting_queue q
JOIN media_items m ON q.media_item_id = m.id
WHERE q.status = 'pending'
ORDER BY q.scheduled_for
LIMIT 5;
\""
```

## 3. Recent Posts (last 5)

```bash
ssh crogberrypi "psql -h localhost -U storyline_user -d storyline_ai -c \"
SELECT
    posted_at,
    posting_method,
    m.file_name
FROM posting_history h
JOIN media_items m ON h.media_item_id = m.id
ORDER BY h.posted_at DESC
LIMIT 5;
\""
```

## 4. Service Health

```bash
ssh crogberrypi "systemctl is-active storyline-ai && journalctl -u storyline-ai --no-pager -n 3 --since '1 hour ago' 2>/dev/null | grep -iE 'error|warning' | head -5 || echo 'No recent errors'"
```

## Presenting Results

Format the output as a clear activity timeline:

```
## Telegram Bot Status

**Service:** ✓ active

### Recent Activity (↓ newest first)
| Time | Direction | Action | Detail |
|------|-----------|--------|--------|
| 16:05 | → BOT | photo_notification | IMG_1234.jpg |
| 16:05 | ← USER | autopost | IMG_1234.jpg |
| 16:06 | → BOT | caption_update | "✅ Posted to Instagram..." |

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
