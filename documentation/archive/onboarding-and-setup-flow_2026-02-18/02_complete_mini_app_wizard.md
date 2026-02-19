# Phase 02: Complete the Mini App Onboarding Wizard

**Status:** 🔧 IN PROGRESS
**Started:** 2026-02-19

## Challenge Round Corrections

1. **Step 1 (STRING_SETTINGS) — SKIP**: Phase 01 already added `TEXT_SETTINGS` with identical content. No work needed.
2. **Step 3 media_sync changes — SKIP**: Phase 01 already added `telegram_chat_id` param to `sync()` and `_create_provider()`.
3. **Test 5e (STRING_SETTINGS tests) — SKIP**: Phase 01 already added `TestSettingsServiceMediaSource` class.
4. **goToStep fire-and-forget init call — REMOVED**: `/init` is read-only, doesn't save step. Backend `set_onboarding_step()` calls in Step 6 handle resume.
5. **Empty folder button disable — REMOVED**: Over-engineering for rare case. Indexing returns `new: 0` which is self-explanatory.
6. **`complete` redundant media_source_type — REMOVED**: Already set during folder validation. Only `enable_instagram_api` and `media_sync_enabled` needed.
7. **`_get_setup_state` missing `onboarding_step` — ADDED**: Plan Step 4 return dict now includes `onboarding_step`.

## 1. Header

| Field | Value |
|---|---|
| **PR Title** | `feat: complete onboarding wizard - folder save, indexing, skip steps` |
| **Risk Level** | Medium -- touches user-facing wizard and persists new settings, but all behind `dry_run_mode=True` |
| **Estimated Effort** | 6-8 hours |
| **Branch Name** | `feature/onboarding-wizard-complete` |

### Files Created
| File | Purpose |
|---|---|
| (none) | No new files needed |

### Files Modified
| File | Purpose |
|---|---|
| `src/api/routes/onboarding.py` | Fix folder save, add indexing endpoint, enrich init response, enhance complete logic |
| `src/api/static/onboarding/index.html` | Add indexing UI step, update skip buttons, update summary, add step-nav on schedule |
| `src/api/static/onboarding/app.js` | Add indexing call, skip tracking, step persistence, resume logic, enriched summary |
| `src/api/static/onboarding/style.css` | Minor additions for indexing result cards and skip badges |
| `src/services/core/settings_service.py` | Add `STRING_SETTINGS` set with `media_source_type` and `media_source_root` |
| `tests/src/api/test_onboarding_routes.py` | New tests for indexing endpoint, folder-save behavior, init enriched response, complete auto-config |
| `CHANGELOG.md` | Entry under `[Unreleased]` |

### Files NOT Modified (owned by other phases)
| File | Owner |
|---|---|
| `src/models/chat_settings.py` | Phase 01 |
| `src/services/core/telegram_commands.py` | Phase 03 |
| `src/services/core/telegram_settings.py` | Phase 04 |

---

## 2. Context

The onboarding wizard currently validates a Google Drive folder but never persists the folder ID to `chat_settings`. When the user finishes the wizard, no media gets indexed and none of the dependent settings (`media_source_type`, `media_sync_enabled`, `enable_instagram_api`) are auto-configured. This means a user who completes the wizard still has a non-functional system. This phase closes that gap.

**Prerequisite**: Phase 01 must already be merged. Phase 01 adds two columns to `chat_settings`:
- `media_source_type VARCHAR(50) DEFAULT 'local'`
- `media_source_root TEXT DEFAULT NULL`

Without those columns, the folder-save code in this phase will fail at the database level.

---

## 3. Dependencies

- **Phase 01 (per-chat media source columns)** must be completed and merged before this phase.
  - Migration `017_chat_settings_media_source.sql` (or whatever number Phase 01 uses) adds `media_source_type` and `media_source_root` to `chat_settings`.
  - The `ChatSettings` model must already include these two columns.
  - The `ChatSettingsRepository.update()` method already handles arbitrary `**kwargs` via `setattr()`, so no repository changes are needed.

---

## 4. Detailed Implementation Plan

### Step 1: Add `STRING_SETTINGS` to `SettingsService`

**File**: `/Users/chris/Projects/storyline-ai/src/services/core/settings_service.py`

**Why**: The `update_setting` method currently rejects any setting not in `TOGGLEABLE_SETTINGS | NUMERIC_SETTINGS`. The onboarding endpoint should use `update_setting` for consistency and audit tracking rather than bypassing to the repository. Adding `STRING_SETTINGS` follows the existing pattern.

**Current code (lines 19-26)**:
```python
TOGGLEABLE_SETTINGS = {
    "dry_run_mode",
    "enable_instagram_api",
    "is_paused",
    "show_verbose_notifications",
    "media_sync_enabled",
}
NUMERIC_SETTINGS = {"posts_per_day", "posting_hours_start", "posting_hours_end"}
```

**New code (insert after line 26)**:
```python
STRING_SETTINGS = {"media_source_type", "media_source_root"}
```

**Update the validation check on line 132**:

Change:
```python
if setting_name not in TOGGLEABLE_SETTINGS | NUMERIC_SETTINGS:
    raise ValueError(f"Unknown setting: {setting_name}")
```

To:
```python
if setting_name not in TOGGLEABLE_SETTINGS | NUMERIC_SETTINGS | STRING_SETTINGS:
    raise ValueError(f"Unknown setting: {setting_name}")
```

**Add validation for string settings** inside `update_setting`, after the numeric validation block (after line 156):
```python
elif setting_name == "media_source_type":
    value = str(value)
    allowed_types = {"local", "google_drive"}
    if value not in allowed_types:
        raise ValueError(
            f"media_source_type must be one of: {', '.join(sorted(allowed_types))}"
        )
elif setting_name == "media_source_root":
    value = str(value) if value else ""
```

This keeps all setting modifications flowing through the same audited path.

---

### Step 2: Fix `POST /api/onboarding/media-folder` to Save Folder ID

**File**: `/Users/chris/Projects/storyline-ai/src/api/routes/onboarding.py`

**Current code (lines 221-227)**:
```python
    # TODO: Store folder_id in chat_settings when media_source_root column exists

    return {
        "folder_id": folder_id,
        "file_count": file_count,
        "categories": sorted(categories),
    }
```

