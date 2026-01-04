"""Tests for validators utility."""
import pytest
from unittest.mock import Mock, patch

from src.utils.validators import ConfigValidator
from src.config.settings import Settings


@pytest.mark.unit
class TestConfigValidator:
    """Test suite for ConfigValidator."""

    @patch("src.utils.validators.settings")
    def test_validate_telegram_config_valid(self, mock_settings):
        """Test validating valid Telegram configuration."""
        mock_settings.TELEGRAM_BOT_TOKEN = "123456:ABC-DEF1234ghIkl"
        mock_settings.TELEGRAM_CHANNEL_ID = -1001234567890
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = 123456789

        is_valid, errors = ConfigValidator.validate_telegram_config()

        assert is_valid is True
        assert len(errors) == 0

    @patch("src.utils.validators.settings")
    def test_validate_telegram_config_missing_token(self, mock_settings):
        """Test validation fails with missing bot token."""
        mock_settings.TELEGRAM_BOT_TOKEN = ""
        mock_settings.TELEGRAM_CHANNEL_ID = -1001234567890
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = 123456789

        is_valid, errors = ConfigValidator.validate_telegram_config()

        assert is_valid is False
        assert any("TELEGRAM_BOT_TOKEN" in error for error in errors)

    @patch("src.utils.validators.settings")
    def test_validate_telegram_config_positive_channel_id(self, mock_settings):
        """Test validation fails with positive channel ID."""
        mock_settings.TELEGRAM_BOT_TOKEN = "123456:ABC-DEF1234ghIkl"
        mock_settings.TELEGRAM_CHANNEL_ID = 1001234567890  # Positive (invalid)
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = 123456789

        is_valid, errors = ConfigValidator.validate_telegram_config()

        assert is_valid is False
        assert any("TELEGRAM_CHANNEL_ID" in error and "negative" in error for error in errors)

    @patch("src.utils.validators.settings")
    def test_validate_database_config_valid(self, mock_settings):
        """Test validating valid database configuration."""
        mock_settings.DB_HOST = "localhost"
        mock_settings.DB_PORT = 5432
        mock_settings.DB_NAME = "storyline_ai"
        mock_settings.DB_USER = "postgres"
        mock_settings.DB_PASSWORD = "password123"

        is_valid, errors = ConfigValidator.validate_database_config()

        assert is_valid is True
        assert len(errors) == 0

    @patch("src.utils.validators.settings")
    def test_validate_database_config_missing_password(self, mock_settings):
        """Test validation fails with missing password."""
        mock_settings.DB_HOST = "localhost"
        mock_settings.DB_PORT = 5432
        mock_settings.DB_NAME = "storyline_ai"
        mock_settings.DB_USER = "postgres"
        mock_settings.DB_PASSWORD = ""

        is_valid, errors = ConfigValidator.validate_database_config()

        assert is_valid is False
        assert any("DB_PASSWORD" in error for error in errors)

    @patch("src.utils.validators.settings")
    def test_validate_schedule_config_valid(self, mock_settings):
        """Test validating valid schedule configuration."""
        mock_settings.POSTS_PER_DAY = 3
        mock_settings.POSTING_HOURS_START = 14
        mock_settings.POSTING_HOURS_END = 2

        is_valid, errors = ConfigValidator.validate_schedule_config()

        assert is_valid is True
        assert len(errors) == 0

    @patch("src.utils.validators.settings")
    def test_validate_schedule_config_invalid_posts_per_day(self, mock_settings):
        """Test validation fails with invalid posts per day."""
        mock_settings.POSTS_PER_DAY = 0  # Invalid
        mock_settings.POSTING_HOURS_START = 14
        mock_settings.POSTING_HOURS_END = 2

        is_valid, errors = ConfigValidator.validate_schedule_config()

        assert is_valid is False
        assert any("POSTS_PER_DAY" in error for error in errors)

    @patch("src.utils.validators.settings")
    def test_validate_schedule_config_invalid_hours(self, mock_settings):
        """Test validation fails with invalid hours."""
        mock_settings.POSTS_PER_DAY = 3
        mock_settings.POSTING_HOURS_START = 25  # Invalid (> 23)
        mock_settings.POSTING_HOURS_END = 2

        is_valid, errors = ConfigValidator.validate_schedule_config()

        assert is_valid is False
        assert any("POSTING_HOURS_START" in error for error in errors)

    @patch("src.utils.validators.ConfigValidator.validate_telegram_config")
    @patch("src.utils.validators.ConfigValidator.validate_database_config")
    @patch("src.utils.validators.ConfigValidator.validate_schedule_config")
    def test_validate_all_success(
        self, mock_schedule, mock_database, mock_telegram
    ):
        """Test validate_all when all configs are valid."""
        mock_telegram.return_value = (True, [])
        mock_database.return_value = (True, [])
        mock_schedule.return_value = (True, [])

        is_valid, errors = ConfigValidator.validate_all()

        assert is_valid is True
        assert len(errors) == 0

    @patch("src.utils.validators.ConfigValidator.validate_telegram_config")
    @patch("src.utils.validators.ConfigValidator.validate_database_config")
    @patch("src.utils.validators.ConfigValidator.validate_schedule_config")
    def test_validate_all_with_errors(
        self, mock_schedule, mock_database, mock_telegram
    ):
        """Test validate_all when some configs are invalid."""
        mock_telegram.return_value = (False, ["Telegram error"])
        mock_database.return_value = (True, [])
        mock_schedule.return_value = (False, ["Schedule error"])

        is_valid, errors = ConfigValidator.validate_all()

        assert is_valid is False
        assert len(errors) == 2
        assert "Telegram error" in errors
        assert "Schedule error" in errors
