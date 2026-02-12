-- Migration 011: Add media source columns for provider abstraction
-- Phase 01 of cloud media enhancement
--
-- Adds source_type and source_identifier columns to media_items.
-- These columns allow the system to track where media originated from
-- (local filesystem, Google Drive, S3, etc.).
--
-- For existing records:
--   source_type = 'local' (default)
--   source_identifier = file_path (backfilled from existing column)

BEGIN;

-- Add source columns
ALTER TABLE media_items
    ADD COLUMN source_type VARCHAR(50) NOT NULL DEFAULT 'local',
    ADD COLUMN source_identifier TEXT;

-- Backfill source_identifier from file_path for all existing records
UPDATE media_items SET source_identifier = file_path WHERE source_identifier IS NULL;

-- Create composite index for provider-based lookups
CREATE INDEX idx_media_items_source_type_identifier
    ON media_items (source_type, source_identifier);

-- Record migration
INSERT INTO schema_version (version, description, applied_at)
VALUES (11, 'Add media source columns (source_type, source_identifier)', NOW());

COMMIT;
