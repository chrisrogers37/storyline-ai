# Phase 07: Central Deployment & Infrastructure Guide

**Status:** PENDING
**Risk:** Low
**Effort:** 2-3 hours
**PR Title:** `docs: central deployment and infrastructure guide for multi-tenant SaaS`

---

## Summary of Findings

After thorough exploration of the codebase, here is what has been confirmed about the current system:

**Current Architecture:**
- Single-process Python application started via `python -m src.main` that runs:
  - Telegram bot polling loop (using `python-telegram-bot`)
  - Posting scheduler loop (checks every 60 seconds)
  - Lock cleanup loop (every 3600 seconds)
  - Media sync loop (if enabled, configurable interval)
  - Transaction cleanup loop (every 30 seconds)
- No FastAPI/HTTP server currently running (API layer mentioned in CLAUDE.md as Phase 2.5 but not yet implemented)
- No Dockerfile, Procfile, or runtime.txt exists
- Database: PostgreSQL via SQLAlchemy (synchronous, `psycopg2-binary`)
- Database URL assembled from individual components (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`) -- no support for a single `DATABASE_URL` string or SSL mode
- Deployment: SSH to Raspberry Pi via `scripts/deploy.sh` (git pull, pip install, systemd restart)
- Current deploy.sh target: `crogberrypi` (SSH alias), user `crog`

**External Services Connected:**
1. **Telegram Bot API** -- polling mode (not webhook), token-based
2. **Instagram Graph API** (Meta) -- via `graph.facebook.com/v18.0`, long-lived OAuth tokens
3. **Cloudinary** -- media uploads for Instagram API posting
4. **Google Drive API** -- media source provider, currently supports service account auth only (despite `UserCredentials` import, the `GoogleDriveService` only handles `service_account` type)

**Key Environment Variables** (from `settings.py` and `.env.example`):
- 6 DB vars, 3 Telegram vars, 4 Instagram vars, 3 Cloudinary vars, 1 encryption key, media/schedule/dev settings
- Total: ~30 environment variables

**Database Setup:**
- `scripts/setup_database.sql` (base schema with 8 tables)
- 13 migration files in `scripts/migrations/` (numbered 001-013)
- Requires `uuid-ossp` PostgreSQL extension
- No Alembic usage for migrations despite it being in requirements.txt

**Critical Gap for Cloud Deployment:**
- The `database_url` property in `settings.py` assembles a PostgreSQL URL without SSL support. Neon requires `sslmode=require` which is not currently configurable
- The `MEDIA_DIR` validator in `ConfigValidator` checks that the directory exists on the filesystem, which will fail on cloud platforms unless using Google Drive as the media source
- Logger writes to local `logs/` directory, which is fine for cloud but ephemeral
- No `DATABASE_URL` env var support (cloud platforms typically provide a single connection string)

---

## Detailed Implementation Plan

The deliverable is a single comprehensive Markdown document at `documentation/guides/cloud-deployment.md`. Below is the structure, content strategy, and sequencing.

### Step 1: Create the Document Skeleton

File: `/Users/chris/Projects/storyline-ai/documentation/guides/cloud-deployment.md`

The document should contain these major sections:

---

**Section 0: Prerequisites and Overview**
- What this guide covers (Neon DB + Railway/Render + all external service setup)
- Estimated time: 2-3 hours for complete setup
- Prerequisites: GitHub account, credit card for cloud services (free tiers available), existing Storyline AI codebase
- Architecture diagram showing cloud topology: GitHub repo -> Railway/Render -> Neon -> External APIs (Telegram, Instagram, Cloudinary, Google Drive)
- Table comparing Raspberry Pi deployment vs cloud deployment

**Section 1: Database Setup (Neon)**

Content to include:
- Creating a Neon account and project at `console.neon.tech`
- Creating a database named `storyline_ai` and user
- Neon connection string format: `postgresql://storyline_user:password@ep-xxx.region.neon.tech/storyline_ai?sslmode=require`
- **Code change required note**: The current `settings.py` assembles URLs from individual `DB_*` components. Document that for Neon, the individual components must be set to match the Neon connection string:
  - `DB_HOST=ep-xxx.region.neon.tech`
  - `DB_PORT=5432`
  - `DB_NAME=storyline_ai`
  - `DB_USER=storyline_user`
  - `DB_PASSWORD=neon_password`
- **SSL consideration**: Document that Neon requires SSL and note that `psycopg2-binary` supports this by default when Neon provides `?sslmode=require` but the current `database_url` property does NOT append sslmode. Recommend either:
  - (a) Adding a `DB_SSLMODE` env var to settings.py (code change, small), or
  - (b) Using SQLAlchemy connect_args: `create_engine(url, connect_args={"sslmode": "require"})` (code change in database.py)
  - Flag this as a prerequisite code change needed before cloud deployment
- Running schema setup: Connect via `psql` to Neon endpoint, run `setup_database.sql`
- Running all 13 migrations in order (list each file)
- Note: `uuid-ossp` extension -- Neon supports this, just run `CREATE EXTENSION IF NOT EXISTS "uuid-ossp";`
- Verification queries to confirm schema is correct
- Connection pool sizing note: Neon free tier allows 5 connections. The current `database.py` uses `pool_size=10, max_overflow=20` which is too aggressive. Document the need to reduce these for Neon free tier (another code consideration)

**Section 2: Application Deployment (Railway or Render)**

Content to include:
- **Railway option** (recommended for simplicity):
  - Connect GitHub repo
  - Set build command: `pip install -r requirements.txt && pip install -e .`
  - Set start command: `python -m src.main`
  - Railway uses `Nixpacks` by default for Python detection
  - No Dockerfile or Procfile needed (but recommend adding a `Procfile` for clarity: `worker: python -m src.main`)
  - Note: This is a **worker** process, not a web process. Railway and Render both support this but configuration differs
- **Render option** (alternative):
  - Create a "Background Worker" service (NOT a "Web Service")
  - Connect GitHub repo
  - Set build command and start command
  - Python version: specify 3.10+ (may need `runtime.txt` or Render's environment setting)
- **Environment Variable Configuration**: Full table of ALL environment variables with:
  - Variable name
  - Required/Optional
  - Description
  - Example value
  - Notes (e.g., "Get from Neon dashboard", "Get from BotFather")

Complete env var table (derived from `settings.py` and `.env.example`):

| Variable | Required | Description | Example |
|---|---|---|---|
| `ENABLE_INSTAGRAM_API` | No | Enable Instagram API automation | `false` |
| `DB_HOST` | Yes | Database hostname | `ep-cool-morning-123456.us-east-2.aws.neon.tech` |
| `DB_PORT` | No | Database port (default: 5432) | `5432` |
| `DB_NAME` | Yes | Database name | `storyline_ai` |
| `DB_USER` | Yes | Database user | `storyline_user` |
| `DB_PASSWORD` | Yes | Database password | `neon_generated_password` |
| `TELEGRAM_BOT_TOKEN` | Yes | Telegram bot token from BotFather | `123456:ABC-DEF...` |
| `TELEGRAM_CHANNEL_ID` | Yes | Telegram channel ID (negative) | `-1001234567890` |
| `ADMIN_TELEGRAM_CHAT_ID` | Yes | Admin's personal chat ID | `123456789` |
| `POSTS_PER_DAY` | No | Posts per day (default: 3) | `3` |
| `POSTING_HOURS_START` | No | Start hour UTC (default: 14) | `14` |
| `POSTING_HOURS_END` | No | End hour UTC (default: 2) | `2` |
| `REPOST_TTL_DAYS` | No | Days before repost (default: 30) | `30` |
| `MEDIA_DIR` | Yes* | Path to media directory | `/app/media` |
| `BACKUP_DIR` | No | Backup directory | `/tmp/backups` |
| `INSTAGRAM_ACCOUNT_ID` | Phase 2 | Instagram Business Account ID | `17841405793087218` |
| `INSTAGRAM_ACCESS_TOKEN` | Phase 2 | Initial long-lived token | `IGQV...` |
| `FACEBOOK_APP_ID` | Phase 2 | Meta Developer App ID | `1234567890123456` |
| `FACEBOOK_APP_SECRET` | Phase 2 | Meta Developer App Secret | `abc123...` |
| `INSTAGRAM_POSTS_PER_HOUR` | No | Rate limit (default: 25) | `25` |
| `CLOUDINARY_CLOUD_NAME` | Phase 2 | Cloudinary cloud name | `dxyz123` |
| `CLOUDINARY_API_KEY` | Phase 2 | Cloudinary API key | `123456789012345` |
| `CLOUDINARY_API_SECRET` | Phase 2 | Cloudinary API secret | `abc_secret...` |
| `CLOUD_UPLOAD_RETENTION_HOURS` | No | Cloud upload TTL (default: 24) | `24` |
| `ENCRYPTION_KEY` | Phase 2 | Fernet encryption key | `base64key...` |
| `MEDIA_SYNC_ENABLED` | No | Enable media sync (default: false) | `true` |
| `MEDIA_SYNC_INTERVAL_SECONDS` | No | Sync interval (default: 300) | `300` |
| `MEDIA_SOURCE_TYPE` | No | Media source type (default: local) | `google_drive` |
| `MEDIA_SOURCE_ROOT` | No | Root path or folder ID | `1BxiM...` |
| `DRY_RUN_MODE` | No | Prevent actual posting | `true` |
| `LOG_LEVEL` | No | Log level (default: INFO) | `INFO` |
| `SEND_LIFECYCLE_NOTIFICATIONS` | No | Startup/shutdown notifications | `true` |
| `INSTAGRAM_USERNAME` | No | Instagram username for deep links | `yourbrand` |
| `CAPTION_STYLE` | No | Caption style (default: enhanced) | `enhanced` |

- **MEDIA_DIR note**: On cloud platforms, local filesystem is ephemeral. Document two approaches:
  1. Use Google Drive as media source (`MEDIA_SOURCE_TYPE=google_drive`) -- recommended
  2. Create a dummy `MEDIA_DIR` path and use only cloud media sync
  3. Note that `ConfigValidator.validate_all()` checks `Path(settings.MEDIA_DIR).exists()` -- this must be a valid path. On Railway, `/app/media` can be created at build time

- **Health check endpoint**: Currently no HTTP endpoint exists (no FastAPI running). Document that Railway/Render may need a health check. Options:
  1. Railway: Can use process-based health (just checks if process is running)
  2. Render: Background workers don't need HTTP health checks
  3. Future: When FastAPI API layer is added, it will provide `/health`

- **Process management**: Signal handling is built-in (SIGTERM, SIGINT handlers in `main.py`). Railway and Render send SIGTERM on redeploy, which triggers graceful shutdown including Telegram shutdown notification

**Section 3: Domain and SSL**
- Railway provides `*.up.railway.app` domains with automatic SSL
- Render provides `*.onrender.com` domains with automatic SSL
- Custom domain setup for OAuth callbacks (needed for Instagram and Google OAuth redirect URIs)
- Note: Currently the system does NOT have OAuth callback endpoints -- tokens are obtained manually via Meta's Graph API Explorer and stored via CLI. So custom domain is NOT strictly required for current functionality
- Future-proof: When FastAPI OAuth callback endpoints are added, document the redirect URI format: `https://yourdomain.com/api/auth/instagram/callback` and `https://yourdomain.com/api/auth/google/callback`

**Section 4: Telegram Bot Setup**
- Reference the existing `documentation/guides/deployment.md` Section 1 (BotFather, channel creation, channel ID, admin chat ID)
- Add cloud-specific notes:
  - Polling mode works well for cloud deployment (no webhook setup needed)
  - If switching to webhook mode (future): need HTTPS URL, set webhook via `bot.setWebhook()`
  - Telegram bot commands registration via BotFather `/setcommands` -- list all 16 commands from CLAUDE.md

**Section 5: Instagram App Setup**
- Reference the existing `documentation/guides/instagram-api-setup.md` (Steps 1-12)
- Add cloud-specific notes:
  - OAuth redirect URI: If setting up OAuth flow in the future, configure redirect URI in Meta Developer Console to point to cloud domain
  - Required permissions: `pages_show_list`, `pages_read_engagement`, `instagram_basic`, `instagram_content_publish`, `business_management`
  - App review requirements for production: Document that without App Review, only users with roles (admins, developers, testers) on the Meta app can use the API. For a single-brand use case, this is fine
  - Token management: Initial token obtained via Graph API Explorer, then auto-refreshed by `TokenRefreshService`

**Section 6: Google Cloud Setup**
- Creating a Google Cloud project at `console.cloud.google.com`
- Enabling the Google Drive API
- For current functionality: Create a **Service Account** (not OAuth client), download JSON key
- Store credentials via `storyline-cli connect-google-drive` command
- The service account email must be shared with the Google Drive folder
- Future note: The `GoogleDriveProvider` accepts `UserCredentials` but the `GoogleDriveService.connect()` only supports `service_account` type. If OAuth is needed later, this will require code changes
- Document `MEDIA_SOURCE_TYPE=google_drive` and `MEDIA_SOURCE_ROOT=<drive_folder_id>` configuration

**Section 7: Cloudinary Setup**
- Create account at `cloudinary.com` (free tier: 25 credits/month, ~25GB storage)
- Get credentials from Dashboard: Cloud Name, API Key, API Secret
- No upload preset configuration needed -- the `CloudStorageService` uses direct API upload
- Set env vars: `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`
- Note on Cloudinary URL transformations: The `get_story_optimized_url()` method applies 9:16 transformations automatically

**Section 8: Monitoring and Operations**
- **Logs**: Railway and Render both provide log streaming in their dashboards. The app logs to stdout (via `setup_logger()` console handler), which is captured by both platforms
- **Database backups**: Neon provides automatic point-in-time recovery on paid plans. Free tier has limited retention
- **Service restart**: Via Railway/Render dashboard or CLI
- **Health monitoring**: Use `storyline-cli check-health` via Railway/Render CLI exec
- **Cost estimates**:
  - Neon Free: 0.5 GB storage, 190 hours/month compute -- adequate for single-tenant
  - Railway Starter: $5/month credit, ~$5-10/month for a Python worker
  - Render Free: Background workers require paid plan (~$7/month)
  - Cloudinary Free: 25 credits/month
  - Telegram Bot API: Free
  - Meta/Instagram API: Free (rate-limited)
  - Google Drive API: Free (quota-limited)
  - **Total estimated: $5-15/month**

**Section 9: Security Checklist**
- All secrets stored as environment variables (never in code or committed files)
- `ENCRYPTION_KEY` generated and set (for token encryption in database)
- Database password is strong and unique
- Telegram bot token is kept secret
- Instagram/Facebook app secret is kept secret
- Cloudinary API secret is kept secret
- Google service account key JSON is encrypted in database
- `.env` file is NOT committed (verified in `.gitignore`)
- SSL/TLS for all connections (Neon requires it, Telegram API is HTTPS, Instagram API is HTTPS)
- Database connection pool sizing appropriate for Neon tier

**Section 10: Troubleshooting**
- Common issues:
  1. Database connection fails: Check Neon endpoint is correct, SSL is enabled, connection pool not exceeded
  2. Telegram bot not responding: Check bot token, verify polling is running in logs
  3. `MEDIA_DIR does not exist`: Create the directory at build time or use Google Drive
  4. `ENCRYPTION_KEY not configured`: Generate one and add to env vars
  5. Service restarts frequently: Check memory limits on Railway/Render
  6. Database "idle in transaction": The app has built-in transaction cleanup (every 30 seconds)
  7. Neon connection limits exceeded: Reduce `pool_size` and `max_overflow` in `database.py`

**Section 11: Pre-Deployment Code Changes**
- Document the small code changes needed before cloud deployment:
  1. Add SSL support to database URL (either `DB_SSLMODE` env var or `connect_args`)
  2. Optionally support `DATABASE_URL` as a single connection string (standard for PaaS)
  3. Reduce default pool size for Neon compatibility (or make configurable via env var)
  4. Ensure `MEDIA_DIR` validation handles cloud scenarios (optional path or skip if using cloud media)
  5. Add `Procfile` for Railway/Render (`worker: python -m src.main`)

---

### Step 2: Update documentation/README.md

Add the new guide to the documentation index under "Getting Started Guides" section, with a brief description.

### Step 3: Update CHANGELOG.md

Add entry under `## [Unreleased]` with `### Added` section describing the new cloud deployment guide.

---

## Dependencies and Sequencing

1. The guide itself is purely documentation -- no code changes
2. However, the guide SHOULD document the prerequisite code changes needed (Section 11) as actionable items for a future PR
3. The guide references existing documentation (deployment.md, instagram-api-setup.md) rather than duplicating content
4. Cross-references to external docs (Neon, Railway, Render, Meta Developer, Google Cloud, Cloudinary) should use stable documentation URLs

## Potential Challenges

1. **Database URL format**: The current settings.py does not support Neon's SSL requirement. The guide must clearly call this out as a prerequisite code change, or provide a workaround (e.g., setting `DB_HOST` to include query params, which would be a hack)

2. **MEDIA_DIR validation**: `ConfigValidator.validate_all()` will fail on cloud platforms if `MEDIA_DIR` points to a non-existent path. The guide should recommend using Google Drive as the media source and creating a minimal local directory at build time

3. **No HTTP server**: Railway and Render typically expect web services with HTTP endpoints. The app is a long-running worker process. Both platforms support this but the setup differs from a typical web deployment

4. **Connection pooling**: Neon free tier has strict connection limits (5 concurrent). The current `pool_size=10, max_overflow=20` will cause connection errors. This must be addressed before deployment

## Critical Files for Implementation

- `/Users/chris/Projects/storyline-ai/documentation/guides/cloud-deployment.md` -- The new guide to be created (primary deliverable)
- `/Users/chris/Projects/storyline-ai/src/config/settings.py` -- Must be referenced extensively for the env var table; may need small changes for SSL support and DATABASE_URL
- `/Users/chris/Projects/storyline-ai/src/config/database.py` -- Connection pool settings and SSL configuration; needs adjustment for Neon compatibility
- `/Users/chris/Projects/storyline-ai/documentation/guides/deployment.md` -- Existing deployment guide to cross-reference (Telegram bot setup, systemd service pattern)
- `/Users/chris/Projects/storyline-ai/scripts/setup_database.sql` -- Schema setup that must be run against Neon; referenced in migration instructions
