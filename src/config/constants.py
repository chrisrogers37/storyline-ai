"""Shared application constants.

Constants used by multiple modules are defined here to ensure consistency.
Module-specific constants should be defined as class-level attributes on
their respective service classes instead.
"""

# Posting schedule limits (used by telegram_settings.py and settings_service.py)
MIN_POSTS_PER_DAY = 1
MAX_POSTS_PER_DAY = 50
MIN_POSTING_HOUR = 0
MAX_POSTING_HOUR = 23

# Instagram caption limits (used by caption_service.py)
MAX_CAPTION_LENGTH = 2200  # Instagram caption character limit

# Instagram Login API base URLs (unversioned, separate from Meta Graph API)
# Used by instagram_login_oauth.py and token_refresh.py
IG_LOGIN_GRAPH_BASE = "https://graph.instagram.com"
IG_LOGIN_API_BASE = "https://api.instagram.com"
