# Phase 5: Media-Product Linking

**Status**: 📋 PLANNED
**Dependencies**: Phase 3 (Shopify), Phase 4 (Printify)
**Estimated Duration**: 2-3 weeks

---

## Overview

Create relationships between media assets (UGC, product photos, memes) and products to enable attribution, suggestions, and performance correlation.

### Goals

1. Link media items to one or more products (many-to-many)
2. Track which media drove which sales (attribution)
3. Correlate posting performance with product sales
4. Suggest products for media tagging
5. Enable ad tag linking for paid campaigns

---

## Sub-Phase Breakdown

### 5.1 Linking Data Model
**Duration**: 1 week

**Deliverables**:
- MediaProductLink junction table
- Link types (featured, mentioned, background)
- Confidence scoring for suggestions

### 5.2 Manual Linking Interface
**Duration**: 0.5 weeks

**Deliverables**:
- CLI commands for linking
- Telegram commands for quick linking
- Bulk linking support

### 5.3 Attribution & Analytics
**Duration**: 1 week

**Deliverables**:
- Post → Order correlation (time-windowed)
- Revenue attribution per media
- Performance scoring
- Suggestion engine foundation

---

## Data Model

### MediaProductLink

```sql
CREATE TABLE IF NOT EXISTS media_product_links (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- The relationship
    media_item_id UUID NOT NULL REFERENCES media_items(id),
    shopify_product_id BIGINT,  -- NULL if Printify-only
    printify_product_id TEXT,   -- NULL if Shopify-only

    -- Link metadata
    link_type VARCHAR(50) NOT NULL DEFAULT 'featured',
        -- 'featured': Product is main focus
        -- 'mentioned': Product appears/mentioned
        -- 'background': Product visible but not focus
        -- 'suggested': AI-suggested (not confirmed)

    -- Attribution
    is_confirmed BOOLEAN DEFAULT TRUE,  -- FALSE for AI suggestions
    confidence_score NUMERIC(3, 2),     -- 0.00-1.00 for suggestions

    -- Performance (updated by analytics service)
    posts_using_link INTEGER DEFAULT 0,
    attributed_orders INTEGER DEFAULT 0,
    attributed_revenue NUMERIC(12, 2) DEFAULT 0,

    -- For ad campaigns
    ad_campaign_id TEXT,
    utm_tags JSONB,  -- {source, medium, campaign, content}

    -- Audit
    linked_by_user_id UUID REFERENCES users(id),
    linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    unlinked_at TIMESTAMP,  -- Soft delete
    unlinked_by_user_id UUID REFERENCES users(id),

    -- Metadata
    notes TEXT,
    custom_metadata JSONB,

    -- Constraints
    CONSTRAINT at_least_one_product
        CHECK (shopify_product_id IS NOT NULL OR printify_product_id IS NOT NULL)
);

CREATE INDEX idx_media_product_links_media ON media_product_links(media_item_id);
CREATE INDEX idx_media_product_links_shopify ON media_product_links(shopify_product_id);
CREATE INDEX idx_media_product_links_printify ON media_product_links(printify_product_id);
CREATE INDEX idx_media_product_links_type ON media_product_links(link_type);
CREATE INDEX idx_media_product_links_active ON media_product_links(media_item_id)
    WHERE unlinked_at IS NULL;
```

### ProductPerformance (Aggregated Metrics)

```sql
CREATE TABLE IF NOT EXISTS product_performance (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Product reference
    shopify_product_id BIGINT,
    printify_product_id TEXT,

    -- Time period
    period_type VARCHAR(20) NOT NULL,  -- 'daily', 'weekly', 'monthly'
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,

    -- Posting metrics
    total_posts INTEGER DEFAULT 0,
    posts_with_product INTEGER DEFAULT 0,  -- Posts featuring this product

    -- Engagement (from Instagram metrics - Phase 5+)
    total_impressions BIGINT DEFAULT 0,
    total_reach BIGINT DEFAULT 0,
    total_engagement INTEGER DEFAULT 0,  -- likes + comments + shares

    -- Sales metrics
    total_orders INTEGER DEFAULT 0,
    total_revenue NUMERIC(12, 2) DEFAULT 0,
    average_order_value NUMERIC(10, 2),

    -- Attribution
    attributed_orders INTEGER DEFAULT 0,  -- Orders within attribution window
    attributed_revenue NUMERIC(12, 2) DEFAULT 0,
    attribution_rate NUMERIC(5, 4),  -- attributed_orders / total_orders

    -- Calculated
    revenue_per_post NUMERIC(10, 2),
    engagement_to_sale_rate NUMERIC(5, 4),

    -- Metadata
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_product_period
        UNIQUE (shopify_product_id, printify_product_id, period_type, period_start)
);

CREATE INDEX idx_product_performance_shopify ON product_performance(shopify_product_id);
CREATE INDEX idx_product_performance_period ON product_performance(period_start, period_end);
```

