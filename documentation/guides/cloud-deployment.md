# Cloud Deployment Guide

Deploy Storyline AI to cloud infrastructure (Railway + Neon) for multi-tenant SaaS operation.

**Estimated time:** 2-3 hours for complete setup
**Prerequisites:** GitHub account, Railway account, Neon account

---

## Architecture Overview

```
GitHub Repo
    |
    ├──► Railway (worker)     python -m src.main
    |    - Telegram bot polling
    |    - Posting scheduler loop
    |    - Lock cleanup loop
    |    - Media sync loop
    |
    ├──► Railway (web)        uvicorn src.api.app:app
    |    - OAuth callbacks (Instagram, Google Drive)
    |    - Onboarding Mini App
    |    - API endpoints
    |
    └──► Neon (PostgreSQL)
         - All application data
         - SSL required

External APIs:
  - Telegram Bot API (polling, free)
  - Instagram Graph API (OAuth tokens, free)
  - Google Drive API (user OAuth, free)
  - Cloudinary (media hosting, free tier)
```

### Raspberry Pi vs Cloud Comparison

| Aspect | Raspberry Pi | Cloud (Railway + Neon) |
|--------|-------------|----------------------|
| Database | Local PostgreSQL | Neon (managed, SSL) |
| Process mgmt | systemd | Railway (managed) |
| HTTPS | Not available | Automatic (Railway) |
| OAuth callbacks | Not possible | Built-in |
| Multi-tenant | Single tenant | Multi-tenant ready |
| Cost | Hardware only | ~$5-15/month |
| Availability | Depends on network | 99.9%+ |

---

## 1. Database Setup (Neon)

### Create a Neon Project

