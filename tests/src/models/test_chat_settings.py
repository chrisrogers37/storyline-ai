"""Tests for ChatSettings model definition."""

import pytest

from src.models.chat_settings import ChatSettings


@pytest.mark.unit
class TestChatSettingsModel:
    """Tests for ChatSettings model column definitions and defaults."""

    def test_tablename(self):
        assert ChatSettings.__tablename__ == "chat_settings"

    def test_id_default_generates_uuids(self):
        default_fn = ChatSettings.id.default.arg
        assert callable(default_fn)
        assert default_fn.__name__ == "uuid4"

    def test_telegram_chat_id_not_nullable(self):
        assert ChatSettings.telegram_chat_id.nullable is False

    def test_telegram_chat_id_is_unique(self):
        assert ChatSettings.telegram_chat_id.unique is True

    def test_dry_run_mode_defaults_to_true(self):
        assert ChatSettings.dry_run_mode.default.arg is True

    def test_enable_instagram_api_defaults_to_false(self):
        assert ChatSettings.enable_instagram_api.default.arg is False

    def test_is_paused_defaults_to_false(self):
        assert ChatSettings.is_paused.default.arg is False

    def test_posts_per_day_defaults_to_three(self):
        assert ChatSettings.posts_per_day.default.arg == 3

    def test_posting_hours_start_defaults_to_14(self):
        assert ChatSettings.posting_hours_start.default.arg == 14

    def test_posting_hours_end_defaults_to_2(self):
        assert ChatSettings.posting_hours_end.default.arg == 2

    def test_show_verbose_notifications_defaults_to_true(self):
        assert ChatSettings.show_verbose_notifications.default.arg is True

    def test_media_sync_enabled_defaults_to_false(self):
        assert ChatSettings.media_sync_enabled.default.arg is False

    def test_active_instagram_account_id_nullable(self):
        assert ChatSettings.active_instagram_account_id.nullable is True

    def test_repr_format(self):
        item = ChatSettings(telegram_chat_id=-1001234567, is_paused=False)
        result = repr(item)
        assert "-1001234567" in result
        assert "False" in result
