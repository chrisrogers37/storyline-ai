# Phase 4: Printify Integration

**Status**: 📋 PLANNED
**Dependencies**: Phase 3 (Shopify Integration)
**Estimated Duration**: 2 weeks

---

## Overview

Connect to Printify for print-on-demand (POD) product management and order fulfillment tracking. Printify is your dropshipping provider that fulfills orders when customers buy products.

### Goals

1. Sync Printify product catalog (blueprints, variants, pricing)
2. Track fulfillment status for POD orders
3. Calculate profit margins (Printify cost vs Shopify sale price)
4. Enable media linking to POD products

### Relationship to Shopify

```
Shopify (Storefront)          Printify (Fulfillment)
├── Product listing ──────────→ Blueprint/Design
├── Customer order ───────────→ Fulfillment order
├── Sale price ───────────────→ Production cost
└── Inventory = Printify capacity (unlimited POD)
```

---

## Sub-Phase Breakdown

### 4.1 Printify API Foundation
**Duration**: 0.5 weeks

**Deliverables**:
- PrintifyService with API authentication
- Connection health check
- Rate limit handling

### 4.2 Product/Blueprint Sync
**Duration**: 1 week

**Deliverables**:
- PrintifyProduct model (Type 2 SCD)
- Blueprint and variant sync
- Cost tracking per variant
- Link to Shopify products

### 4.3 Order & Fulfillment Tracking
**Duration**: 0.5 weeks

**Deliverables**:
- PrintifyOrder model
- Fulfillment status tracking
- Shipping updates
- Profit margin calculation

---

## Data Model

### PrintifyProduct (Type 2 SCD)

```sql
CREATE TABLE IF NOT EXISTS printify_products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Printify identifiers
    printify_product_id TEXT NOT NULL,
    printify_blueprint_id INTEGER,  -- Template product
    print_provider_id INTEGER,      -- Which printer

    -- Product data
    title TEXT NOT NULL,
    description TEXT,
    tags TEXT[],

    -- Variants (denormalized for cost lookup)
    variants JSONB,  -- [{id, title, cost, sku}, ...]

    -- Cost info (POD production cost)
    base_cost NUMERIC(10, 2),
    shipping_cost NUMERIC(10, 2),
    currency VARCHAR(3) DEFAULT 'USD',

    -- Linked Shopify product (if published)
    shopify_product_id BIGINT,
    is_published_to_shopify BOOLEAN DEFAULT FALSE,

    -- Type 2 SCD fields
    effective_from TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    effective_to TIMESTAMP,
    is_current BOOLEAN DEFAULT TRUE,
    version_number INTEGER DEFAULT 1,
    change_reason TEXT,

    -- Audit
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_printify_product_version
        UNIQUE (printify_product_id, effective_from)
);

CREATE INDEX idx_printify_products_printify_id ON printify_products(printify_product_id);
CREATE INDEX idx_printify_products_current ON printify_products(is_current) WHERE is_current = TRUE;
CREATE INDEX idx_printify_products_shopify ON printify_products(shopify_product_id) WHERE is_current = TRUE;
```

### PrintifyOrder

```sql
CREATE TABLE IF NOT EXISTS printify_orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Printify identifiers
    printify_order_id TEXT NOT NULL UNIQUE,
    printify_product_id TEXT,

    -- Linked Shopify order
    shopify_order_id BIGINT,

    -- Status tracking
    status VARCHAR(50),  -- 'pending', 'in_production', 'shipped', 'delivered', 'canceled'
    fulfillment_status VARCHAR(50),

    -- Shipping
    carrier TEXT,
    tracking_number TEXT,
    tracking_url TEXT,
    estimated_delivery DATE,
    shipped_at TIMESTAMP,
    delivered_at TIMESTAMP,

    -- Costs (for margin calculation)
    production_cost NUMERIC(10, 2),
    shipping_cost NUMERIC(10, 2),
    total_cost NUMERIC(10, 2),
    sale_price NUMERIC(10, 2),  -- From Shopify order
    profit NUMERIC(10, 2),      -- Calculated: sale_price - total_cost

    -- Timestamps
    printify_created_at TIMESTAMP,
    printify_updated_at TIMESTAMP,

    -- Metadata
    custom_metadata JSONB,

    -- Audit
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_printify_orders_printify_id ON printify_orders(printify_order_id);
CREATE INDEX idx_printify_orders_shopify ON printify_orders(shopify_order_id);
CREATE INDEX idx_printify_orders_status ON printify_orders(status);
```