1. Sign up at [console.neon.tech](https://console.neon.tech)
2. Create a new project (name: `storyline-ai`)
3. Note your connection details from the dashboard

### Run Schema Setup

Connect via `psql` using the Neon connection string:

```bash
psql "postgresql://storyline_user:PASSWORD@ep-xxx.region.neon.tech/storyline_ai?sslmode=require"
```

Run the base schema and all migrations in order:

```bash
# Base schema
psql "$DATABASE_URL" -f scripts/setup_database.sql

# All migrations (run in order)
for f in scripts/migrations/0{01,02,03,04,05,06,07,08,09,10,11,12,13,14,15,16}_*.sql; do
  echo "Running $f..."
  psql "$DATABASE_URL" -f "$f"
done
```

### Verify Schema

```sql
-- Check schema version
SELECT * FROM schema_version ORDER BY version;

-- Should show version 16 as latest

-- Check uuid-ossp extension
SELECT extname FROM pg_extension WHERE extname = 'uuid-ossp';
```

### Connection Pool Sizing

Neon free tier allows 5 concurrent connections. Set these env vars:

```
DB_POOL_SIZE=3
DB_MAX_OVERFLOW=2
```

The defaults (pool_size=10, max_overflow=20) are too aggressive for Neon free tier.

---

## 2. Railway Deployment

### Two-Process Architecture

Storyline AI requires **two processes** on Railway:

1. **Worker** (`python -m src.main`): Telegram bot + scheduler + background loops
2. **Web** (`uvicorn src.api.app:app`): OAuth callbacks + onboarding Mini App

The included `Procfile` defines both:

```
worker: python -m src.main
web: uvicorn src.api.app:app --host 0.0.0.0 --port ${PORT:-8000}
```

### Setup Steps

1. **Connect GitHub repo** in Railway dashboard
2. **Create two services** from the same repo:
   - Service 1: Set start command to `python -m src.main` (worker)
   - Service 2: Set start command to `uvicorn src.api.app:app --host 0.0.0.0 --port ${PORT:-8000}` (web)
3. **Set build command** for both: `pip install -r requirements.txt && pip install -e .`
4. **Generate a domain** for the web service (needed for OAuth callbacks)
5. **Configure environment variables** (see Section 3 below)

### MEDIA_DIR on Cloud

The `ConfigValidator` checks that `MEDIA_DIR` exists on the filesystem. On Railway:

- **Recommended**: Use Google Drive as media source (`MEDIA_SOURCE_TYPE=google_drive`). Set `MEDIA_DIR` to `/tmp/media` and create it at build time.
- Add to build command: `pip install -r requirements.txt && pip install -e . && mkdir -p /tmp/media`
- The local `MEDIA_DIR` is only used as fallback when Google Drive is not configured.

### Health Checks

- **Worker**: Railway monitors the process — if it exits, it restarts automatically. The app has built-in SIGTERM handling for graceful shutdown.
- **Web**: Railway health checks hit the web service automatically. FastAPI responds to requests by default.

---

## 3. Environment Variables

Configure these in the Railway dashboard for **both** services:

### Required (All Deployments)

| Variable | Description | Example |
|---|---|---|
| `DATABASE_URL` | Full Neon connection string (includes SSL) | `postgresql://user:pass@ep-xxx.neon.tech/storyline_ai?sslmode=require` |
| `TELEGRAM_BOT_TOKEN` | From BotFather | `123456:ABC-DEF1234ghIkl` |
| `TELEGRAM_CHANNEL_ID` | Your Telegram channel (negative) | `-1001234567890` |
| `ADMIN_TELEGRAM_CHAT_ID` | Your personal chat ID | `123456789` |
| `MEDIA_DIR` | Local media path (can be dummy on cloud) | `/tmp/media` |
| `ENCRYPTION_KEY` | Fernet key for token encryption | Generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

### Database (Alternative to DATABASE_URL)

If not using `DATABASE_URL`, set individual components:

| Variable | Description | Example |
|---|---|---|
| `DB_HOST` | Neon endpoint | `ep-cool-morning-123456.us-east-2.aws.neon.tech` |
| `DB_PORT` | Database port | `5432` |
| `DB_NAME` | Database name | `storyline_ai` |
| `DB_USER` | Database user | `storyline_user` |
| `DB_PASSWORD` | Database password | `neon_generated_password` |
| `DB_SSLMODE` | SSL mode (required for Neon) | `require` |
| `DB_POOL_SIZE` | Connection pool size | `3` (Neon free tier) |
| `DB_MAX_OVERFLOW` | Max overflow connections | `2` (Neon free tier) |

### OAuth & API (Web Service)

| Variable | Description | Example |
|---|---|---|
| `OAUTH_REDIRECT_BASE_URL` | Railway web service URL | `https://your-app.up.railway.app` |
| `FACEBOOK_APP_ID` | Meta Developer App ID | `1234567890123456` |
| `FACEBOOK_APP_SECRET` | Meta Developer App Secret | `abc123...` |
| `GOOGLE_CLIENT_ID` | Google OAuth Client ID | `xxx.apps.googleusercontent.com` |
| `GOOGLE_CLIENT_SECRET` | Google OAuth Client Secret | `GOCSPX-...` |

### Instagram API (Phase 2)

| Variable | Description | Example |
|---|---|---|
| `ENABLE_INSTAGRAM_API` | Enable Instagram posting | `true` |
| `INSTAGRAM_ACCOUNT_ID` | Instagram Business Account ID | `17841405793087218` |
| `CLOUDINARY_CLOUD_NAME` | Cloudinary cloud name | `dxyz123` |
| `CLOUDINARY_API_KEY` | Cloudinary API key | `123456789012345` |
| `CLOUDINARY_API_SECRET` | Cloudinary API secret | `abc_secret...` |

### Media & Schedule

| Variable | Default | Description |
|---|---|---|
| `MEDIA_SOURCE_TYPE` | `local` | Set to `google_drive` for cloud |
| `MEDIA_SOURCE_ROOT` | `""` | Google Drive folder ID |
| `MEDIA_SYNC_ENABLED` | `false` | Enable Google Drive sync |
| `MEDIA_SYNC_INTERVAL_SECONDS` | `300` | Sync interval |
| `POSTS_PER_DAY` | `3` | Default posts per day |
| `POSTING_HOURS_START` | `14` | Start hour (UTC) |
| `POSTING_HOURS_END` | `2` | End hour (UTC) |
| `DRY_RUN_MODE` | `false` | Prevent actual posting |

---

## 4. Telegram Bot Setup

### BotFather Configuration

1. Message [@BotFather](https://t.me/botfather) on Telegram
2. `/newbot` and follow prompts to get your bot token
3. `/setcommands` to register commands:

```
start - Initialize bot and setup wizard
status - System health and queue status
help - Show available commands
queue - View upcoming posts
next - Force send next post
pause - Pause automatic posting
resume - Resume posting
schedule - Create posting schedule
stats - Media library statistics
history - Recent post history
locks - View permanently rejected items
reset - Reset posting queue
cleanup - Delete recent bot messages
settings - Configure bot settings
dryrun - Toggle dry-run mode
sync - Trigger manual media sync
connect - Connect Instagram account
```

4. Add the bot as admin to your Telegram channel/group
5. Get the channel ID (send a message, check via `https://api.telegram.org/bot<TOKEN>/getUpdates`)

### Polling vs Webhooks

The app uses **polling mode** by default, which works well for cloud deployment (no webhook URL needed). If you want to switch to webhooks later, set the webhook URL to your Railway domain.

---

## 5. Instagram OAuth Setup

Instagram account connection uses browser-based OAuth, which requires the web service (FastAPI) to be running.

### Meta Developer Setup

1. Create an app at [developers.facebook.com](https://developers.facebook.com)
2. Add the "Instagram Basic Display" product
3. Configure OAuth redirect URI: `https://your-app.up.railway.app/auth/instagram/callback`
4. Required permissions: `pages_show_list`, `pages_read_engagement`, `instagram_basic`, `instagram_content_publish`, `business_management`
5. Set `FACEBOOK_APP_ID` and `FACEBOOK_APP_SECRET` env vars

### How It Works (Post-Phase 04)

1. User sends `/connect` in Telegram
2. Bot replies with an "Connect Instagram" button (OAuth link)
3. User clicks, authorizes in browser, Meta redirects to callback
4. Callback exchanges code for long-lived token, stores encrypted in DB
5. Bot notifies user of successful connection

### App Review

Without Meta App Review, only users with roles on the Meta app (admins, developers, testers) can use the API. For a single-brand use case, this is sufficient.

---

## 6. Google Drive OAuth Setup

Google Drive is the recommended media source for cloud deployments.

### Google Cloud Setup

1. Create a project at [console.cloud.google.com](https://console.cloud.google.com)
2. Enable the **Google Drive API**
3. Create **OAuth 2.0 Client ID** (Web application type)
4. Add authorized redirect URI: `https://your-app.up.railway.app/auth/google-drive/callback`
5. Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` env vars

### How It Works (Post-Phase 05)

1. User connects Google Drive via the onboarding wizard (`/start`)
2. Bot replies with "Connect Google Drive" button (OAuth link)
3. User clicks, authorizes Google account access
4. Callback exchanges code for tokens, stores encrypted per-tenant in DB
5. User's Google Drive folders become available as media sources
6. Media sync pulls files from the user's shared folder

### User Experience

End users just need a Google account with a Drive folder containing their media. They never interact with GCP or service accounts. The GCP project setup is a one-time task for the app operator.

---

## 7. Cloudinary Setup

Required only when `ENABLE_INSTAGRAM_API=true` (Phase 2 posting).

1. Create account at [cloudinary.com](https://cloudinary.com) (free tier: 25 credits/month)
2. Get credentials from Dashboard: Cloud Name, API Key, API Secret
3. Set env vars: `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`

The `CloudStorageService` uploads media to Cloudinary with 9:16 transformations and auto-cleanup after `CLOUD_UPLOAD_RETENTION_HOURS` (default: 24).

---

## 8. Monitoring & Operations

### Logs

Railway provides log streaming in the dashboard. The app logs to stdout via the console handler, which Railway captures automatically.

### Database Backups

- **Neon**: Automatic point-in-time recovery (paid plans). Free tier has limited retention.
- **Manual**: `pg_dump "$DATABASE_URL" > backup_$(date +%Y%m%d).sql`

### Health Monitoring

Use the Telegram bot itself as a health indicator:
- `/status` shows system health, queue state, and recent activity
- `/check-health` (via CLI in Railway shell) runs comprehensive health check

### Service Management

- **Restart**: Via Railway dashboard or `railway restart`
- **Logs**: `railway logs` or dashboard
- **Shell**: `railway shell` for running CLI commands

### Cost Estimates

| Service | Tier | Cost |
|---------|------|------|
| Neon | Free | $0 (0.5 GB, 190 compute-hours) |
| Railway | Starter | ~$5-10/month (worker + web) |
| Cloudinary | Free | $0 (25 credits/month) |
| Telegram Bot API | Free | $0 |
| Instagram/Meta API | Free | $0 (rate-limited) |
| Google Drive API | Free | $0 (quota-limited) |
| **Total** | | **~$5-10/month** |

---

## 9. Security Checklist

- [ ] All secrets stored as Railway environment variables (never in code)
- [ ] `ENCRYPTION_KEY` generated and set (for token encryption in DB)
- [ ] Database password is strong and unique
- [ ] Telegram bot token is kept secret
- [ ] Instagram/Facebook app secret is kept secret
- [ ] Cloudinary API secret is kept secret
- [ ] Google OAuth client secret is kept secret
- [ ] `.env` file is NOT committed (verified in `.gitignore`)
- [ ] SSL/TLS for all connections (Neon requires it, all APIs use HTTPS)
- [ ] Connection pool sizing appropriate for Neon tier
- [ ] `OAUTH_REDIRECT_BASE_URL` points to your Railway HTTPS domain

---

## 10. Troubleshooting

| Problem | Solution |
|---------|----------|
| Database connection fails | Check `DATABASE_URL` or `DB_*` vars. Ensure `DB_SSLMODE=require` for Neon. |
| Neon connection limit exceeded | Reduce `DB_POOL_SIZE` to 3 and `DB_MAX_OVERFLOW` to 2. |
| Telegram bot not responding | Verify `TELEGRAM_BOT_TOKEN` is correct. Check Railway worker logs. |
| `MEDIA_DIR does not exist` | Add `mkdir -p /tmp/media` to build command. |
| `ENCRYPTION_KEY not configured` | Generate one: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| OAuth callback fails | Check `OAUTH_REDIRECT_BASE_URL` matches your Railway web domain. |
| Mini App won't load | Ensure web service is running and domain has HTTPS. Check `OAUTH_REDIRECT_BASE_URL`. |
| Service restarts frequently | Check memory limits in Railway. Review logs for OOM or crash loops. |
| "idle in transaction" | Built-in cleanup runs every 30 seconds. Reduce pool size if persistent. |
| Instagram API rate limited | Default: 25 posts/hour. Check `INSTAGRAM_POSTS_PER_HOUR`. |

---

## Quick Start Checklist

1. [ ] Create Neon database and run schema + all 16 migrations
2. [ ] Create Railway project with two services (worker + web)
3. [ ] Set all required environment variables
4. [ ] Create Telegram bot via BotFather, get token
5. [ ] Add bot to your channel/group as admin
6. [ ] Generate Railway domain for web service
7. [ ] Set `OAUTH_REDIRECT_BASE_URL` to the Railway HTTPS domain
8. [ ] Configure Meta Developer App (Instagram OAuth redirect URI)
9. [ ] Configure Google Cloud OAuth (Google Drive redirect URI)
10. [ ] Deploy and verify bot responds to `/start`
11. [ ] Test onboarding wizard opens from `/start`
12. [ ] Test Instagram OAuth flow (via `/connect` or wizard)
13. [ ] Test Google Drive OAuth flow (via onboarding wizard)
14. [ ] Set `DRY_RUN_MODE=false` when ready for live posting
