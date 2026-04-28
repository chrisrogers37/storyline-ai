# Storydump - Instagram Story Automation System

A self-hosted Instagram Story scheduling system with Telegram-based team collaboration.

## Features

- 📅 **Smart Scheduling**: Intelligent posting schedule based on your preferences
- 📁 **Category-Based Scheduling**: Organize media by folder (memes/, merch/) with configurable ratios
- 📱 **Telegram Integration**: Team collaboration via Telegram bot with lifecycle notifications
- 🔄 **Phased Approach**: Start with manual posting, optionally enable automation
- 🔒 **TTL Locks**: Prevent premature reposts with 30-day locks
- 🚫 **Permanent Reject**: Permanently block unwanted media from ever being queued
- 📊 **Full Audit Trail**: Track who posted what and when
- 🎨 **Image Validation**: Automatic validation against Instagram requirements
- 📱 **Instagram Deep Links**: One-tap button to open Instagram app/web
- ✨ **Enhanced Captions**: Clean workflow instructions with actionable steps

## Quick Start

### 1. Installation

```bash
# Clone repository
git clone <your-repo-url>
cd storydump

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install CLI tool
pip install -e .
```

### 2. Configuration

```bash
# Create .env file with your credentials
nano .env
```

Add the following required variables to your `.env` file:

Required configuration:
- `TELEGRAM_BOT_TOKEN`: Get from @BotFather on Telegram
- `TELEGRAM_CHANNEL_ID`: Your Telegram channel ID
- `ADMIN_TELEGRAM_CHAT_ID`: Your personal chat ID for alerts
- `DB_PASSWORD`: PostgreSQL password (optional for local development)

### 3. Database Setup

```bash
# Create database
createdb storydump

# Run schema setup
psql -U postgres -d storydump -f scripts/setup_database.sql

# Or use Python script
python scripts/init_db.py
```

### 4. Index Your Media

```bash
# Index media files
storydump-cli index-media /path/to/media/stories

# List indexed media
storydump-cli list-media --limit 20
```

### 5. Create Schedule

```bash
# Create 7-day posting schedule
storydump-cli create-schedule --days 7

# View queue
storydump-cli list-queue
```

### 6. Run the Application

```bash
# Run in foreground (for testing)
python -m src.main

# Or run as background service (see documentation)
```

## CLI Commands

### Media Management

```bash
# Index media from directory
storydump-cli index-media /path/to/media

# List all media items
storydump-cli list-media --limit 50 --active-only

# Validate image
storydump-cli validate-image /path/to/image.jpg
```

### Queue Management

```bash
# Create posting schedule (uses category ratios)
storydump-cli create-schedule --days 7

# Process pending posts
storydump-cli process-queue

# Force process next post (development testing)
storydump-cli process-queue --force

# View queue
storydump-cli list-queue

# Reset queue (clear all pending posts)
storydump-cli reset-queue
```

### Category Management

```bash
# List categories and their posting ratios
storydump-cli list-categories

# Update category posting ratios (interactive prompts)
storydump-cli update-category-mix

# View ratio history (Type 2 SCD)
storydump-cli category-mix-history --limit 10
```

### User Management

```bash
# List users
storydump-cli list-users

# Promote user to admin
storydump-cli promote-user <telegram_user_id> --role admin
```

### Health Check

```bash
# Check system health
storydump-cli check-health
```

## Telegram Bot Commands

The bot responds to these commands in Telegram:

### Core Commands
- `/start` - Initialize bot and show welcome message
- `/status` - Show system health and queue status
- `/help` - Show all available commands

### Queue Management
- `/queue` - View pending scheduled posts
- `/next` - Force-send next scheduled post immediately
- `/schedule [N]` - Create N days of posting schedule (default: 7)
- `/reset` - Reset posting queue to empty (with confirmation)

### Operational Control
- `/pause` - Pause automatic posting
- `/resume` - Resume posting (with smart overdue handling)
- `/cleanup` - Delete recent bot messages from chat