---

## Service Interface

```python
# src/services/integrations/printify_service.py

class PrintifyService(BaseService):
    """
    Printify API integration for POD fulfillment.
    """

    def __init__(self):
        super().__init__()
        self.product_repo = PrintifyProductRepository()
        self.order_repo = PrintifyOrderRepository()
        self.shopify_repo = ShopifyProductRepository()

    # ─────────────────────────────────────────────────────────────
    # Product Sync
    # ─────────────────────────────────────────────────────────────

    async def sync_all_products(self) -> dict:
        """Full product catalog sync from Printify."""
        pass

    async def sync_product(self, printify_product_id: str) -> dict:
        """Sync single product (Type 2 SCD update)."""
        pass

    def get_product_cost(
        self,
        printify_product_id: str,
        variant_id: Optional[str] = None,
    ) -> dict:
        """Get production cost for margin calculation."""
        pass

    # ─────────────────────────────────────────────────────────────
    # Order Tracking
    # ─────────────────────────────────────────────────────────────

    async def sync_order(self, printify_order_id: str) -> dict:
        """Sync order status from Printify."""
        pass

    async def process_webhook(self, event: str, payload: dict) -> dict:
        """
        Process Printify webhook.

        Events:
        - order:created
        - order:shipped
        - order:delivered
        - order:canceled
        """
        pass

    # ─────────────────────────────────────────────────────────────
    # Analytics
    # ─────────────────────────────────────────────────────────────

    def calculate_margins(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> dict:
        """
        Calculate profit margins for POD products.

        Returns:
            {
                "total_revenue": 5000.00,
                "total_cost": 2500.00,
                "total_profit": 2500.00,
                "average_margin_percent": 50.0,
                "by_product": [...]
            }
        """
        pass

    def get_fulfillment_stats(self) -> dict:
        """
        Get fulfillment performance stats.

        Returns:
            {
                "avg_production_days": 2.5,
                "avg_shipping_days": 4.2,
                "on_time_delivery_rate": 0.95,
                "orders_in_production": 12,
            }
        """
        pass
```

---

## Configuration

```python
# settings.py additions

class Settings(BaseSettings):
    # Phase 4: Printify
    ENABLE_PRINTIFY_SYNC: bool = False
    PRINTIFY_API_KEY: Optional[str] = None
    PRINTIFY_SHOP_ID: Optional[str] = None
    PRINTIFY_WEBHOOK_SECRET: Optional[str] = None
    PRINTIFY_SYNC_INTERVAL_MINUTES: int = 30
```

---

## Webhook Endpoints

```python
# src/api/routes/webhooks.py additions

@router.post("/printify")
async def printify_webhook(
    request: Request,
    x_printify_signature: str = Header(...),
):
    """
    Handle Printify webhooks.

    Events: order:created, order:shipped, order:delivered, order:canceled
    """
    payload = await request.body()
    service = PrintifyService()

    if not await service.verify_webhook_signature(payload, x_printify_signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    data = await request.json()
    event = data.get("type")

    await service.process_webhook(event, data)

    return {"status": "ok"}
```

---

## Implementation Checklist

### 4.1 Printify API Foundation
- [ ] Create `src/services/integrations/printify_service.py`
- [ ] Implement API authentication
- [ ] Add connection health check
- [ ] Add rate limit handling

### 4.2 Product/Blueprint Sync
- [ ] Create `printify_products` table
- [ ] Create `src/repositories/printify_product_repository.py`
- [ ] Implement Type 2 SCD sync
- [ ] Link to Shopify products

### 4.3 Order & Fulfillment Tracking
- [ ] Create `printify_orders` table
- [ ] Implement webhook handler
- [ ] Calculate profit margins
- [ ] Add fulfillment stats

---

## Success Metrics

- **Sync freshness**: Products < 30 min behind Printify
- **Order tracking accuracy**: 100% of orders tracked
- **Margin calculation accuracy**: Within $0.01 of actual
- **Fulfillment visibility**: Real-time status updates
