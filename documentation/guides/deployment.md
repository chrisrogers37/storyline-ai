# Phase 1 Deployment Checklist

This checklist covers everything you need to do **outside of code** to get Phase 1 running in production.

## Prerequisites ✅

- [ ] Raspberry Pi 4 (16GB RAM) or similar Linux server
- [ ] PostgreSQL 12+ installed
- [ ] Python 3.10+ installed
- [ ] Instagram account for your business
- [ ] Telegram account

> **Note on paths**: This guide uses `/home/pi/` as the example home directory (the default Raspberry Pi OS user). Replace with your actual home directory (e.g., `/home/crog/`, `/home/ubuntu/`) throughout. The `deploy.sh` script uses `~/storyline-ai` which resolves correctly regardless of username.

---

## 1. Telegram Bot Setup (15 minutes)

### Create Bot with BotFather

- [ ] Open Telegram and search for **@BotFather**
- [ ] Send `/newbot` to BotFather
- [ ] Follow prompts:
  - Choose bot name (e.g., "Storyline AI Bot")
  - Choose bot username (e.g., "storyline_yourcompany_bot")
- [ ] **Save the bot token** (looks like `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)
  - ⚠️ Keep this secret! Anyone with this token controls your bot

### Create Telegram Channel

- [ ] Create a new Telegram channel (not group)
  - Name it (e.g., "Storyline Queue - Internal")
  - Set to Private (only your team can see)
- [ ] Add your bot as an administrator:
  1. Go to channel info
  2. Tap "Administrators"
  3. Tap "Add Administrator"
  4. Search for your bot username
  5. Give it "Post Messages" permission

### Get Channel ID

- [ ] Add **@userinfobot** to your channel
- [ ] Forward any message from the channel to @userinfobot
- [ ] **Save the channel ID** (negative number like `-1001234567890`)
- [ ] Remove @userinfobot from channel

### Get Your Admin Chat ID

- [ ] Send any message to **@userinfobot**
- [ ] **Save your user ID** (positive number like `123456789`)
- [ ] This becomes your `ADMIN_TELEGRAM_CHAT_ID`

### Test Bot

- [ ] Send `/start` to your bot
- [ ] Verify it responds (if not, code isn't running yet - that's okay)

**Deliverables:**
```
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_CHANNEL_ID=-1001234567890
ADMIN_TELEGRAM_CHAT_ID=123456789
```

---

## 2. Database Setup (10 minutes)

### Install PostgreSQL

**Raspberry Pi / Debian / Ubuntu:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql  # Start on boot
```

**macOS:**
```bash
brew install postgresql
brew services start postgresql
```

### Create Database & User

```bash
# Switch to postgres user
sudo -u postgres psql

# In PostgreSQL shell:
CREATE DATABASE storyline_ai;
CREATE USER storyline_user WITH ENCRYPTED PASSWORD 'your_secure_password_here';
GRANT ALL PRIVILEGES ON DATABASE storyline_ai TO storyline_user;
\q
```

### Initialize Schema

```bash
cd /path/to/storyline-ai
psql -U storyline_user -d storyline_ai -f scripts/setup_database.sql
```

### Verify Setup

```bash
psql -U storyline_user -d storyline_ai -c "\dt"
# Should show: users, media_items, posting_queue, posting_history, media_locks, service_runs
```

**Deliverables:**
```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=storyline_ai
DB_USER=storyline_user
DB_PASSWORD=your_secure_password_here
```

---

## 3. Media Files Setup (5 minutes)

### Create Media Directory

```bash
# On Raspberry Pi
mkdir -p /home/pi/media/stories
chmod 755 /home/pi/media/stories
```

### Add Test Images

- [ ] Copy 10-20 Instagram story images to `/home/pi/media/stories/`
- [ ] Supported formats: JPG, JPEG, PNG, GIF, HEIC
- [ ] Recommended: 1080x1920 (9:16 aspect ratio)

### Verify Files

```bash
ls -lh /home/pi/media/stories/
# Should show your image files
```

**Deliverable:**
```
MEDIA_DIR=/home/pi/media/stories
```

---

## 4. Application Configuration (5 minutes)

### Clone Repository

```bash
cd /home/pi
git clone https://github.com/yourusername/storyline-ai.git
cd storyline-ai
```

### Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

### Configure Environment

```bash
cp .env.example .env
nano .env  # or vim, or any editor
```

**Fill in your values:**
```bash
# Phase Control
ENABLE_INSTAGRAM_API=false  # Phase 1 = false

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=storyline_ai
DB_USER=storyline_user
DB_PASSWORD=your_secure_password_here

# Telegram (from step 1)
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_CHANNEL_ID=-1001234567890
ADMIN_TELEGRAM_CHAT_ID=123456789

# Posting Schedule
POSTS_PER_DAY=3
POSTING_HOURS_START=14  # 9 AM EST = 14 UTC
POSTING_HOURS_END=2     # 9 PM EST = 2 UTC (next day)
REPOST_TTL_DAYS=30

# Media
MEDIA_DIR=/home/pi/media/stories

# Backup
BACKUP_DIR=/home/pi/backups/storyline

# Operational
DRY_RUN_MODE=false  # Set to true for testing
LOG_LEVEL=INFO
```

### Validate Configuration

```bash
storyline-cli check-health
# All checks should pass ✓
```

---

## 5. Initial Data Load (2 minutes)

### Index Media Files

```bash
storyline-cli index-media /home/pi/media/stories
# Should show: Added X media items
```

### Create Initial Schedule

```bash
storyline-cli create-schedule --days 7
# Creates 7 days of scheduled posts (3 per day = 21 total)
```

### Verify Queue

```bash
storyline-cli list-queue
# Should show scheduled items
```

---

## 6. System Service Setup (10 minutes)

### Create Systemd Service

```bash
sudo nano /etc/systemd/system/storyline-ai.service
```

**Service file:**
```ini
[Unit]
Description=Storyline AI - Instagram Story Automation
After=network.target postgresql.service

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/home/pi/storyline-ai
Environment="PATH=/home/pi/storyline-ai/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/pi/storyline-ai/venv/bin/python -m src.main
Restart=always
RestartSec=10
StandardOutput=append:/home/pi/storyline-ai/logs/service.log
StandardError=append:/home/pi/storyline-ai/logs/service-error.log

[Install]
WantedBy=multi-user.target
```

### Enable and Start Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable storyline-ai
sudo systemctl start storyline-ai
sudo systemctl status storyline-ai
```

### Verify Service is Running

```bash
# Check status
sudo systemctl status storyline-ai

# View logs
tail -f logs/storyline.log

# Check Telegram channel
# You should see a test message or scheduled posts
```

---

## 7. Team Onboarding (5 minutes per person)

### Add Team Members

Each team member needs to:

- [ ] Join the Telegram channel
- [ ] Send `/start` to the bot (creates their user account)
- [ ] Test posting workflow:
  1. Wait for notification in channel
  2. Post story to Instagram manually
  3. Click "✅ Posted" button

### Promote Admins (Optional)

```bash
# Get their Telegram user ID (they send /start to @userinfobot)
storyline-cli list-users
# Find their ID

storyline-cli promote-user <telegram_user_id> --role admin
```

---

## 8. Backup Strategy (10 minutes)

### Create Backup Directory

```bash
mkdir -p /home/pi/backups/storyline
```

### Manual Backup

```bash
make db-backup
# Creates: backups/storyline_ai_20260103_120000.sql
```

### Automated Backups (Cron)

```bash
crontab -e
```

**Add daily backup at 3 AM:**
```cron
0 3 * * * cd /home/pi/storyline-ai && /home/pi/storyline-ai/venv/bin/python -c "from src.services.backup import BackupService; BackupService().create_backup()"
```

### Test Restore

```bash
# Test that backup can be restored
make db-restore FILE=backups/storyline_ai_20260103_120000.sql
```

---

## 9. Monitoring Setup (15 minutes)

### Log Rotation

```bash
sudo nano /etc/logrotate.d/storyline-ai
```

```
/home/pi/storyline-ai/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 pi pi
    sharedscripts
    postrotate
        systemctl reload storyline-ai > /dev/null 2>&1 || true
    endscript
}
```

### Health Check Monitoring (Optional)

**Option 1: Manual checks**
```bash
# Add to crontab for alerts
0 */4 * * * cd /home/pi/storyline-ai && /home/pi/storyline-ai/venv/bin/storyline-cli check-health || echo "Health check failed" | mail -s "Storyline Alert" you@email.com
```

**Option 2: Use uptime monitoring service**
- [ ] Sign up for UptimeRobot (free tier)
- [ ] Monitor Raspberry Pi IP:port
- [ ] Get email/SMS alerts if service goes down

---

## 10. Instagram Account Preparation (5 minutes)

### Business Account Setup

- [ ] Convert to Instagram Business Account (if not already)
  1. Go to Settings → Account
  2. Switch to Professional Account
  3. Choose Business category
  4. Connect Facebook Page (optional for Phase 1)

### Story Preparation

Phase 1 is **manual posting**, so prepare your workflow:

- [ ] Keep Instagram app logged in
- [ ] Enable notifications for Telegram channel
- [ ] Have media downloading method ready (if posting from phone)

### Media Transfer Options

**Option 1: Cloud sync**
- [ ] Use Dropbox/Google Drive to sync media folder to phone
- [ ] Download from cloud when notification arrives

**Option 2: Direct transfer**
- [ ] Use file transfer app (AirDrop, Snapdrop, etc.)
- [ ] Transfer from Pi to phone when needed

**Option 3: Telegram (simplest)**
- [ ] Bot already sends the image in notification
- [ ] Download from Telegram, post to Instagram
- [ ] Click "Posted" button

---

## 11. Testing Phase (1-2 days)

### Initial Testing Checklist

- [ ] **Day 1 Morning:**
  - Set `DRY_RUN_MODE=true` in `.env`
  - Restart service: `sudo systemctl restart storyline-ai`
  - Verify notifications arrive in Telegram
  - Test "Posted" and "Skip" buttons
  - Check `storyline-cli list-queue` shows updated status

- [ ] **Day 1 Afternoon:**
  - Set `DRY_RUN_MODE=false`
  - Restart service
  - Wait for first real notification
  - Post ONE story to Instagram manually
  - Click "Posted" button
  - Verify in `storyline-cli list-media` shows `times_posted=1`

- [ ] **Day 2:**
  - Monitor all scheduled posts
  - Verify team members can interact
  - Check no duplicate notifications
  - Verify posting history is recorded

### Success Criteria

- [ ] Notifications arrive at scheduled times
- [ ] Team can click Posted/Skip buttons
- [ ] No duplicate posts scheduled
- [ ] Locks prevent reposting within 30 days
- [ ] Service stays running for 24+ hours
- [ ] Logs show no errors

---

## 12. Production Launch (Go Live!)

### Final Checklist

- [ ] All tests passing
- [ ] Team trained on workflow
- [ ] Backup system verified
- [ ] Monitoring alerts configured
- [ ] Emergency contacts documented
- [ ] Rollback plan documented

### Go Live

```bash
# 1. Set production mode
nano .env
# Set: DRY_RUN_MODE=false

