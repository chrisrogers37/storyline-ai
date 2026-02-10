# Storyline AI Documentation

Welcome to the Storyline AI documentation hub. All project documentation is organized here by purpose.

**Last Updated**: 2026-02-09
**Current Version**: v1.6.0
**Current Phase**: Phase 2 (Instagram API Automation) - ✅ COMPLETE | Phase 1.8 (Telegram UX) - ✅ COMPLETE

## 📁 Documentation Structure

```
documentation/
├── README.md (this file)          # Documentation index
├── ROADMAP.md                     # Product roadmap and version history
├── planning/                       # Planning and design documents
├── guides/                         # How-to guides and tutorials
├── operations/                     # Operational runbooks
├── updates/                        # Project updates, bugfixes, patches
├── archive/                        # Completed/obsolete documents
└── api/                            # API documentation (Phase 5)
```

---

## 📋 Planning & Architecture

### Master Roadmap
**[phases/00_MASTER_ROADMAP.md](planning/phases/00_MASTER_ROADMAP.md)** - ✅ Phases 1-2.5 Complete
- Vision and long-term architecture
- Phase overview with status markers
- Service naming conventions and data model strategy
- Data flow diagrams (current and future)

### Phase Planning Documents

**[phases/01_settings_and_multitenancy.md](planning/phases/01_settings_and_multitenancy.md)** - ✅ Phases 1-1.5 Complete
- Database-backed settings management
- Multi-Instagram account management
- Full implementation details (models, repos, services, CLI, tests)
- Future: Cloud Media Storage (Phase 2), Multi-Tenancy (Phase 3)

**[phases/02_shopify_integration.md](planning/phases/02_shopify_integration.md)** - 📋 PLANNED
**[phases/03_printify_integration.md](planning/phases/03_printify_integration.md)** - 📋 PLANNED
**[phases/04_media_product_linking.md](planning/phases/04_media_product_linking.md)** - 📋 PLANNED
**[phases/05_llm_integration.md](planning/phases/05_llm_integration.md)** - 📋 PLANNED
**[phases/06_order_email_automation.md](planning/phases/06_order_email_automation.md)** - 📋 PLANNED
**[phases/07_dashboard_ui.md](planning/phases/07_dashboard_ui.md)** - 📋 PLANNED

### Completed Feature Designs

**[telegram-service-refactor-plan.md](planning/telegram-service-refactor-plan.md)** - ✅ COMPLETE
- Decomposition of 3,500-line TelegramService monolith into 5 handler modules
- Composition-based architecture, 3-PR migration strategy
- All PRs merged

**[phase-1.7-inline-account-selector.md](planning/phase-1.7-inline-account-selector.md)** - ✅ COMPLETE (v1.5.0)
- Inline account selection in posting workflow
- Account switching without leaving posting context

**[verbose-settings-improvement-plan.md](planning/verbose-settings-improvement-plan.md)** - ✅ COMPLETE
- Expanded scope of verbose notifications toggle
- `_is_verbose()` helper method, bug fixes

**[phases/user-interactions-design.md](planning/phases/user-interactions-design.md)** - ✅ COMPLETE
- User interaction tracking (InteractionService)
- Command/callback logging, bot response tracking, analytics

### Test Coverage Report
**[TEST_COVERAGE.md](guides/TEST_COVERAGE.md)** - ✅ CURRENT (488 tests)
- Test suite summary by layer
- Phase 1.6 through Phase 2 test additions
- Coverage gaps and future work
- Test infrastructure documentation

### Other Planning Documents

**[01B_telegram_mini_app_secure_input.md](planning/01B_telegram_mini_app_secure_input.md)** - 📋 PLANNED (Future)
- Telegram Mini App for secure credential input
- Decision: proceed with message-based approach for now

---

## 🚀 Getting Started Guides

### Quick Start (10 Minutes)
**[quickstart.md](guides/quickstart.md)**
- Fastest path to running the application
- Step-by-step setup instructions
- Essential commands
- Troubleshooting common issues

