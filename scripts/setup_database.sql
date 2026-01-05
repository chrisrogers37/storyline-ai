-- Storyline AI Database Schema
-- Phase 1: Core Tables

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table (auto-populated from Telegram interactions)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Telegram identity (source of truth)
    telegram_user_id BIGINT UNIQUE NOT NULL,
    telegram_username VARCHAR(100),
    telegram_first_name VARCHAR(255),
    telegram_last_name VARCHAR(255),

    -- Team
    team_name VARCHAR(255),

    -- Role (manually assigned via CLI)
    role VARCHAR(50) DEFAULT 'member', -- 'admin', 'member'
    is_active BOOLEAN DEFAULT TRUE,

    -- Auto-tracked stats
    total_posts INTEGER DEFAULT 0,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_user_id);

-- Media items table (source of truth for all media)
CREATE TABLE IF NOT EXISTS media_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_path TEXT NOT NULL UNIQUE,
    file_name TEXT NOT NULL,
    file_size BIGINT NOT NULL,
    file_hash TEXT NOT NULL, -- Not unique - allow duplicate content
    mime_type VARCHAR(100),

    -- Routing logic: determines auto vs manual posting
    requires_interaction BOOLEAN DEFAULT FALSE, -- TRUE = send to Telegram, FALSE = auto-post

    -- Optional metadata (flexible for any use case)
    title TEXT, -- General purpose title (product name, meme title, etc.)
    link_url TEXT, -- Link for sticker (if requires_interaction = TRUE)
    caption TEXT,
    tags TEXT[], -- Array of custom tags (user-defined)
    custom_metadata JSONB, -- Flexible JSON field for any additional data

    -- Tracking
    times_posted INTEGER DEFAULT 0,
    last_posted_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,

    -- User tracking
    indexed_by_user_id UUID REFERENCES users(id),

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_media_items_file_path ON media_items(file_path);
CREATE INDEX IF NOT EXISTS idx_media_items_file_hash ON media_items(file_hash);
CREATE INDEX IF NOT EXISTS idx_media_items_is_active ON media_items(is_active);
CREATE INDEX IF NOT EXISTS idx_media_items_requires_interaction ON media_items(requires_interaction);
CREATE INDEX IF NOT EXISTS idx_media_items_tags ON media_items USING GIN(tags);

-- Posting queue table (active work items only)
CREATE TABLE IF NOT EXISTS posting_queue (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    media_item_id UUID NOT NULL REFERENCES media_items(id) ON DELETE CASCADE,

    scheduled_for TIMESTAMP NOT NULL,
    status VARCHAR(50) DEFAULT 'pending' NOT NULL, -- 'pending', 'processing', 'retrying'

    -- Temporary web-hosted URL (e.g., Cloudinary, S3, etc.)
    web_hosted_url TEXT,
    web_hosted_public_id TEXT,

    -- Telegram tracking (for manual posts)
    telegram_message_id BIGINT,
    telegram_chat_id BIGINT,

    -- Retry logic
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    next_retry_at TIMESTAMP,
    last_error TEXT,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT check_status CHECK (status IN ('pending', 'processing', 'retrying'))
);

CREATE INDEX IF NOT EXISTS idx_posting_queue_media_item ON posting_queue(media_item_id);
CREATE INDEX IF NOT EXISTS idx_posting_queue_scheduled_for ON posting_queue(scheduled_for);
CREATE INDEX IF NOT EXISTS idx_posting_queue_status ON posting_queue(status);

-- Posting history (permanent audit log - never deleted)
CREATE TABLE IF NOT EXISTS posting_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    media_item_id UUID NOT NULL REFERENCES media_items(id),
    queue_item_id UUID,

    -- Queue lifecycle timestamps
    queue_created_at TIMESTAMP NOT NULL,
    queue_deleted_at TIMESTAMP NOT NULL,
    scheduled_for TIMESTAMP NOT NULL,

    -- Media metadata snapshot
    media_metadata JSONB,

    -- Posting outcome
    posted_at TIMESTAMP NOT NULL,
    status VARCHAR(50) NOT NULL, -- 'posted', 'failed', 'skipped', 'rejected'
    success BOOLEAN NOT NULL,

    -- Instagram result (if successful)
    instagram_media_id TEXT,
    instagram_permalink TEXT,

    -- User tracking
    posted_by_user_id UUID REFERENCES users(id),
    posted_by_telegram_username TEXT,

    -- Error info (if failed)
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT check_history_status CHECK (status IN ('posted', 'failed', 'skipped', 'rejected'))
);

CREATE INDEX IF NOT EXISTS idx_posting_history_media_item ON posting_history(media_item_id);
CREATE INDEX IF NOT EXISTS idx_posting_history_posted_at ON posting_history(posted_at);
CREATE INDEX IF NOT EXISTS idx_posting_history_scheduled_for ON posting_history(scheduled_for);

-- Media posting locks (TTL-based repost prevention)
CREATE TABLE IF NOT EXISTS media_posting_locks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    media_item_id UUID NOT NULL REFERENCES media_items(id) ON DELETE CASCADE,

    -- Lock details
    locked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    locked_until TIMESTAMP, -- NULL = permanent lock (infinite TTL)
    lock_reason VARCHAR(100) DEFAULT 'recent_post', -- 'recent_post', 'manual_hold', 'seasonal', 'permanent_reject'

    -- Who created the lock
    created_by_user_id UUID REFERENCES users(id),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Ensure only one active lock per media item
    CONSTRAINT unique_active_lock UNIQUE (media_item_id, locked_until)
);

CREATE INDEX IF NOT EXISTS idx_media_posting_locks_media_item ON media_posting_locks(media_item_id);
CREATE INDEX IF NOT EXISTS idx_media_posting_locks_locked_until ON media_posting_locks(locked_until);

-- Service runs table (tracks all service executions)
CREATE TABLE IF NOT EXISTS service_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Service identification
    service_name VARCHAR(100) NOT NULL,
    method_name VARCHAR(100) NOT NULL,

    -- Execution context
    user_id UUID REFERENCES users(id),
    triggered_by VARCHAR(50) DEFAULT 'system',

    -- Timing
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    duration_ms INTEGER,

    -- Status
    status VARCHAR(50) NOT NULL DEFAULT 'running',
    success BOOLEAN,

    -- Results
    result_summary JSONB,
    error_message TEXT,
    error_type VARCHAR(100),
    stack_trace TEXT,

    -- Metadata
    input_params JSONB,
    context_metadata JSONB,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT check_service_run_status CHECK (status IN ('running', 'completed', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_service_runs_service_name ON service_runs(service_name);
CREATE INDEX IF NOT EXISTS idx_service_runs_started_at ON service_runs(started_at);
CREATE INDEX IF NOT EXISTS idx_service_runs_status ON service_runs(status);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

-- Insert initial schema version
INSERT INTO schema_version (version, description)
VALUES (1, 'Initial schema - Phase 1')
ON CONFLICT (version) DO NOTHING;
