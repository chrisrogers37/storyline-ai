"""Tests for the per-tenant scheduler and media sync loops in main.py."""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from src.main import run_scheduler_loop, media_sync_loop


@pytest.mark.unit
class TestSchedulerLoop:
    """Tests for run_scheduler_loop multi-tenant behavior."""

    @pytest.mark.asyncio
    async def test_scheduler_loop_iterates_over_active_chats(self):
        """Scheduler loop processes each active chat's queue independently."""
        posting_service = Mock()
        posting_service.process_pending_posts = AsyncMock(
            return_value={"processed": 1, "telegram": 1, "failed": 0}
        )
        posting_service.cleanup_transactions = Mock()

        chat1 = Mock(telegram_chat_id=-100111)
        chat2 = Mock(telegram_chat_id=-100222)
        settings_service = Mock()
        settings_service.get_all_active_chats.return_value = [chat1, chat2]

        # First sleep (end of iteration 1) raises to break loop after one pass
        with patch("src.main.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_sleep.side_effect = StopAsyncIteration
            try:
                await run_scheduler_loop(posting_service, settings_service)
            except StopAsyncIteration:
                pass

        # Should have called process_pending_posts for each chat
        assert posting_service.process_pending_posts.call_count == 2
        posting_service.process_pending_posts.assert_any_call(telegram_chat_id=-100111)
        posting_service.process_pending_posts.assert_any_call(telegram_chat_id=-100222)

    @pytest.mark.asyncio
    async def test_scheduler_loop_falls_back_to_global_when_no_tenants(self):
        """Scheduler loop uses global posting when no active chats exist."""
        posting_service = Mock()
        posting_service.process_pending_posts = AsyncMock(
            return_value={"processed": 0, "telegram": 0, "failed": 0}
        )
        posting_service.cleanup_transactions = Mock()

        settings_service = Mock()
        settings_service.get_all_active_chats.return_value = []

        with patch("src.main.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_sleep.side_effect = StopAsyncIteration
            try:
                await run_scheduler_loop(posting_service, settings_service)
            except StopAsyncIteration:
                pass

        # Should fall back to global (no telegram_chat_id)
        posting_service.process_pending_posts.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_scheduler_loop_falls_back_when_no_settings_service(self):
        """Scheduler loop uses global posting when settings_service is None."""
        posting_service = Mock()
        posting_service.process_pending_posts = AsyncMock(
            return_value={"processed": 0, "telegram": 0, "failed": 0}
        )
        posting_service.cleanup_transactions = Mock()

        with patch("src.main.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_sleep.side_effect = StopAsyncIteration
            try:
                await run_scheduler_loop(posting_service, None)
            except StopAsyncIteration:
                pass

        # Should fall back to global (no telegram_chat_id)
        posting_service.process_pending_posts.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_scheduler_loop_skips_failed_tenant(self):
        """One tenant's error does not prevent other tenants from processing."""
        posting_service = Mock()
        posting_service.process_pending_posts = AsyncMock(
            side_effect=[
                Exception("Chat 1 failed"),
                {"processed": 1, "telegram": 1, "failed": 0},
            ]
        )
        posting_service.cleanup_transactions = Mock()

        chat1 = Mock(telegram_chat_id=-100111)
        chat2 = Mock(telegram_chat_id=-100222)
        settings_service = Mock()
        settings_service.get_all_active_chats.return_value = [chat1, chat2]

        with patch("src.main.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_sleep.side_effect = StopAsyncIteration
            try:
                await run_scheduler_loop(posting_service, settings_service)
            except StopAsyncIteration:
                pass

        # Both chats should have been attempted despite chat1 failing
        assert posting_service.process_pending_posts.call_count == 2


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
