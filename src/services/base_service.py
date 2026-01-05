"""Base service class with automatic execution tracking and error handling."""
from abc import ABC
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID
import traceback
from contextlib import contextmanager

from src.repositories.service_run_repository import ServiceRunRepository
from src.utils.logger import logger


class BaseService(ABC):
    """
    Base class for all services.
    Provides automatic execution tracking and error handling.

    All service methods should use the track_execution context manager
    to automatically log execution details.
    """

    def __init__(self):
        self.service_run_repo = ServiceRunRepository()
        self.service_name = self.__class__.__name__

    @contextmanager
    def track_execution(
        self,
        method_name: str,
        user_id: Optional[UUID] = None,
        triggered_by: str = "system",
        input_params: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Context manager to track service method execution.

        Usage:
            with self.track_execution("scan_directory", input_params={"path": "/media"}):
                # Your service logic here
                result = self.do_work()
                return result

        Args:
            method_name: Name of the method being executed
            user_id: User who triggered the execution (optional)
            triggered_by: How it was triggered ('user', 'system', 'scheduler', 'cli')
            input_params: Parameters passed to the method
            metadata: Additional context

        Yields:
            run_id: UUID of the service run record
        """
        # Create service run record
        run_id = self.service_run_repo.create_run(
            service_name=self.service_name,
            method_name=method_name,
            user_id=str(user_id) if user_id else None,
            triggered_by=triggered_by,
            input_params=input_params,
            context_metadata=metadata,
        )

        started_at = datetime.utcnow()

        try:
            logger.info(f"[{self.service_name}.{method_name}] Starting execution (run_id: {run_id})")

            yield run_id  # Allow service to access run_id if needed

            # Success
            completed_at = datetime.utcnow()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            self.service_run_repo.complete_run(run_id=run_id, success=True, duration_ms=duration_ms)

            logger.info(f"[{self.service_name}.{method_name}] Completed successfully ({duration_ms}ms)")

        except Exception as e:
            # Failure
            completed_at = datetime.utcnow()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            error_type = type(e).__name__
            error_message = str(e)
            stack_trace = traceback.format_exc()

            self.service_run_repo.fail_run(
                run_id=run_id,
                error_type=error_type,
                error_message=error_message,
                stack_trace=stack_trace,
                duration_ms=duration_ms,
            )

            logger.error(
                f"[{self.service_name}.{method_name}] Failed after {duration_ms}ms: {error_message}", exc_info=True
            )

            # Re-raise the exception
            raise

    def set_result_summary(self, run_id: str, summary: Dict[str, Any]):
        """
        Update the result summary for a service run.
        Call this at the end of your method to record what was accomplished.

        Args:
            run_id: Service run ID (from track_execution)
            summary: Dictionary of results (e.g., {"indexed": 10, "skipped": 2})
        """
        self.service_run_repo.set_result_summary(run_id, summary)
