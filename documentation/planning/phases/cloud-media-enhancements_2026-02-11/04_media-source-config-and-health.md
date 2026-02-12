# Phase 04: Media Source Configuration & Health

**PR Title**: feat: add media source configuration UI and sync health monitoring
**Risk Level**: Low
**Estimated Effort**: Medium (2 new files, 6 modified files, ~15 new tests)
**Branch**: `enhance/cloud-media-enhancements/phase-04-config-and-health`

---

## Context

Phases 01-03 built the media source provider abstraction, Google Drive integration, and a scheduled sync engine with background loop. However, all of this is configured exclusively through `.env` files and CLI commands. The user's primary interface is Telegram, and they need to be able to:

1. Toggle media sync on/off from Telegram `/settings`
2. Trigger a manual sync and see results inline via a new `/sync` command
3. See sync health prominently in `/status` output
4. Receive proactive notifications when sync encounters errors

**User intent**: "A user comes to use the product, they hook in their Google Drive folder, the system indexes their media, everything works." This phase makes the sync engine observable and controllable from within Telegram, completing the user-facing loop.

---

## Dependencies

- **Depends on**: Phase 01 (Provider Abstraction), Phase 02 (Google Drive Provider), Phase 03 (Scheduled Sync Engine -- `MediaSyncService`, `SyncResult`, `media_sync_loop`, `_check_media_sync` health check, settings `MEDIA_SYNC_ENABLED`/`MEDIA_SYNC_INTERVAL_SECONDS`/`MEDIA_SOURCE_TYPE`/`MEDIA_SOURCE_ROOT`). All three must be merged first.
- **Unlocks**: Future phases can extend the Telegram UI for provider-specific configuration (e.g., changing Google Drive folder ID from Telegram, connecting new providers via bot conversation flow).

---

## Detailed Implementation Plan

### Step 1: Add `media_sync_enabled` Column to `chat_settings`

Phase 03 added `MEDIA_SYNC_ENABLED` as a deployment-level `.env` setting. Phase 04 promotes this to a per-chat toggle in the `chat_settings` table so users can control it from Telegram `/settings`. The `.env` value becomes the bootstrap default (same pattern as `dry_run_mode`, `enable_instagram_api`).

#### New File: `scripts/migrations/012_chat_settings_media_sync.sql`

```sql
-- Migration 012: Add media_sync_enabled to chat_settings
-- Phase 04 of cloud media enhancement
--
-- Adds per-chat media sync toggle. Bootstrap default comes from
-- MEDIA_SYNC_ENABLED in .env (resolved by ChatSettingsRepository.get_or_create).

BEGIN;

ALTER TABLE chat_settings
    ADD COLUMN media_sync_enabled BOOLEAN DEFAULT FALSE;

-- Backfill existing records to match current .env default
UPDATE chat_settings SET media_sync_enabled = FALSE WHERE media_sync_enabled IS NULL;

-- Record migration
INSERT INTO schema_version (version, description, applied_at)
VALUES (12, 'Add media_sync_enabled to chat_settings', NOW());

COMMIT;
```

#### Modify: `/Users/chris/Projects/storyline-ai/src/models/chat_settings.py`

**Current code (lines 48-56):**
```python
    # Notification settings
    show_verbose_notifications = Column(Boolean, default=True)

    # Active Instagram account (for multi-account support)
    active_instagram_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("instagram_accounts.id"),
        nullable=True,  # NULL = no account selected yet
    )
```

**New code (replace lines 48-56):**
```python
    # Notification settings
    show_verbose_notifications = Column(Boolean, default=True)

    # Media sync (Phase 04 Cloud Media)
    media_sync_enabled = Column(Boolean, default=False)

    # Active Instagram account (for multi-account support)
    active_instagram_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("instagram_accounts.id"),
        nullable=True,  # NULL = no account selected yet
    )
```

No new imports needed -- `Boolean` and `Column` are already imported.

#### Modify: `/Users/chris/Projects/storyline-ai/src/repositories/chat_settings_repository.py`

**Current code in `get_or_create` (lines 46-55):**
```python
        # Bootstrap from .env values
        chat_settings = ChatSettings(
            telegram_chat_id=telegram_chat_id,
            dry_run_mode=env_settings.DRY_RUN_MODE,
            enable_instagram_api=env_settings.ENABLE_INSTAGRAM_API,
            is_paused=False,
            posts_per_day=env_settings.POSTS_PER_DAY,
            posting_hours_start=env_settings.POSTING_HOURS_START,
            posting_hours_end=env_settings.POSTING_HOURS_END,
            show_verbose_notifications=True,
        )
```

