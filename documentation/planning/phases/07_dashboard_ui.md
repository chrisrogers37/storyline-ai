# Phase 8: Dashboard UI

**Status**: 📋 PENDING
**Dependencies**: Phase 5 (Media-Product Linking), Phase 6 (LLM)
**Estimated Duration**: 4-6 weeks

---

## Overview

Build a web-based dashboard for analytics, media management, and team collaboration. The UI complements the Telegram bot (which remains the primary operational interface) by providing rich visualizations and bulk operations.

### Goals

1. Analytics dashboard with sales/posting correlation
2. Media library browser with filtering and bulk actions
3. Product performance visualization
4. Team activity feed
5. Settings and configuration management

### Non-Goals (This Phase)

- Replacing Telegram for day-to-day operations
- Mobile app (responsive web is sufficient)
- Real-time collaboration features
- Direct Instagram posting from UI (use Telegram workflow)

---

## Tech Stack

```
Frontend:
├── Next.js 14 (App Router)
├── TypeScript
├── Tailwind CSS
├── shadcn/ui components
├── Recharts / Tremor (visualizations)
├── TanStack Query (data fetching)
└── Zustand (client state)

Backend:
├── FastAPI (existing API layer)
├── JWT authentication
└── WebSocket for real-time updates
```

---

## Sub-Phase Breakdown

### 8.1 Foundation & Authentication
**Duration**: 1 week

**Deliverables**:
- Next.js project setup with TypeScript
- Authentication flow (JWT from FastAPI)
- Layout components (sidebar, header)
- Dark/light theme support

### 8.2 Analytics Dashboard
**Duration**: 1.5 weeks

**Deliverables**:
- Overview page with key metrics
- Revenue charts (daily, weekly, monthly)
- Posting frequency visualization
- Top performing content cards
- Sales correlation insights

### 8.3 Media Library
**Duration**: 1.5 weeks

**Deliverables**:
- Grid/list view with thumbnails
- Advanced filtering (category, tags, date, status)
- Bulk actions (tag, link to product, archive)
- Media detail panel
- Upload new media

### 8.4 Product & Performance
**Duration**: 1 week

**Deliverables**:
- Product catalog browser
- Product performance metrics
- Media-product relationship view
- Attribution visualization
- Margin analysis (Shopify vs Printify)

### 8.5 Team & Settings
**Duration**: 1 week

**Deliverables**:
- Team activity feed
- User management
- System settings
- Integration status dashboard
- Prompt template management (Phase 6)

---

## UI/UX Design

### Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  Logo   [Search...]                    [Notifications] [Avatar] │
├────────┬────────────────────────────────────────────────────────┤
│        │                                                        │
│ MENU   │                    MAIN CONTENT                        │
│        │                                                        │
│ Home   │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│ Media  │  │ Revenue  │ │  Posts   │ │  Orders  │ │  Margin  │  │
│ Products│  │  $12.5K  │ │   145    │ │    89    │ │   48%    │  │
│ Orders │  │  ↑ 12%   │ │  ↓ 5%    │ │  ↑ 23%   │ │  → 0%    │  │
│ Team   │  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│ Settings│                                                        │
│        │  ┌────────────────────────────────────────────────────┐│
│        │  │                                                    ││
│        │  │              Revenue vs Posts Chart                ││
│        │  │                                                    ││
│        │  └────────────────────────────────────────────────────┘│
│        │                                                        │
│        │  ┌─────────────────────┐ ┌────────────────────────────┐│
│        │  │  Top Media          │ │  Recent Activity           ││
│        │  │  • meme_042.jpg     │ │  • @chris posted story     ││
│        │  │  • hoodie_promo.mp4 │ │  • Order #1234 received    ││
│        │  │  • ugc_review.jpg   │ │  • Product price updated   ││
│        │  └─────────────────────┘ └────────────────────────────┘│
└────────┴────────────────────────────────────────────────────────┘
```

### Media Library View

```
┌─────────────────────────────────────────────────────────────────┐
│ Media Library                          [Upload] [Grid] [List]   │
├─────────────────────────────────────────────────────────────────┤
│ Filters: [Category ▼] [Tags ▼] [Status ▼] [Date Range]  [Clear]│
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │
│  │ [img]   │ │ [img]   │ │ [img]   │ │ [img]   │ │ [img]   │  │
│  │ ☑       │ │         │ │ ☑       │ │         │ │         │  │
│  │ meme_01 │ │ meme_02 │ │ merch_1 │ │ ugc_01  │ │ promo_1 │  │
│  │ 📊 12   │ │ 📊 8    │ │ 📊 23   │ │ 📊 5    │ │ 📊 0    │  │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘  │
│                                                                 │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │
│  │ [img]   │ │ [img]   │ │ [img]   │ │ [img]   │ │ [img]   │  │
│  │         │ │         │ │         │ │         │ │         │  │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘  │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│ 2 selected  [Link to Product] [Add Tags] [Archive] [Delete]     │
└─────────────────────────────────────────────────────────────────┘
```

---

## API Endpoints Required

### Dashboard Analytics

```python
# src/api/routes/dashboard.py

