# Phase 01: Tenant Isolation Bypass and OAuth Authentication

| Field | Value |
|-------|-------|
| **PR Title** | `fix: tenant isolation bypass and OAuth authentication` |
| **Severity** | HIGH |
| **Effort** | Medium (4-6 hours) |
| **Risk** | High |
| **Dependencies** | None (can run first) |
| **Unlocks** | None |

## Files Modified

| File | Action |
|------|--------|
| `src/api/routes/onboarding/helpers.py` | Modify `_validate_request()` to reject None `signed_chat_id` |
| `src/api/routes/oauth.py` | Add authentication to `/instagram/start` and `/google-drive/start` |
| `src/api/routes/onboarding/dashboard.py` | Filter `accounts` endpoint by tenant |
| `src/api/routes/onboarding/settings.py` | Add tenant scoping to `remove-account` and `switch-account` |
| `src/services/core/instagram_account_service.py` | Add `telegram_chat_id` param to `deactivate_account()` and `list_accounts()` |
| `src/repositories/instagram_account_repository.py` | Add `get_active_by_chat_ids()` method for tenant-scoped queries |
| `tests/src/api/conftest.py` | Update `mock_validate` default to include `chat_id` |
| `tests/src/api/test_onboarding_routes.py` | Add tenant isolation bypass tests |
| `tests/src/api/test_onboarding_dashboard.py` | Add cross-tenant accounts list test |
| `tests/src/api/test_oauth_routes.py` | Add authentication tests for `/start` endpoints |
| `tests/src/utils/test_webapp_auth.py` | (no changes expected) |
| `CHANGELOG.md` | Add security fix entries under `[Unreleased]` |

## Findings Addressed

- **Finding #1 (HIGH)**: Tenant isolation bypass -- `_validate_request()` skips the chat_id mismatch check when `signed_chat_id` is None (private/DM-opened Mini Apps), allowing any authenticated user to access any tenant's data.
- **Finding #2 (HIGH)**: Unauthenticated OAuth `/start` endpoints -- `/auth/instagram/start` and `/auth/google-drive/start` accept an arbitrary `chat_id` query param with zero authentication, enabling account hijacking.
- **Finding #5 (MEDIUM)**: Cross-tenant account operations -- `remove-account` and `switch-account` don't verify account ownership by tenant; `accounts` list returns ALL system accounts unfiltered.

## Context

The Storyline AI API uses Telegram WebApp initData (HMAC-SHA256) and Fernet-encrypted URL tokens for authentication. The `_validate_request()` function in `helpers.py` is the central auth gate for all 17 onboarding/dashboard/settings routes. It validates the credential and checks that the signed `chat_id` matches the request's `chat_id` -- but ONLY when the signed credential contains a `chat_id`. When Telegram initData comes from a private/DM context, the `chat` field is absent and `signed_chat_id` is None, causing the check to be silently skipped.

Meanwhile, the OAuth `/start` endpoints have no authentication at all. They accept a raw `chat_id` query parameter and immediately generate a state token containing that chat_id, allowing an attacker to complete the OAuth flow and hijack the victim's connected accounts.

Finally, the `accounts` list endpoint returns ALL system accounts across all tenants, and `remove-account`/`switch-account` don't verify that the targeted account belongs to the requesting tenant.

---

## Detailed Implementation Plan

### Step 1: Fix `_validate_request()` to reject None `signed_chat_id` (Finding #1)

**File:** `src/api/routes/onboarding/helpers.py`
**Function:** `_validate_request()` (lines 18-46)

The current code at lines 37-44:

```python
# If auth contains a chat_id, verify it matches the request
signed_chat_id = user_info.get("chat_id")
if signed_chat_id is not None and signed_chat_id != chat_id:
    logger.warning(
        f"Chat ID mismatch: auth has {signed_chat_id}, "
        f"request has {chat_id} (user_id={user_info.get('user_id')})"
    )
    raise HTTPException(status_code=403, detail="Chat ID mismatch")
```

**Problem:** When `signed_chat_id` is `None` (private chat initData with no `chat` field), the entire check is skipped. The request proceeds with whatever `chat_id` the caller specified in the request body.

**Fix:** After the existing mismatch check, add a second check: if `signed_chat_id` is still `None` after both initData and URL token parsing, reject the request. The URL token format (`validate_url_token`) always returns a `chat_id`, so this only rejects initData from private chats where the chat context is ambiguous.

**Replace** lines 37-44 of `src/api/routes/onboarding/helpers.py` with:

```python
    # Verify signed chat_id matches the request
    signed_chat_id = user_info.get("chat_id")
    if signed_chat_id is None:
        logger.warning(
            f"Auth credential has no chat_id — rejecting request for "
            f"chat_id={chat_id} (user_id={user_info.get('user_id')}). "
            f"Use a URL token for browser-based access."
        )
        raise HTTPException(
            status_code=403,
            detail="Authentication credential does not contain a chat ID. "
            "Please open this app from the group chat, not a private message.",
        )
    if signed_chat_id != chat_id:
        logger.warning(
            f"Chat ID mismatch: auth has {signed_chat_id}, "
            f"request has {chat_id} (user_id={user_info.get('user_id')})"
        )
        raise HTTPException(status_code=403, detail="Chat ID mismatch")
```

**Full function after change:**

