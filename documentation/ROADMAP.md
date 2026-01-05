# Storyline AI - Product Roadmap

**Last Updated**: 2026-01-05
**Current Version**: v1.2.0
**Current Phase**: Phase 1.5 (Telegram Enhancements) - ✅ COMPLETE

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

**Status**: ✅ Released v1.2.0
**Branch**: `feature/phase-1-5-enhancements`
**Duration**: January 2026 (1 week)
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

**Priority 2** (Should Have) - 📋 BACKLOG:
4. 📋 **Instagram Deep Link Redirect Service** - Direct link to story camera (optional)
   - Moved to backlog due to security concerns with URLgenius
   - Self-hosted solution documented as future enhancement
5. 📋 **Instagram Username Configuration** - Bot commands to set/view account
   - Moved to backlog - not critical for current workflow

### Week 2: Quality of Life - 📋 BACKLOG

**Priority 3** (Nice to Have):
6. 📋 **Inline Media Editing** - Edit title/caption/tags from Telegram
7. 📋 **Quick Actions Menu** - `/menu` command with common operations
8. 📋 **Posting Stats Dashboard** - Enhanced `/stats` with charts

**Priority 4** (Future):
9. 📋 **Smart Scheduling Hints** - Optimal posting times based on history

**Completed**: 2026-01-05

---

## Phase 2: Instagram API Automation 📅 PLANNED

**Status**: 📅 Not Started
**Estimated Start**: February 2026
**Duration**: 3-4 weeks
**Goal**: Fully automated posting via Instagram Graph API

### Scope
- Instagram Graph API integration
- OAuth flow for account linking
- Automated story publishing
- Media hosting (Cloudinary or similar)
- Fallback to manual mode if API fails
- Error handling and retry logic
- API rate limit management

### Prerequisites
- Instagram Business Account
- Facebook Developer App
- Cloudinary account (or alternative CDN)
- Graph API access tokens

### Configuration
- Add `ENABLE_INSTAGRAM_API=true` flag
- Hybrid mode: Try API first, fallback to Telegram

**Target Completion**: March 2026

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
- [ ] Multi-account support
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
| v1.2.0 | 2026-01-05 | Phase 1.5 | Telegram workflow enhancements + Permanent Reject |
| v1.0.1 | 2026-01-04 | Phase 1 | Production release with bug fixes |
| v1.0.0 | 2025-12-XX | Phase 1 | Initial Telegram-only implementation |
| v2.0.0 | TBD | Phase 2 | Instagram API automation |

---

## Decision Log

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
