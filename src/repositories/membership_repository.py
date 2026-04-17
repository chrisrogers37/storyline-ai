"""User-chat membership repository - CRUD for instance memberships."""

from typing import Optional

from src.repositories.audit_repository import AuditRepository
from src.repositories.base_repository import BaseRepository
from src.models.user_chat_membership import UserChatMembership


class MembershipRepository(BaseRepository):
    """Repository for UserChatMembership CRUD operations."""

    def __init__(self):
        super().__init__()
        self._audit_repo: Optional[AuditRepository] = None

    @property
    def audit_repo(self) -> AuditRepository:
        if self._audit_repo is None:
            self._audit_repo = AuditRepository()
        return self._audit_repo

    def close(self):
        if self._audit_repo is not None:
            self._audit_repo.close()
        super().close()

    def get_for_user(
        self, user_id: str, active_only: bool = True
    ) -> list[UserChatMembership]:
        """Get all memberships for a user, eagerly loading chat_settings."""
        from sqlalchemy.orm import joinedload

        query = (
            self.db.query(UserChatMembership)
            .options(joinedload(UserChatMembership.chat_settings))
            .filter(UserChatMembership.user_id == user_id)
        )
        if active_only:
            query = query.filter(UserChatMembership.is_active == True)  # noqa: E712
        result = query.order_by(UserChatMembership.joined_at.asc()).all()
        self.end_read_transaction()
        return result

    def get_for_chat(
        self, chat_settings_id: str, active_only: bool = True
    ) -> list[UserChatMembership]:
        """Get all memberships for a chat instance."""
        query = self.db.query(UserChatMembership).filter(
            UserChatMembership.chat_settings_id == chat_settings_id
        )
        if active_only:
            query = query.filter(UserChatMembership.is_active == True)  # noqa: E712
        result = query.order_by(UserChatMembership.joined_at.asc()).all()
        self.end_read_transaction()
        return result

    def get_membership(
        self, user_id: str, chat_settings_id: str
    ) -> Optional[UserChatMembership]:
        """Get a specific user-chat membership."""
        result = (
            self.db.query(UserChatMembership)
            .filter(
                UserChatMembership.user_id == user_id,
                UserChatMembership.chat_settings_id == chat_settings_id,
            )
            .first()
        )
        self.end_read_transaction()
        return result

    def create_membership(
        self,
        user_id: str,
        chat_settings_id: str,
        instance_role: str = "member",
    ) -> UserChatMembership:
        """Idempotent upsert. Returns existing membership if active; reactivates if inactive."""
        from sqlalchemy.exc import IntegrityError

        existing = self.get_membership(user_id, chat_settings_id)
        if existing:
            if not existing.is_active:
                existing.is_active = True
                self.db.commit()
                self.db.refresh(existing)
                try:
                    self.audit_repo.log(
                        entity_type="membership",
                        entity_id=str(existing.id),
                        action="update",
                        field_changed="is_active",
                        old_value=False,
                        new_value=True,
                        changed_by_user_id=user_id,
                        chat_settings_id=chat_settings_id,
                    )
                except Exception:
                    from src.utils.logger import logger

                    logger.warning(
                        "Audit log failed for membership change", exc_info=True
                    )
            return existing

        membership = UserChatMembership(
            user_id=user_id,
            chat_settings_id=chat_settings_id,
            instance_role=instance_role,
        )
        self.db.add(membership)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            return self.get_membership(user_id, chat_settings_id)
        self.db.refresh(membership)
        try:
            self.audit_repo.log(
                entity_type="membership",
                entity_id=str(membership.id),
                action="create",
                new_value={"instance_role": instance_role},
                changed_by_user_id=user_id,
                chat_settings_id=chat_settings_id,
            )
        except Exception:
            from src.utils.logger import logger

            logger.warning("Audit log failed for membership change", exc_info=True)
        return membership

    def deactivate_for_chat(self, chat_settings_id: str) -> int:
        """Deactivate all memberships for a chat (e.g. bot kicked from group).

        Returns number of memberships deactivated.

        No per-row audit logging — this is a system-triggered bulk operation
        (Telegram ChatMemberHandler). The event is tracked via service_runs.
        """
        count = (
            self.db.query(UserChatMembership)
            .filter(
                UserChatMembership.chat_settings_id == chat_settings_id,
                UserChatMembership.is_active == True,  # noqa: E712
            )
            .update({"is_active": False})
        )
        self.db.commit()
        return count

    def deactivate(
        self, user_id: str, chat_settings_id: str
    ) -> Optional[UserChatMembership]:
        """Deactivate a specific membership."""
        membership = self.get_membership(user_id, chat_settings_id)
        if membership and membership.is_active:
            membership.is_active = False
            self.db.commit()
            self.db.refresh(membership)
            try:
                self.audit_repo.log(
                    entity_type="membership",
                    entity_id=str(membership.id),
                    action="update",
                    field_changed="is_active",
                    old_value=True,
                    new_value=False,
                    changed_by_user_id=user_id,
                    chat_settings_id=chat_settings_id,
                )
            except Exception:
                pass
        return membership
