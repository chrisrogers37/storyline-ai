# Phase 2: Instagram API Automation

**Status**: 📋 PLANNED
**Dependencies**: Phase 1.6 (Category Scheduling)
**Estimated Duration**: 3-4 weeks

---

## Overview

Enable automated Instagram Story posting via Meta Graph API while maintaining manual posting capability for complex content.

### Goals

1. Automate posting of simple content (no product tags, no interactive elements)
2. Maintain Telegram workflow for content requiring manual attention
3. Handle token refresh and API rate limits gracefully
4. Provide fallback to manual mode on API failures

### Non-Goals (This Phase)

- Instagram Reels or Feed posts (future phase)
- Direct messaging automation
- Comment management
- Analytics collection (Phase 5)

---

## Sub-Phase Breakdown

### 2.1 Cloud Storage Integration
**Duration**: 1 week

Instagram API requires publicly accessible URLs for media. We need cloud storage.

**Deliverables**:
- CloudStorageService (abstraction for Cloudinary/S3)
- Media upload on demand (not pre-upload all)
- URL expiration handling
- Cleanup of uploaded media after posting

### 2.2 Instagram API Service
**Duration**: 1 week

Core integration with Meta Graph API for Stories.

**Deliverables**:
- InstagramAPIService with authentication
- Story creation endpoint wrapper
- Error handling and categorization
- Rate limit awareness

### 2.3 Token Management
**Duration**: 0.5 weeks

Long-lived tokens and automatic refresh.

**Deliverables**:
- TokenRefreshService
- Encrypted token storage
- Refresh scheduling (before expiry)
- Alert on refresh failures

### 2.4 Hybrid Posting Logic
**Duration**: 0.5-1 week

Smart routing between automated and manual posting.

**Deliverables**:
- Update PostingService routing logic
- `requires_interaction` flag handling
- Fallback to Telegram on API failure
- Success/failure tracking in history

---

## Data Model Changes

### New Fields on Existing Tables

```sql
-- media_items: Track cloud upload status
ALTER TABLE media_items ADD COLUMN IF NOT EXISTS
    cloud_url TEXT;  -- Cloudinary/S3 URL when uploaded
ALTER TABLE media_items ADD COLUMN IF NOT EXISTS
    cloud_uploaded_at TIMESTAMP;
ALTER TABLE media_items ADD COLUMN IF NOT EXISTS
    cloud_expires_at TIMESTAMP;  -- For signed URLs

-- posting_history: Track Instagram-specific data
ALTER TABLE posting_history ADD COLUMN IF NOT EXISTS
    instagram_story_id TEXT;  -- Story ID from Meta API
ALTER TABLE posting_history ADD COLUMN IF NOT EXISTS
    posting_method VARCHAR(20);  -- 'instagram_api', 'telegram_manual'
```

### New Table: API Tokens

```sql
CREATE TABLE IF NOT EXISTS api_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Token identification
    service_name VARCHAR(50) NOT NULL,  -- 'instagram', 'shopify', etc.
    token_type VARCHAR(50) NOT NULL,     -- 'access_token', 'refresh_token'

    -- Token data (encrypted at rest)
    token_value TEXT NOT NULL,

    -- Lifecycle
    issued_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP,  -- NULL = never expires
    last_refreshed_at TIMESTAMP,

    -- Metadata
    scopes TEXT[],  -- Array of granted scopes
    metadata JSONB,  -- Service-specific data

    -- Audit
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    UNIQUE(service_name, token_type)
);

CREATE INDEX idx_api_tokens_service ON api_tokens(service_name);
CREATE INDEX idx_api_tokens_expires ON api_tokens(expires_at);
```

---

## Service Interfaces

### CloudStorageService

