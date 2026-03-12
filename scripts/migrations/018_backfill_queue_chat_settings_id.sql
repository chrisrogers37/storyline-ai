-- Migration 018: Backfill chat_settings_id on orphaned posting_queue items
--
-- Queue items created by the scheduler before this fix had chat_settings_id = NULL.
-- The scheduler's process_pending_posts() filters by chat_settings_id, so NULL items
-- are invisible to the processing loop — they pile up but never get posted.
--
-- This migration assigns all NULL-tenant queue items to the production chat
-- (-1003688539654, chat_settings_id = 951b9100-de61-4330-9d06-d6f1b155e927).
--
-- Safe to run: only affects rows with chat_settings_id IS NULL.

BEGIN;

UPDATE posting_queue
SET chat_settings_id = '951b9100-de61-4330-9d06-d6f1b155e927'
WHERE chat_settings_id IS NULL;

INSERT INTO schema_version (version, description, applied_at)
VALUES (18, 'Backfill chat_settings_id on orphaned posting_queue items', NOW());

COMMIT;
