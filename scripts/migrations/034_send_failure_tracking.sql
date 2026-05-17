-- Migration 034: Add send failure tracking
-- Supports retry logic for Telegram send failures (#359)

-- Allow 'failed' status in posting_queue (items no longer deleted on failure)
ALTER TABLE posting_queue DROP CONSTRAINT IF EXISTS check_status;
ALTER TABLE posting_queue ADD CONSTRAINT check_status
    CHECK (status IN ('pending', 'processing', 'failed'));

-- Add error_message column to posting_history for failure diagnostics
ALTER TABLE posting_history ADD COLUMN IF NOT EXISTS error_message TEXT;
