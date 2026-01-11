# Phase 3: Shopify Integration

**Status**: 📋 PLANNED
**Dependencies**: Phase 2 (Instagram API)
**Estimated Duration**: 2-3 weeks

---

## Overview

Connect to your Shopify store to sync product catalog, track orders, and enable product-media relationships for future analytics.

### Goals

1. Sync product catalog from Shopify (one-way: Shopify → Storyline)
2. Track orders for correlation with social media posts
3. Preserve product history using Type 2 SCD pattern
4. Enable webhook-based real-time updates

### Non-Goals (This Phase)

- Pushing data back to Shopify
- Inventory management
- Checkout modifications
- Customer data (PII concerns)

---

## Sub-Phase Breakdown

### 3.1 Shopify API Foundation
**Duration**: 1 week

Set up authenticated connection to Shopify Admin API.

**Deliverables**:
- ShopifyService with OAuth authentication
- Rate limit handling
- Connection health check
- Token storage in api_tokens table

### 3.2 Product Catalog Sync
**Duration**: 1 week

Sync products with Type 2 SCD for historical tracking.

**Deliverables**:
- ShopifyProduct model (Type 2 SCD)
- Initial full sync command
- Incremental sync via webhooks
- Product variant handling

### 3.3 Order Tracking
**Duration**: 0.5-1 week

Track orders for future analytics correlation.

**Deliverables**:
- ShopifyOrder model
- Webhook receiver for order events
- Basic order statistics

---

## Data Model

### ShopifyProduct (Type 2 SCD)

```sql
CREATE TABLE IF NOT EXISTS shopify_products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Shopify identifiers
    shopify_product_id BIGINT NOT NULL,
    shopify_variant_id BIGINT,  -- NULL for parent product

    -- Product data (snapshot at this version)
    title TEXT NOT NULL,
    description TEXT,
    handle TEXT,  -- URL slug
    product_type TEXT,  -- Category in Shopify
    vendor TEXT,
    tags TEXT[],

    -- Pricing (at this version)
    price NUMERIC(10, 2),
    compare_at_price NUMERIC(10, 2),  -- Original price for sales
    currency VARCHAR(3) DEFAULT 'USD',

    -- Inventory (at this version)
    inventory_quantity INTEGER,
    inventory_policy VARCHAR(20),  -- 'deny' or 'continue'

    -- Media
    featured_image_url TEXT,
    image_urls TEXT[],

    -- Status
    status VARCHAR(20),  -- 'active', 'draft', 'archived'
    published_at TIMESTAMP,

    -- Type 2 SCD fields
    effective_from TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    effective_to TIMESTAMP,  -- NULL = current version
    is_current BOOLEAN DEFAULT TRUE,
    version_number INTEGER DEFAULT 1,

    -- Change tracking
    change_reason TEXT,  -- 'initial_sync', 'price_change', 'title_update', etc.

    -- Shopify metadata
    shopify_created_at TIMESTAMP,
    shopify_updated_at TIMESTAMP,

    -- Our metadata
    custom_metadata JSONB,  -- Flexible field for extensions

    -- Audit
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Indexes
    CONSTRAINT unique_product_version UNIQUE (shopify_product_id, shopify_variant_id, effective_from)
);

CREATE INDEX idx_shopify_products_shopify_id ON shopify_products(shopify_product_id);
CREATE INDEX idx_shopify_products_current ON shopify_products(is_current) WHERE is_current = TRUE;
CREATE INDEX idx_shopify_products_effective ON shopify_products(effective_from, effective_to);
CREATE INDEX idx_shopify_products_handle ON shopify_products(handle) WHERE is_current = TRUE;
CREATE INDEX idx_shopify_products_type ON shopify_products(product_type) WHERE is_current = TRUE;
```

### ShopifyOrder

```sql
CREATE TABLE IF NOT EXISTS shopify_orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Shopify identifiers
    shopify_order_id BIGINT NOT NULL UNIQUE,
    shopify_order_number TEXT,  -- Human-readable #1001, etc.

    -- Order basics
    financial_status VARCHAR(50),  -- 'paid', 'pending', 'refunded'
    fulfillment_status VARCHAR(50),  -- 'fulfilled', 'partial', NULL
    total_price NUMERIC(10, 2),
    subtotal_price NUMERIC(10, 2),
    total_tax NUMERIC(10, 2),
    total_discounts NUMERIC(10, 2),
    currency VARCHAR(3) DEFAULT 'USD',

    -- Customer (anonymized - no PII)
    customer_id_hash TEXT,  -- Hashed Shopify customer ID for analytics
    is_repeat_customer BOOLEAN,
    order_count INTEGER,  -- Customer's order number

    -- Line items (denormalized for analytics)
    line_item_count INTEGER,
    line_items JSONB,  -- [{product_id, variant_id, quantity, price}, ...]

    -- Timestamps
    shopify_created_at TIMESTAMP NOT NULL,
    shopify_updated_at TIMESTAMP,
    processed_at TIMESTAMP,  -- When payment was processed
    closed_at TIMESTAMP,     -- When order was completed

    -- Source tracking (for attribution)
    source_name TEXT,        -- 'web', 'instagram', etc.
    referring_site TEXT,
    landing_site TEXT,
    utm_source TEXT,
    utm_medium TEXT,
    utm_campaign TEXT,

    -- Our metadata
    custom_metadata JSONB,

    -- Audit
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_shopify_orders_shopify_id ON shopify_orders(shopify_order_id);
CREATE INDEX idx_shopify_orders_created ON shopify_orders(shopify_created_at);
CREATE INDEX idx_shopify_orders_financial ON shopify_orders(financial_status);
CREATE INDEX idx_shopify_orders_source ON shopify_orders(source_name);
```

