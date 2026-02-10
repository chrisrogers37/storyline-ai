# Storyline AI Documentation

Welcome to the Storyline AI documentation hub. All project documentation is organized here by purpose.

**Last Updated**: 2026-02-10
**Current Version**: v1.6.0
**Current Phase**: Phase 2 (Instagram API Automation) - COMPLETED | Phase 1.8 (Telegram UX) - COMPLETED
**Next Phase**: Phase 3 (Shopify Integration) - PENDING

## Documentation Structure

```
documentation/
├── README.md (this file)          # Documentation index
├── ROADMAP.md                     # Product roadmap and version history
├── SECURITY_REVIEW.md             # Security audit findings
├── planning/                       # Planning and design documents
│   ├── phases/                    # Phased implementation plans
│   │   ├── 00_MASTER_ROADMAP.md   # Vision, architecture, phase overview
│   │   ├── 01_settings_and_multitenancy.md  # COMPLETED (Phases 1-1.5)
│   │   ├── 02_shopify_integration.md        # PENDING
│   │   ├── 03_printify_integration.md       # PENDING
│   │   ├── 04_media_product_linking.md      # PENDING
│   │   ├── 05_llm_integration.md            # PENDING
│   │   ├── 06_order_email_automation.md     # PENDING
│   │   └── 07_dashboard_ui.md              # PENDING
│   └── 01B_telegram_mini_app_secure_input.md  # PENDING (Future)
├── guides/                         # How-to guides and tutorials
├── operations/                     # Operational runbooks
├── updates/                        # Project updates, bugfixes, patches
└── archive/                        # Completed/obsolete documents
```

---

## Planning & Architecture

### Master Roadmap
**[phases/00_MASTER_ROADMAP.md](planning/phases/00_MASTER_ROADMAP.md)** - Phases 1-2.5 COMPLETED
- Vision: E-commerce Optimization Hub for Social Media Marketing
- Architecture principles (strict separation of concerns)
- Service naming conventions and data model strategy
- Data flow diagrams (current Phase 2 and future Phase 5+)
- Phase overview with status markers (8 phases total, 5 completed, 6 pending)

### Active Phase Planning Documents

**[phases/01_settings_and_multitenancy.md](planning/phases/01_settings_and_multitenancy.md)** - Phases 1-1.5 COMPLETED | Phases 2-3 PENDING
- Phase 1: Database-backed settings via `/settings` command (COMPLETED)
- Phase 1.5: Multi-Instagram account management (COMPLETED)
- Phase 2: Cloud Media Storage (PENDING)
- Phase 3: Multi-Tenancy with full isolation (PENDING)

**[phases/02_shopify_integration.md](planning/phases/02_shopify_integration.md)** - PENDING
- Shopify Admin API integration, product catalog sync (Type 2 SCD), order tracking

**[phases/03_printify_integration.md](planning/phases/03_printify_integration.md)** - PENDING
- Printify API for print-on-demand, product/blueprint sync, fulfillment tracking

**[phases/04_media_product_linking.md](planning/phases/04_media_product_linking.md)** - PENDING
- Many-to-many media-product relationships, attribution tracking, performance analytics

**[phases/05_llm_integration.md](planning/phases/05_llm_integration.md)** - PENDING
- LLM service abstraction (Claude/OpenAI), content suggestions, email drafting

**[phases/06_order_email_automation.md](planning/phases/06_order_email_automation.md)** - PENDING
- Order notifications via Telegram, Gmail API, LLM-drafted customer responses

**[phases/07_dashboard_ui.md](planning/phases/07_dashboard_ui.md)** - PENDING
- Next.js web dashboard, analytics visualizations, media-product management

### Other Planning Documents

**[01B_telegram_mini_app_secure_input.md](planning/01B_telegram_mini_app_secure_input.md)** - PENDING (Future)
- Telegram Mini App for secure credential input (replaces message-based token entry)
- Decision: proceed with message-based approach for now