**New code (replace lines 46-55):**
```python
        # Bootstrap from .env values
        chat_settings = ChatSettings(
            telegram_chat_id=telegram_chat_id,
            dry_run_mode=env_settings.DRY_RUN_MODE,
            enable_instagram_api=env_settings.ENABLE_INSTAGRAM_API,
            is_paused=False,
            posts_per_day=env_settings.POSTS_PER_DAY,
            posting_hours_start=env_settings.POSTING_HOURS_START,
            posting_hours_end=env_settings.POSTING_HOURS_END,
            show_verbose_notifications=True,
            media_sync_enabled=env_settings.MEDIA_SYNC_ENABLED,
        )
```

#### Modify: `/Users/chris/Projects/storyline-ai/src/services/core/settings_service.py`

**Current code (lines 19-25):**
```python
# Allowed settings that can be toggled/changed
TOGGLEABLE_SETTINGS = {
    "dry_run_mode",
    "enable_instagram_api",
    "is_paused",
    "show_verbose_notifications",
}
NUMERIC_SETTINGS = {"posts_per_day", "posting_hours_start", "posting_hours_end"}
```

**New code (replace lines 19-25):**
```python
# Allowed settings that can be toggled/changed
TOGGLEABLE_SETTINGS = {
    "dry_run_mode",
    "enable_instagram_api",
    "is_paused",
    "show_verbose_notifications",
    "media_sync_enabled",
}
NUMERIC_SETTINGS = {"posts_per_day", "posting_hours_start", "posting_hours_end"}
```

**Also modify `get_settings_display` (add to the returned dict, after `show_verbose_notifications`):**

**Current code (lines 186-197):**
```python
        return {
            "dry_run_mode": settings.dry_run_mode,
            "enable_instagram_api": settings.enable_instagram_api,
            "is_paused": settings.is_paused,
            "paused_at": settings.paused_at,
            "paused_by_user_id": settings.paused_by_user_id,
            "posts_per_day": settings.posts_per_day,
            "posting_hours_start": settings.posting_hours_start,
            "posting_hours_end": settings.posting_hours_end,
            "show_verbose_notifications": settings.show_verbose_notifications,
            "updated_at": settings.updated_at,
        }
```

**New code (replace lines 186-197):**
```python
        return {
            "dry_run_mode": settings.dry_run_mode,
            "enable_instagram_api": settings.enable_instagram_api,
            "is_paused": settings.is_paused,
            "paused_at": settings.paused_at,
            "paused_by_user_id": settings.paused_by_user_id,
            "posts_per_day": settings.posts_per_day,
            "posting_hours_start": settings.posting_hours_start,
            "posting_hours_end": settings.posting_hours_end,
            "show_verbose_notifications": settings.show_verbose_notifications,
            "media_sync_enabled": settings.media_sync_enabled,
            "updated_at": settings.updated_at,
        }
```

---

### Step 2: Add Media Sync Toggle to `/settings` Menu

#### Modify: `/Users/chris/Projects/storyline-ai/src/services/core/telegram_settings.py`

**Current code in `build_settings_message_and_keyboard` (lines 86-106):**
```python
            [
                InlineKeyboardButton(
                    f"📝 Verbose: {'ON' if settings_data['show_verbose_notifications'] else 'OFF'}",
                    callback_data="settings_toggle:show_verbose_notifications",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔄 Regenerate", callback_data="schedule_action:regenerate"
                ),
                InlineKeyboardButton(
                    "📅 +7 Days", callback_data="schedule_action:extend"
                ),
            ],
            [InlineKeyboardButton("❌ Close", callback_data="settings_close")],
        ]

        return message, InlineKeyboardMarkup(keyboard)
```

