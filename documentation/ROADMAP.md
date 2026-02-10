# Storyline AI - Product Roadmap

**Last Updated**: 2026-02-09
**Current Version**: v1.6.0 (Phase 2 Complete, Phase 1.8 Complete)
**Next Version**: TBD

---

## Vision

Build a delightful Instagram Story automation system that:
1. Manages a media library
2. Schedules posts intelligently
3. Minimizes manual effort
4. Maintains quality and engagement

---

## Phase 1: Telegram-Only Mode ✅ COMPLETE

**Status**: ✅ Released v1.0.1
**Duration**: November 2025 - January 2026
**Goal**: Manual posting workflow via Telegram notifications

### Delivered Features
- ✅ PostgreSQL database with full schema
- ✅ Media library management (scan, index, metadata)
- ✅ Smart scheduling system (distributes posts across posting window)
- ✅ TTL-based lock system (prevents reposting within 30 days)
- ✅ Telegram bot with interactive buttons (Posted/Skip)
- ✅ Queue management system
- ✅ History tracking with user attribution
- ✅ Team collaboration (multi-user support)
- ✅ CLI tools for management
- ✅ 147 comprehensive tests
- ✅ Raspberry Pi deployment with systemd service
- ✅ Production-ready with 4 critical bug fixes

**Outcome**: Fully functional Telegram-based workflow, 100% tested, deployed to production.

---

## Phase 1.5: Telegram Workflow Enhancements ✅ COMPLETE

**Status**: ✅ Released v1.3.0
**Branch**: `main`
**Duration**: January 2026 (2 weeks)
**Goal**: Make manual Telegram workflow as smooth as possible

### Priority 0: Critical Blocker ✅ COMPLETE

**REQUIRED FOR PRODUCTION USE**:
0. ✅ **Permanent Reject Button** - Infinite lock for unwanted media
   - Added "🚫 Reject" button to permanently block media
   - Prevents unwanted files from being queued again
   - Creates infinite TTL lock (NULL `locked_until`)
   - Logs rejection to history with user attribution
   - Fixed critical scheduler bug (was ignoring permanent locks)
   - **Production-ready - safe to run with real media folders**

### Week 1: Core Improvements ✅ COMPLETE

**Priority 1** (Must Have) - ✅ COMPLETE:
1. ✅ **Bot Lifecycle Notifications** - Startup/shutdown messages with system status
2. ✅ **Instagram Deep Links** - One-tap button to open Instagram app
3. ✅ **Enhanced Media Captions** - Clean workflow instructions (removed clutter)

**Priority 1.5** (Production Polish) - ✅ COMPLETE:
- ✅ **Button Layout Reorder** - Instagram button moved above Reject
- ✅ **Reject Confirmation** - Two-step confirmation prevents accidents
- ✅ **@None Username Bug Fix** - Display name fallback + username sync
- ✅ **`/queue` Fix** - Now shows all pending, not just due items
- ✅ **`/next` Command** - Force-send next scheduled post

### Week 2: Bot Management Commands ✅ COMPLETE (v1.3.0)

**Priority 2** (Operational Control) - ✅ COMPLETE:
- ✅ **`/pause`** - Pause automatic posting
- ✅ **`/resume`** - Resume with smart overdue handling (reschedule/clear/force)
- ✅ **`/schedule [N]`** - Create N days of posting schedule from Telegram
- ✅ **`/reset`** - Reset queue with confirmation dialog (originally `/clear`)

**Priority 3** (Information Commands) - ✅ COMPLETE:
- ✅ **`/stats`** - Media library statistics (active, posted, locked counts)
- ✅ **`/history [N]`** - Recent post history with user attribution
- ✅ **`/locks`** - View permanently rejected items

### Remaining Backlog - 📋 FUTURE

**Nice to Have** (Phase 1.5+):
- 📋 **Instagram Deep Link Redirect Service** - Direct link to story camera
- 📋 **Instagram Username Configuration** - Bot commands to set/view account
- 📋 **Inline Media Editing** - Edit title/caption/tags from Telegram
- 📋 **Quick Actions Menu** - `/menu` command with common operations
- 📋 **Enhanced `/stats` Dashboard** - Charts and visualizations
- 📋 **Smart Scheduling Hints** - Optimal posting times based on history