```python
# src/services/integrations/cloud_storage.py

class CloudStorageService(BaseService):
    """
    Abstraction for cloud storage (Cloudinary/S3).

    Handles media upload for Instagram API which requires public URLs.
    """

    def __init__(self, provider: str = "cloudinary"):
        super().__init__()
        self.provider = provider
        # Initialize provider-specific client

    async def upload_media(
        self,
        file_path: str,
        public_id: Optional[str] = None,
        folder: str = "storyline",
        expires_in_hours: int = 24,
    ) -> dict:
        """
        Upload media file to cloud storage.

        Args:
            file_path: Local path to media file
            public_id: Optional custom identifier
            folder: Cloud folder/prefix
            expires_in_hours: URL expiration time

        Returns:
            {
                "url": "https://...",
                "public_id": "storyline/abc123",
                "expires_at": datetime,
                "size_bytes": 1234567,
            }
        """
        pass

    async def delete_media(self, public_id: str) -> bool:
        """Delete uploaded media from cloud storage."""
        pass

    async def get_url(
        self,
        public_id: str,
        expires_in_hours: int = 1,
    ) -> str:
        """Get (possibly signed) URL for existing upload."""
        pass

    def cleanup_expired(self) -> int:
        """Remove uploads older than retention period. Returns count."""
        pass
```

### InstagramAPIService

```python
# src/services/integrations/instagram_api.py

class InstagramAPIService(BaseService):
    """
    Instagram Graph API integration for Stories.

    Uses Meta's Content Publishing API:
    https://developers.facebook.com/docs/instagram-api/guides/content-publishing
    """

    def __init__(self):
        super().__init__()
        self.token_service = TokenRefreshService()
        self.cloud_service = CloudStorageService()

    async def post_story(
        self,
        media_url: str,
        media_type: str = "IMAGE",  # IMAGE or VIDEO
    ) -> dict:
        """
        Post a Story to Instagram.

        Args:
            media_url: Public URL to media (from CloudStorageService)
            media_type: IMAGE or VIDEO

        Returns:
            {
                "success": True,
                "story_id": "17895695668004550",
                "timestamp": datetime,
            }

        Raises:
            InstagramAPIError: On API failure (with error code)
            RateLimitError: When rate limited
            TokenExpiredError: When token needs refresh
        """
        pass

    async def check_media_status(self, container_id: str) -> dict:
        """Check status of media container (for async uploads)."""
        pass

    def get_rate_limit_status(self) -> dict:
        """
        Get current rate limit status.

        Returns:
            {
                "remaining": 25,
                "limit": 25,
                "reset_at": datetime,
            }
        """
        pass

    async def validate_media(self, media_url: str) -> dict:
        """
        Validate media meets Instagram requirements.

        Returns:
            {
                "valid": True,
                "warnings": [],
                "errors": [],
            }
        """
        pass
```

### TokenRefreshService

```python
# src/services/integrations/token_refresh.py

class TokenRefreshService(BaseService):
    """
    Manage OAuth tokens for external services.

    Handles:
    - Token storage (encrypted)
    - Automatic refresh before expiry
    - Alerting on refresh failures
    """

    def __init__(self):
        super().__init__()
        self.token_repo = TokenRepository()

    def get_token(self, service: str, token_type: str = "access_token") -> str:
        """Get current valid token for service."""
        pass

    async def refresh_token(self, service: str) -> bool:
        """
        Refresh token for service.

        Returns True if refresh successful.
        Alerts admin on failure.
        """
        pass

    def schedule_refresh(self, service: str, buffer_hours: int = 24):
        """Schedule token refresh before expiry."""
        pass

    def check_token_health(self, service: str) -> dict:
        """
        Check token status.

        Returns:
            {
                "valid": True,
                "expires_in_hours": 168,
                "last_refreshed": datetime,
                "needs_refresh": False,
            }
        """
        pass
```

---

## Updated PostingService Logic