**Replacement code**:
```python
    # Save folder config to chat_settings
    settings_service = SettingsService()
    try:
        settings_service.update_setting(
            request.chat_id, "media_source_root", folder_id
        )
        settings_service.update_setting(
            request.chat_id, "media_source_type", "google_drive"
        )
        settings_service.update_setting(
            request.chat_id, "media_sync_enabled", True
        )
    finally:
        settings_service.close()

    return {
        "folder_id": folder_id,
        "file_count": file_count,
        "categories": sorted(categories),
        "saved": True,
    }
```

Note: `media_sync_enabled` is already in `TOGGLEABLE_SETTINGS` so it goes through `update_setting` without issue. The `SettingsService` import is already at the top of the file.

---

### Step 3: Add `POST /api/onboarding/start-indexing` Endpoint

**File**: `/Users/chris/Projects/storyline-ai/src/api/routes/onboarding.py`

**Add a new request model** (after `CompleteRequest`, around line 49):
```python
class StartIndexingRequest(BaseModel):
    init_data: str
    chat_id: int
```

**Add the endpoint** (after the `onboarding_media_folder` function, before `onboarding_schedule`):
```python
@router.post("/start-indexing")
async def onboarding_start_indexing(request: StartIndexingRequest):
    """Trigger media indexing for this chat's configured folder.

    Requires that media-folder has already been validated and saved.
    Calls MediaSyncService.sync() with the chat's per-tenant config.
    """
    _validate_request(request.init_data, request.chat_id)

    # Load chat settings to get source config
    settings_repo = ChatSettingsRepository()
    try:
        chat_settings = settings_repo.get_or_create(request.chat_id)
        source_type = chat_settings.media_source_type
        source_root = chat_settings.media_source_root
        chat_settings_id = str(chat_settings.id)
    finally:
        settings_repo.close()

    if not source_root:
        raise HTTPException(
            status_code=400,
            detail="No media folder configured. Complete the media folder step first.",
        )

    from src.services.core.media_sync import MediaSyncService

    sync_service = MediaSyncService()
    try:
        result = sync_service.sync(
            source_type=source_type,
            source_root=source_root,
            triggered_by="onboarding",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Media indexing failed during onboarding: {e}")
        raise HTTPException(
            status_code=500,
            detail="Media indexing failed. Please try again or use /sync later.",
        )
    finally:
        sync_service.close()

    return {
        "indexed": True,
        "new": result.new,
        "updated": result.updated,
        "unchanged": result.unchanged,
        "deactivated": result.deactivated,
        "errors": result.errors,
        "total_processed": result.total_processed,
    }
```

**Important note on `telegram_chat_id`**: The current `MediaSyncService._create_provider` method hardcodes `settings.TELEGRAM_CHANNEL_ID` for Google Drive (line 297). For per-tenant indexing, the sync service needs to use the per-chat `telegram_chat_id`. However, modifying `MediaSyncService` is a broader change. Instead, create the provider directly in the onboarding endpoint:

Actually, looking at this more carefully, the `MediaSyncService.sync()` method calls `self._create_provider()` which uses the global `settings.TELEGRAM_CHANNEL_ID`. For per-tenant use during onboarding, we need to pass the `telegram_chat_id` through. Since modifying `MediaSyncService._create_provider` is a simple extension and the method already exists for this purpose, the cleanest approach is to add `telegram_chat_id` as an optional parameter to `sync()`.

**Revised approach** -- also modify `MediaSyncService`:

**File**: `/Users/chris/Projects/storyline-ai/src/services/core/media_sync.py`

Update the `sync` method signature (line 81-86):

```python
def sync(
    self,
    source_type: Optional[str] = None,
    source_root: Optional[str] = None,
    triggered_by: str = "system",
    telegram_chat_id: Optional[int] = None,
) -> SyncResult:
```

Update the `_create_provider` call (line 118):

Change:
```python
provider = self._create_provider(resolved_source_type, resolved_source_root)
```

To:
```python
provider = self._create_provider(
    resolved_source_type, resolved_source_root, telegram_chat_id
)
```

Update `_create_provider` signature and body (line 289):

Change:
```python
def _create_provider(self, source_type: str, source_root: str):
    """Create a MediaSourceProvider based on source type and root."""
    if source_type == "local":
        return MediaSourceFactory.create(source_type, base_path=source_root)
    elif source_type == "google_drive":
        return MediaSourceFactory.create(
            source_type,
            root_folder_id=source_root,
            telegram_chat_id=settings.TELEGRAM_CHANNEL_ID,
        )
    else:
        return MediaSourceFactory.create(source_type)
```

To:
```python
def _create_provider(
    self,
    source_type: str,
    source_root: str,
    telegram_chat_id: Optional[int] = None,
):
    """Create a MediaSourceProvider based on source type and root."""
    if source_type == "local":
        return MediaSourceFactory.create(source_type, base_path=source_root)
    elif source_type == "google_drive":
        resolved_chat_id = telegram_chat_id or settings.TELEGRAM_CHANNEL_ID
        return MediaSourceFactory.create(
            source_type,
            root_folder_id=source_root,
            telegram_chat_id=resolved_chat_id,
        )
    else:
        return MediaSourceFactory.create(source_type)
```

This is backward-compatible: callers that don't pass `telegram_chat_id` get the old behavior.

Then in the onboarding endpoint, call:
```python
result = sync_service.sync(
    source_type=source_type,
    source_root=source_root,
    triggered_by="onboarding",
    telegram_chat_id=request.chat_id,
)
```

---

### Step 4: Update `POST /api/onboarding/init` Response

**File**: `/Users/chris/Projects/storyline-ai/src/api/routes/onboarding.py`

**Current `_get_setup_state` function** (lines 77-122) returns a dict without media folder info.

**Add media folder fields** to the return dict. Insert before the final `return` (after line 118):