**Completed**: 2026-01-08

---

## Phase 1.6: Category-Based Scheduling ✅ COMPLETE

**Status**: ✅ Released v1.4.0
**Branch**: `main`
**Duration**: January 2026 (1 week)
**Goal**: Organize media by category with configurable posting ratios

### Delivered Features
- ✅ **Category Extraction** - Automatic category from folder structure
  - `media/stories/memes/` → category: `memes`
  - `media/stories/merch/` → category: `merch`
- ✅ **Posting Ratios** - Type 2 SCD for ratio configuration
  - Configurable ratios per category (e.g., 70% memes, 30% merch)
  - Full audit trail of ratio changes
  - Validation ensures ratios sum to 100%
- ✅ **Scheduler Integration** - Category-aware slot allocation
  - Proportional slot allocation based on ratios
  - Fallback to any category when target exhausted
  - Shuffled for variety
- ✅ **New CLI Commands**
  - `list-categories` - Show categories with ratios
  - `update-category-mix` - Interactive ratio configuration
  - `category-mix-history` - View ratio change history
- ✅ **268 comprehensive tests**

**Completed**: 2026-01-10

---

## Phase 2: Instagram API Automation ✅ COMPLETE

**Status**: ✅ Released v1.5.0+
**Branch**: `main`
**Duration**: January 2026
**Goal**: Fully automated posting via Instagram Graph API with hybrid mode

### Delivered Features

#### Core Instagram API Integration
- ✅ **Instagram Graph API Service** - Story creation and publishing
  - Media container status polling
  - Rate limit tracking (25 posts/hour default)
  - Error categorization and handling
  - Multi-account support

- ✅ **Cloudinary Integration** - Cloud media hosting
  - Automatic upload with TTL expiration
  - Public URL generation for Instagram API
  - Cleanup of expired media

- ✅ **Token Management** - OAuth token lifecycle
  - Encrypted token storage in database
  - Automatic token refresh (60-day expiry)
  - Token health monitoring
  - Per-account token management

#### Multi-Account Support
- ✅ **Instagram Accounts Table** - Multiple account identities
  - Display name, Instagram ID, username per account
  - Active/inactive status for soft deletion
  - Separation: identity vs credentials vs selection

- ✅ **Account Switching** - Per-chat active account selection
  - Switch accounts via Telegram /settings menu
  - Inline account selector in posting workflow
  - Auto-select when only one account exists

- ✅ **CLI Commands** - Account management
  - `add-instagram-account` - Register new account with token
  - `list-instagram-accounts` - Show all accounts
  - `deactivate-instagram-account` / `reactivate-instagram-account`

#### Hybrid Mode (Intelligent Routing)
- ✅ **Automatic + Manual Workflow** - Best of both worlds
  - `enable_instagram_api=true` enables API posting
  - "🤖 Auto Post to Instagram" button in notifications
  - Automatic fallback to Telegram on API errors
  - Graceful handling of rate limits and token expiry

- ✅ **Smart Fallback Logic**
  - Try Instagram API first
  - On error (RateLimitError, TokenExpiredError, InstagramAPIError) → Telegram
  - Manual override always available
  - All fallbacks logged for observability

#### Configuration & Safety
- ✅ **Feature Flags** - Per-chat settings in database
  - `enable_instagram_api` toggle (database, not .env)
  - `dry_run_mode` for testing without posting
  - Settings persist across restarts

- ✅ **Database Migrations**
  - `007_instagram_accounts.sql` - Accounts table
  - `008_api_tokens_account_fk.sql` - Token-account linking
  - `009_chat_settings_active_account.sql` - Per-chat selection
  - `004_instagram_api_phase2.sql` - API metadata columns

**Completed**: January 2026

---

## Phase 1.7: Inline Account Selector ✅ COMPLETE

**Status**: ✅ Delivered in v1.5.0
**Goal**: Add inline account selection to posting workflow

### Delivered Features
- ✅ **Inline Account Selector** - Switch accounts without leaving posting context
- ✅ **Redesigned Settings Flow** - Clearer account management in `/settings`
- ✅ **Visual Feedback** - Checkmark on active account, clear switching UX
- ✅ **Auto-Select** - Single account auto-selected

