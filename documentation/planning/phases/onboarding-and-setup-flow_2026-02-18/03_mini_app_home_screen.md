# Phase 03: Mini App Home Screen for Returning Users

**PR Title:** `feat: Mini App home screen for returning users with edit-and-return flow`

**Risk Level:** Low

**Estimated Effort:** Medium (2-3 days)

**Branch Name:** `feat/onboarding-phase-03-home-screen`

## Files Summary

| Action | File Path | Description |
|--------|-----------|-------------|
| Modify | `src/services/core/telegram_commands.py` | Always show Mini App button from `/start` |
| Modify | `src/api/routes/onboarding.py` | Expand `_get_setup_state` with queue/history/status fields |
| Modify | `src/api/static/onboarding/index.html` | Add home screen HTML section |
| Modify | `src/api/static/onboarding/app.js` | Add home mode, edit-and-return flow |
| Modify | `src/api/static/onboarding/style.css` | Home screen card styles |
| Modify | `tests/src/services/test_telegram_commands.py` | Update `/start` tests for always-Mini-App behavior |
| Modify | `tests/src/api/test_onboarding_routes.py` | Add tests for expanded init response fields |
| Modify | `CHANGELOG.md` | Add entry under `[Unreleased]` |

---

## 1. Context

The user's vision is that `/start` is the single entry point for the entire Storyline AI experience. Currently, `/start` bifurcates: new users see a Mini App button leading to the onboarding wizard, while returning users see a text-only list of commands. This phase unifies both paths by always opening the Mini App. The Mini App itself decides what to render based on `onboarding_completed`:

- `onboarding_completed = false` -> Wizard (already built in Phase 02)
- `onboarding_completed = true` -> Home screen dashboard with live configuration status and edit shortcuts

This creates a single, visual, touch-friendly entry point that replaces the dated text command list.

---

## 2. Dependencies

- **Phase 01** must be merged. The `chat_settings` model must have `onboarding_step` and `onboarding_completed` columns.
- **Phase 02** must be merged. The onboarding wizard (6-step flow) in `index.html` / `app.js` / `style.css` must be functional. The `/api/onboarding/init` endpoint must return `setup_state` with at minimum: `instagram_connected`, `instagram_username`, `gdrive_connected`, `gdrive_email`, `posts_per_day`, `posting_hours_start`, `posting_hours_end`, `onboarding_completed`.

---

## 3. Detailed Implementation Plan

### Step 1: Update `/start` handler to always show Mini App button

**File:** `/Users/chris/Projects/storyline-ai/src/services/core/telegram_commands.py`

**What changes:** The `handle_start` method currently has an `if/else` branch on `onboarding_done`. Replace this with a single code path that always shows a `WebAppInfo` button, but varies the button text and greeting message.

**Current code (lines 32-84):**

```python
async def handle_start(self, update, context):
    """Handle /start command.

    New users: show onboarding Mini App button.
    Returning users: show dashboard summary.
    """
    user = self.service._get_or_create_user(update.effective_user)
    chat_id = update.effective_chat.id

    # Check onboarding status
    from src.services.core.settings_service import SettingsService

    settings_service = SettingsService()
    try:
        chat_settings = settings_service.get_settings(chat_id)
        onboarding_done = chat_settings.onboarding_completed
    finally:
        settings_service.close()

    if not onboarding_done and settings.OAUTH_REDIRECT_BASE_URL:
        # New user — show setup wizard button
        webapp_url = (
            f"{settings.OAUTH_REDIRECT_BASE_URL}/webapp/onboarding"
            f"?chat_id={chat_id}"
        )
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Open Setup Wizard",
                        web_app=WebAppInfo(url=webapp_url),
                    )
                ]
            ]
        )
        await update.message.reply_text(
            "Welcome to *Storyline AI*\\!\n\n"
            "Let's get you set up\\. Tap the button below to "
            "connect your accounts and configure your posting schedule\\.",
            parse_mode="MarkdownV2",
            reply_markup=keyboard,
        )
    else:
        # Returning user — show dashboard
        await update.message.reply_text(
            "\U0001f44b *Storyline AI Bot*\n\n"
            "Commands:\n"
            "/queue - View upcoming posts\n"
            "/next - Force send next post\n"
            "/status - Check system status\n"
            "/help - Show all commands",
            parse_mode="Markdown",
        )

    # Log interaction
    self.service.interaction_service.log_command(
        user_id=str(user.id),
        command="/start",
        telegram_chat_id=chat_id,
        telegram_message_id=update.message.message_id,
    )
```

**New code (replace lines 32-92):**

```python
async def handle_start(self, update, context):
    """Handle /start command.

    Always opens the Mini App. New users see the onboarding wizard,
    returning users see a dashboard home screen.
    """
    user = self.service._get_or_create_user(update.effective_user)
    chat_id = update.effective_chat.id

    # Check onboarding status
    from src.services.core.settings_service import SettingsService

    settings_service = SettingsService()
    try:
        chat_settings = settings_service.get_settings(chat_id)
        onboarding_done = chat_settings.onboarding_completed
    finally:
        settings_service.close()

    if settings.OAUTH_REDIRECT_BASE_URL:
        # Always show Mini App button — app decides what to render
        webapp_url = (
            f"{settings.OAUTH_REDIRECT_BASE_URL}/webapp/onboarding"
            f"?chat_id={chat_id}"
        )

        if onboarding_done:
            button_text = "Open Storyline"
            message_text = (
                "Welcome back to *Storyline AI*\\!\n\n"
                "Tap the button below to view your dashboard "
                "and manage your settings\\."
            )
        else:
            button_text = "Open Setup Wizard"
            message_text = (
                "Welcome to *Storyline AI*\\!\n\n"
                "Let's get you set up\\. Tap the button below to "
                "connect your accounts and configure your posting schedule\\."
            )

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        button_text,
                        web_app=WebAppInfo(url=webapp_url),
                    )
                ]
            ]
        )
        await update.message.reply_text(
            message_text,
            parse_mode="MarkdownV2",
            reply_markup=keyboard,
        )
    else:
        # Fallback when OAUTH_REDIRECT_BASE_URL not configured
        await update.message.reply_text(
            "\U0001f44b *Storyline AI Bot*\n\n"
            "Commands:\n"
            "/queue - View upcoming posts\n"
            "/next - Force send next post\n"
            "/status - Check system status\n"
            "/help - Show all commands",
            parse_mode="Markdown",
        )

    # Log interaction
    self.service.interaction_service.log_command(
        user_id=str(user.id),
        command="/start",
        telegram_chat_id=chat_id,
        telegram_message_id=update.message.message_id,
    )
```

**Key behavioral changes:**
- When `OAUTH_REDIRECT_BASE_URL` is set (production), returning users now see a Mini App button labeled "Open Storyline" instead of a text command list.
- The text-only fallback only appears when `OAUTH_REDIRECT_BASE_URL` is not configured at all (local dev without the API server).
- The `webapp_url` is identical for both cases -- the Mini App's `app.js` reads `onboarding_completed` from the init response and chooses which view to render.

