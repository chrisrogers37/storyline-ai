"""Tests for authentication failure monitoring and alerting."""

import time
from unittest.mock import patch, MagicMock

import pytest

from src.utils import auth_monitor


@pytest.fixture(autouse=True)
def _clean_state():
    """Reset monitor state before each test."""
    auth_monitor.reset()
    yield
    auth_monitor.reset()


class TestRecordFailure:
    def test_single_failure_logs_warning(self):
        with patch.object(auth_monitor, "logger") as mock_logger:
            auth_monitor.record_failure("192.168.1.1", "Invalid signature")
            mock_logger.warning.assert_called_once()
            args = mock_logger.warning.call_args[0]
            assert "192.168.1.1" in args[2]
            assert "Invalid signature" in args[3]

    def test_failures_below_threshold_no_alert(self):
        with patch.object(auth_monitor, "_send_alert") as mock_alert:
            for _ in range(auth_monitor.FAILURE_THRESHOLD - 1):
                auth_monitor.record_failure("10.0.0.1", "bad token")
            mock_alert.assert_not_called()

    def test_threshold_reached_triggers_alert(self):
        with patch.object(auth_monitor, "_send_alert") as mock_alert:
            for _ in range(auth_monitor.FAILURE_THRESHOLD):
                auth_monitor.record_failure("10.0.0.1", "bad token")
            mock_alert.assert_called_once_with(
                "10.0.0.1", auth_monitor.FAILURE_THRESHOLD
            )

    def test_alert_fires_only_once_at_threshold(self):
        with patch.object(auth_monitor, "_send_alert") as mock_alert:
            for _ in range(auth_monitor.FAILURE_THRESHOLD + 3):
                auth_monitor.record_failure("10.0.0.1", "bad token")
            # Alert fires at exactly the threshold count, not on subsequent failures
            mock_alert.assert_called_once()

    def test_different_sources_tracked_independently(self):
        with patch.object(auth_monitor, "_send_alert") as mock_alert:
            for _ in range(auth_monitor.FAILURE_THRESHOLD - 1):
                auth_monitor.record_failure("10.0.0.1", "bad token")
            for _ in range(auth_monitor.FAILURE_THRESHOLD - 1):
                auth_monitor.record_failure("10.0.0.2", "bad token")
            mock_alert.assert_not_called()

    def test_expired_failures_pruned(self):
        with patch.object(auth_monitor, "_send_alert") as mock_alert:
            # Record old failures outside the window
            old_time = time.time() - auth_monitor.WINDOW_SECONDS - 1
            with patch("src.utils.auth_monitor.time") as mock_time:
                mock_time.time.return_value = old_time
                for _ in range(auth_monitor.FAILURE_THRESHOLD - 1):
                    auth_monitor.record_failure("10.0.0.1", "bad token")

            # Record one more at current time — should not trigger since old ones expired
            auth_monitor.record_failure("10.0.0.1", "bad token")
            mock_alert.assert_not_called()

    def test_reset_clears_all_state(self):
        with patch.object(auth_monitor, "_send_alert") as mock_alert:
            for _ in range(auth_monitor.FAILURE_THRESHOLD - 1):
                auth_monitor.record_failure("10.0.0.1", "bad token")
            auth_monitor.reset()
            # After reset, need full threshold again
            for _ in range(auth_monitor.FAILURE_THRESHOLD - 1):
                auth_monitor.record_failure("10.0.0.1", "bad token")
            mock_alert.assert_not_called()


class TestSendAlert:
    def test_sends_telegram_message(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        with (
            patch(
                "src.utils.auth_monitor.httpx.post", return_value=mock_resp
            ) as mock_post,
            patch("src.utils.auth_monitor.settings") as mock_settings,
        ):
            mock_settings.TELEGRAM_BOT_TOKEN = "test-token"
            mock_settings.ADMIN_TELEGRAM_CHAT_ID = 12345

            auth_monitor._send_alert("10.0.0.1", 5)

            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args
            assert "api.telegram.org" in call_kwargs[0][0]
            assert call_kwargs[1]["json"]["chat_id"] == 12345
            assert "10.0.0.1" in call_kwargs[1]["json"]["text"]
            assert "5 failures" in call_kwargs[1]["json"]["text"]

    def test_alert_failure_logs_error(self):
        import httpx

        with (
            patch(
                "src.utils.auth_monitor.httpx.post",
                side_effect=httpx.ConnectError("down"),
            ),
            patch("src.utils.auth_monitor.settings") as mock_settings,
            patch.object(auth_monitor, "logger") as mock_logger,
        ):
            mock_settings.TELEGRAM_BOT_TOKEN = "test-token"
            mock_settings.ADMIN_TELEGRAM_CHAT_ID = 12345

            auth_monitor._send_alert("10.0.0.1", 5)

            mock_logger.error.assert_called_once()
