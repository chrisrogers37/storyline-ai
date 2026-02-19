# Phase 01: Per-Chat Media Source Configuration (Database Migration + Service Plumbing)

**Status:** 🔧 IN PROGRESS
**Started:** 2026-02-19

## 1. Header

**PR Title:** `feat: add per-chat media_source_type and media_source_root to chat_settings`

**Risk Level:** Low

**Estimated Effort:** Small (1-2 hours of focused work)

**Files Created:**
- `scripts/migrations/017_add_media_source_to_chat_settings.sql`

**Files Modified:**
- `src/models/chat_settings.py`
- `src/services/core/settings_service.py`
- `src/services/core/media_sync.py`
- `src/api/routes/onboarding.py`
- `tests/src/services/test_settings_service.py`
- `tests/src/services/test_media_sync.py`
- `tests/src/services/test_telegram_settings.py`
- `tests/src/services/test_telegram_accounts.py`
- `CHANGELOG.md`

**Files Deleted:** None

---

## 2. Context

Currently, `MEDIA_SOURCE_TYPE` and `MEDIA_SOURCE_ROOT` are global environment variables defined in `src/config/settings.py` (lines 74-75). This means every tenant (every Telegram chat) shares the same media source. In a multi-tenant world, different chats need different Google Drive folders or different local paths.

This phase adds two nullable columns to the `chat_settings` table: `media_source_type` and `media_source_root`. When these are `NULL`, the system falls back to the global `.env` values (backward compatible). When set, the system uses the per-chat values. This unblocks the onboarding flow (which already has a TODO at `src/api/routes/onboarding.py` line 221) and future phases where each chat picks its own media folder.

---

## 3. Dependencies

**Prerequisites:** None. This is Phase 01; it has no dependencies.

**What this unlocks:** Phases 02, 03, 04, and 05 all depend on this phase. Specifically:
- The onboarding flow can store the selected Google Drive folder ID per chat
- The `/sync` command can read per-chat media configuration
- The scheduled sync loop can iterate over chats and sync each one independently
- The health check can verify per-chat provider connectivity

---

## 4. Detailed Implementation Plan

### Step 1: Create the Database Migration

**New file:** `scripts/migrations/017_add_media_source_to_chat_settings.sql`

Follow the exact pattern established in `scripts/migrations/016_chat_settings_onboarding.sql`.

**Content:**

```sql
BEGIN;

-- Add per-chat media source configuration columns
-- NULL = use global env var fallback (backward compatible)
ALTER TABLE chat_settings
    ADD COLUMN IF NOT EXISTS media_source_type VARCHAR(50) DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS media_source_root TEXT DEFAULT NULL;

-- No backfill needed: NULL means "use global env var"
-- Existing chats continue to use MEDIA_SOURCE_TYPE / MEDIA_SOURCE_ROOT from .env

INSERT INTO schema_version (version, description, applied_at)
VALUES (17, 'Add media_source_type and media_source_root to chat_settings', NOW());

COMMIT;
```

**Why VARCHAR(50) for `media_source_type`:** Matches the existing pattern for `onboarding_step` which is also `VARCHAR(50)`. Valid values are short strings like `"local"` or `"google_drive"`.

**Why TEXT for `media_source_root`:** Google Drive folder IDs are 33+ characters and local paths can be arbitrarily long. `TEXT` avoids artificial limits.

**Why DEFAULT NULL (not DEFAULT ''):** `NULL` has explicit semantic meaning here: "not configured, use env var fallback." An empty string would be ambiguous.

### Step 2: Update the SQLAlchemy Model

**File:** `src/models/chat_settings.py`

**Before** (lines 51-53):

```python
    # Media sync (Phase 04 Cloud Media)
    media_sync_enabled = Column(Boolean, default=False)
```

**After:**

```python
    # Media sync (Phase 04 Cloud Media)
    media_sync_enabled = Column(Boolean, default=False)

    # Per-chat media source configuration (NULL = use global env var fallback)
    media_source_type = Column(String(50), nullable=True)  # 'local' or 'google_drive'
    media_source_root = Column(Text, nullable=True)  # path (local) or folder ID (google_drive)
```

