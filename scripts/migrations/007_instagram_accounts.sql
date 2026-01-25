-- Migration: 007_instagram_accounts.sql
-- Description: Create instagram_accounts table for multi-account support
-- Date: 2026-01-24

-- Enable UUID extension if not exists
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS instagram_accounts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Account identification
    display_name VARCHAR(100) NOT NULL,           -- User-friendly name: "Main Brand"
    instagram_account_id VARCHAR(50) NOT NULL,    -- Meta's account ID (numeric string)
    instagram_username VARCHAR(50),               -- @username for display

    -- Status
    is_active BOOLEAN DEFAULT true,               -- Can be disabled without deletion

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT unique_instagram_account UNIQUE (instagram_account_id)
);

-- Index for quick lookup of active accounts
CREATE INDEX IF NOT EXISTS idx_instagram_accounts_active
ON instagram_accounts(is_active) WHERE is_active = true;

-- Record migration
INSERT INTO schema_version (version, description, applied_at)
VALUES (7, 'Add instagram_accounts table for multi-account support', NOW())
ON CONFLICT DO NOTHING;