```python
        # Check media folder configuration
        media_folder_configured = bool(chat_settings.media_source_root)
        media_folder_id = chat_settings.media_source_root

        # Check if media has been indexed
        media_count = 0
        media_indexed = False
        if media_folder_configured:
            from src.repositories.media_repository import MediaRepository

            media_repo = MediaRepository()
            try:
                items = media_repo.get_all(
                    is_active=True,
                    chat_settings_id=chat_settings_id,
                    limit=1,
                )
                # Use get_active_by_source_type for accurate count
                active_items = media_repo.get_active_by_source_type(
                    "google_drive", chat_settings_id=chat_settings_id
                )
                media_count = len(active_items)
                media_indexed = media_count > 0
            finally:
                media_repo.close()
```

**Update the return dict** (line 110-119). Add three new keys:

```python
        return {
            "instagram_connected": instagram_connected,
            "instagram_username": instagram_username,
            "gdrive_connected": gdrive_connected,
            "gdrive_email": gdrive_email,
            "media_folder_configured": media_folder_configured,
            "media_folder_id": media_folder_id,
            "media_indexed": media_indexed,
            "media_count": media_count,
            "posts_per_day": chat_settings.posts_per_day,
            "posting_hours_start": chat_settings.posting_hours_start,
            "posting_hours_end": chat_settings.posting_hours_end,
            "onboarding_completed": chat_settings.onboarding_completed,
            "onboarding_step": chat_settings.onboarding_step,
        }
```

Note: accessing `chat_settings.media_source_root` and `chat_settings.media_source_type` requires Phase 01 columns to exist. The `media_folder_configured` check avoids a heavy query when no folder is set.

---

### Step 5: Update `POST /api/onboarding/complete` to Auto-Configure

**File**: `/Users/chris/Projects/storyline-ai/src/api/routes/onboarding.py`

**Current code (lines 258-292)**: Simply calls `complete_onboarding` and optionally creates a schedule.

**Replace the body** of `onboarding_complete`:

```python
@router.post("/complete")
async def onboarding_complete(request: CompleteRequest):
    """Mark onboarding as finished, auto-configure dependent settings."""
    _validate_request(request.init_data, request.chat_id)

    settings_service = SettingsService()
    try:
        # Auto-configure dependent settings based on what was connected
        setup_state = _get_setup_state(request.chat_id)

        if setup_state["instagram_connected"]:
            settings_service.update_setting(
                request.chat_id, "enable_instagram_api", True
            )

        if setup_state.get("media_folder_configured"):
            settings_service.update_setting(
                request.chat_id, "media_sync_enabled", True
            )
            settings_service.update_setting(
                request.chat_id, "media_source_type", "google_drive"
            )

        # NOTE: dry_run_mode stays True. User flips it manually later.

        settings_service.complete_onboarding(request.chat_id)
    finally:
        settings_service.close()

    result = {"onboarding_completed": True, "schedule_created": False}

    if request.create_schedule:
        from src.services.core.scheduler import SchedulerService

        scheduler = SchedulerService()
        try:
            schedule_result = scheduler.create_schedule(
                days=request.schedule_days,
                telegram_chat_id=request.chat_id,
            )
            result["schedule_created"] = True
            result["schedule_summary"] = {
                "scheduled": schedule_result.get("scheduled", 0),
                "total_slots": schedule_result.get("total_slots", 0),
                "days": request.schedule_days,
            }
        except Exception as e:
            logger.error(f"Failed to create schedule during onboarding: {e}")
            result["schedule_error"] = str(e)
        finally:
            scheduler.close()

    return result
```

Key behavior: `enable_instagram_api` is set to `True` only if Instagram was actually connected. `media_sync_enabled` is re-confirmed. `dry_run_mode` is NEVER changed here.

---

### Step 6: Update Onboarding Step Tracking in Endpoints

Each endpoint that advances the wizard should save the `onboarding_step` value.

**File**: `/Users/chris/Projects/storyline-ai/src/api/routes/onboarding.py`

In `onboarding_init`, after fetching setup state, save the step:
```python
# At the start of the wizard, set the onboarding_step if not completed
if not setup_state.get("onboarding_completed"):
    settings_service = SettingsService()
    try:
        settings_service.set_onboarding_step(request.chat_id, "welcome")
    finally:
        settings_service.close()
```

In `onboarding_media_folder`, after saving folder settings, add:
```python
    settings_service.set_onboarding_step(request.chat_id, "media_folder")
```
(This `settings_service` instance is the same one used to save the folder settings above, so put it before the `finally: settings_service.close()` block.)

In `onboarding_start_indexing`, after sync completes, save step:
```python
    # Update onboarding step
    step_service = SettingsService()
    try:
        step_service.set_onboarding_step(request.chat_id, "indexing")
    finally:
        step_service.close()
```

In `onboarding_schedule`, after saving schedule settings, add:
```python
    settings_service.set_onboarding_step(request.chat_id, "schedule")
```
(Reuse the existing `settings_service` instance before `finally`.)

---

### Step 7: Update Frontend HTML

**File**: `/Users/chris/Projects/storyline-ai/src/api/static/onboarding/index.html`

#### 7a. Update the Welcome Step to show 5 steps

Replace the step-list (lines 18-23):
```html
                <div class="step-list">
                    <div class="step-item"><span class="step-num">1</span> Connect Instagram</div>
                    <div class="step-item"><span class="step-num">2</span> Connect Google Drive</div>
                    <div class="step-item"><span class="step-num">3</span> Pick media folder</div>
                    <div class="step-item"><span class="step-num">4</span> Index your media</div>
                    <div class="step-item"><span class="step-num">5</span> Set your schedule</div>
                </div>
```

#### 7b. Update progress bar percentages

With 7 steps (welcome, instagram, gdrive, media-folder, indexing, schedule, summary), the progress percentages become:
- welcome: `14%`
- instagram: `28%`
- gdrive: `43%`
- media-folder: `57%`
- indexing: `71%`
- schedule: `86%`
- summary: `100%`

Update each `<div class="progress-fill" style="width: XX%">` accordingly in each step.

#### 7c. Add Indexing step (new HTML)

Insert after the Media Folder step (after line 95, before the Schedule step):

