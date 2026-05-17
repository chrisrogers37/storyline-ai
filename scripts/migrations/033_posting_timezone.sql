-- Migration 033: Add timezone awareness to posting window.
-- posting_hours_start/end are now interpreted in the user's local timezone
-- instead of UTC. NULL = UTC for backward compatibility.
BEGIN;

ALTER TABLE chat_settings
ADD COLUMN IF NOT EXISTS posting_timezone VARCHAR(50);

COMMENT ON COLUMN chat_settings.posting_timezone IS
    'IANA timezone (e.g. America/New_York). NULL = UTC.';

INSERT INTO schema_version (version, description, applied_at)
VALUES ('033', 'Per-chat posting timezone for window hours', NOW());

COMMIT;