Also add `Text` to the SQLAlchemy import at the top of the file.

**Before** (lines 2-11):

```python
from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    BigInteger,
    DateTime,
    ForeignKey,
)
```

**After:**

```python
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Boolean,
    BigInteger,
    DateTime,
    ForeignKey,
)
```

### Step 3: Update SettingsService

**File:** `src/services/core/settings_service.py`

Three changes in this file:

#### 3a. Add a new constant for text/string settings

**After** line 26 (the `NUMERIC_SETTINGS` definition), add:

```python
TEXT_SETTINGS = {"media_source_type", "media_source_root"}
```

#### 3b. Update `update_setting()` to accept text settings

**Before** (line 132):

```python
        if setting_name not in TOGGLEABLE_SETTINGS | NUMERIC_SETTINGS:
            raise ValueError(f"Unknown setting: {setting_name}")
```

**After:**

```python
        if setting_name not in TOGGLEABLE_SETTINGS | NUMERIC_SETTINGS | TEXT_SETTINGS:
            raise ValueError(f"Unknown setting: {setting_name}")
```

Also add validation for `media_source_type` inside the method. After the existing `posting_hours_start/end` validation block (around line 156), add:

```python
            elif setting_name == "media_source_type":
                if value is not None and value not in ("local", "google_drive"):
                    raise ValueError(
                        "media_source_type must be 'local', 'google_drive', or None"
                    )
```

This goes right before the `updated = self.settings_repo.update(...)` call.

#### 3c. Update `get_settings_display()` to include new fields

**Before** (lines 187-199):

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

**After:**

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
            "media_source_type": settings.media_source_type,
            "media_source_root": settings.media_source_root,
            "updated_at": settings.updated_at,
        }