```python
def _validate_request(init_data: str, chat_id: int) -> dict:
    """Validate initData or URL token, and verify chat_id matches.

    Accepts either Telegram WebApp initData (from Mini App) or a signed
    URL token (from group chat browser links). The init_data field carries
    whichever credential the frontend provides.

    Raises HTTPException on auth failure or chat_id mismatch.
    """
    # Try Telegram initData first, fall back to URL token
    try:
        user_info = validate_init_data(init_data)
    except ValueError:
        # Not valid initData — try URL token format
        try:
            user_info = validate_url_token(init_data)
        except ValueError as e:
            raise HTTPException(status_code=401, detail=str(e))

    # Verify signed chat_id matches the request
    signed_chat_id = user_info.get("chat_id")
    if signed_chat_id is None:
        logger.warning(
            f"Auth credential has no chat_id — rejecting request for "
            f"chat_id={chat_id} (user_id={user_info.get('user_id')}). "
            f"Use a URL token for browser-based access."
        )
        raise HTTPException(
            status_code=403,
            detail="Authentication credential does not contain a chat ID. "
            "Please open this app from the group chat, not a private message.",
        )
    if signed_chat_id != chat_id:
        logger.warning(
            f"Chat ID mismatch: auth has {signed_chat_id}, "
            f"request has {chat_id} (user_id={user_info.get('user_id')})"
        )
        raise HTTPException(status_code=403, detail="Chat ID mismatch")

    return user_info
```

**Why this approach:** The simplest and most secure fix. Private-chat initData fundamentally cannot carry a tenant identifier, so it cannot be trusted for tenant-scoped operations. The URL token format (generated by the bot with `generate_url_token(chat_id, user_id)`) always includes a signed `chat_id` and is the correct fallback for browser-based access. This does NOT break the Mini App -- the Mini App is opened from a group chat (which includes `chat` in initData) or via URL token links.

---

### Step 2: Add authentication to OAuth `/start` endpoints (Finding #2)

**File:** `src/api/routes/oauth.py`
**Functions:** `instagram_oauth_start()` (lines 17-29) and `google_drive_oauth_start()` (lines 185-197)

**Current code** (Instagram, line 17-29):

```python
@router.get("/instagram/start")
async def instagram_oauth_start(
    chat_id: int = Query(..., description="Telegram chat ID initiating the flow"),
):
    """
    Generate Instagram OAuth authorization URL.

    Called when user clicks "Connect Instagram" in Telegram.
    Returns a redirect to Meta's authorization page.
    """
    with OAuthService() as oauth_service, service_error_handler():
        auth_url = oauth_service.generate_authorization_url(chat_id)
        return RedirectResponse(url=auth_url)
```

**Current code** (Google Drive, line 185-197):

```python
@router.get("/google-drive/start")
async def google_drive_oauth_start(
    chat_id: int = Query(..., description="Telegram chat ID initiating the flow"),
):
    """
    Generate Google Drive OAuth authorization URL.

    Called when user clicks "Connect Google Drive" in Telegram.
    Returns a redirect to Google's consent screen.
    """
    with GoogleDriveOAuthService() as gdrive_service, service_error_handler():
        auth_url = gdrive_service.generate_authorization_url(chat_id)
        return RedirectResponse(url=auth_url)
```

**Problem:** Both endpoints accept any `chat_id` with zero authentication. An attacker can call `GET /auth/instagram/start?chat_id=<VICTIM>` to initiate an OAuth flow that, when completed, hijacks the victim's connected Instagram account.

**Fix:** Add a `token` query parameter that must be a valid URL token (signed with the bot token, contains the chat_id). Validate the token and verify the embedded chat_id matches the `chat_id` query parameter. The bot already generates URL tokens via `generate_url_token()` -- we just need to include the token when constructing the OAuth start URL.

First, add the import at the top of `src/api/routes/oauth.py`. After the existing imports on line 12 (`from src.utils.logger import logger`), add:

```python
from src.utils.webapp_auth import validate_url_token
```

**Replace** `instagram_oauth_start` (lines 17-29) with:

```python
@router.get("/instagram/start")
async def instagram_oauth_start(
    chat_id: int = Query(..., description="Telegram chat ID initiating the flow"),
    token: str = Query(..., description="Signed URL token for authentication"),
):
    """
    Generate Instagram OAuth authorization URL.

    Called when user clicks "Connect Instagram" in Telegram.
    Requires a signed URL token to prove the request originated from
    a legitimate Telegram interaction.
    Returns a redirect to Meta's authorization page.
    """
    # Validate the signed token and verify chat_id matches
    try:
        token_info = validate_url_token(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    if token_info["chat_id"] != chat_id:
        raise HTTPException(status_code=403, detail="Chat ID mismatch")

    with OAuthService() as oauth_service, service_error_handler():
        auth_url = oauth_service.generate_authorization_url(chat_id)
        return RedirectResponse(url=auth_url)
```

**Replace** `google_drive_oauth_start` (lines 185-197) with:

```python
@router.get("/google-drive/start")
async def google_drive_oauth_start(
    chat_id: int = Query(..., description="Telegram chat ID initiating the flow"),
    token: str = Query(..., description="Signed URL token for authentication"),
):
    """
    Generate Google Drive OAuth authorization URL.

    Called when user clicks "Connect Google Drive" in Telegram.
    Requires a signed URL token to prove the request originated from
    a legitimate Telegram interaction.
    Returns a redirect to Google's consent screen.
    """
    # Validate the signed token and verify chat_id matches
    try:
        token_info = validate_url_token(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    if token_info["chat_id"] != chat_id:
        raise HTTPException(status_code=403, detail="Chat ID mismatch")

    with GoogleDriveOAuthService() as gdrive_service, service_error_handler():
        auth_url = gdrive_service.generate_authorization_url(chat_id)
        return RedirectResponse(url=auth_url)
```

