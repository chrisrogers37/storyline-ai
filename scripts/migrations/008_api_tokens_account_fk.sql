-- Migration: 008_api_tokens_account_fk.sql
-- Description: Add instagram_account_id foreign key to api_tokens table
-- Date: 2026-01-24

-- Add foreign key column to api_tokens
ALTER TABLE api_tokens
ADD COLUMN IF NOT EXISTS instagram_account_id UUID REFERENCES instagram_accounts(id);

-- Drop old unique constraint (one token per service) if it exists
ALTER TABLE api_tokens
DROP CONSTRAINT IF EXISTS unique_service_token_type;

-- Add new unique constraint (one token per service per account)
-- For non-Instagram tokens (e.g., Shopify), instagram_account_id will be NULL
-- The constraint allows: (shopify, access_token, NULL) alongside (instagram, access_token, <uuid>)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'unique_service_token_type_account'
    ) THEN
        ALTER TABLE api_tokens
        ADD CONSTRAINT unique_service_token_type_account
        UNIQUE (service_name, token_type, instagram_account_id);
    END IF;
END $$;

-- Index for efficient lookups by account
CREATE INDEX IF NOT EXISTS idx_api_tokens_instagram_account
ON api_tokens(instagram_account_id) WHERE instagram_account_id IS NOT NULL;

-- Record migration
INSERT INTO schema_version (version, description, applied_at)
VALUES (8, 'Add instagram_account_id FK to api_tokens', NOW())
ON CONFLICT DO NOTHING;