### Test Coverage Report
**[TEST_COVERAGE.md](guides/TEST_COVERAGE.md)** - CURRENT (494 tests)
- Test suite summary by layer (36 test files)
- Phase 1.6 through Phase 2 test additions
- Coverage gaps and future work
- Test infrastructure documentation

---

## Getting Started Guides

### Quick Start (10 Minutes)
**[quickstart.md](guides/quickstart.md)**
- Fastest path to running the application
- Step-by-step setup: clone, venv, database, configure, index media, run
- Essential CLI and Telegram bot commands
- Troubleshooting common issues

### Deployment Guide
**[deployment.md](guides/deployment.md)**
- 12-section deployment checklist for production
- Telegram bot setup (BotFather, channel, admin ID)
- PostgreSQL database configuration
- Raspberry Pi systemd service setup
- Media indexing and schedule creation
- Team onboarding, backups, monitoring

### Testing Guide
**[testing-guide.md](guides/testing-guide.md)**
- Automatic test database setup and fixture architecture
- Running tests: `make test`, `make test-unit`, `pytest` with markers
- 494 tests (351 passing, 143 skipped integration tests) as of v1.6.0
- Test fixtures and patterns (session-scoped DB, function-scoped transactions)
- CI/CD integration (GitHub Actions)

### Instagram API Setup
**[instagram-api-setup.md](guides/instagram-api-setup.md)**
- Meta Business Suite and developer app setup (12 steps)
- Instagram Graph API token generation and extension
- Cloudinary integration for media hosting
- Multi-account management via CLI commands
- Token bootstrapping (.env to DB), encryption, and troubleshooting

### Development Environment Setup
**[dev-environment-setup.md](guides/dev-environment-setup.md)**
- Mac to Raspberry Pi workflow optimization
- Shell aliases for both environments
- Database permission setup (CREATEDB for test user)
- `scripts/deploy.sh` usage and deployment workflow
- Quick reference command card

### Deployment Options
**[deployment-options.md](guides/deployment-options.md)**
- Why manual deployment (public repo security)
- `scripts/deploy.sh` workflow (test, push, SSH, pull, restart)
- GitHub Actions CI (lint, test, security scan on cloud runners)

### GitHub Actions + Tailscale (Advanced)
**[github-actions-tailscale.md](guides/github-actions-tailscale.md)**
- Automated deployment via Tailscale VPN (documented, not yet active)
- Setup guide for Tailscale on Pi + GitHub Actions workflow

---

## Operations & Maintenance

### Monitoring & Alerting
**[operations/monitoring.md](operations/monitoring.md)**
- systemd service health checks via SSH
- SQL queries for queue health, posting rate, token expiry
- Alerting thresholds (stuck posts, token expiry, error rate)
- Health check script for cron

### Backup & Restore
**[operations/backup-restore.md](operations/backup-restore.md)**
- Database backup procedures (manual via `pg_dump`, automated via cron)
- Media files backup (rsync to external storage)
- Configuration backup (.env, tokens)
- Disaster recovery steps

### Troubleshooting
**[operations/troubleshooting.md](operations/troubleshooting.md)**
- Service won't start (common causes, log inspection)
- Posts not going out (queue, scheduling, dry-run check)
- Telegram bot not responding (token, webhook, permissions)
- Instagram API errors (rate limits, token expiry, account selection)
- Media indexing failures (paths, permissions, formats)
- Emergency procedures (service restart, queue reset)

---

## Project Updates

### Feature Updates
**[2026-01-11-force-posting-queue-shift.md](updates/2026-01-11-force-posting-queue-shift.md)** - COMPLETED
- Force posting via `/next` and `process-queue --force`
- Queue slot-shift logic (subsequent items inherit earlier time slots)

**[2026-01-10-category-scheduling.md](updates/2026-01-10-category-scheduling.md)** - COMPLETED
- Category-based media organization (folder to category extraction)
- Configurable posting ratios per category (Type 2 SCD)
- Scheduler integration with category-aware slot allocation
- New CLI commands: `list-categories`, `update-category-mix`, `category-mix-history`

