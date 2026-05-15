-- Migration 031: Persist Google Drive disconnect alert state per chat.
-- Replaces the in-memory PostingService._last_gdrive_alert_time cooldown so
-- the alert behaves as a state transition (fires once per disconnect,
-- self-clears on reconnect) instead of a recurring hourly event.
BEGIN;

ALTER TABLE chat_settings
ADD COLUMN IF NOT EXISTS gdrive_alerted_at TIMESTAMPTZ;

INSERT INTO schema_version (version, description, applied_at)
VALUES ('031', 'Per-chat Google Drive disconnect alert state', NOW());

COMMIT;
