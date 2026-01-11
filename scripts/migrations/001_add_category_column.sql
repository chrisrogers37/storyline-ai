-- Migration: Add category column to media_items
-- Description: Stores the category extracted from folder structure during indexing
-- Date: 2026-01-10

-- Add the category column
ALTER TABLE media_items
ADD COLUMN IF NOT EXISTS category TEXT;

-- Create index for efficient category queries
CREATE INDEX IF NOT EXISTS idx_media_items_category ON media_items(category);

-- Record migration in schema_version if table exists
-- (Create the table if it doesn't exist)
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Record this migration
INSERT INTO schema_version (version, description)
VALUES (1, 'Add category column to media_items')
ON CONFLICT (version) DO NOTHING;