@router.get("/analytics/overview")
async def get_overview(
    period: str = "30d",  # '7d', '30d', '90d', 'ytd'
) -> DashboardOverview:
    """
    Returns:
        {
            "revenue": {"value": 12500.00, "change": 0.12},
            "orders": {"value": 89, "change": 0.23},
            "posts": {"value": 145, "change": -0.05},
            "margin": {"value": 0.48, "change": 0.00},
            "top_media": [...],
            "recent_activity": [...],
        }
    """
    pass

@router.get("/analytics/revenue-chart")
async def get_revenue_chart(
    period: str = "30d",
    granularity: str = "daily",  # 'daily', 'weekly', 'monthly'
) -> List[ChartDataPoint]:
    """Time series data for revenue chart."""
    pass

@router.get("/analytics/correlation")
async def get_correlation_data(
    period: str = "30d",
) -> CorrelationData:
    """
    Returns posting vs sales correlation data.
    """
    pass
```

### Media Library

```python
# src/api/routes/media.py

@router.get("/media")
async def list_media(
    page: int = 1,
    per_page: int = 50,
    category: Optional[str] = None,
    tags: Optional[List[str]] = None,
    status: Optional[str] = None,  # 'active', 'archived', 'locked'
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> PaginatedResponse[MediaItem]:
    """List media with filtering and pagination."""
    pass

@router.get("/media/{media_id}")
async def get_media(media_id: str) -> MediaDetailResponse:
    """
    Get media details including:
    - Basic info (path, hash, dimensions)
    - Posting history
    - Linked products
    - Performance metrics
    - Lock status
    """
    pass

@router.post("/media/bulk-action")
async def bulk_action(
    media_ids: List[str],
    action: str,  # 'tag', 'link_product', 'archive', 'delete'
    params: dict,
) -> BulkActionResult:
    """Execute bulk action on multiple media items."""
    pass

@router.post("/media/upload")
async def upload_media(
    file: UploadFile,
    category: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> MediaItem:
    """Upload new media file."""
    pass
```

### Products

```python
# src/api/routes/products.py

@router.get("/products")
async def list_products(
    page: int = 1,
    per_page: int = 50,
    source: Optional[str] = None,  # 'shopify', 'printify'
    sort_by: str = "revenue",
) -> PaginatedResponse[ProductWithMetrics]:
    """List products with performance metrics."""
    pass

@router.get("/products/{product_id}/performance")
async def get_product_performance(
    product_id: str,
    source: str,
    period: str = "30d",
) -> ProductPerformanceDetail:
    """
    Detailed performance for a product:
    - Revenue over time
    - Posting frequency
    - Attribution breakdown
    - Margin analysis
    """
    pass

@router.get("/products/{product_id}/media")
async def get_product_media(
    product_id: str,
    source: str,
) -> List[MediaItem]:
    """Get all media linked to a product."""
    pass
```

### Team & Settings

```python
# src/api/routes/team.py

@router.get("/team/activity")
async def get_activity_feed(
    page: int = 1,
    per_page: int = 50,
    user_id: Optional[str] = None,
) -> PaginatedResponse[ActivityItem]:
    """
    Activity feed showing:
    - Posts made
    - Media uploaded
    - Products linked
    - Settings changed
    """
    pass

@router.get("/team/users")
async def list_users() -> List[UserWithStats]:
    """List team members with activity stats."""
    pass

# src/api/routes/settings.py

@router.get("/settings/integrations")
async def get_integration_status() -> IntegrationStatusResponse:
    """
    Status of all integrations:
    - Instagram API (connected, token expiry)
    - Shopify (connected, last sync)
    - Printify (connected, last sync)
    - Gmail (connected)
    - Telegram (connected)
    """
    pass

@router.get("/settings/category-ratios")
async def get_category_ratios() -> List[CategoryRatio]:
    """Get current posting ratios."""
    pass

@router.put("/settings/category-ratios")
async def update_category_ratios(
    ratios: List[CategoryRatioUpdate],
) -> List[CategoryRatio]:
    """Update posting ratios (creates Type 2 SCD version)."""
    pass
```

---

## Data Models (Frontend)

### TypeScript Types

```typescript
// types/dashboard.ts

interface DashboardOverview {
  revenue: MetricWithChange;
  orders: MetricWithChange;
  posts: MetricWithChange;
  margin: MetricWithChange;
  topMedia: MediaSummary[];
  recentActivity: ActivityItem[];
}

interface MetricWithChange {
  value: number;
  change: number;  // Percentage change vs previous period
}

interface ChartDataPoint {
  date: string;
  value: number;
  label?: string;
}

// types/media.ts

interface MediaItem {
  id: string;
  filePath: string;
  filename: string;
  thumbnailUrl: string;
  category: string;
  tags: string[];
  isActive: boolean;
  timesPosted: number;
  lastPostedAt: string | null;
  createdAt: string;
  lockStatus: LockStatus | null;
}

interface MediaDetail extends MediaItem {
  fileHash: string;
  fileSize: number;
  dimensions: { width: number; height: number };
  duration: number | null;  // For video
  postingHistory: PostingHistoryItem[];
  linkedProducts: LinkedProduct[];
  performanceMetrics: MediaPerformance;
}

interface LockStatus {
  type: 'recent_post' | 'manual_hold' | 'seasonal' | 'permanent_reject';
  lockedUntil: string | null;  // null = permanent
  lockedBy: string | null;
  reason: string | null;
}

// types/products.ts

interface Product {
  id: string;
  source: 'shopify' | 'printify';
  externalId: string;
  title: string;
  description: string;
  price: number;
  compareAtPrice: number | null;
  imageUrl: string;
  status: string;
}

interface ProductWithMetrics extends Product {
  totalRevenue: number;
  totalOrders: number;
  postsFeaturingProduct: number;
  attributedRevenue: number;
  margin: number | null;  // For Printify products
}

// types/team.ts

interface User {
  id: string;
  telegramUsername: string;
  telegramFirstName: string;
  role: 'admin' | 'operator' | 'member';
  createdAt: string;
  lastActiveAt: string;
}

interface ActivityItem {
  id: string;
  type: 'post' | 'upload' | 'link' | 'settings' | 'order';
  description: string;
  user: User | null;
  timestamp: string;
  metadata: Record<string, unknown>;
}
```

---

## Component Structure

```
ui/
├── app/
│   ├── layout.tsx              # Root layout with providers
│   ├── page.tsx                # Dashboard home
│   ├── login/
│   │   └── page.tsx            # Login page
│   ├── media/
│   │   ├── page.tsx            # Media library
│   │   └── [id]/
│   │       └── page.tsx        # Media detail
│   ├── products/
│   │   ├── page.tsx            # Product list
│   │   └── [id]/
│   │       └── page.tsx        # Product detail
│   ├── orders/
│   │   └── page.tsx            # Orders (if Phase 7)
│   ├── team/
│   │   └── page.tsx            # Team & activity
│   └── settings/
│       ├── page.tsx            # General settings
│       ├── integrations/
│       │   └── page.tsx        # Integration status
│       └── prompts/
│           └── page.tsx        # Prompt management
├── components/
│   ├── ui/                     # shadcn/ui components
│   ├── layout/
│   │   ├── Sidebar.tsx
│   │   ├── Header.tsx
│   │   └── PageContainer.tsx
│   ├── dashboard/
│   │   ├── MetricCard.tsx
│   │   ├── RevenueChart.tsx
│   │   ├── CorrelationChart.tsx
│   │   └── ActivityFeed.tsx
│   ├── media/
│   │   ├── MediaGrid.tsx
│   │   ├── MediaCard.tsx
│   │   ├── MediaFilters.tsx
│   │   ├── MediaDetail.tsx
│   │   └── BulkActionBar.tsx
│   └── products/
│       ├── ProductGrid.tsx
│       ├── ProductCard.tsx
│       └── PerformanceChart.tsx
├── lib/
│   ├── api.ts                  # API client
│   ├── auth.ts                 # Auth utilities
│   └── utils.ts                # General utilities
├── hooks/
│   ├── useAuth.ts
│   ├── useMedia.ts
│   └── useProducts.ts
└── stores/
    ├── authStore.ts
    └── uiStore.ts
```

---

## Authentication Flow

```typescript
// lib/auth.ts

interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  expiresAt: number;
}

async function login(telegramData: TelegramLoginData): Promise<AuthTokens> {
  /**
   * Login flow:
   * 1. User clicks "Login with Telegram" widget
   * 2. Telegram returns signed user data
   * 3. Send to /api/auth/telegram endpoint
   * 4. Backend verifies signature, returns JWT
   * 5. Store tokens, redirect to dashboard
   */
  const response = await api.post('/auth/telegram', telegramData);
  return response.data;
}

async function refreshTokens(): Promise<AuthTokens> {
  /**
   * Token refresh:
   * 1. Check if access token expires within 5 minutes
   * 2. Call /api/auth/refresh with refresh token
   * 3. Update stored tokens
   */
  const response = await api.post('/auth/refresh', {
    refreshToken: getRefreshToken(),
  });
  return response.data;
}
```

---

## Configuration

```python
# settings.py additions

class Settings(BaseSettings):
    # Phase 8: Dashboard
    ENABLE_DASHBOARD: bool = False

    # Frontend
    FRONTEND_URL: str = "http://localhost:3000"
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # Auth
    JWT_SECRET_KEY: str  # Required for JWT signing
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Telegram Login Widget
    TELEGRAM_LOGIN_BOT_TOKEN: Optional[str] = None  # Can be same as main bot

    # Media thumbnails
    THUMBNAIL_SIZE: tuple = (300, 300)
    THUMBNAIL_STORAGE: str = "local"  # 'local' or 'cloudinary'
```

---

## Implementation Checklist

### 8.1 Foundation & Authentication
- [ ] Initialize Next.js project with TypeScript
- [ ] Set up Tailwind CSS and shadcn/ui
- [ ] Create layout components (Sidebar, Header)
- [ ] Implement dark/light theme
- [ ] Create API client with interceptors
- [ ] Implement JWT auth flow
- [ ] Add Telegram Login Widget
- [ ] Create auth middleware
- [ ] Add protected route wrapper

### 8.2 Analytics Dashboard
- [ ] Create DashboardOverview API endpoint
- [ ] Build MetricCard component
- [ ] Build RevenueChart component (Recharts)
- [ ] Build CorrelationChart component
- [ ] Build ActivityFeed component
- [ ] Create TopMediaCard component
- [ ] Add date range selector
- [ ] Implement data caching (TanStack Query)

### 8.3 Media Library
- [ ] Create /media API endpoints
- [ ] Build MediaGrid component
- [ ] Build MediaCard with selection
- [ ] Build MediaFilters component
- [ ] Build MediaDetail panel/page
- [ ] Implement bulk selection
- [ ] Build BulkActionBar
- [ ] Add media upload flow
- [ ] Generate and store thumbnails

### 8.4 Product & Performance
- [ ] Create /products API endpoints
- [ ] Build ProductGrid component
- [ ] Build ProductCard with metrics
- [ ] Build product detail page
- [ ] Build PerformanceChart component
- [ ] Build AttributionVisualization
- [ ] Build MarginAnalysis component
- [ ] Link products to media UI

### 8.5 Team & Settings
- [ ] Create /team API endpoints
- [ ] Build ActivityFeed page
- [ ] Build UserList component
- [ ] Build SettingsForm components
- [ ] Build IntegrationStatus cards
- [ ] Build CategoryRatioEditor
- [ ] Build PromptTemplateManager (Phase 6)
- [ ] Add WebSocket for real-time updates

---

## Performance Considerations

### Frontend Optimization

```typescript
// Lazy loading for heavy components
const RevenueChart = dynamic(() => import('@/components/dashboard/RevenueChart'), {
  loading: () => <ChartSkeleton />,
});

// Image optimization with Next.js
<Image
  src={media.thumbnailUrl}
  alt={media.filename}
  width={300}
  height={300}
  placeholder="blur"
  blurDataURL={media.blurHash}
/>

// Infinite scrolling for media grid
const { data, fetchNextPage, hasNextPage } = useInfiniteQuery({
  queryKey: ['media', filters],
  queryFn: ({ pageParam = 1 }) => fetchMedia({ ...filters, page: pageParam }),
  getNextPageParam: (lastPage) => lastPage.nextPage,
});
```

### Backend Optimization

```python
# Thumbnail generation on ingest
async def generate_thumbnail(file_path: str) -> str:
    """Generate and cache thumbnail."""
    pass

# Aggregated metrics caching
@cache(ttl=300)  # 5 minute cache
async def get_dashboard_overview(period: str) -> dict:
    """Cache dashboard metrics."""
    pass

# Efficient media listing with cursor pagination
async def list_media_cursor(
    cursor: Optional[str] = None,
    limit: int = 50,
) -> CursorPaginatedResponse:
    """Use cursor for efficient large dataset pagination."""
    pass
```

---

## Responsive Design

```css
/* Tailwind breakpoints used */
/* sm: 640px - Mobile landscape */
/* md: 768px - Tablet */
/* lg: 1024px - Desktop */
/* xl: 1280px - Large desktop */

/* Media grid responsive */
.media-grid {
  @apply grid gap-4;
  @apply grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6;
}

/* Sidebar collapses on mobile */
.sidebar {
  @apply fixed lg:static;
  @apply -translate-x-full lg:translate-x-0;
  @apply transition-transform;
}
```

---

## Success Metrics

- **Page load time**: < 2 seconds for dashboard
- **Media grid performance**: Smooth scrolling with 1000+ items
- **Search responsiveness**: < 200ms for filtered results
- **Mobile usability**: Full functionality on tablet
- **User adoption**: Team uses dashboard for analytics (not just Telegram)
