# Phase 06: Remaining Large File Splits

**Status**: ✅ COMPLETE
**Started**: 2026-02-28
**Completed**: 2026-02-28
**PR**: #92
**PR Title**: Extract wizard, downloader, and credential manager from large files
**Risk Level**: Low
**Estimated Effort**: Medium (2-3 hours)
**Files Modified**: 6 existing + 3 new
**Dependencies**: None
**Blocks**: None

---

## Context

Three files exceed 680 lines with clear natural splitting points:
- `telegram_accounts.py` (720 lines) — wizard + removal + handlers
- `instagram_backfill.py` (698 lines) — orchestration + download + API client
- `instagram_api.py` (686 lines) — publishing + credentials + rate limiting

Each file has 2-3 distinct responsibilities that can be cleanly extracted.

---

## Implementation Plan

### Extraction 1: TelegramAccountWizard from telegram_accounts.py

**New file**: `src/services/core/telegram_account_wizard.py` (~215 lines)

Extract the multi-step add-account wizard:

| Method | Lines | Purpose |
|--------|-------|---------|
| `handle_add_account_start()` | 87-119 | Init wizard state, show Step 1 |
| `handle_add_account_message()` | 121-139 | Dispatch to step handlers |
| `handle_add_account_cancel()` | 141-155 | Clean up, reset state |
| `_handle_display_name_input()` | 161-181 | Step 1 — collect display name |
| `_handle_account_id_input()` | 183-212 | Step 2 — validate numeric ID |
| `_handle_token_input()` | 214-301 | Step 3 — validate token with API |
| `_validate_instagram_credentials()` | 307-361 | API call, create/update account |
| `_handle_token_error()` | 363-402 | Error recovery options |

**Structure**:
```python
# src/services/core/telegram_account_wizard.py

class TelegramAccountWizard:
    """Multi-step wizard for adding Instagram accounts via Telegram."""

    def __init__(self, accounts_handler):
        """
        Args:
            accounts_handler: Parent TelegramAccountHandlers for access
                to service, repos, and settings.
        """
        self.handler = accounts_handler
        self.service = accounts_handler.service
```

**Wire up** in `telegram_accounts.py`:
```python
from src.services.core.telegram_account_wizard import TelegramAccountWizard

class TelegramAccountHandlers:
    def __init__(self, service):
        self.service = service
        self.wizard = TelegramAccountWizard(self)

    # Delegation methods:
    async def handle_add_account_start(self, ...):
        return await self.wizard.handle_add_account_start(...)

    async def handle_add_account_message(self, ...):
        return await self.wizard.handle_add_account_message(...)

    async def handle_add_account_cancel(self, ...):
        return await self.wizard.handle_add_account_cancel(...)
```

**Result**: `telegram_accounts.py` drops from 720 to ~505 lines.

---

### Extraction 2: BackfillDownloader from instagram_backfill.py

**New file**: `src/services/integrations/backfill_downloader.py` (~200 lines)

Extract download, storage, and API client methods:

| Method | Lines | Purpose |
|--------|-------|---------|
| `_process_carousel()` | 428-458 | Expand carousel children recursively |
| `_download_and_index()` | 459-516 | Download, hash, store, index |
| `_fetch_media_page()` | 519-543 | GET /media API |
| `_fetch_stories()` | 545-564 | GET /stories API |
| `_fetch_carousel_children()` | 566-585 | GET /children API |
| `_download_media()` | 587-635 | Download with expiry detection |
| `_get_storage_dir()` | 639-641 | Resolve path |
| `_get_extension_for_type()` | 643-655 | Determine extension |
| `_is_after_date()` | 657-671 | Timestamp comparison |

**Structure**:
```python
# src/services/integrations/backfill_downloader.py

class BackfillDownloader:
    """Handles media downloading, storage, and Instagram API calls for backfill."""

    def __init__(self, backfill_service):
        """
        Args:
            backfill_service: Parent InstagramBackfillService for access
                to httpx client, repos, and config.
        """
        self.service = backfill_service
```

**Wire up** in `instagram_backfill.py`:
```python
from src.services.integrations.backfill_downloader import BackfillDownloader

class InstagramBackfillService(BaseService):
    def __init__(self):
        super().__init__()
        self.downloader = BackfillDownloader(self)
```

Methods in the parent that call extracted methods will delegate:
```python
# In _process_media_item, replace:
#   await self._download_and_index(item, context)
# with:
#   await self.downloader.download_and_index(item, context)
```

**Result**: `instagram_backfill.py` drops from 698 to ~350 lines.

---

### Extraction 3: InstagramCredentialManager from instagram_api.py

