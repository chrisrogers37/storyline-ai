# Storyline AI - Instagram Story Automation System
## Complete Implementation Plan v4.0 - Smart Scheduling with Team Collaboration

---

## 📋 Executive Summary

**What is Storyline AI?**
A self-hosted Instagram Story scheduling system that sends smart notifications to your team via Telegram. Start with 100% manual posting (Phase 1), optionally add Instagram API automation later (Phase 2).

**Why This Approach?**
- ✅ **Fast to market**: 30-minute setup, no API complexity
- ✅ **Low risk**: Validate scheduling logic before adding automation
- ✅ **Flexible**: Start simple, add automation when ready
- ✅ **No commitment**: Phase 2 is optional, not required

**Phase 1 (Start Here)**: Telegram-Only Mode
- Smart scheduling + Telegram notifications
- Team posts manually to Instagram (15-30 seconds)
- No Instagram API or Cloudinary needed
- Setup time: 30 minutes

**Phase 2 (Optional)**: Add Automation
- Enable Instagram API for simple stories
- Telegram workflow for interactive stories
- Requires: Meta Developer setup + Cloudinary
- Setup time: 1-2 hours
- **Activation**: Flip one config flag (`ENABLE_INSTAGRAM_API=true`)

**Recommended Path**: Build Phase 1 → Test for 1-2 weeks → Decide if Phase 2 is needed

---

## Project Overview

### Purpose
An open-source, self-hosted Instagram Story scheduling and automation system for content creators. The system intelligently schedules posts and sends notifications to a Telegram channel where team members can post to Instagram in 15-30 seconds. Optional automation via Instagram Graph API can be enabled for simple stories without interactive elements.

**Key Insight**: Start with Telegram-first workflow (100% manual posting with smart scheduling), then optionally enable Instagram Graph API automation for simple stories. This phased approach lets you validate the system quickly while keeping full automation ready when you need it.

### Key Features
- **Smart Scheduling**: Intelligent posting schedule based on your preferences (time windows, frequency)
- **Team Collaboration via Telegram**: All posts sent to shared Telegram channel with workflow tracking
- **Flexible Tagging**: Tag stories with custom metadata (not just "meme" vs "merch" - use any tags you want)
- **Multi-User Management**: Team members can claim and complete posts
- **Audit Trail**: Track who posted what and when
- **Optional Automation**: Enable Instagram Graph API posting for simple stories (feature flag)
- **Phased Rollout**: Start Telegram-only, enable automation when ready
- **Self-Hosted**: Runs on Raspberry Pi with PostgreSQL
- **Cloud-Ready**: Modular services allow easy migration to cloud storage and hosting
- **Database as Source of Truth**: Filesystem is just storage; all logic queries PostgreSQL
- **Open Source Ready**: Generalizable for any creator or team

### Tech Stack
- **Language**: Python 3.10+
- **Database**: PostgreSQL (local → Neon migration path)
- **Notifications**: Telegram Bot API (primary workflow)
- **Hosting**: Raspberry Pi (local → Railway/Render migration path)
- **Architecture**: Service-oriented with strict separation of concerns

**Optional (Phase 2 - Automation)**:
- **Cloud Storage**: Cloudinary (for automated posts only - free tier sufficient)
- **API**: Instagram Graph API (official, no ban risk)

### Phased Deployment Strategy

**Phase 1: Telegram-Only Mode (Recommended Start)**
```
Local File → Database → Scheduler → Telegram Notification → Team Member → Instagram App → Posted ✅
```
- **All posts** go through Telegram (100% manual posting)
- Smart scheduling handles timing and frequency
- Team posts manually to Instagram in 15-30 seconds
- Full audit trail of who posted what
- No Instagram API or Cloudinary needed yet
- **Enable this mode**: `ENABLE_INSTAGRAM_API=false` in `.env`

**Phase 2: Hybrid Mode (Optional - Enable When Ready)**
```
Workflow A (Simple Stories):
Local File → Cloudinary (temp) → Instagram API → Posted ✅ (automated)

Workflow B (Interactive Stories):
Local File → Telegram Notification → Team Member → Instagram App → Posted ✅ (manual)
```
- System routes based on `requires_interaction` flag
- Simple stories (no stickers) → Automated via API
- Interactive stories (links, polls) → Manual via Telegram
- **Enable this mode**: `ENABLE_INSTAGRAM_API=true` in `.env`
- Requires: Instagram API setup + Cloudinary account

**Why This Approach?**
- ✅ Start using the system immediately (no API setup needed)
- ✅ Validate scheduling logic and team workflow first
- ✅ Add automation later with a simple config change
- ✅ No code changes needed between phases
- ✅ Can revert to Telegram-only anytime (just flip the flag)

---

## Quick Start Guide

### 30-Minute Setup (Phase 1 - Telegram-Only)

**Prerequisites**:
- Raspberry Pi (or any Linux server) with PostgreSQL installed
- Telegram account
- 10-50 test images

**Steps**:

1. **Create Telegram Bot** (5 minutes)
   - Message @BotFather on Telegram
   - Create bot, get token
   - Create private channel, add bot as admin
   - Get channel ID

2. **Install System** (10 minutes)
   ```bash
   git clone https://github.com/yourusername/storyline-ai.git
   cd storyline-ai
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure** (5 minutes)
   ```bash
   cp .env.example .env
   nano .env
   # Set: DB credentials, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID
   # Keep: ENABLE_INSTAGRAM_API=false
   ```

4. **Setup Database** (5 minutes)
   ```bash
   psql -U postgres -c "CREATE DATABASE storyline_ai;"
   psql -U postgres -d instagram_automation -f scripts/setup_database.sql
   ```

5. **Test & Run** (5 minutes)
   ```bash
   # Test Telegram connection
   storyline-cli test-telegram
   
   # Index your media files
   storyline-cli index-media
   
   # Create schedule
   storyline-cli create-schedule
   
   # Start the system
   python -m src.main
   ```

**What Happens Next**:
- System sends first notification to Telegram
- You download image, post to Instagram manually
- Mark as complete in Telegram
- System tracks completion
- Repeat for each scheduled post

**You're Done!** 🎉

No Instagram API setup needed. No Cloudinary account needed. Just smart scheduling + Telegram workflow.

---

## System Specifications & Scale

### Production Environment

**Hardware**: Raspberry Pi (16GB RAM, purchased 2024)
- ✅ Sufficient for PostgreSQL database
- ✅ Handles concurrent operations (scheduler + Telegram bot)
- ✅ Stable internet connection

**Scale Targets**:
- **Posts per day**: 3-5 stories
- **Team size**: 3 members (designed to scale to multiple teams)
- **Media library**: 2,000-3,000 images at full production
- **Testing**: Start with 10-50 images for initial validation

**Database Performance**:
- PostgreSQL on 16GB RAM handles 3,000+ media items easily
- Indexed queries for fast media selection
- Efficient duplicate detection via hash indexing

**Cloudinary Usage** (Free Tier - Phase 2 Only):
- 25GB bandwidth/month = ~12,500 posts/month
- At 3-5 posts/day = ~100-150 posts/month
- **Usage**: ~1-2% of free tier (plenty of headroom)
- **Note**: Not needed for Phase 1 (Telegram-only mode)

**Architecture Benefits**:
- Single process design minimizes RAM usage
- Database-driven logic (no heavy in-memory caching needed)
- Efficient file hash calculation (chunked reading)
- Cloudinary images deleted after posting (zero storage used)

### Testing & Development

**Initial Testing**:
1. Start with 10-50 sample images
2. Validate media indexing and hash calculation
3. Test scheduling logic with small dataset
4. Verify Telegram workflow with team
5. Gradually scale to full 2,000-3,000 image library

**Dry Run Mode**:
- Test full system without posting
- Validate all logic before going live
- No API quota usage during testing

---

## System Architecture

### Phase 1: Telegram-Only Mode (Start Here)

```
┌─────────────────────────────────────────────────────┐
│      Manual File Upload to Raspberry Pi             │
│      (via SFTP, USB, etc.)                           │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│   Local Filesystem (/home/pi/media/)                │
│   - stories/ (flat or nested directories)           │
│   - metadata.json (optional, per directory)         │
│   - Tag stories with custom metadata                │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼ (CLI: index-media)
┌─────────────────────────────────────────────────────┐
│        Media Ingestion Service                       │
│  - Scans directories, calculates hashes             │
│  - Reads metadata, inserts to PostgreSQL            │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│          PostgreSQL Database                         │
│          (Source of Truth)                           │
│  - media_items, posting_queue, posting_history       │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼ (Scheduler queries DB)
┌─────────────────────────────────────────────────────┐
│            Scheduler Service                         │
│  - Creates intelligent posting schedule              │
│  - Respects frequency and time windows              │
└────────────────────┬────────────────────────────────┘
                     │
                     │ ENABLE_INSTAGRAM_API=false
                     │ (ALL posts go to Telegram)
                     ▼
           ┌────────────────────────────┐
           │ Telegram Notification      │
           │ Service                    │
           │                            │
           │  1. Send image directly    │
           │     from filesystem        │
           │  2. Include metadata       │
           │  3. Show inline buttons    │
           │  4. Wait for team action   │
           │  5. Update DB on callback  │
           └────────────┬───────────────┘
                        │
                        ▼
           ┌────────────────────────────┐
           │   Telegram Channel         │
           │   (Team Members)           │
           │                            │
           │  📸 Story notification     │
           │  🔗 Metadata & links       │
           │  [✅ Posted] [⏭️ Skip]    │
           │                            │
           │  Team member:              │
           │  1. Downloads image        │
           │  2. Posts to Instagram     │
           │  3. Marks as posted        │
           └────────────────────────────┘
```

### Phase 2: Hybrid Mode (Optional - Enable Later)

```
┌─────────────────────────────────────────────────────┐
│            Scheduler Service                         │
│  - Creates intelligent posting schedule              │
└────────────────────┬────────────────────────────────┘
                     │
                     │ ENABLE_INSTAGRAM_API=true
                     │ (Routes based on requires_interaction)
                     │
        ┌────────────┴────────────┐
        │                         │
        │ requires_interaction    │ requires_interaction
        │ = false                 │ = true
        ▼                         ▼
┌──────────────────────┐   ┌────────────────────────────┐
│  Posting Service     │   │ Telegram Notification      │
│  (Automated)         │   │ Service (Manual)           │
│                      │   │                            │
│  1. Load from DB     │   │  1. Send to Telegram       │
│  2. Upload Cloudinary│   │  2. Team posts manually    │
│  3. Post to Instagram│   │  3. Marks as posted        │
│  4. Update DB        │   │                            │
│  5. Cleanup Cloudinary│  │                            │
└──────────────────────┘   └────────────────────────────┘
         │                              │
         ▼                              ▼
    ✅ Posted                  ✅ Posted (by team)
    (automated)                (manual)
```

### Decision Flow

**How the System Routes Each Post**:

```
┌─────────────────────────────────────┐
│  Queue Item Ready to Process        │
└──────────────┬──────────────────────┘
               │
               ▼
        ┌──────────────────┐
        │ Check Feature    │
        │ Flag:            │
        │ ENABLE_          │
        │ INSTAGRAM_API?   │
        └──────┬───────────┘
               │
        ┌──────┴──────┐
        │             │
    false         true
        │             │
        │             ▼
        │      ┌──────────────────┐
        │      │ Check Media Item:│
        │      │ requires_        │
        │      │ interaction?     │
        │      └──────┬───────────┘
        │             │
        │      ┌──────┴──────┐
        │      │             │
        │   false         true
        │      │             │
        ▼      ▼             ▼
   ┌────────┐ ┌──────────┐ ┌────────┐
   │Telegram│ │Instagram │ │Telegram│
   │        │ │   API    │ │        │
   │ Manual │ │Automated │ │ Manual │
   └────────┘ └──────────┘ └────────┘
   
   Phase 1    Phase 2       Phase 2
   (Always)   (Simple)      (Interactive)
```

**Examples**:

| Scenario | `ENABLE_INSTAGRAM_API` | `requires_interaction` | Result |
|----------|------------------------|------------------------|--------|
| Phase 1 - Any story | `false` | `false` | → Telegram |
| Phase 1 - Any story | `false` | `true` | → Telegram |
| Phase 2 - Meme | `true` | `false` | → Instagram API ✨ |
| Phase 2 - Product | `true` | `true` | → Telegram |

---

### Separation of Concerns

**Layer 0: Configuration (Global Settings)**
- `src/config/settings.py`: Global settings object loaded from environment
- `src/config/database.py`: Database connection and session management
- Single source of truth for all configuration
- Validates required settings based on phase (Phase 1 vs Phase 2)
- Usage: `from src.config.settings import settings`

**Layer 1: Storage (Filesystem + Cloudinary)**
- Local files for scanning/indexing
- Cloudinary for temporary hosting (Instagram API requirement - Phase 2 only)
- No logic, just file I/O

**Layer 2: Data (PostgreSQL)**
- Source of truth for all state
- Tracks posting status, Telegram messages, user actions
- No business logic

**Layer 3: Repositories**
- CRUD operations only
- Pure database queries
- Examples: `MediaRepository`, `QueueRepository`, `HistoryRepository`

**Layer 4: Services (Business Logic)**

*Core Services (Phase 1)*:
- `MediaIngestionService`: Scan filesystem, calculate hashes, insert to database
- `SchedulerService`: Create posting schedule, manage queue
- `PostingService`: Execute posts (orchestrates other services)
- `TelegramService`: All Telegram bot operations (send, receive, callbacks)
- `MediaLockService`: Manage TTL locks, check availability

*Integration Services (Phase 2)*:
- `CloudStorageService`: Upload/delete from cloud storage (Cloudinary, S3, etc.)
- `InstagramAPIService`: All Instagram Graph API calls
- `InstagramMetricsService`: Fetch and store performance metrics

*Future Services (Roadmap)*:
- `ShopifyService`: Sync products from Shopify API
- `ProductLinkService`: Link media items to products
- `AnalyticsService`: Aggregate metrics and generate insights

**Service Design Principles**:
- ✅ Single Responsibility: Each service manages one domain
- ✅ API-Ready: All services designed for future REST/GraphQL exposure
- ✅ Testable: Services can be mocked/tested independently
- ✅ Stateless: Services don't maintain state between calls

**Layer 5: CLI & Scheduler**
- CLI commands for manual operations
- APScheduler for automated jobs
- Telegram bot (polling mode)

**Configuration Flow**:
```
┌─────────────────────────────────────────┐
│  .env file (environment variables)      │
│  - ENABLE_INSTAGRAM_API=false           │
│  - TELEGRAM_BOT_TOKEN=...               │
│  - DB_PASSWORD=...                      │
│  - etc.                                 │
└──────────────┬──────────────────────────┘
               │ loaded by python-dotenv
               ▼
┌─────────────────────────────────────────┐
│  src/config/settings.py                 │
│                                         │
│  class Settings:                        │
│    ENABLE_INSTAGRAM_API = os.getenv()  │
│    TELEGRAM_BOT_TOKEN = os.getenv()    │
│    ...                                  │
│                                         │
│  settings = Settings()  ← Global       │
└──────────────┬──────────────────────────┘
               │ imported everywhere
               ▼
┌─────────────────────────────────────────┐
│  All Services, Repositories, CLI        │
│                                         │
│  from src.config.settings import       │
│         settings                        │
│                                         │
│  if settings.ENABLE_INSTAGRAM_API:     │
│      # Use Instagram API                │
│  else:                                  │
│      # Use Telegram only                │
└─────────────────────────────────────────┘
```

**Example Usage**:
```python
# In any service, repository, or CLI command
from src.config.settings import settings

# Access configuration
if settings.ENABLE_INSTAGRAM_API and not media_item.requires_interaction:
    # Phase 2: Automated posting
    await self._post_automated(queue_item, media_item)
else:
    # Phase 1 or Phase 2 (interactive): Telegram
    await self._post_via_telegram(queue_item, media_item)

# Database connection
print(f"Connecting to: {settings.DATABASE_URL}")

# Telegram
bot_token = settings.TELEGRAM_BOT_TOKEN
channel_id = settings.TELEGRAM_CHANNEL_ID

# Paths
media_path = settings.STORIES_PATH
```

---

## Instagram Graph API Capabilities (As of 2023)

### What the API Can Do ✅

**Story Posting (Since May 2023)**
- ✅ Post image stories via API
- ✅ Post video stories via API
- ✅ Requires publicly accessible HTTPS URL (hence Cloudinary requirement)
- ✅ Official, no ban risk
- ✅ Endpoint: `POST /{ig-user-id}/media` with `media_type=STORIES`

### What the API Cannot Do ❌

**Interactive Elements**
- ❌ Link stickers (requires 10k+ followers + manual addition)
- ❌ Poll stickers
- ❌ Question stickers
- ❌ Quiz stickers
- ❌ Countdown stickers
- ❌ Location tags
- ❌ Mention tags
- ❌ Hashtag stickers
- ❌ Music stickers

### Why This Hybrid Approach Works

**For Simple Stories**: API handles it automatically
- Memes, quotes, announcements
- No user interaction needed
- Fast, automated, reliable

**For Interactive Stories**: Telegram workflow handles it
- Product links (main use case)
- Polls and questions
- Location tags
- Any sticker/interaction
- 15-30 seconds of human time

**Result**: Best of both worlds - automation where possible, human touch where needed.

---

## Getting Started: Phase 1 vs Phase 2

### Phase 1: Telegram-Only Mode (Start Here)

**What You Get**:
- ✅ Smart scheduling system (posts at optimal times)
- ✅ Media library management (index, tag, organize)
- ✅ Telegram notifications with images and metadata
- ✅ Team workflow tracking (who posted what, when)
- ✅ Audit trail and statistics
- ✅ Dry-run mode for testing
- ✅ Full system validation without external APIs

**What You Need**:
- Raspberry Pi (or any Linux server)
- PostgreSQL database
- Telegram bot + channel
- Your media files

**What You DON'T Need (Yet)**:
- ❌ Instagram API setup
- ❌ Cloudinary account
- ❌ Meta Developer account
- ❌ Facebook Business Page

**Setup Time**: ~30 minutes

**How It Works**:
1. System scans your media files
2. Creates intelligent posting schedule
3. At scheduled times, sends notification to Telegram
4. Team member downloads image from Telegram
5. Posts to Instagram manually (15-30 seconds)
6. Marks as complete in Telegram
7. System tracks completion and updates database

**Configuration**:
```bash
# In .env file
ENABLE_INSTAGRAM_API=false  # Keep this false for Phase 1
```

---

### Phase 2: Hybrid Mode (Optional - Add Later)

**When to Enable**:
- ✅ You've validated Phase 1 works well for your team
- ✅ You want to automate simple stories (no stickers)
- ✅ You're comfortable setting up Instagram API
- ✅ You have stories that don't need interactive elements

**Additional Benefits**:
- ✅ Automated posting for simple stories (memes, quotes, announcements)
- ✅ Reduced manual work for non-interactive content
- ✅ Telegram workflow still available for interactive stories

**Additional Requirements**:
- Instagram Business account
- Meta Developer account + app
- Long-lived access token
- Cloudinary account (free tier)

**Setup Time**: ~1-2 hours (mostly Meta Developer setup)

**How It Works**:
1. System checks `ENABLE_INSTAGRAM_API` flag
2. If `true` AND `requires_interaction=false`:
   - Uploads to Cloudinary
   - Posts via Instagram API
   - Deletes from Cloudinary
   - Updates database
3. If `requires_interaction=true`:
   - Sends to Telegram (same as Phase 1)

**Configuration**:
```bash
# In .env file
ENABLE_INSTAGRAM_API=true  # Enable automation

# Add these credentials:
INSTAGRAM_ACCOUNT_ID=your_id
ACCESS_TOKEN=your_token
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_key
CLOUDINARY_API_SECRET=your_secret
```

**Switching Between Phases**:
```bash
# Disable automation (go back to Telegram-only)
ENABLE_INSTAGRAM_API=false

# Enable automation
ENABLE_INSTAGRAM_API=true

# Restart the service
sudo systemctl restart storyline-ai
```

---

### Recommended Path

**Week 1**: Phase 1 (Telegram-Only)
- Set up database, Telegram bot, and basic system
- Index your media library (start with 10-50 images)
- Test scheduling logic
- Validate team workflow
- Ensure everyone is comfortable with Telegram interface

**Week 2**: Refine Phase 1
- Adjust posting frequency and timing
- Add more media files
- Fine-tune metadata and tagging
- Monitor team adoption

**Week 3+**: Consider Phase 2 (Optional)
- If you have many simple stories (no stickers needed)
- If manual posting becomes tedious
- If you want to reduce team workload
- Set up Instagram API and Cloudinary
- Enable automation with `ENABLE_INSTAGRAM_API=true`

**You may never need Phase 2** if:
- Most of your stories need interactive elements (links, polls)
- Team prefers manual control over all posts
- You have a small volume of posts (3-5 per day is easy to manage manually)

---

## Part A: Telegram Bot Setup (Required - Phase 1)

### Why Telegram?

Instagram's official API **cannot add link stickers** to Stories. Telegram provides the perfect workaround:
- ✅ Team collaboration (multiple users can manage posts)
- ✅ Rich media (full-resolution images)
- ✅ Workflow tracking (inline buttons, status updates)
- ✅ Audit trail (who posted what and when)
- ✅ Mobile-first (works perfectly on phones)
- ✅ No additional app required (everyone has Telegram)

### Step 1: Create Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Start a chat and send `/newbot`
3. Follow prompts:
   - **Bot name**: `Instagram Story Manager` (user-facing name)
   - **Username**: `your_brand_story_bot` (must end in `bot`)
4. Save the **Bot Token** (looks like `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
5. Send `/setcommands` to BotFather
6. Select your bot
7. Paste these commands:
```
pending - Show all pending posts
posted - Show recent posting history
stats - Show posting statistics
help - Show help message
```

### Step 2: Create Telegram Channel

1. In Telegram, create a new **Channel** (not a group)
   - Tap menu → New Channel
   - Name: `Instagram Story Queue` (or your preference)
   - Description: `Automated story posting queue for [Your Brand]`
   - **Make it Private** (invite-only)
2. Add your bot as an **Administrator**:
   - Channel settings → Administrators → Add Administrator
   - Search for your bot username
   - Grant permissions: **Post Messages**, **Edit Messages**, **Delete Messages**
3. Get the **Channel ID**:
   - Post a test message in the channel
   - Forward it to **@userinfobot**
   - Note the channel ID (looks like `-1001234567890`)

### Step 3: Configure Bot Settings (Optional but Recommended)

Send these commands to @BotFather:

```
/setdescription - Set bot description
Description: Manages Instagram Story posting workflow for your team

/setabouttext - Set about text
About: This bot sends story notifications and tracks posting completion

/setuserpic - Upload a profile picture for your bot
```

### Step 4: Add Team Members

1. Add team members to your Telegram channel
2. Each member will receive notifications
3. Any member can mark posts as completed
4. Bot tracks who completed each post

**Multi-Team Support**:
- Current setup: Single Instagram account + single Telegram channel
- Future: Multiple Instagram accounts + multiple Telegram channels
- Database schema supports this (just add `instagram_account_id` to config)
- Each team gets their own channel and posting queue
- See "Advanced Configuration" section for multi-team setup

### Step 5: Test the Bot

```bash
# Test bot is working
curl "https://api.telegram.org/bot{BOT_TOKEN}/getMe"

# Should return bot info
{
  "ok": true,
  "result": {
    "id": 123456789,
    "is_bot": true,
    "first_name": "Instagram Story Manager",
    "username": "your_brand_story_bot"
  }
}

# Test channel access
curl "https://api.telegram.org/bot{BOT_TOKEN}/sendMessage?chat_id={CHANNEL_ID}&text=Test message"
```

### Telegram Message Flow Example

**When story requiring interaction is due, bot sends:**

```
📸 STORY #47
━━━━━━━━━━━━━━━━━━━━━
📌 Title: "Dank Meme" Tshirt
🔗 Link: https://shop.com/products/tshirt
🏷️ Tags: product, tshirt, newdrop
⏰ Scheduled: Jan 3, 2026 2:30 PM

👉 Download image above, post to Instagram with link sticker

[📋 Copy Link] [✅ Mark Posted] [⏭️ Skip]

Status: ⏳ PENDING
Queue ID: abc-123
```

**After team member taps "✅ Mark Posted":**

```
📸 STORY #47
━━━━━━━━━━━━━━━━━━━━━
📌 Title: "Dank Meme" Tshirt
🔗 Link: https://shop.com/products/tshirt
🏷️ Tags: product, tshirt, newdrop
⏰ Scheduled: Jan 3, 2026 2:30 PM

Status: ✅ POSTED
👤 Posted by: @sarah
🕐 Posted at: 2:32 PM
📊 Took: 2 minutes

Queue ID: abc-123
```

---

## Part B: Database Schema

### PostgreSQL Setup on Raspberry Pi

**Performance Tuning for 16GB RAM**:

Edit `/etc/postgresql/*/main/postgresql.conf`:

```ini
# Memory Settings (optimized for 16GB RAM Raspberry Pi)
shared_buffers = 2GB                    # 25% of RAM
effective_cache_size = 12GB             # 75% of RAM
maintenance_work_mem = 512MB
work_mem = 32MB

# Checkpoint Settings
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100

# Query Planner
random_page_cost = 1.1                  # SSD/SD card optimization
effective_io_concurrency = 200

# Connection Settings
max_connections = 20                    # Low concurrent load
```

Restart PostgreSQL after changes:
```bash
sudo systemctl restart postgresql
```

**Database Creation**:

