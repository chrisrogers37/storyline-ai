-- Migration 027: Fix onboarding_completed for bootstrapped chats
--
-- get_or_create() was missing onboarding_completed=True when
-- bootstrapping new chat_settings from .env defaults. Migration 016
-- backfilled existing rows, but any row created after that (including
-- rows recreated after migration 024 cleanup) defaulted to FALSE.
--
-- This caused get_all_active() to return empty — the scheduler ran
-- but found no eligible chats, silently producing zero posts.
--
-- Fix: set onboarding_completed=TRUE for all non-paused chats.
-- These are legitimate deployment chats, not half-setup test instances.

BEGIN;

UPDATE chat_settings
SET onboarding_completed = TRUE
WHERE onboarding_completed = FALSE
  AND is_paused = FALSE;

INSERT INTO schema_version (version, description, applied_at)
VALUES (27, 'Fix onboarding_completed for bootstrapped chats', NOW());

COMMIT;
