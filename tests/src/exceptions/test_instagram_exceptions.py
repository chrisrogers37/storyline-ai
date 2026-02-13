"""Tests for Instagram and cloud exception classes."""

import pytest

from src.exceptions.base import StorylineError
from src.exceptions.instagram import (
    InstagramAPIError,
    RateLimitError,
    TokenExpiredError,
    MediaUploadError,
)


@pytest.mark.unit
class TestInstagramAPIError:
    """Tests for InstagramAPIError base class."""

    def test_inherits_from_storyline_error(self):
        assert issubclass(InstagramAPIError, StorylineError)

    def test_can_be_raised(self):
        with pytest.raises(InstagramAPIError, match="api error"):
            raise InstagramAPIError("api error")

    def test_caught_by_storyline_error(self):
        with pytest.raises(StorylineError):
            raise InstagramAPIError("caught by parent")

    def test_error_code_attribute(self):
        err = InstagramAPIError("msg", error_code="OAuthException")
        assert err.error_code == "OAuthException"

    def test_error_code_default_none(self):
        err = InstagramAPIError("msg")
        assert err.error_code is None

    def test_error_subcode_attribute(self):
        err = InstagramAPIError("msg", error_subcode=463)
        assert err.error_subcode == 463

    def test_response_attribute(self):
        err = InstagramAPIError("msg", response={"error": "bad"})
        assert err.response == {"error": "bad"}

    def test_str_includes_error_code(self):
        err = InstagramAPIError("msg", error_code="OAuthException")
        assert "OAuthException" in str(err)

    def test_str_without_error_code(self):
        err = InstagramAPIError("plain msg")
        assert str(err) == "plain msg"


@pytest.mark.unit
class TestRateLimitError:
    """Tests for RateLimitError."""

    def test_inherits_from_instagram_api_error(self):
        assert issubclass(RateLimitError, InstagramAPIError)

    def test_inherits_from_storyline_error(self):
        assert issubclass(RateLimitError, StorylineError)

    def test_can_be_raised(self):
        with pytest.raises(RateLimitError, match="rate limited"):
            raise RateLimitError("rate limited")

    def test_caught_by_parent(self):
        with pytest.raises(InstagramAPIError):
            raise RateLimitError("caught")

    def test_retry_after_attribute(self):
        err = RateLimitError("limited", retry_after_seconds=120)
        assert err.retry_after_seconds == 120

    def test_default_message(self):
        err = RateLimitError()
        assert "rate limit" in str(err).lower()


@pytest.mark.unit
class TestTokenExpiredError:
    """Tests for TokenExpiredError."""

    def test_inherits_from_instagram_api_error(self):
        assert issubclass(TokenExpiredError, InstagramAPIError)

    def test_can_be_raised(self):
        with pytest.raises(TokenExpiredError, match="token expired"):
            raise TokenExpiredError("token expired")

    def test_caught_by_parent(self):
        with pytest.raises(InstagramAPIError):
            raise TokenExpiredError("caught")

    def test_default_message(self):
        err = TokenExpiredError()
        assert "expired" in str(err).lower()


@pytest.mark.unit
class TestMediaUploadError:
    """Tests for MediaUploadError."""

    def test_inherits_from_storyline_error(self):
        assert issubclass(MediaUploadError, StorylineError)

    def test_not_instagram_api_error(self):
        """MediaUploadError is separate from InstagramAPIError hierarchy."""
        assert not issubclass(MediaUploadError, InstagramAPIError)

    def test_can_be_raised(self):
        with pytest.raises(MediaUploadError, match="upload failed"):
            raise MediaUploadError("upload failed")

    def test_provider_attribute(self):
        err = MediaUploadError("failed", provider="cloudinary")
        assert err.provider == "cloudinary"

    def test_provider_default_none(self):
        err = MediaUploadError("failed")
        assert err.provider is None

    def test_file_path_attribute(self):
        err = MediaUploadError("failed", file_path="/tmp/image.jpg")
        assert err.file_path == "/tmp/image.jpg"

    def test_str_includes_file_path(self):
        err = MediaUploadError("upload failed", file_path="/tmp/img.jpg")
        assert "/tmp/img.jpg" in str(err)

    def test_str_without_file_path(self):
        err = MediaUploadError("upload failed")
        assert str(err) == "upload failed"
