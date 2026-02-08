# Verbose Settings Improvement Plan

## Problem Statement

The `show_verbose_notifications` setting (toggled via `/settings` > "Verbose: ON/OFF") is **underspecified in scope**. Users expect that toggling verbose OFF produces a minimal, clean chat experience. In practice, only 2 of ~15+ user-facing message types respect the setting:

1. **Queue notification caption** — workflow instructions are hidden when verbose=OFF
2. **Auto-post success message** — switches between detailed and minimal

Everything else (status, posted/skipped confirmations, dry run output, reject confirmations, error messages, etc.) always shows full detail regardless of the setting.

Additionally, the **auto-post success message in verbose=OFF mode** drops the user attribution entirely:
- Verbose ON: `✅ *Posted to Instagram!*` + filename + account + story ID + "Posted by: @user"
- Verbose OFF: `✅ Posted to @account` ← **missing user**

---

## Current Behavior Audit

### Messages That DO Respect Verbose

| Location | Lines | Verbose ON | Verbose OFF |
|----------|-------|-----------|------------|
| `_build_enhanced_caption()` | 351-360 | Shows 3-step workflow instructions | Instructions hidden |
| `_do_autopost()` success | 2755-2767 | Filename + account + story ID + user | Just `✅ Posted to @account` |

### Messages That DO NOT Respect Verbose (Candidates)

| Message | Location | Lines | Current Output | Priority |
|---------|----------|-------|---------------|----------|
| **Posted confirmation** | `_handle_posted()` | 2398 | `✅ Marked as posted by @user` | Medium |
| **Skipped confirmation** | `_handle_skipped()` | 2458 | `⏭️ Skipped by @user` | Medium |
| **Rejected confirmation** | `_handle_rejected()` | 3358-3363 | File + user + "never queued again" | Medium |
| **Reject dialog** | `_handle_reject_confirmation()` | 2950-2956 | File + "cannot be undone" warning | Low |
| **Dry run output** | `_do_autopost()` | 2637-2650 | Full dry run details (10 lines) | High |
| **Safety check failure** | `_do_autopost()` | 2555-2559 | Full error list | Low |
| **Auto-post error** | `_do_autopost()` | 2810-2813 | Error + retry instructions | Low |
| **Progress messages** | `_do_autopost()` | 2569, 2681 | "Uploading...", "Posting..." | Low |

### Command Responses (NOT candidates for verbose toggle)

These are user-initiated commands — the user explicitly asked for this information, so they should always show full detail regardless of verbose:

| Command | Lines | Rationale for Exclusion |
|---------|-------|------------------------|
| `/status` | 446-462 | User explicitly requested status |
| `/queue` | 493-513 | User explicitly requested queue list |
| `/stats` | 2061-2075 | User explicitly requested stats |
| `/history` | 2104-2121 | User explicitly requested history |
| `/locks` | 2144-2153 | User explicitly requested lock list |
| `/help` | 592-618 | User explicitly requested help |
| `/start` | 389-394 | One-time welcome message |
| `/pause` | 1918-1925 | User explicitly toggled pause |
| `/resume` | 1969-1985 | User explicitly toggled resume |
| `/schedule` | 2019-2025 | User explicitly ran schedule |
| `/dryrun` | 670-700 | User explicitly toggled dry run |
| `/reset` | 2184-2191 | User explicitly requested reset |
| `/cleanup` | 2238-2246 | User explicitly ran cleanup |

### System Messages (NOT candidates)

| Message | Rationale |
|---------|-----------|
| Startup notification | Controlled by `SEND_LIFECYCLE_NOTIFICATIONS` flag |
| Shutdown notification | Controlled by `SEND_LIFECYCLE_NOTIFICATIONS` flag |
| Settings menu | UI chrome, always needed |
| Account management flows | Wizard-style prompts, always needed |
| Error/warning toasts (`query.answer()`) | Brief toasts, already minimal |

---

## Design Principles

### What "Verbose OFF" Should Mean

