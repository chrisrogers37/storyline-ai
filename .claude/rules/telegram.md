---
paths:
  - "src/services/core/telegram_*"
---

# Telegram Bot

## Active Commands

| Command | Description | Handler |
|---------|-------------|---------|
| `/start` | Open setup wizard or show dashboard | `telegram_commands.py` |
| `/status` | Health, media stats, queue status | `telegram_commands.py` |
| `/help` | Show available commands | `telegram_commands.py` |
| `/next` | Force-send next post now | `telegram_commands.py` |
| `/cleanup` | Delete recent bot messages | `telegram_commands.py` |
| `/setup` / `/settings` | Quick settings & toggles | `telegram_settings.py` |

**Retired commands**: `/queue`, `/pause`, `/resume`, `/history`, `/sync`, `/schedule`, `/stats`, `/locks`, `/reset`, `/dryrun`, `/backfill`, `/connect` — respond with redirect messages but are not listed in the bot menu.

## Callback Actions

| Action | Description | Handler |
|--------|-------------|---------|
| `posted:{queue_id}` | Mark as posted | `telegram_callbacks.py` |
| `skip:{queue_id}` | Skip for later | `telegram_callbacks.py` |
| `reject:{queue_id}` | Initiate rejection | `telegram_callbacks.py` |
| `confirm_reject:{queue_id}` | Confirm rejection | `telegram_callbacks.py` |
| `autopost:{queue_id}` | Auto-post via API | `telegram_autopost.py` |
| `settings_toggle:{setting}` | Toggle setting | `telegram_settings.py` |
| `sa:{queue_id}` | Account selector | `telegram_accounts.py` |
| `sap:{queue_id}:{account_id}` | Switch account | `telegram_accounts.py` |

## Handler Architecture

Telegram handler modules use a **composition pattern** — they receive a reference to the parent `TelegramService` and are NOT standalone services. `InteractionService` intentionally does NOT extend `BaseService` to avoid recursive tracking.
