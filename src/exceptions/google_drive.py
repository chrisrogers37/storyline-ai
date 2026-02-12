"""Google Drive related exceptions."""

from typing import Optional

from src.exceptions.base import StorylineError


class GoogleDriveError(StorylineError):
    """General Google Drive API error."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        error_reason: Optional[str] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.error_reason = error_reason

    def __str__(self) -> str:
        base = super().__str__()
        if self.status_code:
            return f"{base} (status: {self.status_code})"
        return base


class GoogleDriveAuthError(GoogleDriveError):
    """Authentication or authorization error (invalid/expired credentials,
    or service account lacks folder access)."""

    def __init__(
        self,
        message: str = "Google Drive authentication failed",
        **kwargs,
    ):
        super().__init__(message, **kwargs)


class GoogleDriveRateLimitError(GoogleDriveError):
    """API rate limit exceeded (1000 queries per 100 seconds)."""

    def __init__(
        self,
        message: str = "Google Drive API rate limit exceeded",
        retry_after_seconds: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.retry_after_seconds = retry_after_seconds


class GoogleDriveFileNotFoundError(GoogleDriveError, FileNotFoundError):
    """File or folder not found or not accessible.

    Inherits from both GoogleDriveError and FileNotFoundError so callers
    catching either type will handle it correctly (satisfies ABC contract).
    """

    def __init__(
        self,
        message: str = "Google Drive file not found",
        file_id: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.file_id = file_id
