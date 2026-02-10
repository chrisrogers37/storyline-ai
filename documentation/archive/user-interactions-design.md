# User Interactions System Design

**Created**: 2026-01-06
**Status**: ✅ COMPLETE (Implemented in Phase 1.5)
**Phase**: Implemented as part of Phase 1.5 Telegram Enhancements
**Priority**: Delivered

## Overview

A dedicated system for tracking all user interactions with the Storyline AI bot. This enables analytics, audit trails, and usage insights while maintaining strict separation of concerns.

## Goals

1. **Track all user interactions** - Commands, button clicks, and messages
2. **Enable analytics** - Understand usage patterns, team activity, content decisions
3. **Maintain audit trail** - Who did what, when
4. **Separation of concerns** - Dedicated service, not mixed into TelegramService

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  TelegramService (Interface Layer)                          │
│  • Handles bot commands and callbacks                       │
│  • Delegates interaction logging to InteractionService      │
└─────────────────────────┬───────────────────────────────────┘
                          │ logs interaction
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  InteractionService (Service Layer)                         │
│  • log_command() - Track /queue, /status, etc.              │
│  • log_callback() - Track posted, skip, reject buttons      │
│  • get_user_stats() - Analytics for a user                  │
│  • get_team_activity() - Team-wide analytics                │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  InteractionRepository (Repository Layer)                   │
│  • create() - Insert interaction record                     │
│  • get_by_user() - Query by user                            │
│  • get_by_type() - Query by interaction type                │
│  • get_counts() - Aggregated counts                         │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  UserInteraction (Model Layer)                              │
│  • Database schema definition                               │
└─────────────────────────────────────────────────────────────┘
```

## Data Model

### Table: `user_interactions`

```sql
CREATE TABLE IF NOT EXISTS user_interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Who performed the interaction
    user_id UUID NOT NULL REFERENCES users(id),

    -- What type of interaction
    interaction_type VARCHAR(50) NOT NULL,  -- 'command', 'callback', 'message'
    interaction_name VARCHAR(100) NOT NULL, -- '/queue', '/status', 'posted', 'skip', 'reject'

    -- Flexible context data
    context JSONB,  -- {queue_item_id, media_id, items_shown, response_time_ms, etc.}

    -- Telegram metadata (for potential message editing/reference)
    telegram_chat_id BIGINT,
    telegram_message_id BIGINT,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT check_interaction_type CHECK (interaction_type IN ('command', 'callback', 'message'))
);

-- Indexes for common queries
CREATE INDEX idx_user_interactions_user_id ON user_interactions(user_id);
CREATE INDEX idx_user_interactions_type ON user_interactions(interaction_type);
CREATE INDEX idx_user_interactions_name ON user_interactions(interaction_name);
CREATE INDEX idx_user_interactions_created_at ON user_interactions(created_at);
CREATE INDEX idx_user_interactions_context ON user_interactions USING GIN(context);
```

### SQLAlchemy Model

```python
# src/models/user_interaction.py

class UserInteraction(Base):
    """User interaction model - tracks all bot interactions."""

    __tablename__ = "user_interactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Who
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # What
    interaction_type = Column(String(50), nullable=False, index=True)
    interaction_name = Column(String(100), nullable=False, index=True)

    # Context
    context = Column(JSONB)

    # Telegram metadata
    telegram_chat_id = Column(BigInteger)
    telegram_message_id = Column(BigInteger)

    # When
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        CheckConstraint(
            "interaction_type IN ('command', 'callback', 'message')",
            name="check_interaction_type"
        ),
    )
