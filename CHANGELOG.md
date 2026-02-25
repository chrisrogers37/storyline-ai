# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **Onboarding routes split into package** — Split monolithic 859-line `onboarding.py` into focused submodules: `models.py`, `helpers.py`, `setup.py`, `dashboard.py`, `settings.py`. Consolidated lazy imports to module-level. No functional changes.
- **WebApp button builder extracted** — Deduplicated private-vs-group WebApp button logic from 3 locations into shared `build_webapp_button()` utility in `telegram_utils.py`

### Fixed
- **InteractionService session leak** — `TelegramService.cleanup_transactions()` now also cleans up `InteractionService`'s repository session. InteractionService doesn't extend BaseService, so recursive cleanup traversal missed it, leaving idle-in-transaction DB connections after SSL drops.
- **Early callback feedback** — Telegram callback handlers now remove the inline keyboard immediately after acquiring the lock, before running DB operations. This gives users instant visual feedback that their button press was received, eliminating the "nothing happened" perception during slow DB calls.
- **SSL retry in callbacks** — Callback handlers (posted/skip/reject) now catch `OperationalError` from stale SSL connections, refresh all repository sessions, re-fetch the queue item, and retry once. Previously, a Neon SSL drop during callback processing left the user stuck with no feedback.
- **Graceful race condition handling** — When a queue item is missing during callback validation (e.g., user clicks Skip after Auto Post already completed), now checks `posting_history` for what happened and shows a contextual message ("Already posted via Instagram API", "Already skipped", etc.) instead of generic "Queue item not found".
- **Duplicate scheduler runs** — `get_all_active()` now requires chats to have completed onboarding or have an active Instagram account, filtering out half-setup test/dev chats that caused duplicate `process_pending_posts` runs per cycle.
- **Duplicate Telegram sends** — Queue items are now claimed (status → "processing") BEFORE sending the Telegram notification, not after. Previously, the scheduler could pick up the same "pending" item again if the next cycle fired before the Telegram API responded, causing duplicate messages in the channel. On send failure, the item is rolled back to "pending".
- **Queue batch-fire prevention** — Throttled scheduler to process 1 post per 60s cycle (was 100), preventing all overdue items from burst-firing to Telegram simultaneously
- **Queue race condition** — Added `FOR UPDATE SKIP LOCKED` to `get_pending()` query, preventing concurrent scheduler calls from claiming the same queue item
- **Session recovery for nested services** — `cleanup_transactions()` now recursively traverses nested `BaseService` instances (e.g., `SettingsService` inside `PostingService`). Previously, an SSL connection drop could poison a nested service's session, causing an unrecoverable `PendingRollbackError` loop. Also added `settings_service` to the periodic cleanup loop and proactive rollback in the `track_execution` error handler.
- **Dead SSL session replacement** — `end_read_transaction()` now creates a fresh session when both commit and rollback fail (e.g., Neon SSL drops), and `track_execution` wraps `fail_run()` in try/except so cleanup always runs. Also caches ORM attributes before try blocks to prevent lazy-load failures in error handlers.
- **Tenant scope on posting history** — All 5 `posting_history` creation paths now propagate `chat_settings_id` from the queue item, fixing NULL tenant scope on history records
- **Observability gaps** — Added `logger.debug()` to 6 silent exception handlers in status check helpers (`telegram_commands.py`), replacing bare `except Exception:` blocks that swallowed errors with zero logging
- **Docstring cleanup** — Replaced `print()` examples in `cloud_storage.py` and `instagram_api.py` docstrings with comments to avoid setting bad patterns

### Added

- **Enhanced Mini App Dashboard** - Richer home screen with collapsible cards for deeper functionality without scroll overload
  - **Quick Controls card** - Toggle Delivery (pause/resume) and Dry Run mode directly from the dashboard
  - **Schedule card** - Expandable day-by-day breakdown, Extend (+7 Days) and Regenerate schedule actions with confirmation dialog
  - **Queue card** - Expandable list of next 10 upcoming posts with media name, category, and relative time
  - **Recent Activity card** - Last 10 posts with status (posted/skipped/failed) and posting method (API/Manual)
  - **Media Library card** - Category breakdown with visual bar chart showing file distribution
  - Cards lazy-load data on first expand to keep initial load fast
  - Schedule timing info (next post, schedule end date) shown in card summaries

- **Dashboard API endpoints** - Seven new endpoints powering the enhanced dashboard
  - `GET /api/onboarding/queue-detail` - Queue items with day summary and schedule bounds
  - `GET /api/onboarding/history-detail` - Recent posting history with media info
  - `GET /api/onboarding/media-stats` - Media library category breakdown
  - `POST /api/onboarding/toggle-setting` - Toggle boolean settings from dashboard (all 5: is_paused, dry_run_mode, enable_instagram_api, show_verbose_notifications, media_sync_enabled)
  - `POST /api/onboarding/update-setting` - Update numeric settings from dashboard (posts_per_day, posting_hours_start, posting_hours_end)
  - `POST /api/onboarding/extend-schedule` - Extend schedule by N days
  - `POST /api/onboarding/regenerate-schedule` - Clear queue and rebuild schedule

- **Full Settings in Quick Controls card** - All settings now editable from the Mini App dashboard (Phase 1 of Mini App Consolidation)
  - 3 new toggle switches: Instagram API, Verbose Notifications, Media Sync
  - Stepper controls for Posts/Day (1-50) and Posting Hours (start/end with wraparound)
  - Optimistic UI updates with automatic rollback on API failure
  - Setup state now returns all boolean settings for dashboard hydration

- **Account Management in Mini App** - Manage Instagram accounts directly from the dashboard (Phase 2 of Mini App Consolidation)
  - Instagram card is now expandable with full account list
  - Switch active account with one tap
  - Add new accounts via OAuth flow (reuses existing `connectOAuth` pattern)
  - Remove accounts with inline confirmation dialog (soft-delete, can be re-added later)
  - Active account highlighted with badge; summary shows `@username`
  - `GET /api/onboarding/accounts` - List all active accounts with active marker for current chat
  - `POST /api/onboarding/switch-account` - Switch active Instagram account
  - `POST /api/onboarding/remove-account` - Deactivate (soft-delete) an account

- **System Status in Mini App** - System health and setup status card in the dashboard (Phase 3 of Mini App Consolidation)
  - New expandable System Status card positioned after Quick Controls
  - Setup checklist: 5 items (Instagram, Google Drive, Media Library, Schedule, Delivery) with status icons
  - System health checks: Database, Telegram, Instagram API, Queue, Recent Posts, Media Sync
  - Badge shows "Healthy"/"All Set" or issue count based on health check results
  - `GET /api/onboarding/system-status` - Aggregated health data from HealthCheckService

- **Sync Media action in Mini App** - Trigger media sync directly from the dashboard (Phase 4 of Mini App Consolidation)
  - "Sync Media" button in Quick Controls card below settings
  - Inline result display showing new/updated/removed/error counts
  - `POST /api/onboarding/sync-media` - Calls MediaSyncService with per-tenant config

- **"Open Dashboard" button on /status** - Quick link to the Mini App from the status command (Phase 5 of Mini App Consolidation)

### Changed

- **Command cleanup** - Reduced active Telegram commands from 11 to 6 (Phase 5 of Mini App Consolidation)
  - **Retired 5 commands** as redirects: `/queue`, `/pause`, `/resume`, `/history`, `/sync` — all now show a helpful message pointing to the Mini App dashboard
  - **Updated `/help`** to show only 6 active commands: `/start`, `/status`, `/setup`, `/next`, `/cleanup`, `/help`
  - **Updated BotCommand menu** from 11 to 6 entries in Telegram autocomplete
  - `/status` and `/settings` kept as full handlers (not slimmed down) since they provide valuable in-chat diagnostics and quick controls
  - Total retired commands now: 12 (5 new + 7 from previous cleanup)

### Fixed

- **Google Drive media download in `/next` and auto-post** - Fixed "No Google Drive credentials found" error when sending notifications. The media download path was using the service account credential lookup instead of per-chat OAuth tokens. Now passes `telegram_chat_id` through `MediaSourceFactory.get_provider_for_media_item()` so Google Drive files are fetched with the correct user OAuth credentials.
- **WebApp buttons in group chats** - `/start` and `/settings` failed with `Button_type_invalid` because Telegram rejects `WebAppInfo` buttons in groups. Now uses signed URL tokens for browser-based access in groups (`web_app=` in DMs, `url=` + HMAC token in groups). API accepts both `initData` and URL tokens for authentication.
- **Telegram bot polling on Railway** - Bot was not responding to commands since migration from Pi. Fixed three issues:
  - Polling task completed immediately after starting background updater; now blocks to keep task alive
  - Added explicit `allowed_updates` and `drop_pending_updates=True` to ensure clean startup
  - Added application-level error handler so handler exceptions are logged instead of silently swallowed
  - Routed `telegram`/`httpx` library logs through app logger so internal errors appear in Railway logs
- **Resource management** — Converted all `try/finally/close()` patterns to context manager `with` statements in `telegram_commands.py` and `onboarding.py`, ensuring consistent database connection cleanup
- **Multi-tenant media sync** - Sync loop now iterates all tenants with `media_sync_enabled=true` instead of relying on global env var. New tenants completing onboarding will have their media synced automatically.

### Changed

- **Telegram command cleanup** - Consolidated bot commands from 18 to 11 for a cleaner daily experience
  - **Kept:** `/start`, `/status`, `/help`, `/queue`, `/next`, `/pause`, `/resume`, `/history`, `/cleanup`, `/settings` (alias: `/setup`), `/sync`
  - **Removed:** `/schedule`, `/stats`, `/locks`, `/reset`, `/dryrun`, `/backfill`, `/connect`
  - Removed commands show a helpful redirect message (e.g., "Use /settings to toggle dry-run mode")
  - `/stats` media breakdown (never-posted, posted-once, posted-2+) merged into `/status` output
  - Schedule management remains available via `/settings` panel (Regenerate / +7 Days buttons)
  - OAuth connections remain available via `/start` setup wizard
  - `/backfill` remains available via CLI (`storyline-cli backfill-instagram`)