# 2. Restart service
sudo systemctl restart storyline-ai

# 3. Monitor first day
tail -f logs/storyline.log
```

### First Week Monitoring

- [ ] Check logs daily
- [ ] Verify all posts going out
- [ ] Monitor team feedback
- [ ] Track any issues
- [ ] Adjust schedule if needed (`POSTS_PER_DAY`, `POSTING_HOURS_START`, etc.)

---

## Ongoing Maintenance

### Daily
- [ ] Check Telegram channel for any issues
- [ ] Verify posts are being published

### Weekly
- [ ] Add new media to `/home/pi/media/stories/`
- [ ] Run `storyline-cli index-media /home/pi/media/stories`
- [ ] Check `storyline-cli check-health`
- [ ] Review posting history: `storyline-cli list-media --limit 50`

### Monthly
- [ ] Review posting schedule effectiveness
- [ ] Check backup files exist
- [ ] Update media library
- [ ] Review team permissions

### As Needed
- [ ] Create new schedule: `storyline-cli create-schedule --days 7`
- [ ] Promote team members: `storyline-cli promote-user <id> --role admin`
- [ ] Clear old queue items if needed

---

## Troubleshooting Quick Reference

### Service Won't Start
```bash
sudo systemctl status storyline-ai
sudo journalctl -u storyline-ai -n 50
# Check logs/storyline.log for errors
```

### Bot Not Responding
```bash
# Verify token with Telegram API
curl https://api.telegram.org/bot<YOUR_TOKEN>/getMe

