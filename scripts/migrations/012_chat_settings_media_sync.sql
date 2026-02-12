-- Migration 012: Add media_sync_enabled to chat_settings
-- Phase 04 of cloud media enhancements
--
-- Adds per-chat media sync toggle. Bootstrap default comes from
-- MEDIA_SYNC_ENABLED in .env (resolved by ChatSettingsRepository.get_or_create).

BEGIN;

ALTER TABLE chat_settings
    ADD COLUMN media_sync_enabled BOOLEAN DEFAULT FALSE;

-- Backfill existing records to match current .env default
UPDATE chat_settings SET media_sync_enabled = FALSE WHERE media_sync_enabled IS NULL;

-- Record migration
INSERT INTO schema_version (version, description, applied_at)
VALUES (12, 'Add media_sync_enabled to chat_settings', NOW());

COMMIT;
