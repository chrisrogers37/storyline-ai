-- Migration 003: Add user_interactions table
-- Run on Pi: PGPASSWORD=storyline2024 psql -h localhost -U storyline_user -d storyline_ai -f scripts/migrations/003_add_user_interactions.sql

-- User interactions table (tracks all bot interactions for analytics)
CREATE TABLE IF NOT EXISTS user_interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Who performed the interaction
    user_id UUID NOT NULL REFERENCES users(id),

    -- What type of interaction
    interaction_type VARCHAR(50) NOT NULL,  -- 'command', 'callback', 'message'
    interaction_name VARCHAR(100) NOT NULL, -- '/queue', '/status', 'posted', 'skip', etc.

    -- Flexible context data
    context JSONB,  -- {queue_item_id, media_id, items_shown, etc.}

    -- Telegram metadata
    telegram_chat_id BIGINT,
    telegram_message_id BIGINT,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT check_interaction_type CHECK (interaction_type IN ('command', 'callback', 'message'))
);

CREATE INDEX IF NOT EXISTS idx_user_interactions_user_id ON user_interactions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_interactions_type ON user_interactions(interaction_type);
CREATE INDEX IF NOT EXISTS idx_user_interactions_name ON user_interactions(interaction_name);
CREATE INDEX IF NOT EXISTS idx_user_interactions_created_at ON user_interactions(created_at);
CREATE INDEX IF NOT EXISTS idx_user_interactions_context ON user_interactions USING GIN(context);

-- Update schema version
INSERT INTO schema_version (version, description)
VALUES (3, 'Add user_interactions table for tracking bot interactions')
ON CONFLICT (version) DO NOTHING;

-- Verify table was created
SELECT 'user_interactions table created successfully' AS status
WHERE EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'user_interactions');
