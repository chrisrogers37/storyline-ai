-- Migration 021: Fix permanent lock uniqueness
-- The old UniqueConstraint on (media_item_id, locked_until, chat_settings_id)
-- was broken for permanent locks because NULL != NULL in SQL, allowing
-- duplicate permanent locks per media item.
--
-- Fix: Replace with partial unique indexes that correctly handle NULLs.

BEGIN;

-- =================================================================
-- 1. Drop the broken unique constraint
-- =================================================================
ALTER TABLE media_posting_locks
    DROP CONSTRAINT IF EXISTS unique_active_lock_per_tenant;

-- Also drop the pre-tenant version if it exists
ALTER TABLE media_posting_locks
    DROP CONSTRAINT IF EXISTS unique_active_lock;

-- =================================================================
-- 2. Add partial unique indexes for permanent locks
-- =================================================================

-- Tenanted permanent locks: one per media item per tenant
CREATE UNIQUE INDEX IF NOT EXISTS unique_permanent_lock_per_tenant
    ON media_posting_locks (media_item_id, chat_settings_id)
    WHERE locked_until IS NULL AND chat_settings_id IS NOT NULL;

-- Legacy (NULL tenant) permanent locks: one per media item
CREATE UNIQUE INDEX IF NOT EXISTS unique_permanent_lock_legacy
    ON media_posting_locks (media_item_id)
    WHERE locked_until IS NULL AND chat_settings_id IS NULL;

-- =================================================================
-- 3. Record migration
-- =================================================================
INSERT INTO schema_version (version, description, applied_at)
VALUES (21, 'Fix permanent lock uniqueness with partial unique indexes', NOW());

COMMIT;