```sql
-- Create database
CREATE DATABASE storyline_ai;

-- Connect to database
\c storyline_ai;

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Media items table (source of truth for all media)
CREATE TABLE media_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_path TEXT NOT NULL UNIQUE,
    file_name TEXT NOT NULL,
    file_size BIGINT NOT NULL,
    file_hash TEXT NOT NULL, -- Not unique - allow duplicate content
    mime_type VARCHAR(100),
    
    -- Routing logic: determines auto vs manual posting
    requires_interaction BOOLEAN DEFAULT FALSE, -- TRUE = send to Telegram, FALSE = auto-post
    
    -- Optional metadata (flexible for any use case)
    title TEXT, -- General purpose title (product name, meme title, etc.)
    link_url TEXT, -- Link for sticker (if requires_interaction = TRUE)
    caption TEXT,
    tags TEXT[], -- Array of custom tags (user-defined)
    custom_metadata JSONB, -- Flexible JSON field for any additional data
    
    -- Tracking
    times_posted INTEGER DEFAULT 0,
    last_posted_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    
    -- User tracking
    indexed_by_user_id UUID REFERENCES users(id), -- Who indexed/uploaded this media
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Posting queue table (active work items only)
CREATE TABLE posting_queue (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    media_item_id UUID NOT NULL REFERENCES media_items(id) ON DELETE CASCADE,
    
    scheduled_for TIMESTAMP NOT NULL,
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'processing', 'retrying'
    
    -- Temporary web-hosted URL (e.g., Cloudinary, S3, etc.)
    -- Used during posting process, deleted after completion
    web_hosted_url TEXT,
    web_hosted_public_id TEXT, -- Provider-specific ID for cleanup
    
    -- Telegram tracking (for manual posts)
    telegram_message_id BIGINT,
    telegram_chat_id BIGINT,
    
    -- Retry logic
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    next_retry_at TIMESTAMP,
    last_error TEXT,
    
    -- Timestamps (preserved in history)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT check_status CHECK (status IN ('pending', 'processing', 'retrying'))
);

-- Posting history (permanent audit log - never deleted)
CREATE TABLE posting_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    media_item_id UUID NOT NULL REFERENCES media_items(id),
    queue_item_id UUID, -- Link back to queue (nullable after queue cleanup)
    
    -- Queue lifecycle timestamps (preserved from posting_queue)
    queue_created_at TIMESTAMP NOT NULL, -- When item was added to queue
    queue_deleted_at TIMESTAMP NOT NULL, -- When item was removed from queue
    scheduled_for TIMESTAMP NOT NULL,    -- Original scheduled time
    
    -- Media metadata snapshot (at posting time)
    -- Alternative to Type 2 SCD for media_items
    media_metadata JSONB, -- {title, tags, caption, link_url, custom_metadata}
    
    -- Posting outcome
    posted_at TIMESTAMP NOT NULL,
    status VARCHAR(50) NOT NULL, -- 'posted', 'failed', 'skipped'
    success BOOLEAN NOT NULL,
    
    -- Instagram result (if successful)
    instagram_media_id TEXT,
    instagram_permalink TEXT,
    
    -- User tracking
    posted_by_user_id UUID REFERENCES users(id), -- User who posted (NULL for automated)
    posted_by_telegram_username TEXT, -- Snapshot of username at posting time
    
    -- Error info (if failed)
    error_message TEXT,
    retry_count INTEGER DEFAULT 0, -- How many times we retried
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT check_history_status CHECK (status IN ('posted', 'failed', 'skipped'))
);

-- Users table (auto-populated from Telegram interactions)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Telegram identity (source of truth)
    telegram_user_id BIGINT UNIQUE NOT NULL,
    telegram_username VARCHAR(100),
    telegram_first_name VARCHAR(255),
    telegram_last_name VARCHAR(255),
    
    -- Team
    team_name VARCHAR(255), -- Team/group identifier
    
    -- Role (manually assigned via CLI)
    role VARCHAR(50) DEFAULT 'member', -- 'admin', 'member'
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Auto-tracked stats
    total_posts INTEGER DEFAULT 0,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Service runs table (tracks all service executions)
CREATE TABLE service_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Service identification
    service_name VARCHAR(100) NOT NULL, -- 'MediaIngestionService', 'PostingService'
    method_name VARCHAR(100) NOT NULL, -- 'scan_directory', 'process_pending_posts'
    
    -- Execution context
    user_id UUID REFERENCES users(id), -- Who triggered it (NULL for automated)
    triggered_by VARCHAR(50) DEFAULT 'system', -- 'user', 'system', 'scheduler', 'cli'
    
    -- Timing
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    duration_ms INTEGER, -- Calculated: completed_at - started_at
    
    -- Status
    status VARCHAR(50) NOT NULL DEFAULT 'running', -- 'running', 'completed', 'failed'
    success BOOLEAN,
    
    -- Results
    result_summary JSONB, -- {items_processed: 10, items_failed: 2}
    error_message TEXT,
    error_type VARCHAR(100),
    stack_trace TEXT,
    
    -- Metadata
    input_params JSONB, -- Parameters passed to the method
    metadata JSONB, -- Additional context
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT check_service_run_status CHECK (status IN ('running', 'completed', 'failed'))
);

-- Media posting locks (TTL-based repost prevention)
CREATE TABLE media_posting_locks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    media_item_id UUID NOT NULL REFERENCES media_items(id) ON DELETE CASCADE,
    
    -- Lock details
    locked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    locked_until TIMESTAMP NOT NULL, -- TTL: locked_at + X days
    lock_reason VARCHAR(100) DEFAULT 'recent_post', -- 'recent_post', 'manual_hold', 'seasonal'
    
    -- Who created the lock
    created_by_user_id UUID REFERENCES users(id), -- NULL for system-created locks
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure only one active lock per media item
    CONSTRAINT unique_active_lock UNIQUE (media_item_id, locked_until)
);

-- Shopify products (future integration - Type 2 SCD for historical tracking)
CREATE TABLE shopify_products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shopify_product_id BIGINT NOT NULL, -- Shopify's product ID (natural key)
    
    -- Product details (can change over time)
    title TEXT NOT NULL,
    handle TEXT NOT NULL, -- URL-friendly identifier
    product_url TEXT NOT NULL,
    price DECIMAL(10, 2),
    compare_at_price DECIMAL(10, 2),
    
    -- Metadata
    description TEXT,
    product_type VARCHAR(100),
    vendor VARCHAR(100),
    tags TEXT[],
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    published_at TIMESTAMP,
    
    -- Type 2 SCD: Track historical changes
    version INTEGER NOT NULL DEFAULT 1,
    valid_from TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    valid_to TIMESTAMP, -- NULL = current version
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- Tracking
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure only one current version per product
    CONSTRAINT unique_current_product 
        UNIQUE (shopify_product_id, is_current) 
        WHERE is_current = TRUE
);

-- Link media items to Shopify products (many-to-many)
CREATE TABLE media_product_links (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    media_item_id UUID NOT NULL REFERENCES media_items(id) ON DELETE CASCADE,
    shopify_product_id UUID NOT NULL REFERENCES shopify_products(id) ON DELETE CASCADE,
    
    -- Link metadata
    is_primary BOOLEAN DEFAULT FALSE, -- Is this the hero image for the product?
    display_order INTEGER DEFAULT 0,  -- Order for multiple images per product
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure unique media-product pairs
    CONSTRAINT unique_media_product UNIQUE (media_item_id, shopify_product_id)
);

-- Instagram post performance metrics (future: Meta API integration)
CREATE TABLE instagram_post_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    posting_history_id UUID NOT NULL REFERENCES posting_history(id) ON DELETE CASCADE,
    instagram_media_id TEXT NOT NULL,
    
    -- Engagement metrics
    impressions INTEGER DEFAULT 0,
    reach INTEGER DEFAULT 0,
    replies INTEGER DEFAULT 0,
    taps_forward INTEGER DEFAULT 0,
    taps_back INTEGER DEFAULT 0,
    exits INTEGER DEFAULT 0,
    
    -- Link metrics (if story had link sticker)
    link_clicks INTEGER DEFAULT 0,
    
    -- Metadata
    fetched_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Allow multiple fetches over time (track metric evolution)
    CONSTRAINT unique_metric_fetch UNIQUE (posting_history_id, fetched_at)
);

-- Configuration table
CREATE TABLE config (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default configuration
INSERT INTO config (key, value, description) VALUES
    ('posting_frequency', '3', 'Number of posts per day'),
    ('posting_hours_start', '9', 'Start posting hour (UTC, 24h format)'),
    ('posting_hours_end', '21', 'End posting hour (UTC, 24h format)'),
    ('media_repost_ttl_days', '30', 'Default TTL lock after posting (days)'),
    ('instagram_account_id', '', 'Instagram Business Account ID'),
    ('access_token', '', 'Instagram Graph API access token'),
    ('telegram_bot_token', '', 'Telegram bot token'),
    ('telegram_channel_id', '', 'Telegram channel ID for notifications'),
    ('last_token_refresh', '', 'Last time token was refreshed'),
    ('shopify_store_url', '', 'Shopify store URL (for future integration)'),
    ('shopify_api_key', '', 'Shopify API key (for future integration)');

-- Indexes for performance
CREATE INDEX idx_users_telegram_id ON users(telegram_user_id);
CREATE INDEX idx_users_team ON users(team_name);
CREATE INDEX idx_users_active ON users(is_active) WHERE is_active = TRUE;

CREATE INDEX idx_service_runs_service ON service_runs(service_name);
CREATE INDEX idx_service_runs_started ON service_runs(started_at);
CREATE INDEX idx_service_runs_status ON service_runs(status);
CREATE INDEX idx_service_runs_user ON service_runs(user_id);

CREATE INDEX idx_media_items_active ON media_items(is_active);
CREATE INDEX idx_media_items_requires_interaction ON media_items(requires_interaction);
CREATE INDEX idx_media_items_last_posted ON media_items(last_posted_at);
CREATE INDEX idx_media_items_hash ON media_items(file_hash); -- For duplicate detection
CREATE INDEX idx_media_items_tags ON media_items USING GIN(tags); -- For tag-based queries
CREATE INDEX idx_media_items_indexed_by ON media_items(indexed_by_user_id);

CREATE INDEX idx_posting_queue_scheduled ON posting_queue(scheduled_for);
CREATE INDEX idx_posting_queue_status ON posting_queue(status);
CREATE INDEX idx_posting_queue_telegram_msg ON posting_queue(telegram_message_id);
CREATE INDEX idx_posting_queue_next_retry ON posting_queue(next_retry_at) WHERE next_retry_at IS NOT NULL;
CREATE INDEX idx_posting_queue_media_item ON posting_queue(media_item_id);

CREATE INDEX idx_posting_history_posted_at ON posting_history(posted_at);
CREATE INDEX idx_posting_history_user ON posting_history(posted_by_user_id);
CREATE INDEX idx_posting_history_media_item ON posting_history(media_item_id);
CREATE INDEX idx_posting_history_success ON posting_history(success);
CREATE INDEX idx_posting_history_instagram_id ON posting_history(instagram_media_id);
CREATE INDEX idx_posting_history_metadata ON posting_history USING GIN(media_metadata); -- For JSONB queries

CREATE INDEX idx_media_locks_until ON media_posting_locks(locked_until);
CREATE INDEX idx_media_locks_media_item ON media_posting_locks(media_item_id);
CREATE INDEX idx_media_locks_active ON media_posting_locks(locked_until) WHERE locked_until > NOW();
CREATE INDEX idx_media_locks_created_by ON media_posting_locks(created_by_user_id);

CREATE INDEX idx_shopify_products_shopify_id ON shopify_products(shopify_product_id);
CREATE INDEX idx_shopify_products_current ON shopify_products(shopify_product_id) WHERE is_current = TRUE;
CREATE INDEX idx_shopify_products_valid_range ON shopify_products(shopify_product_id, valid_from, valid_to);
CREATE INDEX idx_shopify_products_active ON shopify_products(is_active) WHERE is_current = TRUE;
CREATE INDEX idx_shopify_products_handle ON shopify_products(handle) WHERE is_current = TRUE;
CREATE INDEX idx_shopify_products_version ON shopify_products(shopify_product_id, version);

CREATE INDEX idx_media_product_links_media ON media_product_links(media_item_id);
CREATE INDEX idx_media_product_links_product ON media_product_links(shopify_product_id);
CREATE INDEX idx_media_product_links_primary ON media_product_links(is_primary) WHERE is_primary = TRUE;

CREATE INDEX idx_instagram_metrics_history ON instagram_post_metrics(posting_history_id);
CREATE INDEX idx_instagram_metrics_media_id ON instagram_post_metrics(instagram_media_id);
CREATE INDEX idx_instagram_metrics_fetched ON instagram_post_metrics(fetched_at);

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_media_items_updated_at BEFORE UPDATE ON media_items
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    
CREATE TRIGGER update_config_updated_at BEFORE UPDATE ON config
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

---

## Data Model Design Decisions

### Queue vs History: Two-Table Pattern

**Why separate tables?**

1. **Performance**: `posting_queue` stays small (only active work), enabling fast queries
2. **Semantics**: Clear separation between "work to do" vs "work done"
3. **Reposting**: Can post same media multiple times without losing history
4. **Archival**: History table can be partitioned/archived without affecting operations

**Queue Lifecycle**:
```
1. Item added to queue → created_at timestamp
2. Processing (with retries if needed)
3. Completion → Insert to history with queue timestamps
4. Delete from queue → queue_deleted_at preserved in history
```

**Best Practice**: Never delete from history (permanent audit log), but queue is ephemeral.

---

### TTL Locks: Preventing Premature Reposts

**Problem**: Don't want to repost the same meme 3 days in a row.

**Solution**: `media_posting_locks` table with TTL (Time-To-Live).

```sql
-- After posting, create a 30-day lock
INSERT INTO media_posting_locks (media_item_id, locked_until)
VALUES ('abc-123', NOW() + INTERVAL '30 days');

-- Scheduler excludes locked media
SELECT m.* FROM media_items m
WHERE NOT EXISTS (
    SELECT 1 FROM media_posting_locks l
    WHERE l.media_item_id = m.id
      AND l.locked_until > NOW()
);
```

**Lock Types**:
- `recent_post`: Default 30-day TTL after posting
- `manual_hold`: Indefinite hold (e.g., seasonal content)
- `seasonal`: Lock until specific date (e.g., Halloween content locked until Oct 1)

**Cleanup**: Locks automatically expire (no manual deletion needed).

---

### User Tracking: Telegram-Native User Management

**Philosophy**: Users are automatically discovered from Telegram interactions. No separate registration system needed!

**User Discovery Flow**:
```
1. User clicks "Mark Posted" in Telegram
2. System extracts Telegram user data (ID, username, name)
3. Check if user exists in database
4. If not, create user record automatically
5. Link action to user in posting_history
6. Update user.last_seen_at and user.total_posts
```

**User Table Design**:
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    telegram_user_id BIGINT UNIQUE NOT NULL,  -- Source of truth
    telegram_username VARCHAR(100),
    telegram_first_name VARCHAR(255),
    telegram_last_name VARCHAR(255),
    team_name VARCHAR(255),  -- Set via CLI
    role VARCHAR(50) DEFAULT 'member',  -- 'admin', 'member'
    is_active BOOLEAN DEFAULT TRUE,
    total_posts INTEGER DEFAULT 0,  -- Auto-incremented
    first_seen_at TIMESTAMP,  -- First interaction
    last_seen_at TIMESTAMP  -- Most recent interaction
);
```

**User Attribution Across Tables**:

| Table | Column | Purpose |
|-------|--------|---------|
| `media_items` | `indexed_by_user_id` | Track who uploaded/indexed media |
| `posting_history` | `posted_by_user_id` | Track who posted to Instagram |
| `media_posting_locks` | `created_by_user_id` | Track who created manual locks |
| `service_runs` | `user_id` | Track who triggered service calls |

