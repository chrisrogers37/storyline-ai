"""Tests for PostingHistory model definition."""

import uuid
from datetime import datetime

import pytest

from src.models.posting_history import PostingHistory


@pytest.mark.unit
class TestPostingHistoryModel:
    """Tests for PostingHistory model column definitions and defaults."""

    def test_tablename(self):
        assert PostingHistory.__tablename__ == "posting_history"

    def test_id_default_generates_uuids(self):
        default_fn = PostingHistory.id.default.arg
        assert callable(default_fn)
        assert default_fn.__name__ == "uuid4"

    def test_media_item_id_not_nullable(self):
        assert PostingHistory.media_item_id.nullable is False

    def test_posted_at_not_nullable(self):
        assert PostingHistory.posted_at.nullable is False

    def test_status_not_nullable(self):
        assert PostingHistory.status.nullable is False

    def test_success_not_nullable(self):
        assert PostingHistory.success.nullable is False

    def test_retry_count_defaults_to_zero(self):
        assert PostingHistory.retry_count.default.arg == 0

    def test_posting_method_defaults_to_telegram_manual(self):
        assert PostingHistory.posting_method.default.arg == "telegram_manual"

    def test_chat_settings_id_nullable(self):
        assert PostingHistory.chat_settings_id.nullable is True

    def test_has_check_constraint(self):
        constraint_names = [
            c.name for c in PostingHistory.__table_args__ if hasattr(c, "name")
        ]
        assert "check_history_status" in constraint_names

    def test_repr_format(self):
        item = PostingHistory(
            id=uuid.uuid4(),
            status="posted",
            posted_at=datetime(2026, 2, 12, 14, 0),
        )
        result = repr(item)
        assert "posted" in result
        assert "2026" in result
