# Phase 1.7: Inline Account Selector for Posting Workflow

**Status**: Planning (Feature Design)
**Created**: 2026-01-26
**Priority**: Medium (UX Enhancement)
**Dependencies**: Phase 1.5 (Instagram Account Management) - Complete
**Target Version**: v1.5.0
**Estimated Effort**: 3-5 days

---

## Executive Summary

This document outlines a UX enhancement to the posting workflow that adds inline account selection to posting action menus, making it easier for users to switch between Instagram accounts without navigating to `/settings`.

**Current State:**
- Multi-account support exists (Phase 1.5)
- Account selection happens in `/settings` → "Configure Accounts"
- Users must leave posting workflow to switch accounts
- Default account concept is unclear in settings UI

**Proposed Enhancement:**
- Add account selector button to posting workflow (auto-post, posted, skip, reject menus)
- Redesign `/settings` "Configure Accounts" to emphasize default account initialization
- Allow quick account switching during posting with visual feedback
- Maintain account context across posting actions

---

## Problem Statement

### Current User Journey

**Scenario**: User wants to post to a different Instagram account

```
1. User sees post notification in Telegram
2. Realizes this should go to different account
3. Navigates to /settings
4. Clicks "Configure Accounts" (unclear this is for account switching)
5. Selects different account
6. Returns to posting workflow
7. Clicks Posted/Auto Post
```

**Issues:**
1. **Context Switching**: User must leave posting workflow to change accounts
2. **Unclear Language**: "Configure Accounts" doesn't clearly indicate it's for switching
3. **Friction**: Multiple steps to perform a common action
4. **Lost Context**: Easy to forget which post they were working on

### Desired User Journey

```
1. User sees post notification in Telegram
2. Realizes this should go to different account
3. Clicks account selector button (📸 icon or account name)
4. Sees inline menu with all accounts
5. Selects target account
6. Returns to same posting workflow with new account active
7. Clicks Posted/Auto Post
```

**Benefits:**
1. **No Context Loss**: Stay in posting workflow
2. **One-Click Access**: Account selector readily available
3. **Visual Feedback**: See which account is active
4. **Faster Workflow**: Fewer steps to switch accounts

---

## User Interface Design

### 1. Posting Workflow with Account Selector

#### Current Layout (Phase 1.5)
```
┌─────────────────────────────────────┐
│  [Photo]                             │
│                                      │
│  📁 Category: memes                  │
│  📅 Scheduled: Jan 26, 2:30 PM      │
│                                      │
│  [🤖 Auto Post to Instagram]        │  (if enabled)
│                                      │
│  [✅ Posted]  [⏭️ Skip]             │
│                                      │
│  [📱 Open Instagram]                │
│                                      │
│  [🚫 Reject]                        │
└─────────────────────────────────────┘
```

#### Proposed Layout (Phase 1.7)
```
┌─────────────────────────────────────┐
│  [Photo]                             │
│                                      │
│  📁 Category: memes                  │
│  📅 Scheduled: Jan 26, 2:30 PM      │
│  📸 Account: Main Account           │  ← NEW: Shows active account (friendly name)
│                                      │
│  [🤖 Auto Post to Instagram]        │  (if enabled)
│                                      │
│  [✅ Posted]  [⏭️ Skip]             │
│                                      │
│  [📸 Main Account]                  │  ← NEW: Account selector (shows friendly name)
│                                      │
│  [📱 Open Instagram]                │
│                                      │
│  [🚫 Reject]                        │
└─────────────────────────────────────┘
```

**Design Considerations:**
- Account selector placed between manual actions and Open Instagram ✅
- Shows current account in caption (read-only indicator, friendly name)
- Button label shows friendly name: "📸 Main Account"
- Clicking opens simplified account selector (no add/remove)
- Consistent placement across all posting states

### 2. Account Selector Submenu

When user clicks "📸 Main Account" (the account button):