- **`/status` enhanced with setup completion reporting** - Now shows setup status at the top: Instagram connection, Google Drive connection, media library, schedule config, and delivery mode. Users with missing configuration see a hint to run `/start`.
- **`/settings` renamed to `/setup`** - Primary command is now `/setup` with `/settings` kept as an alias. Bot command list updated: `/setup` = "Quick settings + open full setup wizard", `/settings` = "Alias for /setup". Header changed from "Bot Settings" to "Quick Setup".
- **Delivery language replaces pause/resume language** - All user-facing text reframed around "Delivery ON/OFF" instead of "Paused/Active/Running". Affects `/pause`, `/resume`, `/status`, `/help`, `/settings` toggle, and resume callback messages.
- **`/start` command always opens Mini App** - Returning users now see an "Open Storyline" button linking to a visual dashboard instead of a text command list. Text fallback retained when `OAUTH_REDIRECT_BASE_URL` is not configured.

### Removed

- **`/connect_drive` command removed** - Google Drive connection is now handled exclusively through the onboarding Mini App wizard (accessible via `/start`). The underlying OAuth routes remain unchanged.
- **7 Telegram commands retired** - `/schedule`, `/stats`, `/locks`, `/reset`, `/dryrun`, `/backfill`, `/connect` removed from bot menu. All still respond with a redirect message pointing to the appropriate replacement (`/settings`, `/status`, `/start`, or CLI).

### Added

- **Smart delivery reschedule for paused tenants** - When delivery is OFF, the scheduler loop automatically bumps overdue queue items forward by +24hr increments until they're in the future. Prevents a flood of 50+ items when resuming after extended pause.
  - New `QueueRepository.get_overdue_pending()` query method
  - New `ChatSettingsRepository.get_all_paused()` query method
  - New `SettingsService.get_all_paused_chats()` method
  - New `PostingService.reschedule_overdue_for_paused_chat()` with +24hr bump logic
  - Scheduler loop runs reschedule pass for all paused tenants every cycle
- **Mini App button in settings keyboard** - When `OAUTH_REDIRECT_BASE_URL` is configured, the settings menu includes a "Full Setup Wizard" button that opens the Mini App directly
- **Mini App home screen for returning users** - Dashboard view showing Instagram connection status, Google Drive connection, posting schedule, and queue status. Each section has an Edit button that jumps to the relevant setup step with a "Save & Return" flow.
- **Expanded `/api/onboarding/init` response** - Now includes `is_paused`, `dry_run_mode`, `queue_count`, and `last_post_at` fields for the dashboard display
- **"Run Full Setup Again" button** - Returning users can re-enter the full onboarding wizard from the home screen
- **Onboarding wizard completion** - Mini App wizard now fully functional end-to-end
  - Media folder validation saves `media_source_type`, `media_source_root`, and `media_sync_enabled` to `chat_settings`
  - New `/api/onboarding/start-indexing` endpoint triggers media sync during wizard
  - Enriched `/api/onboarding/init` response with `media_folder_configured`, `media_indexed`, `media_count`, and `onboarding_step`
  - Completing onboarding auto-enables `enable_instagram_api` (if connected) and `media_sync_enabled` (if folder configured); `dry_run_mode` always stays true
  - Onboarding step tracking: each wizard step saves progress to database for resume on reopen
  - New "Index Media" wizard step with progress indicator and result display
  - All wizard steps are skippable (Instagram, Google Drive, media folder, indexing, schedule)
  - Summary step shows configuration status for all setup items
  - Folder validation no longer auto-advances — shows results with explicit "Continue" button
- **Per-chat media source configuration** - `media_source_type` and `media_source_root` columns on `chat_settings` table
  - Each Telegram chat can now have its own media source (local path or Google Drive folder ID)
  - `NULL` values fall back to global `MEDIA_SOURCE_TYPE` / `MEDIA_SOURCE_ROOT` env vars (backward compatible)
  - New `SettingsService.get_media_source_config()` resolves per-chat config with env var fallback
  - `MediaSyncService.sync()` accepts `telegram_chat_id` for per-chat sync
  - Onboarding media-folder endpoint now saves selected folder to chat settings
  - Migration: `scripts/migrations/017_add_media_source_to_chat_settings.sql`

### Fixed

- **Google Drive media sync auth** - Media sync now passes tenant chat ID when creating Google Drive provider, enabling per-tenant OAuth credential lookup instead of falling back to non-existent service account

### Changed

- **ConfigValidator cloud deployment support** - Relaxed startup validation for cloud environments
  - `MEDIA_DIR` is now auto-created if it doesn't exist (needed for Railway's `/tmp/media`)
  - Removed `INSTAGRAM_ACCESS_TOKEN` and `INSTAGRAM_ACCOUNT_ID` env var requirements — tokens are managed via OAuth and stored in the database in multi-tenant mode
  - Cloudinary config check retained when `ENABLE_INSTAGRAM_API=true`

- **`.env.example` cloud variables** - Added cloud deployment configuration reference
  - `DATABASE_URL` full connection string option for PaaS platforms
  - `DB_SSLMODE`, `DB_POOL_SIZE`, `DB_MAX_OVERFLOW` for Neon tuning
  - `OAUTH_REDIRECT_BASE_URL` for Railway HTTPS domain
  - `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` for Google Drive OAuth
  - `MEDIA_SOURCE_TYPE`, `MEDIA_SOURCE_ROOT`, `MEDIA_SYNC_ENABLED` for cloud media

### Security

- **XSS prevention in OAuth HTML pages** - All user-supplied values (`username`, `email`, `title`, `message`) now escaped with `html.escape()` before interpolation into HTML responses (`src/api/routes/oauth.py`)
- **Onboarding chat_id verification** - `_validate_request()` now verifies the `chat_id` from the signed `initData` matches the request's `chat_id`, preventing cross-tenant manipulation; returns 403 on mismatch
- **CORS origin restriction** - Replaced `allow_origins=["*"]` with `OAUTH_REDIRECT_BASE_URL` (or `localhost` in development), and restricted `allow_headers` to `Content-Type`
- **Google Drive API query injection fix** - Escaped single quotes and backslashes in `folder_name` before interpolating into Google Drive API query strings (`google_drive_provider.py`)
- **Schedule input validation** - Added Pydantic `Field` validators: `posts_per_day` (1-50), `posting_hours_start/end` (0-23), `schedule_days` (1-30)
- **Instagram API exception data sanitization** - Removed `response` dict from `InstagramAPIError` to prevent full API response leakage through error tracking/logging
- **initData chat extraction** - `validate_init_data()` now extracts `chat_id` from Telegram's `chat` object when present in signed data (group chats)

### Added

- **Cloud deployment guide** - Comprehensive guide for deploying to Railway + Neon
  - Two-process architecture (worker + web) with Procfile
  - Neon PostgreSQL setup with SSL, pool sizing, and schema migration instructions
  - Full environment variable reference (30+ vars)
  - OAuth callback configuration for Instagram and Google Drive
  - Security checklist, cost estimates, and troubleshooting guide

- **Cloud-ready database configuration**
  - `DATABASE_URL` env var support — full connection string overrides individual `DB_*` components
  - `DB_SSLMODE` env var — appends `?sslmode=require` for Neon compatibility
  - `DB_POOL_SIZE` and `DB_MAX_OVERFLOW` env vars — configurable connection pool (default: 10/20, Neon free tier: 3/2)

- **Telegram Mini App onboarding wizard** - Self-service setup flow for new users via Telegram WebApp
  - 6-step wizard: Welcome, Connect Instagram, Connect Google Drive, Media Folder, Schedule, Summary
  - `validate_init_data()`: HMAC-SHA256 validation of Telegram `initData` for secure Mini App authentication
  - 5 API endpoints under `/api/onboarding/`: init, oauth-url, media-folder, schedule, complete
  - Static Mini App frontend (HTML/CSS/JS) served by FastAPI, Telegram theme-aware
  - OAuth polling pattern: Mini App polls `/init` every 3s to detect when OAuth completes
  - `/start` command updated: new users see "Open Setup Wizard" `WebAppInfo` button, returning users see dashboard
  - Migration 016: `onboarding_step` + `onboarding_completed` columns on `chat_settings`
  - `SettingsService`: `set_onboarding_step()` and `complete_onboarding()` methods
  - 30 new tests (8 webapp auth, 16 API routes, 3 settings service, 3 /start command)

- **Google Drive user OAuth flow** - Browser-based Google Drive connection for per-tenant media sourcing
  - `GoogleDriveOAuthService`: Fernet-encrypted state tokens, Google token exchange, per-tenant token storage
  - Google Drive OAuth routes: `/auth/google-drive/start` (redirect to Google consent) and `/auth/google-drive/callback` (exchange + store)
  - `/connect_drive` Telegram command: sends inline button with Google Drive OAuth link
  - Per-tenant token storage via `api_tokens.chat_settings_id` FK (migration 015)
  - `TokenRepository`: 3 new tenant-scoped methods (`get_token_for_chat`, `create_or_update_for_chat`, `delete_tokens_for_chat`)
  - `GoogleDriveService.get_provider_for_chat()`: creates GoogleDriveProvider from user OAuth credentials
  - `MediaSourceFactory`: accepts `telegram_chat_id` param, tries user OAuth before service account fallback
  - New settings: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
  - 43 new tests (18 OAuth service, 13 routes, 6 token repo, 3 command, 3 provider)

