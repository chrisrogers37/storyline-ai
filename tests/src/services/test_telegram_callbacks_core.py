"""Tests for TelegramCallbackCore — shared utilities and DB operations."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch, MagicMock

import pytest

from src.repositories.history_repository import HistoryCreateParams
from src.services.core.telegram_callbacks_core import TelegramCallbackCore
from tests.src.services.conftest import noop_context_manager  # noqa: E402


@pytest.fixture
def mock_service():
    """Build a minimal TelegramService mock with the dependencies Core needs."""
    service = Mock()

    # Repos
    service.history_repo = Mock()
    service.history_repo.db = MagicMock()
    service.history_repo._db = MagicMock()
    service.media_repo = Mock()
    service.media_repo._db = MagicMock()
    service.queue_repo = Mock()
    service.queue_repo._db = MagicMock()
    service.user_repo = Mock()
    service.user_repo._db = MagicMock()
    service.lock_service = Mock()
    service.lock_service.lock_repo = Mock()
    service.lock_service.lock_repo._db = MagicMock()

    # Operation lock (real asyncio.Lock by default)
    service.get_operation_lock.return_value = asyncio.Lock()
    service.cleanup_operation_state = Mock()

    return service


@pytest.fixture
def core(mock_service):
    """Create a TelegramCallbackCore with mocked service."""
    return TelegramCallbackCore(mock_service)


# ──────────────────────────────────────────────────────────────
# _safe_locked_callback
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
class TestSafeLockedCallback:
    async def test_runs_coroutine_under_lock(self, core):
        """Happy path: coroutine runs, keyboard removed, state cleaned up."""
        query = AsyncMock()
        ran = False

        async def work():
            nonlocal ran
            ran = True

        await core._safe_locked_callback("q-1", query, "test_cb", "err msg", work())

        assert ran
        query.edit_message_reply_markup.assert_called_once()
        core.service.cleanup_operation_state.assert_called_once_with("q-1")

    async def test_already_locked_answers_and_skips(self, core):
        """If the lock is already held, answer with a warning and skip."""
        lock = asyncio.Lock()
        await lock.acquire()  # pre-lock
        core.service.get_operation_lock.return_value = lock

        query = AsyncMock()
        ran = False

        async def work():
            nonlocal ran
            ran = True

        await core._safe_locked_callback("q-1", query, "test_cb", "err msg", work())

        assert not ran
        query.answer.assert_called_once()
        assert "Already processing" in query.answer.call_args[0][0]
        lock.release()

    @patch("src.services.core.telegram_callbacks_core.telegram_edit_with_retry")
    async def test_callback_error_shows_error_message(self, mock_retry, core):
        """If the coroutine raises, show the error caption and clean up."""
        query = AsyncMock()

        async def failing():
            raise RuntimeError("boom")

        await core._safe_locked_callback(
            "q-1", query, "test_cb", "something went wrong", failing()
        )

        mock_retry.assert_called_once()
        assert mock_retry.call_args[1]["caption"] == "something went wrong"
        core.service.cleanup_operation_state.assert_called_once_with("q-1")

    async def test_keyboard_removal_failure_does_not_block(self, core):
        """If removing the keyboard fails, the callback still runs."""
        query = AsyncMock()
        query.edit_message_reply_markup.side_effect = Exception("Telegram hiccup")

        ran = False

        async def work():
            nonlocal ran
            ran = True

        await core._safe_locked_callback("q-1", query, "test_cb", "err msg", work())

        assert ran


# ──────────────────────────────────────────────────────────────
# _shared_session
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestSharedSession:
    def test_commits_on_success(self, core):
        """All repos share one session; real commit called at the end."""
        primary = core.service.history_repo.db
        original_commit = Mock()
        primary.commit = original_commit

        with core._shared_session():
            pass  # no-op body

        original_commit.assert_called_once()

    def test_rollback_on_exception(self, core):
        """On any exception, rollback is called and the error re-raised."""
        primary = core.service.history_repo.db
        original_commit = Mock()
        primary.commit = original_commit

        with pytest.raises(ValueError):
            with core._shared_session():
                raise ValueError("db problem")

        primary.rollback.assert_called_once()
        original_commit.assert_not_called()

    def test_sessions_restored_after_success(self, core):
        """After the context manager exits, each repo gets its original session back."""
        repos = [
            core.service.history_repo,
            core.service.media_repo,
            core.service.queue_repo,
            core.service.user_repo,
            core.service.lock_service.lock_repo,
        ]
        originals = [r._db for r in repos]

        with core._shared_session():
            pass

        for repo, orig in zip(repos, originals):
            repo.use_session.assert_called()
            last_call = repo.use_session.call_args_list[-1]
            assert last_call[0][0] is orig

    def test_sessions_restored_after_failure(self, core):
        """Sessions are restored even on failure."""
        repos = [
            core.service.history_repo,
            core.service.media_repo,
            core.service.queue_repo,
            core.service.user_repo,
            core.service.lock_service.lock_repo,
        ]
        originals = [r._db for r in repos]

        with pytest.raises(RuntimeError):
            with core._shared_session():
                raise RuntimeError("kaboom")

        for repo, orig in zip(repos, originals):
            last_call = repo.use_session.call_args_list[-1]
            assert last_call[0][0] is orig


# ──────────────────────────────────────────────────────────────
# _create_history_params
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestCreateHistoryParams:
    def test_builds_correct_params(self, core):
        """Returns HistoryCreateParams with all fields populated."""
        queue_item = Mock(
            media_item_id="media-1",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            scheduled_for=datetime(2026, 1, 2, tzinfo=timezone.utc),
            chat_settings_id="cs-1",
        )
        user = Mock(id="user-1", telegram_username="test_user")

        result = core._create_history_params("q-1", queue_item, user, "posted", True)

        assert isinstance(result, HistoryCreateParams)
        assert result.media_item_id == "media-1"
        assert result.queue_item_id == "q-1"
        assert result.status == "posted"
        assert result.success is True
        assert result.posted_by_user_id == "user-1"
        assert result.posted_by_telegram_username == "test_user"
        assert result.chat_settings_id == "cs-1"

    def test_none_chat_settings_id(self, core):
        """chat_settings_id is None when queue_item has no chat_settings_id."""
        queue_item = Mock(
            media_item_id="media-1",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            scheduled_for=datetime(2026, 1, 2, tzinfo=timezone.utc),
            chat_settings_id=None,
        )
        user = Mock(id="user-1", telegram_username="test_user")

        result = core._create_history_params("q-1", queue_item, user, "skipped", False)

        assert result.chat_settings_id is None


# ──────────────────────────────────────────────────────────────
# _execute_complete_db_ops
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestExecuteCompleteDbOps:
    def _setup_shared_session(self, core):
        """Replace _shared_session with a pass-through context manager."""
        core._shared_session = noop_context_manager

    def test_posted_increments_and_locks(self, core):
        """For 'posted' status: increment posts, create lock, increment user."""
        self._setup_shared_session(core)
        media_item = Mock()
        core.service.media_repo.get_by_id.return_value = media_item

        queue_item = Mock(
            media_item_id="media-1",
            telegram_chat_id=-100123,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            scheduled_for=datetime(2026, 1, 2, tzinfo=timezone.utc),
            chat_settings_id="cs-1",
        )
        user = Mock(id="user-1", telegram_username="u")

        result = core._execute_complete_db_ops("q-1", queue_item, user, "posted", True)

        assert result is media_item
        core.service.history_repo.create.assert_called_once()
        core.service.media_repo.increment_times_posted.assert_called_once_with(
            "media-1"
        )
        # Lock now passes chat_id so MediaLockService can look up the per-chat TTL
        core.service.lock_service.create_lock.assert_called_once_with(
            "media-1", telegram_chat_id=-100123
        )
        core.service.user_repo.increment_posts.assert_called_once_with("user-1")
        core.service.queue_repo.delete.assert_called_once_with("q-1")

    def test_skipped_creates_skip_lock(self, core):
        """For 'skipped' status: create skip lock, no post increment.

        TTL is resolved server-side from chat_settings.skip_ttl_days (per-chat)
        with REPOST/SKIP env defaults as fallback, so the caller no longer
        passes ttl_days directly — it just identifies the chat.
        """
        self._setup_shared_session(core)
        media_item = Mock()
        core.service.media_repo.get_by_id.return_value = media_item

        queue_item = Mock(
            media_item_id="media-1",
            telegram_chat_id=-100123,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            scheduled_for=datetime(2026, 1, 2, tzinfo=timezone.utc),
            chat_settings_id="cs-1",
        )
        user = Mock(id="user-1", telegram_username="u")

        core._execute_complete_db_ops("q-1", queue_item, user, "skipped", False)

        core.service.lock_service.create_lock.assert_called_once_with(
            "media-1", lock_reason="skip", telegram_chat_id=-100123
        )
        core.service.media_repo.increment_times_posted.assert_not_called()
        core.service.user_repo.increment_posts.assert_not_called()


# ──────────────────────────────────────────────────────────────
# _execute_reject_db_ops
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestExecuteRejectDbOps:
    def test_creates_permanent_lock_and_deletes_queue(self, core):
        """Rejection: history created, permanent lock, queue item deleted."""
        core._shared_session = noop_context_manager

        media_item = Mock()
        core.service.media_repo.get_by_id.return_value = media_item

        queue_item = Mock(
            media_item_id="media-1",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            scheduled_for=datetime(2026, 1, 2, tzinfo=timezone.utc),
            chat_settings_id="cs-1",
        )
        user = Mock(id="user-1", telegram_username="u")

        result = core._execute_reject_db_ops("q-1", queue_item, user)

        assert result is media_item
        core.service.history_repo.create.assert_called_once()
        core.service.lock_service.create_permanent_lock.assert_called_once_with(
            "media-1", created_by_user_id="user-1"
        )
        core.service.queue_repo.delete.assert_called_once_with("q-1")


# ──────────────────────────────────────────────────────────────
# _refresh_repo_sessions
# ──────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestRefreshRepoSessions:
    def test_calls_end_read_transaction_on_all_repos(self, core):
        """All repos and lock_repo have their sessions refreshed."""
        core._refresh_repo_sessions()

        core.service.history_repo.end_read_transaction.assert_called_once()
        core.service.media_repo.end_read_transaction.assert_called_once()
        core.service.queue_repo.end_read_transaction.assert_called_once()
        core.service.user_repo.end_read_transaction.assert_called_once()
        core.service.lock_service.lock_repo.end_read_transaction.assert_called_once()