**New code (replace lines 86-106):**
```python
            [
                InlineKeyboardButton(
                    f"📝 Verbose: {'ON' if settings_data['show_verbose_notifications'] else 'OFF'}",
                    callback_data="settings_toggle:show_verbose_notifications",
                ),
            ],
            [
                InlineKeyboardButton(
                    f"🔄 Media Sync: {'ON' if settings_data['media_sync_enabled'] else 'OFF'}",
                    callback_data="settings_toggle:media_sync_enabled",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔄 Regenerate", callback_data="schedule_action:regenerate"
                ),
                InlineKeyboardButton(
                    "📅 +7 Days", callback_data="schedule_action:extend"
                ),
            ],
            [InlineKeyboardButton("❌ Close", callback_data="settings_close")],
        ]

        return message, InlineKeyboardMarkup(keyboard)
```

This adds a "Media Sync: ON/OFF" toggle button to the settings menu, directly below the "Verbose" toggle. It follows the exact same pattern as all other toggles -- uses `settings_toggle:media_sync_enabled` callback, which is already handled by the existing `handle_settings_toggle` method (since we added `media_sync_enabled` to `TOGGLEABLE_SETTINGS` in Step 1).

---

### Step 3: Add `/sync` Command Handler

Following the composition pattern, the `/sync` command is added directly to `TelegramCommandHandlers` since it is a simple operational command (same as `/dryrun`, `/pause`, `/resume`).

#### Modify: `/Users/chris/Projects/storyline-ai/src/services/core/telegram_commands.py`

**Add new method at the end of the `TelegramCommandHandlers` class (after `handle_cleanup`):**

```python
    async def handle_sync(self, update, context):
        """Handle /sync command - trigger manual media sync and report results.

        Usage:
            /sync - Run a manual media sync against the configured provider
        """
        user = self.service._get_or_create_user(update.effective_user)
        chat_id = update.effective_chat.id

        # Check if sync is configured
        from src.config.settings import settings as app_settings

        source_type = app_settings.MEDIA_SOURCE_TYPE
        source_root = app_settings.MEDIA_SOURCE_ROOT

        if not source_root and source_type == "local":
            source_root = app_settings.MEDIA_DIR

        if not source_root:
            await update.message.reply_text(
                "⚠️ *Media Sync Not Configured*\n\n"
                "No media source root is set.\n"
                "Configure `MEDIA_SOURCE_ROOT` in `.env` or connect a Google Drive.",
                parse_mode="Markdown",
            )
            self.service.interaction_service.log_command(
                user_id=str(user.id),
                command="/sync",
                context={"error": "not_configured"},
                telegram_chat_id=chat_id,
                telegram_message_id=update.message.message_id,
            )
            return

        # Send "syncing..." message
        status_msg = await update.message.reply_text(
            f"🔄 *Syncing media...*\n\n"
            f"Source: `{source_type}`\n"
            f"Root: `{source_root[:40]}{'...' if len(source_root) > 40 else ''}`",
            parse_mode="Markdown",
        )

        try:
            from src.services.core.media_sync import MediaSyncService

            sync_service = MediaSyncService()
            result = sync_service.sync(
                source_type=source_type,
                source_root=source_root,
                triggered_by="telegram",
            )

            # Build result message
            lines = ["✅ *Sync Complete*\n"]

            if result.new > 0:
                lines.append(f"📥 New: {result.new}")
            if result.updated > 0:
                lines.append(f"✏️ Updated: {result.updated}")
            if result.deactivated > 0:
                lines.append(f"🗑️ Removed: {result.deactivated}")
            if result.reactivated > 0:
                lines.append(f"♻️ Restored: {result.reactivated}")

            lines.append(f"📁 Unchanged: {result.unchanged}")

            if result.errors > 0:
                lines.append(f"⚠️ Errors: {result.errors}")

            lines.append(f"\n📊 Total: {result.total_processed}")

            await status_msg.edit_text(
                "\n".join(lines),
                parse_mode="Markdown",
            )

            # Log interaction
            self.service.interaction_service.log_command(
                user_id=str(user.id),
                command="/sync",
                context=result.to_dict(),
                telegram_chat_id=chat_id,
                telegram_message_id=update.message.message_id,
            )

            logger.info(
                f"Manual sync triggered by {self.service._get_display_name(user)}: "
                f"{result.new} new, {result.updated} updated, "
                f"{result.deactivated} deactivated"
            )

        except ValueError as e:
            await status_msg.edit_text(
                f"❌ *Sync Failed*\n\n{str(e)}",
                parse_mode="Markdown",
            )
            logger.error(f"Manual sync failed (config): {e}")

        except Exception as e:
            await status_msg.edit_text(
                f"❌ *Sync Failed*\n\n{str(e)[:200]}",
                parse_mode="Markdown",
            )
            logger.error(f"Manual sync failed: {e}", exc_info=True)
```

