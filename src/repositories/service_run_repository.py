"""Service run repository - CRUD operations for service runs."""

from typing import Optional, List
from datetime import datetime, timedelta

from src.repositories.base_repository import BaseRepository
from src.models.service_run import ServiceRun


class ServiceRunRepository(BaseRepository):
    """Repository for ServiceRun CRUD operations."""

    def __init__(self):
        super().__init__()

    def get_by_id(self, run_id: str) -> Optional[ServiceRun]:
        """Get service run by ID."""
        result = self.db.query(ServiceRun).filter(ServiceRun.id == run_id).first()
        self.end_read_transaction()
        return result

    def create_run(
        self,
        service_name: str,
        method_name: str,
        user_id: Optional[str] = None,
        triggered_by: str = "system",
        input_params: Optional[dict] = None,
        context_metadata: Optional[dict] = None,
    ) -> str:
        """Create a new service run record. Returns run_id."""
        run = ServiceRun(
            service_name=service_name,
            method_name=method_name,
            user_id=user_id,
            triggered_by=triggered_by,
            input_params=input_params,
            context_metadata=context_metadata,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return str(run.id)

    def complete_run(
        self,
        run_id: str,
        success: bool,
        duration_ms: int,
        result_summary: Optional[dict] = None,
    ):
        """Mark a service run as completed."""
        run = self.get_by_id(run_id)
        if run:
            run.status = "completed"
            run.success = success
            run.completed_at = datetime.utcnow()
            run.duration_ms = duration_ms
            run.result_summary = result_summary
            self.db.commit()

    def fail_run(
        self,
        run_id: str,
        error_type: str,
        error_message: str,
        stack_trace: str,
        duration_ms: int,
    ):
        """Mark a service run as failed."""
        run = self.get_by_id(run_id)
        if run:
            run.status = "failed"
            run.success = False
            run.completed_at = datetime.utcnow()
            run.duration_ms = duration_ms
            run.error_type = error_type
            run.error_message = error_message
            run.stack_trace = stack_trace
            self.db.commit()

    def set_result_summary(self, run_id: str, summary: dict):
        """Update the result summary for a run."""
        run = self.get_by_id(run_id)
        if run:
            run.result_summary = summary
            self.db.commit()

    # Used by InstagramBackfillService.get_backfill_status() and
    # MediaSyncService.get_last_sync_info(), plus test_base_service.py integration tests.
    def get_recent_runs(
        self, service_name: Optional[str] = None, limit: int = 100
    ) -> List[ServiceRun]:
        """Get recent service runs."""
        query = self.db.query(ServiceRun)

        if service_name:
            query = query.filter(ServiceRun.service_name == service_name)

        result = query.order_by(ServiceRun.started_at.desc()).limit(limit).all()
        self.end_read_transaction()
        return result

    def delete_older_than(self, days: int) -> int:
        """Delete service runs older than the given number of days.

        Used for retention policy to prevent unbounded table growth.

        Args:
            days: Delete runs with started_at older than this many days ago.

        Returns:
            Number of rows deleted.
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        count = (
            self.db.query(ServiceRun).filter(ServiceRun.started_at < cutoff).delete()
        )
        self.db.commit()
        return count

    # NOTE: Unused in production as of 2026-02-10.
    # Planned for Phase 3 monitoring dashboard and alerting system.
    def get_failed_runs(
        self, since_hours: int = 24, limit: int = 50
    ) -> List[ServiceRun]:
        """Get recent failed runs."""
        since = datetime.utcnow() - timedelta(hours=since_hours)
        result = (
            self.db.query(ServiceRun)
            .filter(ServiceRun.status == "failed", ServiceRun.started_at >= since)
            .order_by(ServiceRun.started_at.desc())
            .limit(limit)
            .all()
        )
        self.end_read_transaction()
        return result