```
┌─────────────────────────────────────┐
│  📸 Select Instagram Account        │
│                                      │
│  Which account should this post     │
│  be attributed to?                   │
│                                      │
│  [✅ Main Account (@mainaccount)]   │  ← Currently active
│  [   Brand Account (@brandacct)]    │
│  [   Personal (@myaccount)]         │
│                                      │
│  [↩️ Back to Post]                  │
└─────────────────────────────────────┘
```

**Behavior:**
- Shows ONLY configured accounts (no add/remove options)
- Current account marked with ✅
- Shows both friendly name AND @username for clarity
- Clicking any account switches immediately and returns to post
- Clicking "Back to Post" returns without changing account
- Simpler than settings menu (focused on quick switching)

### 3. After Account Switch

User clicks a different account, sees immediate feedback:

```
┌─────────────────────────────────────┐
│  [Photo]                             │
│                                      │
│  📁 Category: memes                  │
│  📅 Scheduled: Jan 26, 2:30 PM      │
│  📸 Account: Brand Account          │  ← Updated (friendly name)
│                                      │
│  [🤖 Auto Post to Instagram]        │
│                                      │
│  [✅ Posted]  [⏭️ Skip]             │
│                                      │
│  [📸 Brand Account]                 │  ← Updated button label
│                                      │
│  [📱 Open Instagram]                │
│                                      │
│  [🚫 Reject]                        │
└─────────────────────────────────────┘

✅ Switched to Brand Account
```

**Feedback Mechanisms:**
- Caption updates to show new account (friendly name)
- Button label updates to show new account (friendly name)
- Toast notification confirms switch

### 4. Redesigned /settings Account Configuration

#### Current /settings (Phase 1.5)
```
┌─────────────────────────────────────┐
│  ⚙️ Bot Settings                    │
│                                      │
│  [  ] Dry Run                       │
│  [✅] Instagram API                 │
│  [▶️ Active]                        │
│  [📸 @mainaccount]                  │  ← Unclear purpose
│  [📊 Posts/Day: 3]                  │
│  ...                                 │
└─────────────────────────────────────┘
```

#### Proposed /settings (Phase 1.7)
```
┌─────────────────────────────────────┐
│  ⚙️ Bot Settings                    │
│                                      │
│  [  ] Dry Run                       │
│  [✅] Instagram API                 │
│  [▶️ Active]                        │
│  [📸 Default: Main Account]         │  ← NEW: Shows friendly name
│  [📊 Posts/Day: 3]                  │
│  ...                                 │
└─────────────────────────────────────┘
```

**Label Changes:**
- OLD: `"📸 @{username}"` or `"📸 Configure Accounts"`
- NEW: `"📸 Default: {friendly_name}"` or `"📸 Set Default Account"`

#### Account Configuration Menu (Redesigned)

When user clicks "📸 Default: Main Account" (or "📸 Set Default Account"):

```
┌─────────────────────────────────────┐
│  📸 Choose Default Account          │  ← Header: "Choose" not "Configure"
│                                      │
│  [✅ Main Account (@mainaccount)]   │  ← Current default
│  [   Brand Account (@brandacct)]    │
│  [   Personal (@myaccount)]         │
│                                      │
│  [➕ Add Account]                   │
│  [🗑️ Remove Account]                │
│                                      │
│  [↩️ Back to Settings]              │
└─────────────────────────────────────┘
```

**Key Changes:**
1. **Header**: "Choose Default Account" (action-oriented)
2. **Simplified**: No explainer text (cleaner UI)
3. **Current default marked with ✅**: Clear visual indicator
4. **Full configuration options**: Add/Remove available here (not in posting workflow)
5. **Purpose**: Sets default for NEW posts (can override during posting)

---

## Technical Implementation

### Database Changes

**No schema changes required!** All necessary structures exist from Phase 1.5:
- `chat_settings.active_instagram_account_id` - Stores active account per chat
- `instagram_accounts` table - Stores all accounts
- `api_tokens` table - Stores credentials per account

### Code Changes

