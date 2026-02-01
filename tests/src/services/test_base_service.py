"""Tests for BaseService."""

import pytest

from src.services.base_service import BaseService
from src.repositories.service_run_repository import ServiceRunRepository


class MockServiceForTesting(BaseService):
    """Mock service implementation for testing BaseService."""

    def __init__(self, db=None):
        super().__init__(db)
        self.service_name = "TestService"

    def test_method(self):
        """Test method that uses execution tracking."""
        with self.track_execution("test_method"):
            return {"result": "success"}

    def test_method_with_error(self):
        """Test method that raises an error."""
        with self.track_execution("test_method_with_error"):
            raise ValueError("Test error")


@pytest.mark.unit
class TestBaseService:
    """Test suite for BaseService."""

    @pytest.mark.skip(
        reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/"
    )
    def test_service_initialization(self, test_db):
        """Test service initialization."""
        service = MockServiceForTesting(db=test_db)

        assert service.db is not None
        assert service.service_run_repo is not None

    @pytest.mark.skip(
        reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/"
    )
    def test_track_execution_creates_run(self, test_db):
        """Test that track_execution creates a service run record."""
        service = MockServiceForTesting(db=test_db)
        run_repo = ServiceRunRepository(test_db)

        # Execute method
        service.test_method()

        # Verify run was created
        recent_runs = run_repo.get_recent_runs(limit=1)
        assert len(recent_runs) >= 1

        latest_run = recent_runs[0]
        assert latest_run.service_name == "TestService"
        assert latest_run.method_name == "test_method"
        assert latest_run.status == "success"

    @pytest.mark.skip(
        reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/"
    )
    def test_track_execution_records_success(self, test_db):
        """Test that successful execution is recorded correctly."""
        service = MockServiceForTesting(db=test_db)
        run_repo = ServiceRunRepository(test_db)

        result = service.test_method()

        # Verify result
        assert result["result"] == "success"

        # Verify run status
        recent_runs = run_repo.get_recent_runs(limit=1)
        latest_run = recent_runs[0]

        assert latest_run.status == "success"
        assert latest_run.completed_at is not None
        assert latest_run.execution_time_seconds is not None
        assert latest_run.error_message is None

    @pytest.mark.skip(
        reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/"
    )
    def test_track_execution_records_failure(self, test_db):
        """Test that failed execution is recorded correctly."""
        service = MockServiceForTesting(db=test_db)
        run_repo = ServiceRunRepository(test_db)

        # Execute method that raises error
        with pytest.raises(ValueError, match="Test error"):
            service.test_method_with_error()

        # Verify run status
        recent_runs = run_repo.get_recent_runs(limit=1)
        latest_run = recent_runs[0]

        assert latest_run.status == "failed"
        assert latest_run.error_message == "Test error"
        assert latest_run.error_traceback is not None
        assert "ValueError" in latest_run.error_traceback

    @pytest.mark.skip(
        reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/"
    )
    def test_track_execution_with_parameters(self, test_db):
        """Test tracking execution with parameters."""
        service = MockServiceForTesting(db=test_db)
        run_repo = ServiceRunRepository(test_db)

        params = {"param1": "value1", "param2": 42}

        with service.track_execution("test_with_params", parameters=params):
            pass

        # Verify parameters were recorded
        recent_runs = run_repo.get_recent_runs(limit=1)
        latest_run = recent_runs[0]

        assert latest_run.parameters == params

    @pytest.mark.skip(
        reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/"
    )
    def test_track_execution_with_user_id(self, test_db):
        """Test tracking execution with user attribution."""
        from src.repositories.user_repository import UserRepository

        service = MockServiceForTesting(db=test_db)
        run_repo = ServiceRunRepository(test_db)
        user_repo = UserRepository(test_db)

        # Create test user
        user = user_repo.create(telegram_user_id=900001)

        with service.track_execution("test_with_user", user_id=user.id):
            pass

        # Verify user attribution
        recent_runs = run_repo.get_recent_runs(limit=1)
        latest_run = recent_runs[0]

        assert latest_run.triggered_by_user_id == user.id

    @pytest.mark.skip(
        reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/"
    )
    def test_track_execution_with_result_summary(self, test_db):
        """Test tracking execution with result summary."""
        service = MockServiceForTesting(db=test_db)
        run_repo = ServiceRunRepository(test_db)

        result_summary = {"items_processed": 10, "items_skipped": 2}

        with service.track_execution(
            "test_with_summary", result_summary=result_summary
        ):
            pass

        # Verify result summary was recorded
        recent_runs = run_repo.get_recent_runs(limit=1)
        latest_run = recent_runs[0]

        assert latest_run.result_summary == result_summary

    @pytest.mark.skip(
        reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/"
    )
    def test_track_execution_calculates_timing(self, test_db):
        """Test that execution time is calculated."""
        import time

        service = MockServiceForTesting(db=test_db)
        run_repo = ServiceRunRepository(test_db)

        with service.track_execution("test_timing"):
            time.sleep(0.1)

        # Verify timing
        recent_runs = run_repo.get_recent_runs(limit=1)
        latest_run = recent_runs[0]

        assert latest_run.execution_time_seconds is not None
        assert latest_run.execution_time_seconds >= 0.1

    @pytest.mark.skip(
        reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/"
    )
    def test_get_logger(self, test_db):
        """Test that service has logger."""
        service = MockServiceForTesting(db=test_db)

        logger = service.logger

        assert logger is not None
        assert logger.name == "TestService"
