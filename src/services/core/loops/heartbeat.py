"""Loop liveness tracking via heartbeat timestamps.

Each background loop calls record_heartbeat() on every tick. The health
check endpoint calls get_loop_liveness() to detect stalled loops.
"""

from time import time


# Expected intervals (seconds) per loop, used to detect stalls.
LOOP_EXPECTED_INTERVALS: dict[str, int] = {
    "scheduler": 60,
    "lock_cleanup": 3600,
    "cloud_cleanup": 3600,
    "media_sync": 300,
    "transaction_cleanup": 30,
}

# In-memory heartbeat timestamps (UTC). Updated by loops, read by health check.
loop_heartbeats: dict[str, float] = {}


def record_heartbeat(name: str) -> None:
    """Record a heartbeat for a named loop."""
    loop_heartbeats[name] = time()


def get_loop_liveness() -> dict[str, dict]:
    """Return liveness status for all registered loops.

    Each loop is reported as alive or stale based on whether its last
    heartbeat is within 2x its expected interval. Loops that have never
    sent a heartbeat are reported as not started.
    """
    now = time()
    result = {}
    for name, expected_interval in LOOP_EXPECTED_INTERVALS.items():
        last_beat = loop_heartbeats.get(name)
        if last_beat is None:
            result[name] = {
                "alive": False,
                "message": "Not started",
                "expected_interval_s": expected_interval,
            }
        else:
            elapsed = now - last_beat
            threshold = expected_interval * 2
            alive = elapsed <= threshold
            result[name] = {
                "alive": alive,
                "last_heartbeat_s_ago": round(elapsed),
                "expected_interval_s": expected_interval,
                "message": "OK"
                if alive
                else f"Stale ({round(elapsed)}s since last tick)",
            }
    return result
