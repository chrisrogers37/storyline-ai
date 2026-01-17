-- Migration 004: Instagram API Phase 2 support
-- Date: 2026-01-11
-- Description: Add cloud storage fields, Instagram posting tracking, and API tokens table
--
-- Run on local:
--   psql -U storyline_user -d storyline_ai -f scripts/migrations/004_instagram_api_phase2.sql
--
-- Run on Pi:
--   PGPASSWORD=your_password psql -h localhost -U storyline_user -d storyline_ai -f scripts/migrations/004_instagram_api_phase2.sql

BEGIN;

-- ============================================================================
-- 1. Add cloud storage fields to media_items
-- ============================================================================
-- These fields track temporary cloud uploads for Instagram API posting.
-- After successful posting, cloud_url is cleared (media deleted from cloud).

ALTER TABLE media_items ADD COLUMN IF NOT EXISTS cloud_url TEXT;
ALTER TABLE media_items ADD COLUMN IF NOT EXISTS cloud_public_id TEXT;
ALTER TABLE media_items ADD COLUMN IF NOT EXISTS cloud_uploaded_at TIMESTAMP;
ALTER TABLE media_items ADD COLUMN IF NOT EXISTS cloud_expires_at TIMESTAMP;

COMMENT ON COLUMN media_items.cloud_url IS 'Temporary Cloudinary URL for Instagram API posting';
COMMENT ON COLUMN media_items.cloud_public_id IS 'Cloudinary public_id for deletion after posting';
COMMENT ON COLUMN media_items.cloud_uploaded_at IS 'When media was uploaded to cloud storage';
COMMENT ON COLUMN media_items.cloud_expires_at IS 'When the cloud URL expires (for signed URLs)';

-- ============================================================================
-- 2. Add Instagram-specific fields to posting_history
-- ============================================================================

ALTER TABLE posting_history ADD COLUMN IF NOT EXISTS instagram_story_id TEXT;
ALTER TABLE posting_history ADD COLUMN IF NOT EXISTS posting_method VARCHAR(20) DEFAULT 'telegram_manual';

COMMENT ON COLUMN posting_history.instagram_story_id IS 'Story ID from Meta Graph API (when posted via API)';
COMMENT ON COLUMN posting_history.posting_method IS 'How the post was made: instagram_api or telegram_manual';

-- Add check constraint for posting_method values
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'check_posting_method'
    ) THEN
        ALTER TABLE posting_history ADD CONSTRAINT check_posting_method
            CHECK (posting_method IN ('instagram_api', 'telegram_manual'));
    END IF;
END $$;

-- Index for rate limit calculations (count API posts in last hour)
CREATE INDEX IF NOT EXISTS idx_posting_history_method_posted
    ON posting_history(posting_method, posted_at)
    WHERE posting_method = 'instagram_api';

-- ============================================================================
-- 3. Backfill existing history records as telegram_manual
-- ============================================================================

UPDATE posting_history
SET posting_method = 'telegram_manual'
WHERE posting_method IS NULL;

-- ============================================================================
-- 4. Create api_tokens table for OAuth token storage
-- ============================================================================

CREATE TABLE IF NOT EXISTS api_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Token identification
    service_name VARCHAR(50) NOT NULL,      -- 'instagram', 'shopify', etc.
    token_type VARCHAR(50) NOT NULL,        -- 'access_token', 'refresh_token'

    -- Token data (encrypted at application level)
    token_value TEXT NOT NULL,

    -- Lifecycle tracking
    issued_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP,                   -- NULL = never expires
    last_refreshed_at TIMESTAMP,

    -- OAuth metadata
    scopes TEXT[],                          -- Array of granted scopes
    token_metadata JSONB,                   -- Service-specific data (e.g., account_id)

    -- Audit timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Only one token per service/type combination
    UNIQUE(service_name, token_type)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_api_tokens_service ON api_tokens(service_name);
CREATE INDEX IF NOT EXISTS idx_api_tokens_expires ON api_tokens(expires_at)
    WHERE expires_at IS NOT NULL;

COMMENT ON TABLE api_tokens IS 'OAuth tokens for external services (Instagram, Shopify, etc.)';
COMMENT ON COLUMN api_tokens.token_value IS 'Encrypted token value (Fernet encryption)';
COMMENT ON COLUMN api_tokens.expires_at IS 'NULL means token never expires';
COMMENT ON COLUMN api_tokens.scopes IS 'OAuth scopes granted with this token';

-- ============================================================================
-- 5. Track migration version
-- ============================================================================

INSERT INTO schema_version (version, description)
VALUES (4, 'Instagram API Phase 2: cloud storage fields, posting_method tracking, api_tokens table')
ON CONFLICT (version) DO NOTHING;

COMMIT;

-- ============================================================================
-- Verification queries (run after migration to verify):
-- ============================================================================
-- SELECT * FROM schema_version ORDER BY version;
-- \d media_items
-- \d posting_history
-- \d api_tokens
-- SELECT COUNT(*) FROM posting_history WHERE posting_method = 'telegram_manual';
