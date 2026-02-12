"""Instagram backfill related exceptions."""

from typing import Optional

from src.exceptions.base import StorylineError


class BackfillError(StorylineError):
    """General error during Instagram media backfill."""

    def __init__(
        self,
        message: str,
        instagram_media_id: Optional[str] = None,
    ):
        super().__init__(message)
        self.instagram_media_id = instagram_media_id

    def __str__(self) -> str:
        base = super().__str__()
        if self.instagram_media_id:
            return f"{base} (media_id: {self.instagram_media_id})"
        return base


class BackfillMediaExpiredError(BackfillError):
    """Instagram media URL has expired before download completed."""

    def __init__(
        self,
        message: str = "Instagram media URL has expired",
        **kwargs,
    ):
        super().__init__(message, **kwargs)


class BackfillMediaNotFoundError(BackfillError):
    """Instagram media item was not found or is no longer accessible."""

    def __init__(
        self,
        message: str = "Instagram media not found",
        **kwargs,
    ):
        super().__init__(message, **kwargs)
