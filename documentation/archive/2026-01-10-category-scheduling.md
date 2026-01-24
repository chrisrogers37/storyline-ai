# Category-Based Scheduling Feature

**Date**: 2026-01-10
**Version**: 1.4.0
**Phase**: 1.6

## Overview

This update introduces category-based media organization and configurable posting ratios. Media is now organized into categories based on folder structure (e.g., `memes/`, `merch/`), and the scheduler allocates posting slots according to configured ratios.

## Features Added

### 1. Category Extraction from Folder Structure

Media files are now automatically categorized based on their folder location during indexing.

**Folder Structure:**
```
media/stories/
├── memes/        → category: "memes"
│   ├── image1.jpg
│   └── image2.png
└── merch/        → category: "merch"
    ├── product1.jpg
    └── product2.png
```

**How it works:**
- During `index-media`, the first-level subfolder becomes the category
- Files directly in the base directory get `category: NULL`
- Category is stored in the `media_items.category` column

### 2. Posting Ratios (Type 2 SCD)

Configure what percentage of posts should come from each category.

**Example Configuration:**
- memes: 70%
- merch: 30%

**Database Design:**
The `category_post_case_mix` table uses Type 2 Slowly Changing Dimension design:
- Maintains full history of ratio changes
- `is_current = true` for active ratios
- `effective_from` / `effective_to` for temporal queries
- Supports auditing and analytics

**Validation:**
- All active ratios must sum to 100% (1.0)
- Ratios stored as decimals (0.70 = 70%)
- Validation occurs before saving

### 3. Scheduler Integration

The scheduler now allocates slots based on configured ratios.

**Algorithm:**
1. Generate time slots for the scheduling period
2. Allocate slots to categories based on ratios (deterministic)
3. Shuffle allocation for variety
4. Select media from each category
5. Fall back to any category if target is exhausted

**Example:**
With 21 total slots and 70/30 ratio:
- 15 slots allocated to memes (70% × 21 ≈ 15)
- 6 slots allocated to merch (30% × 21 ≈ 6)
- Slots are shuffled so posts alternate between categories

### 4. New CLI Commands

#### `list-categories`
Show all categories with media counts and posting ratios.

```bash
storyline-cli list-categories
```

Output:
```
Categories (2 found):
  Category    Items    Ratio
  memes       1287     70.00%
  merch       45       30.00%
```

#### `update-category-mix`
Interactively update posting ratios.

```bash
storyline-cli update-category-mix
```

Prompts:
```
What % would you like 'memes'? 70
What % would you like 'merch'? 30
✓ Category mix updated!
```

#### `category-mix-history`
View history of ratio changes (Type 2 SCD).

```bash
storyline-cli category-mix-history --limit 10
```

### 5. Enhanced Existing Commands

#### `index-media`
- Now extracts categories from folder structure
- Prompts for ratio configuration after indexing new categories

#### `create-schedule`
- Shows category breakdown in output
- Logs allocation summary

#### `list-queue`
- Added category column to queue display

## Database Changes

### New Column: `media_items.category`
```sql
ALTER TABLE media_items ADD COLUMN category TEXT;
CREATE INDEX idx_media_items_category ON media_items(category);
```

### New Table: `category_post_case_mix`
```sql
CREATE TABLE category_post_case_mix (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category VARCHAR(100) NOT NULL,
    ratio NUMERIC(5, 4) NOT NULL,
    effective_from TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    effective_to TIMESTAMP,  -- NULL = currently active
    is_current BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by_user_id UUID REFERENCES users(id),
    CONSTRAINT check_ratio_range CHECK (ratio >= 0 AND ratio <= 1)
);
```

## Migration

### For Existing Installations

Run the migration scripts:

```bash
# Add category column
psql -d storyline_ai -f scripts/migrations/001_add_category_column.sql

# Create ratio table
psql -d storyline_ai -f scripts/migrations/002_add_category_post_case_mix.sql
```

### For Fresh Installations

The `scripts/setup_database.sql` has been updated to include all new schema elements.

```bash
make reset-db
```

## New Components

### Models
- `src/models/category_mix.py` - CategoryPostCaseMix SQLAlchemy model

### Repositories
- `src/repositories/category_mix_repository.py` - Type 2 SCD operations
  - `get_current_mix()` - Get active ratios
  - `get_current_mix_as_dict()` - Get as {category: ratio} dict
  - `set_mix()` - Set new ratios (creates SCD records)
  - `get_history()` - Get all historical records

### Services
- `SchedulerService` - Enhanced with category-aware allocation
  - `_allocate_slots_to_categories()` - Ratio-based slot allocation
  - `_select_media_from_pool()` - Category-filtered selection
  - `_select_media()` - Category with fallback logic

### CLI
- `cli/commands/media.py` - New category commands and prompts

## Testing

34 new tests added:

- **Category extraction** (7 tests)
  - Extract from folder structure
  - Handle nested folders
  - Handle files in root directory

- **CategoryMixRepository** (18 tests)
  - CRUD operations
  - Ratio validation
  - Type 2 SCD behavior
  - History tracking

- **Scheduler category allocation** (9 tests)
  - Slot allocation by ratio
  - Rounding handling
  - Fallback when exhausted
  - Empty ratio handling

**Total test count: 173 → 268**

## Usage Example

### Complete Workflow

1. **Organize media into folders:**
   ```
   media/stories/
   ├── memes/    (your meme content)
   └── merch/    (product photos)
   ```

2. **Index media with category extraction:**
   ```bash
   storyline-cli index-media /path/to/media/stories
   ```

3. **Configure posting ratios when prompted:**
   ```
   What % would you like 'memes'? 70
   What % would you like 'merch'? 30
   ✓ Category mix updated!
   ```

4. **Create schedule (uses ratios automatically):**
   ```bash
   storyline-cli create-schedule --days 7

   ✓ Schedule created!
     Scheduled: 21
     Category breakdown:
       • memes: 15 (71%)
       • merch: 6 (29%)
   ```

5. **View queue with categories:**
   ```bash
   storyline-cli list-queue
   ```

## Technical Notes

### Rounding Behavior
When allocating slots, the last category receives remaining slots to ensure the total matches. For example, with 21 slots and 70/30:
- memes: round(0.7 × 21) = 15
- merch: remaining = 21 - 15 = 6

### Fallback Behavior
If a category is exhausted (all media locked/queued), the scheduler falls back to any available media from other categories. This ensures schedules are always filled.

### SCD Benefits
Type 2 SCD design enables:
- Auditing: "Who changed the ratios and when?"
- Analytics: "What was the ratio when this post was scheduled?"
- Rollback: Easy to see previous configurations

## Known Limitations

1. **Single-level categories**: Only first-level subfolders become categories. Nested folders like `memes/funny/` still map to `memes`.

2. **No ratio scheduling by time**: Ratios are static across the schedule. Future enhancement could support different ratios for different times/days.

3. **Manual ratio updates**: Ratios must be set via CLI. Future Telegram bot command could be added.

---

*For the complete CHANGELOG entry, see [CHANGELOG.md](../../CHANGELOG.md)*