#### 1. TelegramService Updates

**File**: `src/services/core/telegram_service.py`

##### A. Update Caption Builder

Add account indicator to captions:

```python
def _build_caption(self, media_item, queue_item=None, force_sent: bool = False, verbose: bool = True) -> str:
    """Build caption with account indicator."""

    # Get active account for this chat
    active_account = self.ig_account_service.get_active_account(self.channel_id)
    account_display = active_account.display_name if active_account else "Not set"

    # Add to caption
    caption = f"📁 Category: {media_item.category}\n"
    caption += f"📅 Scheduled: {queue_item.scheduled_for}\n"
    caption += f"📸 Account: {account_display}\n"  # NEW LINE (shows friendly name)
    # ... rest of caption
```

##### B. Update Keyboard Builder

Add account selector button to posting workflow:

```python
def send_notification(self, media_item, queue_item_id=None, force_sent=False):
    """Send notification with account selector."""

    # ... existing code ...

    # Build keyboard
    keyboard = []

    # Auto Post button (if enabled)
    if chat_settings.enable_instagram_api:
        keyboard.append([
            InlineKeyboardButton(
                "🤖 Auto Post to Instagram",
                callback_data=f"autopost:{queue_item_id}"
            ),
        ])

    # Manual workflow buttons
    keyboard.extend([
        [
            InlineKeyboardButton("✅ Posted", callback_data=f"posted:{queue_item_id}"),
            InlineKeyboardButton("⏭️ Skip", callback_data=f"skip:{queue_item_id}"),
        ],
        # NEW: Account selector button (shows friendly name)
        [
            InlineKeyboardButton(
                f"📸 {active_account.display_name}" if active_account else "📸 No Account",
                callback_data=f"select_account:{queue_item_id}"
            ),
        ],
        [
            InlineKeyboardButton("📱 Open Instagram", url="https://www.instagram.com/"),
        ],
        [
            InlineKeyboardButton("🚫 Reject", callback_data=f"reject:{queue_item_id}"),
        ]
    ])

    # ... rest of method
```

##### C. Add Account Selector Callback Handler