**Benefits**:
- ✅ Zero-friction onboarding (users auto-added on first interaction)
- ✅ Single source of truth (Telegram)
- ✅ Complete audit trail (know who did what)
- ✅ Team analytics (see who's most active)
- ✅ Role-based permissions (promote users via CLI)

**User Stats View**:
```sql
CREATE VIEW v_user_stats AS
SELECT 
    u.telegram_username,
    u.role,
    u.team_name,
    COUNT(h.id) as total_posts,
    COUNT(h.id) FILTER (WHERE h.success = TRUE) as successful_posts,
    MAX(h.posted_at) as last_post_at,
    COUNT(DISTINCT DATE(h.posted_at)) as active_days
FROM users u
LEFT JOIN posting_history h ON h.posted_by_user_id = u.id
GROUP BY u.id, u.telegram_username, u.role, u.team_name;
```

**Example: Get or Create User**:
```python
def get_or_create_user(telegram_user_id: int, telegram_data: dict) -> User:
    """Get existing user or create from Telegram data."""
    user = user_repo.get_by_telegram_id(telegram_user_id)
    
    if not user:
        # Auto-create user from Telegram
        user = user_repo.create(
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_data.get('username'),
            telegram_first_name=telegram_data.get('first_name'),
            telegram_last_name=telegram_data.get('last_name'),
            role='member',  # Default role
            is_active=True
        )
        logger.info(f"New user discovered: @{telegram_data.get('username')}")
    else:
        # Update last seen
        user_repo.update_last_seen(user.id)
    
    return user
```

---

### Service Execution Tracking

**Philosophy**: Every service call should be logged for observability and debugging.

**Service Runs Table**:
```sql
CREATE TABLE service_runs (
    id UUID PRIMARY KEY,
    service_name VARCHAR(100) NOT NULL,  -- 'MediaIngestionService'
    method_name VARCHAR(100) NOT NULL,   -- 'scan_directory'
    user_id UUID REFERENCES users(id),   -- Who triggered it
    triggered_by VARCHAR(50),            -- 'user', 'system', 'scheduler', 'cli'
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    duration_ms INTEGER,
    status VARCHAR(50),  -- 'running', 'completed', 'failed'
    success BOOLEAN,
    result_summary JSONB,  -- {indexed: 10, skipped: 2}
    error_message TEXT,
    error_type VARCHAR(100),
    stack_trace TEXT,
    input_params JSONB,  -- Parameters passed to method
    metadata JSONB  -- Additional context
);
```

**Benefits**:
- ✅ Complete audit trail of all service executions
- ✅ Performance monitoring (track execution times)
- ✅ Error debugging (stack traces preserved)
- ✅ User attribution (know who triggered what)
- ✅ Result tracking (see what was accomplished)

**Base Service Pattern**:

All services inherit from `BaseService` which automatically logs execution:

```python
class MediaIngestionService(BaseService):
    def scan_directory(self, path: str, user_id: UUID = None):
        with self.track_execution(
            method_name="scan_directory",
            user_id=user_id,
            triggered_by="cli",
            input_params={"path": path}
        ) as run_id:
            # Your service logic here
            result = self._do_scan(path)
            
            # Record results
            self.set_result_summary(run_id, {
                "indexed": result.indexed_count,
                "skipped": result.skipped_count
            })
            
            return result
```

**Query Examples**:
```sql
-- Find slow service calls
SELECT service_name, method_name, AVG(duration_ms) as avg_ms
FROM service_runs
WHERE status = 'completed'
GROUP BY service_name, method_name
ORDER BY avg_ms DESC;

-- Find recent failures
SELECT service_name, method_name, error_message, started_at
FROM service_runs
WHERE status = 'failed'
  AND started_at > NOW() - INTERVAL '24 hours'
ORDER BY started_at DESC;

-- User activity
SELECT u.telegram_username, COUNT(*) as service_calls
FROM service_runs sr
JOIN users u ON u.id = sr.user_id
WHERE sr.started_at > NOW() - INTERVAL '7 days'
GROUP BY u.telegram_username
ORDER BY service_calls DESC;
```

---

### Shopify Integration: Product-Media Linking

**Future Feature**: Link Instagram stories to Shopify products.

**Schema**:
```
shopify_products (1) ←→ (many) media_product_links ←→ (many) media_items
```

**Use Cases**:
1. **Product Stories**: Automatically include product link in Telegram notification
2. **Multi-Image Products**: Link multiple lifestyle shots to one product
3. **Hero Images**: Mark primary image for each product (`is_primary` flag)
4. **Product Analytics**: Track which products get the most engagement

**Telegram Workflow Enhancement**:
```
📸 STORY #47
━━━━━━━━━━━━━━━━━━━━━
📌 Title: "Dank Meme" Tshirt
🛍️ Product: Cool Tshirt ($29.99)
🔗 Link: https://shop.com/products/cool-tshirt
🏷️ Tags: product, tshirt, newdrop

[📋 Copy Link] [✅ Mark Posted] [⏭️ Skip]
```

---

### Instagram Metrics: Performance Tracking

**Future Feature**: Pull engagement metrics from Instagram Graph API.

**Schema**: `instagram_post_metrics` linked to `posting_history`.

**Metrics Tracked**:
- Impressions, Reach, Replies
- Taps forward/back, Exits
- Link clicks (for stories with links)

**Time-Series Data**: Multiple fetches over time (24h, 7d, 30d) to track metric evolution.

**Analytics Queries**:
```sql
-- Best performing stories
SELECT 
    h.media_item_id,
    m.title,
    MAX(pm.reach) as max_reach,
    MAX(pm.link_clicks) as total_clicks
FROM posting_history h
JOIN instagram_post_metrics pm ON pm.posting_history_id = h.id
JOIN media_items m ON m.id = h.media_item_id
GROUP BY h.media_item_id, m.title
ORDER BY max_reach DESC
LIMIT 10;

-- Product performance
SELECT 
    sp.title as product_name,
    COUNT(h.id) as times_posted,
    AVG(pm.reach) as avg_reach,
    SUM(pm.link_clicks) as total_clicks
FROM shopify_products sp
JOIN media_product_links mpl ON mpl.shopify_product_id = sp.id
JOIN posting_history h ON h.media_item_id = mpl.media_item_id
LEFT JOIN instagram_post_metrics pm ON pm.posting_history_id = h.id
GROUP BY sp.id, sp.title
ORDER BY total_clicks DESC;
```

---

### Complete Data Model Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     CORE TABLES                             │
└─────────────────────────────────────────────────────────────┘

┌──────────────────┐
│  media_items     │ ← Source files + metadata
│  ──────────────  │
│  • file_path     │
│  • file_hash     │
│  • title         │
│  • link_url      │
│  • tags[]        │
│  • times_posted  │
└────────┬─────────┘
         │
         │ 1:many
         ▼
┌──────────────────┐      ┌──────────────────────┐
│ posting_queue    │      │ media_posting_locks  │
│ ──────────────   │      │ ──────────────────   │
│ • scheduled_for  │      │ • locked_until       │
│ • status         │      │ • lock_reason        │
│ • web_hosted_url │      └──────────────────────┘
│ • retry_count    │               ▲
└────────┬─────────┘               │
         │                         │ TTL locks
         │ on completion           │
         ▼                         │
┌──────────────────┐               │
│ posting_history  │───────────────┘
│ ──────────────   │
│ • queue_created  │
│ • queue_deleted  │
│ • posted_at      │
│ • success        │
│ • instagram_id   │
└────────┬─────────┘
         │
         │ 1:many
         ▼
┌──────────────────────┐
│ instagram_post_      │
│ metrics              │
│ ──────────────────   │
│ • impressions        │
│ • reach              │
│ • link_clicks        │
│ • fetched_at         │
└──────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              FUTURE: SHOPIFY INTEGRATION                    │
└─────────────────────────────────────────────────────────────┘

┌──────────────────┐         ┌──────────────────────┐
│  media_items     │◄────────┤ media_product_links  │
└──────────────────┘  many   │ ──────────────────   │
                              │ • is_primary         │
                              │ • display_order      │
                              └──────────┬───────────┘
                                         │ many
                                         ▼
                              ┌──────────────────────────┐
                              │ shopify_products         │
                              │ (Type 2 SCD)             │
                              │ ──────────────────────   │
                              │ • shopify_product_id     │
                              │ • title                  │
                              │ • price                  │
                              │ • version                │
                              │ • valid_from             │
                              │ • valid_to               │
                              │ • is_current             │
                              └──────────────────────────┘
                                         ▲
                                         │ temporal join
                                         │ (at posting time)
                                         │
                              ┌──────────┴───────────┐
                              │ posting_history      │
                              │ ──────────────────   │
                              │ • posted_at          │
                              └──────────────────────┘
                              
Note: Temporal join ensures we get the correct
product version for each posting based on posted_at
```

**Key Relationships**:
- **1:many**: One media item → many queue entries (reposting)
- **1:many**: One media item → many locks (TTL management)
- **1:many**: One history entry → many metric snapshots (time-series)
- **many:many**: Media items ↔ Shopify products (via link table)

---

### Type 2 SCD for Shopify Products

**Design Decision**: `shopify_products` uses Type 2 SCD, but `media_items` does NOT.

**Why Type 2 SCD for Shopify?**

Shopify products change over time (price, title, description). Type 2 SCD tracks these changes by creating new versions instead of updating existing rows.

**Why NOT SCD for Media Items?**

1. **File content is immutable**: If the image changes, `file_hash` changes → it's a new media item
2. **Metadata rarely changes**: Title, tags, caption are mostly set once
3. **Snapshot alternative**: Store metadata in `posting_history.media_metadata` JSONB at posting time
4. **Complexity not justified**: Overhead doesn't match benefit

```sql
-- Media items: Simple current-state table
CREATE TABLE media_items (
    id UUID PRIMARY KEY,
    file_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    title TEXT,
    tags TEXT[],
    -- No version, valid_from, valid_to
);

-- Snapshot metadata at posting time instead
CREATE TABLE posting_history (
    id UUID PRIMARY KEY,
    media_item_id UUID,
    media_metadata JSONB,  -- Snapshot: {title, tags, caption}
    posted_at TIMESTAMP
);
```

**Benefits**:
1. **Historical Accuracy**: "What was the price when we posted story #47?"
2. **Performance Analysis**: "Did the price increase affect click-through rate?"
3. **A/B Testing**: "Which product title performed better?"
4. **Audit Trail**: Complete history of product changes

**How It Works**:

```sql
-- Initial product sync (Version 1)
INSERT INTO shopify_products (
    shopify_product_id, title, price, 
    version, valid_from, is_current
) VALUES (
    123, 'Cool Tshirt', 29.99,
    1, NOW(), TRUE
);

-- Product updated in Shopify (Version 2)
-- Step 1: Close current version
UPDATE shopify_products 
SET valid_to = NOW(), is_current = FALSE
WHERE shopify_product_id = 123 AND is_current = TRUE;

-- Step 2: Insert new version
INSERT INTO shopify_products (
    shopify_product_id, title, price,
    version, valid_from, is_current
) VALUES (
    123, 'Awesome Tee', 34.99,
    2, NOW(), TRUE
);
```

**Query Patterns**:

```sql
-- Get current version (most common - fast with index)
SELECT * FROM shopify_products 
WHERE shopify_product_id = 123 
  AND is_current = TRUE;

-- Get product state at specific time (for analytics)
SELECT * FROM shopify_products 
WHERE shopify_product_id = 123
  AND valid_from <= '2024-01-15 10:00:00'
  AND (valid_to IS NULL OR valid_to > '2024-01-15 10:00:00');

-- Get all versions (audit trail)
SELECT version, title, price, valid_from, valid_to
FROM shopify_products
WHERE shopify_product_id = 123
ORDER BY version;

-- Join with posting history (get product state at posting time)
SELECT 
    h.posted_at,
    p.title as product_title_at_posting,
    p.price as price_at_posting,
    m.link_clicks
FROM posting_history h
JOIN media_product_links mpl ON mpl.media_item_id = h.media_item_id
JOIN shopify_products p ON p.shopify_product_id = mpl.shopify_product_id
    AND p.valid_from <= h.posted_at
    AND (p.valid_to IS NULL OR p.valid_to > h.posted_at)
LEFT JOIN instagram_post_metrics m ON m.posting_history_id = h.id
WHERE h.media_item_id = 'abc-123';
```

**Service Implementation**:

```python
class ShopifyService:
    def sync_product(self, shopify_data):
        """Sync product with Type 2 SCD logic."""
        shopify_id = shopify_data['id']
        
        # Get current version
        current = self.repo.get_current_version(shopify_id)
        
        if not current:
            # First sync - create initial version
            self.repo.create_version(
                shopify_data,
                version=1,
                is_current=True
            )
        else:
            # Check if product changed
            if self._has_changes(current, shopify_data):
                # Close current version
                self.repo.close_version(current.id)
                
                # Create new version
                self.repo.create_version(
                    shopify_data,
                    version=current.version + 1,
                    is_current=True
                )
    
    def _has_changes(self, current, new_data):
        """Check if product attributes changed."""
        return (
            current.title != new_data['title'] or
            current.price != Decimal(str(new_data['price'])) or
            current.description != new_data['description'] or
            current.handle != new_data['handle']
        )
```

**Analytics with Historical Context**:

```python
class AnalyticsService:
    def get_product_performance_over_time(self, shopify_product_id):
        """Get performance with product state at each posting."""
        
        # This query automatically gets the correct product version
        # for each posting based on temporal join
        query = """
        SELECT 
            h.posted_at,
            p.version as product_version,
            p.title as title_at_posting,
            p.price as price_at_posting,
            AVG(m.reach) as avg_reach,
            AVG(m.link_clicks) as avg_clicks
        FROM posting_history h
        JOIN media_product_links mpl 
            ON mpl.media_item_id = h.media_item_id
        JOIN shopify_products p 
            ON p.shopify_product_id = :product_id
            AND p.valid_from <= h.posted_at
            AND (p.valid_to IS NULL OR p.valid_to > h.posted_at)
        LEFT JOIN instagram_post_metrics m 
            ON m.posting_history_id = h.id
        WHERE mpl.shopify_product_id = :product_id
        GROUP BY h.posted_at, p.version, p.title, p.price
        ORDER BY h.posted_at
        """
        
        # Results show how performance changed across product versions
        # Example output:
        # posted_at           | version | title         | price | avg_clicks
        # 2024-01-10 10:00:00 | 1       | Cool Tshirt   | 29.99 | 45
        # 2024-01-15 14:00:00 | 1       | Cool Tshirt   | 29.99 | 52
        # 2024-01-20 11:00:00 | 2       | Awesome Tee   | 34.99 | 38
        # 2024-01-25 09:00:00 | 2       | Awesome Tee   | 34.99 | 41
```

**Storage Considerations**:

- **Overhead**: One row per product change (not per posting)
- **Typical**: 5-10 versions per product over lifetime
- **1000 products** × **10 versions** = **10,000 rows** (manageable)
- **Indexes**: Optimized for current version queries (most common)

**Maintenance**:

```sql
-- Archive old versions (optional - after 2+ years)
DELETE FROM shopify_products
WHERE valid_to < NOW() - INTERVAL '2 years'
  AND is_current = FALSE;

-- Cleanup orphaned versions (no linked media)
DELETE FROM shopify_products p
WHERE p.is_current = FALSE
  AND NOT EXISTS (
    SELECT 1 FROM media_product_links mpl
    WHERE mpl.shopify_product_id = p.shopify_product_id
  );
```

---

### Web-Hosted URL: Provider-Agnostic Design

**Column Name**: `web_hosted_url` (not `cloudinary_url`)

**Why Generic?**
- ✅ Future-proof for different providers (S3, Cloudinary, Backblaze, etc.)
- ✅ Clear semantics: "temporary web-accessible URL for posting"
- ✅ Not tied to specific vendor

**Usage**:
```python
# Phase 2: Cloudinary
queue_item.web_hosted_url = "https://res.cloudinary.com/..."
queue_item.web_hosted_public_id = cloudinary_result["public_id"]

# Future: AWS S3
queue_item.web_hosted_url = "https://s3.amazonaws.com/..."
queue_item.web_hosted_public_id = s3_key

# Future: Self-hosted
queue_item.web_hosted_url = "https://cdn.mysite.com/..."
queue_item.web_hosted_public_id = file_hash
```

---

## Service-Oriented Architecture

### Design Philosophy

**Single Responsibility**: Each service manages one domain or integration.

**API-First**: All services designed to be exposed via REST API in the future.

**Testable**: Services can be tested independently with mocked dependencies.

**Stateless**: Services don't maintain state between calls (state lives in database).

**Observable**: All services automatically log execution to `service_runs` table.

---

### Base Service Class

All services inherit from a `BaseService` class that provides automatic logging, error handling, and execution tracking.

**Implementation**:

```python
# src/services/base_service.py
from abc import ABC
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID
import traceback
from contextlib import contextmanager

from src.repositories.service_run_repository import ServiceRunRepository
from src.utils.logger import logger


class BaseService(ABC):
    """
    Base class for all services.
    Provides automatic execution tracking and error handling.
    """
    
    def __init__(self):
        self.service_run_repo = ServiceRunRepository()
        self.service_name = self.__class__.__name__
    
    @contextmanager
    def track_execution(
        self,
        method_name: str,
        user_id: Optional[UUID] = None,
        triggered_by: str = "system",
        input_params: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Context manager to track service method execution.
        
        Usage:
            with self.track_execution("scan_directory", input_params={"path": "/media"}):
                # Your service logic here
                result = self.do_work()
                return result
        """
        # Create service run record
        run_id = self.service_run_repo.create_run(
            service_name=self.service_name,
            method_name=method_name,
            user_id=user_id,
            triggered_by=triggered_by,
            input_params=input_params,
            metadata=metadata
        )
        
        started_at = datetime.utcnow()
        
        try:
            logger.info(f"[{self.service_name}.{method_name}] Starting execution (run_id: {run_id})")
            
            yield run_id  # Allow service to access run_id if needed
            
            # Success
            completed_at = datetime.utcnow()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)
            
            self.service_run_repo.complete_run(
                run_id=run_id,
                success=True,
                duration_ms=duration_ms
            )
            
            logger.info(f"[{self.service_name}.{method_name}] Completed successfully ({duration_ms}ms)")
            
        except Exception as e:
            # Failure
            completed_at = datetime.utcnow()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)
            
            error_type = type(e).__name__
            error_message = str(e)
            stack_trace = traceback.format_exc()
            
            self.service_run_repo.fail_run(
                run_id=run_id,
                error_type=error_type,
                error_message=error_message,
                stack_trace=stack_trace,
                duration_ms=duration_ms
            )
            
            logger.error(
                f"[{self.service_name}.{method_name}] Failed after {duration_ms}ms: {error_message}",
                exc_info=True
            )
            
            # Re-raise the exception
            raise
    
    def set_result_summary(self, run_id: UUID, summary: Dict[str, Any]):
        """
        Update the result summary for a service run.
        Call this at the end of your method to record what was accomplished.
        """
        self.service_run_repo.set_result_summary(run_id, summary)
```

**Service Run Repository**:

```python
# src/repositories/service_run_repository.py
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session
from src.config.database import get_db
from src.models.service_run import ServiceRun


class ServiceRunRepository:
    def __init__(self):
        self.db: Session = next(get_db())
    
    def create_run(
        self,
        service_name: str,
        method_name: str,
        user_id: Optional[UUID] = None,
        triggered_by: str = "system",
        input_params: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """Create a new service run record."""
        run = ServiceRun(
            id=uuid4(),
            service_name=service_name,
            method_name=method_name,
            user_id=user_id,
            triggered_by=triggered_by,
            input_params=input_params,
            metadata=metadata,
            status="running",
            started_at=datetime.utcnow()
        )
        
        self.db.add(run)
        self.db.commit()
        
        return run.id
    
    def complete_run(
        self,
        run_id: UUID,
        success: bool,
        duration_ms: int,
        result_summary: Optional[Dict[str, Any]] = None
    ):
        """Mark a service run as completed."""
        run = self.db.query(ServiceRun).filter(ServiceRun.id == run_id).first()
        if run:
            run.status = "completed"
            run.success = success
            run.completed_at = datetime.utcnow()
            run.duration_ms = duration_ms
            run.result_summary = result_summary
            self.db.commit()
    
    def fail_run(
        self,
        run_id: UUID,
        error_type: str,
        error_message: str,
        stack_trace: str,
        duration_ms: int
    ):
        """Mark a service run as failed."""
        run = self.db.query(ServiceRun).filter(ServiceRun.id == run_id).first()
        if run:
            run.status = "failed"
            run.success = False
            run.completed_at = datetime.utcnow()
            run.duration_ms = duration_ms
            run.error_type = error_type
            run.error_message = error_message
            run.stack_trace = stack_trace
            self.db.commit()
    
    def set_result_summary(self, run_id: UUID, summary: Dict[str, Any]):
        """Update the result summary for a run."""
        run = self.db.query(ServiceRun).filter(ServiceRun.id == run_id).first()
        if run:
            run.result_summary = summary
            self.db.commit()
    
    def get_recent_runs(
        self,
        service_name: Optional[str] = None,
        limit: int = 100
    ) -> list[ServiceRun]:
        """Get recent service runs."""
        query = self.db.query(ServiceRun)
        
        if service_name:
            query = query.filter(ServiceRun.service_name == service_name)
        
        return query.order_by(ServiceRun.started_at.desc()).limit(limit).all()
```

**Example Service Implementation**:

```python
# src/services/core/media_ingestion.py
from typing import Optional
from uuid import UUID
from pathlib import Path

from src.services.base_service import BaseService
from src.repositories.media_repository import MediaRepository
from src.utils.file_hash import calculate_file_hash


class MediaIngestionService(BaseService):
    """Scan filesystem and index media files."""
    
    def __init__(self):
        super().__init__()
        self.media_repo = MediaRepository()
    
    def scan_directory(
        self,
        directory_path: str,
        user_id: Optional[UUID] = None,
        recursive: bool = True
    ) -> Dict[str, int]:
        """
        Scan a directory and index all media files.
        
        Returns:
            Dict with counts: {indexed: 10, skipped: 2, errors: 1}
        """
        with self.track_execution(
            method_name="scan_directory",
            user_id=user_id,
            triggered_by="cli" if user_id else "system",
            input_params={"directory_path": directory_path, "recursive": recursive}
        ) as run_id:
            
            indexed_count = 0
            skipped_count = 0
            error_count = 0
            
            path = Path(directory_path)
            pattern = "**/*" if recursive else "*"
            
            for file_path in path.glob(pattern):
                if not file_path.is_file():
                    continue
                
                if file_path.suffix.lower() not in ['.jpg', '.jpeg', '.png', '.gif']:
                    skipped_count += 1
                    continue
                
                try:
                    # Index the file
                    self._index_file(file_path, user_id)
                    indexed_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to index {file_path}: {e}")
                    error_count += 1
            
            # Record results
            result_summary = {
                "indexed": indexed_count,
                "skipped": skipped_count,
                "errors": error_count,
                "total_files": indexed_count + skipped_count + error_count
            }
            
            self.set_result_summary(run_id, result_summary)
            
            return result_summary
    
    def _index_file(self, file_path: Path, user_id: Optional[UUID]):
        """Index a single file."""
        file_hash = calculate_file_hash(str(file_path))
        
        # Check for duplicates
        existing = self.media_repo.get_by_hash(file_hash)
        if existing:
            logger.info(f"Skipping duplicate: {file_path.name}")
            return
        
        # Create media item
        self.media_repo.create(
            file_path=str(file_path),
            file_name=file_path.name,
            file_hash=file_hash,
            file_size_bytes=file_path.stat().st_size,
            indexed_by_user_id=user_id
        )
```

**Benefits**:

1. ✅ **Automatic Logging**: Every service call logged to database
2. ✅ **Performance Tracking**: Execution time automatically recorded
3. ✅ **Error Handling**: Exceptions caught and logged with stack traces
4. ✅ **Audit Trail**: Know who triggered what and when
5. ✅ **Debugging**: Easy to see what services are running and failing
6. ✅ **Monitoring**: Query `service_runs` for system health
7. ✅ **Consistency**: All services follow same pattern

**Querying Service Runs**:

```python
# Get recent runs for a service
recent_runs = service_run_repo.get_recent_runs(service_name="MediaIngestionService", limit=10)

# Find failed runs
failed_runs = db.query(ServiceRun).filter(
    ServiceRun.status == "failed",
    ServiceRun.started_at > datetime.utcnow() - timedelta(hours=24)
).all()

# Get average execution time
avg_duration = db.query(func.avg(ServiceRun.duration_ms)).filter(
    ServiceRun.service_name == "PostingService",
    ServiceRun.success == True
).scalar()
```

---

### Core Services (Phase 1)

#### `MediaIngestionService`
**Responsibility**: Scan filesystem and index media files.

**Methods**:
- `scan_directory(path)`: Recursively scan directory
- `index_file(file_path)`: Calculate hash, extract metadata, insert to DB
- `detect_duplicates()`: Find duplicate content by hash
- `update_metadata(media_id, metadata)`: Update media item metadata

**Dependencies**: `MediaRepository`, `file_hash` utility

**Future API**: `POST /api/media/scan`, `POST /api/media/index`

---

#### `SchedulerService`
**Responsibility**: Create and manage posting schedule.

**Methods**:
- `create_schedule(days, posts_per_day)`: Generate schedule
- `select_random_media(filters)`: Pick media for posting
- `check_availability(media_id)`: Check if media is locked
- `add_to_queue(media_id, scheduled_time)`: Create queue entry

**Dependencies**: `QueueRepository`, `MediaRepository`, `MediaLockService`

**Future API**: `POST /api/schedule/create`, `GET /api/schedule/preview`

**Scheduler Algorithm Specification**:

The scheduler uses a combination of strategies to ensure intelligent, varied posting:

1. **Eligibility Filtering**:
   ```sql
   SELECT m.* FROM media_items m
   WHERE m.is_active = TRUE
     AND NOT EXISTS (
       -- Exclude locked media
       SELECT 1 FROM media_posting_locks l
       WHERE l.media_item_id = m.id
         AND l.locked_until > NOW()
     )
     AND NOT EXISTS (
       -- Exclude already queued media
       SELECT 1 FROM posting_queue q
       WHERE q.media_item_id = m.id
         AND q.status = 'pending'
     )
   ```

2. **Selection Logic**:
   - **Primary Sort**: `last_posted_at ASC NULLS FIRST` (never-posted items prioritized)
   - **Secondary Sort**: `times_posted ASC` (least-posted items preferred)
   - **Tertiary Sort**: `RANDOM()` (break ties randomly for variety)

3. **Tag Distribution** (Optional Enhancement):
   - Track last-posted tag in session
   - Prefer media with different tags than previous selection
   - Ensures variety (don't post 5 memes in a row)

4. **Time Slot Allocation**:
   ```python
   # Calculate evenly distributed time slots
   posting_window_hours = POSTING_HOURS_END - POSTING_HOURS_START
   interval_hours = posting_window_hours / POSTS_PER_DAY

   time_slots = []
   for i in range(POSTS_PER_DAY):
       base_hour = POSTING_HOURS_START + (i * interval_hours)
       # Add ±30min jitter for unpredictability
       jitter_minutes = random.randint(-30, 30)
       scheduled_time = base_hour + (jitter_minutes / 60)
       time_slots.append(scheduled_time)

   # Example: 3 posts/day, 9AM-9PM UTC (12 hour window)
   # Base slots: 9:00, 13:00, 17:00
   # With jitter: 9:15, 13:22, 16:47
   ```

5. **Duplicate Prevention**:
   - After successful post, create 30-day TTL lock automatically
   - Prevents same media from being selected again immediately

---

#### `PostingService`
**Responsibility**: Orchestrate the posting process.

**Methods**:
- `process_pending_posts()`: Main processing loop
- `post_automated(queue_item)`: Post via Instagram API
- `post_via_telegram(queue_item)`: Send Telegram notification
- `handle_completion(queue_item, result)`: Move to history, create lock

**Dependencies**: `QueueRepository`, `HistoryRepository`, `MediaLockService`, `InstagramAPIService`, `TelegramService`, `CloudStorageService`

**Future API**: `POST /api/posts/process`, `POST /api/posts/{id}/retry`

---

#### `TelegramService`
**Responsibility**: All Telegram bot operations.

**Methods**:
- `start_bot()`: Initialize bot with handlers
- `stop_bot()`: Graceful shutdown
- `send_story_notification(queue_item, media_item)`: Send notification
- `handle_callback(callback_query)`: Process button clicks
- `update_message(message_id, new_status)`: Edit message
- `send_alert(message)`: Send admin alert

**Dependencies**: `QueueRepository`, `HistoryRepository`

**Future API**: `POST /api/telegram/send`, `GET /api/telegram/status`

---

#### `MediaLockService`
**Responsibility**: Manage TTL locks to prevent premature reposting.

**Methods**:
- `create_lock(media_id, ttl_days, reason)`: Create new lock
- `check_locked(media_id)`: Check if media is currently locked
- `get_lock_status(media_id)`: Get lock details
- `remove_lock(lock_id)`: Manually remove lock
- `cleanup_expired_locks()`: Remove expired locks (maintenance)

**Dependencies**: `LockRepository`

**Future API**: `POST /api/locks`, `GET /api/locks/{media_id}`, `DELETE /api/locks/{id}`

---

### Integration Services (Phase 2)

#### `CloudStorageService`
**Responsibility**: Upload and manage files in cloud storage.

**Methods**:
- `upload_image(file_path)`: Upload to cloud, return URL
- `delete_image(public_id)`: Delete from cloud
- `get_url(public_id)`: Get public URL
- `list_uploads()`: List all uploaded files (for cleanup)

**Dependencies**: Cloudinary SDK (or S3, etc.)

**Configuration**: Provider-agnostic (supports Cloudinary, S3, Backblaze, etc.)

**Future API**: `POST /api/storage/upload`, `DELETE /api/storage/{id}`

---

#### `InstagramAPIService`
**Responsibility**: All Instagram Graph API operations.

**Methods**:
- `create_story(image_url)`: Post story via API
- `verify_credentials()`: Check if token is valid
- `refresh_token()`: Refresh long-lived token
- `get_rate_limit_status()`: Check API quota
- `get_account_info()`: Fetch account details

**Dependencies**: `RateLimiter` utility

**Future API**: `POST /api/instagram/post`, `GET /api/instagram/status`

---

#### `InstagramMetricsService`
**Responsibility**: Fetch and store performance metrics from Instagram.

**Methods**:
- `fetch_metrics(instagram_media_id)`: Fetch metrics for one post
- `fetch_batch_metrics(media_ids)`: Fetch metrics for multiple posts
- `schedule_metric_fetch(history_id, intervals)`: Schedule fetches (24h, 7d, 30d)
- `get_metric_history(history_id)`: Get time-series data

**Dependencies**: `InstagramAPIService`, `MetricsRepository`

**Future API**: `POST /api/metrics/fetch`, `GET /api/metrics/{history_id}`

---

### Domain Services (Future)

#### `ShopifyService`
**Responsibility**: Sync products from Shopify API.

**Methods**:
- `sync_products()`: Fetch all products from Shopify
- `sync_product(product_id)`: Sync single product
- `get_product(shopify_id)`: Get product details
- `search_products(query)`: Search Shopify products
- `webhook_handler(event)`: Handle Shopify webhooks (product updates)

**Dependencies**: Shopify SDK, `ShopifyRepository`

**Future API**: `POST /api/shopify/sync`, `GET /api/shopify/products`

---

#### `ProductLinkService`
**Responsibility**: Link media items to Shopify products.

**Methods**:
- `link_media_to_product(media_id, product_id)`: Create link
- `unlink_media_from_product(media_id, product_id)`: Remove link
- `set_primary_image(media_id, product_id)`: Mark as hero image
- `get_product_media(product_id)`: Get all media for product
- `get_media_products(media_id)`: Get all products for media
- `reorder_product_media(product_id, media_ids)`: Set display order

**Dependencies**: `ProductLinkRepository`, `MediaRepository`, `ShopifyRepository`

**Future API**: `POST /api/links`, `DELETE /api/links/{id}`, `PUT /api/links/reorder`

---

#### `AnalyticsService`
**Responsibility**: Aggregate metrics and generate insights.

**Methods**:
- `get_top_performing_media(limit, metric)`: Best stories by reach/clicks
- `get_product_performance(product_id)`: Performance for specific product
- `get_user_performance(user_id)`: Team member performance
- `get_time_series(history_id)`: Metric evolution over time
- `generate_report(start_date, end_date)`: Comprehensive report
- `predict_optimal_time()`: ML-based posting time prediction

**Dependencies**: `MetricsRepository`, `HistoryRepository`, `ProductLinkRepository`

**Future API**: `GET /api/analytics/top-media`, `GET /api/analytics/products/{id}`, `GET /api/analytics/reports`

---

### Service Interaction Patterns

#### Pattern 1: Orchestration (PostingService)
```python
class PostingService:
    def __init__(self):
        self.queue_repo = QueueRepository()
        self.history_repo = HistoryRepository()
        self.lock_service = MediaLockService()
        self.instagram = InstagramAPIService()
        self.telegram = TelegramService()
        self.storage = CloudStorageService()
    
    async def post_automated(self, queue_item, media_item):
        """Orchestrates multiple services to complete a post."""
        # 1. Upload to cloud
        upload = self.storage.upload_image(media_item.file_path)
        
        # 2. Post to Instagram
        result = self.instagram.create_story(upload['url'])
        
        # 3. Update queue
        self.queue_repo.mark_as_posted(queue_item.id, result)
        
        # 4. Create history record
        self.history_repo.create_entry(queue_item, result)
        
        # 5. Create TTL lock
        self.lock_service.create_lock(media_item.id, ttl_days=30)
        
        # 6. Cleanup cloud storage
        self.storage.delete_image(upload['public_id'])
```

#### Pattern 2: Single Responsibility (MediaLockService)
```python
class MediaLockService:
    def __init__(self):
        self.lock_repo = LockRepository()
    
    def check_locked(self, media_id: str) -> bool:
        """Single responsibility: check lock status."""
        active_locks = self.lock_repo.get_active_locks(media_id)
        return len(active_locks) > 0
    
    def create_lock(self, media_id: str, ttl_days: int, reason: str):
        """Single responsibility: create lock."""
        locked_until = datetime.utcnow() + timedelta(days=ttl_days)
        return self.lock_repo.create(media_id, locked_until, reason)
```

#### Pattern 3: API-Ready (Future)
```python
# Future: FastAPI route
@router.post("/api/locks")
async def create_lock(
    media_id: str,
    ttl_days: int = 30,
    reason: str = "recent_post",
    lock_service: MediaLockService = Depends(get_lock_service)
):
    """API endpoint wraps service method."""
    lock = lock_service.create_lock(media_id, ttl_days, reason)
    return {"id": lock.id, "locked_until": lock.locked_until}
```

---

### Service Testing Strategy

Each service can be tested independently:

```python
# tests/src/services/core/test_media_lock.py
def test_create_lock(mock_lock_repo):
    """Test MediaLockService in isolation."""
    service = MediaLockService()
    service.lock_repo = mock_lock_repo  # Inject mock
    
    lock = service.create_lock("media-123", ttl_days=30, reason="recent_post")
    
    assert mock_lock_repo.create.called
    assert lock.locked_until > datetime.utcnow()
```

---

## Part C: Python Application Structure

### Directory Structure

```
storyline-ai/
│
├── cli/
│   ├── __init__.py
│   ├── main.py                      # CLI entry point
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── index.py                 # index-media command
│   │   ├── list.py                  # list-media command
│   │   ├── schedule.py              # create-schedule command
│   │   ├── post.py                  # process-queue command
│   │   ├── test.py                  # test-api command
│   │   ├── users.py                 # user management commands
│   │   └── service_runs.py          # service run monitoring commands
│
├── ui/                               # Web frontend (Future - Phase 3)
│   ├── package.json
│   ├── next.config.js                # Next.js configuration
│   ├── tsconfig.json
│   │
│   ├── public/
│   │   ├── favicon.ico
│   │   └── assets/
│   │
│   ├── src/
│   │   ├── app/                      # Next.js app directory
│   │   │   ├── page.tsx              # Dashboard home
│   │   │   ├── media/
│   │   │   │   └── page.tsx          # Media library
│   │   │   ├── queue/
│   │   │   │   └── page.tsx          # Queue management
│   │   │   ├── history/
│   │   │   │   └── page.tsx          # Posting history
│   │   │   ├── analytics/
│   │   │   │   └── page.tsx          # Analytics dashboard
│   │   │   └── settings/
│   │   │       └── page.tsx          # Settings
│   │   │
│   │   ├── components/
│   │   │   ├── MediaGrid.tsx         # Media item grid view
│   │   │   ├── Calendar.tsx          # Posting schedule calendar
│   │   │   ├── StatsCard.tsx         # Dashboard stat cards
│   │   │   └── Layout.tsx            # Main layout wrapper
│   │   │
│   │   ├── lib/
│   │   │   ├── api.ts                # API client (calls src/api)
│   │   │   ├── auth.ts               # JWT authentication
│   │   │   └── utils.ts              # Utility functions
│   │   │
│   │   └── types/
│   │       ├── media.ts              # Type definitions
│   │       ├── queue.ts
│   │       └── api.ts
│   │
│   └── README.md                      # UI setup instructions
│
├── src/
│   ├── __init__.py
│   ├── main.py                      # Main application entry point (scheduler + Telegram bot)
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py              # Configuration management
│   │   └── database.py              # Database connection
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py                  # User model (Telegram-derived)
│   │   ├── service_run.py           # Service execution tracking model
│   │   ├── media_item.py            # Media item model
│   │   ├── posting_queue.py         # Posting queue model
│   │   ├── posting_history.py       # Posting history model
│   │   ├── media_lock.py            # Media posting lock model
│   │   ├── shopify_product.py       # Shopify product model (future)
│   │   ├── media_product_link.py    # Media-product link model (future)
│   │   ├── instagram_metrics.py     # Instagram metrics model (future)
│   │   └── config.py                # Config model
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── base_service.py          # Base service class with execution tracking
│   │   │
│   │   ├── core/                    # Core services (Phase 1)
│   │   │   ├── __init__.py
│   │   │   ├── media_ingestion.py   # Scan and index media files
│   │   │   ├── scheduler.py         # Create posting schedule
│   │   │   ├── posting.py           # Post execution orchestration
│   │   │   ├── telegram_service.py  # All Telegram bot operations
│   │   │   ├── media_lock.py        # TTL lock management
│   │   │   ├── health_check.py      # System health checks
│   │   │   ├── alert_service.py     # Admin alerting via Telegram
│   │   │   └── backup_service.py    # Automated backup management
│   │   │
│   │   ├── integrations/            # External API integrations (Phase 2+)
│   │   │   ├── __init__.py
│   │   │   ├── cloud_storage.py     # Cloud storage (Cloudinary, S3, etc.)
│   │   │   ├── instagram_api.py     # Instagram Graph API wrapper
│   │   │   ├── instagram_metrics.py # Fetch Instagram performance metrics
│   │   │   └── shopify.py           # Shopify API integration (future)
│   │   │
│   │   └── domain/                  # Domain-specific services (Future)
│   │       ├── __init__.py
│   │       ├── product_link.py      # Link media to products
│   │       └── analytics.py         # Analytics and insights
│   │
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── user_repository.py       # CRUD for users
│   │   ├── service_run_repository.py # CRUD for service runs
│   │   ├── media_repository.py      # CRUD for media items
│   │   ├── queue_repository.py      # CRUD for posting queue
│   │   ├── history_repository.py    # CRUD for posting history
│   │   ├── lock_repository.py       # CRUD for media locks
│   │   ├── shopify_repository.py    # CRUD for Shopify products (future)
│   │   ├── product_link_repository.py # CRUD for media-product links (future)
│   │   ├── metrics_repository.py    # CRUD for Instagram metrics (future)
│   │   └── config_repository.py     # CRUD for config
│   │
│   ├── api/                         # REST API (Phase 2.5 - enables web frontend)
│   │   ├── __init__.py
│   │   ├── app.py                   # FastAPI application
│   │   ├── dependencies.py          # API dependencies (auth, db, etc.)
│   │   ├── middleware.py            # CORS, auth, logging middleware
│   │   │
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── media.py             # Media endpoints (/api/v1/media)
│   │   │   ├── queue.py             # Queue management (/api/v1/queue)
│   │   │   ├── history.py           # History and analytics (/api/v1/history)
│   │   │   ├── shopify.py           # Shopify integration (/api/v1/shopify)
│   │   │   ├── telegram.py          # Telegram bot management (/api/v1/telegram)
│   │   │   ├── users.py             # User management (/api/v1/users)
│   │   │   └── health.py            # Health check endpoints (/health, /api/v1/health)
│   │   │
│   │   └── schemas/
│   │       ├── __init__.py
│   │       ├── media.py             # Pydantic schemas for media
│   │       ├── queue.py             # Pydantic schemas for queue
│   │       ├── shopify.py           # Pydantic schemas for Shopify
│   │       ├── auth.py              # JWT token schemas
│   │       └── responses.py         # Common response schemas
│   │
│   └── utils/
│       ├── __init__.py
│       ├── file_hash.py             # File hashing utilities (SHA256 of content)
│       ├── image_processing.py      # Image validation & optimization for Instagram
│       ├── logger.py                # Logging configuration
│       ├── validators.py            # Input validation & configuration validation
│       ├── rate_limiter.py          # Rate limiting utilities
│       └── backup.py                # Backup utilities for database & media
│
├── media/
│   └── stories/                     # All story images (organize however you want)
│       ├── simple/                  # Auto-post stories (no interaction needed)
│       │   └── meme1.jpg
│       ├── products/                # Stories requiring link stickers
│       │   └── tshirt1.jpg
│       ├── polls/                   # Stories requiring poll stickers
│       │   └── poll1.jpg
│       └── metadata.json            # Optional metadata file
│
├── scripts/
│   ├── setup_database.sql           # Database schema
│   └── migrate_to_neon.py           # Migration script for Neon
│
├── tests/                           # Mirror structure of src/
│   ├── __init__.py
│   ├── conftest.py                 # Pytest fixtures and configuration
│   │
│   ├── src/                        # Tests mirror src/ structure
│   │   ├── __init__.py
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── test_media_ingestion.py
│   │   │   ├── test_scheduler.py
│   │   │   ├── test_instagram_api.py
│   │   │   ├── test_posting.py
│   │   │   ├── test_telegram_service.py
│   │   │   └── test_cloud_storage.py
│   │   │
│   │   ├── repositories/
│   │   │   ├── __init__.py
│   │   │   ├── test_media_repository.py
│   │   │   ├── test_queue_repository.py
│   │   │   └── test_history_repository.py
│   │   │
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── test_file_hash.py
│   │       └── test_validators.py
│   │
│   └── integration/                # Integration tests
│       ├── __init__.py
│       ├── test_end_to_end.py
│       └── test_telegram_workflow.py
│
├── logs/                            # Application logs
│   └── app.log
│
├── .env.example                     # Example environment variables
├── .env.test                        # Test environment variables (optional)
├── .gitignore
├── pytest.ini                       # Pytest configuration
├── requirements.txt
├── README.md
├── LICENSE
└── setup.py                         # For CLI installation
```

### Metadata JSON Format

**Purpose**: Define which stories need manual interaction and provide metadata.

**Option 1: Directory-level metadata.json** (recommended for batch imports)

```json
{
  "default_requires_interaction": false,
  "default_tags": ["simple"],
  "items": [
    {
      "file_name": "tshirt-photo.jpg",
      "requires_interaction": true,
      "title": "Cool Meme Tshirt",
      "link_url": "https://yourshop.com/products/cool-tshirt",
      "caption": "New tshirt drop! Swipe up 👆",
      "tags": ["product", "tshirt", "newdrop"]
    },
    {
      "file_name": "meme1.jpg",
      "requires_interaction": false,
      "title": "Funny Meme",
      "tags": ["meme", "humor"]
    },
    {
      "file_name": "poll-story.jpg",
      "requires_interaction": true,
      "title": "Community Poll",
      "caption": "What do you think?",
      "tags": ["poll", "engagement"],
      "custom_metadata": {
        "poll_question": "Which design do you prefer?",
        "poll_options": ["Design A", "Design B"]
      }
    }
  ]
}
```

**Option 2: Filename conventions** (for quick setup without JSON)

```
stories/
  simple/
    meme1.jpg                          → requires_interaction = false
    meme2.jpg                          → requires_interaction = false
  
  products/
    tshirt__https-shop-com-tshirt.jpg  → requires_interaction = true
                                         link_url extracted from filename
```

**Option 3: Sidecar files** (one JSON per image)

```
stories/
  tshirt-photo.jpg
  tshirt-photo.json  ← metadata for this specific image
```

---

## File Hash Strategy

### Hash Implementation

**What is hashed**: SHA256 of **file content only** (not filename, not metadata)

```python
# src/utils/file_hash.py
import hashlib
from pathlib import Path

def calculate_file_hash(file_path: Path) -> str:
    """
    Calculate SHA256 hash of file content.
    
    Note: Hash is based ONLY on file content, not filename.
    This means:
    - Same image with different names = same hash
    - Different images with same name = different hash
    
    Args:
        file_path: Path to file
        
    Returns:
        Hex string of SHA256 hash
    """
    sha256_hash = hashlib.sha256()
    
    with open(file_path, "rb") as f:
        # Read in chunks for memory efficiency
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    
    return sha256_hash.hexdigest()
```

### Duplicate Handling Strategy

**Scenario 1: Same content, different filename**
```
stories/product-a.jpg (hash: abc123...)
stories/product-b.jpg (hash: abc123...)  # Same image, different name
```

**Behavior**: 
- Both files are indexed separately (unique `file_path`)
- Both have same `file_hash`
- System logs warning: "Duplicate content detected"
- Both can be posted (user might want to post same image twice)
- Scheduler can optionally avoid posting duplicates close together

**Scenario 2: Different content, same filename** (after replacing file)
```
stories/product.jpg (hash: abc123...)  # Original
# User replaces file
stories/product.jpg (hash: xyz789...)  # New content
```

**Behavior**:
- Re-indexing detects hash change
- Updates database record
- Resets `times_posted` counter (optional)

**Scenario 3: Exact duplicate** (same path + same hash)
```
stories/product.jpg (hash: abc123...)
# Re-run indexing
stories/product.jpg (hash: abc123...)  # No change
```

**Behavior**:
- Skip indexing (already in database)
- Update `updated_at` timestamp
- No duplicate record created

### Database Schema for Hash Handling

```sql
-- file_path is UNIQUE (can't have two records for same path)
file_path TEXT NOT NULL UNIQUE,

-- file_hash is NOT UNIQUE (allows duplicate content with different paths)
file_hash TEXT NOT NULL,

-- Index for duplicate detection queries
CREATE INDEX idx_media_items_hash ON media_items(file_hash);
```

### Duplicate Detection Queries

```python
# Find all duplicates
SELECT file_hash, COUNT(*), ARRAY_AGG(file_path) as paths
FROM media_items
GROUP BY file_hash
HAVING COUNT(*) > 1;

# Check if content already exists before posting
SELECT id, file_path, times_posted, last_posted_at
FROM media_items
WHERE file_hash = %s
ORDER BY last_posted_at DESC NULLS LAST;
```

### Scheduler Duplicate Avoidance

```python
# In SchedulerService.select_random_media()
# Optionally avoid posting duplicate content within X days

SELECT m.*
FROM media_items m
WHERE m.is_active = TRUE
  AND m.requires_interaction = FALSE
  AND (
    m.last_posted_at IS NULL 
    OR m.last_posted_at < NOW() - INTERVAL '7 days'
  )
  -- Avoid other images with same hash that were posted recently
  AND NOT EXISTS (
    SELECT 1 FROM media_items m2
    WHERE m2.file_hash = m.file_hash
      AND m2.id != m.id
      AND m2.last_posted_at > NOW() - INTERVAL '7 days'
  )
ORDER BY RANDOM()
LIMIT 1;
```

---

## Image Processing & Validation

### Instagram Story Requirements

Instagram has specific requirements for Story media:

| Requirement | Value |
|------------|-------|
| **Aspect Ratio** | 9:16 (ideal), 1.91:1 to 9:16 (acceptable) |
| **Resolution** | 1080x1920 pixels (recommended), min 720x1280 |
| **File Size** | Max 100 MB (images), max 4 GB (videos) |
| **Formats** | JPG, PNG, GIF (images), MP4, MOV (videos) |
| **Duration** | Max 15 seconds (videos) |

### Image Validation Service

```python
# src/utils/image_processing.py
from PIL import Image
from pathlib import Path
from typing import Tuple, Optional
from dataclasses import dataclass

@dataclass
class ValidationResult:
    """Result of image validation."""
    is_valid: bool
    warnings: list[str]
    errors: list[str]
    width: int
    height: int
    aspect_ratio: float
    file_size_mb: float
    format: str

class ImageProcessor:
    """Validate and optimize images for Instagram Stories."""

    # Instagram Story specs
    IDEAL_WIDTH = 1080
    IDEAL_HEIGHT = 1920
    IDEAL_ASPECT_RATIO = 9/16
    MIN_ASPECT_RATIO = 1.91/1  # More horizontal
    MAX_ASPECT_RATIO = 9/16     # More vertical
    MAX_FILE_SIZE_MB = 100
    SUPPORTED_FORMATS = {'JPEG', 'PNG', 'GIF'}

    def validate_image(self, file_path: Path) -> ValidationResult:
        """
        Validate image meets Instagram requirements.

        Returns:
            ValidationResult with validation details
        """
        errors = []
        warnings = []

        try:
            img = Image.open(file_path)
            width, height = img.size
            aspect_ratio = width / height
            file_size_mb = file_path.stat().st_size / (1024 * 1024)

            # Check format
            if img.format not in self.SUPPORTED_FORMATS:
                errors.append(f"Unsupported format: {img.format}. Must be JPG, PNG, or GIF")

            # Check file size
            if file_size_mb > self.MAX_FILE_SIZE_MB:
                errors.append(f"File too large: {file_size_mb:.1f}MB (max {self.MAX_FILE_SIZE_MB}MB)")

            # Check aspect ratio
            if aspect_ratio < self.MAX_ASPECT_RATIO or aspect_ratio > self.MIN_ASPECT_RATIO:
                warnings.append(
                    f"Non-ideal aspect ratio: {aspect_ratio:.2f}. "
                    f"Instagram prefers 9:16 ({self.IDEAL_ASPECT_RATIO:.2f})"
                )

            # Check resolution
            if width < 720 or height < 1280:
                warnings.append(
                    f"Low resolution: {width}x{height}. "
                    f"Minimum recommended: 720x1280"
                )
            elif width != self.IDEAL_WIDTH or height != self.IDEAL_HEIGHT:
                warnings.append(
                    f"Non-optimal resolution: {width}x{height}. "
                    f"Instagram ideal: {self.IDEAL_WIDTH}x{self.IDEAL_HEIGHT}"
                )

            is_valid = len(errors) == 0

            return ValidationResult(
                is_valid=is_valid,
                warnings=warnings,
                errors=errors,
                width=width,
                height=height,
                aspect_ratio=aspect_ratio,
                file_size_mb=file_size_mb,
                format=img.format
            )

        except Exception as e:
            return ValidationResult(
                is_valid=False,
                warnings=[],
                errors=[f"Failed to open image: {str(e)}"],
                width=0,
                height=0,
                aspect_ratio=0,
                file_size_mb=0,
                format="unknown"
            )

    def optimize_for_instagram(self, file_path: Path, output_path: Optional[Path] = None) -> Path:
        """
        Resize/convert image to Instagram specs.

        Args:
            file_path: Source image path
            output_path: Destination path (default: overwrite source)

        Returns:
            Path to optimized image
        """
        img = Image.open(file_path)
        width, height = img.size
        aspect_ratio = width / height

        # Calculate target dimensions maintaining aspect ratio
        if aspect_ratio > self.IDEAL_ASPECT_RATIO:
            # Image is too wide, crop to 9:16
            target_width = int(height * self.IDEAL_ASPECT_RATIO)
            target_height = height
            left = (width - target_width) // 2
            img = img.crop((left, 0, left + target_width, height))
        else:
            # Image is correct or too tall, resize to 1080x1920
            target_width = self.IDEAL_WIDTH
            target_height = self.IDEAL_HEIGHT
            img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)

        # Convert RGBA to RGB if needed (PNG with transparency)
        if img.mode == 'RGBA':
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            rgb_img.paste(img, mask=img.split()[3])
            img = rgb_img

        # Save optimized image
        if output_path is None:
            output_path = file_path

        img.save(output_path, 'JPEG', quality=95, optimize=True)

        return output_path
```

### Integration with Media Ingestion

```python
# src/services/core/media_ingestion.py (enhancement)
from src.utils.image_processing import ImageProcessor

class MediaIngestionService(BaseService):
    def __init__(self):
        super().__init__()
        self.image_processor = ImageProcessor()

    def index_file(self, file_path: Path, auto_optimize: bool = False):
        """Index a file with optional validation and optimization."""

        # Validate image
        validation = self.image_processor.validate_image(file_path)

        if not validation.is_valid:
            logger.error(f"Invalid image {file_path}: {validation.errors}")
            raise ValueError(f"Image validation failed: {validation.errors}")

        if validation.warnings:
            logger.warning(f"Image {file_path} has warnings: {validation.warnings}")

        # Optionally optimize
        if auto_optimize and validation.warnings:
            logger.info(f"Optimizing {file_path} for Instagram...")
            optimized_path = self.image_processor.optimize_for_instagram(file_path)
            file_path = optimized_path

        # Continue with normal indexing...
        file_hash = calculate_file_hash(file_path)
        # ... rest of indexing logic
```

---

## Media Upload Workflows

### Phase 1: File Upload Options

Users have multiple options for getting media onto the Raspberry Pi:

#### Option A: iCloud Photos Sync (Recommended for iOS)

**Setup**:
```bash
# Install icloudpd
pip install icloudpd

# Configure credentials
icloud --username=your@email.com

# Set up automatic sync (cron)
*/30 * * * * icloudpd --directory /home/pi/media/stories --recent 100 --folder "Instagram Stories"
```

**Workflow**:
1. User adds photos to "Instagram Stories" shared album on iPhone
2. icloudpd syncs every 30 minutes to Raspberry Pi
3. Cron job runs `storyline-cli index-media` hourly
4. Media automatically appears in system

**Benefits**: Zero manual intervention, works from anywhere

#### Option B: SFTP/SCP Upload (Manual)

**Setup**:
```bash
# Enable SSH on Raspberry Pi (usually already enabled)
sudo systemctl enable ssh
sudo systemctl start ssh
```

**Workflow**:
1. User connects via Cyberduck, FileZilla, or command line
2. Upload files to `/home/pi/media/stories/`
3. Run `storyline-cli index-media /home/pi/media/stories`
4. Media appears in system

**Benefits**: Simple, works with any device

#### Option C: USB Transfer (Offline)

**Workflow**:
1. Copy files to USB drive
2. Insert USB into Raspberry Pi
3. Mount and copy: `cp /media/usb/photos/* /home/pi/media/stories/`
4. Run `storyline-cli index-media /home/pi/media/stories`

**Benefits**: No network required

#### Option D: Telegram Bot Upload (Future Enhancement)

```python
# Future feature - upload directly via Telegram
@bot.message_handler(content_types=['photo', 'document'])
async def handle_photo_upload(message):
    """Save uploaded photo to filesystem and auto-index."""
    # Download photo from Telegram
    file_path = download_telegram_file(message.photo[-1].file_id)

    # Save to media directory
    destination = Path(f"/home/pi/media/stories/{file_path.name}")
    shutil.copy(file_path, destination)

    # Auto-index
    media_service.index_file(destination)

    await bot.reply_to(message, f"✅ Uploaded and indexed: {file_path.name}")
```

**Benefits**: Upload from anywhere via Telegram app

### Recommended Setup

**For Individuals**: iCloud sync + manual SFTP for bulk uploads
**For Teams**: Shared Dropbox/Google Drive folder synced to Pi via rclone
**For Advanced**: Custom web upload interface (Phase 3)

---

## Access Token Management

### Instagram Access Token Lifecycle

Instagram (Meta) access tokens expire and must be refreshed:

| Token Type | Validity | Refresh Strategy |
|-----------|----------|------------------|
| Short-lived token | 1 hour | Exchange for long-lived immediately |
| Long-lived token | 60 days | Refresh before expiration |

### Token Refresh Service

```python
# src/services/integrations/token_refresh.py
from datetime import datetime, timedelta
from typing import Optional
import requests

from src.services.base_service import BaseService
from src.services.core.alert_service import AlertService
from src.utils.logger import logger
from src.config.settings import settings


class TokenRefreshService(BaseService):
    """Manage Instagram API access token lifecycle."""

    def __init__(self):
        super().__init__()
        self.alert_service = AlertService()
        self.token_warning_days = 7  # Alert if < 7 days remaining

    def check_token_expiration(self) -> dict:
        """
        Check if access token is expiring soon.

        Returns:
            dict with status, days_remaining, expires_at
        """
        if not settings.INSTAGRAM_ACCESS_TOKEN:
            return {"status": "missing", "days_remaining": 0}

        # Check token validity via Graph API
        response = requests.get(
            "https://graph.facebook.com/v18.0/me",
            params={"access_token": settings.INSTAGRAM_ACCESS_TOKEN}
        )

        if response.status_code != 200:
            logger.error(f"Token validation failed: {response.text}")
            return {"status": "invalid", "days_remaining": 0}

        # Get token info to check expiration
        debug_response = requests.get(
            "https://graph.facebook.com/v18.0/debug_token",
            params={
                "input_token": settings.INSTAGRAM_ACCESS_TOKEN,
                "access_token": settings.INSTAGRAM_ACCESS_TOKEN
            }
        )

        if debug_response.status_code == 200:
            data = debug_response.json()['data']
            expires_at = datetime.fromtimestamp(data.get('expires_at', 0))
            days_remaining = (expires_at - datetime.now()).days

            return {
                "status": "valid",
                "days_remaining": days_remaining,
                "expires_at": expires_at.isoformat()
            }

        return {"status": "unknown", "days_remaining": 0}

    def refresh_long_lived_token(self) -> Optional[str]:
        """
        Refresh long-lived access token.

        Returns:
            New access token or None if refresh failed
        """
        logger.info("Attempting to refresh Instagram access token...")

        response = requests.get(
            "https://graph.facebook.com/v18.0/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": settings.FACEBOOK_APP_ID,
                "client_secret": settings.FACEBOOK_APP_SECRET,
                "fb_exchange_token": settings.INSTAGRAM_ACCESS_TOKEN
            }
        )

        if response.status_code == 200:
            new_token = response.json()['access_token']
            logger.info("✅ Access token refreshed successfully")

            # TODO: Save to config file or database
            self._save_new_token(new_token)

            return new_token
        else:
            logger.error(f"Token refresh failed: {response.text}")
            self.alert_service.alert_admin(
                severity="ERROR",
                message=f"Instagram token refresh failed: {response.text}"
            )
            return None

    def _save_new_token(self, new_token: str):
        """Save refreshed token to configuration."""
        # Option 1: Update .env file
        env_file = Path(".env")
        if env_file.exists():
            content = env_file.read_text()
            updated = content.replace(
                f"INSTAGRAM_ACCESS_TOKEN={settings.INSTAGRAM_ACCESS_TOKEN}",
                f"INSTAGRAM_ACCESS_TOKEN={new_token}"
            )
            env_file.write_text(updated)

        # Option 2: Store in database (more secure for multi-instance)
        # config_repo.update("instagram_access_token", new_token)

    def monitor_and_refresh(self):
        """Check token status and refresh if needed (run via cron)."""
        status = self.check_token_expiration()

        if status['status'] == 'invalid' or status['status'] == 'missing':
            self.alert_service.alert_admin(
                severity="CRITICAL",
                message="Instagram access token is invalid or missing!"
            )
            return

        days_remaining = status['days_remaining']

        if days_remaining < self.token_warning_days:
            logger.warning(f"Token expires in {days_remaining} days, refreshing...")
            new_token = self.refresh_long_lived_token()

            if new_token:
                self.alert_service.alert_admin(
                    severity="INFO",
                    message=f"✅ Instagram token refreshed successfully. Was expiring in {days_remaining} days."
                )
            else:
                self.alert_service.alert_admin(
                    severity="ERROR",
                    message=f"❌ Failed to refresh Instagram token! Expires in {days_remaining} days. Manual intervention required."
                )
        else:
            logger.info(f"Token is healthy. Expires in {days_remaining} days.")
```

### Automated Token Refresh (Cron)

```bash
# Run daily at 3 AM to check/refresh token
0 3 * * * cd /home/pi/storyline-ai && /home/pi/.local/bin/storyline-cli refresh-token
```

---

## Backup & Disaster Recovery

### Backup Strategy

Critical data includes:
1. **PostgreSQL Database** (all metadata, queue, history)
2. **Media Files** (original images)
3. **Configuration** (.env, settings)

### Automated Backup Service

```python
# src/services/core/backup_service.py
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
import shutil

from src.services.base_service import BaseService
from src.utils.logger import logger
from src.config.settings import settings


class BackupService(BaseService):
    """Automated backup management for database and media."""

    def __init__(self):
        super().__init__()
        self.backup_dir = Path(settings.BACKUP_DIR or "/backup/storyline-ai")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.retention_days = 30

    def backup_database(self) -> Path:
        """
        Backup PostgreSQL database using pg_dump.

        Returns:
            Path to backup file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"db_backup_{timestamp}.sql.gz"

        logger.info(f"Starting database backup to {backup_file}")

        # Run pg_dump
        cmd = [
            "pg_dump",
            "-h", settings.DB_HOST,
            "-p", str(settings.DB_PORT),
            "-U", settings.DB_USER,
            "-d", settings.DB_NAME,
            "-F", "p",  # Plain text format
            "--no-owner",
            "--no-acl",
        ]

        try:
            # Dump and compress
            with open(backup_file, 'wb') as f:
                dump_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    env={"PGPASSWORD": settings.DB_PASSWORD}
                )
                gzip_process = subprocess.Popen(
                    ["gzip"],
                    stdin=dump_process.stdout,
                    stdout=f
                )
                dump_process.stdout.close()
                gzip_process.communicate()

            file_size_mb = backup_file.stat().st_size / (1024 * 1024)
            logger.info(f"✅ Database backup complete: {backup_file} ({file_size_mb:.1f}MB)")

            return backup_file

        except Exception as e:
            logger.error(f"Database backup failed: {str(e)}")
            raise

    def backup_media(self) -> Path:
        """
        Backup media directory using tar.

        Returns:
            Path to backup archive
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"media_backup_{timestamp}.tar.gz"

        logger.info(f"Starting media backup to {backup_file}")

        media_dir = Path(settings.MEDIA_DIR or "/home/pi/media")

        try:
            subprocess.run(
                ["tar", "-czf", str(backup_file), "-C", str(media_dir.parent), media_dir.name],
                check=True
            )

            file_size_mb = backup_file.stat().st_size / (1024 * 1024)
            logger.info(f"✅ Media backup complete: {backup_file} ({file_size_mb:.1f}MB)")

            return backup_file

        except Exception as e:
            logger.error(f"Media backup failed: {str(e)}")
            raise

    def backup_config(self) -> Path:
        """Backup configuration files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"config_backup_{timestamp}.tar.gz"

        config_files = [".env", "pytest.ini", "requirements.txt"]

        subprocess.run(
            ["tar", "-czf", str(backup_file)] + config_files,
            check=True
        )

        logger.info(f"✅ Config backup complete: {backup_file}")
        return backup_file

    def cleanup_old_backups(self):
        """Delete backups older than retention period."""
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)

        for backup_file in self.backup_dir.glob("*_backup_*.{sql.gz,tar.gz}"):
            file_date = datetime.fromtimestamp(backup_file.stat().st_mtime)

            if file_date < cutoff_date:
                logger.info(f"Deleting old backup: {backup_file}")
                backup_file.unlink()

    def full_backup(self) -> dict:
        """Run complete backup (database + media + config)."""
        with self.track_execution("full_backup") as run_id:
            results = {}

            try:
                results['database'] = str(self.backup_database())
                results['media'] = str(self.backup_media())
                results['config'] = str(self.backup_config())
                results['status'] = 'success'

                # Cleanup old backups
                self.cleanup_old_backups()

                self.set_result_summary(run_id, results)
                return results

            except Exception as e:
                results['status'] = 'failed'
                results['error'] = str(e)
                self.set_result_summary(run_id, results)
                raise
