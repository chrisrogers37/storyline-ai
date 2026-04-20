"""Shared fixtures for service-layer tests."""

import pytest
from contextlib import contextmanager
from unittest.mock import AsyncMock, Mock, patch

from src.services.core.start_command_router import StartCommandRouter  # noqa: F401
from src.services.core.telegram_service import TelegramService


def make_query(chat_id=-100123):
    """Build a mock Telegram CallbackQuery."""
    query = AsyncMock()
    query.message = Mock()
    query.message.chat_id = chat_id
    query.message.message_id = 42
    return query


def make_user(user_id="user-1"):
    """Build a mock Telegram user."""
    return Mock(id=user_id)


@contextmanager
def noop_context_manager():
    """Pass-through context manager for replacing service context managers in tests."""
    yield


@contextmanager
def mock_track_execution(*args, **kwargs):
    """Mock context manager for BaseService.track_execution.

    Yields a fake run_id. Use by assigning to ``service.track_execution``
    after bypassing ``__init__`` with ``patch.object``.
    """
    yield "mock_run_id"


@pytest.fixture
def mock_telegram_service():
    """Create a TelegramService with all 10 dependencies mocked.

    Yields the service instance. Individual test files create their
    handler from this service, e.g.::

        @pytest.fixture
        def mock_callback_handlers(mock_telegram_service):
            return TelegramCallbackHandlers(mock_telegram_service)

    The service has all repos/services as Mock instances for assertion.
    """
    with (
        patch("src.services.core.telegram_service.settings") as mock_settings,
        patch(
            "src.services.core.telegram_service.UserRepository"
        ) as mock_user_repo_class,
        patch(
            "src.services.core.telegram_service.QueueRepository"
        ) as mock_queue_repo_class,
        patch(
            "src.services.core.telegram_service.MediaRepository"
        ) as mock_media_repo_class,
        patch(
            "src.services.core.telegram_service.HistoryRepository"
        ) as mock_history_repo_class,
        patch(
            "src.services.core.telegram_service.LockRepository"
        ) as mock_lock_repo_class,
        patch(
            "src.services.core.telegram_service.MediaLockService"
        ) as mock_lock_service_class,
        patch(
            "src.services.core.telegram_service.InteractionService"
        ) as mock_interaction_service_class,
        patch(
            "src.services.core.telegram_service.SettingsService"
        ) as mock_settings_service_class,
        patch(
            "src.services.core.telegram_service.InstagramAccountService"
        ) as mock_ig_account_service_class,
        patch(
            "src.services.core.telegram_service.MembershipRepository"
        ) as mock_membership_repo_class,
    ):
        mock_settings.TELEGRAM_BOT_TOKEN = "123456:ABC-DEF1234ghIkl"
        mock_settings.TELEGRAM_CHANNEL_ID = -1001234567890
        mock_settings.CAPTION_STYLE = "enhanced"
        mock_settings.SEND_LIFECYCLE_NOTIFICATIONS = False

        service = TelegramService()

        # Make repos/services accessible for test assertions
        service.user_repo = mock_user_repo_class.return_value
        service.queue_repo = mock_queue_repo_class.return_value
        service.media_repo = mock_media_repo_class.return_value
        service.history_repo = mock_history_repo_class.return_value
        service.lock_repo = mock_lock_repo_class.return_value
        service.lock_service = mock_lock_service_class.return_value
        service.interaction_service = mock_interaction_service_class.return_value
        service.settings_service = mock_settings_service_class.return_value
        service.ig_account_service = mock_ig_account_service_class.return_value
        service.ig_account_service.count_active_accounts.return_value = 1
        service.membership_repo = mock_membership_repo_class.return_value
        service.start_router = StartCommandRouter(service)

        yield service
