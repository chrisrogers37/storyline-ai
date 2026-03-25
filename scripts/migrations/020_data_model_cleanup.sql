-- Migration 020: Data Model Cleanup
-- Drops vestigial columns, adds missing constraints, fixes types
-- From: Data Model Audit 2026-03-25

BEGIN;

-- =================================================================
-- 1. Drop vestigial columns from posting_queue
-- =================================================================
ALTER TABLE posting_queue DROP COLUMN IF EXISTS web_hosted_url;
ALTER TABLE posting_queue DROP COLUMN IF EXISTS web_hosted_public_id;
ALTER TABLE posting_queue DROP COLUMN IF EXISTS retry_count;
ALTER TABLE posting_queue DROP COLUMN IF EXISTS max_retries;
ALTER TABLE posting_queue DROP COLUMN IF EXISTS next_retry_at;
ALTER TABLE posting_queue DROP COLUMN IF EXISTS last_error;

-- Update CHECK constraint to remove 'retrying'
ALTER TABLE posting_queue DROP CONSTRAINT IF EXISTS check_status;
ALTER TABLE posting_queue ADD CONSTRAINT check_status
    CHECK (status IN ('pending', 'processing'));

-- =================================================================
-- 2. Drop write-only columns from posting_history
-- =================================================================
ALTER TABLE posting_history DROP COLUMN IF EXISTS media_metadata;
ALTER TABLE posting_history DROP COLUMN IF EXISTS error_message;
ALTER TABLE posting_history DROP COLUMN IF EXISTS retry_count;

-- =================================================================
-- 3. Drop requires_interaction from media_items
-- =================================================================
DROP INDEX IF EXISTS idx_media_items_requires_interaction;
ALTER TABLE media_items DROP COLUMN IF EXISTS requires_interaction;

-- =================================================================
-- 4. Drop unused columns from users
-- =================================================================
ALTER TABLE users DROP COLUMN IF EXISTS team_name;
ALTER TABLE users DROP COLUMN IF EXISTS first_seen_at;

-- Add role CHECK constraint
ALTER TABLE users DROP CONSTRAINT IF EXISTS check_user_role;
ALTER TABLE users ADD CONSTRAINT check_user_role
    CHECK (role IN ('admin', 'member'));

-- =================================================================
-- 5. Drop chat_name from chat_settings
-- =================================================================
ALTER TABLE chat_settings DROP COLUMN IF EXISTS chat_name;

-- =================================================================
-- 6. Add lock_reason CHECK constraint
-- =================================================================
ALTER TABLE media_posting_locks DROP CONSTRAINT IF EXISTS check_lock_reason;
ALTER TABLE media_posting_locks ADD CONSTRAINT check_lock_reason
    CHECK (lock_reason IN ('recent_post', 'skip', 'manual_hold', 'seasonal', 'permanent_reject'));

-- =================================================================
-- 7. Record migration
-- =================================================================
INSERT INTO schema_version (version, description, applied_at)
VALUES (20, 'Data model cleanup: drop vestigial columns, add constraints', NOW());

COMMIT;
