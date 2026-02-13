"""Tests for PostingQueue model definition."""

import uuid
from datetime import datetime

import pytest

from src.models.posting_queue import PostingQueue


@pytest.mark.unit
class TestPostingQueueModel:
    """Tests for PostingQueue model column definitions and defaults."""

    def test_tablename(self):
        assert PostingQueue.__tablename__ == "posting_queue"

    def test_id_default_generates_uuids(self):
        default_fn = PostingQueue.id.default.arg
        assert callable(default_fn)
        assert default_fn.__name__ == "uuid4"

    def test_media_item_id_not_nullable(self):
        assert PostingQueue.media_item_id.nullable is False

    def test_scheduled_for_not_nullable(self):
        assert PostingQueue.scheduled_for.nullable is False

    def test_status_defaults_to_pending(self):
        assert PostingQueue.status.default.arg == "pending"

    def test_status_not_nullable(self):
        assert PostingQueue.status.nullable is False

    def test_retry_count_defaults_to_zero(self):
        assert PostingQueue.retry_count.default.arg == 0

    def test_max_retries_defaults_to_three(self):
        assert PostingQueue.max_retries.default.arg == 3

    def test_has_check_constraint(self):
        constraint_names = [
            c.name for c in PostingQueue.__table_args__ if hasattr(c, "name")
        ]
        assert "check_status" in constraint_names

    def test_repr_format(self):
        item = PostingQueue(
            id=uuid.uuid4(),
            status="pending",
            scheduled_for=datetime(2026, 2, 12, 14, 0),
        )
        result = repr(item)
        assert "pending" in result
        assert "2026" in result
