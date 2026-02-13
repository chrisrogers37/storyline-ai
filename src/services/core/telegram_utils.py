"""Telegram handler utilities - shared patterns extracted from handler modules.

This module contains common patterns used across multiple Telegram handler files:
- Queue item validation
- Standard action keyboard builders
- Settings edit state management
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.utils.logger import logger

if TYPE_CHECKING:
    from src.services.core.telegram_service import TelegramService


# =========================================================================
# Pattern 1: Queue Item Validation
# =========================================================================


async def validate_queue_item(service: TelegramService, queue_id: str, query):
    """Fetch a queue item by ID, showing an error if not found.

    This is the standard validation pattern used by nearly every callback handler.
    On success, returns the queue item. On failure, edits the message caption
    with an error and returns None.

    Args:
        service: The parent TelegramService instance (provides queue_repo)
        queue_id: The queue item UUID string
        query: The Telegram CallbackQuery to edit on failure

    Returns:
        The queue item if found, or None if not found (message already updated)
    """
    queue_item = service.queue_repo.get_by_id(queue_id)
    if not queue_item:
        await query.edit_message_caption(caption="⚠️ Queue item not found")
        return None
    return queue_item


async def validate_queue_and_media(service: TelegramService, queue_id: str, query):
    """Fetch both queue item and its associated media item.

    Convenience wrapper that validates the queue item and then fetches the
    associated media item. Returns (None, None) on any failure, with the
    message already updated with an error.

    Args:
        service: The parent TelegramService instance
        queue_id: The queue item UUID string
        query: The Telegram CallbackQuery to edit on failure

    Returns:
        Tuple of (queue_item, media_item), or (None, None) on failure
    """
    queue_item = await validate_queue_item(service, queue_id, query)
    if not queue_item:
        return None, None

    media_item = service.media_repo.get_by_id(str(queue_item.media_item_id))
    if not media_item:
        await query.edit_message_caption(caption="⚠️ Media item not found")
        return None, None

    return queue_item, media_item


# =========================================================================
# Pattern 2: Standard Action Keyboard
# =========================================================================


def build_queue_action_keyboard(
    queue_id: str,
    enable_instagram_api: bool = False,
    active_account=None,
) -> InlineKeyboardMarkup:
    """Build the standard action keyboard for a queue item notification.

    This is the keyboard shown on every posting notification message. It includes:
    - Auto Post button (if Instagram API is enabled)
    - Posted / Skip buttons
    - Reject button
    - Account selector button
    - Open Instagram link

    Args:
        queue_id: The queue item UUID string (used in callback_data)
        enable_instagram_api: Whether to show the Auto Post button
        active_account: The active InstagramAccount object (for account label),
                        or None to show "No Account"

    Returns:
        InlineKeyboardMarkup with the complete action keyboard
    """
    keyboard = []

    # Auto Post button (if Instagram API is enabled)
    if enable_instagram_api:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "🤖 Auto Post to Instagram",
                    callback_data=f"autopost:{queue_id}",
                ),
            ]
        )

    # Status action buttons
    keyboard.extend(
        [
            [
                InlineKeyboardButton("✅ Posted", callback_data=f"posted:{queue_id}"),
                InlineKeyboardButton("⏭️ Skip", callback_data=f"skip:{queue_id}"),
            ],
            [
                InlineKeyboardButton("🚫 Reject", callback_data=f"reject:{queue_id}"),
            ],
        ]
    )

    # Instagram-related buttons
    account_label = (
        f"📸 {active_account.display_name}" if active_account else "📸 No Account"
    )
    keyboard.extend(
        [
            [
                InlineKeyboardButton(
                    account_label,
                    callback_data=f"select_account:{queue_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "📱 Open Instagram", url="https://www.instagram.com/"
                ),
            ],
        ]
    )

    return InlineKeyboardMarkup(keyboard)


def build_error_recovery_keyboard(
    queue_id: str,
    enable_instagram_api: bool = False,
) -> InlineKeyboardMarkup:
    """Build the keyboard shown after an auto-post failure.

    Similar to the standard keyboard but with a "Retry" button instead of
    Auto Post, and no account selector.

    Args:
        queue_id: The queue item UUID string
        enable_instagram_api: Whether to show the Retry Auto Post button

    Returns:
        InlineKeyboardMarkup with retry and fallback options
    """
    keyboard = []

    if enable_instagram_api:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "🔄 Retry Auto Post",
                    callback_data=f"autopost:{queue_id}",
                ),
            ]
        )

    keyboard.extend(
        [
            [
                InlineKeyboardButton("✅ Posted", callback_data=f"posted:{queue_id}"),
                InlineKeyboardButton("⏭️ Skip", callback_data=f"skip:{queue_id}"),
            ],
            [
                InlineKeyboardButton(
                    "📱 Open Instagram",
                    url="https://www.instagram.com/",
                ),
            ],
            [
                InlineKeyboardButton("🚫 Reject", callback_data=f"reject:{queue_id}"),
            ],
        ]
    )

    return InlineKeyboardMarkup(keyboard)


# =========================================================================
# Pattern 3: Cancel Button Keyboard (for settings edit flows)
# =========================================================================


CANCEL_KEYBOARD = InlineKeyboardMarkup(
    [[InlineKeyboardButton("❌ Cancel", callback_data="settings_edit_cancel")]]
)
"""Pre-built keyboard with a single Cancel button for settings edit flows.

