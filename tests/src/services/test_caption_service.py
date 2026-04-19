"""Tests for AI caption generation service."""

import pytest
from contextlib import contextmanager
from unittest.mock import Mock, patch

from src.config.constants import MAX_CAPTION_LENGTH
from src.services.core.caption_service import CaptionService


@contextmanager
def mock_track_execution(*args, **kwargs):
    yield "mock_run_id"


@pytest.fixture
def caption_service():
    with patch.object(CaptionService, "__init__", lambda self: None):
        service = CaptionService()
        service.media_repo = Mock()
        service.service_run_repo = Mock()
        service.service_name = "CaptionService"
        service.track_execution = mock_track_execution
        service.set_result_summary = Mock()
        return service


def _make_media_item(**overrides):
    """Create a mock media item with sensible defaults."""
    defaults = {
        "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "file_name": "meme_001.jpg",
        "category": "memes",
        "title": "Funny meme",
        "caption": None,
        "generated_caption": None,
        "tags": ["funny", "relatable"],
        "custom_metadata": None,
    }
    defaults.update(overrides)
    return Mock(**defaults)


def _mock_api_response(text):
    """Create a mock Anthropic API response."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.content = [Mock(text=text)]
    mock_client.messages.create.return_value = mock_response
    return mock_client


class TestCaptionService:
    """Unit tests for CaptionService."""

    def test_generate_caption_success(self, caption_service):
        """Should generate and persist a caption via Claude API."""
        media_item = _make_media_item()
        mock_client = _mock_api_response("Check this out! ")

        with (
            patch("src.services.core.caption_service.settings") as mock_settings,
            patch(
                "src.services.core.caption_service._get_anthropic_client",
                return_value=mock_client,
            ),
        ):
            mock_settings.ANTHROPIC_API_KEY = "sk-test"
            result = caption_service.generate_caption(media_item)

        assert result == "Check this out!"
        caption_service.media_repo.update_metadata.assert_called_once_with(
            str(media_item.id), generated_caption="Check this out!"
        )

    def test_skip_when_manual_caption_exists(self, caption_service):
        """Should skip generation when media has a manual caption."""
        media_item = _make_media_item(caption="My custom caption")

        result = caption_service.generate_caption(media_item)

        assert result is None

    def test_skip_when_already_generated(self, caption_service):
        """Should return cached caption when one already exists."""
        media_item = _make_media_item(generated_caption="Existing AI caption")

        result = caption_service.generate_caption(media_item)

        assert result == "Existing AI caption"

    def test_regenerate_overrides_existing(self, caption_service):
        """Should regenerate when regenerate=True even if caption exists."""
        media_item = _make_media_item(generated_caption="Old caption")
        mock_client = _mock_api_response("New caption")

        with (
            patch("src.services.core.caption_service.settings") as mock_settings,
            patch(
                "src.services.core.caption_service._get_anthropic_client",
                return_value=mock_client,
            ),
        ):
            mock_settings.ANTHROPIC_API_KEY = "sk-test"
            result = caption_service.generate_caption(media_item, regenerate=True)

        assert result == "New caption"

    def test_skip_when_no_api_key(self, caption_service):
        """Should skip when ANTHROPIC_API_KEY is not configured."""
        media_item = _make_media_item()

        with patch("src.services.core.caption_service.settings") as mock_settings:
            mock_settings.ANTHROPIC_API_KEY = None
            result = caption_service.generate_caption(media_item)

        assert result is None

    def test_api_failure_returns_none(self, caption_service):
        """Should return None on API error without crashing."""
        media_item = _make_media_item()
        mock_client = Mock()
        mock_client.messages.create.side_effect = Exception("API timeout")

        with (
            patch("src.services.core.caption_service.settings") as mock_settings,
            patch(
                "src.services.core.caption_service._get_anthropic_client",
                return_value=mock_client,
            ),
        ):
            mock_settings.ANTHROPIC_API_KEY = "sk-test"
            result = caption_service.generate_caption(media_item)

        assert result is None
        caption_service.media_repo.update_metadata.assert_not_called()

    def test_caption_truncated_at_limit(self, caption_service):
        """Should truncate captions exceeding Instagram's limit."""
        media_item = _make_media_item()
        mock_client = _mock_api_response("x" * 3000)

        with (
            patch("src.services.core.caption_service.settings") as mock_settings,
            patch(
                "src.services.core.caption_service._get_anthropic_client",
                return_value=mock_client,
            ),
        ):
            mock_settings.ANTHROPIC_API_KEY = "sk-test"
            result = caption_service.generate_caption(media_item)

        assert len(result) == MAX_CAPTION_LENGTH


class TestBuildPrompt:
    """Tests for prompt construction."""

    def test_prompt_includes_category(self):
        media_item = _make_media_item(category="merch")
        prompt = CaptionService._build_prompt(media_item)
        assert "merch" in prompt

    def test_prompt_includes_title(self):
        media_item = _make_media_item(title="New hoodie drop")
        prompt = CaptionService._build_prompt(media_item)
        assert "New hoodie drop" in prompt

    def test_prompt_includes_tags(self):
        media_item = _make_media_item(tags=["streetwear", "new"])
        prompt = CaptionService._build_prompt(media_item)
        assert "streetwear" in prompt
        assert "new" in prompt

    def test_prompt_handles_no_metadata(self):
        media_item = _make_media_item(
            category=None, title=None, tags=None, custom_metadata=None
        )
        prompt = CaptionService._build_prompt(media_item)
        assert "Instagram Story caption" in prompt

    def test_prompt_includes_custom_metadata(self):
        media_item = _make_media_item(custom_metadata={"product_price": "$29.99"})
        prompt = CaptionService._build_prompt(media_item)
        assert "$29.99" in prompt