```

### Backup Cron Jobs

```bash
# Daily backup at 2 AM
0 2 * * * cd /home/pi/storyline-ai && /home/pi/.local/bin/storyline-cli backup --full

# Sync backups to cloud storage (optional)
0 3 * * * rclone sync /backup/storyline-ai remote:storyline-backups/
```

### Recovery Procedures

**Database Restoration**:
```bash
# Stop services
sudo systemctl stop storyline-ai

# Restore database
gunzip -c /backup/storyline-ai/db_backup_20240115_020000.sql.gz | psql -U storyline_user -d storyline_ai

# Start services
sudo systemctl start storyline-ai
```

**Media Restoration**:
```bash
# Extract media backup
tar -xzf /backup/storyline-ai/media_backup_20240115_020000.tar.gz -C /home/pi/
```

---

## Monitoring & Alerting

### Alert Service

```python
# src/services/core/alert_service.py
from enum import Enum
from typing import Optional
import httpx

from src.services.base_service import BaseService
from src.utils.logger import logger
from src.config.settings import settings


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "ℹ️ INFO"
    WARNING = "⚠️ WARNING"
    ERROR = "❌ ERROR"
    CRITICAL = "🚨 CRITICAL"


class AlertService(BaseService):
    """Send alerts to admin via Telegram."""

    def __init__(self):
        super().__init__()
        self.admin_chat_id = settings.ADMIN_TELEGRAM_CHAT_ID
        self.bot_token = settings.TELEGRAM_BOT_TOKEN

    async def alert_admin(
        self,
        severity: str,
        message: str,
        include_health_check: bool = False
    ):
        """
        Send alert to admin Telegram chat.

        Args:
            severity: Alert level (INFO, WARNING, ERROR, CRITICAL)
            message: Alert message
            include_health_check: Whether to append health check results
        """
        severity_enum = AlertSeverity[severity]
        formatted_message = f"{severity_enum.value}\n\n{message}"

        if include_health_check:
            from src.services.core.health_check import HealthCheckService
            health = HealthCheckService()
            health_result = health.check_all()
            formatted_message += f"\n\n**System Health**: {health_result['status']}"

        await self._send_telegram_message(formatted_message)

        # Also log locally
        logger.error(f"[ALERT] {severity}: {message}")

    async def _send_telegram_message(self, message: str):
        """Send message via Telegram Bot API."""
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

        async with httpx.AsyncClient() as client:
            await client.post(
                url,
                json={
                    "chat_id": self.admin_chat_id,
                    "text": message,
                    "parse_mode": "Markdown"
                }
            )


# Usage in other services
class PostingService(BaseService):
    def __init__(self):
        super().__init__()
        self.alert_service = AlertService()
        self.consecutive_failures = 0

    async def process_queue(self):
        """Process queue with failure monitoring."""
        try:
            # ... posting logic ...
            self.consecutive_failures = 0

        except Exception as e:
            self.consecutive_failures += 1

            if self.consecutive_failures >= 3:
                await self.alert_service.alert_admin(
                    severity="ERROR",
                    message=f"Posting service failed 3 times in a row!\nLast error: {str(e)}",
                    include_health_check=True
                )
```

### Queue Backlog Monitoring

```python
# src/services/core/queue_monitor.py
from datetime import datetime, timedelta

from src.services.base_service import BaseService
from src.services.core.alert_service import AlertService
from src.repositories.queue_repository import QueueRepository


class QueueMonitorService(BaseService):
    """Monitor queue health and alert on issues."""

    def __init__(self):
        super().__init__()
        self.queue_repo = QueueRepository()
        self.alert_service = AlertService()

    async def check_queue_health(self):
        """Check for queue issues and alert if needed."""
        pending_count = self.queue_repo.count_pending()
        oldest_pending = self.queue_repo.get_oldest_pending()

        # Alert if queue is backing up
        if pending_count > 50:
            await self.alert_service.alert_admin(
                severity="WARNING",
                message=f"Queue backlog: {pending_count} items pending"
            )

        # Alert if oldest item is very old
        if oldest_pending:
            age = datetime.now() - oldest_pending.created_at
            if age > timedelta(hours=24):
                await self.alert_service.alert_admin(
                    severity="ERROR",
                    message=f"Oldest queue item is {age.total_seconds()/3600:.1f} hours old! Possible rate limit or processing issue."
                )
```

### Monitoring Checklist

Run these checks via cron:

```bash
# Every hour: Check queue health
0 * * * * storyline-cli monitor-queue

# Every 6 hours: Check system health
0 */6 * * * storyline-cli check-health --alert-on-error

# Daily: Check token expiration
0 3 * * * storyline-cli check-token

# Daily: Verify backups exist
0 4 * * * storyline-cli verify-backups
```

---

## Configuration Validation

### Startup Validation

```python
# src/utils/validators.py
from typing import List, Tuple
from src.config.settings import settings


class ConfigValidator:
    """Validate configuration on startup."""

    @staticmethod
    def validate_all() -> Tuple[bool, List[str]]:
        """
        Validate all configuration settings.

        Returns:
            (is_valid, error_messages)
        """
        errors = []

        # Validate posting schedule
        if settings.POSTS_PER_DAY < 1 or settings.POSTS_PER_DAY > 10:
            errors.append("POSTS_PER_DAY must be between 1 and 10")

        if settings.POSTING_HOURS_START >= settings.POSTING_HOURS_END:
            errors.append("POSTING_HOURS_START must be before POSTING_HOURS_END")

        if settings.POSTING_HOURS_START < 0 or settings.POSTING_HOURS_END > 23:
            errors.append("Posting hours must be between 0-23 (UTC)")

        # Validate repost TTL
        if settings.REPOST_TTL_DAYS < 1:
            errors.append("REPOST_TTL_DAYS must be at least 1")

        # Validate Telegram config
        if not settings.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN is required")

        if not settings.TELEGRAM_CHANNEL_ID:
            errors.append("TELEGRAM_CHANNEL_ID is required")

        # Validate Instagram config (if API enabled)
        if settings.ENABLE_INSTAGRAM_API:
            if not settings.INSTAGRAM_ACCOUNT_ID:
                errors.append("INSTAGRAM_ACCOUNT_ID required when ENABLE_INSTAGRAM_API=true")

            if not settings.INSTAGRAM_ACCESS_TOKEN:
                errors.append("INSTAGRAM_ACCESS_TOKEN required when ENABLE_INSTAGRAM_API=true")

            if not settings.CLOUDINARY_CLOUD_NAME:
                errors.append("Cloudinary config required when ENABLE_INSTAGRAM_API=true")

        # Validate database config
        if not settings.DB_NAME:
            errors.append("DB_NAME is required")

        # Validate paths
        media_dir = Path(settings.MEDIA_DIR)
        if not media_dir.exists():
            errors.append(f"MEDIA_DIR does not exist: {settings.MEDIA_DIR}")

        is_valid = len(errors) == 0
        return is_valid, errors


# In src/main.py - validate on startup
def main():
    """Application entry point."""
    # Validate configuration
    is_valid, errors = ConfigValidator.validate_all()

    if not is_valid:
        logger.error("Configuration validation failed:")
        for error in errors:
            logger.error(f"  - {error}")
        sys.exit(1)

    logger.info("✅ Configuration validated successfully")

    # Continue with normal startup...
```

---

## Part D: Python Implementation

### pytest.ini

```ini
[pytest]
# Test discovery
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Output
addopts = 
    -v
    --strict-markers
    --tb=short
    --cov=src
    --cov-report=term-missing
    --cov-report=html

# Markers
markers =
    unit: Unit tests (fast, isolated)
    integration: Integration tests (slower, multiple components)
    slow: Slow tests (skip with -m "not slow")

# Asyncio
asyncio_mode = auto

# Warnings
filterwarnings =
    error
    ignore::DeprecationWarning
    ignore::PendingDeprecationWarning
```

### requirements.txt

```txt
# Core dependencies
python-dotenv==1.0.0
requests==2.31.0
psycopg2-binary==2.9.9
sqlalchemy==2.0.23

# Scheduling
apscheduler==3.10.4

# Image processing
Pillow==10.1.0

# Cloud storage
cloudinary==1.40.0

# Telegram
python-telegram-bot==20.7

# CLI
click==8.1.7
rich==13.7.0

# Utilities
python-dateutil==2.8.2

# Development
pytest==7.4.3
pytest-cov==4.1.0
pytest-asyncio==0.21.1
pytest-xdist==3.5.0  # Parallel test execution
black==23.12.0
flake8==6.1.0
mypy==1.7.1
```

### .env.example

```bash
# ============================================
# PHASE 1: REQUIRED (Telegram-Only Mode)
# ============================================

# Database Configuration
# Option 1: Use DATABASE_URL (recommended - works with local or Neon)
# DATABASE_URL=postgresql://postgres:password@localhost:5432/storyline_ai
# DATABASE_URL=postgresql://user:pass@ep-cool-name.us-east-2.aws.neon.tech/storyline_ai?sslmode=require

# Option 2: Use individual components (if DATABASE_URL not provided)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=storyline_ai
DB_USER=postgres
DB_PASSWORD=your_password_here

# Telegram Configuration (REQUIRED)
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHANNEL_ID=-1001234567890

# Media Configuration
MEDIA_BASE_PATH=/home/pi/storyline-ai/media

# Posting Configuration
POSTS_PER_DAY=3
POSTING_HOURS_START=9    # UTC hour (9 = 9 AM UTC)
POSTING_HOURS_END=21     # UTC hour (21 = 9 PM UTC)
AVOID_REPOST_DAYS=7

# Note: All times are in UTC. To post at 9 AM EST (UTC-5), set POSTING_HOURS_START=14

# Logging
LOG_LEVEL=INFO
LOG_FILE=/home/pi/storyline-ai/logs/app.log

# Dry Run Mode (set to true to test without actually posting)
DRY_RUN_MODE=false

# ============================================
# PHASE 2: OPTIONAL (Enable Automation)
# ============================================

# Instagram API Automation (OPTIONAL - set to true to enable)
ENABLE_INSTAGRAM_API=false

# Instagram API Configuration (only needed if ENABLE_INSTAGRAM_API=true)
INSTAGRAM_ACCOUNT_ID=your_instagram_business_account_id
ACCESS_TOKEN=your_long_lived_page_access_token
APP_ID=your_app_id
APP_SECRET=your_app_secret

# Cloudinary Configuration (only needed if ENABLE_INSTAGRAM_API=true)
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
```

### src/config/settings.py

```python
"""Application configuration management."""
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Settings:
    """Application settings."""
    
    # Database
    # Option 1: Use DATABASE_URL directly (supports local or Neon)
    # Option 2: Build from individual components
    DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")
    
    # Individual components (used if DATABASE_URL not provided)
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "storyline_ai")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    
    @property
    def database_url(self) -> str:
        """
        Get database URL.
        
        Priority:
        1. Use DATABASE_URL if provided (supports local or Neon)
        2. Build from individual components
        
        Examples:
        - Local: postgresql://postgres:password@localhost:5432/storyline_ai
        - Neon: postgresql://user:pass@ep-cool-name.us-east-2.aws.neon.tech/storyline_ai?sslmode=require
        """
        if self.DATABASE_URL:
            return self.DATABASE_URL
        
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    # Instagram API Automation (OPTIONAL - Phase 2)
    ENABLE_INSTAGRAM_API: bool = os.getenv("ENABLE_INSTAGRAM_API", "false").lower() == "true"
    INSTAGRAM_ACCOUNT_ID: str = os.getenv("INSTAGRAM_ACCOUNT_ID", "")
    ACCESS_TOKEN: str = os.getenv("ACCESS_TOKEN", "")
    APP_ID: str = os.getenv("APP_ID", "")
    APP_SECRET: str = os.getenv("APP_SECRET", "")
    GRAPH_API_VERSION: str = "v21.0"
    GRAPH_API_BASE_URL: str = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
    
    # Cloudinary (OPTIONAL - Phase 2, only needed if ENABLE_INSTAGRAM_API=true)
    CLOUDINARY_CLOUD_NAME: str = os.getenv("CLOUDINARY_CLOUD_NAME", "")
    CLOUDINARY_API_KEY: str = os.getenv("CLOUDINARY_API_KEY", "")
    CLOUDINARY_API_SECRET: str = os.getenv("CLOUDINARY_API_SECRET", "")
    
    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHANNEL_ID: str = os.getenv("TELEGRAM_CHANNEL_ID", "")
    
    # Media paths
    MEDIA_BASE_PATH: Path = Path(os.getenv("MEDIA_BASE_PATH", "./media"))
    STORIES_PATH: Path = MEDIA_BASE_PATH / "stories"
    
    # Posting configuration
    POSTS_PER_DAY: int = int(os.getenv("POSTS_PER_DAY", "3"))
    POSTING_HOURS_START: int = int(os.getenv("POSTING_HOURS_START", "9"))
    POSTING_HOURS_END: int = int(os.getenv("POSTING_HOURS_END", "21"))
    AVOID_REPOST_DAYS: int = int(os.getenv("AVOID_REPOST_DAYS", "7"))
    
    # Note: All times stored in database as UTC
    # POSTING_HOURS_START/END are interpreted as UTC hours
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: Optional[str] = os.getenv("LOG_FILE")
    
    # Dry run mode (for testing without actually posting)
    DRY_RUN_MODE: bool = os.getenv("DRY_RUN_MODE", "false").lower() == "true"
    
    def validate(self) -> bool:
        """Validate required settings are present."""
        # Phase 1 requirements (always required)
        required = [
            ("DB_PASSWORD", self.DB_PASSWORD),
            ("TELEGRAM_BOT_TOKEN", self.TELEGRAM_BOT_TOKEN),
            ("TELEGRAM_CHANNEL_ID", self.TELEGRAM_CHANNEL_ID),
        ]
        
        # Phase 2 requirements (only if Instagram API is enabled)
        if self.ENABLE_INSTAGRAM_API:
            required.extend([
                ("INSTAGRAM_ACCOUNT_ID", self.INSTAGRAM_ACCOUNT_ID),
                ("ACCESS_TOKEN", self.ACCESS_TOKEN),
                ("CLOUDINARY_CLOUD_NAME", self.CLOUDINARY_CLOUD_NAME),
                ("CLOUDINARY_API_KEY", self.CLOUDINARY_API_KEY),
                ("CLOUDINARY_API_SECRET", self.CLOUDINARY_API_SECRET),
            ])
        
        missing = [name for name, value in required if not value]
        
        if missing:
            raise ValueError(f"Missing required settings: {', '.join(missing)}")
        
        # Ensure media directories exist
        self.STORIES_PATH.mkdir(parents=True, exist_ok=True)
        
        return True