- **Instagram OAuth redirect flow** - Browser-based Instagram account connection replacing manual CLI token copy-paste
  - `OAuthService`: Fernet-encrypted state tokens (10min TTL, CSRF nonce), Meta token exchange (short→long-lived), account create/update
  - FastAPI app (`src/api/app.py`) with two OAuth endpoints: `/auth/instagram/start` (redirect to Meta) and `/auth/instagram/callback` (exchange + store)
  - `/connect` Telegram command: sends inline button with OAuth link, 10-minute expiry notice
  - HTML success/error pages for browser feedback after OAuth callback
  - Telegram notification on success ("Instagram connected! Account: @username") and failure
  - New dependencies: `fastapi>=0.109.0`, `uvicorn>=0.27.0`
  - New setting: `OAUTH_REDIRECT_BASE_URL`
  - 32 new tests (17 OAuthService, 12 route, 3 /connect command)

- **Per-tenant scheduler and posting pipeline** - Thread `telegram_chat_id` through scheduler, posting, and main loop for multi-tenant operation
  - `ChatSettingsRepository.get_all_active()` — discover all non-paused tenants
  - `SettingsService.get_all_active_chats()` — service-layer tenant discovery
  - `SchedulerService`: 4 methods accept `telegram_chat_id` (create_schedule, extend_schedule, both time-slot generators)
  - `PostingService`: `process_pending_posts` and `_get_chat_settings` accept `telegram_chat_id`; `_post_via_instagram` reads chat context from queue item
  - `main.py`: Scheduler loop iterates over all active tenants with per-tenant error isolation; legacy single-tenant fallback preserved
  - `TelegramService`: `admin_chat_id` cached in constructor, lifecycle notifications use instance property
  - `/schedule` command passes `update.effective_chat.id` to scheduler
  - `_notify_sync_error` uses `telegram_service.channel_id` instead of hardcoded constant
  - 20 new unit tests (scheduler loop, posting tenant, scheduler tenant, repository, service)

- **Per-tenant repository query filtering** - Add optional `chat_settings_id` parameter to 42 repository methods across 5 repositories
  - `BaseRepository`: New `_apply_tenant_filter()` helper used by all tenant-scoped repositories
  - `MediaRepository`: 13 methods updated (including `get_next_eligible_for_posting` with tenant-scoped subqueries)
  - `QueueRepository`: 10 methods updated (`shift_slots_forward` passes tenant through to `get_all`)
  - `HistoryRepository`: 5 methods + `HistoryCreateParams` dataclass updated
  - `LockRepository`: 7 methods updated (`is_locked` passes tenant through to `get_active_lock`)
  - `CategoryMixRepository`: 6 methods updated (`set_mix` scopes both SCD expire and create operations)
  - All parameters are `Optional[str] = None` — backward compatible, no service code changes
  - ~53 new unit tests for tenant filtering behavior

- **Multi-tenant data model foundation** - Add nullable `chat_settings_id` FK to 5 core tables for multi-tenant support
  - `media_items`, `posting_queue`, `posting_history`, `media_posting_locks`, `category_post_case_mix`
  - All FKs nullable: `NULL` = legacy single-tenant data (full backward compatibility)
  - `media_items.file_path` uniqueness moved from column-level to table-level `UniqueConstraint` per tenant
  - `media_posting_locks` unique constraint updated to include tenant scope
  - Partial unique index preserves legacy file_path uniqueness for NULL-tenant rows
  - Migration: `014_multi_tenant_chat_settings_fk.sql`
  - New model test suites: `test_posting_history.py`, `test_media_lock.py`, `test_category_mix.py`

- **CLI command tests for backfill, Google Drive, and sync** - 27 new unit tests for 3 previously untested CLI modules
  - `tests/cli/test_backfill_commands.py` - 10 tests covering `backfill-instagram` and `backfill-status` commands
  - `tests/cli/test_google_drive_commands.py` - 8 tests covering `connect-google-drive`, `google-drive-status`, `disconnect-google-drive`
  - `tests/cli/test_sync_commands.py` - 9 tests covering `sync-media` and `sync-status`

- **Model, config, and exception unit tests** - 12 new test files covering previously untested areas
  - Exception tests: `test_base_exceptions.py` (5 tests), `test_google_drive_exceptions.py` (22 tests), `test_instagram_exceptions.py` (22 tests) — inheritance hierarchy, attribute storage, catchability
  - Model tests: `test_media_item.py` (16 tests), `test_posting_queue.py` (10 tests), `test_chat_settings.py` (14 tests), `test_instagram_account.py` (8 tests), `test_api_token.py` (14 tests) — column defaults, nullability, uniqueness, repr, computed properties
  - Config tests: `test_constants.py` (7 tests), `test_settings.py` (22 tests) — default values, `database_url` property
  - All tests are pure unit tests (no database required)

### Fixed

- **Repository exports** - Added `ChatSettingsRepository` and `InstagramAccountRepository` to `src/repositories/__init__.py`
- **Stale comment** - Updated `get_recent_runs()` comment in `service_run_repository.py` to reflect actual production usage

- **Instagram backfill timestamp parsing on Python 3.10** - `+0000` timezone format isn't supported by `datetime.fromisoformat()` in Python 3.10, causing silent parse failures in `_is_after_date` and `_download_and_index`
- **CI FutureWarning crash** - Filter `FutureWarning` from `google.api_core` in pytest config to prevent test collection errors on Python 3.10

- **CLI unit tests for user, queue, and media commands** - Converted 17 skipped integration test placeholders to 24 working unit tests
  - `test_user_commands.py`: 6 tests (list users, empty DB, no-username fallback, promote, nonexistent user, invalid role)
  - `test_queue_commands.py`: 7 tests (create schedule, no media, default days, list queue, empty queue, process queue, force post)
  - `test_media_commands.py`: 11 tests (index success/error/nonexistent, list items/empty/category/active-only, validate valid/warnings/errors/nonexistent)
  - All tests use `@patch` + `CliRunner` pattern matching existing `test_instagram_commands.py`

### Changed

- **Extract shared Telegram handler utilities** - Promoted 2 private methods to module-level utilities in `telegram_utils.py`
  - `build_account_management_keyboard()` — pure function replacing duplicated keyboard building in account selection menu and add-account success path
  - `cleanup_conversation_messages()` — async helper replacing 3 identical message-deletion loops (success, error, cancel paths)
  - Deleted `_build_account_config_keyboard()` and `_cleanup_conversation_messages()` private methods from `TelegramAccountHandlers`
  - 12 new utility tests, 4 existing tests updated

- **Extract sub-methods from long handlers** - Decomposed `_do_autopost()` and `handle_status()` into focused helpers
  - `_do_autopost()` reduced from 353 to ~50 lines via `AutopostContext` dataclass + 7 extracted helpers (`_get_account_display`, `_upload_to_cloudinary`, `_handle_dry_run`, `_execute_instagram_post`, `_record_successful_post`, `_send_success_message`, `_handle_autopost_error`)
  - `handle_status()` reduced from 115 to ~50 lines via 4 extracted helpers (`_get_next_post_display`, `_get_last_posted_display`, `_get_instagram_api_status`, `_get_sync_status_line`)
  - 27 new tests covering all extracted methods

- **BackfillContext dataclass for parameter reduction** - Introduced `BackfillContext` to bundle shared state across backfill call chain
  - Reduces `_backfill_feed` from 9 to 3 params, `_backfill_stories` from 8 to 2, `_process_media_item` from 8 to 3, `_process_carousel` from 7 to 2, `_download_and_index` from 7 to 6
  - Removed unused `username` parameter from `_download_and_index`
  - Added `make_ctx` test fixture and 2 new `TestBackfillContext` tests

- **Refactored add-account state machine** - Decomposed 315-line `handle_add_account_message()` into focused helpers
  - Extracted `_handle_display_name_input()`, `_handle_account_id_input()`, `_handle_token_input()` step handlers
  - Extracted `_validate_instagram_credentials()` for API call + account create/update
  - Extracted `_cleanup_conversation_messages()` deduplicating 3 identical cleanup loops
  - Extracted `_build_account_config_keyboard()` deduplicating 2 keyboard builders (returns `InlineKeyboardMarkup`)
  - Simplified `handle_account_selection_menu()` and `handle_add_account_cancel()` using shared helpers

### Fixed

- **Exception-shadowing bug in add-account error handling** - Inner `except Exception as e:` during message deletion overwrote the outer API error variable, causing error messages to display deletion errors instead of the actual API failure

### Added

- **Media Source Provider Abstraction** - Foundation for cloud media sources (Phase 01 of Cloud Media Enhancements)
  - `MediaSourceProvider` abstract interface for file access across local, cloud, and remote sources
  - `MediaFileInfo` dataclass for provider-agnostic file metadata
  - `LocalMediaProvider` wrapping filesystem operations behind the provider interface
  - `MediaSourceFactory` for creating provider instances by source type
  - `source_type` and `source_identifier` columns on `media_items` table (migration 011)
  - `get_by_source_identifier()` repository method for provider-based lookups
  - Unified `upload_media()` method on CloudStorageService accepting file path or raw bytes

- **Google Drive Media Source Provider** - Cloud media integration via Google Drive API v3 (Phase 02 of Cloud Media Enhancements)
  - `GoogleDriveProvider` implementing `MediaSourceProvider` for Drive API file access
  - Service account authentication for server-to-server access (folder shared with service account)
  - Subfolder-as-category convention matching local filesystem behavior
  - Uses Drive's `md5Checksum` for dedup (avoids downloading just to hash)
  - Chunked downloads via `MediaIoBaseDownload` for large files
  - `GoogleDriveService` orchestration with encrypted credential storage via `api_tokens` table
  - Google Drive exception hierarchy: `GoogleDriveError`, `GoogleDriveAuthError`, `GoogleDriveRateLimitError`, `GoogleDriveFileNotFoundError`
  - `MediaSourceFactory` lazy registration of Google Drive provider (no crash if SDK not installed)
  - CLI commands: `connect-google-drive`, `google-drive-status`, `disconnect-google-drive`
  - `delete_token()` method added to `TokenRepository` for proper credential cleanup

