"""Tests for the per-tenant scheduler, media sync loops, and _guarded() in main.py."""

import asyncio

import pytest
from unittest.mock import AsyncMock, Mock, patch

from src.main import (
    _guarded,
    get_loop_liveness,
    loop_heartbeats,
    record_heartbeat,
    run_scheduler_loop,
    media_sync_loop,
)


@pytest.mark.unit
class TestSchedulerLoop:
    """Tests for run_scheduler_loop JIT multi-tenant behavior."""

    @pytest.mark.asyncio
    async def test_scheduler_loop_iterates_over_active_chats(self):
        """Scheduler loop calls process_slot for each active chat."""
        scheduler_service = Mock()
        scheduler_service.process_slot = AsyncMock(return_value={"posted": False})
        scheduler_service.cleanup_transactions = Mock()

        posting_service = Mock()
        posting_service.cleanup_transactions = Mock()

        chat1 = Mock(telegram_chat_id=-100111)
        chat2 = Mock(telegram_chat_id=-100222)
        settings_service = Mock()
        settings_service.get_all_active_chats.return_value = [chat1, chat2]

        with (
            patch("src.main.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch("src.main.QueueRepository") as mock_queue_repo_cls,
            patch("src.main.ServiceRunRepository"),
        ):
            mock_queue_repo_cls.return_value.discard_abandoned_processing.return_value = 0
            mock_sleep.side_effect = StopAsyncIteration
            try:
                await run_scheduler_loop(
                    scheduler_service, posting_service, settings_service
                )
            except StopAsyncIteration:
                pass

        # Should have called process_slot for each chat
        assert scheduler_service.process_slot.call_count == 2
        scheduler_service.process_slot.assert_any_call(telegram_chat_id=-100111)
        scheduler_service.process_slot.assert_any_call(telegram_chat_id=-100222)

    @pytest.mark.asyncio
    async def test_scheduler_loop_no_calls_when_no_tenants(self):
        """Scheduler loop does nothing when no active chats exist."""
        scheduler_service = Mock()
        scheduler_service.process_slot = AsyncMock()
        scheduler_service.cleanup_transactions = Mock()

        posting_service = Mock()
        posting_service.cleanup_transactions = Mock()

        settings_service = Mock()
        settings_service.get_all_active_chats.return_value = []

        with (
            patch("src.main.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch("src.main.QueueRepository") as mock_queue_repo_cls,
            patch("src.main.ServiceRunRepository"),
        ):
            mock_queue_repo_cls.return_value.discard_abandoned_processing.return_value = 0
            mock_sleep.side_effect = StopAsyncIteration
            try:
                await run_scheduler_loop(
                    scheduler_service, posting_service, settings_service
                )
            except StopAsyncIteration:
                pass

        # No active chats means no process_slot calls
        scheduler_service.process_slot.assert_not_called()

    @pytest.mark.asyncio
    async def test_scheduler_loop_no_calls_when_no_settings_service(self):
        """Scheduler loop does nothing when settings_service is None."""
        scheduler_service = Mock()
        scheduler_service.process_slot = AsyncMock()
        scheduler_service.cleanup_transactions = Mock()

        posting_service = Mock()
        posting_service.cleanup_transactions = Mock()

        with (
            patch("src.main.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch("src.main.QueueRepository") as mock_queue_repo_cls,
            patch("src.main.ServiceRunRepository"),
        ):
            mock_queue_repo_cls.return_value.discard_abandoned_processing.return_value = 0
            mock_sleep.side_effect = StopAsyncIteration
            try:
                await run_scheduler_loop(scheduler_service, posting_service, None)
            except StopAsyncIteration:
                pass

        # No settings_service means no process_slot calls
        scheduler_service.process_slot.assert_not_called()

    @pytest.mark.asyncio
    async def test_scheduler_loop_skips_failed_tenant(self):
        """One tenant's error does not prevent other tenants from processing."""
        scheduler_service = Mock()
        scheduler_service.process_slot = AsyncMock(
            side_effect=[
                Exception("Chat 1 failed"),
                {"posted": False},
            ]
        )
        scheduler_service.cleanup_transactions = Mock()

        posting_service = Mock()
        posting_service.cleanup_transactions = Mock()

        chat1 = Mock(telegram_chat_id=-100111)
        chat2 = Mock(telegram_chat_id=-100222)
        settings_service = Mock()
        settings_service.get_all_active_chats.return_value = [chat1, chat2]

        with (
            patch("src.main.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch("src.main.QueueRepository") as mock_queue_repo_cls,
            patch("src.main.ServiceRunRepository"),
        ):
            mock_queue_repo_cls.return_value.discard_abandoned_processing.return_value = 0
            mock_sleep.side_effect = StopAsyncIteration
            try:
                await run_scheduler_loop(
                    scheduler_service, posting_service, settings_service
                )
            except StopAsyncIteration:
                pass

        # Both chats should have been attempted despite chat1 failing
        assert scheduler_service.process_slot.call_count == 2

    @pytest.mark.asyncio
    async def test_scheduler_loop_handles_gdrive_auth_error(self):
        """GoogleDriveAuthError triggers send_gdrive_auth_alert for that chat."""
        from src.exceptions.google_drive import GoogleDriveAuthError

        scheduler_service = Mock()
        scheduler_service.process_slot = AsyncMock(
            side_effect=[
                GoogleDriveAuthError("Token expired"),
                {"posted": False},
            ]
        )
        scheduler_service.cleanup_transactions = Mock()

        posting_service = Mock()
        posting_service.send_gdrive_auth_alert = AsyncMock()
        posting_service.cleanup_transactions = Mock()

        chat1 = Mock(telegram_chat_id=-100111)
        chat2 = Mock(telegram_chat_id=-100222)
        settings_service = Mock()
        settings_service.get_all_active_chats.return_value = [chat1, chat2]

        with (
            patch("src.main.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch("src.main.QueueRepository") as mock_queue_repo_cls,
            patch("src.main.ServiceRunRepository"),
        ):
            mock_queue_repo_cls.return_value.discard_abandoned_processing.return_value = 0
            mock_sleep.side_effect = StopAsyncIteration
            try:
                await run_scheduler_loop(
                    scheduler_service, posting_service, settings_service
                )
            except StopAsyncIteration:
                pass

        # Alert should be sent for chat1's GDrive auth failure
        posting_service.send_gdrive_auth_alert.assert_called_once_with(-100111)
        # Chat2 should still have been processed
        assert scheduler_service.process_slot.call_count == 2

    @pytest.mark.asyncio
    async def test_scheduler_loop_cleans_up_both_services(self):
        """Both scheduler_service and posting_service get cleanup_transactions called."""
        scheduler_service = Mock()
        scheduler_service.process_slot = AsyncMock(return_value={"posted": False})
        scheduler_service.cleanup_transactions = Mock()

        posting_service = Mock()
        posting_service.cleanup_transactions = Mock()

        settings_service = Mock()
        settings_service.get_all_active_chats.return_value = []

        with (
            patch("src.main.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch("src.main.QueueRepository") as mock_queue_repo_cls,
            patch("src.main.ServiceRunRepository"),
        ):
            mock_queue_repo_cls.return_value.discard_abandoned_processing.return_value = 0
            mock_sleep.side_effect = StopAsyncIteration
            try:
                await run_scheduler_loop(
                    scheduler_service, posting_service, settings_service
                )
            except StopAsyncIteration:
                pass

        scheduler_service.cleanup_transactions.assert_called()
        posting_service.cleanup_transactions.assert_called()

    @pytest.mark.asyncio
    async def test_scheduler_loop_increments_session_posts_on_posted(self):
        """Session counter increments when process_slot returns posted=True."""
        import src.main as main_module

        original = main_module.session_posts_sent
        main_module.session_posts_sent = 0

        scheduler_service = Mock()
        scheduler_service.process_slot = AsyncMock(
            return_value={"posted": True, "media_file": "test.jpg", "category": "meme"}
        )
        scheduler_service.cleanup_transactions = Mock()

        posting_service = Mock()
        posting_service.cleanup_transactions = Mock()

        chat1 = Mock(telegram_chat_id=-100111)
        settings_service = Mock()
        settings_service.get_all_active_chats.return_value = [chat1]

        with (
            patch("src.main.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch("src.main.QueueRepository") as mock_queue_repo_cls,
            patch("src.main.ServiceRunRepository"),
        ):
            mock_queue_repo_cls.return_value.discard_abandoned_processing.return_value = 0
            mock_sleep.side_effect = StopAsyncIteration
            try:
                await run_scheduler_loop(
                    scheduler_service, posting_service, settings_service
                )
            except StopAsyncIteration:
                pass

        assert main_module.session_posts_sent == 1
        main_module.session_posts_sent = original

    @pytest.mark.asyncio
    async def test_scheduler_loop_runs_retention_at_interval(self):
        """Service runs retention fires after RETENTION_INTERVAL_TICKS ticks."""
        import src.main as main_module

        scheduler_service = Mock()
        scheduler_service.process_slot = AsyncMock(return_value={"posted": False})
        scheduler_service.cleanup_transactions = Mock()

        posting_service = Mock()
        posting_service.cleanup_transactions = Mock()

        settings_service = Mock()
        settings_service.get_all_active_chats.return_value = []

        tick_count = 0

        async def counting_sleep(seconds):
            nonlocal tick_count
            tick_count += 1
            if tick_count >= main_module.RETENTION_INTERVAL_TICKS:
                raise StopAsyncIteration

        with (
            patch("src.main.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch("src.main.QueueRepository") as mock_queue_repo_cls,
            patch("src.main.ServiceRunRepository") as mock_sr_repo_cls,
        ):
            mock_queue_repo_cls.return_value.discard_abandoned_processing.return_value = 0
            mock_sr_repo = mock_sr_repo_cls.return_value
            mock_sr_repo.delete_older_than.return_value = 5
            mock_sr_repo.end_read_transaction = Mock()
            mock_sleep.side_effect = counting_sleep

            try:
                await run_scheduler_loop(
                    scheduler_service, posting_service, settings_service
                )
            except StopAsyncIteration:
                pass

        mock_sr_repo.delete_older_than.assert_called_once_with(
            main_module.SERVICE_RUNS_RETENTION_DAYS
        )


@pytest.mark.unit
class TestMediaSyncLoop:
    """Tests for media_sync_loop multi-tenant behavior."""

    @pytest.mark.asyncio
    async def test_sync_loop_iterates_sync_enabled_chats(self):
        """Sync loop syncs each tenant with media_sync_enabled=True."""
        sync_service = Mock()
        result = Mock(total_processed=0, errors=0, new=0)
        sync_service.sync.return_value = result
        sync_service.cleanup_transactions = Mock()

        chat1 = Mock(telegram_chat_id=-100111)
        chat2 = Mock(telegram_chat_id=-100222)
        settings_service = Mock()
        settings_service.get_all_sync_enabled_chats.return_value = [chat1, chat2]
        settings_service.cleanup_transactions = Mock()

        with patch("src.main.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_sleep.side_effect = StopAsyncIteration
            try:
                await media_sync_loop(sync_service, settings_service=settings_service)
            except StopAsyncIteration:
                pass

        assert sync_service.sync.call_count == 2
        sync_service.sync.assert_any_call(
            telegram_chat_id=-100111, triggered_by="scheduler"
        )
        sync_service.sync.assert_any_call(
            telegram_chat_id=-100222, triggered_by="scheduler"
        )

    @pytest.mark.asyncio
    async def test_sync_loop_falls_back_when_no_sync_enabled_chats(self):
        """Sync loop uses global env vars when no chats have sync enabled."""
        sync_service = Mock()
        result = Mock(total_processed=0, errors=0, new=0)
        sync_service.sync.return_value = result
        sync_service.cleanup_transactions = Mock()

        settings_service = Mock()
        settings_service.get_all_sync_enabled_chats.return_value = []
        settings_service.cleanup_transactions = Mock()

        with patch("src.main.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_sleep.side_effect = StopAsyncIteration
            try:
                await media_sync_loop(sync_service, settings_service=settings_service)
            except StopAsyncIteration:
                pass

        # Should fall back to global (no telegram_chat_id)
        sync_service.sync.assert_called_once_with(triggered_by="scheduler")

    @pytest.mark.asyncio
    async def test_sync_loop_falls_back_when_no_settings_service(self):
        """Sync loop uses global env vars when settings_service is None."""
        sync_service = Mock()
        result = Mock(total_processed=0, errors=0, new=0)
        sync_service.sync.return_value = result
        sync_service.cleanup_transactions = Mock()

        with patch("src.main.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_sleep.side_effect = StopAsyncIteration
            try:
                await media_sync_loop(sync_service)
            except StopAsyncIteration:
                pass

        sync_service.sync.assert_called_once_with(triggered_by="scheduler")

    @pytest.mark.asyncio
    async def test_sync_loop_skips_failed_tenant(self):
        """One tenant's sync error does not block other tenants."""
        sync_service = Mock()
        result_ok = Mock(total_processed=0, errors=0, new=0)
        sync_service.sync.side_effect = [
            Exception("Chat 1 failed"),
            result_ok,
        ]
        sync_service.cleanup_transactions = Mock()

        chat1 = Mock(telegram_chat_id=-100111)
        chat2 = Mock(telegram_chat_id=-100222)
        settings_service = Mock()
        settings_service.get_all_sync_enabled_chats.return_value = [chat1, chat2]
        settings_service.cleanup_transactions = Mock()

        with patch("src.main.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_sleep.side_effect = StopAsyncIteration
            try:
                await media_sync_loop(sync_service, settings_service=settings_service)
            except StopAsyncIteration:
                pass

        # Both should have been attempted
        assert sync_service.sync.call_count == 2


@pytest.mark.unit
class TestGuarded:
    """Tests for _guarded() crash handling and Telegram alerts."""

    @pytest.mark.asyncio
    async def test_logs_critical_on_crash(self):
        """Crashed coroutine is logged at CRITICAL level, not propagated."""

        async def crashing_coro():
            raise RuntimeError("boom")

        with patch("src.main.logger") as mock_logger:
            await _guarded("test_task", crashing_coro())

        mock_logger.critical.assert_called_once()
        assert "test_task" in mock_logger.critical.call_args[0][0]

    @pytest.mark.asyncio
    async def test_sends_telegram_alert_on_crash(self):
        """When bot is provided, sends crash alert to admin chat."""
        mock_bot = AsyncMock()

        async def crashing_coro():
            raise ValueError("something broke")

        with patch("src.main.settings") as mock_settings:
            mock_settings.ADMIN_TELEGRAM_CHAT_ID = -100999
            await _guarded("scheduler", crashing_coro(), bot=mock_bot)

        mock_bot.send_message.assert_called_once()
        call_kwargs = mock_bot.send_message.call_args.kwargs
        assert call_kwargs["chat_id"] == -100999
        assert "scheduler" in call_kwargs["text"]
        assert "something broke" in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_no_alert_when_bot_is_none(self):
        """When no bot provided, only logs — no Telegram alert."""

        async def crashing_coro():
            raise RuntimeError("boom")

        with patch("src.main.logger"):
            # Should not raise — just logs
            await _guarded("test_task", crashing_coro(), bot=None)

    @pytest.mark.asyncio
    async def test_alert_failure_does_not_mask_crash_log(self):
        """If Telegram alert fails, the original crash is still logged."""
        mock_bot = AsyncMock()
        mock_bot.send_message.side_effect = Exception("Telegram down")

        async def crashing_coro():
            raise RuntimeError("original error")

        with (
            patch("src.main.logger") as mock_logger,
            patch("src.main.settings") as mock_settings,
        ):
            mock_settings.ADMIN_TELEGRAM_CHAT_ID = -100999
            await _guarded("scheduler", crashing_coro(), bot=mock_bot)

        # Original crash still logged at CRITICAL
        mock_logger.critical.assert_called_once()
        assert "scheduler" in mock_logger.critical.call_args[0][0]
        # Alert failure logged at ERROR
        mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancelled_error_propagates(self):
        """CancelledError should propagate (for clean shutdown)."""

        async def cancelled_coro():
            raise asyncio.CancelledError()

        with pytest.raises(asyncio.CancelledError):
            await _guarded("test_task", cancelled_coro(), bot=AsyncMock())


@pytest.mark.unit
class TestLoopLiveness:
    """Tests for loop heartbeat tracking and liveness detection."""

    def setup_method(self):
        """Clear heartbeats before each test."""
        loop_heartbeats.clear()

    def test_record_heartbeat_stores_timestamp(self):
        """record_heartbeat() stores a float timestamp."""
        record_heartbeat("scheduler")
        assert "scheduler" in loop_heartbeats
        assert isinstance(loop_heartbeats["scheduler"], float)

    def test_unstarted_loop_reported_as_not_alive(self):
        """Loops that never sent a heartbeat are reported as not started."""
        result = get_loop_liveness()
        assert "scheduler" in result
        assert result["scheduler"]["alive"] is False
        assert "Not started" in result["scheduler"]["message"]

    def test_fresh_heartbeat_reported_as_alive(self):
        """A loop with a recent heartbeat is reported as alive."""
        record_heartbeat("scheduler")
        result = get_loop_liveness()
        assert result["scheduler"]["alive"] is True
        assert result["scheduler"]["message"] == "OK"

    def test_stale_heartbeat_reported_as_not_alive(self):
        """A loop whose heartbeat is older than 2x its interval is stale."""
        from time import time

        # Set heartbeat to 200s ago (scheduler interval is 60s, threshold 120s)
        loop_heartbeats["scheduler"] = time() - 200
        result = get_loop_liveness()
        assert result["scheduler"]["alive"] is False
        assert "Stale" in result["scheduler"]["message"]

    def test_all_registered_loops_included(self):
        """get_loop_liveness() reports on all registered loops."""
        result = get_loop_liveness()
        expected = {
            "scheduler",
            "lock_cleanup",
            "cloud_cleanup",
            "media_sync",
            "transaction_cleanup",
        }
        assert set(result.keys()) == expected