```python
async def _handle_callback(self, update, context):
    """Handle inline button callbacks."""
    # ... existing code ...

    # NEW: Account selector callbacks
    elif action == "select_account":
        await self._handle_account_selector_menu(data, user, query)
    elif action == "switch_account_post":
        await self._handle_account_switch_from_post(data, user, query)
    elif action == "back_to_post":
        await self._handle_back_to_post(data, user, query)


async def _handle_account_selector_menu(self, queue_id: str, user, query):
    """Show account selector submenu for a specific post."""
    chat_id = query.message.chat_id

    # Get queue item to preserve context
    queue_item = self.queue_repo.get_by_id(queue_id)
    if not queue_item:
        await query.edit_message_caption(caption="⚠️ Queue item not found")
        return

    # Get all accounts
    account_data = self.ig_account_service.get_accounts_for_display(chat_id)

    # Build keyboard with all accounts (simplified - no add/remove)
    keyboard = []
    for acc in account_data["accounts"]:
        is_active = acc["id"] == account_data["active_account_id"]
        # Show friendly name AND @username for clarity
        label = f"{'✅ ' if is_active else '   '}{acc['display_name']}"
        if acc["username"]:
            label += f" (@{acc['username']})"

        keyboard.append([
            InlineKeyboardButton(
                label,
                callback_data=f"switch_account_post:{queue_id}:{acc['id']}"
            )
        ])

    # Back button (no Add/Remove options in posting workflow)
    keyboard.append([
        InlineKeyboardButton(
            "↩️ Back to Post",
            callback_data=f"back_to_post:{queue_id}"
        )
    ])

    await query.edit_message_caption(
        caption=(
            "📸 *Select Instagram Account*\n\n"
            "Which account should this post be attributed to?"
        ),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    # Log interaction
    self.interaction_service.log_callback(
        user_id=str(user.id),
        callback_name="select_account",
        context={
            "queue_item_id": queue_id,
        },
        telegram_chat_id=chat_id,
        telegram_message_id=query.message.message_id,
    )


async def _handle_account_switch_from_post(self, data: str, user, query):
    """Handle account switch from posting workflow.

    Callback data format: "switch_account_post:{queue_id}:{account_id}"
    """
    parts = data.split(":")
    if len(parts) != 2:
        await query.answer("Invalid data", show_alert=True)
        return

    queue_id = parts[0]
    account_id = parts[1]
    chat_id = query.message.chat_id

    # Get queue item
    queue_item = self.queue_repo.get_by_id(queue_id)
    if not queue_item:
        await query.edit_message_caption(caption="⚠️ Queue item not found")
        return

    # Get media item
    media_item = self.media_repo.get_by_id(str(queue_item.media_item_id))
    if not media_item:
        await query.edit_message_caption(caption="⚠️ Media item not found")
        return

    try:
        # Switch account
        account = self.ig_account_service.switch_account(chat_id, account_id, user)

        # Log interaction
        self.interaction_service.log_callback(
            user_id=str(user.id),
            callback_name="switch_account_from_post",
            context={
                "queue_item_id": queue_id,
                "account_id": account_id,
                "account_username": account.instagram_username,
            },
            telegram_chat_id=chat_id,
            telegram_message_id=query.message.message_id,
        )

        # Show success toast (friendly name)
        await query.answer(f"✅ Switched to {account.display_name}")

        # Rebuild posting workflow with new account
        await self._rebuild_posting_workflow(queue_id, query)

    except ValueError as e:
        await query.answer(f"Error: {e}", show_alert=True)


async def _handle_back_to_post(self, queue_id: str, user, query):
    """Return to posting workflow without changing account."""
    await self._rebuild_posting_workflow(queue_id, query)


async def _rebuild_posting_workflow(self, queue_id: str, query):
    """Rebuild the original posting workflow message.

    Used after account selection or when returning from submenu.
    """
    queue_item = self.queue_repo.get_by_id(queue_id)
    if not queue_item:
        await query.edit_message_caption(caption="⚠️ Queue item not found")
        return

    media_item = self.media_repo.get_by_id(str(queue_item.media_item_id))
    if not media_item:
        await query.edit_message_caption(caption="⚠️ Media item not found")
        return

    # Rebuild caption with current account
    caption = self._build_caption(media_item, queue_item)

    # Rebuild keyboard with account selector
    keyboard = []
    chat_settings = self.settings_service.get_settings(query.message.chat_id)

    if chat_settings.enable_instagram_api:
        keyboard.append([
            InlineKeyboardButton(
                "🤖 Auto Post to Instagram",
                callback_data=f"autopost:{queue_id}"
            ),
        ])

    keyboard.extend([
        [
            InlineKeyboardButton("✅ Posted", callback_data=f"posted:{queue_id}"),
            InlineKeyboardButton("⏭️ Skip", callback_data=f"skip:{queue_id}"),
        ],
        [
            InlineKeyboardButton(
                "📸 Switch Account",
                callback_data=f"select_account:{queue_id}"
            ),
        ],
        [
            InlineKeyboardButton("📱 Open Instagram", url="https://www.instagram.com/"),
        ],
        [
            InlineKeyboardButton("🚫 Reject", callback_data=f"reject:{queue_id}"),
        ]
    ])

    await query.edit_message_caption(
        caption=caption,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
```

##### D. Update Settings Menu

Update the settings menu to clarify default account language:

```python
async def _handle_settings(self, update, context):
    """Handle /settings command - show settings menu."""
    # ... existing code ...

    # Update account button label (show friendly name, not @username)
    if account_data["active_account_name"]:
        account_label = f"📸 Default: {account_data['active_account_name']}"
    else:
        account_label = "📸 Set Default Account"

    keyboard = [
        # ... existing buttons ...
        [
            InlineKeyboardButton(
                account_label,  # UPDATED LABEL
                callback_data="settings_accounts:select"
            ),
        ],
        # ... rest of buttons ...
    ]
```

