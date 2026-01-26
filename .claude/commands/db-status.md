---
description: "Check database status and key metrics (safe, read-only)"
---

Run these safe, read-only queries on the Raspberry Pi database:

## 1. Queue Status

```bash
ssh crogberrypi "psql -h localhost -U storyline_user -d storyline_ai -c \"
SELECT
    status,
    COUNT(*) as count,
    MIN(scheduled_for) as earliest,
    MAX(scheduled_for) as latest
FROM posting_queue
GROUP BY status
ORDER BY status;
\""
```

## 2. Recent Posting Activity

```bash
ssh crogberrypi "psql -h localhost -U storyline_user -d storyline_ai -c \"
SELECT
    DATE(posted_at) as date,
    posting_method,
    COUNT(*) as posts
FROM posting_history
WHERE posted_at > NOW() - INTERVAL '7 days'
GROUP BY DATE(posted_at), posting_method
ORDER BY date DESC;
\""
```

## 3. Instagram Accounts

```bash
ssh crogberrypi "psql -h localhost -U storyline_user -d storyline_ai -c \"
SELECT
    display_name,
    instagram_username,
    is_active,
    created_at
FROM instagram_accounts
ORDER BY created_at;
\""
```

## 4. Media Library Stats

```bash
ssh crogberrypi "psql -h localhost -U storyline_user -d storyline_ai -c \"
SELECT
    category,
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE is_active) as active,
    AVG(times_posted)::numeric(10,1) as avg_posts
FROM media_items
GROUP BY category
ORDER BY total DESC;
\""
```

## 5. Token Health

```bash
ssh crogberrypi "psql -h localhost -U storyline_user -d storyline_ai -c \"
SELECT
    service_name,
    token_type,
    ia.display_name as account,
    t.expires_at,
    CASE
        WHEN t.expires_at IS NULL THEN 'No expiry'
        WHEN t.expires_at < NOW() THEN 'EXPIRED'
        WHEN t.expires_at < NOW() + INTERVAL '7 days' THEN 'Expiring soon'
        ELSE 'OK'
    END as status
FROM api_tokens t
LEFT JOIN instagram_accounts ia ON t.instagram_account_id::uuid = ia.id
ORDER BY t.expires_at;
\""
```

## Report Format

Present as a dashboard:
```
## Database Status

### Queue
| Status | Count | Earliest | Latest |
|--------|-------|----------|--------|

### Recent Posts (7 days)
| Date | Method | Count |
|------|--------|-------|

### Accounts
| Name | Username | Active |
|------|----------|--------|

### Media Library
| Category | Active | Avg Posts |
|----------|--------|-----------|

### Token Health
| Account | Expires | Status |
|---------|---------|--------|
```

**REMINDER**: These are READ-ONLY queries. Never run INSERT/UPDATE/DELETE.