# Check bot has admin rights in channel
# Check TELEGRAM_CHANNEL_ID is negative
```

### Database Connection Failed
```bash
# Test connection
psql -U storyline_user -d storyline_ai -c "SELECT version();"

# Check PostgreSQL is running
sudo systemctl status postgresql
```

### No Notifications Arriving
```bash
# Check queue has items
storyline-cli list-queue

# Check scheduled times are in the future
storyline-cli list-queue | grep scheduled_time

# Check service is running
sudo systemctl status storyline-ai
```

---

## Summary: What You Need

### External Services
- ✅ Telegram bot (via @BotFather)
- ✅ Telegram channel (private)
- ✅ Instagram business account (optional for Phase 1)

### Infrastructure
- ✅ Raspberry Pi or Linux server
- ✅ PostgreSQL database
- ✅ Python 3.10+ environment

### One-Time Setup
- ✅ Bot configuration (~15 min)
- ✅ Database setup (~10 min)
- ✅ Application deployment (~30 min)
- ✅ Team onboarding (~5 min/person)

### Ongoing
- ✅ Add media weekly
- ✅ Monitor Telegram notifications daily
- ✅ Manual Instagram posting when notified

**Total setup time: ~1-2 hours**

---

Ready to go? Start with **Section 1: Telegram Bot Setup** and work through the checklist! 🚀