##### E. Update Account Configuration Menu

Add explainer text to account configuration:

```python
async def _handle_account_selection_menu(self, user, query):
    """Show account selection menu with updated language."""
    chat_id = query.message.chat_id
    account_data = self.ig_account_service.get_accounts_for_display(chat_id)

    # Build keyboard
    keyboard = []

    # Separate current default from other accounts
    current_default_id = account_data["active_account_id"]

    for acc in account_data["accounts"]:
        is_default = acc["id"] == current_default_id
        label = f"{'✅ ' if is_default else '   '}{acc['display_name']}"
        if acc["username"]:
            label += f" (@{acc['username']})"
        keyboard.append([
            InlineKeyboardButton(
                label,
                callback_data=f"switch_account:{acc['id']}"
            )
        ])

    # Add/Remove buttons
    keyboard.append([
        InlineKeyboardButton("➕ Add Account", callback_data="accounts_config:add"),
    ])
    if account_data["accounts"]:
        keyboard.append([
            InlineKeyboardButton("🗑️ Remove Account", callback_data="accounts_config:remove"),
        ])

    # Back button
    keyboard.append([
        InlineKeyboardButton("↩️ Back to Settings", callback_data="settings_accounts:back")
    ])

    # UPDATED: Simplified header (no explainer text)
    message = "📸 *Choose Default Account*"

    await query.edit_message_text(
        message,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    await query.answer()
```

#### 2. Update All Posting States

Ensure account selector appears in all posting-related menus:

- ✅ Initial post notification
- ✅ After clicking "Back" from dry run
- ✅ After clicking "Back" from autopost error
- ✅ When returning from reject confirmation (cancelled)

**Consistency Check**: Everywhere `_build_caption()` and keyboard construction happens, include the account selector button.

---

## Testing Strategy

### Unit Tests

**File**: `tests/src/services/test_telegram_service.py`

