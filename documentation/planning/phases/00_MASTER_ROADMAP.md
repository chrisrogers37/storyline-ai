# Storyline AI - Master Roadmap

**Last Updated**: 2026-02-09
**Vision**: E-commerce Optimization Hub for Social Media Marketing

---

## Executive Summary

Storyline AI evolves from an Instagram Story scheduler into a comprehensive e-commerce optimization platform that:

1. **Automates social media posting** (Instagram Stories, future: Reels, Posts)
2. **Connects media assets to products** (Shopify, Printify)
3. **Provides actionable analytics** (Post performance → Product sales correlation)
4. **Orchestrates team workflows** (Telegram notifications, order alerts)
5. **Leverages AI** for content suggestions, email responses, and optimization

---

## Architecture Principles

### Strict Separation of Concerns

```
┌─────────────────────────────────────────────────────────────┐
│  Interface Layer                                             │
│  ├── Telegram Bot (Primary - Team Workflow)                 │
│  ├── CLI (Admin/Development)                                │
│  └── Web Dashboard (Phase 7 - Analytics/Management)         │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│  API Layer (Phase 2.5)                                       │
│  └── FastAPI REST Endpoints (all UI calls go through here)  │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│  Service Layer (Business Logic)                              │
│  ├── Core Services (Scheduling, Posting, Media, Health)     │
│  ├── Integration Services (Instagram, Shopify, Printify)    │
│  ├── Domain Services (Analytics, Suggestions, LLM)          │
│  └── Notification Services (Telegram, Email)                │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│  Repository Layer (Data Access)                              │
│  └── One repository per model, all database queries here    │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│  Data Layer                                                  │
│  ├── PostgreSQL (Primary - Transactional)                   │
│  ├── Redis (Phase 3+ - Caching, Rate Limiting)              │
│  └── External APIs (Instagram, Shopify, Printify, Gmail)    │
└─────────────────────────────────────────────────────────────┘
```

### Service Naming Convention

```
src/services/
├── core/           # Phase 1-2: Core functionality
│   ├── media_ingestion.py
│   ├── scheduler.py
│   ├── posting.py
│   ├── telegram_service.py      # Core bot + handler coordination
│   ├── telegram_commands.py     # /command handlers (refactored)
│   ├── telegram_callbacks.py    # Button callback handlers (refactored)
│   ├── telegram_autopost.py     # Auto-posting logic (refactored)
│   ├── telegram_settings.py     # Settings UI handlers (refactored)
│   ├── telegram_accounts.py     # Account selection handlers (refactored)
│   ├── health_check.py
│   ├── settings_service.py      # Database-backed settings
│   ├── instagram_account_service.py  # Multi-account management
│   ├── interaction_service.py   # Bot interaction tracking
│   └── media_lock.py
│
├── integrations/   # Phase 2-4: External platform integrations
│   ├── instagram_api.py      # ✅ Implemented
│   ├── cloud_storage.py      # ✅ Implemented (Cloudinary)
│   ├── token_refresh.py      # ✅ Implemented
│   ├── shopify_service.py    # Future
│   ├── printify_service.py   # Future
│   └── gmail_service.py      # Future
│
├── domain/         # Phase 5-6: Business intelligence
│   ├── analytics_service.py
│   ├── suggestion_service.py
│   └── llm_service.py
│
└── notifications/  # Cross-cutting notification services
    ├── order_notification_service.py
    └── email_orchestration_service.py
```

### Data Model Strategy

**Core Principle**: Use JSONB for flexibility, Type 2 SCD for audit trails

```
Entities (Tables):
├── Media Domain
│   ├── media_items (source of truth for all media)
│   ├── media_posting_locks (TTL-based repost prevention)
│   └── media_tags (future: AI-generated tags)
│
├── Scheduling Domain
│   ├── posting_queue (ephemeral work items)
│   ├── posting_history (permanent audit log)
│   └── category_post_case_mix (ratio configuration - Type 2 SCD)
│
├── E-commerce Domain (Phase 3-4)
│   ├── shopify_products (Type 2 SCD - price/title history)
│   ├── shopify_orders (order tracking)
│   ├── printify_products (Type 2 SCD)
│   ├── printify_orders (POD order tracking)
│   └── media_product_links (many-to-many: media ↔ products)
│
├── Analytics Domain (Phase 5)
│   ├── instagram_post_metrics (engagement data from Meta API)
│   ├── product_performance (calculated metrics)
│   └── correlation_insights (media → sales relationships)
│
├── Settings Domain (Phase 2.5 - ✅ Complete)
│   ├── chat_settings (per-chat runtime configuration)
│   └── instagram_accounts (multi-account identity management)
│
├── User Domain
│   ├── users (auto-discovered from Telegram)
│   ├── user_interactions (command/callback tracking)
│   └── service_runs (execution observability)
│
└── AI Domain (Phase 6)
    ├── llm_conversations (conversation history)
    ├── generated_content (AI-generated suggestions)
    └── email_drafts (LLM-generated email responses)
```

---

## Phase Overview