# Global settings instance
settings = Settings()
```

### src/config/database.py

```python
"""Database connection and session management."""
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base

from src.config.settings import settings

# Create database engine
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=False
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Provide a transactional scope for database operations."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
```

### src/models/posting_queue.py (Enhanced)

```python
"""Posting queue model with Telegram tracking."""
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, TIMESTAMP, Text, ForeignKey, Boolean, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from src.config.database import Base


class PostingQueue(Base):
    """Posting queue database model."""
    
    __tablename__ = "posting_queue"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    media_item_id = Column(UUID(as_uuid=True), ForeignKey("media_items.id", ondelete="CASCADE"), nullable=False)
    
    scheduled_for = Column(TIMESTAMP, nullable=False)
    status = Column(String(50), default="pending")
    
    # Cloud storage
    cloudinary_public_id = Column(Text, nullable=True)
    cloudinary_url = Column(Text, nullable=True)
    
    # Instagram response (for automated posts)
    instagram_media_id = Column(Text, nullable=True)
    instagram_permalink = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Telegram tracking (for manual posts)
    telegram_message_id = Column(BigInteger, nullable=True)
    telegram_chat_id = Column(BigInteger, nullable=True)
    completed_by_user = Column(Text, nullable=True)
    completed_by_user_id = Column(BigInteger, nullable=True)
    skipped = Column(Boolean, default=False)
    skip_reason = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    posted_at = Column(TIMESTAMP, nullable=True)
    completed_at = Column(TIMESTAMP, nullable=True)
    
    # Relationship
    media_item = relationship("MediaItem", backref="queue_items")
    
    def __repr__(self) -> str:
        return f"<PostingQueue(id={self.id}, scheduled_for={self.scheduled_for}, status={self.status})>"
```

### src/models/posting_history.py (Enhanced)

```python
"""Posting history model with user tracking."""
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Boolean, TIMESTAMP, Text, ForeignKey, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from src.config.database import Base


class PostingHistory(Base):
    """Posting history database model."""
    
    __tablename__ = "posting_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    media_item_id = Column(UUID(as_uuid=True), ForeignKey("media_items.id"), nullable=False)
    queue_item_id = Column(UUID(as_uuid=True), ForeignKey("posting_queue.id"), nullable=True)
    
    posted_at = Column(TIMESTAMP, nullable=False)
    instagram_media_id = Column(Text, nullable=True)
    instagram_permalink = Column(Text, nullable=True)
    cloudinary_public_id = Column(Text, nullable=True)
    
    # User tracking
    posted_by_user = Column(Text, nullable=True)  # Telegram username or 'system'
    posted_by_user_id = Column(BigInteger, nullable=True)  # Telegram user ID
    
    success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    
    # Relationships
    media_item = relationship("MediaItem", backref="history")
    queue_item = relationship("PostingQueue", backref="history")
    
    def __repr__(self) -> str:
        return f"<PostingHistory(id={self.id}, success={self.success}, posted_at={self.posted_at})>"
```

### src/services/posting.py (Enhanced with Error Handling & Retry Logic)

```python
"""Posting service - executes posts from queue with robust error handling.

Error Handling Strategy:
1. Transient errors (network, rate limit) → Retry with exponential backoff
2. Permanent errors (invalid token, bad file) → Fail immediately, no retry
3. All errors logged with full context for debugging
4. Cloudinary cleanup happens even on failure
"""
from datetime import datetime, timedelta
from typing import Optional, Tuple
from pathlib import Path
from sqlalchemy.orm import Session
import time

from src.config.settings import settings
from src.repositories.queue_repository import QueueRepository
from src.repositories.media_repository import MediaRepository
from src.repositories.history_repository import HistoryRepository
from src.services.instagram_api import InstagramAPIService
from src.services.cloud_storage import CloudStorageService
from src.services.telegram_service import TelegramService
from src.utils.logger import logger


# Error classification
TRANSIENT_ERRORS = [
    "network",
    "timeout",
    "rate limit",
    "temporarily unavailable",
    "503",
    "502",
    "504"
]

PERMANENT_ERRORS = [
    "invalid access token",
    "token expired",
    "file not found",
    "invalid media",
    "400",
    "401",
    "403",
    "404"
]


class PostingService:
    """Service for executing posts from the queue with error handling."""
    
    def __init__(self, db: Session):
        """Initialize posting service."""
        self.db = db
        self.queue_repo = QueueRepository(db)
        self.media_repo = MediaRepository(db)
        self.history_repo = HistoryRepository(db)
        self.instagram_api = InstagramAPIService()
        self.cloud_storage = CloudStorageService()
        self.telegram_service = TelegramService()
    
    async def process_pending_posts(self) -> int:
        """
        Process all pending posts that are due (including retries).
        
        Returns:
            Number of posts processed successfully
        """
        logger.info("Processing pending posts...")
        
        # Get posts that are due (including retry attempts)
        pending_posts = self.queue_repo.get_posts_due_for_processing()
        processed_count = 0
        
        for queue_item in pending_posts:
            try:
                media_item = queue_item.media_item
                
                # Check if this is a retry attempt
                if queue_item.retry_count > 0:
                    logger.info(
                        f"Retry attempt {queue_item.retry_count}/{queue_item.max_retries} "
                        f"for queue item {queue_item.id}"
                    )
                
                # Determine posting method based on ENABLE_INSTAGRAM_API flag
                if settings.ENABLE_INSTAGRAM_API and not media_item.requires_interaction:
                    # Phase 2: Automated posting via Instagram API (simple story)
                    success = await self._post_automated(queue_item, media_item)
                else:
                    # Phase 1 (or Phase 2 for interactive stories): Send to Telegram
                    success = await self._post_via_telegram(queue_item, media_item)
                
                if success:
                    processed_count += 1
                    
            except Exception as e:
                logger.error(
                    f"Unexpected error processing queue item {queue_item.id}: {str(e)}",
                    exc_info=True
                )
                # Handle unexpected errors
                await self._handle_posting_error(queue_item, str(e))
        
        logger.info(f"Processed {processed_count}/{len(pending_posts)} posts successfully")
        return processed_count
    
    def _is_transient_error(self, error_message: str) -> bool:
        """Check if error is transient (should retry)."""
        error_lower = error_message.lower()
        return any(keyword in error_lower for keyword in TRANSIENT_ERRORS)
    
    def _is_permanent_error(self, error_message: str) -> bool:
        """Check if error is permanent (don't retry)."""
        error_lower = error_message.lower()
        return any(keyword in error_lower for keyword in PERMANENT_ERRORS)
    
    async def _handle_posting_error(
        self,
        queue_item,
        error_message: str,
        cloudinary_public_id: Optional[str] = None
    ) -> None:
        """
        Handle posting error with retry logic.
        
        Args:
            queue_item: Queue item that failed
            error_message: Error message
            cloudinary_public_id: Cloudinary ID to cleanup (if applicable)
        """
        # Cleanup Cloudinary if needed
        if cloudinary_public_id:
            try:
                self.cloud_storage.delete_image(cloudinary_public_id)
                logger.info(f"Cleaned up Cloudinary image: {cloudinary_public_id}")
            except Exception as e:
                logger.warning(f"Failed to cleanup Cloudinary: {str(e)}")
        
        # Determine if we should retry
        should_retry = False
        
        if self._is_permanent_error(error_message):
            logger.error(f"Permanent error detected, will not retry: {error_message}")
            should_retry = False
        elif self._is_transient_error(error_message):
            if queue_item.retry_count < queue_item.max_retries:
                logger.info(f"Transient error detected, will retry: {error_message}")
                should_retry = True
            else:
                logger.error(
                    f"Max retries ({queue_item.max_retries}) exceeded for transient error"
                )
                should_retry = False
        else:
            # Unknown error type - retry if we have attempts left
            if queue_item.retry_count < queue_item.max_retries:
                logger.warning(f"Unknown error type, will retry: {error_message}")
                should_retry = True
            else:
                should_retry = False
        
        if should_retry:
            # Calculate exponential backoff: 2^retry_count * 5 minutes
            delay_minutes = (2 ** queue_item.retry_count) * 5
            next_retry = datetime.utcnow() + timedelta(minutes=delay_minutes)
            
            self.queue_repo.schedule_retry(
                queue_item_id=str(queue_item.id),
                next_retry_at=next_retry,
                retry_count=queue_item.retry_count + 1,
                error_message=error_message
            )
            
            logger.info(
                f"Scheduled retry {queue_item.retry_count + 1}/{queue_item.max_retries} "
                f"in {delay_minutes} minutes (at {next_retry})"
            )
        else:
            # Mark as permanently failed
            self.queue_repo.mark_as_failed(
                queue_item_id=str(queue_item.id),
                error_message=error_message
            )
            
            # Log to history
            self.history_repo.create_history_entry(
                media_item_id=str(queue_item.media_item_id),
                queue_item_id=str(queue_item.id),
                success=False,
                posted_by_user="system",
                error_message=error_message
            )
            
            logger.error(f"Queue item {queue_item.id} marked as failed")
    
    async def _post_automated(self, queue_item, media_item) -> bool:
        """
        Post story automatically via Instagram API.
        
        Args:
            queue_item: Queue item from database
            media_item: Media item from database
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Auto-posting {media_item.file_name}")
            
            # DRY RUN MODE: Simulate posting without actually doing it
            if settings.DRY_RUN_MODE:
                logger.info(f"[DRY RUN] Would post {media_item.file_name} to Instagram")
                logger.info(f"[DRY RUN] File: {media_item.file_path}")
                logger.info(f"[DRY RUN] Tags: {media_item.tags}")
                
                # Simulate success
                self.queue_repo.update_status(
                    str(queue_item.id),
                    status="posted",
                    instagram_media_id="dry_run_media_123",
                    instagram_permalink="https://instagram.com/dry_run"
                )
                
                self.media_repo.update_post_stats(str(media_item.id))
                
                self.history_repo.create_history_entry(
                    media_item_id=str(media_item.id),
                    queue_item_id=str(queue_item.id),
                    success=True,
                    posted_by_user="system (dry-run)",
                    instagram_media_id="dry_run_media_123"
                )
                
                logger.info(f"[DRY RUN] Successfully simulated post")
                return True
            
            # Update status to processing
            self.queue_repo.update_status(str(queue_item.id), status="processing")
            
            # Upload to Cloudinary
            file_path = Path(media_item.file_path)
            upload_result = self.cloud_storage.upload_image(file_path)
            
            # Update queue with Cloudinary info
            self.queue_repo.update_status(
                str(queue_item.id),
                status="processing",
                cloudinary_public_id=upload_result["public_id"],
                cloudinary_url=upload_result["secure_url"]
            )
            
            # Post to Instagram (simple story - no stickers)
            instagram_result = self.instagram_api.create_story(
                image_url=upload_result["secure_url"]
            )
            
            # Update queue status
            self.queue_repo.update_status(
                str(queue_item.id),
                status="posted",
                instagram_media_id=instagram_result["id"],
                instagram_permalink=instagram_result.get("permalink")
            )
            
            # Update media item stats
            self.media_repo.update_post_stats(str(media_item.id))
            
            # Add to history
            self.history_repo.create_history_entry(
                media_item_id=str(media_item.id),
                queue_item_id=str(queue_item.id),
                success=True,
                posted_by_user="system",
                instagram_media_id=instagram_result["id"],
                instagram_permalink=instagram_result.get("permalink"),
                cloudinary_public_id=upload_result["public_id"]
            )
            
            # Cleanup Cloudinary after successful post (saves quota)
            # Note: Instagram caches the image, so safe to delete immediately
            self.cloud_storage.delete_image(upload_result["public_id"])
            
            logger.info(f"Successfully posted {media_item.file_name}")
            return True
            
        except Exception as e:
            logger.error(
                f"Failed to auto-post {media_item.file_name}: {str(e)}",
                exc_info=True
            )
            
            # Handle error with retry logic
            await self._handle_posting_error(
                queue_item=queue_item,
                error_message=str(e),
                cloudinary_public_id=upload_result.get("public_id") if 'upload_result' in locals() else None
            )
            
            return False
    
    async def _post_via_telegram(self, queue_item, media_item) -> bool:
        """
        Send Telegram notification for manual posting.
        
        Note: Sends image directly from filesystem to Telegram.
        No Cloudinary needed for this workflow.
        
        Args:
            queue_item: Queue item from database
            media_item: Media item from database
            
        Returns:
            True if notification sent, False otherwise
        """
        try:
            logger.info(f"Sending Telegram notification for {media_item.file_name}")
            
            # DRY RUN MODE: Simulate Telegram notification
            if settings.DRY_RUN_MODE:
                logger.info(f"[DRY RUN] Would send Telegram notification for {media_item.file_name}")
                logger.info(f"[DRY RUN] Title: {media_item.title}")
                logger.info(f"[DRY RUN] Link: {media_item.link_url}")
                logger.info(f"[DRY RUN] Channel: {settings.TELEGRAM_CHANNEL_ID}")
                
                # Simulate success
                self.queue_repo.update_status(
                    str(queue_item.id),
                    status="pending",  # Keep as pending in dry run
                    telegram_message_id=99999,
                    telegram_chat_id=int(settings.TELEGRAM_CHANNEL_ID)
                )
                
                logger.info(f"[DRY RUN] Successfully simulated Telegram notification")
                return True
            
            # Update status to processing
            self.queue_repo.update_status(str(queue_item.id), status="processing")
            
            # Prepare media item data
            media_dict = media_item.to_dict()
            
            # Send Telegram notification with image directly from filesystem
            message_id = await self.telegram_service.send_story_notification(
                queue_item_id=str(queue_item.id),
                media_item_dict=media_dict,
                image_path=Path(media_item.file_path)  # Direct file upload
            )
            
            if message_id:
                # Update queue with Telegram info
                self.queue_repo.update_status(
                    str(queue_item.id),
                    status="pending",  # Keep as pending until manually marked
                    telegram_message_id=message_id,
                    telegram_chat_id=int(settings.TELEGRAM_CHANNEL_ID)
                )
                
                logger.info(f"Telegram notification sent: message_id={message_id}")
                return True
            else:
                raise Exception("Failed to send Telegram notification")
                
        except Exception as e:
            logger.error(
                f"Failed to send Telegram notification for {media_item.file_name}: {str(e)}",
                exc_info=True
            )
            
            # Handle error with retry logic
            await self._handle_posting_error(
                queue_item=queue_item,
                error_message=f"Telegram notification failed: {str(e)}"
            )
            
            return False
```

### src/services/telegram_service.py (Consolidated Telegram Service)

```python
"""Telegram service - handles all Telegram bot operations.

This service manages:
- Bot initialization and lifecycle
- Sending story notifications to channel
- Handling callback queries (button clicks)
- Command handlers (/pending, /stats, etc.)
- Message updates and edits
"""
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

from src.config.settings import settings
from src.config.database import get_db
from src.repositories.queue_repository import QueueRepository
from src.repositories.history_repository import HistoryRepository
from src.utils.logger import logger


class TelegramService:
    """Centralized service for all Telegram bot operations."""
    
    def __init__(self):
        """Initialize Telegram service."""
        self.application: Optional[Application] = None
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.channel_id = settings.TELEGRAM_CHANNEL_ID
        
    async def start_bot(self) -> None:
        """Start the Telegram bot with all handlers."""
        logger.info("Starting Telegram bot...")
        
        # Create application
        self.application = Application.builder().token(self.bot_token).build()
        
        # Register command handlers
        self.application.add_handler(CommandHandler("pending", self.cmd_pending))
        self.application.add_handler(CommandHandler("posted", self.cmd_posted))
        self.application.add_handler(CommandHandler("stats", self.cmd_stats))
        self.application.add_handler(CommandHandler("help", self.cmd_help))
        
        # Register callback query handler (for button clicks)
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        
        # Start bot (polling mode)
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        
        logger.info("Telegram bot started successfully")
    
    async def stop_bot(self) -> None:
        """Stop the Telegram bot gracefully."""
        if self.application:
            logger.info("Stopping Telegram bot...")
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
        logger.info("Telegram bot stopped")

    async def send_story_notification(
        self,
        queue_item_id: str,
        media_item_dict: Dict[str, Any],
        image_path: Path
    ) -> Optional[int]:
        """
        Send story notification to Telegram channel.
        
        Args:
            queue_item_id: Queue item UUID
            media_item_dict: Media item data from database
            image_path: Path to image file
            
        Returns:
            Message ID if successful, None otherwise
        """
        try:
            # Build message text
            title = media_item_dict.get('title', 'Untitled')
            link_url = media_item_dict.get('link_url', '')
            tags = media_item_dict.get('tags', [])
            caption = media_item_dict.get('caption', '')
            
            message_text = f"📸 STORY NOTIFICATION\n"
            message_text += f"━━━━━━━━━━━━━━━━━━━━━\n"
            message_text += f"📌 Title: {title}\n"
            
            if link_url:
                message_text += f"🔗 Link: {link_url}\n"
            
            if tags:
                message_text += f"🏷️ Tags: {', '.join(tags)}\n"
            
            if caption:
                message_text += f"💬 Caption: {caption}\n"
            
            message_text += f"\n👉 Download image above, post to Instagram\n"
            message_text += f"\nStatus: ⏳ PENDING\n"
            message_text += f"Queue ID: {queue_item_id[:8]}"
            
            # Build inline keyboard
            keyboard = []
            
            if link_url:
                keyboard.append([
                    InlineKeyboardButton("📋 Copy Link", callback_data=f"copy:{queue_item_id}")
                ])
            
            keyboard.append([
                InlineKeyboardButton("✅ Mark Posted", callback_data=f"posted:{queue_item_id}"),
                InlineKeyboardButton("⏭️ Skip", callback_data=f"skip:{queue_item_id}")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Send photo with message
            with open(image_path, 'rb') as photo:
                message = await self.application.bot.send_photo(
                    chat_id=self.channel_id,
                    photo=photo,
                    caption=message_text,
                    reply_markup=reply_markup
                )
            
            logger.info(f"Sent Telegram notification: message_id={message.message_id}")
            return message.message_id
            
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {str(e)}")
            return None
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle button callback queries."""
        query = update.callback_query
        await query.answer()
        
        # Parse callback data
        action, queue_item_id = query.data.split(':', 1)
        
        if action == "posted":
            await self._handle_posted(query, queue_item_id)
        elif action == "skip":
            await self._handle_skip(query, queue_item_id)
        elif action == "copy":
            await self._handle_copy_link(query, queue_item_id)
    
    async def _handle_posted(self, query, queue_item_id: str) -> None:
        """Handle 'Mark Posted' button click."""
        try:
            with get_db() as db:
                queue_repo = QueueRepository(db)
                history_repo = HistoryRepository(db)
                
                # Try to claim the post (atomic operation)
                success = queue_repo.mark_as_posted(
                    queue_item_id=queue_item_id,
                    telegram_user_id=query.from_user.id,
                    telegram_username=query.from_user.username or "unknown"
                )
                
                if success:
                    # Update message
                    new_text = query.message.caption.replace(
                        "Status: ⏳ PENDING",
                        f"Status: ✅ POSTED\n"
                        f"👤 Posted by: @{query.from_user.username}\n"
                        f"🕐 Posted at: {datetime.now().strftime('%I:%M %p')}"
                    )
                    
                    await query.edit_message_caption(
                        caption=new_text,
                        reply_markup=None  # Remove buttons
                    )
                    
                    await query.answer("✅ Marked as posted!")
                else:
                    await query.answer(
                        "⚠️ Someone else already marked this as posted",
                        show_alert=True
                    )
                    
        except Exception as e:
            logger.error(f"Error handling posted callback: {str(e)}")
            await query.answer("❌ Error updating status", show_alert=True)
    
    async def _handle_skip(self, query, queue_item_id: str) -> None:
        """Handle 'Skip' button click."""
        try:
            with get_db() as db:
                queue_repo = QueueRepository(db)
                
                success = queue_repo.mark_as_skipped(
                    queue_item_id=queue_item_id,
                    telegram_user_id=query.from_user.id,
                    telegram_username=query.from_user.username or "unknown"
                )
                
                if success:
                    new_text = query.message.caption.replace(
                        "Status: ⏳ PENDING",
                        f"Status: ⏭️ SKIPPED\n"
                        f"👤 Skipped by: @{query.from_user.username}"
                    )
                    
                    await query.edit_message_caption(
                        caption=new_text,
                        reply_markup=None
                    )
                    
                    await query.answer("⏭️ Skipped")
                else:
                    await query.answer("⚠️ Already processed", show_alert=True)
                    
        except Exception as e:
            logger.error(f"Error handling skip callback: {str(e)}")
            await query.answer("❌ Error", show_alert=True)
    
    async def _handle_copy_link(self, query, queue_item_id: str) -> None:
        """Handle 'Copy Link' button click."""
        # Note: Telegram doesn't support copying to clipboard
        # This just shows the link in a popup
        try:
            with get_db() as db:
                queue_repo = QueueRepository(db)
                queue_item = queue_repo.get_by_id(queue_item_id)
                
                if queue_item and queue_item.media_item.link_url:
                    await query.answer(
                        f"Link: {queue_item.media_item.link_url}",
                        show_alert=True
                    )
                else:
                    await query.answer("No link available", show_alert=True)
                    
        except Exception as e:
            logger.error(f"Error handling copy link: {str(e)}")
            await query.answer("❌ Error", show_alert=True)
    
    # Command handlers
    async def cmd_pending(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show pending posts."""
        # Implementation here
        await update.message.reply_text("📋 Pending posts feature coming soon!")
    
    async def cmd_posted(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show recent posting history."""
        await update.message.reply_text("📊 Posting history feature coming soon!")
    
    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show posting statistics."""
        await update.message.reply_text("📈 Statistics feature coming soon!")
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show help message."""
        help_text = (
            "🤖 Storyline AI Bot Commands\n\n"
            "/pending - Show pending posts\n"
            "/posted - Show recent posting history\n"
            "/stats - Show posting statistics\n"
            "/help - Show this help message"
        )
        await update.message.reply_text(help_text)
```

### src/main.py (Single Process Architecture)

```python
"""Main application entry point - runs scheduler and Telegram bot in single process.

Architecture:
- Single asyncio event loop
- APScheduler for posting jobs
- Telegram bot for manual workflow
- All services run in same process
"""
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config.settings import settings
from src.config.database import get_db
from src.services.media_ingestion import MediaIngestionService
from src.services.scheduler import SchedulerService
from src.services.posting import PostingService
from src.services.telegram_service import TelegramService
from src.utils.logger import logger


# Global Telegram service instance (shared across jobs)
telegram_service = None


def scan_media_files():
    """Scan media directories for new files."""
    logger.info("Starting media scan...")
    
    with get_db() as db:
        service = MediaIngestionService(db)
        results = service.scan_all_directories()
        
    logger.info(f"Media scan complete: {results}")


def create_schedule():
    """Create posting schedule for the next week."""
    logger.info("Creating posting schedule...")
    
    with get_db() as db:
        service = SchedulerService(db)
        count = service.create_week_schedule()
        
    logger.info(f"Schedule created: {count} posts scheduled")


async def process_queue():
    """Process pending posts in the queue."""
    logger.info("Processing posting queue...")
    
    with get_db() as db:
        service = PostingService(db)
        count = await service.process_pending_posts()
        
    logger.info(f"Queue processing complete: {count} posts processed")


async def main():
    """Main application loop - runs scheduler and Telegram bot together."""
    global telegram_service
    
    logger.info("Starting Storyline AI - Instagram Story Automation System")
    
    # Log current mode
    if settings.ENABLE_INSTAGRAM_API:
        logger.info("Mode: HYBRID (Telegram + Instagram API automation)")
    else:
        logger.info("Mode: TELEGRAM-ONLY (all posts via Telegram)")
    
    # Validate configuration
    try:
        settings.validate()
        logger.info("Configuration validated successfully")
    except ValueError as e:
        logger.error(f"Configuration error: {str(e)}")
        return
    
    # Initialize Telegram service (single instance)
    telegram_service = TelegramService()
    
    # Start Telegram bot (non-blocking)
    await telegram_service.start_bot()
    
    # Initialize scheduler
    scheduler = AsyncIOScheduler()
    
    # Schedule media scanning (every hour)
    scheduler.add_job(
        scan_media_files,
        CronTrigger(minute=0),
        id="scan_media",
        name="Scan media directories",
        replace_existing=True
    )
    
    # Schedule posting schedule creation (daily at 1 AM)
    scheduler.add_job(
        create_schedule,
        CronTrigger(hour=1, minute=0),
        id="create_schedule",
        name="Create posting schedule",
        replace_existing=True
    )
    
    # Schedule queue processing (every 5 minutes)
    scheduler.add_job(
        process_queue,
        CronTrigger(minute="*/5"),
        id="process_queue",
        name="Process posting queue",
        replace_existing=True
    )
    
    # Run initial setup
    logger.info("Running initial setup...")
    scan_media_files()
    create_schedule()
    
    # Start scheduler
    scheduler.start()
    logger.info("Scheduler started. Press Ctrl+C to exit.")
    
    try:
        # Keep running indefinitely
        logger.info("System running. Press Ctrl+C to stop.")
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down gracefully...")
        scheduler.shutdown(wait=False)
        await telegram_service.stop_bot()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
```

### CLI Commands for Telegram

### cli/commands/telegram.py

```python
"""Telegram bot management commands."""
import click
import asyncio
from rich.console import Console

from src.services.telegram_service import TelegramService
from src.config.settings import settings

console = Console()


@click.command()
def start_telegram():
    """
    Start the Telegram bot (standalone mode).
    
    Note: Normally the bot runs within src/main.py alongside the scheduler.
    This command is for testing/debugging the bot independently.
    """
    console.print("[bold blue]Starting Telegram bot (standalone mode)...[/bold blue]")
    console.print("[dim]Tip: In production, use 'python -m src.main' to run bot + scheduler together[/dim]\n")
    
    if not settings.TELEGRAM_BOT_TOKEN:
        console.print("[bold red]Error: TELEGRAM_BOT_TOKEN not configured[/bold red]")
        return
    
    if not settings.TELEGRAM_CHANNEL_ID:
        console.print("[bold red]Error: TELEGRAM_CHANNEL_ID not configured[/bold red]")
        return
    
    async def run_bot():
        service = TelegramService()
        await service.start_bot()
        console.print("[green]✓[/green] Bot started. Press Ctrl+C to stop.")
        await asyncio.Event().wait()
    
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        console.print("\n[yellow]Bot stopped[/yellow]")


@click.command()
def test_telegram():
    """Test Telegram bot connection."""
    console.print("[bold blue]Testing Telegram bot...[/bold blue]")
    
    if not settings.TELEGRAM_BOT_TOKEN:
        console.print("[bold red]Error: TELEGRAM_BOT_TOKEN not configured[/bold red]")
        return
    
    import requests
    
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getMe"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        if data.get("ok"):
            bot_info = data.get("result", {})
            console.print(f"[green]✓[/green] Bot connected: @{bot_info.get('username')}")
            console.print(f"  Name: {bot_info.get('first_name')}")
            console.print(f"  ID: {bot_info.get('id')}")
        else:
            console.print("[red]✗[/red] Bot authentication failed")
    else:
        console.print(f"[red]✗[/red] Connection failed: {response.status_code}")
    
    # Test channel access
    if settings.TELEGRAM_CHANNEL_ID:
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": settings.TELEGRAM_CHANNEL_ID,
            "text": "🤖 Test message from Instagram Story Automation"
        }
        response = requests.post(url, json=data)
        
        if response.status_code == 200:
            console.print(f"[green]✓[/green] Channel access verified")
        else:
            console.print(f"[red]✗[/red] Channel access failed: {response.json()}")


if __name__ == "__main__":
    test_telegram()
```

### cli/commands/list_cmd.py (With Rich Output)

```python
"""List media command with beautiful rich output."""
import click
from rich.console import Console
from rich.table import Table
from rich.progress import track
from datetime import datetime

from src.config.database import get_db
from src.repositories.media_repository import MediaRepository

console = Console()


@click.command()
@click.option('--type', type=click.Choice(['all', 'auto', 'manual']), default='all',
              help='Filter by posting type')
@click.option('--limit', default=50, help='Maximum number of items to show')
def list_media(type, limit):
    """List indexed media files with beautiful formatting."""
    console.print("[bold blue]📚 Media Library[/bold blue]\n")
    
    with get_db() as db:
        repo = MediaRepository(db)
        
        # Get media items based on filter
        if type == 'auto':
            items = repo.get_by_requires_interaction(False, limit=limit)
            filter_desc = "Automated Posts"
        elif type == 'manual':
            items = repo.get_by_requires_interaction(True, limit=limit)
            filter_desc = "Manual Posts (Telegram)"
        else:
            items = repo.get_all(limit=limit)
            filter_desc = "All Media"
        
        if not items:
            console.print("[yellow]No media files found. Run 'index-media' first.[/yellow]")
            return
        
        # Create table
        table = Table(title=f"{filter_desc} ({len(items)} items)")
        
        table.add_column("File", style="cyan", no_wrap=False, max_width=40)
        table.add_column("Type", style="magenta", justify="center")
        table.add_column("Title", style="green", max_width=30)
        table.add_column("Posted", style="yellow", justify="center")
        table.add_column("Tags", style="blue", max_width=30)
        
        for item in track(items, description="Loading media..."):
            # Determine type
            post_type = "🤖 Auto" if not item.requires_interaction else "👤 Manual"
            
            # Format title
            title = item.title or "-"
            
            # Format posted count
            if item.times_posted > 0:
                posted = f"✓ {item.times_posted}x"
                if item.last_posted_at:
                    days_ago = (datetime.utcnow() - item.last_posted_at).days
                    posted += f" ({days_ago}d ago)"
            else:
                posted = "Never"
            
            # Format tags
            tags = ", ".join(item.tags[:3]) if item.tags else "-"
            if item.tags and len(item.tags) > 3:
                tags += f" +{len(item.tags) - 3}"
            
            table.add_row(
                item.file_name,
                post_type,
                title,
                posted,
                tags
            )
        
        console.print(table)
        
        # Summary statistics
        console.print(f"\n[dim]Total: {len(items)} files[/dim]")
        
        auto_count = sum(1 for item in items if not item.requires_interaction)
        manual_count = sum(1 for item in items if item.requires_interaction)
        posted_count = sum(1 for item in items if item.times_posted > 0)
        
        console.print(f"[dim]🤖 Auto: {auto_count} | 👤 Manual: {manual_count} | ✓ Posted: {posted_count}[/dim]")
