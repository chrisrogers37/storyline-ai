# Backup & Restore Procedures

## Overview

Critical data to backup:
1. **PostgreSQL database** - All application state
2. **Media files** - Source images/videos
3. **Configuration** - `.env` file with tokens
4. **Tokens** - Encrypted in database, but backup separately

---

## Database Backup

### Manual Backup

```bash
# Create backup on Pi
ssh crogberrypi "pg_dump -U storyline_user -d storyline_ai -F c -f /home/pi/backups/storyline_$(date +%Y%m%d_%H%M%S).dump"

# Copy to local machine
scp crogberrypi:/home/pi/backups/storyline_*.dump ~/backups/
```

### Automated Daily Backup

Create `/home/pi/scripts/backup_db.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/home/pi/backups"
RETENTION_DAYS=30

# Create backup
pg_dump -U storyline_user -d storyline_ai -F c \
    -f "$BACKUP_DIR/storyline_$(date +%Y%m%d).dump"

# Remove old backups
find "$BACKUP_DIR" -name "storyline_*.dump" -mtime +$RETENTION_DAYS -delete

echo "Backup complete: storyline_$(date +%Y%m%d).dump"
```

Add to crontab:
```bash
# Daily at 3am
0 3 * * * /home/pi/scripts/backup_db.sh >> /home/pi/logs/backup.log 2>&1
```

---

## Database Restore

### Full Restore

```bash
# Stop service first
ssh crogberrypi "sudo systemctl stop storyline-ai"

# Drop and recreate database
ssh crogberrypi "psql -U postgres -c 'DROP DATABASE storyline_ai;'"
ssh crogberrypi "psql -U postgres -c 'CREATE DATABASE storyline_ai OWNER storyline_user;'"

# Restore from backup
ssh crogberrypi "pg_restore -U storyline_user -d storyline_ai /home/pi/backups/storyline_YYYYMMDD.dump"

# Restart service
ssh crogberrypi "sudo systemctl start storyline-ai"
```

### Partial Restore (specific tables)

```bash
# List contents of backup
ssh crogberrypi "pg_restore -l /home/pi/backups/storyline_YYYYMMDD.dump"

# Restore specific table
ssh crogberrypi "pg_restore -U storyline_user -d storyline_ai \
    -t posting_history /home/pi/backups/storyline_YYYYMMDD.dump"
```

---

## Media Files Backup

### Sync to External Storage

```bash
# Backup media to external drive
rsync -av --progress /path/to/media/stories/ /mnt/external/storyline-media/

# Or to remote server
rsync -av --progress /path/to/media/stories/ user@backup-server:/backups/storyline-media/
```

### Backup Manifest

Keep a manifest of media files for verification:

```bash
# Generate manifest
find /path/to/media/stories -type f -exec md5sum {} \; > media_manifest.txt

# Verify against manifest
md5sum -c media_manifest.txt
```

---

## Configuration Backup

### .env File

```bash
# Backup .env (contains tokens!)
scp crogberrypi:/home/pi/storyline-ai/.env ~/backups/storyline_env_$(date +%Y%m%d).env

# Store securely - this contains secrets!
chmod 600 ~/backups/storyline_env_*.env
```

### Token Backup

Tokens are encrypted in the database. For extra safety:

```bash
# Export tokens (encrypted values)
ssh crogberrypi "psql -U storyline_user -d storyline_ai -c \
    \"COPY (SELECT * FROM api_tokens) TO STDOUT WITH CSV HEADER\" \
    > /home/pi/backups/tokens_$(date +%Y%m%d).csv"
```

---

## Disaster Recovery

### Complete System Recovery

1. **Set up new Pi** with PostgreSQL
2. **Restore database** from latest backup
3. **Copy media files** to correct path
4. **Restore .env** configuration
5. **Install application**:
   ```bash
   git clone https://github.com/chrisrogers37/storyline-ai.git
   cd storyline-ai
   pip install -r requirements.txt
   pip install -e .
   ```
6. **Start service**:
   ```bash
   sudo systemctl start storyline-ai
   ```
7. **Verify**:
   ```bash
   storyline-cli check-health
   ```

---

## Backup Verification

Monthly verification checklist:

- [ ] Restore backup to test database
- [ ] Verify row counts match production
- [ ] Check media file integrity
- [ ] Test token decryption works
- [ ] Verify service starts with restored data
