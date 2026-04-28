# Backup & Restore Procedures

## Overview

Critical data to backup:
1. **PostgreSQL database** - All application state (hosted on Neon)
2. **Media files** - Source images/videos (hosted on Google Drive)
3. **Configuration** - Environment variables in Railway
4. **Tokens** - Encrypted in database, but backup separately

---

## Database Backup

### Manual Backup

```bash
# Dump from Neon using DATABASE_URL
pg_dump "$DATABASE_URL" -F c -f ~/backups/storydump_$(date +%Y%m%d_%H%M%S).dump

# Or with explicit connection string
pg_dump "postgresql://user:pass@ep-xxx.neon.tech/storydump_ai?sslmode=require" \
    -F c -f ~/backups/storydump_$(date +%Y%m%d_%H%M%S).dump
```

### Automated Daily Backup

Create a backup script on your local machine or a CI runner:

```bash
#!/bin/bash
# backup_db.sh
BACKUP_DIR="$HOME/backups/storydump"
RETENTION_DAYS=30

mkdir -p "$BACKUP_DIR"

# Create backup from Neon
pg_dump "$DATABASE_URL" -F c \
    -f "$BACKUP_DIR/storydump_$(date +%Y%m%d).dump"

# Remove old backups
find "$BACKUP_DIR" -name "storydump_*.dump" -mtime +$RETENTION_DAYS -delete

echo "Backup complete: storydump_$(date +%Y%m%d).dump"
```

Schedule via crontab on your local machine or a GitHub Actions workflow:
```bash
# Daily at 3am (local machine)
0 3 * * * ~/scripts/backup_db.sh >> ~/logs/backup.log 2>&1
```

### Neon Built-in Backups

Neon provides automatic point-in-time recovery on paid plans. Free tier has limited retention. Check the [Neon dashboard](https://console.neon.tech) for backup status.

---

## Database Restore

### Full Restore

```bash
# Drop and recreate database (via Neon dashboard or psql)
psql "$DATABASE_URL" -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'

# Restore from backup
pg_restore -d "$DATABASE_URL" ~/backups/storydump_YYYYMMDD.dump

# Restart Railway services after restore
railway restart --service worker
railway restart --service web
```

### Partial Restore (specific tables)

```bash
# List contents of backup
pg_restore -l ~/backups/storydump_YYYYMMDD.dump

# Restore specific table
pg_restore -d "$DATABASE_URL" \
    -t posting_history ~/backups/storydump_YYYYMMDD.dump
```

---

## Media Files Backup

### Google Drive (Primary Media Source)

When using Google Drive as the media source, files are already stored in the cloud. Ensure the Google Drive folder is shared or backed up according to your Google Workspace settings.

### Sync to External Storage

```bash
# Backup media from Google Drive to local storage using rclone
rclone sync gdrive:storydump-media/ ~/backups/storydump-media/

# Or download via the Google Drive web interface
```

### Backup Manifest

Keep a manifest of media files for verification:

```sql
-- Generate manifest from database
SELECT file_name, file_hash, category, created_at
FROM media_items
WHERE is_active = true
ORDER BY file_name;
```

---

## Configuration Backup

### Railway Environment Variables

```bash
# Export Railway env vars (requires Railway CLI)
railway variables --service worker > ~/backups/railway_worker_env_$(date +%Y%m%d).txt
railway variables --service web > ~/backups/railway_web_env_$(date +%Y%m%d).txt

# Store securely - these contain secrets!
chmod 600 ~/backups/railway_*_env_*.txt
```

### Token Backup

Tokens are encrypted in the database. For extra safety:

```bash
# Export tokens (encrypted values)
psql "$DATABASE_URL" -c \
    "COPY (SELECT * FROM api_tokens) TO STDOUT WITH CSV HEADER" \
    > ~/backups/tokens_$(date +%Y%m%d).csv
```

---

## Disaster Recovery

### Complete System Recovery

1. **Create new Railway project** with worker + web services
2. **Create new Neon database** (or restore from Neon backup)
3. **Restore database** from latest `pg_dump` backup
4. **Configure environment variables** in Railway dashboard
5. **Deploy application**:
   ```bash
   # Connect Railway to GitHub repo
   # Railway will auto-build and deploy
   ```
6. **Verify**:
   ```bash
   railway shell --service worker -c "storydump-cli check-health"
   ```
7. **Re-connect OAuth** (if tokens expired):
   - Instagram: Re-authorize via /settings in Telegram
   - Google Drive: Re-authorize via /start onboarding wizard

---

## Backup Verification

Monthly verification checklist:

- [ ] Restore backup to test database
- [ ] Verify row counts match production
- [ ] Check media file integrity (Google Drive)
- [ ] Test token decryption works
- [ ] Verify service starts with restored data