| Phase | Name | Status | Duration | Dependencies |
|-------|------|--------|----------|--------------|
| 1.0 | Telegram-Only Posting | ✅ COMPLETE | - | - |
| 1.5 | Telegram Enhancements | ✅ COMPLETE | - | Phase 1 |
| 1.6 | Category Scheduling | ✅ COMPLETE | - | Phase 1.5 |
| **2** | **Instagram API Automation** | ✅ COMPLETE | - | Phase 1.6 |
| **2.5** | **Settings & Multi-Tenancy** | ✅ COMPLETE (Phase 1-1.5) | - | Phase 2 |
| **3** | **Shopify Integration** | 📋 PLANNED | - | Phase 2 |
| **4** | **Printify Integration** | 📋 PLANNED | - | Phase 3 |
| **5** | **Media-Product Linking** | 📋 PLANNED | - | Phase 3, 4 |
| **6** | **LLM Integration** | 📋 PLANNED | - | Phase 5 |
| **7** | **Order & Email Automation** | 📋 PLANNED | - | Phase 3, 6 |
| **8** | **Dashboard UI** | 📋 PLANNED | - | Phase 5, 6, 7 |

---

## Phase Details

### Phase 2: Instagram API Automation ✅ COMPLETE
**Document**: [archive/01_instagram_api.md](../archive/01_instagram_api.md)

Enable automated Instagram Story posting via Meta Graph API. Hybrid mode: auto-post simple content, manual-post complex content.

**Key Deliverables** (all delivered):
- Instagram Graph API integration
- Cloudinary cloud storage for media URLs
- Token refresh service with encrypted storage
- Feature flag: `ENABLE_INSTAGRAM_API` (per-chat in database)
- Multi-account support (add/switch/deactivate via CLI and Telegram)
- Inline account selector in posting workflow
- Per-chat settings with `.env` fallback

### Phase 2.5: Settings & Multi-Tenancy ✅ COMPLETE (Phases 1-1.5)
**Document**: [01_settings_and_multitenancy.md](01_settings_and_multitenancy.md)

Runtime-configurable settings and Instagram account management. Phases 1 and 1.5 of this document are complete; Phases 2 (Cloud Media Storage) and 3 (Multi-Tenancy) remain future work.

**Key Deliverables** (delivered):
- Database-backed settings (`chat_settings` table) with `.env` fallback
- `/settings` command with inline toggle buttons
- Per-chat pause/resume, dry-run, Instagram API toggles
- Multi-Instagram account management (identity, credentials, selection separation)
- Account switching via Telegram `/settings` and inline posting workflow

---

### Phase 3: Shopify Integration
**Document**: [02_shopify_integration.md](02_shopify_integration.md)

Connect to Shopify store for product catalog sync and order tracking.

**Key Deliverables**:
- Shopify Admin API integration
- Product catalog sync (Type 2 SCD)
- Order webhook receiver
- Basic order analytics

---

### Phase 4: Printify Integration
**Document**: [03_printify_integration.md](03_printify_integration.md)

Connect to Printify for print-on-demand product management and order fulfillment tracking.

**Key Deliverables**:
- Printify API integration
- POD product sync
- Order/fulfillment status tracking
- Cost/margin calculations

---

### Phase 5: Media-Product Linking
**Document**: [04_media_product_linking.md](04_media_product_linking.md)

Create relationships between media assets and products for attribution and suggestions.

**Key Deliverables**:
- Many-to-many linking system
- Product tag suggestions based on media
- Attribution tracking (which media drove which sales)
- Performance correlation dashboard

---

### Phase 6: LLM Integration
**Document**: [05_llm_integration.md](05_llm_integration.md)

Add AI capabilities for content suggestions, email drafts, and optimization insights.

**Key Deliverables**:
- LLM service abstraction (Claude/OpenAI)
- Content suggestion engine
- Email response drafting
- Prompt management system

---

### Phase 7: Order & Email Automation
**Document**: [06_order_email_automation.md](06_order_email_automation.md)

Telegram order notifications and LLM-assisted email responses.

**Key Deliverables**:
- Order notification to Telegram
- Gmail API integration
- LLM-drafted customer responses
- Review/approve workflow

---

### Phase 8: Dashboard UI
**Document**: [07_dashboard_ui.md](07_dashboard_ui.md)

Web-based analytics dashboard and management interface.

**Key Deliverables**:
- Next.js frontend
- Analytics visualizations
- Media-product management
- Team activity dashboard

---

## Cross-Cutting Concerns

### Authentication Strategy

**Phase 1-4**: Single-tenant (your company only)
- Telegram user auto-discovery (no registration)
- Admin role via `ADMIN_TELEGRAM_CHAT_ID`
- API tokens stored in environment variables

**Phase 5+**: Multi-tenant ready (future)
- JWT authentication for API
- Team-based access control
- OAuth2 for third-party integrations

### Configuration Management

All integrations use feature flags:

```python
# settings.py pattern
ENABLE_INSTAGRAM_API: bool = False
ENABLE_SHOPIFY_SYNC: bool = False
ENABLE_PRINTIFY_SYNC: bool = False
ENABLE_LLM_FEATURES: bool = False
ENABLE_EMAIL_AUTOMATION: bool = False
```

