"""Tests for backfill exception hierarchy."""

import pytest

from src.exceptions.backfill import (
    BackfillError,
    BackfillMediaExpiredError,
    BackfillMediaNotFoundError,
)
from src.exceptions.base import StorylineError


@pytest.mark.unit
class TestBackfillExceptions:
    """Tests for the backfill exception classes."""

    def test_backfill_error_str_with_media_id(self):
        """BackfillError includes instagram_media_id in string representation."""
        error = BackfillError("Download failed", instagram_media_id="12345")
        assert "Download failed" in str(error)
        assert "media_id: 12345" in str(error)

    def test_backfill_error_str_without_media_id(self):
        """BackfillError works without instagram_media_id."""
        error = BackfillError("General failure")
        assert str(error) == "General failure"
        assert error.instagram_media_id is None

    def test_backfill_error_inherits_from_storyline_error(self):
        """BackfillError is a StorylineError."""
        error = BackfillError("test")
        assert isinstance(error, StorylineError)

    def test_backfill_media_expired_error(self):
        """BackfillMediaExpiredError inherits from BackfillError."""
        error = BackfillMediaExpiredError(instagram_media_id="abc")
        assert isinstance(error, BackfillError)
        assert "expired" in str(error).lower()
        assert error.instagram_media_id == "abc"

    def test_backfill_media_not_found_error(self):
        """BackfillMediaNotFoundError inherits from BackfillError."""
        error = BackfillMediaNotFoundError(instagram_media_id="xyz")
        assert isinstance(error, BackfillError)
        assert "not found" in str(error).lower()
        assert error.instagram_media_id == "xyz"