**New file**: `src/services/integrations/instagram_credentials.py` (~150 lines)

Extract credential management and validation:

| Method | Lines | Purpose |
|--------|-------|---------|
| `_get_active_account_credentials()` | 63-115 | Multi-account + .env fallback |
| `is_configured()` | 458-482 | Check API enabled |
| `validate_instagram_account_id()` | 484-527 | Format validation |
| `get_account_info()` | 532-605 | Fetch/cache account info (includes `_account_info_cache` class var) |
| `validate_media_url()` | 423-456 | HEAD request validation |
| `safety_check_before_post()` | 607-685 | Comprehensive pre-post checks |

**Structure**:
```python
# src/services/integrations/instagram_credentials.py

class InstagramCredentialManager:
    """Manages Instagram API credentials, validation, and safety checks."""

    def __init__(self, api_service):
        """
        Args:
            api_service: Parent InstagramAPIService for access to
                token service, account service, and settings.
        """
        self.service = api_service
```

**Wire up** in `instagram_api.py`:
```python
from src.services.integrations.instagram_credentials import InstagramCredentialManager

class InstagramAPIService(BaseService):
    def __init__(self):
        super().__init__()
        self.credentials = InstagramCredentialManager(self)
```

**Delegation methods** in `InstagramAPIService` preserve the public API:
```python
def is_configured(self):
    return self.credentials.is_configured()

def validate_instagram_account_id(self, account_id):
    return self.credentials.validate_instagram_account_id(account_id)

# etc.
```

**Result**: `instagram_api.py` drops from 686 to ~400 lines (publishing core + rate limiting).

---

## Test Plan

### For each extraction:

```bash
# 1. Create test file for extracted class
# tests/src/services/test_telegram_account_wizard.py
# tests/src/services/test_backfill_downloader.py
# tests/src/services/test_instagram_credentials.py

# 2. Move relevant tests from parent test files to new files

# 3. Run new test files
pytest tests/src/services/test_telegram_account_wizard.py -v
pytest tests/src/services/test_backfill_downloader.py -v
pytest tests/src/services/test_instagram_credentials.py -v

# 4. Run parent test files (delegation should pass)
pytest tests/src/services/test_telegram_accounts.py -v
pytest tests/src/services/test_instagram_backfill.py -v
pytest tests/src/services/test_instagram_api.py -v

# 5. Full suite
pytest

# 6. Lint
ruff check src/ tests/ && ruff format --check src/ tests/
```

### Test structure for extracted classes:

```python
# Example: test_telegram_account_wizard.py
@pytest.fixture
def mock_accounts_handler():
    handler = Mock()
    handler.service = Mock()
    handler.service.instagram_account_service = Mock()
    handler.service.settings_service = Mock()
    handler.service.interaction_service = Mock()
    return handler

@pytest.fixture
def wizard(mock_accounts_handler):
    return TelegramAccountWizard(mock_accounts_handler)

class TestHandleAddAccountStart:
    async def test_initializes_wizard_state(self, wizard):
        # Test that wizard state is set up correctly
        pass

class TestHandleTokenInput:
    async def test_valid_token_creates_account(self, wizard):
        # Test successful token validation flow
        pass

    async def test_invalid_token_shows_error(self, wizard):
        # Test error handling for bad tokens
        pass
```

---

## Verification Checklist

- [ ] `telegram_account_wizard.py` created (~215 lines)
- [ ] `backfill_downloader.py` created (~200 lines)
- [ ] `instagram_credentials.py` created (~150 lines)
- [ ] `telegram_accounts.py` reduced from 720 to ~505 lines
- [ ] `instagram_backfill.py` reduced from 698 to ~350 lines
- [ ] `instagram_api.py` reduced from 686 to ~400 lines
- [ ] All delegation methods in parent classes work correctly
- [ ] No circular imports
- [ ] New test files created and passing
- [ ] Existing tests pass (with minimal mock updates)
- [ ] `pytest` passes
- [ ] `ruff check` and `ruff format` pass
- [ ] CHANGELOG.md updated

---

## What NOT To Do

- **Don't extract all three at once without testing** — do one extraction, run tests, then the next
- **Don't change the public API of any parent class** — all external callers must work unchanged
- **Don't make extracted classes extend BaseService** — they're composition components
- **Don't extract `_route_post()` from posting.py** — that's Phase 04 scope
- **Don't extract rate limiting from instagram_api.py** — it's only ~40 lines, not worth the complexity
- **Don't remove delegation methods** — handler modules call `self.service.send_notification()` etc., the delegation layer must stay
- **Don't combine this PR with other phases** — it's already large enough at 3 extractions
