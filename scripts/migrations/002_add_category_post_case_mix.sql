-- Migration: Create category_post_case_mix table (Type 2 SCD)
-- Description: Tracks posting ratio configuration per category with full history
-- Date: 2026-01-10

-- Create the category_post_case_mix table
CREATE TABLE IF NOT EXISTS category_post_case_mix (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Category name (matches media_items.category)
    category VARCHAR(100) NOT NULL,

    -- Ratio as decimal (0.70 = 70%)
    ratio NUMERIC(5, 4) NOT NULL,

    -- Type 2 SCD fields
    effective_from TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    effective_to TIMESTAMP,  -- NULL = currently active
    is_current BOOLEAN DEFAULT TRUE,

    -- Audit fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by_user_id UUID REFERENCES users(id),

    -- Constraints
    CONSTRAINT check_ratio_range CHECK (ratio >= 0 AND ratio <= 1)
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_category_mix_category ON category_post_case_mix(category);
CREATE INDEX IF NOT EXISTS idx_category_mix_is_current ON category_post_case_mix(is_current);
CREATE INDEX IF NOT EXISTS idx_category_mix_effective_dates ON category_post_case_mix(effective_from, effective_to);

-- Record migration
INSERT INTO schema_version (version, description)
VALUES (2, 'Add category_post_case_mix table (Type 2 SCD)')
ON CONFLICT (version) DO NOTHING;

-- Comment on table
COMMENT ON TABLE category_post_case_mix IS 'Type 2 SCD table tracking posting ratio configuration per category. All current ratios must sum to 1.0.';
COMMENT ON COLUMN category_post_case_mix.ratio IS 'Posting ratio as decimal (0.70 = 70% of posts will be from this category)';
COMMENT ON COLUMN category_post_case_mix.is_current IS 'TRUE if this is the currently active ratio for this category';
