"""Tests for the worker health check endpoint in src/main.py."""

import json

import pytest
from unittest.mock import patch
from time import time

from src.main import _build_health_response


@pytest.mark.unit
class TestBuildHealthResponse:
    """Test _build_health_response against loop liveness states."""

    def test_all_loops_alive_returns_200(self):
        """When every loop has a recent heartbeat, return 200."""
        liveness = {
            "scheduler": {
                "alive": True,
                "last_heartbeat_s_ago": 10,
                "expected_interval_s": 60,
                "message": "OK",
            },
            "media_sync": {
                "alive": True,
                "last_heartbeat_s_ago": 50,
                "expected_interval_s": 300,
                "message": "OK",
            },
        }
        with patch("src.main.get_loop_liveness", return_value=liveness):
            response = _build_health_response()

        assert b"200 OK" in response
        body = json.loads(response.split(b"\r\n\r\n", 1)[1])
        assert body["status"] == "healthy"
        assert "stale_loops" not in body

    def test_stale_loop_returns_503(self):
        """When a loop is stale, return 503 with stale loop details."""
        liveness = {
            "scheduler": {
                "alive": False,
                "last_heartbeat_s_ago": 300,
                "expected_interval_s": 60,
                "message": "Stale (300s since last tick)",
            },
            "media_sync": {
                "alive": True,
                "last_heartbeat_s_ago": 50,
                "expected_interval_s": 300,
                "message": "OK",
            },
        }
        with patch("src.main.get_loop_liveness", return_value=liveness):
            response = _build_health_response()

        assert b"503 Service Unavailable" in response
        body = json.loads(response.split(b"\r\n\r\n", 1)[1])
        assert body["status"] == "unhealthy"
        assert "scheduler" in body["stale_loops"]
        assert body["stale_loops"]["scheduler"]["alive"] is False

    def test_multiple_stale_loops(self):
        """All stale loops appear in the response."""
        liveness = {
            "scheduler": {
                "alive": False,
                "last_heartbeat_s_ago": 200,
                "expected_interval_s": 60,
                "message": "Stale (200s since last tick)",
            },
            "media_sync": {
                "alive": False,
                "last_heartbeat_s_ago": 900,
                "expected_interval_s": 300,
                "message": "Stale (900s since last tick)",
            },
            "transaction_cleanup": {
                "alive": True,
                "last_heartbeat_s_ago": 5,
                "expected_interval_s": 30,
                "message": "OK",
            },
        }
        with patch("src.main.get_loop_liveness", return_value=liveness):
            response = _build_health_response()

        assert b"503" in response
        body = json.loads(response.split(b"\r\n\r\n", 1)[1])
        assert len(body["stale_loops"]) == 2
        assert "scheduler" in body["stale_loops"]
        assert "media_sync" in body["stale_loops"]

    def test_not_started_loop_returns_503(self):
        """A loop that never sent a heartbeat is treated as stale."""
        liveness = {
            "scheduler": {
                "alive": False,
                "message": "Not started",
                "expected_interval_s": 60,
            },
        }
        with patch("src.main.get_loop_liveness", return_value=liveness):
            response = _build_health_response()

        assert b"503" in response
        body = json.loads(response.split(b"\r\n\r\n", 1)[1])
        assert body["stale_loops"]["scheduler"]["message"] == "Not started"

    def test_response_has_valid_content_length(self):
        """Content-Length header matches actual body size."""
        liveness = {
            "scheduler": {
                "alive": True,
                "last_heartbeat_s_ago": 10,
                "expected_interval_s": 60,
                "message": "OK",
            },
        }
        with patch("src.main.get_loop_liveness", return_value=liveness):
            response = _build_health_response()

        header_section, body = response.split(b"\r\n\r\n", 1)
        for line in header_section.split(b"\r\n"):
            if line.startswith(b"Content-Length:"):
                declared = int(line.split(b":")[1].strip())
                assert declared == len(body)
                break
        else:
            pytest.fail("No Content-Length header found")

    def test_response_content_type_is_json(self):
        """Response Content-Type is application/json."""
        with patch("src.main.get_loop_liveness", return_value={}):
            response = _build_health_response()

        assert b"Content-Type: application/json" in response


@pytest.mark.unit
class TestHeartbeatIntegration:
    """Test that record_heartbeat + get_loop_liveness round-trips correctly."""

    def test_fresh_heartbeat_is_alive(self):
        """A loop that just recorded a heartbeat is alive."""
        from src.services.core.loops.heartbeat import (
            record_heartbeat,
            get_loop_liveness,
            loop_heartbeats,
        )

        # Clear state
        loop_heartbeats.clear()
        record_heartbeat("scheduler")

        liveness = get_loop_liveness()
        assert liveness["scheduler"]["alive"] is True

    def test_expired_heartbeat_is_stale(self):
        """A loop whose heartbeat is older than 2x interval is stale."""
        from src.services.core.loops.heartbeat import (
            get_loop_liveness,
            loop_heartbeats,
            LOOP_EXPECTED_INTERVALS,
        )

        # Set heartbeat to well past the threshold
        loop_heartbeats["scheduler"] = time() - (
            LOOP_EXPECTED_INTERVALS["scheduler"] * 3
        )

        liveness = get_loop_liveness()
        assert liveness["scheduler"]["alive"] is False
        assert "Stale" in liveness["scheduler"]["message"]

    def test_no_heartbeat_is_not_started(self):
        """A loop that never recorded a heartbeat reports as not started."""
        from src.services.core.loops.heartbeat import (
            get_loop_liveness,
            loop_heartbeats,
        )

        loop_heartbeats.clear()

        liveness = get_loop_liveness()
        assert liveness["scheduler"]["alive"] is False
        assert liveness["scheduler"]["message"] == "Not started"