**Completed**: January 2026

---

## Phase 1.8: Telegram UX Improvements ✅ COMPLETE

**Status**: ✅ Released v1.6.0
**Goal**: Improve Telegram bot UX and code maintainability

### Delivered Features
- ✅ **TelegramService Refactor** - 3,500-line monolith decomposed into 5 handler modules
  - `telegram_commands.py` - Command handlers
  - `telegram_callbacks.py` - Button callback handlers
  - `telegram_autopost.py` - Auto-posting logic
  - `telegram_settings.py` - Settings UI handlers
  - `telegram_accounts.py` - Account selection handlers
- ✅ **Verbose Settings Expansion** - Toggle now controls more message types
- ✅ **`/cleanup` Command** - Delete recent bot messages (database-backed, queries last 48h of bot responses)
- ✅ **Command Menu Registration** - Native Telegram `/` autocomplete
- ✅ **Dry Run Bug Fix** - Fixed dry run not actually skipping Instagram API
- ✅ **Button Race Condition Fix** - Async locks prevent duplicate operations on same queue item
- ✅ **494 comprehensive tests** (351 passing, 143 skipped integration tests)

**Completed**: February 2026

---

## Phase 3: Advanced Features 🔮 FUTURE

**Status**: 🔮 Exploratory
**Timeframe**: Q2 2026 and beyond

### Under Consideration

**Analytics & Insights**:
- Story view tracking
- Engagement metrics
- Performance reports
- A/B testing framework

**Content Intelligence**:
- AI-powered caption suggestions
- Optimal posting time predictions
- Content categorization
- Tag recommendations

**Multi-Platform Support**:
- TikTok integration
- YouTube Shorts
- Twitter/X posts
- Cross-platform scheduling

**Advanced Scheduling**:
- Seasonal campaigns
- Event-based triggers
- Weather-based content
- Trending topic integration

**Team Features**:
- Role-based permissions
- Approval workflows
- Content calendar view
- Collaboration tools

---

## Backlog & Future Enhancements

### High Priority
- [ ] **Instagram Story Camera Deep Link** (Phase 1.5+)
  - Self-hosted redirect service for true deep linking
  - GitHub Pages or Vercel hosting
  - Alternative to URLgenius/Branch.io (security concerns)
  - ~1 hour setup time
  - Nice-to-have, not critical

### Medium Priority
- [ ] Web dashboard for queue management
- [ ] Backup/restore automation
- [x] Multi-account support ✅ (Completed in Phase 2)
- [ ] Content templates system
- [ ] Bulk media import tools

### Low Priority
- [ ] Desktop app (Electron)
- [ ] Browser extension
- [ ] Mobile app (React Native)
- [ ] API for third-party integrations

### Research Items
- [ ] Instagram API limitations and best practices
- [ ] Story analytics extraction methods
- [ ] AI/ML for content optimization
- [ ] Compliance with platform policies

---

## Version History

| Version | Date | Phase | Description |
|---------|------|-------|-------------|
| v1.6.0 | 2026-02-09 | Phase 1.5-1.8 | Instagram account management, inline account selector, TelegramService refactor, verbose expansion, /cleanup |
| v1.5.0 | 2026-01-24 | Phase 2 | Instagram API automation + Multi-account support |
| v1.4.0 | 2026-01-10 | Phase 1.6 | Category-based scheduling with configurable ratios |
| v1.3.0 | 2026-01-08 | Phase 1.5 | Bot management commands (/pause, /resume, /stats, etc.) |
| v1.2.0 | 2026-01-05 | Phase 1.5 | Telegram workflow enhancements + Permanent Reject |
| v1.0.1 | 2026-01-04 | Phase 1 | Production release with bug fixes |
| v1.0.0 | 2025-12-XX | Phase 1 | Initial Telegram-only implementation |

---

## Decision Log

