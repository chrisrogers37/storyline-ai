-- Migration 026: Add AI caption generation support
-- Adds enable_ai_captions toggle to chat_settings and generated_caption to media_items
BEGIN;

ALTER TABLE chat_settings
ADD COLUMN IF NOT EXISTS enable_ai_captions BOOLEAN DEFAULT FALSE;

ALTER TABLE media_items
ADD COLUMN IF NOT EXISTS generated_caption TEXT;

INSERT INTO schema_version (version, description, applied_at)
VALUES ('026', 'Add AI caption generation support', NOW());

COMMIT;
