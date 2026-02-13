"""Tests for Settings configuration model."""

import pytest

from src.config.settings import Settings


@pytest.mark.unit
class TestSettingsDefaults:
    """Tests for Settings default values via model field definitions."""

    def test_enable_instagram_api_defaults_false(self):
        assert Settings.model_fields["ENABLE_INSTAGRAM_API"].default is False

    def test_db_host_defaults_to_localhost(self):
        assert Settings.model_fields["DB_HOST"].default == "localhost"

    def test_db_port_defaults_to_5432(self):
        assert Settings.model_fields["DB_PORT"].default == 5432

    def test_db_name_defaults(self):
        assert Settings.model_fields["DB_NAME"].default == "storyline_ai"

    def test_posts_per_day_defaults_to_3(self):
        assert Settings.model_fields["POSTS_PER_DAY"].default == 3

    def test_posting_hours_start_defaults_to_14(self):
        assert Settings.model_fields["POSTING_HOURS_START"].default == 14

    def test_posting_hours_end_defaults_to_2(self):
        assert Settings.model_fields["POSTING_HOURS_END"].default == 2

    def test_repost_ttl_days_defaults_to_30(self):
        assert Settings.model_fields["REPOST_TTL_DAYS"].default == 30

    def test_dry_run_mode_defaults_to_false(self):
        assert Settings.model_fields["DRY_RUN_MODE"].default is False

    def test_log_level_defaults_to_info(self):
        assert Settings.model_fields["LOG_LEVEL"].default == "INFO"

    def test_instagram_posts_per_hour_defaults_to_25(self):
        assert Settings.model_fields["INSTAGRAM_POSTS_PER_HOUR"].default == 25

    def test_cloud_upload_retention_hours_defaults_to_24(self):
        assert Settings.model_fields["CLOUD_UPLOAD_RETENTION_HOURS"].default == 24

    def test_media_sync_enabled_defaults_to_false(self):
        assert Settings.model_fields["MEDIA_SYNC_ENABLED"].default is False

    def test_media_sync_interval_defaults_to_300(self):
        assert Settings.model_fields["MEDIA_SYNC_INTERVAL_SECONDS"].default == 300

    def test_media_source_type_defaults_to_local(self):
        assert Settings.model_fields["MEDIA_SOURCE_TYPE"].default == "local"

    def test_caption_style_defaults_to_enhanced(self):
        assert Settings.model_fields["CAPTION_STYLE"].default == "enhanced"

    def test_cloud_storage_provider_defaults_to_cloudinary(self):
        assert Settings.model_fields["CLOUD_STORAGE_PROVIDER"].default == "cloudinary"

    def test_optional_fields_default_to_none(self):
        assert Settings.model_fields["INSTAGRAM_ACCOUNT_ID"].default is None
        assert Settings.model_fields["INSTAGRAM_ACCESS_TOKEN"].default is None
        assert Settings.model_fields["FACEBOOK_APP_ID"].default is None
        assert Settings.model_fields["FACEBOOK_APP_SECRET"].default is None
        assert Settings.model_fields["CLOUDINARY_CLOUD_NAME"].default is None
        assert Settings.model_fields["CLOUDINARY_API_KEY"].default is None
        assert Settings.model_fields["CLOUDINARY_API_SECRET"].default is None
        assert Settings.model_fields["ENCRYPTION_KEY"].default is None


@pytest.mark.unit
class TestSettingsDatabaseUrl:
    """Tests for the database_url computed property."""

    def _make_settings(self, **overrides):
        defaults = {
            "TELEGRAM_BOT_TOKEN": "test-token-123",
            "TELEGRAM_CHANNEL_ID": -1001234567,
            "ADMIN_TELEGRAM_CHAT_ID": 12345,
            "DB_USER": "storyline_user",
            "DB_NAME": "storyline_ai",
            "TEST_DB_NAME": "storyline_ai_test",
        }
        defaults.update(overrides)
        return Settings(_env_file=None, **defaults)

    def test_database_url_with_password(self):
        s = self._make_settings(DB_PASSWORD="secret123")
        url = s.database_url
        assert "secret123" in url
        assert url.startswith("postgresql://")
        assert "storyline_user" in url
        assert "storyline_ai" in url

    def test_database_url_without_password(self):
        s = self._make_settings(DB_PASSWORD="")
        url = s.database_url
        assert ":@" not in url
        assert "storyline_user@" in url

    def test_test_database_url_uses_test_db_name(self):
        s = self._make_settings(DB_PASSWORD="secret")
        url = s.test_database_url
        assert "storyline_ai_test" in url
        assert url != s.database_url

    def test_database_url_includes_host_and_port(self):
        s = self._make_settings(DB_HOST="myhost", DB_PORT=5433, DB_PASSWORD="pw")
        url = s.database_url
        assert "myhost" in url
        assert "5433" in url
