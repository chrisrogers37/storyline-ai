"""Instagram and cloud storage related exceptions."""

from typing import Optional

from src.exceptions.base import StorylineError


class InstagramAPIError(StorylineError):
    """
    General Instagram API error.

    Raised when Instagram's Graph API returns an error response.

    Attributes:
        message: Human-readable error description
        error_code: Instagram/Meta error code (e.g., 'OAuthException')
        error_subcode: More specific error subcode from Meta
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        error_subcode: Optional[int] = None,
    ):
        super().__init__(message)
        self.error_code = error_code
        self.error_subcode = error_subcode

    def __str__(self) -> str:
        base = super().__str__()
        if self.error_code:
            return f"{base} (code: {self.error_code})"
        return base


class RateLimitError(InstagramAPIError):
    """
    Instagram API rate limit exceeded.

    Raised when we've hit Meta's rate limits (typically 25 posts/hour for Stories).
    The caller should back off and retry later, or route to Telegram fallback.

    Attributes:
        retry_after_seconds: Suggested wait time before retrying (if provided by API)
    """

    def __init__(
        self,
        message: str = "Instagram API rate limit exceeded",
        retry_after_seconds: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.retry_after_seconds = retry_after_seconds


class TokenExpiredError(InstagramAPIError):
    """
    Instagram access token has expired or is invalid.

    Raised when the API returns an authentication error indicating
    the token needs to be refreshed or re-authorized.

    This error should trigger automatic token refresh if possible,
    or alert the admin to re-authenticate.
    """

    def __init__(
        self,
        message: str = "Instagram access token has expired",
        **kwargs,
    ):
        super().__init__(message, **kwargs)


class MediaUploadError(StorylineError):
    """
    Cloud storage upload failed.

    Raised when uploading media to Cloudinary (or other cloud storage) fails.
    This could be due to network issues, invalid credentials, or file problems.

    Attributes:
        file_path: Local path to the file that failed to upload
        provider: Cloud storage provider name (e.g., 'cloudinary')
    """

    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        provider: Optional[str] = None,
    ):
        super().__init__(message)
        self.file_path = file_path
        self.provider = provider

    def __str__(self) -> str:
        base = super().__str__()
        if self.file_path:
            return f"{base} (file: {self.file_path})"
        return base