```html
        <!-- Step 4b: Indexing -->
        <div class="step hidden" id="step-indexing">
            <div class="progress-bar"><div class="progress-fill" style="width: 71%"></div></div>
            <div class="step-content">
                <h2>Index Media</h2>
                <p class="subtitle">Import your media files into Storyline so they can be scheduled.</p>

                <div id="indexing-preview" class="result-card">
                    <div class="result-row"><strong>Files found:</strong> <span id="indexing-file-count">0</span></div>
                    <div class="result-row"><strong>Categories:</strong> <span id="indexing-categories">-</span></div>
                </div>

                <button class="btn btn-primary" id="btn-start-indexing" onclick="App.startIndexing()">
                    Index Files Now
                </button>

                <div id="indexing-progress" class="polling-indicator hidden">
                    <div class="spinner"></div>
                    <span>Indexing media files...</span>
                </div>

                <div id="indexing-result" class="hidden">
                    <div class="result-card result-success">
                        <div class="result-row"><strong>New files indexed:</strong> <span id="indexing-new-count">0</span></div>
                        <div class="result-row"><strong>Total processed:</strong> <span id="indexing-total-count">0</span></div>
                        <div id="indexing-errors" class="hidden">
                            <div class="result-row error-text"><strong>Errors:</strong> <span id="indexing-error-count">0</span></div>
                        </div>
                    </div>
                </div>

                <div id="indexing-error" class="error-text hidden"></div>

                <div class="step-nav">
                    <button class="btn btn-text" onclick="App.goToStep('schedule')">Skip, I'll index later</button>
                </div>
            </div>
        </div>
```

#### 7d. Update Media Folder step to NOT auto-advance

Remove the auto-advance `setTimeout` from the JS (handled in Step 8 below), and change the behavior so after folder validation succeeds, the user stays on the media-folder step to see results, then clicks "Next" to go to indexing.

Add a "Continue to Indexing" button that appears after validation:

Replace the folder-result section (lines 84-89):
```html
                <div id="folder-result" class="hidden">
                    <div class="result-card">
                        <div class="result-row"><strong>Files found:</strong> <span id="folder-file-count"></span></div>
                        <div class="result-row"><strong>Categories:</strong> <span id="folder-categories"></span></div>
                    </div>
                    <button class="btn btn-primary" onclick="App.goToStep('indexing')">Continue</button>
                </div>
```

#### 7e. Add skip button to schedule step

The schedule step currently has no "Skip" option. Add one at the bottom (after the Continue button, around line 124):

```html
                <div class="step-nav">
                    <button class="btn btn-text" onclick="App.goToStep('summary')">Skip for now</button>
                </div>
```

#### 7f. Update Summary step

Add rows for Media Folder and Indexing status. Replace the summary-card content (lines 135-152):

```html
                <div class="summary-card">
                    <div class="summary-row">
                        <span class="summary-label">Instagram</span>
                        <span class="summary-value" id="summary-instagram">Not connected</span>
                    </div>
                    <div class="summary-row">
                        <span class="summary-label">Google Drive</span>
                        <span class="summary-value" id="summary-gdrive">Not connected</span>
                    </div>
                    <div class="summary-row">
                        <span class="summary-label">Media Folder</span>
                        <span class="summary-value" id="summary-media-folder">Not configured</span>
                    </div>
                    <div class="summary-row">
                        <span class="summary-label">Media Indexed</span>
                        <span class="summary-value" id="summary-media-indexed">No</span>
                    </div>
                    <div class="summary-row">
                        <span class="summary-label">Schedule</span>
                        <span class="summary-value" id="summary-schedule">3 posts/day</span>
                    </div>
                    <div class="summary-row">
                        <span class="summary-label">Posting window</span>
                        <span class="summary-value" id="summary-window">2pm - 2am UTC</span>
                    </div>
                </div>
```

---

### Step 8: Update Frontend JavaScript

**File**: `/Users/chris/Projects/storyline-ai/src/api/static/onboarding/app.js`

#### 8a. Add skip tracking state

Add to the App object state (after line 14):
```javascript
    // Track which steps were completed vs skipped
    skippedSteps: new Set(),
    folderValidation: null,  // Stores folder_id, file_count, categories after validation
```

#### 8b. Update `validateFolder()` to NOT auto-advance

Replace the `validateFolder` method (lines 127-158):

```javascript
    async validateFolder() {
        const urlInput = document.getElementById('folder-url');
        const url = urlInput.value.trim();

        if (!url) return;

        document.getElementById('folder-error').classList.add('hidden');
        document.getElementById('folder-result').classList.add('hidden');

        this._showLoading(true);
        try {
            const response = await this._api('/api/onboarding/media-folder', {
                init_data: this.initData,
                chat_id: this.chatId,
                folder_url: url,
            });

            this.folderValidation = response;

            document.getElementById('folder-file-count').textContent = response.file_count;
            document.getElementById('folder-categories').textContent =
                response.categories.length > 0 ? response.categories.join(', ') : 'None';
            document.getElementById('folder-result').classList.remove('hidden');

            // Also pre-populate the indexing step preview
            document.getElementById('indexing-file-count').textContent = response.file_count;
            document.getElementById('indexing-categories').textContent =
                response.categories.length > 0 ? response.categories.join(', ') : 'None';

            // Update local state
            if (this.setupState) {
                this.setupState.media_folder_configured = true;
                this.setupState.media_folder_id = response.folder_id;
            }
        } catch (err) {
            const errorEl = document.getElementById('folder-error');
            errorEl.textContent = err.message || 'Could not access this folder.';
            errorEl.classList.remove('hidden');
        } finally {
            this._showLoading(false);
        }
    },
```

#### 8c. Add `startIndexing()` method

Add after `validateFolder()`:

