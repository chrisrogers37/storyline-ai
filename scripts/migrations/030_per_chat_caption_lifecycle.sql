-- Migration 030: Move CAPTION_STYLE and SEND_LIFECYCLE_NOTIFICATIONS to chat_settings.
-- Final pass of the env→DB audit. Existing chats get their current env values
-- backfilled at bootstrap time; new chats receive hardcoded defaults from
-- ChatSettingsRepository.get_or_create.
BEGIN;

ALTER TABLE chat_settings
ADD COLUMN IF NOT EXISTS caption_style TEXT;

ALTER TABLE chat_settings
ADD COLUMN IF NOT EXISTS send_lifecycle_notifications BOOLEAN;

INSERT INTO schema_version (version, description, applied_at)
VALUES ('030', 'Per-chat caption_style and send_lifecycle_notifications', NOW());

COMMIT;