```

### cli/commands/index.py (With Rich Output)

```python
"""Index media command with progress bars."""
import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel

from src.config.database import get_db
from src.services.media_ingestion import MediaIngestionService
from src.config.settings import settings

console = Console()


@click.command()
@click.option('--path', default=None, help='Specific directory to index')
def index_media(path):
    """Index media files with progress tracking."""
    console.print(Panel.fit(
        "[bold blue]📁 Media Indexing[/bold blue]\n"
        "Scanning directories and calculating file hashes...",
        border_style="blue"
    ))
    
    target_path = path or settings.STORIES_PATH
    
    with get_db() as db:
        service = MediaIngestionService(db)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            
            # Add task
            task = progress.add_task("[cyan]Indexing media files...", total=None)
            
            # Run indexing
            results = service.scan_directory(target_path)
            
            progress.update(task, completed=True)
        
        # Display results
        console.print("\n[bold green]✓ Indexing Complete[/bold green]\n")
        
        # Results table
        from rich.table import Table
        
        table = Table(show_header=False, box=None)
        table.add_column(style="cyan", justify="right")
        table.add_column(style="white")
        
        table.add_row("✓ Added:", f"[green]{results['added']}[/green] new files")
        table.add_row("↻ Updated:", f"[yellow]{results['updated']}[/yellow] existing files")
        table.add_row("⊗ Skipped:", f"[dim]{results['skipped']}[/dim] unchanged files")
        
        if results.get('duplicates', 0) > 0:
            table.add_row("⚠ Duplicates:", f"[yellow]{results['duplicates']}[/yellow] duplicate content")
        
        console.print(table)
        
        if results['added'] > 0:
            console.print(f"\n[dim]Run 'create-schedule' to schedule new posts[/dim]")
```

### cli/main.py (Updated)

```python
"""CLI entry point with rich styling."""
import click
from rich.console import Console
from rich.panel import Panel

from cli.commands import index, list_cmd, schedule, post, test, telegram, health

console = Console()


@click.group()
def cli():
    """
    🎬 Storyline AI - Instagram Story Automation
    
    Automate your Instagram Stories with smart scheduling and team collaboration.
    """
    pass


@cli.command()
def version():
    """Show version information."""
    console.print(Panel.fit(
        "[bold blue]Storyline AI[/bold blue]\n"
        "Version: 1.0.0\n"
        "Instagram Story Automation System",
        border_style="blue"
    ))


# Register commands
cli.add_command(index.index_media, name="index-media")
cli.add_command(list_cmd.list_media, name="list-media")
cli.add_command(schedule.create_schedule, name="create-schedule")
cli.add_command(post.process_queue, name="process-queue")
cli.add_command(test.test_api, name="test-api")
cli.add_command(telegram.start_telegram, name="start-telegram")
cli.add_command(telegram.test_telegram, name="test-telegram")
cli.add_command(health.check_health, name="check-health")
cli.add_command(users.list_users, name="list-users")
cli.add_command(users.promote_user, name="promote-user")
cli.add_command(users.deactivate_user, name="deactivate-user")
cli.add_command(users.user_stats, name="user-stats")
cli.add_command(service_runs.list_runs, name="list-service-runs")


if __name__ == "__main__":
    cli()
```

### Example CLI Output

**`storyline-cli list-media`**:
```
📚 Media Library

                    All Media (47 items)                    
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━┓
┃ File               ┃ Type  ┃ Title       ┃ Posted  ┃ Tags       ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━┩
│ meme1.jpg          │ 🤖 Auto│ Funny Meme  │ ✓ 2x    │ meme, fun  │
│                    │       │             │ (3d ago)│            │
│ tshirt-red.jpg     │ 👤 Man │ Red Tshirt  │ Never   │ product,   │
│                    │  ual  │             │         │ tshirt     │
│ poll-story.jpg     │ 👤 Man │ Community   │ ✓ 1x    │ poll,      │
│                    │  ual  │ Poll        │ (1d ago)│ engage     │
└────────────────────┴───────┴─────────────┴─────────┴────────────┘

Total: 47 files
🤖 Auto: 32 | 👤 Manual: 15 | ✓ Posted: 23
```

**`storyline-cli index-media`**:
```
╭─────────────────────────────────────────╮
│ 📁 Media Indexing                       │
│ Scanning directories and calculating    │
│ file hashes...                          │
╰─────────────────────────────────────────╯

⠋ Indexing media files... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100%

✓ Indexing Complete

  ✓ Added:      12 new files
  ↻ Updated:    3 existing files
  ⊗ Skipped:    32 unchanged files
  ⚠ Duplicates: 2 duplicate content

Run 'create-schedule' to schedule new posts
```

**`storyline-cli check-health`**:
```
Running health checks...

✓ System Status: HEALTHY

           Health Check Results           
┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Component        ┃ Status    ┃ Details                 ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Database         │ ✓ Healthy │ Database connection OK  │
│ Instagram Api    │ ✓ Healthy │ Credentials valid       │
│ Telegram         │ ✓ Healthy │ Bot connected: @mybot   │
│ Recent Posts     │ ✓ Healthy │ 5 posts in last 24h     │
│ Pending Queue    │ ✓ Healthy │ 3 pending, 0 overdue    │
│ Failed Posts     │ ✓ Healthy │ 0 failed in last 7 days │
└──────────────────┴───────────┴─────────────────────────┘
```


### src/services/health_check.py

```python
"""Health check service for monitoring system status."""
from datetime import datetime, timedelta
from typing import Dict, Any
from sqlalchemy import text

from src.config.database import get_db
from src.config.settings import settings
from src.services.instagram_api import InstagramAPIService
from src.utils.logger import logger


class HealthCheckService:
    """Service for checking system health."""
    
    def __init__(self):
        """Initialize health check service."""
        self.instagram_api = InstagramAPIService()
    
    def check_all(self) -> Dict[str, Any]:
        """
        Run all health checks.
        
        Returns:
            Dict with overall status and individual check results
        """
        checks = {
            'database': self._check_database(),
            'instagram_api': self._check_instagram_api(),
            'telegram': self._check_telegram(),
            'recent_posts': self._check_recent_posts(),
            'pending_queue': self._check_pending_queue(),
            'failed_posts': self._check_failed_posts(),
        }
        
        # Overall status is healthy if all checks pass
        all_healthy = all(check['status'] == 'healthy' for check in checks.values())
        
        return {
            'status': 'healthy' if all_healthy else 'degraded',
            'timestamp': datetime.utcnow().isoformat(),
            'checks': checks
        }
    
    def _check_database(self) -> Dict[str, Any]:
        """Check database connectivity."""
        try:
            with get_db() as db:
                # Simple query to test connection
                result = db.execute(text("SELECT 1")).scalar()
                
                if result == 1:
                    return {
                        'status': 'healthy',
                        'message': 'Database connection OK'
                    }
                else:
                    return {
                        'status': 'unhealthy',
                        'message': 'Database query returned unexpected result'
                    }
                    
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            return {
                'status': 'unhealthy',
                'message': f'Database error: {str(e)}'
            }
    
    def _check_instagram_api(self) -> Dict[str, Any]:
        """Check Instagram API connectivity and credentials."""
        try:
            if self.instagram_api.verify_credentials():
                rate_limit = self.instagram_api.get_rate_limit_status()
                return {
                    'status': 'healthy',
                    'message': 'Instagram API credentials valid',
                    'rate_limit': rate_limit
                }
            else:
                return {
                    'status': 'unhealthy',
                    'message': 'Instagram API credentials invalid'
                }
                
        except Exception as e:
            logger.error(f"Instagram API health check failed: {str(e)}")
            return {
                'status': 'unhealthy',
                'message': f'Instagram API error: {str(e)}'
            }
    
    def _check_telegram(self) -> Dict[str, Any]:
        """Check Telegram bot configuration."""
        try:
            import requests
            
            url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getMe"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    bot_info = data.get('result', {})
                    return {
                        'status': 'healthy',
                        'message': f"Telegram bot connected: @{bot_info.get('username')}",
                        'bot_id': bot_info.get('id')
                    }
            
            return {
                'status': 'unhealthy',
                'message': 'Telegram bot authentication failed'
            }
                
        except Exception as e:
            logger.error(f"Telegram health check failed: {str(e)}")
            return {
                'status': 'unhealthy',
                'message': f'Telegram error: {str(e)}'
            }
    
    def _check_recent_posts(self) -> Dict[str, Any]:
        """Check if posts have been made recently."""
        try:
            with get_db() as db:
                # Check for posts in last 24 hours
                result = db.execute(text("""
                    SELECT COUNT(*) 
                    FROM posting_history 
                    WHERE posted_at > NOW() - INTERVAL '24 hours'
                      AND success = TRUE
                """)).scalar()
                
                if result > 0:
                    return {
                        'status': 'healthy',
                        'message': f'{result} posts in last 24 hours',
                        'count': result
                    }
                else:
                    return {
                        'status': 'warning',
                        'message': 'No posts in last 24 hours',
                        'count': 0
                    }
                    
        except Exception as e:
            logger.error(f"Recent posts check failed: {str(e)}")
            return {
                'status': 'unhealthy',
                'message': f'Error checking recent posts: {str(e)}'
            }
    
    def _check_pending_queue(self) -> Dict[str, Any]:
        """Check pending queue status."""
        try:
            with get_db() as db:
                # Count pending posts
                pending_count = db.execute(text("""
                    SELECT COUNT(*) 
                    FROM posting_queue 
                    WHERE status = 'pending'
                """)).scalar()
                
                # Count overdue posts
                overdue_count = db.execute(text("""
                    SELECT COUNT(*) 
                    FROM posting_queue 
                    WHERE status = 'pending'
                      AND scheduled_for < NOW() - INTERVAL '1 hour'
                """)).scalar()
                
                status = 'healthy'
                if overdue_count > 5:
                    status = 'warning'
                
                return {
                    'status': status,
                    'message': f'{pending_count} pending, {overdue_count} overdue',
                    'pending': pending_count,
                    'overdue': overdue_count
                }
                    
        except Exception as e:
            logger.error(f"Pending queue check failed: {str(e)}")
            return {
                'status': 'unhealthy',
                'message': f'Error checking queue: {str(e)}'
            }
    
    def _check_failed_posts(self) -> Dict[str, Any]:
        """Check for failed posts that need attention."""
        try:
            with get_db() as db:
                # Count permanently failed posts (max retries exceeded)
                failed_count = db.execute(text("""
                    SELECT COUNT(*) 
                    FROM posting_queue 
                    WHERE status = 'failed'
                      AND retry_count >= max_retries
                      AND created_at > NOW() - INTERVAL '7 days'
                """)).scalar()
                
                status = 'healthy'
                if failed_count > 0:
                    status = 'warning'
                if failed_count > 10:
                    status = 'unhealthy'
                
                return {
                    'status': status,
                    'message': f'{failed_count} permanently failed posts in last 7 days',
                    'count': failed_count
                }
                    
        except Exception as e:
            logger.error(f"Failed posts check failed: {str(e)}")
            return {
                'status': 'unhealthy',
                'message': f'Error checking failed posts: {str(e)}'
            }
```

### src/api.py (Optional FastAPI Health Endpoint)

```python
"""Optional FastAPI server for health checks and monitoring.

This is useful for cloud deployments (Railway, Render) that need
an HTTP endpoint to check if the service is running.
"""
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.services.health_check import HealthCheckService
from src.utils.logger import logger

app = FastAPI(title="Storyline AI Health API")

health_service = HealthCheckService()


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Storyline AI - Instagram Story Automation"}


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        200 if healthy, 503 if unhealthy
    """
    try:
        result = health_service.check_all()
        
        status_code = 200 if result['status'] == 'healthy' else 503
        
        return JSONResponse(
            content=result,
            status_code=status_code
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JSONResponse(
            content={
                'status': 'unhealthy',
                'message': f'Health check error: {str(e)}'
            },
            status_code=503
        )


@app.get("/health/simple")
async def simple_health_check():
    """
    Simple health check (just returns 200 OK).
    
    Useful for basic uptime monitoring.
    """
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### CLI Health Check Command

```python
# cli/commands/health.py
"""Health check CLI command."""
import click
from rich.console import Console
from rich.table import Table

from src.services.health_check import HealthCheckService

console = Console()


@click.command()
def check_health():
    """Check system health status."""
    console.print("[bold blue]Running health checks...[/bold blue]\n")
    
    service = HealthCheckService()
    result = service.check_all()
    
    # Overall status
    if result['status'] == 'healthy':
        console.print("[bold green]✓ System Status: HEALTHY[/bold green]\n")
    else:
        console.print("[bold yellow]⚠ System Status: DEGRADED[/bold yellow]\n")
    
    # Create table
    table = Table(title="Health Check Results")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="magenta")
    table.add_column("Details", style="white")
    
    for component, check in result['checks'].items():
        status = check['status']
        
        # Color code status
        if status == 'healthy':
            status_display = "[green]✓ Healthy[/green]"
        elif status == 'warning':
            status_display = "[yellow]⚠ Warning[/yellow]"
        else:
            status_display = "[red]✗ Unhealthy[/red]"
        
        table.add_row(
            component.replace('_', ' ').title(),
            status_display,
            check.get('message', '')
        )
    
    console.print(table)
```

### Usage

```bash
# CLI health check
storyline-cli check-health

# HTTP health check (if running FastAPI server)
curl http://localhost:8000/health

# Simple uptime check
curl http://localhost:8000/health/simple
```

---

## User Management

### Telegram-Native User Discovery

Users are automatically discovered and created when they interact with the Telegram bot. No manual registration needed!

**How It Works**:

1. User clicks a button in Telegram (e.g., "Mark Posted")
2. System checks if user exists in database
3. If not, creates user record from Telegram data
4. Tracks user's action in `posting_history`

**User Record**:
```python
# Automatically populated from Telegram
user = User(
    telegram_user_id=12345678,
    telegram_username="john_doe",
    telegram_first_name="John",
    telegram_last_name="Doe",
    team_name="Marketing Team",  # Set via CLI
    role="member",  # Default, promote via CLI
    is_active=True
)
```

---

### CLI Commands for User Management

**`storyline-cli list-users`**

List all users discovered from Telegram interactions.

```bash
storyline-cli list-users

# Output:
👥 Team Users

                    User List (3 users)                    
┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Username         ┃ Name        ┃ Role     ┃ Posts      ┃ Last Seen  ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ @sarah_m         │ Sarah M.    │ admin    │ 45 posts   │ 2 hrs ago  │
│ @john_doe        │ John Doe    │ member   │ 23 posts   │ 1 day ago  │
│ @alex_k          │ Alex K.     │ member   │ 12 posts   │ 3 days ago │
└──────────────────┴─────────────┴──────────┴────────────┴────────────┘

Total: 3 users | Active: 3 | Admins: 1
```

**Implementation**:

```python
# cli/commands/users.py
import click
from rich.console import Console
from rich.table import Table

from src.repositories.user_repository import UserRepository

console = Console()


@click.command()
@click.option('--team', default=None, help='Filter by team name')
@click.option('--role', default=None, help='Filter by role (admin, member)')
def list_users(team, role):
    """List all users discovered from Telegram."""
    user_repo = UserRepository()
    
    users = user_repo.get_all(team_name=team, role=role)
    
    console.print(f"\n[bold blue]👥 Team Users[/bold blue]\n")
    
    table = Table(title=f"User List ({len(users)} users)")
    table.add_column("Username", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Role", style="magenta")
    table.add_column("Posts", style="green")
    table.add_column("Last Seen", style="yellow")
    
    for user in users:
        username = f"@{user.telegram_username}" if user.telegram_username else "N/A"
        full_name = f"{user.telegram_first_name or ''} {user.telegram_last_name or ''}".strip()
        role_display = f"[bold]{user.role}[/bold]" if user.role == 'admin' else user.role
        
        # Calculate time since last seen
        if user.last_seen_at:
            time_diff = datetime.utcnow() - user.last_seen_at
            if time_diff.days > 0:
                last_seen = f"{time_diff.days} day{'s' if time_diff.days > 1 else ''} ago"
            elif time_diff.seconds > 3600:
                hours = time_diff.seconds // 3600
                last_seen = f"{hours} hr{'s' if hours > 1 else ''} ago"
            else:
                minutes = time_diff.seconds // 60
                last_seen = f"{minutes} min{'s' if minutes > 1 else ''} ago"
        else:
            last_seen = "Never"
        
        table.add_row(
            username,
            full_name or "N/A",
            role_display,
            f"{user.total_posts} posts",
            last_seen
        )
    
    console.print(table)
    
    # Summary
    admin_count = sum(1 for u in users if u.role == 'admin')
    active_count = sum(1 for u in users if u.is_active)
    
    console.print(f"\nTotal: {len(users)} users | Active: {active_count} | Admins: {admin_count}\n")
```

---

**`storyline-cli promote-user`**

Promote a user to admin role.

```bash
storyline-cli promote-user --username sarah_m --role admin

# Output:
✓ User @sarah_m promoted to admin
```

**Implementation**:

```python
@click.command()
@click.option('--username', required=True, help='Telegram username (without @)')
@click.option('--role', type=click.Choice(['admin', 'member']), required=True, help='New role')
def promote_user(username, role):
    """Change user role."""
    user_repo = UserRepository()
    
    user = user_repo.get_by_telegram_username(username)
    
    if not user:
        console.print(f"[red]✗ User @{username} not found[/red]")
        console.print("[yellow]Users must interact with the bot first to be discovered[/yellow]")
        return
    
    user_repo.update_role(user.id, role)
    
    console.print(f"[green]✓ User @{username} promoted to {role}[/green]")
```

---

**`storyline-cli deactivate-user`**

Deactivate a user (prevent them from posting).

```bash
storyline-cli deactivate-user --username john_doe

# Output:
✓ User @john_doe deactivated
```

**Implementation**:

```python
@click.command()
@click.option('--username', required=True, help='Telegram username (without @)')
def deactivate_user(username):
    """Deactivate a user."""
    user_repo = UserRepository()
    
    user = user_repo.get_by_telegram_username(username)
    
    if not user:
        console.print(f"[red]✗ User @{username} not found[/red]")
        return
    
    user_repo.deactivate(user.id)
    
    console.print(f"[green]✓ User @{username} deactivated[/green]")
    console.print("[yellow]They can no longer mark posts as completed[/yellow]")
```

---

**`storyline-cli user-stats`**

Show detailed statistics for a user.

```bash
storyline-cli user-stats --username sarah_m

# Output:
👤 User Statistics: @sarah_m

Name:              Sarah Martinez
Role:              admin
Team:              Marketing Team
Status:            Active
First Seen:        2024-01-01 10:00:00 UTC
Last Seen:         2 hours ago

📊 Posting Activity

Total Posts:       45
Successful:        43 (95.6%)
Failed:            2 (4.4%)
This Week:         8 posts
This Month:        32 posts

🏆 Top Tags
  • product: 25 posts
  • meme: 15 posts
  • announcement: 5 posts

⏱️ Most Active Times
  • 9 AM - 11 AM: 15 posts
  • 2 PM - 4 PM: 18 posts
  • 6 PM - 8 PM: 12 posts
```

**Implementation**:

```python
@click.command()
@click.option('--username', required=True, help='Telegram username (without @)')
def user_stats(username):
    """Show detailed user statistics."""
    user_repo = UserRepository()
    history_repo = HistoryRepository()
    
    user = user_repo.get_by_telegram_username(username)
    
    if not user:
        console.print(f"[red]✗ User @{username} not found[/red]")
        return
    
    # Get user's posting history
    stats = history_repo.get_user_stats(user.id)
    
    console.print(f"\n[bold blue]👤 User Statistics: @{username}[/bold blue]\n")
    
    # Basic info
    console.print(f"Name:              {user.telegram_first_name} {user.telegram_last_name}")
    console.print(f"Role:              [bold]{user.role}[/bold]")
    console.print(f"Team:              {user.team_name or 'Not set'}")
    console.print(f"Status:            {'[green]Active[/green]' if user.is_active else '[red]Inactive[/red]'}")
    console.print(f"First Seen:        {user.first_seen_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    time_diff = datetime.utcnow() - user.last_seen_at
    if time_diff.days > 0:
        last_seen = f"{time_diff.days} day{'s' if time_diff.days > 1 else ''} ago"
    elif time_diff.seconds > 3600:
        hours = time_diff.seconds // 3600
        last_seen = f"{hours} hour{'s' if hours > 1 else ''} ago"
    else:
        minutes = time_diff.seconds // 60
        last_seen = f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    
    console.print(f"Last Seen:         {last_seen}\n")
    
    # Posting activity
    console.print("[bold]📊 Posting Activity[/bold]\n")
    console.print(f"Total Posts:       {stats['total_posts']}")
    console.print(f"Successful:        {stats['successful_posts']} ({stats['success_rate']:.1f}%)")
    console.print(f"Failed:            {stats['failed_posts']} ({100 - stats['success_rate']:.1f}%)")
    console.print(f"This Week:         {stats['posts_this_week']} posts")
    console.print(f"This Month:        {stats['posts_this_month']} posts\n")
    
    # Top tags
    if stats['top_tags']:
        console.print("[bold]🏆 Top Tags[/bold]")
        for tag, count in stats['top_tags'][:5]:
            console.print(f"  • {tag}: {count} posts")
    
    console.print()
```

---

**`storyline-cli list-service-runs`**

View recent service executions (for debugging and monitoring).

```bash
storyline-cli list-service-runs --service PostingService --limit 10

# Output:
🔧 Service Execution Log

                    Recent Service Runs                    
┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┓
┃ Service              ┃ Method           ┃ Status    ┃ Duration ┃ Started  ┃
┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━┩
│ PostingService       │ process_pending  │ ✓ Success │ 1,234 ms │ 2 min ago│
│ MediaIngestionService│ scan_directory   │ ✓ Success │ 5,678 ms │ 1 hr ago │
│ PostingService       │ process_pending  │ ✗ Failed  │ 234 ms   │ 2 hrs ago│
│ SchedulerService     │ create_schedule  │ ✓ Success │ 890 ms   │ 3 hrs ago│
└──────────────────────┴──────────────────┴───────────┴──────────┴──────────┘

Total: 10 runs | Success: 8 | Failed: 2
```

**Implementation**:

```python
# cli/commands/service_runs.py
@click.command()
@click.option('--service', default=None, help='Filter by service name')
@click.option('--status', type=click.Choice(['running', 'completed', 'failed']), help='Filter by status')
@click.option('--limit', default=20, help='Number of runs to show')
def list_runs(service, status, limit):
    """List recent service executions."""
    service_run_repo = ServiceRunRepository()
    
    runs = service_run_repo.get_recent_runs(
        service_name=service,
        status=status,
        limit=limit
    )
    
    console.print(f"\n[bold blue]🔧 Service Execution Log[/bold blue]\n")
    
    table = Table(title="Recent Service Runs")
    table.add_column("Service", style="cyan")
    table.add_column("Method", style="white")
    table.add_column("Status", style="magenta")
    table.add_column("Duration", style="yellow")
    table.add_column("Started", style="green")
    
    for run in runs:
        # Status display
        if run.status == 'completed' and run.success:
            status_display = "[green]✓ Success[/green]"
        elif run.status == 'failed':
            status_display = "[red]✗ Failed[/red]"
        else:
            status_display = "[yellow]⏳ Running[/yellow]"
        
        # Duration
        duration = f"{run.duration_ms:,} ms" if run.duration_ms else "N/A"
        
        # Time ago
        time_diff = datetime.utcnow() - run.started_at
        if time_diff.days > 0:
            time_ago = f"{time_diff.days}d ago"
        elif time_diff.seconds > 3600:
            time_ago = f"{time_diff.seconds // 3600}h ago"
        else:
            time_ago = f"{time_diff.seconds // 60}m ago"
        
        table.add_row(
            run.service_name,
            run.method_name,
            status_display,
            duration,
            time_ago
        )
    
    console.print(table)
    
    # Summary
    success_count = sum(1 for r in runs if r.success)
    failed_count = sum(1 for r in runs if r.status == 'failed')
    
    console.print(f"\nTotal: {len(runs)} runs | Success: {success_count} | Failed: {failed_count}\n")
```

---

### src/services/instagram_api.py (With Rate Limiting)

```python
"""Instagram Graph API service with rate limiting.

Rate Limits (as of 2024):
- 200 calls per hour per user
- 4800 calls per day per app

Strategy:
- Token bucket algorithm
- Sliding window for hourly limit
- Automatic backoff on rate limit errors
"""
import time
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from collections import deque
from threading import Lock

from src.config.settings import settings
from src.utils.logger import logger


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""
    pass


class RateLimiter:
    """Token bucket rate limiter for Instagram API."""
    
    def __init__(self, max_calls_per_hour: int = 200):
        """
        Initialize rate limiter.
        
        Args:
            max_calls_per_hour: Maximum API calls per hour
        """
        self.max_calls = max_calls_per_hour
        self.calls: deque = deque()  # Timestamps of recent calls
        self.lock = Lock()
    
    def wait_if_needed(self) -> None:
        """
        Wait if rate limit would be exceeded.
        
        Uses sliding window: only allow max_calls in last 60 minutes.
        """
        with self.lock:
            now = datetime.utcnow()
            cutoff = now - timedelta(hours=1)
            
            # Remove calls older than 1 hour
            while self.calls and self.calls[0] < cutoff:
                self.calls.popleft()
            
            # Check if we're at limit
            if len(self.calls) >= self.max_calls:
                # Calculate wait time
                oldest_call = self.calls[0]
                wait_until = oldest_call + timedelta(hours=1)
                wait_seconds = (wait_until - now).total_seconds()
                
                if wait_seconds > 0:
                    logger.warning(
                        f"Rate limit reached ({self.max_calls} calls/hour). "
                        f"Waiting {wait_seconds:.0f} seconds..."
                    )
                    time.sleep(wait_seconds + 1)  # +1 for safety margin
                    
                    # Refresh after waiting
                    now = datetime.utcnow()
                    cutoff = now - timedelta(hours=1)
                    while self.calls and self.calls[0] < cutoff:
                        self.calls.popleft()
            
            # Record this call
            self.calls.append(now)
            
            logger.debug(f"Rate limiter: {len(self.calls)}/{self.max_calls} calls in last hour")


class InstagramAPIService:
    """Instagram Graph API service with rate limiting."""
    
    def __init__(self):
        """Initialize Instagram API service."""
        self.base_url = settings.GRAPH_API_BASE_URL
        self.account_id = settings.INSTAGRAM_ACCOUNT_ID
        self.access_token = settings.ACCESS_TOKEN
        self.rate_limiter = RateLimiter(max_calls_per_hour=180)  # Conservative limit
        
    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Make API request with rate limiting and retry logic.
        
        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint
            params: Query parameters
            data: Request body data
            max_retries: Maximum retry attempts
            
        Returns:
            API response as dict
            
        Raises:
            RateLimitExceeded: If rate limit is exceeded
            requests.HTTPError: If request fails
        """
        # Wait if rate limit would be exceeded
        self.rate_limiter.wait_if_needed()
        
        url = f"{self.base_url}/{endpoint}"
        
        # Add access token to params
        if params is None:
            params = {}
        params['access_token'] = self.access_token
        
        # Retry logic with exponential backoff
        for attempt in range(max_retries):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    params=params,
                    json=data,
                    timeout=30
                )
                
                # Check for rate limit error
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logger.warning(f"Rate limit hit (429). Waiting {retry_after} seconds...")
                    time.sleep(retry_after)
                    continue
                
                # Check for other errors
                response.raise_for_status()
                
                return response.json()
                
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"Request timeout. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise
                    
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Request failed: {str(e)}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise
        
        raise Exception(f"Failed after {max_retries} attempts")
    
    def create_story(self, image_url: str) -> Dict[str, Any]:
        """
        Create Instagram Story.
        
        Args:
            image_url: Publicly accessible HTTPS URL of image
            
        Returns:
            Instagram media response with id and permalink
        """
        logger.info(f"Creating Instagram Story from {image_url}")
        
        # Step 1: Create media container
        container_response = self._make_request(
            method='POST',
            endpoint=f"{self.account_id}/media",
            params={
                'image_url': image_url,
                'media_type': 'STORIES'
            }
        )
        
        container_id = container_response.get('id')
        logger.info(f"Created media container: {container_id}")
        
        # Step 2: Publish media container
        publish_response = self._make_request(
            method='POST',
            endpoint=f"{self.account_id}/media_publish",
            params={
                'creation_id': container_id
            }
        )
        
        media_id = publish_response.get('id')
        logger.info(f"Published story: {media_id}")
        
        # Step 3: Get media details (optional - for permalink)
        try:
            media_details = self._make_request(
                method='GET',
                endpoint=media_id,
                params={'fields': 'id,permalink'}
            )
            return media_details
        except Exception as e:
            logger.warning(f"Failed to get media details: {str(e)}")
            return {'id': media_id}
    
    def verify_credentials(self) -> bool:
        """
        Verify Instagram API credentials.
        
        Returns:
            True if credentials are valid
        """
        try:
            response = self._make_request(
                method='GET',
                endpoint=self.account_id,
                params={'fields': 'id,username'}
            )
            
            logger.info(f"Credentials verified for @{response.get('username')}")
            return True
            
        except Exception as e:
            logger.error(f"Credential verification failed: {str(e)}")
            return False
    
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """
        Get current rate limit status.
        
        Returns:
            Dict with calls_made and calls_remaining
        """
        with self.rate_limiter.lock:
            now = datetime.utcnow()
            cutoff = now - timedelta(hours=1)
            
            # Clean old calls
            while self.rate_limiter.calls and self.rate_limiter.calls[0] < cutoff:
                self.rate_limiter.calls.popleft()
            
            calls_made = len(self.rate_limiter.calls)
            calls_remaining = self.rate_limiter.max_calls - calls_made
            
            return {
                'calls_made_last_hour': calls_made,
                'calls_remaining': calls_remaining,
                'max_calls_per_hour': self.rate_limiter.max_calls,
                'oldest_call': self.rate_limiter.calls[0].isoformat() if self.rate_limiter.calls else None
            }
