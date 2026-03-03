# Deployment Checklist

This checklist covers everything you need to do **outside of code** to get Storyline AI running in production on Railway + Neon.

## Prerequisites

- [ ] GitHub account (public repository)
- [ ] Railway account ([railway.app](https://railway.app))
- [ ] Neon account ([console.neon.tech](https://console.neon.tech))
- [ ] Instagram account for your business
- [ ] Telegram account

---

## 1. Telegram Bot Setup (15 minutes)

### Create Bot with BotFather

- [ ] Open Telegram and search for **@BotFather**
- [ ] Send `/newbot` to BotFather
- [ ] Follow prompts:
  - Choose bot name (e.g., "Storyline AI Bot")
  - Choose bot username (e.g., "storyline_yourcompany_bot")
- [ ] **Save the bot token** (looks like `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)

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
- [ ] Verify it responds (if not, service isn't running yet - that's okay)

**Deliverables:**
```
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_CHANNEL_ID=-1001234567890
ADMIN_TELEGRAM_CHAT_ID=123456789
```

---

## 2. Database Setup - Neon (10 minutes)

### Create Neon Project

- [ ] Sign up at [console.neon.tech](https://console.neon.tech)
- [ ] Create a new project (name: `storyline-ai`)
- [ ] Note your connection string from the dashboard

### Initialize Schema

```bash
# Set your Neon connection string
export DATABASE_URL="postgresql://user:pass@ep-xxx.neon.tech/storyline_ai?sslmode=require"

# Run base schema
psql "$DATABASE_URL" -f scripts/setup_database.sql

# Run all migrations
for f in scripts/migrations/0{01,02,03,04,05,06,07,08,09,10,11,12,13,14,15,16}_*.sql; do
  echo "Running $f..."
  psql "$DATABASE_URL" -f "$f"
done
```

### Verify Setup

```bash
psql "$DATABASE_URL" -c "\dt"
# Should show all tables
```

### Connection Pool Sizing

Neon free tier allows 5 concurrent connections:
```
DB_POOL_SIZE=3
DB_MAX_OVERFLOW=2
```

**Deliverables:**
```
DATABASE_URL=postgresql://user:pass@ep-xxx.neon.tech/storyline_ai?sslmode=require
```

---

## 3. Media Setup (5 minutes)

### Google Drive (Recommended for Cloud)

Media is sourced from Google Drive when running on Railway:

- [ ] Create a Google Drive folder for your media
- [ ] Organize subfolders by category (e.g., `memes/`, `merch/`)
- [ ] Upload your Instagram story images (JPG, JPEG, PNG, GIF)
- [ ] Note the folder ID from the URL

Google Drive OAuth will be configured during the onboarding wizard (`/start` command).

### Local Development

For local development, create a media directory:
```bash
mkdir -p /tmp/media
```

**Deliverable:**
```
MEDIA_SOURCE_TYPE=google_drive
MEDIA_DIR=/tmp/media
```

---

## 4. Railway Deployment (15 minutes)

### Create Railway Project

- [ ] Go to [railway.app](https://railway.app) and create a new project
- [ ] Connect your GitHub repository

### Create Two Services

Railway requires two services from the same repo:

**Service 1: Worker**
- Start command: `python -m src.main`
- Build command: `pip install -r requirements.txt && pip install -e . && mkdir -p /tmp/media`

**Service 2: Web**
- Start command: `uvicorn src.api.app:app --host 0.0.0.0 --port ${PORT:-8000}`
- Build command: `pip install -r requirements.txt && pip install -e . && mkdir -p /tmp/media`

### Generate Domain

- [ ] Generate a public domain for the Web service (needed for OAuth callbacks)
- [ ] Note the URL (e.g., `https://your-app.up.railway.app`)

### Configure Environment Variables

Set these on **both** services in the Railway dashboard:

```bash
# Required
DATABASE_URL=postgresql://user:pass@ep-xxx.neon.tech/storyline_ai?sslmode=require
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_CHANNEL_ID=-1001234567890
ADMIN_TELEGRAM_CHAT_ID=123456789
MEDIA_DIR=/tmp/media
ENCRYPTION_KEY=<generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">

# Schedule
POSTS_PER_DAY=3
POSTING_HOURS_START=14
POSTING_HOURS_END=2
REPOST_TTL_DAYS=30

# Safety (start with dry run!)
DRY_RUN_MODE=true
LOG_LEVEL=INFO

# OAuth (Web service)
OAUTH_REDIRECT_BASE_URL=https://your-app.up.railway.app
```

### Validate Deployment

```bash
# Check worker logs
railway logs --service worker

# Check web service is responding
curl https://your-app.up.railway.app/health
```

---

## 5. Initial Data Load (2 minutes)

### Connect Google Drive

- [ ] Send `/start` to the Telegram bot
- [ ] Follow the onboarding wizard to connect Google Drive
- [ ] Select your media folder

### Sync Media

```bash
# Via Railway shell
railway shell --service worker -c "storyline-cli sync-media"
railway shell --service worker -c "storyline-cli list-media"
```

### Create Initial Schedule

```bash
railway shell --service worker -c "storyline-cli create-schedule --days 7"
# Creates 7 days of scheduled posts
```

### Verify Queue

```bash
railway shell --service worker -c "storyline-cli list-queue"
# Should show scheduled items
```

---

## 6. Team Onboarding (5 minutes per person)

### Add Team Members

Each team member needs to:

- [ ] Join the Telegram channel
- [ ] Send `/start` to the bot (creates their user account)
- [ ] Test posting workflow:
  1. Wait for notification in channel
  2. Post story to Instagram manually
  3. Click "Posted" button

### Promote Admins (Optional)

```bash
# Get their Telegram user ID
railway shell --service worker -c "storyline-cli list-users"

# Promote
railway shell --service worker -c "storyline-cli promote-user <telegram_user_id> --role admin"
```

---

## 7. Backup Strategy (10 minutes)

### Neon Built-in Backups

Neon provides automatic point-in-time recovery on paid plans.

### Manual Backup

```bash
# Dump from Neon
pg_dump "$DATABASE_URL" -F c -f ~/backups/storyline_$(date +%Y%m%d).dump
```

### Test Restore

```bash
# Restore to a test database
pg_restore -d "$TEST_DATABASE_URL" ~/backups/storyline_YYYYMMDD.dump
```

See [backup-restore.md](../operations/backup-restore.md) for full backup procedures.

---

## 8. Monitoring Setup (10 minutes)

### Railway Dashboard

Railway provides built-in log streaming and service monitoring.

### Health Check via Telegram

Use the bot itself as a health indicator:
- `/status` shows system health, queue state, and recent activity

### External Monitoring (Optional)

- [ ] Sign up for UptimeRobot (free tier)
- [ ] Monitor your Railway web service URL
- [ ] Get email/SMS alerts if service goes down

See [monitoring.md](../operations/monitoring.md) for detailed monitoring setup.

---

## 9. Instagram Account Preparation (5 minutes)

### Business Account Setup

- [ ] Convert to Instagram Business Account (if not already)
  1. Go to Settings -> Account
  2. Switch to Professional Account
  3. Choose Business category
  4. Connect Facebook Page (optional for Phase 1)

### Story Preparation

Phase 1 is **manual posting**, so prepare your workflow:

- [ ] Keep Instagram app logged in
- [ ] Enable notifications for Telegram channel
- [ ] Have media downloading method ready (if posting from phone)

### Media Transfer Options

**Option 1: Telegram (simplest)**
- Bot already sends the image in notification
- Download from Telegram, post to Instagram
- Click "Posted" button

**Option 2: Cloud sync**
- Use Google Drive to sync media folder to phone
- Download from cloud when notification arrives

---

## 10. Testing Phase (1-2 days)

### Initial Testing Checklist

- [ ] **Day 1 Morning:**
  - Verify `DRY_RUN_MODE=true` in Railway env vars
  - Verify notifications arrive in Telegram
  - Test "Posted" and "Skip" buttons
  - Check queue via `storyline-cli list-queue`

- [ ] **Day 1 Afternoon:**
  - Set `DRY_RUN_MODE=false` in Railway env vars
  - Wait for first real notification
  - Post ONE story to Instagram manually
  - Click "Posted" button
  - Verify posting history is recorded

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

## 11. Production Launch (Go Live!)

### Final Checklist

- [ ] All tests passing
- [ ] Team trained on workflow
- [ ] Backup system verified
- [ ] Monitoring alerts configured
- [ ] Emergency contacts documented

### Go Live

```bash
# Set DRY_RUN_MODE=false in Railway dashboard
# Railway will restart the service automatically

# Monitor first day
railway logs --service worker
```

### First Week Monitoring

- [ ] Check logs daily via Railway dashboard
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
- [ ] Add new media to Google Drive folder
- [ ] Run media sync: `/sync` in Telegram or `storyline-cli sync-media`
- [ ] Check health: `/status` in Telegram

### Monthly
- [ ] Review posting schedule effectiveness
- [ ] Verify database backups
- [ ] Update media library
- [ ] Review team permissions

### As Needed
- [ ] Create new schedule: `storyline-cli create-schedule --days 7`
- [ ] Promote team members: `storyline-cli promote-user <id> --role admin`
- [ ] Clear old queue items if needed

---

## Troubleshooting Quick Reference

### Service Not Starting
```bash
railway logs --service worker | tail -50
# Check for missing env vars or build errors
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
psql "$DATABASE_URL" -c "SELECT version();"
```

### No Notifications Arriving
```bash
# Check queue has items
railway shell --service worker -c "storyline-cli list-queue"

# Check service is running
railway logs --service worker
```

---

## Summary: What You Need

### External Services
- Telegram bot (via @BotFather)
- Telegram channel (private)
- Instagram business account (optional for Phase 1)

### Cloud Infrastructure
- Railway account (worker + web services)
- Neon PostgreSQL database
- Google Drive (media storage)

### One-Time Setup
- Bot configuration (~15 min)
- Database setup (~10 min)
- Railway deployment (~15 min)
- Team onboarding (~5 min/person)

### Ongoing
- Add media to Google Drive weekly
- Monitor Telegram notifications daily
- Manual Instagram posting when notified

**Total setup time: ~1-2 hours**

---

Ready to go? Start with **Section 1: Telegram Bot Setup** and work through the checklist!
