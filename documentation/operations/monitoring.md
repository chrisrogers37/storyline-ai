# Monitoring & Alerting

## Overview

Storydump runs on Railway with a Neon PostgreSQL database. This guide covers monitoring the service health and common metrics.

---

## Service Status

### Check Service Health

```bash
# Check Railway service status via dashboard
# https://railway.app/dashboard → Select project → View service logs

# Or via Railway CLI
railway logs --service worker
railway logs --service web

# Run health check via Railway shell
railway shell --service worker
storydump-cli check-health
```

### Common Status Indicators

| Status | Meaning | Action |
|--------|---------|--------|
| `Active` | Service is healthy | None |
| `Deploying` | New deployment in progress | Wait for completion |
| `Crashed` | Service crashed | Check logs for error |
| `Sleeping` | Service scaled to zero | Check Railway settings |

---

## Key Metrics to Monitor

### 1. Queue Health

```sql
-- Pending posts count
SELECT COUNT(*) FROM posting_queue WHERE status = 'pending';

-- Stuck posts (scheduled but not processed)
SELECT COUNT(*) FROM posting_queue
WHERE status = 'pending'
AND scheduled_for < NOW() - INTERVAL '1 hour';

-- Failed posts
SELECT COUNT(*) FROM posting_queue WHERE status = 'failed';
```

### 2. Posting Rate

```sql
-- Posts per day (last 7 days)
SELECT
    DATE(posted_at) as date,
    COUNT(*) as posts
FROM posting_history
WHERE posted_at > NOW() - INTERVAL '7 days'
GROUP BY DATE(posted_at)
ORDER BY date DESC;
```

### 3. Token Health

```sql
-- Check token expiry
SELECT
    service_name,
    ia.display_name,
    expires_at,
    CASE
        WHEN expires_at < NOW() THEN 'EXPIRED'
        WHEN expires_at < NOW() + INTERVAL '7 days' THEN 'EXPIRING SOON'
        ELSE 'OK'
    END as status
FROM api_tokens t
LEFT JOIN instagram_accounts ia ON t.instagram_account_id::uuid = ia.id;
```

### 4. Error Rate

```bash
# Check errors in Railway logs
railway logs --service worker | grep -c ERROR

# Or view errors directly in Railway dashboard log viewer
# Filter by "ERROR" in the search bar
```

---

## Alerting Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Queue stuck posts | > 1 | > 5 |
| Token expires in | < 14 days | < 3 days |
| Error rate (per hour) | > 5 | > 20 |
| Service restarts (per day) | > 1 | > 3 |

---

## Health Check Script

Run a health check via the Railway shell or schedule via external monitoring:

```bash
#!/bin/bash
# health_check.sh - Run via Railway shell or external cron

# Check for stuck posts
STUCK=$(psql "$DATABASE_URL" -t -c \
    "SELECT COUNT(*) FROM posting_queue WHERE status='pending' AND scheduled_for < NOW() - INTERVAL '1 hour'")

if [ "$STUCK" -gt 5 ]; then
    echo "CRITICAL: $STUCK stuck posts in queue"
    exit 2
elif [ "$STUCK" -gt 1 ]; then
    echo "WARNING: $STUCK stuck posts in queue"
    exit 1
fi

echo "OK: Service healthy"
exit 0
```

---

## Log Locations

| Log | Location |
|-----|----------|
| Worker logs | Railway dashboard or `railway logs --service worker` |
| Web/API logs | Railway dashboard or `railway logs --service web` |
| Application logs | Configured via `LOG_LEVEL` env var (stdout, captured by Railway) |
| PostgreSQL logs | Neon dashboard |

---

## Restart Procedures

```bash
# Restart via Railway CLI
railway restart --service worker

# Or restart via Railway dashboard:
# Project → Service → Settings → Restart

# Redeploy (pulls latest code and restarts)
railway up --service worker
```
