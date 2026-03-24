-- Migration 019: Add last_post_sent_at to chat_settings for JIT scheduler
--
-- Tracks when the last post was sent to Telegram for each tenant.
-- Used by the JIT scheduler's is_slot_due() to compute posting intervals
-- instead of pre-populating the posting_queue days in advance.

ALTER TABLE chat_settings
ADD COLUMN IF NOT EXISTS last_post_sent_at TIMESTAMPTZ;

-- Backfill from posting_history: set to the most recent posted_at per tenant
UPDATE chat_settings cs
SET last_post_sent_at = sub.latest_post
FROM (
    SELECT ph.chat_settings_id, MAX(ph.posted_at) AS latest_post
    FROM posting_history ph
    WHERE ph.chat_settings_id IS NOT NULL
      AND ph.status = 'posted'
    GROUP BY ph.chat_settings_id
) sub
WHERE cs.id = sub.chat_settings_id
  AND cs.last_post_sent_at IS NULL;

-- Record migration
INSERT INTO schema_version (version, description)
VALUES (19, 'Add last_post_sent_at to chat_settings for JIT scheduler');