Used in all settings edit prompts (posts_per_day, hours_start, hours_end)
and their error states. This is a module-level constant because the keyboard
never changes.
"""


# =========================================================================
# Pattern 4: Settings Edit State Cleanup
# =========================================================================


SETTINGS_EDIT_KEYS = [
    "settings_edit_state",
    "settings_edit_chat_id",
    "settings_edit_message_id",
    "settings_edit_hours_start",
]
"""All context.user_data keys used during a settings edit conversation."""


def clear_settings_edit_state(context) -> None:
    """Clear all settings edit conversation state from context.user_data.

    Call this when a settings edit conversation ends (success, cancel, or error).
    Safely pops all keys without raising if they don't exist.

    Args:
        context: The Telegram CallbackContext or equivalent with user_data dict
    """
    for key in SETTINGS_EDIT_KEYS:
        context.user_data.pop(key, None)


ADD_ACCOUNT_KEYS = [
    "add_account_state",
    "add_account_data",
    "add_account_chat_id",
    "add_account_messages",
]
"""All context.user_data keys used during an add-account conversation."""


def clear_add_account_state(context) -> None:
    """Clear all add-account conversation state from context.user_data.

    Call this when the add-account conversation ends (success, cancel, or error).

    Args:
        context: The Telegram CallbackContext or equivalent with user_data dict
    """
    for key in ADD_ACCOUNT_KEYS:
        context.user_data.pop(key, None)


# =========================================================================
# Pattern 5: Account Management Keyboard
# =========================================================================


def build_account_management_keyboard(
    account_data: dict,
) -> list[list[InlineKeyboardButton]]:
    """Build the account list rows + management buttons for the accounts config menu.

    Produces the keyboard rows used by both handle_account_selection_menu()
    and the add-account success confirmation. The caller wraps the result
    in InlineKeyboardMarkup.

    Args:
        account_data: Dict from ig_account_service.get_accounts_for_display(),
                      must contain keys "accounts" (list of dicts with id,
                      display_name, username) and "active_account_id" (str or None).

    Returns:
        List of keyboard rows (list of lists of InlineKeyboardButton).
    """
    keyboard: list[list[InlineKeyboardButton]] = []

    if account_data["accounts"]:
        for account in account_data["accounts"]:
            is_active = account["id"] == account_data["active_account_id"]
            label = f"{'✅ ' if is_active else '   '}{account['display_name']}"
            if account["username"]:
                label += f" (@{account['username']})"
            keyboard.append(
                [
                    InlineKeyboardButton(
                        label, callback_data=f"switch_account:{account['id']}"
                    )
                ]
            )
    else:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "No accounts configured", callback_data="accounts_config:noop"
                )
            ]
        )

    keyboard.append(
        [InlineKeyboardButton("➕ Add Account", callback_data="accounts_config:add")]
    )

    if account_data["accounts"]:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "🗑️ Remove Account", callback_data="accounts_config:remove"
                )
            ]
        )

    keyboard.append(
        [
            InlineKeyboardButton(
                "↩️ Back to Settings", callback_data="settings_accounts:back"
            )
        ]
    )

    return keyboard


# =========================================================================
# Pattern 6: Conversation Message Cleanup
# =========================================================================


async def cleanup_conversation_messages(
    bot,
    chat_id: int,
    message_ids: list[int],
    exclude_id: int | None = None,
) -> int:
    """Delete a list of tracked conversation messages (best-effort).

    Iterates through message_ids and attempts to delete each one via the
    Telegram Bot API. Failures are logged at DEBUG level and silently
    ignored (the message may have been already deleted or be inaccessible).

    Args:
        bot: The telegram.Bot instance (context.bot).
        chat_id: The Telegram chat ID to delete messages from.
        message_ids: List of message IDs to delete.
        exclude_id: Optional message ID to skip (e.g., a message that will
                    be edited instead of deleted).

    Returns:
        The number of messages successfully deleted.
    """
    deleted = 0
    for msg_id in message_ids:
        if exclude_id is not None and msg_id == exclude_id:
            continue
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
            deleted += 1
        except Exception as e:
            logger.debug(f"Could not delete conversation message {msg_id}: {e}")
    return deleted
