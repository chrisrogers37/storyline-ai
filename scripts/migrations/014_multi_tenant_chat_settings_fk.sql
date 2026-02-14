-- Migration 014: Add chat_settings_id FK to 5 tables for multi-tenant data model
-- Phase 01 of multi-tenant transition
--
-- Adds a nullable chat_settings_id UUID foreign key column to:
--   1. media_items
--   2. posting_queue
--   3. posting_history
--   4. media_posting_locks
--   5. category_post_case_mix
--
-- api_tokens excluded: tokens are scoped via their service account (instagram_accounts),
-- not directly to tenant.
--
-- All FKs are NULLABLE: NULL means legacy single-tenant data.
-- This ensures full backward compatibility with existing data.
--
-- Unique constraint changes:
--   - media_items: UNIQUE(file_path) -> UNIQUE(file_path, chat_settings_id)
--     + partial index for NULL chat_settings_id to preserve legacy uniqueness
--   - media_posting_locks: UNIQUE(media_item_id, locked_until) -> UNIQUE(media_item_id, locked_until, chat_settings_id)

BEGIN;

-- ============================================================
-- 1. media_items
-- ============================================================

ALTER TABLE media_items
    ADD COLUMN chat_settings_id UUID REFERENCES chat_settings(id);

CREATE INDEX IF NOT EXISTS idx_media_items_chat_settings_id
    ON media_items(chat_settings_id)
    WHERE chat_settings_id IS NOT NULL;

-- Drop old column-level unique constraint on file_path
ALTER TABLE media_items
    DROP CONSTRAINT IF EXISTS media_items_file_path_key;

-- New composite unique constraint: file_path per tenant
ALTER TABLE media_items
    ADD CONSTRAINT unique_file_path_per_tenant
    UNIQUE (file_path, chat_settings_id);

-- Partial unique index for legacy rows (chat_settings_id IS NULL)
-- Without this, multiple NULL-tenant rows with the same file_path would be allowed
-- because PostgreSQL treats NULLs as distinct in unique constraints.
CREATE UNIQUE INDEX IF NOT EXISTS idx_media_items_file_path_legacy_unique
    ON media_items(file_path)
    WHERE chat_settings_id IS NULL;

-- ============================================================
-- 2. posting_queue
-- ============================================================

ALTER TABLE posting_queue
    ADD COLUMN chat_settings_id UUID REFERENCES chat_settings(id);

CREATE INDEX IF NOT EXISTS idx_posting_queue_chat_settings_id
    ON posting_queue(chat_settings_id)
    WHERE chat_settings_id IS NOT NULL;

-- No unique constraint changes needed for posting_queue

-- ============================================================
-- 3. posting_history
-- ============================================================

ALTER TABLE posting_history
    ADD COLUMN chat_settings_id UUID REFERENCES chat_settings(id);

CREATE INDEX IF NOT EXISTS idx_posting_history_chat_settings_id
    ON posting_history(chat_settings_id)
    WHERE chat_settings_id IS NOT NULL;

-- No unique constraint changes needed for posting_history

-- ============================================================
-- 4. media_posting_locks
-- ============================================================

ALTER TABLE media_posting_locks
    ADD COLUMN chat_settings_id UUID REFERENCES chat_settings(id);

CREATE INDEX IF NOT EXISTS idx_media_posting_locks_chat_settings_id
    ON media_posting_locks(chat_settings_id)
    WHERE chat_settings_id IS NOT NULL;

-- Drop old unique constraint and create tenant-scoped version
ALTER TABLE media_posting_locks
    DROP CONSTRAINT IF EXISTS unique_active_lock;

ALTER TABLE media_posting_locks
    ADD CONSTRAINT unique_active_lock_per_tenant
    UNIQUE (media_item_id, locked_until, chat_settings_id);

-- ============================================================
-- 5. category_post_case_mix
-- ============================================================

ALTER TABLE category_post_case_mix
    ADD COLUMN chat_settings_id UUID REFERENCES chat_settings(id);

CREATE INDEX IF NOT EXISTS idx_category_post_case_mix_chat_settings_id
    ON category_post_case_mix(chat_settings_id)
    WHERE chat_settings_id IS NOT NULL;

-- No unique constraint changes needed (only has check constraint on ratio)

-- ============================================================
-- Record migration
-- ============================================================

INSERT INTO schema_version (version, description, applied_at)
VALUES (14, 'Add chat_settings_id FK to 5 tables for multi-tenant data model', NOW());

COMMIT;
