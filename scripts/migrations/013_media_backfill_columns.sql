-- Migration 013: Add Instagram backfill tracking columns to media_items
-- Phase 05 of cloud media enhancement
--
-- Adds instagram_media_id and backfilled_at columns to media_items.
-- These columns track which items were imported from Instagram's API
-- and prevent duplicate backfill downloads.
--
-- instagram_media_id: The Instagram Graph API media ID (e.g., "17841405793087218")
-- backfilled_at: When this item was backfilled from Instagram (NULL = not backfilled)

BEGIN;

-- Add backfill tracking columns
ALTER TABLE media_items
    ADD COLUMN instagram_media_id TEXT,
    ADD COLUMN backfilled_at TIMESTAMP;

-- Index for duplicate prevention during backfill
CREATE UNIQUE INDEX idx_media_items_instagram_media_id
    ON media_items (instagram_media_id)
    WHERE instagram_media_id IS NOT NULL;

-- Record migration
INSERT INTO schema_version (version, description, applied_at)
VALUES (13, 'Add Instagram backfill tracking columns (instagram_media_id, backfilled_at)', NOW());

COMMIT;
