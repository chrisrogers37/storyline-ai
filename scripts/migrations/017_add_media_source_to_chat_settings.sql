BEGIN;

-- Add per-chat media source configuration columns
-- NULL = use global env var fallback (backward compatible)
ALTER TABLE chat_settings
    ADD COLUMN IF NOT EXISTS media_source_type VARCHAR(50) DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS media_source_root TEXT DEFAULT NULL;

-- No backfill needed: NULL means "use global env var"
-- Existing chats continue to use MEDIA_SOURCE_TYPE / MEDIA_SOURCE_ROOT from .env

INSERT INTO schema_version (version, description, applied_at)
VALUES (17, 'Add media_source_type and media_source_root to chat_settings', NOW());

COMMIT;