```

### src/repositories/queue_repository.py (Key Methods for Error Handling)

```python
"""Queue repository with retry logic support."""
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from src.models.posting_queue import PostingQueue
from src.utils.logger import logger


class QueueRepository:
    """Repository for posting queue operations."""
    
    def __init__(self, db: Session):
        """Initialize repository."""
        self.db = db
    
    def get_posts_due_for_processing(self) -> List[PostingQueue]:
        """
        Get all posts that are due for processing.
        
        Includes:
        - Pending posts with scheduled_for <= now
        - Failed posts with next_retry_at <= now
        
        Returns:
            List of queue items ready to process
        """
        now = datetime.utcnow()
        
        return self.db.query(PostingQueue).filter(
            or_(
                # Regular pending posts that are due
                and_(
                    PostingQueue.status == 'pending',
                    PostingQueue.scheduled_for <= now,
                    PostingQueue.next_retry_at.is_(None)
                ),
                # Failed posts ready for retry
                and_(
                    PostingQueue.status == 'failed',
                    PostingQueue.next_retry_at <= now,
                    PostingQueue.retry_count < PostingQueue.max_retries
                )
            )
        ).all()
    
    def schedule_retry(
        self,
        queue_item_id: str,
        next_retry_at: datetime,
        retry_count: int,
        error_message: str
    ) -> bool:
        """
        Schedule a retry for a failed post.
        
        Args:
            queue_item_id: Queue item UUID
            next_retry_at: When to retry
            retry_count: Current retry count
            error_message: Error that caused the failure
            
        Returns:
            True if successful
        """
        try:
            queue_item = self.db.query(PostingQueue).filter(
                PostingQueue.id == queue_item_id
            ).first()
            
            if queue_item:
                queue_item.status = 'failed'  # Keep as failed until retry succeeds
                queue_item.next_retry_at = next_retry_at
                queue_item.retry_count = retry_count
                queue_item.last_error = error_message
                
                self.db.commit()
                logger.info(f"Scheduled retry for queue item {queue_item_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error scheduling retry: {str(e)}")
            self.db.rollback()
            return False
    
    def mark_as_failed(self, queue_item_id: str, error_message: str) -> bool:
        """
        Mark post as permanently failed (no more retries).
        
        Args:
            queue_item_id: Queue item UUID
            error_message: Final error message
            
        Returns:
            True if successful
        """
        try:
            queue_item = self.db.query(PostingQueue).filter(
                PostingQueue.id == queue_item_id
            ).first()
            
            if queue_item:
                queue_item.status = 'failed'
                queue_item.error_message = error_message
                queue_item.last_error = error_message
                queue_item.next_retry_at = None  # No more retries
                queue_item.completed_at = datetime.utcnow()
                
                self.db.commit()
                logger.info(f"Marked queue item {queue_item_id} as permanently failed")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error marking as failed: {str(e)}")
            self.db.rollback()
            return False
    
    def mark_as_posted(
        self,
        queue_item_id: str,
        telegram_user_id: int,
        telegram_username: str
    ) -> bool:
        """
        Mark post as completed (atomic operation to prevent race conditions).
        
        Args:
            queue_item_id: Queue item UUID
            telegram_user_id: Telegram user ID who completed it
            telegram_username: Telegram username
            
        Returns:
            True if successfully claimed and marked, False if already claimed
        """
        try:
            # Atomic update - only succeeds if status is still 'pending'
            result = self.db.query(PostingQueue).filter(
                and_(
                    PostingQueue.id == queue_item_id,
                    PostingQueue.status == 'pending'  # Only if still pending
                )
            ).update({
                'status': 'posted',
                'completed_by_user': telegram_username,
                'completed_by_user_id': telegram_user_id,
                'completed_at': datetime.utcnow(),
                'posted_at': datetime.utcnow()
            }, synchronize_session=False)
            
            self.db.commit()
            
            if result > 0:
                logger.info(
                    f"Queue item {queue_item_id} marked as posted by @{telegram_username}"
                )
                return True
            else:
                logger.warning(
                    f"Queue item {queue_item_id} already processed by someone else"
                )
                return False
                
        except Exception as e:
            logger.error(f"Error marking as posted: {str(e)}")
            self.db.rollback()
            return False
    
    def mark_as_skipped(
        self,
        queue_item_id: str,
        telegram_user_id: int,
        telegram_username: str
    ) -> bool:
        """
        Mark post as skipped (atomic operation).
        
        Args:
            queue_item_id: Queue item UUID
            telegram_user_id: Telegram user ID who skipped it
            telegram_username: Telegram username
            
        Returns:
            True if successfully skipped, False if already processed
        """
        try:
            result = self.db.query(PostingQueue).filter(
                and_(
                    PostingQueue.id == queue_item_id,
                    PostingQueue.status == 'pending'
                )
            ).update({
                'status': 'skipped',
                'skipped': True,
                'completed_by_user': telegram_username,
                'completed_by_user_id': telegram_user_id,
                'completed_at': datetime.utcnow()
            }, synchronize_session=False)
            
            self.db.commit()
            
            return result > 0
                
        except Exception as e:
            logger.error(f"Error marking as skipped: {str(e)}")
            self.db.rollback()
            return False
```

---

## Part E: Deployment & Usage

### Installation on Raspberry Pi

```bash
# Clone repository
cd ~
git clone https://github.com/yourusername/instagram-story-automation.git
cd instagram-story-automation

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install CLI
pip install -e .

# Verify installation
storyline-cli --help
```

### Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit configuration
nano .env

# PHASE 1 (Telegram-Only) - Fill in these required values:
# - Database credentials (DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD)
# - Telegram bot token (TELEGRAM_BOT_TOKEN)
# - Telegram channel ID (TELEGRAM_CHANNEL_ID)
# - Media path (MEDIA_BASE_PATH)
# - Keep ENABLE_INSTAGRAM_API=false

# PHASE 2 (Optional - Add Later):
# - Set ENABLE_INSTAGRAM_API=true
# - Add Instagram API tokens (INSTAGRAM_ACCOUNT_ID, ACCESS_TOKEN)
# - Add Cloudinary credentials (CLOUDINARY_CLOUD_NAME, API_KEY, API_SECRET)
```

### Database Setup

#### Local Development (Your Machine)

```bash
# Create PostgreSQL database
sudo -u postgres psql -c "CREATE DATABASE storyline_ai;"
sudo -u postgres psql -c "CREATE USER storyline_user WITH PASSWORD 'your_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE storyline_ai TO storyline_user;"

# Run migrations
psql -U storyline_user -d storyline_ai -f scripts/setup_database.sql

# Configure .env for local development
cat > .env << EOF
# Local PostgreSQL
DATABASE_URL=postgresql://storyline_user:your_password@localhost:5432/storyline_ai

# Or use individual components:
# DB_HOST=localhost
# DB_PORT=5432
# DB_NAME=storyline_ai
# DB_USER=storyline_user
# DB_PASSWORD=your_password
EOF
```

#### Raspberry Pi (Production)

```bash
# Same setup as local development
sudo -u postgres psql -c "CREATE DATABASE storyline_ai;"
sudo -u postgres psql -c "CREATE USER storyline_user WITH PASSWORD 'your_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE storyline_ai TO storyline_user;"

# Run migrations
psql -U storyline_user -d storyline_ai -f scripts/setup_database.sql

# Configure .env for Raspberry Pi
DATABASE_URL=postgresql://storyline_user:your_password@localhost:5432/storyline_ai
```

#### Neon (Cloud - Optional)

```bash
# Create database in Neon dashboard
# Copy connection string from Neon

# Configure .env for Neon
DATABASE_URL=postgresql://user:pass@ep-cool-name.us-east-2.aws.neon.tech/storyline_ai?sslmode=require

# Run migrations (from your local machine)
psql "$DATABASE_URL" -f scripts/setup_database.sql
```

#### Test Database (Automated)

```bash
# Tests automatically create/destroy isolated databases
# No manual setup needed!

# Optional: Configure test database credentials
export TEST_DB_HOST=localhost
export TEST_DB_PORT=5432
export TEST_DB_USER=postgres
export TEST_DB_PASSWORD=postgres

# Run tests (creates storyline_ai_test_<random> database)
pytest

# Test database is automatically cleaned up after tests
```

### CLI Usage

**Phase 1 Commands** (Telegram-Only):
```bash
# Check system health
storyline-cli check-health

# Test Telegram bot
storyline-cli test-telegram

# Index media files
storyline-cli index-media

# List indexed media
storyline-cli list-media

# Create posting schedule
storyline-cli create-schedule

# Process queue manually (sends Telegram notifications)
storyline-cli process-queue

# Start Telegram bot (foreground - for testing)
storyline-cli start-telegram
```

**Phase 2 Commands** (After Enabling Automation):
```bash
# Test Instagram API (only works if ENABLE_INSTAGRAM_API=true)
storyline-cli test-api

# All Phase 1 commands still work
# process-queue will now auto-post simple stories
```

### Understanding the Feature Flag

**How the System Decides What to Do**:

```python
# In src/services/posting.py

if settings.ENABLE_INSTAGRAM_API and not media_item.requires_interaction:
    # Route to automated posting (Phase 2 only)
    await self._post_automated(queue_item, media_item)
else:
    # Route to Telegram (Phase 1, or Phase 2 for interactive stories)
    await self._post_via_telegram(queue_item, media_item)
```

**Phase 1 Behavior** (`ENABLE_INSTAGRAM_API=false`):
- ✅ All stories → Telegram (100% manual)
- ✅ `requires_interaction=true` → Telegram
- ✅ `requires_interaction=false` → Telegram
- ❌ No Instagram API calls
- ❌ No Cloudinary usage

**Phase 2 Behavior** (`ENABLE_INSTAGRAM_API=true`):
- ✅ `requires_interaction=false` → Instagram API (automated)
- ✅ `requires_interaction=true` → Telegram (manual)
- ✅ Uses Cloudinary for automated posts
- ✅ Best of both worlds

**Example Scenarios**:

| Story Type | `requires_interaction` | Phase 1 | Phase 2 |
|------------|------------------------|---------|---------|
| Meme (no link) | `false` | Telegram | Instagram API ✨ |
| Quote (no link) | `false` | Telegram | Instagram API ✨ |
| Product + link | `true` | Telegram | Telegram |
| Poll story | `true` | Telegram | Telegram |
| Location tag | `true` | Telegram | Telegram |

---

### Dry Run Mode

**Purpose**: Test the entire system without actually posting to Instagram or sending Telegram notifications.

**How to Enable**:
```bash
# Set in .env file
DRY_RUN_MODE=true

# Or set as environment variable
export DRY_RUN_MODE=true
python -m src.main
```

**What Happens in Dry Run Mode**:
- ✅ Media indexing works normally
- ✅ Schedule creation works normally
- ✅ Database operations work normally
- ✅ All business logic executes
- ❌ No actual Instagram API calls
- ❌ No actual Telegram messages sent
- ✅ Detailed logging of what WOULD happen

**Example Output**:
```
[INFO] Auto-posting meme1.jpg
[INFO] [DRY RUN] Would post meme1.jpg to Instagram
[INFO] [DRY RUN] File: /home/pi/media/stories/meme1.jpg
[INFO] [DRY RUN] Tags: ['meme', 'funny']
[INFO] [DRY RUN] Successfully simulated post

[INFO] Sending Telegram notification for product1.jpg
[INFO] [DRY RUN] Would send Telegram notification for product1.jpg
[INFO] [DRY RUN] Title: Cool Tshirt
[INFO] [DRY RUN] Link: https://shop.com/products/tshirt
[INFO] [DRY RUN] Channel: -1001234567890
[INFO] [DRY RUN] Successfully simulated Telegram notification
```

**Use Cases**:
- Testing configuration before going live
- Validating media indexing and scheduling logic
- Debugging issues without affecting production
- Demonstrating the system to stakeholders
- Running integration tests

### Running the Full System

**Architecture Note**: The system runs as a **single process** with:
- APScheduler for automated jobs (media scanning, scheduling, posting)
- Telegram bot for manual workflow (notifications, callbacks)
- Shared asyncio event loop

#### Option 1: Foreground (for testing)

```bash
# Run everything in one process
python -m src.main

# Output:
# [INFO] Starting Storyline AI - Instagram Story Automation System
# [INFO] Configuration validated successfully
# [INFO] Telegram bot started successfully
# [INFO] Scheduler started. Press Ctrl+C to exit.
```

#### Option 2: Systemd Service (production)

Create `/etc/systemd/system/storyline-ai.service`:

```ini
[Unit]
Description=Storyline AI - Instagram Story Automation Service
After=network.target postgresql.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/storyline-ai
Environment="PATH=/home/pi/storyline-ai/venv/bin"
ExecStart=/home/pi/storyline-ai/venv/bin/python3 -m src.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable storyline-ai
sudo systemctl start storyline-ai
sudo systemctl status storyline-ai

# View logs
sudo journalctl -u storyline-ai -f
```

---

## Part F: Team Onboarding Guide

### For Team Members

**Step 1: Join Telegram Channel**
1. Team admin adds you to the private Telegram channel
2. You'll see posting notifications appear in the channel

**Step 2: When a Notification Arrives**

```
📸 MERCH STORY #47
━━━━━━━━━━━━━━━━━━━━━
🎽 Product: "Dank Meme" Tshirt
🔗 Link: https://shop.com/products/tshirt
⏰ Scheduled: Jan 3, 2026 2:30 PM

[📋 Copy Link] [✅ Mark Posted] [⏭️ Skip]
```

**Step 3: Post to Instagram** (15-30 seconds)
1. Tap the image in Telegram → Save to camera roll
2. Tap "📋 Copy Link" button to copy URL (if applicable)
3. Open Instagram app
4. Create Story → Select saved image
5. Add interactive elements:
   - Link sticker (paste URL)
   - Poll sticker
   - Question sticker
   - Location tag
   - etc.
6. Post Story

**Step 4: Mark as Complete**
1. Return to Telegram
2. Tap "✅ Mark Posted" button
3. Done! The bot tracks your completion

**Step 5: Bot Commands** (optional)
- `/pending` - See upcoming posts
- `/posted` - See what's been posted
- `/stats` - View team statistics
- `/help` - Show help message

---

## Timezone Handling

### All Times are UTC

**Design Decision**: The system uses **UTC (Coordinated Universal Time)** for all timestamps and scheduling.

**Why UTC?**
- ✅ No daylight saving time complications
- ✅ Consistent across server migrations (local → cloud)
- ✅ Standard practice for distributed systems
- ✅ PostgreSQL `TIMESTAMP` columns store UTC
- ✅ Instagram API uses UTC
- ✅ Simplifies multi-timezone team collaboration

### Database Timestamps

All timestamp columns use UTC:
```sql
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- UTC
updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- UTC
posted_at TIMESTAMP                             -- UTC
scheduled_for TIMESTAMP                         -- UTC
```

### Scheduling Configuration

`POSTING_HOURS_START` and `POSTING_HOURS_END` are interpreted as **UTC hours**:

```bash
# Example: Post between 9 AM and 9 PM UTC
POSTING_HOURS_START=9
POSTING_HOURS_END=21
```

### Converting Local Time to UTC

**If you want to post during specific local hours**, convert to UTC:

```python
# Example: Post between 9 AM - 9 PM EST (UTC-5)
# 9 AM EST = 2 PM UTC (14:00)
# 9 PM EST = 2 AM UTC (02:00 next day)

POSTING_HOURS_START=14
POSTING_HOURS_END=2  # Note: wraps to next day
```

**For PST (UTC-8)**:
```python
# 9 AM PST = 5 PM UTC (17:00)
# 9 PM PST = 5 AM UTC (05:00 next day)

POSTING_HOURS_START=17
POSTING_HOURS_END=5
```

### Scheduler Logic

The scheduler handles UTC correctly:

```python
# src/services/scheduler.py
from datetime import datetime

def create_schedule():
    """Create schedule using UTC times."""
    now_utc = datetime.utcnow()  # Always use UTC
    
    # Schedule between configured UTC hours
    start_hour = settings.POSTING_HOURS_START  # UTC hour
    end_hour = settings.POSTING_HOURS_END      # UTC hour
    
    # Generate random times within UTC hour range
    scheduled_time = generate_random_time_utc(start_hour, end_hour)
```

### Displaying Times to Users

When showing times in logs or UI, always indicate UTC:

```python
logger.info(f"Scheduled for {scheduled_time.isoformat()} UTC")
logger.info(f"Posted at {posted_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
```

### Telegram Notifications

Telegram messages show UTC times:

```
📸 STORY NOTIFICATION
━━━━━━━━━━━━━━━━━━━━━
⏰ Scheduled: Jan 3, 2026 14:30 UTC
```

### Future Enhancement: Display Timezone

If you want to show local times to users, add a display timezone setting:

```python
# Future feature (not in current plan)
from zoneinfo import ZoneInfo

DISPLAY_TIMEZONE = "America/New_York"

def format_time_for_display(utc_time):
    """Convert UTC to display timezone."""
    local_time = utc_time.replace(tzinfo=ZoneInfo('UTC')).astimezone(
        ZoneInfo(DISPLAY_TIMEZONE)
    )
    return local_time.strftime('%Y-%m-%d %I:%M %p %Z')
```

But for now: **Everything is UTC, everywhere, always.**

---

## Part G: Testing Strategy

### Testing Philosophy

**Test Structure**: Mirror `src/` directory structure in `tests/`
- `src/services/posting.py` → `tests/src/services/test_posting.py`
- `src/repositories/queue_repository.py` → `tests/src/repositories/test_queue_repository.py`
- Makes tests easy to find and maintain

**Test Levels**:
1. **Unit Tests**: Test individual functions/methods in isolation
2. **Integration Tests**: Test multiple components working together
3. **End-to-End Tests**: Test complete workflows

### Test Configuration

**tests/conftest.py**
```python
"""Pytest configuration and shared fixtures."""
import pytest
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from pathlib import Path
import tempfile
import uuid

from src.config.database import Base
from src.config.settings import Settings


# Test database configuration
TEST_DB_HOST = os.getenv("TEST_DB_HOST", "localhost")
TEST_DB_PORT = os.getenv("TEST_DB_PORT", "5432")
TEST_DB_USER = os.getenv("TEST_DB_USER", "postgres")
TEST_DB_PASSWORD = os.getenv("TEST_DB_PASSWORD", "postgres")


def get_test_database_url(db_name: str) -> str:
    """
    Get test database URL.
    
    Isolated from dev/production databases.
    Each test run gets a unique database name.
    """
    return f"postgresql://{TEST_DB_USER}:{TEST_DB_PASSWORD}@{TEST_DB_HOST}:{TEST_DB_PORT}/{db_name}"


@pytest.fixture(scope="session")
def test_db_name():
    """Generate unique database name for this test session."""
    # Unique name per test run to avoid conflicts
    return f"storyline_ai_test_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="session")
def postgres_engine(test_db_name):
    """
    Create test database (session-scoped).
    
    Creates a fresh PostgreSQL database for the entire test session.
    Dropped after all tests complete.
    """
    # Connect to postgres database to create test database
    admin_url = f"postgresql://{TEST_DB_USER}:{TEST_DB_PASSWORD}@{TEST_DB_HOST}:{TEST_DB_PORT}/postgres"
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    
    # Create test database
    with admin_engine.connect() as conn:
        # Drop if exists (cleanup from failed previous run)
        conn.execute(text(f"DROP DATABASE IF EXISTS {test_db_name}"))
        conn.execute(text(f"CREATE DATABASE {test_db_name}"))
    
    # Create engine for test database
    test_url = get_test_database_url(test_db_name)
    engine = create_engine(test_url)
    
    # Create all tables
    Base.metadata.create_all(engine)
    
    yield engine
    
    # Cleanup: Drop test database
    engine.dispose()
    with admin_engine.connect() as conn:
        # Terminate connections
        conn.execute(text(f"""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = '{test_db_name}'
              AND pid <> pg_backend_pid()
        """))
        conn.execute(text(f"DROP DATABASE IF EXISTS {test_db_name}"))
    
    admin_engine.dispose()


@pytest.fixture(scope="function")
def test_db(postgres_engine):
    """
    Create a test database session for each test.
    
    Each test gets a fresh session with automatic rollback.
    Tests are isolated from each other.
    """
    SessionLocal = sessionmaker(bind=postgres_engine)
    session = SessionLocal()
    
    # Start a transaction
    connection = postgres_engine.connect()
    transaction = connection.begin()
    
    # Bind session to transaction
    session = SessionLocal(bind=connection)
    
    yield session
    
    # Rollback transaction (isolates tests)
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def test_settings(test_db_name):
    """
    Create test settings that point to test database.
    
    Isolated from dev/production settings.
    """
    settings = Settings()
    settings.DATABASE_URL = get_test_database_url(test_db_name)
    settings.DB_NAME = test_db_name
    settings.DRY_RUN_MODE = True  # Safe default for tests
    
    return settings


@pytest.fixture(scope="function")
def temp_media_dir():
    """Create temporary media directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        media_path = Path(tmpdir) / "media"
        media_path.mkdir()
        yield media_path


@pytest.fixture
def sample_image(temp_media_dir):
    """Create a sample test image."""
    from PIL import Image
    
    img_path = temp_media_dir / "test_image.jpg"
    img = Image.new('RGB', (1080, 1920), color='red')
    img.save(img_path)
    
    return img_path


@pytest.fixture
def mock_instagram_api(monkeypatch):
    """Mock Instagram API responses."""
    class MockInstagramAPI:
        def create_story(self, image_url):
            return {
                'id': 'test_media_123',
                'permalink': 'https://instagram.com/p/test123'
            }
        
        def verify_credentials(self):
            return True
    
    return MockInstagramAPI()


@pytest.fixture
def mock_telegram_service(monkeypatch):
    """Mock Telegram service."""
    class MockTelegramService:
        async def send_story_notification(self, queue_item_id, media_item_dict, image_path):
            return 12345  # Mock message ID
        
        async def start_bot(self):
            pass
        
        async def stop_bot(self):
            pass
    
    return MockTelegramService()
```

### Unit Test Examples

**tests/src/utils/test_file_hash.py**
```python
"""Test file hashing utilities."""
import pytest
from pathlib import Path

from src.utils.file_hash import calculate_file_hash


def test_calculate_file_hash(sample_image):
    """Test file hash calculation."""
    hash1 = calculate_file_hash(sample_image)
    
    # Hash should be consistent
    hash2 = calculate_file_hash(sample_image)
    assert hash1 == hash2
    
    # Hash should be SHA256 (64 hex characters)
    assert len(hash1) == 64
    assert all(c in '0123456789abcdef' for c in hash1)


def test_same_content_different_name(temp_media_dir, sample_image):
    """Test that same content produces same hash regardless of filename."""
    import shutil
    
    # Copy file with different name
    copy_path = temp_media_dir / "different_name.jpg"
    shutil.copy(sample_image, copy_path)
    
    hash1 = calculate_file_hash(sample_image)
    hash2 = calculate_file_hash(copy_path)
    
    # Same content = same hash
    assert hash1 == hash2
```

**tests/src/repositories/test_queue_repository.py**
```python
"""Test queue repository."""
import pytest
from datetime import datetime, timedelta

from src.repositories.queue_repository import QueueRepository
from src.models.posting_queue import PostingQueue
from src.models.media_item import MediaItem


def test_get_posts_due_for_processing(test_db):
    """Test getting posts that are due."""
    repo = QueueRepository(test_db)
    
    # Create test media item
    media_item = MediaItem(
        file_path="/test/image.jpg",
        file_name="image.jpg",
        file_size=1000,
        file_hash="abc123",
        requires_interaction=False
    )
    test_db.add(media_item)
    test_db.commit()
    
    # Create queue items
    # 1. Due now
    queue1 = PostingQueue(
        media_item_id=media_item.id,
        scheduled_for=datetime.utcnow() - timedelta(minutes=5),
        status='pending'
    )
    # 2. Future
    queue2 = PostingQueue(
        media_item_id=media_item.id,
        scheduled_for=datetime.utcnow() + timedelta(hours=1),
        status='pending'
    )
    # 3. Ready for retry
    queue3 = PostingQueue(
        media_item_id=media_item.id,
        scheduled_for=datetime.utcnow() - timedelta(hours=1),
        status='failed',
        retry_count=1,
        next_retry_at=datetime.utcnow() - timedelta(minutes=1)
    )
    
    test_db.add_all([queue1, queue2, queue3])
    test_db.commit()
    
    # Get due posts
    due_posts = repo.get_posts_due_for_processing()
    
    # Should return queue1 (due now) and queue3 (ready for retry)
    assert len(due_posts) == 2
    assert queue1 in due_posts
    assert queue3 in due_posts
    assert queue2 not in due_posts


def test_mark_as_posted_race_condition(test_db):
    """Test that mark_as_posted prevents race conditions."""
    repo = QueueRepository(test_db)
    
    # Create test data
    media_item = MediaItem(
        file_path="/test/image.jpg",
        file_name="image.jpg",
        file_size=1000,
        file_hash="abc123"
    )
    test_db.add(media_item)
    test_db.commit()
    
    queue_item = PostingQueue(
        media_item_id=media_item.id,
        scheduled_for=datetime.utcnow(),
        status='pending'
    )
    test_db.add(queue_item)
    test_db.commit()
    
    # First user marks as posted
    success1 = repo.mark_as_posted(
        queue_item_id=str(queue_item.id),
        telegram_user_id=123,
        telegram_username="user1"
    )
    assert success1 is True
    
    # Second user tries to mark as posted (should fail)
    success2 = repo.mark_as_posted(
        queue_item_id=str(queue_item.id),
        telegram_user_id=456,
        telegram_username="user2"
    )
    assert success2 is False
    
    # Verify only first user is recorded
    test_db.refresh(queue_item)
    assert queue_item.completed_by_user == "user1"
    assert queue_item.completed_by_user_id == 123
```

**tests/src/services/test_posting.py**
```python
"""Test posting service."""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock

from src.services.posting import PostingService
from src.models.posting_queue import PostingQueue
from src.models.media_item import MediaItem


@pytest.mark.asyncio
async def test_post_automated_success(test_db, sample_image, mock_instagram_api):
    """Test successful automated posting."""
    # Create test data
    media_item = MediaItem(
        file_path=str(sample_image),
        file_name="test.jpg",
        file_size=1000,
        file_hash="abc123",
        requires_interaction=False
    )
    test_db.add(media_item)
    test_db.commit()
    
    queue_item = PostingQueue(
        media_item_id=media_item.id,
        scheduled_for=datetime.utcnow(),
        status='pending'
    )
    test_db.add(queue_item)
    test_db.commit()
    
    # Create service with mocked dependencies
    service = PostingService(test_db)
    service.instagram_api = mock_instagram_api
    service.cloud_storage = Mock()
    service.cloud_storage.upload_image = Mock(return_value={
        'public_id': 'test123',
        'secure_url': 'https://cloudinary.com/test123.jpg'
    })
    service.cloud_storage.delete_image = Mock()
    
    # Execute post
    success = await service._post_automated(queue_item, media_item)
    
    # Verify success
    assert success is True
    assert service.cloud_storage.upload_image.called
    assert service.cloud_storage.delete_image.called
    
    # Verify database updated
    test_db.refresh(queue_item)
    assert queue_item.status == 'posted'
    assert queue_item.instagram_media_id == 'test_media_123'


@pytest.mark.asyncio
async def test_post_automated_retry_on_transient_error(test_db, sample_image):
    """Test retry logic on transient errors."""
    # Create test data
    media_item = MediaItem(
        file_path=str(sample_image),
        file_name="test.jpg",
        file_size=1000,
        file_hash="abc123",
        requires_interaction=False
    )
    test_db.add(media_item)
    test_db.commit()
    
    queue_item = PostingQueue(
        media_item_id=media_item.id,
        scheduled_for=datetime.utcnow(),
        status='pending',
        retry_count=0,
        max_retries=3
    )
    test_db.add(queue_item)
    test_db.commit()
    
    # Create service with failing Instagram API
    service = PostingService(test_db)
    service.instagram_api = Mock()
    service.instagram_api.create_story = Mock(side_effect=Exception("Network timeout"))
    service.cloud_storage = Mock()
    service.cloud_storage.upload_image = Mock(return_value={
        'public_id': 'test123',
        'secure_url': 'https://cloudinary.com/test123.jpg'
    })
    
    # Execute post (should fail and schedule retry)
    success = await service._post_automated(queue_item, media_item)
    
    # Verify failure
    assert success is False
    
    # Verify retry scheduled
    test_db.refresh(queue_item)
    assert queue_item.status == 'failed'
    assert queue_item.retry_count == 1
    assert queue_item.next_retry_at is not None
```

### Integration Test Examples

**tests/integration/test_end_to_end.py**
```python
"""End-to-end integration tests."""
import pytest
from pathlib import Path
from datetime import datetime

from src.services.media_ingestion import MediaIngestionService
from src.services.scheduler import SchedulerService
from src.services.posting import PostingService


@pytest.mark.asyncio
async def test_full_workflow(test_db, temp_media_dir, sample_image, mock_instagram_api, mock_telegram_service):
    """Test complete workflow from file to post."""
    # Step 1: Index media
    ingestion_service = MediaIngestionService(test_db)
    results = ingestion_service.scan_directory(temp_media_dir)
    assert results['added'] == 1
    
    # Step 2: Create schedule
    scheduler_service = SchedulerService(test_db)
    scheduled_count = scheduler_service.create_schedule_for_today()
    assert scheduled_count > 0
    
    # Step 3: Process queue
    posting_service = PostingService(test_db)
    posting_service.instagram_api = mock_instagram_api
    posting_service.telegram_service = mock_telegram_service
    
    processed_count = await posting_service.process_pending_posts()
    assert processed_count > 0
```

