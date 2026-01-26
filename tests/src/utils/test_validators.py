"""Tests for validators utility."""

import pytest
from unittest.mock import patch, MagicMock

from src.utils.validators import ConfigValidator


@pytest.mark.unit
class TestConfigValidator:
    """Test suite for ConfigValidator."""

    @patch("src.utils.validators.settings")
    @patch("src.utils.validators.Path")
    def test_validate_all_valid_config(self, mock_path, mock_settings):
        """Test validate_all with valid configuration."""
        # Set up valid config
        mock_settings.POSTS_PER_DAY = 3
        mock_settings.POSTING_HOURS_START = 14
        mock_settings.POSTING_HOURS_END = 2
        mock_settings.REPOST_TTL_DAYS = 30
        mock_settings.TELEGRAM_BOT_TOKEN = "123456:ABC-DEF1234ghIkl"
        mock_settings.TELEGRAM_CHANNEL_ID = -1001234567890
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = 123456789
        mock_settings.ENABLE_INSTAGRAM_API = False
        mock_settings.DB_NAME = "storyline_ai"
        mock_settings.MEDIA_DIR = "/media/stories"

        # Mock path exists
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance

        is_valid, errors = ConfigValidator.validate_all()

        assert is_valid is True
        assert len(errors) == 0

    @patch("src.utils.validators.settings")
    @patch("src.utils.validators.Path")
    def test_validate_all_missing_telegram_token(self, mock_path, mock_settings):
        """Test validation fails with missing bot token."""
        mock_settings.POSTS_PER_DAY = 3
        mock_settings.POSTING_HOURS_START = 14
        mock_settings.POSTING_HOURS_END = 2
        mock_settings.REPOST_TTL_DAYS = 30
        mock_settings.TELEGRAM_BOT_TOKEN = ""  # Missing
        mock_settings.TELEGRAM_CHANNEL_ID = -1001234567890
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = 123456789
        mock_settings.ENABLE_INSTAGRAM_API = False
        mock_settings.DB_NAME = "storyline_ai"
        mock_settings.MEDIA_DIR = "/media/stories"

        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance

        is_valid, errors = ConfigValidator.validate_all()

        assert is_valid is False
        assert any("TELEGRAM_BOT_TOKEN" in error for error in errors)

    @patch("src.utils.validators.settings")
    @patch("src.utils.validators.Path")
    def test_validate_all_missing_channel_id(self, mock_path, mock_settings):
        """Test validation fails with missing channel ID."""
        mock_settings.POSTS_PER_DAY = 3
        mock_settings.POSTING_HOURS_START = 14
        mock_settings.POSTING_HOURS_END = 2
        mock_settings.REPOST_TTL_DAYS = 30
        mock_settings.TELEGRAM_BOT_TOKEN = "123456:ABC"
        mock_settings.TELEGRAM_CHANNEL_ID = None  # Missing
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = 123456789
        mock_settings.ENABLE_INSTAGRAM_API = False
        mock_settings.DB_NAME = "storyline_ai"
        mock_settings.MEDIA_DIR = "/media/stories"

        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance

        is_valid, errors = ConfigValidator.validate_all()

        assert is_valid is False
        assert any("TELEGRAM_CHANNEL_ID" in error for error in errors)

    @patch("src.utils.validators.settings")
    @patch("src.utils.validators.Path")
    def test_validate_all_invalid_posts_per_day_zero(self, mock_path, mock_settings):
        """Test validation fails with invalid posts per day (zero)."""
        mock_settings.POSTS_PER_DAY = 0  # Invalid
        mock_settings.POSTING_HOURS_START = 14
        mock_settings.POSTING_HOURS_END = 2
        mock_settings.REPOST_TTL_DAYS = 30
        mock_settings.TELEGRAM_BOT_TOKEN = "123456:ABC"
        mock_settings.TELEGRAM_CHANNEL_ID = -1001234567890
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = 123456789
        mock_settings.ENABLE_INSTAGRAM_API = False
        mock_settings.DB_NAME = "storyline_ai"
        mock_settings.MEDIA_DIR = "/media/stories"

        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance

        is_valid, errors = ConfigValidator.validate_all()

        assert is_valid is False
        assert any("POSTS_PER_DAY" in error for error in errors)

    @patch("src.utils.validators.settings")
    @patch("src.utils.validators.Path")
    def test_validate_all_invalid_posts_per_day_too_high(
        self, mock_path, mock_settings
    ):
        """Test validation fails with posts per day > 10."""
        mock_settings.POSTS_PER_DAY = 15  # Invalid (> 10)
        mock_settings.POSTING_HOURS_START = 14
        mock_settings.POSTING_HOURS_END = 2
        mock_settings.REPOST_TTL_DAYS = 30
        mock_settings.TELEGRAM_BOT_TOKEN = "123456:ABC"
        mock_settings.TELEGRAM_CHANNEL_ID = -1001234567890
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = 123456789
        mock_settings.ENABLE_INSTAGRAM_API = False
        mock_settings.DB_NAME = "storyline_ai"
        mock_settings.MEDIA_DIR = "/media/stories"

        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance

        is_valid, errors = ConfigValidator.validate_all()

        assert is_valid is False
        assert any("POSTS_PER_DAY" in error for error in errors)

    @patch("src.utils.validators.settings")
    @patch("src.utils.validators.Path")
    def test_validate_all_invalid_posting_hours_start(self, mock_path, mock_settings):
        """Test validation fails with invalid hours start."""
        mock_settings.POSTS_PER_DAY = 3
        mock_settings.POSTING_HOURS_START = 25  # Invalid (> 23)
        mock_settings.POSTING_HOURS_END = 2
        mock_settings.REPOST_TTL_DAYS = 30
        mock_settings.TELEGRAM_BOT_TOKEN = "123456:ABC"
        mock_settings.TELEGRAM_CHANNEL_ID = -1001234567890
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = 123456789
        mock_settings.ENABLE_INSTAGRAM_API = False
        mock_settings.DB_NAME = "storyline_ai"
        mock_settings.MEDIA_DIR = "/media/stories"

        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance

        is_valid, errors = ConfigValidator.validate_all()

        assert is_valid is False
        assert any("POSTING_HOURS_START" in error for error in errors)

    @patch("src.utils.validators.settings")
    @patch("src.utils.validators.Path")
    def test_validate_all_invalid_posting_hours_end(self, mock_path, mock_settings):
        """Test validation fails with invalid hours end."""
        mock_settings.POSTS_PER_DAY = 3
        mock_settings.POSTING_HOURS_START = 14
        mock_settings.POSTING_HOURS_END = 30  # Invalid (> 23)
        mock_settings.REPOST_TTL_DAYS = 30
        mock_settings.TELEGRAM_BOT_TOKEN = "123456:ABC"
        mock_settings.TELEGRAM_CHANNEL_ID = -1001234567890
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = 123456789
        mock_settings.ENABLE_INSTAGRAM_API = False
        mock_settings.DB_NAME = "storyline_ai"
        mock_settings.MEDIA_DIR = "/media/stories"

        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance

        is_valid, errors = ConfigValidator.validate_all()

        assert is_valid is False
        assert any("POSTING_HOURS_END" in error for error in errors)

    @patch("src.utils.validators.settings")
    @patch("src.utils.validators.Path")
    def test_validate_all_invalid_repost_ttl(self, mock_path, mock_settings):
        """Test validation fails with invalid repost TTL."""
        mock_settings.POSTS_PER_DAY = 3
        mock_settings.POSTING_HOURS_START = 14
        mock_settings.POSTING_HOURS_END = 2
        mock_settings.REPOST_TTL_DAYS = 0  # Invalid (< 1)
        mock_settings.TELEGRAM_BOT_TOKEN = "123456:ABC"
        mock_settings.TELEGRAM_CHANNEL_ID = -1001234567890
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = 123456789
        mock_settings.ENABLE_INSTAGRAM_API = False
        mock_settings.DB_NAME = "storyline_ai"
        mock_settings.MEDIA_DIR = "/media/stories"

        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance

        is_valid, errors = ConfigValidator.validate_all()

        assert is_valid is False
        assert any("REPOST_TTL_DAYS" in error for error in errors)

    @patch("src.utils.validators.settings")
    @patch("src.utils.validators.Path")
    def test_validate_all_missing_db_name(self, mock_path, mock_settings):
        """Test validation fails with missing DB name."""
        mock_settings.POSTS_PER_DAY = 3
        mock_settings.POSTING_HOURS_START = 14
        mock_settings.POSTING_HOURS_END = 2
        mock_settings.REPOST_TTL_DAYS = 30
        mock_settings.TELEGRAM_BOT_TOKEN = "123456:ABC"
        mock_settings.TELEGRAM_CHANNEL_ID = -1001234567890
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = 123456789
        mock_settings.ENABLE_INSTAGRAM_API = False
        mock_settings.DB_NAME = ""  # Missing
        mock_settings.MEDIA_DIR = "/media/stories"

        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance

        is_valid, errors = ConfigValidator.validate_all()

        assert is_valid is False
        assert any("DB_NAME" in error for error in errors)

    @patch("src.utils.validators.settings")
    @patch("src.utils.validators.Path")
    def test_validate_all_media_dir_not_exists(self, mock_path, mock_settings):
        """Test validation fails when media dir doesn't exist."""
        mock_settings.POSTS_PER_DAY = 3
        mock_settings.POSTING_HOURS_START = 14
        mock_settings.POSTING_HOURS_END = 2
        mock_settings.REPOST_TTL_DAYS = 30
        mock_settings.TELEGRAM_BOT_TOKEN = "123456:ABC"
        mock_settings.TELEGRAM_CHANNEL_ID = -1001234567890
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = 123456789
        mock_settings.ENABLE_INSTAGRAM_API = False
        mock_settings.DB_NAME = "storyline_ai"
        mock_settings.MEDIA_DIR = "/nonexistent/path"

        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = False  # Doesn't exist
        mock_path.return_value = mock_path_instance

        is_valid, errors = ConfigValidator.validate_all()

        assert is_valid is False
        assert any("MEDIA_DIR" in error for error in errors)

    @patch("src.utils.validators.settings")
    @patch("src.utils.validators.Path")
    def test_validate_all_instagram_api_missing_config(self, mock_path, mock_settings):
        """Test validation fails when Instagram API enabled but config missing."""
        mock_settings.POSTS_PER_DAY = 3
        mock_settings.POSTING_HOURS_START = 14
        mock_settings.POSTING_HOURS_END = 2
        mock_settings.REPOST_TTL_DAYS = 30
        mock_settings.TELEGRAM_BOT_TOKEN = "123456:ABC"
        mock_settings.TELEGRAM_CHANNEL_ID = -1001234567890
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = 123456789
        mock_settings.ENABLE_INSTAGRAM_API = True  # Enabled
        mock_settings.INSTAGRAM_ACCOUNT_ID = ""  # Missing
        mock_settings.INSTAGRAM_ACCESS_TOKEN = ""  # Missing
        mock_settings.CLOUDINARY_CLOUD_NAME = ""  # Missing
        mock_settings.DB_NAME = "storyline_ai"
        mock_settings.MEDIA_DIR = "/media/stories"

        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance

        is_valid, errors = ConfigValidator.validate_all()

        assert is_valid is False
        assert any("INSTAGRAM_ACCOUNT_ID" in error for error in errors)
        assert any("INSTAGRAM_ACCESS_TOKEN" in error for error in errors)
        assert any("Cloudinary" in error for error in errors)

    @patch("src.utils.validators.settings")
    @patch("src.utils.validators.Path")
    def test_validate_all_multiple_errors(self, mock_path, mock_settings):
        """Test validate_all collects multiple errors."""
        mock_settings.POSTS_PER_DAY = 0  # Invalid
        mock_settings.POSTING_HOURS_START = 25  # Invalid
        mock_settings.POSTING_HOURS_END = 2
        mock_settings.REPOST_TTL_DAYS = 30
        mock_settings.TELEGRAM_BOT_TOKEN = ""  # Missing
        mock_settings.TELEGRAM_CHANNEL_ID = -1001234567890
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = 123456789
        mock_settings.ENABLE_INSTAGRAM_API = False
        mock_settings.DB_NAME = "storyline_ai"
        mock_settings.MEDIA_DIR = "/media/stories"

        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance

        is_valid, errors = ConfigValidator.validate_all()

        assert is_valid is False
        assert len(errors) >= 3  # At least 3 errors