```

#### 3d. Add `get_media_source_config()` method

Add this new method after `get_settings_display()` and before `set_onboarding_step()`:

```python
    def get_media_source_config(
        self, telegram_chat_id: int
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Get resolved media source configuration for a chat.

        Resolution order:
        1. Per-chat value from chat_settings (if not NULL)
        2. Global env var fallback

        Args:
            telegram_chat_id: Telegram chat/channel ID

        Returns:
            Tuple of (source_type, source_root)
        """
        from src.config.settings import settings as env_settings

        chat_settings = self.get_settings(telegram_chat_id)

        source_type = chat_settings.media_source_type or env_settings.MEDIA_SOURCE_TYPE
        source_root = chat_settings.media_source_root or env_settings.MEDIA_SOURCE_ROOT

        return source_type, source_root
```

The `from src.config.settings import settings as env_settings` is a local import to avoid adding a new top-level import. The file currently does NOT import settings globally, which is by design.

### Step 4: Update MediaSyncService

**File:** `src/services/core/media_sync.py`

#### 4a. Update `sync()` method signature and resolution logic

**Before** (lines 81-101):

```python
    def sync(
        self,
        source_type: Optional[str] = None,
        source_root: Optional[str] = None,
        triggered_by: str = "system",
    ) -> SyncResult:
        """..."""
        resolved_source_type = source_type or settings.MEDIA_SOURCE_TYPE
        resolved_source_root = source_root or settings.MEDIA_SOURCE_ROOT
```

**After:**

```python
    def sync(
        self,
        source_type: Optional[str] = None,
        source_root: Optional[str] = None,
        triggered_by: str = "system",
        telegram_chat_id: Optional[int] = None,
    ) -> SyncResult:
        """Run a full media sync against the configured provider.

        Args:
            source_type: Override settings.MEDIA_SOURCE_TYPE
            source_root: Override settings.MEDIA_SOURCE_ROOT
            triggered_by: Who triggered ('system', 'cli', 'scheduler')
            telegram_chat_id: If provided, look up per-chat media source config

        Returns:
            SyncResult with counts for each action taken

        Raises:
            ValueError: If provider is not configured or source_type is invalid
        """
        # Resolution order: explicit params > per-chat DB config > global env vars
        if not source_type and not source_root and telegram_chat_id:
            from src.services.core.settings_service import SettingsService

            settings_service = SettingsService()
            try:
                source_type, source_root = settings_service.get_media_source_config(
                    telegram_chat_id
                )
            finally:
                settings_service.close()

        resolved_source_type = source_type or settings.MEDIA_SOURCE_TYPE
        resolved_source_root = source_root or settings.MEDIA_SOURCE_ROOT
```

**Key design decisions:**
- Explicit `source_type`/`source_root` parameters still take highest priority (for CLI overrides)
- The per-chat lookup only fires when `telegram_chat_id` is provided AND no explicit overrides are given
- The `SettingsService` is imported locally and properly closed to avoid import cycles and connection leaks

#### 4b. Update `_create_provider()` to accept per-chat telegram_chat_id

**Before** (lines 289-300):

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

**After:**

```python
    def _create_provider(
        self, source_type: str, source_root: str, telegram_chat_id: Optional[int] = None
    ):
        """Create a MediaSourceProvider based on source type and root."""
        if source_type == "local":
            return MediaSourceFactory.create(source_type, base_path=source_root)
        elif source_type == "google_drive":
            chat_id = telegram_chat_id or settings.TELEGRAM_CHANNEL_ID
            return MediaSourceFactory.create(
                source_type,
                root_folder_id=source_root,
                telegram_chat_id=chat_id,
            )
        else:
            return MediaSourceFactory.create(source_type)
```

And update the call site within `sync()` (currently line 118):

**Before:**

```python
            provider = self._create_provider(resolved_source_type, resolved_source_root)
```

**After:**

```python
            provider = self._create_provider(
                resolved_source_type, resolved_source_root, telegram_chat_id
            )
```

### Step 5: Resolve the TODO in Onboarding API

**File:** `src/api/routes/onboarding.py`

**Before** (lines 221-227):

```python
    # TODO: Store folder_id in chat_settings when media_source_root column exists

    return {
        "folder_id": folder_id,
        "file_count": file_count,
        "categories": sorted(categories),
    }
```

**After:**

```python
    # Store folder_id and source type in per-chat settings
    settings_service = SettingsService()
    try:
        settings_service.update_setting(
            request.chat_id, "media_source_type", "google_drive"
        )
        settings_service.update_setting(
            request.chat_id, "media_source_root", folder_id
        )
    finally:
        settings_service.close()

    return {
        "folder_id": folder_id,
        "file_count": file_count,
        "categories": sorted(categories),
    }
```

The `SettingsService` is already imported at line 11 of this file, so no new import is needed.

---

## 5. Test Plan

### 5a. New tests in `tests/src/services/test_settings_service.py`

Add `TEXT_SETTINGS` to the existing import:

```python
from src.services.core.settings_service import (
    SettingsService,
    TOGGLEABLE_SETTINGS,
    NUMERIC_SETTINGS,
    TEXT_SETTINGS,
)
```

**New test class** (add after `TestSettingsServiceOnboarding`):

```python
@pytest.mark.unit
class TestSettingsServiceMediaSource:
    """Tests for per-chat media source configuration."""

    @pytest.fixture
    def settings_service(self):
        """Create SettingsService with mocked repository."""
        with patch.object(SettingsService, "__init__", lambda self: None):
            service = SettingsService()
            service.settings_repo = Mock()
            return service

    def test_text_settings_defined(self):
        """TEXT_SETTINGS contains media source settings."""
        assert "media_source_type" in TEXT_SETTINGS
        assert "media_source_root" in TEXT_SETTINGS

    def test_update_media_source_type_valid(self, settings_service):
        """Can update media_source_type to a valid value."""
        mock_settings = Mock(spec=ChatSettings)
        mock_settings.media_source_type = None
        settings_service.settings_repo.get_or_create.return_value = mock_settings
        settings_service.settings_repo.update.return_value = mock_settings
        settings_service.service_run_repo = Mock()
        settings_service.service_run_repo.create_run.return_value = str(uuid4())

        settings_service.update_setting(-100, "media_source_type", "google_drive")

        settings_service.settings_repo.update.assert_called_once()
        call_kwargs = settings_service.settings_repo.update.call_args[1]
        assert call_kwargs["media_source_type"] == "google_drive"

    def test_update_media_source_type_invalid_raises(self, settings_service):
        """Invalid media_source_type value raises ValueError."""
        mock_settings = Mock(spec=ChatSettings)
        mock_settings.media_source_type = None
        settings_service.settings_repo.get_or_create.return_value = mock_settings
        settings_service.service_run_repo = Mock()
        settings_service.service_run_repo.create_run.return_value = str(uuid4())

        with pytest.raises(ValueError, match="media_source_type must be"):
            settings_service.update_setting(-100, "media_source_type", "dropbox")

    def test_update_media_source_type_none_allowed(self, settings_service):
        """Setting media_source_type to None is valid (clears override)."""
        mock_settings = Mock(spec=ChatSettings)
        mock_settings.media_source_type = "google_drive"
        settings_service.settings_repo.get_or_create.return_value = mock_settings
        settings_service.settings_repo.update.return_value = mock_settings
        settings_service.service_run_repo = Mock()
        settings_service.service_run_repo.create_run.return_value = str(uuid4())

        settings_service.update_setting(-100, "media_source_type", None)

        settings_service.settings_repo.update.assert_called_once()

    @patch("src.services.core.settings_service.settings", create=True)
    def test_get_media_source_config_uses_per_chat_values(self, mock_env, settings_service):
        """Per-chat values take priority over env vars."""
        mock_env.MEDIA_SOURCE_TYPE = "local"
        mock_env.MEDIA_SOURCE_ROOT = "/default/path"

        mock_settings = Mock(spec=ChatSettings)
        mock_settings.media_source_type = "google_drive"
        mock_settings.media_source_root = "folder_abc"
        settings_service.settings_repo.get_or_create.return_value = mock_settings

        source_type, source_root = settings_service.get_media_source_config(-100)

        assert source_type == "google_drive"
        assert source_root == "folder_abc"

    @patch("src.services.core.settings_service.settings", create=True)
    def test_get_media_source_config_falls_back_to_env(self, mock_env, settings_service):
        """NULL per-chat values fall back to env vars."""
        mock_env.MEDIA_SOURCE_TYPE = "local"
        mock_env.MEDIA_SOURCE_ROOT = "/env/path"

        mock_settings = Mock(spec=ChatSettings)
        mock_settings.media_source_type = None
        mock_settings.media_source_root = None
        settings_service.settings_repo.get_or_create.return_value = mock_settings

        source_type, source_root = settings_service.get_media_source_config(-100)

        assert source_type == "local"
        assert source_root == "/env/path"

    @patch("src.services.core.settings_service.settings", create=True)
    def test_get_media_source_config_partial_override(self, mock_env, settings_service):
        """One per-chat value set, the other NULL -- mixed resolution."""
        mock_env.MEDIA_SOURCE_TYPE = "local"
        mock_env.MEDIA_SOURCE_ROOT = "/default"

        mock_settings = Mock(spec=ChatSettings)
        mock_settings.media_source_type = "google_drive"
        mock_settings.media_source_root = None
        settings_service.settings_repo.get_or_create.return_value = mock_settings

        source_type, source_root = settings_service.get_media_source_config(-100)

        assert source_type == "google_drive"
        assert source_root == "/default"

    def test_get_settings_display_includes_media_source_fields(self, settings_service):
        """get_settings_display includes media_source_type and media_source_root."""
        mock_settings = Mock(spec=ChatSettings)
        mock_settings.dry_run_mode = False
        mock_settings.enable_instagram_api = False
        mock_settings.is_paused = False
        mock_settings.paused_at = None
        mock_settings.paused_by_user_id = None
        mock_settings.posts_per_day = 3
        mock_settings.posting_hours_start = 14
        mock_settings.posting_hours_end = 2
        mock_settings.show_verbose_notifications = True
        mock_settings.media_sync_enabled = False
        mock_settings.media_source_type = "google_drive"
        mock_settings.media_source_root = "folder_123"
        mock_settings.updated_at = datetime.utcnow()

        settings_service.settings_repo.get_or_create.return_value = mock_settings

        display = settings_service.get_settings_display(-100)

        assert display["media_source_type"] == "google_drive"
        assert display["media_source_root"] == "folder_123"
```

### 5b. New tests in `tests/src/services/test_media_sync.py`

```python
    @patch("src.services.core.media_sync.settings")
    @patch("src.services.core.media_sync.MediaSourceFactory")
    def test_sync_with_telegram_chat_id_reads_per_chat_config(
        self, mock_factory, mock_settings, sync_service
    ):
        """When telegram_chat_id is provided, reads per-chat config via SettingsService."""
        mock_settings.MEDIA_SOURCE_TYPE = "local"
        mock_settings.MEDIA_SOURCE_ROOT = "/default"
        mock_settings.MEDIA_DIR = "/media"
        mock_settings.TELEGRAM_CHANNEL_ID = -100123456789

        mock_provider = Mock()
        mock_factory.create.return_value = mock_provider
        mock_provider.is_configured.return_value = True
        mock_provider.list_files.return_value = []
        sync_service.media_repo.get_active_by_source_type.return_value = []

        with patch("src.services.core.media_sync.SettingsService") as MockSettingsSvc:
            mock_svc_instance = MockSettingsSvc.return_value
            mock_svc_instance.get_media_source_config.return_value = (
                "google_drive",
                "per_chat_folder",
            )

            sync_service.sync(triggered_by="scheduler", telegram_chat_id=-100999)

        mock_svc_instance.get_media_source_config.assert_called_once_with(-100999)
        mock_svc_instance.close.assert_called_once()

    @patch("src.services.core.media_sync.settings")
    @patch("src.services.core.media_sync.MediaSourceFactory")
    def test_sync_explicit_params_override_per_chat_config(
        self, mock_factory, mock_settings, sync_service
    ):
        """Explicit source_type/source_root params override per-chat config."""
        mock_settings.MEDIA_SOURCE_TYPE = "local"
        mock_settings.MEDIA_SOURCE_ROOT = "/default"
        mock_settings.MEDIA_DIR = "/media"

        mock_provider = Mock()
        mock_factory.create.return_value = mock_provider
        mock_provider.is_configured.return_value = True
        mock_provider.list_files.return_value = []
        sync_service.media_repo.get_active_by_source_type.return_value = []

        sync_service.sync(
            source_type="local",
            source_root="/explicit/path",
            telegram_chat_id=-100999,
        )

        mock_factory.create.assert_called_once_with("local", base_path="/explicit/path")
```

### 5c. Update `get_settings_display` mocks in test files

In every location where `get_settings_display.return_value = {` appears, add the two new keys after `"media_sync_enabled"`:

```python
            "media_source_type": None,
            "media_source_root": None,
```

**Files to update:**
1. `tests/src/services/test_telegram_settings.py` — 10 occurrences
2. `tests/src/services/test_telegram_accounts.py` — 1 occurrence

---

## 6. Documentation Updates

### CHANGELOG.md

Add under `## [Unreleased]`, in the `### Added` section:

```markdown
### Added

- **Per-chat media source configuration** - `media_source_type` and `media_source_root` columns on `chat_settings` table
  - Enables each Telegram chat to have its own media source (local path or Google Drive folder ID)
  - `NULL` values fall back to global `MEDIA_SOURCE_TYPE` / `MEDIA_SOURCE_ROOT` env vars (backward compatible)
  - New `SettingsService.get_media_source_config()` method resolves per-chat config with env var fallback
  - `MediaSyncService.sync()` now accepts `telegram_chat_id` parameter for per-chat sync
  - Onboarding media-folder endpoint now saves selected folder to chat settings
  - Migration: `scripts/migrations/017_add_media_source_to_chat_settings.sql`
```

---

## 7. Stress Testing and Edge Cases

### NULL handling

- **Both columns NULL:** System falls back to `MEDIA_SOURCE_TYPE` and `MEDIA_SOURCE_ROOT` from `.env`. This is the default for all existing rows. No backfill migration is needed.
- **One column NULL, the other set:** `get_media_source_config()` resolves each independently. For example, if `media_source_type = "google_drive"` but `media_source_root = NULL`, it resolves to `("google_drive", <env var value>)`. This is a valid intermediate state.
- **Both columns set to empty string `""`:** The `or` operator in `get_media_source_config()` treats `""` as falsy, falling back to the env var. This is acceptable behavior.

### Backward compatibility

- **Existing data:** All existing `chat_settings` rows get `NULL` for both new columns. No behavioral change.
- **Existing `sync()` callers that do not pass `telegram_chat_id`:** Work identically to before.
- **`update_setting()` validation gate:** Now accepts `TEXT_SETTINGS` in addition to `TOGGLEABLE_SETTINGS | NUMERIC_SETTINGS`. This is a new capability, not a breaking change.

### Concurrent writes

- Two concurrent writes to different columns will both succeed because SQLAlchemy generates `SET column = value` for only the changed columns. Two concurrent writes to the SAME column will last-write-wins, which is acceptable for settings.

### Provider not configured

- If a chat sets `media_source_type = "google_drive"` but has no OAuth tokens, `provider.is_configured()` returns `False` and raises a clear `ValueError`. Existing behavior, unaffected.

---

## 8. Verification Checklist

```bash
# 1. Activate virtual environment
source venv/bin/activate

# 2. Lint check
ruff check src/ tests/ cli/

# 3. Format check
ruff format --check src/ tests/ cli/

# 4. Run full test suite
pytest

# 5. Run specific test files changed in this phase
pytest tests/src/services/test_settings_service.py -v
pytest tests/src/services/test_media_sync.py -v
pytest tests/src/services/test_telegram_settings.py -v
pytest tests/src/services/test_telegram_accounts.py -v
pytest tests/src/api/test_onboarding_routes.py -v

# 6. Verify model imports correctly
python -c "from src.models.chat_settings import ChatSettings; print('OK')"

# 7. Verify new method exists
python -c "from src.services.core.settings_service import SettingsService, TEXT_SETTINGS; print(TEXT_SETTINGS)"
```

---

## 9. "What NOT To Do"

1. **Do NOT backfill existing rows with env var values.** Leave `media_source_type` and `media_source_root` as `NULL`. Setting them would "cement" the current env var values into the database, making future env var changes ineffective for those chats.

2. **Do NOT add `media_source_type` or `media_source_root` to `TOGGLEABLE_SETTINGS`.** These are not booleans. They belong in `TEXT_SETTINGS`.

3. **Do NOT add these columns to the `get_or_create()` bootstrap in `ChatSettingsRepository`.** The `get_or_create()` method bootstraps from `.env` values. But `media_source_type` and `media_source_root` should remain `NULL` until explicitly set by the user via onboarding. The fallback logic lives in `SettingsService.get_media_source_config()`, not in the repository.

4. **Do NOT add UI buttons for these settings in `telegram_settings.py` in this phase.** That is a future phase concern.

5. **Do NOT modify `src/main.py` media_sync_loop yet.** Making it iterate over all active chats is a future phase concern. This phase just adds the `telegram_chat_id` parameter.

6. **Do NOT forget to update the mock dictionaries in test files.** The MEMORY.md explicitly warns: "When adding keys to `get_settings_display()`, update ALL test files that mock it (telegram_settings, telegram_accounts)."

7. **Do NOT use `settings` as a local variable name in `get_media_source_config()`.** Use `env_settings` as the local import alias to avoid shadowing.

8. **Do NOT add the `Text` import to `chat_settings.py` on a separate line.** Keep it inside the existing `from sqlalchemy import (...)` block.
