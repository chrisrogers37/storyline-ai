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