### 2026-01-27: Telegram Command Menu Registration + /cleanup Command
**Decision**: Implement native Telegram command autocomplete and bot message cleanup
**Features Added**:
- `set_my_commands()` registration for native "/" menu in Telegram
- `/cleanup` command to delete recent bot messages (uses `InteractionService.get_deletable_bot_messages()` to query bot responses from the last 48 hours via the database)
- Renamed `/clear` → `/reset` for semantic clarity
**Rationale**:
- Command discovery through native Telegram UI improves UX significantly
- Users can clean up verbose bot messages (queue lists, status reports)
- Clear semantic distinction: "reset" = start over, "cleanup" = tidy up
- CLI aligned: `storyline-cli reset-queue` matches Telegram's `/reset`
**Status**: ✅ COMPLETE - Ready for testing

### 2026-01-24: Phase 2 Complete - Instagram API Automation + Multi-Account
**Decision**: Fully implement Instagram Graph API automation with hybrid mode
**Features Delivered**:
- Instagram API service with rate limiting and error handling
- Cloudinary integration for media hosting
- Encrypted token management with auto-refresh
- Multi-account support (add/switch/deactivate via Telegram)
- Hybrid mode: auto-post via API with fallback to manual Telegram workflow
- Per-chat settings (enable_instagram_api toggle in database)
**Rationale**:
- Reduces manual posting burden while maintaining quality control
- Graceful fallback ensures posts never lost
- Multi-account enables managing multiple Instagram business accounts
- Database-driven settings enable per-chat configuration
**Status**: ✅ COMPLETE - Phase 2 fully operational

### 2026-01-10: Category-Based Scheduling Added (Phase 1.6)
**Decision**: Implement category-based media organization with configurable posting ratios
**Features Added**:
- Folder structure → category extraction during indexing
- Type 2 SCD table for posting ratio configuration
- Category-aware scheduler slot allocation
- 3 new CLI commands for category management
**Rationale**:
- Media naturally organizes by type (memes, merch, quotes, etc.)
- Different content types need different posting frequencies
- Type 2 SCD provides full audit trail of ratio changes
- Enables business rules like "70% memes, 30% merchandise"
**Status**: ✅ COMPLETE - 95 new tests, 268 total

### 2026-01-08: Bot Management Commands Added
**Decision**: Implement comprehensive Telegram bot commands for queue/system management
**Features Added**:
- `/pause` and `/resume` for operational control
- `/schedule`, `/reset` for queue management (originally `/clear`, renamed in v1.6.0)
- `/stats`, `/history`, `/locks` for visibility
**Rationale**:
- Reduces need for SSH access to Raspberry Pi
- Enables team members to manage posting schedule
- Smart overdue handling prevents post flooding after pause
- All operations logged for audit trail
**Status**: ✅ COMPLETE - All 7 commands implemented with 26 new tests

### 2026-01-05: Permanent Reject Feature Implemented
**Decision**: Add "Permanent Reject" as Priority 0 blocker before other Phase 1.5 work
**Rationale**:
- User has mixed media folders (some files should NEVER be posted)
- Current "Skip" button doesn't prevent media from being queued again
- Can't safely run system in production without way to permanently block files
- Blocks actual usage and testing of the system
- Simple implementation (2-3 hours), high value
**Status**: ✅ COMPLETE - Implemented with infinite TTL locks (NULL locked_until)

### 2026-01-04: Instagram Deep Link Strategy
**Decision**: Keep simple `https://www.instagram.com/` link for now
**Rationale**:
- URLgenius flagged as phishing by Phantom wallet
- Current solution works and saves time
- Workflow instructions guide users effectively
- Can revisit with self-hosted solution later
**Status**: Added to backlog as future enhancement

### 2025-12-XX: Two-Phase Approach
**Decision**: Build Telegram-only mode first (Phase 1), Instagram API second (Phase 2)
**Rationale**:
- Faster time to value
- Test workflow before automation
- Avoid Instagram API complexity initially
- Manual mode is valuable on its own

---

## Contributing to the Roadmap

Have ideas for features? Want to prioritize something?

1. Open an issue on GitHub with the `enhancement` label
2. Describe the problem you're solving
3. Propose a solution
4. Discuss trade-offs and implementation

All roadmap items are subject to change based on:
- User feedback
- Technical constraints
- Platform policy changes
- Time and resource availability

---

**Questions?** Open an issue or start a discussion!
