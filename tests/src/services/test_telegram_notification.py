"""Tests for TelegramNotificationService."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4

from src.services.core.telegram_notification import (
    TelegramNotificationService,
    _extract_button_labels,
)


@pytest.fixture
def mock_telegram_service():
    """Mock parent TelegramService with required attributes."""
    service = Mock()
    service.bot = AsyncMock()
    service.bot_token = "123456:ABC-DEF"
    service.channel_id = -1001234567890
    service.media_repo = Mock()
    service.queue_repo = Mock()
    service.history_repo = Mock()
    service.settings_service = Mock()
    service.interaction_service = Mock()
    service.ig_account_service = Mock()
    return service


@pytest.fixture
def notification_service(mock_telegram_service):
    """Create TelegramNotificationService with mocked parent."""
    return TelegramNotificationService(mock_telegram_service)


@pytest.mark.unit
class TestBuildCaption:
    """Tests for _build_caption routing."""

    def test_routes_to_enhanced_when_caption_style_enhanced(self, notification_service):
        """Test _build_caption routes to enhanced when CAPTION_STYLE is enhanced."""
        media = Mock(
            title="Test Image",
            caption=None,
            link_url=None,
            tags=[],
        )

        with patch("src.services.core.telegram_notification.settings") as mock_settings:
            mock_settings.CAPTION_STYLE = "enhanced"
            result = notification_service._build_caption(media, active_account=None)

        # Enhanced caption includes "Account: Not set" for no account
        assert "Account: Not set" in result

    def test_routes_to_simple_when_caption_style_simple(self, notification_service):
        """Test _build_caption routes to simple when CAPTION_STYLE is simple."""
        media = Mock(
            title="Test Image",
            caption=None,
            link_url=None,
            tags=[],
            file_name="test.jpg",
            id="12345678-abcd",
        )

        with patch("src.services.core.telegram_notification.settings") as mock_settings:
            mock_settings.CAPTION_STYLE = "simple"
            result = notification_service._build_caption(
                media, verbose=True, active_account=None
            )

        # Simple caption includes file info when verbose
        assert "File: test.jpg" in result

    def test_enhanced_caption_shows_active_account(self, notification_service):
        """Test enhanced caption shows active account display name."""
        media = Mock(
            title="Test Image",
            caption=None,
            link_url=None,
            tags=[],
        )
        account = Mock(display_name="Main Account")

        with patch("src.services.core.telegram_notification.settings") as mock_settings:
            mock_settings.CAPTION_STYLE = "enhanced"
            result = notification_service._build_caption(media, active_account=account)

        assert "Account: Main Account" in result

    def test_enhanced_caption_shows_not_set_when_no_account(self, notification_service):
        """Test enhanced caption shows 'Not set' when no account."""
        media = Mock(
            title="Test Image",
            caption=None,
            link_url=None,
            tags=[],
        )

        with patch("src.services.core.telegram_notification.settings") as mock_settings:
            mock_settings.CAPTION_STYLE = "enhanced"
            result = notification_service._build_caption(media, active_account=None)

        assert "Account: Not set" in result


@pytest.mark.unit
class TestBuildSimpleCaption:
    """Tests for _build_simple_caption formatting."""

    def test_includes_title(self, notification_service):
        """Test simple caption includes media title."""
        media = Mock(
            title="My Title",
            caption=None,
            link_url=None,
            tags=[],
            file_name="img.jpg",
            id="abcd1234",
        )

        result = notification_service._build_simple_caption(media)

        assert "My Title" in result

    def test_includes_force_sent_indicator(self, notification_service):
        """Test simple caption includes lightning bolt for force-sent."""
        media = Mock(
            title="Test",
            caption=None,
            link_url=None,
            tags=[],
            file_name="img.jpg",
            id="abcd1234",
        )

        result = notification_service._build_simple_caption(media, force_sent=True)

        assert "\u26a1" in result

    def test_verbose_shows_file_and_id(self, notification_service):
        """Test verbose=True includes file name and truncated ID."""
        media = Mock(
            title="Test",
            caption=None,
            link_url=None,
            tags=[],
            file_name="image.jpg",
            id="12345678-abcd-efgh",
        )

        result = notification_service._build_simple_caption(media, verbose=True)

        assert "File: image.jpg" in result
        assert "ID: 12345678" in result

    def test_verbose_off_hides_file_and_id(self, notification_service):
        """Test verbose=False omits file name and ID."""
        media = Mock(
            title="Test",
            caption=None,
            link_url=None,
            tags=[],
            file_name="image.jpg",
            id="12345678-abcd-efgh",
        )

        result = notification_service._build_simple_caption(media, verbose=False)

        assert "File:" not in result
        assert "ID:" not in result

    def test_includes_account_indicator(self, notification_service):
        """Test simple caption includes account when provided."""
        media = Mock(
            title="Test",
            caption=None,
            link_url=None,
            tags=[],
            file_name="img.jpg",
            id="abcd1234",
        )
        account = Mock(display_name="Brand Account")

        result = notification_service._build_simple_caption(
            media, active_account=account
        )

        assert "Brand Account" in result

    def test_includes_tags(self, notification_service):
        """Test simple caption includes tags as hashtags."""
        media = Mock(
            title="Test",
            caption=None,
            link_url=None,
            tags=["meme", "funny"],
            file_name="img.jpg",
            id="abcd1234",
        )

        result = notification_service._build_simple_caption(media, verbose=False)

        assert "#meme" in result
        assert "#funny" in result

    def test_includes_link_url(self, notification_service):
        """Test simple caption includes link URL."""
        media = Mock(
            title="Test",
            caption=None,
            link_url="https://example.com",
            tags=[],
            file_name="img.jpg",
            id="abcd1234",
        )

        result = notification_service._build_simple_caption(media, verbose=False)

        assert "https://example.com" in result


@pytest.mark.unit
class TestBuildEnhancedCaption:
    """Tests for _build_enhanced_caption formatting."""

    def test_verbose_on_shows_workflow_instructions(self, notification_service):
        """Test verbose=True includes workflow instructions."""
        media = Mock(
            title="Test",
            caption=None,
            link_url=None,
            tags=[],
        )

        result = notification_service._build_enhanced_caption(
            media, verbose=True, active_account=None
        )

        assert "Click & hold image" in result
        assert "Open Instagram" in result

    def test_verbose_off_hides_workflow_instructions(self, notification_service):
        """Test verbose=False omits workflow instructions."""
        media = Mock(
            title="Test",
            caption=None,
            link_url=None,
            tags=[],
        )

        result = notification_service._build_enhanced_caption(
            media, verbose=False, active_account=None
        )

        assert "Click & hold image" not in result
        assert "Open Instagram" not in result

    def test_verbose_off_still_shows_account(self, notification_service):
        """Test verbose=False still shows the account indicator."""
        media = Mock(
            title="Test",
            caption=None,
            link_url=None,
            tags=[],
        )
        account = Mock(display_name="My Brand")

        result = notification_service._build_enhanced_caption(
            media, verbose=False, active_account=account
        )

        assert "My Brand" in result

    def test_force_sent_shows_lightning(self, notification_service):
        """Test force_sent=True shows lightning bolt."""
        media = Mock(
            title="Test",
            caption=None,
            link_url=None,
            tags=[],
        )

        result = notification_service._build_enhanced_caption(
            media, force_sent=True, active_account=None
        )

        assert "\u26a1" in result

    def test_includes_caption_text(self, notification_service):
        """Test enhanced caption includes media caption."""
        media = Mock(
            title="Test",
            caption="This is the caption text",
            link_url=None,
            tags=[],
        )

        result = notification_service._build_enhanced_caption(
            media, active_account=None
        )

        assert "This is the caption text" in result

    def test_includes_tags(self, notification_service):
        """Test enhanced caption includes hashtags."""
        media = Mock(
            title="Test",
            caption=None,
            link_url=None,
            tags=["product", "sale"],
        )

        result = notification_service._build_enhanced_caption(
            media, verbose=False, active_account=None
        )

        assert "#product" in result
        assert "#sale" in result


@pytest.mark.unit
class TestGetHeaderEmoji:
    """Tests for _get_header_emoji."""

    def test_no_tags_returns_camera(self, notification_service):
        """Test empty/None tags returns camera emoji."""
        assert notification_service._get_header_emoji(None) == "\U0001f4f8"
        assert notification_service._get_header_emoji([]) == "\U0001f4f8"

    def test_meme_tag_returns_laughing(self, notification_service):
        """Test meme-related tags return laughing emoji."""
        assert notification_service._get_header_emoji(["meme"]) == "\U0001f602"
        assert notification_service._get_header_emoji(["funny"]) == "\U0001f602"
        assert notification_service._get_header_emoji(["humor"]) == "\U0001f602"

    def test_product_tag_returns_shopping(self, notification_service):
        """Test product-related tags return shopping emoji."""
        assert notification_service._get_header_emoji(["product"]) == "\U0001f6cd\ufe0f"
        assert notification_service._get_header_emoji(["shop"]) == "\U0001f6cd\ufe0f"
        assert notification_service._get_header_emoji(["sale"]) == "\U0001f6cd\ufe0f"

    def test_quote_tag_returns_sparkle(self, notification_service):
        """Test quote-related tags return sparkle emoji."""
        assert notification_service._get_header_emoji(["quote"]) == "\u2728"
        assert notification_service._get_header_emoji(["inspiration"]) == "\u2728"

    def test_announcement_tag_returns_megaphone(self, notification_service):
        """Test announcement-related tags return megaphone emoji."""
        assert notification_service._get_header_emoji(["news"]) == "\U0001f4e2"
        assert notification_service._get_header_emoji(["announcement"]) == "\U0001f4e2"

    def test_question_tag_returns_speech_bubble(self, notification_service):
        """Test question-related tags return speech bubble emoji."""
        assert notification_service._get_header_emoji(["poll"]) == "\U0001f4ac"
        assert notification_service._get_header_emoji(["question"]) == "\U0001f4ac"

    def test_unknown_tag_returns_camera(self, notification_service):
        """Test unknown tags return default camera emoji."""
        assert notification_service._get_header_emoji(["random"]) == "\U0001f4f8"
        assert notification_service._get_header_emoji(["unknown"]) == "\U0001f4f8"

    def test_case_insensitive(self, notification_service):
        """Test tag matching is case-insensitive."""
        assert notification_service._get_header_emoji(["MEME"]) == "\U0001f602"
        assert notification_service._get_header_emoji(["Product"]) == "\U0001f6cd\ufe0f"


@pytest.mark.unit
class TestBuildKeyboard:
    """Tests for _build_keyboard."""

    def test_includes_autopost_when_api_enabled(self, notification_service):
        """Test keyboard includes Auto Post button when Instagram API is on."""
        queue_id = str(uuid4())
        chat_settings = Mock(enable_instagram_api=True)
        active_account = Mock(display_name="Test Account")

        result = notification_service._build_keyboard(
            queue_id, chat_settings, active_account
        )

        # Extract all button texts
        buttons = []
        for row in result.inline_keyboard:
            for button in row:
                buttons.append(button.text)

        assert any("Auto Post" in b for b in buttons)

    def test_excludes_autopost_when_api_disabled(self, notification_service):
        """Test keyboard excludes Auto Post button when Instagram API is off."""
        queue_id = str(uuid4())
        chat_settings = Mock(enable_instagram_api=False)
        active_account = Mock(display_name="Test Account")

        result = notification_service._build_keyboard(
            queue_id, chat_settings, active_account
        )

        # Extract all button texts
        buttons = []
        for row in result.inline_keyboard:
            for button in row:
                buttons.append(button.text)

        assert not any("Auto Post" in b for b in buttons)

    def test_includes_posted_skip_reject_buttons(self, notification_service):
        """Test keyboard always includes Posted, Skip, and Reject buttons."""
        queue_id = str(uuid4())
        chat_settings = Mock(enable_instagram_api=False)
        active_account = None

        result = notification_service._build_keyboard(
            queue_id, chat_settings, active_account
        )

        buttons = []
        for row in result.inline_keyboard:
            for button in row:
                buttons.append(button.text)

        assert any("Posted" in b for b in buttons)
        assert any("Skip" in b for b in buttons)
        assert any("Reject" in b for b in buttons)

    def test_shows_account_display_name(self, notification_service):
        """Test account selector button shows display name."""
        queue_id = str(uuid4())
        chat_settings = Mock(enable_instagram_api=False)
        active_account = Mock(display_name="My Brand")

        result = notification_service._build_keyboard(
            queue_id, chat_settings, active_account
        )

        buttons = []
        for row in result.inline_keyboard:
            for button in row:
                buttons.append(button.text)

        assert any("My Brand" in b for b in buttons)

    def test_shows_no_account_when_none(self, notification_service):
        """Test account selector shows 'No Account' when none configured."""
        queue_id = str(uuid4())
        chat_settings = Mock(enable_instagram_api=False)
        active_account = None

        result = notification_service._build_keyboard(
            queue_id, chat_settings, active_account
        )

        buttons = []
        for row in result.inline_keyboard:
            for button in row:
                buttons.append(button.text)

        assert any("No Account" in b for b in buttons)

    def test_includes_open_instagram_link(self, notification_service):
        """Test keyboard includes Open Instagram button with URL."""
        queue_id = str(uuid4())
        chat_settings = Mock(enable_instagram_api=False)
        active_account = None

        result = notification_service._build_keyboard(
            queue_id, chat_settings, active_account
        )

        # Find the Open Instagram button
        for row in result.inline_keyboard:
            for button in row:
                if "Instagram" in button.text:
                    assert button.url == "https://www.instagram.com/"
                    return

        pytest.fail("Open Instagram button not found")


@pytest.mark.unit
class TestExtractButtonLabels:
    """Tests for _extract_button_labels helper."""

    def test_extracts_labels(self):
        """Test extracting button labels from markup."""
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Button 1", callback_data="a"),
                    InlineKeyboardButton("Button 2", callback_data="b"),
                ],
                [InlineKeyboardButton("Button 3", callback_data="c")],
            ]
        )

        labels = _extract_button_labels(markup)

        assert labels == ["Button 1", "Button 2", "Button 3"]

    def test_returns_empty_for_none(self):
        """Test returns empty list for None markup."""
        assert _extract_button_labels(None) == []

    def test_returns_empty_for_no_keyboard(self):
        """Test returns empty list for object without inline_keyboard."""
        assert _extract_button_labels(Mock(spec=[])) == []


@pytest.mark.unit
@pytest.mark.asyncio
class TestSendNotification:
    """Tests for send_notification."""

    async def test_returns_false_when_queue_item_not_found(
        self, notification_service, mock_telegram_service
    ):
        """Test send_notification returns False when queue item doesn't exist."""
        mock_telegram_service.queue_repo.get_by_id.return_value = None

        result = await notification_service.send_notification("nonexistent-id")

        assert result is False

    async def test_returns_false_when_media_item_not_found(
        self, notification_service, mock_telegram_service
    ):
        """Test send_notification returns False when media item doesn't exist."""
        queue_item = Mock(media_item_id=uuid4())
        mock_telegram_service.queue_repo.get_by_id.return_value = queue_item
        mock_telegram_service.media_repo.get_by_id.return_value = None

        result = await notification_service.send_notification("some-id")

        assert result is False

    async def test_initializes_bot_if_none(
        self, notification_service, mock_telegram_service
    ):
        """Test bot is initialized if not already set."""
        mock_telegram_service.bot = None
        mock_telegram_service.queue_repo.get_by_id.return_value = None

        with patch("telegram.Bot") as mock_bot_class:
            mock_bot_class.return_value = Mock()
            await notification_service.send_notification("some-id")

        # Bot should have been created (even though queue item not found)
        mock_bot_class.assert_called_once_with(token=mock_telegram_service.bot_token)

    async def test_sends_photo_on_success(
        self, notification_service, mock_telegram_service
    ):
        """Test successful notification sends photo to channel."""
        queue_item_id = str(uuid4())
        queue_item = Mock(media_item_id=uuid4())
        media_item = Mock(
            file_name="test.jpg",
            title="Test",
            caption=None,
            link_url=None,
            tags=[],
            source_identifier="test.jpg",
        )

        mock_telegram_service.queue_repo.get_by_id.return_value = queue_item
        mock_telegram_service.media_repo.get_by_id.return_value = media_item
        mock_telegram_service.settings_service.get_settings.return_value = Mock(
            enable_instagram_api=False,
            show_verbose_notifications=True,
        )
        mock_telegram_service._is_verbose.return_value = True
        mock_telegram_service.ig_account_service.get_active_account.return_value = None

        # Mock the send_photo to return a message with message_id
        mock_message = Mock(message_id=12345)
        mock_telegram_service.bot.send_photo = AsyncMock(return_value=mock_message)

        # Mock MediaSourceFactory
        mock_provider = Mock()
        mock_provider.download_file.return_value = b"fake-image-bytes"

        with patch(
            "src.services.media_sources.factory.MediaSourceFactory"
        ) as mock_factory:
            mock_factory.get_provider_for_media_item.return_value = mock_provider

            with patch(
                "src.services.core.telegram_notification.settings"
            ) as mock_settings:
                mock_settings.CAPTION_STYLE = "enhanced"
                result = await notification_service.send_notification(queue_item_id)

        assert result is True
        mock_telegram_service.bot.send_photo.assert_called_once()

    async def test_returns_false_on_send_error(
        self, notification_service, mock_telegram_service
    ):
        """Test returns False when sending fails."""
        queue_item = Mock(media_item_id=uuid4())
        media_item = Mock(
            file_name="test.jpg",
            title="Test",
            caption=None,
            link_url=None,
            tags=[],
            source_identifier="test.jpg",
        )

        mock_telegram_service.queue_repo.get_by_id.return_value = queue_item
        mock_telegram_service.media_repo.get_by_id.return_value = media_item
        mock_telegram_service.settings_service.get_settings.return_value = Mock(
            enable_instagram_api=False,
            show_verbose_notifications=True,
        )
        mock_telegram_service._is_verbose.return_value = True
        mock_telegram_service.ig_account_service.get_active_account.return_value = None

        # Mock provider to raise an error
        mock_provider = Mock()
        mock_provider.download_file.side_effect = Exception("Download failed")

        with patch(
            "src.services.media_sources.factory.MediaSourceFactory"
        ) as mock_factory:
            mock_factory.get_provider_for_media_item.return_value = mock_provider

            with patch(
                "src.services.core.telegram_notification.settings"
            ) as mock_settings:
                mock_settings.CAPTION_STYLE = "enhanced"
                result = await notification_service.send_notification("some-id")

        assert result is False