```

## Interaction Types

### Commands (`interaction_type = 'command'`)

| `interaction_name` | Description | Context Fields |
|--------------------|-------------|----------------|
| `/queue` | View upcoming queue | `{items_shown, total_queue}` |
| `/status` | Check system status | `{queue_size, media_count, uptime_hours}` |
| `/help` | View help message | `{}` |
| `/start` | Initial bot interaction | `{}` |

### Callbacks (`interaction_type = 'callback'`)

| `interaction_name` | Description | Context Fields |
|--------------------|-------------|----------------|
| `posted` | Marked as posted | `{queue_item_id, media_id, media_filename}` |
| `skip` | Skipped for later | `{queue_item_id, media_id, media_filename}` |
| `reject` | Initiated rejection | `{queue_item_id, media_id, media_filename}` |
| `confirm_reject` | Confirmed permanent rejection | `{queue_item_id, media_id, media_filename}` |
| `cancel_reject` | Cancelled rejection | `{queue_item_id, media_id}` |

### Messages (`interaction_type = 'message'`)

Reserved for future use (e.g., if users can send text messages to the bot).

## Service Layer

### InteractionService

```python
# src/services/core/interaction_service.py

class InteractionService(BaseService):
    """
    Service for tracking user interactions.

    Responsibilities:
    - Log all user interactions (commands, callbacks)
    - Provide analytics queries
    - NOT responsible for handling the interactions themselves
    """

    def __init__(self):
        super().__init__()
        self.interaction_repo = InteractionRepository()

    # ─────────────────────────────────────────────────────────────
    # Logging Methods
    # ─────────────────────────────────────────────────────────────

    def log_command(
        self,
        user_id: str,
        command: str,
        context: Optional[dict] = None,
        telegram_chat_id: Optional[int] = None,
        telegram_message_id: Optional[int] = None,
    ) -> UserInteraction:
        """
        Log a command interaction (e.g., /queue, /status).

        Args:
            user_id: UUID of the user
            command: Command name (e.g., '/queue', '/status')
            context: Optional context data
            telegram_chat_id: Telegram chat ID
            telegram_message_id: Telegram message ID

        Returns:
            Created UserInteraction record
        """
        return self.interaction_repo.create(
            user_id=user_id,
            interaction_type="command",
            interaction_name=command,
            context=context,
            telegram_chat_id=telegram_chat_id,
            telegram_message_id=telegram_message_id,
        )

    def log_callback(
        self,
        user_id: str,
        callback_name: str,
        context: Optional[dict] = None,
        telegram_chat_id: Optional[int] = None,
        telegram_message_id: Optional[int] = None,
    ) -> UserInteraction:
        """
        Log a callback interaction (e.g., posted, skip, reject).

        Args:
            user_id: UUID of the user
            callback_name: Callback name (e.g., 'posted', 'skip')
            context: Optional context data (queue_item_id, media_id, etc.)
            telegram_chat_id: Telegram chat ID
            telegram_message_id: Telegram message ID

        Returns:
            Created UserInteraction record
        """
        return self.interaction_repo.create(
            user_id=user_id,
            interaction_type="callback",
            interaction_name=callback_name,
            context=context,
            telegram_chat_id=telegram_chat_id,
            telegram_message_id=telegram_message_id,
        )

    # ─────────────────────────────────────────────────────────────
    # Analytics Methods
    # ─────────────────────────────────────────────────────────────

    def get_user_stats(self, user_id: str, days: int = 30) -> dict:
        """
        Get interaction statistics for a specific user.

        Returns:
            {
                "total_interactions": 45,
                "posts_marked": 20,
                "posts_skipped": 15,
                "posts_rejected": 2,
                "commands_used": {"queue": 5, "status": 3},
                "most_active_hour": 14,
            }
        """
        return self.interaction_repo.get_user_stats(user_id, days)

    def get_team_activity(self, days: int = 30) -> dict:
        """
        Get team-wide activity statistics.

        Returns:
            {
                "total_interactions": 150,
                "active_users": 3,
                "interactions_by_user": {...},
                "interactions_by_type": {...},
                "daily_activity": [...],
            }
        """
        return self.interaction_repo.get_team_activity(days)

    def get_content_decisions(self, days: int = 30) -> dict:
        """
        Get statistics on content decisions (posted vs skipped vs rejected).

        Returns:
            {
                "total_decisions": 50,
                "posted": 35,
                "skipped": 12,
                "rejected": 3,
                "posted_percentage": 70.0,
                "rejection_rate": 6.0,
            }
        """
        return self.interaction_repo.get_content_decisions(days)