```javascript
    /**
     * Trigger media indexing for the configured folder.
     */
    async startIndexing() {
        document.getElementById('indexing-error').classList.add('hidden');
        document.getElementById('indexing-result').classList.add('hidden');
        document.getElementById('indexing-progress').classList.remove('hidden');
        document.getElementById('btn-start-indexing').disabled = true;

        try {
            const response = await this._api('/api/onboarding/start-indexing', {
                init_data: this.initData,
                chat_id: this.chatId,
            });

            // Hide progress, show result
            document.getElementById('indexing-progress').classList.add('hidden');
            document.getElementById('indexing-new-count').textContent = response.new;
            document.getElementById('indexing-total-count').textContent = response.total_processed;

            if (response.errors > 0) {
                document.getElementById('indexing-error-count').textContent = response.errors;
                document.getElementById('indexing-errors').classList.remove('hidden');
            }

            document.getElementById('indexing-result').classList.remove('hidden');

            // Update local state
            if (this.setupState) {
                this.setupState.media_indexed = true;
                this.setupState.media_count = response.new;
            }

            // Auto-advance to schedule step after short delay
            setTimeout(() => this.goToStep('schedule'), 2000);
        } catch (err) {
            document.getElementById('indexing-progress').classList.add('hidden');
            const errorEl = document.getElementById('indexing-error');
            errorEl.textContent = err.message || 'Indexing failed. You can try /sync later.';
            errorEl.classList.remove('hidden');
            document.getElementById('btn-start-indexing').disabled = false;
        }
    },
```

#### 8d. Update `goToStep()` to track skips and persist step

Replace the `goToStep` method (lines 72-94):

```javascript
    goToStep(stepName) {
        // Track skip if moving past a step that wasn't completed
        const stepOrder = ['welcome', 'instagram', 'gdrive', 'media-folder', 'indexing', 'schedule', 'summary'];
        const currentIdx = stepOrder.indexOf(this._currentStep);
        const targetIdx = stepOrder.indexOf(stepName);

        // If jumping forward past intermediate steps, mark them as skipped
        if (targetIdx > currentIdx + 1) {
            for (let i = currentIdx + 1; i < targetIdx; i++) {
                this.skippedSteps.add(stepOrder[i]);
            }
        }

        this._currentStep = stepName;

        // Hide all steps
        document.querySelectorAll('.step').forEach(s => s.classList.add('hidden'));

        // Show target step
        const step = document.getElementById('step-' + stepName);
        if (step) {
            step.classList.remove('hidden');
        }

        // Update status indicators from current state
        if (this.setupState) {
            this._updateStatusIndicators();
        }

        // If going to summary, populate it
        if (stepName === 'summary') {
            this._populateSummary();
        }

        // If going to indexing, update the preview from folder validation
        if (stepName === 'indexing' && this.folderValidation) {
            document.getElementById('indexing-file-count').textContent =
                this.folderValidation.file_count;
            document.getElementById('indexing-categories').textContent =
                this.folderValidation.categories.length > 0
                    ? this.folderValidation.categories.join(', ')
                    : 'None';
            // Update button text with file count
            document.getElementById('btn-start-indexing').textContent =
                'Index ' + this.folderValidation.file_count + ' Files Now';
        }

        // Stop any active polling when navigating away
        this._stopPolling();

        // Persist step to backend (fire-and-forget)
        if (stepName !== 'summary' && stepName !== 'welcome') {
            this._api('/api/onboarding/init', {
                init_data: this.initData,
                chat_id: this.chatId,
            }).catch(() => {});  // Ignore errors on step tracking
        }
    },
```

Add `_currentStep: 'welcome',` to the App state at the top (after line 14).

#### 8e. Update `_resumeFromState()` to use enriched state

Replace the `_resumeFromState` method (lines 236-255):

```javascript
    _resumeFromState() {
        if (!this.setupState) {
            this.goToStep('welcome');
            return;
        }

        if (this.setupState.onboarding_completed) {
            this.goToStep('summary');
            return;
        }

        // Update schedule defaults from saved state
        this.schedule.postsPerDay = this.setupState.posts_per_day || 3;
        this.schedule.postingHoursStart = this.setupState.posting_hours_start || 14;
        this.schedule.postingHoursEnd = this.setupState.posting_hours_end || 2;

        // Resume from saved step if available
        const step = this.setupState.onboarding_step;
        if (step && document.getElementById('step-' + step)) {
            this.goToStep(step);
            return;
        }

        // Default: start from the beginning
        this.goToStep('welcome');
    },
```

#### 8f. Update `_populateSummary()` with new fields

Replace the `_populateSummary` method (lines 287-302):

```javascript
    _populateSummary() {
        const s = this.setupState || {};

        document.getElementById('summary-instagram').textContent =
            s.instagram_connected ? '@' + (s.instagram_username || 'connected') : 'Skipped';

        document.getElementById('summary-gdrive').textContent =
            s.gdrive_connected ? s.gdrive_email || 'Connected' : 'Skipped';

        document.getElementById('summary-media-folder').textContent =
            s.media_folder_configured ? 'Configured' : 'Skipped';

        document.getElementById('summary-media-indexed').textContent =
            s.media_indexed ? s.media_count + ' files' : 'Skipped';

        document.getElementById('summary-schedule').textContent =
            this.schedule.postsPerDay + ' posts/day';

        document.getElementById('summary-window').textContent =
            this._formatHour(this.schedule.postingHoursStart) + ' - ' +
            this._formatHour(this.schedule.postingHoursEnd) + ' UTC';
    },
```

#### 8g. Update `_updateStatusIndicators()` to handle media folder

Add after the Google Drive status update (after line 281):

```javascript
        // Media folder (if step exists)
        if (s.media_folder_configured) {
            const folderUrlInput = document.getElementById('folder-url');
            if (folderUrlInput && s.media_folder_id) {
                folderUrlInput.value = 'https://drive.google.com/drive/folders/' + s.media_folder_id;
            }
        }
```

---

### Step 9: Minor CSS Additions

**File**: `/Users/chris/Projects/storyline-ai/src/api/static/onboarding/style.css`

Add at the end of the file:

```css
/* Indexing result success indicator */
.result-success {
    border-left: 3px solid #22c55e;
}

/* Summary skipped items */
.summary-value.skipped {
    color: var(--tg-theme-hint-color);
    font-style: italic;
}
```

---

## 5. Test Plan

### New Tests to Add

**File**: `/Users/chris/Projects/storyline-ai/tests/src/api/test_onboarding_routes.py`

#### 5a. Test that `media-folder` now saves settings