```python
# src/services/core/posting.py (updated)

async def _route_post(self, queue_item, media_item) -> dict:
    """
    Route post to appropriate channel based on settings and content.

    Decision tree:
    1. If ENABLE_INSTAGRAM_API = False → Telegram
    2. If media.requires_interaction = True → Telegram
    3. If Instagram API healthy → Instagram API
    4. Fallback → Telegram
    """

    # Phase 1 mode: Everything goes to Telegram
    if not settings.ENABLE_INSTAGRAM_API:
        return await self._post_via_telegram(queue_item)

    # Content that needs human interaction
    if media_item.requires_interaction:
        logger.info(f"Media {media_item.id} requires interaction, routing to Telegram")
        return await self._post_via_telegram(queue_item)

    # Try Instagram API
    try:
        result = await self._post_via_instagram(queue_item, media_item)
        if result["success"]:
            return result
    except (RateLimitError, TokenExpiredError) as e:
        logger.warning(f"Instagram API unavailable: {e}, falling back to Telegram")
    except InstagramAPIError as e:
        logger.error(f"Instagram API error: {e}, falling back to Telegram")

    # Fallback to Telegram
    return await self._post_via_telegram(queue_item)

async def _post_via_instagram(self, queue_item, media_item) -> dict:
    """
    Post via Instagram API.

    Steps:
    1. Upload to cloud storage (if not already)
    2. Post to Instagram
    3. Record result
    4. Cleanup cloud storage (async)
    """

    # Ensure media is in cloud storage
    if not media_item.cloud_url or self._is_url_expired(media_item):
        upload_result = await self.cloud_service.upload_media(
            file_path=media_item.file_path
        )
        media_item.cloud_url = upload_result["url"]
        media_item.cloud_uploaded_at = datetime.utcnow()
        media_item.cloud_expires_at = upload_result["expires_at"]
        self.media_repo.update(media_item)

    # Post to Instagram
    result = await self.instagram_service.post_story(
        media_url=media_item.cloud_url,
        media_type="IMAGE" if media_item.mime_type.startswith("image") else "VIDEO",
    )

    if result["success"]:
        # Update queue status
        self.queue_repo.update_status(str(queue_item.id), "posted")

        # Create history record
        self.history_repo.create(
            media_item_id=str(media_item.id),
            queue_item_id=str(queue_item.id),
            status="posted",
            success=True,
            posting_method="instagram_api",
            instagram_story_id=result["story_id"],
            # ... other fields
        )

        # Create lock
        self.lock_service.create_lock(str(media_item.id))

        # Delete from queue
        self.queue_repo.delete(str(queue_item.id))

        # Schedule cloud cleanup (don't await)
        asyncio.create_task(self._cleanup_cloud_media(media_item))

    return result
```

---

## Configuration

### New Settings

```python
# src/config/settings.py additions

class Settings(BaseSettings):
    # ... existing settings ...

    # Phase 2: Instagram API
    ENABLE_INSTAGRAM_API: bool = False
    INSTAGRAM_ACCOUNT_ID: Optional[str] = None
    INSTAGRAM_ACCESS_TOKEN: Optional[str] = None  # Initial token
    FACEBOOK_APP_ID: Optional[str] = None
    FACEBOOK_APP_SECRET: Optional[str] = None

    # Phase 2: Cloud Storage
    CLOUD_STORAGE_PROVIDER: str = "cloudinary"  # or "s3"

    # Cloudinary
    CLOUDINARY_CLOUD_NAME: Optional[str] = None
    CLOUDINARY_API_KEY: Optional[str] = None
    CLOUDINARY_API_SECRET: Optional[str] = None

    # S3 (alternative)
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_S3_BUCKET: Optional[str] = None
    AWS_S3_REGION: str = "us-east-1"

    # Rate limiting
    INSTAGRAM_POSTS_PER_HOUR: int = 25  # Meta's limit
    CLOUD_UPLOAD_RETENTION_HOURS: int = 24
```

### Environment Variables

