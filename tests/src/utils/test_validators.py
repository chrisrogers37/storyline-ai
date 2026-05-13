"""Tests for validators utility."""

import pytest
from unittest.mock import patch, MagicMock

from src.utils.validators import ConfigValidator


@pytest.mark.unit
class TestConfigValidator:
    """Test suite for ConfigValidator."""

    @patch(
        "src.utils.validators.ConfigValidator._check_telegram_token", return_value=None
    )
    @patch("src.utils.validators.settings")
    @patch("src.utils.validators.Path")
    def test_validate_all_valid_config(self, mock_path, mock_settings, _mock_tg):
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
        mock_settings.DB_NAME = "storydump"
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
        mock_settings.DB_NAME = "storydump"
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
        mock_settings.DB_NAME = "storydump"
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
        mock_settings.DB_NAME = "storydump"
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
        mock_settings.DB_NAME = "storydump"
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
        mock_settings.DB_NAME = "storydump"
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
        mock_settings.DB_NAME = "storydump"
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
        mock_settings.DB_NAME = "storydump"
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
    def test_validate_all_media_dir_not_exists_and_cannot_create(
        self, mock_path, mock_settings
    ):
        """Test validation fails when media dir doesn't exist and can't be created."""
        mock_settings.POSTS_PER_DAY = 3
        mock_settings.POSTING_HOURS_START = 14
        mock_settings.POSTING_HOURS_END = 2
        mock_settings.REPOST_TTL_DAYS = 30
        mock_settings.TELEGRAM_BOT_TOKEN = "123456:ABC"
        mock_settings.TELEGRAM_CHANNEL_ID = -1001234567890
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = 123456789
        mock_settings.ENABLE_INSTAGRAM_API = False
        mock_settings.DB_NAME = "storydump"
        mock_settings.MEDIA_DIR = "/nonexistent/path"

        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = False
        mock_path_instance.mkdir.side_effect = OSError("Permission denied")
        mock_path.return_value = mock_path_instance

        is_valid, errors = ConfigValidator.validate_all()

        assert is_valid is False
        assert any("MEDIA_DIR" in error for error in errors)

    @patch(
        "src.utils.validators.ConfigValidator._check_telegram_token", return_value=None
    )
    @patch("src.utils.validators.settings")
    @patch("src.utils.validators.Path")
    def test_validate_all_media_dir_auto_created(
        self, mock_path, mock_settings, _mock_tg
    ):
        """Test validation passes when media dir can be auto-created."""
        mock_settings.POSTS_PER_DAY = 3
        mock_settings.POSTING_HOURS_START = 14
        mock_settings.POSTING_HOURS_END = 2
        mock_settings.REPOST_TTL_DAYS = 30
        mock_settings.TELEGRAM_BOT_TOKEN = "123456:ABC"
        mock_settings.TELEGRAM_CHANNEL_ID = -1001234567890
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = 123456789
        mock_settings.ENABLE_INSTAGRAM_API = False
        mock_settings.DB_NAME = "storydump"
        mock_settings.MEDIA_DIR = "/tmp/media"

        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = False
        mock_path_instance.mkdir.return_value = None  # mkdir succeeds
        mock_path.return_value = mock_path_instance

        is_valid, errors = ConfigValidator.validate_all()

        assert is_valid is True
        assert len(errors) == 0
        mock_path_instance.mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch("src.utils.validators.settings")
    @patch("src.utils.validators.Path")
    def test_validate_all_instagram_api_missing_cloudinary(
        self, mock_path, mock_settings
    ):
        """Test validation fails when Instagram API enabled but Cloudinary missing."""
        mock_settings.POSTS_PER_DAY = 3
        mock_settings.POSTING_HOURS_START = 14
        mock_settings.POSTING_HOURS_END = 2
        mock_settings.REPOST_TTL_DAYS = 30
        mock_settings.TELEGRAM_BOT_TOKEN = "123456:ABC"
        mock_settings.TELEGRAM_CHANNEL_ID = -1001234567890
        mock_settings.ADMIN_TELEGRAM_CHAT_ID = 123456789
        mock_settings.ENABLE_INSTAGRAM_API = True  # Enabled
        mock_settings.CLOUDINARY_CLOUD_NAME = ""  # Missing
        mock_settings.DB_NAME = "storydump"
        mock_settings.MEDIA_DIR = "/media/stories"

        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance

        is_valid, errors = ConfigValidator.validate_all()

        assert is_valid is False
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
        mock_settings.DB_NAME = "storydump"
        mock_settings.MEDIA_DIR = "/media/stories"

        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance

        is_valid, errors = ConfigValidator.validate_all()

        assert is_valid is False
        assert len(errors) >= 3  # At least 3 errors