---

## Service Interface

### ShopifyService

```python
# src/services/integrations/shopify_service.py

from shopify import ShopifyAPI  # Official SDK or custom

class ShopifyService(BaseService):
    """
    Shopify Admin API integration.

    Handles product sync, order tracking, and webhook processing.
    """

    def __init__(self):
        super().__init__()
        self.product_repo = ShopifyProductRepository()
        self.order_repo = ShopifyOrderRepository()
        self.token_service = TokenRefreshService()

    # ─────────────────────────────────────────────────────────────
    # Product Sync
    # ─────────────────────────────────────────────────────────────

    async def sync_all_products(self) -> dict:
        """
        Full product catalog sync.

        Use for initial setup or recovery. Handles pagination.

        Returns:
            {
                "total_synced": 150,
                "new_products": 10,
                "updated_products": 5,
                "unchanged": 135,
                "errors": [],
            }
        """
        pass

    async def sync_product(self, shopify_product_id: int) -> dict:
        """
        Sync single product (called by webhook).

        Creates new Type 2 SCD version if product changed.
        """
        pass

    def get_product_history(
        self,
        shopify_product_id: int,
        limit: int = 10,
    ) -> List[ShopifyProduct]:
        """Get version history for a product (Type 2 SCD query)."""
        pass

    def get_product_at_date(
        self,
        shopify_product_id: int,
        as_of: datetime,
    ) -> Optional[ShopifyProduct]:
        """Get product state at a specific point in time."""
        pass

    # ─────────────────────────────────────────────────────────────
    # Order Tracking
    # ─────────────────────────────────────────────────────────────

    async def sync_recent_orders(self, days: int = 7) -> dict:
        """Sync orders from last N days."""
        pass

    async def process_order_webhook(self, payload: dict) -> dict:
        """
        Process incoming order webhook.

        Events: orders/create, orders/updated, orders/paid
        """
        pass

    def get_order_stats(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> dict:
        """
        Get order statistics for date range.

        Returns:
            {
                "total_orders": 50,
                "total_revenue": 5000.00,
                "average_order_value": 100.00,
                "top_products": [...],
            }
        """
        pass

    # ─────────────────────────────────────────────────────────────
    # Webhooks
    # ─────────────────────────────────────────────────────────────

    async def register_webhooks(self) -> dict:
        """
        Register required webhooks with Shopify.

        Webhooks:
        - products/create
        - products/update
        - products/delete
        - orders/create
        - orders/updated
        """
        pass

    async def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str,
    ) -> bool:
        """Verify webhook came from Shopify."""
        pass

    # ─────────────────────────────────────────────────────────────
    # Health
    # ─────────────────────────────────────────────────────────────

    async def check_connection(self) -> dict:
        """
        Verify Shopify API connection.

        Returns:
            {
                "connected": True,
                "shop_name": "your-store",
                "plan": "basic",
                "rate_limit_remaining": 38,
            }
        """
        pass
```

---

## Webhook Endpoints

### FastAPI Router

```python
# src/api/routes/webhooks.py

from fastapi import APIRouter, Request, HTTPException, Header
from src.services.integrations.shopify_service import ShopifyService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

@router.post("/shopify/products")
async def shopify_product_webhook(
    request: Request,
    x_shopify_hmac_sha256: str = Header(...),
    x_shopify_topic: str = Header(...),
):
    """
    Handle Shopify product webhooks.

    Topics: products/create, products/update, products/delete
    """
    payload = await request.body()
    service = ShopifyService()

    # Verify signature
    if not await service.verify_webhook_signature(payload, x_shopify_hmac_sha256):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Process based on topic
    data = await request.json()

    if x_shopify_topic == "products/delete":
        # Mark product as archived (don't delete - preserve history)
        await service.archive_product(data["id"])
    else:
        # Sync product (creates new version if changed)
        await service.sync_product(data["id"])

    return {"status": "ok"}

@router.post("/shopify/orders")
async def shopify_order_webhook(
    request: Request,
    x_shopify_hmac_sha256: str = Header(...),
    x_shopify_topic: str = Header(...),
):
    """
    Handle Shopify order webhooks.

    Topics: orders/create, orders/updated, orders/paid
    """
    payload = await request.body()
    service = ShopifyService()

    if not await service.verify_webhook_signature(payload, x_shopify_hmac_sha256):
        raise HTTPException(status_code=401, detail="Invalid signature")

    data = await request.json()
    await service.process_order_webhook(data)

    return {"status": "ok"}
```

