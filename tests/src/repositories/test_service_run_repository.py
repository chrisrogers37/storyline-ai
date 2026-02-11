"""Tests for ServiceRunRepository."""

import pytest
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from src.repositories.service_run_repository import ServiceRunRepository
from src.models.service_run import ServiceRun


@pytest.fixture
def mock_db():
    """Create a mock database session with chainable query."""
    session = MagicMock(spec=Session)
    mock_query = MagicMock()
    session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    return session


@pytest.fixture
def run_repo(mock_db):
    """Create ServiceRunRepository with mocked database session."""
    with patch.object(ServiceRunRepository, "__init__", lambda self: None):
        repo = ServiceRunRepository()
        repo._db = mock_db
        return repo


@pytest.mark.unit
class TestServiceRunRepository:
    """Test suite for ServiceRunRepository."""

    def test_create_run(self, run_repo, mock_db):
        """Test creating a service run record returns run_id string."""
        mock_run = MagicMock()
        mock_run.id = "test-run-uuid"

        # Mock refresh to keep the mock_run in place
        def mock_refresh(obj):
            pass

        mock_db.refresh.side_effect = mock_refresh

        # The create_run method creates a ServiceRun, adds it, and returns str(run.id)
        # Since we can't control the internal ServiceRun creation,
        # we verify the db operations were called
        result = run_repo.create_run(
            service_name="TestService",
            method_name="test_method",
            input_params={"param1": "value1"},
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

        added_run = mock_db.add.call_args[0][0]
        assert isinstance(added_run, ServiceRun)
        assert added_run.service_name == "TestService"
        assert added_run.method_name == "test_method"
        assert added_run.input_params == {"param1": "value1"}
        assert added_run.triggered_by == "system"

        # Result should be a string (the run ID)
        assert isinstance(result, str)

    def test_create_run_with_user(self, run_repo, mock_db):
        """Test creating a run with user attribution."""
        run_repo.create_run(
            service_name="UserService",
            method_name="user_method",
            user_id="some-user-id",
            triggered_by="user",
        )

        added_run = mock_db.add.call_args[0][0]
        assert added_run.user_id == "some-user-id"
        assert added_run.triggered_by == "user"

    def test_complete_run_success(self, run_repo, mock_db):
        """Test completing a service run successfully."""
        mock_run = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_run

        run_repo.complete_run(
            run_id="some-run-id",
            success=True,
            duration_ms=1500,
            result_summary={"items_processed": 10},
        )

        assert mock_run.status == "completed"
        assert mock_run.success is True
        assert mock_run.duration_ms == 1500
        assert mock_run.result_summary == {"items_processed": 10}
        assert mock_run.completed_at is not None
        mock_db.commit.assert_called_once()

    def test_fail_run(self, run_repo, mock_db):
        """Test marking a service run as failed."""
        mock_run = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_run

        run_repo.fail_run(
            run_id="some-run-id",
            error_type="ValueError",
            error_message="Something went wrong",
            stack_trace="Traceback (most recent call last)...",
            duration_ms=500,
        )

        assert mock_run.status == "failed"
        assert mock_run.success is False
        assert mock_run.error_type == "ValueError"
        assert mock_run.error_message == "Something went wrong"
        assert mock_run.stack_trace == "Traceback (most recent call last)..."
        assert mock_run.duration_ms == 500
        assert mock_run.completed_at is not None
        mock_db.commit.assert_called_once()

    def test_get_recent_runs(self, run_repo, mock_db):
        """Test retrieving recent service runs."""
        mock_runs = [MagicMock(), MagicMock()]
        mock_query = mock_db.query.return_value
        mock_query.all.return_value = mock_runs

        result = run_repo.get_recent_runs(limit=10)

        assert len(result) == 2
        mock_db.query.assert_called_with(ServiceRun)

    def test_get_recent_runs_by_service(self, run_repo, mock_db):
        """Test retrieving runs for a specific service."""
        mock_runs = [MagicMock(service_name="SpecificService")]
        mock_query = mock_db.query.return_value
        mock_query.all.return_value = mock_runs

        result = run_repo.get_recent_runs(service_name="SpecificService", limit=10)

        assert len(result) == 1
        assert result[0].service_name == "SpecificService"

    def test_get_failed_runs(self, run_repo, mock_db):
        """Test retrieving failed service runs."""
        mock_runs = [MagicMock(status="failed")]
        mock_query = mock_db.query.return_value
        mock_query.all.return_value = mock_runs

        result = run_repo.get_failed_runs(since_hours=24)

        assert len(result) == 1
        assert result[0].status == "failed"

    def test_set_result_summary(self, run_repo, mock_db):
        """Test updating the result summary for a run."""
        mock_run = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_run

        run_repo.set_result_summary("some-run-id", {"processed": 5})

        assert mock_run.result_summary == {"processed": 5}
        mock_db.commit.assert_called_once()