---

## Service Interface

### MediaLinkingService

```python
# src/services/domain/media_linking_service.py

class MediaLinkingService(BaseService):
    """
    Manage media ↔ product relationships.
    """

    def __init__(self):
        super().__init__()
        self.link_repo = MediaProductLinkRepository()
        self.media_repo = MediaRepository()
        self.shopify_repo = ShopifyProductRepository()
        self.printify_repo = PrintifyProductRepository()

    # ─────────────────────────────────────────────────────────────
    # Linking Operations
    # ─────────────────────────────────────────────────────────────

    def link_media_to_product(
        self,
        media_id: str,
        product_id: str,  # Shopify or Printify ID
        product_source: str,  # 'shopify' or 'printify'
        link_type: str = "featured",
        user_id: Optional[str] = None,
    ) -> MediaProductLink:
        """Create manual link between media and product."""
        pass

    def unlink_media_from_product(
        self,
        link_id: str,
        user_id: Optional[str] = None,
    ) -> bool:
        """Soft-delete a link (preserves history)."""
        pass

    def bulk_link(
        self,
        media_ids: List[str],
        product_id: str,
        product_source: str,
        link_type: str = "featured",
        user_id: Optional[str] = None,
    ) -> dict:
        """Link multiple media items to one product."""
        pass

    def get_media_products(self, media_id: str) -> List[dict]:
        """Get all products linked to a media item."""
        pass

    def get_product_media(
        self,
        product_id: str,
        product_source: str,
        link_type: Optional[str] = None,
    ) -> List[MediaItem]:
        """Get all media linked to a product."""
        pass

    # ─────────────────────────────────────────────────────────────
    # Attribution
    # ─────────────────────────────────────────────────────────────

    def calculate_attribution(
        self,
        media_id: str,
        attribution_window_hours: int = 72,
    ) -> dict:
        """
        Calculate sales attributed to a media post.

        Logic:
        1. Get posting_history for this media
        2. Get linked products
        3. Find orders for those products within window after post
        4. Attribute proportionally if multiple posts in window

        Returns:
            {
                "media_id": "...",
                "posts": 5,
                "linked_products": 3,
                "attributed_orders": 12,
                "attributed_revenue": 1500.00,
            }
        """
        pass

    def recalculate_all_attribution(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> dict:
        """Batch recalculate attribution for date range."""
        pass

    # ─────────────────────────────────────────────────────────────
    # Suggestions
    # ─────────────────────────────────────────────────────────────

    def suggest_products_for_media(
        self,
        media_id: str,
        limit: int = 5,
    ) -> List[dict]:
        """
        Suggest products to link based on:
        - Media category matching product type
        - Media tags matching product tags
        - Previously linked products for similar media
        - AI analysis (Phase 6)

        Returns:
            [
                {
                    "product_id": "...",
                    "product_source": "shopify",
                    "product_title": "...",
                    "confidence": 0.85,
                    "reason": "category_match",
                },
                ...
            ]
        """
        pass

    def suggest_media_for_product(
        self,
        product_id: str,
        product_source: str,
        limit: int = 10,
    ) -> List[dict]:
        """Suggest media to use for a product."""
        pass
```

### PerformanceAnalyticsService

