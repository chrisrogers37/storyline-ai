"""Audit log model - tracks settings, membership, and lock changes."""

from sqlalchemy import Column, String, DateTime, Text, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import ForeignKey
from datetime import datetime
import uuid

from src.config.database import Base


class AuditLog(Base):
    """
    Audit log for entity changes.

    Tracks who changed what, when, and the before/after values.
    Entity types:
    - 'setting': chat_settings field changes (toggle, update)
    - 'membership': user_chat_membership changes (create, deactivate, role change)
    - 'lock': media_posting_lock lifecycle (create, delete)
    """

    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # What changed
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(UUID(as_uuid=True), index=True)
    action = Column(String(20), nullable=False)  # 'create', 'update', 'delete'
    field_changed = Column(String(100))  # null for create/delete actions
    old_value = Column(Text)  # JSON-serialized
    new_value = Column(Text)  # JSON-serialized

    # Who changed it
    changed_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )

    # Tenant scope
    chat_settings_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_settings.id"),
        nullable=True,
        index=True,
    )

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('setting', 'membership', 'lock')",
            name="check_audit_entity_type",
        ),
        CheckConstraint(
            "action IN ('create', 'update', 'delete')",
            name="check_audit_action",
        ),
    )

    def __repr__(self):
        return (
            f"<AuditLog {self.action} {self.entity_type} by {self.changed_by_user_id}>"
        )
