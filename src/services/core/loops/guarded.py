"""Crash-guarded coroutine wrapper for background tasks."""

import asyncio
from typing import Coroutine

from src.config.settings import settings
from src.utils.logger import logger


async def guarded(name: str, coro: Coroutine, *, bot=None) -> None:
    """Run a coroutine and log (not propagate) unhandled exceptions.

    Prevents a crash in one background loop from killing the whole worker
    via asyncio.gather(). When a bot instance is provided, sends a Telegram
    alert to the admin chat so crashes aren't silent.
    """
    try:
        await coro
    except asyncio.CancelledError:
        raise  # let shutdown propagate
    except Exception as exc:
        logger.critical(f"Background task '{name}' crashed", exc_info=True)

        if bot:
            try:
                await bot.send_message(
                    chat_id=settings.ADMIN_TELEGRAM_CHAT_ID,
                    text=(
                        f"\u26a0\ufe0f *Background task crashed*\n\n"
                        f"Task: `{name}`\n"
                        f"Error: `{type(exc).__name__}: {str(exc)[:200]}`\n\n"
                        f"Worker is still running but this loop has stopped."
                    ),
                    parse_mode="Markdown",
                )
            except Exception:
                logger.error(f"Failed to send crash alert for '{name}'", exc_info=True)