Also add the import for `HTTPException` which is already imported on line 5 -- no change needed there.

**Bot-side update required:** The Telegram bot code that generates the "Connect Instagram" / "Connect Google Drive" URLs must be updated to include the `token` query parameter. Search for where the OAuth start URLs are constructed:

```bash
grep -rn "instagram/start" src/ --include="*.py" | grep -v __pycache__ | grep -v test
grep -rn "google-drive/start" src/ --include="*.py" | grep -v __pycache__ | grep -v test
```

Find each location where the URL is built (e.g., in the Telegram bot command handlers or Mini App frontend) and append `&token={generate_url_token(chat_id, user_id)}` to the URL. The exact locations will vary, but the pattern is:

**Before:**
```python
url = f"{base_url}/auth/instagram/start?chat_id={chat_id}"
```

**After:**
```python
from src.utils.webapp_auth import generate_url_token

token = generate_url_token(chat_id, user_id)
url = f"{base_url}/auth/instagram/start?chat_id={chat_id}&token={token}"
```

The implementer MUST search for all places that construct these URLs and update them. Use:

```bash
grep -rn "instagram/start\|google-drive/start" src/ --include="*.py"
grep -rn "instagram/start\|google-drive/start" src/ --include="*.js"
grep -rn "instagram/start\|google-drive/start" src/ --include="*.html"
```

**Why URL tokens (not initData):** The OAuth start endpoints are GET requests opened in a browser, not POST requests from the Mini App. The browser doesn't have access to Telegram initData. URL tokens are designed exactly for this use case -- they're generated by the bot, signed with the bot token, and embedded in clickable URLs.

---

### Step 3: Add tenant scoping to account operations (Finding #5)

This step has three sub-parts: (A) fix `accounts` list, (B) fix `remove-account`, and (C) fix `switch-account`.

#### Step 3A: Filter `accounts` list by tenant

**File:** `src/api/routes/onboarding/dashboard.py`
**Function:** `onboarding_accounts()` (lines 53-84)

**Current code:**

```python
@router.get("/accounts")
async def onboarding_accounts(
    init_data: str,
    chat_id: int,
):
    """List all active Instagram accounts with active account for this chat marked."""
    _validate_request(init_data, chat_id)

    with (
        InstagramAccountService() as account_service,
        SettingsService() as settings_service,
    ):
        accounts = account_service.list_accounts(include_inactive=False)
        chat_settings = settings_service.get_settings(chat_id)
        active_account_id = (
            str(chat_settings.active_instagram_account_id)
            if chat_settings.active_instagram_account_id
            else None
        )

        items = []
        for acct in accounts:
            items.append(
                {
                    "id": str(acct.id),
                    "display_name": acct.display_name,
                    "instagram_username": acct.instagram_username,
                    "is_active": str(acct.id) == active_account_id,
                }
            )

        return {"accounts": items, "active_account_id": active_account_id}
```

**Problem:** `account_service.list_accounts(include_inactive=False)` calls `account_repo.get_all_active()` which returns ALL active accounts across ALL tenants with no filtering.

**Context on the data model:** The `instagram_accounts` table has no `chat_settings_id` or `telegram_chat_id` column. Accounts are linked to tenants through two mechanisms:
1. `chat_settings.active_instagram_account_id` -- points to the currently active account for a chat
2. `api_tokens.chat_settings_id` -- links OAuth tokens to a specific tenant (but only for tokens created through the per-tenant OAuth flow)

Since accounts can be shared across tenants (a single Instagram account could theoretically be used by multiple chats), the cleanest approach for the accounts list is to filter to accounts that have tokens associated with the requesting tenant, PLUS the active account for the tenant. This covers all accounts the tenant has ever connected.

**However**, the simpler and more practical approach (given the current deployment is single-tenant transitioning to multi-tenant) is to query accounts that are referenced by `api_tokens` belonging to this tenant's `chat_settings_id`, plus the current active account. But this requires a join across three tables and adds complexity.

**Simplest correct approach:** Add a `telegram_chat_id` filter to `list_accounts()` that joins through `api_tokens.instagram_account_id` to find accounts whose tokens belong to the requesting tenant. Also include the active account for the chat (in case it was set up before per-tenant tokens existed).

**File:** `src/repositories/instagram_account_repository.py`

Add a new method after `get_all_active()` (after line 22):

```python
    def get_active_for_tenant(self, chat_settings_id) -> List[InstagramAccount]:
        """Get active Instagram accounts associated with a tenant.

        Returns accounts that have API tokens scoped to this tenant,
        plus the tenant's active account (if any).

        Args:
            chat_settings_id: UUID of the chat_settings row for this tenant
        """
        from src.models.api_token import ApiToken
        from src.models.chat_settings import ChatSettings

        # Accounts with tokens belonging to this tenant
        token_accounts = (
            self.db.query(InstagramAccount)
            .join(ApiToken, ApiToken.instagram_account_id == InstagramAccount.id)
            .filter(
                ApiToken.chat_settings_id == chat_settings_id,
                InstagramAccount.is_active,
            )
            .all()
        )

        # The tenant's active account (may not have tokens in this tenant's scope)
        active_account = (
            self.db.query(InstagramAccount)
            .join(
                ChatSettings,
                ChatSettings.active_instagram_account_id == InstagramAccount.id,
            )
            .filter(
                ChatSettings.id == chat_settings_id,
                InstagramAccount.is_active,
            )
            .first()
        )

        # Deduplicate by id
        seen = set()
        result = []
        for acct in token_accounts:
            if acct.id not in seen:
                seen.add(acct.id)
                result.append(acct)
        if active_account and active_account.id not in seen:
            result.append(active_account)

        result.sort(key=lambda a: a.display_name)
        self.end_read_transaction()
        return result
```

