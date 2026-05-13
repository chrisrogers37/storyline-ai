"""Hardcoded defaults for per-chat settings.

The DB is the single source of truth at runtime — every per-chat setting
lives on `chat_settings`. These constants are used in two places:

1. **Bootstrap** (`ChatSettingsRepository.get_or_create`) — when a brand
   new chat first interacts with the bot we need *some* starting values.
   These are them.

2. **Runtime fallback** — when an older chat_settings row predates a
   migration (column NULL), services read the per-chat value with these
   constants as the fallback. Once the user touches the dashboard the
   NULL becomes an explicit value and the constant stops being consulted.

Operators wanting deployment-wide overrides should set the values once
via the dashboard for the admin chat — there is no longer an env-var
escape hatch for per-chat settings.
"""

# Posting cadence
DEFAULT_POSTS_PER_DAY = 3
DEFAULT_POSTING_HOURS_START = 9  # UTC
DEFAULT_POSTING_HOURS_END = 22  # UTC

# Lock TTLs (days)
DEFAULT_REPOST_TTL_DAYS = 30
DEFAULT_SKIP_TTL_DAYS = 45

# Toggles
DEFAULT_DRY_RUN_MODE = False
DEFAULT_ENABLE_INSTAGRAM_API = False
DEFAULT_SHOW_VERBOSE_NOTIFICATIONS = True
DEFAULT_MEDIA_SYNC_ENABLED = False
DEFAULT_SEND_LIFECYCLE_NOTIFICATIONS = True

# Caption rendering
DEFAULT_CAPTION_STYLE = "enhanced"  # or "simple"

# Media source (NULL/None forces the user through the setup wizard)
DEFAULT_MEDIA_SOURCE_TYPE = "local"

# Instagram deep-link fallback used by the bot keyboard's "Open Instagram"
# button when an active account has no `instagram_username` set. The
# plain instagram.com URL works on every device; a per-username deep
# link (instagram://user?username=...) is preferred when available.
DEFAULT_INSTAGRAM_DEEPLINK_URL = "https://www.instagram.com/"
