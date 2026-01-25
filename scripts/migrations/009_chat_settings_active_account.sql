-- Migration: 009_chat_settings_active_account.sql
-- Description: Add active_instagram_account_id to chat_settings for account switching
-- Date: 2026-01-24

-- Add active account selection column
ALTER TABLE chat_settings
ADD COLUMN IF NOT EXISTS active_instagram_account_id UUID REFERENCES instagram_accounts(id);

-- Index for joins when loading settings with account
CREATE INDEX IF NOT EXISTS idx_chat_settings_active_account
ON chat_settings(active_instagram_account_id) WHERE active_instagram_account_id IS NOT NULL;

-- Record migration
INSERT INTO schema_version (version, description, applied_at)
VALUES (9, 'Add active_instagram_account_id to chat_settings', NOW())
ON CONFLICT DO NOTHING;