Add the necessary import at the top of the repository file. The current imports (lines 1-8):

```python
"""Instagram account repository - CRUD for connected accounts."""

from typing import Optional, List
from datetime import datetime

from src.repositories.base_repository import BaseRepository
from src.models.instagram_account import InstagramAccount
```

No additional top-level imports needed -- the `ApiToken` and `ChatSettings` imports are done inside the method to avoid circular imports (following the existing pattern in `get_by_id_prefix` which imports `cast, String` locally at line 56).

**File:** `src/services/core/instagram_account_service.py`

Update `list_accounts()` (lines 39-51) to accept an optional `telegram_chat_id` parameter:

**Before:**

```python
    def list_accounts(self, include_inactive: bool = False) -> List[InstagramAccount]:
        """
        Get Instagram accounts.

        Args:
            include_inactive: If True, include deactivated accounts

        Returns:
            List of InstagramAccount objects
        """
        if include_inactive:
            return self.account_repo.get_all()
        return self.account_repo.get_all_active()
```

**After:**

```python
    def list_accounts(
        self,
        include_inactive: bool = False,
        telegram_chat_id: Optional[int] = None,
    ) -> List[InstagramAccount]:
        """
        Get Instagram accounts, optionally scoped to a specific tenant.

        Args:
            include_inactive: If True, include deactivated accounts
            telegram_chat_id: If provided, only return accounts associated
                with this tenant (via token ownership or active selection)

        Returns:
            List of InstagramAccount objects
        """
        if telegram_chat_id is not None:
            # Tenant-scoped: find the chat_settings_id, then query
            chat_settings = self.settings_repo.get_or_create(telegram_chat_id)
            return self.account_repo.get_active_for_tenant(chat_settings.id)
        if include_inactive:
            return self.account_repo.get_all()
        return self.account_repo.get_all_active()
```

**File:** `src/api/routes/onboarding/dashboard.py`

Update the `onboarding_accounts` function (lines 53-84) to pass `chat_id` to the service:

**Before** (line 65):

```python
        accounts = account_service.list_accounts(include_inactive=False)
```

**After:**

```python
        accounts = account_service.list_accounts(telegram_chat_id=chat_id)
```

The full updated function:

```python
@router.get("/accounts")
async def onboarding_accounts(
    init_data: str,
    chat_id: int,
):
    """List active Instagram accounts for this chat with active account marked."""
    _validate_request(init_data, chat_id)

    with (
        InstagramAccountService() as account_service,
        SettingsService() as settings_service,
    ):
        accounts = account_service.list_accounts(telegram_chat_id=chat_id)
        chat_settings = settings_service.get_settings(chat_id)
        active_account_id = (
            str(chat_settings.active_instagram_account_id)
            if chat_settings.active_instagram_account_id
            else None
        )

        items = []
        for acct in accounts:
            items.append(
                {
                    "id": str(acct.id),
                    "display_name": acct.display_name,
                    "instagram_username": acct.instagram_username,
                    "is_active": str(acct.id) == active_account_id,
                }
            )

        return {"accounts": items, "active_account_id": active_account_id}
```

#### Step 3B: Add tenant scoping to `remove-account`

**File:** `src/api/routes/onboarding/settings.py`
**Function:** `onboarding_remove_account()` (lines 99-112)

**Current code:**

```python
@router.post("/remove-account")
async def onboarding_remove_account(request: RemoveAccountRequest):
    """Deactivate (soft-delete) an Instagram account."""
    _validate_request(request.init_data, request.chat_id)

    with InstagramAccountService() as account_service, service_error_handler():
        account = account_service.deactivate_account(
            account_id=request.account_id,
        )
        return {
            "account_id": str(account.id),
            "display_name": account.display_name,
            "removed": True,
        }
```

**Problem:** `deactivate_account` takes only `account_id` with no tenant check. Any authenticated user can deactivate any account they know the UUID of.

**Fix:** Pass `telegram_chat_id` to `deactivate_account` and verify ownership in the service layer.

**Updated route:**

```python
@router.post("/remove-account")
async def onboarding_remove_account(request: RemoveAccountRequest):
    """Deactivate (soft-delete) an Instagram account."""
    _validate_request(request.init_data, request.chat_id)

    with InstagramAccountService() as account_service, service_error_handler():
        account = account_service.deactivate_account(
            account_id=request.account_id,
            telegram_chat_id=request.chat_id,
        )
        return {
            "account_id": str(account.id),
            "display_name": account.display_name,
            "removed": True,
        }
```

**File:** `src/services/core/instagram_account_service.py`
**Function:** `deactivate_account()` (lines 431-461)

**Before:**

```python
    def deactivate_account(
        self, account_id: str, user: Optional[User] = None
    ) -> InstagramAccount:
        """
        Soft-delete an account by marking it inactive.

        The account and its tokens are preserved for audit purposes.

        Args:
            account_id: UUID of account to deactivate
            user: User performing the action

        Returns:
            Deactivated InstagramAccount
        """
        with self.track_execution(
            "deactivate_account",
            user_id=user.id if user else None,
            triggered_by="user",
            input_params={"account_id": account_id},
        ) as run_id:
            account = self.account_repo.deactivate(account_id)

            self.set_result_summary(
                run_id,
                {"account_id": str(account.id), "display_name": account.display_name},
            )

            logger.info(f"Deactivated Instagram account: {account.display_name}")

            return account
```

