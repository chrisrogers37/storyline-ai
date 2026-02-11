"""Tests for BaseService."""

import pytest
from unittest.mock import patch
from uuid import uuid4

from src.services.base_service import BaseService


class MockServiceForTesting(BaseService):
    """Mock service implementation for testing BaseService."""

    def __init__(self):
        super().__init__()
        self.service_name = "TestService"

    def test_method(self):
        """Test method that uses execution tracking."""
        with self.track_execution("test_method"):
            return {"result": "success"}

    def test_method_with_error(self):
        """Test method that raises an error."""
        with self.track_execution("test_method_with_error"):
            raise ValueError("Test error")


@pytest.fixture
def mock_service():
    """Create MockServiceForTesting with mocked ServiceRunRepository."""
    with patch("src.services.base_service.ServiceRunRepository") as mock_run_repo_class:
        mock_run_repo = mock_run_repo_class.return_value
        mock_run_repo.create_run.return_value = "run-123"

        service = MockServiceForTesting()
        service._mock_run_repo = mock_run_repo
        yield service


@pytest.mark.unit
class TestBaseService:
    """Test suite for BaseService."""

    def test_service_initialization(self, mock_service):
        """Test service initialization."""
        assert mock_service.service_run_repo is not None
        assert mock_service.service_name == "TestService"

    def test_track_execution_creates_run(self, mock_service):
        """Test that track_execution creates a service run record."""
        mock_service.test_method()

        mock_service._mock_run_repo.create_run.assert_called_once()
        call_kwargs = mock_service._mock_run_repo.create_run.call_args
        assert call_kwargs.kwargs["service_name"] == "TestService"
        assert call_kwargs.kwargs["method_name"] == "test_method"

    def test_track_execution_records_success(self, mock_service):
        """Test that successful execution is recorded correctly."""
        result = mock_service.test_method()

        assert result["result"] == "success"

        mock_service._mock_run_repo.complete_run.assert_called_once()
        call_kwargs = mock_service._mock_run_repo.complete_run.call_args
        assert call_kwargs.kwargs["run_id"] == "run-123"
        assert call_kwargs.kwargs["success"] is True
        assert "duration_ms" in call_kwargs.kwargs

    def test_track_execution_records_failure(self, mock_service):
        """Test that failed execution is recorded correctly."""
        with pytest.raises(ValueError, match="Test error"):
            mock_service.test_method_with_error()

        mock_service._mock_run_repo.fail_run.assert_called_once()
        call_kwargs = mock_service._mock_run_repo.fail_run.call_args
        assert call_kwargs.kwargs["run_id"] == "run-123"
        assert call_kwargs.kwargs["error_type"] == "ValueError"
        assert call_kwargs.kwargs["error_message"] == "Test error"
        assert "stack_trace" in call_kwargs.kwargs
        assert "duration_ms" in call_kwargs.kwargs

    def test_track_execution_with_parameters(self, mock_service):
        """Test tracking execution with parameters."""
        params = {"param1": "value1", "param2": 42}

        with mock_service.track_execution("test_with_params", input_params=params):
            pass

        call_kwargs = mock_service._mock_run_repo.create_run.call_args
        assert call_kwargs.kwargs["input_params"] == params

    def test_track_execution_with_user_id(self, mock_service):
        """Test tracking execution with user attribution."""
        user_id = uuid4()

        with mock_service.track_execution("test_with_user", user_id=user_id):
            pass

        call_kwargs = mock_service._mock_run_repo.create_run.call_args
        assert call_kwargs.kwargs["user_id"] == str(user_id)

    def test_track_execution_with_result_summary(self, mock_service):
        """Test tracking execution with result summary."""
        result_summary = {"items_processed": 10, "items_skipped": 2}

        with mock_service.track_execution("test_with_summary") as run_id:
            mock_service.set_result_summary(run_id, result_summary)

        mock_service._mock_run_repo.set_result_summary.assert_called_once_with(
            "run-123", result_summary
        )

    def test_track_execution_calculates_timing(self, mock_service):
        """Test that execution time is calculated."""
        mock_service.test_method()

        call_kwargs = mock_service._mock_run_repo.complete_run.call_args
        duration_ms = call_kwargs.kwargs["duration_ms"]
        assert isinstance(duration_ms, int)
        assert duration_ms >= 0

    def test_get_logger(self, mock_service):
        """Test that service has logger."""
        # BaseService uses module-level logger from src.utils.logger
        # Service is identified by service_name attribute
        assert mock_service.service_name == "TestService"
