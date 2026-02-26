"""Tests for onboarding API route helpers."""

import pytest
from fastapi import HTTPException

from src.api.routes.onboarding.helpers import service_error_handler


class TestServiceErrorHandler:
    """Tests for the service_error_handler context manager."""

    def test_passes_through_on_success(self):
        """Normal execution passes through unchanged."""
        with service_error_handler():
            result = "success"
        assert result == "success"

    def test_converts_value_error_to_http_400(self):
        """ValueError is converted to HTTPException 400."""
        with pytest.raises(HTTPException) as exc_info:
            with service_error_handler():
                raise ValueError("Invalid input")
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Invalid input"

    def test_propagates_non_value_errors(self):
        """Non-ValueError exceptions propagate unchanged."""
        with pytest.raises(RuntimeError):
            with service_error_handler():
                raise RuntimeError("Something else")