**After:**

```python
    def deactivate_account(
        self,
        account_id: str,
        user: Optional[User] = None,
        telegram_chat_id: Optional[int] = None,
    ) -> InstagramAccount:
        """
        Soft-delete an account by marking it inactive.

        The account and its tokens are preserved for audit purposes.

        Args:
            account_id: UUID of account to deactivate
            user: User performing the action
            telegram_chat_id: If provided, verify the account belongs to this
                tenant before deactivating

        Returns:
            Deactivated InstagramAccount

        Raises:
            ValueError: If account not found or does not belong to the tenant
        """
        with self.track_execution(
            "deactivate_account",
            user_id=user.id if user else None,
            triggered_by="user",
            input_params={"account_id": account_id},
        ) as run_id:
            # Verify tenant ownership if chat_id is provided
            if telegram_chat_id is not None:
                self._verify_account_belongs_to_tenant(account_id, telegram_chat_id)

            account = self.account_repo.deactivate(account_id)

            self.set_result_summary(
                run_id,
                {"account_id": str(account.id), "display_name": account.display_name},
            )

            logger.info(f"Deactivated Instagram account: {account.display_name}")

            return account
```

#### Step 3C: Add tenant scoping to `switch-account`

**File:** `src/services/core/instagram_account_service.py`
**Function:** `switch_account()` (lines 92-144)

The current `switch_account` already takes `telegram_chat_id` and uses it to update the active account. However, it does NOT verify that the account being switched to actually belongs to the requesting tenant. An attacker from Chat A could switch Chat A's active account to an account belonging to Chat B.

Add a tenant ownership check after the existing `is_active` check. The current code at lines 115-120:

```python
            account = self.account_repo.get_by_id(account_id)
            if not account:
                raise ValueError(f"Account {account_id} not found")

            if not account.is_active:
                raise ValueError(f"Account '{account.display_name}' is disabled")
```

**After** the `is_active` check, add:

```python
            if not account.is_active:
                raise ValueError(f"Account '{account.display_name}' is disabled")

            # Verify account belongs to the requesting tenant
            self._verify_account_belongs_to_tenant(
                str(account_id), telegram_chat_id
            )
```

#### Step 3D: Add the shared `_verify_account_belongs_to_tenant` helper

**File:** `src/services/core/instagram_account_service.py`

Add this private method to the `InstagramAccountService` class. Place it after the `list_accounts` method (after the updated version from Step 3A) and before `get_account_by_id`:

```python
    def _verify_account_belongs_to_tenant(
        self, account_id: str, telegram_chat_id: int
    ) -> None:
        """Verify that an Instagram account belongs to the given tenant.

        An account "belongs to" a tenant if:
        1. It is the tenant's currently active account, OR
        2. It has API tokens scoped to the tenant's chat_settings

        Args:
            account_id: UUID of the Instagram account
            telegram_chat_id: Telegram chat ID of the requesting tenant

        Raises:
            ValueError: If the account does not belong to the tenant
        """
        chat_settings = self.settings_repo.get_or_create(telegram_chat_id)

        # Check 1: Is this the tenant's active account?
        if (
            chat_settings.active_instagram_account_id
            and str(chat_settings.active_instagram_account_id) == str(account_id)
        ):
            return

        # Check 2: Does this account have tokens scoped to this tenant?
        from src.models.api_token import ApiToken

        token = (
            self.token_repo.db.query(ApiToken)
            .filter(
                ApiToken.instagram_account_id == account_id,
                ApiToken.chat_settings_id == chat_settings.id,
            )
            .first()
        )
        if token:
            return

        raise ValueError(
            f"Account {account_id} does not belong to this tenant"
        )
```

**Note on `self.token_repo`:** The `InstagramAccountService.__init__` (line 36) already creates `self.token_repo = TokenRepository()`. The `TokenRepository` extends `BaseRepository` which has a `self.db` session attribute. We use `self.token_repo.db.query(...)` to access the SQLAlchemy session for the ad-hoc query. This follows the existing pattern -- `token_repo.db` is the same session as `self.account_repo.db` (both created via `BaseRepository.__init__`).

**Alternative approach considered and rejected:** Adding a `verify_account_ownership` method to the repository layer. This was rejected because the ownership logic involves business rules (checking active account OR token association), which belongs in the service layer per the architecture's separation of concerns.

---

### Step 4: Update test fixtures and add security tests

#### Step 4A: Update `tests/src/api/conftest.py` mock_validate default

**File:** `tests/src/api/conftest.py`

The current `mock_validate` default (line 10-11):

```python
VALID_USER = {"user_id": 12345, "first_name": "Chris"}
```

This simulates a private-chat initData with no `chat_id` -- which will now be rejected by our Step 1 fix. All existing tests that use `mock_validate()` without arguments will break because `_validate_request` will see `signed_chat_id=None` and raise 403.

**Fix:** Update `VALID_USER` to include `chat_id` matching `CHAT_ID`:

**Before:**

```python
VALID_USER = {"user_id": 12345, "first_name": "Chris"}
CHAT_ID = -1001234567890
```

**After:**

```python
CHAT_ID = -1001234567890
VALID_USER = {"user_id": 12345, "first_name": "Chris", "chat_id": CHAT_ID}
```

Note: `CHAT_ID` must be defined BEFORE `VALID_USER` since `VALID_USER` now references it. Swap the order of the two lines.