#### Modify: `/Users/chris/Projects/storyline-ai/src/services/core/telegram_service.py`

**Register the new `/sync` command in the `initialize()` method.**

**Current code (lines 124-139):**
```python
        # Register command handlers
        command_map = {
            "start": self.commands.handle_start,
            "status": self.commands.handle_status,
            "queue": self.commands.handle_queue,
            "next": self.commands.handle_next,
            "pause": self.commands.handle_pause,
            "resume": self.commands.handle_resume,
            "schedule": self.commands.handle_schedule,
            "stats": self.commands.handle_stats,
            "history": self.commands.handle_history,
            "locks": self.commands.handle_locks,
            "reset": self.commands.handle_reset,
            "cleanup": self.commands.handle_cleanup,
            "help": self.commands.handle_help,
            "dryrun": self.commands.handle_dryrun,
            "settings": self.settings_handler.handle_settings,
        }
```

**New code (replace lines 124-139):**
```python
        # Register command handlers
        command_map = {
            "start": self.commands.handle_start,
            "status": self.commands.handle_status,
            "queue": self.commands.handle_queue,
            "next": self.commands.handle_next,
            "pause": self.commands.handle_pause,
            "resume": self.commands.handle_resume,
            "schedule": self.commands.handle_schedule,
            "stats": self.commands.handle_stats,
            "history": self.commands.handle_history,
            "locks": self.commands.handle_locks,
            "reset": self.commands.handle_reset,
            "cleanup": self.commands.handle_cleanup,
            "help": self.commands.handle_help,
            "dryrun": self.commands.handle_dryrun,
            "sync": self.commands.handle_sync,
            "settings": self.settings_handler.handle_settings,
        }
```

**Also register in the BotCommand list for Telegram autocomplete (add after the "dryrun" entry):**

**Current code (lines 154-171):**
```python
        # Register commands with Telegram for autocomplete menu
        commands = [
            BotCommand("start", "Initialize bot and show welcome"),
            BotCommand("status", "Show system health and queue status"),
            BotCommand("help", "Show all available commands"),
            BotCommand("queue", "View pending scheduled posts"),
            BotCommand("next", "Force-send next scheduled post"),
            BotCommand("pause", "Pause automatic posting"),
            BotCommand("resume", "Resume posting"),
            BotCommand("schedule", "Create N days of posting schedule"),
            BotCommand("stats", "Show media library statistics"),
            BotCommand("history", "Show recent post history"),
            BotCommand("locks", "View permanently rejected items"),
            BotCommand("reset", "Reset posting queue to empty"),
            BotCommand("cleanup", "Delete recent bot messages"),
            BotCommand("settings", "Configure bot settings"),
            BotCommand("dryrun", "Toggle dry-run mode"),
        ]
```

**New code (replace lines 154-171):**
```python
        # Register commands with Telegram for autocomplete menu
        commands = [
            BotCommand("start", "Initialize bot and show welcome"),
            BotCommand("status", "Show system health and queue status"),
            BotCommand("help", "Show all available commands"),
            BotCommand("queue", "View pending scheduled posts"),
            BotCommand("next", "Force-send next scheduled post"),
            BotCommand("pause", "Pause automatic posting"),
            BotCommand("resume", "Resume posting"),
            BotCommand("schedule", "Create N days of posting schedule"),
            BotCommand("stats", "Show media library statistics"),
            BotCommand("history", "Show recent post history"),
            BotCommand("locks", "View permanently rejected items"),
            BotCommand("reset", "Reset posting queue to empty"),
            BotCommand("cleanup", "Delete recent bot messages"),
            BotCommand("settings", "Configure bot settings"),
            BotCommand("dryrun", "Toggle dry-run mode"),
            BotCommand("sync", "Sync media from configured source"),
        ]
```

#### Also update the `/help` text in `telegram_commands.py`

Add `/sync` to the help text under "Control Commands":

```python
            "/sync - Sync media from source\n"
```

(Insert this line after the `/dryrun` line in the existing help_text string.)

---

### Step 4: Enhance `/status` Command with Media Sync Info

#### Modify: `/Users/chris/Projects/storyline-ai/src/services/core/telegram_commands.py`