@pytest.mark.unit
class TestLatestMigrationVersion:
    """Tests for _latest_migration_version helper."""

    def test_reads_real_migrations_dir(self):
        """Sanity check: finds migrations from the actual scripts/ directory."""
        from src.utils.validators import _latest_migration_version

        version = _latest_migration_version()
        assert version is not None
        assert version >= 22  # current count at time of writing

    @patch("src.utils.validators.MIGRATIONS_DIR")
    def test_returns_none_when_dir_missing(self, mock_dir):
        """Returns None when migrations directory doesn't exist."""
        from src.utils.validators import _latest_migration_version

        mock_dir.is_dir.return_value = False
        assert _latest_migration_version() is None

    @patch("src.utils.validators.MIGRATIONS_DIR")
    def test_returns_none_when_no_sql_files(self, mock_dir):
        """Returns None when directory has no migration files."""
        from src.utils.validators import _latest_migration_version

        mock_dir.is_dir.return_value = True
        mock_dir.iterdir.return_value = []
        assert _latest_migration_version() is None


@pytest.mark.unit
class TestCheckSchemaVersion:
    """Tests for ConfigValidator.check_schema_version."""

    @patch("src.utils.validators.logger")
    @patch("src.utils.validators._latest_migration_version", return_value=22)
    @patch("src.config.database.engine")
    def test_logs_success_when_versions_match(
        self, mock_engine, mock_latest, mock_logger
    ):
        """Logs success when DB version matches migration files."""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.scalar.return_value = 22
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        ConfigValidator.check_schema_version()

        mock_logger.info.assert_called_once()
        assert "up to date (version 22)" in mock_logger.info.call_args[0][0]

    @patch("src.utils.validators.logger")
    @patch("src.utils.validators._latest_migration_version", return_value=22)
    @patch("src.config.database.engine")
    def test_warns_when_db_behind(self, mock_engine, mock_latest, mock_logger):
        """Warns when DB version is behind migration files."""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.scalar.return_value = 18
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        ConfigValidator.check_schema_version()

        mock_logger.warning.assert_called_once()
        msg = mock_logger.warning.call_args[0][0]
        assert "DB at version 18" in msg
        assert "latest migration is 22" in msg

    @patch("src.utils.validators.logger")
    @patch("src.utils.validators._latest_migration_version", return_value=20)
    @patch("src.config.database.engine")
    def test_warns_when_db_ahead(self, mock_engine, mock_latest, mock_logger):
        """Warns when DB version is ahead of migration files."""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.scalar.return_value = 25
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        ConfigValidator.check_schema_version()

        mock_logger.warning.assert_called_once()
        assert "ahead of migration files" in mock_logger.warning.call_args[0][0]

    @patch("src.utils.validators.logger")
    @patch("src.utils.validators._latest_migration_version", return_value=None)
    def test_skips_when_no_migrations(self, mock_latest, mock_logger):
        """Skips check when no migration files found."""
        ConfigValidator.check_schema_version()

        mock_logger.warning.assert_called_once()
        assert "no migration files found" in mock_logger.warning.call_args[0][0]

    @patch("src.utils.validators.logger")
    @patch("src.utils.validators._latest_migration_version", return_value=22)
    @patch("src.config.database.engine")
    def test_handles_db_error_gracefully(self, mock_engine, mock_latest, mock_logger):
        """Handles database connection errors without crashing."""
        mock_engine.connect.side_effect = Exception("Connection refused")

        ConfigValidator.check_schema_version()

        mock_logger.warning.assert_called_once()
        assert "Schema version check failed" in mock_logger.warning.call_args[0][0]


@pytest.mark.unit
class TestCheckTelegramToken:
    """Test ConfigValidator._check_telegram_token (boot-time getMe probe)."""

    @patch("requests.get")
    def test_returns_none_when_token_accepted(self, mock_get):
        """HTTP 200 from Telegram means the token is good."""
        mock_get.return_value = MagicMock(status_code=200)

        assert ConfigValidator._check_telegram_token("anything") is None

    @patch("requests.get")
    def test_returns_error_on_401(self, mock_get):
        """HTTP 401 means the token is revoked/invalid — flag it loudly."""
        mock_get.return_value = MagicMock(status_code=401)

        error = ConfigValidator._check_telegram_token("anything")
        assert error is not None
        assert "401" in error
        assert "rotate" in error.lower() or "revoked" in error.lower()

    @patch("requests.get")
    def test_returns_error_on_other_4xx_5xx(self, mock_get):
        """Other non-200 statuses also fail validation."""
        mock_get.return_value = MagicMock(status_code=500)

        error = ConfigValidator._check_telegram_token("anything")
        assert error is not None
        assert "500" in error

    @patch("requests.get")
    def test_returns_none_on_network_error(self, mock_get):
        """Network errors are inconclusive — don't block startup on a blip."""
        import requests as requests_lib

        mock_get.side_effect = requests_lib.ConnectTimeout("timeout")

        assert ConfigValidator._check_telegram_token("anything") is None
