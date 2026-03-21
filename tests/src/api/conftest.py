"""Shared fixtures for API-layer tests."""

import pytest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from src.api.app import app

VALID_USER = {"user_id": 12345, "first_name": "Chris"}
CHAT_ID = -1001234567890


@pytest.fixture
def client():
    return TestClient(app)


def mock_validate(return_value=None):
    """Patch validate_init_data to skip HMAC validation in tests.

    The default return has no chat_id, simulating DM-opened Mini Apps.
    Pass chat_id in return_value to test group-chat initData.
    """
    return patch(
        "src.api.routes.onboarding.helpers.validate_init_data",
        return_value=return_value or VALID_USER,
    )


def service_ctx(mock_cls):
    """Set up __enter__/__exit__ on mock_cls.return_value for context manager use.

    Returns the mock service instance (mock_cls.return_value) configured
    so that ``with ServiceClass() as svc:`` works in the code under test.
    """
    mock_svc = mock_cls.return_value
    mock_svc.__enter__ = Mock(return_value=mock_svc)
    mock_svc.__exit__ = Mock(return_value=False)
    return mock_svc