**In `handle_status`, after the Instagram API status block and before the `status_msg` string construction, add sync status gathering:**

```python
        # Media sync status
        sync_status_line = ""
        try:
            from src.services.core.media_sync import MediaSyncService

            sync_service = MediaSyncService()
            last_sync = sync_service.get_last_sync_info()
            chat_settings = self.service.settings_service.get_settings(
                update.effective_chat.id
            )

            if not chat_settings.media_sync_enabled:
                sync_status_line = "🔄 Media Sync: ❌ Disabled"
            elif not last_sync:
                sync_status_line = "🔄 Media Sync: ⏳ No syncs yet"
            elif last_sync["success"]:
                result = last_sync.get("result", {}) or {}
                new_count = result.get("new", 0)
                total = sum(
                    result.get(k, 0)
                    for k in ["new", "updated", "deactivated", "reactivated", "unchanged"]
                )
                sync_status_line = (
                    f"🔄 Media Sync: ✅ OK"
                    f"\n   └─ Last: {last_sync['started_at'][:16]} "
                    f"({total} items, {new_count} new)"
                )
            else:
                sync_status_line = (
                    f"🔄 Media Sync: ⚠️ Last sync failed"
                    f"\n   └─ {last_sync.get('started_at', 'N/A')[:16]}"
                )
        except Exception:
            sync_status_line = "🔄 Media Sync: ❓ Check failed"
```

**Add the sync section to the `status_msg` string. Insert between the Instagram API block and the Queue & Media block:**

```python
            f"*Media Source:*\n"
            f"{sync_status_line}\n\n"
```

---

### Step 5: Enhanced Health Check with Provider Connectivity

#### Modify: `/Users/chris/Projects/storyline-ai/src/services/core/health_check.py`

**Replace Phase 03's `_check_media_sync` method with this enhanced version that also checks provider connectivity:**

```python
    def _check_media_sync(self) -> dict:
        """Check media sync health including provider connectivity."""
        if not settings.MEDIA_SYNC_ENABLED:
            return {
                "healthy": True,
                "message": "Disabled via config",
                "enabled": False,
            }

        try:
            from src.services.core.media_sync import MediaSyncService
            from src.services.media_sources.factory import MediaSourceFactory

            # Check provider connectivity
            source_type = settings.MEDIA_SOURCE_TYPE
            source_root = settings.MEDIA_SOURCE_ROOT
            if source_type == "local" and not source_root:
                source_root = settings.MEDIA_DIR

            provider_healthy = False
            provider_message = ""
            try:
                if source_type == "local":
                    provider = MediaSourceFactory.create(source_type, base_path=source_root)
                elif source_type == "google_drive":
                    provider = MediaSourceFactory.create(
                        source_type, root_folder_id=source_root
                    )
                else:
                    provider = MediaSourceFactory.create(source_type)

                provider_healthy = provider.is_configured()
                if not provider_healthy:
                    provider_message = f"Provider '{source_type}' not accessible"
            except Exception as e:
                provider_message = f"Provider error: {str(e)[:100]}"

            if not provider_healthy:
                return {
                    "healthy": False,
                    "message": provider_message or f"Provider '{source_type}' not configured",
                    "enabled": True,
                    "source_type": source_type,
                }

            # Check last sync run
            sync_service = MediaSyncService()
            last_sync = sync_service.get_last_sync_info()

            if not last_sync:
                return {
                    "healthy": False,
                    "message": f"No sync runs recorded yet (source: {source_type})",
                    "enabled": True,
                    "source_type": source_type,
                }

            if not last_sync["success"]:
                return {
                    "healthy": False,
                    "message": f"Last sync failed: {last_sync.get('status', 'unknown')}",
                    "enabled": True,
                    "source_type": source_type,
                    "last_run": last_sync["started_at"],
                }

            # Check if last sync is stale (more than 3x interval)
            if last_sync["completed_at"]:
                completed = datetime.fromisoformat(last_sync["completed_at"])
                stale_threshold = timedelta(
                    seconds=settings.MEDIA_SYNC_INTERVAL_SECONDS * 3
                )
                if datetime.utcnow() - completed > stale_threshold:
                    return {
                        "healthy": False,
                        "message": (
                            f"Last sync was {last_sync['completed_at']} "
                            f"(stale, expected every {settings.MEDIA_SYNC_INTERVAL_SECONDS}s)"
                        ),
                        "enabled": True,
                        "source_type": source_type,
                        "last_run": last_sync["started_at"],
                    }

            result_summary = last_sync.get("result", {}) or {}
            errors = result_summary.get("errors", 0)

            if errors > 0:
                return {
                    "healthy": True,
                    "message": (
                        f"Last sync OK with {errors} error(s) "
                        f"(source: {source_type})"
                    ),
                    "enabled": True,
                    "source_type": source_type,
                    "last_run": last_sync["started_at"],
                    "last_result": result_summary,
                }

            return {
                "healthy": True,
                "message": f"OK (source: {source_type}, last: {last_sync['started_at'][:16]})",
                "enabled": True,
                "source_type": source_type,
                "last_run": last_sync["started_at"],
                "last_result": result_summary,
            }

        except Exception as e:
            return {
                "healthy": False,
                "message": f"Sync check error: {str(e)}",
                "enabled": True,
            }
```

