# Monitoring & Alerting

## Overview

Storyline AI runs on a Raspberry Pi with systemd service management. This guide covers monitoring the service health and common metrics.

> **Note on paths**: This guide uses `/home/pi/` as the example home directory. Replace with your actual home directory (e.g., `/home/crog/`).

---

## Service Status

### Check Service Health

```bash
# Is the service running?
ssh crogberrypi "systemctl is-active storyline-ai"

# Detailed status
ssh crogberrypi "systemctl status storyline-ai"

# Recent logs (last 50 lines)
ssh crogberrypi "journalctl -u storyline-ai -n 50 --no-pager"

# Follow logs in real-time
ssh crogberrypi "journalctl -u storyline-ai -f"
```

### Common Status Indicators

| Status | Meaning | Action |
|--------|---------|--------|
| `active (running)` | Service is healthy | None |
| `inactive (dead)` | Service stopped | Check logs, restart |
| `failed` | Service crashed | Check logs for error |
| `activating` | Service starting | Wait, check if it completes |

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
# Errors in last hour
ssh crogberrypi "journalctl -u storyline-ai --since '1 hour ago' | grep -c ERROR"

# Error details
ssh crogberrypi "journalctl -u storyline-ai --since '1 hour ago' | grep ERROR"
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

Create a simple health check that can be run via cron:

```bash
#!/bin/bash
# /home/pi/scripts/health_check.sh

# Check service
if ! systemctl is-active --quiet storyline-ai; then
    echo "CRITICAL: storyline-ai service is not running"
    exit 2
fi

# Check for stuck posts
STUCK=$(psql -U storyline_user -d storyline_ai -t -c \
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
| Service logs | `journalctl -u storyline-ai` |
| Application logs | Configured via `LOG_LEVEL` in `.env` |
| PostgreSQL logs | `/var/log/postgresql/` |

---

## Restart Procedures

```bash
# Graceful restart
ssh crogberrypi "sudo systemctl restart storyline-ai"

# Check it came back up
ssh crogberrypi "systemctl status storyline-ai"

# If stuck, force kill and restart
ssh crogberrypi "sudo systemctl kill storyline-ai && sudo systemctl start storyline-ai"
```