```

## Repository Layer

### InteractionRepository

```python
# src/repositories/interaction_repository.py

class InteractionRepository:
    """Repository for user interaction database operations."""

    def __init__(self):
        self.db = get_db_session()

    def create(
        self,
        user_id: str,
        interaction_type: str,
        interaction_name: str,
        context: Optional[dict] = None,
        telegram_chat_id: Optional[int] = None,
        telegram_message_id: Optional[int] = None,
    ) -> UserInteraction:
        """Create a new interaction record."""
        interaction = UserInteraction(
            user_id=user_id,
            interaction_type=interaction_type,
            interaction_name=interaction_name,
            context=context or {},
            telegram_chat_id=telegram_chat_id,
            telegram_message_id=telegram_message_id,
        )
        self.db.add(interaction)
        self.db.commit()
        self.db.refresh(interaction)
        return interaction

    def get_by_user(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[UserInteraction]:
        """Get interactions for a specific user."""
        return (
            self.db.query(UserInteraction)
            .filter(UserInteraction.user_id == user_id)
            .order_by(UserInteraction.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_by_type(
        self,
        interaction_type: str,
        days: int = 30,
    ) -> List[UserInteraction]:
        """Get interactions by type within date range."""
        since = datetime.utcnow() - timedelta(days=days)
        return (
            self.db.query(UserInteraction)
            .filter(
                UserInteraction.interaction_type == interaction_type,
                UserInteraction.created_at >= since,
            )
            .order_by(UserInteraction.created_at.desc())
            .all()
        )

    def get_user_stats(self, user_id: str, days: int = 30) -> dict:
        """Get aggregated stats for a user."""
        since = datetime.utcnow() - timedelta(days=days)

        interactions = (
            self.db.query(UserInteraction)
            .filter(
                UserInteraction.user_id == user_id,
                UserInteraction.created_at >= since,
            )
            .all()
        )

        # Aggregate stats
        stats = {
            "total_interactions": len(interactions),
            "posts_marked": 0,
            "posts_skipped": 0,
            "posts_rejected": 0,
            "commands_used": {},
        }

        for interaction in interactions:
            if interaction.interaction_name == "posted":
                stats["posts_marked"] += 1
            elif interaction.interaction_name == "skip":
                stats["posts_skipped"] += 1
            elif interaction.interaction_name == "confirm_reject":
                stats["posts_rejected"] += 1
            elif interaction.interaction_type == "command":
                cmd = interaction.interaction_name
                stats["commands_used"][cmd] = stats["commands_used"].get(cmd, 0) + 1

        return stats

    def get_team_activity(self, days: int = 30) -> dict:
        """Get team-wide activity stats."""
        since = datetime.utcnow() - timedelta(days=days)

        interactions = (
            self.db.query(UserInteraction)
            .filter(UserInteraction.created_at >= since)
            .all()
        )

        user_ids = set()
        by_type = {}
        by_name = {}

        for interaction in interactions:
            user_ids.add(str(interaction.user_id))

            t = interaction.interaction_type
            by_type[t] = by_type.get(t, 0) + 1

            n = interaction.interaction_name
            by_name[n] = by_name.get(n, 0) + 1

        return {
            "total_interactions": len(interactions),
            "active_users": len(user_ids),
            "interactions_by_type": by_type,
            "interactions_by_name": by_name,
        }

    def get_content_decisions(self, days: int = 30) -> dict:
        """Get content decision breakdown."""
        since = datetime.utcnow() - timedelta(days=days)

        decisions = (
            self.db.query(UserInteraction)
            .filter(
                UserInteraction.interaction_type == "callback",
                UserInteraction.interaction_name.in_(["posted", "skip", "confirm_reject"]),
                UserInteraction.created_at >= since,
            )
            .all()
        )

        posted = sum(1 for d in decisions if d.interaction_name == "posted")
        skipped = sum(1 for d in decisions if d.interaction_name == "skip")
        rejected = sum(1 for d in decisions if d.interaction_name == "confirm_reject")
        total = len(decisions)

        return {
            "total_decisions": total,
            "posted": posted,
            "skipped": skipped,
            "rejected": rejected,
            "posted_percentage": round(posted / total * 100, 1) if total > 0 else 0,
            "rejection_rate": round(rejected / total * 100, 1) if total > 0 else 0,
        }
```

## Integration with TelegramService

The TelegramService will delegate interaction logging to InteractionService:

```python
# In TelegramService.__init__
self.interaction_service = InteractionService()

# In _handle_posted (example)
async def _handle_posted(self, queue_id: str, user, query):
    # ... existing logic ...

    # Log the interaction
    self.interaction_service.log_callback(
        user_id=str(user.id),
        callback_name="posted",
        context={
            "queue_item_id": queue_id,
            "media_id": str(queue_item.media_item_id),
            "media_filename": media_item.file_name if media_item else None,
        },
        telegram_chat_id=query.message.chat_id,
        telegram_message_id=query.message.message_id,
    )

# In _handle_queue_command (new)
async def _handle_queue_command(self, update, context):
    user = self._get_or_create_user(update.effective_user)

    # Get queue items
    queue_items = self.queue_repo.get_pending(limit=5)

    # Format response
    response = self._format_queue_response(queue_items)

    # Send response
    await update.message.reply_text(response, parse_mode="Markdown")

    # Log the interaction
    self.interaction_service.log_command(
        user_id=str(user.id),
        command="/queue",
        context={
            "items_shown": len(queue_items),
            "total_queue": self.queue_repo.count_pending(),
        },
        telegram_chat_id=update.effective_chat.id,
        telegram_message_id=update.message.message_id,
    )
```

## Implementation Plan

### Step 1: Create Model
- [x] Create `src/models/user_interaction.py`
- [x] Add to `src/models/__init__.py`

### Step 2: Create Repository
- [x] Create `src/repositories/interaction_repository.py`
- [x] Add to `src/repositories/__init__.py`

### Step 3: Create Service
- [x] Create `src/services/core/interaction_service.py`
- [x] Add logging methods
- [x] Add analytics methods
- [x] Add `log_bot_response()` for outgoing message tracking

### Step 4: Database Migration
- [x] Add CREATE TABLE to `scripts/setup_database.sql`
- [x] Create migration script for Pi: `scripts/migrations/003_add_user_interactions.sql`

### Step 5: Integrate with TelegramService
- [x] Add InteractionService dependency
- [x] Log existing callbacks (posted, skip, reject, confirm_reject, cancel_reject)
- [x] Implement `/queue` command with logging
- [x] Implement `/status` command with logging

### Step 6: Testing
- [x] Unit tests for InteractionRepository
- [x] Unit tests for InteractionService
- [x] Integration tests for TelegramService logging

> **Note**: `InteractionService` intentionally does NOT extend `BaseService` to avoid
> recursive tracking (logging interactions about logging interactions). This is a deliberate
> architectural exception.

## Future Enhancements

1. **`/stats` Command** - Users can view their own stats
2. **`/team` Command** - Admins can view team activity
3. **Rate Limiting** - Use interaction data to rate limit commands
4. **Activity Notifications** - Alert admins to unusual activity patterns
5. **Export** - Export interaction data for external analytics

## Migration Script

```sql
-- scripts/migrations/003_add_user_interactions.sql
-- Run on Pi: psql -U storyline_user -d storyline_ai -f scripts/migrations/003_add_user_interactions.sql

CREATE TABLE IF NOT EXISTS user_interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    interaction_type VARCHAR(50) NOT NULL,
    interaction_name VARCHAR(100) NOT NULL,
    context JSONB,
    telegram_chat_id BIGINT,
    telegram_message_id BIGINT,
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
```

## Summary

This design provides:

1. **Clean Separation** - InteractionService handles only interaction tracking
2. **Single Responsibility** - TelegramService handles bot logic, delegates logging
3. **Flexible Schema** - JSONB context field allows varied metadata per interaction type
4. **Analytics Ready** - Indexed for common query patterns
5. **Audit Trail** - Complete history of who did what, when
