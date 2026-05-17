-- Migration 032: Add revocation timestamp for compromised OAuth tokens.
-- Revoked tokens are filtered out of all retrieval queries (revoked_at IS NULL).
-- Provider revoke APIs (Meta DELETE /permissions, Google POST /revoke) are called
-- before setting this column, so the token is invalidated upstream first.
BEGIN;

ALTER TABLE api_tokens
ADD COLUMN IF NOT EXISTS revoked_at TIMESTAMPTZ;

INSERT INTO schema_version (version, description, applied_at)
VALUES ('032', 'Token revocation timestamp for compromised OAuth tokens', NOW());

COMMIT;
