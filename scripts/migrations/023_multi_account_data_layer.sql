-- Migration 023: Multi-account data layer
--
-- Phase 1a of multi-account dashboard migration.
-- Adds:
--   1. user_chat_memberships table (user ↔ chat_settings join table)
--   2. onboarding_sessions table (DM onboarding state machine)
--   3. display_name column on chat_settings
--   4. Backfill index on user_interactions for future migration script
--
-- All changes are additive. No existing data modified.

BEGIN;

-- ============================================================
-- 1. user_chat_memberships
-- ============================================================

CREATE TABLE user_chat_memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    chat_settings_id UUID NOT NULL REFERENCES chat_settings(id),
    instance_role VARCHAR(20) NOT NULL DEFAULT 'member',
    joined_at TIMESTAMP NOT NULL DEFAULT NOW(),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT unique_user_chat_membership UNIQUE (user_id, chat_settings_id),
    CONSTRAINT check_instance_role CHECK (instance_role IN ('owner', 'admin', 'member'))
);

CREATE INDEX idx_ucm_user_id ON user_chat_memberships(user_id)
    WHERE is_active = TRUE;

CREATE INDEX idx_ucm_chat_settings_id ON user_chat_memberships(chat_settings_id)
    WHERE is_active = TRUE;

-- ============================================================
-- 2. onboarding_sessions
-- ============================================================

CREATE TABLE onboarding_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    step VARCHAR(50) NOT NULL DEFAULT 'naming',
    pending_instance_name VARCHAR(100),
    pending_chat_settings_id UUID REFERENCES chat_settings(id),
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_active_onboarding UNIQUE (user_id),
    CONSTRAINT check_onboarding_step CHECK (step IN ('naming', 'awaiting_group', 'complete'))
);

-- ============================================================
-- 3. display_name on chat_settings
-- ============================================================

ALTER TABLE chat_settings ADD COLUMN display_name VARCHAR(100);

-- (Section 4 — backfill index — runs after COMMIT below because
--  CREATE INDEX CONCURRENTLY cannot run inside a transaction block.)

-- ============================================================
-- Record migration
-- ============================================================

INSERT INTO schema_version (version, description, applied_at)
VALUES (23, 'Multi-account data layer: user_chat_memberships, onboarding_sessions, display_name', NOW());

COMMIT;

-- ============================================================
-- 4. Backfill index on user_interactions (outside transaction —
--    CREATE INDEX CONCURRENTLY cannot run inside a transaction block)
-- ============================================================

-- Supports the Phase 1b backfill query:
--   SELECT DISTINCT user_id, telegram_chat_id FROM user_interactions
--   WHERE user_id IS NOT NULL AND telegram_chat_id < 0
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_interactions_backfill
    ON user_interactions(user_id, telegram_chat_id)
    WHERE user_id IS NOT NULL AND telegram_chat_id < 0;