---

### Step 6: Telegram Notification on Sync Errors

When the background sync loop encounters errors, optionally notify the Telegram channel (if verbose notifications are enabled).

#### Modify: `/Users/chris/Projects/storyline-ai/src/main.py`

**Phase 03 designed a `media_sync_loop` function. Phase 04 enhances it with Telegram notification capability.**

**New `media_sync_loop` function (replaces the Phase 03 version):**

```python
async def media_sync_loop(
    sync_service: MediaSyncService,
    telegram_service=None,
):
    """Run media sync loop - reconcile provider files with database on schedule.

    Args:
        sync_service: The MediaSyncService instance
        telegram_service: Optional TelegramService for error notifications
    """
    logger.info(
        f"Starting media sync loop "
        f"(interval: {settings.MEDIA_SYNC_INTERVAL_SECONDS}s, "
        f"source: {settings.MEDIA_SOURCE_TYPE})"
    )

    # Track consecutive failures for notification suppression
    consecutive_failures = 0
    last_error_notified = None

    while True:
        try:
            result = sync_service.sync(triggered_by="scheduler")

            if result.total_processed > 0 or result.errors > 0:
                logger.info(
                    f"Media sync completed: "
                    f"{result.new} new, {result.updated} updated, "
                    f"{result.deactivated} deactivated, "
                    f"{result.reactivated} reactivated, "
                    f"{result.errors} errors"
                )

            # Reset failure counter on success
            if result.errors == 0:
                consecutive_failures = 0
                last_error_notified = None

            # Notify on sync errors (first occurrence or every 10th consecutive)
            elif result.errors > 0 and telegram_service:
                consecutive_failures += 1
                error_summary = "; ".join(result.error_details[:3])

                if consecutive_failures == 1 or consecutive_failures % 10 == 0:
                    await _send_sync_error_notification(
                        telegram_service,
                        result,
                        consecutive_failures,
                        error_summary,
                    )

        except Exception as e:
            logger.error(f"Error in media sync loop: {e}", exc_info=True)

            consecutive_failures += 1
            error_str = str(e)

            if telegram_service and (
                consecutive_failures == 1
                or error_str != last_error_notified
            ):
                last_error_notified = error_str
                await _send_sync_error_notification_exception(
                    telegram_service, e, consecutive_failures
                )

        finally:
            sync_service.cleanup_transactions()

        await asyncio.sleep(settings.MEDIA_SYNC_INTERVAL_SECONDS)


async def _send_sync_error_notification(
    telegram_service,
    result,
    consecutive_failures: int,
    error_summary: str,
):
    """Send sync error notification to admin channel."""
    try:
        chat_settings = telegram_service.settings_service.get_settings(
            telegram_service.channel_id
        )
        if not chat_settings.show_verbose_notifications:
            return

        message = (
            f"⚠️ *Media Sync Errors*\n\n"
            f"Sync completed with {result.errors} error(s).\n"
            f"Consecutive failures: {consecutive_failures}\n\n"
            f"Details: {error_summary[:300]}"
        )

        await telegram_service.bot.send_message(
            chat_id=settings.TELEGRAM_CHANNEL_ID,
            text=message,
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.warning(f"Failed to send sync error notification: {e}")


async def _send_sync_error_notification_exception(
    telegram_service,
    error: Exception,
    consecutive_failures: int,
):
    """Send sync exception notification to admin channel."""
    try:
        chat_settings = telegram_service.settings_service.get_settings(
            telegram_service.channel_id
        )
        if not chat_settings.show_verbose_notifications:
            return

        error_type = type(error).__name__
        error_msg = str(error)[:200]

        message = (
            f"🔴 *Media Sync Failed*\n\n"
            f"Error: `{error_type}`\n"
            f"Details: {error_msg}\n\n"
            f"Consecutive failures: {consecutive_failures}\n"
            f"Sync will retry in {settings.MEDIA_SYNC_INTERVAL_SECONDS}s."
        )

        await telegram_service.bot.send_message(
            chat_id=settings.TELEGRAM_CHANNEL_ID,
            text=message,
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.warning(f"Failed to send sync error notification: {e}")
```