This ensures all existing tests pass because the mock now always returns a user_info dict with a matching `chat_id`.

#### Step 4B: Add tenant isolation bypass tests

**File:** `tests/src/api/test_onboarding_routes.py`

Add a new test class at the end of the file:

```python
@pytest.mark.unit
class TestTenantIsolation:
    """Test that tenant isolation cannot be bypassed."""

    def test_no_chat_id_in_auth_returns_403(self, client):
        """Auth credential without chat_id is rejected (Finding #1)."""
        user_no_chat = {"user_id": 12345, "first_name": "Chris"}
        with patch(
            "src.api.routes.onboarding.helpers.validate_init_data",
            return_value=user_no_chat,
        ):
            response = client.post(
                "/api/onboarding/init",
                json={"init_data": "fake", "chat_id": CHAT_ID},
            )
        assert response.status_code == 403
        assert "chat ID" in response.json()["detail"].lower()

    def test_chat_id_mismatch_returns_403(self, client):
        """Auth credential with different chat_id is rejected."""
        user_wrong_chat = {
            "user_id": 12345,
            "first_name": "Chris",
            "chat_id": -9999999,
        }
        with patch(
            "src.api.routes.onboarding.helpers.validate_init_data",
            return_value=user_wrong_chat,
        ):
            response = client.post(
                "/api/onboarding/init",
                json={"init_data": "fake", "chat_id": CHAT_ID},
            )
        assert response.status_code == 403
        assert "mismatch" in response.json()["detail"].lower()

    def test_matching_chat_id_succeeds(self, client):
        """Auth credential with matching chat_id passes validation."""
        with (
            mock_validate({"user_id": 12345, "first_name": "Chris", "chat_id": CHAT_ID}),
            _mock_setup_state(),
        ):
            response = client.post(
                "/api/onboarding/init",
                json={"init_data": "fake", "chat_id": CHAT_ID},
            )
        assert response.status_code == 200
```

Add the necessary import at the top of the test file if not already present:

```python
from unittest.mock import patch
```

(This import already exists at line 4.)

#### Step 4C: Add cross-tenant accounts test

**File:** `tests/src/api/test_onboarding_dashboard.py`

Add a test to verify the accounts endpoint passes `telegram_chat_id` to the service:

```python
@pytest.mark.unit
class TestAccountsTenantScoping:
    """Test that accounts endpoint is tenant-scoped (Finding #5)."""

    def test_accounts_passes_chat_id_to_service(self, client):
        """Accounts list must filter by the requesting tenant's chat_id."""
        with (
            mock_validate(),
            patch(
                "src.api.routes.onboarding.dashboard.InstagramAccountService"
            ) as MockAcctSvc,
            patch(
                "src.api.routes.onboarding.dashboard.SettingsService"
            ) as MockSettingsSvc,
        ):
            mock_acct = service_ctx(MockAcctSvc)
            mock_acct.list_accounts.return_value = []

            mock_settings = service_ctx(MockSettingsSvc)
            mock_settings.get_settings.return_value = _mock_settings_obj()

            response = client.get(
                f"/api/onboarding/accounts?init_data=fake&chat_id={CHAT_ID}"
            )

        assert response.status_code == 200
        # Verify list_accounts was called with tenant scoping
        mock_acct.list_accounts.assert_called_once_with(telegram_chat_id=CHAT_ID)
```

#### Step 4D: Add OAuth `/start` authentication tests

**File:** `tests/src/api/test_oauth_routes.py`

Update existing tests and add new ones. The existing tests pass `chat_id` without a `token` parameter. They will need updating.

Add these test methods to the existing `TestOAuthStartEndpoint` class:

```python
    def test_start_without_token_returns_422(self, client):
        """GET /auth/instagram/start without token returns validation error."""
        response = client.get("/auth/instagram/start?chat_id=-1001234567890")
        assert response.status_code == 422

    def test_start_with_invalid_token_returns_401(self, client):
        """GET /auth/instagram/start with invalid token returns 401."""
        response = client.get(
            "/auth/instagram/start?chat_id=-1001234567890&token=invalid"
        )
        assert response.status_code == 401

    def test_start_with_mismatched_chat_id_returns_403(self, client):
        """GET /auth/instagram/start with token for different chat returns 403."""
        with patch("src.api.routes.oauth.validate_url_token") as mock_validate:
            mock_validate.return_value = {"user_id": 123, "chat_id": -9999}

            response = client.get(
                "/auth/instagram/start?chat_id=-1001234567890&token=valid-token",
                follow_redirects=False,
            )

        assert response.status_code == 403

    def test_start_with_valid_token_redirects(self, client):
        """GET /auth/instagram/start with valid token succeeds."""
        with (
            patch("src.api.routes.oauth.validate_url_token") as mock_validate_tok,
            patch("src.api.routes.oauth.OAuthService") as MockService,
        ):
            mock_validate_tok.return_value = {
                "user_id": 123,
                "chat_id": -1001234567890,
            }
            mock_svc = MockService.return_value
            mock_svc.generate_authorization_url.return_value = (
                "https://www.facebook.com/dialog/oauth?client_id=123"
            )
            mock_svc.__enter__ = Mock(return_value=mock_svc)
            mock_svc.__exit__ = Mock(return_value=False)

            response = client.get(
                "/auth/instagram/start?chat_id=-1001234567890&token=valid-token",
                follow_redirects=False,
            )

        assert response.status_code == 307
        assert "facebook.com" in response.headers["location"]
```

Add a similar test class for Google Drive:

