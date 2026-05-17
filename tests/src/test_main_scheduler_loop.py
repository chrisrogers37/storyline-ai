"""Tests for the per-tenant scheduler, media sync loops, _guarded(), and heartbeat."""

import asyncio

import pytest
from unittest.mock import AsyncMock, Mock, patch

from src.services.core.loops.guarded import (
    guarded,
    _INITIAL_BACKOFF_SECONDS,
    _MAX_BACKOFF_SECONDS,
)
from src.services.core.loops.heartbeat import (
    get_loop_liveness,
    loop_heartbeats,
    record_heartbeat,
)
from src.services.core.loops.scheduler_loop import (
    run_scheduler_loop,
    RETENTION_INTERVAL_TICKS,
    SERVICE_RUNS_RETENTION_DAYS,
)
from src.services.core.loops.media_sync_loop import media_sync_loop

# Module paths for patching
_SCHEDULER = "src.services.core.loops.scheduler_loop"
_GUARDED = "src.services.core.loops.guarded"
_SYNC = "src.services.core.loops.media_sync_loop"


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
            patch(f"{_SCHEDULER}.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch(f"{_SCHEDULER}.QueueRepository") as mock_queue_repo_cls,
            patch(f"{_SCHEDULER}.ServiceRunRepository"),
        ):
            mock_queue_repo_cls.return_value.discard_abandoned_processing.return_value = 0
            mock_sleep.side_effect = StopAsyncIteration
            try:
                await run_scheduler_loop(
                    scheduler_service, posting_service, settings_service
                )
            except StopAsyncIteration:
                pass

        # Should have called process_slot for each chat (first_tick=True on first tick)
        assert scheduler_service.process_slot.call_count == 2
        scheduler_service.process_slot.assert_any_call(
            telegram_chat_id=-100111, first_tick=True
        )
        scheduler_service.process_slot.assert_any_call(
            telegram_chat_id=-100222, first_tick=True
        )

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
            patch(f"{_SCHEDULER}.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch(f"{_SCHEDULER}.QueueRepository") as mock_queue_repo_cls,
            patch(f"{_SCHEDULER}.ServiceRunRepository"),
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
            patch(f"{_SCHEDULER}.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch(f"{_SCHEDULER}.QueueRepository") as mock_queue_repo_cls,
            patch(f"{_SCHEDULER}.ServiceRunRepository"),
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
            patch(f"{_SCHEDULER}.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch(f"{_SCHEDULER}.QueueRepository") as mock_queue_repo_cls,
            patch(f"{_SCHEDULER}.ServiceRunRepository"),
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
            patch(f"{_SCHEDULER}.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch(f"{_SCHEDULER}.QueueRepository") as mock_queue_repo_cls,
            patch(f"{_SCHEDULER}.ServiceRunRepository"),
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
            patch(f"{_SCHEDULER}.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch(f"{_SCHEDULER}.QueueRepository") as mock_queue_repo_cls,
            patch(f"{_SCHEDULER}.ServiceRunRepository"),
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
        from src.services.core.loops.lifecycle import session_state

        original = session_state.posts_sent
        session_state.posts_sent = 0

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
            patch(f"{_SCHEDULER}.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch(f"{_SCHEDULER}.QueueRepository") as mock_queue_repo_cls,
            patch(f"{_SCHEDULER}.ServiceRunRepository"),
        ):
            mock_queue_repo_cls.return_value.discard_abandoned_processing.return_value = 0
            mock_sleep.side_effect = StopAsyncIteration
            try:
                await run_scheduler_loop(
                    scheduler_service, posting_service, settings_service
                )
            except StopAsyncIteration:
                pass

        assert session_state.posts_sent == 1
        session_state.posts_sent = original

    @pytest.mark.asyncio
    async def test_scheduler_loop_runs_retention_at_interval(self):
        """Service runs retention fires after RETENTION_INTERVAL_TICKS ticks."""
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
            if tick_count >= RETENTION_INTERVAL_TICKS:
                raise StopAsyncIteration

        with (
            patch(f"{_SCHEDULER}.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch(f"{_SCHEDULER}.QueueRepository") as mock_queue_repo_cls,
            patch(f"{_SCHEDULER}.ServiceRunRepository") as mock_sr_repo_cls,
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
            SERVICE_RUNS_RETENTION_DAYS
        )

    @pytest.mark.asyncio
    async def test_scheduler_loop_rolls_back_queue_repo_on_discard_error(self):
        """If queue_repo.discard_abandoned_processing raises, the session is
        rolled back so the next tick doesn't PendingRollbackError. This was a
        real production incident: one bad query left the standalone queue_repo
        in a broken transaction and every subsequent tick errored for hours.
        """
        scheduler_service = Mock()
        scheduler_service.process_slot = AsyncMock(return_value={"posted": False})
        scheduler_service.cleanup_transactions = Mock()

        posting_service = Mock()
        posting_service.cleanup_transactions = Mock()

        settings_service = Mock()
        settings_service.get_all_active_chats.return_value = []
        settings_service.cleanup_transactions = Mock()

        with (
            patch(f"{_SCHEDULER}.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch(f"{_SCHEDULER}.QueueRepository") as mock_queue_repo_cls,
            patch(f"{_SCHEDULER}.ServiceRunRepository"),
        ):
            queue_repo = mock_queue_repo_cls.return_value
            queue_repo.discard_abandoned_processing.side_effect = RuntimeError(
                "simulated DB error"
            )
            queue_repo.rollback = Mock()
            mock_sleep.side_effect = StopAsyncIteration

            try:
                await run_scheduler_loop(
                    scheduler_service, posting_service, settings_service
                )
            except StopAsyncIteration:
                pass

        # Session was rolled back so the next tick starts clean.
        queue_repo.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_first_tick_flag_is_true_then_false(self):
        """first_tick=True on first tick, False on subsequent ticks."""
        scheduler_service = Mock()
        scheduler_service.process_slot = AsyncMock(return_value={"posted": False})
        scheduler_service.cleanup_transactions = Mock()

        posting_service = Mock()
        posting_service.cleanup_transactions = Mock()

        chat1 = Mock(telegram_chat_id=-100111)
        settings_service = Mock()
        settings_service.get_all_active_chats.return_value = [chat1]
        settings_service.cleanup_transactions = Mock()

        tick_count = 0

        async def counting_sleep(seconds):
            nonlocal tick_count
            tick_count += 1
            if tick_count >= 2:
                raise StopAsyncIteration

        with (
            patch(f"{_SCHEDULER}.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch(f"{_SCHEDULER}.QueueRepository") as mock_queue_repo_cls,
            patch(f"{_SCHEDULER}.ServiceRunRepository"),
        ):
            mock_queue_repo_cls.return_value.discard_abandoned_processing.return_value = 0
            mock_sleep.side_effect = counting_sleep
            try:
                await run_scheduler_loop(
                    scheduler_service, posting_service, settings_service
                )
            except StopAsyncIteration:
                pass

        # Two ticks = two calls
        assert scheduler_service.process_slot.call_count == 2
        calls = scheduler_service.process_slot.call_args_list
        assert calls[0].kwargs["first_tick"] is True
        assert calls[1].kwargs["first_tick"] is False


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

        with patch(f"{_SYNC}.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
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

        with patch(f"{_SYNC}.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
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

        with patch(f"{_SYNC}.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
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

        with patch(f"{_SYNC}.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_sleep.side_effect = StopAsyncIteration
            try:
                await media_sync_loop(sync_service, settings_service=settings_service)
            except StopAsyncIteration:
                pass

        # Both should have been attempted
        assert sync_service.sync.call_count == 2


@pytest.mark.unit
class TestGuarded:
    """Tests for guarded() crash handling, restart logic, and alerts."""

    @pytest.mark.asyncio
    async def test_single_crash_restarts_loop(self):
        """A single crash triggers a restart and the loop continues."""
        call_count = 0

        async def flaky_coro():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("boom")
            # Second call succeeds (returns normally)

        with patch(f"{_GUARDED}.asyncio.sleep", new_callable=AsyncMock):
            await guarded("test_task", flaky_coro)

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_backoff_timing_doubles(self):
        """Backoff doubles on each consecutive crash: 1, 2, 4, 8..."""
        call_count = 0
        sleep_values = []

        async def always_crash():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("boom")

        async def capture_sleep(seconds):
            sleep_values.append(seconds)

        with patch(f"{_GUARDED}.asyncio.sleep", side_effect=capture_sleep):
            await guarded("test_task", always_crash, max_restarts_per_hour=4)

        # 4 crashes = 4 sleeps before giving up on the 5th
        assert sleep_values == [1, 2, 4, 8]

    @pytest.mark.asyncio
    async def test_backoff_caps_at_max(self):
        """Backoff never exceeds _MAX_BACKOFF_SECONDS (60s)."""
        sleep_values = []

        async def always_crash():
            raise RuntimeError("boom")

        async def capture_sleep(seconds):
            sleep_values.append(seconds)

        with patch(f"{_GUARDED}.asyncio.sleep", side_effect=capture_sleep):
            await guarded("test_task", always_crash, max_restarts_per_hour=8)

        # 1, 2, 4, 8, 16, 32, 60, 60
        assert all(s <= _MAX_BACKOFF_SECONDS for s in sleep_values)
        assert sleep_values[-1] == _MAX_BACKOFF_SECONDS

    @pytest.mark.asyncio
    async def test_max_restart_cap_gives_up(self):
        """After max_restarts_per_hour crashes, guarded() stops and logs CRITICAL."""
        call_count = 0

        async def always_crash():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("relentless")

        with (
            patch(f"{_GUARDED}.asyncio.sleep", new_callable=AsyncMock),
            patch(f"{_GUARDED}.logger") as mock_logger,
        ):
            await guarded("test_task", always_crash, max_restarts_per_hour=3)

        # 3 crashes recorded, then on the 4th crash it hits the cap
        # (first crash doesn't check cap until after recording)
        # Actually: crash 1 records, crash 2 records, crash 3 records,
        # crash 4 sees len==3 >= max==3 and gives up
        assert call_count == 4

        # The final CRITICAL log should mention "exhausted"
        critical_calls = mock_logger.critical.call_args_list
        final_msg = critical_calls[-1][0][0]
        assert "exhausted" in final_msg

    @pytest.mark.asyncio
    async def test_counter_resets_after_stable_period(self):
        """After _STABLE_PERIOD_SECONDS of uptime, restart counter resets."""
        call_count = 0

        async def crash_then_stable_then_crash():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("first crash")
            if call_count == 2:
                # Simulate long stable run — we'll fake time.monotonic
                return  # clean exit after "stable" run
            # Won't reach here

        monotonic_seq = [
            0.0,  # loop_started_at for call 1
            1.0,  # now after crash 1 (run_duration=1s, not stable)
            100.0,  # loop_started_at for call 2 (after sleep)
            500.0,  # won't be used (clean exit)
        ]
        mono_idx = 0

        def fake_monotonic():
            nonlocal mono_idx
            val = monotonic_seq[mono_idx]
            mono_idx += 1
            return val

        with (
            patch(f"{_GUARDED}.asyncio.sleep", new_callable=AsyncMock),
            patch(f"{_GUARDED}.time.monotonic", side_effect=fake_monotonic),
        ):
            await guarded("test_task", crash_then_stable_then_crash)

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_stable_run_resets_backoff(self):
        """A long stable run resets backoff back to initial value."""
        call_count = 0
        sleep_values = []

        async def crash_stable_crash():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("boom")

        async def capture_sleep(seconds):
            sleep_values.append(seconds)

        # Simulate: crash at t=1 (short run), crash at t=400 (long run > 300s),
        # then short crashes until cap is hit.
        # Each iteration calls monotonic twice: once for loop_started_at, once for now.
        # With max_restarts_per_hour=3, the cap is hit on the 5th crash attempt
        # (after 3 timestamps recorded post-reset, the 4th post-reset crash gives up).
        # Actually: crash1 records (pre-reset), crash2 resets+records (1 in deque),
        # crash3 records (2 in deque), crash4 records (3 in deque),
        # crash5 sees len==3 >= 3 and gives up.
        monotonic_seq = [
            0.0,  # loop_started_at call 1
            1.0,  # now after crash 1 (duration=1, not stable)
            2.0,  # loop_started_at call 2 (after backoff sleep)
            303.0,  # now after crash 2 (duration=301, stable! resets)
            304.0,  # loop_started_at call 3
            305.0,  # now after crash 3 (duration=1, not stable)
            306.0,  # loop_started_at call 4
            307.0,  # now after crash 4 (duration=1, not stable)
            308.0,  # loop_started_at call 5
            309.0,  # now after crash 5 (hits cap, gives up)
        ]
        mono_idx = 0

        def fake_monotonic():
            nonlocal mono_idx
            val = monotonic_seq[mono_idx]
            mono_idx += 1
            return val

        with (
            patch(f"{_GUARDED}.asyncio.sleep", side_effect=capture_sleep),
            patch(f"{_GUARDED}.time.monotonic", side_effect=fake_monotonic),
        ):
            await guarded("test_task", crash_stable_crash, max_restarts_per_hour=3)

        # First crash: backoff=1, second crash: stable resets so backoff=1 again,
        # third crash: backoff=2 (doubled from reset 1), fourth crash: backoff=4
        assert sleep_values[0] == _INITIAL_BACKOFF_SECONDS
        assert sleep_values[1] == _INITIAL_BACKOFF_SECONDS  # reset after stable
        assert sleep_values[2] == 2  # doubled from fresh reset

    @pytest.mark.asyncio
    async def test_cancelled_error_propagates(self):
        """CancelledError should propagate (for clean shutdown)."""

        async def cancelled_coro():
            raise asyncio.CancelledError()

        with pytest.raises(asyncio.CancelledError):
            await guarded("test_task", cancelled_coro, bot=AsyncMock())

    @pytest.mark.asyncio
    async def test_sends_telegram_alert_on_crash(self):
        """When bot is provided, sends crash alert to admin chat."""
        mock_bot = AsyncMock()
        call_count = 0

        async def crash_once():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("something broke")

        with patch(f"{_GUARDED}.settings") as mock_settings:
            mock_settings.ADMIN_TELEGRAM_CHAT_ID = -100999
            with patch(f"{_GUARDED}.asyncio.sleep", new_callable=AsyncMock):
                await guarded("scheduler", crash_once, bot=mock_bot)

        mock_bot.send_message.assert_called_once()
        call_kwargs = mock_bot.send_message.call_args.kwargs
        assert call_kwargs["chat_id"] == -100999
        assert "scheduler" in call_kwargs["text"]
        assert "something broke" in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_no_alert_when_bot_is_none(self):
        """When no bot provided, only logs."""
        call_count = 0

        async def crash_once():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("boom")

        with (
            patch(f"{_GUARDED}.logger"),
            patch(f"{_GUARDED}.asyncio.sleep", new_callable=AsyncMock),
        ):
            await guarded("test_task", crash_once, bot=None)

    @pytest.mark.asyncio
    async def test_alert_failure_does_not_prevent_restart(self):
        """If Telegram alert fails, the loop still restarts."""
        mock_bot = AsyncMock()
        mock_bot.send_message.side_effect = Exception("Telegram down")
        call_count = 0

        async def crash_once():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("original error")

        with (
            patch(f"{_GUARDED}.logger"),
            patch(f"{_GUARDED}.settings") as mock_settings,
            patch(f"{_GUARDED}.asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_settings.ADMIN_TELEGRAM_CHAT_ID = -100999
            await guarded("scheduler", crash_once, bot=mock_bot)

        # Loop restarted despite alert failure
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_exhausted_sends_critical_alert(self):
        """When restarts are exhausted, sends a 'permanently stopped' alert."""
        mock_bot = AsyncMock()

        async def always_crash():
            raise RuntimeError("persistent failure")

        with (
            patch(f"{_GUARDED}.settings") as mock_settings,
            patch(f"{_GUARDED}.asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_settings.ADMIN_TELEGRAM_CHAT_ID = -100999
            await guarded(
                "scheduler", always_crash, bot=mock_bot, max_restarts_per_hour=2
            )

        # Last alert should mention "permanently stopped"
        last_call = mock_bot.send_message.call_args_list[-1]
        assert "permanently stopped" in last_call.kwargs["text"]

    @pytest.mark.asyncio
    async def test_clean_exit_does_not_restart(self):
        """If the coroutine returns normally, guarded() returns without restart."""
        call_count = 0

        async def clean_coro():
            nonlocal call_count
            call_count += 1

        await guarded("test_task", clean_coro)
        assert call_count == 1


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

    def test_unstarted_loop_reported_as_starting_up(self):
        """Loops that never sent a heartbeat are alive with 'Starting up'."""
        result = get_loop_liveness()
        assert "scheduler" in result
        assert result["scheduler"]["alive"] is True
        assert "Starting up" in result["scheduler"]["message"]

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
