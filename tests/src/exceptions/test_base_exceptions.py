"""Tests for base exception hierarchy."""

import pytest

from src.exceptions.base import StorydumpError


@pytest.mark.unit
class TestStorydumpError:
    """Tests for the StorydumpError base exception."""

    def test_inherits_from_exception(self):
        """StorydumpError inherits from Exception."""
        assert issubclass(StorydumpError, Exception)

    def test_can_be_raised_and_caught(self):
        """StorydumpError can be raised and caught."""
        with pytest.raises(StorydumpError, match="test error"):
            raise StorydumpError("test error")

    def test_caught_by_exception_handler(self):
        """StorydumpError is caught by a generic Exception handler."""
        with pytest.raises(Exception):
            raise StorydumpError("generic catch")

    def test_message_stored(self):
        """Error message is accessible via args."""
        err = StorydumpError("my message")
        assert str(err) == "my message"
        assert err.args == ("my message",)

    def test_empty_message(self):
        """StorydumpError works with empty message."""
        err = StorydumpError()
        assert str(err) == ""
