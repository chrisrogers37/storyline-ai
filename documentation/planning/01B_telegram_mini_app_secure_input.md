# Telegram Mini App for Secure Credential Input

**Status**: Planned (Future Enhancement)
**Created**: 2026-01-25
**Priority**: Low (current message-based approach works with security warning)
**Dependencies**: Phase 1.5 (Instagram Account Management) - Complete
**Parent Document**: `phases/01_settings_and_multitenancy.md`

---

## Executive Summary

This document outlines an enhancement to the Instagram account configuration flow using Telegram Mini Apps (Web Apps) to eliminate the security concern of sensitive credentials appearing in chat history.

**Current State:**
- Account configuration uses message-based input (user types credentials in chat)
- Telegram Bot API limitation: bots cannot delete user messages in private chats
- Security warning instructs users to manually delete their messages

**Proposed Solution:**
- Use Telegram Mini Apps to collect credentials via a web form
- Data is sent directly to the bot without appearing in chat history
- No user action required for cleanup

---

## Problem Statement

### Current Flow (Message-Based)

```
User clicks "Add Account"
     ↓
Bot: "Enter display name"
     ↓
User types: "My Account"          ← Message stays in chat
     ↓
Bot: "Enter Account ID"
     ↓
User types: "17841425591637879"   ← Message stays in chat (sensitive)
     ↓
Bot: "Enter Access Token"
     ↓
User types: "EAAG..."             ← Message stays in chat (VERY sensitive)
     ↓
Bot deletes its own prompts
     ↓
User's messages with credentials REMAIN (bot can't delete them)
     ↓
Security warning tells user to delete their own messages
```

### Issues
1. **Security Risk**: Access tokens visible in chat history until user manually deletes
2. **User Friction**: Requires user to remember to delete messages
3. **Audit Trail**: Messages may be backed up before deletion
4. **Multi-Device**: Messages sync to other devices before deletion

---

## Proposed Solution: Telegram Mini Apps

### What are Mini Apps?

Telegram Mini Apps (formerly Web Apps) allow bots to display interactive web interfaces within Telegram. Key features:
- Opens as an overlay within the Telegram app
- Full HTML/CSS/JavaScript support
- Secure data transmission back to bot via `sendData` API
- Data never appears in chat history

### Proposed Flow (Mini App)

```
User clicks "Add Account"
     ↓
Bot opens Mini App (web form)
     ↓
User fills form:
  - Display name
  - Account ID
  - Access Token
     ↓
User clicks "Submit"
     ↓
Mini App calls Telegram.WebApp.sendData(JSON)
     ↓
Bot receives web_app_data event
     ↓
Bot validates credentials via Instagram API
     ↓
Bot sends confirmation message
     ↓
NO sensitive data ever appears in chat
```