```python
@pytest.mark.unit
class TestOnboardingMediaFolderSave:
    """Test that media-folder endpoint saves folder config to chat_settings."""

    def test_valid_folder_saves_source_config(self, client):
        """After validating folder, media_source_root and media_source_type are saved."""
        mock_files = [
            {"name": "a.jpg", "category": "memes"},
        ]

        with (
            _mock_validate(),
            patch(
                "src.services.integrations.google_drive.GoogleDriveService"
            ) as MockGDrive,
            patch("src.api.routes.onboarding.SettingsService") as MockSettings,
        ):
            mock_provider = Mock()
            mock_provider.list_files.return_value = mock_files
            MockGDrive.return_value.get_provider_for_chat.return_value = mock_provider
            MockGDrive.return_value.close = Mock()
            MockSettings.return_value.close = Mock()

            response = client.post(
                "/api/onboarding/media-folder",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "folder_url": "https://drive.google.com/drive/folders/abc123",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["saved"] is True

        # Verify settings were saved
        mock_svc = MockSettings.return_value
        calls = mock_svc.update_setting.call_args_list
        setting_names = [c.args[1] for c in calls]
        assert "media_source_root" in setting_names
        assert "media_source_type" in setting_names
        assert "media_sync_enabled" in setting_names
```

#### 5b. Test the new `start-indexing` endpoint

```python
@pytest.mark.unit
class TestOnboardingStartIndexing:
    """Test POST /api/onboarding/start-indexing."""

    def test_indexing_runs_sync(self, client):
        """Start indexing triggers MediaSyncService.sync() with chat config."""
        mock_settings = Mock(
            id=uuid4(),
            media_source_type="google_drive",
            media_source_root="abc123",
        )
        mock_sync_result = Mock(
            new=42,
            updated=0,
            unchanged=0,
            deactivated=0,
            errors=0,
            total_processed=42,
        )

        with (
            _mock_validate(),
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch(
                "src.services.core.media_sync.MediaSyncService"
            ) as MockSync,
        ):
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.close = Mock()
            MockSync.return_value.sync.return_value = mock_sync_result
            MockSync.return_value.close = Mock()

            response = client.post(
                "/api/onboarding/start-indexing",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["indexed"] is True
        assert data["new"] == 42
        assert data["total_processed"] == 42

    def test_indexing_without_folder_returns_400(self, client):
        """Start indexing without a configured folder returns 400."""
        mock_settings = Mock(
            id=uuid4(),
            media_source_type="local",
            media_source_root=None,
        )

        with (
            _mock_validate(),
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
        ):
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.close = Mock()

            response = client.post(
                "/api/onboarding/start-indexing",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 400
        assert "No media folder" in response.json()["detail"]

    def test_indexing_sync_error_returns_500(self, client):
        """MediaSyncService failure returns 500 with user-friendly message."""
        mock_settings = Mock(
            id=uuid4(),
            media_source_type="google_drive",
            media_source_root="abc123",
        )

        with (
            _mock_validate(),
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch(
                "src.services.core.media_sync.MediaSyncService"
            ) as MockSync,
        ):
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.close = Mock()
            MockSync.return_value.sync.side_effect = Exception("Connection timeout")
            MockSync.return_value.close = Mock()

            response = client.post(
                "/api/onboarding/start-indexing",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 500
        assert "failed" in response.json()["detail"].lower()

    def test_indexing_value_error_returns_400(self, client):
        """MediaSyncService ValueError (e.g., unconfigured provider) returns 400."""
        mock_settings = Mock(
            id=uuid4(),
            media_source_type="google_drive",
            media_source_root="abc123",
        )

        with (
            _mock_validate(),
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch(
                "src.services.core.media_sync.MediaSyncService"
            ) as MockSync,
        ):
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.close = Mock()
            MockSync.return_value.sync.side_effect = ValueError("Provider not configured")
            MockSync.return_value.close = Mock()

            response = client.post(
                "/api/onboarding/start-indexing",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        assert response.status_code == 400
```

#### 5c. Test enriched init response

```python
class TestOnboardingInitEnriched:
    """Test that init response includes media folder and indexing state."""

    def test_init_includes_media_folder_fields(self, client):
        """Init response contains media_folder_configured, media_indexed, media_count."""
        mock_settings = Mock(
            id=uuid4(),
            posts_per_day=3,
            posting_hours_start=14,
            posting_hours_end=2,
            onboarding_completed=False,
            onboarding_step="media_folder",
            media_source_root="abc123",
            media_source_type="google_drive",
        )

        with (
            _mock_validate(),
            patch(
                "src.api.routes.onboarding.ChatSettingsRepository"
            ) as MockSettingsRepo,
            patch("src.api.routes.onboarding.TokenRepository") as MockTokenRepo,
            patch("src.api.routes.onboarding.InstagramAccountService") as MockIGService,
            patch("src.repositories.media_repository.MediaRepository") as MockMediaRepo,
        ):
            MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
            MockSettingsRepo.return_value.close = Mock()
            MockTokenRepo.return_value.get_token_for_chat.return_value = None
            MockTokenRepo.return_value.close = Mock()
            MockIGService.return_value.get_active_account.return_value = None
            MockIGService.return_value.close = Mock()
            MockMediaRepo.return_value.get_all.return_value = [Mock()]
            MockMediaRepo.return_value.get_active_by_source_type.return_value = [
                Mock(), Mock(), Mock()
            ]
            MockMediaRepo.return_value.close = Mock()

            response = client.post(
                "/api/onboarding/init",
                json={"init_data": "test", "chat_id": CHAT_ID},
            )

        data = response.json()
        assert data["setup_state"]["media_folder_configured"] is True
        assert data["setup_state"]["media_folder_id"] == "abc123"
        assert data["setup_state"]["media_indexed"] is True
        assert data["setup_state"]["media_count"] == 3
        assert data["setup_state"]["onboarding_step"] == "media_folder"
```

#### 5d. Test complete endpoint auto-configures settings

