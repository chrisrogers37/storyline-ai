"""Tests for Google Drive exception classes."""

import pytest

from src.exceptions.base import StorylineError
from src.exceptions.google_drive import (
    GoogleDriveError,
    GoogleDriveAuthError,
    GoogleDriveFileNotFoundError,
    GoogleDriveRateLimitError,
)


@pytest.mark.unit
class TestGoogleDriveError:
    """Tests for GoogleDriveError base class."""

    def test_inherits_from_storyline_error(self):
        assert issubclass(GoogleDriveError, StorylineError)

    def test_can_be_raised(self):
        with pytest.raises(GoogleDriveError, match="drive error"):
            raise GoogleDriveError("drive error")

    def test_caught_by_storyline_error(self):
        with pytest.raises(StorylineError):
            raise GoogleDriveError("caught by parent")

    def test_status_code_attribute(self):
        err = GoogleDriveError("msg", status_code=403)
        assert err.status_code == 403

    def test_status_code_default_none(self):
        err = GoogleDriveError("msg")
        assert err.status_code is None

    def test_error_reason_attribute(self):
        err = GoogleDriveError("msg", error_reason="forbidden")
        assert err.error_reason == "forbidden"

    def test_str_includes_status_code(self):
        err = GoogleDriveError("msg", status_code=404)
        assert "404" in str(err)

    def test_str_without_status_code(self):
        err = GoogleDriveError("plain msg")
        assert str(err) == "plain msg"


@pytest.mark.unit
class TestGoogleDriveAuthError:
    """Tests for GoogleDriveAuthError."""

    def test_inherits_from_google_drive_error(self):
        assert issubclass(GoogleDriveAuthError, GoogleDriveError)

    def test_inherits_from_storyline_error(self):
        assert issubclass(GoogleDriveAuthError, StorylineError)

    def test_can_be_raised(self):
        with pytest.raises(GoogleDriveAuthError, match="auth failed"):
            raise GoogleDriveAuthError("auth failed")

    def test_caught_by_parent(self):
        with pytest.raises(GoogleDriveError):
            raise GoogleDriveAuthError("caught")

    def test_default_message(self):
        err = GoogleDriveAuthError()
        assert "authentication failed" in str(err).lower()


@pytest.mark.unit
class TestGoogleDriveFileNotFoundError:
    """Tests for GoogleDriveFileNotFoundError."""

    def test_inherits_from_google_drive_error(self):
        assert issubclass(GoogleDriveFileNotFoundError, GoogleDriveError)

    def test_dual_inheritance_from_file_not_found(self):
        """Also inherits from built-in FileNotFoundError for compatibility."""
        assert issubclass(GoogleDriveFileNotFoundError, FileNotFoundError)

    def test_can_be_raised(self):
        with pytest.raises(GoogleDriveFileNotFoundError, match="not found"):
            raise GoogleDriveFileNotFoundError("not found")

    def test_caught_by_file_not_found(self):
        """Can be caught by FileNotFoundError handler."""
        with pytest.raises(FileNotFoundError):
            raise GoogleDriveFileNotFoundError("caught by builtin")

    def test_caught_by_google_drive_error(self):
        with pytest.raises(GoogleDriveError):
            raise GoogleDriveFileNotFoundError("caught by parent")

    def test_file_id_attribute(self):
        err = GoogleDriveFileNotFoundError("msg", file_id="abc123")
        assert err.file_id == "abc123"


@pytest.mark.unit
class TestGoogleDriveRateLimitError:
    """Tests for GoogleDriveRateLimitError."""

    def test_inherits_from_google_drive_error(self):
        assert issubclass(GoogleDriveRateLimitError, GoogleDriveError)

    def test_can_be_raised(self):
        with pytest.raises(GoogleDriveRateLimitError, match="rate limit"):
            raise GoogleDriveRateLimitError("rate limit exceeded")

    def test_retry_after_attribute(self):
        err = GoogleDriveRateLimitError("quota", retry_after_seconds=60)
        assert err.retry_after_seconds == 60

    def test_retry_after_default_none(self):
        err = GoogleDriveRateLimitError("quota")
        assert err.retry_after_seconds is None