**Update the task creation in `main_async()` to pass `telegram_service`:**

Phase 03 designed:
```python
    if sync_service:
        all_services.append(sync_service)
        tasks.append(asyncio.create_task(media_sync_loop(sync_service)))
```

Phase 04 changes this to:
```python
    if sync_service:
        all_services.append(sync_service)
        tasks.append(
            asyncio.create_task(
                media_sync_loop(sync_service, telegram_service=telegram_service)
            )
        )
```

---

## Test Plan

### New Test File: `tests/src/services/test_telegram_sync_command.py`

6 tests for the `/sync` command handler:

1. **`test_sync_not_configured`** -- `/sync` when no source root is set. Shows "Not Configured" message.
2. **`test_sync_success`** -- Successful sync returns result counts in edited message.
3. **`test_sync_with_errors`** -- Sync with errors shows error count.
4. **`test_sync_exception`** -- `MediaSyncService.sync()` raises ValueError. Shows "Sync Failed".
5. **`test_sync_local_fallback_to_media_dir`** -- When source_root empty and source_type="local", uses MEDIA_DIR.
6. **`test_sync_logs_interaction`** -- Verifies `interaction_service.log_command` called with `/sync`.

### Updated Test Files

**`tests/src/services/test_telegram_settings.py`** -- 2 new tests:

7. **`test_media_sync_toggle_button_shows_on`** -- Settings keyboard shows "Media Sync: ON" when enabled.
8. **`test_media_sync_toggle_button_shows_off`** -- Settings keyboard shows "Media Sync: OFF" when disabled.

**Note**: Existing tests that mock `get_settings_display` return values need `"media_sync_enabled": False` added.

**`tests/src/services/test_settings_service.py`** -- 2 new tests:

9. **`test_media_sync_enabled_is_toggleable`** -- `media_sync_enabled` is in `TOGGLEABLE_SETTINGS`.
10. **`test_get_settings_display_includes_media_sync`** -- Display dict includes `media_sync_enabled`.

**`tests/src/services/test_health_check.py`** -- 5 new tests:

11. **`test_check_media_sync_disabled`** -- Returns `healthy=True, enabled=False` when disabled.
12. **`test_check_media_sync_provider_not_accessible`** -- Returns `healthy=False` when provider fails.
13. **`test_check_media_sync_healthy`** -- Returns `healthy=True` with source_type info.
14. **`test_check_media_sync_no_runs_yet`** -- Returns `healthy=False` when never synced.
15. **`test_check_media_sync_last_run_failed`** -- Returns `healthy=False` with failure info.

### Total: ~15 new tests

---

## Documentation Updates

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Added

- **Media Source Configuration & Health** - Telegram UI integration for media sync engine
  - Media sync toggle in `/settings` menu (per-chat, persisted to `chat_settings`)
  - New `/sync` command for manual media sync from Telegram
  - Enhanced `/status` output with media sync health section
  - Proactive Telegram notifications on sync errors (respects verbose setting)
  - Enhanced health check with provider connectivity testing
  - Database migration `012_chat_settings_media_sync.sql` for per-chat sync toggle
