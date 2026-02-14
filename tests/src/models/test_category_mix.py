"""Tests for CategoryPostCaseMix model definition."""

from datetime import datetime
from decimal import Decimal

import pytest

from src.models.category_mix import CategoryPostCaseMix


@pytest.mark.unit
class TestCategoryPostCaseMixModel:
    """Tests for CategoryPostCaseMix model column definitions and defaults."""

    def test_tablename(self):
        assert CategoryPostCaseMix.__tablename__ == "category_post_case_mix"

    def test_id_default_generates_uuids(self):
        default_fn = CategoryPostCaseMix.id.default.arg
        assert callable(default_fn)
        assert default_fn.__name__ == "uuid4"

    def test_category_not_nullable(self):
        assert CategoryPostCaseMix.category.nullable is False

    def test_ratio_not_nullable(self):
        assert CategoryPostCaseMix.ratio.nullable is False

    def test_effective_from_not_nullable(self):
        assert CategoryPostCaseMix.effective_from.nullable is False

    def test_is_current_defaults_to_true(self):
        assert CategoryPostCaseMix.is_current.default.arg is True

    def test_chat_settings_id_nullable(self):
        assert CategoryPostCaseMix.chat_settings_id.nullable is True

    def test_has_ratio_check_constraint(self):
        constraint_names = [
            c.name for c in CategoryPostCaseMix.__table_args__ if hasattr(c, "name")
        ]
        assert "check_ratio_range" in constraint_names

    def test_repr_current(self):
        item = CategoryPostCaseMix(
            category="memes", ratio=Decimal("0.7000"), is_current=True
        )
        result = repr(item)
        assert "memes" in result
        assert "70.0%" in result
        assert "current" in result

    def test_repr_expired(self):
        item = CategoryPostCaseMix(
            category="merch",
            ratio=Decimal("0.3000"),
            is_current=False,
            effective_to=datetime(2026, 1, 15),
        )
        result = repr(item)
        assert "merch" in result
        assert "expired" in result