### Error Handling Strategy

1. **Service Level**: All services extend `BaseService` with automatic error tracking
2. **Repository Level**: Database errors wrapped with context
3. **Integration Level**: External API failures logged with retry logic
4. **Notification Level**: Critical failures alert admin via Telegram

### Observability

Built-in via `service_runs` table:
- Every method execution logged
- Duration, status, error details
- Result summaries in JSONB
- User attribution when applicable

---

## Data Flow Diagrams

### Current (Phase 2 Complete)

```
Media Files → MediaIngestionService → media_items table
                                              ↓
SchedulerService → posting_queue ← CategoryMixRepository
       ↑                ↓
 chat_settings    PostingService ──→ Route Decision
 (per-chat)             │
                   ┌────┴────────────────────┐
                   ↓                          ↓
           TelegramService           InstagramAPIService
           (manual workflow)         (auto-post via API)
                   │                          │
                   ↓                    ┌─────┴──────┐
           Telegram Channel             ↓             ↓
                   ↓              CloudStorage   Instagram
           User Action            (Cloudinary)    Graph API
           (Posted/Skip/Reject)       ↓             ↓
                   ↓              Upload media   Post story
                   ↓                   └─────┬──────┘
           posting_history + locks           ↓
                                       posting_history
```

### Future (Phase 5+)

```
Media Files ─────────────────────┐
                                 ↓
Shopify Products ──────→ media_product_links ←── MediaItem
                                 ↓
Printify Products ─────┐    Performance Data
                       ↓         ↓
Analytics Service ← Instagram Metrics + Order Data
         ↓
Suggestion Service → Telegram (recommend posts)
         ↓
LLM Service → Email Drafts → Gmail
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Instagram API rate limits | Cloudinary CDN + batch scheduling |
| Shopify API changes | Version-locked SDK + webhook fallbacks |
| LLM costs | Caching, prompt optimization, usage limits |
| Data consistency | Type 2 SCD for external data, snapshots in JSONB |
| Single point of failure | Feature flags allow disabling any integration |

---

## Success Metrics

### Phase 2 (Instagram API)
- Automated posts/day
- API error rate < 1%
- Manual override rate (how often team uses manual mode)

### Phase 3-4 (E-commerce)
- Product sync freshness (< 15 min lag)
- Order notification latency (< 1 min)
- Data accuracy vs Shopify/Printify dashboards

### Phase 5-6 (Intelligence)
- Suggestion acceptance rate
- Time saved on email responses
- Correlation accuracy (predicted vs actual sales)

### Phase 7-8 (Automation + UI)
- Order-to-notification latency
- Email response time reduction
- Dashboard adoption (daily active users)

---

## Document Index

| Document | Description |
|----------|-------------|
| [01_settings_and_multitenancy.md](01_settings_and_multitenancy.md) | Settings menu, multi-account, multi-tenancy (Phases 1-1.5 ✅) |
| [02_shopify_integration.md](02_shopify_integration.md) | Shopify Admin API integration |
| [03_printify_integration.md](03_printify_integration.md) | Printify API integration |
| [04_media_product_linking.md](04_media_product_linking.md) | Media ↔ Product relationships |
| [05_llm_integration.md](05_llm_integration.md) | AI/LLM service integration |
| [06_order_email_automation.md](06_order_email_automation.md) | Order alerts + Email automation |
| [07_dashboard_ui.md](07_dashboard_ui.md) | Web dashboard implementation |

**Archived** (completed phases):
| [archive/01_instagram_api.md](../archive/01_instagram_api.md) | Instagram Graph API (✅ COMPLETE) |

---

## Backlog / Future Improvements

Items to address in future iterations:

### Telegram Bot UX Improvements

**Race Condition Handling for Button Clicks** ✅ COMPLETE (v1.6.0)
- **Problem**: Multiple rapid button clicks can trigger duplicate operations or conflicting actions
- **Solution Implemented**:
  1. Track pending operations per queue_id with cancellation tokens
  2. Use asyncio locks to prevent concurrent execution on same item
  3. Terminal actions (Skip/Posted/Reject) cancel any pending Auto Post
  4. Same button clicked twice shows "⏳ Already processing..." feedback
  5. Visual feedback: "⏳ Already processing..." toast when lock is held
- **Implementation Details**:
  - Added `_operation_locks: dict[str, asyncio.Lock]` to TelegramService
  - Added `_cancel_flags: dict[str, asyncio.Event]` for cancellation signaling
  - Cancellation checked at key points: after Cloudinary upload, before Instagram API call
  - Graceful abort with cleanup if cancelled mid-operation
  - 7 new tests for race condition handling

---

## Getting Started

1. Read this document for overall vision
2. Review completed phases in `/documentation/ROADMAP.md`
3. For next implementation, start with Phase 3 (Shopify Integration)
4. Each phase document contains:
   - Sub-phase breakdown (01_, 02_, 03_)
   - Data models with SQL
   - Service interfaces
   - Test requirements
   - Configuration needed
