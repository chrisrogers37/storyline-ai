-- Migration 029: Per-chat lock TTLs
-- Surface REPOST_TTL_DAYS and SKIP_TTL_DAYS to chat_settings so each tenant
-- can pick its own reuse cadence. NULL = use deployment env default.
BEGIN;

ALTER TABLE chat_settings
ADD COLUMN IF NOT EXISTS repost_ttl_days INTEGER;

ALTER TABLE chat_settings
ADD COLUMN IF NOT EXISTS skip_ttl_days INTEGER;

INSERT INTO schema_version (version, description, applied_at)
VALUES ('029', 'Per-chat lock TTLs (repost_ttl_days, skip_ttl_days)', NOW());

COMMIT;