---

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Telegram Client                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Mini App (WebView)                                  │   │
│  │  ┌───────────────────────────────────────────────┐ │   │
│  │  │  HTML Form                                     │ │   │
│  │  │  - Display Name input                          │ │   │
│  │  │  - Account ID input                            │ │   │
│  │  │  - Access Token input (password field)         │ │   │
│  │  │  - Submit button                               │ │   │
│  │  └───────────────────────────────────────────────┘ │   │
│  │       │                                             │   │
│  │       │ Telegram.WebApp.sendData()                  │   │
│  │       ▼                                             │   │
│  └───────┼─────────────────────────────────────────────┘   │
│          │                                                  │
└──────────┼──────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────┐
│  Telegram Bot (python-telegram-bot)                          │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  WebAppDataHandler                                      │ │
│  │  - Receives web_app_data update                        │ │
│  │  - Parses JSON payload                                 │ │
│  │  - Calls InstagramAccountService                       │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────┐
│  Instagram Graph API                                         │
│  - Validates credentials                                     │
│  - Fetches username                                          │
└──────────────────────────────────────────────────────────────┘
```

### File Structure

```
storyline-ai/
├── src/
│   ├── services/
│   │   └── core/
│   │       └── telegram_service.py    # Add WebAppData handler
│   └── webapp/                        # NEW: Mini App static files
│       ├── __init__.py
│       ├── static/
│       │   ├── add_account.html       # Form HTML
│       │   ├── style.css              # Styling
│       │   └── app.js                 # Form logic + Telegram WebApp SDK
│       └── server.py                  # Optional: Simple static file server
├── src/api/                           # Alternative: Serve via FastAPI
│   └── webapp_routes.py               # Serve static files
```

### Separation of Concerns

| Component | Responsibility | Location |
|-----------|---------------|----------|
| **Mini App HTML/JS** | User interface for credential input | `src/webapp/static/` |
| **Static File Server** | Serve Mini App files via HTTPS | `src/webapp/server.py` or external CDN |
| **TelegramService** | Handle `web_app_data` events | `src/services/core/telegram_service.py` |
| **InstagramAccountService** | Validate and store credentials | `src/services/core/instagram_account_service.py` |

---

## Implementation Details

### 1. Mini App HTML (`src/webapp/static/add_account.html`)

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Add Instagram Account</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="container">
        <h1>Add Instagram Account</h1>

        <form id="accountForm">
            <div class="field">
                <label for="displayName">Display Name</label>
                <input type="text" id="displayName" required
                       placeholder="e.g., Thursday Lines">
                <span class="hint">A friendly name for this account</span>
            </div>

            <div class="field">
                <label for="accountId">Instagram Account ID</label>
                <input type="text" id="accountId" required
                       placeholder="e.g., 17841425591637879"
                       pattern="[0-9]+">
                <span class="hint">Found in Meta Business Suite</span>
            </div>

            <div class="field">
                <label for="accessToken">Access Token</label>
                <input type="password" id="accessToken" required
                       placeholder="EAAG...">
                <span class="hint">Your Instagram API access token</span>
            </div>

            <button type="submit" id="submitBtn">Add Account</button>
        </form>

        <div id="status" class="hidden"></div>
    </div>

    <script src="app.js"></script>
</body>
</html>
```

### 2. Mini App JavaScript (`src/webapp/static/app.js`)

```javascript
// Initialize Telegram WebApp
const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

// Apply Telegram theme
document.body.style.backgroundColor = tg.backgroundColor;
document.body.style.color = tg.textColor;

const form = document.getElementById('accountForm');
const submitBtn = document.getElementById('submitBtn');
const statusDiv = document.getElementById('status');

form.addEventListener('submit', async (e) => {
    e.preventDefault();

    // Disable button during submission
    submitBtn.disabled = true;
    submitBtn.textContent = 'Adding...';

    const data = {
        action: 'add_account',
        display_name: document.getElementById('displayName').value.trim(),
        account_id: document.getElementById('accountId').value.trim(),
        access_token: document.getElementById('accessToken').value.trim()
    };

    // Validate locally
    if (!data.display_name || !data.account_id || !data.access_token) {
        showError('Please fill in all fields');
        resetButton();
        return;
    }

    if (!/^\d+$/.test(data.account_id)) {
        showError('Account ID must be numeric');
        resetButton();
        return;
    }

    // Send data to bot (closes Mini App automatically)
    tg.sendData(JSON.stringify(data));
});

function showError(message) {
    statusDiv.className = 'error';
    statusDiv.textContent = message;
    statusDiv.classList.remove('hidden');
}

function resetButton() {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Add Account';
}

// Handle back button
tg.BackButton.onClick(() => {
    tg.close();
});
```

### 3. TelegramService Handler Update

