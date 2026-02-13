"""Tests for shared application constants."""

import pytest

from src.config.constants import (
    MIN_POSTS_PER_DAY,
    MAX_POSTS_PER_DAY,
    MIN_POSTING_HOUR,
    MAX_POSTING_HOUR,
)


@pytest.mark.unit
class TestPostingConstants:
    """Tests for posting schedule constants."""

    def test_min_posts_per_day_is_positive(self):
        assert MIN_POSTS_PER_DAY >= 1

    def test_max_posts_per_day_greater_than_min(self):
        assert MAX_POSTS_PER_DAY > MIN_POSTS_PER_DAY

    def test_max_posts_per_day_is_reasonable(self):
        assert MAX_POSTS_PER_DAY <= 50

    def test_min_posting_hour_is_zero(self):
        assert MIN_POSTING_HOUR == 0

    def test_max_posting_hour_is_23(self):
        assert MAX_POSTING_HOUR == 23

    def test_posting_hour_range_covers_full_day(self):
        assert MAX_POSTING_HOUR - MIN_POSTING_HOUR == 23

    def test_specific_values_match_expected(self):
        assert MIN_POSTS_PER_DAY == 1
        assert MAX_POSTS_PER_DAY == 50
        assert MIN_POSTING_HOUR == 0
        assert MAX_POSTING_HOUR == 23
