"""Service run model - tracks all service executions."""

from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import ForeignKey
from datetime import datetime
import uuid

from src.config.database import Base


class ServiceRun(Base):
    """
    Service run model.

    Tracks all service executions for observability and debugging.
    """

    __tablename__ = "service_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Service identification
    service_name = Column(
        String(100), nullable=False, index=True
    )  # 'MediaIngestionService', 'PostingService'
    method_name = Column(
        String(100), nullable=False
    )  # 'scan_directory', 'process_pending_posts'

    # Execution context
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )  # Who triggered it (NULL for automated)
    triggered_by = Column(
        String(50), default="system"
    )  # 'user', 'system', 'scheduler', 'cli'

    # Timing
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime)
    duration_ms = Column(Integer)  # Calculated: completed_at - started_at

    # Status
    status = Column(
        String(50), nullable=False, default="running", index=True
    )  # 'running', 'completed', 'failed'
    success = Column(Boolean)

    # Results
    result_summary = Column(JSONB)  # {items_processed: 10, items_failed: 2}
    error_message = Column(Text)
    error_type = Column(String(100))
    stack_trace = Column(Text)

    # Metadata
    input_params = Column(JSONB)  # Parameters passed to the method
    context_metadata = Column(JSONB)  # Additional context

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'completed', 'failed')",
            name="check_service_run_status",
        ),
    )

    def __repr__(self):
        return f"<ServiceRun {self.service_name}.{self.method_name} ({self.status})>"
