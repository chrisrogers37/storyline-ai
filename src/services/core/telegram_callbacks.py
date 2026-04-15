"""Telegram callback handlers - thin facade over focused handler modules.

Delegates to:
- telegram_callbacks_core: shared utilities (locking, sessions, DB ops)
- telegram_callbacks_queue: queue action handlers (posted, skipped, rejected)
- telegram_callbacks_admin: admin handlers (batch approve, resume, reset)

This facade preserves the original public API so that TelegramService and
all tests work without changes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.services.core.telegram_callbacks_admin import TelegramCallbackAdminHandlers
from src.services.core.telegram_callbacks_core import TelegramCallbackCore
from src.services.core.telegram_callbacks_queue import TelegramCallbackQueueHandlers

if TYPE_CHECKING:
    from src.services.core.telegram_service import TelegramService


class TelegramCallbackHandlers:
    """Handles queue action callback buttons in Telegram.

    Manages posted/skipped/rejected/resume/reset callback flows.
    Uses composition: receives a TelegramService reference for shared state.

    This is a thin facade that delegates to focused handler modules.
    """

    def __init__(self, service: TelegramService):
        self.service = service
        self._core = TelegramCallbackCore(service)
        self._queue = TelegramCallbackQueueHandlers(service, self._core)
        self._admin = TelegramCallbackAdminHandlers(service, self._core)

    # -- Core utilities (exposed for tests that access them directly) --

    async def _safe_locked_callback(
        self, queue_id, query, callback_name, error_msg, coro
    ):
        return await self._core._safe_locked_callback(
            queue_id, query, callback_name, error_msg, coro
        )

    def _shared_session(self):
        return self._core._shared_session()

    def _create_history_params(self, queue_id, queue_item, user, status, success):
        return self._core._create_history_params(
            queue_id, queue_item, user, status, success
        )

    def _execute_complete_db_ops(self, queue_id, queue_item, user, status, success):
        return self._core._execute_complete_db_ops(
            queue_id, queue_item, user, status, success
        )

    def _execute_reject_db_ops(self, queue_id, queue_item, user):
        return self._core._execute_reject_db_ops(queue_id, queue_item, user)

    def _refresh_repo_sessions(self):
        return self._core._refresh_repo_sessions()

    # -- Queue action handlers --

    async def complete_queue_action(
        self, queue_id, user, query, status, success, caption, callback_name
    ):
        return await self._queue.complete_queue_action(
            queue_id, user, query, status, success, caption, callback_name
        )

    async def _do_complete_queue_action(
        self, queue_id, user, query, status, success, caption, callback_name
    ):
        return await self._queue._do_complete_queue_action(
            queue_id, user, query, status, success, caption, callback_name
        )

    async def handle_posted(self, queue_id, user, query):
        return await self._queue.handle_posted(queue_id, user, query)

    async def handle_skipped(self, queue_id, user, query):
        return await self._queue.handle_skipped(queue_id, user, query)

    async def handle_back(self, queue_id, user, query):
        return await self._queue.handle_back(queue_id, user, query)

    async def handle_reject_confirmation(self, queue_id, user, query):
        return await self._queue.handle_reject_confirmation(queue_id, user, query)

    async def handle_cancel_reject(self, queue_id, user, query):
        return await self._queue.handle_cancel_reject(queue_id, user, query)

    async def handle_rejected(self, queue_id, user, query):
        return await self._queue.handle_rejected(queue_id, user, query)

    async def _do_handle_rejected(self, queue_id, user, query):
        return await self._queue._do_handle_rejected(queue_id, user, query)

    # -- Admin handlers --

    async def handle_batch_approve(self, data, user, query):
        return await self._admin.handle_batch_approve(data, user, query)

    async def handle_batch_approve_cancel(self, data, user, query):
        return await self._admin.handle_batch_approve_cancel(data, user, query)

    async def handle_resume_callback(self, action, user, query):
        return await self._admin.handle_resume_callback(action, user, query)

    async def _do_resume_callback(self, action, user, query):
        return await self._admin._do_resume_callback(action, user, query)

    async def handle_reset_callback(self, action, user, query):
        return await self._admin.handle_reset_callback(action, user, query)
