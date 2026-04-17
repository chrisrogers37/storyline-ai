"""Audit log repository - CRUD for audit trail entries."""

import json
from typing import Optional, List
from datetime import datetime, timedelta

from src.repositories.base_repository import BaseRepository
from src.models.audit_log import AuditLog


class AuditRepository(BaseRepository):
    """Repository for AuditLog CRUD operations."""

    def log(
        self,
        entity_type: str,
        entity_id: Optional[str],
        action: str,
        changed_by_user_id: Optional[str] = None,
        chat_settings_id: Optional[str] = None,
        field_changed: Optional[str] = None,
        old_value=None,
        new_value=None,
    ) -> AuditLog:
        """Create an audit log entry."""
        entry = AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            changed_by_user_id=changed_by_user_id,
            chat_settings_id=chat_settings_id,
            field_changed=field_changed,
            old_value=json.dumps(old_value) if old_value is not None else None,
            new_value=json.dumps(new_value) if new_value is not None else None,
        )
        self.db.add(entry)
        self.db.commit()
        return entry

    def get_for_instance(
        self,
        chat_settings_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AuditLog]:
        """Get audit log entries for a chat instance, most recent first."""
        result = (
            self.db.query(AuditLog)
            .filter(AuditLog.chat_settings_id == chat_settings_id)
            .order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        self.end_read_transaction()
        return result

    def get_for_entity(
        self,
        entity_type: str,
        entity_id: str,
        limit: int = 50,
    ) -> List[AuditLog]:
        """Get audit history for a specific entity."""
        result = (
            self.db.query(AuditLog)
            .filter(
                AuditLog.entity_type == entity_type,
                AuditLog.entity_id == entity_id,
            )
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .all()
        )
        self.end_read_transaction()
        return result

    def delete_older_than(self, days: int) -> int:
        """Delete audit entries older than N days. Returns count deleted."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        count = self.db.query(AuditLog).filter(AuditLog.created_at < cutoff).delete()
        self.db.commit()
        return count
