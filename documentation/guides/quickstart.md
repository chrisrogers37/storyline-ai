# Quick Start Guide - Get Running in 10 Minutes

## Prerequisites

- Python 3.10+
- PostgreSQL installed
- Telegram account

## Step 1: Clone & Install (2 min)

```bash
cd /Users/chris/Projects/storyline-ai

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install CLI
pip install -e .
```

## Step 2: Setup Telegram Bot (3 min)

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow prompts
3. Copy the bot token (looks like `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)
4. Create a Telegram channel for your team
5. Add your bot as admin to the channel
6. Get channel ID using **@userinfobot** (will be negative, like `-1001234567890`)

## Step 3: Configure Database (2 min)

```bash
# Create database
createdb storyline_ai

# Setup schema
psql -U postgres -d storyline_ai -f scripts/setup_database.sql
```

## Step 4: Configure Application (2 min)

```bash
# Copy example config
cp .env.example .env

# Edit configuration
nano .env
```

**Minimum required changes:**
```bash
# Telegram (REQUIRED)
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHANNEL_ID=-1001234567890
ADMIN_TELEGRAM_CHAT_ID=your_user_id

# Database (DB_PASSWORD is optional for local PostgreSQL without password auth)
DB_USER=your_username
DB_PASSWORD=your_db_password  # Leave empty if not needed
MEDIA_DIR=/absolute/path/to/media/stories  # Must be absolute path

# Posting Schedule (adjust to your timezone)
POSTS_PER_DAY=3
POSTING_HOURS_START=14  # 9 AM EST = 14 UTC
POSTING_HOURS_END=2     # 9 PM EST = 2 UTC (next day)
```

## Step 5: Index Media & Create Schedule (1 min)

```bash
# Create media directory if it doesn't exist
mkdir -p media/stories
# Copy some images to media/stories/

# Index media
storyline-cli index-media media/stories

# Create 7-day schedule
storyline-cli create-schedule --days 7

# View what was scheduled
storyline-cli list-queue
```

## Step 6: Run the Application (1 min)

```bash
# Check health first
storyline-cli check-health

# Run application
python -m src.main
```

You should see:
```
Storyline AI - Instagram Story Automation System
✓ Configuration validated successfully
✓ All services started
✓ Phase: Telegram-Only
✓ Posts per day: 3
```

## Step 7: Test the Workflow

1. Application will send notifications to your Telegram channel when posts are due
2. Click **✅ Posted** after posting to Instagram
3. Click **⏭️ Skip** to skip a post
4. Check history: `storyline-cli list-media`

## Troubleshooting

**"Configuration validation failed"**
- Check .env file has all required values
- Verify TELEGRAM_BOT_TOKEN is correct
- Ensure TELEGRAM_CHANNEL_ID is negative

**"Database connection failed"**
- Check PostgreSQL is running: `pg_ctl status`
- Verify database exists: `psql -l | grep storyline_ai`
- Check DB_PASSWORD in .env matches PostgreSQL

**"Telegram bot not responding"**
- Verify bot token with: `curl https://api.telegram.org/bot<TOKEN>/getMe`
- Check bot is admin in channel
- Ensure TELEGRAM_CHANNEL_ID is correct (negative for channels)

**"No media found"**
- Run: `storyline-cli index-media media/stories`
- Check files are .jpg, .jpeg, .png, or .gif
- Verify files exist: `ls media/stories/`

## Useful Commands

```bash
# Health check
storyline-cli check-health

# List media
storyline-cli list-media --limit 50

# List users (after first Telegram interaction)
storyline-cli list-users

# View queue
storyline-cli list-queue

# Process queue manually
storyline-cli process-queue
```

## Next Steps

1. **Customize schedule**: Edit POSTS_PER_DAY and POSTING_HOURS in .env
2. **Add team members**: Just have them interact with the bot
3. **Promote admins**: `storyline-cli promote-user <telegram_id> --role admin`
4. **Run as service**: See documentation for systemd setup

## Success! 🎉

You now have a fully functional Instagram Story scheduling system with Telegram-based team collaboration!

---

**Need help?** Check:
- `README.md` - Full documentation
- `CLAUDE.md` - Developer guide
- `documentation/instagram_automation_plan.md` - Complete specs