```

### CLAUDE.md Updates

- Add `/sync` to Telegram Bot Commands Reference table
- Add `settings_toggle:media_sync_enabled` to Telegram Callback Actions table
- Add migration 012 to the migration history table

---

## Stress Testing & Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| `/sync` called while background sync loop is running | Both run independently. Repo operations are atomic per item. No data corruption. |
| `/sync` with Google Drive credentials expired | Shows "Sync Failed" with error message in Telegram. |
| Media sync toggle OFF in settings while background loop is running | Background loop uses `.env` MEDIA_SYNC_ENABLED for startup decision. Per-chat toggle controls display only. Loop continues until restart. |
| Sync error notification flood | `consecutive_failures` counter throttles: first occurrence + every 10th. |
| Verbose notifications OFF | Sync error notifications suppressed. |
| `/status` when MediaSyncService not importable (Phase 03 not merged) | Wrapped in try/except, shows "Check failed" gracefully. |
| New chat accessing `/settings` for first time | `get_or_create` bootstraps `media_sync_enabled` from MEDIA_SYNC_ENABLED in `.env`. |
| Migration 012 on DB with existing chat_settings records | `media_sync_enabled` defaults to `FALSE`. No data loss. |

---

## Verification Checklist

- [ ] Migration `012` applies cleanly on dev database
- [ ] Existing chat_settings records get `media_sync_enabled = FALSE` after migration
- [ ] `/settings` menu shows "Media Sync: OFF" toggle button
- [ ] Clicking "Media Sync" toggle flips the button text between ON/OFF
- [ ] `media_sync_enabled` persisted to `chat_settings` table after toggle
- [ ] `/sync` command shows "Syncing..." then updates with results
- [ ] `/sync` handles unconfigured source gracefully
- [ ] `/sync` handles sync errors gracefully
- [ ] `/status` shows "Media Source" section with sync health
- [ ] `/help` includes `/sync` command description
- [ ] `check-health` CLI shows `media_sync` with provider connectivity
- [ ] Error notifications sent on first sync failure
- [ ] Error notifications suppressed when verbose OFF
- [ ] All new tests pass
- [ ] All existing tests pass: `pytest`
- [ ] `ruff check src/ tests/` passes
- [ ] `ruff format --check src/ tests/` passes
- [ ] CHANGELOG.md updated

---

## What NOT To Do

1. **Do NOT make the background sync loop check the per-chat `media_sync_enabled` setting.** The background loop is deployment-level (`.env`). The per-chat setting controls the display in `/settings` and future per-chat behavior.

2. **Do NOT add Google Drive configuration (folder ID, credentials) to the Telegram settings UI.** Credential management requires file upload and is security-sensitive. Keep it in CLI.

3. **Do NOT create a separate `TelegramSyncHandlers` module.** `/sync` is a single handler method in `TelegramCommandHandlers`.

4. **Do NOT remove the `.env` `MEDIA_SYNC_ENABLED` setting.** It serves as the bootstrap default and background loop control.

5. **Do NOT send sync notifications on every single failure.** Use `consecutive_failures` counter to throttle.

6. **Do NOT modify `MediaSyncService` itself.** This phase only adds UI/notification around it.

7. **Do NOT add `media_sync_enabled` column as `NOT NULL`.** Use `DEFAULT FALSE` with backfill UPDATE.

---

## Files Summary

### New Files (2)

| File | Purpose |
|------|---------|
| `scripts/migrations/012_chat_settings_media_sync.sql` | DB migration for per-chat sync toggle |
| `tests/src/services/test_telegram_sync_command.py` | Tests for `/sync` command handler (6 tests) |

### Modified Files (6)

| File | Changes |
|------|---------|
| `src/models/chat_settings.py` | Add `media_sync_enabled` column |
| `src/repositories/chat_settings_repository.py` | Bootstrap `media_sync_enabled` from `.env` |
| `src/services/core/settings_service.py` | Add to TOGGLEABLE_SETTINGS and display dict |
| `src/services/core/telegram_settings.py` | Add "Media Sync: ON/OFF" toggle button |
| `src/services/core/telegram_commands.py` | Add `/sync` handler, enhance `/status`, update `/help` |
| `src/services/core/telegram_service.py` | Register `/sync` command, add to BotCommand list |

### Modified Files (from Phase 03, enhanced by Phase 04)

| File | Changes |
|------|---------|
| `src/services/core/health_check.py` | Enhanced `_check_media_sync` with provider connectivity |
| `src/main.py` | Enhanced `media_sync_loop` with Telegram error notifications |

### Updated Test Files (3)

| File | Changes |
|------|---------|
| `tests/src/services/test_telegram_settings.py` | 2 new tests + update existing mocks |
| `tests/src/services/test_settings_service.py` | 2 new tests |
| `tests/src/services/test_health_check.py` | 5 new tests for enhanced health check |
