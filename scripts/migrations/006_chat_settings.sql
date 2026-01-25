-- Migration: 006_chat_settings.sql
-- Description: Add chat_settings table for runtime configuration
-- Created: 2026-01-24
--
-- This table enables runtime-configurable settings with .env fallback.
-- For Phase 1, there will be one record per deployment.
-- Phase 3 introduces true multi-tenancy with one record per chat.

-- Enable UUID extension if not exists
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS chat_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Chat identification (for future multi-tenancy)
    -- For Phase 1: Use ADMIN_TELEGRAM_CHAT_ID as the single chat
    telegram_chat_id BIGINT NOT NULL UNIQUE,
    chat_name VARCHAR(255),

    -- Operational settings (mirrors .env defaults)
    dry_run_mode BOOLEAN DEFAULT true,
    enable_instagram_api BOOLEAN DEFAULT false,
    is_paused BOOLEAN DEFAULT false,
    paused_at TIMESTAMP,           -- When paused (NULL if not paused)
    paused_by_user_id UUID REFERENCES users(id),  -- Who paused

    -- Schedule settings
    posts_per_day INTEGER DEFAULT 3,
    posting_hours_start INTEGER DEFAULT 14,  -- UTC hour (0-23)
    posting_hours_end INTEGER DEFAULT 2,     -- UTC hour (0-23)

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT valid_posts_per_day CHECK (posts_per_day BETWEEN 1 AND 50),
    CONSTRAINT valid_hours_start CHECK (posting_hours_start BETWEEN 0 AND 23),
    CONSTRAINT valid_hours_end CHECK (posting_hours_end BETWEEN 0 AND 23)
);

-- Index for quick lookup by telegram chat ID
CREATE INDEX IF NOT EXISTS idx_chat_settings_telegram_id ON chat_settings(telegram_chat_id);

-- Record migration
INSERT INTO schema_version (version, description, applied_at)
VALUES (6, 'Add chat_settings table for runtime configuration', NOW())
ON CONFLICT DO NOTHING;