```bash
# .env additions for Phase 2

# Feature flag
ENABLE_INSTAGRAM_API=true

# Instagram API (from Meta Developer Portal)
INSTAGRAM_ACCOUNT_ID=17841400000000000
FACEBOOK_APP_ID=123456789
FACEBOOK_APP_SECRET=abc123...

# Cloudinary (recommended for simplicity)
CLOUDINARY_CLOUD_NAME=your-cloud
CLOUDINARY_API_KEY=123456789
CLOUDINARY_API_SECRET=abc123...

# OR S3
# AWS_ACCESS_KEY_ID=AKIA...
# AWS_SECRET_ACCESS_KEY=...
# AWS_S3_BUCKET=storyline-media
```

---

## Testing Requirements

### Unit Tests

```python
# tests/src/services/test_cloud_storage.py
class TestCloudStorageService:
    def test_upload_media_success(self)
    def test_upload_media_invalid_file(self)
    def test_delete_media(self)
    def test_get_signed_url(self)
    def test_cleanup_expired(self)

# tests/src/services/test_instagram_api.py
class TestInstagramAPIService:
    def test_post_story_success(self)
    def test_post_story_rate_limited(self)
    def test_post_story_token_expired(self)
    def test_validate_media(self)
    def test_check_media_status(self)

# tests/src/services/test_token_refresh.py
class TestTokenRefreshService:
    def test_get_valid_token(self)
    def test_refresh_token_success(self)
    def test_refresh_token_failure_alerts(self)
    def test_check_token_health(self)
```

### Integration Tests

```python
# tests/integration/test_instagram_posting.py
class TestInstagramPostingIntegration:
    def test_full_posting_flow_api(self)  # Mock Instagram API
    def test_fallback_to_telegram_on_api_error(self)
    def test_requires_interaction_routes_to_telegram(self)
    def test_cloud_cleanup_after_post(self)
```

---

## Implementation Checklist

### 2.1 Cloud Storage Integration
- [ ] Create `src/services/integrations/cloud_storage.py`
- [ ] Implement Cloudinary provider
- [ ] Implement S3 provider (optional)
- [ ] Add cloud fields to `media_items` table
- [ ] Write unit tests
- [ ] Add configuration settings
- [ ] Document in CLAUDE.md

### 2.2 Instagram API Service
- [ ] Create `src/services/integrations/instagram_api.py`
- [ ] Implement story posting
- [ ] Implement error handling
- [ ] Add rate limit tracking
- [ ] Write unit tests
- [ ] Add configuration settings

### 2.3 Token Management
- [ ] Create `api_tokens` table
- [ ] Create `src/repositories/token_repository.py`
- [ ] Create `src/services/integrations/token_refresh.py`
- [ ] Implement Instagram token refresh
- [ ] Add refresh scheduling
- [ ] Write unit tests

### 2.4 Hybrid Posting Logic
- [ ] Update `PostingService._route_post()`
- [ ] Add `posting_method` to history
- [ ] Implement fallback logic
- [ ] Write integration tests
- [ ] Update health check for Instagram API status
- [ ] Add Telegram notification on API failures

---

## Rollout Plan

### Stage 1: Development
1. Implement cloud storage with test account
2. Implement Instagram API with sandbox
3. Full test coverage

### Stage 2: Staging
1. Deploy with `ENABLE_INSTAGRAM_API=false`
2. Test cloud uploads manually
3. Test Instagram API in sandbox mode

### Stage 3: Production (Gradual)
1. Enable for 1 post/day initially
2. Monitor error rates and fallback frequency
3. Increase to full automation
4. Keep Telegram as backup always available

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Meta API changes | High | Version lock SDK, monitor deprecation notices |
| Token expiry | High | Auto-refresh with 24h buffer, admin alerts |
| Rate limits | Medium | Queue aware of limits, spread posts evenly |
| Cloud storage costs | Low | Cleanup after posting, compress images |
| API downtime | Medium | Auto-fallback to Telegram, health monitoring |

---

## Success Metrics

- **Automation rate**: % of posts via API vs manual
- **API error rate**: < 1% failures
- **Fallback frequency**: < 5% posts requiring Telegram fallback
- **Token refresh success**: 100% (any failure is critical)
- **Cloud storage costs**: < $10/month at current volume
