-- Migration 028: Add thumbnail_url for dashboard preview tiles
-- Populated from Google Drive thumbnailLink during sync; null for local uploads.
BEGIN;

ALTER TABLE media_items
ADD COLUMN IF NOT EXISTS thumbnail_url TEXT;

INSERT INTO schema_version (version, description, applied_at)
VALUES ('028', 'Add thumbnail_url to media_items for preview tiles', NOW());

COMMIT;