```python
class TestAccountSelectorInPostingWorkflow:
    """Test inline account selector in posting workflow."""

    def test_caption_includes_active_account(self, telegram_service, media_item, queue_item):
        """Test that caption shows active account (friendly name)."""
        # Arrange
        telegram_service.ig_account_service.get_active_account = Mock(
            return_value=Mock(display_name="Main Account", instagram_username="testaccount")
        )

        # Act
        caption = telegram_service._build_caption(media_item, queue_item)

        # Assert
        assert "📸 Account: Main Account" in caption

    def test_caption_handles_no_active_account(self, telegram_service, media_item, queue_item):
        """Test caption when no account is set."""
        # Arrange
        telegram_service.ig_account_service.get_active_account = Mock(return_value=None)

        # Act
        caption = telegram_service._build_caption(media_item, queue_item)

        # Assert
        assert "📸 Account: Not set" in caption

    def test_keyboard_includes_account_selector(self, telegram_service):
        """Test that posting keyboard includes account button with friendly name."""
        # Arrange
        telegram_service.ig_account_service.get_active_account = Mock(
            return_value=Mock(display_name="Main Account")
        )

        # Act
        keyboard = telegram_service._build_posting_keyboard("queue123", enable_api=False)

        # Assert
        # Flatten keyboard to get all buttons
        all_buttons = [btn for row in keyboard for btn in row]
        button_texts = [btn.text for btn in all_buttons]

        assert "📸 Main Account" in button_texts

        # Verify callback data
        account_selector_btn = next(
            btn for btn in all_buttons if "📸 Main Account" in btn.text
        )
        assert account_selector_btn.callback_data == "select_account:queue123"

    async def test_handle_account_selector_menu(self, telegram_service, mock_query):
        """Test showing account selector submenu."""
        # Arrange
        queue_id = "queue123"
        user = Mock(id="user1")
        telegram_service.queue_repo.get_by_id = Mock(
            return_value=Mock(id=queue_id, media_item_id="media1")
        )
        telegram_service.ig_account_service.get_accounts_for_display = Mock(
            return_value={
                "accounts": [
                    {"id": "acc1", "display_name": "Main", "username": "main"},
                    {"id": "acc2", "display_name": "Brand", "username": "brand"},
                ],
                "active_account_id": "acc1"
            }
        )

        # Act
        await telegram_service._handle_account_selector_menu(queue_id, user, mock_query)

        # Assert
        mock_query.edit_message_caption.assert_called_once()
        call_args = mock_query.edit_message_caption.call_args
        assert "Select Instagram Account" in call_args.kwargs["caption"]

        # Verify keyboard has both accounts
        keyboard = call_args.kwargs["reply_markup"].inline_keyboard
        assert len(keyboard) >= 2  # At least 2 accounts + back button

    async def test_account_switch_from_post(self, telegram_service, mock_query):
        """Test switching account from posting workflow."""
        # Arrange
        queue_id = "queue123"
        account_id = "acc2"
        data = f"{queue_id}:{account_id}"
        user = Mock(id="user1")

        telegram_service.queue_repo.get_by_id = Mock(
            return_value=Mock(id=queue_id, media_item_id="media1")
        )
        telegram_service.media_repo.get_by_id = Mock(
            return_value=Mock(id="media1", file_name="test.jpg", category="memes")
        )
        telegram_service.ig_account_service.switch_account = Mock(
            return_value=Mock(instagram_username="newaccount")
        )

        # Act
        await telegram_service._handle_account_switch_from_post(data, user, mock_query)

        # Assert
        # Verify account was switched
        telegram_service.ig_account_service.switch_account.assert_called_once_with(
            mock_query.message.chat_id,
            account_id,
            user
        )

        # Verify success toast (friendly name)
        mock_query.answer.assert_called_with("✅ Switched to New Account")

        # Verify workflow was rebuilt
        mock_query.edit_message_caption.assert_called_once()

    async def test_back_to_post_preserves_context(self, telegram_service, mock_query):
        """Test returning to post without changing account."""
        # Arrange
        queue_id = "queue123"
        telegram_service.queue_repo.get_by_id = Mock(
            return_value=Mock(id=queue_id, media_item_id="media1")
        )
        telegram_service.media_repo.get_by_id = Mock(
            return_value=Mock(id="media1", file_name="test.jpg", category="memes")
        )

        # Act
        await telegram_service._handle_back_to_post(queue_id, Mock(), mock_query)

        # Assert
        # Should rebuild posting workflow
        mock_query.edit_message_caption.assert_called_once()
        call_args = mock_query.edit_message_caption.call_args

        # Verify keyboard has account selector (with friendly name)
        keyboard = call_args.kwargs["reply_markup"].inline_keyboard
        all_buttons = [btn for row in keyboard for btn in row]
        button_texts = [btn.text for btn in all_buttons]
        # Should have account button (exact text depends on active account)
        assert any("📸" in text for text in button_texts)
```

### Integration Tests

**File**: `tests/integration/test_account_selector_workflow.py`

```python
class TestAccountSelectorIntegration:
    """Integration tests for account selector in real workflow."""

    @pytest.mark.integration
    async def test_full_account_switch_workflow(self, db_session):
        """Test complete flow: post → switch account → post."""
        # Arrange
        # Create two accounts
        account1 = create_instagram_account(
            display_name="Main Account",
            instagram_account_id="123",
            instagram_username="main"
        )
        account2 = create_instagram_account(
            display_name="Brand Account",
            instagram_account_id="456",
            instagram_username="brand"
        )

        # Create queue item
        media_item = create_media_item(file_path="/test/image.jpg")
        queue_item = create_queue_item(media_item_id=str(media_item.id))

        # Set account1 as active
        chat_id = -1001234567890
        settings_service = ChatSettingsService()
        settings_service.update(chat_id, active_instagram_account_id=str(account1.id))

        # Act & Assert
        telegram_service = TelegramService()

        # Step 1: Initial post shows account1 (friendly name)
        caption = telegram_service._build_caption(media_item, queue_item)
        assert "Main Account" in caption

        # Step 2: Switch to account2
        ig_account_service = InstagramAccountService()
        ig_account_service.switch_account(chat_id, str(account2.id))

        # Step 3: Rebuilt caption shows account2 (friendly name)
        caption = telegram_service._build_caption(media_item, queue_item)
        assert "Brand Account" in caption
        assert "Main Account" not in caption

    @pytest.mark.integration
    async def test_posting_history_records_correct_account(self, db_session):
        """Test that posting history records which account was active."""
        # TODO: This test depends on Phase 2 (instagram_story_id in posting_history)
        # For now, verify that active account at time of posting is retrievable
        pass
```

