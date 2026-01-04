"""Tests for ServiceRunRepository."""
import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from src.repositories.service_run_repository import ServiceRunRepository
from src.repositories.user_repository import UserRepository


@pytest.mark.unit
class TestServiceRunRepository:
    """Test suite for ServiceRunRepository."""

    def test_create_run(self, test_db):
        """Test creating a service run record."""
        run_repo = ServiceRunRepository(test_db)

        run = run_repo.create_run(
            service_name="TestService",
            method_name="test_method",
            parameters={"param1": "value1"}
        )

        assert run.id is not None
        assert run.service_name == "TestService"
        assert run.method_name == "test_method"
        assert run.status == "running"

    def test_complete_run_success(self, test_db):
        """Test completing a service run successfully."""
        run_repo = ServiceRunRepository(test_db)

        run = run_repo.create_run(
            service_name="TestService",
            method_name="success_method"
        )

        # Complete successfully
        completed_run = run_repo.complete_run(
            run.id,
            status="success",
            result_summary={"items_processed": 10}
        )

        assert completed_run.status == "success"
        assert completed_run.completed_at is not None
        assert completed_run.execution_time_seconds is not None
        assert completed_run.error_message is None

    def test_complete_run_failure(self, test_db):
        """Test completing a service run with failure."""
        run_repo = ServiceRunRepository(test_db)

        run = run_repo.create_run(
            service_name="TestService",
            method_name="failing_method"
        )

        # Complete with failure
        completed_run = run_repo.complete_run(
            run.id,
            status="failed",
            error_message="Something went wrong",
            error_traceback="Traceback (most recent call last)..."
        )

        assert completed_run.status == "failed"
        assert completed_run.error_message == "Something went wrong"
        assert completed_run.error_traceback is not None

    def test_get_recent_runs(self, test_db):
        """Test retrieving recent service runs."""
        run_repo = ServiceRunRepository(test_db)

        # Create multiple runs
        run_repo.create_run(service_name="ServiceA", method_name="methodA")
        run_repo.create_run(service_name="ServiceB", method_name="methodB")

        recent_runs = run_repo.get_recent_runs(limit=10)

        assert len(recent_runs) >= 2

    def test_get_failed_runs(self, test_db):
        """Test retrieving failed service runs."""
        run_repo = ServiceRunRepository(test_db)

        # Create and fail a run
        run = run_repo.create_run(
            service_name="FailingService",
            method_name="bad_method"
        )
        run_repo.complete_run(run.id, status="failed", error_message="Test failure")

        failed_runs = run_repo.get_failed_runs(hours=24)

        assert len(failed_runs) >= 1
        assert all(r.status == "failed" for r in failed_runs)

    def test_get_runs_by_service(self, test_db):
        """Test retrieving runs for a specific service."""
        run_repo = ServiceRunRepository(test_db)

        # Create runs for different services
        run_repo.create_run(service_name="SpecificService", method_name="method1")
        run_repo.create_run(service_name="OtherService", method_name="method2")

        specific_runs = run_repo.get_runs_by_service("SpecificService", limit=10)

        assert len(specific_runs) >= 1
        assert all(r.service_name == "SpecificService" for r in specific_runs)

    def test_get_runs_by_user(self, test_db):
        """Test retrieving runs triggered by a specific user."""
        user_repo = UserRepository(test_db)
        run_repo = ServiceRunRepository(test_db)

        user = user_repo.create(telegram_user_id=500001)

        # Create run with user attribution
        run_repo.create_run(
            service_name="UserService",
            method_name="user_method",
            triggered_by_user_id=user.id
        )

        user_runs = run_repo.get_runs_by_user(user.id, limit=10)

        assert len(user_runs) >= 1
        assert all(r.triggered_by_user_id == user.id for r in user_runs)

    def test_execution_time_calculation(self, test_db):
        """Test that execution time is calculated correctly."""
        run_repo = ServiceRunRepository(test_db)

        run = run_repo.create_run(
            service_name="TimedService",
            method_name="timed_method"
        )

        # Simulate some processing time
        import time
        time.sleep(0.1)

        # Complete the run
        completed_run = run_repo.complete_run(run.id, status="success")

        assert completed_run.execution_time_seconds is not None
        assert completed_run.execution_time_seconds >= 0.1
