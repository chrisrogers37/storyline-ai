"""Logging configuration."""
import logging
import sys
from pathlib import Path
from typing import Optional
from src.config.settings import settings


def setup_logger(
    name: str = "storyline-ai",
    level: int = None,
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    Setup and configure a logger.

    Args:
        name: Logger name
        level: Logging level (defaults to settings.LOG_LEVEL)
        log_file: Path to log file (defaults to logs/app.log)

    Returns:
        Configured logger instance
    """
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Get or create logger
    logger_instance = logging.getLogger(name)

    # Set level
    if level is None:
        level = getattr(logging, settings.LOG_LEVEL)
    logger_instance.setLevel(level)

    # Avoid adding duplicate handlers
    if logger_instance.handlers:
        return logger_instance

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_format)

    # File handler
    if log_file is None:
        log_file = str(log_dir / "app.log")

    file_path = Path(log_file)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(file_path)
    file_handler.setLevel(logging.INFO)
    file_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_format)

    # Add handlers
    logger_instance.addHandler(console_handler)
    logger_instance.addHandler(file_handler)

    # Prevent propagation to root logger
    logger_instance.propagate = False

    return logger_instance


def get_logger(name: str = "storyline-ai") -> logging.Logger:
    """
    Get an existing logger or create a new one.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    logger_instance = logging.getLogger(name)
    if not logger_instance.handlers:
        return setup_logger(name)
    return logger_instance


# Default logger instance
logger = setup_logger()