```python
class TestGoogleDriveOAuthStartAuth:
    """Test authentication on GET /auth/google-drive/start."""

    def test_start_without_token_returns_422(self, client):
        """GET /auth/google-drive/start without token returns validation error."""
        response = client.get("/auth/google-drive/start?chat_id=-1001234567890")
        assert response.status_code == 422

    def test_start_with_invalid_token_returns_401(self, client):
        """GET /auth/google-drive/start with invalid token returns 401."""
        response = client.get(
            "/auth/google-drive/start?chat_id=-1001234567890&token=invalid"
        )
        assert response.status_code == 401

    def test_start_with_valid_token_redirects(self, client):
        """GET /auth/google-drive/start with valid token succeeds."""
        with (
            patch("src.api.routes.oauth.validate_url_token") as mock_validate_tok,
            patch("src.api.routes.oauth.GoogleDriveOAuthService") as MockService,
        ):
            mock_validate_tok.return_value = {
                "user_id": 123,
                "chat_id": -1001234567890,
            }
            mock_svc = MockService.return_value
            mock_svc.generate_authorization_url.return_value = (
                "https://accounts.google.com/o/oauth2/auth?client_id=123"
            )
            mock_svc.__enter__ = Mock(return_value=mock_svc)
            mock_svc.__exit__ = Mock(return_value=False)

            response = client.get(
                "/auth/google-drive/start?chat_id=-1001234567890&token=valid-token",
                follow_redirects=False,
            )

        assert response.status_code == 307
        assert "google.com" in response.headers["location"]
```

**Update existing tests** in `TestOAuthStartEndpoint`: The existing `test_start_redirects_to_meta` and other tests that call `/auth/instagram/start?chat_id=...` without a `token` will now get 422. These tests must be updated to include a mocked `validate_url_token`. Update the first test:

**Before:**

```python
    def test_start_redirects_to_meta(self, client):
        """GET /auth/instagram/start redirects to Meta OAuth."""
        with patch("src.api.routes.oauth.OAuthService") as MockService:
            mock_svc = MockService.return_value
            mock_svc.generate_authorization_url.return_value = (
                "https://www.facebook.com/dialog/oauth?client_id=123"
            )
            mock_svc.__enter__ = Mock(return_value=mock_svc)
            mock_svc.__exit__ = Mock(return_value=False)

            response = client.get(
                "/auth/instagram/start?chat_id=-1001234567890",
                follow_redirects=False,
            )

        assert response.status_code == 307
        assert "facebook.com" in response.headers["location"]
```

**After:**

```python
    def test_start_redirects_to_meta(self, client):
        """GET /auth/instagram/start redirects to Meta OAuth."""
        with (
            patch("src.api.routes.oauth.validate_url_token") as mock_validate_tok,
            patch("src.api.routes.oauth.OAuthService") as MockService,
        ):
            mock_validate_tok.return_value = {
                "user_id": 123,
                "chat_id": -1001234567890,
            }
            mock_svc = MockService.return_value
            mock_svc.generate_authorization_url.return_value = (
                "https://www.facebook.com/dialog/oauth?client_id=123"
            )
            mock_svc.__enter__ = Mock(return_value=mock_svc)
            mock_svc.__exit__ = Mock(return_value=False)

            response = client.get(
                "/auth/instagram/start?chat_id=-1001234567890&token=valid",
                follow_redirects=False,
            )

        assert response.status_code == 307
        assert "facebook.com" in response.headers["location"]
```

Apply the same pattern to `test_start_invalid_config_returns_400` and `test_start_calls_close_on_success` -- add `mock_validate_tok` patch and `&token=valid` to the URL.

**Do not change** `test_start_missing_chat_id_returns_422` -- this test should still pass as-is (missing `chat_id` causes a 422 before token validation even runs).

---

