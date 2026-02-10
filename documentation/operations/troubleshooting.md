# Troubleshooting Guide

## Quick Diagnostics

```bash
# One-liner health check
ssh crogberrypi "systemctl is-active storyline-ai && echo 'Service: OK' || echo 'Service: DOWN'"
```

---

## Common Issues

### 1. Service Won't Start

**Symptoms**: `systemctl status` shows `failed` or `inactive`

**Diagnosis**:
```bash
ssh crogberrypi "journalctl -u storyline-ai -n 100 --no-pager | tail -50"
```

**Common Causes**:

| Error | Cause | Fix |
|-------|-------|-----|
| `ModuleNotFoundError` | Missing dependency | `pip install -r requirements.txt` |
| `Connection refused` | Database not running | `sudo systemctl start postgresql` |
| `Permission denied` | File permissions | Check `.env` and media folder permissions |
| `Invalid token` | Expired/corrupt token | Re-authenticate via CLI |

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
# Check service is running
ssh crogberrypi "systemctl status storyline-ai"

# Check for Telegram errors
ssh crogberrypi "journalctl -u storyline-ai --since '1 hour ago' | grep -i telegram"

# Test bot token
curl "https://api.telegram.org/bot<TOKEN>/getMe"
```

**Common Causes**:

| Cause | Fix |
|-------|-----|
| Service crashed | Restart service |
| Bot token invalid | Check `TELEGRAM_BOT_TOKEN` in `.env` |
| Webhook conflict | Only one instance should run |
| Network issues | Check Pi internet connectivity |

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
2. Use /settings → Add Account
3. Complete OAuth flow
4. Verify token is encrypted in database

---

### 5. Media Not Indexing

**Symptoms**: `list-media` shows old/missing files

**Diagnosis**:
```bash
# Check media path exists
ssh crogberrypi "ls -la /path/to/media/stories/"

# Check file permissions
ssh crogberrypi "ls -la /path/to/media/stories/*.jpg | head -5"
```

**Common Causes**:

| Cause | Fix |
|-------|-----|
| Wrong path in `.env` | Update `MEDIA_DIR` |
| Permission denied | `chmod -R 755 /path/to/media` |
| Unsupported format | Only JPG, JPEG, PNG, GIF, MP4, MOV supported |
| File too large | Max 100MB per file |

**Re-index**:
```bash
storyline-cli index-media /path/to/media/stories --force
```

---

### 6. Database Connection Issues

**Symptoms**: Service fails with database errors

**Diagnosis**:
```bash
# Check PostgreSQL is running
ssh crogberrypi "systemctl status postgresql"

# Test connection
ssh crogberrypi "psql -U storyline_user -d storyline_ai -c 'SELECT 1;'"
```

**Common Causes**:

| Cause | Fix |
|-------|-----|
| PostgreSQL stopped | `sudo systemctl start postgresql` |
| Wrong credentials | Check `DATABASE_URL` in `.env` |
| Database doesn't exist | Run setup script |
| Disk full | Free up space |

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
# All errors in last 24 hours
ssh crogberrypi "journalctl -u storyline-ai --since '24 hours ago' | grep -i error"

# Specific error patterns
ssh crogberrypi "journalctl -u storyline-ai --since '1 hour ago' | grep -iE 'exception|traceback|failed'"
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
# Stop service
ssh crogberrypi "sudo systemctl stop storyline-ai"

# Or enable dry run via database
ssh crogberrypi "psql -U storyline_user -d storyline_ai -c \
    \"UPDATE chat_settings SET dry_run_mode = true;\""
```

### Clear Stuck Queue

```bash
# Mark failed posts as cancelled
ssh crogberrypi "psql -U storyline_user -d storyline_ai -c \
    \"UPDATE posting_queue SET status = 'cancelled' WHERE status = 'pending' AND scheduled_for < NOW();\""
```

### Force Service Restart

```bash
ssh crogberrypi "sudo systemctl kill storyline-ai && sudo systemctl start storyline-ai"
```