---

### Step 2: Expand `/api/onboarding/init` response with dashboard data

**File:** `/Users/chris/Projects/storyline-ai/src/api/routes/onboarding.py`

**What changes:** The `_get_setup_state` helper (lines 77-122) needs to return additional fields that the home screen dashboard needs: `is_paused`, `dry_run_mode`, `queue_count`, and `last_post_at`. These come from `ChatSettings` (already fetched), `QueueRepository`, and `HistoryRepository`.

**Current `_get_setup_state` function (lines 77-122):**

```python
def _get_setup_state(telegram_chat_id: int) -> dict:
    """Build the current setup state for a chat."""
    settings_repo = ChatSettingsRepository()
    token_repo = TokenRepository()

    try:
        chat_settings = settings_repo.get_or_create(telegram_chat_id)
        chat_settings_id = str(chat_settings.id)

        # Check Instagram connection
        instagram_connected = False
        instagram_username = None
        account_service = InstagramAccountService()
        try:
            active_account = account_service.get_active_account(telegram_chat_id)
            if active_account:
                instagram_connected = True
                instagram_username = active_account.instagram_username
        finally:
            account_service.close()

        # Check Google Drive connection
        gdrive_connected = False
        gdrive_email = None
        gdrive_token = token_repo.get_token_for_chat(
            "google_drive", "oauth_access", chat_settings_id
        )
        if gdrive_token:
            gdrive_connected = True
            if gdrive_token.token_metadata:
                gdrive_email = gdrive_token.token_metadata.get("email")

        return {
            "instagram_connected": instagram_connected,
            "instagram_username": instagram_username,
            "gdrive_connected": gdrive_connected,
            "gdrive_email": gdrive_email,
            "posts_per_day": chat_settings.posts_per_day,
            "posting_hours_start": chat_settings.posting_hours_start,
            "posting_hours_end": chat_settings.posting_hours_end,
            "onboarding_completed": chat_settings.onboarding_completed,
        }
    finally:
        settings_repo.close()
        token_repo.close()
```

**New `_get_setup_state` function:**

```python
def _get_setup_state(telegram_chat_id: int) -> dict:
    """Build the current setup state for a chat.

    Returns all fields needed by both the onboarding wizard and
    the returning-user home screen dashboard.
    """
    settings_repo = ChatSettingsRepository()
    token_repo = TokenRepository()

    try:
        chat_settings = settings_repo.get_or_create(telegram_chat_id)
        chat_settings_id = str(chat_settings.id)

        # Check Instagram connection
        instagram_connected = False
        instagram_username = None
        account_service = InstagramAccountService()
        try:
            active_account = account_service.get_active_account(telegram_chat_id)
            if active_account:
                instagram_connected = True
                instagram_username = active_account.instagram_username
        finally:
            account_service.close()

        # Check Google Drive connection
        gdrive_connected = False
        gdrive_email = None
        gdrive_token = token_repo.get_token_for_chat(
            "google_drive", "oauth_access", chat_settings_id
        )
        if gdrive_token:
            gdrive_connected = True
            if gdrive_token.token_metadata:
                gdrive_email = gdrive_token.token_metadata.get("email")

        # Dashboard data: queue count and last post time
        queue_count = 0
        last_post_at = None
        try:
            from src.repositories.queue_repository import QueueRepository
            from src.repositories.history_repository import HistoryRepository

            queue_repo = QueueRepository()
            history_repo = HistoryRepository()
            try:
                queue_count = queue_repo.count_pending(
                    chat_settings_id=chat_settings_id
                )
                recent_posts = history_repo.get_recent_posts(
                    hours=720, chat_settings_id=chat_settings_id
                )  # last 30 days
                if recent_posts:
                    last_post_at = recent_posts[0].posted_at.isoformat()
            finally:
                queue_repo.close()
                history_repo.close()
        except Exception:
            # Non-critical — dashboard still renders with defaults
            logger.debug("Failed to fetch queue/history for onboarding init")

        return {
            "instagram_connected": instagram_connected,
            "instagram_username": instagram_username,
            "gdrive_connected": gdrive_connected,
            "gdrive_email": gdrive_email,
            "posts_per_day": chat_settings.posts_per_day,
            "posting_hours_start": chat_settings.posting_hours_start,
            "posting_hours_end": chat_settings.posting_hours_end,
            "onboarding_completed": chat_settings.onboarding_completed,
            "is_paused": chat_settings.is_paused,
            "dry_run_mode": chat_settings.dry_run_mode,
            "queue_count": queue_count,
            "last_post_at": last_post_at,
        }
    finally:
        settings_repo.close()
        token_repo.close()
```

