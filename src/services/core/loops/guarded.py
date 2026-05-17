"""Crash-guarded coroutine wrapper for background tasks with restart logic."""

import asyncio
import time
from collections import deque
from typing import Callable, Coroutine

from src.config.settings import settings
from src.utils.logger import logger

# Restart policy constants
_MAX_RESTARTS_PER_HOUR = 10
_HOUR_SECONDS = 3600
_INITIAL_BACKOFF_SECONDS = 1
_MAX_BACKOFF_SECONDS = 60
_STABLE_PERIOD_SECONDS = 300  # 5 minutes without crash resets counters


async def guarded(
    name: str,
    coro_factory: Callable[[], Coroutine],
    *,
    bot=None,
    max_restarts_per_hour: int = _MAX_RESTARTS_PER_HOUR,
) -> None:
    """Run a coroutine factory with automatic restart on crash.

    Restarts the loop with exponential backoff (1s, 2s, 4s, ... max 60s).
    Caps total restarts at max_restarts_per_hour within a rolling hour window.
    Resets backoff and counters after 5 minutes of stable operation.

    Args:
        name: Human-readable loop name for logging.
        coro_factory: Zero-arg callable returning a coroutine. Called on each
            restart to produce a fresh coroutine instance.
        bot: Optional Telegram bot instance for crash alerts.
        max_restarts_per_hour: Maximum restart attempts in a rolling hour window.
    """
    restart_timestamps: deque[float] = deque()
    backoff = _INITIAL_BACKOFF_SECONDS

    while True:
        loop_started_at = time.monotonic()
        try:
            await coro_factory()
            # Clean exit (loop returned normally) — done
            return
        except asyncio.CancelledError:
            raise  # let shutdown propagate
        except Exception as exc:
            now = time.monotonic()
            run_duration = now - loop_started_at

            # If the loop ran for longer than the stable period, reset state
            if run_duration >= _STABLE_PERIOD_SECONDS:
                restart_timestamps.clear()
                backoff = _INITIAL_BACKOFF_SECONDS

            # Prune restart timestamps older than 1 hour
            cutoff = now - _HOUR_SECONDS
            while restart_timestamps and restart_timestamps[0] < cutoff:
                restart_timestamps.popleft()

            # Check if we've exceeded the hourly restart cap
            if len(restart_timestamps) >= max_restarts_per_hour:
                logger.critical(
                    f"Background task '{name}' exhausted restart budget "
                    f"({max_restarts_per_hour} restarts in the last hour). "
                    f"Giving up.",
                    exc_info=True,
                )
                if bot:
                    await _send_alert(
                        bot,
                        name,
                        exc,
                        exhausted=True,
                        restarts=len(restart_timestamps),
                    )
                return

            # Log the crash and upcoming restart
            attempt = len(restart_timestamps) + 1
            logger.critical(
                f"Background task '{name}' crashed (restart {attempt}/{max_restarts_per_hour})",
                exc_info=True,
            )
            logger.warning(
                f"Restarting '{name}' in {backoff}s (attempt {attempt}/{max_restarts_per_hour})"
            )

            if bot:
                await _send_alert(bot, name, exc, exhausted=False, restarts=attempt)

            # Record this restart and apply backoff
            restart_timestamps.append(now)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, _MAX_BACKOFF_SECONDS)


async def _send_alert(
    bot, name: str, exc: Exception, *, exhausted: bool, restarts: int
) -> None:
    """Send crash alert to admin Telegram chat."""
    try:
        if exhausted:
            text = (
                f"\u26a0\ufe0f *Background task permanently stopped*\n\n"
                f"Task: `{name}`\n"
                f"Error: `{type(exc).__name__}: {str(exc)[:200]}`\n"
                f"Restarts exhausted ({restarts}). Manual intervention required."
            )
        else:
            text = (
                f"\u26a0\ufe0f *Background task crashed — restarting*\n\n"
                f"Task: `{name}`\n"
                f"Error: `{type(exc).__name__}: {str(exc)[:200]}`\n"
                f"Restart attempt: {restarts}/{_MAX_RESTARTS_PER_HOUR}"
            )
        await bot.send_message(
            chat_id=settings.ADMIN_TELEGRAM_CHAT_ID,
            text=text,
            parse_mode="Markdown",
        )
    except Exception:
        logger.error(f"Failed to send crash alert for '{name}'", exc_info=True)