### Manual Testing Checklist

#### Account Selector Display
- [ ] Account selector button appears in initial post notification
- [ ] Account selector button appears after clicking "Back" from dry run
- [ ] Account selector button appears after autopost error
- [ ] Account selector button appears when cancelling reject
- [ ] Caption shows current active account
- [ ] Caption updates immediately after account switch

#### Account Selector Functionality
- [ ] Clicking "Switch Account" shows all configured accounts
- [ ] Current account is marked with ✅
- [ ] Clicking an account switches and returns to post
- [ ] Toast notification confirms switch
- [ ] Clicking "Back to Post" returns without switching
- [ ] Optional "Add New Account" button works (if implemented)

#### Settings Menu Changes
- [ ] Settings shows "📸 Default: @username" when account set
- [ ] Settings shows "📸 Set Default Account" when no account
- [ ] Clicking button opens account configuration
- [ ] Account configuration has explainer text about default vs inline switching
- [ ] Selecting account in settings updates default

#### Multi-Account Scenarios
- [ ] Works with 1 account (selector shows single option)
- [ ] Works with 2 accounts
- [ ] Works with 3+ accounts
- [ ] Works when no account configured (shows "Not set" in caption)

#### Edge Cases
- [ ] Account switch works when Instagram API disabled
- [ ] Account switch works when Instagram API enabled
- [ ] Account switch works in dry run mode
- [ ] Queue item not found handled gracefully
- [ ] Account not found handled gracefully

---

## Rollout Plan

### Phase 1: Core Implementation (Day 1-2)

1. **Update Caption Builder** ✅
   - Add account indicator to `_build_caption()`
   - Handle case when no account set

2. **Update Keyboard Builder** ✅
   - Add "Switch Account" button to posting keyboard
   - Ensure consistent placement across all states

3. **Implement Callback Handlers** ✅
   - `_handle_account_selector_menu()` - Show account list
   - `_handle_account_switch_from_post()` - Switch and return
   - `_handle_back_to_post()` - Return without switching
   - `_rebuild_posting_workflow()` - Reconstruct post view

### Phase 2: Settings Menu Updates (Day 2-3)

1. **Update Settings Display** ✅
   - Change button label to "Default: @username"
   - Add explainer text to account configuration menu

2. **Test Settings Integration** ✅
   - Verify default account setting still works
   - Ensure no regressions in existing functionality

### Phase 3: Testing (Day 3-4)

1. **Unit Tests** ✅
   - Caption building with accounts
   - Keyboard construction
   - Callback handlers

2. **Integration Tests** ✅
   - Full workflow tests
   - Multi-account scenarios

3. **Manual Testing** ✅
   - Follow manual testing checklist
   - Test on production Pi

### Phase 4: Documentation & Deployment (Day 4-5)

1. **Update Documentation** ✅
   - Update CLAUDE.md with new button
   - Update user-facing guides
   - Update CHANGELOG.md

2. **Deploy to Production** ✅
   - Backup database
   - Deploy code changes
   - Monitor logs for errors
   - Test with real posts

---

## Success Metrics