### Deployment Guide
**[deployment.md](guides/deployment.md)**
- Complete deployment checklist for Phase 1
- Telegram bot setup (detailed)
- Database configuration
- Raspberry Pi deployment
- System service setup
- Team onboarding
- Production launch steps

### Testing Guide
**[testing-guide.md](guides/testing-guide.md)**
- Automatic test database setup and fixture architecture
- Running tests (unit, integration, coverage)
- Writing new tests (488 tests as of v1.6.0)
- Test fixtures and patterns
- CI/CD integration
- Troubleshooting test failures

### Instagram API Setup
**[instagram-api-setup.md](guides/instagram-api-setup.md)**
- Meta Business Suite and developer app setup
- Instagram Graph API token generation
- Cloudinary integration
- Multi-account management via CLI
- Token bootstrapping and troubleshooting

### Development Environment Setup
**[dev-environment-setup.md](guides/dev-environment-setup.md)**
- Mac ↔ Raspberry Pi workflow optimization
- Shell aliases for both environments
- Database permission setup
- Deployment scripts and rsync shortcuts
- Quick reference command card

---

## 🛠 Operations & Maintenance

### Monitoring & Alerting
**[operations/monitoring.md](operations/monitoring.md)**
- Service health checks
- Key metrics to monitor (queue, posting rate, tokens)
- Alerting thresholds
- Log analysis

### Backup & Restore
**[operations/backup-restore.md](operations/backup-restore.md)**
- Database backup procedures (manual & automated)
- Media files backup
- Configuration backup
- Disaster recovery steps

### Troubleshooting
**[operations/troubleshooting.md](operations/troubleshooting.md)**
- Common issues and fixes
- Service won't start
- Posts not going out
- Telegram bot not responding
- Token refresh failures
- Emergency procedures

---

## 🔄 Project Updates

### Feature Updates
**[2026-01-11-force-posting-queue-shift.md](updates/2026-01-11-force-posting-queue-shift.md)**
- Force posting implementation
- Queue shift behavior on manual posts

**[2026-01-10-category-scheduling.md](updates/2026-01-10-category-scheduling.md)**
- Category-based media organization (folder → category extraction)
- Configurable posting ratios per category (Type 2 SCD)
- Scheduler integration with category-aware slot allocation
- New CLI commands: `list-categories`, `update-category-mix`, `category-mix-history`

### Bug Fixes & Patches
**[2026-01-04-bugfixes.md](updates/2026-01-04-bugfixes.md)**
- 4 critical bugs fixed (service run metadata, scheduler date mutation, health check, lock creation)
- All bugs identified during code review and deployment testing
- Production verified and tested

*Note: Updates folder contains dated documents for bug fixes, patches, and significant changes.*
*Historical handoffs have been moved to `archive/`.*

---

## 📚 API Documentation

Coming in Phase 5:
- REST API endpoints
- Authentication flows
- Rate limiting
- WebSocket events
- SDK documentation

---

## 📦 Archive

Completed and historical documents (see [archive/ARCHIVE_INDEX.md](archive/ARCHIVE_INDEX.md) for full list):

**[archive/IMPLEMENTATION_COMPLETE.md](archive/IMPLEMENTATION_COMPLETE.md)** - ✅ Phase 1 Complete (v1.0.1)
**[archive/HANDOFF-2026-01-05.md](archive/HANDOFF-2026-01-05.md)** - ✅ v1.2.0 deployment handoff
**[archive/upcoming_build_notes.md](archive/upcoming_build_notes.md)** - ✅ All features implemented
**[archive/phase-1.5-telegram-enhancements.md](archive/phase-1.5-telegram-enhancements.md)** - ✅ Phase 1.5 Complete (v1.3.0)
**[archive/instagram_automation_plan.md](archive/instagram_automation_plan.md)** - 📋 Reference (superseded by phases/ docs)
**[archive/01_instagram_api.md](archive/01_instagram_api.md)** - ✅ Phase 2 Complete (v1.5.0)

---

## 🔍 Quick Reference

### For New Developers
1. Start with **[quickstart.md](guides/quickstart.md)** (10 min setup)
2. Read **[testing-guide.md](guides/testing-guide.md)** (understand testing)
3. Review **[phases/00_MASTER_ROADMAP.md](planning/phases/00_MASTER_ROADMAP.md)** (architecture and roadmap)