```python
# In src/services/core/telegram_service.py

from telegram import Update, WebAppInfo
from telegram.ext import MessageHandler, filters

class TelegramService:
    def __init__(self):
        # ... existing init ...

        # Add WebApp data handler
        self.application.add_handler(
            MessageHandler(
                filters.StatusUpdate.WEB_APP_DATA,
                self._handle_web_app_data
            )
        )

    async def _handle_web_app_data(self, update: Update, context):
        """Handle data received from Mini App."""
        web_app_data = update.effective_message.web_app_data

        if not web_app_data:
            return

        try:
            import json
            data = json.loads(web_app_data.data)

            if data.get("action") == "add_account":
                await self._process_add_account_from_webapp(
                    update, context, data
                )
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON from Mini App: {web_app_data.data}")
        except Exception as e:
            logger.error(f"Error processing Mini App data: {e}")
            await update.effective_message.reply_text(
                f"❌ Error: {str(e)}"
            )

    async def _process_add_account_from_webapp(self, update, context, data):
        """Process account addition from Mini App data."""
        user = self._get_or_create_user(update.effective_user)
        chat_id = update.effective_chat.id

        # Validate with Instagram API
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://graph.facebook.com/v18.0/{data['account_id']}",
                params={
                    "fields": "username",
                    "access_token": data["access_token"]
                },
                timeout=30.0
            )

            if response.status_code != 200:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", "Unknown error")
                await update.effective_message.reply_text(
                    f"❌ *Failed to add account*\n\n{error_msg}",
                    parse_mode="Markdown"
                )
                return

            api_data = response.json()
            username = api_data.get("username")

        # Check if exists and add/update
        existing = self.ig_account_service.get_account_by_instagram_id(
            data["account_id"]
        )

        if existing:
            account = self.ig_account_service.update_account_token(
                instagram_account_id=data["account_id"],
                access_token=data["access_token"],
                instagram_username=username,
                user=user,
                set_as_active=True,
                telegram_chat_id=chat_id
            )
            action = "Updated token for"
        else:
            account = self.ig_account_service.add_account(
                display_name=data["display_name"],
                instagram_account_id=data["account_id"],
                instagram_username=username,
                access_token=data["access_token"],
                user=user,
                set_as_active=True,
                telegram_chat_id=chat_id
            )
            action = "Added"

        await update.effective_message.reply_text(
            f"✅ *{action} @{account.instagram_username}*\n\n"
            "Your credentials were submitted securely via the Mini App.",
            parse_mode="Markdown"
        )

    async def _handle_account_selection_menu(self, user, query, context):
        """Show account selection menu with Mini App button."""
        chat_id = query.message.chat_id
        account_data = self.ig_account_service.get_accounts_for_display(chat_id)

        keyboard = []

        # Account list
        for acc in account_data["accounts"]:
            is_active = acc["id"] == account_data["active_account_id"]
            label = f"{'✅ ' if is_active else '   '}{acc['display_name']}"
            if acc["username"]:
                label += f" (@{acc['username']})"
            keyboard.append([
                InlineKeyboardButton(
                    label,
                    callback_data=f"switch_account:{acc['id']}"
                )
            ])

        # Add Account button - opens Mini App
        keyboard.append([
            InlineKeyboardButton(
                "➕ Add Account",
                web_app=WebAppInfo(url="https://your-domain.com/add_account.html")
            )
        ])

        # ... rest of menu ...
```

---

## Hosting Options

### Option 1: GitHub Pages (Recommended for Simplicity)

```
Pros:
- Free hosting
- HTTPS included
- Easy deployment (push to repo)
- CDN-backed

Cons:
- Separate repo or gh-pages branch
- Public repository required

Setup:
1. Create gh-pages branch with static files
2. Enable GitHub Pages in repo settings
3. Use URL: https://username.github.io/storyline-ai/add_account.html
```

### Option 2: Serve from Pi via FastAPI

```
Pros:
- Self-contained (no external dependencies)
- Full control

Cons:
- Requires HTTPS certificate (Let's Encrypt)
- Pi must be publicly accessible
- More complex setup

Setup:
1. Add FastAPI to requirements.txt
2. Create webapp routes
3. Configure nginx/caddy for HTTPS
4. Open port 443
```

