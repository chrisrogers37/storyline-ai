# Troubleshooting Guide

## Quick Diagnostics

```bash
# One-liner health check via Railway shell
railway shell --service worker -c "storydump-cli check-health"

# Or check logs for recent errors
railway logs --service worker | grep -i error | tail -20
```

---

## Common Issues

### 1. Service Won't Start

**Symptoms**: Railway shows `Crashed` status or repeated restarts

**Diagnosis**:
```bash
railway logs --service worker | tail -50
```

**Common Causes**:

| Error | Cause | Fix |
|-------|-------|-----|
| `ModuleNotFoundError` | Missing dependency | Check `requirements.txt` and build command |
| `Connection refused` | Database not reachable | Check `DATABASE_URL` and Neon status |
| `Permission denied` | Environment misconfiguration | Verify env vars in Railway dashboard |
| `Invalid token` | Expired/corrupt token | Re-authenticate via Telegram bot |

---

### 2. Posts Not Going Out

**Symptoms**: Queue has pending items but nothing posts

**Diagnosis**:
```sql
-- Check for stuck posts
SELECT id, scheduled_for, status, error_message
FROM posting_queue
WHERE scheduled_for < NOW()
ORDER BY scheduled_for DESC
LIMIT 10;
```

**Common Causes**:

| Cause | Check | Fix |
|-------|-------|-----|
| Dry run enabled | `chat_settings.dry_run_mode` | Toggle off in /settings |
| Instagram API disabled | `chat_settings.enable_instagram_api` | Toggle on in /settings |
| Token expired | `api_tokens.expires_at` | Refresh token |
| Rate limited | Check logs for 429 | Wait or reduce frequency |
| Wrong account selected | `chat_settings.active_instagram_account_id` | Switch account |

---

### 3. Telegram Bot Not Responding

**Symptoms**: Commands don't work, no responses

**Diagnosis**:
```bash
# Check worker service is running
railway logs --service worker | grep -i telegram

# Test bot token
curl "https://api.telegram.org/bot<TOKEN>/getMe"
```

**Common Causes**:

| Cause | Fix |
|-------|-----|
| Service crashed | Restart via Railway dashboard |
| Bot token invalid | Check `TELEGRAM_BOT_TOKEN` env var in Railway |
| Webhook conflict | Only one instance should run |
| Network issues | Check Railway service status |

---

### 4. Token Refresh Failures

**Symptoms**: Posts fail with auth errors after working previously

**Diagnosis**:
```sql
-- Check token status
SELECT
    ia.display_name,
    t.expires_at,
    t.updated_at,
    LEFT(t.token_value, 20) as token_prefix
FROM api_tokens t
JOIN instagram_accounts ia ON t.instagram_account_id::uuid = ia.id;
```

**Common Causes**:

| Cause | Check | Fix |
|-------|-------|-----|
| Token expired | `expires_at < NOW()` | Re-authenticate |
| Token not encrypted | Doesn't start with `gAAAAA` | Re-add account |
| Wrong account linked | `instagram_account_id` | Verify account mapping |

**Re-authentication**:
1. Go to Telegram bot
2. Use /settings -> Add Account
3. Complete OAuth flow
4. Verify token is encrypted in database

---

### 5. Media Not Indexing

**Symptoms**: `list-media` shows old/missing files

**Diagnosis**:
```bash
# For Google Drive media source, check sync status
railway shell --service worker -c "storydump-cli sync-status"

# Check media source configuration
railway shell --service worker -c "echo \$MEDIA_SOURCE_TYPE"
```

**Common Causes**:

| Cause | Fix |
|-------|-----|
| Google Drive not connected | Complete OAuth via /start onboarding |
| Wrong folder ID | Update `MEDIA_SOURCE_ROOT` env var |
| Sync disabled | Set `MEDIA_SYNC_ENABLED=true` |
| Unsupported format | Only JPG, JPEG, PNG, GIF, MP4, MOV supported |
| File too large | Max 100MB per file |

**Re-sync**:
```bash
railway shell --service worker -c "storydump-cli sync-media"
```

---

### 6. Database Connection Issues

**Symptoms**: Service fails with database errors

**Diagnosis**:
```bash
# Test connection to Neon
psql "$DATABASE_URL" -c 'SELECT 1;'

# Check connection pool settings
railway shell --service worker -c "echo \$DB_POOL_SIZE"
```

**Common Causes**:

| Cause | Fix |
|-------|-----|
| Neon endpoint sleeping | First connection wakes it (cold start ~1-2s) |
| Wrong credentials | Check `DATABASE_URL` in Railway env vars |
| Connection pool exhausted | Reduce `DB_POOL_SIZE` to 3, `DB_MAX_OVERFLOW` to 2 |
| SSL not configured | Ensure `DB_SSLMODE=require` or use full `DATABASE_URL` |
| Neon free tier limit | Check Neon dashboard for compute hour usage |

---

### 7. Settings Not Persisting

**Symptoms**: Toggle settings reset, wrong account posts

**Diagnosis**:
```sql
-- Check chat_settings
SELECT * FROM chat_settings WHERE telegram_chat_id = YOUR_CHAT_ID;
```

**Common Causes**:

| Cause | Fix |
|-------|-----|
| .env overriding DB | Ensure code reads from `chat_settings` |
| Wrong chat_id | Verify chat ID matches |
| Migration not run | Apply latest migrations |

---

## Log Analysis

### Find Errors

```bash
# All errors in recent logs
railway logs --service worker | grep -i error

# Specific error patterns
railway logs --service worker | grep -iE 'exception|traceback|failed'
```

### Common Log Patterns

| Pattern | Meaning |
|---------|---------|
| `RateLimitError` | Instagram API rate limited |
| `TokenExpiredError` | Need to refresh token |
| `ConnectionError` | Network/API unreachable |
| `ValidationError` | Invalid image format/size |

---

## Emergency Procedures

### Stop All Posting Immediately

```bash
# Enable dry run via database
psql "$DATABASE_URL" -c "UPDATE chat_settings SET dry_run_mode = true;"

# Or restart the service (stops processing temporarily)
railway restart --service worker
```

### Clear Stuck Queue

```bash
# Mark failed posts as cancelled
psql "$DATABASE_URL" -c \
    "UPDATE posting_queue SET status = 'cancelled' WHERE status = 'pending' AND scheduled_for < NOW();"
```

### Force Service Restart

```bash
# Restart via Railway
railway restart --service worker
```
