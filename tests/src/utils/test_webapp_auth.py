"""Tests for Telegram WebApp initData HMAC-SHA256 validation."""

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from unittest.mock import patch

from src.utils.webapp_auth import validate_init_data, INIT_DATA_TTL


def _build_init_data(
    bot_token="test-bot-token",
    user_id=12345,
    first_name="Chris",
    auth_date=None,
    extra_params=None,
    tamper_hash=False,
    omit_hash=False,
):
    """Helper to build a valid initData string with correct HMAC."""
    if auth_date is None:
        auth_date = int(time.time())

    user_data = json.dumps({"id": user_id, "first_name": first_name})

    params = {"auth_date": str(auth_date), "user": user_data}
    if extra_params:
        params.update(extra_params)

    # Build data_check_string (sorted alphabetically, newline-joined)
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))

    # Compute HMAC-SHA256
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if tamper_hash:
        computed_hash = "a" * 64  # Invalid hash

    if omit_hash:
        return urlencode(params)

    params["hash"] = computed_hash
    return urlencode(params)


@pytest.mark.unit
class TestValidateInitData:
    """Test initData HMAC-SHA256 validation."""

    @patch("src.utils.webapp_auth.settings")
    def test_valid_init_data_returns_user_info(self, mock_settings):
        """Happy path: valid initData returns user_id and first_name."""
        mock_settings.TELEGRAM_BOT_TOKEN = "test-bot-token"

        init_data = _build_init_data(bot_token="test-bot-token")
        result = validate_init_data(init_data)

        assert result["user_id"] == 12345
        assert result["first_name"] == "Chris"

    def test_empty_init_data_raises(self):
        """Empty string raises ValueError."""
        with pytest.raises(ValueError, match="Empty initData"):
            validate_init_data("")

    @patch("src.utils.webapp_auth.settings")
    def test_missing_hash_raises(self, mock_settings):
        """initData without hash field raises ValueError."""
        mock_settings.TELEGRAM_BOT_TOKEN = "test-bot-token"

        init_data = _build_init_data(omit_hash=True)

        with pytest.raises(ValueError, match="Missing hash"):
            validate_init_data(init_data)

    @patch("src.utils.webapp_auth.settings")
    def test_invalid_signature_raises(self, mock_settings):
        """Tampered initData raises ValueError."""
        mock_settings.TELEGRAM_BOT_TOKEN = "test-bot-token"

        init_data = _build_init_data(tamper_hash=True)

        with pytest.raises(ValueError, match="Invalid initData signature"):
            validate_init_data(init_data)

    @patch("src.utils.webapp_auth.settings")
    def test_wrong_bot_token_raises(self, mock_settings):
        """initData signed with different token is rejected."""
        mock_settings.TELEGRAM_BOT_TOKEN = "wrong-token"

        init_data = _build_init_data(bot_token="correct-token")

        with pytest.raises(ValueError, match="Invalid initData signature"):
            validate_init_data(init_data)

    @patch("src.utils.webapp_auth.settings")
    def test_expired_init_data_raises(self, mock_settings):
        """initData older than TTL raises ValueError."""
        mock_settings.TELEGRAM_BOT_TOKEN = "test-bot-token"

        old_time = int(time.time()) - INIT_DATA_TTL - 60  # 1 minute past TTL
        init_data = _build_init_data(auth_date=old_time)

        with pytest.raises(ValueError, match="initData expired"):
            validate_init_data(init_data)

    @patch("src.utils.webapp_auth.settings")
    def test_missing_user_data_returns_none_fields(self, mock_settings):
        """initData without user JSON returns None for user fields."""
        mock_settings.TELEGRAM_BOT_TOKEN = "test-bot-token"

        auth_date = str(int(time.time()))
        params = {"auth_date": auth_date}
        data_check_string = f"auth_date={auth_date}"

        secret_key = hmac.new(b"WebAppData", b"test-bot-token", hashlib.sha256).digest()
        computed_hash = hmac.new(
            secret_key, data_check_string.encode(), hashlib.sha256
        ).hexdigest()

        params["hash"] = computed_hash
        init_data = urlencode(params)

        result = validate_init_data(init_data)
        assert result["user_id"] is None
        assert result["first_name"] is None

    @patch("src.utils.webapp_auth.settings")
    def test_extra_params_included_in_check_string(self, mock_settings):
        """Extra params are part of the signed data and validated."""
        mock_settings.TELEGRAM_BOT_TOKEN = "test-bot-token"

        init_data = _build_init_data(extra_params={"query_id": "test-query-123"})
        result = validate_init_data(init_data)

        assert result["user_id"] == 12345

    @patch("src.utils.webapp_auth.settings")
    def test_chat_id_extracted_when_present(self, mock_settings):
        """When initData contains a chat object, chat_id is extracted."""
        mock_settings.TELEGRAM_BOT_TOKEN = "test-bot-token"

        chat_data = json.dumps({"id": -1001234567890, "type": "supergroup"})
        init_data = _build_init_data(extra_params={"chat": chat_data})
        result = validate_init_data(init_data)

        assert result["chat_id"] == -1001234567890

    @patch("src.utils.webapp_auth.settings")
    def test_no_chat_id_when_absent(self, mock_settings):
        """When initData has no chat object, chat_id is not in result."""
        mock_settings.TELEGRAM_BOT_TOKEN = "test-bot-token"

        init_data = _build_init_data()
        result = validate_init_data(init_data)

        assert "chat_id" not in result