## Documentation Updates

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Security
- **fix:** Reject API requests where auth credential has no signed chat_id (tenant isolation bypass)
- **fix:** Require authenticated URL token on OAuth `/start` endpoints (prevents account hijacking)
- **fix:** Scope account list, removal, and switching to the requesting tenant only
```

---

## Verification Checklist

After implementing all changes:

1. **Run linting:**
   ```bash
   source venv/bin/activate && ruff check src/ tests/ && ruff format --check src/ tests/
   ```

2. **Run all tests:**
   ```bash
   pytest
   ```

3. **Run specific test files for the changed code:**
   ```bash
   pytest tests/src/api/test_onboarding_routes.py -v
   pytest tests/src/api/test_onboarding_dashboard.py -v
   pytest tests/src/api/test_oauth_routes.py -v
   pytest tests/src/utils/test_webapp_auth.py -v
   ```

4. **Verify no existing tests regressed** -- particularly:
   - All onboarding route tests that use `mock_validate()` still pass (after conftest update)
   - OAuth callback tests are unaffected (callbacks don't use the `/start` auth)

5. **Manual verification:**
   - Open the Mini App from a Telegram group chat -- should work normally
   - Verify the "Connect Instagram" and "Connect Google Drive" buttons in Telegram include the `&token=...` parameter in their URLs
   - Confirm that calling `/auth/instagram/start?chat_id=X` without a token returns 422
   - Confirm that calling `/auth/instagram/start?chat_id=X&token=invalid` returns 401

6. **Search for all OAuth start URL construction sites:**
   ```bash
   grep -rn "instagram/start" src/ --include="*.py" --include="*.js" --include="*.html"
   grep -rn "google-drive/start" src/ --include="*.py" --include="*.js" --include="*.html"
   ```
   Every location must append `&token={url_token}`.

---

## Test Plan

### New Tests

| Test | File | What It Verifies |
|------|------|-----------------|
| `test_no_chat_id_in_auth_returns_403` | `test_onboarding_routes.py` | Finding #1: Private-chat initData without chat_id is rejected |
| `test_chat_id_mismatch_returns_403` | `test_onboarding_routes.py` | Finding #1: Mismatched chat_id is still rejected |
| `test_matching_chat_id_succeeds` | `test_onboarding_routes.py` | Regression: Matching chat_id still works |
| `test_start_without_token_returns_422` | `test_oauth_routes.py` | Finding #2: Missing token on Instagram OAuth start |
| `test_start_with_invalid_token_returns_401` | `test_oauth_routes.py` | Finding #2: Invalid token on Instagram OAuth start |
| `test_start_with_mismatched_chat_id_returns_403` | `test_oauth_routes.py` | Finding #2: Token for wrong chat on Instagram OAuth start |
| `test_start_with_valid_token_redirects` | `test_oauth_routes.py` | Regression: Valid token on Instagram OAuth start works |
| `TestGoogleDriveOAuthStartAuth` (3 tests) | `test_oauth_routes.py` | Finding #2: Same tests for Google Drive OAuth start |
| `test_accounts_passes_chat_id_to_service` | `test_onboarding_dashboard.py` | Finding #5: Accounts list passes tenant filter |

### Existing Tests Modified

| Test | Change |
|------|--------|
| `conftest.py` `VALID_USER` | Add `chat_id` to default mock return |
| `test_start_redirects_to_meta` | Add `validate_url_token` mock + `&token=` param |
| `test_start_invalid_config_returns_400` | Add `validate_url_token` mock + `&token=` param |
| `test_start_calls_close_on_success` | Add `validate_url_token` mock + `&token=` param |

### Coverage Expectations

All new code paths should be covered:
- `_validate_request` None chat_id branch: tested by `test_no_chat_id_in_auth_returns_403`
- OAuth `/start` token validation: tested by 4 new Instagram tests + 3 Google Drive tests
- Tenant-scoped account listing: tested by `test_accounts_passes_chat_id_to_service`
- `deactivate_account` and `switch_account` tenant checks: add service-level unit tests in `tests/src/services/test_instagram_account_service.py` if they exist, verifying `_verify_account_belongs_to_tenant` raises `ValueError` for cross-tenant access

---

## Stress Testing & Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Private-chat initData (no `chat` field) | 403 with clear error message directing user to open from group chat |
| Valid initData from group chat | Passes validation, proceeds normally |
| URL token with matching chat_id | Passes validation, proceeds normally |
| URL token with mismatched chat_id | 403 "Chat ID mismatch" |
| Expired URL token on OAuth start | 401 "Token expired" |
| `deactivate_account` for account with no tokens and not active | `ValueError` "does not belong to this tenant" |
| `list_accounts` for tenant with no accounts | Returns empty list `{"accounts": [], "active_account_id": null}` |
| `list_accounts` for tenant with legacy accounts (no `chat_settings_id` on tokens) | Returns only the active account (if set), not all legacy accounts |
| `switch_account` to account from another tenant | `ValueError` raised before any state mutation |
| OAuth start URL with tampered token signature | 401 "Invalid token signature" |

---

## What NOT To Do

1. **Do NOT fall back to "allow all" when signed_chat_id is None.** The entire point of this fix is to close the gap where None causes the check to be skipped. Never add logic like "if None, look up user's chats and allow any of them" -- this creates a secondary attack surface where a user who belongs to multiple chats can impersonate any of them. The correct fix is to reject and require a URL token or group-chat initData.

2. **Do NOT add the token to OAuth callback URLs.** Only the `/start` endpoints need the token. The `/callback` endpoints are called by Meta/Google after the OAuth redirect -- they use the encrypted state token for CSRF protection, which is a separate mechanism. Adding token requirements to callbacks would break the OAuth flow.

3. **Do NOT add a `chat_settings_id` or `telegram_chat_id` column to the `instagram_accounts` table.** The current data model deliberately separates account identity from tenant ownership (accounts can be shared across tenants). Adding a direct FK would break this design. Ownership is determined through `api_tokens.chat_settings_id` and `chat_settings.active_instagram_account_id`.

4. **Do NOT use `request.state` or middleware for the OAuth start auth.** These endpoints are simple GET redirects -- adding a `token` query parameter is the simplest and most explicit approach. Middleware would be overkill and could interfere with the callback endpoints.

5. **Do NOT remove the `include_inactive` parameter from `list_accounts()`.** It's still used by CLI commands and other internal callers that need the full list. The new `telegram_chat_id` parameter is additive and orthogonal.

6. **Do NOT use `initData` validation on the OAuth `/start` endpoints.** These are GET requests opened directly in the browser -- the browser does not have Telegram WebApp SDK context. Only URL tokens work in this scenario.

7. **Do NOT forget to update the bot code that generates OAuth start URLs.** If you update the API to require tokens but don't add `&token=...` to the URLs the bot generates, users will get 422 errors when clicking "Connect Instagram" or "Connect Google Drive". Search ALL locations that construct these URLs.

8. **Do NOT use `mock_validate()` without arguments in new tests if you need a specific chat_id.** After the conftest update, `mock_validate()` returns `VALID_USER` which includes `CHAT_ID`. If your test needs a different chat_id, pass an explicit dict: `mock_validate({"user_id": 123, "first_name": "Test", "chat_id": -999})`.