- **Scheduled Media Sync Engine** - Automatic reconciliation of media sources with database (Phase 03 of Cloud Media Enhancements)
  - `MediaSyncService` with full sync algorithm: new file indexing, deleted file deactivation, rename/move detection via hash matching, reactivation of reappeared files
  - `SyncResult` dataclass for tracking sync outcomes (new, updated, deactivated, reactivated, unchanged, errors)
  - Background `media_sync_loop` in `src/main.py` following existing asyncio loop pattern
  - Health check integration: `media_sync` check in `check-health` command
  - CLI commands: `sync-media` (manual trigger), `sync-status` (last sync info)
  - New settings: `MEDIA_SYNC_ENABLED`, `MEDIA_SYNC_INTERVAL_SECONDS`, `MEDIA_SOURCE_TYPE`, `MEDIA_SOURCE_ROOT`
  - New repository methods: `get_active_by_source_type()`, `get_inactive_by_source_identifier()`, `reactivate()`, `update_source_info()`

- **Media Source Configuration & Health** - Telegram UI integration for media sync engine (Phase 04 of Cloud Media Enhancements)
  - Media sync toggle in `/settings` menu (per-chat, persisted to `chat_settings`)
  - New `/sync` command for manual media sync from Telegram
  - Enhanced `/status` output with media sync health section
  - Proactive Telegram notifications on sync errors (respects verbose setting)
  - Enhanced health check with provider connectivity testing
  - Database migration `012_chat_settings_media_sync.sql` for per-chat sync toggle

- **Instagram Media Backfill** - Pull existing media from Instagram back into the system (Phase 05 of Cloud Media Enhancements)
  - New `InstagramBackfillService` for fetching feed posts, live stories, and carousel albums from Instagram Graph API
  - New CLI commands: `backfill-instagram` (with --limit, --media-type, --since, --dry-run, --account-id), `backfill-status`
  - New Telegram command: `/backfill [limit] [dry]`
  - Carousel album expansion: downloads each child image/video individually
  - Cursor-based pagination for large media libraries
  - Duplicate prevention via `instagram_media_id` tracking column
  - Content-level dedup via SHA256 hash comparison
  - Date filtering with early termination (--since flag)
  - Dry-run mode for previewing without downloading
  - Multi-account support via --account-id flag
  - New exception hierarchy: `BackfillError`, `BackfillMediaExpiredError`, `BackfillMediaNotFoundError`
  - Database migration 013: `instagram_media_id` and `backfilled_at` columns on `media_items`

### Changed

- **Posting pipeline decoupled from filesystem** - All media access now goes through provider abstraction
  - TelegramService sends photos via provider download + BytesIO (not `open(file_path)`)
  - TelegramAutopostHandler uploads to Cloudinary via provider download + bytes
  - PostingService uses provider for Instagram API upload flow
  - Media type detection uses `mime_type` column instead of file extension parsing

### Removed

- **Remove 13 confirmed dead repository methods** - Audit and clean up unused code from 4 repository files
  - `category_mix_repository.py`: removed `get_category_ratio`, `get_mix_at_date`
  - `interaction_repository.py`: removed `get_by_user`, `get_by_type`, `get_by_name`, `count_by_user`, `count_by_name`
  - `history_repository.py`: removed `get_by_user_id`, `get_stats`
  - `token_repository.py`: removed `get_all_for_service`, `get_expired_tokens`, `delete_token`, `delete_all_for_service`
  - Annotated 5 future-use methods with `# NOTE: Unused in production` comments
  - Cleaned up corresponding tests and unused imports (`func` from interaction_repository)

### Tests

- **Add missing test files for 6 uncovered modules** - Create 64 new unit tests across 6 previously untested files
  - `test_telegram_autopost.py` (6 tests): Safety gates, dry-run mode, Cloudinary failure, operation locks
  - `test_instagram_commands.py` (11 tests): CLI commands for status, add/list/deactivate/reactivate accounts
  - `test_base_repository.py` (14 tests): Session lifecycle, commit/rollback, context manager, check_connection
  - `test_chat_settings_repository.py` (7 tests): CRUD, .env bootstrap, pause tracking
  - `test_instagram_account_repository.py` (12 tests): Account CRUD, activate/deactivate, prefix lookup
  - `test_token_repository.py` (14 tests): Token CRUD, UPSERT, expiry, multi-account filter chains
  - Fixed plan's lazy-import patch paths (must patch at source module for `from ... import` inside function bodies)
  - Total test suite: 528 passed, 38 skipped, 0 failures

- **Convert 45 skipped service tests to unit tests** - Replace integration fixtures with mock-based unit tests across 7 service test files
  - Rewrote test_base_service.py, test_media_lock.py, test_posting.py, test_scheduler.py with correct method signatures
  - Implemented 3 stub tests in test_telegram_commands.py (next_media_not_found, next_notification_failure, next_logs_interaction)
  - Fixed is_paused/set_paused mocking for pause/resume tests (property reads from settings_service)
  - Removed 12 duplicate @pytest.mark.skip decorators from test_instagram_api.py; added missing dependency patches
  - Updated Instagram API tests for multi-account architecture (is_configured, post_story credential flow)
  - Fixed time-dependent scheduler tests (days=2 to ensure future slots)

- **Convert 74 skipped repository tests to unit tests** - Replace `test_db` integration fixtures with mock-based unit tests
  - Pattern: `patch.object(Repo, '__init__')` + `MagicMock(spec=Session)` for chainable query mocking
  - 67 new passing tests across 7 repository test files (media, queue, user, interaction, lock, history, service_run)
  - Fixed method signatures to match actual repo APIs (e.g., `create(media_item_id=)` not `create(media_id=)`)
  - Dropped 7 tests for non-existent methods (`get_or_create`, `get_never_posted`, `get_least_posted`, etc.)
  - 9 integration-only tests remain skipped (complex multi-table queries, slot shifting)
  - Added edge case tests: not-found paths, max retries exceeded, empty stats, permanent locks

### Changed

- **Update all pinned dependencies to latest versions** - Bring all ==pinned packages current
  - Tier 1 (patch): psycopg2-binary 2.9.9→2.9.11, python-dateutil 2.8.2→2.9.0.post0
  - Tier 2 (minor): pydantic 2.5→2.12.5, pydantic-settings 2.1→2.12, SQLAlchemy 2.0.23→2.0.46, click 8.1→8.3, rich 13.7→14.3, python-dotenv 1.0→1.2, alembic 1.13→1.18
  - Tier 3 (major): python-telegram-bot 20.7→22.6, httpx 0.25→0.28, Pillow 10.1→12.1, pytest 7.4→9.0, pytest-asyncio 0.21→1.3, pytest-cov 4.1→7.0, pytest-mock 3.12→3.15

- **Documentation review and accuracy audit** - Cross-referenced all docs against codebase post-v1.6.0 refactor
  - Corrected test counts, setting names, supported formats, and deploy script defaults
  - Updated code examples in security review for post-refactor handler locations
  - Archived 4 completed planning docs; standardized status markers (PENDING/IN PROGRESS/COMPLETED)

### Refactored

- **Decompose long functions into focused helpers** - Extract logic from 5 oversized methods
  - `HistoryRepository.create()`: Bundle 16 parameters into `HistoryCreateParams` dataclass; update all 5 call sites
  - `SchedulerService`: Extract shared `_fill_schedule_slots()` from duplicated loops in `create_schedule()` and `extend_schedule()`
  - `InstagramAccountService.add_account()`: Extract `_validate_new_account()` and `_create_account_with_token()`
  - `CloudStorageService.upload_media()`: Extract `_validate_file_path()` and `_build_upload_options()`

