-- Migration 025: Create audit_log table
--
-- Tracks settings changes, membership role changes, and media lock
-- lifecycle for multi-account team accountability.
-- See issue #244.

BEGIN;

CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID,
    action VARCHAR(20) NOT NULL,
    field_changed VARCHAR(100),
    old_value TEXT,
    new_value TEXT,
    changed_by_user_id UUID REFERENCES users(id),
    chat_settings_id UUID REFERENCES chat_settings(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT check_audit_entity_type CHECK (entity_type IN ('setting', 'membership', 'lock')),
    CONSTRAINT check_audit_action CHECK (action IN ('create', 'update', 'delete'))
);

CREATE INDEX IF NOT EXISTS idx_audit_log_entity_type ON audit_log(entity_type);
CREATE INDEX IF NOT EXISTS idx_audit_log_entity_id ON audit_log(entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_chat_settings_id ON audit_log(chat_settings_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_changed_by ON audit_log(changed_by_user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_log_instance_time ON audit_log(chat_settings_id, created_at DESC);

INSERT INTO schema_version (version, description, applied_at)
VALUES ('025', 'Create audit_log table for settings/membership/lock changes', NOW());

COMMIT;
