"""Operation state management for Telegram callback handlers.

Manages per-queue-item asyncio locks and cancellation flags that prevent
duplicate actions from rapid button clicks and allow terminal actions
(Posted/Skip/Reject) to abort background tasks like auto-posting.
"""

import asyncio


class OperationStateManager:
    """Manages per-queue-item operation locks and cancellation flags."""

    def __init__(self):
        self._operation_locks: dict[str, asyncio.Lock] = {}
        self._cancel_flags: dict[str, asyncio.Event] = {}

    def get_lock(self, queue_id: str) -> asyncio.Lock:
        """Get or create an asyncio lock for a queue item."""
        if queue_id not in self._operation_locks:
            self._operation_locks[queue_id] = asyncio.Lock()
        return self._operation_locks[queue_id]

    def get_cancel_flag(self, queue_id: str) -> asyncio.Event:
        """Get or create a cancellation flag for a queue item."""
        if queue_id not in self._cancel_flags:
            self._cancel_flags[queue_id] = asyncio.Event()
        return self._cancel_flags[queue_id]

    def cleanup(self, queue_id: str):
        """Remove lock and cancel flag after operation completes."""
        self._operation_locks.pop(queue_id, None)
        self._cancel_flags.pop(queue_id, None)