### Bug Fixes & Patches
**[2026-01-04-bugfixes.md](updates/2026-01-04-bugfixes.md)** - COMPLETED
- 4 critical bugs fixed (service run metadata, scheduler date mutation, health check, lock creation)
- All bugs identified during code review and deployment testing

*Note: Updates folder contains dated documents for bug fixes, patches, and significant changes.*
*Historical handoffs have been moved to `archive/`.*
*Line numbers in older updates reference pre-refactor code (v1.6.0 refactored TelegramService).*

---

## Security

**[SECURITY_REVIEW.md](SECURITY_REVIEW.md)** - Reviewed 2026-01-11, Updated 2026-02-10
- No hardcoded credentials found
- `.env` properly gitignored, all secrets via environment variables
- Collaborative bot design (intentional, private channel = security boundary)
- Token encryption (Fernet) for Instagram API credentials in database
- Cloning the repo exposes zero credentials
- Optional admin-only command pattern documented

---

## API Documentation

Coming in Phase 5 (Dashboard UI):
- REST API endpoints (FastAPI)
- Authentication flows (JWT via Telegram Login Widget)
- Rate limiting
- WebSocket events
- SDK documentation

---

## Archive

Completed and historical documents (see [archive/ARCHIVE_INDEX.md](archive/ARCHIVE_INDEX.md) for full list):

| Document | Status | Description |
|----------|--------|-------------|
| [IMPLEMENTATION_COMPLETE.md](archive/IMPLEMENTATION_COMPLETE.md) | COMPLETED | Phase 1 completion checklist (v1.0.1) |
| [HANDOFF-2026-01-05.md](archive/HANDOFF-2026-01-05.md) | COMPLETED | v1.2.0 deployment handoff |
| [upcoming_build_notes.md](archive/upcoming_build_notes.md) | COMPLETED | Feature brainstorming (all implemented) |
| [phase-1.5-telegram-enhancements.md](archive/phase-1.5-telegram-enhancements.md) | COMPLETED | Phase 1.5 planning (v1.3.0) |
| [instagram_automation_plan.md](archive/instagram_automation_plan.md) | Superseded | Original plan, replaced by phases/ docs |
| [01_instagram_api.md](archive/01_instagram_api.md) | COMPLETED | Phase 2 Instagram API (v1.5.0) |
| [telegram-service-refactor-plan.md](archive/telegram-service-refactor-plan.md) | COMPLETED | TelegramService decomposition (v1.6.0) |
| [verbose-settings-improvement-plan.md](archive/verbose-settings-improvement-plan.md) | COMPLETED | Verbose notifications expansion (v1.6.0) |
| [phase-1.7-inline-account-selector.md](archive/phase-1.7-inline-account-selector.md) | COMPLETED | Inline account selection (v1.5.0) |
| [user-interactions-design.md](archive/user-interactions-design.md) | COMPLETED | InteractionService design (v1.4.0) |

---

## Quick Reference

### For New Developers
1. Start with **[quickstart.md](guides/quickstart.md)** (10 min setup)
2. Read **[testing-guide.md](guides/testing-guide.md)** (understand testing)
3. Review **[phases/00_MASTER_ROADMAP.md](planning/phases/00_MASTER_ROADMAP.md)** (architecture and roadmap)
4. Read root **[CLAUDE.md](../CLAUDE.md)** for detailed service/model reference and safety rules

### For Deploying to Production
1. Follow **[deployment.md](guides/deployment.md)** step-by-step
2. Complete Telegram bot setup (Section 1)
3. Configure database (Section 2)
4. Deploy and test (Sections 5-11)
5. For Instagram API: **[instagram-api-setup.md](guides/instagram-api-setup.md)**
6. For ongoing deploys: `./scripts/deploy.sh` (see **[deployment-options.md](guides/deployment-options.md)**)