### For Deploying to Production
1. Follow **[deployment.md](guides/deployment.md)** step-by-step
2. Complete Telegram bot setup (Section 1)
3. Configure database (Section 2)
4. Deploy and test (Sections 5-11)
5. For Instagram API: **[instagram-api-setup.md](guides/instagram-api-setup.md)**

### For Understanding Architecture
1. Check **[phases/00_MASTER_ROADMAP.md](planning/phases/00_MASTER_ROADMAP.md)**
   - See architecture principles and data flow diagrams
   - Review service naming conventions
   - Understand phase progression
2. Read root **[CLAUDE.md](../CLAUDE.md)** for detailed service/model reference

### For Contributing Code
1. Read root **[CLAUDE.md](../CLAUDE.md)** (development guidelines, pre-commit checklist)
2. Review **[testing-guide.md](guides/testing-guide.md)** (test requirements)
3. Check **[phases/00_MASTER_ROADMAP.md](planning/phases/00_MASTER_ROADMAP.md)** for context

---

## 📖 Additional Resources

### Root-Level Documentation
These critical files remain in the project root for visibility:

- **[../README.md](../README.md)** - Project overview and quick start
- **[../CHANGELOG.md](../CHANGELOG.md)** - Version history and release notes
- **[../CLAUDE.md](../CLAUDE.md)** - Developer guide for AI assistants
- **../LICENSE** - Project license (if applicable)

### External Documentation
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Instagram Graph API](https://developers.facebook.com/docs/instagram-api) (Phase 2)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Python Telegram Bot](https://python-telegram-bot.readthedocs.io/)

---

## 🤝 Contributing Documentation

When adding new documentation:

1. **Choose the right location:**
   - Planning/design → `planning/`
   - How-to guides → `guides/`
   - Operations → `operations/`
   - API docs → `api/`

2. **Update this index** (`documentation/README.md`)

3. **Follow naming conventions:**
   - Use lowercase with hyphens: `backup-restore.md`
   - Be descriptive: ✅ `telegram-bot-setup.md` ❌ `setup.md`

4. **Keep root-level clean:**
   - Only critical files in project root
   - Everything else goes in `documentation/`

---

## 📊 Documentation Coverage

Current documentation status:

| Area | Status | Files | Notes |
|------|--------|-------|-------|
| **Planning** | ✅ Current | 12 files | Phases 1-2.5 complete, 3-8 planned |
| **Getting Started** | ✅ Current | 6 guides | Setup, deployment, testing, Instagram API |
| **Testing** | ✅ Current | 1 guide | 488 tests documented |
| **Updates** | ✅ Current | 3 files | Bugfixes, features |
| **Archive** | ✅ Organized | 7 files | Historical docs preserved |
| **Operations** | ✅ Current | 3 files | Monitoring, backup, troubleshooting |
| **Security** | ✅ Current | 1 file | Security review completed |
| **API Docs** | ⏳ Future | 0 files | Future: REST API |

### Document Status Legend
- ✅ **COMPLETE** - Fully implemented and documented
- 🚧 **WIP** - Work in progress
- 📋 **PENDING** - Planned for future implementation
- ⏳ **FUTURE** - Scheduled for later phases

---

## 🆘 Need Help?

- **Setup issues?** → See [quickstart.md](guides/quickstart.md) troubleshooting
- **Deployment questions?** → Check [deployment.md](guides/deployment.md)
- **Test failures?** → Review [testing-guide.md](guides/testing-guide.md)
- **Architecture questions?** → Read [phases/00_MASTER_ROADMAP.md](planning/phases/00_MASTER_ROADMAP.md)
- **Version history?** → Check [ROADMAP.md](ROADMAP.md)
- **Instagram API setup?** → Follow [instagram-api-setup.md](guides/instagram-api-setup.md)
- **Security concerns?** → Review [SECURITY_REVIEW.md](SECURITY_REVIEW.md)

---

*Last updated: 2026-02-09*
