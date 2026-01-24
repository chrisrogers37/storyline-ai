-- Migration: 005_add_bot_response_logging
-- Description: Enable logging of outgoing bot messages for visibility
-- Date: 2026-01-24

-- ============================================
-- 1. Make user_id nullable (for bot_response entries)
-- ============================================
ALTER TABLE user_interactions
ALTER COLUMN user_id DROP NOT NULL;

-- ============================================
-- 2. Update check constraint to allow 'bot_response'
-- ============================================
ALTER TABLE user_interactions
DROP CONSTRAINT IF EXISTS check_interaction_type;

ALTER TABLE user_interactions
ADD CONSTRAINT check_interaction_type
CHECK (interaction_type IN ('command', 'callback', 'message', 'bot_response'));

-- ============================================
-- 3. Add index for bot_response queries
-- ============================================
CREATE INDEX IF NOT EXISTS idx_user_interactions_bot_response
ON user_interactions (created_at DESC)
WHERE interaction_type = 'bot_response';

-- ============================================
-- Record migration
-- ============================================
INSERT INTO schema_version (version, description, applied_at)
VALUES (5, 'Add bot_response logging for Telegram visibility', NOW())
ON CONFLICT DO NOTHING;