### Running Tests

**Test Database Isolation**: Tests automatically create and destroy isolated PostgreSQL databases. No manual setup needed!

```bash
# Run all tests (creates fresh test database)
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/src/services/test_posting.py

# Run specific test
pytest tests/src/services/test_posting.py::test_post_automated_success

# Run with verbose output
pytest -v

# Run only unit tests (exclude integration)
pytest tests/src/

# Run only integration tests
pytest tests/integration/

# Run tests in parallel (faster)
pytest -n auto

# See test database names (for debugging)
pytest -v -s
```

**Test Database Lifecycle**:
```
1. Test session starts
   → Creates storyline_ai_test_<random>
   → Creates all tables

2. Each test runs
   → Gets fresh session
   → Runs in transaction
   → Rollback after test (isolated)

3. Test session ends
   → Drops storyline_ai_test_<random>
   → Cleanup complete
```

**Configure Test Database** (optional):
```bash
# .env.test (if you need custom test DB settings)
TEST_DB_HOST=localhost
TEST_DB_PORT=5432
TEST_DB_USER=postgres
TEST_DB_PASSWORD=postgres
```

**Test Isolation Guarantees**:
- ✅ Tests never touch dev/production databases
- ✅ Each test run gets unique database name
- ✅ Tests are isolated via transactions (rollback after each)
- ✅ Parallel test execution supported
- ✅ Automatic cleanup (even if tests fail)

---

### Database Environment Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    LOCAL DEVELOPMENT                         │
└─────────────────────────────────────────────────────────────┘

Your Machine
    ↓ DATABASE_URL=postgresql://...@localhost/storyline_ai
┌─────────────────────────────────────────────────────────────┐
│  Local PostgreSQL                                           │
│  • storyline_ai (dev database)                              │
│  • Manual setup                                             │
│  • Persists between runs                                    │
└─────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────┐
│                    RASPBERRY PI (PRODUCTION)                 │
└─────────────────────────────────────────────────────────────┘

Raspberry Pi
    ↓ DATABASE_URL=postgresql://...@localhost/storyline_ai
┌─────────────────────────────────────────────────────────────┐
│  Local PostgreSQL                                           │
│  • storyline_ai (production database)                       │
│  • Same schema as dev                                       │
│  • Isolated from dev                                        │
└─────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────┐
│                    NEON (CLOUD - OPTIONAL)                   │
└─────────────────────────────────────────────────────────────┘

Your Machine / Raspberry Pi
    ↓ DATABASE_URL=postgresql://...@neon.tech/storyline_ai?sslmode=require
┌─────────────────────────────────────────────────────────────┐
│  Neon PostgreSQL (Cloud)                                    │
│  • storyline_ai (cloud database)                            │
│  • Same schema as local                                     │
│  • Accessible from anywhere                                 │
└─────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────┐
│                    TEST ENVIRONMENT                          │
└─────────────────────────────────────────────────────────────┘

pytest
    ↓ Automatically creates test database
┌─────────────────────────────────────────────────────────────┐
│  Local PostgreSQL                                           │
│  • storyline_ai_test_a1b2c3d4 (unique per run)             │
│  • Automatically created                                    │
│  • Automatically destroyed                                  │
│  • Isolated from dev/production                             │
└─────────────────────────────────────────────────────────────┘
```

**Key Points**:
- Same code works with local or Neon (just change `DATABASE_URL`)
- Tests always use isolated databases (never touch dev/prod)
- Raspberry Pi uses local PostgreSQL (same as dev)
- Easy migration path: local → Neon (just update env var)

### Continuous Integration

Add to `.github/workflows/test.yml`:
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.10'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov pytest-asyncio
    
    - name: Run tests
      run: pytest --cov=src --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v2
```

---

## Part H: Troubleshooting

### Telegram Bot Issues

**Bot not responding:**
```bash
# Check bot token
storyline-cli test-telegram

# Check logs
tail -f logs/app.log | grep telegram
```

**Can't send to channel:**
- Ensure bot is added as Administrator
- Check channel ID is correct (should start with `-100`)
- Verify bot has "Post Messages" permission

**Buttons not working:**
- Bot must have "Edit Messages" permission
- Check database connection
- Review error logs

### Instagram API Issues

**"Invalid access token":**
```bash
# Test token
storyline-cli test-api

# Refresh token (see Meta Developer setup section)
```

**"Cannot add link sticker":**
- This is expected - Instagram API doesn't support link stickers
- This is why we use Telegram for manual posting
- Memes post automatically without links

### Database Issues

**Connection refused:**
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Test connection
psql -U storyline_user -d storyline_ai -c "SELECT 1;"
```

---

## Part I: Advanced Configuration

### Customizing Posting Schedule

Edit configuration in database:

```sql
-- Change posting frequency
UPDATE config SET value = '5' WHERE key = 'posting_frequency';

-- Change posting hours
UPDATE config SET value = '8' WHERE key = 'posting_hours_start';
UPDATE config SET value = '23' WHERE key = 'posting_hours_end';

-- Change repost avoidance period
UPDATE config SET value = '14' WHERE key = 'avoid_recent_posts_days';
```

### Custom Telegram Messages

Edit `src/services/telegram_notification.py`:

```python
# Customize message format
message_text = (
    f"🔥 NEW DROP ALERT 🔥\n"
    f"Product: {product_name}\n"
    f"Link: {product_url}\n"
    # ... customize as needed
)
```

### Multiple Telegram Channels

For different product categories or multiple teams:

```python
# In settings.py
TELEGRAM_CHANNEL_MERCH = os.getenv("TELEGRAM_CHANNEL_MERCH")
TELEGRAM_CHANNEL_DROPS = os.getenv("TELEGRAM_CHANNEL_DROPS")

# Route based on tags
if "new-drop" in media_item.tags:
    channel_id = settings.TELEGRAM_CHANNEL_DROPS
else:
    channel_id = settings.TELEGRAM_CHANNEL_MERCH
```

### Multi-Team / Multi-Account Setup

To support multiple Instagram accounts (different teams/brands):

**Database Changes**:
```sql
-- Add account identifier to media items
ALTER TABLE media_items ADD COLUMN account_id VARCHAR(50) DEFAULT 'default';
CREATE INDEX idx_media_items_account ON media_items(account_id);

-- Add to config table
INSERT INTO config (key, value, description) VALUES
    ('team_alpha_instagram_id', '', 'Team Alpha Instagram account'),
    ('team_alpha_telegram_channel', '', 'Team Alpha Telegram channel'),
    ('team_beta_instagram_id', '', 'Team Beta Instagram account'),
    ('team_beta_telegram_channel', '', 'Team Beta Telegram channel');
```

**Service Updates**:
```python
# In PostingService, route by account_id
def get_instagram_credentials(account_id: str):
    """Get credentials for specific account."""
    return {
        'instagram_id': config.get(f'{account_id}_instagram_id'),
        'telegram_channel': config.get(f'{account_id}_telegram_channel')
    }
```

**Benefits**:
- One system manages multiple brands
- Separate Telegram channels per team
- Isolated posting queues
- Shared infrastructure and maintenance

---

## Part J: Phase 2 Setup (Optional - Instagram API Automation)

> **Note**: This entire section is **optional** and only needed if you want to enable Instagram API automation (Phase 2).
> If you're happy with Telegram-only mode (Phase 1), you can skip this entirely.

### When to Complete This Setup

Complete this setup when:
- ✅ You've validated Phase 1 works well for your team
- ✅ You have many simple stories that don't need interactive elements
- ✅ You want to reduce manual posting workload
- ✅ You're ready to invest 1-2 hours in API setup

### Part J.1: Meta Developer Setup

#### Prerequisites
- ✅ Instagram Business or Creator account
- ✅ Facebook Page linked to Instagram account
- ⬜ Meta Developer account (we'll create this)

#### Step 1: Create Meta Developer Account

1. Go to [https://developers.facebook.com](https://developers.facebook.com)
2. Click **"Get Started"** in the top right
3. Log in with the Facebook account connected to your Instagram Business account
4. Complete the registration:
   - Accept terms and conditions
   - Verify email if prompted
   - Complete any security checks

#### Step 2: Create a New App

1. From the Meta for Developers dashboard, click **"My Apps"** → **"Create App"**
2. Choose use case: **"Other"** → **"Next"**
3. Choose app type: **"Business"** → **"Next"**
4. Fill in app details:
   - **App Name**: `Instagram Story Automation` (or your preference)
   - **App Contact Email**: Your email
   - **Business Account**: Select your business account or create one
5. Click **"Create App"**
6. Complete security check if prompted

#### Step 3: Add Instagram Graph API

1. In your new app dashboard, find **"Add Products"** section
2. Locate **"Instagram"** and click **"Set Up"**
3. This adds the Instagram Graph API product to your app

#### Step 4: Configure Basic Settings

1. In left sidebar, go to **Settings** → **Basic**
2. Note your **App ID** and **App Secret** (you'll need these)
3. Add **Privacy Policy URL**: Can use a placeholder like `https://yoursite.com/privacy`
4. Save changes

#### Step 5: Get Instagram Business Account ID

1. Go to [Graph API Explorer](https://developers.facebook.com/tools/explorer/)
2. Select your app from the dropdown (top right)
3. Click **"Generate Access Token"**
4. Select required permissions:
   - `pages_show_list`
   - `pages_read_engagement`
   - `instagram_basic`
   - `instagram_content_publish`
5. Click **"Generate Access Token"** and authorize
6. In the query field, enter: `me/accounts`
7. Click **Submit**
8. Find your Facebook Page in the response, note the `id` and `access_token`
9. Now query: `{page-id}?fields=instagram_business_account`
10. Note the `instagram_business_account.id` - this is your **Instagram Business Account ID**

#### Step 6: Get Long-Lived Page Access Token

Short-lived tokens expire in 1 hour. We need a long-lived Page token (never expires).

**Step 6.1: Get Long-Lived User Token**

```bash
curl -X GET "https://graph.facebook.com/v21.0/oauth/access_token?grant_type=fb_exchange_token&client_id={APP_ID}&client_secret={APP_SECRET}&fb_exchange_token={SHORT_LIVED_USER_TOKEN}"
```

This returns a 60-day user token.

**Step 6.2: Get Page Access Token**

```bash
curl -X GET "https://graph.facebook.com/v21.0/me/accounts?access_token={LONG_LIVED_USER_TOKEN}"
```

Find your Page's `access_token` in the response. **This Page token never expires** and is what you'll use in the app.

#### Step 7: Verify Token

Test your token:

```bash
curl -X GET "https://graph.facebook.com/v21.0/{INSTAGRAM_ACCOUNT_ID}?fields=id,username&access_token={PAGE_ACCESS_TOKEN}"
```

You should see your Instagram username.

#### Step 8: App Review (Optional - For Public Distribution)

For personal use, you can skip this. For public distribution:

1. Go to **App Review** → **Permissions and Features**
2. Request advanced access for:
   - `instagram_basic`
   - `instagram_content_publish`
   - `pages_read_engagement`
3. Provide use case description and screencast
4. Wait for Meta approval (3-5 business days)

#### Security Notes

- **Never commit tokens to Git**: Use environment variables
- **Store App Secret securely**: Never expose client-side
- **Use HTTPS in production**: Required for webhooks

---

### Part J.2: Cloudinary Setup

#### Why Cloudinary?

**Critical Requirement**: Instagram Graph API requires images to be accessible via **publicly accessible HTTPS URL**. You cannot upload directly from filesystem.

**Why Not Just Use Local Files?**
- ❌ Instagram API rejects `file://` paths
- ❌ Instagram API rejects `http://localhost` URLs
- ❌ Instagram API requires public HTTPS endpoint
- ✅ Must use cloud storage or self-hosted HTTPS server

**Cloudinary Benefits:**
- ✅ Free tier: 25GB storage, 25GB bandwidth/month (sufficient for most creators)
- ✅ Automatic HTTPS (no SSL certificate management)
- ✅ Simple Python SDK (3 lines of code to upload)
- ✅ Programmatic deletion (cleanup after posting to save quota)
- ✅ Works from anywhere (Raspberry Pi, laptop, cloud)
- ✅ No port forwarding or domain name required

**Alternative Options** (more complex):
- Self-hosted with ngrok/Cloudflare Tunnel (requires keeping tunnel alive)
- Self-hosted web server with Let's Encrypt (requires domain + port forwarding)
- AWS S3 + CloudFront (overkill for this use case)

**For Telegram Workflow**: Cloudinary is NOT used. Images are sent directly from filesystem to Telegram, since Telegram accepts direct file uploads.

#### Cloudinary Workflow (Automated Posts Only)

```
┌─────────────────────────────────────────────────┐
│ Automated Story Workflow (Simple Stories)       │
└─────────────────────────────────────────────────┘

1. Read image from local filesystem
   /home/pi/media/stories/meme1.jpg

2. Upload to Cloudinary (temporary)
   → Returns: https://res.cloudinary.com/.../meme1.jpg

3. Post to Instagram via API
   POST /{ig-user-id}/media
   {
     "image_url": "https://res.cloudinary.com/.../meme1.jpg",
     "media_type": "STORIES"
   }

4. Instagram fetches image from Cloudinary
   (Instagram downloads and caches the image)

5. Delete from Cloudinary (save quota)
   → Image is gone from Cloudinary
   → Still exists on Instagram (they cached it)

Total Cloudinary storage used: ~0 MB (deleted after post)
Total Cloudinary bandwidth used: ~1-2 MB per post
```

#### Setup Steps

1. Create account at [cloudinary.com](https://cloudinary.com)
2. Go to Dashboard
3. Note these credentials:
   - **Cloud Name**
   - **API Key**
   - **API Secret**
4. Add to your `.env` file

**Free Tier Limits:**
- 25 GB storage (we use ~0 since we delete immediately)
- 25 GB bandwidth/month
- At ~2 MB per image, that's ~12,500 automated posts/month
- More than enough for most creators

#### Enable Phase 2

After completing both Meta Developer and Cloudinary setup:

```bash
# Edit .env file
nano .env

# Set these values:
ENABLE_INSTAGRAM_API=true
INSTAGRAM_ACCOUNT_ID=your_instagram_business_account_id
ACCESS_TOKEN=your_long_lived_page_access_token
APP_ID=your_app_id
APP_SECRET=your_app_secret
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret

# Restart the service
sudo systemctl restart storyline-ai
```

The system will now automatically post simple stories (where `requires_interaction=false`) via Instagram API, while still sending interactive stories to Telegram.

---

## Part K: Migration to Cloud

### Phase 1: Database (Neon)

```bash
# Export local database
pg_dump -U storyline_user storyline_ai > backup.sql

# Import to Neon
psql "postgresql://user:password@host.neon.tech/database?sslmode=require" < backup.sql

# Update .env
DB_HOST=your-project.neon.tech
DB_PORT=5432
DB_NAME=your_database
DB_USER=your_user
DB_PASSWORD=your_password

# Restart service
sudo systemctl restart storyline-ai
```

### Phase 2: Hosting (Railway)

```bash
# Push to GitHub
git init
git add .
git commit -m "Initial commit"
git push origin main

# In Railway dashboard:
# 1. New Project → Deploy from GitHub
# 2. Select repository
# 3. Add environment variables (all from .env)
# 4. Deploy

# Railway will automatically:
# - Install dependencies
# - Run the application
# - Provide logs and metrics
```

### Phase 3: File Storage (Optional - S3)

For cloud-native file storage:

```python
# Update CloudStorageService to support S3
# Or keep Cloudinary (it already works from anywhere)
```

---

## Roadmap & Future Enhancements

### Phase 1: Core System (Telegram-Only)
**Status**: ✅ Ready to implement
**Timeline**: Week 1-2

**Services**:
- ✅ `MediaIngestionService`: Scan and index media
- ✅ `SchedulerService`: Create posting schedule
- ✅ `PostingService`: Orchestrate posting workflow
- ✅ `TelegramService`: Bot operations and callbacks
- ✅ `MediaLockService`: TTL lock management

**Features**:
- Smart scheduling system
- Telegram bot with workflow tracking
- Media library management
- Team collaboration features
- Audit trail and statistics
- Dry-run mode for testing

**Deliverables**:
- CLI tools for all operations
- Systemd service for production
- Full test coverage

---

### Phase 2: Instagram API Automation (Optional)
**Status**: 🔄 Ready when you are (feature-flagged)
**Timeline**: Week 3-4 (or later)

**Services**:
- ✅ `CloudStorageService`: Upload to Cloudinary/S3
- ✅ `InstagramAPIService`: Graph API integration

**Features**:
- Automated posting for simple stories
- Cloudinary integration
- Hybrid workflow (auto + manual)
- Rate limiting and retry logic

**Activation**: Set `ENABLE_INSTAGRAM_API=true` in `.env`

---

### Phase 3: Shopify Integration
**Status**: 📋 Schema-ready, implementation pending
**Timeline**: Month 2-3

**Services**:
- 🆕 `ShopifyService`: Sync products from Shopify API (with Type 2 SCD)
- 🆕 `ProductLinkService`: Link media to products

**Features**:
- Sync products from Shopify
- Track product changes over time (price, title, description)
- Link media items to products (many-to-many)
- Enhanced Telegram notifications with product details
- Product-level analytics with historical context
- CLI: `storyline-cli sync-shopify`

**Database**: Already prepared (`shopify_products` with Type 2 SCD, `media_product_links`)

**Key Innovation**: Type 2 SCD enables queries like "What was the price when we posted this story?" for accurate performance analysis

---

### Phase 4: Instagram Analytics
**Status**: 📋 Schema-ready, implementation pending
**Timeline**: Month 3-4

**Services**:
- 🆕 `InstagramMetricsService`: Fetch performance metrics
- 🆕 `AnalyticsService`: Aggregate and generate insights

**Features**:
- Pull engagement metrics from Instagram Graph API
- Track impressions, reach, replies, link clicks
- Time-series data (24h, 7d, 30d snapshots)
- Performance dashboards
- Best-performing content identification
- Product-level analytics (via Shopify links)
- CLI: `storyline-cli fetch-metrics`

**Database**: Already prepared (`instagram_post_metrics`)

---

### Phase 5: REST API & Web Frontend
**Status**: 🎨 Architecture defined, implementation pending
**Timeline**: Month 4-6

**Components**:
- 🆕 FastAPI backend (exposes all services)
- 🆕 React/Next.js frontend
- 🆕 JWT authentication
- 🆕 OpenAPI/Swagger documentation

**Features**:
- Web-based media library browser
- Calendar view of scheduled posts
- Drag-and-drop product linking
- Analytics dashboards
- Settings management
- Team member management
- No CLI needed (full web UI)

**Architecture**: All existing services become API endpoints (no code changes needed)

---

### Service Architecture Evolution

```
┌─────────────────────────────────────────────────────────────┐
│                    PHASE 1: CLI + Services                   │
└─────────────────────────────────────────────────────────────┘

CLI Commands
    ↓
┌─────────────────────────────────────────────────────────────┐
│  Core Services                                              │
│  • MediaIngestionService                                    │
│  • SchedulerService                                         │
│  • PostingService                                           │
│  • TelegramService                                          │
│  • MediaLockService                                         │
└────────────────────┬────────────────────────────────────────┘
                     ↓
              Repositories
                     ↓
              PostgreSQL


┌─────────────────────────────────────────────────────────────┐
│              PHASE 2: Add Integration Services              │
└─────────────────────────────────────────────────────────────┘

CLI Commands
    ↓
┌─────────────────────────────────────────────────────────────┐
│  Core Services + Integration Services                       │
│  • MediaIngestionService                                    │
│  • SchedulerService                                         │
│  • PostingService                                           │
│  • TelegramService                                          │
│  • MediaLockService                                         │
│  • CloudStorageService       ← NEW                          │
│  • InstagramAPIService       ← NEW                          │
└────────────────────┬────────────────────────────────────────┘
                     ↓
              Repositories
                     ↓
              PostgreSQL


┌─────────────────────────────────────────────────────────────┐
│            PHASE 3-4: Add Domain Services                   │
└─────────────────────────────────────────────────────────────┘

CLI Commands
    ↓
┌─────────────────────────────────────────────────────────────┐
│  All Services                                               │
│  Core + Integration + Domain                                │
│  • ShopifyService            ← NEW                          │
│  • ProductLinkService        ← NEW                          │
│  • InstagramMetricsService   ← NEW                          │
│  • AnalyticsService          ← NEW                          │
└────────────────────┬────────────────────────────────────────┘
                     ↓
              Repositories
                     ↓
              PostgreSQL


┌─────────────────────────────────────────────────────────────┐
│              PHASE 5: Add API Layer                         │
└─────────────────────────────────────────────────────────────┘

Web Frontend (React)
    ↓ HTTP/REST
┌─────────────────────────────────────────────────────────────┐
│  FastAPI Layer (NEW)                                        │
│  • Authentication (JWT)                                     │
│  • API Routes                                               │
│  • Request/Response validation                              │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│  All Services (UNCHANGED)                                   │
│  • MediaIngestionService                                    │
│  • SchedulerService                                         │
│  • PostingService                                           │
│  • TelegramService                                          │
│  • MediaLockService                                         │
│  • CloudStorageService                                      │
│  • InstagramAPIService                                      │
│  • ShopifyService                                           │
│  • ProductLinkService                                       │
│  • InstagramMetricsService                                  │
│  • AnalyticsService                                         │
└────────────────────┬────────────────────────────────────────┘
                     ↓
              Repositories
                     ↓
              PostgreSQL
```

**Key Insight**: Services remain unchanged across phases. Each phase adds new services or exposes existing ones via API. This is true service-oriented architecture!

---

### Future: Telegram Webhook Mode (Planned)
**Current**: Polling mode (bot checks for updates every few seconds)
**Future**: Webhook mode (Telegram pushes updates instantly)

**Benefits of Webhook**:
- ✅ Instant updates (no polling delay)
- ✅ Lower server load
- ✅ More efficient
- ✅ Better for cloud deployments

**Requirements**:
- HTTPS endpoint (required by Telegram)
- Public domain name
- SSL certificate
- Not feasible for local Raspberry Pi without tunnel

**Implementation Path**:
1. Keep polling for local/Raspberry Pi deployments
2. Add webhook support when migrating to cloud (Railway/Render)
3. Auto-detect environment and choose appropriate mode

```python
# Future implementation
if settings.TELEGRAM_WEBHOOK_URL:
    # Cloud deployment - use webhook
    await application.set_webhook(settings.TELEGRAM_WEBHOOK_URL)
else:
    # Local deployment - use polling
    await application.updater.start_polling()
```

### Future: Web Dashboard (Planned)
- React/Next.js web interface
- View posting schedule calendar
- Manual post trigger
- Analytics and insights
- Media library management
- Team member management
- Real-time Telegram message preview

### Future: Shopify Integration (Planned)
**Database**: Already schema-ready (`shopify_products`, `media_product_links`)

**Features**:
- Sync products from Shopify API
- Link media items to products (many-to-many)
- Auto-populate product URLs in Telegram notifications
- Track which products get posted most
- Product performance analytics

**Implementation**:
- `ShopifyService`: Sync products via Shopify API
- `ProductRepository`: CRUD for products and links
- CLI: `storyline-cli sync-shopify`
- Telegram: Enhanced notifications with product details

---

### Future: Instagram Analytics (Planned)
**Database**: Already schema-ready (`instagram_post_metrics`)

**Features**:
- Pull engagement metrics from Instagram Graph API
- Track impressions, reach, replies, link clicks
- Time-series data (24h, 7d, 30d snapshots)
- Performance dashboards
- Best-performing content identification
- Product-level analytics (via Shopify links)

**Implementation**:
- `InstagramMetricsService`: Fetch metrics via Graph API
- `MetricsRepository`: Store time-series data
- CLI: `storyline-cli fetch-metrics`
- Analytics queries for reporting

---

### Future: Advanced Features (Planned)
- Video story support
- Multi-account management (multiple Instagram accounts)
- A/B testing for post timing
- AI-powered caption generation
- Optimal posting time prediction (based on metrics)
- Automated product recommendations (based on performance)

### Future: REST API & Web Frontend (Planned)

**Purpose**: Expose services via REST API for web-based management interface.

**Technology Stack**:
- **Backend**: FastAPI (Python)
- **Frontend**: React/Next.js
- **Authentication**: JWT tokens
- **Documentation**: Auto-generated OpenAPI/Swagger

**API Structure**:
```
/api/v1/
  /media/
    GET    /media              # List media items
    POST   /media/scan         # Trigger media scan
    GET    /media/{id}         # Get media details
    PUT    /media/{id}         # Update metadata
    DELETE /media/{id}         # Delete media
    
  /queue/
    GET    /queue              # List queue items
    POST   /queue              # Add to queue
    GET    /queue/{id}         # Get queue item
    DELETE /queue/{id}         # Remove from queue
    POST   /queue/process      # Trigger processing
    
  /history/
    GET    /history            # List posting history
    GET    /history/{id}       # Get history details
    GET    /history/stats      # Get statistics
    
  /locks/
    GET    /locks              # List active locks
    POST   /locks              # Create lock
    DELETE /locks/{id}         # Remove lock
    
  /shopify/
    POST   /shopify/sync       # Sync products
    GET    /shopify/products   # List products
    GET    /shopify/products/{id} # Get product
    
  /links/
    POST   /links              # Link media to product
    DELETE /links/{id}         # Unlink
    PUT    /links/reorder      # Reorder product images
    
  /analytics/
    GET    /analytics/top-media      # Best performing
    GET    /analytics/products/{id}  # Product performance
    GET    /analytics/reports        # Generate report
    
  /telegram/
    GET    /telegram/status    # Bot status
    POST   /telegram/send      # Send test message
    
  /health/
    GET    /health             # System health check
```

**Web Frontend Features**:
- 📊 Dashboard with posting statistics
- 📁 Media library browser with filters
- 📅 Calendar view of scheduled posts
- 🛍️ Shopify product management
- 🔗 Drag-and-drop media-product linking
- 📈 Analytics and performance charts
- ⚙️ Settings and configuration
- 👥 Team member management

**Authentication Flow**:
```
1. User logs in → JWT token issued
2. Frontend stores token
3. All API calls include token in header
4. Backend validates token before processing
```

**Example API Usage**:
```python
# Frontend calls API
fetch('/api/v1/media/scan', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer <token>',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ path: '/media/stories' })
})

# Backend (FastAPI)
@router.post("/media/scan")
async def scan_media(
    path: str,
    current_user: User = Depends(get_current_user),
    media_service: MediaIngestionService = Depends(get_media_service)
):
    results = media_service.scan_directory(path)
    return {"status": "success", "results": results}
```

---

### Future: iCloud Sync (Planned)
- Automatic sync from iCloud Shared Album using rclone
- Cron job to sync every 30 minutes
- Automatic indexing after sync
- CLI command: `storyline-cli sync-icloud`
- **Note**: Not needed for initial launch, can be added later based on workflow needs

---

## Appendix: Phase Comparison

### What You Need for Each Phase

| Component | Phase 1 (Telegram-Only) | Phase 2 (Hybrid) |
|-----------|-------------------------|------------------|
| **Hardware** | | |
| Raspberry Pi / Server | ✅ Required | ✅ Required |
| PostgreSQL Database | ✅ Required | ✅ Required |
| **Accounts** | | |
| Telegram Bot | ✅ Required | ✅ Required |
| Telegram Channel | ✅ Required | ✅ Required |
| Instagram Business Account | ❌ Not needed | ✅ Required |
| Meta Developer Account | ❌ Not needed | ✅ Required |
| Facebook Business Page | ❌ Not needed | ✅ Required |
| Cloudinary Account | ❌ Not needed | ✅ Required |
| **Configuration** | | |
| `ENABLE_INSTAGRAM_API` | `false` | `true` |
| `TELEGRAM_BOT_TOKEN` | ✅ Required | ✅ Required |
| `TELEGRAM_CHANNEL_ID` | ✅ Required | ✅ Required |
| `INSTAGRAM_ACCOUNT_ID` | ❌ Not needed | ✅ Required |
| `ACCESS_TOKEN` | ❌ Not needed | ✅ Required |
| `CLOUDINARY_*` | ❌ Not needed | ✅ Required |
| **Setup Time** | ~30 minutes | +1-2 hours |
| **Complexity** | Low | Medium |
| **External APIs** | 1 (Telegram) | 3 (Telegram, Instagram, Cloudinary) |
| **Manual Work** | All posts | Interactive posts only |
| **Automation** | None | Simple stories |

### Feature Availability

| Feature | Phase 1 | Phase 2 |
|---------|---------|---------|
| Smart scheduling | ✅ | ✅ |
| Media library management | ✅ | ✅ |
| Telegram notifications | ✅ | ✅ |
| Team workflow tracking | ✅ | ✅ |
| Audit trail | ✅ | ✅ |
| Dry-run mode | ✅ | ✅ |
| Health checks | ✅ | ✅ |
| CLI tools | ✅ | ✅ |
| Automated posting (simple stories) | ❌ | ✅ |
| Instagram API integration | ❌ | ✅ |
| Cloudinary integration | ❌ | ✅ |
| Rate limiting | ❌ | ✅ |

### When to Use Each Phase

**Use Phase 1 If**:
- ✅ You want to start quickly (30 minutes)
- ✅ You want to validate the system first
- ✅ Most stories need interactive elements (links, polls)
- ✅ You prefer manual control over all posts
- ✅ You want to avoid external API complexity
- ✅ Small team can handle 3-5 manual posts per day

**Add Phase 2 If**:
- ✅ You've validated Phase 1 works well
- ✅ You have many simple stories (memes, quotes, no stickers)
- ✅ Manual posting becomes tedious
- ✅ You want to reduce team workload
- ✅ You're comfortable with Instagram API setup
- ✅ You want hybrid workflow (auto + manual)

**Bottom Line**: Start with Phase 1, add Phase 2 only if you need it.