```python
class TestOnboardingCompleteAutoConfig:
    """Test that complete endpoint auto-configures dependent settings."""

    def test_complete_enables_instagram_when_connected(self, client):
        """When Instagram is connected, complete enables enable_instagram_api."""
        with (
            _mock_validate(),
            patch("src.api.routes.onboarding.SettingsService") as MockSettings,
            patch(
                "src.api.routes.onboarding._get_setup_state",
                return_value={
                    "instagram_connected": True,
                    "media_folder_configured": False,
                },
            ),
        ):
            MockSettings.return_value.close = Mock()

            response = client.post(
                "/api/onboarding/complete",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "create_schedule": False,
                },
            )

        assert response.status_code == 200

        calls = MockSettings.return_value.update_setting.call_args_list
        setting_updates = {c.args[1]: c.args[2] for c in calls}
        assert setting_updates.get("enable_instagram_api") is True

    def test_complete_does_not_disable_dry_run(self, client):
        """Complete NEVER changes dry_run_mode."""
        with (
            _mock_validate(),
            patch("src.api.routes.onboarding.SettingsService") as MockSettings,
            patch(
                "src.api.routes.onboarding._get_setup_state",
                return_value={
                    "instagram_connected": True,
                    "media_folder_configured": True,
                },
            ),
        ):
            MockSettings.return_value.close = Mock()

            client.post(
                "/api/onboarding/complete",
                json={
                    "init_data": "test",
                    "chat_id": CHAT_ID,
                    "create_schedule": False,
                },
            )

        calls = MockSettings.return_value.update_setting.call_args_list
        setting_names = [c.args[1] for c in calls]
        assert "dry_run_mode" not in setting_names
```

#### 5e. Test for `SettingsService` STRING_SETTINGS

**File**: `/Users/chris/Projects/storyline-ai/tests/src/services/test_settings_service.py` (add to existing test file, or create if not exists)

```python
class TestSettingsServiceStringSettings:
    """Test string settings (media_source_type, media_source_root)."""

    def test_update_media_source_type_valid(self, settings_service):
        """Valid media_source_type is accepted."""
        settings_service.settings_repo.get_or_create.return_value = Mock(
            media_source_type="local"
        )
        settings_service.settings_repo.update.return_value = Mock(
            media_source_type="google_drive"
        )

        result = settings_service.update_setting(
            CHAT_ID, "media_source_type", "google_drive"
        )
        assert result.media_source_type == "google_drive"

    def test_update_media_source_type_invalid(self, settings_service):
        """Invalid media_source_type raises ValueError."""
        settings_service.settings_repo.get_or_create.return_value = Mock(
            media_source_type="local"
        )

        with pytest.raises(ValueError, match="media_source_type must be one of"):
            settings_service.update_setting(
                CHAT_ID, "media_source_type", "dropbox"
            )

    def test_update_media_source_root(self, settings_service):
        """media_source_root can be set to a folder ID."""
        settings_service.settings_repo.get_or_create.return_value = Mock(
            media_source_root=None
        )
        settings_service.settings_repo.update.return_value = Mock(
            media_source_root="abc123"
        )

        result = settings_service.update_setting(
            CHAT_ID, "media_source_root", "abc123"
        )
        settings_service.settings_repo.update.assert_called_once()
```

---

## 6. Documentation Updates

### CHANGELOG.md Entry

Add under `## [Unreleased]`:

```markdown
### Added

- **Onboarding media folder persistence** - Wizard now saves Google Drive folder ID to `chat_settings.media_source_root` and sets `media_source_type` to `google_drive` when folder is validated
- **Media indexing from onboarding** - New `/api/onboarding/start-indexing` endpoint triggers a full media sync during wizard; user can choose "Index now" or skip for later
- **Enriched onboarding init response** - `/api/onboarding/init` now returns `media_folder_configured`, `media_folder_id`, `media_indexed`, `media_count`, and `onboarding_step` for proper wizard state resume
- **Auto-configuration on complete** - Completing onboarding auto-enables `enable_instagram_api` (if connected) and `media_sync_enabled` (if folder configured); `dry_run_mode` always stays true
- **Onboarding step tracking** - Each wizard step saves `onboarding_step` to database, enabling resume from where the user left off
- **String settings support** - `SettingsService` now supports `STRING_SETTINGS` (`media_source_type`, `media_source_root`) with validation

### Changed

- **MediaSyncService per-tenant support** - `sync()` and `_create_provider()` now accept optional `telegram_chat_id` parameter for per-tenant Google Drive OAuth credential lookup (backward-compatible, falls back to global `TELEGRAM_CHANNEL_ID`)
- **Onboarding wizard steps** - Updated from 4 to 5 visible steps (added "Index your media"); progress bar percentages adjusted
- **Media folder validation** - No longer auto-advances after 1.5s; shows results and "Continue" button for explicit user control
- **Summary step** - Now shows media folder and indexing status alongside Instagram, Google Drive, and schedule configuration
```

---

## 7. Stress Testing and Edge Cases

### Large Folders (1000+ files)
- The `start-indexing` endpoint calls `MediaSyncService.sync()` which processes files sequentially. For very large folders (5000+ files), this could take 30-60 seconds.
- **Mitigation**: The loading spinner in the UI is shown during the request. The `_api` fetch call has no explicit timeout, so it will wait for the server.
- **Future improvement**: Consider running indexing as a background task with a polling status endpoint. For Phase 02, synchronous is acceptable since most users have < 5000 files.

### Empty Folder (0 files)
- `validateFolder()` returns `file_count: 0`. The UI shows "Files found: 0".
- The indexing step button shows "Index 0 Files Now" -- not useful.
- **Mitigation**: In `goToStep('indexing')`, if `folderValidation.file_count === 0`, disable the "Index Files Now" button and show a hint like "Your folder is empty. Add media files to Google Drive and come back to index."

Add this logic in the `goToStep` method when `stepName === 'indexing'`:
```javascript
        if (stepName === 'indexing') {
            if (this.folderValidation && this.folderValidation.file_count === 0) {
                document.getElementById('btn-start-indexing').disabled = true;
                document.getElementById('btn-start-indexing').textContent = 'No files to index';
            } else if (this.folderValidation) {
                document.getElementById('btn-start-indexing').disabled = false;
                document.getElementById('btn-start-indexing').textContent =
                    'Index ' + this.folderValidation.file_count + ' Files Now';
            }
        }
```