---

## Configuration

```python
# settings.py additions

class Settings(BaseSettings):
    # ... existing ...

    # Phase 3: Shopify
    ENABLE_SHOPIFY_SYNC: bool = False
    SHOPIFY_SHOP_DOMAIN: Optional[str] = None  # your-store.myshopify.com
    SHOPIFY_API_KEY: Optional[str] = None
    SHOPIFY_API_SECRET: Optional[str] = None
    SHOPIFY_ACCESS_TOKEN: Optional[str] = None  # From OAuth or private app
    SHOPIFY_API_VERSION: str = "2024-01"

    # Sync settings
    SHOPIFY_SYNC_INTERVAL_MINUTES: int = 60
    SHOPIFY_WEBHOOK_SECRET: Optional[str] = None
```

---

## CLI Commands

```python
# cli/commands/shopify.py

@click.group(name="shopify")
def shopify_group():
    """Shopify integration commands."""
    pass

@shopify_group.command(name="sync-products")
@click.option("--full", is_flag=True, help="Force full sync (ignore webhooks)")
def sync_products(full):
    """Sync product catalog from Shopify."""
    pass

@shopify_group.command(name="sync-orders")
@click.option("--days", default=7, help="Days of history to sync")
def sync_orders(days):
    """Sync recent orders from Shopify."""
    pass

@shopify_group.command(name="check-connection")
def check_connection():
    """Test Shopify API connection."""
    pass

@shopify_group.command(name="product-history")
@click.argument("product_id")
def product_history(product_id):
    """Show price/title history for a product."""
    pass
```

---

## Testing Requirements

### Unit Tests

```python
# tests/src/services/test_shopify_service.py
class TestShopifyService:
    def test_sync_product_new(self)
    def test_sync_product_update_creates_version(self)
    def test_sync_product_no_change_skips(self)
    def test_get_product_at_date(self)
    def test_process_order_webhook(self)
    def test_verify_webhook_signature(self)

# tests/src/repositories/test_shopify_product_repository.py
class TestShopifyProductRepository:
    def test_create_first_version(self)
    def test_create_new_version_closes_previous(self)
    def test_get_current_returns_latest(self)
    def test_get_history_returns_all_versions(self)
    def test_get_at_date_returns_correct_version(self)
```

### Integration Tests

```python
# tests/integration/test_shopify_sync.py
class TestShopifySync:
    def test_full_sync_pagination(self)  # Mock Shopify API
    def test_webhook_creates_version(self)
    def test_order_sync_calculates_stats(self)
```

---

## Implementation Checklist

### 3.1 Shopify API Foundation
- [ ] Create `src/services/integrations/shopify_service.py`
- [ ] Add Shopify token to `api_tokens` table
- [ ] Implement connection check
- [ ] Add rate limit handling
- [ ] Write unit tests
- [ ] Add configuration settings

### 3.2 Product Catalog Sync
- [ ] Create `shopify_products` table migration
- [ ] Create `src/repositories/shopify_product_repository.py`
- [ ] Implement Type 2 SCD logic
- [ ] Implement full sync with pagination
- [ ] Implement webhook handler
- [ ] Add CLI commands
- [ ] Write unit tests

### 3.3 Order Tracking
- [ ] Create `shopify_orders` table migration
- [ ] Create `src/repositories/shopify_order_repository.py`
- [ ] Implement order webhook handler
- [ ] Implement order statistics
- [ ] Write unit tests

---

## Type 2 SCD Pattern Reference

```python
# How Type 2 SCD works for product updates

def sync_product(self, shopify_product_id: int):
    """
    Type 2 SCD update flow:

    1. Fetch current product from Shopify
    2. Get current version from our DB
    3. Compare key fields (price, title, etc.)
    4. If different:
       a. Close current version (set effective_to = now)
       b. Create new version (effective_from = now, is_current = True)
    5. If same: do nothing (idempotent)
    """

    shopify_data = self._fetch_from_shopify(shopify_product_id)
    current_version = self.product_repo.get_current(shopify_product_id)

    if not current_version:
        # First sync - create initial version
        self.product_repo.create(shopify_data)
        return {"action": "created"}

    # Check if anything changed
    changes = self._detect_changes(current_version, shopify_data)

    if not changes:
        return {"action": "unchanged"}

    # Close current version
    current_version.effective_to = datetime.utcnow()
    current_version.is_current = False

    # Create new version
    new_version = self.product_repo.create(
        shopify_data,
        version_number=current_version.version_number + 1,
        change_reason=", ".join(changes),
    )

    return {"action": "updated", "changes": changes}
```

---

## Success Metrics

- **Sync latency**: Webhook → DB update < 5 seconds
- **Data freshness**: Products < 5 min behind Shopify
- **Sync reliability**: > 99.9% webhook success rate
- **History accuracy**: All price changes captured
- **Order coverage**: 100% of orders tracked
