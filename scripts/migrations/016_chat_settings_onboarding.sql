BEGIN;

-- Add onboarding wizard tracking columns to chat_settings
ALTER TABLE chat_settings
    ADD COLUMN IF NOT EXISTS onboarding_step VARCHAR(50) DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS onboarding_completed BOOLEAN DEFAULT FALSE;

-- Backfill: existing chats are already configured (via CLI)
UPDATE chat_settings SET onboarding_completed = TRUE;

INSERT INTO schema_version (version, description, applied_at)
VALUES (16, 'Add onboarding tracking to chat_settings', NOW());

COMMIT;