**Verbose OFF = Minimal *unsolicited* notifications in the chat.** The goal is a clean timeline where the essential info (what happened, to which account, by whom) is preserved, but extra detail is stripped.

**Guiding rules:**

1. **User-initiated commands** (`/status`, `/queue`, `/help`, etc.) → **Always full detail.** The user asked for it.
2. **Bot-initiated notifications** (queue items appearing, success/failure messages) → **Respect verbose toggle.**
3. **Action confirmations** (posted, skipped, rejected) → **Respect verbose toggle** — these replace the notification in-place.
4. **Error messages** → **Always show.** Users need to know what went wrong.
5. **Progress indicators** ("Uploading...", "Posting...") → **Always show.** These are transient and necessary for UX.
6. **The user who took the action should ALWAYS be shown**, even in verbose=OFF mode.
7. **The account should ALWAYS be shown**, even in verbose=OFF mode.

### Verbose Behavior by Message Category

| Category | Verbose ON | Verbose OFF |
|----------|-----------|------------|
| **Queue notification caption** | Full caption + workflow instructions | Caption without workflow instructions (current) |
| **Auto-post success** | Filename + account + story ID + user | `✅ Posted to @account by @user` |
| **Manual posted** | `✅ Marked as posted by @user` (unchanged) | `✅ Posted by @user` |
| **Skipped** | `⏭️ Skipped by @user` (unchanged) | `⏭️ Skipped by @user` (unchanged — already minimal) |
| **Rejected** | Full: file + user + "never queued again" | `🚫 Rejected by @user` |
| **Reject confirmation dialog** | Full: file + "cannot be undone" warning | Same (always show — user is making a destructive decision) |
| **Dry run** | Full 10-line output | Condensed: account + status + user |
| **Safety check failure** | Full error list | Same (always show errors) |
| **Auto-post error** | Full error + retry | Same (always show errors) |
| **Progress ("Uploading...")** | Same | Same (transient, necessary) |

---

## Implementation Plan

### Fix 1: Auto-Post Success — Always Include User (Bug Fix)

**File:** `src/services/core/telegram_service.py`
**Lines:** 2765-2767

**Current (verbose=OFF):**
```python
caption = f"✅ Posted to {account_display}"
```

**Proposed:**
```python
caption = f"✅ Posted to {account_display} by {self._get_display_name(user)}"
```

**Effort:** Trivial — single line change.

---

### Fix 2: Dry Run Output — Respect Verbose

**File:** `src/services/core/telegram_service.py`
**Lines:** 2637-2650

**Current:** Always shows full 10-line output regardless of verbose.

**Proposed:** Add verbose check (chat_settings already loaded at line 2546):
```python
verbose = (
    chat_settings.show_verbose_notifications
    if chat_settings.show_verbose_notifications is not None
    else True
)

if verbose:
    # Current full output
    caption = (
        f"🧪 DRY RUN - Cloudinary Upload Complete\n\n"
        f"📁 File: {media_item.file_name}\n"
        f"📸 Account: {account_display}\n\n"
        f"✅ Cloudinary upload: Success\n"
        f"🔗 Preview (with blur): {preview_url}\n\n"
        f"⏸️ Stopped before Instagram API\n"
        f"(DRY_RUN_MODE=true)\n\n"
        f"• No Instagram post made\n"
        f"• No history recorded\n"
        f"• No TTL lock created\n"
        f"• Queue item preserved\n\n"
        f"Tested by: {self._get_display_name(user)}"
    )
else:
    caption = (
        f"🧪 DRY RUN ✅\n\n"
        f"📸 Account: {account_display}\n"
        f"Tested by: {self._get_display_name(user)}"
    )
```

**Effort:** Small — add verbose check and condensed alternative.

---

### Fix 3: Rejected Confirmation — Respect Verbose

**File:** `src/services/core/telegram_service.py`
**Lines:** 3358-3363

**Current:** Always shows file + user + "never queued again".