```python
# src/services/domain/performance_analytics.py

class PerformanceAnalyticsService(BaseService):
    """
    Calculate and store product performance metrics.
    """

    def calculate_product_performance(
        self,
        product_id: str,
        product_source: str,
        period_type: str = "weekly",
    ) -> ProductPerformance:
        """Calculate performance metrics for a product."""
        pass

    def calculate_all_performance(
        self,
        period_type: str = "weekly",
    ) -> dict:
        """Batch calculate performance for all products."""
        pass

    def get_top_performing_products(
        self,
        metric: str = "revenue_per_post",
        period: str = "last_30_days",
        limit: int = 10,
    ) -> List[dict]:
        """Get products ranked by performance metric."""
        pass

    def get_top_performing_media(
        self,
        metric: str = "attributed_revenue",
        period: str = "last_30_days",
        limit: int = 10,
    ) -> List[dict]:
        """Get media ranked by performance metric."""
        pass

    def get_correlation_insights(
        self,
        product_id: Optional[str] = None,
    ) -> dict:
        """
        Find correlations between posting and sales.

        Returns:
            {
                "best_posting_days": ["Tuesday", "Friday"],
                "best_posting_hours": [14, 18],
                "optimal_post_frequency": 3,  # posts per week
                "category_performance": {...},
            }
        """
        pass
```

---

## Telegram Commands

```python
# New commands in TelegramService

async def _handle_link(self, update, context):
    """
    /link <product_search> - Link current/last media to a product

    Usage:
    /link blue hoodie  → Search and link to matching product
    /link SKU:ABC123   → Link by SKU
    """
    pass

async def _handle_unlink(self, update, context):
    """
    /unlink <product_search> - Remove link from current media
    """
    pass

async def _handle_products(self, update, context):
    """
    /products - Show products linked to current media
    """
    pass
```

---

## CLI Commands

```python
# cli/commands/linking.py

@click.group(name="link")
def link_group():
    """Media-product linking commands."""
    pass

@link_group.command(name="add")
@click.argument("media_id")
@click.argument("product_id")
@click.option("--source", type=click.Choice(["shopify", "printify"]), required=True)
@click.option("--type", default="featured")
def add_link(media_id, product_id, source, type):
    """Link media to a product."""
    pass

@link_group.command(name="bulk")
@click.option("--category", help="Link all media in category")
@click.option("--product", required=True, help="Product to link to")
@click.option("--source", type=click.Choice(["shopify", "printify"]), required=True)
def bulk_link(category, product, source):
    """Bulk link media to a product."""
    pass

@link_group.command(name="suggest")
@click.argument("media_id")
def suggest(media_id):
    """Show product suggestions for media."""
    pass

@link_group.command(name="attribution")
@click.option("--days", default=30, help="Days to analyze")
def attribution(days):
    """Show attribution report."""
    pass
```

---

## Implementation Checklist

### 5.1 Linking Data Model
- [ ] Create `media_product_links` table
- [ ] Create `product_performance` table
- [ ] Create `src/repositories/media_product_link_repository.py`
- [ ] Create `src/repositories/product_performance_repository.py`

### 5.2 Manual Linking Interface
- [ ] Create `src/services/domain/media_linking_service.py`
- [ ] Add Telegram `/link`, `/unlink`, `/products` commands
- [ ] Add CLI linking commands
- [ ] Write unit tests

### 5.3 Attribution & Analytics
- [ ] Implement attribution calculation
- [ ] Create `src/services/domain/performance_analytics.py`
- [ ] Add scheduled recalculation job
- [ ] Implement suggestion engine (rule-based)
- [ ] Write unit tests

---

## Attribution Window Logic

```python
def calculate_attribution(media_id: str, window_hours: int = 72):
    """
    Attribution algorithm:

    1. Get all posts of this media (from posting_history)
    2. Get all linked products
    3. For each post:
       a. Find orders for linked products within `window_hours` after post
       b. If multiple posts in window, split attribution proportionally
       c. Sum attributed revenue

    Multi-touch attribution (simple):
    - If 2 posts within window before order, each gets 50% credit
    - If 3 posts, each gets 33.3%
    - Last-touch alternative: 100% to most recent post
    """
    pass
```

---

## Success Metrics

- **Linking coverage**: % of media with product links
- **Attribution accuracy**: Manual validation of sample
- **Suggestion acceptance**: % of suggestions confirmed by users
- **Performance insights**: Correlation strength (posting → sales)
