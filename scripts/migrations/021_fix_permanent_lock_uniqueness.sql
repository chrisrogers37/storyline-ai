-- Migration 021: Fix permanent lock uniqueness
-- The old UniqueConstraint on (media_item_id, locked_until) was broken
-- for permanent locks because NULL != NULL in SQL, allowing duplicate
-- permanent locks per media item.
--
-- Fix: Replace with a partial unique index that correctly handles NULLs.
--
-- Note: media_posting_locks does not have chat_settings_id in the DB
-- (multi-tenant FK was not added to this table). The index is per-media-item only.

BEGIN;

-- =================================================================
-- 1. Drop the broken unique constraint
-- =================================================================
ALTER TABLE media_posting_locks
    DROP CONSTRAINT IF EXISTS unique_active_lock;

ALTER TABLE media_posting_locks
    DROP CONSTRAINT IF EXISTS unique_active_lock_per_tenant;

-- =================================================================
-- 2. Add partial unique index for permanent locks
-- =================================================================

-- One permanent lock per media item
CREATE UNIQUE INDEX IF NOT EXISTS unique_permanent_lock_per_media
    ON media_posting_locks (media_item_id)
    WHERE locked_until IS NULL;

-- =================================================================
-- 3. Record migration
-- =================================================================
INSERT INTO schema_version (version, description, applied_at)
VALUES (21, 'Fix permanent lock uniqueness with partial unique index', NOW());

COMMIT;