### User Experience
- [ ] Reduced steps to switch accounts (from 7 to 3)
- [ ] Increased account switching during posting (measurable via interaction logs)
- [ ] Reduced confusion about account configuration (qualitative feedback)

### Technical
- [ ] No performance regression (button interactions < 500ms)
- [ ] No errors in logs related to account selector
- [ ] All tests passing (100% coverage for new code)

### Adoption
- [ ] Feature documented in help text
- [ ] Users discover feature without explicit training
- [ ] Default account concept clearly understood

---

## Future Enhancements

### Quick Add from Selector
Add "➕ Add New Account" directly from account selector:
- Opens add account flow
- Returns to post after completion
- Reduces friction for new account setup

### Account-Specific Media
Show which accounts have posted this media before:
```
📸 Select Account

Post history for this image:
• @mainaccount - Posted 2 times
• @brandacct - Never posted
• @personal - Posted 1 time
```

### Account Presets
Allow users to set account preferences per category:
```
Category: memes → @mainaccount
Category: merch → @brandacct
```

### Account Rotation
Auto-rotate between accounts for variety:
```
[⚙️ Settings]
[🔄 Account Rotation: ON]
Rotation: Main (60%) → Brand (40%)
```

---

## Risks & Mitigations

### Risk 1: Button Overload
**Risk**: Too many buttons in posting workflow
**Severity**: Medium
**Mitigation**:
- Place account selector strategically (after primary actions)
- Use collapsible submenu pattern
- Consider hiding when only 1 account configured

### Risk 2: Callback Data Length
**Risk**: Telegram limits callback_data to 64 bytes
**Severity**: Low
**Mitigation**:
- Current format: `switch_account_post:{queue_id}:{account_id}`
- UUIDs are 36 chars, total ~85 chars (too long!)
- **Solution**: Use shorter format: `swp:{short_queue_id}:{short_account_id}`
- Or store context in database with short lookup key

**Updated Callback Format**:
```python
# Instead of: "switch_account_post:550e8400-e29b-41d4-a716-446655440000:660f9511-f39c-52e5-b827-557766551111"
# Use: "swp:550e8400:660f9511" (first 8 chars of each UUID)

# Or use sequential IDs from callback_context table:
# "swp:ctx123" → lookup in database → get full queue_id + account_id
```

### Risk 3: State Management
**Risk**: User switches account mid-autopost
**Severity**: Low
**Mitigation**:
- Autopost uses account active at time of button click
- Account switch disabled during autopost in progress
- Clear messaging about which account was used

### Risk 4: Friendly Name Truncation
**Risk**: Long friendly names cause button text overflow
**Severity**: Low
**Mitigation**:
- Telegram handles long button text automatically (wraps or truncates)
- Recommend keeping display names under 20 characters
- Consider truncating in button (full name in caption): "📸 Very Long Account N..."

---

## Related Documents

- **Phase 1.5 Implementation**: Instagram Account Management (Complete)
- **Database Schema**: `chat_settings`, `instagram_accounts`, `api_tokens`
- **User Interactions Design**: `documentation/planning/phases/user-interactions-design.md`

---

## Changelog

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2026-01-26 | 1.0 | Initial feature design | Claude |

---

## Appendix: Callback Data Format

### Current Callbacks (Phase 1.5)
```
posted:{queue_id}
skip:{queue_id}
autopost:{queue_id}
reject:{queue_id}
back:{queue_id}
settings_accounts:select
switch_account:{account_id}
```

### New Callbacks (Phase 1.7)
```
select_account:{queue_id}                      # Show account selector
switch_account_post:{queue_id}:{account_id}    # Switch from post (64 byte limit!)
back_to_post:{queue_id}                        # Return to post
```

### Optimization (if needed)
```
sa:{queue_id}                   # select_account
sap:{q_id}:{a_id}              # switch_account_post (shortened IDs)
btp:{queue_id}                 # back_to_post
```

Or use context lookup:
```
sa:{queue_id}
ctx:{context_id}               # Look up full data in callback_context table
btp:{queue_id}
```
