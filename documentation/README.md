# Storyline AI Documentation

Welcome to the Storyline AI documentation hub. All project documentation is organized here by purpose.

## 📁 Documentation Structure

```
documentation/
├── README.md (this file)          # Documentation index
├── planning/                       # Planning and design documents
├── guides/                         # How-to guides and tutorials
├── operations/                     # Operational runbooks
├── updates/                        # Project updates, bugfixes, patches
└── api/                            # API documentation (Phase 5)
```

---

## 📋 Planning & Architecture

### Master Implementation Plan
**[instagram_automation_plan.md](planning/instagram_automation_plan.md)**
- Complete technical specification
- All phases (1-5) with detailed requirements
- Database schema design
- Service architecture
- API endpoints
- UI mockups and workflows

### Implementation Status
**[IMPLEMENTATION_COMPLETE.md](planning/IMPLEMENTATION_COMPLETE.md)**
- Phase 1 completion checklist
- Delivered components
- Testing summary
- Next steps for Phase 2

### Feature Designs
**[user-interactions-design.md](planning/user-interactions-design.md)**
- User interaction tracking system
- InteractionService architecture
- Analytics capabilities
- `/queue` and `/status` command design

**[phase-1.5-telegram-enhancements.md](planning/phase-1.5-telegram-enhancements.md)**
- Telegram UX improvements
- Bot lifecycle notifications
- Instagram deep links
- Enhanced captions

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
**[testing.md](guides/testing.md)**
**[testing-guide.md](guides/testing-guide.md)**
- How test database auto-creation works
- Running tests (unit, integration, coverage)
- Writing new tests
- Test fixtures and patterns
- CI/CD integration
- Troubleshooting test failures

### Development Environment Setup
**[dev-environment-setup.md](guides/dev-environment-setup.md)**
- Mac ↔ Raspberry Pi workflow optimization
- Shell aliases for both environments
- Database permission setup
- Deployment scripts and rsync shortcuts
- Quick reference command card

---

## 🛠 Operations & Maintenance

Coming soon:
- Monitoring and alerting setup
- Backup and restore procedures
- Troubleshooting runbooks
- Performance tuning
- Security hardening

---

## 🔄 Project Updates

### Feature Updates
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

---

## 📚 API Documentation

Coming in Phase 5:
- REST API endpoints
- Authentication flows
- Rate limiting
- WebSocket events
- SDK documentation

---

## 🔍 Quick Reference

### For New Developers
1. Start with **[quickstart.md](guides/quickstart.md)** (10 min setup)
2. Read **[testing-guide.md](guides/testing-guide.md)** (understand testing)
3. Review **[instagram_automation_plan.md](planning/instagram_automation_plan.md)** (full architecture)

### For Deploying to Production
1. Follow **[deployment.md](guides/deployment.md)** step-by-step
2. Complete Telegram bot setup (Section 1)
3. Configure database (Section 2)
4. Deploy and test (Sections 5-11)

### For Understanding Architecture
1. Check **[instagram_automation_plan.md](planning/instagram_automation_plan.md)**
   - See "System Architecture" section
   - Review database schema
   - Understand service layer design

### For Contributing Code
1. Read root **[CLAUDE.md](../CLAUDE.md)** (development guidelines)
2. Review **[testing-guide.md](guides/testing-guide.md)** (test requirements)
3. Check **[planning/instagram_automation_plan.md](planning/instagram_automation_plan.md)** for context

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

| Area | Coverage | Files |
|------|----------|-------|
| **Planning** | ✅ Complete | 3 files |
| **Getting Started** | ✅ Complete | 4 guides |
| **Testing** | ✅ Complete | 2 guides |
| **Updates** | ✅ Current | 2 files |
| **Operations** | 🚧 Planned | 0 files |
| **API Docs** | ⏳ Phase 5 | 0 files |

---

## 🆘 Need Help?

- **Setup issues?** → See [quickstart.md](guides/quickstart.md) troubleshooting
- **Deployment questions?** → Check [deployment.md](guides/deployment.md)
- **Test failures?** → Review [testing-guide.md](guides/testing-guide.md)
- **Architecture questions?** → Read [instagram_automation_plan.md](planning/instagram_automation_plan.md)

---

*Last updated: 2026-01-10*
