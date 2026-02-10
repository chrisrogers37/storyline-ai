# Archive Directory

This directory contains **legacy documentation** that is preserved for historical context.

## Purpose

Documents in this archive:
- Represent completed work or obsolete planning
- Provide context for past decisions and implementations
- Should **NOT** be used as source of truth for current system state

## Current State

For current documentation, refer to:
- `/documentation/README.md` - Documentation index
- `/documentation/ROADMAP.md` - Current roadmap and version history
- `/documentation/planning/` - Active planning documents
- `/CHANGELOG.md` - Authoritative version history

## Archived Documents

| Document | Original Purpose | Archived Because |
|----------|------------------|------------------|
| `IMPLEMENTATION_COMPLETE.md` | Phase 1 completion checklist | Phase 1 shipped (v1.0.1) |
| `HANDOFF-2026-01-05.md` | v1.2.0 deployment handoff | Merged to main, deployed |
| `upcoming_build_notes.md` | Feature brainstorming | All features implemented |
| `phase-1.5-telegram-enhancements.md` | Phase 1.5 planning | Phase 1.5 complete (v1.3.0) |
| `instagram_automation_plan.md` | Original master planning doc | Superseded by `phases/` docs |
| `01_instagram_api.md` | Phase 2 Instagram API planning | Phase 2 complete (v1.5.0) |
| `telegram-service-refactor-plan.md` | TelegramService decomposition plan | Refactor complete (v1.6.0) - 3,500-line monolith split into 6 modules |
| `verbose-settings-improvement-plan.md` | Verbose notifications expansion | Complete (v1.6.0) - `_is_verbose()` helper, 4 message type fixes |
| `phase-1.7-inline-account-selector.md` | Inline account selection in posting workflow | Complete (v1.5.0) - Account switching without leaving post context |
| `user-interactions-design.md` | InteractionService design for analytics | Complete (v1.4.0) - Command/callback/response logging |

## When to Reference Archive

- Understanding historical decisions
- Reviewing past implementation details
- Auditing what was delivered in earlier phases
- Onboarding context for project history

## Do Not

- Update these documents (they are historical snapshots)
- Use them to understand current functionality
- Reference them for current API or schema details