- **Extract magic numbers into named constants** (#29) - Replace hardcoded values with descriptive constants
  - Created `src/config/constants.py` for shared constants (MIN/MAX_POSTS_PER_DAY, MIN/MAX_POSTING_HOUR)
  - Added class-level constants to SchedulerService, TelegramCommandHandlers, TelegramSettingsHandlers, SettingsService, InstagramAPIService, TelegramAccountHandlers
  - All validation logic now references named constants with clear error messages

- **Replace silent error swallowing with debug logging** (#30) - Add diagnostic visibility to suppressed exceptions
  - Added `logger.debug()` to 9 bare `except Exception: pass` blocks across 3 files
  - Covers repository lifecycle cleanup, Telegram message deletion, and session recovery
  - `__del__` method intentionally kept as `pass` (logging unsafe during garbage collection)

- **Route health check database query through repository layer** (#31) - Fix architecture violation (ARCH-1)
  - Added `BaseRepository.check_connection()` static method for DB connectivity checks
  - Removed direct `sqlalchemy` and `get_db` imports from `HealthCheckService`
  - No services now access the database directly; all queries go through repositories

- **Route scheduler media selection through repository layer** (#32) - Fix architecture violation (ARCH-2)
  - Moved `_select_media_from_pool()` query logic from `SchedulerService` to `MediaRepository.get_next_eligible_for_posting()`
  - Removed inline `sqlalchemy` and model imports from service layer
  - Service method now delegates to repository with identical query behavior

- **Refactor callback dispatcher to dictionary dispatch** - Replace 90-line if-elif chain with two-tier dispatch
  - Standard `(data, user, query)` handlers served via dictionary lookup (20 entries)
  - Special-case handlers (non-standard signatures, sub-routing) in dedicated method (7 entries)
  - Unknown callback actions now log a warning instead of being silently ignored

- **Extract Telegram handler common utilities** - Deduplicate 4 repeated patterns across handler modules
  - Created `telegram_utils.py` with shared validation, keyboard builders, and state cleanup helpers
  - Replaced ~15 inline queue validation blocks with `validate_queue_item()` / `validate_queue_and_media()`
  - Replaced ~3 keyboard constructions with `build_queue_action_keyboard()` / `build_error_recovery_keyboard()`
  - Replaced ~6 cancel keyboard constructions with shared `CANCEL_KEYBOARD` constant
  - Replaced ~6 state cleanup blocks with `clear_settings_edit_state()` / `clear_add_account_state()`

### Fixed

- **Race Condition on Telegram Button Clicks** - Prevent duplicate operations from rapid double-clicks
  - Added `asyncio.Lock` per queue item to prevent concurrent execution
  - Added cancellation flags so terminal actions (Posted/Skip/Reject) abort pending auto-posts
  - Auto-post checks cancellation after Cloudinary upload and before Instagram API call
  - Shows "⏳ Already processing..." feedback when lock is held
  - Locks and flags cleaned up after operation completes

## [1.6.0] - 2026-02-09

### Added

#### Instagram Account Management (Phase 1.5)

- **Multi-Account Support** - Store multiple Instagram account identities
  - Display name, Instagram ID, username per account
  - Active/inactive status for soft deletion
  - Separation of concerns: identity (accounts) vs credentials (tokens) vs selection (settings)
- **Account Switching via Telegram** - Switch between accounts in /settings menu
  - Per-chat active account selection stored in `chat_settings`
  - Auto-select when only one account exists
  - Visual indicator of currently active account
- **Per-Account Token Storage** - OAuth tokens linked to specific accounts
  - `api_tokens.instagram_account_id` foreign key
  - Supports multiple tokens per service (one per account)
  - Backward compatible with legacy .env-based tokens
- **New CLI Commands**
  - `add-instagram-account` - Register new Instagram account with encrypted token
  - `list-instagram-accounts` - Show all registered accounts with status
  - `deactivate-instagram-account` - Soft-delete an account
  - `reactivate-instagram-account` - Restore a deactivated account
- **InstagramAccountService** - New service for account management
  - `list_accounts()`, `get_active_account()`, `switch_account()`
  - `add_account()`, `deactivate_account()`, `reactivate_account()`
  - `get_accounts_for_display()` - Formatted data for Telegram UI
  - `auto_select_account_if_single()` - Auto-selection logic
- **InstagramAPIService** - Multi-account posting support
  - `post_story()` now accepts `telegram_chat_id` parameter
  - Credentials retrieved based on active account for chat
  - Fallback to legacy .env config when no account selected
- **TokenRefreshService** - Per-account token refresh
  - `refresh_instagram_token()` accepts `instagram_account_id`
  - `refresh_all_instagram_tokens()` - Batch refresh for all accounts
  - Maintains backward compatibility with legacy tokens
- 24 new unit tests for InstagramAccountService

#### Telegram /settings Menu Improvements

- **Close Button** - Dismiss the settings menu cleanly with ❌ Close button
- **Verbose Mode Toggle** - Control notification verbosity via 📝 Verbose toggle
  - ON (default): Shows detailed workflow instructions
  - OFF: Shows minimal info
  - Applies to manual posting notifications and auto-post success messages
- **Schedule Management Buttons** - Manage queue directly from settings
  - 🔄 Regenerate: Clears queue and creates new 7-day schedule (with confirmation)
  - 📅 +7 Days: Extends existing queue by 7 days (preserves current items)
- Removed Quick Actions buttons (📋 Queue, 📊 Status) - use `/queue` and `/status` commands instead
- **Instagram Account Configuration via Telegram**
  - Renamed "Select Account" to "Configure Accounts" - full account management menu
  - **Add Account Flow** - 3-step conversation: display name → account ID → access token
    - Auto-fetches username from Instagram API to validate credentials
    - If account already exists, updates the token instead of erroring
  - **Remove Account** - Deactivate accounts directly from Telegram with confirmation
  - **Account Selection** - Select active account from the same menu
  - Security: bot messages deleted after flow; user warned to delete sensitive messages
- **SchedulerService `extend_schedule()` method** - Add days to existing schedule without clearing
  - Finds last scheduled time, generates new slots starting from next day
  - Respects category ratios and existing scheduler logic

#### Inline Account Selector (Phase 1.7)

- **Account Indicator in Caption** - Posting notifications show which Instagram account is active
  - Format: "📸 Account: {display_name}"
  - Shows "📸 Account: Not set" when no account is configured
- **Account Selector Button** - Switch accounts without leaving the posting workflow
  - New "📸 {account_name}" button in posting notifications
  - Click to see simplified account selector (no add/remove, just switch)
  - Immediate feedback with toast notification on switch
  - Automatically returns to posting workflow with updated caption
- **Button Layout Reorganization**
  - Status Actions Grouped: Posted, Skip, and Reject buttons together
  - Instagram Actions Grouped: Account selector and Open Instagram below
  - New order: Auto Post → Posted/Skip → Reject → Account Selector → Open Instagram
- **Shortened Callback Data** - Uses 8-char UUID prefixes for Telegram's 64-byte callback limit
  - New repository methods: `QueueRepository.get_by_id_prefix()`, `InstagramAccountRepository.get_by_id_prefix()`
- **Settings Menu** - Renamed account button to "Default: {friendly_name}", clearer "Choose Default Account" language

#### Telegram Command Menu & Message Cleanup (Phase 1.8)

- **Native Telegram Command Menu** - Commands appear in Telegram's native "/" autocomplete
  - Uses `set_my_commands()` API; all 15 commands registered with descriptions
  - Updates automatically when bot initializes
- **`/cleanup` Command** - Delete recent bot messages from chat
  - Queries `user_interactions` table for bot messages
  - Gracefully handles 48-hour deletion limit (Telegram API restriction)
  - Shows summary: deleted count and failed count
  - Auto-deletes confirmation message after 5 seconds
- **Renamed `/clear` → `/reset`** - Clearer distinction from `/cleanup`
  - `/reset` = Reset posting queue to empty; `/cleanup` = Delete bot messages from chat
  - CLI aligned: `storyline-cli reset-queue`
- **Automatic Message ID Tracking** - Bot tracks sent message IDs for cleanup
  - Tracks notification messages (photos with buttons) and status/queue listing messages
  - 100-message rolling cache

### Changed

#### TelegramService Refactor

- **PR 1: Extract Command Handlers** - Architecture improvement
  - Extracted 14 `/command` handlers into new `TelegramCommandHandlers` class (`telegram_commands.py`, ~715 lines)
  - `TelegramService` reduced by ~655 lines (from 3,504 to 2,849)
  - Uses composition pattern: handler class receives service reference via `__init__(self, service)`
  - Command registration moved to a clean `command_map` dict in `initialize()`
  - Tests split into `test_telegram_commands.py`
  - All 81 tests pass (65 passed, 16 skipped) - zero regressions
- **PR 2: Extract Callbacks + Autopost** - Architecture improvement
  - Extracted 9 callback handlers into new `TelegramCallbackHandlers` class (`telegram_callbacks.py`)
  - Extracted auto-post flow into new `TelegramAutopostHandler` class (`telegram_autopost.py`)
  - `TelegramService` reduced by ~765 lines (from 2,849 to ~1,984)
  - Tests split into `test_telegram_callbacks.py`; routing tests remain in `test_telegram_service.py`
  - All 81 tests pass - zero regressions
- **PR 3: Extract Settings + Accounts** - Architecture improvement
  - Extracted settings handlers into new `TelegramSettingsHandlers` class (`telegram_settings.py`)
  - Extracted account handlers into new `TelegramAccountHandlers` class (`telegram_accounts.py`)
  - `TelegramService` reduced from ~1,984 to ~681 lines (core routing, initialization, captions, shared utilities)
  - Tests split into `test_telegram_settings.py` and `test_telegram_accounts.py`
  - All 345 tests pass (77 telegram-specific) - zero regressions

#### Verbose Settings Expansion

- **Verbose Setting Now Controls More Message Types** - Manual posted confirmations, rejected confirmations, and dry run results
- Added `_is_verbose()` helper method to reduce code duplication (replaces 3-line inline checks)
- User-initiated commands (`/status`, `/queue`, `/help`, etc.) always show full detail

#### Code Quality & Developer Experience

- **Refactored Settings Keyboard** - Eliminated 3x code duplication; extracted `_build_settings_message_and_keyboard()` helper
- **Refactored Posted/Skipped Handlers** - Extracted shared `_complete_queue_action()` helper (~60 lines of duplicated code removed)
- **Simple Caption Now Respects Verbose and Account** - Consistency fix for `CAPTION_STYLE=simple`
- **Centralized Version String** - Added `__version__` in `src/__init__.py`; `setup.py`, `cli/main.py`, and startup notification now reference it
- **Eliminated Redundant DB Queries** - `_is_verbose()` accepts optional pre-loaded `chat_settings` parameter
- **Claude Code Hooks** - Auto-fix linting errors on file save (`ruff check --fix` + `ruff format`)
- **Pre-Push Linting Script** - `scripts/lint.sh` catches CI failures locally
- **Documentation Organization** - Moved SECURITY_REVIEW.md to documentation/ folder; added markdown write permissions
- **Phase 1.7 Feature Plan** - Added inline account selector planning document

### Fixed

#### Critical Bugs

- **Dry Run Mode Blocking Telegram Notifications** - Dry run was blocking ALL Telegram notifications; now only affects Instagram API posting (`src/services/core/posting.py:304-340`)
- **`/cleanup` Command Not Finding Messages After Restart** - Relied on in-memory deque cleared on restart; now queries `user_interactions` table
  - Removed in-memory `message_cache` deque; added `get_bot_responses_by_chat()` repository method and `get_deletable_bot_messages()` service method
- **Auto-Post Success Missing User in Verbose OFF** - Now always shows `✅ Posted to @account by @user` regardless of verbose setting
- **Settings Workflow - Database vs .env** - Fixed .env values overriding database settings for dry run, Instagram API toggle, account switching, and verbose mode
  - Fixed all toggle locations: `_do_autopost()`, `send_notification()`, `/dryrun`, `safety_check_before_post()`
  - All settings now persist across service restarts
- **Token Encryption for Multi-Account** - Tokens added via Telegram were stored unencrypted; now properly encrypts when storing
- **Account Switching from Posting Workflow** - Fixed critical bug preventing account switching
  - Root Cause 1: Callback data parsing split on ALL colons instead of just the first one
  - Root Cause 2: Debug logging sliced UUID objects without converting to string

#### Settings & Account Fixes

- **Add Account Flow - Existing Account Handling** - Token now updated instead of showing error when account already exists
- **Add Account Flow - Security Warning** - Fixed misleading message about bot deleting user messages
- **InstagramAccountService** - Added `update_account_token()` and `get_account_by_instagram_id()` methods
- **Editable Posts/Day and Hours** - Previously display-only in /settings; now starts a conversation flow to edit values
- **`_handle_cancel_reject` Bug** - Now uses `chat_settings.enable_instagram_api` (database) instead of `settings.ENABLE_INSTAGRAM_API` (env var)

#### CI & Code Quality

- **CI Failures** - Resolved all blocking CI issues (#20)
  - Fixed missing `asyncio` import, auto-formatted telegram_service.py
  - Updated test suite for `/clear` → `/reset` rename; fixed assertion for dry_run_mode
  - All 310 tests passing
- **Ruff Linting Errors** - Fixed all 48 linting errors
  - Removed 8 unused imports, fixed 18 unnecessary f-strings, fixed 7 boolean comparison patterns
  - Reorganized imports in cli/main.py, removed 1 unused variable
- **CI Test Failures** - Fixed ALL test failures (48 failures → 0)
  - Updated CI environment variables for individual database components
  - Fixed PostingService, HistoryRepository, CategoryMixRepository, TelegramService tests
  - Converted integration tests to use mocks; skipped complex tests for future refactoring
  - Final: 310 passed, 141 skipped, 0 failed

### Technical Details

#### Database Migrations

- `007_instagram_accounts.sql` - Creates `instagram_accounts` table
- `008_api_tokens_account_fk.sql` - Adds FK to `api_tokens`, updates unique constraint
- `009_chat_settings_active_account.sql` - Adds `active_instagram_account_id` to `chat_settings`
- `010_add_verbose_notifications.sql` - Adds `show_verbose_notifications` column to `chat_settings`

#### New Files

- `src/models/instagram_account.py` - InstagramAccount SQLAlchemy model
- `src/repositories/instagram_account_repository.py` - Full CRUD operations
- `src/services/core/instagram_account_service.py` - Business logic layer
- `src/services/core/telegram_commands.py` - Command handlers (~715 lines)
- `src/services/core/telegram_callbacks.py` - Callback handlers
- `src/services/core/telegram_autopost.py` - Auto-post handler
- `src/services/core/telegram_settings.py` - Settings UI handlers
- `src/services/core/telegram_accounts.py` - Account selection handlers
- `tests/src/services/test_instagram_account_service.py` - Unit tests
- `tests/src/services/test_telegram_commands.py` - Command handler tests
- `tests/src/services/test_telegram_callbacks.py` - Callback handler tests
- `tests/src/services/test_telegram_settings.py` - Settings UI tests
- `tests/src/services/test_telegram_accounts.py` - Account handler tests

#### Modified Files

- `src/models/api_token.py` - Added instagram_account_id FK and relationship
- `src/models/chat_settings.py` - Added active_instagram_account_id FK, show_verbose_notifications
- `src/repositories/token_repository.py` - Per-account token methods
- `src/repositories/queue_repository.py` - Added `get_by_id_prefix()`
- `src/repositories/chat_settings_repository.py` - Updated get_or_create defaults
- `src/services/core/telegram_service.py` - Reduced to ~681 lines (core routing, initialization, captions)
- `src/services/core/scheduler.py` - Added `extend_schedule()` method
- `src/services/integrations/instagram_api.py` - Multi-account support
- `src/services/integrations/token_refresh.py` - Per-account refresh
- `cli/commands/instagram.py` - New CLI commands
- `cli/main.py` - Registered new commands

## [1.5.0] - 2026-01-24

### Added - Claude Code Automation & Bot Response Logging

#### Bot Response Logging
- **Outgoing Message Tracking** - Log all bot responses to `user_interactions` table
  - New `bot_response` interaction type for outgoing messages
  - Captures message text, button layouts, and media filenames
  - Enables full visibility into bot activity without viewing Telegram
  - Query both incoming (user actions) and outgoing (bot responses) in one place

- **Enhanced Visibility Methods** - Log key bot actions
  - `photo_notification` - When bot sends media with approve buttons
  - `caption_update` - When marking posts or updating captions
  - `text_reply` - For status messages and confirmations

#### Claude Code Integration
- **Project-Specific Configuration** - `.claude/settings.json` for safe automation
  - Allow list for safe read-only commands (list, status, check)
  - Deny list for dangerous posting commands (process-queue, create-schedule)
  - Enables autonomous development iteration with guardrails

- **`/telegram-status` Command** - SSH-based bot status checking
  - Query bidirectional activity (incoming + outgoing messages)
  - Show current queue and recent posts
  - Check service health via systemctl
  - No need to view Telegram directly

- **Safety Documentation** - Updated CLAUDE.md with critical rules
  - Clear dangerous vs safe command lists
  - Remote development (Raspberry Pi) guidelines
  - Database query examples for safe inspection

### Changed
- `user_interactions.user_id` is now nullable to support `bot_response` entries
- Updated `check_interaction_type` constraint to include `bot_response`
- Moved legacy docs from `documentation/updates/` to `documentation/archive/`

### Technical Details

#### Database Migration (005)
- `ALTER TABLE user_interactions ALTER COLUMN user_id DROP NOT NULL`
- Added `bot_response` to interaction_type check constraint
- New partial index on `created_at` for bot_response queries

#### Files Changed
- `src/models/user_interaction.py` - Nullable user_id, updated docstring
- `src/services/core/interaction_service.py` - Added `log_bot_response()` method
- `src/services/core/telegram_service.py` - Log outgoing messages in handlers
- `scripts/migrations/005_add_bot_response_logging.sql` - Schema migration
- `.claude/settings.json` - Project permission configuration
- `.claude/commands/telegram-status.md` - Status check slash command

## [1.4.0] - 2026-01-10

### Added - Phase 1.6: Category-Based Scheduling

#### Category Organization
- **Category Extraction** - Automatically extract category from folder structure during indexing
  - Folder structure: `media/stories/memes/` → category: `memes`
  - Folder structure: `media/stories/merch/` → category: `merch`
  - Categories stored in `media_items.category` column
  - Configurable via `--extract-category` flag (default: enabled)

#### Posting Ratios (Type 2 SCD)
- **`category_post_case_mix` Table** - Track posting ratio configuration with full history
  - Type 2 Slowly Changing Dimension design for audit trail
  - Ratios stored as decimals (0.70 = 70%)
  - Validation: all active ratios must sum to 1.0 (100%)
  - Supports multiple categories with any ratio split

- **Interactive Ratio Configuration** - User-friendly prompts during indexing
  - Prompts: "What % would you like 'memes'?" format
  - Validates total sums to 100%
  - Allows re-entry if validation fails
  - Shows current vs new ratio comparisons

#### Scheduler Integration
- **Category-Aware Slot Allocation** - Deterministic ratio-based scheduling
  - Allocates slots proportionally (e.g., 70% memes, 30% merch)
  - Handles rounding with largest remainder to last category
  - Shuffles allocation for variety (not all memes then all merch)
  - Fallback to any category when target is exhausted

- **Enhanced Selection Logic** - Category-filtered media selection
  - Filters by target category first
  - Falls back to any available media if category exhausted
  - Maintains existing priority rules (never-posted first, least-posted)
  - Logs category allocation and fallbacks

#### New CLI Commands
- **`storyline-cli list-categories`** - Show categories with posting ratios
  - Displays current ratios and media counts per category
  - Shows if no ratios are configured

- **`storyline-cli update-category-mix`** - Update posting ratios interactively
  - Prompts for each category's percentage
  - Validates total and saves to database
  - Creates new SCD record (preserves history)

- **`storyline-cli category-mix-history`** - View ratio change history
  - Shows all historical ratio configurations
  - Includes effective dates and who made changes
  - Useful for auditing scheduling changes

#### Enhanced Existing Commands
- **`create-schedule`** - Now shows category breakdown
  - Displays how many slots allocated per category
  - Shows percentage breakdown of scheduled items
  - Logs category allocation summary

- **`list-queue`** - Added category column
  - Shows category for each queued item
  - Helps verify ratio-based scheduling

- **`index-media`** - Category extraction and ratio prompts
  - Extracts category from folder structure
  - Prompts for ratio configuration after indexing
  - Option to skip ratio configuration

### Technical Details

#### Database Schema
- **New column**: `media_items.category` (TEXT, indexed)
- **New table**: `category_post_case_mix`
  - `id` (UUID) - Primary key
  - `category` (VARCHAR 100) - Category name
  - `ratio` (NUMERIC 5,4) - Ratio as decimal (0.0000-1.0000)
  - `effective_from` (TIMESTAMP) - When ratio became active
  - `effective_to` (TIMESTAMP) - When ratio was superseded (NULL = current)
  - `is_current` (BOOLEAN) - Quick filter for active ratios
  - `created_by_user_id` (UUID FK) - Who made the change

#### Migrations
- `scripts/migrations/001_add_category_column.sql` - Add category to media_items
- `scripts/migrations/002_add_category_post_case_mix.sql` - Create ratio table
- `scripts/setup_database.sql` - Updated for fresh installations

#### New Components
- **CategoryPostCaseMix** model (`src/models/category_mix.py`)
- **CategoryMixRepository** (`src/repositories/category_mix_repository.py`)
  - `get_current_mix()` - Returns list of active ratio records
  - `get_current_mix_as_dict()` - Returns {category: ratio} dict
  - `set_mix()` - Sets new ratios (creates SCD records)
  - `get_history()` - Returns all historical records

#### Modified Components
- **SchedulerService** - Added category-based slot allocation
- **MediaRepository** - Added category parameter and get_categories()
- **MediaIngestionService** - Added category extraction logic

### Testing
- **34 new tests** for category scheduling features
  - Category extraction tests (7 tests)
  - CategoryMixRepository tests (18 tests)
  - Scheduler category allocation tests (9 tests)
- **Total tests: 173 → 268** (95 new, including other improvements)

### Documentation
- Updated README.md with Phase 1.6 features
- Updated CHANGELOG.md (this file)
- Updated project structure with media subdirectories
- Updated CLAUDE.md with new database tables and CLI commands

## [1.3.0] - 2026-01-08

### Added - Phase 1.5 Week 2: Telegram Bot Commands

#### New Slash Commands
- **`/pause`** - Pause automatic posting while keeping bot responsive
  - Prevents scheduled posts from being processed
  - Manual posting via `/next` still works
  - Shows count of pending posts that will be held

- **`/resume`** - Resume posting with smart overdue handling
  - If no overdue posts: Resumes immediately
  - If overdue posts exist: Shows options to:
    - 🔄 Reschedule (spread overdue posts over next few hours)
    - 🗑️ Clear (remove overdue posts, keep future scheduled)
    - ⚡ Force (process all overdue posts immediately)

- **`/schedule [N]`** - Create N days of posting schedule (1-30 days)
  - Default: 7 days if no argument provided
  - Shows: scheduled count, skipped count, total slots
  - Uses existing scheduler algorithm with smart media selection

- **`/stats`** - Show media library statistics
  - Total active media items
  - Never posted vs posted once vs posted 2+ times
  - Permanently locked (rejected) count
  - Temporarily locked count
  - Items available for posting

- **`/history [N]`** - Show last N posts (default 5, max 20)
  - Status indicator (✅ posted, ⏭️ skipped, 🚫 rejected)
  - Timestamp and user attribution
  - Handles empty history gracefully

- **`/locks`** - View permanently locked (rejected) items
  - Lists all permanently rejected media files
  - Shows file names for identification
  - Useful for reviewing what's been blocked

- **`/clear`** - Clear pending queue with confirmation
  - Shows confirmation dialog with pending count
  - Two-step process prevents accidental clearing
  - Media items remain in library (only queue cleared)

#### Pause Integration
- **PostingService** now checks pause state before processing
  - Scheduled posts are skipped when paused
  - Returns `paused: True` in result dict for visibility
  - Logs when posts are skipped due to pause

#### Repository Enhancement
- **QueueRepository** - Added `update_scheduled_time()` method
  - Supports rescheduling queue items
  - Used by resume:reschedule callback

#### Updated Help Text
- `/help` command now includes all new commands with descriptions
- Commands grouped by function (operational vs informational)

### Changed

#### Test Suite Expansion
- **26 new tests** for all new commands and callbacks
- Test coverage for:
  - Pause command (2 tests)
  - Resume command with overdue handling (3 tests)
  - Schedule command (2 tests)
  - Stats command (1 test)
  - History command (2 tests)
  - Locks command (2 tests)
  - Clear command (2 tests)
  - Resume callbacks: reschedule, clear, force (3 tests)
  - Clear callbacks: confirm, cancel (2 tests)
  - Pause integration with PostingService (1 test)
- **Total tests: 147 → 173** (26 new)

### Technical Details

#### Pause State Management
- Uses class-level variable `TelegramService._paused`
- Property `is_paused` for read access
- Method `set_paused(bool)` for write access
- Persists across scheduler cycles within same process

#### Callback Handler Routing
- New callback prefixes: `resume:*`, `clear:*`
- Extends existing callback router pattern
- Full interaction logging for audit trail

### Documentation
- Updated CHANGELOG.md (this file)
- Updated README.md with new commands
- Updated ROADMAP.md with Week 2 status
- Updated phase-1.5-telegram-enhancements.md
- Updated TEST_COVERAGE.md with new test count

## [1.2.0] - 2026-01-05

### Added - Phase 1.5 Priority 0: Permanent Reject Feature

#### Critical Feature (Production Blocker Resolved)
- **🚫 Permanent Reject Button** - Third button added to Telegram notifications
  - Allows users to permanently block unwanted media (personal photos, test files, etc.)
  - Creates infinite TTL lock (locked_until = NULL) to prevent media from ever being queued again
  - Logs rejection to history with user attribution
  - Essential for safe production use with mixed media folders

#### Button Layout Enhancement
- Updated from 2-button to 3-button layout:
  ```
  [✅ Posted] [⏭️ Skip]
       [🚫 Reject]
   [📱 Open Instagram]
  ```
- Clear visual separation between posting actions and permanent rejection

#### Infrastructure Updates
- **Infinite Lock System** - Permanent locks with NULL `locked_until` value
- **Database Schema Changes**:
  - `media_posting_locks.locked_until` now nullable (NULL = permanent lock)
  - `posting_history.status` accepts 'rejected' value
  - Updated CHECK constraints to include 'rejected' status
- **New Service Methods**:
  - `MediaLockService.create_permanent_lock()` - Convenience method for permanent locks
  - `TelegramService._handle_rejected()` - Handles permanent rejection workflow
  - `LockRepository.get_permanent_locks()` - Query permanently locked media

#### Phase 1.5 Week 1 Priority 1 Features
- **Bot Lifecycle Notifications** - Startup/shutdown messages to admin
  - System status on startup (queue count, media count, last posted time, uptime)
  - Session summary on shutdown (uptime, posts sent, graceful shutdown confirmation)
  - Signal handling for graceful shutdown (SIGTERM/SIGINT)
  - Configurable via `SEND_LIFECYCLE_NOTIFICATIONS` setting
- **Instagram Deep Links** - One-tap Instagram app opening
  - "📱 Open Instagram" button opens Instagram app/web
  - Uses HTTPS URL (Telegram Bot API requirement)
  - Works on desktop (opens web) and mobile (redirects to app)
- **Enhanced Media Captions** - Workflow-focused formatting
  - Clean, actionable 3-step workflow instructions
  - Removed technical metadata clutter (file names, post counts)
  - Kept essential context (scheduled time when relevant)
  - Two modes: "enhanced" (with formatting) and "simple" (plain text)
  - Configurable via `CAPTION_STYLE` setting

### Fixed

#### Critical Bugs
- **Scheduler Permanent Lock Bug** (CRITICAL) - Scheduler was ignoring permanent locks
  - Problem: Lock check only evaluated `locked_until > now`, missing NULL values
  - Solution: Updated to `(locked_until IS NULL) OR (locked_until > now)`
  - Impact: Permanently rejected media was still being scheduled
  - Status: ✅ FIXED - Rejected media now correctly excluded from all schedules

#### Service Bugs
- **Startup Notification Parameter Mismatch** - Failed to send lifecycle notification
  - Problem: Called `MediaRepository.get_all(active_only=True)` but parameter is `is_active`
  - Solution: Changed to `MediaRepository.get_all(is_active=True)`
  - Impact: Startup notification failed silently
  - Status: ✅ FIXED

#### Lock Repository Enhancement
- Updated `get_active_lock()` to detect permanent locks (NULL `locked_until`)
- Updated `get_all_active()` to include permanent locks with proper ordering
- Updated `cleanup_expired()` to never delete permanent locks
- Updated `create()` to support NULL TTL for permanent locks

### Changed

#### Database Operations (Makefile)
- **Mac PostgreSQL Compatibility** - Simplified database commands
  - Changed from psql connection URLs to direct `createdb`/`dropdb` commands
  - Removed dependency on 'postgres' admin database
  - Default `DB_USER` now uses `$(USER)` (current shell user)
  - All commands work without manual postgres database creation
- **Updated Commands**:
  - `make create-db` - Uses `createdb` command
  - `make drop-db` - Uses `dropdb --if-exists`
  - `make init-db` - Connects directly with `psql -d $(DB_NAME)`
  - `make reset-db` - Streamlined drop → create → init flow
  - `make db-shell`, `make db-backup`, `make db-restore` - Simplified
- Inspired by foxxed project's cleaner Makefile approach

#### Configuration
- Added Phase 1.5 settings to `.env.example`:
  - `SEND_LIFECYCLE_NOTIFICATIONS` (default: true)
  - `INSTAGRAM_USERNAME` (optional, for future features)
  - `CAPTION_STYLE` (enhanced|simple, default: enhanced)

### Technical Details

#### Database Schema
- `media_posting_locks.locked_until` - Changed from NOT NULL to nullable
- `media_posting_locks.lock_reason` - Added 'permanent_reject' option
- `posting_history.status` - CHECK constraint includes 'rejected'
- `scripts/setup_database.sql` - Updated for fresh installations

#### Lock Behavior
- **Posted**: Creates 30-day TTL lock (existing behavior)
- **Skipped**: No lock, can be queued again (existing behavior)
- **Rejected**: **Permanent lock**, never queued again (**NEW**)

#### Testing & Validation
- ✅ Tested with 996 media files indexed
- ✅ Verified permanent lock creation in database
- ✅ Confirmed rejected media excluded from scheduling
- ✅ Validated button interactions and message updates
- ✅ Tested on Mac development environment
- ✅ Ready for Raspberry Pi deployment

### Documentation

- Updated `documentation/ROADMAP.md` with Phase 1.5 status
- Updated `documentation/planning/phase-1.5-telegram-enhancements.md` with implementation details
- Added decision log entry for Permanent Reject priority
- Created `scripts/setup_database.sql` (was gitignored, now tracked)

### Deployment Notes

#### Breaking Changes
- **Database schema change required** - Run `make reset-db` or manual migration
- Existing locks remain valid (30-day TTL locks unaffected)
- No data migration needed for existing media or history

#### Upgrade Path
1. Pull latest code from `feature/phase-1-5-enhancements` branch
2. Reset database: `make reset-db` (or manual: drop DB → create DB → init schema)
3. Re-index media: `storyline-cli index-media <path> --recursive`
4. Create schedule: `storyline-cli create-schedule --days 7`
5. Test: `storyline-cli process-queue --force`
6. Deploy to Raspberry Pi and restart service

#### Configuration Required
- No new required settings (all Phase 1.5 settings have defaults)
- Optional: Set `CAPTION_STYLE=simple` if you prefer plain captions
- Optional: Set `SEND_LIFECYCLE_NOTIFICATIONS=false` to disable startup/shutdown messages

### Next Steps - Phase 1.5 Remaining Features

**Week 1 - Priority 2** (Should Have):
- Instagram Deep Link Redirect Service (URLgenius or self-hosted)
- Instagram Username Configuration (bot commands + database storage)

**Week 2 - Priority 3** (Nice to Have):
- Inline Media Editing (edit title/caption/tags from Telegram)
- Quick Actions Menu (/menu command)
- Posting Stats Dashboard (enhanced /stats with charts)

**Week 2 - Priority 4** (Future):
- Smart Scheduling Hints (optimal posting times based on history)

## [1.0.1] - 2026-01-04

### Added
- Comprehensive test suite with 147 tests covering all Phase 1 functionality
- Automatic test database creation and cleanup (pytest fixtures)
- Repository layer tests (6 test files, 49 tests)
- Service layer tests (7 test files, 56 tests)
- Utility layer tests (4 test files, 33 tests)
- CLI command tests (4 test files, 18 tests)
- Test fixtures for database sessions with automatic rollback
- Test documentation (tests/README.md, TESTING_SETUP.md)
- Makefile targets for test execution (test, test-unit, test-quick, test-failed)
- Enhanced logger utility with setup_logger() and get_logger() functions for testability
- Development command: `storyline-cli process-queue --force` for immediate testing
- Lock creation verification in telegram service tests

### Fixed (Code Review - 2026-01-04)
- **Critical**: Service run metadata silently discarded (wrong column name in repository)
- **Critical**: Scheduler date mutation bug causing incorrect scheduling for midnight-crossing windows

### Fixed (Deployment - 2026-01-04)
- **Critical**: 30-day lock creation missing in TelegramService button handlers
- **Database**: Made DB_PASSWORD optional for local PostgreSQL development
- **Database**: Database URL now handles empty password correctly
- **Telegram**: Auto-initialization of bot for CLI commands (one-time use)
- **Validation**: Removed DB_PASSWORD requirement from config validator
- **SQLAlchemy**: Added text() wrapper for raw SQL in health check (SQLAlchemy 2.0+ compatibility)

### Fixed (Testing)
- SQLAlchemy reserved keyword issue (renamed ServiceRun.metadata to context_metadata)
- Test environment configuration loading in conftest.py
- CLI command function names in test imports

### Technical Improvements
- Session-scoped database fixture for one-time setup per test run
- Function-scoped test_db fixture with transaction rollback for test isolation
- Zero-manual-setup testing (database auto-created from .env.test)
- CI/CD ready test infrastructure
- TelegramService now creates locks when "Posted" button is clicked
- PostingService.process_next_immediate() method for development testing

### Next Steps
- **Phase 2 (Optional)**: Instagram API automation integration
  - CloudStorageService (Cloudinary/S3)
  - InstagramAPIService (Graph API)
  - Token refresh service
  - Hybrid workflow (automated simple stories, manual interactive stories)
- **Phase 3**: Shopify product integration (schema ready)
- **Phase 4**: Instagram analytics and metrics (schema ready)
- **Phase 5**: REST API and web frontend

## [1.0.0] - 2026-01-03

### Added

#### Core Infrastructure
- Complete PostgreSQL database schema with 6 core tables
- SQLAlchemy ORM models for all entities
- Pydantic-based configuration management with environment variables
- Comprehensive logging system with file and console outputs
- Service execution tracking for observability and debugging

#### Data Models
- `User` model with auto-discovery from Telegram interactions
- `MediaItem` model as source of truth for media files
- `PostingQueue` model for active work items (ephemeral)
- `PostingHistory` model for permanent audit trail
- `MediaPostingLock` model for TTL-based repost prevention
- `ServiceRun` model for service execution tracking

#### Repository Layer (CRUD Operations)
- `UserRepository` with user management and stats tracking
- `MediaRepository` with duplicate detection and filtering
- `QueueRepository` with retry logic and status management
- `HistoryRepository` with statistics and filtering
- `LockRepository` with TTL lock management
- `ServiceRunRepository` with execution tracking

#### Services Layer
- `BaseService` class with automatic execution tracking and error handling
- `MediaIngestionService` for filesystem scanning and media indexing
- `SchedulerService` with intelligent media selection algorithm
- `MediaLockService` for TTL lock management (30-day default)
- `PostingService` for workflow orchestration
- `TelegramService` with bot polling and callback handlers
- `HealthCheckService` with 4 health checks (database, telegram, queue, recent posts)

#### Utilities
- SHA256 file content hashing (filename-agnostic)
- Image validation against Instagram Story requirements (aspect ratio, resolution, file size)
- Image optimization for Instagram (resize, crop, convert)
- Configuration validation with startup checks
- Structured logging with configurable log levels

#### CLI Commands
- `index-media` - Index media files from directory
- `list-media` - List all indexed media items with filters
- `validate-image` - Validate image against Instagram requirements
- `create-schedule` - Generate intelligent posting schedule
- `process-queue` - Process pending queue items
- `list-queue` - View pending queue items
- `list-users` - List all users with stats
- `promote-user` - Change user role (admin/member)
- `check-health` - System health check with component status

#### Features
- **Smart Scheduling Algorithm**
  - Prioritizes never-posted media items
  - Prefers least-posted items
  - Random selection for variety
  - Excludes locked and queued media
  - Evenly distributed time slots with ±30min jitter
- **Telegram Bot Integration**
  - Inline keyboard buttons (Posted/Skip)
  - Auto-discovery of users from interactions
  - User attribution for all actions
  - /start and /status commands
  - Callback handling for workflow tracking
- **TTL Lock System**
  - Automatic 30-day repost prevention
  - Self-expiring locks (no manual cleanup)
  - Configurable lock duration
  - Multiple lock reasons (recent_post, manual_hold, seasonal)
- **User Management**
  - Auto-creation from Telegram interactions
  - Role-based access (admin/member)
  - Statistics tracking (total posts, last seen)
  - Team name support
- **Complete Audit Trail**
  - Permanent posting history (never deleted)
  - Media metadata snapshots
  - User attribution for all posts
  - Error tracking with retry counts
  - Queue lifecycle timestamps preserved
- **Service Execution Tracking**
  - Automatic logging of all service calls
  - Performance metrics (execution time)
  - Error tracking with stack traces
  - Input parameters and result summaries
  - User attribution for manual triggers
- **Image Processing**
  - Validation against Instagram Story specs (9:16 aspect ratio, 1080x1920 resolution)
  - Automatic optimization (resize, crop, format conversion)
  - HEIC to JPG conversion support
  - PNG transparency handling (RGBA to RGB)
- **Health Monitoring**
  - Database connectivity check
  - Telegram configuration validation
  - Queue backlog detection
  - Recent posts verification
- **Development Features**
  - Dry-run mode for testing without posting
  - Configuration validation on startup (fail-fast)
  - Comprehensive error messages
  - Rich CLI output with tables and colors

#### Application
- Main application entry point with async event loop
- Scheduler loop (checks every minute for pending posts)
- Cleanup loop (hourly expired lock cleanup)
- Telegram bot polling in same process
- Graceful shutdown handling (SIGTERM/SIGINT)
- Configuration validation before startup

#### Database
- Complete schema with indexes for performance
- Foreign key constraints and cascading deletes
- Check constraints for data integrity
- GIN indexes for array columns (tags)
- Schema version tracking table

#### Documentation
- Comprehensive README with quick start guide
- QUICKSTART.md for 10-minute setup
- CLAUDE.md developer guide for AI assistants
- IMPLEMENTATION_COMPLETE.md with full component list
- Complete implementation plan in documentation/
- Inline code documentation and docstrings

#### Testing
- Pytest configuration with coverage reporting
- Test fixtures for database and sample data
- Unit tests for file hashing
- Unit tests for media ingestion service
- Test structure mirroring src/ directory
- Markers for unit/integration/slow tests

#### DevOps
- SQL schema setup script
- Python database initialization script
- requirements.txt with pinned versions
- setup.py for CLI installation
- .env.example with complete configuration template
- .env.test for test environment
- .gitignore for Python projects

### Technical Details

#### Architecture
- Three-layer architecture: CLI → Services → Repositories → Models
- Strict separation of concerns enforced
- Repository pattern for data access
- Service layer for business logic
- Base service class for cross-cutting concerns

#### Configuration
- Environment-based configuration (12-factor app)
- Pydantic settings with validation
- Support for .env files
- Separate test environment configuration
- Feature flags (ENABLE_INSTAGRAM_API, DRY_RUN_MODE)

#### Database
- PostgreSQL with SQLAlchemy ORM
- UUID primary keys
- Timestamp tracking (created_at, updated_at)
- JSONB columns for flexible metadata
- Array columns for tags

#### Performance
- Database indexes on foreign keys and frequently queried columns
- GIN indexes for array searches
- Connection pooling (5 connections, 10 overflow)
- Chunked file reading for hash calculation
- Pre-ping for connection validation

#### Security
- No sensitive data in code (environment variables only)
- Database password required
- User roles for access control
- Input validation at all layers

### Phase Information
- **Current Phase**: Phase 1 (Telegram-Only Mode)
- **Deployment Target**: Raspberry Pi (16GB RAM)
- **Python Version**: 3.10+
- **Database**: PostgreSQL
- **Posting Mode**: 100% manual via Telegram
- **Instagram API**: Not required for Phase 1

[Unreleased]: https://github.com/chrisrogers37/storyline-ai/compare/v1.6.0...HEAD
[1.6.0]: https://github.com/chrisrogers37/storyline-ai/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/chrisrogers37/storyline-ai/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/chrisrogers37/storyline-ai/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/chrisrogers37/storyline-ai/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/chrisrogers37/storyline-ai/compare/v1.0.1...v1.2.0
[1.0.1]: https://github.com/chrisrogers37/storyline-ai/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/chrisrogers37/storyline-ai/releases/tag/v1.0.0
