# Storyline AI - Instagram Story Automation System

A self-hosted Instagram Story scheduling system with Telegram-based team collaboration.

## Features

- 📅 **Smart Scheduling**: Intelligent posting schedule based on your preferences
- 📱 **Telegram Integration**: Team collaboration via Telegram bot
- 🔄 **Phased Approach**: Start with manual posting, optionally enable automation
- 🔒 **TTL Locks**: Prevent premature reposts
- 📊 **Full Audit Trail**: Track who posted what and when
- 🎨 **Image Validation**: Automatic validation against Instagram requirements

## Quick Start

### 1. Installation

```bash
# Clone repository
git clone <your-repo-url>
cd storyline-ai

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
# Copy example environment file
cp .env.example .env

# Edit .env with your credentials
nano .env
```

Required configuration:
- `TELEGRAM_BOT_TOKEN`: Get from @BotFather on Telegram
- `TELEGRAM_CHANNEL_ID`: Your Telegram channel ID
- `ADMIN_TELEGRAM_CHAT_ID`: Your personal chat ID for alerts
- `DB_PASSWORD`: PostgreSQL password (optional for local development)

### 3. Database Setup

```bash
# Create database
createdb storyline_ai

# Run schema setup
psql -U postgres -d storyline_ai -f scripts/setup_database.sql

# Or use Python script
python scripts/init_db.py
```

### 4. Index Your Media

```bash
# Index media files
storyline-cli index-media /path/to/media/stories

# List indexed media
storyline-cli list-media --limit 20
```

### 5. Create Schedule

```bash
# Create 7-day posting schedule
storyline-cli create-schedule --days 7

# View queue
storyline-cli list-queue
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
storyline-cli index-media /path/to/media

# List all media items
storyline-cli list-media --limit 50 --active-only

# Validate image
storyline-cli validate-image /path/to/image.jpg
```

### Queue Management

```bash
# Create posting schedule
storyline-cli create-schedule --days 7

# Process pending posts
storyline-cli process-queue

# View queue
storyline-cli list-queue
```

### User Management

```bash
# List users
storyline-cli list-users

# Promote user to admin
storyline-cli promote-user <telegram_user_id> --role admin
```

### Health Check

```bash
# Check system health
storyline-cli check-health
```

## Architecture

**Phase 1** (Telegram-Only Mode) - ✅ COMPLETE:
- ✅ Smart scheduling + Telegram notifications
- ✅ Team posts manually to Instagram
- ✅ No Instagram API needed
- ✅ 147 comprehensive tests
- ✅ Production-tested and deployed

**Phase 2** (Hybrid Mode - Optional):
- 🔄 Enable Instagram API for simple stories
- 🔄 Telegram workflow for interactive stories
- 🔄 Requires Meta Developer setup + Cloudinary
- 🔄 Activate with `ENABLE_INSTAGRAM_API=true`

## Development

### Running Tests

Phase 1 includes 147 comprehensive tests with automatic test database setup:

```bash
# Run all tests with coverage
pytest --cov=src --cov-report=html

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Force process next post (development testing)
storyline-cli process-queue --force
```

### Project Structure

```
storyline-ai/
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