### Information
- `/stats` - Show media library statistics
- `/history [N]` - Show last N posts (default: 5)
- `/locks` - View permanently rejected items

## Architecture

**Phase 1** (Telegram-Only Mode) - ✅ COMPLETE (v1.0.1):
- ✅ Smart scheduling + Telegram notifications
- ✅ Team posts manually to Instagram
- ✅ No Instagram API needed
- ✅ 147 comprehensive tests
- ✅ Production-tested and deployed

**Phase 1.5** (Telegram Enhancements) - ✅ COMPLETE (v1.3.0):
- ✅ Permanent Reject button for unwanted media (infinite locks)
- ✅ Bot lifecycle notifications (startup/shutdown with system status)
- ✅ Instagram deep links (one-tap Instagram app opening)
- ✅ Enhanced captions with workflow instructions
- ✅ 3-button layout: Posted, Skip, Reject
- ✅ 7 new bot commands: `/pause`, `/resume`, `/schedule`, `/stats`, `/history`, `/locks`, `/reset`
- ✅ Smart overdue handling when resuming after pause

**Phase 1.6** (Category Scheduling) - ✅ COMPLETE (v1.4.0):
- ✅ Category-based media organization (folder structure → category)
- ✅ Configurable posting ratios per category (e.g., 70% memes, 30% merch)
- ✅ Type 2 SCD tracking for ratio history
- ✅ Interactive ratio configuration during indexing
- ✅ Scheduler integration with category-aware slot allocation
- ✅ 488 comprehensive tests

**Phase 2** (Instagram API Automation) - ✅ COMPLETE (v1.5.0):
- ✅ Instagram Graph API integration with rate limiting
- ✅ Cloudinary media hosting with TTL expiration
- ✅ Encrypted token management with auto-refresh
- ✅ Multi-account support (add/switch/deactivate via Telegram)
- ✅ Hybrid mode: auto-post via API, fallback to Telegram on errors
- ✅ Per-chat settings stored in database
- ✅ "🤖 Auto Post to Instagram" button when API enabled

**Phase 1.8** (Telegram UX Improvements) - ✅ COMPLETE:
- ✅ Native Telegram command menu (autocomplete with descriptions)
- ✅ `/cleanup` command to delete recent bot messages
- ✅ `/reset` command to clear posting queue (renamed from `/clear`)
- ✅ Message tracking (100-message cache) for efficient cleanup
- ✅ TelegramService refactored from 3,500-line monolith into 5 handler modules
- ✅ Verbose settings expansion (controls more message types)
- ✅ 488 comprehensive tests

## Development

### Running Tests

The project includes 488 comprehensive tests with automatic test database setup:

```bash
# Run all tests with coverage
pytest --cov=src --cov-report=html

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Force process next post (development testing)
storydump-cli process-queue --force
```

### Project Structure

```
storydump/
├── src/                    # Main application code
│   ├── config/            # Configuration management
│   ├── models/            # Database models
│   ├── repositories/      # Data access layer
│   ├── services/          # Business logic
│   ├── utils/             # Utility functions
│   └── main.py            # Application entry point
├── cli/                   # CLI commands
├── tests/                 # Test suite
├── scripts/               # Database scripts
└── media/                 # Media storage
    └── stories/           # Instagram stories
        ├── memes/         # Meme content
        └── merch/         # Merchandise content
```

## Documentation

📚 **[Complete Documentation Index](documentation/README.md)**

Key resources:
- **[Quick Start Guide](documentation/guides/quickstart.md)** - Get running in 10 minutes
- **[Deployment Guide](documentation/guides/deployment.md)** - Production deployment checklist
- **[Testing Guide](documentation/guides/testing-guide.md)** - How to run and write tests
- **[Technical Specification](documentation/planning/instagram_automation_plan.md)** - Complete implementation plan
- **[Developer Guide](CLAUDE.md)** - Development guidelines and architecture

## License

MIT License - see LICENSE file for details

## Support

For issues and questions, please open a GitHub issue.
