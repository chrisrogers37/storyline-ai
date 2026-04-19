"""AI caption generation service using Claude API."""

from typing import Optional

from src.config.constants import MAX_CAPTION_LENGTH
from src.config.settings import settings
from src.repositories.media_repository import MediaRepository
from src.services.base_service import BaseService
from src.utils.logger import logger

# Module-level singleton — avoids creating/destroying HTTP clients per call
_anthropic_client = None


def _get_anthropic_client():
    """Return a cached Anthropic client instance."""
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic

        _anthropic_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _anthropic_client


class CaptionService(BaseService):
    """Generates Instagram Story captions using Claude API.

    Called at queue time to produce captions based on a media item's
    category, tags, and title. Captions are stored in
    ``media_items.generated_caption`` so they are cached and never
    re-generated unless explicitly requested.

    Accepts an optional ``media_repo`` to reuse the caller's DB session
    instead of opening a new one.
    """

    def __init__(self, media_repo: Optional[MediaRepository] = None):
        super().__init__()
        self.media_repo = media_repo or MediaRepository()

    async def generate_caption(
        self,
        media_item,
        *,
        regenerate: bool = False,
    ) -> Optional[str]:
        """Generate a caption for a media item.

        Skips generation when:
        - The media item already has a manual caption.
        - A generated caption already exists (unless ``regenerate=True``).
        - No ANTHROPIC_API_KEY is configured.

        Args:
            media_item: MediaItem ORM instance.
            regenerate: Force a new generation even if one exists.

        Returns:
            The generated caption string, or None if skipped.
        """
        if media_item.caption:
            logger.debug(
                f"Skipping AI caption for {media_item.file_name}: manual caption exists"
            )
            return None

        if media_item.generated_caption and not regenerate:
            logger.debug(
                f"Skipping AI caption for {media_item.file_name}: already generated"
            )
            return media_item.generated_caption

        if not settings.ANTHROPIC_API_KEY:
            logger.warning("ANTHROPIC_API_KEY not set — skipping AI caption generation")
            return None

        with self.track_execution(
            "generate_caption",
            triggered_by="scheduler",
            input_params={
                "media_id": str(media_item.id),
                "category": media_item.category,
                "regenerate": regenerate,
            },
        ) as run_id:
            caption = await self._call_api(media_item)

            if caption:
                self.media_repo.update_metadata(
                    str(media_item.id), generated_caption=caption
                )

            self.set_result_summary(
                run_id,
                {
                    "generated": caption is not None,
                    "caption_length": len(caption) if caption else 0,
                    "category": media_item.category,
                },
            )
            return caption

    async def _call_api(self, media_item) -> Optional[str]:
        """Call Claude API to generate a caption.

        Runs the synchronous Anthropic SDK call in a thread to avoid
        blocking the asyncio event loop.

        Returns:
            Generated caption text, or None on failure.
        """
        import asyncio

        prompt = self._build_prompt(media_item)
        try:
            client = _get_anthropic_client()
            response = await asyncio.to_thread(
                client.messages.create,
                model=settings.CAPTION_MODEL,
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            caption = response.content[0].text.strip()
            if len(caption) > MAX_CAPTION_LENGTH:
                caption = caption[:MAX_CAPTION_LENGTH]
            return caption
        except Exception as e:
            logger.error(f"AI caption generation failed: {e}", exc_info=True)
            return None

    @staticmethod
    def _build_prompt(media_item) -> str:
        """Build the LLM prompt from media metadata."""
        parts = [
            "Generate a short, engaging Instagram Story caption. "
            "Keep it casual, punchy, and under 150 characters. "
            "Do not include hashtags — those are added separately. "
            "Return ONLY the caption text, nothing else."
        ]

        if media_item.category:
            parts.append(f"\nContent category: {media_item.category}")

        if media_item.title:
            parts.append(f"Title/subject: {media_item.title}")

        if media_item.tags:
            parts.append(f"Tags: {', '.join(media_item.tags)}")

        # NOTE: custom_metadata is sent to Anthropic's API for caption context.
        # Do not store sensitive data in this JSONB field if AI captions are enabled.
        if media_item.custom_metadata:
            parts.append(f"Additional context: {media_item.custom_metadata}")

        return "\n".join(parts)
