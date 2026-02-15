BEGIN;

-- Add chat_settings_id FK to api_tokens for per-tenant Google Drive tokens
ALTER TABLE api_tokens
    ADD COLUMN IF NOT EXISTS chat_settings_id UUID REFERENCES chat_settings(id);

CREATE INDEX IF NOT EXISTS idx_api_tokens_chat_settings ON api_tokens (chat_settings_id);

-- Partial unique constraint for google_drive tokens (one per tenant per token type)
CREATE UNIQUE INDEX IF NOT EXISTS unique_google_drive_token_per_chat
    ON api_tokens (service_name, token_type, chat_settings_id)
    WHERE service_name = 'google_drive' AND chat_settings_id IS NOT NULL;

INSERT INTO schema_version (version, description, applied_at)
VALUES (15, 'Add chat_settings_id FK to api_tokens for per-tenant Google Drive tokens', NOW());

COMMIT;
