# Quick Start Guide - Get Running in 10 Minutes

## Prerequisites

- Python 3.10+
- PostgreSQL installed
- Telegram account

## Step 1: Clone & Install (2 min)

```bash
# Clone the repository and navigate to it
git clone <your-repo-url> storydump
cd storydump

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
createdb storydump

# Setup schema
psql -U postgres -d storydump -f scripts/setup_database.sql
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
storydump-cli index-media media/stories

# Create 7-day schedule
storydump-cli create-schedule --days 7

# View what was scheduled
storydump-cli list-queue
```

## Step 6: Run the Application (1 min)

```bash
# Check health first
storydump-cli check-health

# Run application
python -m src.main
```

You should see:
```
Storydump - Instagram Story Automation System
✓ Configuration validated successfully
✓ All services started
✓ Phase: Telegram-Only
✓ Posts per day: 3
```

## Step 7: Test the Workflow

1. Application will send notifications to your Telegram channel when posts are due
2. Click **✅ Posted** after posting to Instagram
3. Click **⏭️ Skip** to skip a post
4. Click **🚫 Reject** to permanently block unwanted media
5. Use `/settings` in Telegram to configure bot behavior
6. Check history: `storydump-cli list-media`

## Troubleshooting

**"Configuration validation failed"**
- Check .env file has all required values
- Verify TELEGRAM_BOT_TOKEN is correct
- Ensure TELEGRAM_CHANNEL_ID is negative

**"Database connection failed"**
- Check PostgreSQL is running: `pg_ctl status`
- Verify database exists: `psql -l | grep storydump`
- Check DB_PASSWORD in .env matches PostgreSQL

**"Telegram bot not responding"**
- Verify bot token with: `curl https://api.telegram.org/bot<TOKEN>/getMe`
- Check bot is admin in channel
- Ensure TELEGRAM_CHANNEL_ID is correct (negative for channels)

**"No media found"**
- Run: `storydump-cli index-media media/stories`
- Check files are .jpg, .jpeg, .png, or .gif
- Verify files exist: `ls media/stories/`

## Useful Commands

```bash
# Health check
storydump-cli check-health

# List media
storydump-cli list-media --limit 50

# List users (after first Telegram interaction)
storydump-cli list-users

# View queue
storydump-cli list-queue

# Preview upcoming posts
storydump-cli queue-preview
```

## Next Steps

1. **Customize schedule**: Use `/settings` in Telegram or edit .env for defaults
2. **Add team members**: Just have them interact with the bot (auto-discovery)
3. **Promote admins**: `storydump-cli promote-user <telegram_id> --role admin`
4. **Deploy to Railway**: See [deployment.md](deployment.md) for production setup
5. **Enable Instagram API** (Phase 2): See [instagram-api-setup.md](instagram-api-setup.md)
6. **Add multiple accounts**: `storydump-cli add-instagram-account --help`
7. **Category scheduling**: Organize media in subfolders, use `storydump-cli list-categories`

## Telegram Bot Commands

Once running, these commands are available in Telegram:

| Command | Description |
|---------|-------------|
| `/start` | Open setup wizard or show dashboard |
| `/status` | System health, media stats, queue status |
| `/setup` / `/settings` | Quick settings and toggles |
| `/next` | Force-send next post immediately |
| `/cleanup` | Delete recent bot messages |
| `/help` | Show available commands |

---

**Need help?** Check:
- `README.md` - Full documentation
- `CLAUDE.md` - Developer guide
- [deployment.md](deployment.md) - Production deployment
- [instagram-api-setup.md](instagram-api-setup.md) - Instagram API setup
