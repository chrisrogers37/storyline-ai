"""Tests for MediaPostingLock model definition."""

import uuid

import pytest

from src.models.media_lock import MediaPostingLock


@pytest.mark.unit
class TestMediaPostingLockModel:
    """Tests for MediaPostingLock model column definitions and defaults."""

    def test_tablename(self):
        assert MediaPostingLock.__tablename__ == "media_posting_locks"

    def test_id_default_generates_uuids(self):
        default_fn = MediaPostingLock.id.default.arg
        assert callable(default_fn)
        assert default_fn.__name__ == "uuid4"

    def test_media_item_id_not_nullable(self):
        assert MediaPostingLock.media_item_id.nullable is False

    def test_locked_at_not_nullable(self):
        assert MediaPostingLock.locked_at.nullable is False

    def test_locked_until_nullable(self):
        assert MediaPostingLock.locked_until.nullable is True

    def test_lock_reason_defaults_to_recent_post(self):
        assert MediaPostingLock.lock_reason.default.arg == "recent_post"

    def test_chat_settings_id_nullable(self):
        assert MediaPostingLock.chat_settings_id.nullable is True

    def test_has_tenant_scoped_unique_constraint(self):
        constraint_names = [
            c.name for c in MediaPostingLock.__table_args__ if hasattr(c, "name")
        ]
        assert "unique_active_lock_per_tenant" in constraint_names

    def test_old_unique_constraint_removed(self):
        constraint_names = [
            c.name for c in MediaPostingLock.__table_args__ if hasattr(c, "name")
        ]
        assert "unique_active_lock" not in constraint_names

    def test_repr_format(self):
        item_id = uuid.uuid4()
        item = MediaPostingLock(media_item_id=item_id, locked_until=None)
        result = repr(item)
        assert str(item_id) in result
