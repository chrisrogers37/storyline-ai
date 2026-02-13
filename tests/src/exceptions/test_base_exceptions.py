"""Tests for base exception hierarchy."""

import pytest

from src.exceptions.base import StorylineError


@pytest.mark.unit
class TestStorylineError:
    """Tests for the StorylineError base exception."""

    def test_inherits_from_exception(self):
        """StorylineError inherits from Exception."""
        assert issubclass(StorylineError, Exception)

    def test_can_be_raised_and_caught(self):
        """StorylineError can be raised and caught."""
        with pytest.raises(StorylineError, match="test error"):
            raise StorylineError("test error")

    def test_caught_by_exception_handler(self):
        """StorylineError is caught by a generic Exception handler."""
        with pytest.raises(Exception):
            raise StorylineError("generic catch")

    def test_message_stored(self):
        """Error message is accessible via args."""
        err = StorylineError("my message")
        assert str(err) == "my message"
        assert err.args == ("my message",)

    def test_empty_message(self):
        """StorylineError works with empty message."""
        err = StorylineError()
        assert str(err) == ""