### Option 3: Cloudflare Pages / Vercel

```
Pros:
- Free tier available
- Automatic HTTPS
- Global CDN
- Easy deployment

Cons:
- External dependency
- Requires account setup

Setup:
1. Create project on Cloudflare Pages
2. Connect to GitHub repo or upload files
3. Get URL for Mini App
```

---

## BotFather Configuration

To enable Mini Apps, configure with BotFather:

```
User: /mybots
User: Select @storyline_bot
User: Bot Settings → Menu Button

Set menu button URL to Mini App (optional)

Or configure inline via API:
Bot.set_chat_menu_button(
    menu_button=MenuButtonWebApp(
        text="Add Account",
        web_app=WebAppInfo(url="https://...")
    )
)
```

---

## Security Considerations

### Data Transmission
- Mini App uses Telegram's secure WebApp SDK
- Data sent via `sendData()` is encrypted in transit
- Only bot receives the data (not stored by Telegram)

### Token Handling
- Access token never appears in chat history
- Token goes directly to bot → validation → encrypted storage
- Form uses `type="password"` to prevent shoulder surfing

### Validation
- Client-side: Basic format validation (numeric ID, non-empty fields)
- Server-side: Full Instagram API validation before storage
- Same security as current implementation, minus the chat history risk

---

## Testing Plan

### Unit Tests
- [ ] Test `_handle_web_app_data` with valid JSON
- [ ] Test `_handle_web_app_data` with invalid JSON
- [ ] Test `_process_add_account_from_webapp` success path
- [ ] Test `_process_add_account_from_webapp` API error path
- [ ] Test `_process_add_account_from_webapp` existing account update

### Integration Tests
- [ ] Mini App form submission → bot receives data
- [ ] Form validation (client-side)
- [ ] Theme adaptation (light/dark mode)
- [ ] Mobile and desktop Telegram clients

### Manual Testing
- [ ] Full flow on iOS Telegram
- [ ] Full flow on Android Telegram
- [ ] Full flow on Telegram Desktop
- [ ] Full flow on Telegram Web

---

## Migration Path

### Phase 1: Parallel Support (Recommended)
1. Implement Mini App alongside existing message-based flow
2. Keep both "➕ Add Account" buttons:
   - `web_app=WebAppInfo(...)` for Mini App
   - `callback_data="accounts_config:add"` for message flow (fallback)
3. Let users choose their preferred method
4. Monitor usage to determine deprecation timeline

### Phase 2: Mini App Only
1. Remove message-based flow
2. Update documentation
3. Simplify TelegramService code

---

## Effort Estimate

| Task | Complexity | Estimate |
|------|------------|----------|
| Create Mini App HTML/CSS/JS | Low | 2-3 hours |
| Add WebAppData handler to TelegramService | Low | 1-2 hours |
| Set up hosting (GitHub Pages) | Low | 30 min |
| Configure BotFather | Low | 15 min |
| Testing | Medium | 2-3 hours |
| Documentation | Low | 1 hour |
| **Total** | | **7-10 hours** |

---

## Decision

**Proceed with current message-based approach for now.**

Rationale:
- Current implementation works with security warning
- Mini App adds deployment complexity (hosting requirement)
- Low priority given other roadmap items
- Can be implemented later as an enhancement

**Recommendation**: Revisit when:
- Users complain about manual message deletion
- Setting up API layer (FastAPI) for other features
- Preparing for multi-tenancy/public deployment

---

## References

- [Telegram Mini Apps Documentation](https://core.telegram.org/bots/webapps)
- [Telegram WebApp SDK](https://core.telegram.org/bots/webapps#initializing-mini-apps)
- [python-telegram-bot WebApp Support](https://docs.python-telegram-bot.org/en/stable/telegram.webappinfo.html)
- [Parent Document: Settings & Multi-Tenancy](phases/01_settings_and_multitenancy.md)
