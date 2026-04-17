-- Migration 024: Clean up phantom DM chat_settings rows
--
-- Deletes chat_settings rows that:
--   1. Have telegram_chat_id > 0 (DM, not group/supergroup)
--   2. Have no references from media_items, posting_queue, posting_history,
--      or user_chat_memberships
--
-- These rows were created by the old get_or_create() behavior in
-- SettingsService.get_settings() when DM users interacted with the bot.
-- Phase 2a's get_settings() split prevents new phantoms.

BEGIN;

DELETE FROM chat_settings
WHERE telegram_chat_id > 0
  AND id NOT IN (SELECT DISTINCT chat_settings_id FROM media_items WHERE chat_settings_id IS NOT NULL)
  AND id NOT IN (SELECT DISTINCT chat_settings_id FROM posting_queue WHERE chat_settings_id IS NOT NULL)
  AND id NOT IN (SELECT DISTINCT chat_settings_id FROM posting_history WHERE chat_settings_id IS NOT NULL)
  AND id NOT IN (SELECT DISTINCT chat_settings_id FROM user_chat_memberships);

INSERT INTO schema_version (version, description, applied_at)
VALUES (24, 'Clean up phantom DM chat_settings rows', NOW());

COMMIT;
