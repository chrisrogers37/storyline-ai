-- Migration 022: Add auth_method to instagram_accounts
-- Tracks how accounts were connected: 'oauth', 'manual', or NULL (legacy)

ALTER TABLE instagram_accounts ADD COLUMN IF NOT EXISTS auth_method VARCHAR(20);

INSERT INTO schema_version (version, description, applied_at)
VALUES (22, 'Add auth_method column to instagram_accounts', NOW());
