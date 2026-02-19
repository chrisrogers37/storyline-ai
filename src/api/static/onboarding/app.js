/**
 * Storyline AI Onboarding Mini App
 *
 * Telegram WebApp SDK integration for guided setup wizard.
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

    // --- Private methods ---

    /**
     * Determine which step to show based on current state.
     */
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

    /**
     * Update connection status indicators.
     */
    _updateStatusIndicators() {
        const s = this.setupState;

        // Instagram
        const igStatus = document.getElementById('instagram-status');
        if (s.instagram_connected) {
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

                    // Auto-advance to next step
                    if (provider === 'instagram') {
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