**Key design decisions:**
- `queue_count` and `last_post_at` are fetched inside a try/except because they are non-critical. If the repositories fail, the dashboard still renders with `0` and `null`.
- `last_post_at` uses ISO format string for easy JS parsing. Looks back 30 days (720 hours).
- `is_paused` and `dry_run_mode` come directly from `chat_settings` which is already fetched -- zero additional DB queries for these.
- The `QueueRepository` and `HistoryRepository` imports are local (inside the function) to avoid circular imports and to match the existing pattern used elsewhere in this file (see the `onboarding_complete` endpoint's lazy import of `SchedulerService`).

---

### Step 3: Add home screen HTML section

**File:** `/Users/chris/Projects/storyline-ai/src/api/static/onboarding/index.html`

**What changes:** Insert a new `<div class="step hidden" id="step-home">` section after the `<div id="app">` open tag but before the first wizard step. This section is hidden by default and shown by `app.js` when `onboarding_completed` is true.

**Insert the following HTML immediately after `<div id="app">` (line 11) and before `<!-- Step 1: Welcome -->` (line 12):**

```html
        <!-- Home Screen (returning users) -->
        <div class="step hidden" id="step-home">
            <div class="step-content">
                <h1>Storyline AI</h1>
                <p class="subtitle">Your posting dashboard</p>

                <!-- Instagram card -->
                <div class="home-card" id="home-card-instagram">
                    <div class="home-card-header">
                        <div class="home-card-title">
                            <span class="home-card-icon">&#x1F4F8;</span>
                            <span>Instagram</span>
                        </div>
                        <span class="home-card-badge" id="home-badge-instagram"></span>
                    </div>
                    <div class="home-card-detail" id="home-detail-instagram"></div>
                    <button class="btn btn-card-edit" onclick="App.editSection('instagram')">Edit</button>
                </div>

                <!-- Google Drive card -->
                <div class="home-card" id="home-card-gdrive">
                    <div class="home-card-header">
                        <div class="home-card-title">
                            <span class="home-card-icon">&#x1F4C1;</span>
                            <span>Google Drive</span>
                        </div>
                        <span class="home-card-badge" id="home-badge-gdrive"></span>
                    </div>
                    <div class="home-card-detail" id="home-detail-gdrive"></div>
                    <button class="btn btn-card-edit" onclick="App.editSection('gdrive')">Edit</button>
                </div>

                <!-- Schedule card -->
                <div class="home-card" id="home-card-schedule">
                    <div class="home-card-header">
                        <div class="home-card-title">
                            <span class="home-card-icon">&#x1F4C5;</span>
                            <span>Schedule</span>
                        </div>
                        <span class="home-card-badge" id="home-badge-schedule"></span>
                    </div>
                    <div class="home-card-detail" id="home-detail-schedule"></div>
                    <button class="btn btn-card-edit" onclick="App.editSection('schedule')">Edit</button>
                </div>

                <!-- Queue status card (read-only) -->
                <div class="home-card" id="home-card-queue">
                    <div class="home-card-header">
                        <div class="home-card-title">
                            <span class="home-card-icon">&#x1F4CA;</span>
                            <span>Queue Status</span>
                        </div>
                        <span class="home-card-badge" id="home-badge-queue"></span>
                    </div>
                    <div class="home-card-detail" id="home-detail-queue"></div>
                </div>

                <div class="home-divider"></div>

                <button class="btn btn-secondary" onclick="App.runFullSetup()">Run Full Setup Again</button>
            </div>
        </div>
```

**Also add a "Save & Return" button to each wizard step.** This button is hidden by default and shown only in edit mode. Add the following to each step's `step-content` div (steps: instagram, gdrive, media-folder, schedule), placed after the existing "Skip for now" nav or the main action button:

For **step-instagram** (after the `step-nav` div, around line 47):
```html
                <div class="step-nav-return hidden" id="return-nav-instagram">
                    <button class="btn btn-primary" onclick="App.returnToHome()">Save &amp; Return</button>
                </div>
```

For **step-gdrive** (after the `step-nav` div, around line 70):
```html
                <div class="step-nav-return hidden" id="return-nav-gdrive">
                    <button class="btn btn-primary" onclick="App.returnToHome()">Save &amp; Return</button>
                </div>
```

For **step-media-folder** (after the `step-nav` div, around line 93):
```html
                <div class="step-nav-return hidden" id="return-nav-media-folder">
                    <button class="btn btn-primary" onclick="App.returnToHome()">Save &amp; Return</button>
                </div>
```

For **step-schedule** (replace the existing "Continue" button with a conditional pair):

Change the existing button (line 124):
```html
                <button class="btn btn-primary" id="btn-schedule-next" onclick="App.saveSchedule()">Continue</button>
                <button class="btn btn-primary hidden" id="btn-schedule-return" onclick="App.saveScheduleAndReturn()">Save &amp; Return</button>
```

---

### Step 4: Update `app.js` to handle wizard mode vs home mode

**File:** `/Users/chris/Projects/storyline-ai/src/api/static/onboarding/app.js`

**What changes:** Add a `mode` property (`'wizard'` or `'home'`), a `editingFrom` property (tracks that we're in edit-from-home mode), new methods for the home screen, and modify `_resumeFromState` to route to the home screen for completed users.

**Full replacement for `app.js`:**

```javascript
/**
 * Storyline AI Onboarding Mini App
 *
 * Telegram WebApp SDK integration for guided setup wizard
 * and returning-user home screen dashboard.
 * No framework — vanilla JS with simple state management.
 */

const App = {
    // State
    chatId: null,
    initData: null,
    setupState: null,
    pollInterval: null,
    pollTimeout: null,

    // Mode: 'wizard' (onboarding) or 'home' (returning user dashboard)
    mode: 'wizard',

    // When true, wizard steps show "Save & Return" instead of "Next"/"Skip"
    editingFrom: false,

    // Schedule config (defaults)
    schedule: {
        postsPerDay: 3,
        postingHoursStart: 14,
        postingHoursEnd: 2,
    },

    /**
     * Initialize the Mini App.
     */
    async init() {
        const tg = window.Telegram && window.Telegram.WebApp;
        if (!tg) {
            this._showError('This page must be opened from Telegram.');
            return;
        }

        tg.ready();
        tg.expand();

        // Apply Telegram theme
        this._applyTheme(tg.themeParams);

        // Get initData for API authentication
        this.initData = tg.initData;
        if (!this.initData) {
            this._showError('Missing authentication data. Please reopen from Telegram.');
            return;
        }

        // Get chat_id from URL parameter
        const params = new URLSearchParams(window.location.search);
        this.chatId = parseInt(params.get('chat_id'), 10);
        if (!this.chatId) {
            this._showError('Missing chat context. Please use /start in your Telegram chat.');
            return;
        }

        // Fetch initial state
        try {
            const response = await this._api('/api/onboarding/init', {
                init_data: this.initData,
                chat_id: this.chatId,
            });
            this.setupState = response.setup_state;

            // Resume from where the user left off
            this._resumeFromState();
        } catch (err) {
            this._showError('Failed to load setup state. Please try again.');
        }
    },

    /**
     * Navigate to a step (wizard or home).
     */
    goToStep(stepName) {
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

        // If going to home, populate dashboard cards
        if (stepName === 'home') {
            this._populateHome();
        }

        // Toggle wizard step navigation based on editing mode
        this._updateStepNavVisibility(stepName);

        // Stop any active polling when navigating away
        this._stopPolling();
    },

    // ==================== Home Screen Methods ====================

    /**
     * Populate the home screen dashboard cards from setupState.
     */
    _populateHome() {
        const s = this.setupState || {};

        // Instagram card
        if (s.instagram_connected) {
            this._setHomeBadge('instagram', 'connected', 'Connected');
            this._setHomeDetail('instagram',
                '@' + this._escapeHtml(s.instagram_username || 'unknown'));
        } else {
            this._setHomeBadge('instagram', 'warning', 'Not connected');
            this._setHomeDetail('instagram', 'Tap Edit to connect your account');
        }

        // Google Drive card
        if (s.gdrive_connected) {
            this._setHomeBadge('gdrive', 'connected', 'Connected');
            this._setHomeDetail('gdrive', this._escapeHtml(s.gdrive_email || 'Connected'));
        } else {
            this._setHomeBadge('gdrive', 'warning', 'Not connected');
            this._setHomeDetail('gdrive', 'Tap Edit to connect Google Drive');
        }

        // Schedule card
        const postsPerDay = s.posts_per_day || 3;
        const start = s.posting_hours_start != null ? s.posting_hours_start : 14;
        const end = s.posting_hours_end != null ? s.posting_hours_end : 2;

        if (s.is_paused) {
            this._setHomeBadge('schedule', 'error', 'Paused');
        } else {
            this._setHomeBadge('schedule', 'connected', 'Active');
        }
        this._setHomeDetail('schedule',
            postsPerDay + ' posts/day, ' +
            this._formatHour(start) + ' - ' + this._formatHour(end) + ' UTC' +
            (s.dry_run_mode ? '<br><span class="home-card-tag">Dry run ON</span>' : ''));

        // Queue status card
        const queueCount = s.queue_count || 0;
        if (queueCount > 0) {
            this._setHomeBadge('queue', 'connected', queueCount + ' pending');
        } else {
            this._setHomeBadge('queue', 'neutral', 'Empty');
        }

        let queueDetail = queueCount + ' posts in queue';
        if (s.last_post_at) {
            const lastDate = new Date(s.last_post_at);
            const now = new Date();
            const hoursAgo = Math.floor((now - lastDate) / (1000 * 60 * 60));
            if (hoursAgo < 1) {
                queueDetail += ' \u00B7 Last post: < 1h ago';
            } else if (hoursAgo < 24) {
                queueDetail += ' \u00B7 Last post: ' + hoursAgo + 'h ago';
            } else {
                const daysAgo = Math.floor(hoursAgo / 24);
                queueDetail += ' \u00B7 Last post: ' + daysAgo + 'd ago';
            }
        } else {
            queueDetail += ' \u00B7 No posts yet';
        }
        this._setHomeDetail('queue', queueDetail);
    },

    /**
     * Set a home card badge (status indicator).
     * @param {string} section - Card section name (instagram, gdrive, schedule, queue)
     * @param {string} type - Badge type: connected, warning, error, neutral
     * @param {string} text - Badge label text
     */
    _setHomeBadge(section, type, text) {
        const el = document.getElementById('home-badge-' + section);
        if (el) {
            el.textContent = text;
            el.className = 'home-card-badge badge-' + type;
        }
    },

    /**
     * Set home card detail text (supports HTML).
     */
    _setHomeDetail(section, html) {
        const el = document.getElementById('home-detail-' + section);
        if (el) {
            el.innerHTML = html;
        }
    },

    /**
     * Enter edit mode for a section — jumps to the wizard step
     * with "Save & Return" button shown instead of "Next".
     */
    editSection(section) {
        this.editingFrom = true;
        this.mode = 'wizard';

        // Map section names to wizard step names
        const sectionToStep = {
            'instagram': 'instagram',
            'gdrive': 'gdrive',
            'media-folder': 'media-folder',
            'schedule': 'schedule',
        };

        const stepName = sectionToStep[section] || section;
        this.goToStep(stepName);
    },

    /**
     * Return from edit mode to the home screen.
     * Re-fetches state to get latest data, then shows home.
     */
    async returnToHome() {
        this.editingFrom = false;
        this.mode = 'home';

        // Refresh state from server
        try {
            const response = await this._api('/api/onboarding/init', {
                init_data: this.initData,
                chat_id: this.chatId,
            });
            this.setupState = response.setup_state;
        } catch (err) {
            // Non-critical: show home with stale data
        }

        this.goToStep('home');
    },

    /**
     * Save schedule settings then return to home (edit mode).
     */
    async saveScheduleAndReturn() {
        this._showLoading(true);
        try {
            await this._api('/api/onboarding/schedule', {
                init_data: this.initData,
                chat_id: this.chatId,
                posts_per_day: this.schedule.postsPerDay,
                posting_hours_start: this.schedule.postingHoursStart,
                posting_hours_end: this.schedule.postingHoursEnd,
            });
            await this.returnToHome();
        } catch (err) {
            this._showError('Failed to save schedule. Please try again.');
        } finally {
            this._showLoading(false);
        }
    },

    /**
     * "Run Full Setup Again" — reset to wizard mode from step 1.
     */
    runFullSetup() {
        this.editingFrom = false;
        this.mode = 'wizard';
        this.goToStep('welcome');
    },

    /**
     * Show or hide "Save & Return" vs normal navigation
     * based on whether we are editing from home.
     */
    _updateStepNavVisibility(stepName) {
        // List of steps that have return navigation
        const editableSteps = ['instagram', 'gdrive', 'media-folder', 'schedule'];

        editableSteps.forEach(step => {
            const returnNav = document.getElementById('return-nav-' + step);
            if (returnNav) {
                returnNav.classList.toggle('hidden', !this.editingFrom);
            }
        });

        // For steps with regular nav, hide it when editing
        if (this.editingFrom) {
            document.querySelectorAll('.step-nav').forEach(el => {
                el.classList.add('hidden');
            });
        } else {
            document.querySelectorAll('.step-nav').forEach(el => {
                el.classList.remove('hidden');
            });
        }

        // Toggle schedule buttons
        const scheduleNext = document.getElementById('btn-schedule-next');
        const scheduleReturn = document.getElementById('btn-schedule-return');
        if (scheduleNext && scheduleReturn) {
            scheduleNext.classList.toggle('hidden', this.editingFrom);
            scheduleReturn.classList.toggle('hidden', !this.editingFrom);
        }
    },

    // ==================== Existing Wizard Methods ====================

    /**
     * Start OAuth flow for a provider.
     */
    async connectOAuth(provider) {
        try {
            const queryParams = new URLSearchParams({
                init_data: this.initData,
                chat_id: this.chatId,
            });
            const response = await this._apiGet(
                '/api/onboarding/oauth-url/' + provider + '?' + queryParams.toString()
            );

            // Open OAuth URL in new tab
            window.open(response.auth_url, '_blank');

            // Show polling indicator
            const key = provider === 'google-drive' ? 'gdrive' : provider;
            document.getElementById(key + '-polling').classList.remove('hidden');
            document.getElementById('btn-connect-' + key).disabled = true;

            // Start polling for OAuth completion
            this._startPolling(key);
        } catch (err) {
            this._showError('Failed to start ' + provider + ' connection. Please try again.');
        }
    },

    /**
     * Validate a Google Drive folder URL.
     */
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

            document.getElementById('folder-file-count').textContent = response.file_count;
            document.getElementById('folder-categories').textContent =
                response.categories.length > 0 ? response.categories.join(', ') : 'None';
            document.getElementById('folder-result').classList.remove('hidden');

            // Auto-advance: if editing from home, return; otherwise go to schedule
            if (this.editingFrom) {
                setTimeout(() => this.returnToHome(), 1500);
            } else {
                setTimeout(() => this.goToStep('schedule'), 1500);
            }
        } catch (err) {
            const errorEl = document.getElementById('folder-error');
            errorEl.textContent = err.message || 'Could not access this folder.';
            errorEl.classList.remove('hidden');
        } finally {
            this._showLoading(false);
        }
    },

    /**
     * Select a posts-per-day option.
     */
    selectOption(group, value) {
        document.querySelectorAll('#' + group + '-group .btn-option').forEach(btn => {
            btn.classList.toggle('active', parseInt(btn.dataset.value, 10) === value);
        });
        this.schedule.postsPerDay = value;
    },

    /**
     * Select a posting window preset.
     */
    selectWindow(start, end) {
        document.querySelectorAll('#posting-window-group .btn-option').forEach(btn => {
            const btnStart = parseInt(btn.dataset.start, 10);
            const btnEnd = parseInt(btn.dataset.end, 10);
            btn.classList.toggle('active', btnStart === start && btnEnd === end);
        });
        this.schedule.postingHoursStart = start;
        this.schedule.postingHoursEnd = end;
    },

    /**
     * Save schedule settings (wizard mode — advances to summary).
     */
    async saveSchedule() {
        this._showLoading(true);
        try {
            await this._api('/api/onboarding/schedule', {
                init_data: this.initData,
                chat_id: this.chatId,
                posts_per_day: this.schedule.postsPerDay,
                posting_hours_start: this.schedule.postingHoursStart,
                posting_hours_end: this.schedule.postingHoursEnd,
            });
            this.goToStep('summary');
        } catch (err) {
            this._showError('Failed to save schedule. Please try again.');
        } finally {
            this._showLoading(false);
        }
    },

    /**
     * Finish onboarding and close the Mini App.
     */
    async finishSetup() {
        const createSchedule = document.getElementById('create-schedule-toggle').checked;

        this._showLoading(true);
        try {
            await this._api('/api/onboarding/complete', {
                init_data: this.initData,
                chat_id: this.chatId,
                create_schedule: createSchedule,
                schedule_days: 7,
            });

            // Close the Mini App
            if (window.Telegram && window.Telegram.WebApp) {
                window.Telegram.WebApp.close();
            }
        } catch (err) {
            this._showError('Failed to complete setup. Please try again.');
        } finally {
            this._showLoading(false);
        }
    },

    // --- Private methods ---

    /**
     * Determine which step to show based on current state.
     */
    _resumeFromState() {
        if (!this.setupState) {
            this.mode = 'wizard';
            this.goToStep('welcome');
            return;
        }

        if (this.setupState.onboarding_completed) {
            // Returning user — show home screen dashboard
            this.mode = 'home';
            this.goToStep('home');
            return;
        }

        // Onboarding in progress — show wizard
        this.mode = 'wizard';

        // Update schedule defaults from saved state
        this.schedule.postsPerDay = this.setupState.posts_per_day || 3;
        this.schedule.postingHoursStart = this.setupState.posting_hours_start || 14;
        this.schedule.postingHoursEnd = this.setupState.posting_hours_end || 2;

        // Start from the beginning
        this.goToStep('welcome');
    },

    /**
     * Update connection status indicators on wizard steps.
     */
    _updateStatusIndicators() {
        const s = this.setupState;

        // Instagram
        const igStatus = document.getElementById('instagram-status');
        if (igStatus && s.instagram_connected) {
            igStatus.innerHTML =
                '<div class="status-icon status-connected">&#9679;</div>' +
                '<span>Connected: @' + this._escapeHtml(s.instagram_username || '') + '</span>';
            document.getElementById('btn-connect-instagram').textContent = 'Connected';
            document.getElementById('btn-connect-instagram').disabled = true;
        }

        // Google Drive
        const gdStatus = document.getElementById('gdrive-status');
        if (gdStatus && s.gdrive_connected) {
            gdStatus.innerHTML =
                '<div class="status-icon status-connected">&#9679;</div>' +
                '<span>Connected: ' + this._escapeHtml(s.gdrive_email || '') + '</span>';
            document.getElementById('btn-connect-gdrive').textContent = 'Connected';
            document.getElementById('btn-connect-gdrive').disabled = true;
        }
    },

    /**
     * Populate the summary step.
     */
    _populateSummary() {
        const s = this.setupState || {};

        document.getElementById('summary-instagram').textContent =
            s.instagram_connected ? '@' + (s.instagram_username || 'connected') : 'Not connected';

        document.getElementById('summary-gdrive').textContent =
            s.gdrive_connected ? s.gdrive_email || 'Connected' : 'Not connected';

        document.getElementById('summary-schedule').textContent =
            this.schedule.postsPerDay + ' posts/day';

        document.getElementById('summary-window').textContent =
            this._formatHour(this.schedule.postingHoursStart) + ' - ' +
            this._formatHour(this.schedule.postingHoursEnd) + ' UTC';
    },

    /**
     * Start polling for OAuth completion.
     */
    _startPolling(provider) {
        this._stopPolling();

        this.pollInterval = setInterval(async () => {
            try {
                const response = await this._api('/api/onboarding/init', {
                    init_data: this.initData,
                    chat_id: this.chatId,
                });
                this.setupState = response.setup_state;

                const connected = provider === 'instagram'
                    ? this.setupState.instagram_connected
                    : this.setupState.gdrive_connected;

                if (connected) {
                    this._stopPolling();
                    this._updateStatusIndicators();

                    // Auto-advance depends on mode
                    if (this.editingFrom) {
                        setTimeout(() => this.returnToHome(), 800);
                    } else if (provider === 'instagram') {
                        setTimeout(() => this.goToStep('gdrive'), 800);
                    } else {
                        setTimeout(() => this.goToStep('media-folder'), 800);
                    }
                }
            } catch (_) {
                // Silently retry on poll failure
            }
        }, 3000);

        // Stop after 10 minutes
        this.pollTimeout = setTimeout(() => this._stopPolling(), 600000);
    },

    _stopPolling() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
        if (this.pollTimeout) {
            clearTimeout(this.pollTimeout);
            this.pollTimeout = null;
        }
        // Hide all polling indicators
        document.querySelectorAll('.polling-indicator').forEach(el => el.classList.add('hidden'));
    },

    /**
     * POST to an API endpoint.
     */
    async _api(path, body) {
        const response = await fetch(path, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || 'Request failed');
        }

        return response.json();
    },

    /**
     * GET from an API endpoint.
     */
    async _apiGet(path) {
        const response = await fetch(path);

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || 'Request failed');
        }

        return response.json();
    },

    /**
     * Apply Telegram theme colors.
     */
    _applyTheme(params) {
        if (!params) return;
        const root = document.documentElement;
        if (params.bg_color) root.style.setProperty('--tg-theme-bg-color', params.bg_color);
        if (params.text_color) root.style.setProperty('--tg-theme-text-color', params.text_color);
        if (params.hint_color) root.style.setProperty('--tg-theme-hint-color', params.hint_color);
        if (params.link_color) root.style.setProperty('--tg-theme-link-color', params.link_color);
        if (params.button_color) root.style.setProperty('--tg-theme-button-color', params.button_color);
        if (params.button_text_color) root.style.setProperty('--tg-theme-button-text-color', params.button_text_color);
        if (params.secondary_bg_color) root.style.setProperty('--tg-theme-secondary-bg-color', params.secondary_bg_color);

        document.body.style.backgroundColor = params.bg_color || '#ffffff';
    },

    _showLoading(show) {
        document.getElementById('loading-overlay').classList.toggle('hidden', !show);
    },

    _showError(message) {
        // For critical errors, replace the whole app content
        const app = document.getElementById('app');
        app.innerHTML =
            '<div class="step"><div class="step-content" style="text-align:center;padding-top:60px">' +
            '<h2>Oops</h2><p class="subtitle">' + this._escapeHtml(message) + '</p>' +
            '</div></div>';
    },

    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    _formatHour(h) {
        if (h === 0) return '12am';
        if (h === 12) return '12pm';
        if (h < 12) return h + 'am';
        return (h - 12) + 'pm';
    },
};

// Start the app when DOM is ready
document.addEventListener('DOMContentLoaded', () => App.init());
```

**Summary of changes in `app.js`:**

1. Added `mode` property (`'wizard'` or `'home'`).
2. Added `editingFrom` property (boolean).
3. `_resumeFromState()` now routes to `step-home` when `onboarding_completed` is true (previously went to `step-summary`).
4. Added `_populateHome()` to fill all four dashboard cards from `setupState`.
5. Added `_setHomeBadge()` and `_setHomeDetail()` helpers.
6. Added `editSection()` to enter edit mode: sets `editingFrom = true`, then navigates to the relevant wizard step.
7. Added `returnToHome()`: sets `editingFrom = false`, re-fetches state via `/api/onboarding/init`, then goes to `step-home`.
8. Added `saveScheduleAndReturn()` for the schedule step's "Save & Return" button.
9. Added `runFullSetup()` for the "Run Full Setup Again" button.
10. Added `_updateStepNavVisibility()` to toggle between "Skip/Next" nav and "Save & Return" nav based on `editingFrom`.
11. Modified `_startPolling()` auto-advance: if `editingFrom`, returns to home instead of advancing to next wizard step.
12. Modified `validateFolder()` auto-advance: if `editingFrom`, returns to home instead of going to schedule step.

---

### Step 5: Add home screen CSS

**File:** `/Users/chris/Projects/storyline-ai/src/api/static/onboarding/style.css`

**What changes:** Append the following CSS rules at the end of the file (after the existing `.hidden` rule on line 399):

```css
/* ==================== Home Screen Dashboard ==================== */

/* Home card */
.home-card {
    background: var(--tg-theme-secondary-bg-color);
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 12px;
    position: relative;
}

.home-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
}

.home-card-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 600;
    font-size: 15px;
}

.home-card-icon {
    font-size: 18px;
    line-height: 1;
}

/* Badge (status pill) */
.home-card-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 500;
    line-height: 1.4;
}

.badge-connected {
    background: rgba(34, 197, 94, 0.15);
    color: #16a34a;
}

.badge-warning {
    background: rgba(245, 158, 11, 0.15);
    color: #d97706;
}

.badge-error {
    background: rgba(239, 68, 68, 0.15);
    color: #dc2626;
}

.badge-neutral {
    background: rgba(0, 0, 0, 0.06);
    color: var(--tg-theme-hint-color);
}

/* Card detail text */
.home-card-detail {
    font-size: 13px;
    color: var(--tg-theme-hint-color);
    padding-right: 50px; /* leave room for edit button */
    line-height: 1.5;
}

/* Inline tag (e.g., "Dry run ON") */
.home-card-tag {
    display: inline-block;
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 500;
    background: rgba(245, 158, 11, 0.15);
    color: #d97706;
}

/* Edit button positioned bottom-right of card */
.btn-card-edit {
    position: absolute;
    bottom: 16px;
    right: 16px;
    background: none;
    border: none;
    color: var(--tg-theme-link-color);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    padding: 4px 0;
    -webkit-tap-highlight-color: transparent;
}

.btn-card-edit:active {
    opacity: 0.6;
}

/* Divider */
.home-divider {
    height: 1px;
    background: rgba(0, 0, 0, 0.08);
    margin: 20px 0;
}

/* Secondary button (e.g., "Run Full Setup Again") */
.btn-secondary {
    width: 100%;
    padding: 14px 24px;
    background: var(--tg-theme-secondary-bg-color);
    color: var(--tg-theme-text-color);
    border: none;
    border-radius: 10px;
    font-size: 15px;
    font-weight: 600;
    cursor: pointer;
    -webkit-tap-highlight-color: transparent;
}

.btn-secondary:active {
    opacity: 0.7;
}

/* Return navigation (shown in edit-from-home mode) */
.step-nav-return {
    margin-top: 16px;
}

.step-nav-return.hidden {
    display: none;
}
```

---

### Step 6: Update tests

#### 6a. Update `/start` command tests

**File:** `/Users/chris/Projects/storyline-ai/tests/src/services/test_telegram_commands.py`

The existing `TestStartCommand` class (around line 1478) needs updating. The test `test_start_returning_user_shows_dashboard` currently asserts that `/queue` and `/status` appear in the text response. After this change, returning users get a Mini App button labeled "Open Storyline" instead.

**Replace `test_start_returning_user_shows_dashboard` (starting at line 1516):**

```python
async def test_start_returning_user_shows_webapp_button(self, mock_command_handlers):
    """Returning user (onboarding completed) sees 'Open Storyline' Mini App button."""
    handlers = mock_command_handlers
    service = handlers.service

    mock_user = Mock()
    mock_user.id = uuid4()
    service.user_repo.get_by_telegram_id.return_value = mock_user

    mock_update = AsyncMock()
    mock_update.effective_user.id = 12345
    mock_update.effective_user.first_name = "Test"
    mock_update.effective_user.username = "testuser"
    mock_update.effective_chat.id = -100123
    mock_update.message.message_id = 1

    with patch(
        "src.services.core.settings_service.SettingsService"
    ) as MockSettings:
        mock_chat_settings = Mock(onboarding_completed=True)
        MockSettings.return_value.get_settings.return_value = mock_chat_settings
        MockSettings.return_value.close = Mock()

        with patch(
            "src.services.core.telegram_commands.settings"
        ) as mock_app_settings:
            mock_app_settings.OAUTH_REDIRECT_BASE_URL = "https://example.com"

            await handlers.handle_start(mock_update, Mock())

    call_args = mock_update.message.reply_text.call_args
    assert "Open Storyline" in str(call_args)
    assert "Welcome back" in str(call_args)
```

**Add a new test for the fallback case (no OAUTH_REDIRECT_BASE_URL):**

```python
async def test_start_no_oauth_url_shows_text_fallback(self, mock_command_handlers):
    """When OAUTH_REDIRECT_BASE_URL is not set, show text command list."""
    handlers = mock_command_handlers
    service = handlers.service

    mock_user = Mock()
    mock_user.id = uuid4()
    service.user_repo.get_by_telegram_id.return_value = mock_user

    mock_update = AsyncMock()
    mock_update.effective_user.id = 12345
    mock_update.effective_user.first_name = "Test"
    mock_update.effective_user.username = "testuser"
    mock_update.effective_chat.id = -100123
    mock_update.message.message_id = 1

    with patch(
        "src.services.core.settings_service.SettingsService"
    ) as MockSettings:
        mock_chat_settings = Mock(onboarding_completed=True)
        MockSettings.return_value.get_settings.return_value = mock_chat_settings
        MockSettings.return_value.close = Mock()

        with patch(
            "src.services.core.telegram_commands.settings"
        ) as mock_app_settings:
            mock_app_settings.OAUTH_REDIRECT_BASE_URL = None

            await handlers.handle_start(mock_update, Mock())

    call_text = mock_update.message.reply_text.call_args[0][0]
    assert "/queue" in call_text
    assert "/status" in call_text
```

#### 6b. Update onboarding init response tests

**File:** `/Users/chris/Projects/storyline-ai/tests/src/api/test_onboarding_routes.py`

**Add a new test within `TestOnboardingInit`:**

```python
def test_init_returns_dashboard_fields(self, client):
    """Init response includes queue_count, last_post_at, is_paused, dry_run_mode."""
    mock_settings = Mock(
        id=uuid4(),
        posts_per_day=3,
        posting_hours_start=14,
        posting_hours_end=2,
        onboarding_completed=True,
        is_paused=False,
        dry_run_mode=True,
    )

    with (
        _mock_validate(),
        patch(
            "src.api.routes.onboarding.ChatSettingsRepository"
        ) as MockSettingsRepo,
        patch("src.api.routes.onboarding.TokenRepository") as MockTokenRepo,
        patch("src.api.routes.onboarding.InstagramAccountService") as MockIGService,
        patch("src.api.routes.onboarding.QueueRepository") as MockQueueRepo,
        patch("src.api.routes.onboarding.HistoryRepository") as MockHistoryRepo,
    ):
        MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
        MockSettingsRepo.return_value.close = Mock()
        MockTokenRepo.return_value.get_token_for_chat.return_value = None
        MockTokenRepo.return_value.close = Mock()
        MockIGService.return_value.get_active_account.return_value = None
        MockIGService.return_value.close = Mock()
        MockQueueRepo.return_value.count_pending.return_value = 5
        MockQueueRepo.return_value.close = Mock()

        mock_post = Mock()
        mock_post.posted_at = datetime(2026, 2, 18, 10, 30, 0)
        MockHistoryRepo.return_value.get_recent_posts.return_value = [mock_post]
        MockHistoryRepo.return_value.close = Mock()

        response = client.post(
            "/api/onboarding/init",
            json={"init_data": "test", "chat_id": CHAT_ID},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["setup_state"]["is_paused"] is False
    assert data["setup_state"]["dry_run_mode"] is True
    assert data["setup_state"]["queue_count"] == 5
    assert data["setup_state"]["last_post_at"] is not None
```

**Important note on the test mock:** The `QueueRepository` and `HistoryRepository` are imported lazily inside `_get_setup_state`, so you need to patch them at the module level where they are imported. Since they are imported locally via `from src.repositories.queue_repository import QueueRepository` inside the function, you must patch at `src.api.routes.onboarding.QueueRepository` and `src.api.routes.onboarding.HistoryRepository`. However, because the import is local (inside the function body), you need to patch the source module instead:

```python
patch("src.repositories.queue_repository.QueueRepository") as MockQueueRepo,
patch("src.repositories.history_repository.HistoryRepository") as MockHistoryRepo,
```

Alternatively, move the imports to the top of `onboarding.py` to make patching simpler and more consistent with the existing pattern (where `ChatSettingsRepository`, `TokenRepository`, and `InstagramAccountService` are all imported at the top of the file). This is the recommended approach.

If taking the recommended approach, add to the top of `/Users/chris/Projects/storyline-ai/src/api/routes/onboarding.py`:

```python
from src.repositories.queue_repository import QueueRepository
from src.repositories.history_repository import HistoryRepository
```

Then the test patches become `patch("src.api.routes.onboarding.QueueRepository")` and `patch("src.api.routes.onboarding.HistoryRepository")`, consistent with the existing test patterns.

**Add import for datetime in the test file** (at the top of `test_onboarding_routes.py`):

```python
from datetime import datetime
```

**Add a test for graceful degradation when queue/history repos fail:**

```python
def test_init_dashboard_fields_default_on_error(self, client):
    """Queue/history errors don't break the init response."""
    mock_settings = Mock(
        id=uuid4(),
        posts_per_day=3,
        posting_hours_start=14,
        posting_hours_end=2,
        onboarding_completed=True,
        is_paused=False,
        dry_run_mode=False,
    )

    with (
        _mock_validate(),
        patch(
            "src.api.routes.onboarding.ChatSettingsRepository"
        ) as MockSettingsRepo,
        patch("src.api.routes.onboarding.TokenRepository") as MockTokenRepo,
        patch("src.api.routes.onboarding.InstagramAccountService") as MockIGService,
        patch("src.api.routes.onboarding.QueueRepository") as MockQueueRepo,
    ):
        MockSettingsRepo.return_value.get_or_create.return_value = mock_settings
        MockSettingsRepo.return_value.close = Mock()
        MockTokenRepo.return_value.get_token_for_chat.return_value = None
        MockTokenRepo.return_value.close = Mock()
        MockIGService.return_value.get_active_account.return_value = None
        MockIGService.return_value.close = Mock()
        # Queue repo throws an exception
        MockQueueRepo.side_effect = Exception("DB connection failed")

        response = client.post(
            "/api/onboarding/init",
            json={"init_data": "test", "chat_id": CHAT_ID},
        )

    assert response.status_code == 200
    data = response.json()
    # Defaults when repos fail
    assert data["setup_state"]["queue_count"] == 0
    assert data["setup_state"]["last_post_at"] is None
```

---

## 4. Test Plan

### Unit Tests

| Test | File | What it validates |
|------|------|-------------------|
| `test_start_new_user_shows_webapp_button` | `test_telegram_commands.py` | New user sees "Open Setup Wizard" button (unchanged) |
| `test_start_returning_user_shows_webapp_button` | `test_telegram_commands.py` | Returning user sees "Open Storyline" button (NEW -- replaces old text test) |
| `test_start_no_oauth_url_shows_text_fallback` | `test_telegram_commands.py` | Without OAUTH_REDIRECT_BASE_URL, fallback to text command list (NEW) |
| `test_start_logs_interaction` | `test_telegram_commands.py` | Interaction logged for both cases (unchanged) |
| `test_init_returns_dashboard_fields` | `test_onboarding_routes.py` | Init response includes `is_paused`, `dry_run_mode`, `queue_count`, `last_post_at` (NEW) |
| `test_init_dashboard_fields_default_on_error` | `test_onboarding_routes.py` | Graceful fallback when repos fail (NEW) |
| All existing `TestOnboardingInit` tests | `test_onboarding_routes.py` | Existing tests still pass (no regression) |

### Frontend (Manual)

The Mini App is vanilla HTML/JS/CSS with no build step. Testing is manual via Telegram.

---

## 5. Documentation Updates

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Changed

- **`/start` command always opens Mini App** - Returning users now see an "Open Storyline" button linking to a visual dashboard instead of a text command list. The Mini App decides what to show (onboarding wizard vs. home screen) based on the user's onboarding status. Text fallback retained when `OAUTH_REDIRECT_BASE_URL` is not configured.

### Added

- **Mini App home screen for returning users** - Dashboard view showing Instagram connection status, Google Drive connection, posting schedule, and queue status. Each section has an Edit button that jumps to the relevant setup step with a "Save & Return" flow.
- **Expanded `/api/onboarding/init` response** - Now includes `is_paused`, `dry_run_mode`, `queue_count`, and `last_post_at` fields for the dashboard display
- **"Run Full Setup Again" button** - Returning users can re-enter the full onboarding wizard from the home screen
```

---

## 6. Stress Testing and Edge Cases

### Partially Configured Users

**Scenario:** User completed onboarding but only connected Instagram (skipped Google Drive and media folder).

**Expected behavior:** Home screen shows:
- Instagram: green "Connected" badge, `@username`
- Google Drive: amber "Not connected" badge, "Tap Edit to connect Google Drive"
- Schedule: green "Active" badge (always configured via defaults)
- Queue: gray "Empty" badge, "0 posts in queue -- No posts yet"

**Why it works:** `_populateHome()` checks each field independently. Null/false values trigger the "Not connected" variant. No field depends on any other.

### User Disconnects Instagram After Onboarding

**Scenario:** User completed onboarding, then their Instagram token expired or was revoked.

**Expected behavior:** The `/api/onboarding/init` re-checks live state every time the Mini App opens. `get_active_account()` returns `None` if no valid account exists. The home screen would show Instagram as "Not connected" with "Tap Edit to connect your account". The user taps Edit, goes through the Instagram OAuth flow, and returns to home.

**Why it works:** `_get_setup_state()` always fetches fresh data from the database. It does not cache or assume state based on `onboarding_completed`.

### Concurrent Mini App Sessions

**Scenario:** User opens the Mini App on two devices simultaneously.

**Expected behavior:** Both sessions read the same state from the database. If one session makes changes (e.g., saves schedule), the other session will pick up the new state the next time it calls `/api/onboarding/init` (which happens on `returnToHome()`). There is no real-time sync between sessions -- this is intentional for simplicity.

**Risk mitigation:** No destructive operations happen from the home screen. All edits go through the same idempotent `SettingsService.update_setting()` calls.

### Empty Queue and No Posts

**Scenario:** Brand-new user who just finished onboarding but has not created a schedule yet.

**Expected behavior:** 
- Queue: "Empty" badge, "0 posts in queue -- No posts yet"
- `queue_count` is 0, `last_post_at` is null.

**Why it works:** The init response defaults `queue_count` to 0 and `last_post_at` to `null`. The JS handles null gracefully with "No posts yet".

### Queue/History Repository Failure

**Scenario:** Database connection issues when fetching queue or history data.

**Expected behavior:** The `try/except` block in `_get_setup_state()` catches the exception, logs a debug message, and returns defaults (`queue_count: 0`, `last_post_at: null`). The home screen still renders with all other data intact.

---

## 7. Verification Checklist

After implementing, verify each item manually in Telegram:

- [ ] **New user `/start`**: Shows "Open Setup Wizard" button with MarkdownV2 welcome message
- [ ] **New user Mini App**: Opens wizard at step 1 (welcome), not home screen
- [ ] **Returning user `/start`**: Shows "Open Storyline" button with "Welcome back" message
- [ ] **Returning user Mini App**: Opens home screen dashboard, NOT the wizard or summary
- [ ] **Home: Instagram card**: Shows correct badge (Connected/Not connected) and username
- [ ] **Home: Google Drive card**: Shows correct badge and email
- [ ] **Home: Schedule card**: Shows posts/day, posting window, "Paused" badge if paused, "Dry run ON" tag if active
- [ ] **Home: Queue card**: Shows count and last post time (or "No posts yet")
- [ ] **Edit Instagram**: Tapping Edit opens the Instagram wizard step with "Save & Return" visible and "Skip for now" hidden
- [ ] **Edit Google Drive**: Same pattern as Instagram
- [ ] **Edit Schedule**: "Continue" button replaced with "Save & Return" button. Saving returns to home with updated values.
- [ ] **OAuth in edit mode**: Connecting Instagram via Edit returns to home screen after OAuth completes (not to next wizard step)
- [ ] **Folder validation in edit mode**: Validating a folder in edit mode returns to home (not to schedule step)
- [ ] **Run Full Setup Again**: Returns to wizard step 1 (welcome), "Skip"/"Next" navigation restored
- [ ] **No OAUTH_REDIRECT_BASE_URL**: `/start` falls back to text command list
- [ ] **Theme**: Home screen cards respect Telegram theme colors (test in light and dark mode)

---

## 8. What NOT To Do

1. **Do not modify `/settings` command** -- That is Phase 04's responsibility. The home screen is a visual dashboard; `/settings` is the Telegram-native toggle interface.

2. **Do not add new API endpoints** -- The existing `/api/onboarding/init` endpoint is expanded with additional response fields. Do not create `/api/onboarding/dashboard` or similar. One init endpoint serves both wizard and home screen.

3. **Do not break the wizard flow** -- The 6-step wizard must continue to work identically for users who have not completed onboarding. The `mode` and `editingFrom` flags control behavior; they do not change wizard step HTML or logic.

4. **Do not modify `src/models/chat_settings.py`** -- Phase 01 owns this file. All fields needed are already present (`onboarding_step`, `onboarding_completed`, `is_paused`, `dry_run_mode`).

5. **Do not modify `src/services/core/telegram_settings.py`** -- Phase 04 owns this file.

6. **Do not modify `src/services/core/media_sync.py`** -- Phase 01 owns this file.

7. **Do not add a "Trigger Sync" button to the home screen** -- This was considered but deferred. The home screen is read-only for queue and media status. Triggering syncs should go through `/sync` in Telegram or a future Phase 04 addition.

8. **Do not persist `mode` or `editingFrom` state server-side** -- These are ephemeral client-side state variables. The Mini App always re-derives mode from `onboarding_completed` on open.

9. **Do not use a JS framework** -- The Mini App is vanilla JS by design. Do not introduce React, Vue, or any bundler. Keep it as a single `app.js` file with no dependencies.

10. **Do not store the `init` response in localStorage** -- Always fetch fresh state from the server. Cached state could be stale if settings were changed from Telegram commands between Mini App sessions.

---

### Critical Files for Implementation
- `/Users/chris/Projects/storyline-ai/src/services/core/telegram_commands.py` - Core change: /start handler must always show Mini App button
- `/Users/chris/Projects/storyline-ai/src/api/static/onboarding/app.js` - Largest change: dual-mode logic (wizard vs home), edit-and-return flow
- `/Users/chris/Projects/storyline-ai/src/api/routes/onboarding.py` - Backend change: expand _get_setup_state with queue/history/status fields
- `/Users/chris/Projects/storyline-ai/src/api/static/onboarding/index.html` - New HTML section for home screen cards and return nav buttons
- `/Users/chris/Projects/storyline-ai/tests/src/api/test_onboarding_routes.py` - Test coverage for expanded init response fields