### For Understanding Architecture
1. Check **[phases/00_MASTER_ROADMAP.md](planning/phases/00_MASTER_ROADMAP.md)**
   - Architecture principles and data flow diagrams
   - Service naming conventions (core/, integrations/, domain/)
   - Phase progression and dependencies
2. Read root **[CLAUDE.md](../CLAUDE.md)** for service/model/table reference

### For Contributing Code
1. Read root **[CLAUDE.md](../CLAUDE.md)** (development guidelines, pre-commit checklist)
2. Review **[testing-guide.md](guides/testing-guide.md)** (test requirements — every feature needs tests)
3. Check **[phases/00_MASTER_ROADMAP.md](planning/phases/00_MASTER_ROADMAP.md)** for context
4. Run pre-commit: `source venv/bin/activate && ruff check src/ tests/ && ruff format --check src/ tests/ && pytest`

---

## Additional Resources

### Root-Level Documentation
These critical files remain in the project root for visibility:

- **[../README.md](../README.md)** - Project overview and quick start
- **[../CHANGELOG.md](../CHANGELOG.md)** - Version history and release notes
- **[../CLAUDE.md](../CLAUDE.md)** - Developer guide for AI assistants (safety rules, architecture, patterns)

### External Documentation
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Instagram Graph API](https://developers.facebook.com/docs/instagram-api)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Python Telegram Bot](https://python-telegram-bot.readthedocs.io/)
- [Cloudinary Documentation](https://cloudinary.com/documentation)

---

## Contributing Documentation

When adding new documentation:

1. **Choose the right location:**
   - Planning/design → `planning/`
   - How-to guides → `guides/`
   - Operations → `operations/`
   - Bug fixes/patches → `updates/` (use dated filenames: `YYYY-MM-DD-description.md`)
   - Completed plans → `archive/` (update `archive/ARCHIVE_INDEX.md`)

2. **Update this index** (`documentation/README.md`)

3. **Follow naming conventions:**
   - Use lowercase with hyphens: `backup-restore.md`
   - Be descriptive: `telegram-bot-setup.md` not `setup.md`
   - Date updates: `2026-02-10-feature-name.md`

4. **Keep root-level clean:**
   - Only critical files in project root (README, CHANGELOG, CLAUDE.md)
   - Everything else goes in `documentation/`

---

## Documentation Coverage

| Area | Status | Files | Notes |
|------|--------|-------|-------|
| **Planning** | Current | 8 active + 1 future | Phases 1-2.5 complete, 3-8 pending |
| **Guides** | Current | 8 guides | Setup, deployment, testing, Instagram API, dev env, deployment options, Tailscale, test coverage |
| **Operations** | Current | 3 files | Monitoring, backup, troubleshooting |
| **Updates** | Current | 3 files | Bugfixes, category scheduling, force posting |
| **Security** | Current | 1 file | Security review (updated post-refactor) |
| **Archive** | Organized | 10 files | Historical docs preserved with index |
| **API Docs** | Future | 0 files | Planned for Phase 5 (Dashboard UI) |

### Document Status Legend
- **COMPLETED** - Fully implemented and documented
- **IN PROGRESS** - Work actively underway
- **PENDING** - Planned for future implementation

---

## Need Help?

- **Setup issues?** → See [quickstart.md](guides/quickstart.md) troubleshooting
- **Deployment questions?** → Check [deployment.md](guides/deployment.md)
- **Test failures?** → Review [testing-guide.md](guides/testing-guide.md)
- **Architecture questions?** → Read [phases/00_MASTER_ROADMAP.md](planning/phases/00_MASTER_ROADMAP.md)
- **Version history?** → Check [ROADMAP.md](ROADMAP.md) or [../CHANGELOG.md](../CHANGELOG.md)
- **Instagram API setup?** → Follow [instagram-api-setup.md](guides/instagram-api-setup.md)
- **Security concerns?** → Review [SECURITY_REVIEW.md](SECURITY_REVIEW.md)

---

*Last updated: 2026-02-10*
