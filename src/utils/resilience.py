"""Resilience utilities - circuit breaker, retry, and pool monitoring."""

import asyncio
import time
from enum import Enum
from typing import Optional

from telegram.error import RetryAfter, TimedOut, NetworkError

from src.utils.logger import logger


# ─────────────────────────────────────────────────────────────
# Circuit Breaker
# ─────────────────────────────────────────────────────────────


class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing — reject requests immediately
    HALF_OPEN = "half_open"  # Testing — allow one request through


class CircuitBreaker:
    """Simple circuit breaker for database operations.

    When consecutive failures exceed the threshold, the circuit "opens"
    and subsequent calls fail immediately instead of hanging on a dead
    connection for 30 seconds (the pool timeout).

    After the recovery timeout, the circuit enters "half-open" state
    and allows one request through. If it succeeds, the circuit closes;
    if it fails, it opens again.

    Usage:
        breaker = CircuitBreaker("neon_db", failure_threshold=3, recovery_timeout=30)

        if not breaker.allow_request():
            raise DatabaseUnavailableError("Circuit open — DB is down")

        try:
            result = do_db_operation()
            breaker.record_success()
            return result
        except Exception as e:
            breaker.record_failure()
            raise
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._last_state_change: float = time.monotonic()

    @property
    def state(self) -> CircuitState:
        """Get current state, auto-transitioning OPEN → HALF_OPEN when timeout expires."""
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                self._transition(CircuitState.HALF_OPEN)
        return self._state

    def allow_request(self) -> bool:
        """Check if a request should be allowed through."""
        current = self.state
        if current == CircuitState.CLOSED:
            return True
        if current == CircuitState.HALF_OPEN:
            return True  # Allow probe request
        return False  # OPEN — fail fast

    def record_success(self):
        """Record a successful operation. Resets failure count and closes circuit."""
        if self._state != CircuitState.CLOSED:
            logger.info(
                f"[CircuitBreaker:{self.name}] Circuit closed (recovery successful)"
            )
        self._failure_count = 0
        self._transition(CircuitState.CLOSED)

    def record_failure(self):
        """Record a failed operation. May open the circuit."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._state == CircuitState.HALF_OPEN:
            # Probe failed — reopen
            self._transition(CircuitState.OPEN)
            logger.warning(
                f"[CircuitBreaker:{self.name}] Circuit re-opened "
                f"(probe failed, waiting {self.recovery_timeout}s)"
            )
        elif self._failure_count >= self.failure_threshold:
            self._transition(CircuitState.OPEN)
            logger.warning(
                f"[CircuitBreaker:{self.name}] Circuit opened "
                f"({self._failure_count} consecutive failures, "
                f"waiting {self.recovery_timeout}s before retry)"
            )

    def _transition(self, new_state: CircuitState):
        if self._state != new_state:
            self._state = new_state
            self._last_state_change = time.monotonic()

    def get_status(self) -> dict:
        """Get circuit breaker status for monitoring."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "seconds_in_state": round(time.monotonic() - self._last_state_change, 1),
        }


# Global circuit breaker for the database
db_circuit_breaker = CircuitBreaker(
    "database",
    failure_threshold=5,
    recovery_timeout=30.0,
)


# ─────────────────────────────────────────────────────────────
# Telegram Message Edit Retry
# ─────────────────────────────────────────────────────────────


async def telegram_edit_with_retry(
    edit_func,
    *args,
    max_retries: int = 2,
    base_delay: float = 1.0,
    **kwargs,
) -> Optional[object]:
    """Retry a Telegram message edit on transient failures.

    Telegram's API can transiently fail with network timeouts,
    rate limits (RetryAfter), or connection drops. This wrapper
    retries with exponential backoff for those cases only.

    Non-retryable errors (BadRequest, message not found, etc.)
    are raised immediately.

    Args:
        edit_func: The async Telegram method to call (e.g., query.edit_message_caption)
        *args: Positional args to pass to edit_func
        max_retries: Maximum retry attempts (default 2, so 3 total attempts)
        base_delay: Base delay in seconds for exponential backoff
        **kwargs: Keyword args to pass to edit_func

    Returns:
        The result of edit_func, or None if all retries exhausted.
    """
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            return await edit_func(*args, **kwargs)
        except RetryAfter as e:
            # Telegram explicitly told us to wait
            last_error = e
            if attempt < max_retries:
                wait = e.retry_after + 0.5
                logger.warning(
                    f"Telegram RetryAfter: waiting {wait}s "
                    f"(attempt {attempt + 1}/{max_retries + 1})"
                )
                await asyncio.sleep(wait)
            else:
                logger.warning(f"Telegram RetryAfter exhausted retries: {e}")
        except (TimedOut, NetworkError) as e:
            # Transient network issue
            last_error = e
            if attempt < max_retries:
                delay = base_delay * (2**attempt)
                logger.warning(
                    f"Telegram {type(e).__name__}, retrying in {delay}s "
                    f"(attempt {attempt + 1}/{max_retries + 1}): {e}"
                )
                await asyncio.sleep(delay)
            else:
                logger.warning(
                    f"Telegram edit failed after {max_retries + 1} attempts: {e}"
                )
        except Exception:
            # Non-retryable (BadRequest, Forbidden, etc.) — raise immediately
            raise

    # All retries exhausted — log and return None
    logger.error(
        f"Telegram edit gave up after {max_retries + 1} attempts: {last_error}"
    )
    return None


# ─────────────────────────────────────────────────────────────
# Connection Pool Monitoring
# ─────────────────────────────────────────────────────────────


def get_pool_status() -> dict:
    """Get SQLAlchemy connection pool statistics.

    Returns a dict with pool utilization info that can be logged
    periodically to spot exhaustion before it causes freezes.
    """
    from src.config.database import engine

    pool = engine.pool
    return {
        "pool_size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "utilization_pct": round(
            (pool.checkedout() / max(pool.size() + pool.overflow(), 1)) * 100, 1
        ),
    }


def log_pool_status():
    """Log pool status at appropriate level based on utilization."""
    status = get_pool_status()
    utilization = status["utilization_pct"]

    if utilization >= 90:
        logger.warning(f"DB pool near exhaustion: {status}")
    elif utilization >= 70:
        logger.info(f"DB pool elevated usage: {status}")
    else:
        logger.debug(f"DB pool status: {status}")

    return status