**Proposed:**
```python
# Get verbose setting
chat_settings = self.settings_service.get_settings(query.message.chat_id)
verbose = (
    chat_settings.show_verbose_notifications
    if chat_settings.show_verbose_notifications is not None
    else True
)

if verbose:
    caption = (
        f"🚫 *Permanently Rejected*\n\n"
        f"By: {self._get_display_name(user)}\n"
        f"File: {media_item.file_name if media_item else 'Unknown'}\n\n"
        f"This media will never be queued again."
    )
else:
    caption = f"🚫 Rejected by {self._get_display_name(user)}"
```

**Effort:** Small.

---

### Fix 4: Manual "Posted" Confirmation — Respect Verbose

**File:** `src/services/core/telegram_service.py`
**Lines:** 2397-2398

**Current:** `✅ Marked as posted by @user`

**Proposed:**
```python
chat_settings = self.settings_service.get_settings(query.message.chat_id)
verbose = (
    chat_settings.show_verbose_notifications
    if chat_settings.show_verbose_notifications is not None
    else True
)

if verbose:
    new_caption = f"✅ Marked as posted by {self._get_display_name(user)}"
else:
    new_caption = f"✅ Posted by {self._get_display_name(user)}"
```

**Effort:** Small.

---

### Refactor: Extract Verbose Check Helper

Since the verbose check pattern is repeated ~6 times:

```python
chat_settings = self.settings_service.get_settings(chat_id)
verbose = (
    chat_settings.show_verbose_notifications
    if chat_settings.show_verbose_notifications is not None
    else True
)
```

Extract a helper method:

```python
def _is_verbose(self, chat_id: int) -> bool:
    """Check if verbose notifications are enabled for a chat."""
    chat_settings = self.settings_service.get_settings(chat_id)
    if chat_settings.show_verbose_notifications is not None:
        return chat_settings.show_verbose_notifications
    return True
```

This simplifies every callsite to:
```python
verbose = self._is_verbose(query.message.chat_id)
```

**Note:** In `_do_autopost()`, `chat_settings` is already loaded for other reasons (dry_run_mode, enable_instagram_api). In that case, use the already-loaded value to avoid an extra DB query.

---

## Summary of Changes

| # | Change | Type | Effort |
|---|--------|------|--------|
| 1 | Auto-post success: always show user in verbose=OFF | Bug fix | Trivial |
| 2 | Dry run output: respect verbose | Enhancement | Small |
| 3 | Rejected confirmation: respect verbose | Enhancement | Small |
| 4 | Manual "Posted" confirmation: respect verbose | Enhancement | Small |
| 5 | Extract `_is_verbose()` helper | Refactor | Small |

### Files to Change
- `src/services/core/telegram_service.py` — All changes are here

### Files NOT Changing (by design)
- Models, repositories, settings service — No schema changes needed
- CLI, config — Not affected
- Command handlers (`/status`, `/queue`, etc.) — Intentionally excluded

---

## Testing Plan

### Unit Tests
- Test `_is_verbose()` with `None`, `True`, `False` values
- Test auto-post success message includes user in both verbose modes
- Test dry run caption varies by verbose mode
- Test rejected caption varies by verbose mode
- Test posted caption varies by verbose mode

### Manual Testing
1. Toggle verbose OFF via `/settings`
2. Auto-post a story → verify `✅ Posted to @account by @user`
3. Mark a post as manually posted → verify `✅ Posted by @user`
4. Reject a post → verify `🚫 Rejected by @user`
5. Run dry run → verify condensed output
6. Toggle verbose ON → verify all original detailed messages return

---

## Out of Scope

- **Skipped confirmation** — Already minimal (`⏭️ Skipped by @user`), no change needed
- **Error messages** — Always shown regardless of verbose (users need to see errors)
- **Progress messages** — Always shown (transient UX indicators)
- **Reject confirmation dialog** — Always detailed (destructive action, user needs context)
- **Safety check failures** — Always detailed (users need to understand why post was blocked)
- **User-initiated command responses** — Always detailed (user explicitly asked)
- **Settings/account management UI** — Always detailed (configuration flows)