### OAuth Expiry During Wizard
- If Google Drive OAuth token expires while the user is in the wizard (e.g., they started, went away for 30 min, came back), the `media-folder` validation will fail.
- The `GoogleDriveOAuthService` should handle token refresh automatically (it uses `google.oauth2.credentials.Credentials` which auto-refreshes).
- **Mitigation**: The existing error handling catches the exception and shows "Cannot access this folder."
- **Improvement**: Check the specific error and suggest re-connecting Google Drive if it is an auth error.

### Concurrent Sessions
- Two users from the same chat opening the wizard simultaneously: Both will write to the same `chat_settings` row. The last write wins.
- This is acceptable because: (a) settings are idempotent (same folder ID, same schedule), and (b) Telegram groups typically have one admin doing setup.
- No locking needed for Phase 02.

### Folder Accessible But Files Take Long to List
- Google Drive API may be slow for large folder hierarchies. The `provider.list_files()` call in `media-folder` validation is blocking.
- **Mitigation**: The loading overlay is shown. The existing `_showLoading(true)` covers this.

### User Navigates Back After Skipping
- If user skips Instagram, goes to Google Drive, then presses browser back -- the wizard uses `goToStep()` not browser history. There is no browser back handling.
- **Mitigation**: The Telegram WebApp SDK does not support browser back in Mini Apps. This is a non-issue.

### Indexing Called Before Folder Validation
- If someone crafts a direct API call to `/api/onboarding/start-indexing` without first validating a folder, the `media_source_root` check returns 400.
- This is already handled by the `if not source_root` guard.

---

## 8. Verification Checklist

### Automated Checks
```bash
# 1. Lint and format
source venv/bin/activate
ruff check src/ tests/ cli/
ruff format --check src/ tests/ cli/

# 2. Run all tests
pytest

# 3. Run onboarding tests specifically
pytest tests/src/api/test_onboarding_routes.py -v

# 4. Run settings tests
pytest tests/src/services/test_settings_service.py -v
```

### Manual Verification Steps

1. **Pre-requisite**: Phase 01 migration applied (`media_source_type` and `media_source_root` columns exist on `chat_settings`).

2. **Test wizard from scratch**:
   - Open the Mini App from `/start` in a fresh chat
   - Verify welcome page shows 5 steps
   - Connect Instagram (or skip)
   - Connect Google Drive (or skip)
   - Paste a valid folder URL, click Validate
   - Verify folder results appear with file count and categories
   - Click "Continue" to indexing step
   - Verify indexing step shows file count preview
   - Click "Index N Files Now"
   - Verify spinner, then success result
   - Auto-advance to schedule step
   - Configure schedule, click Continue
   - Verify summary shows all configured items
   - Check "Create 7-day schedule now" toggle
   - Click "Finish Setup"
   - Verify Mini App closes

3. **Test skip behavior**:
   - Open wizard, skip Instagram, skip Google Drive, skip media folder
   - Verify schedule step still works
   - Verify summary shows "Skipped" for skipped items

4. **Test resume**:
   - Open wizard, complete Instagram, close Mini App
   - Reopen Mini App
   - Verify wizard resumes at the step after Instagram (or the saved step)

5. **Verify database state** after completion:
   ```sql
   SELECT telegram_chat_id, media_source_type, media_source_root,
          media_sync_enabled, enable_instagram_api, dry_run_mode,
          onboarding_completed, onboarding_step
   FROM chat_settings
   WHERE telegram_chat_id = <your_chat_id>;
   ```
   - `media_source_type` = `google_drive`
   - `media_source_root` = the folder ID
   - `media_sync_enabled` = `true`
   - `enable_instagram_api` = `true` (if Instagram was connected)
   - `dry_run_mode` = `true` (always!)
   - `onboarding_completed` = `true`
   - `onboarding_step` = `NULL`

---

## 9. "What NOT To Do"

1. **DO NOT modify `src/models/chat_settings.py`** -- Phase 01 owns the model changes. This phase assumes the columns already exist.

2. **DO NOT modify `src/services/core/telegram_commands.py`** -- Phase 03 will update the `/sync` command to read per-chat settings. Do not change the Telegram `/sync` handler.

3. **DO NOT modify `src/services/core/telegram_settings.py`** -- Phase 04 handles the Telegram settings UI updates. Do not add media_source settings to the Telegram settings display.

4. **DO NOT set `dry_run_mode = False`** anywhere in the onboarding flow. The user must explicitly disable dry run mode after they are confident the system is configured correctly. The `complete` endpoint must NEVER touch `dry_run_mode`.

5. **DO NOT make steps non-skippable**. Every step except Welcome and Summary must have a skip option. The Instagram step and Google Drive step already have skip buttons. The media folder step and indexing step must also have skip. Schedule should also be skippable.

6. **DO NOT run indexing automatically** when the folder is validated. Indexing should be a separate explicit user action. The user may want to validate folder access without immediately indexing 1000 files.

7. **DO NOT add the migration file** -- Phase 01 handles the migration. This phase only writes Python and JS code that depends on those columns.

8. **DO NOT use `ChatSettingsRepository.update()` directly** for settings changes that should be audited. Use `SettingsService.update_setting()` so all changes flow through `track_execution` and appear in `service_runs`.

9. **DO NOT break backward compatibility** of `MediaSyncService.sync()`. The new `telegram_chat_id` parameter must be optional with a default of `None`, falling back to the global `settings.TELEGRAM_CHANNEL_ID`.

10. **DO NOT poll the `start-indexing` endpoint**. Unlike OAuth (which uses polling because it completes in a separate tab), indexing is a single synchronous request. The frontend should await the response, not poll.

---

### Critical Files for Implementation
- `/Users/chris/Projects/storyline-ai/src/api/routes/onboarding.py` - Core backend: fix folder save, add indexing endpoint, enrich init, update complete
- `/Users/chris/Projects/storyline-ai/src/api/static/onboarding/app.js` - Frontend state machine: indexing flow, skip tracking, resume logic
- `/Users/chris/Projects/storyline-ai/src/services/core/settings_service.py` - Add STRING_SETTINGS for media_source_type/root validation
- `/Users/chris/Projects/storyline-ai/src/services/core/media_sync.py` - Add telegram_chat_id parameter for per-tenant provider creation
- `/Users/chris/Projects/storyline-ai/tests/src/api/test_onboarding_routes.py` - Existing test patterns to follow; all new tests go here