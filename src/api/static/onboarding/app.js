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
    _currentStep: 'welcome',

    // Mode: 'wizard' (onboarding) or 'home' (returning user dashboard)
    mode: 'wizard',

    // When true, wizard steps show "Save & Return" instead of "Next"/"Skip"
    editingFrom: false,

    // Track which steps were completed vs skipped
    skippedSteps: new Set(),
    folderValidation: null,

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

        // Get URL parameters (chat_id and optional token for browser access)
        const params = new URLSearchParams(window.location.search);
        this.chatId = parseInt(params.get('chat_id'), 10);
        const urlToken = params.get('token');

        if (tg && tg.initData) {
            // Opened as Telegram Mini App — use native auth
            tg.ready();
            tg.expand();
            this._applyTheme(tg.themeParams);
            this.initData = tg.initData;
        } else if (urlToken) {
            // Opened via browser URL with signed token (group chats)
            this.initData = urlToken;
        } else {
            this._showError('Missing authentication data. Please open from Telegram.');
            return;
        }

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
     * Navigate to a step.
     */
    goToStep(stepName) {
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

        // If going to home, populate dashboard cards
        if (stepName === 'home') {
            this._populateHome();
        }

        // Toggle wizard step navigation based on editing mode
        this._updateStepNavVisibility(stepName);

        // If going to indexing, update the preview from folder validation
        if (stepName === 'indexing' && this.folderValidation) {
            document.getElementById('indexing-file-count').textContent =
                this.folderValidation.file_count;
            document.getElementById('indexing-categories').textContent =
                this.folderValidation.categories.length > 0
                    ? this.folderValidation.categories.join(', ')
                    : 'None';
            document.getElementById('btn-start-indexing').textContent =
                'Index ' + this.folderValidation.file_count + ' Files Now';
        }

        // Stop any active polling when navigating away
        this._stopPolling();
    },

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

    /**
     * Select a posts-per-day option.
     */
    selectOption(group, value) {
        // Update button active states
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
     * Save schedule settings.
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

    // ==================== Home Screen Methods ====================

    // Track which cards have been loaded (lazy loading)
    _cardDataLoaded: {},

    /**
     * Populate the home screen dashboard cards from setupState.
     * @param {Object} opts - Options
     * @param {boolean} opts.keepExpanded - If true, don't collapse cards or reset loaded state
     */
    _populateHome(opts) {
        const s = this.setupState || {};
        const keepExpanded = opts && opts.keepExpanded;

        if (!keepExpanded) {
            // Reset card data loaded state on each home populate
            this._cardDataLoaded = {};

            // Collapse all cards
            document.querySelectorAll('.home-card-expandable').forEach(card => {
                card.classList.remove('expanded');
            });
        }

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

        // Quick Controls card summary
        const deliveryOn = !s.is_paused;
        const dryRunOn = s.dry_run_mode;
        this._setHomeDetail('controls',
            'Delivery: ' + (deliveryOn ? 'ON' : 'OFF') +
            ' \u00B7 Dry Run: ' + (dryRunOn ? 'ON' : 'OFF'));
        // Set toggle states
        const deliveryToggle = document.getElementById('toggle-delivery');
        const dryRunToggle = document.getElementById('toggle-dryrun');
        const igApiToggle = document.getElementById('toggle-instagram-api');
        const verboseToggle = document.getElementById('toggle-verbose');
        const mediaSyncToggle = document.getElementById('toggle-media-sync');
        if (deliveryToggle) deliveryToggle.checked = deliveryOn;
        if (dryRunToggle) dryRunToggle.checked = dryRunOn;
        if (igApiToggle) igApiToggle.checked = !!s.enable_instagram_api;
        if (verboseToggle) verboseToggle.checked = !!s.show_verbose_notifications;
        if (mediaSyncToggle) mediaSyncToggle.checked = !!s.media_sync_enabled;

        // Set numeric setting displays
        this._updateSettingDisplay('posts_per_day', s.posts_per_day || 3);
        this._updateSettingDisplay('posting_hours_start',
            s.posting_hours_start != null ? s.posting_hours_start : 14);
        this._updateSettingDisplay('posting_hours_end',
            s.posting_hours_end != null ? s.posting_hours_end : 2);

        // Schedule card
        const postsPerDay = s.posts_per_day || 3;
        const start = s.posting_hours_start != null ? s.posting_hours_start : 14;
        const end = s.posting_hours_end != null ? s.posting_hours_end : 2;

        if (s.is_paused) {
            this._setHomeBadge('schedule', 'error', 'Paused');
        } else {
            this._setHomeBadge('schedule', 'connected', 'Active');
        }

        let scheduleDetail = postsPerDay + '/day, ' +
            this._formatHour(start) + '-' + this._formatHour(end) + ' UTC';
        if (s.schedule_end_date) {
            const endDate = new Date(s.schedule_end_date);
            scheduleDetail += ' \u00B7 Ends ' + this._formatShortDate(endDate);
        }
        this._setHomeDetail('schedule', scheduleDetail);

        // Queue status card
        const queueCount = s.queue_count || 0;
        if (queueCount > 0) {
            this._setHomeBadge('queue', 'connected', queueCount + ' pending');
        } else {
            this._setHomeBadge('queue', 'neutral', 'Empty');
        }

        let queueDetail = '';
        if (s.next_post_at) {
            const nextDate = new Date(s.next_post_at);
            queueDetail = 'Next: ' + this._formatRelativeTime(nextDate);
        } else {
            queueDetail = 'No posts scheduled';
        }
        this._setHomeDetail('queue', queueDetail);

        // Recent Activity card summary
        if (s.last_post_at) {
            const lastDate = new Date(s.last_post_at);
            this._setHomeDetail('history', 'Last post: ' + this._formatRelativeTime(lastDate));
        } else {
            this._setHomeDetail('history', 'No posts yet');
        }

        // Media Library card
        const mediaCount = s.media_count || 0;
        if (mediaCount > 0) {
            this._setHomeBadge('media', 'connected', mediaCount.toLocaleString() + ' files');
        } else {
            this._setHomeBadge('media', 'neutral', 'Empty');
        }
        this._setHomeDetail('media', 'Tap to see categories');
    },

    _setHomeBadge(section, type, text) {
        const el = document.getElementById('home-badge-' + section);
        if (el) {
            el.textContent = text;
            el.className = 'home-card-badge badge-' + type;
        }
    },

    _setHomeDetail(section, html) {
        const el = document.getElementById('home-detail-' + section);
        if (el) {
            el.innerHTML = html;
        }
    },

    /**
     * Toggle a collapsible card open/closed.
     * Lazy-loads data on first expand.
     */
    toggleCard(cardId) {
        const card = document.getElementById('home-card-' + cardId);
        if (!card) return;

        const isExpanded = card.classList.toggle('expanded');

        if (isExpanded && !this._cardDataLoaded[cardId]) {
            this._cardDataLoaded[cardId] = true;
            this._loadCardData(cardId);
        }
    },

    /**
     * Load data for a specific card on first expand.
     */
    async _loadCardData(cardId) {
        const loaders = {
            schedule: () => this._loadQueueDetail('schedule'),
            queue: () => this._loadQueueDetail('queue'),
            history: () => this._loadHistoryDetail(),
            media: () => this._loadMediaStats(),
        };

        const loader = loaders[cardId];
        if (loader) await loader();
    },

    /**
     * Fetch queue detail and render into schedule or queue card.
     */
    async _loadQueueDetail(target) {
        const loadingId = target + '-loading';
        const loadingEl = document.getElementById(loadingId);
        if (loadingEl) loadingEl.classList.remove('hidden');

        try {
            const params = new URLSearchParams({
                init_data: this.initData,
                chat_id: this.chatId,
                limit: 10,
            });
            const data = await this._apiGet('/api/onboarding/queue-detail?' + params.toString());

            if (target === 'schedule' || target === 'queue') {
                // Both cards share the same data source
                this._renderDaySummary(data.day_summary, data.days_remaining);
                this._renderQueueItems(data.items);
                // Mark both as loaded
                this._cardDataLoaded['schedule'] = true;
                this._cardDataLoaded['queue'] = true;
            }
        } catch (err) {
            const container = target === 'schedule'
                ? document.getElementById('schedule-day-summary')
                : document.getElementById('queue-items-list');
            if (container) {
                container.innerHTML = '<div class="card-body-empty">Failed to load data</div>';
            }
        } finally {
            if (loadingEl) loadingEl.classList.add('hidden');
        }
    },

    /**
     * Fetch and render recent posting history.
     */
    async _loadHistoryDetail() {
        const loadingEl = document.getElementById('history-loading');
        if (loadingEl) loadingEl.classList.remove('hidden');

        try {
            const params = new URLSearchParams({
                init_data: this.initData,
                chat_id: this.chatId,
                limit: 10,
            });
            const data = await this._apiGet('/api/onboarding/history-detail?' + params.toString());
            this._renderHistoryItems(data.items);
        } catch (err) {
            const container = document.getElementById('history-items-list');
            if (container) {
                container.innerHTML = '<div class="card-body-empty">Failed to load history</div>';
            }
        } finally {
            if (loadingEl) loadingEl.classList.add('hidden');
        }
    },

    /**
     * Fetch and render media library stats.
     */
    async _loadMediaStats() {
        const loadingEl = document.getElementById('media-loading');
        if (loadingEl) loadingEl.classList.remove('hidden');

        try {
            const params = new URLSearchParams({
                init_data: this.initData,
                chat_id: this.chatId,
            });
            const data = await this._apiGet('/api/onboarding/media-stats?' + params.toString());
            this._renderCategoryBreakdown(data.categories, data.total_active);
        } catch (err) {
            const container = document.getElementById('media-category-list');
            if (container) {
                container.innerHTML = '<div class="card-body-empty">Failed to load media stats</div>';
            }
        } finally {
            if (loadingEl) loadingEl.classList.add('hidden');
        }
    },

    // Toggle element IDs mapped to setting names
    _toggleIds: {
        'is_paused': 'toggle-delivery',
        'dry_run_mode': 'toggle-dryrun',
        'enable_instagram_api': 'toggle-instagram-api',
        'show_verbose_notifications': 'toggle-verbose',
        'media_sync_enabled': 'toggle-media-sync',
    },

    /**
     * Toggle a boolean setting via API.
     */
    async toggleSetting(settingName) {
        try {
            const data = await this._api('/api/onboarding/toggle-setting', {
                init_data: this.initData,
                chat_id: this.chatId,
                setting_name: settingName,
            });

            // Update local state
            if (this.setupState) {
                this.setupState[settingName] = data.new_value;
            }

            // Update summary text
            this._updateControlsSummary();

            // Update schedule badge
            if (settingName === 'is_paused') {
                if (this.setupState.is_paused) {
                    this._setHomeBadge('schedule', 'error', 'Paused');
                } else {
                    this._setHomeBadge('schedule', 'connected', 'Active');
                }
            }
        } catch (err) {
            // Revert toggle on failure
            const toggleId = this._toggleIds[settingName];
            if (toggleId) {
                const toggle = document.getElementById(toggleId);
                if (toggle) toggle.checked = !toggle.checked;
            }
        }
    },

    /**
     * Adjust a numeric setting by a delta (stepper +/- buttons).
     */
    async adjustSetting(settingName, delta) {
        const s = this.setupState || {};
        const current = s[settingName] || 0;
        let newValue = current + delta;

        // Clamp values
        if (settingName === 'posts_per_day') {
            newValue = Math.max(1, Math.min(50, newValue));
        } else {
            // Hours: wrap around 0-23
            newValue = ((newValue % 24) + 24) % 24;
        }

        if (newValue === current) return;

        // Optimistic UI update
        this.setupState[settingName] = newValue;
        this._updateSettingDisplay(settingName, newValue);

        try {
            await this._api('/api/onboarding/update-setting', {
                init_data: this.initData,
                chat_id: this.chatId,
                setting_name: settingName,
                value: newValue,
            });

            // Update controls summary
            this._updateControlsSummary();
        } catch (err) {
            // Revert on failure
            this.setupState[settingName] = current;
            this._updateSettingDisplay(settingName, current);
        }
    },

    /**
     * Update the displayed value for a numeric setting.
     */
    _updateSettingDisplay(settingName, value) {
        const displayMap = {
            'posts_per_day': { id: 'setting-posts-per-day', fmt: v => String(v) },
            'posting_hours_start': { id: 'setting-posting-hours-start', fmt: v => this._formatHour(v) },
            'posting_hours_end': { id: 'setting-posting-hours-end', fmt: v => this._formatHour(v) },
        };
        const mapping = displayMap[settingName];
        if (mapping) {
            const el = document.getElementById(mapping.id);
            if (el) el.textContent = mapping.fmt(value);
        }
    },

    /**
     * Update the Quick Controls card summary text.
     */
    _updateControlsSummary() {
        const s = this.setupState || {};
        const deliveryOn = !s.is_paused;
        const dryRunOn = s.dry_run_mode;
        this._setHomeDetail('controls',
            'Delivery: ' + (deliveryOn ? 'ON' : 'OFF') +
            ' \u00B7 Dry Run: ' + (dryRunOn ? 'ON' : 'OFF'));
    },

    /**
     * Extend the schedule by N days.
     */
    async extendSchedule(days) {
        this._showLoading(true);
        try {
            await this._api('/api/onboarding/extend-schedule', {
                init_data: this.initData,
                chat_id: this.chatId,
                days: days,
            });

            // Refresh state without collapsing cards
            await this._refreshHome({ keepExpanded: true });
        } catch (err) {
            // Show error inline
        } finally {
            this._showLoading(false);
        }
    },

    /**
     * Show the regenerate confirmation dialog.
     */
    confirmRegenerate() {
        const actions = document.getElementById('schedule-actions');
        const confirm = document.getElementById('regenerate-confirm');
        if (actions) actions.classList.add('hidden');
        if (confirm) confirm.classList.remove('hidden');
    },

    /**
     * Cancel the regenerate confirmation.
     */
    cancelRegenerate() {
        const actions = document.getElementById('schedule-actions');
        const confirm = document.getElementById('regenerate-confirm');
        if (actions) actions.classList.remove('hidden');
        if (confirm) confirm.classList.add('hidden');
    },

    /**
     * Regenerate the schedule (clear + rebuild).
     */
    async regenerateSchedule() {
        this.cancelRegenerate();
        this._showLoading(true);
        try {
            await this._api('/api/onboarding/regenerate-schedule', {
                init_data: this.initData,
                chat_id: this.chatId,
                days: 7,
            });

            // Refresh state without collapsing cards
            await this._refreshHome({ keepExpanded: true });
        } catch (err) {
            // Show error inline
        } finally {
            this._showLoading(false);
        }
    },

    /**
     * Re-fetch setup state to refresh dashboard numbers.
     * @param {Object} opts - Options passed to _populateHome
     * @param {boolean} opts.keepExpanded - If true, don't collapse cards
     */
    async _refreshHome(opts) {
        try {
            const response = await this._api('/api/onboarding/init', {
                init_data: this.initData,
                chat_id: this.chatId,
            });
            this.setupState = response.setup_state;
            this._populateHome(opts);

            // If keeping cards expanded, reload data for any currently expanded cards
            if (opts && opts.keepExpanded) {
                const expandedCards = document.querySelectorAll('.home-card-expandable.expanded');
                for (const card of expandedCards) {
                    const cardId = card.id.replace('home-card-', '');
                    this._cardDataLoaded[cardId] = false;
                    await this._loadCardData(cardId);
                }
            }
        } catch (err) {
            // Non-critical
        }
    },

    // ==================== Render Helpers ====================

    _renderDaySummary(daySummary, daysRemaining) {
        const container = document.getElementById('schedule-day-summary');
        if (!container) return;

        if (!daySummary || daySummary.length === 0) {
            container.innerHTML = '<div class="card-body-empty">No scheduled days</div>';
            return;
        }

        let html = '';
        for (const day of daySummary) {
            const date = new Date(day.date + 'T00:00:00');
            const label = this._formatShortDate(date);
            html += '<div class="day-summary-row">' +
                '<span class="day-summary-date">' + this._escapeHtml(label) + '</span>' +
                '<span class="day-summary-count">' + day.count + ' posts</span>' +
                '</div>';
        }

        container.innerHTML = html;
    },

    _renderQueueItems(items) {
        const container = document.getElementById('queue-items-list');
        if (!container) return;

        if (!items || items.length === 0) {
            container.innerHTML = '<div class="card-body-empty">Queue is empty</div>';
            return;
        }

        let html = '';
        for (const item of items) {
            const time = new Date(item.scheduled_for);
            html += '<div class="queue-item-row">' +
                '<div class="item-row-left">' +
                '<div class="item-row-name">' + this._escapeHtml(item.media_name) + '</div>' +
                '<div class="item-row-meta">' + this._escapeHtml(item.category) + '</div>' +
                '</div>' +
                '<div class="item-row-right">' +
                '<div class="item-row-time">' + this._formatRelativeTime(time) + '</div>' +
                '</div>' +
                '</div>';
        }

        container.innerHTML = html;
    },

    _renderHistoryItems(items) {
        const container = document.getElementById('history-items-list');
        if (!container) return;

        if (!items || items.length === 0) {
            container.innerHTML = '<div class="card-body-empty">No posting history</div>';
            return;
        }

        let html = '';
        for (const item of items) {
            const time = new Date(item.posted_at);
            const statusClass = 'status-' + (item.status || 'posted');
            html += '<div class="history-item-row">' +
                '<div class="item-row-left">' +
                '<div class="item-row-name">' + this._escapeHtml(item.media_name) + '</div>' +
                '<div class="item-row-meta">' + this._escapeHtml(item.category) +
                ' \u00B7 ' + this._escapeHtml(item.posting_method === 'instagram_api' ? 'API' : 'Manual') +
                '</div>' +
                '</div>' +
                '<div class="item-row-right">' +
                '<span class="item-row-status ' + statusClass + '">' +
                this._escapeHtml(item.status || 'posted') + '</span>' +
                '<div class="item-row-time">' + this._formatRelativeTime(time) + '</div>' +
                '</div>' +
                '</div>';
        }

        container.innerHTML = html;
    },

    _renderCategoryBreakdown(categories, totalActive) {
        const container = document.getElementById('media-category-list');
        if (!container) return;

        if (!categories || categories.length === 0) {
            container.innerHTML = '<div class="card-body-empty">No media indexed</div>';
            return;
        }

        const maxCount = categories[0].count;
        let html = '';
        for (const cat of categories) {
            const pct = maxCount > 0 ? Math.round((cat.count / maxCount) * 100) : 0;
            html += '<div class="category-row">' +
                '<span class="category-name">' + this._escapeHtml(cat.name) + '</span>' +
                '<div class="category-bar-wrap">' +
                '<div class="category-bar" style="width:' + pct + '%"></div>' +
                '</div>' +
                '<span class="category-count">' + cat.count + '</span>' +
                '</div>';
        }

        container.innerHTML = html;
    },

    /**
     * Enter edit mode for a section — jumps to the wizard step
     * with "Save & Return" shown instead of "Next"/"Skip".
     */
    editSection(section) {
        this.editingFrom = true;
        this.mode = 'wizard';
        this.goToStep(section);
    },

    /**
     * Return from edit mode to the home screen.
     * Re-fetches state to get latest data, then shows home.
     */
    async returnToHome() {
        this.editingFrom = false;
        this.mode = 'home';

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

        // Resume from saved step if available
        const step = this.setupState.onboarding_step;
        if (step && document.getElementById('step-' + step)) {
            this.goToStep(step);
            return;
        }

        // Default: start from the beginning
        this.goToStep('welcome');
    },

    /**
     * Update connection status indicators.
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
        if (s.gdrive_connected) {
            gdStatus.innerHTML =
                '<div class="status-icon status-connected">&#9679;</div>' +
                '<span>Connected: ' + this._escapeHtml(s.gdrive_email || '') + '</span>';
            document.getElementById('btn-connect-gdrive').textContent = 'Connected';
            document.getElementById('btn-connect-gdrive').disabled = true;
        }

        // Media folder
        if (s.media_folder_configured) {
            const folderUrlInput = document.getElementById('folder-url');
            if (folderUrlInput && s.media_folder_id) {
                folderUrlInput.value = 'https://drive.google.com/drive/folders/' + s.media_folder_id;
            }
        }
    },

    /**
     * Populate the summary step.
     */
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

    _formatRelativeTime(date) {
        const now = new Date();
        const diffMs = now - date;
        const absDiffMs = Math.abs(diffMs);
        const isFuture = diffMs < 0;

        const minutes = Math.floor(absDiffMs / (1000 * 60));
        const hours = Math.floor(absDiffMs / (1000 * 60 * 60));
        const days = Math.floor(absDiffMs / (1000 * 60 * 60 * 24));

        if (minutes < 1) return isFuture ? 'now' : 'just now';
        if (minutes < 60) return isFuture ? 'in ' + minutes + 'm' : minutes + 'm ago';
        if (hours < 24) return isFuture ? 'in ' + hours + 'h' : hours + 'h ago';
        if (days < 7) return isFuture ? 'in ' + days + 'd' : days + 'd ago';

        return this._formatShortDate(date);
    },

    _formatShortDate(date) {
        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
            'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        return months[date.getMonth()] + ' ' + date.getDate();
    },
};

// Start the app when DOM is ready
document.addEventListener('DOMContentLoaded', () => App.init());
