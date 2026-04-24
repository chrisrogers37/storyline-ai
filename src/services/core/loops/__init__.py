"""Background loop modules extracted from main.py.

Each loop runs as an asyncio task in the worker process. This package
organises them into focused, independently-testable modules while
main.py remains the thin wiring layer.

Import loop functions directly from their submodules to avoid
eagerly loading heavy dependencies (repositories, services):

    from src.services.core.loops.scheduler_loop import run_scheduler_loop
"""

# Lightweight modules only — no heavy service/repo imports
from src.services.core.loops.heartbeat import (
    LOOP_EXPECTED_INTERVALS,
    get_loop_liveness,
    loop_heartbeats,
    record_heartbeat,
)
from src.services.core.loops.lifecycle import (
    log_service_summary,
    session_state,
    validate_and_log_startup,
)

__all__ = [
    "LOOP_EXPECTED_INTERVALS",
    "get_loop_liveness",
    "log_service_summary",
    "loop_heartbeats",
    "record_heartbeat",
    "session_state",
    "validate_and_log_startup",
]
